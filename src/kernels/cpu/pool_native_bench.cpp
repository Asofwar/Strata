// src/kernels/cpu/pool_native_bench.cpp - the decode pool's phases per expert format, on the CPU alone.  No GPU, no
// model: the engine's own pool (ExpertPool::run_split_multi_native, the call a decode layer makes for its missed
// experts) on random expert blobs quantized by ggml-cpu, with a model's geometry.  Each "layer" takes E experts of nt
// tokens each from an arena far larger than the L3 (or, with --hot, from 4 experts that stay in the caches), and the
// host spins --gap-us between two layers as it does on the GPU's flags.  Prints the pool's three phases per layer
// (gate/up rows, the intermediate's quantization, down rows) and the weight bytes per second of each row phase: the
// decode pool line of STRATA_DECODE_TIMING, split by phase, without a model or a GPU.
//
//     pool_native_bench [--pairs iq3_s/iq4_xs,iq3_s/q6_K] [--geom 2048x512] [--experts 2,3] [--nt 1,2]
//                       [--workers 7] [--no-host] [--affinity all|p-cores|auto] [--tasks 0] [--mb 4096]
//                       [--layers 2000] [--gap-us 150] [--hot] [--reps 3]
//
// The env switches the engine reads (STRATA_IQ3S_MT1, STRATA_IQ_MT_MIN, ...) apply as they do in the engine.
#include "strata/kernels/cpu/expert_layout.hpp"
#include "strata/kernels/cpu/native_expert.hpp"
#include "strata/kernels/cpu/pool.hpp"

#include "ggml.h"
#include "ggml-cpu.h"

#if defined(_WIN32)
#ifndef NOMINMAX
#define NOMINMAX
#endif
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
#endif

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <memory>
#include <random>
#include <string>
#include <vector>

namespace cpu = strata::kernels::cpu;
using Clock = std::chrono::steady_clock;

namespace {

int type_of(const std::string& s) {
    for (int t = 0; t < GGML_TYPE_COUNT; ++t) {
        const char* n = ggml_type_name((ggml_type) t);
        if (n != nullptr && s == n) return t;
    }
    return -1;
}

std::vector<std::string> split(const std::string& s, char c = ',') {
    std::vector<std::string> v;
    size_t from = 0;
    for (;;) {
        const size_t k = s.find(c, from);
        v.push_back(s.substr(from, k == std::string::npos ? std::string::npos : k - from));
        if (k == std::string::npos) break;
        from = k + 1;
    }
    return v;
}

std::vector<int> ints(const std::string& s) {
    std::vector<int> v;
    for (const std::string& x : split(s)) v.push_back(std::atoi(x.c_str()));
    return v;
}

// one expert blob in the GGUF form (gate rows, up rows, down rows) from random weights quantized by ggml
// (ggml_quantize_chunk: ggml-cpu has no from_float for IQ3_S)
void make_blob(const cpu::NativeFmt& f, uint8_t* blob, std::mt19937& rng) {
    std::normal_distribution<float> nd(0.f, 0.02f);
    std::vector<float> w((size_t) (2 * f.n_ff * f.n_embd));
    for (auto& v : w) v = nd(rng);
    ggml_quantize_chunk((ggml_type) f.gu_type, w.data(), blob, 0, 2 * f.n_ff, f.n_embd, nullptr);
    for (int64_t i = 0; i < f.n_embd * f.n_ff; ++i) w[(size_t) i] = nd(rng);
    ggml_quantize_chunk((ggml_type) f.d_type, w.data(), blob + f.down_off, 0, f.n_embd, f.n_ff, nullptr);
}

double median(std::vector<double> v) {
    std::sort(v.begin(), v.end());
    return v.empty() ? 0.0 : v[v.size() / 2];
}

}  // namespace

