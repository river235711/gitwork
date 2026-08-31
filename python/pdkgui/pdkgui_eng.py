#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pdkgui_eng.py
-------------
Engineer mode: `pdkgui -e ...` -- the command-line side of pdkgui.

This is where the engineer / test features live, so the window keeps its own
shape and the terminal tools keep theirs. Everything here runs in the caller's
terminal (the launcher does not detach `-e`), may ask a question on stdin, and
never opens a pdkgui window.

The first tool is "open a layout with skipper":

    pdkgui -e -p t22_1p7m_4x1z1u top.gds.gz    # process named
    pdkgui -e top.gds.gz                       # terminal asks which process
    pdkgui -e t22_1p7m_4x1z1u top.gds.gz       # shorthand: <process> <gds>

The process is what picks the cds tech / display / layermap: they come from that
process's central SKIPPER.conf, exactly as the SKIPPER tab reads them, so a
command-line open and a tab open give the same viewer.

Engineer mode reads the saved session (the design last chosen on the PROCESS
tab is offered as the default, the ENV tab's skipper/calibre versions are used)
but never writes it: opening one GDS from a terminal should not move the tab the
window opens on next time.

To add another tool, give it a function and an option here; the point of `-e` is
that these do not each need a tab.
"""

import os
import subprocess
import sys

import config

USAGE = """usage: pdkgui -e [options] <gds|gds.gz>        (engineer mode)

Open a layout with skipper from the command line -- no window, no tabs. The
process supplies the cds tech / display / layermap from its central
SKIPPER.conf, the same settings the SKIPPER tab uses.

options:
  -p, --process <name>   process to open the layout with. Without it, the
                         processes are listed in the terminal and you pick one.
  -P, --list-process     print the process list and exit
  -n, --dry-run          print the skipper script instead of running it
  -h, --help             this message

  <process> may also be given as the first of two arguments:
      pdkgui -e <process> <gds>

examples:
  pdkgui -e -p t22_1p7m_4x1z1u top.gds.gz
  pdkgui -e top.gds                 # asks which process
  pdkgui -e -n -p t40lp_1p6m_4x1u top.gds
"""


# --------------------------------------------------------------------------
# process list / chooser
# --------------------------------------------------------------------------
def process_list():
    """The selectable processes -- the same list the PROCESS tab shows."""
    return config.read_lines(config.page_file("PROCESS")) or [config.DESIGN_NAME]


def saved_process():
    """The design last chosen on the PROCESS tab, when it is still listed.

    Only a default for the prompt: someone who works on one process all week
    should be able to answer it with Enter."""
    saved = config.load_json(config.user_global_file("PROCESS")).get("design")
    return saved if saved in process_list() else None


def resolve_process(name):
    """Accept a process name, or its number in the list. None when unknown."""
    values = process_list()
    name = (name or "").strip()
    if name in values:
        return name
    if name.isdigit() and 1 <= int(name) <= len(values):
        return values[int(name) - 1]
    return None


def ask_process():
    """Ask in the terminal which process to use; None if the user gave up.

    Enter takes the default (the last one used on the PROCESS tab, else the
    first listed), so the common case is one keystroke."""
    values = process_list()
    default = saved_process() or values[0]
    sys.stderr.write("\nProcess:\n")
    for i, name in enumerate(values, 1):
        sys.stderr.write("  %2d) %s%s\n"
                         % (i, name, "   [default]" if name == default else ""))
    while True:
        try:
            answer = input("select [1-%d, Enter=%s]: " % (len(values), default))
        except (EOFError, KeyboardInterrupt):
            sys.stderr.write("\n")
            return None
        if not answer.strip():
            return default
        chosen = resolve_process(answer)
        if chosen:
            return chosen
        sys.stderr.write("pdkgui: no such process: %s\n" % answer.strip())


# --------------------------------------------------------------------------
# open a layout with skipper
# --------------------------------------------------------------------------
class _Session(object):
    """What build_skipper_script() needs from the window: the ENV tab's tool
    versions. Defaults from data/env.txt, overlaid with what was last selected
    on the ENV tab -- the same two steps the window does when it starts."""

    def __init__(self):
        from pages.env import env_defaults
        self.env = env_defaults()
        saved = config.load_json(config.user_global_file("ENV"))
        if isinstance(saved, dict):
            for key, value in saved.items():
                if value:
                    self.env[key] = value


def view_gds(process, gds, dry_run=False):
    """Open <gds> with skipper configured for <process>. Returns an exit status."""
    from pages.gdsview import build_skipper_script

    gds = os.path.abspath(os.path.expanduser(gds))
    if not os.path.isfile(gds):
        sys.stderr.write("pdkgui: no such file: %s\n" % gds)
        return 2

    # The whole viewer configuration hangs off the current design, so set it and
    # let the shared builder read it. Nothing is saved, so the window's own
    # PROCESS selection is untouched.
    config.DESIGN_NAME = process
    conf_path = config.central_skipper_conf(process)
    if not os.path.isfile(conf_path):
        sys.stderr.write("pdkgui: warning: no SKIPPER.conf for %s\n"
                         "        (%s)\n"
                         "        opening with -i only; layers will be unmapped.\n"
                         % (process, conf_path))

    script = build_skipper_script(_Session(), gds)
    if dry_run:
        sys.stdout.write(script)
        return 0

    if not os.environ.get("DISPLAY"):
        sys.stderr.write("pdkgui: no DISPLAY, cannot open skipper\n")
        return 1

    try:
        os.makedirs(config.USER_DIR, exist_ok=True)
        sh_path = os.path.join(config.USER_DIR, "skipper_eng.sh")
        with open(sh_path, "w", encoding="utf-8") as f:
            f.write(script)
        os.chmod(sh_path, 0o755)
    except OSError as e:
        sys.stderr.write("pdkgui: failed to write viewer script: %s\n" % e)
        return 1

    sys.stderr.write("pdkgui: %s  <-  %s\n" % (process, gds))
    # Foreground, in the terminal that asked for it: this was typed at a shell,
    # so that shell is where the viewer's output belongs.
    return subprocess.call(["bash", "-l", sh_path])


# --------------------------------------------------------------------------
# command line
# --------------------------------------------------------------------------
def parse_argv(argv):
    """(options, message, status). `message` set means print it and stop."""
    opts = {"process": None, "gds": None, "dry_run": False}
    rest = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("-h", "--help"):
            return None, USAGE, 0
        elif arg in ("-P", "--list-process"):
            return None, "".join(name + "\n" for name in process_list()), 0
        elif arg in ("-n", "--dry-run"):
            opts["dry_run"] = True
        elif arg in ("-p", "--process"):
            i += 1
            if i >= len(argv):
                return None, "pdkgui -e: %s needs a process name\n\n%s" % (arg, USAGE), 2
            opts["process"] = argv[i]
        elif arg.startswith("--process="):
            opts["process"] = arg.split("=", 1)[1]
        elif arg == "--":
            rest += argv[i + 1:]
            break
        elif arg.startswith("-") and arg != "-":
            return None, "pdkgui -e: unknown option %s\n\n%s" % (arg, USAGE), 2
        else:
            rest.append(arg)
        i += 1

    # "<process> <gds>" -- the shorthand, only when -p did not already say
    if len(rest) == 2 and opts["process"] is None:
        opts["process"], rest = rest[0], rest[1:]
    if not rest:
        return None, "pdkgui -e: no GDS given\n\n%s" % USAGE, 2
    if len(rest) > 1:
        return None, ("pdkgui -e: one GDS at a time (got %d: %s)\n\n%s"
                      % (len(rest), " ".join(rest), USAGE)), 2
    opts["gds"] = rest[0]

    if opts["process"] is not None:
        chosen = resolve_process(opts["process"])
        if not chosen:
            return None, ("pdkgui -e: no such process: %s\n\nknown processes:\n%s\n"
                          % (opts["process"],
                             "".join("  " + n + "\n" for n in process_list()))), 2
        opts["process"] = chosen
    return opts, None, 0


def main(argv):
    opts, message, status = parse_argv(list(argv))
    if message:
        (sys.stderr if status else sys.stdout).write(message)
        return status

    process = opts["process"] or ask_process()
    if not process:
        sys.stderr.write("pdkgui: no process chosen, nothing opened\n")
        return 1
    return view_gds(process, opts["gds"], dry_run=opts["dry_run"])
