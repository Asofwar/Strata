"""Read the conversation disk tier's .idx files (src/core/conversation_disk.cpp): the live token ids of each
saved conversation, and decode/summarize them with the pack's tokenizer."""
import json, struct, sys, glob, os
from pathlib import Path

sys.path.insert(0, r"E:\Projects\Strata-fork\.claude\worktrees\modest-heisenberg-691b50\tools")
TOKDIR = Path(r"D:\Strata-data\packs\cyber-tiel-iq4_xs\tokenizer")
MAGIC = 0x3158444943525453


def read_idx(path):
    b = Path(path).read_bytes()
    at = 0

    def get(fmt):
        nonlocal at
        v = struct.unpack_from(fmt, b, at)
        at += struct.calcsize(fmt)
        return v[0]

    def key():
        nonlocal at
        n = get("<I")
        ids = list(struct.unpack_from(f"<{n}i", b, at))
        at += 4 * n
        m = get("<I")
        at += 16 * m
        return ids

    if get("<Q") != MAGIC:
        return None
    get("<Q"); get("<Q")
    written = get("<q")
    get("<B")
    get("<Q")
    nf = get("<I")
    for _ in range(nf):
        n = get("<I")
        at += n
    live = key()
    nck = get("<I")
    cks = [key() for _ in range(nck)]
    return {"written": written, "live": live, "checkpoints": cks}


_tok = None


def tok():
    global _tok
    if _tok is None:
        import strata_tokenizer as ST
        vocab = json.loads((TOKDIR / "vocab.json").read_text(encoding="utf-8"))
        tokens = [None] * len(vocab)
        for t, i in vocab.items():
            tokens[i] = t
        merges = (TOKDIR / "merges.txt").read_text(encoding="utf-8").split("\n")
        types = json.loads((TOKDIR / "token_type.json").read_text())
        _tok = ST.Tokenizer(tokens, merges, types)
    return _tok


if __name__ == "__main__":
    rows = []
    for p in sorted(glob.glob(r"D:\Strata-data\conv-disk\*.idx")):
        e = read_idx(p)
        if e is None:
            continue
        rows.append((os.path.basename(p), len(e["live"]), len(e["checkpoints"]), e["written"]))
    for r in rows:
        print(*r)
