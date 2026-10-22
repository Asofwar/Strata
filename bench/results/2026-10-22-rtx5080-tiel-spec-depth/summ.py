"""Summarize bench results: per group x arm, tokens/window, acceptance, ms/window, decode tok/s (pooled), and
paired per-(cut, rep) ratios against c4."""
import json, sys, statistics as st
from collections import defaultdict
from pathlib import Path

S = Path(__file__).resolve().parent / "runs"
rows = []
for f in sys.argv[1:] or [str(p) for p in S.glob("d*-results.jsonl")]:
    rows += [json.loads(l) for l in open(f, encoding="utf-8")]
rows = [r for r in rows if r["rep"] >= 0]
ARMS = ["c4", "x8", "s5", "s6", "s8", "d5", "d7"]
groups = []
for r in rows:
    if r["group"] not in groups:
        groups.append(r["group"])


def windows(r):
    return sum(n for _, n in r.get("win_mtp", [])) + sum(n for _, n in r.get("win_lu", [])) + 1


# a request in a slow stretch (the CPU pool's slow state, VRAM paging: consecutive requests of every arm) is left out
# of the trimmed rate: below 0.6 x the median rate of its (group, cut)
cutmed = defaultdict(list)
for r in rows:
    cutmed[(r["group"], r["cut"])].append(r["produced"] / r["decode_ms"])
cutmed = {k: st.median(v) for k, v in cutmed.items()}
slow = lambda r: r["produced"] / r["decode_ms"] < 0.6 * cutmed[(r["group"], r["cut"])]
print("slow requests left out of 'trim':", sum(slow(r) for r in rows), "of", len(rows))
print(f"{'group':8} {'arm':3} {'req':>3} {'tok':>6} {'tok/s':>6} {'trim':>6} {'ms/win':>6} {'tok/win':>7} {'T mean':>6} "
      f"{'acc%':>5} {'lu win%':>7} {'lu tok/win':>10} {'paired':>14} {'hit%':>5}")
for g in groups:
    base = {(r["cut"], r["rep"]): r for r in rows if r["group"] == g and r["arm"] == "c4"}
    for a in ARMS:
        rs = [r for r in rows if r["group"] == g and r["arm"] == a]
        if not rs:
            continue
        tok = sum(r["produced"] for r in rs)
        ms = sum(r["decode_ms"] for r in rs)
        win = sum(windows(r) for r in rs)
        tsum = sum(t * n for r in rs for t, (_, n) in enumerate(r.get("win_mtp", []), 1)) + \
               sum(t * n for r in rs for t, (_, n) in enumerate(r.get("win_lu", []), 1))
        wn = sum(n for r in rs for _, n in r.get("win_mtp", [])) + sum(n for r in rs for _, n in r.get("win_lu", []))
        luw = sum(n for r in rs for _, n in r.get("win_lu", []))
        luok = sum(k for r in rs for k, _ in r.get("win_lu", []))
        acc = sum(r["accepted"] for r in rs) / max(1, sum(r["offered"] for r in rs))
        ratios = []
        for r in rs:
            b = base.get((r["cut"], r["rep"]))
            if b and b["decode_ms"] > 0 and r["decode_ms"] > 0 and not slow(r) and not slow(b):
                ratios.append((r["produced"] / r["decode_ms"]) / (b["produced"] / b["decode_ms"]))
        pr = f"{st.median(ratios):.3f} {sum(x > 1 for x in ratios)}/{len(ratios)}" if ratios else "-"
        hit = st.mean(r["hit"] for r in rs if "hit" in r) if any("hit" in r for r in rs) else 0
        ok = [r for r in rs if not slow(r)]
        trim = 1000 * sum(r["produced"] for r in ok) / sum(r["decode_ms"] for r in ok)
        print(f"{g:8} {a:3} {len(rs):3d} {tok:6d} {1000 * tok / ms:6.1f} {trim:6.1f} {ms / win:6.2f} {tok / win:7.2f} "
              f"{tsum / max(wn, 1):6.2f} {100 * acc:5.1f} {100 * luw / max(wn, 1):7.1f} "
              f"{(luok + luw) / max(luw, 1):10.2f} {pr:>14} {hit:5.1f}")
    # windows by size for c4 vs s8 vs x8: mtp / lookup counts and the mean accepted
    for a in ("c4", "x8", "s8"):
        rs = [r for r in rows if r["group"] == g and r["arm"] == a]
        if not rs:
            continue
        line = []
        for kind in ("win_mtp", "win_lu"):
            cnt = [sum(r[kind][t][1] for r in rs if kind in r) for t in range(8)]
            ok = [sum(r[kind][t][0] for r in rs if kind in r) for t in range(8)]
            line.append(" ".join(f"{t + 1}:{cnt[t]}({ok[t] / cnt[t]:.1f})" for t in range(8) if cnt[t]))
        print(f"   {a} mtp {line[0]}\n      lookup {line[1]}")
