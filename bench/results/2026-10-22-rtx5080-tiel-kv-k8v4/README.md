# `--kv k8v4` against `--kv int8` on the fork's live setup (RTX 5080, Cyber-Tiel, 130K and 200K)

Question: at 200K the int8 K/V takes VRAM the expert cache could use. Does a smaller K/V (`--kv k8v4`: 8-bit K,
rotated 4-bit V) leave enough VRAM for more expert slots to make long-context decode faster, and what does it cost?

Answer: no. k8v4 leaves the expert cache 184 more slots at 130K and 298 at 200K, but it loses the int8-only
attention kernels the live config runs. Prompts take 7-9 times as long at 130K-200K (4 times at 64K) and decode is
36% (130K) and 58% (200K) slower. KL against int8 is 1.5-2.1 times the noise floor. Keep `--kv int8`.

## Setup

Measured on 2026-10-22, 17:10-17:50, one machine: RTX 5080 16 GB (PCIe 5.0 x8), i9-14900K, 47.7 GiB RAM, Windows 11.
Engine `E:\Projects\Strata-main\build\strata.exe` at 238b5125. Model Cyber-Tiel-Coder-35B-A3B-MTP UD-IQ4_XS from the
pack. The live server's config (`strata-tiel-main.json`: `--spec 4` with the MTP head, `--max-context 262144`,
`--kv-grow`, `--pcie-frac 0.00`, the adaptive tier, the conversation cache in RAM and its `STRATA_*` switches, among
them `STRATA_ATTN_WINDOW=1`, `STRATA_ATTN_WINDOW_SMALL=1`, `STRATA_PROMPT_ATTN_DENSE_IMMA=4`,
`STRATA_ARENA_WSLOCK=1`) without the conversation disk, plus `STRATA_DECODE_TIMING=1` in the speed arms. The engine
ran in `--serve` mode with a request file on stdin (`master.ps1`); the user's server was stopped for the run.

- Speed arms: a 2K warm-up, then 130K x3 and 200K x3, each read from scratch (token 0 changed per request, so the
  conversation cache reuses nothing), 192 greedy tokens each. Arm order: int8, k8v4, int8.
- KL arms: 64K, 130K and 200K of real text; the last 512 tokens go through the verify windows and every position's
  teacher-forced top-40 log-probabilities are written (`STRATA_LOGPOS`). `klana.py` compares them.
- The k8v4 speed arm was stopped after its first 200K request, and the planned second k8v4 speed arm and second
  int8 KL arm were skipped, to keep the downtime short once the gap was clear. So k8v4 has 3 requests at 130K but 1
  at 200K.

## Results

Medians; per-request values in brackets. "ms/window" is one verify window (several tokens). "CPU" is the host's time
on CPU experts per window. "Slots" is how many expert slots still hold experts once the K/V has grown.

| | int8 (2 arms, 6 requests) | k8v4 (1 arm) |
| --- | ---: | ---: |
| 130K prompt, s | 25.4 (25.0-25.7) | 186.5 (185.9-187.1) |
| 200K prompt, s | 48.9 (48.1-49.3) | 449.6 (1 request) |
| 130K decode, tok/s | 168.8 (150.9-177.4) | 107.9 (80.1, 107.9, 114.3) |
| 200K decode, tok/s | 180.1 (163.2-192.9) | 75.1 (1 request) |
| 130K ms/window, tokens/window | 9.41, 1.51 | 26.95, 2.91 |
| 200K ms/window, tokens/window | 11.21, 2.04 | 36.00, 2.70 |
| 130K / 200K GPU-reach wait, ms/window | 6.52 / 7.89 | 22.96 / 31.13 |
| 130K / 200K CPU, ms/window | 0.99 / 1.21 | 1.67 / 2.29 |
| 130K / 200K expert hit rate | 92.8% / 93.2% | 92.8% / 90.8% |
| K/V at 130K / 200K, GiB | 1.42 / 2.23 | 1.12 / 1.79 |
| Slots the K/V took at 130K / 200K (cumulative) | 875 / 1465 | 691 / 1167 |
| Slots holding experts at 130K / 200K | 6638, 6676 / 6048, 6086 | 6809 / 6333 |
| VRAM free after load (engine), MiB | 265, 223 | 292 |
| KL vs int8, last 511 tokens of 64K / 130K / 200K | noise floor 0.0053 / 0.0100 / 0.0147 | 0.0112 / 0.0155 / 0.0237 |
| Top-1 agreement with int8, 64K / 130K / 200K | | 96.9% / 93.0% / 93.0% |
| Perplexity of the last 511 tokens, 64K / 130K / 200K | 2.081 / 4.320 / 9.065 | 2.102 / 4.270 / 9.192 |

