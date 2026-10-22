"""bench/agent-ru/run_agent.py - a multi-turn agentic coding benchmark through a running Strata server.

The model gets a task in a small sandbox repository and works on it with OpenAI-format tools (list_dir, read_file,
write_file, edit_file, search, run_tests, run_command, finish) for at most --max-turns requests.  Then the original
visible tests are put back (an agent may not pass by editing them), the hidden tests are added, and the run passes
when both suites pass.  The conversation goes to /v1/chat/completions as Codex sends it: the whole history every
turn, with the reasoning of earlier turns returned in reasoning_content (the server's preserve_thinking decides
whether the template keeps it).

    python bench/agent-ru/run_agent.py --tag tiel --runs 3
    python bench/agent-ru/run_agent.py --tag tiel-effort-low --runs 2 --reasoning-effort low
    python bench/agent-ru/run_agent.py --tag tiel-nopreserve --preserve-thinking off
    python bench/agent-ru/score.py tiel ornith kat

One JSON line per run goes to results/<tag>.jsonl and the whole conversation to results/transcripts/<tag>/ (not
in git).  A rerun skips the runs already there; --budget-min stops starting runs after that many minutes, so a
config can be measured in several server windows.  Each run's requests carry seed = 1 + run index (the server's
sampler takes a per-request seed; speculative decoding still makes text depend on timing, hence several runs).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "tools"))

import tasks_js  # noqa: E402
import tasks_py  # noqa: E402

TASKS = tasks_py.TASKS + tasks_js.TASKS
OUT_LIMIT = 8000            # characters of a tool result the model sees
CMD_TIMEOUT = 60
TEST_TIMEOUT = 120

SYSTEM = """You are a coding agent. You work in a git-less repository on the user's machine through the tools \
you are given; paths are relative to the repository root. Look at the code before you change it, make the \
smallest change that does the task, and run the tests to check your work. Do not change the existing tests unless \
the task asks for it. When the task is done, call `finish` with a one-line summary. Answer in the language of the \
task."""

TOOLS = [
    {"type": "function", "function": {
        "name": "list_dir", "description": "List the files and directories under a directory (recursively, up to "
                                           "200 entries).",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "directory, relative to the repository root; '.' for the root"}},
            "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "read_file", "description": "Read a text file. Lines are numbered in the output.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"},
            "start_line": {"type": "integer", "description": "first line to show (1-based), optional"},
            "end_line": {"type": "integer", "description": "last line to show, optional"}},
            "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "write_file", "description": "Create or overwrite a file with the given content.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {
        "name": "edit_file", "description": "Replace an exact piece of text in a file. old_text must occur exactly "
                                            "once in the file (include surrounding lines to make it unique).",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}},
            "required": ["path", "old_text", "new_text"]}}},
    {"type": "function", "function": {
        "name": "search", "description": "Search the repository's text files for a regular expression; returns "
                                         "matching lines as path:line: text.",
        "parameters": {"type": "object", "properties": {
            "pattern": {"type": "string"}, "path": {"type": "string", "description": "directory, default '.'"}},
            "required": ["pattern"]}}},
    {"type": "function", "function": {
        "name": "run_tests", "description": "Run the repository's test suite and return its output and exit code.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "run_command", "description": "Run a command in the repository root (no shell: pipes and "
                                              "redirections do not work). Allowed programs: python, node. Timeout "
                                              "60 s.",
        "parameters": {"type": "object", "properties": {
            "command": {"type": "string", "description": "for example: python wordcount.py notes.txt --top 3"}},
            "required": ["command"]}}},
    {"type": "function", "function": {
        "name": "finish", "description": "Say that the task is done.",
        "parameters": {"type": "object", "properties": {"summary": {"type": "string"}}, "required": ["summary"]}}},
]
REQUIRED = {t["function"]["name"]: t["function"]["parameters"].get("required", []) for t in TOOLS}


def test_cmd(lang, where):
    if lang == "python":
        return [sys.executable, "-m", "unittest", "discover", "-s", where, "-v"]
    ext = "mjs" if lang == "js" else "ts"
    return ["node", "--test", f"{where}/*.test.{ext}"]


