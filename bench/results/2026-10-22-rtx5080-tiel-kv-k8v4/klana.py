# klana.py <a.lp> <b.lp> [labels]: per request and in all, KL(A || B) of the teacher-forced next-token distributions
# (STRATA_LOGPOS + STRATA_LOGPOS_TOPK), argmax agreement, mean |d logp(target)| and perplexity (the KL of
# analyze.py in session confident-goldwasser: A's top-K plus one bucket for the rest)
import math, pathlib, statistics as st, sys


def read_lp(path):
    reqs, cur, last = [], [], None
    for line in pathlib.Path(path).read_text().splitlines():
        c = line.split("\t")
        pos = int(c[0])
        if last is not None and (pos <= last or pos != last + 1):
            reqs.append(cur)
            cur = []
        last = pos
        tk = {int(x.split(":")[0]): float(x.split(":")[1]) for x in c[8:]}
        cur.append((pos, int(c[1]), float(c[2]), int(c[3]), tk))
    if cur:
        reqs.append(cur)
    return reqs


def kl_pos(ka, kb):
    floor_b = min(kb.values())
    s, pa_sum, pb_sum = 0.0, 0.0, 0.0
    for i, lpa in ka.items():
        lpb = kb.get(i, floor_b)
        p, q = math.exp(lpa), math.exp(lpb)
        s += p * (lpa - lpb)
        pa_sum += p
        pb_sum += q
    ra_, rb_ = max(1e-12, 1 - pa_sum), max(1e-12, 1 - pb_sum)
    s += ra_ * math.log(ra_ / rb_)
    return max(0.0, s)


A, B = read_lp(sys.argv[1]), read_lp(sys.argv[2])
labels = sys.argv[3].split(",") if len(sys.argv) > 3 else [str(i) for i in range(len(A))]
allk, alla, alln = [], 0, 0
for i, (ra, rb) in enumerate(zip(A, B)):
    kls, agree, dlp, nll_a, nll_b = [], 0, [], 0.0, 0.0
    for (pa, ta, la, topa, ka), (pb, tb, lb, topb, kb) in zip(ra, rb):
        assert pa == pb and ta == tb
        agree += topa == topb
        dlp.append(abs(la - lb))
        nll_a -= la
        nll_b -= lb
        kls.append(kl_pos(ka, kb))
    n = len(kls)
    allk += kls
    alla += agree
    alln += n
    print(f"  {labels[i] if i < len(labels) else i:>6}: {n} positions, argmax agree {100 * agree / n:.2f}%, mean KL {st.mean(kls):.5f} "
          f"(max {max(kls):.3f}), mean |d logp| {st.mean(dlp):.5f}, ppl {math.exp(nll_a / n):.4f} / {math.exp(nll_b / n):.4f}")
print(f"  all: {alln} positions, argmax agree {100 * alla / alln:.2f}%, mean KL {st.mean(allk):.5f}")
