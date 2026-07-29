#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_runs.py
------------
Generates a run folder per tab per option, ready to be run for real.

The unit tests check that pdkgui writes the right command files; this answers
the next question -- whether calibre actually accepts them. It drives pdkgui
itself (opens each tab, sets one option, presses Run), so what lands in each
folder is exactly what a user would get, and it keeps working when pdkgui's
generation changes.

One option is varied at a time from the defaults, so a failure names the option
that caused it. The cases come from the widgets, not from a list here: every
dropdown value and every checkbox produces a case, so adding an option to
pdkgui adds a case automatically.

    python3 make_runs.py --out ~/pdkgui_runs
    python3 make_runs.py --out ~/pdkgui_runs --process t22_1p7m_4x1z1u
    python3 make_runs.py --out ~/pdkgui_runs --tabs XRC,LVS
    python3 make_runs.py --out ~/pdkgui_runs \
        --layout /path/top.gds --primary top \
        --source /path/top.cdl --source-primary top --netlist /path/top.lump

Reads the central directory pdkgui is configured for (--central overrides) and
writes nothing outside --out: the session goes to <out>/.session, never to
~/.pdkgui.
"""

import os
import sys
import shutil
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SRC = os.path.normpath(os.path.join(HERE, os.pardir, "pdkgui"))

RUN_ALL = "run_all"
INDEX = "cases.txt"
SESSION_DIR = ".session"

# tabs that have a Run button, in menu order; JIVARO only when --netlist is given
VERIFY_TABS = ("DRC", "ANT", "WB", "BUMP", "DMDV", "DPDO", "LVS", "XRC", "JIVARO")


# --------------------------------------------------------------------------
# cases
# --------------------------------------------------------------------------
class Case(object):
    """One run folder: the options to set, and why."""

    def __init__(self, name, settings=None, action="run", note=""):
        self.name = name
        self.settings = settings or {}     # field -> value
        self.action = action               # "run" or "rve"
        self.note = note

    def __repr__(self):
        return "Case(%s)" % self.name


def cases_for(page, with_rve=False):
    """Baseline, then one case per option value.

    Derived from the page's widgets so it follows pdkgui rather than a list
    kept in step by hand.

    Rve is left out unless asked for: `calibre -rve` opens the interactive
    results viewer, so a batch run of those cases would just fill the screen
    with windows (and there are no results to view before the runs happen)."""
    import tkinter as tk
    from tkinter import ttk

    found = [Case("baseline", note="defaults as they come from central")]
    for key, widget in sorted(page.entries.items()):
        if isinstance(widget, ttk.Combobox):
            default = widget.get()
            for value in widget.cget("values"):
                if value != default:
                    found.append(Case("%s_%s" % (key, value), {key: value},
                                      note="%s = %s (default %s)"
                                           % (key, value, default)))
        elif isinstance(widget, tk.BooleanVar):
            flipped = not widget.get()
            found.append(Case("%s_%s" % (key, "on" if flipped else "off"),
                              {key: flipped},
                              note="%s %s (default %s)"
                                   % (key, "ticked" if flipped else "unticked",
                                      "on" if widget.get() else "off")))
    # only where the page actually offers it -- JIVARO has no Rve button
    if with_rve and has_button(page, "Rve"):
        found.append(Case("rve", action="rve", note="what the Rve button writes"))
    return found


def has_button(parent, label):
    for child in parent.winfo_children():
        if child.winfo_class() == "Button" and child.cget("text") == label:
            return True
        if has_button(child, label):
            return True
    return False


# --------------------------------------------------------------------------
# generation
# --------------------------------------------------------------------------
def generate(app, out_dir, processes, tabs, fields, netlist, with_rve=False):
    """Write every case; return [(process, tab, case, folder)]."""
    import config

    written = []
    for process in processes:
        app.set_design(process)
        for tab in tabs:
            if tab == "JIVARO" and not netlist:
                continue
            page = app.show_module(tab) or app._page
            app.update()

            for case in cases_for(page, with_rve):
                folder = os.path.join(out_dir, process, tab, case.name)
                _make(folder)
                _apply(app, page, folder, fields, netlist, case)
                _write_case_note(folder, process, tab, case)
                written.append((process, tab, case, folder))
                # the next case starts from a clean page
                page = app.show_module(tab) or app._page
                app.update()
    return written


def _apply(app, page, folder, fields, netlist, case):
    """Set the fields for one case and press its button."""
    for key, value in fields.items():
        if key in page.entries:
            _set(app, page, key, value)
    if netlist and "File" in page.entries:
        _set(app, page, "File", netlist)

    _set(app, page, "RunFolder", folder)
    for key, value in case.settings.items():
        _set(app, page, key, value)

    if case.action == "rve":
        page._on_rve()
    else:
        page._on_run()
    app.update()


def _set(app, page, key, value):
    """Change a field the way the GUI does (widget, then its handler)."""
    import tkinter as tk
    from tkinter import ttk

    widget = page.entries[key]
    if isinstance(widget, tk.BooleanVar):
        widget.set(bool(value))
        page._schedule_save()
    elif isinstance(widget, ttk.Combobox):
        widget.set(value)
        page._on_field_change(key)
    else:
        widget.delete(0, "end")
        widget.insert(0, value)
        page._on_field_change(key)
    app.update()


def _write_case_note(folder, process, tab, case):
    with open(os.path.join(folder, "case.txt"), "w", encoding="utf-8") as f:
        f.write("process : %s\ntab     : %s\ncase    : %s\naction  : %s\n"
                % (process, tab, case.name, case.action))
        f.write("varies  : %s\n" % (case.note or "-"))
        for key, value in sorted(case.settings.items()):
            f.write("          %s = %s\n" % (key, value))


def _make(path):
    if os.path.isdir(path):
        shutil.rmtree(path)
    os.makedirs(path)


# --------------------------------------------------------------------------
# the run_all script and the index
# --------------------------------------------------------------------------
RUN_ALL_TEXT = """\
#!/bin/bash
# Runs every generated case. Written by make_runs.py -- regenerate, do not edit.
#
#   ./run_all                run every case that has not passed yet
#   ./run_all -n             list what would run, run nothing
#   ./run_all -a             run all of them, including ones that passed before
#   ./run_all -j 4           run four at a time
#   ./run_all -x             stop at the first failure
#   ./run_all XRC t22        only cases whose path contains all of these
#   ./run_all -s             show the results of the last run
#
# Every case keeps its own run.log, and its outcome in .status, so a second
# ./run_all picks up where the last one stopped instead of repeating hours of
# calibre. Rve is not among the cases: it opens the interactive results viewer.
set -u
cd "$(dirname "$0")" || exit 1

