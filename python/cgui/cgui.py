#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cgui.py  -- bootstrap
---------------------
Entry point for running cgui from Python source or compiling into a native ELF
executable via Nuitka (`cgui_build_nuitka.py`).
"""

import io
import os
import sys
import time

# Safety net for UTF-8 output under locale=C on old Python
for _stream_name in ("stdout", "stderr"):
    _stream = getattr(sys, _stream_name, None)
    try:
        if _stream is not None and (_stream.encoding is None
                                    or "utf" not in _stream.encoding.lower()):
            setattr(sys, _stream_name,
                    io.TextIOWrapper(_stream.buffer, encoding="utf-8"))
    except Exception:
        pass

_TIMING = (
    os.environ.get("PVFLOW_TIMING") or os.environ.get("CGUI_TIMING")
) not in (None, "", "0")
_T0 = time.time()


def _report(label, since):
    if _TIMING:
        sys.stderr.write("[pvflow] %-34s %6.1f ms\n"
                         % (label, (time.time() - since) * 1000))


_t = time.time()
import cgui_app
_report("import cgui_app", _t)

if __name__ == "__main__":
    if _TIMING:
        os.environ["PVFLOW_START"] = str(_T0)
    sys.exit(cgui_app.main())
