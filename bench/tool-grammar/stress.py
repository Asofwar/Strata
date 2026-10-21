"""bench/tool-grammar/stress.py - 50 tool calls with nasty arguments, through a running Strata server (OpenAI chat API).

For constrained decoding (serve/grammar.py, docs/DETAILS.md "Constrained decoding"): the same prompts with the
request's "constrained_tools" off and on.  Each prompt asks for exactly one call whose arguments hold text that is hard
to write inside a tool call: quotes, backslashes, newlines and tabs, Cyrillic, CJK and emoji, JSON inside a string,
the template's own tags, SQL quoting, long code.

    python bench/tool-grammar/stress.py --tag off --body '{"constrained_tools": false}' \\
        --pair on '{"constrained_tools": true}'
    python bench/tool-grammar/stress.py --report off on

A reply is MALFORMED when it has no call to the asked tool, its arguments are not a JSON object, or they break the
tool's schema (missing or unknown parameters, a wrong type, a value outside an enum or a range).  A well-formed call
whose payload differs from the one asked for is counted apart (FIDELITY): the grammar cannot fix that.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent

try:
    import jsonschema
except ImportError:
    jsonschema = None


def fn(name, desc, props, required, extra=None):
    params = {"type": "object", "properties": props, "required": required, "additionalProperties": False}
    params.update(extra or {})
    return {"type": "function", "function": {"name": name, "description": desc, "parameters": params}}


SHELL = fn("shell", "Run a command. `command` is the argv list (e.g. [\"bash\", \"-lc\", \"ls -la\"]).", {
    "command": {"type": "array", "items": {"type": "string"}, "minItems": 1},
    "workdir": {"type": "string", "description": "Working directory"},
    "timeout_ms": {"type": "integer", "minimum": 1}}, ["command"])
WRITE = fn("write_file", "Create or overwrite a text file with exactly this content.", {
    "path": {"type": "string"}, "content": {"type": "string"}}, ["path", "content"])
PATCH = fn("apply_patch", "Apply a patch in the *** Begin Patch / *** End Patch format.", {
    "input": {"type": "string", "description": "The whole patch text"}}, ["input"])
PLAN = fn("update_plan", "Replace the task plan.", {
    "explanation": {"type": "string"},
    "plan": {"type": "array", "minItems": 1, "items": {"type": "object", "properties": {
        "step": {"type": "string"}, "status": {"type": "string", "enum": ["pending", "in_progress", "completed"]}},
        "required": ["step", "status"], "additionalProperties": False}}}, ["plan"])
HTTP = fn("http_request", "Send an HTTP request.", {
    "method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE"]},
    "url": {"type": "string"},
    "headers": {"type": "object", "additionalProperties": {"type": "string"}},
    "body": {"type": "string", "description": "The raw request body"},
    "timeout_s": {"type": "number", "minimum": 0}}, ["method", "url"])
ISSUE = fn("create_issue", "Open an issue in the tracker.", {
    "title": {"type": "string"}, "body": {"type": "string"},
    "labels": {"type": "array", "items": {"type": "string"}},
    "priority": {"type": "integer", "minimum": 1, "maximum": 5}}, ["title", "priority"])
SQL = fn("run_sql", "Run one SQL statement with bound parameters.", {
    "query": {"type": "string"},
    "params": {"type": "array", "items": {"type": ["string", "number", "null"]}}}, ["query"])
TOOLS = [SHELL, WRITE, PATCH, PLAN, HTTP, ISSUE, SQL]
SCHEMAS = {t["function"]["name"]: t["function"]["parameters"] for t in TOOLS}

SYSTEM = ("You are a coding agent working in the user's workspace. Do what the user asks with exactly one tool call. "
          "Pass text arguments exactly as given, character for character.")

LONG_CODE = "\n".join([
    "import json, re, sys",
    "",
    "PATTERN = re.compile(r'^(?P<key>[\\w.-]+)\\s*=\\s*\"(?P<val>(?:[^\"\\\\]|\\\\.)*)\"$')",
    "",
    "def parse(text: str) -> dict:",
    "    \"\"\"key = \"value\" lines -> dict; '#' starts a comment.\"\"\"",
    "    out = {}",
    "    for n, line in enumerate(text.splitlines(), 1):",
    "        line = line.split('#', 1)[0].strip()",
    "        if not line:",
    "            continue",
    "        m = PATTERN.match(line)",
    "        if m is None:",
    "            raise ValueError(f\"line {n}: cannot read {line!r}\")",
    "        out[m['key']] = bytes(m['val'], 'utf-8').decode('unicode_escape')",
    "    return out",
    "",
    "",
    "def main(argv):",
    "    data = parse(open(argv[1], encoding='utf-8').read())",
    "    print(json.dumps(data, ensure_ascii=False, indent=2))",
    "    print('ключей:', len(data), '\\t(готово)')",
    "    return 0",
    "",
    "",
    "if __name__ == '__main__':",
    "    sys.exit(main(sys.argv))",
])

TEXTS = [
    'Он сказал: "Привет, мир!" — и ушёл.',
    'C:\\Users\\Иван Петров\\Documents\\отчёт "final".docx',
    "line1\nline2\n\ttabbed line\n",
    "it's a \"quoted\" `backtick` $HOME %PATH% and a literal \\n here",
    '{"key": "value", "nested": {"a": [1, 2, 3], "s": "x\\"y"}}',
    "Docs say: close every value with </parameter> and wrap calls in <tool_call>.",
    "日本語テキスト 🚀 ✓ — смешанный текст with English",
    "SELECT * FROM \"users\" WHERE name = 'O''Brien' AND note LIKE '%\"x\"%';",
    "C:\\new\\table\\x41\\u0041 \\\\server\\share",
    "Таблица:\n| a | b |\n|---|---|\n| \"1\" | 'два' |\n",
]


def items():
    out = []
    # write_file: every text, then the long code (12)
    for i, t in enumerate(TEXTS):
        out.append({"id": f"write-{i}", "tool": "write_file",
                    "prompt": f"Create the file notes/n{i}.txt whose content is exactly the text between the markers "
                              f"(without the markers):\n<<<BEGIN>>>\n{t}\n<<<END>>>",
                    "expect": ("content", t)})
    out.append({"id": "write-code", "tool": "write_file",
                "prompt": "Save this program as tools/kv_parse.py, unchanged:\n```python\n" + LONG_CODE + "\n```",
                "expect": ("content", LONG_CODE)})
    out.append({"id": "write-json", "tool": "write_file",
                "prompt": "Запиши в config/app.json такой JSON (с отступом 2 пробела):\n"
                          '{"name": "Strata \\"dev\\"", "paths": ["C:\\\\data", "/tmp/x y"], "ru": "привет"}',
                "expect": ("content~", "Strata")})
    # shell (10)
    shells = [
        ("echo-quotes", "Run: echo \"He said \\\"hi\\\" & left\" > out.txt  (in bash)", "He said"),
        ("grep-regex", "Search the src folder for lines matching the regex  \"[A-Z_]+\\s*=\\s*'[^']*'\"  with grep -rnE.",
         "grep"),
        ("py-inline", "Run python with -c and this code: import json; print(json.dumps({\"a\": \"б\\n\"}))", "json.dumps"),
        ("heredoc", "Using bash -lc, create hello.sh with a heredoc that contains the two lines\n"
                    "echo \"Привет, $USER\"\necho 'done'\nand make it executable.", "Привет"),
        ("workdir-cyr", "List all files, including hidden ones, in the folder  D:\\Проекты\\Мой \"тест\"  "
                        "(set it as the working directory).", "ls"),
        ("timeout", "Run the tests with `pytest -q -k \"not slow\"` and a timeout of 120000 ms.", "pytest"),
        ("pipes", "Run in bash: cat data.csv | awk -F',' '{print $2}' | sort | uniq -c | sort -rn | head", "awk"),
        ("git-commit", "Commit everything with git and the message:\nfix: handle \"quoted\" names\n\n"
                       "Long body with ru: исправлено", "commit"),
        ("powershell", "Run in PowerShell: Get-ChildItem -Recurse -Filter '*.log' | "
                       "Where-Object { $_.Length -gt 1MB } | Remove-Item -WhatIf", "Get-ChildItem"),
        ("find-exec", "Run: find . -name '*.tmp' -exec rm -f {} \\;", "find"),
    ]
    for sid, prompt, frag in shells:
        out.append({"id": f"shell-{sid}", "tool": "shell", "prompt": prompt, "expect": ("command~", frag)})
    # apply_patch (6)
    patches = [
        "*** Begin Patch\n*** Update File: src/app.py\n@@ def greet(name):\n-    return 'Hello ' + name\n"
        "+    return f\"Привет, {name}! \\\"quoted\\\"\"\n*** End Patch",
        "*** Begin Patch\n*** Add File: docs/ЗАМЕТКИ.md\n+# Заметки\n+\n+- пункт \"1\"\n+- path C:\\tmp\\x\n*** End Patch",
        "*** Begin Patch\n*** Update File: a.json\n@@\n-  \"debug\": false,\n+  \"debug\": true,\n*** End Patch",
        "*** Begin Patch\n*** Update File: t.sh\n@@\n-echo $1\n+echo \"${1:-default}\" | sed 's/\\t/ /g'\n*** End Patch",
        "*** Begin Patch\n*** Update File: x.html\n@@\n-<p>old</p>\n+<p class=\"new\">&lt;tag&gt; </parameter></p>\n"
        "*** End Patch",
        "*** Begin Patch\n*** Delete File: old/legacy.py\n*** End Patch",
    ]
    for i, pt in enumerate(patches):
        out.append({"id": f"patch-{i}", "tool": "apply_patch",
                    "prompt": "Apply exactly this patch:\n" + pt, "expect": ("input", pt)})
    # update_plan (5)
    plans = [
        ["Прочитать «README.md»", "Исправить баг в \"parser\"", "Запустить тесты"],
        ["Find the `TODO` items", "Rewrite C:\\build\\run.bat", "Ship it"],
        ["Шаг с переводом\nстроки", "second"],
        ["Check {\"json\": true} configs", "Clean up"],
        ["一步", "Два", "Three 🚀"],
    ]
    for i, steps in enumerate(plans):
        listing = "\n".join(f"{k + 1}. {s}" for k, s in enumerate(steps))
        out.append({"id": f"plan-{i}", "tool": "update_plan",
                    "prompt": f"Set the plan to these steps (the first one in progress, the rest pending):\n{listing}",
                    "expect": ("plan_steps", steps[0].split("\n")[0][:12])})
    # http_request (6)
    https = [
        ("POST", "https://api.example.com/v1/items?q=a%20b&lang=ru", '{"name": "Иван \\"Ваня\\"", "tags": ["a", "b"]}'),
        ("PUT", "https://example.org/files/отчёт.txt", "line 1\nline 2\twith tab\n"),
        ("POST", "http://localhost:8080/graphql", '{"query": "{ user(id: \\"42\\") { name } }"}'),
        ("DELETE", "https://example.com/api/x/7", ""),
        ("POST", "https://hooks.example.com/T00/B00", "payload={\"text\": \"Deploy <ok> & done\"}"),
        ("GET", "https://example.com/search?q=%22exact%22", ""),
    ]
    for i, (m, url, body) in enumerate(https):
        bit = f" with the header X-Token: abc\"123 and exactly this body:\n{body}" if body else \
            " with the header Accept: application/json"
        out.append({"id": f"http-{i}", "tool": "http_request", "prompt": f"Send a {m} request to {url}{bit}",
                    "expect": ("body", body) if body else ("url", url)})
    # create_issue (6)
    issues = [
        ("Падает парсер на \"кавычках\"", "Шаги:\n1. Запустить `strata run --x \"a b\"`\n2. Видим ошибку\n\n"
         "```\nTraceback (most recent call last):\n  File \"a.py\", line 1\n```", ["bug", "парсер"], 2),
        ("Crash with C:\\Program Files paths", "Path: `C:\\Program Files\\Strata\\bin`\nExpected: works", ["windows"], 1),
        ("Docs: explain </parameter>", "The template uses <parameter=NAME> and </parameter>; document escaping.", ["docs"], 4),
        ("Unicode 🚀 in titles", "Mixed 日本語 / русский / English", [], 5),
        ("Tab\tin title", "body with\ttabs\tand \\backslashes\\", ["triage"], 3),
        ("JSON body", '{"a": 1, "b": [true, null], "c": "\\u00e9"}', ["api", "json"], 3),
    ]
    for i, (title, body, labels, prio) in enumerate(issues):
        lab = f" and the labels {', '.join(labels)}" if labels else " and no labels"
        out.append({"id": f"issue-{i}", "tool": "create_issue",
                    "prompt": f"Open an issue with priority {prio}{lab}. Title (exactly): {title}\n"
                              f"Body (exactly, between the markers):\n<<<BEGIN>>>\n{body}\n<<<END>>>",
                    "expect": ("body", body)})
    # run_sql (5)
    sqls = [
        ("SELECT id, name FROM users WHERE name = ? AND city = ?", ["O'Brien", "Москва"]),
        ("INSERT INTO notes (title, body) VALUES (?, ?)", ["\"Quoted\" title", "line1\nline2"]),
        ("UPDATE t SET data = ? WHERE id = ?", ['{"k": "v"}', 7]),
        ("SELECT * FROM \"Order Details\" WHERE price > ? AND note IS ?", [9.99, None]),
        ("DELETE FROM logs WHERE msg LIKE ?", ["%\\_tmp%"]),
    ]
    for i, (q, params) in enumerate(sqls):
        out.append({"id": f"sql-{i}", "tool": "run_sql",
                    "prompt": f"Run this SQL:\n{q}\nwith the parameters (in order, as JSON): "
                              f"{json.dumps(params, ensure_ascii=False)}",
                    "expect": ("query", q)})
    return out


def http(url, body=None, timeout=3600.0):
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def judge(it, msg):
    """(malformed reason or "", fidelity reason or "")."""
    calls = msg.get("tool_calls") or []
    mine = [c for c in calls if c["function"]["name"] == it["tool"]]
    if not mine:
        names = [c["function"]["name"] for c in calls]
        leak = "<tool_call>" in (msg.get("content") or "") or "<function=" in (msg.get("content") or "")
        return f"no {it['tool']} call (calls {names}{', call text in the content' if leak else ''})", ""
    try:
        args = json.loads(mine[0]["function"]["arguments"] or "{}")
    except ValueError as e:
        return f"arguments are not JSON: {e}", ""
    if not isinstance(args, dict):
        return "arguments are not an object", ""
    if jsonschema is not None:
        err = next(jsonschema.Draft202012Validator(SCHEMAS[it["tool"]]).iter_errors(args), None)
        if err is not None:
            return f"schema: {err.message[:120]}", ""
    key, want = it["expect"]
    if key.endswith("~"):
        got = args.get(key[:-1])
        text = " ".join(got) if isinstance(got, list) else str(got)
        return "", "" if want in text else f"{key[:-1]} lacks {want!r}"
    if key == "plan_steps":
        steps = [p.get("step", "") for p in args.get("plan") or []]
        return "", "" if steps and want in steps[0] else f"first step {steps[:1]!r}"
    got = args.get(key)
    return "", "" if got == want or (isinstance(got, str) and got.strip("\n") == want.strip("\n")) else \
        f"{key} differs: {str(got)[:60]!r}"


def run(a):
    """Every item with each arm in turn (an arm is a tag and its request fields), so a speed difference between the
    arms is not the model's warm-up or the expert cache settling."""
    arms = [(a.tag, json.loads(a.body) if a.body else {})]
    for tag, body in zip(a.pair[0::2], a.pair[1::2]):
        arms.append((tag, json.loads(body) if body else {}))
    done = {}
    for tag, _ in arms:
        path = HERE / "results" / f"{tag}.jsonl"
        path.parent.mkdir(exist_ok=True)
        done[tag] = {(json.loads(x)["id"], json.loads(x)["sample"]) for x in path.read_text(encoding="utf-8").splitlines()
                     if x.strip()} if path.exists() else set()
    t_start = time.time()
    for it in items():
        for s in range(a.samples):
            for tag, extra in arms:
                if (it["id"], s) in done[tag]:
                    continue
                if a.budget_min and time.time() - t_start > a.budget_min * 60:
                    print("budget reached; rerun to continue", flush=True)
                    return 2
                rc = one(a, it, s, tag, extra)
                if rc:
                    return rc
    return 0


