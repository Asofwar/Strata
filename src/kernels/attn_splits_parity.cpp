// src/kernels/attn_splits_parity.cpp - STRATA_ATTN_SPLITS (split-K decode attention) against the default chunk path
// (GPU, synthetic, no model).
//
// For FP16 and INT8 pools, 8 and 12 query heads per KV head, the single-query and the batched entry points:
//   1. a selection that fits P chunks: the split-K form must give the default's output bit for bit;
//   2. a selection of many more chunks than P: the outputs must agree to float rounding (max |diff| / max |out|),
//      and the split-K scratch must be the P-partition size, not the chunk count's.
#include "strata/kernels/f16_bits.hpp"
#include "strata/kernels/kv_q8.hpp"
#include "strata/kernels/qsa.hpp"
#include "strata/kernels/qsa_decode_attn.hpp"

#include <cuda_runtime.h>

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <random>
#include <vector>

namespace k = strata::kernels;

namespace {
int g_fail = 0;
void ck(cudaError_t e, const char* w) {
    if (e != cudaSuccess) { std::fprintf(stderr, "%s: %s\n", w, cudaGetErrorString(e)); std::exit(2); }
}
template <typename T> T* dalloc(size_t n) {
    T* p = nullptr;
    ck(cudaMalloc(&p, n * sizeof(T) + 64), "malloc");
    ck(cudaMemset(p, 0, n * sizeof(T) + 64), "memset");
    return p;
}

constexpr int D = 256, PS = 4, PARTS = 64;

struct Pools {
    k::QsaAttnPools p;
    std::vector<void*> owned;
    ~Pools() { for (void* x : owned) cudaFree(x); }
};

// identity page table, cells x n_kv rows of random keys and values; int8 = codes + one fp16 scale per 64 values
void make_pools(Pools& out, int cells, int n_kv, bool int8, std::mt19937& rng) {
    std::normal_distribution<float> nd(0.0f, 1.0f);
    const int blocks = (cells + PS - 1) / PS;
    const size_t rows = (size_t) blocks * n_kv * PS;
    std::vector<int32_t> table(blocks);
    for (int b = 0; b < blocks; ++b) table[b] = b;
    int32_t* d_table = dalloc<int32_t>(blocks);
    ck(cudaMemcpy(d_table, table.data(), blocks * 4, cudaMemcpyHostToDevice), "table");
    out.owned.push_back(d_table);
    out.p.page_table = d_table;
    if (!int8) {
        std::vector<uint16_t> kh(rows * D), vh(rows * D);
        for (auto& x : kh) x = k::f16_from_f32(nd(rng));
        for (auto& x : vh) x = k::f16_from_f32(nd(rng));
        uint16_t *dk = dalloc<uint16_t>(kh.size()), *dv = dalloc<uint16_t>(vh.size());
        ck(cudaMemcpy(dk, kh.data(), kh.size() * 2, cudaMemcpyHostToDevice), "k");
        ck(cudaMemcpy(dv, vh.data(), vh.size() * 2, cudaMemcpyHostToDevice), "v");
        out.owned.push_back(dk); out.owned.push_back(dv);
        out.p.k_pool = dk; out.p.v_pool = dv;
    } else {
        std::uniform_int_distribution<int> code(-127, 127);
        std::vector<int8_t> kq(rows * D), vq(rows * D);
        std::vector<uint16_t> ks(rows * (D / k::KV_Q8_GROUP)), vs(ks.size());
        for (auto& x : kq) x = (int8_t) code(rng);
        for (auto& x : vq) x = (int8_t) code(rng);
        for (auto& x : ks) x = k::f16_from_f32(0.01f + 0.01f * std::fabs(nd(rng)));
        for (auto& x : vs) x = k::f16_from_f32(0.01f + 0.01f * std::fabs(nd(rng)));
        int8_t *dkq = dalloc<int8_t>(kq.size()), *dvq = dalloc<int8_t>(vq.size());
        uint16_t *dks = dalloc<uint16_t>(ks.size()), *dvs = dalloc<uint16_t>(vs.size());
        ck(cudaMemcpy(dkq, kq.data(), kq.size(), cudaMemcpyHostToDevice), "kq");
        ck(cudaMemcpy(dvq, vq.data(), vq.size(), cudaMemcpyHostToDevice), "vq");
        ck(cudaMemcpy(dks, ks.data(), ks.size() * 2, cudaMemcpyHostToDevice), "ks");
        ck(cudaMemcpy(dvs, vs.data(), vs.size() * 2, cudaMemcpyHostToDevice), "vs");
        out.owned.push_back(dkq); out.owned.push_back(dvq); out.owned.push_back(dks); out.owned.push_back(dvs);
        out.p.k_q = dkq; out.p.v_q = dvq; out.p.k_scale = dks; out.p.v_scale = dvs;
    }
}

// one configuration: `cells` of capacity, n_q queries each selecting its own width (all cells, minus a few per query)
void run(const char* name, int cells, int width, int n_kv, int per, bool int8, bool batched, int n_q, bool expect_bitwise) {
    std::mt19937 rng(1234u + (unsigned) cells + 7u * per + (int8 ? 1u : 0u));
    std::normal_distribution<float> nd(0.0f, 1.0f);
    k::QsaShapes s = k::qsa_real_shapes();
    s.n_head = (int64_t) n_kv * per; s.n_head_kv = n_kv; s.page_size = PS;
    s.idx_top_k = k::kDenseTopK;   // dense attention, as qwen35moe
    Pools pools;
    make_pools(pools, cells, n_kv, int8, rng);
    const int NH = n_kv * per;
    std::vector<float> q((size_t) n_q * NH * D);
    for (auto& x : q) x = nd(rng);
    std::vector<int32_t> ids((size_t) n_q * cells);
    for (int i = 0; i < n_q; ++i)
        for (int c = 0; c < cells; ++c) ids[(size_t) i * cells + c] = c;
    std::vector<int32_t> steps((size_t) n_q * k::kStepCount);
    for (int i = 0; i < n_q; ++i) {
        k::qsa_step_fill(&steps[(size_t) i * k::kStepCount], width - 1 - 3 * i, s);
        steps[(size_t) i * k::kStepCount + k::kStepWidth] = width - 3 * i;
    }
    float* d_q = dalloc<float>(q.size());
    int32_t* d_ids = dalloc<int32_t>(ids.size());
    int32_t* d_steps = dalloc<int32_t>(steps.size());
    ck(cudaMemcpy(d_q, q.data(), q.size() * 4, cudaMemcpyHostToDevice), "q");
    ck(cudaMemcpy(d_ids, ids.data(), ids.size() * 4, cudaMemcpyHostToDevice), "ids");
    ck(cudaMemcpy(d_steps, steps.data(), steps.size() * 4, cudaMemcpyHostToDevice), "steps");

    k::qsa_decode_attn_set_splits(0);
    const uint64_t scr_default = k::qsa_decode_attn_scratch_floats(cells, s);
    k::qsa_decode_attn_set_splits(PARTS);
    const uint64_t scr_split = k::qsa_decode_attn_scratch_floats(cells, s);
    const int64_t chunks = (cells + 63) / 64;
    const uint64_t want_split = (uint64_t) std::min<int64_t>(chunks, PARTS) * NH * (D + 2) + 64;
    if (scr_split != want_split || scr_default != (uint64_t) chunks * NH * (D + 2) + 64) {
        std::printf("FAIL %s: scratch %llu (split) / %llu (default), expected %llu\n", name,
                    (unsigned long long) scr_split, (unsigned long long) scr_default, (unsigned long long) want_split);
        ++g_fail;
    }
    float* d_scr = dalloc<float>(scr_default * n_q);
    float *d_a = dalloc<float>(q.size()), *d_b = dalloc<float>(q.size());
    auto call = [&](float* out) {
        if (batched) k::qsa_decode_attn_batch(d_q, pools.p, d_ids, d_steps, cells, s, d_scr, out, n_q, nullptr);
        else k::qsa_decode_attn_step(d_q, pools.p, d_ids, d_steps, cells, s, d_scr, out, nullptr);
    };
    k::qsa_decode_attn_set_splits(0);
    call(d_a);
    ck(cudaMemset(d_scr, 0xff, scr_default * n_q * 4 + 64), "poison");   // the split run must not read old partials
    k::qsa_decode_attn_set_splits(PARTS);
    call(d_b);
    ck(cudaDeviceSynchronize(), "sync");
    k::qsa_decode_attn_set_splits(0);
    const size_t n_out = (size_t) (batched ? n_q : 1) * NH * D;
    std::vector<float> a(n_out), b(n_out);
    ck(cudaMemcpy(a.data(), d_a, n_out * 4, cudaMemcpyDeviceToHost), "a");
    ck(cudaMemcpy(b.data(), d_b, n_out * 4, cudaMemcpyDeviceToHost), "b");
    size_t diff_bits = 0;
    double max_d = 0.0, max_a = 0.0;
    bool finite = true;
    for (size_t i = 0; i < n_out; ++i) {
        if (std::memcmp(&a[i], &b[i], 4) != 0) ++diff_bits;
        if (!std::isfinite(b[i])) finite = false;
        max_d = std::max(max_d, (double) std::fabs(a[i] - b[i]));
        max_a = std::max(max_a, (double) std::fabs(a[i]));
    }
    const double rel = max_a > 0 ? max_d / max_a : max_d;
    const bool ok = finite && (expect_bitwise ? diff_bits == 0 : rel < 2e-5);
    std::printf("%s %-34s cells %6d of %6d, chunks %5lld parts %d: %zu of %zu values differ, max rel %.3g, scratch %.2f -> %.2f MB/query\n",
                ok ? "PASS" : "FAIL", name, width, cells, (long long) chunks, PARTS, diff_bits, n_out, rel,
                scr_default * 4.0 / 1e6, scr_split * 4.0 / 1e6);
    if (!ok) ++g_fail;
    cudaFree(d_q); cudaFree(d_ids); cudaFree(d_steps); cudaFree(d_scr); cudaFree(d_a); cudaFree(d_b);
}
}  // namespace

int main() {
    int n_dev = 0;
    if (cudaGetDeviceCount(&n_dev) != cudaSuccess || n_dev == 0) { std::printf("SKIP: no GPU\n"); return 0; }
    for (int per : {8, 12})
        for (bool int8 : {false, true})
            for (bool batched : {false, true}) {
                char name[64];
                std::snprintf(name, sizeof name, "%s G=%d %s", int8 ? "int8" : "fp16", per, batched ? "batch x3" : "step");
                const int nq = batched ? 3 : 1;
                const int big = PARTS * 64 * 9 + 37;
                run(name, big, PARTS * 64 - 5, 2, per, int8, batched, nq, true);   // the selection fits P chunks: bit for bit
                run(name, big, big, 2, per, int8, batched, nq, false);             // 9-10 chunks per partition
            }
    std::printf(g_fail == 0 ? "attn_splits_parity: PASS\n" : "attn_splits_parity: %d FAIL\n", g_fail);
    return g_fail == 0 ? 0 : 1;
}
