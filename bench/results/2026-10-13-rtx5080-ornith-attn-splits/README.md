# STRATA_ATTN_SPLITS and a transplanted MTP layer on an RTX 5080 (Ornith 1.5 35B A3B, IQ4_XS)

Measured on 2026-10-13, one machine: RTX 5080 16 GB (driver 617.42), i9-14900K, 47.7 GiB RAM, Windows 11. Model
Huihui-Ornith-1.5-35B-A3B-abliterated i1-IQ4_XS, `--max-context 262144 --kv int8 --spec 4`, the install's configuration
otherwise unchanged. Engine built from `ornith` at f1e33fb9 (the same binary in all three arms). Each arm is one server
start and one run of `tools/strata_bench.py --runs 3 --long`, in the order A, B, C.

- **A**: the default (no `STRATA_ATTN_SPLITS`), draft layer from the model file (IQ4_XS).
- **B**: `STRATA_ATTN_SPLITS=256`, the same draft layer.
- **C**: B plus `--mtp mtp-Ornith-1.5-35B-A3B-Abliterated-MTPv2-Q8_0.gguf` (gbuzhf, Q8_0, 1.99 GB) in place of the
  model file's draft layer.

| | A | B | C |
| --- | ---: | ---: | ---: |
| reserved for the dense attention at 262144 tokens | 393 MiB | 30 MiB | 30 MiB |
| verify window buffers | 441.8 MiB | 78.9 MiB | not logged |
| draft layer | 704 MiB | 704 MiB | 1128 MiB |
| expert cache slots | 5362 | 5378 | 5115 |
| VRAM free with everything loaded | 0 MiB (LOW warning) | 284 MiB | 273 MiB |
| short chat decode, tok/s | 244.2 (206.7-265.7) | 245.7 (192.7-270.1) | 242.8 (207.4-255.9) |
| 4K prompt, tok/s | 5522.9 (5497.2-5782.7) | 6300.4 (6021.9-6321.2) | 6289.5 (6096.8-6306.3) |
| 16K prompt, tok/s | 5983.1 (5975.1-6078.2) | 6363.9 (6303.7-6464.1) | 6474.0 (6375.0-6580.6) |
| 32K prompt, tok/s | 4848.8 (4841.5-4887.5) | 5219.6 (5199.6-5242.8) | 5258.1 (5247.7-5260.7) |
| agent session decode, tok/s | 226.2 (206.9-282.5) | 245.9 (181.0-282.3) | 253.2 (196.3-268.1) |
| drafts accepted, whole run | 1072 of 1604 (66.8%) | 1045 of 1591 (65.7%) | 1115 of 1671 (66.7%) |

Medians with the lowest and highest run. The split frees 363 MiB of reserve and removes the 0 MiB warning; the prompt
speeds were 6-14% higher with it, which one start per arm cannot attribute (the card in A ran with 0 MiB free, where
the driver can page). The decode ranges overlap in every row. The transplanted MTPv2 layer accepted the same share of
drafts as the model's own and costs 424 MiB more, 263 expert slots: not kept.

Not tested: outputs (speed suite only), contexts above 32K tokens, HIP/SYCL builds, more than one start per arm.
Per-arm reports, `results.json` and the engine's start lines are in `A/`, `B/` and `C/`.
