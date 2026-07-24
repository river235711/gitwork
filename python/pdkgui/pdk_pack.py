#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pdk_pack.py
-----------
Encrypt and pack a single .py source file into a .pdkc file.

Usage:
    python3 pdk_pack.py <src.py> [out.pdkc]       # e.g. python3 pdk_pack.py config.py config.pdkc

    # with a custom key (optional):
    PDKGUI_KEY=my-secret python3 pdk_pack.py config.py config.pdkc

You normally do not need this directly; for a full encrypted deploy build use
pdk_build.py.

Flow: read source -> syntax check (compile) -> zlib compress -> encrypt -> write.
(It encrypts the source text, not version-specific bytecode, so it is portable
across Python versions.)
"""

import io
import os
import sys
import zlib

# Safety net for printing under locale=C (wrap stdout/stderr as UTF-8)
for _name in ("stdout", "stderr"):
    _stream = getattr(sys, _name, None)
    try:
        if _stream is not None and (_stream.encoding is None
                                    or "utf" not in _stream.encoding.lower()):
            setattr(sys, _name, io.TextIOWrapper(_stream.buffer, encoding="utf-8"))
    except Exception:
        pass

import pdkcrypt


def pack_source(src_text, filename="<pdkc>"):
    """Compress + encrypt source text, returning the .pdkc file content (bytes)."""
    compile(src_text, filename, "exec")           # verify syntax first
    compressed = zlib.compress(src_text.encode("utf-8"), 9)
    return pdkcrypt.encrypt(compressed)


def pack_file(src_path, out_path=None):
    if out_path is None:
        out_path = os.path.splitext(src_path)[0] + ".pdkc"
    with open(src_path, encoding="utf-8") as f:
        src_text = f.read()
    blob = pack_source(src_text, src_path)
    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(blob)
    return out_path


def main(argv):
    if len(argv) < 2:
        sys.stderr.write(__doc__)
        return 2
    src = argv[1]
    out = argv[2] if len(argv) > 2 else None
    out_path = pack_file(src, out)
    key_src = "PDKGUI_KEY env var" if os.environ.get("PDKGUI_KEY") else "built-in default key"
    print("encrypted: %s -> %s  (key source: %s)" % (src, out_path, key_src))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
