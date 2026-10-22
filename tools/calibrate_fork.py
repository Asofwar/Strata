"""The fork's own settings, tuned per PC (setup.py --calibrate-fork; `python tools/calibrate.py --fork <config>`).

Strata Turbo's pack path (Qwen3.6 / Ornith / Cyber-Tiel; docs/DETAILS.md, "Long contexts on the pack path") has
switches that were measured on one PC (an RTX 5080 16 GB with an i9-14900K) and that setup writes for every PC
(setup.PACK_TUNED), and switches that stay opt-in because they won there by a few percent or lost elsewhere.  This
measures them where the fork matters, at a long context, on the PC it runs on, and keeps a change only when it beats
the run-to-run noise and keeps the text:

  1. Per-request settings, one engine start (no restart per value): --pcie-frac, --spec-min-p and the window depth
     (--spec 3/4/5 through the spec_t / spec_s request keys of an engine started with the deepest).  Every request is
     a decode window after a long document read once (pinned with strata_prefix, so only the question is read again);
     the short prompts of tools/calibrate.py are the check that a long-context winner does not lose short answers.
  2. Engine variables, a restart each: every candidate against the baseline (setup's PACK_TUNED, so a default that is
     slower on this PC can be switched off, plus the settings below), FORK_ROUNDS starts each, the starts interleaved
     (every other round in reverse order).  A start gives one sample: decode tok/s after the long prompt, the long
     prompt's read speed, the short answers' tok/s and their greedy text.  A prompt switch rides on an exact decode
     arm (its decode is unchanged and that arm's text is checked in starts of its own), so it costs no starts.
  3. Text: an "exact" switch (the same bits by construction) must give the baseline's greedy text in --deterministic
     starts with a fixed expert cache; a "close" one (other rounding) must agree with the baseline about as long as
     two baseline starts agree with each other (TEXT_AGREE); a "ref" one runs the more exact arithmetic (no bar).
  4. Settings derived from the hardware, not from timing: STRATA_ARENA_WSLOCK on Windows, --kv-grow on the pack path,
     --vram-reserve-mib when less than the engine's safe line (1024 MiB under WDDM) stayed free, and the conversation
     cache's RAM from the RAM left with the model loaded (and an existing disk tier's budget from the free disk).

A budget in minutes (restarts cost a model load each) keeps the candidates in FORK_CANDIDATES order (expected value:
the measured gain and how likely it differs on another PC) until the estimate is spent; the plan and its estimate are
printed before anything runs.  Samples taken while other programs kept the CPU busy (FOREIGN_MAX) are taken again.
A non-finite answer (#879) or an engine that ends during a measurement stops the whole run.
"""
from __future__ import annotations

import math
import os
import re
import shutil
import statistics
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from itertools import combinations, product
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT))
import calibrate as CAL  # noqa: E402

WIN = os.name == "nt"

