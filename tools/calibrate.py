"""Tune the engine's hardware-dependent settings on this PC (setup's --calibrate).

Three settings depend on the machine more than on the model, and the defaults are right for the PC they were
measured on (a Ryzen 5 7600 + RTX 5070 on PCIe 5):
  --pcie-frac     the share of the experts missing from VRAM that are copied over PCIe and run on the GPU instead of
                  on the CPU.  A fast PCIe link and a slow CPU want more; a laptop's x8 link or a fast CPU want less.
  --spec-min-p    how sure the draft layer must be to extend a verify window by another guess.  A slower CPU pays more
                  per extra window row (more experts per window), so it wants a higher floor.
  --pool-workers  the CPU threads that compute experts.  Every physical core is not always best: on hybrid CPUs the
                  efficiency cores can make the whole window wait for them.
  --adapt-every / --adapt-swaps / --adapt-decay
                  how the VRAM expert tier follows the conversation: how often, how many experts it swaps in, how fast
                  its use counts fade.  A PC whose CPU reads the missed experts slowly (DDR3, ~24 GB/s) gains from
                  swapping more: 160 swaps every window measured +7.9% over the default tier on a Xeon E5-2673 v3 (DDR3) with an
                  RTX 4060 Ti on PCIe 3.0 x8 (Q2_0; with the swaps taking effect a window later, #764).
The first two are measured through one engine (per-request `strata_tune` keys); the worker count and the adaptive
tier need a restart per value.  Decode speed only: the prompt path streams every expert whatever these settings say.

A setting is kept only when it beats the default by more than MIN_GAIN in an interleaved re-measurement - the
adaptive expert tier and the OS make single measurements noisy by a few percent.

Opt-in (setup.py --calibrate-switches, `run_switches`): the decode switches that win on one PC and lose on another
(STRATA_ADAPT_OVERLAP: +8.3% on an A4000, -21% on an RTX 5090 Laptop; STRATA_ADAPT_LAG=2: +3.5% on a P100, -1.3% on
an RTX 3060).  Each is measured off against on, a restart per sample, the starts interleaved; one is kept only when it
beats the baseline by more than the baseline's own spread across its starts (and MIN_GAIN), and with the same greedy
text.

    python tools/calibrate.py strata-q2_0.json        # measure and print; setup.py --calibrate also saves it
    python tools/calibrate.py --switches strata-q2_0.json
"""
from __future__ import annotations

import json
import os
import statistics
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT))

MIN_GAIN = 0.03                    # a setting must beat the default by this much to be kept
PCIE_FRACS = (0.0, 0.2, 0.35, 0.55, 0.75, 0.9, 1.0)   # 1.0: every miss over PCIe, the CPU pool gets no expert
SPEC_MIN_PS = (0.3, 0.5, 0.7)
SWEEP_ROUNDS = 3                   # how many times the sweep visits each value (see `sweep`)
# the adaptive tier's candidates (every, swaps, decay) against the engine's own (None): swapping more and remembering
# longer, the rest of the set as the engine has it
ADAPT_CANDIDATES = (None, ("1", "80", "0.97"), ("1", "160", "0.97"))
ADAPT_FLAGS = ("--adapt-every", "--adapt-swaps", "--adapt-decay")
MAX_NEW = 128
# the expert tier follows a text over some windows: 128-token answers end before it shows (on a Xeon E5-2673 v3 with
# DDR3, every 1 / 160 / 0.97 measured +0.7% with 128 tokens and +7.9% with 512-token answers), so its step uses these
TIER_MAX_NEW = 512
# the opt-in decode switches (`run_switches`): the baseline sets every key to its off value, so an env var the config
# or the shell carries does not decide it; each candidate turns one on.  The two exclude each other (the overlap is off
# with a lag other than 1), so at most one is kept.  STRATA_STAGE_PIN is not here: it is not exact yet.
SWITCH_OFF = {"STRATA_ADAPT_OVERLAP": "0", "STRATA_ADAPT_LAG": "1"}
SWITCHES = {"STRATA_ADAPT_OVERLAP": "1", "STRATA_ADAPT_LAG": "2"}
SWITCH_ROUNDS = 3                  # engine starts per candidate; each start gives one sample
# the text check pins the expert cache below what `auto` found free: `auto` sizes it from the free VRAM of the moment,
# and a cache a few experts larger or smaller moves experts between the GPU and the CPU, which changes the greedy text
# between two starts with the same settings (an RTX 5080 shared with other programs: 5337 to 5455 experts, and no two
# starts with the same text).  A fixed cache below the free VRAM is the same in every start.
SWITCH_CHECK_CACHE = 0.75
# and turns the prompt's CPU share off: on prompts below 1024 tokens the idle CPU takes some of the experts the GPU
# would stream, which ones depending on timing, so the first answer token could differ between two starts too
SWITCH_CHECK_ENV = {"STRATA_PREFILL_CPU_SHARE": "0"}
PROMPTS = (
    "Write a Python function that merges two sorted lists into one sorted list, with a docstring and two tests.",
    "Explain in two paragraphs how a refrigerator moves heat from inside to outside.",
    "List twelve European capitals with one sentence about each.",
)


