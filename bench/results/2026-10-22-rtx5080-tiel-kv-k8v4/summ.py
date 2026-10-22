# summ.py <log glob>...: one row per request (prompt s, decode tok/s, ms/window, tokens/window, GPU-reach wait, CPU
# ms/window, CPU experts per layer-window, hit rate, slots holding experts, VRAM warnings) and per-arm medians.
import glob, re, statistics as st, sys
from collections import defaultdict

agg = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
for pat in sys.argv[1:]:
    for f in sorted(glob.glob(pat)):
        arm = re.sub(r"^.*?[\\/]d\d+-", "", f).replace(".log", "")
        kind = re.sub(r"_\d+$", "", arm)
        print("==", f)
        cur, slots_hold, slots_all, warn = {}, None, None, None
        for line in open(f, encoding="utf-8", errors="replace"):
            m = re.search(r"expert cache (\d+) slots, ([\d.]+) GiB of VRAM", line)
            if m: slots_all = int(m.group(1)); print(f"   start: {slots_all} slots ({m.group(2)} GiB)")
            m = re.search(r"(\d+) MiB of VRAM free with everything loaded", line)
            if m: print(f"   free after load: {m.group(1)} MiB")
            m = re.search(r"elastic K/V: .*", line)
            if m: print("  ", m.group(0)[:140])
            m = re.search(r"K/V grown to (\d+) cells \(([\d.]+) GiB\); the expert cache gave (\d+) slots.*\((\d+) of (\d+) slots hold experts\)", line)
            if m: slots_hold = int(m.group(4)); print(f"   K/V {int(m.group(1))//1024}K cells {m.group(2)} GiB, gave {m.group(3)} slots, {m.group(4)} of {m.group(5)} hold experts")
            m = re.search(r"only (\d+) MiB of VRAM free at the start of this request", line)
            if m: warn = int(m.group(1))
            m = re.search(r"decode timing: (\d+) windows, avg T ([\d.]+), ([\d.]+) tokens/window, ([\d.]+) ms/window = verify ([\d.]+) \(GPU-reach wait ([\d.]+) .*?CPU ([\d.]+)\].*?CPU experts ([\d.]+) \(([\d.]+) entries\), VRAM hits ([\d.]+)", line)
            if m:
                cur.update(zip(["win", "T", "tpw", "ms", "ver", "wait", "cpu", "miss", "ent", "hits"], m.groups()))
                continue
            m = re.search(r"prompt (\d+) tokens = (\d+) reused \+ (\d+) read in (\d+) ms.*?(\d+) generated in (\d+) ms \(([\d.]+) tok/s\)", line)
            if m:
                ctx, reu, rd, rms, gen, gms, tps = m.groups()
                cur.update(ctx=int(ctx), rms=int(rms), gen=int(gen), tps=float(tps))
                continue
            m = re.search(r"decode expert cache hit rate: ([\d.]+)%", line)
            if m and "ctx" in cur:
                c = cur
                k = f"{c['ctx']//1000}K"
                s = f"   {k:>5} prompt {c['rms']/1000:6.1f} s  {c['tps']:6.1f} tok/s"
                if "ms" in c:
                    s += f"  {float(c['ms']):5.2f} ms/w T {c['T']} tpw {c['tpw']} wait {c['wait']:>5} cpu {c['cpu']:>5} miss/l-w {c['miss']:>4}"
                s += f"  hit {m.group(1)}%  hold {slots_hold}  {'' if warn is None else f'WARN {warn} MiB free'}"
                print(s)
                if c["ctx"] > 100000:
                    a = agg[kind][k]
                    a["prompt"].append(c["rms"] / 1000); a["tps"].append(c["tps"]); a["hit"].append(float(m.group(1)))
                    if "ms" in c:
                        a["ms"].append(float(c["ms"])); a["tpw"].append(float(c["tpw"])); a["cpu"].append(float(c["cpu"]))
                        a["wait"].append(float(c["wait"])); a["miss"].append(float(c["miss"]))
                    if slots_hold: a["hold"].append(slots_hold)
                cur, warn = {}, None
print("\n== medians per arm kind (requests >100K)")
for kind, by in agg.items():
    for k, a in sorted(by.items()):
        md = {x: st.median(v) for x, v in a.items() if v}
        print(f"  {kind:>4} {k:>5} n={len(a['tps'])}: prompt {md['prompt']:6.1f} s, {md['tps']:6.1f} tok/s, "
              f"{md.get('ms', 0):5.2f} ms/w, tpw {md.get('tpw', 0):.2f}, wait {md.get('wait', 0):5.2f}, cpu {md.get('cpu', 0):5.2f}, "
              f"miss/l-w {md.get('miss', 0):.2f}, hit {md['hit']:.1f}%, hold {md.get('hold', 0):.0f}   "
              f"tps all {[round(x, 1) for x in a['tps']]} prompt all {[round(x, 1) for x in a['prompt']]}")
