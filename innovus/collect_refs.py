#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Collect an EDA config file and every file it references, recursively.

    collect_refs.py <input_file> <output_dir> [options]

The input file is copied to <output_dir>/<basename>.  Every referenced file is
copied to the location that keeps its path *relative to the input file* intact:

    dest = normpath(join(output_dir, relpath(src, dirname(input_file))))

so with input ~/proj/run1/top.globals and output ./xxx/run1 a reference to
../ref/foo.tlef lands in ./xxx/ref/foo.tlef .  Copied files are scanned in turn
(source / include / `include / read_* / *_file ... ), so the whole hierarchy is
walked.  File contents are never rewritten -- the relative structure is
preserved, so the copy runs as-is.

Everything written is guaranteed to stay inside <output_dir>/.. (see
--up-levels); references reaching further up (absolute paths into /opt, ...)
are reported as EXTERNAL and skipped unless --external copy is given.

Python 3.6+, standard library only.
"""

from __future__ import print_function

import argparse
import filecmp
import fnmatch
import glob as globmod
import os
import re
import shutil
import sys
from collections import deque

# ---------------------------------------------------------------- constants

# Tcl/SDC/verilog word separators: whitespace plus the grouping characters, so
#   set init_lef_file {../ref/a.tlef ../ref/b.lef}
#   -sdc_files [list ../ref/x.sdc]
# both flatten to plain tokens.
TOKEN_SPLIT = re.compile(r"[\s{}\[\]\"';,()]+")

SET_RE = re.compile(r"^\s*set\s+(\S+)\s+(.*)$")
VAR_RE = re.compile(r"\$\{(\w+)\}|\$(\w+)")
EXT_RE = re.compile(r"\.[A-Za-z0-9_+\-]{1,15}$")

# Directive words: a token after one of these is a *declared* reference and is
# reported as MISSING when it cannot be found on disk.
DIRECTIVE_WORDS = frozenset(
    ["source", "include", "`include", "file", "f", "read", "import"]
)

# Not worth scanning for further references (binary or bulk data).
BINARY_EXT = frozenset(
    """.gds .gds2 .gz .bz2 .xz .tar .tgz .zip .oa .db .dat .png .jpg .pdf
       .lib .lef .tlef .spef .sdf .cdb .so .a .o .pyc""".split()
)

DEFAULT_MAX_SCAN = 32 * 1024 * 1024
DEFAULT_MAX_DIR = 2 * 1024 * 1024 * 1024
MANIFEST_NAME = "collect_refs.manifest"


