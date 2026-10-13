"""Tests for setup's --calibrate-switches (tools/calibrate.py measure_switches / run_switches), without a GPU: a
stand-in engine whose decode speed and greedy text depend on the switches in its environment.

    python tools/test_setup_switches.py
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
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT))
import calibrate as CAL  # noqa: E402

BASE = ["--pack", "p", "--spec", "4", "--spec-min-p", "0.5", "--max-context", "8192"]


class SwitchEngine:
    """Speed = speeds[the switch that is on] (each start takes the next value of a list, or a fixed number; 50 when not
    named); the text is [1] * n unless the switch is in `changes_text`."""

    def __init__(self, args, env, speeds, starts, changes_text=(), log=None, off_line=None, unstable=False):
        on = [k for k, v in CAL.SWITCHES.items() if env.get(k) == v]
        self.name = on[0] if on else "off"
        starts.append((self.name, dict(env), list(args)))
        self.info = {"expert_slots": 1000}
        sp = speeds.get(self.name, 50.0)               # a switch not named runs at 50 tok/s
        self.speed = (sp.pop(0) if len(sp) > 1 else sp[0]) if isinstance(sp, list) else sp   # the last one repeats
        # `unstable`: every start gives another text unless the cache is pinned (as `--expert-cache auto` on a shared
        # GPU); "always": pinned or not
        moves = unstable == "always" or (unstable and CAL.arg_value(args, "--expert-cache") in (None, "auto"))
        self.token = (2 if self.name in changes_text else 1) + (len(starts) * 10 if moves else 0)
        self.last = {}
        self.proc = None
        if log and off_line and self.name == "STRATA_ADAPT_OVERLAP":
            with open(log, "a", encoding="utf-8") as f:
                f.write(off_line + "\n")

    def generate(self, ids, max_new, sampling, cancel):
        for _ in range(max_new):
            yield self.token
        self.last = {"generated": max_new, "decode_ms": max_new / self.speed * 1000.0}


def run(speeds, changes_text=(), log=None, off_line=None, fail=(), unstable=False, base=BASE):
    starts, said = [], []

    def start(args, env):
        if env.get("STRATA_ADAPT_LAG") == "2" and "lag" in fail:
            raise RuntimeError("the engine exited before it was ready")
        if "check" in fail and CAL.arg_value(args, "--expert-cache") and len(starts) % 2:
            starts.append(("failed", dict(env), list(args)))
            raise RuntimeError("out of memory")
        return SwitchEngine(args, env, speeds, starts, changes_text, log, off_line, unstable)
    res = CAL.measure_switches(base, [[1, 2, 3]] * 3, start, say=said.append, log=log)
    return res, starts, said


class MeasureSwitches(unittest.TestCase):
    def test_flat_keeps_nothing(self):
        res, starts, _ = run({"off": 50.0})
        self.assertEqual(res["env"], {})
        self.assertEqual(len(starts), CAL.SWITCH_ROUNDS * (1 + len(CAL.SWITCHES)))   # no text check without a winner

    def test_clear_win_is_kept(self):
        res, starts, _ = run({"off": 50.0, "STRATA_ADAPT_OVERLAP": 56.0, "STRATA_ADAPT_LAG": 50.5})
        self.assertEqual(res["env"], {"STRATA_ADAPT_OVERLAP": "1"})
        d = res["report"]["decision"]
        self.assertTrue(d["STRATA_ADAPT_OVERLAP"]["faster"] and d["STRATA_ADAPT_OVERLAP"]["same_text"])
        self.assertFalse(d["STRATA_ADAPT_LAG"]["faster"])
        self.assertEqual(res["report"]["tok_s"], 56.0)
        # the text check: baseline, the faster switch, baseline again, with the cache pinned below auto's 1000 slots
        check = starts[CAL.SWITCH_ROUNDS * (1 + len(CAL.SWITCHES)):]
        self.assertEqual([n for n, _, _ in check], ["off", "STRATA_ADAPT_OVERLAP", "off"])
        self.assertTrue(all(CAL.arg_value(a, "--expert-cache") == "750" for _, _, a in check))
        self.assertTrue(all(e.get("STRATA_PREFILL_CPU_SHARE") == "0" for _, e, _ in check))
        self.assertTrue(all(CAL.arg_value(a, "--expert-cache") is None for _, _, a in starts[:-3]))   # speed: as run

    def test_the_better_of_two_winners(self):
        res, _, _ = run({"off": 50.0, "STRATA_ADAPT_OVERLAP": 54.0, "STRATA_ADAPT_LAG": 58.0})
        self.assertEqual(res["env"], {"STRATA_ADAPT_LAG": "2"})

    def test_a_win_inside_the_noise_is_not_kept(self):
        # the baseline spreads 46-54 (16%) across its starts: a 10% gain is inside it
        res, _, _ = run({"off": [46.0, 50.0, 54.0], "STRATA_ADAPT_OVERLAP": 55.0})
        self.assertEqual(res["env"], {})
        self.assertGreater(res["report"]["decision"]["STRATA_ADAPT_OVERLAP"]["margin"], 0.15)

    def test_the_median_decides_not_one_sample(self):
        # one slow start of the switch (another program on the GPU): its median still wins by more than the noise
        res, _, _ = run({"off": [50.0, 50.0, 51.0], "STRATA_ADAPT_OVERLAP": [54.0, 54.0, 50.5]})
        self.assertEqual(res["env"], {"STRATA_ADAPT_OVERLAP": "1"})

    def test_a_loss_is_not_kept(self):
        # #2010: an RTX 5090 Laptop decoded 21% slower with the overlap
        res, _, _ = run({"off": 106.6, "STRATA_ADAPT_OVERLAP": 84.6})
        self.assertEqual(res["env"], {})
        self.assertLess(res["report"]["decision"]["STRATA_ADAPT_OVERLAP"]["gain"], -0.2)

    def test_a_faster_switch_with_another_text_is_not_kept(self):
        res, _, said = run({"off": 50.0, "STRATA_ADAPT_LAG": 60.0}, changes_text=("STRATA_ADAPT_LAG",))
        self.assertEqual(res["env"], {})
        self.assertFalse(res["report"]["decision"]["STRATA_ADAPT_LAG"]["same_text"])
        self.assertTrue(any("ANOTHER text" in x for x in said))

    def test_the_text_check_pins_the_cache(self):
        # unpinned starts give another text each time (the speed rounds); pinned ones repeat: the switch is kept
        res, _, _ = run({"off": 50.0, "STRATA_ADAPT_OVERLAP": 56.0}, unstable=True,
                        base=BASE + ["--expert-cache", "auto"])
        self.assertEqual(res["env"], {"STRATA_ADAPT_OVERLAP": "1"})
        self.assertTrue(res["report"]["text_check"]["baseline_repeats"])

    def test_a_baseline_that_does_not_repeat_keeps_nothing(self):
        # the text moves between starts even with the cache pinned
        res, _, said = run({"off": 50.0, "STRATA_ADAPT_OVERLAP": 56.0}, unstable="always")
        self.assertEqual(res["env"], {})
        self.assertFalse(res["report"]["text_check"]["baseline_repeats"])
        self.assertTrue(any("cannot be checked" in x for x in said))

    def test_a_failed_check_start_keeps_nothing(self):
        res, _, _ = run({"off": 50.0, "STRATA_ADAPT_OVERLAP": 56.0}, fail=("check",))
        self.assertEqual(res["env"], {})

    def test_baseline_env_is_explicit_and_one_switch_at_a_time(self):
        _, starts, _ = run({"off": 50.0})
        for name, env, _ in starts:
            self.assertEqual(set(env), set(CAL.SWITCHES))            # the speed: the config's env otherwise
            on = [k for k in CAL.SWITCHES if env[k] == CAL.SWITCHES[k]]
            self.assertEqual(on, [] if name == "off" else [name])
        self.assertEqual(starts[0][1], CAL.SWITCH_OFF)
        # interleaved: every other round in reverse order
        names = [n for n, _, _ in starts]
        k = 1 + len(CAL.SWITCHES)
        self.assertEqual(names[k:2 * k], names[:k][::-1])

    def test_a_switch_the_engine_turns_off_is_not_measured(self):
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "strata.log"
            log.write_text("", encoding="utf-8")
            res, starts, said = run({"off": 50.0, "STRATA_ADAPT_OVERLAP": 70.0}, log=str(log),
                                    off_line="strata serve: STRATA_ADAPT_OVERLAP=1 is off: not on a layer split")
        self.assertEqual(res["env"], {})
        self.assertEqual(res["report"]["inactive"], {"STRATA_ADAPT_OVERLAP": "not on a layer split"})
        self.assertEqual(sum(1 for n, _, _ in starts if n == "STRATA_ADAPT_OVERLAP"), 1)   # asked once, then dropped
        self.assertTrue(any("does not run here" in x for x in said))

    def test_a_failed_start_drops_only_that_sample(self):
        res, _, _ = run({"off": 50.0, "STRATA_ADAPT_OVERLAP": 56.0}, fail=("lag",))
        self.assertEqual(res["env"], {"STRATA_ADAPT_OVERLAP": "1"})
        self.assertEqual(res["report"]["switches"]["STRATA_ADAPT_LAG"], [])
        self.assertIn("STRATA_ADAPT_LAG", res["report"]["failed_starts"])

    def test_no_baseline_sample_is_an_error_not_none_wins(self):
        # every start fails (no VRAM, the model already running): an error, so setup keeps the switch chosen before
        def start(args, env):
            raise RuntimeError("cudaMalloc failed")
        with self.assertRaisesRegex(RuntimeError, "cudaMalloc failed"):
            CAL.measure_switches(BASE, [[1, 2, 3]] * 3, start, say=lambda *_: None)

    def test_switch_wins(self):
        self.assertTrue(CAL.switch_wins([50, 50, 50], [52, 52, 52])[0])           # 4%: above MIN_GAIN, no spread
        self.assertFalse(CAL.switch_wins([48, 50, 52], [52, 52, 52])[0])          # 4%: inside the baseline's 8%
        self.assertFalse(CAL.switch_wins([50, 50, 50], [51, 51, 51])[0])          # 2%: below MIN_GAIN
        self.assertFalse(CAL.switch_wins([], [60])[0])
        self.assertFalse(CAL.switch_wins([50], [])[0])

    def test_apply_env(self):
        env = {"STRATA_ATTN_SPLITS": "256", "STRATA_ADAPT_LAG": "2"}
        self.assertEqual(CAL.apply_env(env, {"STRATA_ADAPT_OVERLAP": "1"}),
                         {"STRATA_ATTN_SPLITS": "256", "STRATA_ADAPT_OVERLAP": "1"})
        self.assertEqual(CAL.apply_env(env, {}), {"STRATA_ATTN_SPLITS": "256"})
        self.assertEqual(CAL.apply_env(None, {}), {})


class SetupSwitches(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = {k: os.environ.get(k) for k in ("APPDATA", "XDG_CONFIG_HOME")}
        os.environ["APPDATA"] = self.tmp.name
        os.environ["XDG_CONFIG_HOME"] = self.tmp.name
        import setup as S
        self.S = S
        self.saved = (S.gpu_info, S.cpu_info, S.ram_gb, CAL.run, CAL.run_switches)
        S.gpu_info = lambda pick=None: {"name": "RTX Test", "vram_gb": 16.0, "arch": "120", "count": 1, "index": 0}
        S.cpu_info = lambda: ("Test CPU", True, True)
        S.ram_gb = lambda: 64.0
        self.cfg_path = Path(self.tmp.name) / "strata-q2_0.json"
        self.cfg_path.write_text(json.dumps({"exe": "x", "args": list(BASE), "model_name": "m",
                                             "env": {"STRATA_ATTN_SPLITS": "256"}}))

    def tearDown(self):
        self.S.gpu_info, self.S.cpu_info, self.S.ram_gb, CAL.run, CAL.run_switches = self.saved
        for k, v in self.old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def quiet(self, f, *a):
        with contextlib.redirect_stdout(io.StringIO()):
            return f(*a)

    def test_switches_only_writes_env_and_remembers_it(self):
        CAL.run = lambda *a, **k: self.fail("--calibrate-switches alone must not run the settings' calibration")
        CAL.run_switches = lambda c, say=print: {"env": {"STRATA_ADAPT_OVERLAP": "1"}, "report": {"tok_s": 70.1}}
        self.assertTrue(self.quiet(self.S.calibrate_config, self.cfg_path, False, True))
        written = json.loads(self.cfg_path.read_text())
        self.assertEqual(written["env"], {"STRATA_ATTN_SPLITS": "256", "STRATA_ADAPT_OVERLAP": "1"})
        self.assertEqual(written["args"], BASE)
        saved = self.S.saved_calibration(written)
        self.assertEqual(saved["env"], {"STRATA_ADAPT_OVERLAP": "1"})
        self.assertNotIn("settings", saved)                # a reinstall still applies setup's own rule for those

    def test_no_winner_removes_an_older_choice(self):
        cfg = json.loads(self.cfg_path.read_text())
        cfg["env"]["STRATA_ADAPT_LAG"] = "2"
        self.cfg_path.write_text(json.dumps(cfg))
        CAL.run_switches = lambda c, say=print: {"env": {}, "report": {"tok_s": 60.0}}
        self.assertTrue(self.quiet(self.S.calibrate_config, self.cfg_path, False, True))
        self.assertEqual(json.loads(self.cfg_path.read_text())["env"], {"STRATA_ATTN_SPLITS": "256"})

    def test_settings_then_switches_and_settings_keep_the_switches(self):
        order = []
        CAL.run = lambda c, say=print: order.append("settings") or {"settings": {"--pcie-frac": "0.20"},
                                                                    "report": {"tok_s": 61.0}}
        CAL.run_switches = lambda c, say=print: order.append(("switches", CAL.arg_value(c["args"], "--pcie-frac"))) \
            or {"env": {"STRATA_ADAPT_LAG": "2"}, "report": {"tok_s": 63.0}}
        self.assertTrue(self.quiet(self.S.calibrate_config, self.cfg_path, True, True))
        self.assertEqual(order, ["settings", ("switches", "0.20")])   # measured with what --calibrate chose
        written = json.loads(self.cfg_path.read_text())
        self.assertEqual(written["env"]["STRATA_ADAPT_LAG"], "2")
        # a later --calibrate alone keeps the remembered switch
        self.assertTrue(self.quiet(self.S.calibrate_config, self.cfg_path))
        saved = self.S.saved_calibration(written)
        self.assertEqual(saved["settings"], {"--pcie-frac": "0.20"})
        self.assertEqual(saved["env"], {"STRATA_ADAPT_LAG": "2"})

    def test_failed_settings_skip_the_switches(self):
        def boom(*a, **k):
            raise RuntimeError("the engine exited before it was ready")
        CAL.run = boom
        CAL.run_switches = lambda *a, **k: self.fail("switches measured after a failed --calibrate")
        self.assertFalse(self.quiet(self.S.calibrate_config, self.cfg_path, True, True))

    def test_failed_switches_after_tuned_settings(self):
        # --calibrate --calibrate-switches: the settings are tuned and kept, the switch step's failure is its own
        CAL.run = lambda c, say=print: {"settings": {"--pcie-frac": "0.20"}, "report": {}}

        def boom(*a, **k):
            raise RuntimeError("the engine did not start for the baseline: cudaMalloc failed")
        CAL.run_switches = boom
        self.assertTrue(self.quiet(self.S.calibrate_config, self.cfg_path, True, True))
        written = json.loads(self.cfg_path.read_text())
        self.assertEqual(CAL.arg_value(written["args"], "--pcie-frac"), "0.20")
        self.assertEqual(written["env"], {"STRATA_ATTN_SPLITS": "256"})

    def test_failed_switches_keep_the_config(self):
        before = self.cfg_path.read_text()

        def boom(*a, **k):
            raise RuntimeError("the engine exited before it was ready")
        CAL.run_switches = boom
        self.assertFalse(self.quiet(self.S.calibrate_config, self.cfg_path, False, True))
        self.assertEqual(self.cfg_path.read_text(), before)
        self.assertIsNone(self.S.saved_calibration(json.loads(before)))

    def test_default_calibrate_does_not_measure_switches(self):
        CAL.run = lambda c, say=print: {"settings": {}, "report": {}}
        CAL.run_switches = lambda *a, **k: self.fail("switches measured without --calibrate-switches")
        self.assertTrue(self.quiet(self.S.calibrate_config, self.cfg_path))
        self.assertEqual(json.loads(self.cfg_path.read_text())["env"], {"STRATA_ATTN_SPLITS": "256"})

    def test_main_runs_switches_only(self):
        seen = []
        out = io.StringIO()
        with mock.patch.object(self.S, "ROOT", Path(self.tmp.name)), \
                mock.patch.object(self.S, "data_folder", lambda d: (Path(self.tmp.name) / "data", [])), \
                mock.patch.object(self.S, "update_installed_engine", lambda *a: None), \
                mock.patch.object(self.S, "calibrate_config", lambda p, s=True, w=False: seen.append((s, w)) or True), \
                mock.patch.object(sys, "argv", ["setup.py", "--calibrate-switches", "--no-start"]), \
                contextlib.redirect_stdout(out):
            self.assertEqual(self.S.main(), 0)
        self.assertEqual(seen, [(False, True)])

    def test_main_says_a_failed_switch_step(self):
        out = io.StringIO()
        with mock.patch.object(self.S, "ROOT", Path(self.tmp.name)),                 mock.patch.object(self.S, "data_folder", lambda d: (Path(self.tmp.name) / "data", [])),                 mock.patch.object(self.S, "update_installed_engine", lambda *a: None),                 mock.patch.object(self.S, "calibrate_config", lambda p, s=True, w=False: False),                 mock.patch.object(sys, "argv", ["setup.py", "--calibrate-switches", "--no-start"]),                 contextlib.redirect_stdout(out):
            self.assertEqual(self.S.main(), 0)
        self.assertIn("the decode switches were NOT measured", out.getvalue())
        self.assertNotIn("this PC is NOT tuned", out.getvalue())


if __name__ == "__main__":
    unittest.main()