FORK_CONTEXT = 65536               # the target context of the pack families (their agents run at 30-200K)
FORK_ROUNDS = 3                    # engine starts per arm (each start one sample)
SWEEP_ROUNDS = 3                   # visits per value of a per-request sweep
CONFIRM_ROUNDS = 2                 # starts per arm of the last check (the tuned settings against the baseline)
DECODE_TOKENS = 256                # tokens per answer after the long prompt
QUESTIONS = (
    "Explain in detail, step by step, how the settings described in this document change the speed. Use at least 400 words.",
    "Write a long technical summary of the document above, section by section, with the numbers it gives.",
    "List every command-line flag and environment variable the document mentions, each with one sentence on what it does.",
    "Write a Python script that reads a configuration like the one in the document and prints each setting with a "
    "comment, then explain the code.",
)
SWEEP_QUESTIONS = 2                # answers per visit of a per-request sweep (the confirmation takes all of them)
SPEC_DEPTHS = (3, 4, 5)            # MTP window depths (--spec); the verify window adds the prompt lookup's +2
MIN_PS = (0.3, 0.4, 0.5, 0.6, 0.7)
PCIE_FRACS = CAL.PCIE_FRACS
TEXT_AGREE = 0.5                   # a "close" switch: median first differing token at least this share of the baseline's
FOREIGN_MAX = 0.10                 # other programs' CPU time, as a share of all logical CPUs, above which a sample is retaken
FOREIGN_RETRIES = 2
VRAM_SAFE_MIB = 1024 if WIN else 512   # the engine's kVramSafeMib: below it WDDM pages instead of failing (#2065)
ENGINE_RESERVE_MIB = 700           # the engine's --vram-reserve-mib default
KV_BYTES_PER_TOKEN = 11 * 2 * 2 * (256 + 256 // 64 * 2)   # setup.PACK_KV_BYTES_PER_TOKEN: int8 K/V of the pack path
CONV_STATE_MIB = 128               # a conversation's recurrent state besides its K/V (~118 MB a checkpoint)
CONV_SLOTS = 2
CONV_RAM_KEEP_GIB = 6.0            # RAM left to the PC beside the model and the conversation cache
CONV_RAM_SHARE = 0.5               # of the rest, the share the conversation cache may take
CONV_DISK_SHARE = 0.10             # of the free disk, the share an existing disk tier may take
CONV_DISK_MAX_MIB = 32768
CONV_DISK_MIN_MIB = 4096
CHECK_TOKENS = 128                 # greedy tokens per short prompt in the --deterministic text check
KQUANTS = {10, 11, 12, 13, 14}     # ggml Q2_K .. Q6_K: what STRATA_MMQ_KQ's library runs
IQ3_S, IQ4_XS = 21, 23
PRIOR_LOAD_S = 60.0                # the estimate before the first start is timed
PRIOR_READ_TOK_S = 5000.0
PRIOR_DECODE_TOK_S = 150.0
FLAG_ONLY = ("--kv-grow", "--deterministic")
MEASURE_DROP = ("--conversation-disk-dir", "--conversation-disk-mib", "--conversation-disk-persist",
                "--expert-profile-save")


class ForkAborted(RuntimeError):
    """A non-finite answer or an engine that ended mid-measurement: nothing more is run on this GPU."""


@dataclass(frozen=True)
class Cand:
    name: str      # shown and reported, e.g. "STRATA_IQ3S_MT1=1"
    env: tuple     # ((key, value or None), ...): the change to the baseline's variables; None removes the key
    kind: str      # "decode" (decode tok/s at the target context) or "prompt" (the long prompt's read speed)
    text: str      # "exact" (the same bits), "close" (other rounding), "ref" (the more exact arithmetic)
    group: str     # at most one candidate of a group is kept
    needs: tuple   # what the PC and the model must have (see NEEDS)
    why: str       # the measurement behind it


NEEDS = {"int8kv": "int8 K/V (--kv int8)", "sm80": "an NVIDIA card of compute capability 8.0 or newer",
         "cuda": "CUDA (not run on AMD yet)", "iq3s": "IQ3_S gate/up experts", "iq4xs": "IQ4_XS down experts",
         "avx2": "a CPU with AVX2 and without AVX-512 (where these CPU kernels run)",
         "kq": "K-quant experts and the K-quant library (strata_kq) beside the engine",
         "one_gpu": "one GPU (not a layer split)", "long_ctx": "a context of 128K or more", "win": "Windows",
         "pack": "the pack path (--pack)"}
WINDOW = ("int8kv", "sm80", "cuda")
# Expected-value order: the decode switches that moved this PC's long-context decode most, and the defaults most
# likely to be slower on another card, first.
FORK_CANDIDATES = (
    Cand("STRATA_IQ3S_MT1=1", (("STRATA_IQ3S_MT1", "1"),), "decode", "close", "iq3s", ("iq3s", "avx2"),
         "IQ3_S gate/up on Strata's kernel for one token too: 130K 131.5 -> 145.0, 200K 126.6 -> 163.2 tok/s (i9-14900K)"),
    Cand("STRATA_ADAPT_OVERLAP=1", (("STRATA_ADAPT_OVERLAP", "1"), ("STRATA_ADAPT_LAG", None)), "decode", "exact",
         "adapt", ("one_gpu",), "the expert tier's copies during the next window: +10-15% (RTX 5080), -21% (RTX 5090 Laptop)"),
    Cand("STRATA_ATTN_WINDOW_SMALL off", (("STRATA_ATTN_WINDOW_SMALL", None),), "decode", "close", "small", WINDOW,
         "setup's default: windows of up to 4 tokens on the streaming kernel, 200K 127.6 -> 160.7 tok/s (RTX 5080)"),
    Cand("STRATA_PROMPT_ATTN_DENSE_IMMA off", (("STRATA_PROMPT_ATTN_DENSE_IMMA", None),), "prompt", "ref", "imma", WINDOW,
         "setup's default: prompt attention on INT8 tensor cores, a 200K prompt 76.7 -> 53.8 s (RTX 5080)"),
    Cand("STRATA_IQ3S_FAST=1", (("STRATA_IQ3S_FAST", "1"), ("STRATA_IQ3S_MT1", "1")), "decode", "close", "iq3s",
         ("iq3s", "avx2"), "IQ3_S gate/up of 2+ tokens in fewer instructions (bit for bit STRATA_IQ3S_MT1): -19% pool time"),
    Cand("STRATA_POOL_FUSED=1", (("STRATA_POOL_FUSED", "1"),), "decode", "exact", "fused", ("pack",),
         "gate/up and down as one pool phase (same bits): -4 to -9% pool time per layer"),
    Cand("STRATA_ATTN_WINDOW_PREC=1", (("STRATA_ATTN_WINDOW_PREC", "1"),), "decode", "ref", "prec", WINDOW,
         "setup writes 2 (an FP16 p.v accumulator, half the MMAs of 0); 1 keeps FP32 sums there"),
    Cand("STRATA_IQ4XS_DOWN=1", (("STRATA_IQ4XS_DOWN", "1"),), "decode", "exact", "iq4xs", ("iq4xs", "avx2"),
         "IQ4_XS down rows decoded once per group (ggml's AVX2 dot bit for bit): -7% at one token, -15% at two"),
    Cand("STRATA_ATTN_SPLITS=256", (("STRATA_ATTN_SPLITS", "256"),), "decode", "close", "splits", ("long_ctx",),
         "split-K of the decode attention in 256 parts: 393 -> 30 MiB of VRAM kept at 262K, decode within noise"),
    Cand("STRATA_MMQ_KQ off", (("STRATA_MMQ_KQ", None),), "prompt", "ref", "kq", ("kq",),
         "setup's default: the Q6_K down experts on MMQ, a 200K prompt 51.8 -> 49.4 s (RTX 5080)"),
    Cand("STRATA_IQ4XS_DOWN=2", (("STRATA_IQ4XS_DOWN", "2"),), "decode", "exact", "iq4xs", ("iq4xs", "avx2"),
         "the same kernel from two tokens on (one token keeps ggml's dot)"),
    Cand("STRATA_ADAPT_LAG=2", (("STRATA_ADAPT_LAG", "2"), ("STRATA_ADAPT_OVERLAP", None)), "decode", "close", "adapt",
         ("one_gpu",), "the expert tier's swaps a window later: +3.5% on a P100, -1.3% on an RTX 3060"),
)
# setup's PACK_TUNED variables and what each needs to do anything (one that cannot run is left out of the baseline)
BASE_NEEDS = {"STRATA_ATTN_WINDOW": ("int8kv",), "STRATA_ATTN_WINDOW_PREC": ("int8kv",),
              "STRATA_ATTN_WINDOW_SMALL": ("int8kv",), "STRATA_PROMPT_ATTN_DENSE_IMMA": ("int8kv",),
              "STRATA_MMQ_KQ": ("kq",), "STRATA_ARENA_WSLOCK": ("win",)}


def fork_env_keys(base_env: dict) -> tuple:
    """Every variable the fork calibration decides: the baseline's (setup's PACK_TUNED) and the candidates'."""
    return tuple(dict.fromkeys([*base_env, *(k for c in FORK_CANDIDATES for k, _ in c.env)]))


def pack_base_env() -> dict:
    import setup
    return dict(setup.PACK_TUNED["env"])


# ------------------------------------------------------------------------------------------------ what applies here
def expert_types(pack: str | None) -> tuple[set, set]:
    """(gate/up types, down types) of the pack's native experts (native_experts.txt: layer gu_type d_type ...)."""
    gu, dn = set(), set()
    try:
        for line in (Path(pack) / "native_experts.txt").read_text(encoding="utf-8").splitlines():
            f = line.split()
            if len(f) >= 3 and not line.startswith("#") and f[1].isdigit() and f[2].isdigit():
                gu.add(int(f[1]))
                dn.add(int(f[2]))
    except (OSError, TypeError):
        pass
    return gu, dn


def kq_library(exe: str) -> bool:
    d = Path(exe).parent
    return (d / "strata_kq.dll").is_file() or (d / "libstrata_kq.so").is_file()


def host_facts(cfg: dict) -> dict:
    """This PC: Windows, AVX2 / AVX-512, the GPU's compute capability (setup's probes)."""
    import setup
    _, avx2, avx512 = setup.cpu_info()
    sel = cfg.get("gpu")
    g = setup.gpu_info(sel if isinstance(sel, int) else None) or {}
    try:
        cc = int(str(g.get("arch") or "0"))
    except ValueError:
        cc = 0
    return {"win": WIN, "avx2": bool(avx2), "avx512": bool(avx512), "cc": cc, "gpu": g.get("name"),
            "gpu_index": g.get("index", 0)}


def facts_for(cfg: dict, args: list, host: dict) -> dict:
    gu, dn = expert_types(CAL.arg_value(args, "--pack"))
    kv = CAL.arg_value(args, "--kv") or "int8"
    try:
        ctx = int(CAL.arg_value(args, "--max-context") or 0)
    except ValueError:
        ctx = 0
    split = "--layer-split" in args or isinstance(cfg.get("gpu"), list) and len(cfg["gpu"]) > 1
    return {"pack": "--pack" in args, "int8kv": kv == "int8", "sm80": host.get("cc", 0) >= 80,
            "cuda": cfg.get("backend") not in ("hip", "sycl"), "iq3s": IQ3_S in gu, "iq4xs": IQ4_XS in dn,
            "avx2": host.get("avx2") and not host.get("avx512"),
            "kq": bool((gu | dn) & KQUANTS) and kq_library(cfg.get("exe", "")),
            "one_gpu": not split, "long_ctx": ctx >= 131072, "win": host.get("win", WIN),
            "experts": {"gate_up": sorted(gu), "down": sorted(dn)}, "max_context": ctx}


def missing(needs, facts) -> str | None:
    return next((NEEDS[n] for n in needs if not facts.get(n)), None)


def applicable(facts) -> tuple[list, list]:
    """(the candidates that can run here, in FORK_CANDIDATES order; [(name, what it needs)] for the others)."""
    ok, no = [], []
    for c in FORK_CANDIDATES:
        why = missing(c.needs, facts)
        (no.append((c.name, why)) if why else ok.append(c))
    return ok, no


def baseline_env(cfg_env: dict | None, base_env: dict, facts) -> dict:
    """The config's variables outside the fork's set, and setup's PACK_TUNED ones that can run here."""
    keys = fork_env_keys(base_env)
    out = {k: v for k, v in (cfg_env or {}).items() if k not in keys}
    for k, v in base_env.items():
        if missing(BASE_NEEDS.get(k, ()), facts) is None:
            out[k] = v
    return out


def env_with(env: dict, changes) -> dict:
    out = dict(env)
    for k, v in changes:
        if v is None:
            out.pop(k, None)
        else:
            out[k] = v
    return out


# ------------------------------------------------------------------------------------------------ args
def with_flag(args: list, flag: str, on: bool) -> list:
    out = [a for a in args if a != flag]
    return out + [flag] if on else out


def measure_args(args: list) -> list:
    """The args a measurement start runs with: without the conversation disk tier (a calibration's conversations must
    not be written over the user's, nor wait at QUIT) and without --expert-profile-save (its short prompts must not
    replace a learned profile)."""
    out = list(args)
    for flag in MEASURE_DROP:
        out = CAL.with_arg(out, flag, None)
    return out


def apply_fork(args: list, env: dict | None, fork: dict | None) -> tuple[list, dict]:
    """A config's args and env with a fork calibration: each setting it names is set (True: the flag on, None or
    False: removed), the others stay; each variable it decided is set or removed (None), the config's others stay."""
    fork = fork or {}
    out = list(args)
    for flag, v in (fork.get("settings") or {}).items():
        if flag in FLAG_ONLY:
            out = with_flag(out, flag, bool(v))
        else:
            out = CAL.with_arg(out, flag, None if v is None or v is False else str(v))
    decided = fork.get("env") or {}
    e = {k: v for k, v in (env or {}).items() if k not in decided}
    e.update({k: v for k, v in decided.items() if v is not None})
    return out, e


# ------------------------------------------------------------------------------------------------ the hardware
def gpu_free_mib(index: int = 0) -> int | None:
    try:
        s = subprocess.run(["nvidia-smi", "-i", str(index), "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
                           capture_output=True, text=True, timeout=10).stdout.strip().splitlines()
        return int(float(s[0])) if s else None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def ram_available_gib() -> float | None:
    try:
        import psutil
        return psutil.virtual_memory().available / 2**30
    except ImportError:
        pass
    if WIN:
        try:
            import setup
            return setup._memory_status().ullAvailPhys / 2**30
        except Exception:
            return None
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemAvailable"):
                    return int(line.split()[1]) / 2**20
    except (OSError, ValueError):
        pass
    return None


def disk_free_gib(path: str) -> float | None:
    p = Path(path)
    while not p.exists() and p.parent != p:
        p = p.parent
    try:
        return shutil.disk_usage(p).free / 2**30
    except OSError:
        return None


def log_free_mib(log: str | None, since: int) -> int | None:
    """The engine's own "N MiB of VRAM free with everything loaded" of the start that wrote its log after `since`."""
    if not log:
        return None
    try:
        with open(log, "rb") as f:
            f.seek(since)
            text = f.read().decode("utf-8", "replace")
    except OSError:
        return None
    m = re.search(r"strata serve: (\d+) MiB of VRAM free with everything loaded", text)
    return int(m.group(1)) if m else None


def conv_mib(tokens: int) -> int:
    return int(tokens * KV_BYTES_PER_TOKEN / 2**20) + CONV_STATE_MIB


def derived_settings(args: list, facts: dict, measured: dict) -> tuple[dict, dict]:
    """The settings that follow from the hardware, not from timing: ({flag: value}, {flag: why})."""
    s, why = {}, {}
    if facts.get("pack"):
        s["--kv-grow"] = True
        why["--kv-grow"] = "the pack path: the K/V takes VRAM as the context grows (more expert slots at the start)"
    free = measured.get("vram_free_mib")
    if free is not None:
        cur = int(CAL.arg_value(args, "--vram-reserve-mib") or ENGINE_RESERVE_MIB)
        if free < VRAM_SAFE_MIB:
            want = cur + VRAM_SAFE_MIB - free
            s["--vram-reserve-mib"] = str(int(math.ceil(want / 64.0)) * 64)
            why["--vram-reserve-mib"] = (f"{free} MiB of VRAM stayed free with the model loaded and a long prompt read, "
                                         f"below the engine's safe line of {VRAM_SAFE_MIB} MiB: the reserve grows from "
                                         f"{cur} by the difference")
        else:
            why["--vram-reserve-mib"] = f"{free} MiB stayed free (at least {VRAM_SAFE_MIB}): unchanged"
    ctx = facts.get("max_context") or 0
    ram = measured.get("ram_avail_gib")
    target = measured.get("target_ctx") or FORK_CONTEXT
    if ram is not None and facts.get("pack"):
        room = (ram - CONV_RAM_KEEP_GIB) * 1024 * CONV_RAM_SHARE
        want = CONV_SLOTS * conv_mib(ctx or target)
        mib = int(min(room, want) // 512) * 512
        one = conv_mib(min(target, ctx) if ctx else target)
        if mib >= one:
            slots = max(1, min(CONV_SLOTS, mib // one))
            s.update({"--conversation-cache-mib": str(mib), "--conversation-cache-slots": str(slots)})
            why["--conversation-cache-mib"] = (f"{ram:.1f} GiB of RAM available with the model loaded: half of what is left "
                                               f"beyond {CONV_RAM_KEEP_GIB:g} GiB, at most {CONV_SLOTS} conversations at the "
                                               f"full context ({want} MiB)")
        else:
            s.update({"--conversation-cache-mib": None, "--conversation-cache-slots": None})
            why["--conversation-cache-mib"] = (f"{ram:.1f} GiB of RAM available with the model loaded: no room for a "
                                               f"conversation of {target} tokens ({one} MiB): off")
    disk = CAL.arg_value(args, "--conversation-disk-dir")
    free_disk = measured.get("disk_free_gib")
    if disk and free_disk is not None:
        mib = int(min(CONV_DISK_MAX_MIB, free_disk * 1024 * CONV_DISK_SHARE) // 1024) * 1024
        if mib >= CONV_DISK_MIN_MIB:
            s["--conversation-disk-mib"] = str(mib)
            why["--conversation-disk-mib"] = (f"{free_disk:.0f} GiB free on the disk of {disk}: a tenth of it, at most "
                                              f"{CONV_DISK_MAX_MIB} MiB")
        else:
            s.update({"--conversation-disk-dir": None, "--conversation-disk-mib": None,
                      "--conversation-disk-persist": None})
            why["--conversation-disk-mib"] = f"{free_disk:.0f} GiB free on the disk of {disk}: too little, the disk tier is off"
    return s, why


# ------------------------------------------------------------------------------------------------ CPU load of others
class Foreign:
    """Other programs' CPU time while a sample ran, as a share of all logical CPUs (None without psutil)."""

    def __init__(self):
        try:
            import psutil
            self.ps = psutil
        except ImportError:
            self.ps = None

    def begin(self, pids):
        if self.ps is None:
            return None
        procs = []
        for pid in [os.getpid(), *[p for p in pids if p]]:
            try:
                procs.append(self.ps.Process(pid))
            except Exception:
                pass
        return (self.ps.cpu_times(), procs, [self._proc_s(p) for p in procs])

    def _proc_s(self, p) -> float:
        try:
            t = p.cpu_times()
            return t.user + t.system
        except Exception:
            return 0.0

    def end(self, token) -> float | None:
        if token is None or self.ps is None:
            return None
        t0, procs, p0 = token
        t1 = self.ps.cpu_times()
        total = sum(t1) - sum(t0)
        busy = total - (t1.idle - t0.idle)
        ours = sum(self._proc_s(p) - a for p, a in zip(procs, p0))
        return max(0.0, (busy - ours) / total) if total > 0 else None


# ------------------------------------------------------------------------------------------------ one engine
def first_diff(a, b) -> int:
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return i
    return min(len(a), len(b))


def agreement(xs: list, ys: list | None = None) -> float | None:
    """Median position of the first differing token over the prompts of every pair of starts (a start: its texts in
    prompt order); ys None: the pairs within xs."""
    pairs = combinations(xs, 2) if ys is None else product(xs, ys)
    vals = [first_diff(ta, tb) for x, y in pairs for ta, tb in zip(x, y)]
    return statistics.median(vals) if vals else None


class LongContext:
    """The target-context measurement on one running engine: a long document read once (pinned with strata_prefix,
    so a question after it reads only the question), decode answers after it, and the short prompts."""

    def __init__(self, eng, tok_parts, ctx, short_ids, cancel=None, foreign=None, say=print, log=None, log_since=0):
        self.eng, self.parts, self.ctx, self.short_ids = eng, tok_parts, ctx, short_ids
        self.cancel = cancel or threading.Event()
        self.foreign = foreign
        self.say = say
        self.log, self.log_since = log, log_since
        self.doc = None
        self.rereads = 0

    def _gen(self, ids, max_new, tune=None, pin=None):
        if self.cancel.is_set():
            raise CAL.CalibrationCancelled("calibration cancelled")
        sampling = {"temperature": 0}
        if pin:
            sampling["strata_prefix"] = {"tokens": pin}
        if tune:
            sampling["strata_tune"] = tune
        try:
            out = [t for t in self.eng.generate(ids, max_new, sampling, self.cancel) if t is not None]
        except CAL.CalibrationCancelled:
            raise
        except Exception as e:  # noqa: BLE001 - an engine that ends or hangs mid-measurement stops the run (the GPU)
            why = str(e).strip().splitlines()[0][:200] if str(e).strip() else type(e).__name__
            raise ForkAborted(f"the engine stopped during a measurement: {why}") from e
        last = dict(self.eng.last or {})
        if last.get("finish") == "nonfinite":
            raise ForkAborted("the engine met non-finite logits (#879): the run stops here")
        return out, last

    def read(self, i: int) -> dict:
        """Read document `i` (fresh: its header differs from every other) and keep it as the prefix of the answers."""
        doc, question = self.parts(i, self.ctx)
        self.doc = doc
        _, last = self._gen(doc + question(0), 16, pin=len(doc))
        ms = float(last.get("prompt_ms") or 0.0)
        n = float(last.get("prompt_read") or (last.get("prompt_tokens") or 0) - (last.get("reused") or 0))
        return {"tokens": int(n), "ms": round(ms, 1), "tok_s": round(n / (ms / 1000.0), 1) if ms > 0 and n > 0 else 0.0}

    def answers(self, tune=None, questions=None, max_new=DECODE_TOKENS, measure=True) -> dict:
        """Decode answers to the questions after the document: tokens over decode time, their texts, others' CPU
        (`measure` False: a warm-up, the CPU load is not read)."""
        _, question = self.parts(0, self.ctx)
        n = ms = 0.0
        texts = []
        pid = getattr(getattr(self.eng, "proc", None), "pid", None)
        tok = self.foreign.begin([pid]) if self.foreign and measure else None
        for q in range(len(QUESTIONS) if questions is None else questions):
            out, last = self._gen(self.doc + question(q), max_new, tune, pin=len(self.doc))
            read = float(last.get("prompt_tokens") or 0) - float(last.get("reused") or 0)
            if read > len(self.doc) // 2:
                self.rereads += 1                  # the pinned prefix was not kept: the measurement is still fair
            texts.append(out)
            n += len(out)
            ms += float(last.get("decode_ms") or 0.0)
        fl = self.foreign.end(tok) if self.foreign and measure else None
        return {"tok_s": n / (ms / 1000.0) if ms > 0 and n > 8 else 0.0, "texts": texts, "foreign": fl}

    def answers_checked(self, tune=None, questions=None) -> dict:
        """answers(), taken again (up to FOREIGN_RETRIES times) while other programs keep the CPU busy; the sample with
        the least foreign load is kept, every load is reported."""
        best, loads = None, []
        for k in range(1 + FOREIGN_RETRIES):
            a = self.answers(tune, questions)
            loads.append(None if a["foreign"] is None else round(a["foreign"], 3))
            if best is None or (a["foreign"] or 0.0) < (best["foreign"] or 0.0):
                best = a
            if a["foreign"] is None or a["foreign"] <= FOREIGN_MAX:
                break
            if k < FOREIGN_RETRIES:
                self.say(f"    other programs took {a['foreign'] * 100:.0f}% of the CPU during this sample: taking it again")
        best = dict(best)
        best["foreign_loads"] = loads
        return best

    def short(self, max_new=CAL.MAX_NEW) -> dict:
        texts: list = []
        rate = CAL.Session(self.eng, self.short_ids, self.cancel).rate(max_new=max_new, texts=texts)
        if (self.eng.last or {}).get("finish") == "nonfinite":
            raise ForkAborted("the engine met non-finite logits (#879): the run stops here")
        return {"tok_s": rate, "texts": texts}


def doc_parts(tok):
    """parts(i, ctx) -> (document ids, question(q) -> ids): the docs' text up to `ctx` tokens after a header of its
    own (a fresh read for every i, the same text for every arm), then a question that asks for a long answer."""
    text = "\n\n".join(p.read_text(encoding="utf-8", errors="replace") for p in sorted((ROOT / "docs").glob("*.md")))
    body = tok.encode(text, parse_special=False) or [0]
    tails = [tok.encode(f"\n\n{q}<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n", parse_special=True)
             for q in QUESTIONS]
    room = max(len(t) for t in tails) + DECODE_TOKENS + 64

    def parts(i: int, ctx: int):
        head = tok.encode(f"<|im_start|>user\n[calibration read {i}] Here is a document:\n", parse_special=True)
        n = max(256, ctx - room - len(head))
        return head + (body * (n // len(body) + 1))[:n], (lambda q: tails[q % len(tails)])
    return parts


# ------------------------------------------------------------------------------------------------ the plan
def costs(ctx: int, load_s: float = PRIOR_LOAD_S, read_tok_s: float = PRIOR_READ_TOK_S,
          decode_tok_s: float = PRIOR_DECODE_TOK_S) -> dict:
    ans = DECODE_TOKENS / decode_tok_s + 0.3
    short = len(CAL.PROMPTS) * (CAL.MAX_NEW / decode_tok_s + 0.2)
    return {"load": load_s + 5.0, "read": ctx / read_tok_s, "answer": ans, "short": short,
            "start1": load_s + 5.0 + ctx / read_tok_s + (len(QUESTIONS) + 1) * ans + short}


def start_s(c: dict, reads: int) -> float:
    return c["start1"] + (reads - 1) * c["read"]


def requests_s(c: dict, n_pcie: int, n_minp: int, n_depth: int) -> float:
    visits = SWEEP_ROUNDS * (n_pcie + n_minp + n_depth)
    confirm = 2 * SWEEP_ROUNDS * (len(QUESTIONS) * c["answer"] + c["short"])
    probe = c["load"] + c["read"] + 2 * c["answer"]    # the VRAM / RAM probe with the chosen depth
    return c["start1"] + visits * SWEEP_QUESTIONS * c["answer"] + confirm + probe


def arms_of(cands: list) -> list:
    """Each decode candidate is an arm; a prompt candidate rides on an exact decode arm (its decode and that arm's
    deterministic text are unchanged by a prompt kernel), else it gets an arm of its own."""
    arms = [{"name": c.name, "cands": [c]} for c in cands if c.kind == "decode"]
    for c in (c for c in cands if c.kind == "prompt"):
        host = next((a for a in arms if len(a["cands"]) == 1 and a["cands"][0].text == "exact"), None)
        if host is not None:
            host["cands"].append(c)
            host["name"] += " + " + c.name
        else:
            arms.append({"name": c.name, "cands": [c]})
    return arms


def arm_reads(arm: dict | None) -> int:
    """Long prompts read per start: two where a prompt candidate (or the baseline) is judged by them."""
    return 2 if arm is None or any(c.kind == "prompt" for c in arm["cands"]) else 1


def restarts_s(c: dict, cands: list) -> float:
    arms = arms_of(cands)
    if not arms:
        return 0.0
    per_round = start_s(c, arm_reads(None) if any(x.kind == "prompt" for x in cands) else 1) + \
        sum(start_s(c, arm_reads(a)) for a in arms)
    exact = sum(1 for x in cands if x.text == "exact")
    check = (2 + exact) * (c["load"] + c["short"] * CHECK_TOKENS / CAL.MAX_NEW) if exact else 0.0
    return FORK_ROUNDS * per_round + check


def plan(cands: list, c: dict, budget_s: float, fixed_s: float, confirm: bool = True, compare: bool = False) -> dict:
    """The candidates in order while the estimate fits the budget; then the last check if it still fits."""
    kept, dropped = [], []
    for x in cands:
        if fixed_s + restarts_s(c, kept + [x]) <= budget_s:
            kept.append(x)
        else:
            dropped.append(x)
    rest = restarts_s(c, kept)
    conf = CONFIRM_ROUNDS * (2 + (1 if compare else 0)) * c["start1"] if confirm and kept else 0.0
    if fixed_s + rest + conf > budget_s:
        conf = 0.0
    return {"kept": kept, "dropped": dropped, "requests_s": fixed_s, "restarts_s": rest, "confirm_s": conf,
            "total_s": fixed_s + rest + conf}


def say_plan(p: dict, c: dict, ctx: int, budget_s: float, no: list, say, n_values: tuple) -> None:
    m = lambda s: f"~{max(1, round(s / 60))} min"    # noqa: E731
    arms = arms_of(p["kept"])
    say(f"  The fork's settings, measured at {ctx // 1024}K of context (budget {budget_s / 60:.0f} min):")
    say(f"    1. one engine start, per request: PCIe share ({n_values[0]} values), draft floor ({n_values[1]}), window "
        f"depth ({n_values[2]}), {SWEEP_ROUNDS} rounds, then the winner against the config's own: {m(p['requests_s'])}")
    if arms:
        say(f"    2. {FORK_ROUNDS} engine starts each, interleaved: the baseline (setup's settings) and {len(arms)} "
            f"arms for {len(p['kept'])} candidates ({FORK_ROUNDS * (len(arms) + 1)} starts, plus the text check of the "
            f"exact ones): {m(p['restarts_s'])}")
        for a in arms:
            for x in a["cands"]:
                say(f"       {x.name}: {x.why}")
    if p["confirm_s"]:
        say(f"    3. the tuned settings against the baseline, {CONFIRM_ROUNDS} starts each: {m(p['confirm_s'])}")
    for name, why in no:
        say(f"    not here: {name} (needs {why})")
    for x in p["dropped"]:
        say(f"    left out for the budget: {x.name}")
    say(f"  Estimated: {m(p['total_s'])} (an engine start ~{c['start1']:.0f} s: ~{c['load']:.0f} s to load, a "
        f"{ctx // 1024}K prompt ~{c['read']:.0f} s, {len(QUESTIONS)} answers of {DECODE_TOKENS} tokens)")


# ------------------------------------------------------------------------------------------------ deciding
def gain_vs(base: list, cand: list) -> tuple[bool, float, float]:
    """calibrate.switch_wins: faster by more than the baseline's own spread (at least MIN_GAIN)."""
    return CAL.switch_wins([x for x in base if x], [x for x in cand if x])


def decide(cand: Cand, base: dict, arm: dict, say) -> dict:
    """One candidate against the baseline's samples: speed (its kind's), the short answers, the text bar."""
    key = "prompt" if cand.kind == "prompt" else "decode"
    b = [x for s in base for x in (s[key] if key == "prompt" else [s[key]])]
    a = [x for s in arm for x in (s[key] if key == "prompt" else [s[key]])]
    wins, gain, margin = gain_vs(b, a)
    d = {"gain": round(gain, 4), "margin": round(margin, 4), "faster": wins,
         "samples": [round(x, 1) for x in a], "base": [round(x, 1) for x in b]}
    if wins and cand.kind == "decode":           # a long-context winner must not lose the short answers
        sw, sg, sm = gain_vs([s["short"] for s in base], [s["short"] for s in arm])
        d["short_gain"] = round(sg, 4)
        if sg < -sm:
            d["faster"] = wins = False
            d["why"] = f"short answers {sg * 100:+.1f}% (noise {sm * 100:.1f}%)"
    if wins and cand.text == "close":
        bb = agreement([s["texts"] for s in base])
        cb = agreement([s["texts"] for s in arm], [s["texts"] for s in base])
        d["agree"] = {"baseline": bb, "candidate": cb}
        if bb is None or cb is None or cb < TEXT_AGREE * bb:
            d["faster"] = wins = False
            d["why"] = (f"its text parts from the baseline's at token {cb} (two baseline starts: {bb})"
                        if bb is not None and cb is not None else "too few starts to check the text")
    unit = "prompt tok/s" if key == "prompt" else "tok/s"
    say(f"    {cand.name}: {statistics.median(a) if a else 0:.1f} {unit} against {statistics.median(b) if b else 0:.1f}, "
        f"{gain * 100:+.1f}% (noise {margin * 100:.1f}%)" + (" -> faster" if d["faster"] else "")
        + (f"; not kept: {d['why']}" if d.get("why") else ""))
    return d


def resolve_groups(cands: list, decisions: dict) -> list:
    """The winners, at most one per group (the largest gain)."""
    best: dict = {}
    for c in cands:
        d = decisions.get(c.name) or {}
        if d.get("faster") and d.get("text_ok", c.text != "exact") and \
                (c.group not in best or d["gain"] > decisions[best[c.group].name]["gain"]):
            best[c.group] = c
    return [c for c in cands if best.get(c.group) is c]


# ------------------------------------------------------------------------------------------------ the run
def run_fork(cfg: dict, say=print, start_engine=None, *, budget_min: float = 60.0, ctx: int | None = None,
             host: dict | None = None, base_env: dict | None = None, measure_host=None, foreign=None,
             compare: dict | None = None, dry_run: bool = False, clock=time.monotonic, cancel_event=None,
             tok=None) -> dict:
    """Measure the fork's settings on the engine `cfg` describes; returns {"settings": {flag: value}, "env": {var:
    value or None}, "report": {...}} (apply_fork writes it into a config).  `start_engine(args, env)` returns a
    started engine whose environment is `env` (the full variable set of the arm).  `measure_host()` returns the
    hardware readings {"vram_free_mib", "ram_avail_gib", "disk_free_gib"} (tests pass their own).  `compare`: another
    config whose args and env run as an extra arm of the last check (reported, never chosen)."""
    t0 = clock()
    report: dict = {"target_ctx": None}
    host = host if host is not None else host_facts(cfg)
    base_env = pack_base_env() if base_env is None else dict(base_env)
    args0 = CAL.engine_args(cfg)
    facts = facts_for(cfg, args0, host)
    if not facts["pack"]:
        raise RuntimeError("--calibrate-fork tunes the pack path's settings (Qwen3.6 / Ornith / Cyber-Tiel, --pack): "
                           "this config does not use it")
    max_ctx = facts["max_context"] or FORK_CONTEXT
    ctx = min(ctx or FORK_CONTEXT, max_ctx)
    report.update(target_ctx=ctx, host={k: v for k, v in host.items()}, experts=facts["experts"])
    keys = fork_env_keys(base_env)
    env0 = baseline_env(cfg.get("env"), base_env, facts)
    cands, no = applicable(facts)
    report["not_applicable"] = dict(no)
    log = cfg.get("log")
    if start_engine is None:
        from serve.server import StrataEngine, child_env

        def start_engine(args, env):
            e = child_env({**cfg, "env": env})
            for k in keys:                      # the arm's set only: none from the calibration's own environment
                if k not in env:
                    e.pop(k, None)
            return StrataEngine(cfg["exe"], args, cwd=cfg.get("cwd"), log=log, env=e)
    if measure_host is None:
        gi = host.get("gpu_index", 0)

        def measure_host():
            disk = CAL.arg_value(args0, "--conversation-disk-dir")
            return {"vram_free_mib": gpu_free_mib(gi), "ram_avail_gib": ram_available_gib(),
                    "disk_free_gib": disk_free_gib(disk) if disk else None}
    foreign = Foreign() if foreign is None else foreign
    cancel = cancel_event or threading.Event()

    # the per-request settings' defaults: the config's own
    d_depth = int(CAL.arg_value(args0, "--spec") or 4)
    d_minp = round(float(CAL.arg_value(args0, "--spec-min-p") or 0.5), 2)
    d_pcie = CAL.arg_value(args0, "--pcie-frac")
    d_pcie = None if d_pcie is None else round(float(d_pcie), 2)
    depths = sorted(set(SPEC_DEPTHS) | {d_depth})
    pcies = sorted(set(PCIE_FRACS) | ({d_pcie} if d_pcie is not None else set()))
    minps = sorted(set(MIN_PS) | {d_minp})
    pcie_vals = ([None] if d_pcie is None else []) + pcies          # None: the engine's own share (no request key)
    c = costs(ctx)
    budget_s = budget_min * 60.0
    fixed = requests_s(c, len(pcie_vals), len(minps), len(depths))
    p = plan(cands, c, budget_s, fixed, compare=compare is not None)
    say_plan(p, c, ctx, budget_s, no, say, (len(pcie_vals), len(minps), len(depths)))
    report["plan"] = {"kept": [x.name for x in p["kept"]], "dropped": [x.name for x in p["dropped"]],
                      "estimate_min": round(p["total_s"] / 60, 1)}
    if dry_run:
        return {"settings": {}, "env": {}, "report": report}

    if tok is None:
        tok = CAL.load_tokenizer(cfg)
    parts = doc_parts(tok)
    short_ids = [CAL.chat_ids(tok, q) for q in CAL.PROMPTS]
    margs = measure_args(args0)

    def open_start(args, env, what):
        since = os.path.getsize(log) if log and os.path.isfile(log) else 0
        t = clock()
        e = CAL.restart(lambda a: start_engine(a, env), args, what, say, report)
        return e, clock() - t, since

    # ---- 1. the per-request settings, one engine started with the deepest window
    say(f"  1/3 Per-request settings at {ctx // 1024}K (one engine start) ...")
    a1 = CAL.with_arg(margs, "--spec", str(max(depths)))
    e, load_s, since = open_start(a1, env0, "the per-request settings")
    if e is None:
        raise RuntimeError("the engine did not start: " + next(iter(report.get("failed_starts", {}).values()), "?"))
    try:
        info = dict(getattr(e, "info", {}) or {})
        offset = max(0, int(info.get("spec", max(depths) + 2)) - int(info.get("mtp_max", max(depths))))
        lc = LongContext(e, parts, ctx, short_ids, cancel, foreign, say)
        read = lc.read(1)
        lc.answers(questions=1, max_new=64, measure=False)          # warm-up: the tier starts to follow the text
        say(f"    the {ctx // 1024}K prompt read in {read['ms'] / 1000:.1f} s ({read['tok_s']:.0f} tok/s); engine "
            f"start {load_s:.0f} s")
        hw = dict(measure_host())
        hw["vram_free_log_mib"] = log_free_mib(log, since)
        dec_probe = lc.answers(questions=1, measure=False)
        c = costs(ctx, load_s, read["tok_s"] or PRIOR_READ_TOK_S, dec_probe["tok_s"] or PRIOR_DECODE_TOK_S)

        def tune(pcie, minp, depth):
            t = {"spec_min_p": minp, "spec_t": depth, "spec_s": min(depth + offset, 8)}
            if pcie is not None:
                t["pcie_frac"] = pcie
            return t

        def sweep(values, mk, label):
            out = {v: [] for v in values}
            for r in range(SWEEP_ROUNDS):
                for v in (values if r % 2 == 0 else values[::-1]):
                    out[v].append(lc.answers_checked(mk(v), SWEEP_QUESTIONS)["tok_s"])
            med = {v: statistics.median(x) for v, x in out.items()}
            best = max(med, key=med.get)
            say(f"    {label}: " + ", ".join(f"{'auto' if v is None else f'{v:g}'} {med[v]:.1f}" for v in values)
                + f" -> {'auto' if best is None else f'{best:g}'}")
            return out, best

        by_pcie, b_pcie = sweep(pcie_vals, lambda v: tune(v, d_minp, d_depth), "PCIe share")
        by_minp, b_minp = sweep(minps, lambda v: tune(b_pcie, v, d_depth), "draft floor")
        by_depth, b_depth = sweep(depths, lambda v: tune(b_pcie, b_minp, v), "window depth")
        dflt, cand = (d_pcie, d_minp, d_depth), (b_pcie, b_minp, b_depth)
        conf = {"default": {"long": [], "short": []}, "tuned": {"long": [], "short": []}}
        if cand != dflt:
            for r in range(SWEEP_ROUNDS):
                for k, v in ((("default", dflt), ("tuned", cand)) if r % 2 == 0 else (("tuned", cand), ("default", dflt))):
                    conf[k]["long"].append(lc.answers_checked(tune(*v))["tok_s"])
                    texts: list = []
                    conf[k]["short"].append(CAL.Session(e, short_ids, cancel).rate(tune=tune(*v), texts=texts))
            wins, gain, margin = gain_vs(conf["default"]["long"], conf["tuned"]["long"])
            _, sg, sm = gain_vs(conf["default"]["short"], conf["tuned"]["short"])
            keep = wins and sg >= -sm
            say(f"    the winner {'auto' if b_pcie is None else b_pcie} / {b_minp:g} / depth {b_depth} against the "
                f"config's {'auto' if d_pcie is None else d_pcie} / {d_minp:g} / depth {d_depth}: {gain * 100:+.1f}% "
                f"(noise {margin * 100:.1f}%), short answers {sg * 100:+.1f}%" + (" -> kept" if keep else " -> not kept"))
        else:
            keep, gain = False, 0.0
            say("    the config's own values are the fastest")
        chosen = cand if keep else dflt
        report["requests"] = {"read": read, "load_s": round(load_s, 1), "offset": offset,
                              "pcie": {str(k): [round(x, 1) for x in v] for k, v in by_pcie.items()},
                              "min_p": {str(k): [round(x, 1) for x in v] for k, v in by_minp.items()},
                              "depth": {str(k): [round(x, 1) for x in v] for k, v in by_depth.items()},
                              "confirm": {k: {kk: [round(x, 1) for x in vv] for kk, vv in v.items()}
                                          for k, v in conf.items()},
                              "chosen": {"pcie_frac": chosen[0], "spec_min_p": chosen[1], "depth": chosen[2]},
                              "gain": round(gain, 4), "rereads": lc.rereads}
    finally:
        CAL.close(e)
    settings: dict = {"--spec": str(chosen[2]), "--spec-min-p": f"{chosen[1]:.2f}",
                      "--pcie-frac": None if chosen[0] is None else f"{chosen[0]:.2f}"}
    env_win = {"STRATA_ARENA_WSLOCK": "1" if facts["win"] else None}
    env_base = env_with(env0, env_win.items())
    # ---- the hardware-derived settings, from a start with the chosen window depth (step 1's deepest window takes
    # more VRAM for its buffers: 512 MiB at 7 tokens and 262K on an RTX 5080), into the baseline of the restarts
    hw1 = hw
    probe = measure_args(apply_fork(args0, {}, {"settings": {**settings, "--kv-grow": True}})[0])
    say("  Measuring the VRAM and RAM left with these settings (one engine start) ...")
    e, _, since = open_start(probe, env_base, "the VRAM probe")
    hw = {k: v for k, v in hw1.items() if k in ("ram_avail_gib", "disk_free_gib")}
    if e is not None:
        try:
            lc = LongContext(e, parts, ctx, short_ids, cancel, foreign, say)
            lc.read(1)
            lc.answers(questions=1, measure=False)
            hw = dict(measure_host())
            hw["vram_free_log_mib"] = log_free_mib(log, since)
            hw["expert_slots"] = int((getattr(e, "info", None) or {}).get("expert_slots") or 0) or None
        finally:
            CAL.close(e)
    hw_free = [x for x in (hw.get("vram_free_mib"), hw.get("vram_free_log_mib")) if x is not None]
    measured = {"vram_free_mib": min(hw_free) if hw_free else None, "ram_avail_gib": hw.get("ram_avail_gib"),
                "disk_free_gib": hw.get("disk_free_gib"), "target_ctx": ctx}
    derived, derived_why = derived_settings(args0, facts, measured)
    settings.update(derived)
    rnd = lambda d: {k: (round(v, 1) if isinstance(v, float) else v) for k, v in d.items()}   # noqa: E731
    report["hardware"] = {"measured": rnd(hw), "step1": rnd(hw1), "settings": dict(derived), "why": derived_why}
    for flag, why in derived_why.items():
        say(f"    {flag}: {why}")
    base_args = measure_args(apply_fork(args0, {}, {"settings": settings})[0])

    # ---- 2. the engine variables, a restart each
    elapsed = clock() - t0
    p = plan(cands, c, budget_s - elapsed, 0.0, compare=compare is not None)
    say(f"  2/3 Engine variables ({len(arms_of(p['kept']))} candidates, {FORK_ROUNDS} starts each; re-estimated from "
        f"this PC: an engine start ~{c['start1']:.0f} s, ~{p['restarts_s'] / 60:.0f} min)"
        + (": left out for the budget: " + ", ".join(x.name for x in p["dropped"]) if p["dropped"] else ""))
    report["plan"]["dropped_after_phase1"] = [x.name for x in p["dropped"]]
    arms = arms_of(p["kept"])
    names = ["baseline"] + [a["name"] for a in arms]
    envs = {"baseline": env_base}
    reads = {"baseline": arm_reads(None) if any(x.kind == "prompt" for x in p["kept"]) else 1}
    for a in arms:
        envs[a["name"]] = env_with(env_base, [kv for x in a["cands"] for kv in x.env])
        reads[a["name"]] = arm_reads(a)
    samples: dict = {n: [] for n in names}

    def one_start(n, args, env, nreads, rnd):
        e, load, since = open_start(args, env, n)
        if e is None:
            return None
        try:
            lc = LongContext(e, parts, ctx, short_ids, cancel, foreign, say)
            prompt = [lc.read(1 + i)["tok_s"] for i in range(nreads)]
            lc.answers(questions=1, max_new=64, measure=False)
            ans = lc.answers_checked()
            sh = lc.short()
            s = {"round": rnd, "load_s": round(load, 1), "prompt": prompt, "decode": ans["tok_s"],
                 "short": sh["tok_s"], "texts": ans["texts"] + sh["texts"], "foreign": ans["foreign_loads"],
                 "slots": int((getattr(e, "info", None) or {}).get("expert_slots") or 0),
                 "vram_free": log_free_mib(log, since), "rereads": lc.rereads}
        finally:
            CAL.close(e)
        say(f"    {n}: decode {s['decode']:.1f} tok/s, prompt " + "/".join(f"{x:.0f}" for x in s["prompt"])
            + f" tok/s, short {s['short']:.1f} tok/s" + (f", others' CPU {max(x or 0 for x in s['foreign']) * 100:.0f}%"
                                                          if any(x is not None for x in s["foreign"]) else ""))
        return s

    if arms:
        for r in range(FORK_ROUNDS):
            for n in (names if r % 2 == 0 else names[::-1]):
                say(f"  Round {r + 1}/{FORK_ROUNDS}: {n} (restarts the engine) ...")
                s = one_start(n, base_args, envs[n], reads[n], r)
                if s is not None:
                    samples[n].append(s)
        if not samples["baseline"]:
            raise RuntimeError("the engine did not start for the baseline: "
                               + next(iter(report.get("failed_starts", {}).values()), "?"))
        b_slots = min((s["slots"] for s in samples["baseline"] if s["slots"]), default=0)
        if derived.get("--vram-reserve-mib") and hw.get("expert_slots") and b_slots:
            # what the safety margin costs: the expert slots it takes (decode follows them; said, not measured away)
            report["hardware"]["reserve_slots"] = {"without": hw["expert_slots"], "with": b_slots}
            say(f"    --vram-reserve-mib {derived['--vram-reserve-mib']} keeps {hw['expert_slots'] - b_slots} expert "
                f"slots out of the cache ({hw['expert_slots']} -> {b_slots}): fewer experts on the GPU, for the VRAM "
                f"the driver needs to stay out of paging")
    decisions: dict = {}
    for a in arms:
        for x in a["cands"]:
            decisions[x.name] = decide(x, samples["baseline"], samples[a["name"]], say) if samples[a["name"]] else \
                {"faster": False, "why": "the engine did not start"}

    # ---- 3. the exact winners' text in --deterministic starts
    exact = [x for x in p["kept"] if x.text == "exact" and decisions.get(x.name, {}).get("faster")]
    if exact:
        slots = min((s["slots"] for s in samples["baseline"] if s["slots"]), default=0)
        dargs = with_flag(base_args, "--deterministic", True)
        if slots:
            dargs = CAL.with_arg(dargs, "--expert-cache", str(int(slots * CAL.SWITCH_CHECK_CACHE)))
        say("  Checking the exact ones' text (--deterministic, the expert cache fixed; restarts the engine) ...")
        texts = {}
        for i, n in enumerate(["baseline", *[x.name for x in exact], "baseline"]):
            key = "baseline2" if n == "baseline" and i else n
            env = {**(envs["baseline"] if n == "baseline" else env_with(envs["baseline"], next(x for x in exact if x.name == n).env)),
                   **CAL.SWITCH_CHECK_ENV}
            e, _, _ = open_start(dargs, env, "the text check " + key)
            if e is None:
                continue
            try:
                texts[key] = LongContext(e, parts, ctx, short_ids, cancel, foreign, say).short(CHECK_TOKENS)["texts"]
            finally:
                CAL.close(e)
        base_ok = "baseline" in texts and texts.get("baseline") == texts.get("baseline2")
        report["text_check"] = {"baseline_repeats": base_ok, "expert_cache": int(slots * CAL.SWITCH_CHECK_CACHE) or None}
        for x in exact:
            same = base_ok and texts.get(x.name) == texts["baseline"]
            decisions[x.name]["text_ok"] = same
            report["text_check"][x.name] = same
            say(f"    {x.name}: " + ("the same text" if same else "the baseline's text does not repeat: not kept"
                                     if not base_ok else "ANOTHER text - not kept"))
    for x in p["kept"]:
        if x.text != "exact" and x.name in decisions:
            decisions[x.name].setdefault("text_ok", True)
    winners = resolve_groups(p["kept"], decisions)
    env_final = env_with(env_base, [kv for x in winners for kv in x.env])

    # ---- 4. the tuned settings against the baseline (and another config, if given)
    final_args = base_args
    changed = bool(winners or keep)
    if p["confirm_s"] and (changed or compare is not None) and clock() - t0 + p["confirm_s"] <= budget_s * 1.15:
        say(f"  3/3 The tuned settings against the baseline{' and the compared config' if compare else ''} "
            f"({CONFIRM_ROUNDS} starts each) ...")
        b0_args = measure_args(apply_fork(args0, {}, {"settings": derived})[0])
        arms4 = {"baseline": (b0_args, env_base)}
        if changed:                                     # nothing chosen: the tuned settings are the baseline's
            arms4["tuned"] = (final_args, env_final)
        if compare is not None:
            arms4["compare"] = (measure_args(CAL.engine_args(compare)), dict(compare.get("env") or {}))
        s4: dict = {n: [] for n in arms4}
        order = list(arms4)
        for r in range(CONFIRM_ROUNDS):
            for n in (order if r % 2 == 0 else order[::-1]):
                say(f"  Round {r + 1}/{CONFIRM_ROUNDS}: {n} (restarts the engine) ...")
                s = one_start(n, arms4[n][0], arms4[n][1], 2, r)
                if s is not None:
                    s4[n].append(s)
        summary = {}
        for n, ss in s4.items():
            if ss:
                summary[n] = {"decode": round(statistics.median(x["decode"] for x in ss), 1),
                              "prompt": round(statistics.median(y for x in ss for y in x["prompt"]), 1),
                              "short": round(statistics.median(x["short"] for x in ss), 1)}
                say(f"    {n}: decode {summary[n]['decode']} tok/s, the {ctx // 1024}K prompt {summary[n]['prompt']} tok/s, "
                    f"short {summary[n]['short']} tok/s")
        report["confirm"] = {"summary": summary, "samples": {n: [_slim(x) for x in v] for n, v in s4.items()}}
        # the VRAM reserve once more, from the tuned starts (a variable chosen above, STRATA_ATTN_SPLITS, frees VRAM)
        frees = [x["vram_free"] for x in s4.get("tuned", []) if x.get("vram_free") is not None]
        if frees and facts["pack"]:
            cur = int(CAL.arg_value(final_args, "--vram-reserve-mib") or ENGINE_RESERVE_MIB)
            floor = int(CAL.arg_value(args0, "--vram-reserve-mib") or ENGINE_RESERVE_MIB)
            new = max(floor, int(math.ceil((cur + VRAM_SAFE_MIB - min(frees)) / 64.0)) * 64)
            if abs(new - cur) >= 64:
                v = None if new == ENGINE_RESERVE_MIB and CAL.arg_value(args0, "--vram-reserve-mib") is None else str(new)
                settings["--vram-reserve-mib"] = v
                report["hardware"]["reserve_after_check"] = {"free_mib": min(frees), "from": cur, "to": new}
                say(f"    --vram-reserve-mib: {min(frees)} MiB stayed free in the tuned starts: {cur} -> {new}")
        dec_winners = [x for x in winners if x.kind == "decode"]
        if "tuned" in summary and "baseline" in summary and len(dec_winners) > 1 and \
                summary["tuned"]["decode"] < summary["baseline"]["decode"] * (1.0 - CAL.MIN_GAIN):
            best = max(dec_winners, key=lambda x: decisions[x.name]["gain"])
            say(f"    together the decode switches were slower than the baseline: only {best.name} is kept")
            winners = [x for x in winners if x.kind != "decode" or x is best]
            env_final = env_with(env_base, [kv for x in winners for kv in x.env])
            report["confirm"]["reverted_to"] = best.name
    env_out = {k: env_final.get(k) for k in keys}
    report.update(decisions=decisions, samples={n: [_slim(x) for x in v] for n, v in samples.items()},
                  chosen=[x.name for x in winners], minutes=round((clock() - t0) / 60, 1))
    base_dec = [s["decode"] for s in samples["baseline"]] if samples.get("baseline") else []
    report["baseline"] = {"decode": round(statistics.median(base_dec), 1) if base_dec else None,
                          "prompt": round(statistics.median(y for s in samples["baseline"] for y in s["prompt"]), 1)
                          if base_dec else None}
    return {"settings": settings, "env": env_out, "report": report}


def _slim(s: dict) -> dict:
    return {k: v for k, v in s.items() if k != "texts"}


def say_result(res: dict, say=print) -> None:
    r = res["report"]
    say(f"  Fork calibration: {r.get('minutes')} min")
    for flag, v in res["settings"].items():
        say(f"    {flag} {'(removed)' if v is None or v is False else '' if v is True else v}")
    for k, v in res["env"].items():
        say(f"    {k}={v}" if v is not None else f"    {k} (not set)")
