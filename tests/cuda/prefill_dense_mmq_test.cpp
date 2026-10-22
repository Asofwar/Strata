// prefill_dense_mmq_test - STRATA_DENSE_MMQ=1 on CUDA: the prompt's dense GGUF projections through llama.cpp's int8 MMQ
// (Gemm::native_mmq) instead of dequantize + cuBLAS.
//   1. mmq::quantize_f16 (the FP16 activations quantized as they are) writes the same q8_1 blocks, byte for byte, as
//      mmq::f16_to_f32 followed by mmq::quantize, on rows with outliers, an all-zero row and FP16's extremes.
//   2. Gemm::native on Q8_0 weights with the switch on (several row slices of the 1,024-row activation buffer) against
//      double-precision products of the same dequantized weights with the FP16 activations, and with those activations
//      rounded to q8_1 on the host.  A tolerance test: it screens layout, stride and slicing errors, not the rounding.
// Exit 77 without a CUDA device.
#include "strata/prefill/gemm.hpp"
#include "strata/prefill/moe_mmq.hpp"

#include "ggml.h"

#include <cuda_fp16.h>
#include <cuda_runtime.h>

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
namespace mmq = strata::prefill::mmq;

void ck(cudaError_t e, const char* what) {
    if (e != cudaSuccess) throw std::runtime_error(std::string(what) + ": " + cudaGetErrorString(e));
}

struct Dev {
    void* p = nullptr;
    explicit Dev(size_t n) { ck(cudaMalloc(&p, n), "cudaMalloc"); ck(cudaMemset(p, 0, n), "cudaMemset"); }
    ~Dev() { cudaFree(p); }
    Dev(const Dev&) = delete;
    Dev& operator=(const Dev&) = delete;
    template <typename T> T* as() const { return (T*) p; }
};

uint16_t to_f16(float v) {
    const __half h = __float2half_rn(v);
    uint16_t u;
    std::memcpy(&u, &h, 2);
    return u;
}
float from_f16(uint16_t u) {
    __half h;
    std::memcpy(&h, &u, 2);
    return __half2float(h);
}

std::vector<uint16_t> activations(std::mt19937& rng, int64_t rows, int64_t cols, int64_t zero_row) {
    std::normal_distribution<float> nd(0.0f, 1.0f);
    std::uniform_int_distribution<int> pick(0, 199);
    std::vector<uint16_t> x((size_t) (rows * cols));
    for (int64_t r = 0; r < rows; ++r)
        for (int64_t c = 0; c < cols; ++c) {
            float v = nd(rng) * 0.5f;
            const int p = pick(rng);
            if (p == 0) v *= 300.0f;                              // outliers
            if (p == 1) v = (c & 1) ? 65504.0f : -65504.0f;      // FP16's extremes
            if (p == 2) v = 6.0e-8f;                             // a subnormal
            x[(size_t) (r * cols + c)] = r == zero_row ? to_f16(0.0f) : to_f16(v);
        }
    return x;
}

int quantizer_test() {
    std::mt19937 rng(1234);
    // 768: a row padded to pad512(cols) = 1024 (the zero-filled tail of the last block)
    const int64_t shapes[][2] = {{1, 512}, {37, 2048}, {1024, 4096}, {300, 512}, {5, 768}};
    int bad = 0;
    for (const auto& sh : shapes) {
        const int64_t rows = sh[0], cols = sh[1];
        const std::vector<uint16_t> x = activations(rng, rows, cols, rows > 2 ? 2 : -1);
        const size_t qb = mmq::q8_bytes(rows, cols);
        Dev dx(x.size() * 2), dxf((size_t) (rows * cols) * 4), da(qb), db(qb);
        ck(cudaMemcpy(dx.p, x.data(), x.size() * 2, cudaMemcpyHostToDevice), "upload x");
        if (!mmq::quantize_f16(dx.as<uint16_t>(), da.p, GGML_TYPE_Q8_0, cols, rows, nullptr)) {
            std::printf("FAIL: quantize_f16 does not take Q8_0 (%lld x %lld)\n", (long long) rows, (long long) cols);
            return 1;
        }
        mmq::f16_to_f32(dx.as<uint16_t>(), dxf.as<float>(), rows * cols, nullptr);
        mmq::quantize(dxf.as<float>(), nullptr, db.p, GGML_TYPE_Q8_0, cols, cols, rows, nullptr);
        ck(cudaDeviceSynchronize(), "quantize");
        std::vector<uint8_t> a(qb), b(qb);
        ck(cudaMemcpy(a.data(), da.p, qb, cudaMemcpyDeviceToHost), "download a");
        ck(cudaMemcpy(b.data(), db.p, qb, cudaMemcpyDeviceToHost), "download b");
        size_t diff = 0;
        for (size_t i = 0; i < qb; ++i) diff += a[i] != b[i];
        std::printf("quantize_f16 %4lld x %4lld: %zu of %zu bytes differ from f16_to_f32 + quantize\n", (long long) rows,
                    (long long) cols, diff, qb);
        bad += diff != 0;
    }
    if (mmq::quantize_f16(nullptr, nullptr, GGML_TYPE_Q4_0, 512, 4, nullptr)) {
        std::printf("FAIL: quantize_f16 claims Q4_0 (another activation layout)\n");
        ++bad;
    }
    return bad;
}

