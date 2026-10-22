import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from convidx import read_idx, tok

IM_START = 248045


def turns(ids):
    """[(start index of <|im_start|>, role, length in tokens)]"""
    t = tok()
    starts = [i for i, x in enumerate(ids) if x == IM_START]
    out = []
    for k, s in enumerate(starts):
        e = starts[k + 1] if k + 1 < len(starts) else len(ids)
        head = t.decode(ids[s + 1:s + 4])
        role = head.split("\n")[0].strip()
        out.append((s, role, e - s))
    return out


if __name__ == "__main__":
    for p in sys.argv[1:]:
        e = read_idx(p)
        ids = e["live"]
        ts = turns(ids)
        print(os.path.basename(p), len(ids), "turns", len(ts))
        roles = {}
        for s, r, n in ts:
            roles.setdefault(r, []).append(n)
        for r, ns in roles.items():
            print("  ", r, len(ns), "tokens", sum(ns), "max", max(ns))
