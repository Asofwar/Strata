# Community benchmark on NVIDIA GeForce RTX 5080

Measured on 2026-10-13 with `tools/strata_bench.py` (suite 1, 3 runs per test, medians with ranges). Speeds are the engine's own timings; first-token times are measured by the client over HTTP. Speed only: no correctness check was run.

## Hardware and software

- GPU and VRAM: NVIDIA GeForce RTX 5080, 16 GiB VRAM
- CPU: Intel(R) Core(TM) i9-14900K (24 cores, 32 threads); installed RAM: 47.7 GiB; storage: not measured
- OS: Windows 11 (10.0.28000); GPU driver: 617.42; CUDA: not read
- Strata: project 0.1.43.1, commit f1e33fb9; engine 0.1.43.1
- Background workloads and power limits: not recorded

## Model and configuration

- Model and quantization: ornith-1.5-35b-a3b-abliterated-iq4_xs
- Context: 262144 tokens; parallel slots: 1
- Settings: the install's own configuration, unchanged; thinking off for the suite; temperature 0

```text
strata.exe --pack ornith-abl-iq4_xs --native Huihui-Ornith-1.5-35B-A3B-abliterated.i1-IQ4_XS.gguf --expert-profile expert-profile-qwen36.bin --expert-cache auto --prefill auto --spec 4 --mtp Huihui-Ornith-1.5-35B-A3B-abliterated.i1-IQ4_XS.gguf --mtp-draft-vocab draft_vocab_cyrillic.bin --max-context 262144 --kv int8 --expert-profile-save expert-profile-ornith-learned.bin --pcie-frac 0.00 --spec-min-p 0.50 --pool-workers 7 --adapt-every 1 --adapt-swaps 160 --adapt-decay 0.97
```

Environment of the config: `STRATA_ATTN_SPLITS=256`

## Method

Run by `python tools/strata_bench.py --long` against the HTTP API of a Strata server (started by the benchmark from the install configuration); model loading is not timed. One warm-up chat and a 1K prompt are discarded first. Every prompt starts with a unique tag, so the conversation cache cannot help the fresh-prompt tests.

- short chat: the three questions of `tools/ab_engine.py`, up to 100 new tokens, 3 runs
- 4K / 16K prompts: generated word lists sized by a calibration request, 24 new tokens, 3 fresh prompts each
- agent session: system prompt and four tools, then 5 turns that each add about 1500 words of a project file and continue from the model's own earlier answers (the way agent clients resend a conversation), 64 new tokens per turn, 3 sessions; the cache numbers come from the answer's usage (`cached_tokens`) and timings (`prompt_n`)
- concurrency (when run): N requests sent at the same moment, total tokens over the wall time of the burst, latency over all requests

## Results

| Configuration | Actual prompt tokens | Reused tokens | Generated tokens | Runs | Prompt tok/s median and range | Decode tok/s median and range | TTFT seconds median and range |
| --- | ---: | ---: | ---: | ---: | --- | --- | --- |
| short chat | 46 (43-51) | 0 | 100 (100-100) | 9 | not measured | 245.7 (192.7-270.1) | 0.14 (0.11-0.17) |
| 4K prompt, fresh | 4019 (4019-4019) | 0 (0-0) | 24 cap | 3 | 6300.4 (6021.9-6321.2) | not measured | 0.66 (0.66-0.69) |
| 16K prompt, fresh | 16058 (16058-16058) | 0 (0-0) | 24 cap | 3 | 6363.9 (6303.7-6464.1) | not measured | 2.55 (2.51-2.57) |
| 32K prompt, fresh | 32049 (32049-32049) | 0 (0-0) | 24 cap | 3 | 5219.6 (5199.6-5242.8) | not measured | 6.17 (6.15-6.20) |
| agent session, follow-up turns | 14564 (14538-14569) at the last turn | see below | up to 64 | 3 | see below | 245.9 (181.0-282.3) | 0.70 (0.48-0.82) |

Ranges are the lowest and highest of the runs; `Runs` counts requests that returned a token.

### Agent session (conversation cache)

Cache hit over the follow-up turns: 68.2 % (68.2-68.2); earlier-turn tokens read again per session: 270 (244-275) (earlier turns that the cache did not hold; the 13720 (13720-13720) new tokens of the files are read once); first turn (nothing cached) first token: 0.45 s (0.45-0.46).

| Turn (run 1) | Prompt tokens | Reused | Read | Prompt tok/s | First token (s) | Decode tok/s |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 609 | 0 | 609 | 1431.3 | 0.445 | 210.3 |
| 1 | 3779 | 602 | 3177 | 5340.4 | 0.619 | 181.0 |
| 2 | 5294 | 3772 | 1522 | 3204.2 | 0.488 | 230.6 |
| 3 | 8723 | 5287 | 3436 | 4777.5 | 0.744 | 269.8 |
| 4 | 11625 | 8716 | 2909 | 4130.9 | 0.73 | 229.2 |
| 5 | 14538 | 11618 | 2920 | 3683.6 | 0.821 | 245.9 |

Per-request data: `results.json`. Engine log lines from the start: `engine-log-excerpt.txt` (when this run started the server).

## Correctness and limitations

Not measured: this is a speed suite. The conversation uses the model's own replies, so token counts differ a little between runs. Machine details come from the server, `nvidia-smi`/`rocm-smi` and the OS; background load and power limits are not recorded. Total time of the suite: 51 s.
