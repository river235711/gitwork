#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_tests.py
------------
Runs the pdkgui tab tests.

    python3 run_tests.py                 # everything
    python3 run_tests.py xrc doc         # only tests whose file matches
    python3 run_tests.py -v              # one line per test
    python3 run_tests.py --keep          # leave .sandbox behind to inspect

Order matters at import time: the sandbox is built and its paths are put in the
environment *before* pdkgui's config is imported, because config reads
PDKGUI_USER_DIR / PDKGUI_DEFAULT_DIR and friends into constants right then.

Tk needs a display. With none, Xvfb is started when available, otherwise the run
stops with an explanation rather than a confusing Tk error.
"""

import os
import sys
import atexit
import shutil
import argparse
import subprocess
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SRC = os.path.normpath(os.path.join(HERE, os.pardir, "pdkgui"))
_REEXEC_FLAG = "PDKGUI_TEST_REEXEC"      # guards against re-running in a loop


def _find_source(explicit):
    src = explicit or os.environ.get("PDKGUI_SRC") or DEFAULT_SRC
    src = os.path.abspath(src)
    if not os.path.isfile(os.path.join(src, "pdkgui_app.py")):
        sys.exit("pdkgui source not found in %s\n"
                 "Pass --src /path/to/pdkgui or set PDKGUI_SRC." % src)
    return src


def _ensure_tkinter():
    """Re-run under a python that has tkinter, the way the pdkgui launcher does.

    The EDA hosts' system python3 has no tkinter -- it comes from a module
    (python/3.6.3 by default, PDKGUI_MODULE to pick another, or PDKGUI_PYTHON to
    name an interpreter directly). Without this, the run dies with a confusing
    ImportError inside the first test instead of just working."""
    try:
        import tkinter                                    # noqa: F401
        return
    except ImportError:
        pass
    if os.environ.get(_REEXEC_FLAG):
        sys.exit("This python has no tkinter, and loading %s did not provide one.\n"
                 "Point PDKGUI_PYTHON at an interpreter that has it, or\n"
                 "PDKGUI_MODULE at the right module."
                 % os.environ.get("PDKGUI_MODULE", "python/3.6.3"))

    os.environ[_REEXEC_FLAG] = "1"
    argv = " ".join(_quote(a) for a in [sys.argv[0]] + sys.argv[1:])
    module = os.environ.get("PDKGUI_MODULE", "python/3.6.3")
    python = os.environ.get("PDKGUI_PYTHON", "python3")
    script = (
        'for _i in "$MODULESHOME/init/bash" /usr/share/Modules/init/bash '
        '/etc/profile.d/modules.sh /usr/share/lmod/lmod/init/bash; do\n'
        '  [ -f "$_i" ] && . "$_i" && break\n'
        'done\n'
        'type module >/dev/null 2>&1 && module load %s >/dev/null 2>&1\n'
        'exec %s %s\n'
    ) % (_quote(module), _quote(python), argv)
    print("no tkinter in this python -- reloading via module %s\n" % module)
    sys.stdout.flush()          # exec replaces us; unflushed output would be lost
    os.execvp("bash", ["bash", "-lc", script])


def _quote(arg):
    return "'" + str(arg).replace("'", "'\\''") + "'"


def _ensure_display():
    """Return a description of the display, or exit with advice."""
    if os.environ.get("DISPLAY"):
        return "DISPLAY=%s" % os.environ["DISPLAY"]
    if not shutil.which("Xvfb"):
        sys.exit("No DISPLAY and no Xvfb.\n"
                 "These tests drive a real Tk window, so run them in an X\n"
                 "session (or install Xvfb for a headless run).")
    display = ":99"
    proc = subprocess.Popen(["Xvfb", display, "-screen", "0", "1600x1200x24"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    atexit.register(proc.terminate)
    os.environ["DISPLAY"] = display
    return "Xvfb on %s" % display


def main():
    ap = argparse.ArgumentParser(description="Run the pdkgui tab tests.")
    ap.add_argument("pattern", nargs="*",
                    help="only run test files whose name contains one of these")
    ap.add_argument("--src", help="pdkgui source directory (default ../pdkgui)")
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--keep", action="store_true",
                    help="keep .sandbox after the run (to look at what was written)")
    args = ap.parse_args()

    src = _find_source(args.src)
    _ensure_tkinter()            # may re-exec this script and not return
    display = _ensure_display()

    sys.path.insert(0, HERE)          # harness, sandbox
    sys.path.insert(0, src)           # config, pdkgui_app, pages, widgets

    import sandbox
    paths = sandbox.build(src)        # so the env is right at import time
    sandbox.apply_env(paths)
    os.environ["PDKGUI_SRC"] = src

    import harness
    harness.SRC_DIR = src

    print("pdkgui   : %s" % src)
    print("sandbox  : %s" % paths["sandbox"])
    print("display  : %s\n" % display)

    loader = unittest.TestLoader()
    suite = loader.discover(os.path.join(HERE, "tests"), pattern="test_*.py",
                            top_level_dir=HERE)
    if args.pattern:
        suite = _filter(suite, args.pattern)

    result = unittest.TextTestRunner(verbosity=2 if args.verbose else 1).run(suite)

    if not args.keep:
        shutil.rmtree(paths["sandbox"], ignore_errors=True)
    else:
        print("\nsandbox kept: %s" % paths["sandbox"])
    return 0 if result.wasSuccessful() else 1


def _filter(suite, patterns):
    """Keep tests whose id mentions one of the patterns."""
    keep = unittest.TestSuite()
    for test in _flatten(suite):
        if any(p.lower() in test.id().lower() for p in patterns):
            keep.addTest(test)
    return keep


def _flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            for sub in _flatten(item):
                yield sub
        else:
            yield item


if __name__ == "__main__":
    sys.exit(main())
