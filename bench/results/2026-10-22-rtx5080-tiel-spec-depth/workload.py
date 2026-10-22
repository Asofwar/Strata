"""Replay requests from real conversations (the conversation disk tier's token lists).

long_*: a real agent conversation from the live server (93.5K tokens, terminal / patch / write_file turns), with a real
source file read inserted after the compaction summary to put each cut at ~130K or ~200K. mid: the same conversation
as it was (34-88K). short: bench/agent-ru runs (write_file turns, 4-24K). Each request is the conversation up to an
assistant turn's "<|im_start|>assistant\n"; the engine writes that turn."""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
from convidx import read_idx, tok
from turns import turns

D = r"D:\Strata-data\conv-disk"
SRC = r"E:\Projects\Strata-fork\.claude\worktrees\modest-heisenberg-691b50\src\program\generate.cpp"
IM_START, IM_END = 248045, 248046


def nl_ids(t):
    return t.encode("\n")


def filler(t, n_tokens):
    """an assistant read_file call and its tool response with numbered lines of a real C++ file, ~n_tokens long"""
    lines = open(SRC, encoding="utf-8").read().split("\n")
    head = ("<|im_start|>assistant\n<think>\nLet me read the engine's decode loop before changing the script.\n</think>\n\n"
            "<tool_call>\n<function=read_file>\n<parameter=path>\nsrc/program/generate.cpp\n</parameter>\n</function>\n"
            "</tool_call><|im_end|>\n<|im_start|>user\n<tool_response>\n")
    tail = "\n</tool_response><|im_end|>\n"
    hid = t.encode(head, parse_special=True)
    tid = t.encode(tail, parse_special=True)
    body, have, i = [], 0, 0
    budget = n_tokens - len(hid) - len(tid)
    while have < budget and i < len(lines):
        chunk = "\n".join(f"{k + 1:6d}| {lines[k]}" for k in range(i, min(i + 200, len(lines))))
        ids = t.encode(chunk + "\n")
        body.append(ids)
        have += len(ids)
        i += 200
    out = hid + [x for b in body for x in b] + tid
    return out


def cut_prompt(ids, s):
    """tokens up to and including '<|im_start|>assistant\\n' of the turn at s"""
    t = tok()
    head = t.encode("<|im_start|>assistant\n", parse_special=True)
    assert ids[s:s + len(head)] == head, (ids[s:s + len(head)], head)
    return ids[:s + len(head)]


def main():
    t = tok()
    reqs = []
    # hermes conversation
    h = read_idx(os.path.join(D, "strata-conv-14bf13cf0e4e0076-73.idx"))["live"]
    ts = turns(h)
    by_idx = {k: (s, r, n) for k, (s, r, n) in enumerate(ts)}
    cuts = [8, 22, 44, 56, 62, 80, 99, 117]   # patch, write_file, terminal, write_file, patch, patch, terminal x2
    ins = ts[2][0]                             # the first assistant turn, after the compaction summary
    for group, extra in (("mid", 0), ("long130", 72000), ("long200", 142000)):
        f = filler(t, extra) if extra else []
        for k in cuts:
            s, r, n = by_idx[k]
            assert r == "assistant"
            p = cut_prompt(h, s)
            p = p[:ins] + f + p[ins:]
            reqs.append({"group": group, "conv": "hermes73", "turn": k, "real_len": n, "ids": p})
    # agent-ru runs: write_file turns (the whole module written out) and the ones before them
    for name in ("strata-conv-b1c1f52c23477aaf-122.idx", "strata-conv-b1c1f52c23477aaf-107.idx",
                 "strata-conv-b1c1f52c23477aaf-97.idx"):
        ids = read_idx(os.path.join(D, name))["live"]
        tt = turns(ids)
        picked = []
        for k, (s, r, n) in enumerate(tt):
            if r != "assistant" or s < 2000:
                continue
            x = t.decode(ids[s:s + n])
            fn = re.findall(r"<function=([a-z_]+)", x)
            if any(f in ("write_file", "edit_file", "replace", "patch") for f in fn):
                picked.append((k, s, n, fn))
        for k, s, n, fn in picked[:3]:
            reqs.append({"group": "short", "conv": name[-7:-4], "turn": k, "real_len": n, "ids": cut_prompt(ids, s),
                         "fn": fn})
    for r in reqs:
        print(r["group"], r["conv"], r["turn"], len(r["ids"]), r["real_len"], r.get("fn", ""))
    json.dump(reqs, open(os.path.join(os.path.dirname(__file__), "reqs.json"), "w"))


if __name__ == "__main__":
    main()