def chat_ids(tok, text: str) -> list[int]:
    return tok.encode(f"<|im_start|>user\n{text}<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n",
                      parse_special=True)


def arg_value(args: list[str], flag: str) -> str | None:
    return args[args.index(flag) + 1] if flag in args and args.index(flag) + 1 < len(args) else None


def with_arg(args: list[str], flag: str, value: str | None) -> list[str]:
    """`args` with `flag value` set (replaced if present), or removed when value is None."""
    out = list(args)
    if flag in out:
        i = out.index(flag)
        del out[i:i + 2]
    if value is not None:
        out += [flag, value]
    return out


def worker_candidates(default: int, extra=()) -> list[int]:
    """The engine's own count, and fewer: two thirds, a half and a quarter (at least 2), plus `extra` (the P-cores
    minus one on a hybrid CPU, one socket's cores minus one on a 2-socket PC), without repeats.  Bench #780 #815
    #707 #674: 4 beat 15 by 28.7% on 8P + 16E; 17-18 beat 35 by ~20% on 2-socket Xeons."""
    c = [default]
    for w in (round(default * 2 / 3), round(default / 2), round(default / 4), *extra):
        if 2 <= w < default and w not in c:
            c.append(w)
    return c


def host_worker_extras() -> list[int]:
    """P-cores - 1 (hybrid CPU) and one socket's cores - 1 (several sockets) of this PC: more counts to try."""
    try:
        import setup
        out = []
        cores, sockets = setup.cpu_cores(), setup.cpu_sockets()
        if cores:
            out.append(cores[0] - 1)
        if sockets and sockets[0] >= 2:
            out.append(sockets[1] - 1)
        return out
    except Exception:
        return []


def pick(measured: dict, default_key, min_gain: float = MIN_GAIN):
    """The key with the best median tok/s, or `default_key` unless the best beats it by more than min_gain."""
    med = {k: statistics.median(v) for k, v in measured.items() if v}
    if not med or default_key not in med:
        return default_key
    best = max(med, key=med.get)
    return best if med[best] > med[default_key] * (1.0 + min_gain) else default_key


class Session:
    """One running engine: measure decode tok/s for a setting (the median of the prompts' rates)."""

    def __init__(self, engine, ids_list):
        self.engine = engine
        self.ids_list = ids_list

    def rate(self, tune: dict | None = None, max_new: int | None = None, texts: list | None = None) -> float:
        """`texts`, when given, gets each prompt's generated token ids (greedy: temperature 0)."""
        rates = []
        for ids in self.ids_list:
            sampling = {"temperature": 0}
            if tune:
                sampling["strata_tune"] = tune
            out = [t for t in self.engine.generate(ids, max_new or MAX_NEW, sampling, threading.Event())
                   if t is not None]
            n = len(out)
            if texts is not None:
                texts.append(out)
            ms = (self.engine.last or {}).get("decode_ms") or 0.0
            if n > 8 and ms > 0:
                rates.append(n / (ms / 1000.0))
        return statistics.median(rates) if rates else 0.0

    def warm_up(self, rounds: int = 2):
        for _ in range(rounds):
            self.rate()


