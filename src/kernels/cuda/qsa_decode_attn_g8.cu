// src/kernels/cuda/qsa_decode_attn_g8.cu - the decode attention for 8 query heads per KV head (Qwen3.6-35B-A3B,
// 16 / 2 on Flash-Next's engine path): qsa_decode_attn.cu built again with G = 8, every public name with a _g8
// suffix.  The G = 12 instance calls these for a model with 8 (see the top of qsa_decode_attn.cu).
#define STRATA_QDA_G 8
#include "qsa_decode_attn.cu"