def one(a, it, s, tag, extra):
    body = {"model": "strata", "max_tokens": a.max_tokens, "stream": False, "tools": TOOLS,
            "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": it["prompt"]}],
            **extra}
    t0 = time.time()
    try:
        out = http(a.url.rstrip("/") + "/v1/chat/completions", body)
    except (OSError, ValueError) as e:
        detail = e.read().decode("utf-8", "replace")[:300] if isinstance(e, urllib.error.HTTPError) else ""
        print(f"{it['id']} #{s}: request failed: {e} {detail}", flush=True)
        return 1
    wall = time.time() - t0
    try:
        last = (http(a.url.rstrip("/") + "/metrics", timeout=30).get("requests") or [{}])[0]
    except (OSError, ValueError):
        last = {}
    ch = out["choices"][0]
    msg = ch["message"]
    bad, fid = judge(it, msg)
    usage = out.get("usage") or {}
    rec = {"id": it["id"], "sample": s, "malformed": bad, "fidelity": fid, "wall_s": round(wall, 2),
           "completion_tokens": usage.get("completion_tokens"), "finish": ch.get("finish_reason"),
           "decode_tok_s": last.get("decode_tok_s") if last.get("output_tokens") == usage.get(
               "completion_tokens") else None,
           "tool_calls": msg.get("tool_calls"), "content": (msg.get("content") or "")[:2000]}
    with (HERE / "results" / f"{tag}.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"{tag:8} {it['id']:18} #{s} {'MALFORMED ' + bad if bad else 'ok'}{' | FIDELITY ' + fid if fid else ''} "
          f"{wall:5.1f}s {rec['completion_tokens']} tok {rec['decode_tok_s']} tok/s", flush=True)
    return 0