The KL noise floor is two int8 runs of the same harness from earlier sessions on this machine (0.0053/0.0100/0.0147;
the prefill-200k bench had 0.0058/0.0083/0.0139). The KL arms' prompt times agree with the speed arms: int8
12.9 / 28.1 / 51.8 s, k8v4 51.8 / 196.4 / 466.1 s at 64K / 130K / 200K.

The expert cache starts with 7,513 / 7,551 (int8) and 7,500 (k8v4) slots; the start count moves by a few dozen
between engine starts, so the gain is taken from the slots the K/V took. The hit rate moves 88-96% from request to
request in both arms (the first request after the K/V grows is the lowest), so the extra slots do not show in it.

## Why k8v4 is slower here

The fast paths of the live config take int8 K **and** int8 V only (code at 238b5125):

- Decode/verify: `qsa_decode_attn_window` (`src/kernels/cuda/qsa_prompt_attn.cu:3810`) returns false when the pools
  hold any Q4 data (`:3831`), so the verify window falls back to `qsa_decode_attn_batch`
  (`src/core/verify.cpp:1890-1898`): every query of the window reads the whole K/V again. GPU time per window grows
  from 6.5-7.9 ms to 23-31 ms. The MTP drafter keeps its own int8 ring, so drafting is unaffected.
- Prompt: the dense 8-queries-per-block kernels, `DENSE_IMMA=4` among them, run only when no pool is Q4
  (`qsa_prompt_attn.cu:3302`, `:3312`); k8v4 takes the per-query kernel (`:3327`): the whole prompt is 4 times
  slower at 64K and 7-9 times at 130K-200K, where attention is most of the prompt time.

Upstream measured k8v4 faster on an RTX 3090 (`docs/DETAILS.md`, engine 0.1.25), before these int8 kernels existed.

What k8v4 could win even with int8-speed kernels: the expert misses cost the int8 arm 0.99 / 1.21 ms of a 9.4 /
11.2 ms window at 130K / 200K (about 11%). 184 / 298 more slots (+2.8% / +4.9%, the coldest experts) can remove only
a small part of that, likely 1-2% of decode time, against a KL 1.5-2.1 times the noise floor. Writing window and
IMMA kernels for Q4 V does not pay on this setup.

## Not run

- **bench/eval-ru** (T 0.6) for k8v4: not run. It needs another downtime of about 20 minutes (the 128K needle
  prompts alone take about 3 minutes each at k8v4), and two int8 runs of it already differ by 3 of 128 replies
  (`results/tiel-t06.jsonl` 123, `results/t06b-iq4.jsonl` 120), so it would not resolve a KL difference of this
  size, and the speed result decides the question without it.
- **`--kv q4_0`**: not measured. By the code it misses the same kernels (Q4 K and V; the prompt path has its own
  per-query kernel, mode 4) and quantizes K too; upstream measured perplexity +8-12% on long documents
  (`bench/results/2026-09-27-kv-q4`).
- **A second k8v4 speed arm and 200K x3 for k8v4**: skipped, see Setup. The k8v4 numbers above are 3 requests at
  130K and 1 at 200K.

## Files

- `master.ps1`: the downtime batch (GPU lock, waits until the server is idle, stops it, runs the arms, restarts it).
- `mkreq.py`: the request files. The 130K/200K token files came from earlier benches' scratch folders and are not in
  the repository; any long text tokenized with the pack's tokenizer works.
- `summ.py runs/d1-*.log`: the table's speed rows. `klana.py <int8.lp> <k8v4.lp>`: the KL rows (the `.lp` files,
  1 MB each, are not kept).
- `runs/`: the engine logs, command lines and environment of each arm, and the batch timeline.
