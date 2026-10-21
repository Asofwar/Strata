// src/kernels/attn_window_parity.cpp - STRATA_ATTN_WINDOW (a verify window's dense decode attention, each K/V chunk read
// once for all of the window's queries) against the default decode kernel and an FP64 host reference (GPU, synthetic,
// no model).
//
// Qwen3.6 / qwen35moe geometry: 2 KV heads x 8 query heads, head_dim 256, int8 K/V (one fp16 scale per 64 values), page
// size 4 with a shuffled page table (and, in one case, pages that are not resident: those cells are masked). A window of
// T queries attends causally: query i sees cells [0, n - T + 1 + i). For each context and T it prints the max and mean
// error of both kernels against FP64 (relative to the largest output value) and the window kernel against the default.
// Usage: attn_window_parity [prec 0..3] [cells,cells,...] [small]   (STRATA_ATTN_WINDOW_PREC; default 0, and
// 2048,66000,200000; small: the windows also through STRATA_ATTN_WINDOW_SMALL's kernel)
#include "strata/kernels/f16_bits.hpp"
#include "strata/kernels/kv_q8.hpp"
#include "strata/kernels/qsa.hpp"
#include "strata/kernels/qsa_decode_attn.hpp"
#include "strata/kernels/qsa_prompt_attn.hpp"

#include <cuda_runtime.h>

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <random>
#include <string>
#include <thread>
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
float h2f(uint16_t h) {   // fp16 bits to float
    const uint32_t s = (uint32_t) (h >> 15) << 31, e = (h >> 10) & 0x1f, m = h & 0x3ff;
    uint32_t bits;
    if (e == 0) {
        if (m == 0) bits = s;
        else { float f = std::ldexp((float) m, -24); std::memcpy(&bits, &f, 4); bits |= s; }
    } else if (e == 31) bits = s | 0x7f800000u | (m << 13);
    else bits = s | ((e + 112) << 23) | (m << 13);
    float f;
    std::memcpy(&f, &bits, 4);
    return f;
}

constexpr int D = 256, NKV = 2, PER = 8, NH = NKV * PER, PS = 4, G64 = D / k::KV_Q8_GROUP;

struct Case {
    int cells;
    bool holes;      // some pages not resident (masked)
    float q_mul;     // q's scale: 1 = flat attention, 4 = peaked
};
bool g_small = false;   // argv[3] == "small": the windows also through STRATA_ATTN_WINDOW_SMALL's kernel

// FP64 reference of a window: a thread per (query, head)
std::vector<double> reference(int T, const std::vector<int>& width, const std::vector<int32_t>& table, const std::vector<int8_t>& kq,
                              const std::vector<int8_t>& vq, const std::vector<uint16_t>& ks, const std::vector<uint16_t>& vs,
                              const std::vector<float>& q) {
    std::vector<double> ref((size_t) T * NH * D);
    std::vector<std::thread> th;
    for (int qi = 0; qi < T; ++qi)
        for (int h = 0; h < NH; ++h)
            th.emplace_back([&, qi, h] {
                const int kvh = h / PER;
                const float* qq = &q[((size_t) qi * NH + h) * D];
                std::vector<double> sc(width[qi]);
                double m = -1e300;
                for (int x = 0; x < width[qi]; ++x) {
                    const int pg = table[x / PS];
                    if (pg < 0) { sc[x] = -1e300; continue; }
                    const size_t row = ((size_t) pg * NKV + kvh) * PS + x % PS;
                    double acc = 0;
                    for (int g = 0; g < G64; ++g) {
                        double part = 0;
                        for (int d = g * 64; d < g * 64 + 64; ++d) part += (double) qq[d] * kq[row * D + d];
                        acc += part * h2f(ks[row * G64 + g]);
                    }
                    sc[x] = acc / 16.0;
                    m = std::max(m, sc[x]);
                }
                std::vector<double> o(D, 0.0);
                double l = 0;
                for (int x = 0; x < width[qi]; ++x) {
                    if (sc[x] <= -1e299) continue;
                    const double pr = std::exp(sc[x] - m);
                    l += pr;
                    const size_t row = ((size_t) table[x / PS] * NKV + kvh) * PS + x % PS;
                    for (int d = 0; d < D; ++d) o[d] += pr * vq[row * D + d] * h2f(vs[row * G64 + d / 64]);
                }
                for (int d = 0; d < D; ++d) ref[((size_t) qi * NH + h) * D + d] = l > 0 ? o[d] / l : 0.0;
            });
    for (auto& t : th) t.join();
    return ref;
}

