"""One downtime of the live server (8096): the worktree engine with --spec 8 --mtp-max-t 8 and the live config's other
switches (minus the conversation disk), replaying reqs.json with per-request window caps (spec_t / spec_s), arms
interleaved per cut and repeat. Takes the shared GPU lock (msvcrt byte 0 of strata-gpu.lock), stops the server only
when it is idle, restores run-tiel-main.bat at the end in any case.  Stop early: create bench.stop here.

python bench.py --tag d1 --groups short,long200 [--reps 3] [--max-new 512] [--dry]"""
import argparse, json, msvcrt, os, re, subprocess, sys, time, urllib.request
from pathlib import Path

S = Path(__file__).resolve().parent
WT = Path(r"E:\Projects\Strata-fork\.claude\worktrees\modest-heisenberg-691b50")
sys.path.insert(0, str(WT))
from serve import winjob  # noqa: E402

LOCK = r"C:\Users\Admin\AppData\Local\Temp\strata-gpu.lock"
CFG = r"E:\Projects\Strata-integrate\strata-tiel-main.json"
EXE = r"D:\Build\strata-spec\strata.exe"
STOP = S / "bench.stop"
ARMS = {"c4": (4, 6, ""), "x8": (4, 8, ""), "s5": (5, 7, ""), "s6": (6, 8, ""), "s8": (8, 8, ""),
        # d5 / d7 ran with spec_deep_p=0.5 / 0.7, a request key of a build that was not kept (README)
        "d5": (8, 8, " spec_deep_p=0.5"), "d7": (8, 8, " spec_deep_p=0.7")}   # (spec_t, spec_s, keys)
TL = S / "timeline.log"


def note(m):
    line = f"{time.strftime('%H:%M:%S')} {m}"
    print(line, flush=True)
    with open(TL, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def status():
    try:
        with urllib.request.urlopen("http://127.0.0.1:8096/status", timeout=5) as r:
            return json.loads(r.read())
    except Exception:
        return None


def models_loaded():
    try:
        with urllib.request.urlopen("http://127.0.0.1:8096/v1/models", timeout=5) as r:
            d = json.loads(r.read())
        return d["data"][0].get("status", {}).get("value") == "loaded"
    except Exception:
        return False


def ps(cmd):
    return subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True)


def stop_server():
    ps("Get-CimInstance Win32_Process -Filter \"Name='cmd.exe'\" | Where-Object { $_.CommandLine -like '*run-tiel-main.bat*' } "
       "| ForEach-Object { taskkill /PID $_.ProcessId /T /F | Out-Null }")
    time.sleep(5)
    ps("Get-Process strata -ErrorAction SilentlyContinue | Where-Object { $_.Path -like '*Strata-main*' } "
       "| ForEach-Object { Stop-Process -Id $_.Id -Force }")
    time.sleep(3)


def start_server():
    r = ps("Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine='cmd.exe /c start "
           "\"Strata main\" /D E:\\Projects\\Strata-main E:\\Projects\\Strata-integrate\\run-tiel-main.bat'} "
           "| Select-Object -ExpandProperty ReturnValue")
    note(f"server start requested (ReturnValue {r.stdout.strip()})")
    for _ in range(150):
        time.sleep(5)
        if models_loaded():
            return True
    return False


def engine_cmd(extra_env=None, spec_args=None):
    cfg = json.load(open(CFG, encoding="utf-8"))
    args = []
    a = cfg["args"]
    i = 0
    while i < len(a):
        if a[i] in ("--conversation-disk-dir", "--conversation-disk-mib", "--conversation-disk-persist"):
            i += 2
            continue
        if a[i] == "--spec":
            args += spec_args or ["--spec", "8", "--mtp-max-t", "8"]
            i += 2
            continue
        args.append(a[i])
        i += 1
    env = dict(os.environ)
    env.update({k: str(v) for k, v in cfg["env"].items()})
    env["STRATA_SPEC_DEPTH"] = "1"
    env.update(extra_env or {})
    env["PATH"] = ";".join(cfg["lib_dirs"]) + ";" + env["PATH"]
    return [EXE, "--serve", *args], env, cfg["cwd"]


