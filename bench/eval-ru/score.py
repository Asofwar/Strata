"""Tables from run_eval.py results: one row per model and category, plus the reasoning-loop counts.

    python bench/eval-ru/score.py bench/eval-ru/results/tiel.jsonl bench/eval-ru/results/ornith.jsonl
    python bench/eval-ru/score.py ... --fails      # also list every failed reply with the reason
"""
import json
import re
import statistics
import sys
from pathlib import Path

CATS = ["coding", "tools", "russian", "needle"]
LONG_THINK = 8192


CJK = re.compile(r"[぀-ヿ㐀-䶿一-鿿가-힯]")
TOOL_NAMES = {"get_weather", "convert_currency", "search_issues", "write_file", "run_shell"}


def glitches(r):
    """Copy slips: a word the model had right turns into another one (a sampled token off the path)."""
    out = set()
    if CJK.search(r.get("content") or ""):
        out.add("cjk")
    if any(c["name"] not in TOOL_NAMES for c in r.get("tool_calls") or []):
        out.add("tool")
    if r["cat"] == "needle" and not r["pass"] and re.search(r"-\d{4}\b", r.get("content") or ""):
        out.add("needle")
    return out


def load(p):
    return [json.loads(x) for x in Path(p).read_text(encoding="utf-8").splitlines() if x.strip()]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    fails = "--fails" in sys.argv
    runs = {Path(p).stem: load(p) for p in args}
    print("| Model | Category | Replies | Passed | Pass rate | Items passed in all samples | Mean reasoning tokens "
          "| Mean latency, s |")
    print("|---|---|---|---|---|---|---|---|")
    for tag, rows in runs.items():
        for cat in CATS + ["all"]:
            rs = [r for r in rows if cat == "all" or r["cat"] == cat]
            if not rs:
                continue
            ids = sorted({r["id"] for r in rs})
            solid = sum(all(r["pass"] for r in rs if r["id"] == i) for i in ids)
            p = sum(r["pass"] for r in rs)
            # a repeated long prompt in the same server run is read from the conversation cache: needle latency
            # counts the first sample only (always a cold read)
            lat = [r for r in rs if r["cat"] != "needle" or r["sample"] == 0]
            print(f"| {tag} | {cat} | {len(rs)} | {p} | {100 * p / len(rs):.0f}% | {solid}/{len(ids)} | "
                  f"{statistics.mean(r['reasoning_tokens'] for r in rs):.0f} | "
                  f"{statistics.mean(r['wall_s'] for r in lat):.1f} |")
    print()
    print("| Model | Replies | With reasoning_loop_recovery | Over 8K reasoning tokens | finish = length "
          "| Max reasoning tokens | Median reasoning tokens |")
    print("|---|---|---|---|---|---|---|")
    for tag, rows in runs.items():
        rec = sum(1 for r in rows if (r.get("reasoning_recoveries") or 0) > 0)
        unknown = sum(1 for r in rows if r.get("reasoning_recoveries") is None)
        rec = f"{rec} (+{unknown} unknown)" if unknown else rec
        long = sum(1 for r in rows if r["reasoning_tokens"] > LONG_THINK)
        length = sum(1 for r in rows if r.get("finish") == "length")
        rt = [r["reasoning_tokens"] for r in rows]
        print(f"| {tag} | {len(rows)} | {rec} | {long} | {length} | {max(rt)} | {statistics.median(rt):.0f} |")
    print()
    print("| Model | Replies | CJK characters in the answer | Tool name not in the request | Needle code misspelt "
          "| Any of these |")
    print("|---|---|---|---|---|---|")
    for tag, rows in runs.items():
        g = [glitches(r) for r in rows]
        print(f"| {tag} | {len(rows)} | {sum('cjk' in x for x in g)} | {sum('tool' in x for x in g)} | "
              f"{sum('needle' in x for x in g)} | {sum(bool(x) for x in g)} |")
    if fails:
        print()
        for tag, rows in runs.items():
            for r in rows:
                if not r["pass"]:
                    print(f"- {tag} {r['cat']} {r['id']} #{r['sample']}: {r['why'][:160]} "
                          f"(think {r['reasoning_tokens']}, finish {r.get('finish')})")


if __name__ == "__main__":
    main()