def run(cfg: dict, say=print, start_engine=None) -> dict:
    """Measure on the engine `cfg` describes; returns {"settings": {flag: value}, "report": {...}}.
    `start_engine(args)` returns a started engine (serve.server.StrataEngine or a stand-in in tests)."""
    if start_engine is None:
        from serve.server import StrataEngine, child_env

        def start_engine(args):
            return StrataEngine(cfg["exe"], args, cwd=cfg.get("cwd"), log=cfg.get("log"), env=child_env(cfg))
    return measure(engine_args(cfg), prompt_ids(cfg), start_engine, say, host_worker_extras())


def run_switches(cfg: dict, say=print, start_engine=None) -> dict:
    """The opt-in decode switches on the engine `cfg` describes (with its args as they are, so after a --calibrate
    run with what it chose); returns {"env": {the winner, if any}, "report": {...}}.  `start_engine(args, env)`
    returns a started engine with `env` added to the config's own."""
    if start_engine is None:
        from serve.server import StrataEngine, child_env

        def start_engine(args, env):
            return StrataEngine(cfg["exe"], args, cwd=cfg.get("cwd"), log=cfg.get("log"),
                                env={**child_env(cfg), **env})
    return measure_switches(engine_args(cfg), prompt_ids(cfg), start_engine, say, cfg.get("log"))


def prompt_ids(cfg: dict) -> list:
    import strata_tokenizer as ST
    tpath = Path(cfg["tokenizer"])
    vocab = json.loads((tpath / "vocab.json").read_text(encoding="utf-8"))
    toks = [None] * len(vocab)
    for t, i in vocab.items():
        toks[i] = t
    tok = ST.Tokenizer(toks, (tpath / "merges.txt").read_text(encoding="utf-8").split("\n"),
                       json.loads((tpath / "token_type.json").read_text()))
    return [chat_ids(tok, p) for p in PROMPTS]


def engine_args(cfg: dict) -> list[str]:
    """The arguments the server starts this config's engine with (serve.server.engine_args), so the tuning measures
    the engine as it runs.  #447: this used to read any "gpu" list as a layer split and add --layer-split auto, which
    broke a one-card config with a helper card for the expert tier ("gpu": [0] + --expert-cache-device1: the engine
    refuses a split that leaves no card without a stage), missed the "0,2" spelling, and ignored split_skip_if_fits."""
    from serve.server import engine_args as server_args
    return server_args(cfg)


def engine_error(log: str | None, since: int = 0) -> str | None:
    """#447: the engine's own reason for a failed start - the last line of its log written after byte `since` that is
    its own ("strata ..." or "ERR ..."), else the last line there; None without a log or a new line."""
    if not log:
        return None
    try:
        with open(log, "rb") as f:
            f.seek(since)
            lines = [x.strip() for x in f.read()[-16384:].decode("utf-8", "replace").splitlines() if x.strip()]
    except OSError:
        return None
    return next((x for x in reversed(lines) if x.startswith(("strata", "ERR"))), lines[-1] if lines else None)


