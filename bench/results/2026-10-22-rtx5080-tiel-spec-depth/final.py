"""Markdown tables for the README from d1..d4 results (requests in a slow stretch left out, as summ.py)."""
import json, re, statistics as st
from collections import defaultdict
from pathlib import Path

S = Path(__file__).resolve().parent / "runs"
NAMES = {"c4": "`--spec 4` (control)", "x8": "lookup to 8, MTP 4", "s5": "`--spec 5`", "s6": "`--spec 6`",
         "s8": "`--spec 8`", "d5": "MTP to 8, past 4 only at chain p >= 0.5", "d7": "MTP to 8, past 4 only at chain p >= 0.7"}
CAPS = {"c4": "4 / 6", "x8": "4 / 8", "s5": "5 / 7", "s6": "6 / 8", "s8": "8 / 8", "d5": "8 / 8", "d7": "8 / 8"}
GL = {"short": "short (12-19K)", "mid": "mid (34-88K)", "long130": "~130K (110-136K)", "long200": "~200K (179-206K)"}


def load(tag):
    p = S / f"{tag}-results.jsonl"
    rows = [json.loads(l) for l in open(p, encoding="utf-8")]
    for r in rows:
        r["tag"] = tag
    return [r for r in rows if r["rep"] >= 0 and r["group"] in GL]


def trim(rows):
    cm = defaultdict(list)
    for r in rows:
        cm[(r["tag"], r["group"], r["cut"])].append(r["produced"] / r["decode_ms"])
    cm = {k: st.median(v) for k, v in cm.items()}
    keep = [r for r in rows if r["produced"] / r["decode_ms"] >= 0.6 * cm[(r["tag"], r["group"], r["cut"])]]
    return keep, len(rows) - len(keep)


def wins(r):
    return sum(n for _, n in r["win_mtp"]) + sum(n for _, n in r["win_lu"])


def table(rows, arms, groups):
    base = {(r["tag"], r["group"], r["cut"], r["rep"]): r for r in rows if r["arm"] == "c4"}
    out = ["| context | arm (MTP / verify cap) | requests | tok/s | vs control (paired median, faster) | tokens / window | ms / window | window size | drafts accepted |",
           "|---|---|---|---|---|---|---|---|---|"]
    for g in groups:
        for a in arms:
            rs = [r for r in rows if r["group"] == g and r["arm"] == a]
            if not rs:
                continue
            tok = sum(r["produced"] for r in rs)
            ms = sum(r["decode_ms"] for r in rs)
            w = sum(wins(r) + 1 for r in rs)
            tsum = sum(t * n for r in rs for k in ("win_mtp", "win_lu") for t, (_, n) in enumerate(r[k], 1))
            wn = sum(wins(r) for r in rs)
            acc = sum(r["accepted"] for r in rs) / max(1, sum(r["offered"] for r in rs))
            ratios = []
            for r in rs:
                b = base.get((r["tag"], r["group"], r["cut"], r["rep"]))
                if b is not None and r is not b:
                    ratios.append((r["produced"] / r["decode_ms"]) / (b["produced"] / b["decode_ms"]))
            pr = f"{st.median(ratios):.3f} ({sum(x > 1 for x in ratios)}/{len(ratios)})" if ratios else "-"
            out.append(f"| {GL[g]} | {NAMES[a]} ({CAPS[a]}) | {len(rs)} | {1000 * tok / ms:.1f} | {pr} | "
                       f"{tok / w:.2f} | {ms / w:.2f} | {tsum / wn:.2f} | {100 * acc:.1f}% |")
    return "\n".join(out)


def window_costs(rows, arms, groups):
    out = ["| context | arm | MTP windows of 4 | 5 | 6 | 8 | lookup windows of 4 | 6 | 8 |", "|---|---|---|---|---|---|---|---|---|"]
    for g in groups:
        for a in arms:
            rs = [r for r in rows if r["group"] == g and r["arm"] == a and "ms_mtp" in r]
            if not rs:
                continue
            cells = []
            for kind, ms, ts in (("win_mtp", "ms_mtp", (4, 5, 6, 8)), ("win_lu", "ms_lu", (4, 6, 8))):
                for t in ts:
                    n = sum(r[kind][t - 1][1] for r in rs)
                    if n < 10:
                        cells.append("-")
                        continue
                    ok = sum(r[kind][t - 1][0] for r in rs)
                    m = sum(r[ms][t - 1] for r in rs)
                    cells.append(f"{(ok + n) / n:.2f} t / {m / n:.2f} ms")
            out.append(f"| {GL[g]} | {a} | " + " | ".join(cells) + " |")
    return "\n".join(out)


def forced():
    rows = [json.loads(l) for l in open(S / "d3-results.jsonl", encoding="utf-8")]
    rows = [r for r in rows if r["group"] in ("timing", "profile") and r["rep"] >= 0]
    agg = defaultdict(lambda: defaultdict(list))
    for r in rows:
        t = r["caps"][0]
        for l in r["timing"]:
            m = re.search(r"([\d.]+) ms/window = verify ([\d.]+) \(GPU-reach wait ([\d.]+) \+ per-layer host ([\d.]+) "
                          r"\[.*?CPU ([\d.]+)\].*?draft ([\d.]+)", l)
            if m and r["group"] == "timing":
                for k, v in zip(("window", "verify", "gpu", "host", "cpu", "draft"), m.groups()):
                    agg[t][k].append(float(v))
            if "GPU stages" in l and r["group"] == "profile":
                qa = re.search(r"QSA layers:.*? attention ([\d.]+)", l)
                gh = re.search(r"GDN layers:.*? VRAM hits ([\d.]+)", l)
                qh = re.search(r"QSA layers:.*? VRAM hits ([\d.]+)", l)
                agg[t]["attn"].append(float(qa.group(1)))
                agg[t]["hits"].append(float(gh.group(1)) + float(qh.group(1)))
    out = ["| window size (forced) | ms / window | verify: GPU wait | host (CPU experts) | MTP draft | GPU: attention (10 layers) | GPU: VRAM expert hits |",
           "|---|---|---|---|---|---|---|"]
    for t in sorted(agg):
        a = {k: st.mean(v) for k, v in agg[t].items()}
        out.append(f"| {t} | {a['window']:.2f} | {a['gpu']:.2f} | {a['host']:.2f} ({a['cpu']:.2f}) | {a['draft']:.2f} | "
                   f"{a['attn']:.2f} | {a['hits']:.2f} |")
    return "\n".join(out)


if __name__ == "__main__":
    allr = []
    for tag in ("d1", "d2", "d3", "d4"):
        if (S / f"{tag}-results.jsonl").exists():
            allr += load(tag)
    allr, n_slow = trim(allr)
    print(f"slow requests left out: {n_slow}\n")
    five = [r for r in allr if r["tag"] in ("d1", "d2")]
    print("## all arms (d1: short + ~200K, d2: mid + ~130K; 3 repeats)\n")
    print(table(five, ["c4", "s5", "s6", "s8", "d5", "d7", "x8"], ["short", "mid", "long130", "long200"]))
    print("\n## control vs lookup to 8, every downtime pooled\n")
    two = [r for r in allr if r["arm"] in ("c4", "x8")]
    print(table(two, ["c4", "x8"], ["short", "mid", "long130", "long200"]))
    print("\n## tokens and ms per window by size (d2)\n")
    print(window_costs([r for r in allr if r["tag"] == "d2"], ["c4", "s8", "d7", "x8"], ["mid", "long130"]))
    print("\n## forced window sizes, mid cut 3 (49.6K), 2 x 512 tokens each\n")
    print(forced())