class Engine:
    def __init__(self, tag, extra_env=None, spec_args=None):
        cmd, env, cwd = engine_cmd(extra_env, spec_args)
        self.log_path = S / f"{tag}-engine.log"
        (S / f"{tag}-engine.cmd.txt").write_text(" ".join(cmd), encoding="utf-8")
        self.log = open(self.log_path, "w", encoding="utf-8")
        self.p = subprocess.Popen(cmd, cwd=cwd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.log,
                                  text=True, encoding="utf-8", bufsize=1)
        note(f"engine pid {self.p.pid} contained={winjob.contain(self.p)}")
        self.logpos = 0
        while True:
            line = self.p.stdout.readline()
            if not line:
                raise RuntimeError("engine ended before READY")
            if line.startswith("READY"):
                note("engine " + line.strip())
                break
        self.logpos = self._logsize()

    def _logsize(self):
        self.log.flush()
        return os.path.getsize(self.log_path)

    def gen(self, ids, max_new, keys):
        line = f"GEN {max_new} {keys} {','.join(map(str, ids))}\n"
        self.p.stdin.write(line)
        self.p.stdin.flush()
        toks = []
        while True:
            l = self.p.stdout.readline()
            if not l:
                raise RuntimeError("engine ended mid-request")
            if l.startswith("T "):
                toks.append(int(l[2:]))
            elif l.startswith("DONE"):
                f = l.split()
                done = {"produced": int(f[1]), "n": int(f[2]), "prompt_ms": float(f[3]), "decode_ms": float(f[4]),
                        "finish": f[5], "accepted": int(f[6]), "offered": int(f[7]), "resume": int(f[8])}
                break
            elif l.startswith("ERR"):
                raise RuntimeError(l.strip())
        time.sleep(0.05)
        self.log.flush()
        with open(self.log_path, encoding="utf-8", errors="replace") as fh:
            fh.seek(self.logpos)
            text = fh.read()
            self.logpos = fh.tell()
        m = re.search(r"spec windows \(caps (\d+)/(\d+)\): mtp([\d/ ]+)\| lookup([\d/ ]+)", text)
        if m:
            done["caps"] = [int(m.group(1)), int(m.group(2))]
            done["win_mtp"] = [list(map(int, x.split("/"))) for x in m.group(3).split()]
            done["win_lu"] = [list(map(int, x.split("/"))) for x in m.group(4).split()]
        m = re.search(r"spec window ms: mtp([\d. ]+)\| lookup([\d. ]+)", text)
        if m:
            done["ms_mtp"] = list(map(float, m.group(1).split()))
            done["ms_lu"] = list(map(float, m.group(2).split()))
        m = re.search(r"spec depth: accepted/tested([\d/ ]+)", text)
        if m:
            done["depth"] = [list(map(int, x.split("/"))) for x in m.group(1).split()]
        m = re.search(r"decode expert cache hit rate: ([\d.]+)%", text)
        if m:
            done["hit"] = float(m.group(1))
        m = re.search(r"suffix drafts: (\d+) windows, (\d+) of (\d+)", text)
        if m:
            done["sfx"] = [int(m.group(1)), int(m.group(2)), int(m.group(3))]
        done["toks"] = toks
        done["timing"] = [l for l in text.splitlines() if l.startswith("strata decode")]
        return done

    def quit(self):
        try:
            self.p.stdin.write("QUIT\n")
            self.p.stdin.flush()
            self.p.wait(timeout=60)
        except Exception:
            self.p.kill()
        self.log.close()