// STRATA_ATTN_WINDOW_SMALL: the default decode kernel (a), the window kernel (b; not for a lone query at
// PREC 0) and the small kernel (c): errors against FP64 relative to the largest output, timings over 20 launches
void run_small(int T, int cells, const Case& c, const std::vector<int>& width, const std::vector<int32_t>& table,
               const std::vector<int8_t>& kq, const std::vector<int8_t>& vq, const std::vector<uint16_t>& ks,
               const std::vector<uint16_t>& vs, const std::vector<float>& q, const k::QsaAttnPools& pools, const float* d_q,
               const int32_t* d_ids, const int32_t* d_steps, const k::QsaShapes& s, float* d_scr, uint64_t stride, float* d_a,
               float* d_b, float* d_c, int prec) {
    auto launch = [&](int which) -> bool {   // 0 default, 1 window, 2 small
        if (which == 0) { k::qsa_decode_attn_batch(d_q, pools, d_ids, d_steps, cells, s, d_scr, d_a, T, nullptr); return true; }
        k::qsa_decode_attn_window_set_small(which == 2 ? 8 : 0);
        const bool ok = k::qsa_decode_attn_window(d_q, pools, d_steps, s, d_scr, stride * T, which == 2 ? d_c : d_b, T, nullptr);
        k::qsa_decode_attn_window_set_small(-1);
        return ok;
    };
    const bool has_b = !(prec == 0 && T == 1);
    launch(0);
    ck(cudaMemset(d_scr, 0xff, stride * T * 4), "poison");
    if (has_b && !launch(1)) { std::printf("FAIL window refused\n"); ++g_fail; return; }
    ck(cudaMemset(d_scr, 0xff, stride * T * 4), "poison");
    if (!launch(2)) { std::printf("FAIL small window refused\n"); ++g_fail; return; }
    ck(cudaDeviceSynchronize(), "sync");
    auto time = [&](int which) {
        cudaEvent_t e0, e1;
        cudaEventCreate(&e0); cudaEventCreate(&e1);
        cudaEventRecord(e0);
        for (int r = 0; r < 20; ++r) launch(which);
        cudaEventRecord(e1);
        cudaEventSynchronize(e1);
        float ms = 0;
        cudaEventElapsedTime(&ms, e0, e1);
        cudaEventDestroy(e0); cudaEventDestroy(e1);
        return ms * 1000.0f / 20.0f;
    };
    const float us_a = time(0), us_b = has_b ? time(1) : 0.0f, us_c = time(2);
    const size_t n_out = (size_t) T * NH * D;
    std::vector<float> a(n_out), b(n_out), cc(n_out);
    ck(cudaMemcpy(a.data(), d_a, n_out * 4, cudaMemcpyDeviceToHost), "a");
    if (has_b) ck(cudaMemcpy(b.data(), d_b, n_out * 4, cudaMemcpyDeviceToHost), "b");
    ck(cudaMemcpy(cc.data(), d_c, n_out * 4, cudaMemcpyDeviceToHost), "c");
    const std::vector<double> ref = reference(T, width, table, kq, vq, ks, vs, q);
    double max_ref = 0, ea = 0, eb = 0, ec = 0, ec_sum = 0, cb = 0;
    bool finite = true;
    for (size_t i = 0; i < n_out; ++i) {
        finite = finite && std::isfinite(cc[i]);
        max_ref = std::max(max_ref, std::fabs(ref[i]));
        ea = std::max(ea, std::fabs(a[i] - ref[i]));
        if (has_b) { eb = std::max(eb, std::fabs(b[i] - ref[i])); cb = std::max(cb, (double) std::fabs(cc[i] - b[i])); }
        ec = std::max(ec, std::fabs(cc[i] - ref[i]));
        ec_sum += std::fabs(cc[i] - ref[i]);
    }
    const double nrm = max_ref > 0 ? max_ref : 1.0;
    // the bar: 1e-3 of the output scale (the INT8 arithmetic: q and p * v_scale in 16 bits; the FP16 window is ~1e-3)
    const bool ok = finite && ec / nrm <= 1e-3;
    char wb[32] = "-";
    if (has_b) std::snprintf(wb, sizeof wb, "%.2e", eb / nrm);
    std::printf("%s cells %6d%s q x%.0f T=%d | vs fp64 max: default %.2e window %s small %.2e (mean %.2e) | small vs window %.2e | "
                "%8.1f us default, %7.1f window, %7.1f small\n",
                ok ? "PASS" : "FAIL", cells, c.holes ? " holes" : "      ", c.q_mul, T, ea / nrm, wb, ec / nrm,
                ec_sum / n_out / nrm, cb / nrm, us_a, us_b, us_c);
    std::fflush(stdout);
    if (!ok) ++g_fail;
}

