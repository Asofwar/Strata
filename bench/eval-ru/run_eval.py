"""bench/eval-ru/run_eval.py - a small fixed quality eval through a running Strata server (OpenAI chat API).

Requests carry no sampling fields, so the server applies what Codex gets by default (the model card's sampling and
the config's thinking). Only max_tokens is set, as a guard against a reply that never ends.

    python bench/eval-ru/run_eval.py --url http://127.0.0.1:8096 --tag tiel --cats coding,tools
    python bench/eval-ru/run_eval.py --tag ornith --cats russian,needle --budget-min 25
    python bench/eval-ru/score.py bench/eval-ru/results/tiel.jsonl bench/eval-ru/results/ornith.jsonl

One JSON line per reply goes to results/<tag>.jsonl. A rerun skips the replies already there, so a run can be split
into several windows (--budget-min stops starting new requests after that many minutes).

Categories: coding (12 tasks, unit tests run with python -I / node), tools (7 tool-calling prompts), russian
(10 rubric-checked prompts), needle (32K and 128K needle-in-a-haystack built from docs/*.md, depths 10/50/90).
Reasoning loops are counted over all replies: the server's reasoning_loop_recovery count (GET /metrics) and replies
over 8K reasoning tokens.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
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

import items_coding  # noqa: E402
import items_russian  # noqa: E402
import items_tools  # noqa: E402

NEEDLE_WORDS = ["янтарь", "сокол", "кварц", "ива", "медь", "гавань"]
NEEDLES = [(32768, 10), (32768, 50), (32768, 90), (131072, 10), (131072, 50), (131072, 90)]
CHARS_PER_TOKEN = 3.2


def load_tokenizer(path: Path):
    import strata_tokenizer as ST
    vocab = json.loads((path / "vocab.json").read_text(encoding="utf-8"))
    tokens = [None] * len(vocab)
    for t, i in vocab.items():
        tokens[i] = t
    merges = (path / "merges.txt").read_text(encoding="utf-8").split("\n")
    types = json.loads((path / "token_type.json").read_text())
    return ST.Tokenizer(tokens, merges, types)


def http(url, body=None, timeout=3600.0):
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def chat(url, messages, tools=None, max_tokens=16384):
    body = {"model": "strata", "messages": messages, "max_tokens": max_tokens, "stream": False}
    if tools:
        body["tools"] = tools
    t0 = time.time()
    out = http(url.rstrip("/") + "/v1/chat/completions", body)
    wall = time.time() - t0
    try:
        last = (http(url.rstrip("/") + "/metrics", timeout=30).get("requests") or [{}])[0]   # newest first
    except (OSError, ValueError):
        last = {}
    if last.get("output_tokens") != (out.get("usage") or {}).get("completion_tokens"):
        last = {}                       # not this request's entry: leave its counts unknown rather than wrong
    return out, wall, last


def parse_message(out):
    ch = out["choices"][0]
    m = ch["message"]
    tcs, bad = [], []
    for c in m.get("tool_calls") or []:
        try:
            args = json.loads(c["function"]["arguments"] or "{}")
        except (ValueError, TypeError):
            bad.append(c["function"].get("arguments"))
            args = None
        tcs.append({"name": c["function"]["name"], "args": args})
    return {"content": m.get("content") or "", "reasoning": m.get("reasoning_content") or "",
            "tool_calls": tcs, "bad_args": bad, "finish": ch.get("finish_reason")}


def strip_think(text):
    return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()


def extract_code(text, lang):
    tags = ("python", "py") if lang == "python" else ("javascript", "js", "node")
    blocks = re.findall(r"```([\w+-]*)[ \t]*\n(.*?)```", text, re.S)
    good = [b for t, b in blocks if t.lower() in tags] or [b for t, b in blocks]
    if good:
        return max(good, key=len)
    # a reply that ends inside its block (the closing fence never written): the code after the opening fence
    m = re.search(r"```[\w+-]*[ \t]*\n(.*)$", text, re.S)
    return m.group(1) if m else text


def unclosed_fence(text):
    return text.count("```") % 2 == 1


def run_code(code, test, lang):
    if lang == "javascript":
        code = re.sub(r"^\s*export\s+(default\s+)?", "", code, flags=re.M)
        code = re.sub(r"^\s*module\.exports\s*=.*$", "", code, flags=re.M)
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / ("sol.py" if lang == "python" else "sol.js")
        f.write_text(code + "\n\n" + test, encoding="utf-8")
        cmd = [sys.executable, "-I", str(f)] if lang == "python" else ["node", str(f)]
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=20, cwd=d, encoding="utf-8",
                               errors="replace", env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        except subprocess.TimeoutExpired:
            return False, "timeout"
    if p.returncode == 0:
        return True, ""
    err = (p.stderr or p.stdout).strip().splitlines()
    named = [x for x in err if re.match(r"\s*\w*(Error|Exception)\b", x)]
    return False, (named[0] if named else err[-1] if err else f"exit {p.returncode}").strip()[:200]


def haystack(n_chars):
    files = sorted((ROOT / "docs").rglob("*.md"))
    parts, total = [], 0
    while total < n_chars:
        for f in files:
            t = f.read_text(encoding="utf-8", errors="replace")
            parts.append(f"\n\n=== {f.relative_to(ROOT).as_posix()} ===\n{t}")
            total += len(parts[-1])
            if total >= n_chars:
                break
    return "".join(parts)[:n_chars]


def needle_items():
    rnd = random.Random(20261021)
    out = []
    for i, (tokens, depth) in enumerate(NEEDLES):
        code = f"{NEEDLE_WORDS[i]}-{rnd.randint(1000, 9999)}"
        n_chars = int(tokens * 0.94 * CHARS_PER_TOKEN)
        text = haystack(n_chars)
        at = text.find("\n", int(len(text) * depth / 100))
        at = at if at >= 0 else len(text)
        needle = (f"\n\nВажная заметка для проверки памяти: кодовое слово хранилища - «{code}». "
                  f"Его спросят в конце.\n\n")
        prompt = (text[:at] + needle + text[at:] +
                  "\n\n---\nВ тексте выше спрятано кодовое слово хранилища. Напиши только это кодовое слово.")
        out.append({"id": f"needle-{tokens // 1024}k-d{depth}", "code": code, "prompt": prompt})
    return out


def build(cats):
    jobs = []
    if "coding" in cats:
        for it in items_coding.ITEMS:
            jobs.append(("coding", it["id"], it))
    if "tools" in cats:
        for it in items_tools.ITEMS:
            jobs.append(("tools", it["id"], it))
    if "russian" in cats:
        for it in items_russian.ITEMS:
            jobs.append(("russian", it["id"], it))
    if "needle" in cats:
        for it in needle_items():
            jobs.append(("needle", it["id"], it))
    return jobs


def score(cat, it, msg):
    content = strip_think(msg["content"])
    if cat == "coding":
        if not content:
            return False, "empty content"
        return run_code(extract_code(content, it["lang"]), it["test"], it["lang"])
    if cat == "tools":
        if msg["bad_args"]:
            return False, f"invalid JSON arguments: {msg['bad_args'][0]!r:.80}"
        return it["check"]({"content": content, "tool_calls": msg["tool_calls"]})
    if cat == "russian":
        return it["check"](content)
    if cat == "needle":
        ok = it["code"].lower() in content.lower()
        return ok, "" if ok else f"got {content[:80]!r}"
    raise ValueError(cat)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--url", default="http://127.0.0.1:8096")
    ap.add_argument("--tag", required=True, help="results/<tag>.jsonl")
    ap.add_argument("--cats", default="coding,tools,russian,needle")
    ap.add_argument("--samples", type=int, default=2)
    ap.add_argument("--needle-samples", type=int, default=1)
    ap.add_argument("--max-tokens", type=int, default=16384)
    ap.add_argument("--budget-min", type=float, default=0, help="stop starting requests after this many minutes")
    ap.add_argument("--rescore", action="store_true", help="check the stored replies again (after a checker change)")
    ap.add_argument("--tokenizer", default=r"D:\Strata-data\packs\cyber-tiel-iq4_xs\tokenizer",
                    help="to count reasoning tokens (both models share the Qwen3.6 vocabulary)")
    a = ap.parse_args()
    cats = set(a.cats.split(","))
    out_path = HERE / "results" / f"{a.tag}.jsonl"
    out_path.parent.mkdir(exist_ok=True)
    if a.rescore:
        items = {(cat, iid): it for cat, iid, it in build({"coding", "tools", "russian", "needle"})}
        rows = [json.loads(x) for x in out_path.read_text(encoding="utf-8").splitlines() if x.strip()]
        changed = 0
        for r in rows:
            msg = {"content": r["content"], "tool_calls": r["tool_calls"], "bad_args": r.get("bad_args", [])}
            ok, why = score(r["cat"], items[(r["cat"], r["id"])], msg)
            changed += bool(ok) != r["pass"]
            r["pass"], r["why"] = bool(ok), why
            if r["cat"] == "coding":
                r["unclosed_fence"] = unclosed_fence(r["content"])
        out_path.write_text("".join(json.dumps(r, ensure_ascii=False) + chr(10) for r in rows), encoding="utf-8")
        print(f"rescored {len(rows)} replies, {changed} changed")
        return 0
    done = set()
    if out_path.exists():
        for line in out_path.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            done.add((r["cat"], r["id"], r["sample"]))
    tok = load_tokenizer(Path(a.tokenizer))
    t_start = time.time()
    for cat, iid, it in build(cats):
        n = a.needle_samples if cat == "needle" else a.samples
        for s in range(n):
            if (cat, iid, s) in done:
                continue
            if a.budget_min and time.time() - t_start > a.budget_min * 60:
                print(f"budget of {a.budget_min} min reached; rerun to continue", flush=True)
                return 2
            if cat == "tools":
                messages, tools = it["messages"], it["tools"]
            else:
                messages, tools = [{"role": "user", "content": it["prompt"]}], None
            try:
                out, wall, last = chat(a.url, messages, tools, a.max_tokens)
                msg = parse_message(out)
                error = None
            except (OSError, ValueError, KeyError) as e:
                body = e.read().decode("utf-8", "replace")[:300] if isinstance(e, urllib.error.HTTPError) else ""
                print(f"{cat} {iid} #{s}: request failed: {e} {body}", flush=True)
                return 1
            ok, why = score(cat, it, msg)
            usage = out.get("usage") or {}
            rec = {"cat": cat, "id": iid, "sample": s, "pass": bool(ok), "why": why, "wall_s": round(wall, 2),
                   "prompt_tokens": usage.get("prompt_tokens"), "completion_tokens": usage.get("completion_tokens"),
                   "reasoning_tokens": len(tok.encode(msg["reasoning"])) if msg["reasoning"] else 0,
                   "reasoning_recoveries": last.get("reasoning_recoveries"),
                   "metrics_output_tokens": last.get("output_tokens"),
                   "decode_tok_s": last.get("decode_tok_s"), "prompt_ms": last.get("prompt_ms"),
                   "finish": msg["finish"], "content": msg["content"], "bad_args": msg["bad_args"],
                   "unclosed_fence": unclosed_fence(msg["content"]) if cat == "coding" else None,
                   "tool_calls": msg["tool_calls"], "reasoning_head": msg["reasoning"][:400],
                   "reasoning_tail": msg["reasoning"][-400:] if len(msg["reasoning"]) > 400 else ""}
            if error:
                rec["error"] = error
            with out_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            print(f"{cat:8} {iid:22} #{s} {'PASS' if ok else 'FAIL'} {wall:6.1f}s think {rec['reasoning_tokens']:5} "
                  f"out {rec['completion_tokens']} rec {rec['reasoning_recoveries']} {why[:80]}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