def proc_env():
    env = {k: v for k, v in os.environ.items() if not k.startswith(("STRATA", "PYTHON"))}
    env.update(PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1", NODE_NO_WARNINGS="1")
    return env


def run_proc(cmd, cwd, timeout):
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, timeout=timeout, env=proc_env(),
                           encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return 124, f"timeout after {timeout} s"
    except OSError as e:
        return 127, f"cannot run {cmd[0]}: {e}"
    return p.returncode, (p.stdout + ("\n" if p.stdout and p.stderr else "") + p.stderr)


def clip(text, limit=OUT_LIMIT):
    if len(text) <= limit:
        return text
    half = limit // 2
    return text[:half] + f"\n... [{len(text) - limit} characters cut] ...\n" + text[-half:]


def write_tree(root: Path, files: dict):
    for rel, content in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8", newline="\n")


class Sandbox:
    def __init__(self, root: Path, lang: str):
        self.root = root.resolve()
        self.lang = lang

    def path(self, rel):
        if not isinstance(rel, str) or not rel.strip():
            raise ValueError("path must be a non-empty string")
        p = (self.root / rel.strip()).resolve()
        if p != self.root and self.root not in p.parents:
            raise ValueError(f"path {rel!r} is outside the repository")
        return p

    def rel(self, p: Path):
        return p.relative_to(self.root).as_posix()

    def list_dir(self, path="."):
        base = self.path(path)
        if not base.is_dir():
            raise ValueError(f"{path} is not a directory")
        out = []
        for p in sorted(base.rglob("*")):
            if any(part in ("__pycache__", "node_modules", ".git") for part in p.parts):
                continue
            out.append(self.rel(p) + ("/" if p.is_dir() else f"  ({p.stat().st_size} bytes)"))
            if len(out) >= 200:
                out.append("... (more entries not shown)")
                break
        return "\n".join(out) or "(empty)"

    def read_file(self, path, start_line=None, end_line=None):
        p = self.path(path)
        if not p.is_file():
            raise ValueError(f"no such file: {path}")
        lines = p.read_text(encoding="utf-8", errors="replace").split("\n")
        a = max(1, int(start_line or 1))
        b = min(len(lines), int(end_line or len(lines)))
        return "\n".join(f"{i:4}| {lines[i - 1]}" for i in range(a, b + 1)) or "(empty file)"

    def write_file(self, path, content):
        if not isinstance(content, str):
            raise ValueError("content must be a string")
        p = self.path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8", newline="\n")
        return f"wrote {self.rel(p)} ({len(content)} characters)"

    def edit_file(self, path, old_text, new_text):
        p = self.path(path)
        if not p.is_file():
            raise ValueError(f"no such file: {path}")
        text = p.read_text(encoding="utf-8")
        n = text.count(old_text) if old_text else 0
        if n != 1:
            raise ValueError(f"old_text occurs {n} times in {path}; it must occur exactly once")
        p.write_text(text.replace(old_text, new_text), encoding="utf-8", newline="\n")
        return f"edited {self.rel(p)}"

    def search(self, pattern, path="."):
        rx = re.compile(pattern)
        base = self.path(path)
        hits = []
        for p in sorted(base.rglob("*")):
            if not p.is_file() or "__pycache__" in p.parts:
                continue
            try:
                text = p.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for i, line in enumerate(text.split("\n"), 1):
                if rx.search(line):
                    hits.append(f"{self.rel(p)}:{i}: {line}")
        return "\n".join(hits[:200]) or "no matches"

    def run_tests(self):
        code, out = run_proc(test_cmd(self.lang, "tests"), self.root, TEST_TIMEOUT)
        return f"exit code {code}\n{out}"

    def run_command(self, command):
        try:
            argv = shlex.split(command, posix=True)
        except ValueError as e:
            raise ValueError(f"cannot parse the command: {e}")
        if not argv:
            raise ValueError("empty command")
        prog = Path(argv[0]).name.lower().removesuffix(".exe")
        if prog in ("python", "python3", "py"):
            argv[0] = sys.executable
        elif prog == "node":
            argv[0] = "node"
        else:
            raise ValueError(f"program {argv[0]!r} is not allowed (only python and node)")
        if any(x.lower() in ("pip", "pip3", "ensurepip", "venv") for x in argv[1:3]):
            raise ValueError("installing packages is not allowed here: use the standard library")
        code, out = run_proc(argv, self.root, CMD_TIMEOUT)
        return f"exit code {code}\n{out}"


def http(url, body=None, timeout=3600.0):
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def metrics_entry(url, out):
    """This request's entry of GET /metrics (newest first), matched by its output and prompt token counts."""
    usage = out.get("usage") or {}
    try:
        for e in (http(url.rstrip("/") + "/metrics", timeout=30).get("requests") or [])[:4]:
            if e.get("output_tokens") == usage.get("completion_tokens") and \
                    e.get("prompt_total", e.get("prompt_tokens")) == usage.get("prompt_tokens"):
                return e
    except (OSError, ValueError):
        pass
    return {}


TEXT_CALL = re.compile(r"<tool_call>|<function=|\"name\"\s*:\s*\"(" + "|".join(REQUIRED) + r")\"")


def call_tool(sb: Sandbox, name, args):
    """-> (result text, malformed reason or None, finished)"""
    if name not in REQUIRED:
        return f"error: unknown tool {name!r}", "unknown tool", False
    if not isinstance(args, dict):
        return "error: the arguments must be a JSON object", "arguments not an object", False
    missing = [k for k in REQUIRED[name] if k not in args]
    if missing:
        return f"error: missing argument(s) {', '.join(missing)}", "missing argument", False
    if name == "finish":
        return "ok", None, True
    try:
        return clip(getattr(sb, name)(**args)), None, False
    except TypeError as e:
        return f"error: {e}", "bad argument", False
    except (ValueError, OSError, re.error) as e:
        return f"error: {e}", None, False


def score_run(sb_root: Path, t: dict):
    """Restore the original visible tests, add the hidden ones, run both."""
    for rel, content in t["files"].items():
        if rel.startswith("tests/"):
            write_tree(sb_root, {rel: content})
    write_tree(sb_root, t["hidden"])
    shutil.rmtree(sb_root / "node_modules", ignore_errors=True)
    v_code, v_out = run_proc(test_cmd(t["lang"], "tests"), sb_root, TEST_TIMEOUT)
    h_code, h_out = run_proc(test_cmd(t["lang"], "_hidden"), sb_root, TEST_TIMEOUT)
    why = ""
    if v_code or h_code:
        bad = h_out if h_code else v_out
        lines = [x for x in bad.splitlines() if re.search(r"(Error|FAIL|not ok|assert|Exception)", x)]
        why = ("hidden: " if h_code else "visible: ") + " | ".join(lines[:3])[:300]
    return v_code == 0 and h_code == 0, v_code, h_code, why


def run_one(a, t, run_idx, tok, sandbox_root: Path):
    sb_root = sandbox_root / f"{t['id']}-{run_idx}"
    shutil.rmtree(sb_root, ignore_errors=True)
    sb_root.mkdir(parents=True)
    write_tree(sb_root, t["files"])
    sb = Sandbox(sb_root, t["lang"])
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": t["prompt"]}]
    stats = {"turns": 0, "completion_tokens": 0, "reasoning_tokens": 0, "max_prompt_tokens": 0, "tool_calls": 0,
             "malformed": 0, "malformed_kinds": {}, "text_tool_calls": 0, "recoveries": 0, "length_cuts": 0,
             "repeat_calls": 0, "tests_runs": 0, "finished": False, "ended": None, "request_s": 0.0,
             "prompt_ms": 0.0, "reused_tokens": 0, "errors": []}
    last_sig, same_n = None, 0
    t0 = time.time()
    while stats["turns"] < a.max_turns:
        body = {"model": "strata", "messages": messages, "tools": TOOLS, "max_tokens": a.max_tokens,
                "stream": False, "seed": run_idx + 1}
        if a.reasoning_effort is not None:
            body["reasoning_effort"] = a.reasoning_effort     # False: thinking off
        if a.reasoning_budget is not None:
            body["reasoning_budget_tokens"] = a.reasoning_budget
        if a.preserve_thinking != "default":
            body["chat_template_kwargs"] = {"preserve_thinking": a.preserve_thinking == "on"}
        rt = time.time()
        try:
            out = http(a.url.rstrip("/") + "/v1/chat/completions", body, timeout=a.request_timeout)
        except urllib.error.HTTPError as e:
            msg = e.read().decode("utf-8", "replace")[:300]
            stats["errors"].append(f"HTTP {e.code}: {msg}")
            stats["ended"] = "http-error"
            break
        except (OSError, ValueError) as e:
            stats["errors"].append(str(e)[:300])
            stats["ended"] = "request-failed"
            break
        stats["request_s"] += time.time() - rt
        stats["turns"] += 1
        usage = out.get("usage") or {}
        stats["completion_tokens"] += usage.get("completion_tokens") or 0
        stats["max_prompt_tokens"] = max(stats["max_prompt_tokens"], usage.get("prompt_tokens") or 0)
        m = metrics_entry(a.url, out)
        stats["recoveries"] += m.get("reasoning_recoveries") or 0
        stats["prompt_ms"] += m.get("prompt_ms") or 0
        stats["reused_tokens"] += m.get("reused") or 0
        ch = out["choices"][0]
        msg = ch["message"]
        if ch.get("finish_reason") == "length":
            stats["length_cuts"] += 1
        reasoning = msg.get("reasoning_content") or ""
        if reasoning:
            stats["reasoning_tokens"] += len(tok.encode(reasoning)) if tok else len(reasoning) // 4
        content = msg.get("content") or ""
        calls = msg.get("tool_calls") or []
        amsg = {"role": "assistant", "content": content}
        if reasoning:
            amsg["reasoning_content"] = reasoning
        if calls:
            amsg["tool_calls"] = [{"id": c.get("id") or f"call_{stats['turns']}_{i}", "type": "function",
                                   "function": {"name": c["function"]["name"],
                                                "arguments": c["function"].get("arguments") or "{}"}}
                                  for i, c in enumerate(calls)]
        messages.append(amsg)
        if not calls:
            if TEXT_CALL.search(content):
                stats["text_tool_calls"] += 1
                stats["malformed"] += 1
                stats["malformed_kinds"]["tool call in text"] = stats["malformed_kinds"].get("tool call in text", 0) + 1
                messages.append({"role": "user", "content": "Your tool call was not recognized: call tools through "
                                                            "the tool-calling interface."})
                continue
            stats["ended"] = "no-tool-call" if ch.get("finish_reason") != "length" else "length"
            break
        done = False
        for c in amsg["tool_calls"]:
            stats["tool_calls"] += 1
            name, raw = c["function"]["name"], c["function"]["arguments"]
            try:
                args = json.loads(raw) if isinstance(raw, str) else raw
            except ValueError:
                args = None
                res, bad, fin = f"error: the arguments are not valid JSON: {raw[:200]}", "invalid JSON", False
            if args is not None or not isinstance(raw, str):
                res, bad, fin = call_tool(sb, name, args)
            if bad:
                stats["malformed"] += 1
                stats["malformed_kinds"][bad] = stats["malformed_kinds"].get(bad, 0) + 1
            if name == "run_tests":
                stats["tests_runs"] += 1
            sig = (name, raw)
            same_n = same_n + 1 if sig == last_sig else 1
            last_sig = sig
            if same_n == 3:
                stats["repeat_calls"] += 1
            messages.append({"role": "tool", "tool_call_id": c["id"], "content": res})
            done = done or fin
        if done:
            stats["finished"] = True
            stats["ended"] = "finish"
            break
    else:
        stats["ended"] = "max-turns"
    wall = time.time() - t0
    ok, v_code, h_code, why = score_run(sb_root, t)
    rec = {"task": t["id"], "lang": t["lang"], "kind": t["kind"], "ru": t["ru"], "run": run_idx, "pass": ok,
           "visible_exit": v_code, "hidden_exit": h_code, "why": why, "wall_s": round(wall, 1), **stats,
           "request_s": round(stats["request_s"], 1), "prompt_ms": round(stats["prompt_ms"])}
    tdir = HERE / "results" / "transcripts" / a.tag
    tdir.mkdir(parents=True, exist_ok=True)
    (tdir / f"{t['id']}-{run_idx}.json").write_text(json.dumps({"record": rec, "messages": messages},
                                                               ensure_ascii=False, indent=1), encoding="utf-8")
    if not a.keep_sandbox:
        shutil.rmtree(sb_root, ignore_errors=True)
    return rec


def load_tokenizer(path: Path):
    try:
        import strata_tokenizer as ST
        vocab = json.loads((path / "vocab.json").read_text(encoding="utf-8"))
        tokens = [None] * len(vocab)
        for t, i in vocab.items():
            tokens[i] = t
        merges = (path / "merges.txt").read_text(encoding="utf-8").split("\n")
        types = json.loads((path / "token_type.json").read_text())
        return ST.Tokenizer(tokens, merges, types)
    except (OSError, ImportError, ValueError) as e:
        print(f"no tokenizer ({e}): reasoning tokens estimated as characters / 4", flush=True)
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--url", default="http://127.0.0.1:8096")
    ap.add_argument("--tag", required=True, help="results/<tag>.jsonl")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--tasks", default="", help="comma-separated task ids (default: all)")
    ap.add_argument("--max-turns", type=int, default=25)
    ap.add_argument("--max-tokens", type=int, default=16384, help="per request")
    ap.add_argument("--reasoning-effort", choices=["none", "low", "medium", "high"], default=None)
    ap.add_argument("--reasoning-budget", type=int, default=None, help="reasoning_budget_tokens of every request")
    ap.add_argument("--preserve-thinking", choices=["default", "on", "off"], default="default")
    ap.add_argument("--request-timeout", type=float, default=900, help="seconds; a request over it ends the bench")
    ap.add_argument("--budget-min", type=float, default=0, help="stop starting runs after this many minutes")
    ap.add_argument("--run-order", choices=["run-major", "task-major"], default="run-major",
                    help="run-major: run 0 of every task, then run 1, ... (a cut-short window still covers all tasks)")
    ap.add_argument("--sandbox", default=str(Path(tempfile.gettempdir()) / "strata-agent-bench"))
    ap.add_argument("--keep-sandbox", action="store_true")
    ap.add_argument("--tokenizer", default=r"D:\Strata-data\packs\cyber-tiel-iq4_xs\tokenizer")
    a = ap.parse_args()
    if a.reasoning_effort == "none":
        a.reasoning_effort = False                    # the server's "thinking off"
    tasks = TASKS
    if a.tasks:
        want = a.tasks.split(",")
        tasks = [t for t in TASKS if t["id"] in want]
    out_path = HERE / "results" / f"{a.tag}.jsonl"
    out_path.parent.mkdir(exist_ok=True)
    done = set()
    if out_path.exists():
        for line in out_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                done.add((r["task"], r["run"]))
    jobs = [(t, r) for r in range(a.runs) for t in tasks] if a.run_order == "run-major" else \
        [(t, r) for t in tasks for r in range(a.runs)]
    tok = load_tokenizer(Path(a.tokenizer))
    sandbox_root = Path(a.sandbox) / a.tag
    t_start = time.time()
    for t, r in jobs:
        if (t["id"], r) in done:
            continue
        if a.budget_min and time.time() - t_start > a.budget_min * 60:
            print(f"budget of {a.budget_min} min reached; rerun to continue", flush=True)
            return 2
        rec = run_one(a, t, r, tok, sandbox_root)
        if rec["ended"] in ("http-error", "request-failed"):
            # the server's fault, not the model's: not recorded, so a rerun repeats this run
            print(f"{t['id']} #{r}: the server failed after {rec['turns']} turns; stopping", rec["errors"], flush=True)
            return 1
        rec["config"] = {"reasoning_effort": a.reasoning_effort, "reasoning_budget": a.reasoning_budget,
                         "preserve_thinking": a.preserve_thinking, "max_turns": a.max_turns}
        with out_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"{t['id']:22} #{r} {'PASS' if rec['pass'] else 'FAIL'} turns {rec['turns']:2} {rec['wall_s']:6.1f}s "
              f"think {rec['reasoning_tokens']:6} bad {rec['malformed']} rec {rec['recoveries']} "
              f"ctx {rec['max_prompt_tokens']:6} end {rec['ended']} {rec['why'][:80]}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
