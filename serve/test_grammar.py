"""Constrained decoding (serve/grammar.py): the tool-call and JSON grammars on tricky schemas, the G-line protocol with
drafts, and the server with an engine that follows the masks.  Needs the llguidance package (skipped without it).
STRATA_GRAMMAR_TOKENIZER=<a pack's tokenizer folder> also runs the grammar walks with the model's own tokenizer."""
import contextlib
import io
import json
import os
import sys
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from serve import grammar as G  # noqa: E402
from serve.frontend import ChatTemplate, parse_tool_call  # noqa: E402
from serve.server import ByteTokenizer, MockEngine, Service  # noqa: E402

try:
    import llguidance  # noqa: F401
    HAVE_LLG = True
except ImportError:
    HAVE_LLG = False
try:
    import jsonschema
except ImportError:
    jsonschema = None


class ToolTokenizer(ByteTokenizer):
    """The test byte tokenizer with the template's single-token tags (USER_DEFINED, as in the Qwen3.6 vocabulary)."""
    SPECIALS = ByteTokenizer.SPECIALS + ["<tool_call>", "</tool_call>", "<think>", "</think>"]
    ALWAYS = ("<tool_call>", "</tool_call>", "<think>", "</think>")

    @property
    def tokens(self):
        return [chr(i) for i in range(256)] + list(self.SPECIALS)

    @property
    def token_types(self):
        return [1] * 256 + [4 if s in self.ALWAYS else 3 for s in self.SPECIALS]

    def token_bytes(self, i):
        return bytes([i]) if i < 256 else self.SPECIALS[i - 256].encode()

    def id_of(self, s):
        return 256 + self.SPECIALS.index(s)


SHELL = {"name": "shell", "parameters": {"type": "object", "properties": {
    "command": {"type": "array", "items": {"type": "string"}, "minItems": 1},
    "workdir": {"type": "string"},
    "timeout_ms": {"type": "integer"},
    "with_escalated_permissions": {"type": "boolean"}},
    "required": ["command"], "additionalProperties": False}}
PLAN = {"name": "update_plan", "parameters": {"type": "object", "properties": {
    "explanation": {"type": "string"},
    "plan": {"type": "array", "items": {"type": "object", "properties": {
        "step": {"type": "string"},
        "status": {"type": "string", "enum": ["pending", "in_progress", "completed"]}},
        "required": ["step", "status"], "additionalProperties": False}}},
    "required": ["plan"], "additionalProperties": False}}
NESTED = {"name": "configure", "parameters": {"type": "object", "properties": {
    "mode": {"type": "string", "enum": ["fast", "safe"]},
    "ratio": {"type": "number", "minimum": 0},
    "opts": {"$ref": "#/$defs/opts"},
    "tags": {"type": ["array", "null"], "items": {"type": "string"}}},
    "required": ["mode", "opts"],
    "$defs": {"opts": {"type": "object", "properties": {
        "depth": {"type": "integer"},
        "inner": {"type": "object", "properties": {"on": {"type": "boolean"}, "name": {"type": "string"}},
                  "required": ["on"]}},
        "required": ["inner"]}}}}
WIDE = {"name": "wide", "parameters": {"type": "object", "properties": {
    f"a{i}": {"type": "string"} for i in range(8)}, "required": ["a3"]}}
FREE = {"name": "mcp_any", "parameters": {"type": "object"}}
TOOLS = [SHELL, PLAN, NESTED, WIDE, FREE]


def call(name, *params):
    body = "".join(f"<parameter={k}>\n{v}\n</parameter>\n" for k, v in params)
    return f"\n<function={name}>\n{body}</function>\n</tool_call>"


