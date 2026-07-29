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

# PDKGUI_TIMING=1 reports what start-up costs. Measured here rather than in
# config, because loading config is itself part of what we want to see -- in a
# deployed build that means fetching and decrypting it from NFS.
_TIMING = os.environ.get("PDKGUI_TIMING") not in (None, "", "0")
_T0 = __import__("time").time()


def _report(label, since):
    if _TIMING:
        import time
        sys.stderr.write("[pdkgui] %-34s %6.1f ms\n"
                         % (label, (time.time() - since) * 1000))


import pdk_secure

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Install the encrypted-module loader (takes over only when .pdkc exist;
# skipped automatically in a plain source checkout)
pdk_secure.install_import_hook(BASE_DIR)
_report("python up + import hook", _T0)

_t = __import__("time").time()
import pdkgui_app
_report("import pdkgui_app", _t)

if __name__ == "__main__":
    if _TIMING:
        os.environ["PDKGUI_START"] = str(_T0)    # so the app can report the total
    pdkgui_app.main()