void run(const Case& c, int n_q_max, int prec) {
    std::mt19937 rng(777u + (unsigned) c.cells + (c.holes ? 13u : 0u) + (unsigned) (c.q_mul * 10));
    std::normal_distribution<float> nd(0.0f, 1.0f);
    k::QsaShapes s = k::qsa_real_shapes();
    s.n_head = NH; s.n_head_kv = NKV; s.page_size = PS; s.idx_top_k = k::kDenseTopK;
    const int cells = c.cells, blocks = (cells + PS - 1) / PS;
    // a shuffled page table over twice the pages (as a long-running cache leaves it)
    std::vector<int32_t> table(blocks);
    {
        std::vector<int32_t> perm(2 * (size_t) blocks);
        for (size_t i = 0; i < perm.size(); ++i) perm[i] = (int32_t) i;
        std::shuffle(perm.begin(), perm.end(), rng);
        for (int b = 0; b < blocks; ++b) table[b] = perm[b];
        if (c.holes)
            for (int b = 0; b < blocks; ++b)
                if (rng() % 97 == 0) table[b] = -1;
    }
    const size_t pages = 2 * (size_t) blocks, rows = pages * NKV * PS;
    std::uniform_int_distribution<int> code(-127, 127);
    std::vector<int8_t> kq(rows * D), vq(rows * D);
    std::vector<uint16_t> ks(rows * G64), vs(rows * G64);
    for (auto& x : kq) x = (int8_t) code(rng);
    for (auto& x : vq) x = (int8_t) code(rng);
    for (auto& x : ks) x = k::f16_from_f32(0.005f + 0.01f * std::fabs(nd(rng)));
    for (auto& x : vs) x = k::f16_from_f32(0.005f + 0.01f * std::fabs(nd(rng)));
    // a few strongly attended cells: their keys follow query head 0 of each KV head (set below)
    std::vector<float> q((size_t) n_q_max * NH * D);
    for (auto& x : q) x = nd(rng) * c.q_mul;
    for (int hot = 0; hot < 16; ++hot) {
        const int cell = (int) (rng() % (unsigned) cells), b = cell / PS;
        if (table[b] < 0) continue;
        for (int kvh = 0; kvh < NKV; ++kvh) {
            const size_t row = ((size_t) table[b] * NKV + kvh) * PS + cell % PS;
            for (int d = 0; d < D; ++d) {
                const float want = q[(size_t) (kvh * PER) * D + d] / c.q_mul;
                kq[row * D + d] = (int8_t) std::max(-127, std::min(127, (int) std::lround(want * 40.0f)));
            }
        }
    }
    int32_t* d_table = dalloc<int32_t>(blocks);
    int8_t *dkq = dalloc<int8_t>(kq.size()), *dvq = dalloc<int8_t>(vq.size());
    uint16_t *dks = dalloc<uint16_t>(ks.size()), *dvs = dalloc<uint16_t>(vs.size());
    ck(cudaMemcpy(d_table, table.data(), blocks * 4, cudaMemcpyHostToDevice), "table");
    ck(cudaMemcpy(dkq, kq.data(), kq.size(), cudaMemcpyHostToDevice), "kq");
    ck(cudaMemcpy(dvq, vq.data(), vq.size(), cudaMemcpyHostToDevice), "vq");
    ck(cudaMemcpy(dks, ks.data(), ks.size() * 2, cudaMemcpyHostToDevice), "ks");
    ck(cudaMemcpy(dvs, vs.data(), vs.size() * 2, cudaMemcpyHostToDevice), "vs");
    k::QsaAttnPools pools;
    pools.k_q = dkq; pools.v_q = dvq; pools.k_scale = dks; pools.v_scale = dvs; pools.page_table = d_table;

    std::vector<int32_t> ids((size_t) n_q_max * cells);
    for (int i = 0; i < n_q_max; ++i)
        for (int x = 0; x < cells; ++x) ids[(size_t) i * cells + x] = x;
    int32_t* d_ids = dalloc<int32_t>(ids.size());
    ck(cudaMemcpy(d_ids, ids.data(), ids.size() * 4, cudaMemcpyHostToDevice), "ids");
    float* d_q = dalloc<float>(q.size());
    ck(cudaMemcpy(d_q, q.data(), q.size() * 4, cudaMemcpyHostToDevice), "q");
    const uint64_t stride = k::qsa_decode_attn_scratch_floats(cells, s);
    float* d_scr = dalloc<float>(stride * n_q_max);
    float *d_a = dalloc<float>(q.size()), *d_b = dalloc<float>(q.size()), *d_c = dalloc<float>(q.size());
    int32_t* d_steps = dalloc<int32_t>((size_t) n_q_max * k::kStepCount);

    for (int T = 1; T <= n_q_max; ++T) {
        std::vector<int32_t> steps((size_t) T * k::kStepCount);
        std::vector<int> width(T);
        for (int i = 0; i < T; ++i) {
            width[i] = cells - T + 1 + i;
            k::qsa_step_fill(&steps[(size_t) i * k::kStepCount], width[i] - 1, s);
            steps[(size_t) i * k::kStepCount + k::kStepWidth] = width[i];
        }
        ck(cudaMemcpy(d_steps, steps.data(), steps.size() * 4, cudaMemcpyHostToDevice), "steps");
        if (g_small) {   // STRATA_ATTN_WINDOW_SMALL: the small-window kernel, against the window kernel and FP64
            run_small(T, cells, c, width, table, kq, vq, ks, vs, q, pools, d_q, d_ids, d_steps, s, d_scr, stride, d_a, d_b, d_c, prec);
            continue;
        }
        if (prec == 0 && T == 1) {   // full precision takes windows of 2+ queries only: one query must be refused
            if (k::qsa_decode_attn_window(d_q, pools, d_steps, s, d_scr, stride, d_b, 1, nullptr)) {
                std::printf("FAIL cells %d T=1: the full-precision window took a lone query\n", cells);
                ++g_fail;
            }
            continue;
        }
        k::qsa_decode_attn_batch(d_q, pools, d_ids, d_steps, cells, s, d_scr, d_a, T, nullptr);
        ck(cudaMemset(d_scr, 0xff, stride * T * 4), "poison");
        if (!k::qsa_decode_attn_window(d_q, pools, d_steps, s, d_scr, stride * T, d_b, T, nullptr)) {
            std::printf("FAIL qsa_decode_attn_window refused (STRATA_ATTN_WINDOW unset, or not sm_80+?)\n");
            ++g_fail;
            return;
        }
        ck(cudaDeviceSynchronize(), "sync");
        // timing: 20 launches each
        auto time = [&](bool win) {
            cudaEvent_t e0, e1;
            cudaEventCreate(&e0); cudaEventCreate(&e1);
            cudaEventRecord(e0);
            for (int r = 0; r < 20; ++r) {
                if (win) k::qsa_decode_attn_window(d_q, pools, d_steps, s, d_scr, stride * T, d_b, T, nullptr);
                else k::qsa_decode_attn_batch(d_q, pools, d_ids, d_steps, cells, s, d_scr, d_a, T, nullptr);
            }
            cudaEventRecord(e1);
            cudaEventSynchronize(e1);
            float ms = 0;
            cudaEventElapsedTime(&ms, e0, e1);
            cudaEventDestroy(e0); cudaEventDestroy(e1);
            return ms * 1000.0f / 20.0f;
        };
        const float us_def = time(false), us_win = time(true);
        // the timing runs overwrote d_a / d_b with the same results (deterministic kernels)
        const size_t n_out = (size_t) T * NH * D;
        std::vector<float> a(n_out), b(n_out);
        ck(cudaMemcpy(a.data(), d_a, n_out * 4, cudaMemcpyDeviceToHost), "a");
        ck(cudaMemcpy(b.data(), d_b, n_out * 4, cudaMemcpyDeviceToHost), "b");
        // FP64 reference, a thread per (query, head)
        std::vector<double> ref(n_out);
        std::vector<std::thread> th;
        for (int qi = 0; qi < T; ++qi)
            for (int h = 0; h < NH; ++h)
                th.emplace_back([&, qi, h] {
                    const int kvh = h / PER;
                    const float* qq = &q[((size_t) qi * NH + h) * D];
                    std::vector<double> sc(width[qi]);
                    double m = -1e300;
                    for (int x = 0; x < width[qi]; ++x) {
                        const int pg = table[x / PS];
                        if (pg < 0) { sc[x] = -1e300; continue; }
                        const size_t row = ((size_t) pg * NKV + kvh) * PS + x % PS;
                        double acc = 0;
                        for (int g = 0; g < G64; ++g) {
                            double part = 0;
                            for (int d = g * 64; d < g * 64 + 64; ++d) part += (double) qq[d] * kq[row * D + d];
                            acc += part * h2f(ks[row * G64 + g]);
                        }
                        sc[x] = acc / 16.0;   // 1 / sqrt(256)
                        m = std::max(m, sc[x]);
                    }
                    std::vector<double> o(D, 0.0);
                    double l = 0;
                    for (int x = 0; x < width[qi]; ++x) {
                        if (sc[x] <= -1e299) continue;
                        const double p = std::exp(sc[x] - m);
                        l += p;
                        const size_t row = ((size_t) table[x / PS] * NKV + kvh) * PS + x % PS;
                        for (int d = 0; d < D; ++d) o[d] += p * vq[row * D + d] * h2f(vs[row * G64 + d / 64]);
                    }
                    for (int d = 0; d < D; ++d) ref[((size_t) qi * NH + h) * D + d] = l > 0 ? o[d] / l : 0.0;
                });
        for (auto& t : th) t.join();
        double max_ref = 0, ea_max = 0, ea_sum = 0, eb_max = 0, eb_sum = 0, ab_max = 0;
        bool finite = true;
        for (size_t i = 0; i < n_out; ++i) {
            if (!std::isfinite(b[i])) finite = false;
            max_ref = std::max(max_ref, std::fabs(ref[i]));
            const double ea = std::fabs(a[i] - ref[i]), eb = std::fabs(b[i] - ref[i]);
            ea_max = std::max(ea_max, ea); ea_sum += ea;
            eb_max = std::max(eb_max, eb); eb_sum += eb;
            ab_max = std::max(ab_max, (double) std::fabs(a[i] - b[i]));
        }
        const double nrm = max_ref > 0 ? max_ref : 1.0;
        // the bar: the window kernel within 4x the default's FP64 error (+ a floor), FP16 modes within 1e-2
        const double bar = prec == 0 ? std::max(4.0 * ea_max / nrm, 2e-5) : 1e-2;
        const bool ok = finite && eb_max / nrm <= bar;
        std::printf("%s cells %6d%s q x%.0f T=%d | default vs fp64 max %.2e mean %.2e | window vs fp64 max %.2e mean %.2e | "
                    "window vs default max %.2e | %8.1f us -> %7.1f us (x%.2f)\n",
                    ok ? "PASS" : "FAIL", cells, c.holes ? " holes" : "      ", c.q_mul, T, ea_max / nrm,
                    ea_sum / n_out / nrm, eb_max / nrm, eb_sum / n_out / nrm, ab_max / nrm, us_def, us_win,
                    us_win > 0 ? us_def / us_win : 0.0);
        std::fflush(stdout);
        if (!ok) ++g_fail;
    }
    cudaFree(d_table); cudaFree(dkq); cudaFree(dvq); cudaFree(dks); cudaFree(dvs); cudaFree(d_ids); cudaFree(d_q);
    cudaFree(d_scr); cudaFree(d_a); cudaFree(d_b); cudaFree(d_c); cudaFree(d_steps);
}
}  // namespace

