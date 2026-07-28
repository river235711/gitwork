#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
central_migrate.py -- convert an old central directory to the new layout.

Old central (flat, one file per tab+process):

    <OLD>/.pdkgui.<tab lowercase><PROCESS>.commandfile   the command file
    <OLD>/.pdkgui.<tab lowercase><PROCESS>.fab           'key <value>' per line

New central (one subdirectory per process):

    <NEW>/<PROCESS>/<MODULE>.com     the command file (copied verbatim)
    <NEW>/<PROCESS>/<MODULE>.inc     the deck pointer

.fab -> .inc conversion:

  * DRC / ANT / WB / BUMP / DMDV / DPDO / LVS -- the .inc is the one deck path:

        deck /path/to/CLN22ULP_..._001.19_2a.encrypt
        ->  /path/to/CLN22ULP_..._001.19_2a.encrypt

  * XRC needs four paths, so its .inc is 'key = value'. The rccorner_<corner>
    lines all share one base directory (they only differ in the /<corner>/rules
    tail), and that base is what pdkgui stores as 'rules':

        deck  <DFM_LVS_RC deck>              ->  deck  = <same>
        hcell <.../layout_run/xrc/hcell>     ->  hcell = <same>
        xcell <.../layout_run/xrc/xcell>     ->  xcell = <same>
        rccorner_typical <BASE>/typical/rules
        rccorner_cbest   <BASE>/cbest/rules  ->  rules = <BASE>
        ...

Usage:
    python3 central_migrate.py                     # default paths, dry run
    python3 central_migrate.py --write             # actually write
    python3 central_migrate.py OLD NEW --write
    python3 central_migrate.py --write --force     # also overwrite existing files
