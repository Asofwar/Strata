"""The calibrated config against the live one: 3 interleaved engine starts each; per start a 64K and a 128K prompt read
once, 4 greedy answers of 256 tokens after each, and the short prompts (tools/calibrate_fork.py's own measurement)."""
import json
import os
import statistics
import sys
import time

sys.path.insert(0, r"E:\Projects\Strata-autotune\tools")
sys.path.insert(0, r"E:\Projects\Strata-autotune")
import calibrate as CAL  # noqa: E402
import calibrate_fork as CF  # noqa: E402
from serve.server import StrataEngine, child_env  # noqa: E402

SP = os.path.dirname(os.path.abspath(__file__))
calib = json.load(open(os.path.join(SP, "tiel-calib.json"), encoding="utf-8-sig"))
live = json.load(open(os.path.join(SP, "tiel-live.json"), encoding="utf-8-sig"))
res = json.load(open(os.path.join(SP, "fork-result.json"), encoding="utf-8"))
t_args, t_env = CF.apply_fork(calib["args"], calib.get("env"), res)
arms = {"tuned": (CF.measure_args(t_args), t_env), "live": (CF.measure_args(live["args"]), dict(live["env"]))}
keys = CF.fork_env_keys(CF.pack_base_env())
log = calib["log"]
tok = CAL.load_tokenizer(calib)
parts = CF.doc_parts(tok)
short_ids = [CAL.chat_ids(tok, q) for q in CAL.PROMPTS]
foreign = CF.Foreign()
out = {n: [] for n in arms}
say = lambda *a: print(*a, flush=True)  # noqa: E731
for n, (a, e) in arms.items():
    say(n, "args:", " ".join(x for x in a if x.startswith("--")), "env:", e)
t0 = time.time()
for r in range(3):
    for n in (["tuned", "live"] if r % 2 == 0 else ["live", "tuned"]):
        a, env = arms[n]
        ce = child_env({**calib, "env": env})
        for k in keys:
            if k not in env:
                ce.pop(k, None)
        since = os.path.getsize(log) if os.path.isfile(log) else 0
        ts = time.time()
        eng = StrataEngine(calib["exe"], a, cwd=calib.get("cwd"), log=log, env=ce)
        load = time.time() - ts
        try:
            s = {"load_s": round(load, 1), "slots": eng.info.get("expert_slots"), "vram_free": CF.log_free_mib(log, since)}
            for ctx, doc in ((65536, 1), (131072, 2)):
                lc = CF.LongContext(eng, parts, ctx, short_ids, foreign=foreign, say=say)
                rd = lc.read(doc)
                lc.answers(questions=1, max_new=64, measure=False)
                ans = lc.answers_checked()
                s[f"{ctx // 1024}K"] = {"prompt_s": round(rd["ms"] / 1000, 2), "prompt_tok_s": rd["tok_s"],
                                        "decode": round(ans["tok_s"], 1), "foreign": ans["foreign_loads"],
                                        "rereads": lc.rereads}
            s["short"] = round(lc.short()["tok_s"], 1)
        finally:
            CAL.close(eng)
        out[n].append(s)
        say(f"round {r + 1} {n}: {json.dumps(s)}")
summary = {}
for n, ss in out.items():
    summary[n] = {k: {"prompt_s": statistics.median(x[k]["prompt_s"] for x in ss),
                      "decode": statistics.median(x[k]["decode"] for x in ss),
                      "decode_all": [x[k]["decode"] for x in ss]} for k in ("64K", "128K")}
    summary[n]["short"] = statistics.median(x["short"] for x in ss)
    summary[n]["slots"] = [x["slots"] for x in ss]
    summary[n]["vram_free"] = [x["vram_free"] for x in ss]
say(json.dumps(summary, indent=1))
json.dump({"samples": out, "summary": summary, "minutes": round((time.time() - t0) / 60, 1)},
          open(os.path.join(SP, "compare-result.json"), "w", encoding="utf-8"), indent=1)
