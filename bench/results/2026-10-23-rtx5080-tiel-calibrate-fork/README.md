# `--calibrate-fork` on the RTX 5080 (Cyber-Tiel UD-IQ4_XS, 2026-10-23)

**Question.** What does the new fork calibration (tools/calibrate_fork.py) pick on the PC the fork's settings were
hand-tuned on, and how does that compare with the hand-tuned live config?

**Answer.** It keeps setup's `PACK_TUNED` variables and the config's per-request values (`--spec 4`,
`--spec-min-p 0.50`, `--pcie-frac 0.00`): at 64K no opt-in switch beat the 6.0% spread between baseline starts, and
the three defaults it measured off were slower (`STRATA_ATTN_WINDOW_SMALL` off -10.5% decode, `DENSE_IMMA` off -49%
prompt speed, `MMQ_KQ` off -2.9%). From the hardware it sets `--vram-reserve-mib 1536` (207 MiB stayed free, the
engine's line is 1024), `--conversation-cache-mib 3072` with 2 slots (12.4 GiB of RAM available with the model loaded)
and keeps the disk tier at 32768 MiB (355 GiB free). That config decodes 9-10% slower than the live one at 64K and
128K, because the reserve keeps 857 expert slots off the GPU; the live config runs with ~200 MiB free.

## Setup

- RTX 5080 16 GB (PCIe 5.0 x8), i9-14900K, DDR5-7600 2 x 24 GB, Windows 11, CUDA 13.4. Engine: this branch
  (main 57c7b182 + the calibration), built in its own directory. Cyber-Tiel-Coder-35B-A3B UD-IQ4_XS from the pack,
  a copy of the live config (`strata-tiel-main.json`) with this engine and its own log.
- `python tools/calibrate.py --fork --budget 70 --compare <live config> <copy>`, the live server (port 8096) stopped
  for the run by `window.py` (the GPU lock held, the server stopped only when idle, restored after).
- Measurement starts run without the conversation disk tier (`measure_args`).

## Results

`run.txt` is the calibration's own output, `fork-result.json` its result (every sample). The compared config was not
measured inside it (an earlier version of the last check ran only when something was chosen; fixed since), so
`compare.py` measured the calibrated config against the live one afterwards: 3 interleaved starts each, a 64K and a
128K prompt per start, 4 greedy answers of 256 tokens after each (`compare-result.json`, `compare.txt`).

| | expert slots | VRAM free | 64K prompt | 64K decode | 128K prompt | 128K decode | short answers |
|---|---|---|---|---|---|---|---|
| calibrated | 7,006 | 984-1,048 MiB | 8.90 s | 235.3 (233.1-236.2) | 22.36 s | 210.1 (209.4-211.6) | 254.2 |
| live | 7,863 | 205-212 MiB | 8.87 s | 261.4 (256.2-266.4) | 22.33 s | 231.7 (221.3-232.0) | 291.8 |

Time: the calibration 20.7 minutes (35 engine starts of 9-10 s each), the comparison 5.6 minutes; the live server was
down 21.1 and 6.0 minutes (and 1.5 minutes for a first attempt, stopped when its VRAM reserve came from the step-1
engine with 7-token windows: 145 MiB free there, now a probe start with the chosen depth decides).

Not measured: the calibration at 130K-200K, sampled answers, other PCs.
