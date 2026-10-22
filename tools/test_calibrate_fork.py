"""Tests for tools/calibrate_fork.py (setup's --calibrate-fork) without a GPU: a stand-in engine whose decode and
prompt speeds and greedy text are functions of the variables and request keys it runs with.

    python -m unittest tools.test_calibrate_fork
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT))
import calibrate as CAL  # noqa: E402
import calibrate_fork as CF  # noqa: E402

PACK_ENV = {"STRATA_ATTN_WINDOW": "1", "STRATA_ATTN_WINDOW_PREC": "2", "STRATA_PROMPT_ATTN_DENSE_IMMA": "4",
            "STRATA_ATTN_WINDOW_SMALL": "1", "STRATA_MMQ_KQ": "1", "STRATA_ARENA_WSLOCK": "1"}
HOST = {"win": True, "avx2": True, "avx512": False, "cc": 120, "gpu": "RTX Test", "gpu_index": 0}
CTX = 4096


class Tok:
    def encode(self, text, parse_special=False):
        return [ord(c) % 997 for c in text]


class Model:
    """decode(env, tune, args, long) and prompt(env) in tok/s; the greedy text: the same per prompt, except that a
    normal start drifts from token ~40 on (the engine is not run-to-run exact), `early` variables change it from token
    2, `rounding` ones change it in --deterministic starts, `broken` ones change it there although they are exact."""

    def __init__(self, decode=None, prompt=None, short=None, early=(), rounding=(), broken=(), finish="length"):
        self.decode = decode or (lambda env, tune, args: 100.0)
        self.prompt = prompt or (lambda env: 5000.0)
        self.short = short
        self.early, self.rounding, self.broken = set(early), set(rounding), set(broken)
        self.finish = finish

    def text(self, env, ids, n, det, start):
        seed = sum(ids[-12:]) % 1000
        base = [seed * 1000 + i for i in range(n)]
        on = {(k, v) for k, v in env.items()}
        cut, tag = None, 0
        if not det:
            cut, tag = 40 + (start * 13) % 25, start + 1
        if on & self.early:
            cut, tag = 2, 99
        if det and on & (self.rounding | self.broken):
            cut, tag = 5, 77
        return base if cut is None else base[:cut] + [x + 7919 * tag for x in base[cut:]]


class FakeEngine:
    def __init__(self, args, env, model, starts):
        self.args, self.env, self.model = list(args), dict(env), model
        spec = int(CAL.arg_value(args, "--spec") or 4)
        self.info = {"spec": min(spec + 2, 8), "mtp_max": spec, "expert_slots": 7000, "pool_workers": 7}
        self.last, self.proc, self.cached = {}, None, None
        self.det = "--deterministic" in args
        self.start = len(starts)
        self.requests = []
        starts.append(self)

    def generate(self, ids, max_new, sampling, cancel):
        tune = sampling.get("strata_tune") or {}
        pin = (sampling.get("strata_prefix") or {}).get("tokens")
        self.requests.append(dict(tune))
        reused = 0
        if pin and self.cached == tuple(ids[:pin]):
            reused = pin
        elif pin:
            self.cached = tuple(ids[:pin])
        long = len(ids) > 1000
        rate = self.model.decode(self.env, tune, self.args) if long or self.model.short is None else \
            self.model.short(self.env, tune, self.args)
        out = self.model.text(self.env, ids, max_new, self.det, self.start)
        for t in out:
            yield t
        self.last = {"generated": len(out), "prompt_tokens": len(ids), "reused": reused,
                     "prompt_ms": (len(ids) - reused) / self.model.prompt(self.env) * 1000.0,
                     "decode_ms": len(out) / rate * 1000.0, "finish": self.model.finish}


ARGS = ["--pack", "P", "--native", "m.gguf", "--spec", "4", "--kv", "int8", "--max-context", "262144",
        "--pcie-frac", "0.00", "--spec-min-p", "0.50", "--conversation-cache-mib", "4096",
        "--conversation-disk-dir", "D:\\conv", "--conversation-disk-mib", "32768", "--conversation-disk-persist", "on"]


class Fork(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        pack = Path(self.tmp.name) / "pack"
        pack.mkdir()
        (pack / "native_experts.txt").write_text("# header\n0 21 23 0 1 2 3 4\n1 21 14 0 1 2 3 4\n", encoding="utf-8")
        (Path(self.tmp.name) / "strata_kq.dll").write_text("")
        self.args = CAL.with_arg(list(ARGS), "--pack", str(pack))
        self.cfg = {"exe": str(Path(self.tmp.name) / "strata.exe"), "args": self.args,
                    "env": {"STRATA_SYSMEM_PROBE": "1", "STRATA_IQ3S_MT1": "1"}}

    def tearDown(self):
        self.tmp.cleanup()

    def run_fork(self, model, budget=600.0, host=HOST, cfg=None, foreign=None, hw=None, **kw):
        starts = []
        said = []
        res = CF.run_fork(cfg or self.cfg, say=said.append, budget_min=budget, ctx=CTX, host=host, base_env=PACK_ENV,
                          start_engine=lambda a, e: FakeEngine(a, e, model, starts), tok=Tok(),
                          measure_host=lambda: dict(hw or {"vram_free_mib": 2000, "ram_avail_gib": 20.0,
                                                           "disk_free_gib": 400.0}),
                          foreign=foreign or NoForeign(), **kw)
        return res, starts, said

    # -------------------------------------------------------------------------------- what applies
    def test_dry_run_prints_the_plan_and_starts_nothing(self):
        res, starts, said = self.run_fork(Model(), dry_run=True)
        self.assertEqual(starts, [])
        text = "\n".join(said)
        self.assertIn("Estimated", text)
        self.assertIn("STRATA_IQ3S_MT1=1", text)
        self.assertEqual(res["report"]["plan"]["dropped"], [])

    def test_only_what_applies(self):
        avx512 = dict(HOST, avx512=True)
        res, _, _ = self.run_fork(Model(), host=avx512, dry_run=True)
        na = res["report"]["not_applicable"]
        for name in ("STRATA_IQ3S_MT1=1", "STRATA_IQ3S_FAST=1", "STRATA_IQ4XS_DOWN=1"):
            self.assertIn(name, na)
        q4 = dict(self.cfg, args=CAL.with_arg(self.args, "--kv", "q4_0"))
        res, _, _ = self.run_fork(Model(), cfg=q4, dry_run=True)
        self.assertIn("STRATA_ATTN_WINDOW_SMALL off", res["report"]["not_applicable"])
        self.assertIn("STRATA_PROMPT_ATTN_DENSE_IMMA off", res["report"]["not_applicable"])
        os.remove(Path(self.tmp.name) / "strata_kq.dll")           # no K-quant library: MMQ_KQ is not measured
        res, _, _ = self.run_fork(Model(), dry_run=True)
        self.assertIn("STRATA_MMQ_KQ off", res["report"]["not_applicable"])
        with self.assertRaises(RuntimeError):                      # not the pack path
            self.run_fork(Model(), cfg=dict(self.cfg, args=CAL.with_arg(self.args, "--pack", None)), dry_run=True)

    def test_baseline_env(self):
        facts = CF.facts_for(self.cfg, self.args, HOST)
        env = CF.baseline_env({"STRATA_SYSMEM_PROBE": "1", "STRATA_IQ3S_MT1": "1", "STRATA_ATTN_WINDOW_SMALL": "0"},
                              PACK_ENV, facts)
        self.assertEqual(env, {"STRATA_SYSMEM_PROBE": "1", **PACK_ENV})   # a fork key of the config is reset
        linux = dict(facts, win=False, int8kv=False)
        env = CF.baseline_env({}, PACK_ENV, linux)
        self.assertNotIn("STRATA_ARENA_WSLOCK", env)
        self.assertNotIn("STRATA_ATTN_WINDOW", env)
        self.assertEqual(env.get("STRATA_MMQ_KQ"), "1")

    # -------------------------------------------------------------------------------- per request
    def test_window_depth_and_draft_floor_per_request(self):
        def decode(env, tune, args):                                       # the request's keys, else the start's
            depth = tune.get("spec_t") or int(CAL.arg_value(args, "--spec"))
            floor = tune.get("spec_min_p") or float(CAL.arg_value(args, "--spec-min-p"))
            return 100.0 * (1.12 if depth == 5 else 1.0) * (1.08 if floor == 0.3 else 1.0)
        res, starts, _ = self.run_fork(Model(decode=decode))
        self.assertEqual(CAL.arg_value(starts[0].args, "--spec"), "5")     # started with the deepest window
        self.assertIn({"spec_min_p": 0.5, "spec_t": 4, "spec_s": 6, "pcie_frac": 0.0}, starts[0].requests)
        self.assertEqual(res["settings"]["--spec"], "5")
        self.assertEqual(res["settings"]["--spec-min-p"], "0.30")
        self.assertEqual(res["settings"]["--pcie-frac"], "0.00")
        arms = len(CF.arms_of(CF.applicable(CF.facts_for(self.cfg, self.args, HOST))[0])) + 1
        restarts = starts[2:2 + CF.FORK_ROUNDS * arms]
        self.assertTrue(all(CAL.arg_value(s.args, "--spec") == "5" for s in restarts))   # the restarts with it
        last = res["report"]["confirm"]["summary"]                         # the last check: tuned against setup's
        self.assertGreater(last["tuned"]["decode"], last["baseline"]["decode"])

    def test_a_long_context_winner_must_not_lose_short_answers(self):
        res, _, _ = self.run_fork(Model(decode=lambda e, t, a: 112.0 if t.get("spec_t") == 5 else 100.0,
                                        short=lambda e, t, a: 70.0 if t.get("spec_t") == 5 else 100.0))
        self.assertEqual(res["settings"]["--spec"], "4")

    def test_flat_keeps_the_config(self):
        res, _, _ = self.run_fork(Model())
        self.assertEqual((res["settings"]["--spec"], res["settings"]["--spec-min-p"], res["settings"]["--pcie-frac"]),
                         ("4", "0.50", "0.00"))
        self.assertEqual(res["report"]["chosen"], [])
        self.assertEqual({k: v for k, v in res["env"].items() if v is not None}, PACK_ENV)
        self.assertIsNone(res["env"]["STRATA_IQ3S_MT1"])                    # the config's own goes when it does not win

    # -------------------------------------------------------------------------------- restarts
    def test_three_interleaved_starts_per_arm(self):
        res, starts, _ = self.run_fork(Model())
        restarts = [s for s in starts[2:] if "--deterministic" not in s.args]   # after step 1 and the VRAM probe
        arms = len(CF.arms_of(CF.applicable(CF.facts_for(self.cfg, self.args, HOST))[0])) + 1
        self.assertEqual(len(restarts), CF.FORK_ROUNDS * arms)
        first = [frozenset(s.env.items()) for s in restarts[:arms]]
        second = [frozenset(s.env.items()) for s in restarts[arms:2 * arms]]
        self.assertEqual(first, second[::-1])                               # every other round in reverse
        for s in restarts:                                                  # no disk tier in a measurement start
            self.assertNotIn("--conversation-disk-dir", s.args)

    def test_a_default_that_is_slower_here_is_switched_off(self):
        res, _, _ = self.run_fork(Model(decode=lambda e, t, a: 100.0 if e.get("STRATA_ATTN_WINDOW_SMALL") else 115.0))
        self.assertIsNone(res["env"]["STRATA_ATTN_WINDOW_SMALL"])
        self.assertIn("STRATA_ATTN_WINDOW_SMALL off", res["report"]["chosen"])

    def test_a_close_switch_with_another_text_is_not_kept(self):
        mt1 = ("STRATA_IQ3S_MT1", "1")
        fast = lambda e, t, a: 120.0 if e.get("STRATA_IQ3S_MT1") else 100.0   # noqa: E731
        res, _, _ = self.run_fork(Model(decode=fast, early={mt1}))
        self.assertIsNone(res["env"]["STRATA_IQ3S_MT1"])
        self.assertFalse(res["report"]["decisions"]["STRATA_IQ3S_MT1=1"]["faster"])
        res, _, _ = self.run_fork(Model(decode=fast, rounding={mt1}))       # agrees within the noise: kept
        self.assertEqual(res["env"]["STRATA_IQ3S_MT1"], "1")

    def test_an_exact_switch_needs_the_same_deterministic_text(self):
        fused = ("STRATA_POOL_FUSED", "1")
        fast = lambda e, t, a: 110.0 if e.get("STRATA_POOL_FUSED") else 100.0   # noqa: E731
        res, starts, _ = self.run_fork(Model(decode=fast))
        self.assertEqual(res["env"]["STRATA_POOL_FUSED"], "1")
        det = [s for s in starts if "--deterministic" in s.args]
        self.assertEqual(len(det), 3)                                       # the baseline, the switch, the baseline
        self.assertTrue(all(CAL.arg_value(s.args, "--expert-cache") == str(int(7000 * CAL.SWITCH_CHECK_CACHE))
                            for s in det))
        self.assertTrue(all(s.env.get("STRATA_PREFILL_CPU_SHARE") == "0" for s in det))
        res, _, _ = self.run_fork(Model(decode=fast, broken={fused}))
        self.assertIsNone(res["env"]["STRATA_POOL_FUSED"])
        self.assertFalse(res["report"]["text_check"]["STRATA_POOL_FUSED=1"])

    def test_a_prompt_switch_rides_on_an_exact_arm(self):
        def prompt(env):
            return 5000.0 if env.get("STRATA_PROMPT_ATTN_DENSE_IMMA") else 6000.0
        res, starts, _ = self.run_fork(Model(prompt=prompt))
        self.assertIsNone(res["env"]["STRATA_PROMPT_ATTN_DENSE_IMMA"])
        arms = {a["name"] for a in CF.arms_of(CF.applicable(CF.facts_for(self.cfg, self.args, HOST))[0])}
        self.assertNotIn("STRATA_PROMPT_ATTN_DENSE_IMMA off", arms)         # no starts of its own
        self.assertTrue(any("STRATA_PROMPT_ATTN_DENSE_IMMA off" in a for a in arms))
        self.assertEqual(res["report"]["decisions"]["STRATA_PROMPT_ATTN_DENSE_IMMA off"]["samples"][0], 6000.0)

    def test_one_of_a_group(self):
        def decode(env, tune, args):
            return 100.0 * (1.20 if env.get("STRATA_IQ3S_FAST") else 1.10 if env.get("STRATA_IQ3S_MT1") else 1.0)
        res, _, _ = self.run_fork(Model(decode=decode))
        self.assertEqual(res["report"]["chosen"].count("STRATA_IQ3S_FAST=1"), 1)
        self.assertNotIn("STRATA_IQ3S_MT1=1", res["report"]["chosen"])
        self.assertEqual((res["env"]["STRATA_IQ3S_FAST"], res["env"]["STRATA_IQ3S_MT1"]), ("1", "1"))

    def test_a_failed_start_drops_only_its_arm(self):
        starts = []
        model = Model(decode=lambda e, t, a: 110.0 if e.get("STRATA_POOL_FUSED") else 100.0)

        def start(a, e):
            if e.get("STRATA_IQ3S_MT1"):
                raise RuntimeError("out of memory")
            return FakeEngine(a, e, model, starts)
        res = CF.run_fork(self.cfg, say=lambda *_: None, budget_min=600, ctx=CTX, host=HOST, base_env=PACK_ENV,
                          start_engine=start, tok=Tok(), measure_host=lambda: {}, foreign=NoForeign())
        self.assertEqual(res["report"]["decisions"]["STRATA_IQ3S_MT1=1"]["why"], "the engine did not start")
        self.assertEqual(res["env"]["STRATA_POOL_FUSED"], "1")

    def test_other_programs_cpu_load_retakes_the_sample(self):
        res, _, said = self.run_fork(Model(), foreign=ListForeign([0.5, 0.02]))
        self.assertTrue(any("taking it again" in x for x in said))
        loads = [s["foreign"] for s in res["report"]["samples"]["baseline"]]
        self.assertTrue(all(x for x in loads))

    def test_non_finite_answers_stop_the_run(self):
        with self.assertRaises(CF.ForkAborted):
            self.run_fork(Model(finish="nonfinite"))

    def test_budget_keeps_the_most_valuable_first(self):
        facts = CF.facts_for(self.cfg, self.args, HOST)
        cands, _ = CF.applicable(facts)
        c = CF.costs(65536)
        fixed = CF.requests_s(c, 7, 5, 3)
        small = CF.plan(cands, c, fixed + 20 * 60, fixed)
        order = [x.name for x in cands]
        kept = [x.name for x in small["kept"]]
        self.assertEqual(kept[0], order[0])                                 # the most valuable first
        self.assertEqual(kept, [n for n in order if n in kept])             # in that order; a cheaper later one fits
        self.assertTrue(small["dropped"])
        self.assertLessEqual(small["total_s"], fixed + 20 * 60)
        big = CF.plan(cands, c, 10 ** 6, fixed)
        self.assertEqual(big["dropped"], [])
        self.assertGreater(big["confirm_s"], 0)

    def test_the_last_check_and_a_compared_config(self):
        live = {"args": self.args, "env": {"STRATA_IQ3S_MT1": "1"}}
        res, starts, _ = self.run_fork(Model(decode=lambda e, t, a: 110.0 if e.get("STRATA_POOL_FUSED") else 100.0),
                                       compare=live)
        self.assertEqual(set(res["report"]["confirm"]["summary"]), {"baseline", "tuned", "compare"})
        self.assertEqual(len(res["report"]["confirm"]["samples"]["compare"]), CF.CONFIRM_ROUNDS)
        res, _, _ = self.run_fork(Model(), compare=live)                   # nothing chosen: still the comparison
        self.assertEqual(set(res["report"]["confirm"]["summary"]), {"baseline", "compare"})

    # -------------------------------------------------------------------------------- from the hardware
    def test_derived_settings(self):
        facts = CF.facts_for(self.cfg, self.args, HOST)
        s, why = CF.derived_settings(self.args, facts, {"vram_free_mib": 323, "ram_avail_gib": 14.0,
                                                        "disk_free_gib": 356.0, "target_ctx": 65536})
        self.assertIs(s["--kv-grow"], True)
        self.assertEqual(s["--vram-reserve-mib"], "1408")                 # 700 + 1024 - 323, up to 64
        self.assertEqual(s["--conversation-cache-mib"], "4096")           # (14 - 6) / 2 GiB
        self.assertEqual(s["--conversation-cache-slots"], "2")
        self.assertEqual(s["--conversation-disk-mib"], "32768")
        s, _ = CF.derived_settings(CAL.with_arg(self.args, "--vram-reserve-mib", "1472"), facts,
                                   {"vram_free_mib": 1500, "ram_avail_gib": 6.5, "disk_free_gib": 20.0})
        self.assertNotIn("--vram-reserve-mib", s)                         # room enough: the config's own stays
        self.assertIsNone(s["--conversation-cache-mib"])                  # no RAM to spare: off
        self.assertIsNone(s["--conversation-disk-dir"])                   # 2 GiB would be a tenth: off
        no_disk = CAL.with_arg(self.args, "--conversation-disk-dir", None)
        s, _ = CF.derived_settings(no_disk, facts, {"disk_free_gib": 400.0})
        self.assertNotIn("--conversation-disk-dir", s)                    # never switched on by the calibration

    def test_the_reserve_comes_from_a_start_with_the_chosen_depth(self):
        # step 1's engine runs the deepest window (more VRAM for its buffers): the probe after it decides
        readings = iter([{"vram_free_mib": 145, "ram_avail_gib": 20.0}, {"vram_free_mib": 600, "ram_avail_gib": 20.0}])
        starts = []
        res = CF.run_fork(self.cfg, say=lambda *_: None, budget_min=600, ctx=CTX, host=HOST, base_env=PACK_ENV,
                          start_engine=lambda a, e: FakeEngine(a, e, Model(), starts), tok=Tok(),
                          measure_host=lambda: next(readings), foreign=NoForeign())
        self.assertEqual(res["settings"]["--vram-reserve-mib"], "1152")    # 700 + 1024 - 600, up to 64
        self.assertEqual(CAL.arg_value(starts[1].args, "--spec"), "4")      # the probe: the chosen depth
        self.assertEqual(res["report"]["hardware"]["step1"]["vram_free_mib"], 145)

    def test_apply_fork(self):
        fork = {"settings": {"--kv-grow": True, "--spec": "5", "--pcie-frac": None, "--vram-reserve-mib": "1408"},
                "env": {"STRATA_IQ3S_MT1": "1", "STRATA_ATTN_WINDOW_SMALL": None}}
        args, env = CF.apply_fork(self.args + ["--kv-grow"], {"STRATA_ATTN_WINDOW_SMALL": "1", "X": "2"}, fork)
        self.assertEqual(args.count("--kv-grow"), 1)
        self.assertEqual(CAL.arg_value(args, "--spec"), "5")
        self.assertIsNone(CAL.arg_value(args, "--pcie-frac"))
        self.assertEqual(env, {"X": "2", "STRATA_IQ3S_MT1": "1"})
        again = CF.apply_fork(args, env, fork)
        self.assertEqual(again, (args, env))
        off, _ = CF.apply_fork(args, env, {"settings": {"--kv-grow": False}})
        self.assertNotIn("--kv-grow", off)
        self.assertEqual(CAL.arg_value(off, "--native"), "m.gguf")       # a flag-only setting takes no value with it

    def test_agreement(self):
        a, b = [[1, 2, 3, 4]], [[1, 2, 9, 4]]
        self.assertEqual(CF.agreement([a, b]), 2)
        self.assertEqual(CF.agreement([a], [a]), 4)
        self.assertIsNone(CF.agreement([a]))


class NoForeign:
    def begin(self, pids):
        return None

    def end(self, token):
        return None


class ListForeign(NoForeign):
    def __init__(self, loads):
        self.loads = list(loads)

    def end(self, token):
        return self.loads.pop(0) if self.loads else 0.01


class SetupIntegration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = {k: os.environ.get(k) for k in ("APPDATA", "XDG_CONFIG_HOME")}
        os.environ["APPDATA"] = self.tmp.name
        os.environ["XDG_CONFIG_HOME"] = self.tmp.name
        import setup as S
        self.S = S
        self.saved = (S.gpu_info, S.cpu_info, S.ram_gb, CF.run_fork)
        S.gpu_info = lambda pick=None: {"name": "RTX Test", "vram_gb": 16.0, "arch": "120", "count": 1, "index": 0}
        S.cpu_info = lambda: ("Test CPU", True, False)
        S.ram_gb = lambda: 48.0

    def tearDown(self):
        self.S.gpu_info, self.S.cpu_info, self.S.ram_gb, CF.run_fork = self.saved
        for k, v in self.old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def test_calibrate_fork_writes_and_remembers(self):
        cfg_path = Path(self.tmp.name) / "strata-cybertiel-ud-iq4_xs.json"
        cfg = {"exe": "x", "args": list(ARGS), "model_name": "cyber-tiel", "env": {"STRATA_SYSMEM_PROBE": "1",
                                                                                  "STRATA_ATTN_WINDOW_SMALL": "1"}}
        cfg_path.write_text(json.dumps(cfg))
        res = {"settings": {"--spec": "4", "--kv-grow": True, "--vram-reserve-mib": "1408"},
               "env": {"STRATA_ATTN_WINDOW_SMALL": None, "STRATA_IQ3S_MT1": "1"}, "report": {"minutes": 50.0}}
        seen = {}

        def fake(c, say=print, budget_min=60.0, ctx=None, **k):
            seen.update(budget=budget_min, ctx=ctx)
            return res
        CF.run_fork = fake
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(self.S.calibrate_fork(cfg_path, budget_min=45, context=131072))
        self.assertEqual(seen, {"budget": 45, "ctx": 131072})
        written = json.loads(cfg_path.read_text())
        self.assertIn("--kv-grow", written["args"])
        self.assertEqual(CAL.arg_value(written["args"], "--vram-reserve-mib"), "1408")
        self.assertEqual(written["env"], {"STRATA_SYSMEM_PROBE": "1", "STRATA_IQ3S_MT1": "1"})
        saved = self.S.saved_calibration(written)
        self.assertEqual(saved["fork"]["env"], res["env"])
        # a setup run writes a fresh config (setup's PACK_TUNED) and applies the PC's fork calibration to it
        fresh = {"exe": "x", "args": list(ARGS), "model_name": "cyber-tiel", "env": dict(PACK_ENV)}
        applied = self.S.apply_saved_calibration(fresh, pack=True)
        self.assertNotIn("STRATA_ATTN_WINDOW_SMALL", applied["env"])
        self.assertEqual(applied["env"]["STRATA_IQ3S_MT1"], "1")
        self.assertIn("--kv-grow", applied["args"])

    def test_a_failed_fork_calibration_keeps_the_config(self):
        cfg_path = Path(self.tmp.name) / "strata-cybertiel-ud-iq4_xs.json"
        cfg_path.write_text(json.dumps({"exe": "x", "args": list(ARGS), "model_name": "m"}))

        def boom(*a, **k):
            raise CF.ForkAborted("the engine met non-finite logits (#879): the run stops here")
        CF.run_fork = boom
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertFalse(self.S.calibrate_fork(cfg_path))
        self.assertEqual(json.loads(cfg_path.read_text())["args"], ARGS)
        self.assertIsNone(self.S.saved_calibration({"args": ARGS, "model_name": "m"}))


if __name__ == "__main__":
    unittest.main()
