"""Round cost by window size and kind (ms per window, from 'spec window ms'), per group x arm, slow requests out."""
import json, sys, statistics as st
from collections import defaultdict

rows = []
for f in sys.argv[1:]:
    rows += [json.loads(l) for l in open(f, encoding="utf-8")]
rows = [r for r in rows if r["rep"] >= 0 and "ms_mtp" in r]
cm = defaultdict(list)
for r in rows:
    cm[(r["group"], r["cut"])].append(r["produced"] / r["decode_ms"])
cm = {k: st.median(v) for k, v in cm.items()}
rows = [r for r in rows if r["produced"] / r["decode_ms"] >= 0.6 * cm[(r["group"], r["cut"])]]
groups = list(dict.fromkeys(r["group"] for r in rows))
arms = list(dict.fromkeys(r["arm"] for r in rows))
for g in groups:
    print(g)
    for a in arms:
        rs = [r for r in rows if r["group"] == g and r["arm"] == a]
        if not rs:
            continue
        out = []
        for kind, ms in (("win_mtp", "ms_mtp"), ("win_lu", "ms_lu")):
            parts = []
            for t in range(8):
                n = sum(r[kind][t][1] for r in rs)
                if n >= 10:
                    ok = sum(r[kind][t][0] for r in rs)
                    m = sum(r[ms][t] for r in rs)
                    parts.append(f"{t + 1}:{m / n:5.2f}ms {(ok + n) / n:4.2f}t n{n}")
            out.append("  ".join(parts))
        print(f"  {a:3} mtp  {out[0]}\n      look {out[1]}")
