"""tools/mtp_extract.py - a qwen35moe draft layer (blk.<n_layers>.*, the MTP / nextn block) as a file of its own.

The engine already takes the draft layer from any GGUF: `--mtp <file>` reads only blk.<n_layers>.* from it and drafts
against the main model's own output head, so a head from another quantization (or another upload of the same
checkpoint) needs no transplant into the main file. What it does need is a file that holds the layer, and the donors
are whole 15-25 GB models. This tool writes the layer alone (a few hundred MB), from a local GGUF or straight from
an https URL (Hugging Face `resolve/` links) by HTTP range reads - the header first, then only the layer's tensors.

    python tools/mtp_extract.py SRC --target MODEL.gguf --out head.gguf [--to-q8 auto|off] [--sha256 HEX]
    python tools/mtp_extract.py SRC --info                         # the layer's tensors and types, nothing written

SRC is a path or an https URL. `--target` is the GGUF the head will draft for: the tool refuses a donor whose
architecture, embedding width, expert count/width, block count, nextn layer count, vocabulary size or layer tensor
shapes differ from it, and prints which layer tensors are byte-identical to the target's (a quick way to see whether
two "different" heads are the same weights at another quantization).

The draft layer's projections must be a type the engine's GEMV reads (Q8_0, the K-quants, IQ4_XS, ...). F16, BF16
and F32 projections are not; `--to-q8 auto` (the default) re-quantizes those to Q8_0 the way ggml's quantize_row_q8_0
does (scale = absmax / 127 stored as F16, q = round(x / scale)). Norms and routers stay as stored. Experts are copied
as stored. The CUDA build reads fewer expert types than the GEMV: Q2_K gate/up but no Q2_K down (ICE 1.6 tiers keep
the draft layer's experts at Q2_K), and Q6_K only in a -DSTRATA_Q6K_EXPERTS build, so a donor whose experts the engine
has no kernels for is refused before anything is fetched (`--allow-unsupported` writes it anyway).

The written file keeps all of the donor's metadata (the engine reads none of it for the layer, but it keeps the file
self-describing) and the layer's tensors in the donor's order. `--sha256` checks the whole donor file, so it is only
honoured for a local SRC; for a URL the tool checks every ranged read is the 206 range asked for (a proxy that ignores
Range would otherwise hand back the wrong bytes) and the tensor sizes against the type geometry.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import pathlib
import struct
import sys
import time
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from gguf_reader import BLOCK_GEOMETRY, GGML_TYPES, GGUF_MAGIC, GGUF_META

# the types the draft layer's projections can be stored in (strata::kernels::native_mmvq_supported)
GEMV_TYPES = {2, 6, 7, 8, 11, 12, 13, 14, 16, 17, 18, 20, 21, 22, 23, 29, 42}
# the routed-expert types the grouped expert kernels take (STRATA_GU_FMTS / STRATA_D_FMTS in iq_kernels.cu, the
# default build; -DSTRATA_Q6K_EXPERTS adds Q6_K to both)
EXPERT_GU = {2, 3, 6, 8, 10, 11, 12, 13, 16, 17, 18, 21, 22, 23, 29, 40, 42, 144, 145}
EXPERT_DOWN = {2, 3, 6, 7, 8, 11, 12, 13, 18, 20, 23, 40, 42, 144, 146}
F32, F16, Q8_0, BF16 = 0, 1, 8, 30
NORMS = {"nextn.enorm.weight", "nextn.hnorm.weight", "attn_norm.weight", "attn_q_norm.weight", "attn_k_norm.weight",
         "post_attention_norm.weight", "nextn.shared_head_norm.weight", "ffn_gate_inp.weight",
         "ffn_gate_inp_shexp.weight"}


# ---------------------------------------------------------------- sources: a local file or an https URL
class LocalSource:
    def __init__(self, path):
        self.path = str(path)
        self.fh = open(self.path, "rb")
        self.size = os.path.getsize(self.path)

    def read(self, start, n):
        self.fh.seek(start)
        b = self.fh.read(n)
        if len(b) != n:
            raise OSError(f"{self.path}: short read at {start} ({len(b)} of {n} bytes; is the file complete?)")
        return b


class HttpSource:
    def __init__(self, url):
        self.url = url
        self.size = None

    def read(self, start, n, retries=6):
        last = start + n - 1
        for attempt in range(retries):
            try:
                req = urllib.request.Request(self.url, headers={"Range": f"bytes={start}-{last}",
                                                                 "User-Agent": "strata-mtp-extract"})
                with urllib.request.urlopen(req, timeout=120) as r:
                    cr = r.headers.get("Content-Range", "")
                    if r.status != 206 or not cr.startswith(f"bytes {start}-{last}/"):
                        raise OSError(f"{self.url}: asked for bytes {start}-{last}, got HTTP {r.status} "
                                      f"Content-Range '{cr}' (a server or proxy that ignores Range)")
                    self.size = int(cr.rsplit("/", 1)[1])
                    b = r.read()
                if len(b) != n:
                    raise OSError(f"short body: {len(b)} of {n} bytes")
                return b
            except OSError as ex:
                if attempt == retries - 1 or "ignores Range" in str(ex):
                    raise
                time.sleep(2 * (attempt + 1))


def open_source(src):
    return HttpSource(src) if src.startswith(("http://", "https://")) else LocalSource(src)


class Cursor:
    """Sequential reads over a source, fetched in growing chunks (the header of a remote file is a few MB)."""

    def __init__(self, source, chunk=8 << 20):
        self.s, self.buf, self.base, self.pos, self.chunk = source, b"", 0, 0, chunk

    def take(self, n):
        while self.pos + n > self.base + len(self.buf):
            want = max(self.chunk, self.pos + n - self.base - len(self.buf))
            if self.s.size is not None:
                want = min(want, self.s.size - self.base - len(self.buf))
                if want <= 0:
                    raise OSError("header runs past the end of the file")
            self.buf += self.s.read(self.base + len(self.buf), want)
        off = self.pos - self.base
        self.pos += n
        return self.buf[off:off + n]


# ---------------------------------------------------------------- the header, with each metadata pair's raw bytes
def _skip_value(c, t):
    name, size = GGUF_META[t]
    if name == "string":
        (n,) = struct.unpack("<Q", c.take(8))
        return c.take(n).decode("utf-8", "replace")
    if name == "array":
        et, count = struct.unpack("<IQ", c.take(12))
        ename, esize = GGUF_META[et]
        if ename == "string":
            out = []
            for _ in range(count):
                (n,) = struct.unpack("<Q", c.take(8))
                out.append(c.take(n))
            return out
        c.take(esize * count)
        return count
    fmt = {"u8": "B", "i8": "b", "u16": "H", "i16": "h", "u32": "I", "i32": "i", "f32": "f", "bool": "?",
           "u64": "Q", "i64": "q", "f64": "d"}[name]
    return struct.unpack(f"<{fmt}", c.take(size))[0]


def read_header(source):
    c = Cursor(source)
    magic, version, n_tensors, n_kv = struct.unpack("<IIQQ", c.take(24))
    if magic != GGUF_MAGIC or version != 3:
        raise ValueError(f"not a GGUF v3 file (magic {magic:#x}, version {version})")
    kv_raw, meta = [], {}
    for _ in range(n_kv):
        start = c.pos
        (n,) = struct.unpack("<Q", c.take(8))
        key = c.take(n).decode("utf-8")
        (t,) = struct.unpack("<I", c.take(4))
        v = _skip_value(c, t)
        meta[key] = v
        kv_raw.append((key, c.buf[start - c.base:c.pos - c.base]))
    tensors = []
    for _ in range(n_tensors):
        (n,) = struct.unpack("<Q", c.take(8))
        name = c.take(n).decode("utf-8")
        (nd,) = struct.unpack("<I", c.take(4))
        shape = list(struct.unpack(f"<{nd}Q", c.take(8 * nd)))
        t, off = struct.unpack("<IQ", c.take(12))
        tensors.append({"name": name, "shape": shape, "type": t, "offset": off})
    align = meta.get("general.alignment", 32) or 32
    data_start = (c.pos + align - 1) // align * align
    return {"meta": meta, "kv_raw": kv_raw, "tensors": tensors, "align": align, "data_start": data_start}


def nbytes(t):
    name = GGML_TYPES.get(t["type"], f"type{t['type']}")
    be, bb = BLOCK_GEOMETRY[name]
    n = 1
    for d in t["shape"]:
        n *= d
    if n % be:
        raise ValueError(f"{t['name']}: {n} elements is not a whole number of {name} blocks")
    return n // be * bb


def tname(t):
    return GGML_TYPES.get(t, f"type{t}")


# ---------------------------------------------------------------- Q8_0, as ggml's quantize_row_q8_0_ref
def to_q8_0(raw, src_type, shape):
    import numpy as np
    if src_type == F32:
        x = np.frombuffer(raw, dtype="<f4").astype(np.float32)
    elif src_type == F16:
        x = np.frombuffer(raw, dtype="<f2").astype(np.float32)
    elif src_type == BF16:
        x = (np.frombuffer(raw, dtype="<u2").astype(np.uint32) << 16).view(np.float32)
    else:
        raise ValueError(f"no Q8_0 conversion from {tname(src_type)}")
    if shape[0] % 32:
        raise ValueError(f"row of {shape[0]} is not a multiple of 32")
    b = x.reshape(-1, 32)
    d = np.abs(b).max(axis=1) / 127.0
    inv = np.where(d > 0, 1.0 / np.where(d > 0, d, 1.0), 0.0).astype(np.float32)
    v = b * inv[:, None]
    q = np.trunc(v + np.copysign(np.float32(0.5), v)).astype(np.int8)   # roundf: half away from zero
    out = np.empty(b.shape[0], dtype=[("d", "<f2"), ("q", "i1", 32)])
    out["d"] = d.astype(np.float16)
    out["q"] = q
    return out.tobytes()


# ---------------------------------------------------------------- the checks against the target
GEOM_KEYS = ["embedding_length", "expert_count", "expert_used_count", "expert_feed_forward_length",
             "expert_shared_feed_forward_length", "block_count", "nextn_predict_layers", "attention.head_count",
             "attention.head_count_kv", "attention.key_length", "attention.value_length"]


def check_against(donor, target, prefix):
    problems, notes = [], []
    da, ta = donor["meta"].get("general.architecture"), target["meta"].get("general.architecture")
    if da != ta:
        problems.append(f"architecture {da} vs the target's {ta}")
    for k in GEOM_KEYS:
        dv, tv = donor["meta"].get(f"{da}.{k}"), target["meta"].get(f"{ta}.{k}")
        if dv != tv:
            problems.append(f"{k} {dv} vs the target's {tv}")
    dvoc, tvoc = donor["meta"].get("tokenizer.ggml.tokens"), target["meta"].get("tokenizer.ggml.tokens")
    if isinstance(dvoc, list) and isinstance(tvoc, list):
        if len(dvoc) != len(tvoc):
            problems.append(f"vocabulary {len(dvoc)} tokens vs the target's {len(tvoc)}")
        elif dvoc != tvoc:
            diff = sum(1 for a, b in zip(dvoc, tvoc) if a != b)
            problems.append(f"vocabulary: {diff} token strings differ from the target's")
    tl = {t["name"]: t for t in target["tensors"] if t["name"].startswith(prefix)}
    dl = {t["name"]: t for t in donor["tensors"] if t["name"].startswith(prefix)}
    if set(tl) != set(dl):
        problems.append(f"layer tensors differ: only in the donor {sorted(set(dl) - set(tl))}, "
                        f"only in the target {sorted(set(tl) - set(dl))}")
    for n in sorted(set(tl) & set(dl)):
        if tl[n]["shape"] != dl[n]["shape"]:
            problems.append(f"{n}: shape {dl[n]['shape']} vs the target's {tl[n]['shape']}")
    return problems, notes


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", help="donor GGUF: a path or an https URL")
    ap.add_argument("--target", help="the GGUF the head will draft for (checked against the donor)")
    ap.add_argument("--out", help="the head-only GGUF to write")
    ap.add_argument("--to-q8", choices=["auto", "off"], default="auto",
                    help="re-quantize F16/BF16/F32 projections (which the draft layer cannot read) to Q8_0")
    ap.add_argument("--sha256", help="expected SHA256 of a local donor file (checked before anything is written)")
    ap.add_argument("--allow-unsupported", action="store_true",
                    help="write the head even when its expert types have no kernels in the default CUDA build")
    ap.add_argument("--info", action="store_true", help="print the layer and stop")
    ap.add_argument("--json", action="store_true", help="--info as JSON")
    a = ap.parse_args()

    src = open_source(a.src)
    donor = read_header(src)
    arch = donor["meta"].get("general.architecture")
    n_layers = donor["meta"].get(f"{arch}.block_count", 0) - donor["meta"].get(f"{arch}.nextn_predict_layers", 0)
    if donor["meta"].get(f"{arch}.nextn_predict_layers", 0) < 1:
        sys.exit(f"{a.src}: {arch}.nextn_predict_layers is 0 - the file has no MTP layer")
    prefix = f"blk.{n_layers}."
    layer = [t for t in donor["tensors"] if t["name"].startswith(prefix)]
    if not layer:
        sys.exit(f"{a.src}: no {prefix}* tensors")
    total = sum(nbytes(t) for t in layer)
    by_suffix = {t["name"][len(prefix):]: t["type"] for t in layer}
    unsupported = [f"{k} {tname(by_suffix[k])}" for k, ok in
                   (("ffn_gate_exps.weight", EXPERT_GU), ("ffn_up_exps.weight", EXPERT_GU),
                    ("ffn_down_exps.weight", EXPERT_DOWN)) if k in by_suffix and by_suffix[k] not in ok]
    if a.info:
        rows = [{"name": t["name"], "type": tname(t["type"]), "shape": t["shape"], "bytes": nbytes(t)} for t in layer]
        if a.json:
            print(json.dumps({"arch": arch, "layer": prefix, "bytes": total, "tensors": rows}, indent=1))
        else:
            for r in rows:
                print(f"{r['name']:45s} {r['type']:7s} {r['shape']!s:22s} {r['bytes'] / 1048576:9.1f} MiB")
            print(f"{prefix}*: {len(rows)} tensors, {total / 1048576:.1f} MiB")
        if unsupported:
            print(f"no expert kernels in the default CUDA build for: {', '.join(unsupported)}")
        return 0
    if unsupported and not a.allow_unsupported:
        sys.exit(f"{a.src}: the engine has no expert kernels for {', '.join(unsupported)} "
                 "(the draft layer would not load; --allow-unsupported writes it anyway)")
    if not a.out:
        sys.exit("--out is required (or --info)")

    if a.sha256:
        if not isinstance(src, LocalSource):
            sys.exit("--sha256 needs a local SRC (the whole file is hashed)")
        h = hashlib.sha256()
        with open(src.path, "rb") as fh:
            for blk in iter(lambda: fh.read(64 << 20), b""):
                h.update(blk)
        if h.hexdigest() != a.sha256.lower():
            sys.exit(f"{a.src}: sha256 {h.hexdigest()} is not the expected {a.sha256}")
        print(f"sha256 ok: {a.sha256.lower()}")

    target = None
    if a.target:
        tsrc = open_source(a.target)
        target = read_header(tsrc)
        problems, _ = check_against(donor, target, prefix)
        if problems:
            sys.exit("the donor's draft layer does not fit the target:\n  " + "\n  ".join(problems))
        print(f"the donor fits {a.target}: same geometry, vocabulary and {prefix}* shapes")

    # the tensors: fetched (ranged reads of each tensor), converted where needed
    out_tensors = []
    for t in layer:
        n = nbytes(t)
        raw = src.read(donor["data_start"] + t["offset"], n)
        suffix = t["name"][len(prefix):]
        typ = t["type"]
        if (suffix not in NORMS and len(t["shape"]) == 2 and typ not in GEMV_TYPES and a.to_q8 == "auto"
                and typ in (F16, BF16, F32)):
            raw = to_q8_0(raw, typ, t["shape"])
            print(f"  {t['name']}: {tname(typ)} -> Q8_0 (the draft layer's GEMV cannot read {tname(typ)})")
            typ = Q8_0
        elif suffix not in NORMS and len(t["shape"]) == 2 and typ not in GEMV_TYPES:
            print(f"  warning: {t['name']} is {tname(typ)}, which the draft layer cannot read")
        out_tensors.append({"name": t["name"], "shape": t["shape"], "type": typ, "raw": raw,
                            "src_type": t["type"], "src_sha": hashlib.sha256(raw).hexdigest()})

    if target is not None:
        same = []
        tl = {t["name"]: t for t in target["tensors"] if t["name"].startswith(prefix)}
        for o in out_tensors:
            tt = tl[o["name"]]
            if tt["type"] == o["type"] and nbytes(tt) == len(o["raw"]):
                if hashlib.sha256(tsrc.read(target["data_start"] + tt["offset"], nbytes(tt))).hexdigest() == o["src_sha"]:
                    same.append(o["name"][len(prefix):])
        print(f"byte-identical to the target's layer: {len(same)} of {len(out_tensors)} tensors"
              + (f" ({', '.join(same)})" if same else ""))

    # write: magic, version, counts, the donor's metadata pairs verbatim, the tensor infos, aligned data
    align = donor["align"]
    hdr = io.BytesIO()
    hdr.write(struct.pack("<IIQQ", GGUF_MAGIC, 3, len(out_tensors), len(donor["kv_raw"])))
    for _, raw in donor["kv_raw"]:
        hdr.write(raw)
    off = 0
    offsets = []
    for o in out_tensors:
        offsets.append(off)
        nb = o["name"].encode("utf-8")
        hdr.write(struct.pack("<Q", len(nb)) + nb + struct.pack("<I", len(o["shape"])))
        hdr.write(struct.pack(f"<{len(o['shape'])}Q", *o["shape"]))
        hdr.write(struct.pack("<IQ", o["type"], off))
        off = (off + len(o["raw"]) + align - 1) // align * align
    head = hdr.getvalue()
    pad = (-len(head)) % align
    out = pathlib.Path(a.out)
    tmp = out.with_name(out.name + ".part")
    with open(tmp, "wb") as fh:
        fh.write(head + b"\0" * pad)
        for o, at in zip(out_tensors, offsets):
            cur = fh.tell() - len(head) - pad
            fh.write(b"\0" * (at - cur))
            fh.write(o["raw"])
    os.replace(tmp, out)
    h = hashlib.sha256(out.read_bytes()).hexdigest()
    print(f"wrote {out}: {len(out_tensors)} tensors, {out.stat().st_size / 1048576:.1f} MiB, sha256 {h}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