def human(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return "%.0f%s" % (n, unit) if unit == "B" else "%.1f%s" % (n, unit)
        n /= 1024.0


def is_number(tok):
    try:
        float(tok)
        return True
    except ValueError:
        return False


def looks_like_path(tok):
    """Cheap filter so that flags, numbers and bare words are not probed."""
    if not tok or tok in (".", "..", "/"):
        return False
    if tok.startswith("-") or tok.startswith("`") or tok.startswith("$"):
        return False
    if is_number(tok):
        return False
    return "/" in tok or EXT_RE.search(tok) is not None


def is_directive(tok):
    if "/" in tok or looks_like_path(tok):
        return False        # e.g. ../ref/RC_QRC_rcworst.tar.gz_FILE
    t = tok.lstrip("-").lower()
    if t in DIRECTIVE_WORDS:
        return True
    if t.startswith("read_"):
        return True
    return t.endswith("_file") or t.endswith("_files")


# ---------------------------------------------------------------- collector


class Collector(object):
    def __init__(self, args):
        # Paths are kept as written (abspath, symlinks intact), never
        # realpath'd: EDA trees routinely have ref -> /proj/.../ref, and
        # resolving that would push every reference outside the tree.
        # realpath is used only to recognise a file already visited.
        self.in_file = os.path.abspath(args.input_file)
        self.in_dir = os.path.dirname(self.in_file)
        self.out_dir = os.path.abspath(args.output_dir)
        self.up_levels = args.up_levels
        self.external_mode = args.external
        self.scan_all = args.scan_all
        self.max_scan = args.max_scan_size
        self.max_dir = args.max_dir_size
        self.dry_run = args.dry_run
        self.verbose = args.verbose
        self.overwrite = args.overwrite
        self.manifest = os.path.abspath(args.manifest) if args.manifest else None
        self.search_dirs = [os.path.abspath(d) for d in (args.search or [])]
        self.whole_dir = args.whole_dir or []

        self.queue = deque()
        self.seen = set()          # realpaths already queued (cycle guard)
        self.copied = []           # (src, dest)
        self.dirs = []             # (src, dest, nfiles, nbytes)
        self.missing = []          # (where, line, token)
        self.external = []         # (where, line, path)
        self.skipped_scan = []     # (src, reason)
        self.unresolved = []       # (where, line, token)
        self._reported = set()     # dedupe for the report lists

    # -- logging ----------------------------------------------------------

    def log(self, msg):
        if self.verbose:
            print(msg)

    def note(self, bucket, where, line, text):
        key = (id(bucket), where, line, text)
        if key not in self._reported:
            self._reported.add(key)
            bucket.append((where, line, text))

    def rel_in(self, path):
        """Path relative to the input dir, for readable messages."""
        try:
            return os.path.relpath(path, self.in_dir)
        except ValueError:
            return path

    # -- destination mapping ----------------------------------------------

    def dest_for(self, src):
        rel = os.path.relpath(src, self.in_dir)
        ups = 0
        for part in rel.split(os.sep):
            if part == os.pardir:
                ups += 1
            else:
                break
        if ups > self.up_levels:
            if self.external_mode == "copy":
                return os.path.join(
                    self.out_dir, "_external", src.lstrip(os.sep)
                ), True
            return None, True
        return os.path.normpath(os.path.join(self.out_dir, rel)), False

    # -- copying ----------------------------------------------------------

    def copy_file(self, src, dest):
        if os.path.exists(dest):
            if filecmp.cmp(src, dest, shallow=False):
                self.log("  same, skip: %s" % dest)
                self.copied.append((src, dest))
                return
            if not self.overwrite:
                print("warning: overwriting differing file: %s" % dest,
                      file=sys.stderr)
        if not self.dry_run:
            parent = os.path.dirname(dest)
            if parent and not os.path.isdir(parent):
                os.makedirs(parent)
            shutil.copy2(src, dest)
        self.copied.append((src, dest))

    def dir_size(self, src):
        nfiles = 0
        nbytes = 0
        for root, dirnames, filenames in os.walk(src):
            for name in filenames:
                p = os.path.join(root, name)
                nfiles += 1
                try:
                    nbytes += os.path.getsize(p)
                except OSError:
                    pass
            if nbytes > self.max_dir:
                break
        return nfiles, nbytes

    def copy_dir(self, src, dest):
        """Recursive copy that merges into an existing destination."""
        nfiles, nbytes = self.dir_size(src)
        if nbytes > self.max_dir:
            print("warning: directory too large, skipped (%s > %s): %s"
                  % (human(nbytes), human(self.max_dir), src), file=sys.stderr)
            self.skipped_scan.append((src, "directory > max-dir-size"))
            return
        for root, dirnames, filenames in os.walk(src):
            rel = os.path.relpath(root, src)
            target = dest if rel == "." else os.path.join(dest, rel)
            if not self.dry_run and not os.path.isdir(target):
                os.makedirs(target)
            for name in filenames:
                s = os.path.join(root, name)
                if not self.dry_run:
                    d = os.path.join(target, name)
                    if not os.path.exists(d) or not filecmp.cmp(
                            s, d, shallow=False):
                        shutil.copy2(s, d)
                # already copied as part of the tree; queue only for scanning
                self.enqueue(s, do_copy=False)
        self.dirs.append((src, dest, nfiles, nbytes))

    # -- scanning ---------------------------------------------------------

    def scannable(self, path):
        ext = os.path.splitext(path)[1].lower()
        if not self.scan_all and ext in BINARY_EXT:
            return False, "binary/bulk extension %s" % ext
        try:
            size = os.path.getsize(path)
        except OSError as exc:
            return False, str(exc)
        if size > self.max_scan:
            return False, "%s > max-scan-size" % human(size)
        try:
            with open(path, "rb") as fh:
                if b"\0" in fh.read(8192):
                    return False, "binary content"
        except IOError as exc:
            return False, str(exc)
        return True, ""

    def logical_lines(self, path):
        """Yield (lineno, line) with trailing-backslash continuations joined."""
        buf = ""
        start = 0
        with open(path, "r", errors="replace") as fh:
            for lineno, raw in enumerate(fh, 1):
                raw = raw.rstrip("\r\n")
                if not buf:
                    start = lineno
                if raw.endswith("\\"):
                    buf += raw[:-1] + " "
                    continue
                buf += raw
                yield start, buf
                buf = ""
        if buf:
            yield start, buf

    def var_map(self, lines):
        """Best-effort `set NAME VALUE` table for $VAR substitution."""
        table = {}
        for _, line in lines:
            m = SET_RE.match(line)
            if m:
                value = m.group(2).strip().strip("{}").strip('"').strip()
                if " " not in value:
                    table[m.group(1)] = value
        return table

    def substitute(self, tok, table):
        for _ in range(4):
            if "$" not in tok:
                break

            def repl(m):
                name = m.group(1) or m.group(2)
                if name in table:
                    return table[name]
                return os.environ.get(name, m.group(0))

            new = VAR_RE.sub(repl, tok)
            if new == tok:
                break
            tok = new
        return tok

    def candidates(self, path):
        """Yield (lineno, token, declared) for every path-looking token."""
        lines = list(self.logical_lines(path))
        table = self.var_map(lines)
        for lineno, line in lines:
            stripped = line.lstrip()
            if stripped.startswith("#") or stripped.startswith("//"):
                continue
            declared = False
            for tok in TOKEN_SPLIT.split(line):
                if not tok:
                    continue
                if "$" in tok:
                    tok = self.substitute(tok, table)
                    if "$" in tok:
                        if looks_like_path(tok.replace("$", "x")):
                            self.note(self.unresolved, path, lineno, tok)
                        continue
                if looks_like_path(tok):
                    yield lineno, tok, declared
                elif is_directive(tok):
                    declared = True

    def resolve(self, token, from_file):
        """Resolve a token against the usual search order.

        Returns absolute paths with any symlink in them left alone, so that
        a reference behind a linked directory still maps back to where it was
        written (../ref/x.lib -> <out>/../ref/x.lib).
        """
        if os.path.isabs(token):
            bases = [""]
        else:
            bases = [os.path.dirname(from_file), self.in_dir, os.getcwd()]
            bases.extend(self.search_dirs)
        tried = []
        for base in bases:
            cand = token if base == "" else os.path.join(base, token)
            cand = os.path.normpath(os.path.abspath(cand))
            if cand in tried:
                continue
            tried.append(cand)
            if any(ch in token for ch in "*?"):
                hits = sorted(globmod.glob(cand))
                if hits:
                    return hits
            elif os.path.exists(cand):
                return [cand]
        return []

    def widen_to_dir(self, real):
        """--whole-dir: a file inside a matching directory pulls in the whole
        directory (e.g. a qrcTechFile inside ...rcworst.tar.gz_FILE/)."""
        if not self.whole_dir or os.path.isdir(real):
            return real
        parent = os.path.dirname(real)
        name = os.path.basename(parent)
        for pattern in self.whole_dir:
            if fnmatch.fnmatch(name, pattern) and not self.unsafe_target(parent):
                return parent
        return real

    def unsafe_target(self, real):
        """Reject filesystem roots, ancestors of the input dir, the output."""
        if real == os.sep or real == self.in_dir:
            return True
        if self.in_dir.startswith(real.rstrip(os.sep) + os.sep):
            return True
        if real == self.out_dir or real.startswith(self.out_dir + os.sep):
            return True
        return False

    # -- driver -----------------------------------------------------------

    def enqueue(self, path, do_copy=True):
        key = os.path.realpath(path)
        if key not in self.seen:
            self.seen.add(key)
            self.queue.append((path, do_copy))

    def process(self, path, do_copy=True):
        if do_copy:
            dest, external = self.dest_for(path)
            if external and dest is None:
                return
            if os.path.isdir(path):
                self.copy_dir(path, dest)
                return
            self.copy_file(path, dest)
        elif os.path.isdir(path):
            return

        ok, reason = self.scannable(path)
        if not ok:
            self.log("  not scanned (%s): %s" % (reason, path))
            self.skipped_scan.append((path, reason))
            return

        self.log("scanning %s" % self.rel_in(path))
        for lineno, token, declared in self.candidates(path):
            hits = self.resolve(token, path)
            if not hits:
                # Report a ref that cannot be found either when a directive
                # introduced it (source x.sdc) or when it is unmistakably a
                # file path -- a separator plus an extension.  That covers
                #   -timing [list ../ref/io/dblib/x.lib]
                # which no keyword announces, while leaving design objects
                # such as [get_cells u_a/u_b/reg*] alone.
                if declared or ("/" in token and EXT_RE.search(token)):
                    self.note(self.missing, path, lineno, token)
                    self.log("  MISSING %s:%d %s"
                             % (self.rel_in(path), lineno, token))
                continue
            for hit in hits:
                if self.unsafe_target(hit):
                    self.log("  ignored (unsafe target): %s" % token)
                    continue
                if os.path.isdir(hit) and "/" not in token:
                    continue
                hit = self.widen_to_dir(hit)
                _, is_ext = self.dest_for(hit)
                if is_ext and self.external_mode == "skip":
                    self.note(self.external, path, lineno, hit)
                    continue
                self.log("  -> %s" % self.rel_in(hit))
                self.enqueue(hit)

    def run(self):
        if not os.path.isfile(self.in_file):
            print("error: input file not found: %s" % self.in_file,
                  file=sys.stderr)
            return 2
        if self.out_dir == self.in_dir:
            print("error: output dir is the input dir", file=sys.stderr)
            return 2
        self.enqueue(self.in_file)
        while self.queue:
            path, do_copy = self.queue.popleft()
            self.process(path, do_copy)
        self.report()
        return 1 if self.missing else 0

    # -- report -----------------------------------------------------------

    def manifest_lines(self):
        out = []
        for src, dest in self.copied:
            out.append("COPIED    %s  ->  %s" % (src, dest))
        for src, dest, n, b in self.dirs:
            out.append("DIR       %s/  ->  %s/   (%d files, %s)"
                       % (src, dest, n, human(b)))
        for where, line, tok in self.missing:
            out.append("MISSING   %s:%d  %s" % (where, line, tok))
        for where, line, path in self.external:
            out.append("EXTERNAL  %s:%d  %s" % (where, line, path))
        for src, reason in self.skipped_scan:
            out.append("SKIPPED   %s   (%s)" % (src, reason))
        for where, line, tok in self.unresolved:
            out.append("UNRESOLVED_VAR  %s:%d  %s" % (where, line, tok))
        return out

    def report(self):
        text = "\n".join(self.manifest_lines()) + "\n"
        manifest = self.manifest or os.path.join(self.out_dir, MANIFEST_NAME)
        if not self.dry_run:
            parent = os.path.dirname(manifest)
            if parent and not os.path.isdir(parent):
                os.makedirs(parent)
            with open(manifest, "w") as fh:
                fh.write(text)

        print("%s%d files, %d directories copied to %s"
              % ("[dry-run] " if self.dry_run else "",
                 len(self.copied), len(self.dirs), self.out_dir))
        for label, items in (("missing", self.missing),
                             ("external (skipped)", self.external),
                             ("not scanned", self.skipped_scan),
                             ("unresolved $vars", self.unresolved)):
            if items:
                print("  %-20s %d" % (label + ":", len(items)))
        if self.external:
            print("  ^ outside <output>/.. ; see the manifest, then use "
                  "--external copy or --up-levels N to include them")
        for where, line, tok in self.missing:
            print("  MISSING  %s:%d  %s"
                  % (self.rel_in(where), line, tok), file=sys.stderr)
        if not self.dry_run:
            print("manifest: %s" % manifest)


# ---------------------------------------------------------------------- cli


def size_arg(text):
    units = {"k": 1024, "m": 1024 ** 2, "g": 1024 ** 3}
    text = text.strip().lower()
    if text and text[-1] in units:
        return int(float(text[:-1]) * units[text[-1]])
    return int(text)


def build_parser():
    p = argparse.ArgumentParser(
        description="Copy an EDA config file plus every file it references, "
                    "keeping the relative directory structure.")
    p.add_argument("input_file")
    p.add_argument("output_dir")
    p.add_argument("-n", "--dry-run", action="store_true",
                   help="report what would be copied, write nothing")
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("--search", action="append", metavar="DIR",
                   help="extra directory to resolve references against")
    p.add_argument("--up-levels", type=int, default=1, metavar="N",
                   help="how many '..' levels still count as internal "
                        "(default 1, so everything lands under <output>/..)")
    p.add_argument("--external", choices=("skip", "copy"), default="skip",
                   help="what to do with refs outside that boundary")
    p.add_argument("--whole-dir", action="append", metavar="GLOB",
                   help="when a referenced file sits in a directory whose name "
                        "matches GLOB, copy that whole directory "
                        "(e.g. --whole-dir '*_FILE' for QRC tech dirs)")
    p.add_argument("--scan-all", action="store_true",
                   help="also scan .lib/.lef/.gz ... for nested references")
    p.add_argument("--max-scan-size", type=size_arg, default=DEFAULT_MAX_SCAN,
                   metavar="BYTES", help="per-file scan limit (default 32M)")
    p.add_argument("--max-dir-size", type=size_arg, default=DEFAULT_MAX_DIR,
                   metavar="BYTES", help="directory copy limit (default 2G)")
    p.add_argument("--manifest", metavar="PATH",
                   help="where to write the report "
                        "(default <output_dir>/%s)" % MANIFEST_NAME)
    p.add_argument("--overwrite", action="store_true",
                   help="overwrite differing destination files without warning")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    return Collector(args).run()


if __name__ == "__main__":
    sys.exit(main())
