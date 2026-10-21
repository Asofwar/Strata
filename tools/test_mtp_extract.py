"""tools/test_mtp_extract.py - mtp_extract.py on a synthetic two-layer GGUF (no model, no network).

    python tools/test_mtp_extract.py
"""
import pathlib
import struct
import subprocess
import sys
import tempfile

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mtp_extract  # noqa: E402
from gguf_reader import GGUFFile  # noqa: E402


def gguf(path, meta, tensors, align=32):
    """meta: [(key, 'u32'|'str'|'strs', value)]; tensors: [(name, shape, type, raw)]."""
    def s(x):
        b = x.encode()
        return struct.pack("<Q", len(b)) + b
    h = struct.pack("<IIQQ", 0x46554747, 3, len(tensors), len(meta))
    for k, t, v in meta:
        h += s(k)
        if t == "u32":
            h += struct.pack("<II", 4, v)
        elif t == "str":
            h += struct.pack("<I", 8) + s(v)
        else:
            h += struct.pack("<IIQ", 9, 8, len(v)) + b"".join(s(x) for x in v)
    off, offs = 0, []
    for name, shape, typ, raw in tensors:
        offs.append(off)
        h += s(name) + struct.pack("<I", len(shape)) + struct.pack(f"<{len(shape)}Q", *shape) + struct.pack("<IQ", typ, off)
        off = (off + len(raw) + align - 1) // align * align
    h += b"\0" * ((-len(h)) % align)
    data = b""
    for (_, _, _, raw), at in zip(tensors, offs):
        data += b"\0" * (at - len(data)) + raw
    pathlib.Path(path).write_bytes(h + data)


def ref_q8_0(x):
    out = b""
    for blk in x.reshape(-1, 32):
        amax = float(np.abs(blk).max())
        d = np.float32(amax / 127.0)
        inv = np.float32(1.0 / d) if d else np.float32(0.0)
        q = [int(np.trunc(np.float32(v * inv) + np.copysign(np.float32(0.5), np.float32(v * inv)))) for v in blk]
        out += np.float16(d).tobytes() + struct.pack("<32b", *q)
    return out


def main():
    rng = np.random.default_rng(7)
    meta = [("general.architecture", "str", "qwen35moe"), ("qwen35moe.block_count", "u32", 2),
            ("qwen35moe.nextn_predict_layers", "u32", 1), ("qwen35moe.embedding_length", "u32", 64),
            ("tokenizer.ggml.tokens", "strs", ["a", "b", "c"])]
    k = (rng.standard_normal((4, 64)) * 0.05).astype(np.float32)
    k[0, :32] = 0.0                                        # an all-zero block: scale 0, codes 0
    k[1, 0] = 127 * 0.01 * 1.0                              # a block whose scale makes an exact .5 likely elsewhere
    norm = rng.standard_normal(64).astype(np.float32)
    donor_t = [("token_embd.weight", [64, 3], 0, rng.standard_normal(192).astype(np.float32).tobytes()),
               ("blk.1.attn_k.weight", [64, 4], 1, k.astype(np.float16).tobytes()),
               ("blk.1.attn_norm.weight", [64], 0, norm.tobytes())]
    target_t = [("blk.1.attn_k.weight", [64, 4], 8, ref_q8_0(k.astype(np.float16).astype(np.float32))),
                ("blk.1.attn_norm.weight", [64], 0, norm.tobytes())]
    with tempfile.TemporaryDirectory() as td:
        td = pathlib.Path(td)
        gguf(td / "donor.gguf", meta, donor_t)
        gguf(td / "target.gguf", meta, target_t)
        r = subprocess.run([sys.executable, str(HERE / "mtp_extract.py"), str(td / "donor.gguf"), "--target",
                            str(td / "target.gguf"), "--out", str(td / "head.gguf")], capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        assert "byte-identical to the target's layer: 2 of 2" in r.stdout, r.stdout
        g = GGUFFile(td / "head.gguf")
        assert [t.name for t in g.tensors] == ["blk.1.attn_k.weight", "blk.1.attn_norm.weight"]
        assert g.tensors[0].type_name == "Q8_0" and g.metadata["tokenizer.ggml.tokens"] == ["a", "b", "c"]
        # a target with another vocabulary is refused
        gguf(td / "other.gguf", meta[:-1] + [("tokenizer.ggml.tokens", "strs", ["a", "b"])], target_t)
        r = subprocess.run([sys.executable, str(HERE / "mtp_extract.py"), str(td / "donor.gguf"), "--target",
                            str(td / "other.gguf"), "--out", str(td / "x.gguf")], capture_output=True, text=True)
        assert r.returncode != 0 and "vocabulary 3 tokens" in r.stderr, r.stderr
    # the converter against the scalar reference on random rows, exact halves included
    x = (rng.standard_normal(32 * 64) * 3).astype(np.float32)
    x[:32] = np.arange(32, dtype=np.float32) - 15.5           # many exact .5 codes after scaling
    assert mtp_extract.to_q8_0(x.tobytes(), 0, [32, 64]) == ref_q8_0(x)
    print("ok")


if __name__ == "__main__":
    main()
