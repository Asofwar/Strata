"""One GPU window: hold the GPU lock, stop the live 8096 server when idle, run the job, always restore the server."""
import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

import psutil

sys.path.insert(0, r"E:\Projects\Strata-autotune")
from strata_control.tune_session import FileLock  # noqa: E402

SP = os.path.dirname(os.path.abspath(__file__))
PY = r"D:\Strata-dev\Strata\.venv\Scripts\python.exe"
LOCK = r"C:\Users\Admin\AppData\Local\Temp\strata-gpu.lock"
BASE = "http://127.0.0.1:8096"
BAT = r"E:\Projects\Strata-integrate\run-tiel-main.bat"
LIVE_ENGINE = r"E:\Projects\Strata-main\build\strata.exe".lower()
HANG_S = 900


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def get(path, timeout=5):
    with urllib.request.urlopen(BASE + path, timeout=timeout) as r:
        return json.loads(r.read())


def post(path, timeout=600):
    req = urllib.request.Request(BASE + path, data=b"{}", headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def live_procs():
    out = []
    for p in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            cmd = " ".join(p.info["cmdline"] or []).lower()
        except Exception:
            continue
        if ("strata-tiel-main.json" in cmd and "8096" in cmd) or "run-tiel-main.bat" in cmd:
            out.append(p)
    return out


def live_engines():
    out = []
    for p in psutil.process_iter(["pid", "name"]):
        if (p.info["name"] or "").lower() == "strata.exe":
            try:
                par = p.parent()
                pc = " ".join(par.cmdline()).lower() if par else ""
            except Exception:
                pc = ""
            if "strata-tiel-main.json" in pc:
                out.append(p)
    return out


def foreign_now(sec=3.0):
    return psutil.cpu_percent(interval=sec)


def stop_live():
    while True:
        try:
            st = get("/status")
        except Exception as e:
            log("status unreachable:", e)
            st = {"busy": False, "queued": 0, "down": True}
        if st.get("down"):
            break
        if not st.get("busy") and not st.get("queued"):
            code, body = post("/unload")
            log("unload:", code, body.strip()[:120])
            if code == 200:
                break
        else:
            log("live server busy:", st)
        time.sleep(10)
    t0 = time.time()
    while live_engines() and time.time() - t0 < 300:
        time.sleep(1)
    log("engine gone after", round(time.time() - t0, 1), "s; engines left:", [p.pid for p in live_engines()])
    procs = live_procs()
    for p in sorted(procs, key=lambda q: 0 if (q.info["name"] or "").lower() == "python.exe" else 1):
        try:
            log("stopping", p.pid, p.info["name"])
            for c in p.children(recursive=True):
                c.kill()
            p.kill()
        except psutil.NoSuchProcess:
            pass
    time.sleep(2)
    left = [p.pid for p in live_procs()] + [p.pid for p in live_engines()]
    log("live server stopped; left:", left)


def restore():
    subprocess.run(["powershell", "-NoProfile", "-Command", f"Start-Process '{BAT}'"], check=False)
    t0 = time.time()
    while time.time() - t0 < 900:
        try:
            m = get("/v1/models", timeout=5)
            s = m["data"][0].get("status", {}).get("value")
            if s == "loaded":
                log("live server back: loaded after", round(time.time() - t0, 1), "s")
                return True
        except Exception:
            pass
        time.sleep(3)
    log("LIVE SERVER NOT LOADED after 900 s")
    return False


def run_job(cmd, out_path):
    env = dict(os.environ, STRATA_KEEP_LEFTOVERS="1", PYTHONIOENCODING="utf-8")
    with open(out_path, "a", encoding="utf-8") as f:
        p = subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT, env=env, cwd=r"E:\Projects\Strata-autotune")
    last = [time.time(), os.path.getsize(out_path)]
    while p.poll() is None:
        time.sleep(5)
        sz = os.path.getsize(out_path)
        if sz != last[1]:
            last[:] = [time.time(), sz]
        elif time.time() - last[0] > HANG_S:
            log("no output for", HANG_S, "s: killing the job (hang)")
            for c in psutil.Process(p.pid).children(recursive=True):
                c.kill()
            p.kill()
            break
        if os.path.exists(os.path.join(SP, "STOP")):
            log("STOP file: killing the job")
            for c in psutil.Process(p.pid).children(recursive=True):
                c.kill()
            p.kill()
            break
    # an engine of ours left behind (the job killed) is ended here: only D:\Build\autotune's
    for q in psutil.process_iter(["pid", "name", "exe"]):
        try:
            if (q.info["exe"] or "").lower() == r"d:\build\autotune\strata.exe":
                log("ending our leftover engine", q.pid)
                q.kill()
        except Exception:
            pass
    return p.returncode


def main():
    job = sys.argv[1:]
    out_path = os.path.join(SP, "calib-run.log")
    log("waiting for the GPU lock")
    with FileLock(LOCK, log=log):
        log("lock held; others' CPU now:", foreign_now(), "%")
        t_down = time.time()
        stop_live()
        try:
            log("job:", " ".join(job))
            rc = run_job(job, out_path)
            log("job exit", rc, "after", round((time.time() - t_down) / 60, 1), "min of downtime")
        finally:
            ok = restore()
            log("8096 downtime", round((time.time() - t_down) / 60, 1), "min; restored:", ok)


if __name__ == "__main__":
    main()
