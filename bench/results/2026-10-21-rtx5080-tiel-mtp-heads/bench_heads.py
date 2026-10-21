"""Greedy chat requests through the Strata HTTP server: acceptance and decode rate per prompt, --spec-min-p per request.
python bench_heads.py --port 8097 --label base --runs 3 --out results.jsonl [--only short|long] [--long-chars N]"""
import argparse, hashlib, json, pathlib, time, urllib.request

REPO = pathlib.Path(r"E:\Projects\Strata-fork\.claude\worktrees\mtp-head-3b3c5e")
TOOLS = [
    {"type": "function", "function": {"name": "read_file", "description": "Read a file of the repository",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "grep", "description": "Search the repository with a regular expression",
     "parameters": {"type": "object", "properties": {"pattern": {"type": "string"}, "glob": {"type": "string"}},
                    "required": ["pattern"]}}},
    {"type": "function", "function": {"name": "run", "description": "Run a shell command and return its output",
     "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
]


def text(rel, a, b):
    return (REPO / rel).read_text(encoding="utf-8", errors="replace")[a:b]


def short_prompts():
    code = text("src/core/mtp.cpp", 0, 6500)
    ru = text("docs/FORK.ru.md", 0, 5000) if (REPO / "docs/FORK.ru.md").exists() else text("docs/EVAL.ru.md", 0, 5000)
    agent_ctx = text("tools/mtp_fetch.py", 0, 5000)
    return [
        ("code-2k", [{"role": "user", "content": "Here is a C++ file from an inference engine:\n\n```cpp\n" + code +
                      "\n```\n\nWrite a C++17 function `bool check_norms(const std::vector<float>& w, float lo, float hi)` "
                      "that validates RMSNorm weights loaded above, with unit tests using plain asserts."}], None),
        ("ru-2k", [{"role": "user", "content": "Вот документ:\n\n" + ru +
                    "\n\nПерескажи его по-русски в 8-10 предложениях и предложи три конкретных улучшения."}], None),
        ("agent-2k", [{"role": "system", "content": "You are a coding agent working in the Strata repository. Use the tools "
                       "to inspect files before answering. Be concise."},
                      {"role": "user", "content": "This is tools/mtp_fetch.py (start):\n\n```python\n" + agent_ctx +
                       "\n```\n\nFind where the range check happens, then check whether tests cover it. Start by "
                       "searching the tests."}], TOOLS),
    ]


def long_prefix(chars):
    parts, n = [], 0
    files = sorted((REPO / "src").rglob("*.cpp")) + sorted((REPO / "src").rglob("*.cu"))
    for f in files:
        t = f.read_text(encoding="utf-8", errors="replace")
        parts.append(f"// ===== {f.relative_to(REPO).as_posix()} =====\n{t}\n")
        n += len(parts[-1])
        if n >= chars:
            break
    return "".join(parts)[:chars]


def long_prompts(chars):
    pre = long_prefix(chars)
    base = "Below is part of the source tree of an inference engine.\n\n" + pre + "\n\n"
    return [
        ("code-130k", [{"role": "user", "content": base + "Write a C++17 function that parses the `STRATA_ATTN_SPLITS` "
                        "environment variable the way this code base reads its other STRATA_* variables, with tests."}], None),
        ("ru-130k", [{"role": "user", "content": base + "Объясни по-русски, как в этом коде устроен черновой слой MTP: "
                      "откуда он грузится, как выбираются черновые токены и как они проверяются. 10-12 предложений."}], None),
        ("agent-130k", [{"role": "system", "content": "You are a coding agent. Use the tools before answering."},
                        {"role": "user", "content": base + "The draft acceptance dropped after a change to mtp.cpp. "
                         "Find the tests that cover the MTP draft layer and run them."}], TOOLS),
    ]


def post(port, body, timeout=1800):
    req = urllib.request.Request(f"http://127.0.0.1:{port}/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8097)
    ap.add_argument("--label", required=True)
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--pmins", default="0.5,0.75")
    ap.add_argument("--max-tokens", type=int, default=384)
    ap.add_argument("--only", choices=["short", "long", "all"], default="all")
    ap.add_argument("--long-chars", type=int, default=430000)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    sets = []
    if a.only in ("short", "all"):
        sets += short_prompts()
    if a.only in ("long", "all"):
        sets += long_prompts(a.long_chars)
    pmins = [float(x) for x in a.pmins.split(",")]
    t0 = time.time()
    post(a.port, {"model": "x", "messages": [{"role": "user", "content": "Hi"}], "max_tokens": 8, "temperature": 0})
    print(f"warmup {time.time() - t0:.1f} s", flush=True)
    with open(a.out, "a", encoding="utf-8") as out:
        for name, msgs, tools in sets:
            for run in range(a.runs):
                order = pmins if run % 2 == 0 else list(reversed(pmins))
                for pm in order:
                    body = {"model": "x", "messages": msgs, "max_tokens": a.max_tokens, "temperature": 0,
                            "stream": False, "strata_tune": {"spec_min_p": pm}}
                    if tools:
                        body["tools"] = tools
                    t0 = time.time()
                    r = post(a.port, body)
                    wall = time.time() - t0
                    m = r["choices"][0]["message"]
                    content = (m.get("reasoning_content") or "") + "\x00" + (m.get("content") or "") + "\x00" + \
                        json.dumps(m.get("tool_calls") or [], sort_keys=True)
                    tm = r.get("timings") or {}
                    row = {"label": a.label, "prompt": name, "pmin": pm, "run": run, "wall": round(wall, 2),
                           "prompt_n": tm.get("prompt_n"), "cache_n": tm.get("cache_n"), "prompt_ms": tm.get("prompt_ms"),
                           "predicted_n": tm.get("predicted_n"), "tps": tm.get("predicted_per_second"),
                           "draft_n": tm.get("draft_n"), "draft_acc": tm.get("draft_n_accepted"),
                           "finish": r["choices"][0].get("finish_reason"),
                           "sha": hashlib.sha256(content.encode()).hexdigest()[:16], "text": content}
                    out.write(json.dumps(row, ensure_ascii=False) + "\n")
                    out.flush()
                    acc = (row["draft_acc"] or 0) / row["draft_n"] if row["draft_n"] else 0
                    print(f"{a.label} {name} p{pm} r{run}: prompt {row['prompt_n']} (cache {row['cache_n']}) "
                          f"{row['prompt_ms']} ms, {row['predicted_n']} tok {row['tps']} tok/s, "
                          f"acc {row['draft_acc']}/{row['draft_n']} {acc:.3f} {row['sha']}", flush=True)


if __name__ == "__main__":
    main()
