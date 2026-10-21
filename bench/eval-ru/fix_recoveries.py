"""One-off fix for the first runs: run_eval.py read /metrics' oldest kept request instead of the newest, so those
rows' reasoning_recoveries belonged to another request.

The server prints "repeated reasoning detected at N tokens" to its stdout for every recovery; the detector never
fired below 2560 reasoning tokens in these runs. Rows covered by a kept stdout log with no such line get 0. Rows
from a window whose stdout log was overwritten (--unlogged N: the first N rows of the file) get 0 when their
reasoning stayed under 2560 tokens, else None (unknown).

    python bench/eval-ru/fix_recoveries.py results/tiel.jsonl --unlogged 36 server-tiel.out.log
"""
import argparse
import json
from pathlib import Path

DETECT_MIN = 2560

ap = argparse.ArgumentParser()
ap.add_argument("rows")
ap.add_argument("logs", nargs="*", help="server stdout logs covering the rows after the unlogged ones")
ap.add_argument("--unlogged", type=int, default=0)
a = ap.parse_args()
rows_path = Path(a.rows)
hits = sum(Path(p).read_text(encoding="utf-8", errors="replace").count("repeated reasoning detected") for p in a.logs)
rows = [json.loads(x) for x in rows_path.read_text(encoding="utf-8").splitlines() if x.strip()]
fixed = unknown = 0
for i, r in enumerate(rows):
    if r.get("metrics_output_tokens") is not None and r["metrics_output_tokens"] == r.get("completion_tokens"):
        continue                                            # matched to its own /metrics entry: keep
    if i < a.unlogged:
        r["reasoning_recoveries"] = 0 if r["reasoning_tokens"] < DETECT_MIN else None
    else:
        r["reasoning_recoveries"] = 0 if hits == 0 else None
    r["metrics_output_tokens"] = None
    fixed += 1
    unknown += r["reasoning_recoveries"] is None
rows_path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
print(f"{rows_path.name}: {hits} recoveries in the logs, {fixed} rows fixed, {unknown} unknown")