@unittest.skipUnless(HAVE_LLG, "llguidance is not installed")
class ToolGrammar(unittest.TestCase):
    tok = None

    @classmethod
    def setUpClass(cls):
        if cls.tok is None:
            cls.tok = ToolTokenizer()
        cls.eos = {cls.tok.encode("<|im_end|>", parse_special=True)[0]}
        cls.cache = {}

    def session(self, tools=TOOLS, **kw):
        t = self.tok
        tc = t.encode("<tool_call>")
        te = t.encode("</think>")
        return G.build_session(t, self.eos, tools=tools, tool_call_id=tc[0] if len(tc) == 1 else None,
                               think_end=te[0] if len(te) == 1 else None, cache=self.cache, **kw)

    def walk(self, text, s=None, trigger=True):
        """How far `text` gets through the grammar: (accepted, index of the first refused token or None)."""
        s = s or self.session()
        done0 = s.stats["completed"]
        if trigger:
            s.observe(self.tok.encode("<tool_call>")[0])
        ids = self.tok.encode(text)
        for i, t in enumerate(ids):
            if s.m is None:
                return False, "the grammar ended before " + repr(self.tok.decode(ids[i:])[:30])
            bm = s.m.compute_bitmask()
            if not (bm[t >> 3] >> (t & 7)) & 1:
                return False, self.tok.decode(ids[:i])[-30:] + "|" + self.tok.decode([t])
            s.observe(t)
        return s.m is None and s.stats["completed"] == done0 + 1, None

    def good(self, text, **kw):
        ok, where = self.walk(text, **kw)
        self.assertTrue(ok, f"refused at {where!r}: {text!r}")

    def bad(self, text, **kw):
        ok, _ = self.walk(text, **kw)
        self.assertFalse(ok, f"accepted: {text!r}")

    def test_strings_with_escapes_and_code(self):
        cmd = json.dumps(["bash", "-lc", 'cat > a.py <<\'EOF\'\nprint("привет", r"\\d+")\nEOF\n'], ensure_ascii=False)
        self.good(call("shell", ("command", cmd), ("workdir", 'C:\\Users\\x y "quoted"\n2nd line')))
        self.good(call("shell", ("command", '[ "a" ,\n  "b"\t]')))                     # JSON whitespace
        self.good(call("shell", ("command", '["\\u0041\\n\\t\\\\"]')))
        self.good(call("shell", ("workdir", ""), ("command", '["x"]')))                 # empty string value
        self.good(call("mcp_any", ("q", 'x = "</parameter>" inside')))                  # the end tag mid-line

    def test_numbers_and_booleans(self):
        for n in ("0", "-12", "1000"):
            self.good(call("shell", ("command", '["x"]'), ("timeout_ms", n)))
        for n in ("1.5", '"10"', "1e3", "", "01"):
            self.bad(call("shell", ("command", '["x"]'), ("timeout_ms", n)))
        self.good(call("shell", ("command", '["x"]'), ("with_escalated_permissions", "true")))
        self.bad(call("shell", ("command", '["x"]'), ("with_escalated_permissions", "yes")))
        self.good(call("configure", ("mode", "fast"), ("ratio", "0.25"), ("opts", '{"inner": {"on": false}}')))
        self.bad(call("configure", ("mode", "fast"), ("ratio", "-1"), ("opts", '{"inner": {"on": false}}')))   # minimum

    def test_structure(self):
        self.bad("\n<function=shel>\n")                                                 # unknown tool
        self.bad(call("shell"))                                                         # a required one missing
        self.bad(call("shell", ("cmd", '["x"]')))                                       # unknown parameter
        self.bad(call("shell", ("command", '["x"]'), ("command", '["y"]')))              # twice
        self.bad(call("shell", ("command", "ls -la")))                                  # an array as text
        self.bad(call("shell", ("command", '["echo\nhi"]')))                            # raw newline in a JSON string
        self.bad(call("shell", ("command", '["a"')))                                    # unclosed
        self.bad(call("shell", ("command", "[]")))                                      # minItems
        self.bad("<function=shell>\n")                                                  # the template's newline first

    def test_any_order_and_wide(self):
        self.good(call("shell", ("workdir", "/tmp"), ("timeout_ms", "5"), ("command", '["ls"]')))
        # more than SUBSET_MAX parameters: schema order, the optional ones skippable
        self.good(call("wide", ("a1", "x"), ("a3", "y"), ("a7", "z")))
        self.bad(call("wide", ("a1", "x")))                                             # a3 is required
        self.bad(call("wide", ("a3", "y"), ("a1", "x")))                                # out of order

    def test_nested_enum_ref(self):
        plan = json.dumps([{"step": "Сделать «X»", "status": "in_progress"}, {"step": "b", "status": "pending"}],
                          ensure_ascii=False)
        self.good(call("update_plan", ("plan", plan)))
        self.bad(call("update_plan", ("plan", '[{"step": "a", "status": "done"}]')))      # enum
        self.bad(call("update_plan", ("plan", '[{"step": "a"}]')))                       # required inside
        self.bad(call("update_plan", ("plan", '[{"step": "a", "status": "pending", "x": 1}]')))
        self.good(call("configure", ("opts", '{"depth": 3, "inner": {"on": true, "name": "n"}}'), ("mode", "safe")))
        self.bad(call("configure", ("opts", '{"depth": 3}'), ("mode", "safe")))         # $ref's required
        self.bad(call("configure", ("opts", '{"inner": {"on": true}}'), ("mode", "medium")))   # string enum
        # ["array", "null"]: the parser json-decodes it, so it is JSON of the schema (text would arrive as a string)
        self.good(call("configure", ("mode", "fast"), ("opts", '{"inner": {"on": true}}'), ("tags", '["a", "b"]')))
        self.good(call("configure", ("mode", "fast"), ("opts", '{"inner": {"on": true}}'), ("tags", "null")))
        self.bad(call("configure", ("mode", "fast"), ("opts", '{"inner": {"on": true}}'), ("tags", "a, b")))

    def test_free_form_tool(self):
        self.good(call("mcp_any"))
        self.good(call("mcp_any", ("anything", "1"), ("else", '{"a": [1, 2]}')))

    def test_parsed_arguments_validate(self):
        """What the grammar accepts, the parser reads as arguments that pass the tool's schema."""
        if jsonschema is None:
            self.skipTest("jsonschema is not installed")
        text = call("shell", ("timeout_ms", "250"), ("command", '["git", "commit", "-m", "fix: \\"x\\"\\n\\nbody"]'))
        self.good(text)
        tc = parse_tool_call(text.strip()[: -len("</tool_call>")].strip(), SHELL)
        jsonschema.validate(tc.arguments, SHELL["parameters"])
        self.assertEqual(tc.arguments["command"][3], 'fix: "x"\n\nbody')

    def test_forced_openings(self):
        s = self.session(force="<tool_call>\n<function=")
        # constrained from the start, and the trigger for a second call after the forced one
        self.assertEqual(s.engine_key(), f" grammar=-1,{self.tok.encode('<tool_call>')[0]}")
        self.good(call("shell", ("command", '["ls"]'))[len("\n<function="):], s=s, trigger=False)
        s = self.session(force="<tool_call>\n<function=update_plan>\n")
        self.bad("<parameter=command>\n", s=s, trigger=False)
        s = self.session(force="<tool_call>\n<function=update_plan>\n")
        self.good('<parameter=plan>\n[]\n</parameter>\n</function>\n</tool_call>', s=s, trigger=False)

    def test_thinking_gate(self):
        s = self.session(thinking=True)
        tc = self.tok.encode("<tool_call>")[0]
        s.observe(tc)                         # a call written inside the thinking is not constrained
        self.assertIsNone(s.m)
        s.observe(self.tok.encode("</think>")[0])
        s.observe(tc)
        self.assertIsNotNone(s.m)

    def test_session_ends_and_restarts(self):
        s = self.session()
        self.good(call("shell", ("command", '["a"]')), s=s)
        self.assertIsNone(s.m)
        self.assertEqual(s.answer(3, [1, 2]), "G off\n")
        self.good(call("update_plan", ("plan", "[]")), s=s)                             # a second call
        self.assertEqual(s.stats["completed"], 2)


