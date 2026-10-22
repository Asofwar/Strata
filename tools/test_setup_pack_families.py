"""Tests for setup.py's two qwen35moe families that run on Flash-Next's engine path from a Strata pack (OWN_PATH_FAMILIES
entries with "pack": True: Huihui-Ornith-1.5-35B-A3B-abliterated and Cyber-Tiel-Coder-35B-A3B): the pinned and hashed
files, the menu, and install_own_path's pack branch (the engine's qwen35moe-pack check, a compiled engine when the
ready-made one has none, the pack, and the config: --pack, int8 KV, the expert profile, MTP drafts from the file).
Mocked engine, downloads and processes - nothing is built, fetched or started.

    python tools/test_setup_pack_families.py
"""
from __future__ import annotations

import argparse
import contextlib
import io
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import setup  # noqa: E402

HEX = re.compile(r"^[0-9a-f]{64}$")


def args(**kw):
    base = dict(family="cyber-tiel", model=None, check=False, yes=True, vision=None, models_dir=None, gguf_dir=None,
                context=None, rope_scaling=None, rope_scale=None, kv=None, resident_budget_gib=None, low_ram="auto",
                vram_reserve_mib=None, host=None, api_key=None, browser=None, no_start=True, data_dir=None, gpu=None,
                draft_vocab=None)
    base.update(kw)
    return argparse.Namespace(**base)


def run(fn, *a, **kw):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        try:
            return fn(*a, **kw), out.getvalue()
        except SystemExit as e:
            return e.code, out.getvalue()


class Entries(unittest.TestCase):
    def test_pinned_and_hashed(self):
        for name, repo in (("ornith-abl", "mradermacher/Huihui-Ornith-1.5-35B-A3B-abliterated-i1-GGUF"),
                           ("cyber-tiel", "peculiar-ragdoll/Cyber-Tiel-Coder-35B-A3B-GGUF-MTP")):
            fam = setup.OWN_PATH_FAMILIES[name]
            self.assertTrue(fam["pack"])
            self.assertEqual(fam["arch"], "qwen35moe")
            self.assertIn(repo, setup.HF_REVISIONS)
            self.assertIs(setup.REPO_PINS[repo], fam["sha256"])
            self.assertEqual(fam["hf"], setup.hf(repo))
            for m in fam["models"]:
                size, sha = fam["sha256"][fam["file"].format(q=m)]
                self.assertGreater(size, 10 ** 10)
                self.assertRegex(sha, HEX)

    def test_sizes(self):
        self.assertEqual(list(setup.OWN_PATH_FAMILIES["ornith-abl"]["models"]), ["IQ4_XS", "IQ3_S"])
        self.assertEqual(list(setup.OWN_PATH_FAMILIES["cyber-tiel"]["models"]), ["UD-IQ4_XS", "UD-IQ3_XXS"])
        self.assertEqual(setup.CYBER_TIEL_FILES["Cyber-Tiel-Coder-35B-A3B-MTP-UD-IQ4_XS.gguf"][0], 18119934272)

    def test_a_pack_config_keeps_its_mtp_file(self):
        # update_install refreshes an MTP folder's token subset: not for a qwen35moe config (its --mtp is the GGUF)
        self.assertTrue(setup.own_path_config({"arch": "qwen35moe", "args": ["--pack", "p", "--mtp", "x.gguf"]}))