def sweep(s, values: list, base_tune: dict, key: str, label: str, say) -> dict:
    """Every value, `SWEEP_ROUNDS` times, one round visiting all of them and every other round in reverse order.

    A single rate per value cannot order neighbours.  #1332 has 0.75 to 0.95 inside each other's noise at 72.7,
    69.0, 71.0 and 71.9, and that box moved 8-28% between engine starts at an unchanged setting; a 5080/Xeon box
    reports +9.57 tok/s between two blocks at an unchanged setting (p = 0.00004), larger than the effect being
    hunted.  Rotating the values inside one engine start puts that drift on every value the same number of times,
    and the median over the rounds keeps a single bad sample from deciding.  The caller takes the winner from the
    medians, so every value keeps the same chance the others had.
    """
    out = {v: [] for v in values}
    for r in range(SWEEP_ROUNDS):
        for v in (values if r % 2 == 0 else values[::-1]):
            out[v].append(s.rate({**base_tune, key: v}))
        say(f"    round {r + 1}/{SWEEP_ROUNDS} {label}: " +
            "  ".join(f"{v:g} {out[v][-1]:.1f}" for v in values))
    med = {v: statistics.median(out[v]) for v in values}
    say(f"    {label}, median of {SWEEP_ROUNDS}: " +
        ", ".join(f"{v:g}: {med[v]:.1f} ({min(out[v]):.1f}-{max(out[v]):.1f})" for v in values) +
        f" -> best {max(med, key=lambda k: med[k]):g}")
    return out


def measure(base_args: list[str], ids_list, start_engine, say=print, extra_workers=()) -> dict:
    t0 = time.time()
    report: dict = {}
    say("  Loading the model for the measurements ...")
    base_args = apply(base_args, {})                   # the product defaults: what the measurements must beat
    eng = start_engine(base_args)
    try:
        info = dict(getattr(eng, "info", {}) or {})
        d_pcie = float(info.get("pcie_frac", 0.55))
        d_minp = float(info.get("spec_min_p", 0.5))
        d_workers = int(info.get("pool_workers", 0)) or None
        s = Session(eng, ids_list)
        s.warm_up()
        # 1. the PCIe share, at the default draft floor
        by_pcie = sweep(s, sorted(set(PCIE_FRACS) | {round(d_pcie, 2)}), {"spec_min_p": d_minp}, "pcie_frac",
                        "PCIe share", say)
        best_pcie = max(by_pcie, key=lambda k: statistics.median(by_pcie[k]))
        # 2. the draft floor, at that share
        by_minp = sweep(s, sorted(set(SPEC_MIN_PS) | {round(d_minp, 2)}), {"pcie_frac": best_pcie}, "spec_min_p",
                        "draft floor", say)
        best_minp = max(by_minp, key=lambda k: statistics.median(by_minp[k]))
        # 3. the winner against the default, interleaved, the same number of rounds
        dflt, cand = (round(d_pcie, 2), round(d_minp, 2)), (best_pcie, best_minp)
        confirm = {dflt: [], cand: []}
        if cand != dflt:
            for _ in range(SWEEP_ROUNDS):
                for k in (dflt, cand):
                    confirm[k].append(s.rate({"pcie_frac": k[0], "spec_min_p": k[1]}))
        chosen = pick(confirm, dflt) if cand != dflt else dflt
        report.update(default={"pcie_frac": dflt[0], "spec_min_p": dflt[1], "pool_workers": d_workers},
                      pcie_sweep={str(k): v for k, v in by_pcie.items()},
                      min_p_sweep={str(k): v for k, v in by_minp.items()},
                      confirm={f"{k[0]}/{k[1]}": v for k, v in confirm.items()})
    finally:
        close(eng)
    settings = {}
    if chosen != dflt:
        settings["--pcie-frac"] = f"{chosen[0]:.2f}"
        settings["--spec-min-p"] = f"{chosen[1]:.2f}"
    base_rate = statistics.median(confirm[chosen]) if confirm.get(chosen) else None
    # 4. fewer CPU workers (a restart each), with the chosen settings
    if d_workers and len(worker_candidates(d_workers, extra_workers)) > 1:
        tuned = with_arg(with_arg(base_args, "--pcie-frac", f"{chosen[0]:.2f}"), "--spec-min-p", f"{chosen[1]:.2f}")
        by_workers = {}
        for w in worker_candidates(d_workers, extra_workers):
            say(f"  Measuring with {w} CPU workers (restarts the engine) ...")
            e = restart(start_engine, with_arg(tuned, "--pool-workers", None if w == d_workers else str(w)), f"{w} workers",
                        say, report)
            if e is None:
                continue
            try:
                sw = Session(e, ids_list)
                sw.warm_up(1)
                by_workers[w] = [sw.rate(), sw.rate()]
                say(f"    {w} workers: {statistics.median(by_workers[w]):.1f} tok/s")
            finally:
                close(e)
        report["workers"] = {str(k): v for k, v in by_workers.items()}
        w_best = pick(by_workers, d_workers) if by_workers else d_workers
        if w_best != d_workers:
            settings["--pool-workers"] = str(w_best)
            base_rate = statistics.median(by_workers[w_best])
        elif by_workers.get(d_workers):
            base_rate = statistics.median(by_workers[d_workers])
    # 5. the adaptive expert tier (a restart each), with everything chosen so far
    tuned = apply(base_args, settings)
    by_adapt = {}
    for cand in ADAPT_CANDIDATES:
        key = "default" if cand is None else "/".join(cand)
        args = tuned
        for flag, v in zip(ADAPT_FLAGS, cand or (None,) * len(ADAPT_FLAGS)):
            args = with_arg(args, flag, v)
        say(f"  Measuring the expert tier {'(the engine default)' if cand is None else 'every ' + cand[0] + ', ' + cand[1] + ' swaps, decay ' + cand[2]} (restarts the engine) ...")
        e = restart(start_engine, args, "the expert tier " + key, say, report)
        if e is None:
            continue
        try:
            sa = Session(e, ids_list)
            sa.warm_up(1)
            by_adapt[key] = [sa.rate(max_new=TIER_MAX_NEW), sa.rate(max_new=TIER_MAX_NEW)]
            say(f"    {statistics.median(by_adapt[key]):.1f} tok/s")
        finally:
            close(e)
    a_best = pick(by_adapt, "default") if by_adapt else "default"
    report["adapt"] = by_adapt
    if a_best != "default":
        for flag, v in zip(ADAPT_FLAGS, a_best.split("/")):
            settings[flag] = v
        base_rate = statistics.median(by_adapt[a_best])
    elif by_adapt.get("default"):
        base_rate = statistics.median(by_adapt["default"])
    report["seconds"] = round(time.time() - t0)
    report["tok_s"] = round(base_rate, 1) if base_rate else None
    return {"settings": settings, "report": report}