def plan(reqs, groups, reps, arm_names):
    out = []
    for g in groups:
        cuts = [r for r in reqs if r["group"] == g]
        if g.startswith("long"):
            cuts = cuts[:6]
        for ci, r in enumerate(cuts):
            if ci == 0:
                out.append((g, ci, -1, "c4", r))      # warm-up after the prompt read: not counted
            for rep in range(reps):
                k = (ci + rep) % len(arm_names)
                order = arm_names[k:] + arm_names[:k]
                if rep % 2 == 1:
                    order = order[::-1]
                for a in order:
                    out.append((g, ci, rep, a, r))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--groups", required=True)
    ap.add_argument("--arms", default="c4,x8,s5,s6,s8")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--max-new", type=int, default=512)
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--forced", default="", help="after the arms: forced window sizes (e.g. 4,5,6,8) on mid cut 3, "
                    "one engine with STRATA_DECODE_TIMING=1, one more with STRATA_VERIFY_PROFILE=1 as well")
    ap.add_argument("--startup-check", action="store_true", help="after the arms: an engine started with --spec 8 "
                    "--mtp-max-t 4 (no request caps), the short group's first cut x3")
    a = ap.parse_args()
    reqs = json.load(open(S / "reqs.json"))
    arm_names = a.arms.split(",")
    todo = plan(reqs, a.groups.split(","), a.reps, arm_names)
    note(f"[{a.tag}] plan: {len(todo)} requests, groups {a.groups}, arms {a.arms}, reps {a.reps}, max_new {a.max_new}")
    if a.dry:
        for g, ci, rep, arm, r in todo[:12]:
            print(g, ci, rep, arm, len(r["ids"]))
        print(" ".join(engine_cmd()[0]))
        return
    fh = open(LOCK, "a+")
    while True:
        if STOP.exists():
            note("stop-file before the lock")
            return
        try:
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            break
        except OSError:
            time.sleep(5)
    note(f"[{a.tag}] lock held")
    out = open(S / f"{a.tag}-results.jsonl", "a", encoding="utf-8")
    try:
        idle = 0
        while idle < 20:
            if STOP.exists():
                note("stop-file before downtime")
                return
            st = status()
            idle = idle + 5 if st is None or (not st.get("busy") and not st.get("queued")) else 0
            time.sleep(5)
        stop_server()
        note(f"[{a.tag}] DOWNTIME START")
        try:
            eng = Engine(a.tag)
            try:
                for g, ci, rep, arm, r in todo:
                    if STOP.exists():
                        note("stop-file: ending early")
                        break
                    t, s, extra = ARMS[arm]
                    seed = 1000 * (ci + 1) + max(rep, 0) + 1 + (17 if g == "short" else 0)
                    keys = f"temperature=0.6 seed={seed} spec_t={t} spec_s={s}{extra}"
                    mx = 256 if rep < 0 else a.max_new
                    t0 = time.time()
                    d = eng.gen(r["ids"], mx, keys)
                    d.update({"group": g, "cut": ci, "turn": r["turn"], "conv": r["conv"], "rep": rep, "arm": arm,
                              "wall": time.time() - t0})
                    out.write(json.dumps(d) + "\n")
                    out.flush()
                    print(f"{g} c{ci} r{rep} {arm}: n={d['n']} reuse={d['resume']} pr={d['prompt_ms']:.0f} "
                          f"gen={d['produced']} {1000 * d['produced'] / max(d['decode_ms'], 1):.1f} tok/s "
                          f"acc {d['accepted']}/{d['offered']} {d['finish']}", flush=True)
            finally:
                eng.quit()
                note(f"[{a.tag}] engine ended")
            passes = []
            if a.forced and not STOP.exists():
                passes += [("timing", {"STRATA_DECODE_TIMING": "1"}, None),
                           ("profile", {"STRATA_DECODE_TIMING": "1", "STRATA_VERIFY_PROFILE": "1"}, None)]
            if a.startup_check and not STOP.exists():
                passes.append(("startup", {}, ["--spec", "8", "--mtp-max-t", "4"]))
            for name, env, spec_args in passes:
                if STOP.exists():
                    break
                eng = Engine(f"{a.tag}-{name}", env, spec_args)
                try:
                    if name == "startup":
                        r = [x for x in reqs if x["group"] == "short"][0]
                        jobs = [(r, -1, "")] + [(r, k, "") for k in range(3)]
                    else:
                        r = [x for x in reqs if x["group"] == "mid"][3]
                        jobs = [(r, -1, " spec_t=4 spec_s=4 spec_min_p=0")]
                        for k in range(2):
                            for t in map(int, a.forced.split(",")):
                                jobs.append((r, k, f" spec_t={t} spec_s={t} spec_min_p=0"))
                    for r, k, extra in jobs:
                        keys = f"temperature=0.6 seed={1000 + max(k, 0)}{extra}"
                        d = eng.gen(r["ids"], 256 if k < 0 else a.max_new, keys)
                        d.update({"group": name, "cut": 3, "rep": k, "arm": extra.strip() or "startup"})
                        out.write(json.dumps(d) + "\n")
                        out.flush()
                        print(f"{name} r{k} {extra.strip()}: gen={d['produced']} "
                              f"{1000 * d['produced'] / max(d['decode_ms'], 1):.1f} tok/s", flush=True)
                finally:
                    eng.quit()
                    note(f"[{a.tag}] {name} engine ended")
        finally:
            ok = start_server()
            note(f"[{a.tag}] DOWNTIME END (server loaded={ok})")
    finally:
        fh.seek(0)
        msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        fh.close()
        note(f"[{a.tag}] lock released")


if __name__ == "__main__":
    main()