int product_test() {
    std::mt19937 rng(99);
    const int64_t N = 384, K = 2048, T = 2500;   // T: three slices of the 1,024-row activation buffer
    std::normal_distribution<float> nd(0.0f, 0.02f);
    std::vector<float> wf((size_t) (N * K));
    for (float& v : wf) v = nd(rng);
    const size_t row_bytes = ggml_row_size(GGML_TYPE_Q8_0, K);
    std::vector<uint8_t> wq((size_t) N * row_bytes);
    ggml_quantize_chunk(GGML_TYPE_Q8_0, wf.data(), wq.data(), 0, N, K, nullptr);
    std::vector<float> wd((size_t) (N * K));
    ggml_get_type_traits(GGML_TYPE_Q8_0)->to_float(wq.data(), wd.data(), N * K);
    const std::vector<uint16_t> x = activations(rng, T, K, -1);
    // no extremes here: the product of a 65504 activation is not what this part checks
    std::vector<uint16_t> xs(x);
    for (uint16_t& u : xs) if (std::fabs(from_f16(u)) > 1000.0f) u = to_f16(1.0f);

    cudaStream_t s = nullptr;
    ck(cudaStreamCreate(&s), "stream");
    strata::prefill::Gemm g;
    std::string err;
    // the scratch the prompt path gives (room for 1,024 FP32 activation rows: native_mmq's full slice)
    if (!g.init(s, std::max<int64_t>(N * K, 2 * K * 1024), err)) {
        std::printf("FAIL: Gemm::init: %s\n", err.c_str());
        return 1;
    }
    Dev dx(xs.size() * 2), dw(wq.size()), dy((size_t) (T * N) * 4);
    ck(cudaMemcpy(dx.p, xs.data(), xs.size() * 2, cudaMemcpyHostToDevice), "upload x");
    ck(cudaMemcpy(dw.p, wq.data(), wq.size(), cudaMemcpyHostToDevice), "upload w");
    g.native(dx.as<uint16_t>(), GGML_TYPE_Q8_0, dw.p, dy.as<float>(), T, N, K);
    ck(cudaStreamSynchronize(s), "native");
    std::vector<float> y((size_t) (T * N));
    ck(cudaMemcpy(y.data(), dy.p, y.size() * 4, cudaMemcpyDeviceToHost), "download y");
    // two references in FP64: the FP16 activations as they are (what the rounding costs), and the activations rounded
    // the way quantize_mmq_q8_1 rounds them (d = amax / 127 per 32 values, q = round(x * 127 / amax)) - against that one
    // only the FP32 sums and the odd value next to a rounding boundary differ (the kernel's 127 / amax is a fast-math
    // division: RTX 5080, 1.0e-5 overall and 3.8e-4 in the worst row), so a layout, stride or slicing error (O(1)) stands out
    std::vector<double> xq((size_t) (T * K));
    for (int64_t t = 0; t < T; ++t)
        for (int64_t b = 0; b < K; b += 32) {
            float amax = 0.0f;
            for (int64_t k = b; k < b + 32; ++k) amax = std::max(amax, std::fabs(from_f16(xs[(size_t) (t * K + k)])));
            const float d_inv = 127.0f / amax, d = 1.0f / d_inv;
            for (int64_t k = b; k < b + 32; ++k)
                xq[(size_t) (t * K + k)] = amax > 0.0f ? (double) std::roundf(from_f16(xs[(size_t) (t * K + k)]) * d_inv) * d : 0.0;
        }
    double se[2] = {}, sr[2] = {}, worst[2] = {};
    for (int64_t t = 0; t < T; ++t) {
        double re[2] = {}, rr[2] = {};
        for (int64_t n = 0; n < N; ++n) {
            double ref[2] = {};
            for (int64_t k = 0; k < K; ++k) {
                ref[0] += (double) from_f16(xs[(size_t) (t * K + k)]) * wd[(size_t) (n * K + k)];
                ref[1] += xq[(size_t) (t * K + k)] * wd[(size_t) (n * K + k)];
            }
            for (int i = 0; i < 2; ++i) {
                const double e = (double) y[(size_t) (t * N + n)] - ref[i];
                re[i] += e * e;
                rr[i] += ref[i] * ref[i];
            }
        }
        for (int i = 0; i < 2; ++i) {
            se[i] += re[i];
            sr[i] += rr[i];
            if (rr[i] > 0) worst[i] = std::max(worst[i], std::sqrt(re[i] / rr[i]));
        }
    }
    const double rel0 = std::sqrt(se[0] / sr[0]), rel1 = std::sqrt(se[1] / sr[1]);
    std::printf("dense MMQ Q8_0 %lld x %lld, %lld rows: rel. L2 error %.2e (worst row %.2e) against the FP16 activations, "
                "%.2e (worst row %.2e) against them rounded to q8_1\n", (long long) N, (long long) K, (long long) T, rel0,
                worst[0], rel1, worst[1]);
    cudaStreamDestroy(s);
    if (!(rel1 < 1e-4 && worst[1] < 2e-3 && rel0 < 5e-2)) {
        std::printf("FAIL: dense MMQ error out of bounds\n");
        return 1;
    }
    return 0;
}
}  // namespace

int main() {
    int n = 0;
    if (cudaGetDeviceCount(&n) != cudaSuccess || n <= 0) {
        std::printf("SKIP: no CUDA device\n");
        return 77;
    }
#if defined(_WIN32)
    _putenv_s("STRATA_DENSE_MMQ", "1");
#else
    setenv("STRATA_DENSE_MMQ", "1", 1);
#endif
    try {
        const int bad = quantizer_test() + product_test();
        std::printf(bad ? "FAILED\n" : "OK\n");
        return bad ? 1 : 0;
    } catch (const std::exception& e) {
        std::printf("FAIL: %s\n", e.what());
        return 1;
    }
}