def switch_wins(base: list, cand: list) -> tuple[bool, float, float]:
    """(faster, gain, margin): a switch is faster when its median beats the baseline's by more than the margin - the
    baseline's own spread across its starts ((max - min) / median), at least MIN_GAIN."""
    if not base or not cand:
        return False, 0.0, MIN_GAIN
    mb, mc = statistics.median(base), statistics.median(cand)
    if mb <= 0:
        return False, 0.0, MIN_GAIN
    margin = max(MIN_GAIN, (max(base) - min(base)) / mb)
    gain = mc / mb - 1.0
    return gain > margin, gain, margin


def switch_off_reason(log: str | None, since: int) -> str | None:
    """The engine's own reason a switch asked for does not run ("STRATA_ADAPT_OVERLAP=1 is off: not on a layer
    split"), from its log after byte `since`; None when it runs or there is no log."""
    if not log:
        return None
    try:
        with open(log, "rb") as f:
            f.seek(since)
            text = f.read().decode("utf-8", "replace")
    except OSError:
        return None
    for line in text.splitlines():
        if "STRATA_ADAPT_OVERLAP=1 is off:" in line:
            return line.split("is off:", 1)[1].strip()
    return None


def measure_switches(base_args: list[str], ids_list, start_engine, say=print, log: str | None = None) -> dict:
    """Each switch in SWITCHES against all of them off, SWITCH_ROUNDS engine starts each, the starts interleaved
    (every other round in reverse order) so a drift between starts lands on every candidate alike.  A start gives
    one sample: the median decode rate of the prompts with TIER_MAX_NEW tokens (the adaptive tier needs some windows
    to show), after one warm-up round.  A switch that is faster is then checked for the same greedy text
    (check_text); the fastest that passes is kept."""
    t0 = time.time()
    names = ["off", *SWITCHES]
    rates = {n: [] for n in names}
    slots: dict = {}                   # the expert cache each candidate's first start got (for check_text)
    off_why: dict = {}
    report: dict = {}
    for r in range(SWITCH_ROUNDS):
        for n in (names if r % 2 == 0 else names[::-1]):
            if n in off_why:
                continue
            env = dict(SWITCH_OFF) if n == "off" else {**SWITCH_OFF, n: SWITCHES[n]}
            say(f"  Round {r + 1}/{SWITCH_ROUNDS}: decode with " +
                ("every switch off" if n == "off" else f"{n}={SWITCHES[n]}") + " (restarts the engine) ...")
            since = os.path.getsize(log) if log and os.path.isfile(log) else 0
            e = restart(lambda a, env=env: start_engine(a, env), base_args, n, say, report)
            if e is None:
                continue
            try:
                s = Session(e, ids_list)
                s.warm_up(1)
                why = switch_off_reason(log, since) if n != "off" else None
                if why:
                    off_why[n] = why
                    say(f"    {n} does not run here: {why} - not measured")
                    continue
                rates[n].append(s.rate(max_new=TIER_MAX_NEW))
                slots.setdefault(n, int((getattr(e, "info", None) or {}).get("expert_slots") or 0))
            finally:
                close(e)
            say(f"    {rates[n][-1]:.1f} tok/s")
    if not rates["off"]:                               # nothing measured: an error, not "none wins" (that would
        why = next(iter((report.get("failed_starts") or {}).values()), "no sample")   # drop a switch chosen before)
        raise RuntimeError(f"the engine did not start for the baseline: {why}")
    report.update(switches={n: [round(x, 2) for x in v] for n, v in rates.items()}, inactive=off_why)
    faster = {}
    if rates["off"]:
        say(f"    every switch off: {statistics.median(rates['off']):.1f} tok/s "
            f"({min(rates['off']):.1f}-{max(rates['off']):.1f})")
    for n, on in SWITCHES.items():
        wins, gain, margin = switch_wins(rates["off"], rates[n])
        report.setdefault("decision", {})[n] = {"gain": round(gain, 4), "margin": round(margin, 4), "faster": wins}
        if rates[n]:
            say(f"    {n}={on}: {statistics.median(rates[n]):.1f} tok/s ({min(rates[n]):.1f}-{max(rates[n]):.1f}), "
                f"{gain * 100:+.1f}% against the noise margin {margin * 100:.1f}%" + (" -> faster" if wins else ""))
        if wins:
            faster[n] = gain
    chosen, best = None, 0.0
    if faster:
        same = check_text(base_args, ids_list, start_engine, list(faster), slots.get("off"), say, report)
        for n, gain in faster.items():
            report["decision"][n]["same_text"] = same.get(n)
            if same.get(n) and gain > best:
                chosen, best = n, gain
    report["seconds"] = round(time.time() - t0)
    rate = statistics.median(rates[chosen or "off"]) if rates[chosen or "off"] else None
    report["tok_s"] = round(rate, 1) if rate else None
    return {"env": {chosen: SWITCHES[chosen]} if chosen else {}, "report": report}