list_only=0; stop_on_fail=0; rerun_all=0; summary=0; jobs=1
while [ $# -gt 0 ]; do
    case "$1" in
        -n) list_only=1; shift ;;
        -a) rerun_all=1; shift ;;
        -x) stop_on_fail=1; shift ;;
        -s) summary=1; shift ;;
        -j) jobs="$2"; shift 2 ;;
        -j*) jobs="${1#-j}"; shift ;;
        -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
        --) shift; break ;;
        *) break ;;
    esac
done

all_cases=$(find . -name run -type f | sed 's|/run$||' | sort)
for pattern in "$@"; do
    all_cases=$(printf '%s\\n' "$all_cases" | grep -- "$pattern" || true)
done

if [ "$summary" = 1 ]; then
    for dir in $all_cases; do
        status=$(cat "$dir/.status" 2>/dev/null || echo "not run")
        printf '%-58s %s\\n' "${dir#./}" "$status"
    done
    exit 0
fi

# skip what already passed, unless -a
cases=""
for dir in $all_cases; do
    if [ "$rerun_all" = 0 ] && [ "$(cat "$dir/.status" 2>/dev/null)" = "ok" ]; then
        continue
    fi
    cases="$cases $dir"
done

total=$(printf '%s\\n' $cases | grep -c . || true)
if [ "$list_only" = 1 ]; then
    for dir in $cases; do echo "$dir"; done
    echo
    echo "$total case(s) to run; run without -n to execute them"
    exit 0
fi
if [ "$total" = 0 ]; then
    echo "nothing to run (use -a to repeat the ones that already passed)"
    exit 0
fi

run_one() {
    dir="$1"
    start=$(date +%s)
    if (cd "$dir" && ./run) > "$dir/run.log" 2>&1; then
        echo ok > "$dir/.status"
        printf '%-58s ok    (%ss)\\n' "${dir#./}" "$(( $(date +%s) - start ))"
    else
        echo failed > "$dir/.status"
        printf '%-58s FAIL  (%ss)  see %s\\n' "${dir#./}" \\
               "$(( $(date +%s) - start ))" "$dir/run.log"
    fi
}

echo "$total case(s), $jobs at a time"
echo
if [ "$jobs" -gt 1 ]; then
    running=0
    for dir in $cases; do
        run_one "$dir" &
        running=$((running + 1))
        if [ "$running" -ge "$jobs" ]; then wait -n 2>/dev/null || wait; running=$((running - 1)); fi
    done
    wait
else
    for dir in $cases; do
        run_one "$dir"
        if [ "$stop_on_fail" = 1 ] && [ "$(cat "$dir/.status")" = failed ]; then
            echo; echo "stopped at the first failure"; break
        fi
    done
fi

passed=0; failed=0; failures=""
for dir in $cases; do
    case "$(cat "$dir/.status" 2>/dev/null)" in
        ok)     passed=$((passed + 1)) ;;
        failed) failed=$((failed + 1)); failures="$failures $dir" ;;
    esac
done

