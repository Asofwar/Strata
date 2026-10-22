# Deeper verify windows on the fork's agent traffic (RTX 5080, Cyber-Tiel, 2026-10-22)

**Question.** Decode is about 73% of the live server's time, and drafts are accepted 74-85% of the time at
`--spec 4`. Do longer verify windows (a deeper MTP chain, longer prompt-lookup windows, or a depth chosen per window
by how sure the draft layer is) make real agent requests decode faster?

**Answer: no, keep `--spec 4 --spec-min-p 0.50`.**

- A deeper MTP chain (`--spec 5`, `6`, `8`) was never faster beyond the noise, and tended to be slower at 130K-200K.
- Windows deeper than 4 tokens only when the draft layer is sure (its chain probability at least 0.5 or 0.7): no gain
  over the control either. It was a request key in a test build and was not kept.
- Lookup windows up to 8 tokens with the MTP kept at 4 (`--spec 8 --mtp-max-t 4`, no code change): +2.5% at 12-19K
  (paired median 1.031, faster in 50 of 80 pairs), +1.9% at 34-88K, and nothing at 130K and 200K. The live server
  spends most of its decode at 80-150K, so it was not applied.

Why: each extra row of a window costs about as much as it brings. Forced window sizes at 49.6K tokens (table 4): 4 ->
5 tokens adds 1.93 ms (10.36 -> 12.29 ms): 0.96 ms more waiting for the GPU, 0.43 ms more host time (mostly CPU
experts) and 0.46 ms for one more MTP draft step. On the GPU (a profiled run) attention grows by 0.55 ms, because a
5-query window leaves the 4-query `STRATA_ATTN_WINDOW_SMALL` kernel, and the extra token's routed experts in VRAM by
0.50 ms. Each token after that costs about 0.7 ms more GPU time and 0.5 ms of drafting. At the decode's ~0.25 tokens
per ms the fifth token must bring about 0.48 tokens a window. It brings one only when all four drafts are accepted;
the drafts past the third are accepted 0.73-0.80 of the time when reached (the first three 0.79-0.86), so too few
windows get that far.

## Setup

- RTX 5080 16 GB (PCIe 5.0 x8), i9-14900K, 48 GB DDR5, Windows 11, CUDA 13.4. Cyber-Tiel-Coder-35B-A3B UD-IQ4_XS
  from the pack, the live server's config (`strata-tiel-main.json`: `--kv int8 --max-context 262144 --kv-grow`,
  `--spec-min-p 0.50`, the window/IMMA/WSLOCK switches) without the conversation disk tier. Engine: main a7ac6624 plus
  this commit's request keys, built in its own directory.
- One engine start per downtime with `--spec 8 --mtp-max-t 8`. Each request sets its caps with the new keys
  `spec_t=` (MTP window cap) and `spec_s=` (verify window cap), so all arms run interleaved in one engine. This
  removes the up-to-5% difference between engine starts. Each pair of caps learns in its own draft policy. Arms:
  `c4` 4/6 (= `--spec 4`), `s5` 5/7, `s6` 6/8, `s8` 8/8 (= `--spec 5`/`6`/`8`), `x8` 4/8 (= `--spec 8 --mtp-max-t 4`),
  `d5`/`d7` 8/8 with the not-kept gate. A start with `--spec 8 --mtp-max-t 4` and no keys printed caps 4/8, as `x8`.
