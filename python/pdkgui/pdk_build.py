#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pdk_build.py
------------
Produce the encrypted deploy directory dist/.

  - Business-logic modules (config / widgets / pdkgui_app / pages/*) -> encrypted
    into .pdkc
  - Only the bootstrap and decryptor stay plaintext (pdkgui / pdkgui.py /
    pdkcrypt.py / pdk_secure.py), since they are needed to start and decrypt.
  - data/ is copied as-is.
  - The key is "pinned" into dist/pdkcrypt.py: runtime always uses it and ignores
    env vars, so after deployment you just run it -- no env setup or unset needed.

Usage:
    python3 pdk_build.py [out_dir=dist]

    # to use a custom key (optional): set it at pack time; not needed at runtime.
    PDKGUI_KEY='your-secret' python3 pdk_build.py dist

Deploy: move the whole dist/ to the target machine and run dist/pdkgui.
        `ls` inside dist/ shows only .pdkc -- no logic source.
"""

import io
import os
import re
import sys
import glob
import shutil

# Under locale=C stdout is ASCII and printing non-ASCII raises UnicodeEncodeError;
# wrap stdout/stderr as UTF-8 as a safety net.
for _name in ("stdout", "stderr"):
    _stream = getattr(sys, _name, None)
    try:
        if _stream is not None and (_stream.encoding is None
                                    or "utf" not in _stream.encoding.lower()):
            setattr(sys, _name, io.TextIOWrapper(_stream.buffer, encoding="utf-8"))
    except Exception:
        pass

import pdk_pack
import pdkcrypt

SRC = os.path.dirname(os.path.abspath(__file__))

# Kept plaintext (bootstrap + decryptor + launcher)
PLAINTEXT = ["pdkgui", "pdkgui.py", "pdkcrypt.py", "pdk_secure.py"]

# Top-level modules to encrypt (pages/* collected separately via glob)
ENCRYPT_TOP = ["config.py", "widgets.py", "pdkgui_app.py"]


def _encrypt_to(src_rel, dist):
    src = os.path.join(SRC, src_rel)
    out = os.path.join(dist, src_rel[:-len(".py")] + ".pdkc")
    pdk_pack.pack_file(src, out)
    return out


def build(dist_name="dist"):
    dist = os.path.join(SRC, dist_name)
    if os.path.exists(dist):
        shutil.rmtree(dist)
    os.makedirs(dist)

    # 1. data/ (copied as-is)
    shutil.copytree(os.path.join(SRC, "data"), os.path.join(dist, "data"))

    # 2. copy plaintext files
    for rel in PLAINTEXT:
        s = os.path.join(SRC, rel)
        d = os.path.join(dist, rel)
        os.makedirs(os.path.dirname(d), exist_ok=True)
        shutil.copy2(s, d)

    # 3. encrypt logic modules (with the key active at pack time)
    build_key = pdkcrypt.get_passphrase()
    encrypted = []
    for rel in ENCRYPT_TOP:
        encrypted.append(_encrypt_to(rel, dist))
    for py in sorted(glob.glob(os.path.join(SRC, "pages", "*.py"))):
        encrypted.append(_encrypt_to(os.path.relpath(py, SRC), dist))

    # 4. pin the key into dist/pdkcrypt.py: runtime always uses it and ignores env
    #    vars, so dist runs anywhere regardless of a leftover PDKGUI_KEY -- no unset.
    _pin_key(os.path.join(dist, "pdkcrypt.py"), build_key)

    using_default = (build_key == pdkcrypt.DEFAULT_PASSPHRASE)
    print("deploy build created: %s" % dist)
    print("  key       : pinned into dist/pdkcrypt.py (runtime ignores env vars, no unset)")
    print("  key source: %s" % ("built-in default" if using_default
                                 else "PDKGUI_KEY / key file active at pack time"))
    print("  plaintext : %s" % ", ".join(PLAINTEXT))
    print("  encrypted : %d .pdkc modules" % len(encrypted))
    print("\nDeploy: move the whole dist/ to the target and run it (no env needed):")
    print("  %s/pdkgui" % dist)
    return dist


def _pin_key(pdkcrypt_path, key):
    """Replace `PINNED_KEY = None` in dist/pdkcrypt.py with the actual key."""
    with open(pdkcrypt_path, encoding="utf-8") as f:
        src = f.read()
    new_line = "PINNED_KEY = %r" % key
    if "PINNED_KEY = None" in src:
        src = src.replace("PINNED_KEY = None", new_line, 1)
    else:
        src = re.sub(r'(?m)^PINNED_KEY\s*=.*$', new_line, src, count=1)
    with open(pdkcrypt_path, "w", encoding="utf-8") as f:
        f.write(src)


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "dist")
