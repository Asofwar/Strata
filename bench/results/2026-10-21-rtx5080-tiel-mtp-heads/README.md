# Cyber-Tiel-Coder's draft layer against other quantizations of the same MTP head (RTX 5080)

Measured on 2026-10-21, one machine: RTX 5080 16 GB, i9-14900K, 47.7 GiB RAM, Windows 11. Engine `E:\Projects\Strata-main`
at 668083c7. Model Cyber-Tiel-Coder-35B-A3B-MTP UD-IQ4_XS, the live server's configuration (`--spec 4`,
`--mtp-draft-vocab draft_vocab_cyrillic.bin`, `--max-context 262144 --kv int8`, the adaptive tier, the conversation
cache in RAM, its `STRATA_*` switches) plus `--deterministic`, without the conversation disk. Requests through the HTTP
server, greedy (temperature 0), 384 output tokens at most, `--spec-min-p` per request (`strata_tune.spec_min_p`).

## Which heads exist

Every head found is the same trained head: Ornith-1.5's MTPv2 layer, which huihui-ai's abliterated checkpoint carries
and Cyber-Tiel (a further fine-tune) kept. The uploads differ only in how the layer is quantized.

| head | source | experts | projections | VRAM (the engine's line) |
| --- | --- | --- | --- | ---: |
| base | Cyber-Tiel-Coder UD-IQ4_XS, its own `blk.40` | Q3_K | Q8_0 | 378 MiB |
| q5k | gbuzhf CyberTiel-Calibrated MTPv2 25G-ICE, `blk.40` only | Q5_K | Q8_0 (`attn_k`/`attn_v` F16 -> Q8_0) | 576 MiB |
| q8 | gbuzhf `mtp-Ornith-1.5-35B-A3B-Abliterated-MTPv2-Q8_0.gguf` (from an MLX BF16 export) | Q8_0 | Q8_0 | 864 MiB |
| q2k | gbuzhf Huihui-Sangreal-MTP 19G-ICE (ICE 1.6), `blk.40` only | Q2_K | Q4_K (`attn_k`/`attn_v` F16 -> Q8_0) | does not load |

How that was checked (`tools/mtp_extract.py --target`): q5k's 20 tensors are byte-identical to base's except the three
expert tensors; its F16 `attn_k`/`attn_v`, re-quantized to Q8_0 by the tool, are byte-identical to base's. The norms of
q8 match base's to bf16 rounding (correlation 0.9999+, max difference 0.008), its Q8_0 projections byte for byte.
q2k's nine norms and routers are byte-identical to base's. q2k does not load: the engine's expert kernels take Q2_K
gate/up but not a Q2_K down (`the draft layer's experts are Q2_K/Q2_K, which this engine has no GPU kernels for`).
The head files were cut from the HF uploads by range reads (286 MiB and 580 MiB instead of 18.8 and 24.8 GB).

## Acceptance and decode speed (`main.jsonl`)

Six prompts (code, Russian and an agent request with three tools; 2.1-2.6K tokens, and the same three after a 127K-token
prefix of the engine's sources), 3 runs, `--spec-min-p` 0.5 and 0.75 alternated, one server start per head in the order
base, q5k, q8. All three got 6886 expert slots. Accepted / offered drafts summed over the runs; decode rate is the
server's `predicted_per_second`, median (min-max) of the 9 requests.

| head | context | p-min | accepted / offered | accepted | tokens per round | decode tok/s |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| base | 2K | 0.5 | 1785 / 2234 | 79.9% | 2.55 | 296.8 (220.8-333.6) |
| q5k | 2K | 0.5 | 1743 / 2114 | 82.5% | 2.63 | 326.7 (227.9-355.3) |
| q8 | 2K | 0.5 | 1746 / 2153 | 81.1% | 2.58 | 301.3 (250.4-341.7) |
| base | 2K | 0.75 | 1623 / 1788 | 90.8% | 2.31 | 290.9 (247.2-305.6) |
| q5k | 2K | 0.75 | 1608 / 1743 | 92.3% | 2.32 | 300.5 (253.3-326.9) |
| q8 | 2K | 0.75 | 1576 / 1705 | 92.4% | 2.28 | 312.3 (214.1-321.1) |
| base | 127K | 0.5 | 1816 / 2285 | 79.5% | 2.88 | 209.1 (173.6-240.9) |
| q5k | 127K | 0.5 | 1864 / 2346 | 79.5% | 2.84 | 218.7 (193.0-225.5) |
| q8 | 127K | 0.5 | 1823 / 2250 | 81.0% | 2.89 | 211.7 (196.7-250.4) |
| base | 127K | 0.75 | 1778 / 1940 | 91.6% | 2.76 | 209.8 (190.7-225.6) |
| q5k | 127K | 0.75 | 1834 / 2036 | 90.1% | 2.53 | 216.8 (155.2-226.0) |
| q8 | 127K | 0.75 | 1707 / 1916 | 89.1% | 2.48 | 207.9 (177.2-221.1) |

Tokens per round = output tokens / (output tokens - accepted drafts). The texts in this run differ from run to run
(the adaptive tier moves experts between requests; see below), so each row averages over different token streams.
The 127K prompts read in 27.9-29.9 s on every head.

## The same token stream (`static-placement.jsonl`)

`--adapt-every 0` (no expert moves), the three 2K prompts, 3 runs x 2 p-min per head. With the adaptive tier off every
head wrote one text per prompt in all 6 requests, so the heads are compared on identical outputs:

| head | slots | p-min | accepted / offered | accepted | tokens per round | decode tok/s, median |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| base | 7250 | 0.5 | 1736 / 2128 | 81.6% | 2.68 | 263.9 |
| q5k | 7250 | 0.5 | 1745 / 2117 | 82.4% | 2.70 | 266.6 |
| q8 | 6886 | 0.5 | 1844 / 2264 | 81.4% | 2.71 | 260.3 |
| base | 7250 | 0.75 | 1534 / 1691 | 90.7% | 2.24 | 237.8 |
| q5k | 7250 | 0.75 | 1548 / 1711 | 90.5% | 2.26 | 241.5 |
| q8 | 6886 | 0.75 | 1667 / 1804 | 92.4% | 2.33 | 243.5 |

(q8 wrote other texts than base here because it had fewer slots; its row is not on the same stream.)

## Greedy output is the same with every head

The draft layer only proposes; every token is the main model's own pick, so the head cannot change a greedy answer.
Checked token for token (the reasoning, the answer and the tool calls, with the tool calls' random `id` removed):

- base and q5k, both at 7250 slots: identical text on all three prompts, in all 6 requests each, at both p-min.
- base started with `--vram-reserve-mib 1186` (6886 slots, as q8) and q8: identical text on all three prompts.
- base at 7250 slots and base at 6886 slots: different texts. Which experts sit on the GPU and which on the CPU changes
  the arithmetic slightly, and greedy text forks at a near-tie. With the adaptive tier on, the placement changes
  between requests, so even the same head's runs differ (in `main.jsonl` 3 of 108 same-head pairs are identical).

## Result

No head beats Cyber-Tiel's own. On the same token stream q5k accepts 0.8 points more drafts at p-min 0.5 (tokens per
round 2.68 -> 2.70, decode 263.9 -> 266.6 tok/s, inside the run-to-run spread) and q8 is no better than q5k; at 127K the
three are level. q5k costs 198 MiB more VRAM and q8 486 MiB (in the deterministic mode that rounds the expert cache to
whole 512 MiB, base got 7250 slots and q8 6886 in the static run; the adaptive tier then takes the rest). p-min 0.75
accepts ~91% of drafts against ~80% at 0.5 but offers fewer, so a round carries fewer tokens and decode is not faster
(2K: 290.9 vs 296.8 tok/s; static stream 237.8 vs 263.9). Keep `--spec 4 --spec-min-p 0.50` and the model's own head.

Not tested: sampling above temperature 0, more than one start per head, the Q2_K head (no kernel), other cards.
Downtime of the live server: 22.9 + 8.4 + 3.1 + 1.5 = 35.9 minutes in four windows (the first included a run lost to
`--expert-cache 6886`, which filled the card: 0 MiB free, 9 tok/s; not used).
