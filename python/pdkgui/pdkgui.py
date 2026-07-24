#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pdkgui.py  -- bootstrap (plaintext, no business logic)
------------------------------------------------------
This is the only entry point that must stay plaintext. It does two things:

  1. Install the "encrypted-module import hook" -- afterwards importing config /
     widgets / pages / pdkgui_app etc. transparently decrypts and loads the
     .pdkc files in the same directory (deployed build).
  2. Import and run the main program pdkgui_app.main().

In a source (development) checkout there are no .pdkc files, so the import hook
does not intercept and Python loads the plaintext .py normally -- the same
bootstrap therefore works for both development and deployment.

The actual program logic lives in pdkgui_app / config / widgets / pages; in a
deployed build these are the encrypted .pdkc files (see pdk_build.py).
"""

import io
import os
import sys

# Safety net for Chinese-free UTF-8 output under locale=C on old Python
try:
    if sys.stdout.encoding is None or "utf" not in sys.stdout.encoding.lower():
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
except Exception:
    pass

import pdk_secure

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Install the encrypted-module loader (takes over only when .pdkc exist;
# skipped automatically in a plain source checkout)
pdk_secure.install_import_hook(BASE_DIR)

import pdkgui_app

if __name__ == "__main__":
    pdkgui_app.main()