- Replayed requests: real token lists from the live server's conversation disk tier. "mid" is a real agent
  conversation as it was (8 assistant turns at 34-88K: terminal, `patch`, `write_file`). "~130K" and "~200K" are 6 of
  those turns with a 72K or 142K-token `read_file` result (this repo's `generate.cpp`) inserted after the conversation's
  summary turn. "short" is 9 `write_file` / `edit_file` turns from 3 bench/agent-ru runs (12-19K). The engine writes
  the assistant turn: temperature 0.6 (the server's default), the same seed for every arm of a cut and repeat, at most
  512 tokens. One warm-up request per prompt read is not counted.
- Order: for each cut, every repeat runs every arm in a rotated order (reversed on odd repeats). Downtimes: d1 short +
  ~200K, 5 arms x 3 (18:48:49-18:58:36); d2 mid + ~130K, 7 arms x 3 (19:18:35-19:30:47); d3 short + mid, `c4`/`x8` x 6,
  then forced sizes and the start-up check (19:33:16-19:41:43); d4 ~130K + ~200K, `c4`/`x8` x 6 (19:42:54-19:50:56).
  38.5 minutes in all.
- Noise: the sampled answers differ between arms (length and content), so single requests spread by 20-40%. 9 of 867
  requests ran in slow stretches (the CPU pool's slow state, all arms in turn, 65-90 tok/s at 200K) and are left out:
  below 0.6 x their cut's median. "tok/s" is all tokens over all decode time; "paired" is the median ratio to the
  control request with the same cut, repeat and seed.

## 1. Every arm (d1 and d2, 3 repeats)

| context | arm (MTP / verify cap) | requests | tok/s | vs control (paired median, faster) | tokens / window | ms / window | window size | drafts accepted |
|---|---|---|---|---|---|---|---|---|
| short (12-19K) | `--spec 4` (control) (4 / 6) | 27 | 310.5 | - | 2.73 | 8.78 | 3.27 | 77.2% |
| short (12-19K) | `--spec 5` (5 / 7) | 27 | 305.8 | 0.991 (13/27) | 2.86 | 9.34 | 3.54 | 74.1% |
| short (12-19K) | `--spec 6` (6 / 8) | 27 | 304.7 | 1.019 (15/27) | 2.94 | 9.65 | 3.81 | 70.1% |
| short (12-19K) | `--spec 8` (8 / 8) | 27 | 307.5 | 1.008 (14/27) | 3.06 | 9.96 | 4.03 | 69.1% |
| short (12-19K) | lookup to 8, MTP 4 (4 / 8) | 27 | 319.4 | 1.029 (16/27) | 2.82 | 8.83 | 3.39 | 76.9% |
| mid (34-88K) | `--spec 4` (control) (4 / 6) | 24 | 234.2 | - | 2.20 | 9.39 | 2.71 | 70.7% |
| mid (34-88K) | `--spec 5` (5 / 7) | 24 | 242.6 | 1.034 (17/24) | 2.41 | 9.92 | 3.02 | 70.3% |
| mid (34-88K) | `--spec 6` (6 / 8) | 24 | 241.9 | 1.035 (16/24) | 2.51 | 10.39 | 3.18 | 70.2% |
| mid (34-88K) | `--spec 8` (8 / 8) | 24 | 235.5 | 1.017 (15/24) | 2.57 | 10.91 | 3.49 | 64.0% |
| mid (34-88K) | MTP to 8, past 4 only at chain p >= 0.5 (8 / 8) | 24 | 242.2 | 1.044 (15/24) | 2.48 | 10.22 | 3.13 | 70.1% |
| mid (34-88K) | MTP to 8, past 4 only at chain p >= 0.7 (8 / 8) | 24 | 243.5 | 1.095 (18/24) | 2.42 | 9.92 | 3.00 | 71.6% |
| mid (34-88K) | lookup to 8, MTP 4 (4 / 8) | 24 | 259.0 | 1.094 (19/24) | 2.55 | 9.86 | 3.12 | 74.2% |
| ~130K (110-136K) | `--spec 4` (control) (4 / 6) | 18 | 208.6 | - | 2.32 | 11.13 | 2.84 | 72.5% |
| ~130K (110-136K) | `--spec 5` (5 / 7) | 18 | 212.9 | 1.005 (10/18) | 2.53 | 11.88 | 3.20 | 70.4% |
| ~130K (110-136K) | `--spec 6` (6 / 8) | 18 | 207.3 | 0.958 (6/18) | 2.54 | 12.25 | 3.35 | 66.5% |
| ~130K (110-136K) | `--spec 8` (8 / 8) | 18 | 205.2 | 0.958 (8/18) | 2.58 | 12.58 | 3.49 | 64.4% |
| ~130K (110-136K) | MTP to 8, past 4 only at chain p >= 0.5 (8 / 8) | 18 | 207.5 | 0.945 (6/18) | 2.47 | 11.88 | 3.13 | 69.8% |
| ~130K (110-136K) | MTP to 8, past 4 only at chain p >= 0.7 (8 / 8) | 18 | 213.0 | 0.992 (8/18) | 2.48 | 11.62 | 3.08 | 72.1% |
| ~130K (110-136K) | lookup to 8, MTP 4 (4 / 8) | 18 | 216.2 | 0.990 (8/18) | 2.42 | 11.20 | 2.99 | 72.2% |
| ~200K (179-206K) | `--spec 4` (control) (4 / 6) | 17 | 189.8 | - | 2.23 | 11.74 | 2.71 | 72.4% |
| ~200K (179-206K) | `--spec 5` (5 / 7) | 15 | 185.3 | 0.962 (6/14) | 2.23 | 12.02 | 2.83 | 68.0% |
| ~200K (179-206K) | `--spec 6` (6 / 8) | 15 | 187.7 | 1.006 (8/14) | 2.43 | 12.94 | 3.17 | 66.8% |
| ~200K (179-206K) | `--spec 8` (8 / 8) | 18 | 184.4 | 0.983 (6/17) | 2.51 | 13.60 | 3.40 | 63.7% |
| ~200K (179-206K) | lookup to 8, MTP 4 (4 / 8) | 17 | 178.7 | 1.036 (11/17) | 2.34 | 13.10 | 2.86 | 72.8% |

The mid gains of d2 did not hold: in d3 the same mid cuts gave `x8` 0.985 (18/48) against the control. Table 2 pools
every downtime.

## 2. Control against lookup to 8 (every downtime: 3 + 6 repeats)

| context | arm (MTP / verify cap) | requests | tok/s | vs control (paired median, faster) | tokens / window | ms / window | window size | drafts accepted |
|---|---|---|---|---|---|---|---|---|
| short (12-19K) | `--spec 4` (control) (4 / 6) | 81 | 306.1 | - | 2.75 | 8.97 | 3.29 | 77.1% |
| short (12-19K) | lookup to 8, MTP 4 (4 / 8) | 80 | 313.8 | 1.031 (50/80) | 2.84 | 9.04 | 3.41 | 77.2% |
| mid (34-88K) | `--spec 4` (control) (4 / 6) | 72 | 238.6 | - | 2.33 | 9.77 | 2.85 | 72.7% |
| mid (34-88K) | lookup to 8, MTP 4 (4 / 8) | 72 | 243.2 | 1.003 (37/72) | 2.43 | 10.01 | 2.97 | 73.7% |
| ~130K (110-136K) | `--spec 4` (control) (4 / 6) | 54 | 212.5 | - | 2.37 | 11.16 | 2.87 | 74.1% |
| ~130K (110-136K) | lookup to 8, MTP 4 (4 / 8) | 54 | 214.1 | 0.986 (23/54) | 2.42 | 11.32 | 3.00 | 72.2% |
| ~200K (179-206K) | `--spec 4` (control) (4 / 6) | 53 | 191.2 | - | 2.30 | 12.02 | 2.79 | 73.2% |
| ~200K (179-206K) | lookup to 8, MTP 4 (4 / 8) | 53 | 188.0 | 1.010 (28/53) | 2.37 | 12.59 | 2.91 | 72.5% |

## 3. Tokens and time per window, by size (d2; t = tokens committed, ms = the round with the next draft)

| context | arm | MTP windows of 4 | 5 | 6 | 8 | lookup windows of 4 | 6 | 8 |
|---|---|---|---|---|---|---|---|---|
| mid (34-88K) | c4 | 3.09 t / 10.52 ms | - | - | - | 3.26 t / 11.06 ms | 4.42 t / 13.69 ms | - |
| mid (34-88K) | s8 | 2.98 t / 10.88 ms | 3.59 t / 12.96 ms | 3.87 t / 13.27 ms | 4.80 t / 16.11 ms | 2.37 t / 10.74 ms | 5.00 t / 15.19 ms | 6.10 t / 18.61 ms |
| mid (34-88K) | d7 | 2.96 t / 10.75 ms | 4.36 t / 12.66 ms | 5.43 t / 13.81 ms | 6.04 t / 14.39 ms | 2.05 t / 10.40 ms | 4.00 t / 13.91 ms | 6.96 t / 17.40 ms |
| mid (34-88K) | x8 | 3.19 t / 10.51 ms | - | - | - | 3.08 t / 10.87 ms | - | 6.60 t / 16.60 ms |
| ~130K (110-136K) | c4 | 3.14 t / 12.17 ms | - | - | - | 3.32 t / 12.64 ms | 4.78 t / 16.82 ms | - |
| ~130K (110-136K) | s8 | 2.99 t / 12.83 ms | 3.33 t / 14.89 ms | 4.04 t / 15.61 ms | 4.91 t / 18.05 ms | 3.17 t / 13.34 ms | 4.31 t / 16.72 ms | 6.44 t / 20.06 ms |
| ~130K (110-136K) | d7 | 3.00 t / 12.29 ms | 4.14 t / 14.98 ms | 5.20 t / 15.48 ms | 6.33 t / 16.75 ms | 2.41 t / 12.48 ms | 4.74 t / 16.68 ms | 6.41 t / 21.10 ms |
| ~130K (110-136K) | x8 | 3.17 t / 12.13 ms | - | - | - | 2.82 t / 12.37 ms | - | 6.25 t / 19.64 ms |

With the gate (`d7`) a window past 4 tokens is a sure one (5-8 tokens: 4.1-6.3 committed), but each still costs 2-4.6
ms more than a 4-token window, which commits about 3.0-3.1. A lookup window of 8 commits 6.3-6.6 tokens in 16.6-19.6
ms: that is why `x8` helps where long repeats are common (code written out again), and only there.

## 4. Where the time of a longer window goes (forced sizes: `spec_min_p=0`, every window the cap; mid cut at 49.6K)

Mean of 2 x 512 tokens per size; the GPU stages from a second engine with `STRATA_VERIFY_PROFILE=1` (it times every
stage, so its totals are a little higher).

| window size (forced) | ms / window | verify: GPU wait | host (CPU experts) | MTP draft | GPU: attention (10 layers) | GPU: VRAM expert hits |
|---|---|---|---|---|---|---|
| 4 | 10.36 | 6.91 | 1.03 (0.90) | 1.44 | 1.04 | 2.46 |
| 5 | 12.29 | 7.87 | 1.46 (1.27) | 1.90 | 1.59 | 2.96 |
| 6 | 13.72 | 8.63 | 1.46 (1.24) | 2.51 | 1.62 | 3.33 |
| 8 | 16.03 | 9.88 | 1.48 (1.19) | 3.44 | 1.69 | 4.06 |

MTP drafts accepted by depth when reached (d1, short / ~200K, `--spec 8`): 0.83 / 0.80 at the first draft, 0.78-0.84
at drafts 2-4, 0.74-0.80 at drafts 5-7. The draft layer stays good deep into the chain; the rows are what cost.

## The old adaptive branch

`asofwar/adaptive-spec-depth-0a3429` (`--spec-adaptive MIN:MAX`, a window cap moved by measured acceptance and round
time) was not ported. On Ornith it lost to `--spec 4` (its WIP note), and the measurements above show why no cap
policy can win here: at every context a deeper MTP window costs more per token than the 4-token window it replaces.
The draft policy that already chooses lookup windows by measured cost is the adaptive part that pays (`x8`).

## Not covered

Other cards and CPUs, Linux, `--spec-min-p` other than 0.50 with deeper caps, greedy requests, the pipelined decode
(`--pipeline-windows`), batch slots. The levers these numbers point to (not tried): a 5-8-query version of the small
attention kernel (0.55 ms at the 4 -> 5 step at 49.6K), and drafting that overlaps the verify window (0.48 ms per
draft step, serial today).

## Files

`workload.py` (with `convidx.py`, `turns.py`) builds the requests from the conversation disk tier's `.idx` token
lists (not included: they are private conversations). `bench.py` runs one downtime (GPU lock, server stop and
restore, the engine, the arms); `summ.py`, `cost.py` and `final.py` make the tables from `runs/*-results.jsonl`
(the generated tokens left out). `runs/*-engine.cmd.txt` are the engine command lines, `runs/timeline.log` the
downtimes.
