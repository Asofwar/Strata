"""Grammar-constrained decoding (opt-in: the config's "constrained_tools" / "constrained_json", or the same keys in a
request).  A tool call's body and a response_format json_schema answer are generated under a token mask, so the call
cannot be malformed and cannot break its tool's parameter schema.

How it works (docs/DETAILS.md, "Constrained decoding"):

* The grammar is a Lark grammar for llguidance (pip package `llguidance`, imported only when the option is on).  A
  tool call is the chat template's own form after `<tool_call>`:

      \\n<function=NAME>\\n(<parameter=P>\\nVALUE\\n</parameter>\\n)*</function>\\n</tool_call>

  NAME is one of the request's tools, P one of that tool's declared parameters (each at most once, every required one
  present), VALUE raw text for a string parameter (the parser keeps it as written) and JSON that matches the
  parameter's own schema for any other type (the parser json-decodes it).
* The engine (GEN `grammar=<trigger ids>`) runs freely until it emits a trigger (`<tool_call>`, or `</think>` for a
  json_schema answer after thinking), cuts its window there and from then on writes `G <rows> <drafts>` before each
  verify window.  This module answers with one mask id per row (`G <id> ...`, defining new masks with `GD` lines
  first); row t's mask is the grammar's state after the window's drafts 1..t, so a draft the grammar forbids is never
  accepted (the masked target pick differs from it) and the MTP speculation keeps working.  `G off`: the
  constrained part is over, the engine runs freely again (and watches for the next trigger).
* The masks are computed while the GPU runs the window's forward pass, so they cost little time of their own.
"""
from __future__ import annotations

import json
import threading
import time

try:
    import numpy as np
except ImportError:          # the server itself needs numpy elsewhere; the encoder falls back to plain Python
    np = None

PARAM_END = "\n</parameter>\n"
SUBSET_MAX = 6               # parameters in any order up to this many; schema order (optional ones skippable) beyond
NAME_MAX = 128               # a free-form tool's parameter names (no declared properties)
_NON_STRING = {"integer", "number", "boolean", "array", "object", "null"}

_lock = threading.Lock()
_vocab_cache: dict = {}      # id(tokenizer) -> (tokenizer, LLTokenizer)


class Unavailable(RuntimeError):
    """llguidance is missing, or the grammar cannot be built: the request runs unconstrained."""


def _llg():
    try:
        import llguidance
    except ImportError as e:
        raise Unavailable("constrained decoding needs the llguidance package (pip install llguidance)") from e
    return llguidance


def vocabulary(tok, eos_ids):
    """The llguidance view of the server's tokenizer (built once per tokenizer: ~0.7 s for 248K tokens).  CONTROL
    tokens (`<|im_end|>`, ...) are special: grammar text never matches them; USER_DEFINED ones (`<tool_call>`,
    `</think>`) are plain text, as the parser reads them."""
    llg = _llg()
    with _lock:
        hit = _vocab_cache.get(id(tok))
        if hit is not None and hit[0] is tok:
            return hit[1]
        types = getattr(tok, "token_types", None) or []
        n = len(tok.tokens)
        tokens = []
        for i in range(n):
            try:
                tokens.append(tok.token_bytes(i))
            except (KeyError, IndexError):
                tokens.append(str(tok.tokens[i] or "").encode("utf-8"))
        w = llg.TokenizerWrapper.__new__(llg.TokenizerWrapper)
        w.eos_token_id = int(sorted(eos_ids)[0]) if eos_ids else 0
        w.bos_token_id = None
        w.tokens = tokens
        w.special_token_ids = [i for i, ty in enumerate(types) if ty == 3]
        w.is_tokenizer_wrapper = True
        w._gtokenizer = lambda b: tok.encode(b.decode("utf-8", "replace") if isinstance(b, bytes) else b)
        w._accepts_bytes = True
        lt = llg.LLTokenizer(w, n_vocab=n, eos_token=sorted(int(e) for e in eos_ids) or None)
        _vocab_cache[id(tok)] = (tok, lt)
        return lt