class InstallPack(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.calls = []
        self.families = {"qwen4exp", "qwen35moe", "qwen35moe-pack"}
        self.cfg = {}
        eng = self.root / "engine"
        built = self.root / "built"

        def engine_step(a, gpu, hip, amd, cuda_tk, vision):
            self.calls.append(("engine", vision))
            return self.root / "llama", eng, {"version": "0.1.46"}, ["/libs"], gpu, vision

        def build_engine(gpu, vision, yes, llama, toolkit=None):
            self.calls.append(("build",))
            built.mkdir(parents=True, exist_ok=True)
            (built / "BUILD.json").write_text('{"version": "0.1.46.1", "source": "local"}', encoding="utf-8")
            self.families = {"qwen4exp", "qwen35moe", "qwen35moe-pack"}
            return built

        def write_cfg(path, cfg, source=None, explicit=None):
            self.cfg = cfg
            self.calls.append(("config", path.name))

        patches = [mock.patch.object(setup, "download", lambda url, dst, what=None: self.calls.append(("get", url, dst))),
                   mock.patch.object(setup, "verify_sha256", lambda s, size, sha: self.calls.append(("sha", s.name))),
                   mock.patch.object(setup, "free_gb", lambda p: 500.0),
                   mock.patch.object(setup, "pip_install", lambda *a, **k: None),
                   mock.patch.object(setup, "engine_step", engine_step),
                   mock.patch.object(setup, "build_engine", build_engine),
                   mock.patch.object(setup, "engine_families", lambda e: self.families),
                   mock.patch.object(setup, "run", lambda cmd, **k: self.calls.append(("run", cmd))),
                   mock.patch.object(setup, "data_folder", lambda d, *a, **k: (self.root / "data", [])),
                   mock.patch.object(setup, "write_setup_config", write_cfg),
                   mock.patch.object(setup, "write_run_script", lambda tag, p, port, o=True: self.root / f"run-{tag}.sh"),
                   mock.patch.object(setup, "recommend_pool_workers", lambda a: a),
                   mock.patch.object(setup, "ROOT", self.root)]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def install(self, family="cyber-tiel", ram=64.0, vram=16.0, **kw):
        gpu = {"index": 0, "count": 1, "vram_gb": vram, "name": "Test GPU"}
        return run(setup.install_own_path, args(family=family, models_dir=str(self.root / "models"), **kw), family,
                   gpu, False, [], 13, [], 8080, ram, None)

    def test_cyber_tiel_writes_a_pack_config(self):
        rc, out = self.install(model="UD-IQ4_XS")
        self.assertEqual(rc, 0, out)
        gguf = self.root / "models" / "cybertiel-UD-IQ4_XS" / "Cyber-Tiel-Coder-35B-A3B-MTP-UD-IQ4_XS.gguf"
        get = [c for c in self.calls if c[0] == "get"]
        self.assertEqual([g[2] for g in get], [gguf])              # the GGUF only: no image encoder
        self.assertIn(("sha", gguf.name), self.calls)
        self.assertIn(("engine", "none"), self.calls)
        packs = [c for c in self.calls if c[0] == "run" and "iq_pack.py" in str(c[1])]
        self.assertEqual(len(packs), 1)
        self.assertIn("--compat-bf16", packs[0][1])
        a = self.cfg["args"]
        pack = self.root / "data" / "packs" / "cybertiel-ud-iq4_xs"
        self.assertEqual(a[a.index("--pack") + 1], str(pack))
        self.assertEqual(a[a.index("--native") + 1], str(gguf))
        self.assertEqual(a[a.index("--mtp") + 1], str(gguf))       # the file's own draft layer
        self.assertEqual(a[a.index("--mtp-draft-vocab") + 1], str(self.root / "data" / "draft_vocab.bin"))
        self.assertEqual(a[a.index("--expert-profile") + 1], str(self.root / "data" / "expert-profile-qwen36.bin"))
        self.assertEqual(a[a.index("--kv") + 1], "int8")
        self.assertEqual(a[a.index("--spec") + 1], "4")
        self.assertEqual(a[a.index("--max-context") + 1], "262144")   # 16 GB card, int8 KV
        self.assertNotIn("--vision", a)
        self.assertEqual(self.cfg["arch"], "qwen35moe")
        self.assertEqual(self.cfg["model_name"], "cyber-tiel-coder-35b-a3b-ud-iq4_xs")
        self.assertNotIn("parallel", self.cfg)
        self.assertNotIn(("build",), self.calls)
        self.assertIn(("config", "strata-cybertiel-ud-iq4_xs.json"), self.calls)
        # the fork's measured settings for the pack path (setup.PACK_TUNED)
        self.assertIn("--kv-grow", a)
        self.assertEqual(self.cfg["env"]["STRATA_ATTN_WINDOW"], "1")
        self.assertEqual(self.cfg["env"]["STRATA_ATTN_WINDOW_PREC"], "2")
        # no FP16 prompt mode: DENSE_IMMA takes precedence over it with int8 K/V, so it would change nothing
        self.assertNotIn("STRATA_PROMPT_ATTN_FP16ACC", self.cfg["env"])
        self.assertEqual(self.cfg["reasoning_loop_recovery"], "resample")
        self.assertIs(self.cfg["reasoning_close_retry"], True)
        self.assertEqual(self.cfg["env"]["STRATA_PROMPT_ATTN_DENSE_IMMA"], "4")
        self.assertEqual(self.cfg["env"]["STRATA_ATTN_WINDOW_SMALL"], "1")
        self.assertEqual(self.cfg["env"]["STRATA_MMQ_KQ"], "1")
        self.assertEqual(self.cfg["env"]["STRATA_ARENA_WSLOCK"], "1")
        self.assertEqual(self.cfg["sampling"], {"temperature": 0.6, "presence_penalty": 0})

    def test_ornith_abl_and_the_draft_subset(self):
        rc, out = self.install(family="ornith-abl", model="IQ3_S", draft_vocab="cyrillic", vram=12.0, kv="q4_0")
        self.assertEqual(rc, 0, out)
        a = self.cfg["args"]
        self.assertTrue(a[a.index("--native") + 1].endswith("Huihui-Ornith-1.5-35B-A3B-abliterated.i1-IQ3_S.gguf"))
        self.assertEqual(Path(a[a.index("--mtp-draft-vocab") + 1]).name, "draft_vocab_cyrillic.bin")
        self.assertEqual(a[a.index("--kv") + 1], "q4_0")
        self.assertEqual(a[a.index("--max-context") + 1], "131072")   # a 12 GB card
        self.assertEqual(self.cfg["model_name"], "huihui-ornith-1.5-35b-a3b-abliterated-iq3_s")

    def test_a_ready_made_engine_without_the_pack_path_is_compiled(self):
        self.families = {"qwen4exp", "qwen35moe"}                  # upstream's engine: src/qwen35 only
        rc, out = self.install(model="UD-IQ4_XS")
        self.assertEqual(rc, 0, out)
        self.assertIn(("build",), self.calls)
        self.assertIn("compiling the engine on this PC instead", out)
        self.assertEqual(Path(self.cfg["exe"]).parent, self.root / "built")

    def test_images_are_not_offered(self):
        rc, out = self.install(model="UD-IQ4_XS", vision="gpu")
        self.assertEqual(rc, 0, out)
        self.assertIn("images off", out)
        self.assertNotIn("vision", self.cfg)


if __name__ == "__main__":
    unittest.main()