int main(int argc, char** argv) {
    int n_dev = 0;
    if (cudaGetDeviceCount(&n_dev) != cudaSuccess || n_dev == 0) { std::printf("SKIP: no GPU\n"); return 0; }
    const int prec = argc > 1 ? std::atoi(argv[1]) : 0;
    std::vector<int> sizes = {2048, 66000, 200000};
    if (argc > 2) {
        sizes.clear();
        std::string a = argv[2];
        size_t p = 0;
        while (p < a.size()) {
            const size_t e = a.find(',', p);
            sizes.push_back(std::atoi(a.substr(p, e == std::string::npos ? std::string::npos : e - p).c_str()));
            if (e == std::string::npos) break;
            p = e + 1;
        }
    }
    // the switch is read once, at the first call
#if defined(_WIN32)
    _putenv_s("STRATA_ATTN_WINDOW", "1");
    _putenv_s("STRATA_ATTN_WINDOW_PREC", std::to_string(prec).c_str());
#else
    setenv("STRATA_ATTN_WINDOW", "1", 1);
    setenv("STRATA_ATTN_WINDOW_PREC", std::to_string(prec).c_str(), 1);
#endif
    g_small = argc > 3 && std::strcmp(argv[3], "small") == 0;
    std::printf("attn_window_parity: STRATA_ATTN_WINDOW_PREC=%d%s\n", prec, g_small ? ", small windows" : "");
    for (int cells : sizes) {
        run({cells, false, 1.0f}, g_small ? 8 : 6, prec);
        run({cells, false, 4.0f}, g_small ? 8 : 6, prec);
        if (cells <= 66000) run({cells, true, 4.0f}, g_small ? 8 : 6, prec);
    }
    std::printf(g_fail == 0 ? "attn_window_parity: PASS\n" : "attn_window_parity: %d FAIL\n", g_fail);
    return g_fail == 0 ? 0 : 1;
}