@unittest.skipUnless(HAVE_LLG, "llguidance is not installed")
class Protocol(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tok = ToolTokenizer()
        cls.eos = {cls.tok.encode("<|im_end|>", parse_special=True)[0]}

    def session(self, tools=TOOLS, **kw):
        return G.build_session(self.tok, self.eos, tools=tools, tool_call_id=self.tok.id_of("<tool_call>"),
                               think_end=self.tok.id_of("</think>"), **kw)

    @staticmethod
    def decode(enc, n):
        """The engine's reading of a GD mask (src/program/generate.cpp)."""
        sign, body = enc[0], enc[1:]
        allowed = set()
        for part in filter(None, body.split(",")):
            a, _, b = part.partition("-")
            allowed.update(range(int(a), int(b or a) + 1))
        return allowed if sign == "+" else set(range(n)) - allowed

    def parse(self, reply, masks):
        lines = reply.strip("\n").split("\n")
        for line in lines[:-1]:
            tag, mid, n, enc = line.split(" ", 3)
            self.assertEqual(tag, "GD")
            masks[int(mid)] = self.decode(enc, int(n))
        last = lines[-1].split()
        self.assertEqual(last[0], "G")
        return last[1:]

    def test_mask_encoding_roundtrip(self):
        import random
        rnd = random.Random(1)
        n = 1000
        for density in (0.001, 0.3, 0.7, 0.999):
            bits = [rnd.random() < density for _ in range(n)]
            bm = bytearray((n + 7) // 8)
            for v, on in enumerate(bits):
                if on:
                    bm[v >> 3] |= 1 << (v & 7)
            enc = G.encode_mask(bytes(bm), n)
            self.assertEqual(self.decode(enc, n), {v for v, on in enumerate(bits) if on})
            saved, G.np = G.np, None                     # the plain-Python encoder gives the same text
            try:
                self.assertEqual(G.encode_mask(bytes(bm), n), enc)
            finally:
                G.np = saved

    def test_rows_follow_drafts(self):
        s = self.session()
        s.observe(self.tok.id_of("<tool_call>"))
        masks = {}
        enc = self.tok.encode
        # the window's drafts: "\n<fu" - each row's mask is the state after the drafts before it
        ids = self.parse(s.answer(5, enc("\n<fu")), masks)
        self.assertEqual(len(ids), 5)
        self.assertEqual(masks[int(ids[0])], {enc("\n")[0]})
        self.assertEqual(masks[int(ids[3])], {enc("u")[0]})
        self.assertNotIn(0, map(int, ids))
        # nothing was consumed: the next window starts from the same state
        self.assertEqual(self.parse(s.answer(1, []), masks), [ids[0]])
        # a forbidden draft: its row's mask is used, the rows after it are not (0)
        ids = self.parse(s.answer(4, enc("\nX") + [enc("y")[0]]), masks)
        self.assertEqual(ids[2:], ["0", "0"])
        self.assertNotEqual(ids[1], "0")
        # masks are defined once
        reply = s.answer(5, enc("\n<fu"))
        self.assertNotIn("GD", reply)

    def test_rows_after_the_end_are_free(self):
        s = self.session()
        s.observe(self.tok.id_of("<tool_call>"))
        for t in self.tok.encode(call("mcp_any")[:-1]):   # all but the last '>' of </tool_call>... as bytes
            s.observe(t)
        # the call's last byte as row 0's pick, then two free rows
        ids = self.parse(s.answer(3, self.tok.encode(">") + [self.tok.id_of("<tool_call>")]), {})
        self.assertNotEqual(ids[0], "0")
        self.assertEqual(ids[1:], ["0", "0"])

    def test_engine_key(self):
        s = self.session()
        self.assertEqual(s.engine_key(), f" grammar={self.tok.id_of('<tool_call>')}")
        j = G.build_session(self.tok, self.eos, json_schema={"type": "object"}, thinking=True,
                            think_end=self.tok.id_of("</think>"))
        self.assertEqual(j.engine_key(), f" grammar={self.tok.id_of('</think>')}")
        j = G.build_session(self.tok, self.eos, json_schema={"type": "object"})
        self.assertEqual(j.engine_key(), " grammar=-1")

    def test_masks_defined_again_each_pass(self):
        """The engine forgets the masks with every GEN (a retry, a continuation): they are sent again."""
        s = self.session()
        s.observe(self.tok.id_of("<tool_call>"))
        self.assertIn("GD 1 ", s.answer(1, []))
        self.assertNotIn("GD", s.answer(1, []))
        s.engine_key()
        self.assertIn("GD 1 ", s.answer(1, []))

    def test_end_of_turn_draft(self):
        """An end-of-turn draft is not fed to the matcher: rollback would not count it and undo one token too many."""
        j = G.build_session(self.tok, self.eos, json_schema={"type": "object", "properties": {
            "a": {"type": "integer"}, "b": {"type": "integer"}}, "required": ["a"], "additionalProperties": False})
        for t in self.tok.encode('{"a":'):
            j.observe(t)
        eos = next(iter(self.eos))
        ids = self.parse(j.answer(4, self.tok.encode("1}") + [eos]), {})
        self.assertEqual(ids[3], "0")
        for t in self.tok.encode("1,"):              # the target took "," where the draft had "}"
            j.observe(t)
        self.assertIsNotNone(j.m)
        self.assertEqual(j.stats["errors"], 0)

    def test_json_answer_ends_the_turn(self):
        j = G.build_session(self.tok, self.eos, json_schema={"type": "object", "properties": {
            "a": {"type": "integer"}, "b": {"type": "number"}}, "required": ["a"], "additionalProperties": False})
        for t in self.tok.encode('\n{"a": 5, "b": -2.5E+3}'):
            bm = j.m.compute_bitmask()
            self.assertTrue((bm[t >> 3] >> (t & 7)) & 1, t)
            j.observe(t)
        bm = j.m.compute_bitmask()
        allowed = {v for v in range(len(self.tok.tokens)) if (bm[v >> 3] >> (v & 7)) & 1}
        self.assertTrue(allowed & self.eos)
        self.assertFalse(allowed & set(self.tok.encode("x}")))


class GrammarEngine(MockEngine):
    """A mock engine that speaks the G protocol the way src/program/generate.cpp does, one token a window: its
    "model" wants the scripted tokens; under a mask it takes the next scripted token the mask allows (as a sampler
    takes the next likely one), else the lowest allowed id."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.info = {"grammar": 1}
        self.keys = []

    def generate(self, ids, max_new, sampling, cancel, embeddings=None):
        gs = (sampling or {}).get("strata_grammar")
        key = gs.engine_key() if gs is not None else ""
        self.keys.append(key)
        if not key:
            yield from super().generate(ids, max_new, sampling, cancel, embeddings)
            return
        val = key.split("=", 1)[1]
        active = "-1" in val.split(",")
        triggers = {int(x) for x in val.split(",") if x != "-1"}
        masks = {}
        script = list(self.script)
        i = 0
        for _ in range(max_new):
            mask = None
            if active:
                reply = gs.answer(1, [])
                for line in reply.strip("\n").split("\n"):
                    f = line.split(" ", 3)
                    if f[0] == "GD":
                        masks[int(f[1])] = Protocol.decode(f[3], int(f[2]))
                    elif f[1] == "off":
                        active = False
                    elif f[1] != "0":
                        mask = masks[int(f[1])]
            if mask is None:
                t = script[i] if i < len(script) else script[-1]
                i += 1
            else:
                j = i
                while j < len(script) and script[j] not in mask:
                    j += 1
                if j < len(script):
                    t, i = script[j], j + 1
                else:
                    t = min(mask)
            yield t
            if mask is None and t in triggers:
                active = True
            if t in self.tok.encode("<|im_end|>", parse_special=True):
                return


@unittest.skipUnless(HAVE_LLG, "llguidance is not installed")
class ServerWithMasks(unittest.TestCase):
    MALFORMED = ("I will run it.\n\n<tool_call>\n<function=shell>\n<parameter=cmd>\nx\n</parameter>\n"
                 "<parameter=command>\n[\"bash\", \"-lc\", \"echo \"hi\"\nls\"]\n</parameter>\n"
                 "<parameter=timeout_ms>\n\"500\"\n</parameter>\n</function>\n</tool_call>")

    def run_reply(self, on, script=None, req=None, thinking=False):
        tok = ToolTokenizer()
        eng = GrammarEngine(tok, script or self.MALFORMED, max_context=1 << 16)
        svc = Service(eng, tok, ChatTemplate(ROOT / "serve/chat_template.jinja"))
        svc.constrained_tools = on
        with contextlib.redirect_stdout(io.StringIO()):
            evs = [x for kind, x in svc.run(tok.encode("hi"), thinking, [SHELL], 3000, dict(req or {}),
                                            threading.Event()) if kind == "event"]
        return [e.call.arguments for e in evs if e.kind == "tool_call"], eng

    def test_off_is_unchanged(self):
        calls, eng = self.run_reply(False)
        self.assertEqual(eng.keys, [""])
        self.assertEqual(len(calls), 1)
        self.assertIn("cmd", calls[0])                       # the malformed call as the model wrote it
        self.assertIsInstance(calls[0]["command"], str)

    def test_on_gives_a_valid_call(self):
        calls, eng = self.run_reply(True)
        self.assertTrue(eng.keys[0].startswith(" grammar="))
        self.assertEqual(len(calls), 1)
        args = calls[0]
        self.assertNotIn("cmd", args)
        self.assertIsInstance(args["command"], list)
        self.assertIsInstance(args["timeout_ms"], int)
        if jsonschema is not None:
            jsonschema.validate(args, SHELL["parameters"])

    def test_request_switch(self):
        calls, eng = self.run_reply(False, req={"constrained_tools": True})
        self.assertTrue(eng.keys[0].startswith(" grammar="))
        calls, eng = self.run_reply(True, req={"constrained_tools": False})
        self.assertEqual(eng.keys, [""])

    def test_engine_without_grammar(self):
        tok = ToolTokenizer()
        eng = MockEngine(tok, self.MALFORMED, max_context=1 << 16)          # no info["grammar"]
        svc = Service(eng, tok, ChatTemplate(ROOT / "serve/chat_template.jinja"))
        svc.constrained_tools = True
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertIsNone(svc.grammar_session([SHELL], {}, False))
        self.assertIn("does not support it", out.getvalue())

    def test_thinking_reply(self):
        script = "Let me think. <tool_call> is the tag.</think>\n\n" + self.MALFORMED
        calls, _ = self.run_reply(True, script=script, thinking=True)
        self.assertEqual(len(calls), 1)
        self.assertIsInstance(calls[0]["command"], list)


@unittest.skipUnless(HAVE_LLG and os.environ.get("STRATA_GRAMMAR_TOKENIZER"), "STRATA_GRAMMAR_TOKENIZER is not set")
class ModelTokenizer(ToolGrammar):
    """The same walks with the model's BPE tokenizer: its tokens cross the grammar's literals (`">\\n`, `"]\\n`)."""

    @classmethod
    def setUpClass(cls):
        import strata_tokenizer as ST
        tp = Path(os.environ["STRATA_GRAMMAR_TOKENIZER"])
        vocab = json.loads((tp / "vocab.json").read_text(encoding="utf-8"))
        tokens = [None] * len(vocab)
        for t, i in vocab.items():
            tokens[i] = t
        cls.tok = ST.Tokenizer(tokens, (tp / "merges.txt").read_text(encoding="utf-8").split("\n"),
                               json.loads((tp / "token_type.json").read_text()))
        super().setUpClass()


if __name__ == "__main__":
    unittest.main()