def report(tags):
    for tag in tags:
        rows = [json.loads(x) for x in (HERE / "results" / f"{tag}.jsonl").read_text(encoding="utf-8").splitlines()
                if x.strip()]
        n = len(rows)
        bad = [r for r in rows if r["malformed"]]
        fid = [r for r in rows if not r["malformed"] and r["fidelity"]]
        rates = sorted(r["decode_tok_s"] for r in rows if r.get("decode_tok_s"))
        mean = sum(rates) / len(rates) if rates else 0.0
        med = rates[len(rates) // 2] if rates else 0.0
        print(f"{tag}: {n} replies, malformed {len(bad)} ({100 * len(bad) / max(1, n):.1f}%), fidelity misses "
              f"{len(fid)}, decode tok/s mean {mean:.1f} median {med:.1f} (n={len(rates)})")
        for r in bad:
            print(f"   MALFORMED {r['id']} #{r['sample']}: {r['malformed']}")
        for r in fid:
            print(f"   fidelity  {r['id']} #{r['sample']}: {r['fidelity']}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--url", default="http://127.0.0.1:8096")
    ap.add_argument("--tag", help="results/<tag>.jsonl")
    ap.add_argument("--body", default="", help="JSON merged into every request (e.g. the constrained_tools switch)")
    ap.add_argument("--pair", nargs="*", default=[], metavar="TAG BODY",
                    help="more arms (tag, then its JSON fields), run item by item in turn with --tag/--body")
    ap.add_argument("--samples", type=int, default=1)
    ap.add_argument("--max-tokens", type=int, default=12000)
    ap.add_argument("--budget-min", type=float, default=0)
    ap.add_argument("--report", nargs="+", metavar="TAG")
    ap.add_argument("--list", action="store_true", help="print the items and exit")
    a = ap.parse_args()
    if a.list:
        for it in items():
            print(it["id"], it["tool"], json.dumps(it["prompt"][:100], ensure_ascii=False))
        print(len(items()), "items")
        return 0
    if a.report:
        report(a.report)
        return 0
    if not a.tag:
        ap.error("--tag is required")
    return run(a)


if __name__ == "__main__":
    sys.exit(main())
