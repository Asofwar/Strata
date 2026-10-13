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
strata.exe --pack ornith-abl-iq4_xs --native Huihui-Ornith-1.5-35B-A3B-abliterated.i1-IQ4_XS.gguf --expert-profile expert-profile-qwen36.bin --expert-cache auto --prefill auto --spec 4 --mtp mtp-Ornith-1.5-35B-A3B-Abliterated-MTPv2-Q8_0.gguf --mtp-draft-vocab draft_vocab_cyrillic.bin --max-context 262144 --kv int8 --expert-profile-save expert-profile-ornith-learned.bin --pcie-frac 0.00 --spec-min-p 0.50 --pool-workers 7 --adapt-every 1 --adapt-swaps 160 --adapt-decay 0.97
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
| short chat | 46 (43-51) | 0 | 100 (100-100) | 9 | not measured | 242.8 (207.4-255.9) | 0.14 (0.11-0.16) |
| 4K prompt, fresh | 4019 (4019-4019) | 0 (0-0) | 24 cap | 3 | 6289.5 (6096.8-6306.3) | not measured | 0.66 (0.65-0.68) |
| 16K prompt, fresh | 16058 (16058-16058) | 0 (0-0) | 24 cap | 3 | 6474.0 (6375.0-6580.6) | not measured | 2.51 (2.47-2.55) |
| 32K prompt, fresh | 32049 (32049-32049) | 0 (0-0) | 24 cap | 3 | 5258.1 (5247.7-5260.7) | not measured | 6.13 (6.13-6.14) |
| agent session, follow-up turns | 14579 (14547-14587) at the last turn | see below | up to 64 | 3 | see below | 253.2 (196.3-268.1) | 0.72 (0.50-0.79) |

Ranges are the lowest and highest of the runs; `Runs` counts requests that returned a token.

### Agent session (conversation cache)

Cache hit over the follow-up turns: 68.2 % (68.2-68.2); earlier-turn tokens read again per session: 285 (253-293) (earlier turns that the cache did not hold; the 13720 (13720-13720) new tokens of the files are read once); first turn (nothing cached) first token: 0.47 s (0.46-0.47).

| Turn (run 1) | Prompt tokens | Reused | Read | Prompt tok/s | First token (s) | Decode tok/s |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 609 | 0 | 609 | 1393.9 | 0.457 | 284.0 |
| 1 | 3802 | 602 | 3200 | 5336.9 | 0.615 | 196.3 |
| 2 | 5317 | 3795 | 1522 | 3116.9 | 0.51 | 252.3 |
| 3 | 8754 | 5310 | 3444 | 4547.1 | 0.774 | 256.7 |
| 4 | 11656 | 8747 | 2909 | 4075.4 | 0.74 | 227.3 |
| 5 | 14579 | 11649 | 2930 | 3901.5 | 0.779 | 236.2 |

Per-request data: `results.json`. Engine log lines from the start: `engine-log-excerpt.txt` (when this run started the server).

## Correctness and limitations

Not measured: this is a speed suite. The conversation uses the model's own replies, so token counts differ a little between runs. Machine details come from the server, `nvidia-smi`/`rocm-smi` and the OS; background load and power limits are not recorded. Total time of the suite: 51 s.