def check_text(base_args, ids_list, start_engine, names, slots, say, report) -> dict:
    """{switch: True when its greedy text is the baseline's}, from starts with the expert cache pinned to
    SWITCH_CHECK_CACHE of the slots `auto` gave (`slots`; unpinned when unknown) and SWITCH_CHECK_ENV: the baseline,
    each switch, and the baseline again.  When the two baseline starts differ the text cannot tell a switch's effect from the start's,
    and every switch is False."""
    args = with_arg(base_args, "--expert-cache", str(int(slots * SWITCH_CHECK_CACHE))) if slots else base_args
    say("  Checking the text" + (f" with the expert cache fixed at {int(slots * SWITCH_CHECK_CACHE)}" if slots else "")
        + " (restarts the engine) ...")
    texts = {}
    for i, n in enumerate(["off", *names, "off"]):
        env = {**SWITCH_CHECK_ENV, **SWITCH_OFF, **({} if n == "off" else {n: SWITCHES[n]})}
        key = "off2" if n == "off" and i else n
        e = restart(lambda a, env=env: start_engine(a, env), args, "the text check " + key, say, report)
        if e is None:
            continue
        try:
            out: list = []
            Session(e, ids_list).rate(max_new=TIER_MAX_NEW, texts=out)
            texts[key] = out
        finally:
            close(e)
    base_ok = "off" in texts and texts.get("off") == texts.get("off2")
    same = {n: base_ok and texts.get(n) == texts["off"] for n in names}
    report["text_check"] = {"expert_cache": int(slots * SWITCH_CHECK_CACHE) if slots else None,
                            "baseline_repeats": base_ok, **same}
    if not base_ok:
        say("    the baseline's text differs between two starts: a switch's text cannot be checked, none is kept")
    for n in names:
        if base_ok:
            say(f"    {n}={SWITCHES[n]}: " + ("the same text" if same[n] else "ANOTHER text - not kept"))
    return same


