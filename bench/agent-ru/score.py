"""bench/agent-ru/score.py - tables from results/<tag>.jsonl of run_agent.py.

    python bench/agent-ru/score.py tiel ornith kat               (one row per tag)
    python bench/agent-ru/score.py tiel ornith --tasks           (plus passes per task, a column per tag)
    python bench/agent-ru/score.py tiel ornith --kinds           (plus the pass rate per task kind and language)
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(tag):
    p = HERE / "results" / f"{tag}.jsonl"
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def summary(rows):
    n = len(rows)
    by_task = defaultdict(list)
    for r in rows:
        by_task[r["task"]].append(r["pass"])
    walls = [r["wall_s"] for r in rows]
    return {
        "runs": n, "pass": sum(r["pass"] for r in rows),
        "tasks_any": sum(any(v) for v in by_task.values()), "tasks_all": sum(all(v) for v in by_task.values()),
        "tasks": len(by_task),
        "turns": statistics.mean(r["turns"] for r in rows),
        "turns_pass": statistics.mean([r["turns"] for r in rows if r["pass"]] or [0]),
        "malformed": sum(r["malformed"] for r in rows),
        "runs_malformed": sum(1 for r in rows if r["malformed"]),
        "recoveries": sum(r["recoveries"] for r in rows),
        "repeat": sum(r["repeat_calls"] for r in rows),
        "length": sum(r["length_cuts"] for r in rows),
        "max_turns": sum(1 for r in rows if r["ended"] == "max-turns"),
        "no_finish": sum(1 for r in rows if r["ended"] == "no-tool-call"),
        "errors": sum(1 for r in rows if r["ended"] in ("http-error", "request-failed")),
        "wall": statistics.mean(walls), "wall_med": statistics.median(walls),
        "think": statistics.mean(r["reasoning_tokens"] for r in rows),
        "out": statistics.mean(r["completion_tokens"] for r in rows),
        "ctx": max(r["max_prompt_tokens"] for r in rows),
        "ctx_mean": statistics.mean(r["max_prompt_tokens"] for r in rows),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tags", nargs="+")
    ap.add_argument("--tasks", action="store_true")
    ap.add_argument("--kinds", action="store_true")
    a = ap.parse_args()
    data = {t: load(t) for t in a.tags}
    print("| config | pass (runs) | tasks solved: any / all runs | mean turns (passed) | malformed calls (runs) "
          "| loop recoveries | repeated calls | max-turns hit | stopped w/o finish | length cuts | wall per run, "
          "mean / median s | thinking tokens per run | max / mean context |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for tag, rows in data.items():
        s = summary(rows)
        print(f"| {tag} | {s['pass']}/{s['runs']} ({100 * s['pass'] / s['runs']:.0f}%) | {s['tasks_any']} / "
              f"{s['tasks_all']} of {s['tasks']} | {s['turns']:.1f} ({s['turns_pass']:.1f}) | {s['malformed']} "
              f"({s['runs_malformed']}) | {s['recoveries']} | {s['repeat']} | {s['max_turns']} | {s['no_finish']} | "
              f"{s['length']} | {s['wall']:.0f} / {s['wall_med']:.0f} | {s['think']:.0f} | {s['ctx']} / "
              f"{s['ctx_mean']:.0f} |" + (f" errors {s['errors']}" if s["errors"] else ""))
    if a.kinds:
        print()
        groups = sorted({(r["kind"]) for rows in data.values() for r in rows}) + ["python", "js", "ts", "ru"]
        print("| group | " + " | ".join(a.tags) + " |")
        print("|---|" + "---|" * len(a.tags))
        for g in groups:
            cells = []
            for tag in a.tags:
                rs = [r for r in data[tag] if r["kind"] == g or r["lang"] == g or (g == "ru" and r["ru"])]
                cells.append(f"{sum(r['pass'] for r in rs)}/{len(rs)}" if rs else "-")
            print(f"| {g} | " + " | ".join(cells) + " |")
    if a.tasks:
        print()
        ids = []
        for rows in data.values():
            for r in rows:
                if r["task"] not in ids:
                    ids.append(r["task"])
        print("| task | " + " | ".join(a.tags) + " |")
        print("|---|" + "---|" * len(a.tags))
        for tid in ids:
            cells = []
            for tag in a.tags:
                rs = sorted((r for r in data[tag] if r["task"] == tid), key=lambda r: r["run"])
                cells.append("".join("P" if r["pass"] else "f" for r in rs) +
                             (f" {statistics.mean(r['turns'] for r in rs):.0f}t" if rs else "-"))
            print(f"| {tid} | " + " | ".join(cells) + " |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