int main(int argc, char** argv) {
    setvbuf(stdout, nullptr, _IONBF, 0);
    std::vector<std::string> pairs = split("iq3_s/iq4_xs,iq3_s/q6_K");
    std::vector<int> experts = {2, 3}, nts = {1, 2};
    int64_t n_embd = 2048, n_ff = 512;
    int workers = 7, tasks = 0, mb = 4096, layers = 2000, reps = 3;
    double gap_us = 150.0;
    bool host = true, hot = false;
    cpu::PoolAffinity aff = cpu::PoolAffinity::All;
    for (int i = 1; i < argc; ++i) {
        const std::string a = argv[i];
        const bool more = i + 1 < argc;
        if (a == "--pairs" && more) pairs = split(argv[++i]);
        else if (a == "--geom" && more) {
            const auto g = split(argv[++i], 'x');
            if (g.size() == 2) { n_embd = std::atoll(g[0].c_str()); n_ff = std::atoll(g[1].c_str()); }
        } else if (a == "--experts" && more) experts = ints(argv[++i]);
        else if (a == "--nt" && more) nts = ints(argv[++i]);
        else if (a == "--workers" && more) workers = std::atoi(argv[++i]);
        else if (a == "--no-host") host = false;
        else if (a == "--affinity" && more) {
            const std::string v = argv[++i];
            aff = v == "p-cores" ? cpu::PoolAffinity::PCores : v == "auto" ? cpu::PoolAffinity::Auto : cpu::PoolAffinity::All;
        } else if (a == "--tasks" && more) tasks = std::atoi(argv[++i]);
        else if (a == "--mb" && more) mb = std::atoi(argv[++i]);
        else if (a == "--layers" && more) layers = std::max(10, std::atoi(argv[++i]));
        else if (a == "--gap-us" && more) gap_us = std::atof(argv[++i]);
        else if (a == "--hot") hot = true;
        else if (a == "--reps" && more) reps = std::max(1, std::atoi(argv[++i]));
        else {
            std::fprintf(stderr, "usage: pool_native_bench [--pairs a/b,...] [--geom HxFF] [--experts 2,3] [--nt 1,2] "
                                 "[--workers 7] [--no-host] [--affinity all|p-cores|auto] [--tasks 0] [--mb 4096] "
                                 "[--layers 2000] [--gap-us 150] [--hot] [--reps 3]\n");
            return 2;
        }
    }
#if defined(_WIN32)
    {   // EcoQoS off, as serve/winjob.py does for the engine: a hidden console process may otherwise run on the E-cores
        PROCESS_POWER_THROTTLING_STATE s = {};
        s.Version = PROCESS_POWER_THROTTLING_CURRENT_VERSION;
        s.ControlMask = PROCESS_POWER_THROTTLING_EXECUTION_SPEED;
        s.StateMask = 0;
        (void) SetProcessInformation(GetCurrentProcess(), ProcessPowerThrottling, &s, sizeof s);
    }
#endif
    ggml_cpu_init();
    std::printf("pool_native_bench: %s (avx2 %d, avx512 %d, avxvnni %d), geometry %lldx%lld, %s, gap %.0f us\n",
                cpu::cpu_name().c_str(), (int) cpu::cpu_avx2_ok(), (int) cpu::cpu_avx512_ok(), (int) cpu::cpu_avxvnni_ok(),
                (long long) n_embd, (long long) n_ff, hot ? "4 hot experts" : "cold experts", gap_us);
    for (const std::string& pair : pairs) {
        const size_t slash = pair.find('/');
        const int gt = slash == std::string::npos ? -1 : type_of(pair.substr(0, slash));
        const int dt = slash == std::string::npos ? -1 : type_of(pair.substr(slash + 1));
        cpu::NativeFmt f;
        std::string err;
        if (gt < 0 || dt < 0 || !cpu::native_fmt(gt, dt, n_embd, n_ff, f, err)) {
            std::printf("%s: %s\n", pair.c_str(), err.empty() ? "unknown types" : err.c_str());
            continue;
        }
        if (n_ff > cpu::FF || n_embd > cpu::H) {
            std::printf("%s: geometry larger than the pool's buffers (%d x %d)\n", pair.c_str(), cpu::H, cpu::FF);
            continue;
        }
        ggml_quantize_init((ggml_type) gt);
        ggml_quantize_init((ggml_type) dt);
        const size_t E = hot ? 4 : std::max<size_t>(64, ((size_t) mb << 20) / f.bytes);
        std::unique_ptr<uint8_t[]> mem(new uint8_t[E * f.bytes + 4096]);
        uint8_t* blobs = (uint8_t*) (((uintptr_t) mem.get() + 4095) & ~(uintptr_t) 4095);
        {
            std::mt19937 rng(1234 + gt * 64 + dt);
            const size_t U = std::min<size_t>(4, E);   // 4 distinct experts copied over the arena: the bytes in DRAM are what is timed
            for (size_t e = 0; e < U; ++e) make_blob(f, blobs + e * f.bytes, rng);
            for (size_t e = U; e < E; ++e) std::memcpy(blobs + e * f.bytes, blobs + (e % U) * f.bytes, f.bytes);
        }
        std::mt19937 rng(77);
        std::normal_distribution<float> nd(0.f, 1.f);
        std::vector<std::vector<uint8_t>> xa(cpu::MAXT, std::vector<uint8_t>(cpu::kNativeActBytes));
        for (int t = 0; t < cpu::MAXT; ++t) {
            std::vector<float> x((size_t) n_embd);
            for (auto& v : x) v = nd(rng);
            cpu::native_quant_act(f, x.data(), xa[t].data());
        }
        const double gu_bytes = 2.0 * (double) f.up_off, dn_bytes = (double) (f.bytes - f.down_off);
        std::printf("\n%s: expert %.3f MB (gate/up %.3f, down %.3f), %zu experts in the arena (%.0f MB)\n", pair.c_str(),
                    f.bytes / 1e6, gu_bytes / 1e6, dn_bytes / 1e6, E, E * (double) f.bytes / 1e6);
        cpu::ExpertPool pool(workers, /*pin=*/true, host, aff, tasks);
        const int hc = cpu::planned_host_core(aff);
        cpu::ThreadAffinity prev;
        if (hc >= 0) prev = cpu::pin_current_thread(hc);
        std::printf("  pool: %d workers%s, host on CPU %d\n", pool.workers(), host ? " + the host" : "", hc);
        std::vector<float> out((size_t) cpu::ExpertPool::kMaxSplitMulti * cpu::MAXT * cpu::H);
        for (int ne : experts) {
            if (ne < 1 || ne > (int) E || ne > cpu::ExpertPool::kMaxSplitMulti) continue;
            for (int nt : nts) {
                if (nt < 1 || nt > cpu::MAXT) continue;
                std::vector<double> gu_us, q_us, dn_us, tot_us;
                const cpu::ExpertPool::PhaseStat ph0 = pool.phase_stats();
                const std::vector<cpu::ExpertPool::ThreadStat> th0 = pool.thread_stats();
                std::mt19937 pick(4242);
                std::vector<cpu::ExpertJobMulti> jobs((size_t) ne);
                for (int rep = 0; rep < reps; ++rep) {
                    const double g0 = pool.ms_multi_gu, q0 = pool.ms_multi_q, d0 = pool.ms_multi_down;
                    double wall = 0;
                    for (int l = -50; l < layers; ++l) {   // the first 50 are not timed
                        const double gb = pool.ms_multi_gu, qb = pool.ms_multi_q, db = pool.ms_multi_down;
                        for (int j = 0; j < ne; ++j) {
                            size_t e;
                            bool dup;
                            do {   // distinct experts, as a layer's are
                                e = pick() % E;
                                dup = false;
                                for (int k = 0; k < j; ++k) dup |= jobs[(size_t) k].blob == blobs + e * f.bytes;
                            } while (dup);
                            cpu::ExpertJobMulti& jb = jobs[(size_t) j];
                            jb = cpu::ExpertJobMulti{};
                            jb.blob = blobs + e * f.bytes;
                            jb.nt = nt;
                            for (int t = 0; t < nt; ++t) {
                                jb.nact[t] = xa[(size_t) ((j + t) % cpu::MAXT)].data();
                                jb.out[t] = out.data() + ((size_t) j * cpu::MAXT + (size_t) t) * cpu::H;
                            }
                        }
                        const Clock::time_point t0 = Clock::now();
                        pool.run_split_multi_native(f, jobs.data(), ne);
                        const Clock::time_point t1 = Clock::now();
                        if (l < 0) {   // drop the warm-up layers from the phase sums too
                            pool.ms_multi_gu = gb;
                            pool.ms_multi_q = qb;
                            pool.ms_multi_down = db;
                        } else {
                            wall += std::chrono::duration<double, std::milli>(t1 - t0).count();
                        }
                        while (std::chrono::duration<double, std::micro>(Clock::now() - t1).count() < gap_us) {}
                    }
                    gu_us.push_back((pool.ms_multi_gu - g0) * 1000.0 / layers);
                    q_us.push_back((pool.ms_multi_q - q0) * 1000.0 / layers);
                    dn_us.push_back((pool.ms_multi_down - d0) * 1000.0 / layers);
                    tot_us.push_back(wall * 1000.0 / layers);
                }
                const double g = median(gu_us), q = median(q_us), d = median(dn_us), w = median(tot_us);
                std::printf("  %d experts x %d tokens: per layer %.1f us = gate/up %.1f (%.1f GB/s) + quantize %.1f + down %.1f "
                            "(%.1f GB/s); %.1f GB/s over the row phases\n",
                            ne, nt, w, g, ne * gu_bytes / (g * 1e3), q, d, ne * dn_bytes / (d * 1e3),
                            ne * (gu_bytes + dn_bytes) / ((g + d) * 1e3));
                if (cpu::ExpertPool::stats_on()) {   // STRATA_POOL_STATS=1: where a row phase's wall goes (warm-up included)
                    const cpu::ExpertPool::PhaseStat ph1 = pool.phase_stats();
                    const std::vector<cpu::ExpertPool::ThreadStat> th1 = pool.thread_stats();
                    const double np = (double) std::max<int64_t>(1, ph1.phases - ph0.phases);
                    double arr = 0, tail = 0, busy = 0;
                    for (size_t k = 0; k < th1.size() && k < th0.size(); ++k) {
                        arr += (th1[k].arrive_ms - th0[k].arrive_ms) * 1000.0 / np;
                        tail += (th1[k].tail_ms - th0[k].tail_ms) * 1000.0 / np;
                        busy += (th1[k].ms - th0[k].ms) * 1000.0 / np;
                    }
                    const double nth = (double) std::max<size_t>(1, th1.size());
                    std::printf("    row phases: wall %.1f us, publish to last task %.1f us; per thread: arrival %.1f us, "
                                "in tasks %.1f us, waiting after its last task %.1f us\n",
                                (ph1.wall_ms - ph0.wall_ms) * 1000.0 / np, (ph1.done_ms - ph0.done_ms) * 1000.0 / np,
                                arr / nth, busy / nth, tail / nth);
                }
                std::fflush(stdout);
            }
        }
        if (hc >= 0) cpu::restore_thread_affinity(prev);
    }
    return 0;
}