# ------------------------------------------------------------------------------------------------ grammar text
def _lit(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def _resolve(schema, root: dict, depth: int = 0):
    """A parameter schema that is only a local `$ref` (`#/$defs/X`, `#/definitions/X`) -> the schema it names."""
    while isinstance(schema, dict) and isinstance(schema.get("$ref"), str) and depth < 8:
        ref = schema["$ref"]
        if not ref.startswith("#/"):
            return schema
        node = root
        for part in ref[2:].split("/"):
            node = node.get(part.replace("~1", "/").replace("~0", "~")) if isinstance(node, dict) else None
        if not isinstance(node, dict):
            return schema
        schema, depth = node, depth + 1
    return schema


def _kind(schema) -> str:
    """How the parser reads a parameter's value: "string" (kept as written), "json" (json-decoded) or "any" (decoded
    when it parses, else kept as text - any text is a valid value).  serve/frontend.py parse_tool_call: only
    `"type": "string"` is kept raw; everything else is tried as JSON first."""
    if not isinstance(schema, dict):
        return "any"
    t = schema.get("type")
    if t == "string":
        return "string"
    if isinstance(t, str):
        return "json" if t in _NON_STRING else "any"
    if isinstance(t, list):
        if "string" in t:
            return "any"         # `["string", "null"]`: text that is not JSON stays text
        return "json" if t and all(x in _NON_STRING for x in t) else "any"
    for key in ("anyOf", "oneOf"):
        alts = schema.get(key)
        if isinstance(alts, list) and alts and all(_kind(a) == "json" for a in alts):
            return "json"
    return "any"


def _string_value(schema) -> str:
    """The grammar of a string parameter's raw text, up to and including the template's `\\n</parameter>\\n`."""
    vals = schema.get("enum") if isinstance(schema, dict) else None
    if isinstance(schema, dict) and "const" in schema:
        vals = [schema["const"]]
    if isinstance(vals, list) and vals and all(isinstance(v, str) and "\n</parameter>" not in v for v in vals):
        return "(" + " | ".join(_lit(v) for v in vals) + ") " + _lit(PARAM_END)
    return "textval"


# llguidance's JSON options for every embedded schema: keywords it does not implement are ignored rather than failing
# the grammar (the parser does not check them either), \uXXXX escapes of any printable character are allowed (a model
# writes Cyrillic either way), and a run of blank characters between two JSON tokens is bounded, so a model cannot
# loop on whitespace.
JSON_OPTIONS = {"lenient": True, "json_allow_general_unicode_escapes": True,
                "whitespace_pattern": r"[\x20\x0A\x0D\x09]{1,48}"}


def _json_schema_text(schema: dict) -> str:
    sub = {k: v for k, v in schema.items() if k not in ("description", "title", "examples", "default")}
    sub["x-guidance"] = {**JSON_OPTIONS, **(schema.get("x-guidance") or {})}
    return json.dumps(sub, ensure_ascii=False)


def _json_value(schema) -> str:
    return "%json " + _json_schema_text(schema) + " " + _lit(PARAM_END)


def _defs_root(params: dict) -> dict:
    """$defs / definitions of the tool's parameters object, copied into each parameter's own schema so a local
    `$ref` inside it still resolves."""
    out = {}
    for key in ("$defs", "definitions"):
        if isinstance(params.get(key), dict):
            out[key] = params[key]
    return out


def _tool_rules(idx: int, tool: dict, rules: list[str]) -> str:
    name = tool.get("name")
    params = tool.get("parameters") or tool.get("input_schema") or {}
    if not isinstance(params, dict):
        params = {}
    props = params.get("properties") if isinstance(params.get("properties"), dict) else {}
    required = [r for r in params.get("required") or [] if isinstance(r, str) and r in props]
    defs = _defs_root(params)
    pnames = list(props)
    for j, p in enumerate(pnames):
        schema = props[p] if isinstance(props[p], dict) else {}
        kind = _kind(_resolve(schema, params))
        if kind == "string":
            value = _string_value(_resolve(schema, params))
        elif kind == "json":
            value = _json_value({**defs, **schema} if defs else schema)
        else:
            value = "textval"
        rules.append(f"t{idx}_p{j}: {_lit('<parameter=' + p + '>' + chr(10))} {value}")
    end = _lit("</function>\n</tool_call>")
    body = f"t{idx}_body"
    if not pnames:
        # no declared properties: any parameter names, values as text (the parser decodes what parses as JSON)
        rules.append(f"{body}: freeparam* {end}")
        return f"{_lit(name + chr(62) + chr(10))} {body}"
    req = {pnames.index(r) for r in required}
    n = len(pnames)
    if n <= SUBSET_MAX:
        # any order, each at most once, all required ones: one rule per set of parameters still to write
        full = (1 << n) - 1
        seen = set()
        stack = [full]
        while stack:
            m = stack.pop()
            if m in seen:
                continue
            seen.add(m)
            alts = []
            for j in range(n):
                if m >> j & 1:
                    rest = m & ~(1 << j)
                    alts.append(f"t{idx}_p{j} t{idx}_s{rest}")
                    stack.append(rest)
            if not any(m >> j & 1 for j in req):
                alts.append(end)
            rules.append(f"t{idx}_s{m}: " + " | ".join(alts))
        rules.append(f"{body}: t{idx}_s{full}")
    else:
        parts = [f"t{idx}_p{j}" + ("" if j in req else "?") for j in range(n)]
        rules.append(f"{body}: {' '.join(parts)} {end}")
    return f"{_lit(name + chr(62) + chr(10))} {body}"


def tools_lark(tools: list[dict], opened: str = "") -> str:
    """The Lark grammar of one tool call's text after `<tool_call>` (`opened`: what of it is already written, for a
    forced call - `\\n<function=` or `\\n<function=NAME>\\n`)."""
    rules: list[str] = []
    alts = []
    for i, tool in enumerate(t for t in tools or [] if isinstance(t, dict) and isinstance(t.get("name"), str)
                                and t.get("name") and ">" not in t["name"] and "\n" not in t["name"]):
        alts.append(_tool_rules(i, tool, rules))
    if not alts:
        raise Unavailable("no tool to constrain")
    head = "\n<function="
    named = None
    if opened:
        if opened.startswith(head) and opened != head:
            named = opened[len(head):]
        elif opened != head:
            raise Unavailable("an opening the grammar does not know: " + opened[:40])
    if named is not None:
        body = [a.split(" ", 1)[1] for a in alts if a.split(" ", 1)[0] == _lit(named)]
        if not body:
            raise Unavailable("the forced call names no tool of the request")
        start = "start: " + body[0]
    elif opened:
        start = "start: (" + " | ".join(alts) + ")"
    else:
        start = "start: " + _lit(head) + " (" + " | ".join(alts) + ")"
    lines = [start] + rules + [
        # a string value: any text up to the first `\n</parameter>\n` (lazy: it ends there)
        r"textval[lazy]: /(?s:.*)\n<\/parameter>\n/",
        "freeparam: \"<parameter=\" PNAME \">\\n\" textval",
        f"PNAME: /[^>\\n<]{{1,{NAME_MAX}}}/",
    ]
    return "\n".join(lines) + "\n"


def json_lark(schema: dict) -> str:
    """The Lark grammar of a json_schema answer: up to a few blank characters, then the JSON value."""
    return "start: WS? %json " + _json_schema_text(schema) + "\nWS: /[ \\t\\r\\n]{1,8}/\n"


# ------------------------------------------------------------------------------------------------ the session
class Constraint:
    """One compiled grammar (llguidance's grammar text) and how it ends: `free_after` - the engine runs freely once it
    is complete (a tool call); otherwise the complete grammar allows only the end of the turn (a JSON answer)."""

    def __init__(self, vocab, lark: str, free_after: bool, label: str):
        llg = _llg()
        self.vocab = vocab
        self.grammar = llg.LLMatcher.grammar_from_lark(lark)
        is_err, msgs = llg.LLMatcher.validate_grammar_with_warnings(self.grammar, vocab)
        if is_err:
            raise Unavailable(f"the {label} grammar does not compile: {msgs[0] if msgs else '?'}")
        self.free_after = free_after
        self.label = label
        self.lark = lark

    def matcher(self):
        return _llg().LLMatcher(self.vocab, self.grammar, log_level=0)


def encode_mask(bm: bytes, n_vocab: int) -> str:
    """A mask's text for a GD line: `+ranges` (the allowed tokens) or `-ranges` (the banned ones), whichever is shorter;
    ranges are `a-b` or `a`, comma-separated.  Bit v (LSB first in byte v/8) set = token v allowed."""
    if np is not None:
        bits = np.unpackbits(np.frombuffer(bm, dtype=np.uint8), bitorder="little")[:n_vocab].astype(bool)
        allowed = int(bits.sum())
        sign = "+" if allowed <= n_vocab - allowed else "-"
        sel = bits if sign == "+" else ~bits
        edges = np.flatnonzero(np.diff(np.concatenate(([False], sel, [False])).astype(np.int8)))
        starts, ends = edges[0::2].tolist(), (edges[1::2] - 1).tolist()
    else:
        bits = [(bm[v >> 3] >> (v & 7)) & 1 for v in range(n_vocab)]
        allowed = sum(bits)
        sign = "+" if allowed <= n_vocab - allowed else "-"
        want = 1 if sign == "+" else 0
        starts, ends, v = [], [], 0
        while v < n_vocab:
            if bits[v] == want:
                s = v
                while v + 1 < n_vocab and bits[v + 1] == want:
                    v += 1
                starts.append(s)
                ends.append(v)
            v += 1
    return sign + ",".join(f"{a}" if a == b else f"{a}-{b}" for a, b in zip(starts, ends))


class GrammarSession:
    """One request's constraint state, shared by its engine passes.  `observe(token)` for every token of the reply
    (generated or written by the server), `answer(rows, drafts)` for the engine's G lines."""

    def __init__(self, n_vocab: int, triggers: dict[int, Constraint], gate: int | None = None,
                 start: Constraint | None = None, eos_ids=()):
        self.n_vocab = n_vocab
        self.eos = frozenset(int(e) for e in eos_ids)
        self.triggers = triggers          # token id -> the grammar that starts after it
        self.gate = gate                  # `</think>`: triggers count only after it (None: from the start)
        self.answering = gate is None
        self.c = None                     # the active constraint, or None (free)
        self.m = None
        self.masks: dict[bytes, int] = {}
        self.stats = {"calls": 0, "completed": 0, "errors": 0, "windows": 0, "rows": 0, "masks": 0, "ms": 0.0,
                      "ms_max": 0.0, "off": 0}
        self.error = None
        if start is not None:
            self._activate(start)

    # -- protocol
    def engine_key(self) -> str:
        """The GEN key: the trigger ids, with -1 first when the pass starts constrained.  A new engine pass starts with
        no masks defined (the engine keeps them per request), so they are defined again."""
        self.masks.clear()
        ids = ["-1"] if self.m is not None else []
        ids += [str(t) for t in sorted(self.triggers)]
        return " grammar=" + ",".join(ids) if ids else ""

    def _activate(self, c: Constraint):
        self.c, self.m = c, c.matcher()
        self.stats["calls"] += 1

    def observe(self, tok: int) -> None:
        if self.m is None:
            if self.gate is not None and tok == self.gate:
                self.answering = True
                c = self.triggers.get(tok)        # a json answer starts right after `</think>`
                if c is not None:
                    self._activate(c)
                return
            c = self.triggers.get(tok)
            if c is not None and self.answering:
                self._activate(c)
            return
        if not self.m.consume_token(int(tok)):
            # a token outside the mask: a row the engine did not constrain, or an engine without the masks
            self.stats["errors"] += 1
            self.error = self.m.get_error() or f"token {tok} is outside the grammar"
            self.c = self.m = None
            return
        if self.c.free_after and (self.m.is_accepting() or self.m.is_stopped()):
            self.stats["completed"] += 1
            self.c = self.m = None

    def _mask_id(self, bm: bytes, out: list[str]) -> int:
        mid = self.masks.get(bm)
        if mid is None:
            mid = self.masks[bm] = len(self.masks) + 1
            out.append(f"GD {mid} {self.n_vocab} {encode_mask(bm, self.n_vocab)}\n")
            self.stats["masks"] += 1
        return mid

    def answer(self, rows: int, drafts: list[int]) -> str:
        """The reply to `G <rows> <drafts>`: the GD lines of new masks, then `G <id> x rows` (0 = unconstrained)."""
        t0 = time.perf_counter()
        if self.m is None:
            self.stats["off"] += 1
            return "G off\n"
        out: list[str] = []
        ids: list[int] = []
        m, k = self.m, 0
        for r in range(rows):
            if self.c.free_after and k and (m.is_accepting() or m.is_stopped()):
                ids.extend([0] * (rows - r))      # the call ends at a draft: the rows after it are free
                break
            bm = m.compute_bitmask()
            ids.append(self._mask_id(bm, out))
            if r + 1 < rows:
                d = int(drafts[r]) if r < len(drafts) else -1
                if d in self.eos:                  # the turn ends at this draft: nothing after it is used (and an
                    ids.extend([0] * (rows - 1 - r))   # accepted end-of-turn is not counted by rollback)
                    break
                if 0 <= d < self.n_vocab and (bm[d >> 3] >> (d & 7)) & 1 and m.consume_token(d):
                    k += 1
                else:                              # the draft is not allowed: it is rejected, the rows after it unused
                    ids.extend([0] * (rows - 1 - r))
                    break
        if k:
            m.rollback(k)
        out.append("G " + " ".join(str(i) for i in ids) + "\n")
        ms = (time.perf_counter() - t0) * 1e3
        st = self.stats
        st["windows"] += 1
        st["rows"] += rows
        st["ms"] += ms
        st["ms_max"] = max(st["ms_max"], ms)
        return "".join(out)

    def summary(self) -> str:
        s = self.stats
        w = max(1, s["windows"])
        return (f"constrained: {s['calls']} part(s), {s['completed']} complete, {s['windows']} windows "
                f"({s['rows'] / w:.2f} rows), {s['masks']} masks, {s['ms'] / w:.2f} ms/window (max {s['ms_max']:.1f})"
                + (f", {s['errors']} token(s) outside the grammar ({self.error})" if s["errors"] else ""))


def build_session(tok, eos_ids, tools=None, json_schema=None, thinking=False, force=None, think_end=None,
                  tool_call_id=None, cache=None) -> GrammarSession:
    """The constraint of one request.  `force`: the forced call's opening the prompt ends with (no thinking) - the
    grammar starts inside it.  `cache`: a dict the caller keeps (grammar text -> Constraint), so a client that sends
    the same tools on every turn compiles them once."""
    vocab = vocabulary(tok, eos_ids)
    n_vocab = len(tok.tokens)

    def compiled(lark, free_after, label):
        key = (lark, free_after)
        if cache is not None and key in cache:
            return cache[key]
        c = Constraint(vocab, lark, free_after, label)
        if cache is not None:
            if len(cache) >= 32:
                cache.pop(next(iter(cache)))
            cache[key] = c
        return c

    triggers: dict[int, Constraint] = {}
    start = None
    if tools:
        if tool_call_id is None:
            raise Unavailable("the tokenizer has no <tool_call> token")
        triggers[tool_call_id] = compiled(tools_lark(tools), True, "tool call")
        if force:
            if not force.startswith("<tool_call>"):
                raise Unavailable("a forced opening the grammar does not know")
            start = compiled(tools_lark(tools, opened=force[len("<tool_call>"):]), True, "forced tool call")
    if json_schema is not None:
        c = compiled(json_lark(json_schema), False, "json_schema")
        if thinking:
            if think_end is None:
                raise Unavailable("the tokenizer has no </think> token")
            triggers[think_end] = c
        else:
            start = c
    return GrammarSession(n_vocab, triggers, gate=think_end if thinking else None, start=start, eos_ids=eos_ids)