echo
echo "$passed ok, $failed failed (of $total)"
if [ -n "$failures" ]; then
    echo "failed:"
    for dir in $failures; do echo "  $dir"; done
    echo
    echo "fix, then ./run_all repeats only these"
    exit 1
fi
"""


def write_run_all(out_dir):
    path = os.path.join(out_dir, RUN_ALL)
    with open(path, "w", encoding="utf-8") as f:
        f.write(RUN_ALL_TEXT)
    os.chmod(path, 0o755)
    return path


def write_index(out_dir, written, central):
    path = os.path.join(out_dir, INDEX)
    with open(path, "w", encoding="utf-8") as f:
        f.write("pdkgui run cases\n")
        f.write("central: %s\n" % central)
        f.write("%d case(s); each folder holds the command file, run, case.txt\n\n"
                % len(written))
        for process, tab, case, folder in written:
            f.write("%-22s %-8s %-24s %s\n"
                    % (process, tab, case.name, case.note))
    return path


# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(
        description="Generate a run folder per pdkgui tab per option.")
    ap.add_argument("--out", required=True, help="directory to write the cases in")
    ap.add_argument("--src", help="pdkgui source directory (default ../pdkgui)")
    ap.add_argument("--central", help="central directory (default: pdkgui's own)")
    ap.add_argument("--process", action="append",
                    help="only this process (repeatable; default: all of them)")
    ap.add_argument("--tabs", help="comma separated tabs (default: all with a Run)")
    ap.add_argument("--layout", help="LayoutPath for every case")
    ap.add_argument("--primary", help="LayoutPrimary for every case")
    ap.add_argument("--source", help="SourcePath for every case")
    ap.add_argument("--source-primary", dest="source_primary",
                    help="SourcePrimary for every case")
    ap.add_argument("--netlist", help="File for the JIVARO tab (enables its case)")
    ap.add_argument("--with-rve", dest="with_rve", action="store_true",
                    help="also generate the Rve cases (they open the interactive "
                         "results viewer, so they are left out of a batch)")
    args = ap.parse_args()

    src = os.path.abspath(args.src or os.environ.get("PDKGUI_SRC") or DEFAULT_SRC)
    if not os.path.isfile(os.path.join(src, "pdkgui_app.py")):
        sys.exit("pdkgui source not found in %s (use --src)" % src)

    out_dir = os.path.abspath(args.out)
    os.makedirs(out_dir, exist_ok=True)
    # keep the generator away from the real ~/.pdkgui
    os.environ["PDKGUI_USER_DIR"] = os.path.join(out_dir, SESSION_DIR)
    if args.central:
        os.environ["PDKGUI_DEFAULT_DIR"] = os.path.abspath(args.central)

    sys.path.insert(0, HERE)
    sys.path.insert(0, src)
    try:
        import tkinter                                   # noqa: F401
    except ImportError:
        sys.exit("This python has no tkinter -- run it the way run_tests.py does\n"
                 "(module load python/3.6.3), or set PDKGUI_PYTHON.")
    if not os.environ.get("DISPLAY"):
        sys.exit("No DISPLAY: pdkgui builds Tk widgets even to write files.\n"
                 "Run in an X session, or under Xvfb.")

    import config
    import stubs
    import pdkgui_app

    central = config.DEFAULT_COM_DIR
    processes = args.process or config.read_lines(config.page_file("PROCESS"))
    if not processes:
        sys.exit("no processes configured (central: %s)" % central)
    tabs = ([t.strip().upper() for t in args.tabs.split(",")] if args.tabs
            else list(VERIFY_TABS))

    fields = {}
    for key, value in (("LayoutPath", args.layout), ("LayoutPrimary", args.primary),
                       ("SourcePath", args.source),
                       ("SourcePrimary", args.source_primary)):
        if value:
            fields[key] = value

    print("pdkgui  : %s" % src)
    print("central : %s" % central)
    print("out     : %s" % out_dir)
    print("process : %s" % ", ".join(processes))
    print("tabs    : %s\n" % ", ".join(tabs))

    installed = stubs.Installer().install(quiet_terminal=True,
                                          auto_confirm_update=True)
    app = pdkgui_app.PdkGui()
    app.withdraw()
    try:
        written = generate(app, out_dir, processes, tabs, fields,
                           args.netlist, args.with_rve)
    finally:
        try:
            app._on_close()
        except Exception:
            pass
        installed.restore()

    write_run_all(out_dir)
    write_index(out_dir, written, central)

    for process in processes:
        count = len([w for w in written if w[0] == process])
        print("  %-22s %3d case(s)" % (process, count))
    print("\n%d case(s) written." % len(written))
    if not args.netlist:
        print("JIVARO skipped -- pass --netlist <file.lump> to include it.")
    print("\n  cd %s && ./run_all -n     # list them" % out_dir)
    print("  cd %s && ./run_all        # run them" % out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
