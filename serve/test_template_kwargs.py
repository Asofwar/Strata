"""serve/test_template_kwargs.py - the config's "chat_template_kwargs": a template's own switches (mock engine, no GPU).

Some packs' templates take switches of their own: Cyber-Tiel's adds a "be terse" system text unless `terse` is false,
and has `max_tool_response_chars`, `tool_call_format` and others.  The server passes a request's chat_template_kwargs
on only for enable_thinking, reasoning_effort and preserve_thinking, so `{"terse": false}` (the model card's own
advice) was silently dropped.  The config's "chat_template_kwargs" names the switches to pass and their values for
every request; a request may set its own value for a key the config names (and only for those).  Without the key in
the config nothing changes: the prompt is byte-identical.

    python -m unittest serve.test_template_kwargs -v
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from serve.frontend import ChatTemplate  # noqa: E402
from serve.server import ByteTokenizer, MockEngine, Service, clean_template_kwargs, serve  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
MSG = [{"role": "user", "content": "hello"}]
# the original template with a switch of its own in front, the way Cyber-Tiel's reads `terse`
SWITCH = ("{%- set _terse_on = terse if terse is defined else true %}"
          "{%- if not _terse_on %}[terse off]{% endif %}"
          "{%- if max_tool_response_chars is defined %}[cap {{ max_tool_response_chars }}]{% endif %}")


class TemplateKwargs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        path = Path(cls.tmp.name) / "chat_template.jinja"
        path.write_text(SWITCH + (ROOT / "serve/chat_template.jinja").read_text(encoding="utf-8"), encoding="utf-8")
        cls.tok = ByteTokenizer()
        cls.engine = MockEngine(cls.tok, "<think>\nhm\n</think>\n\nok", max_context=8192)
        cls.svc = Service(cls.engine, cls.tok, ChatTemplate(path))
        cls.httpd = serve(cls.svc, port=0)
        cls.base = f"http://127.0.0.1:{cls.httpd.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.tmp.cleanup()

    def setUp(self):
        self.svc.template_extra = {}

    def post(self, path, body):
        req = urllib.request.Request(self.base + path, data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        self.engine.last_prompt = []
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                status = r.status
                r.read()
        except urllib.error.HTTPError as e:
            with e:
                status = e.code
        return status, self.tok.decode(self.engine.last_prompt)

    def openai(self, **extra):
        return self.post("/v1/chat/completions", {"messages": MSG, "max_tokens": 16, **extra})

    def test_off_by_default_request_switch_ignored(self):
        """No config key: a request's own switch is dropped as before, so every prompt stays what it was."""
        status, plain = self.openai()
        self.assertEqual(status, 200)
        status, asked = self.openai(chat_template_kwargs={"terse": False})
        self.assertEqual(status, 200)
        self.assertEqual(asked, plain)
        self.assertNotIn("[terse off]", plain)

    def test_config_value_reaches_every_api(self):
        self.svc.template_extra = {"terse": False}
        status, prompt = self.openai()
        self.assertEqual((status, "[terse off]" in prompt), (200, True))
        status, prompt = self.post("/v1/messages", {"model": "m", "max_tokens": 16, "messages": MSG})
        self.assertEqual((status, "[terse off]" in prompt), (200, True))
        status, prompt = self.post("/v1/responses", {"model": "m", "input": "hello", "max_output_tokens": 16})
        self.assertEqual((status, "[terse off]" in prompt), (200, True))

    def test_request_overrides_only_named_keys(self):
        self.svc.template_extra = {"terse": True}
        status, prompt = self.openai()
        self.assertEqual((status, "[terse off]" in prompt), (200, False))
        status, prompt = self.openai(chat_template_kwargs={"terse": False, "max_tool_response_chars": 5})
        self.assertEqual(status, 200)
        self.assertIn("[terse off]", prompt)
        self.assertNotIn("[cap", prompt)            # a key the config does not name is not passed on

    def test_config_default_equal_to_template_default_changes_nothing(self):
        status, plain = self.openai()
        self.svc.template_extra = {"terse": True}
        status2, named = self.openai()
        self.assertEqual((status, status2), (200, 200))
        self.assertEqual(named, plain)

    def test_effort_and_preserve_keep_their_own_paths(self):
        self.svc.template_extra = {"terse": False}
        status, prompt = self.openai(reasoning_effort="low", chat_template_kwargs={"preserve_thinking": True})
        self.assertEqual(status, 200)
        self.assertIn("Reasoning effort is set to low.", prompt)
        self.assertIn("[terse off]", prompt)

    def test_bad_request_value_is_400(self):
        self.svc.template_extra = {"terse": True}
        status, _ = self.openai(chat_template_kwargs={"terse": {"x": 1}})
        self.assertEqual(status, 400)


class CleanTemplateKwargs(unittest.TestCase):
    def test_accepts_scalars(self):
        self.assertEqual(clean_template_kwargs({"terse": False, "max_tool_response_chars": 4000, "tool_call_format":
                                                "xml", "x": None, "y": 0.5}),
                         {"terse": False, "max_tool_response_chars": 4000, "tool_call_format": "xml", "x": None,
                          "y": 0.5})

    def test_refuses(self):
        for bad in ([], "terse", {"terse": [1]}, {"terse": {"a": 1}}, {"messages": []}, {"tools": None},
                    {"add_generation_prompt": False}, {"enable_thinking": False}, {"reasoning_effort": "low"},
                    {"preserve_thinking": True}, {"bad key": 1}, {"": 1}):
            with self.assertRaises(ValueError, msg=repr(bad)):
                clean_template_kwargs(bad)


if __name__ == "__main__":
    unittest.main()
