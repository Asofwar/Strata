"""#2261: KV streaming stays off on one card that holds every expert and the whole KV cache.  On an RTX PRO 6000
96 GB (IQ3_S, 262K, int8 KV) setup wrote --kv-resident 32768 although all experts were in VRAM; the KV cache in VRAM
measured decode +9.5%, agent decode +13%, a 16K prompt's first token -23%.  Every other PC keeps what setup wrote
before (the golden configs in tools/test_setup_golden.py check that byte for byte).  No GPU, no downloads.

    python tools/test_setup_kv_stream.py
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import setup  # noqa: E402
from test_setup_golden import PROFILES, card, install  # noqa: E402

BIG_RAM = 253.4                                       # the PC of #2261
BIG = card(0, "NVIDIA RTX PRO 6000 Blackwell Workstation Edition", 95.6, "120")


def go(ram, cards, *flags):
    return install(ram, cards, ["--family", "qwen", "--model", "IQ3_S", "--no-start", "--context", "262144",
                                "--kv", "int8", *flags])


class BigCard(unittest.TestCase):
    def test_everything_fits_streaming_off(self):
        code, out, cfg, _ = go(BIG_RAM, [BIG])
        self.assertEqual(code, 0, out)
        self.assertNotIn("--kv-resident", cfg["args"])
        self.assertIn("this card holds every expert and the whole KV cache", out)

    def test_on_still_streams(self):
        code, out, cfg, _ = go(BIG_RAM, [BIG], "--kv-streaming", "on")
        self.assertEqual(code, 0, out)
        self.assertIn("--kv-resident", cfg["args"])

    def test_a_layer_split_is_unchanged(self):
        code, out, cfg, _ = go(BIG_RAM, [BIG, card(1, BIG["name"], 95.6, "120")], "--gpus", "0,1")
        self.assertEqual(code, 0, out)
        self.assertIn("--kv-resident", cfg["args"])

    def test_the_rule(self):
        self.assertTrue(setup.kv_fits_in_vram("IQ3_S", 95.6, 262144, "int8"))
        self.assertFalse(setup.kv_fits_in_vram("IQ3_S", 47.5, 262144, "int8"))     # a 48 GB card: unchanged
        self.assertFalse(setup.kv_fits_in_vram("Q2_0", 31.8, 131072, "int8"))      # a 32 GB card: unchanged
        self.assertFalse(setup.kv_fits_in_vram("UD-Q4_K_XL", 95.6, 131072, "int8"))   # a budget file: unchanged
        self.assertFalse(setup.kv_fits_in_vram("IQ3_S", 95.6, 262144, "int8", reserve_gb=20))   # VRAM kept free
        with mock.patch.object(setup, "is_wsl", lambda: False):
            self.assertFalse(setup.kv_streaming_wanted("IQ3_S", 262144, "int8", BIG_RAM, "auto", 95.6))
            self.assertTrue(setup.kv_streaming_wanted("IQ3_S", 262144, "int8", BIG_RAM, "on", 95.6))
            self.assertTrue(setup.kv_streaming_wanted("IQ3_S", 262144, "int8", BIG_RAM, "auto"))   # vram unknown


class SmallCard(unittest.TestCase):
    """A 16 GB card streams from 64K as before."""

    def test_16gb_card_unchanged(self):
        ram, found = PROFILES["96GB-1x16GB"]
        for model, ctx in (("Q2_0", "131072"), ("IQ3_XXS", "131072"), ("IQ3_S", "262144")):
            with self.subTest(model=model, ctx=ctx):
                code, out, cfg, _ = install(ram, found, ["--family", "qwen", "--model", model, "--no-start",
                                                         "--context", ctx])
                self.assertEqual(code, 0, out)
                i = cfg["args"].index("--kv-resident")
                self.assertEqual(cfg["args"][i + 1], "32768")
                self.assertNotIn("#2261", out)
                with mock.patch.object(setup, "is_wsl", lambda: False):
                    self.assertTrue(setup.kv_streaming_wanted(model, int(ctx), "int8", ram, "auto",
                                                              found[0]["vram_gb"]))


if __name__ == "__main__":
    unittest.main()