def apply_env(env: dict | None, chosen: dict) -> dict:
    """A config's "env" with the switches calibration chose: the chosen ones set, every other switch removed, so an
    older calibration's choice does not linger.  Other entries stay."""
    out = {k: v for k, v in (env or {}).items() if k not in SWITCHES}
    out.update(chosen)
    return out


def restart(start_engine, args, what, say, report):
    """#1337: a later step's engine start that fails is a candidate that loses, not a failed run: what the earlier
    steps measured (and the settings they chose) must survive it.  Returns the engine, or None after saying why and
    noting it in report["failed_starts"].  (The first start, for steps 1-3, is not covered: with no engine there is
    nothing measured.)"""
    try:
        return start_engine(args)
    except Exception as e:  # noqa: BLE001 - whatever the start raised (RuntimeError, EngineDied, OSError ...)
        why = str(e).strip().splitlines()[0][:300] if str(e).strip() else type(e).__name__
        say(f"    the engine did not start for {what}: {why} - this candidate is dropped, the earlier results are kept")
        report.setdefault("failed_starts", {})[what] = why
        return None


def close(eng):
    proc = getattr(eng, "proc", None)
    if proc is None:
        return
    try:
        proc.stdin.write("QUIT\n")
        proc.stdin.flush()
        proc.stdin.close()
        proc.wait(60)
    except Exception:
        proc.kill()


DEFAULTS = {"--pcie-frac": None, "--spec-min-p": "0.5", "--pool-workers": None,   # None: the engine's own choice
            "--adapt-every": None, "--adapt-swaps": None, "--adapt-decay": None}


def apply(args: list[str], settings: dict) -> list[str]:
    """`args` with the calibrated settings; a setting the calibration did not change goes back to the product
    default (setup's --spec-min-p 0.5, the engine's own PCIe share and worker count), so an older calibration's
    values never linger."""
    out = list(args)
    for flag, default in DEFAULTS.items():
        out = with_arg(out, flag, settings.get(flag, default))
    return out


if __name__ == "__main__":
    argv = [x for x in sys.argv[1:] if x != "--switches"]
    if len(argv) != 1:
        sys.exit("usage: calibrate.py [--switches] <strata-*.json>")
    cfg = json.loads(Path(argv[0]).read_text(encoding="utf-8-sig"))
    res = run_switches(cfg) if "--switches" in sys.argv else run(cfg)
    print(json.dumps(res, indent=1))