"""

import os
import sys
import argparse

import config

OLD_CENTRAL = "/datacenter/techLibs/cad/bin/_pdkgui/current/pdkgui"
NEW_CENTRAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "central_example")

PREFIX = ".pdkgui."
CORNER_KEY = "rccorner_"
CORNER_TAIL = "/rules"

XRC_INC_HEADER = """\
# XRC central files (parsed as 'key = value'; #-comments and blank lines
# ignored). Four keys:
#   hcell / xcell -- the run script does 'ln -sf <path> hcell|xcell'
#   rules         -- the XRC_calibre.<ver> base; pdkgui appends /<corner>/rules
#                    using the XrcRCCorner selection on the XRC tab
#   deck          -- the DFM_LVS_RC deck (second include line)
# On tab open / on Run the XRC command file's two include lines are rewritten
# from 'rules' and 'deck'. To bump a version, edit this one file.
"""


def split_stem(stem):
    """'drct22_1p7m_4x1z1u' -> ('DRC', 't22_1p7m_4x1z1u').

    Module and process are concatenated without a separator, so match the known
    module names (longest first) against the front of the stem."""
    for module in sorted(config.VERIFY_MODULES, key=len, reverse=True):
        low = module.lower()
        if stem.startswith(low) and len(stem) > len(low):
            return module, stem[len(low):]
    return None, None


def read_fab(path):
    """'key <value>' per line -> {key: value} ('#' comments and blanks skipped)."""
    conf = {}
    with open(path, encoding="utf-8", errors="replace") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(None, 1)          # first whitespace run separates
            if len(parts) == 2:
                conf[parts[0]] = parts[1].strip()
    return conf


def rules_base(conf):
    """The 'rules' base, taken from rccorner_typical only -- pdkgui appends
    /<corner>/rules itself, so the other corners carry no extra information
    (they are checked, and reported if they disagree).

    Returns (base, problems)."""
    problems = []
    typical = conf.get(CORNER_KEY + "typical")
    if not typical:
        return None, ["no %stypical line to derive 'rules' from" % CORNER_KEY]
    tail = "/typical" + CORNER_TAIL
    if not typical.endswith(tail):
        return None, ["%stypical does not end with %s: %s"
                      % (CORNER_KEY, tail, typical)]
    base = typical[:-len(tail)]

    for key, value in sorted(conf.items()):
        if not key.startswith(CORNER_KEY) or key == CORNER_KEY + "typical":
            continue
        corner = key[len(CORNER_KEY):]
        expected = "%s/%s%s" % (base, corner, CORNER_TAIL)
        if value != expected:
            problems.append("%s is not under the typical base (%s); dropped"
                            % (key, value))
    return base, problems


def inc_text(module, conf):
    """Build the .inc content for one module. Returns (text, problems)."""
    problems = []
    deck = conf.get("deck")
    if not deck:
        problems.append("no 'deck' line")

    if module != "XRC":
        return (deck + "\n" if deck else None), problems

    base, corner_problems = rules_base(conf)
    problems += corner_problems
    missing = [k for k in ("hcell", "xcell") if not conf.get(k)]
    if missing:
        problems.append("missing %s" % ", ".join(missing))
    if not (deck and base and not missing):
        return None, problems

    text = XRC_INC_HEADER + (
        "hcell = %s\n"
        "xcell = %s\n"
        "rules = %s\n"
        "deck  = %s\n"
    ) % (conf["hcell"], conf["xcell"], base, deck)
    return text, problems


def collect(old_dir):
    """Scan the old central dir.

    Returns ({(module, process): {'com': path, 'fab': path}}, [ignored names]):
    files whose stem starts with no known module (e.g. the DOC ones) are listed
    so nothing disappears silently."""
    found, ignored = {}, []
    for name in sorted(os.listdir(old_dir)):
        if not name.startswith(PREFIX):
            continue
        for suffix, kind in ((".commandfile", "com"), (".fab", "fab")):
            if name.endswith(suffix):
                module, process = split_stem(name[len(PREFIX):-len(suffix)])
                if module:
                    found.setdefault((module, process), {})[kind] = \
                        os.path.join(old_dir, name)
                else:
                    ignored.append(name)
                break
    return found, ignored


def write_file(path, text, write, force):
    """Returns one of: 'written', 'would write', 'exists', 'unchanged'."""
    if os.path.isfile(path):
        with open(path, encoding="utf-8", errors="replace") as f:
            if f.read() == text:
                return "unchanged"
        if not force:
            return "exists"
    if not write:
        return "would write"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return "written"


def main():
    ap = argparse.ArgumentParser(
        description="Convert an old pdkgui central directory to the new layout.")
    ap.add_argument("old", nargs="?", default=OLD_CENTRAL, help="old central dir")
    ap.add_argument("new", nargs="?", default=NEW_CENTRAL, help="new central dir")
    ap.add_argument("--write", action="store_true",
                    help="actually write (default: dry run, only report)")
    ap.add_argument("--force", action="store_true",
                    help="overwrite files that already exist and differ")
    args = ap.parse_args()

    if not os.path.isdir(args.old):
        sys.exit("old central dir not found: %s" % args.old)

    found, ignored = collect(args.old)
    if not found:
        sys.exit("no .pdkgui.*.commandfile / .fab files in %s" % args.old)

    counts, issues = {}, []
    per_process = {}
    for (module, process), src in sorted(found.items()):
        per_process.setdefault(process, []).append(module)
        for kind, ext in (("com", ".com"), ("fab", ".inc")):
            path = src.get(kind)
            if not path:
                issues.append("%s/%s: no %s file" % (process, module, kind))
                continue
            if kind == "com":
                with open(path, encoding="utf-8", errors="replace") as f:
                    text = f.read()
                problems = []
            else:
                text, problems = inc_text(module, read_fab(path))
            for p in problems:
                issues.append("%s/%s: %s" % (process, module, p))
            if text is None:
                continue
            dest = os.path.join(args.new, process, module + ext)
            status = write_file(dest, text, args.write, args.force)
            counts[status] = counts.get(status, 0) + 1
            print("%-11s %s" % (status, os.path.relpath(dest, args.new)))

    print("\n%d process/module pairs from %s" % (len(found), args.old))
    for status in sorted(counts):
        print("  %-11s %d" % (status, counts[status]))

    print("\n%d process(es):" % len(per_process))
    for process in sorted(per_process):
        modules = sorted(per_process[process])
        print("  %-20s %2d modules  %s" % (process, len(modules), " ".join(modules)))

    if ignored:
        print("\nignored (no known module name at the start of the file name):")
        for name in ignored:
            print("  " + name)
    if issues:
        print("\nneeds attention:")
        for i in issues:
            print("  " + i)
    if not args.write:
        print("\n(dry run -- rerun with --write to create the files)")


if __name__ == "__main__":
    main()
