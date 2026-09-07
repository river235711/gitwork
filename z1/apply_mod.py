#!/usr/bin/env python3
"""apply_mod.py -- 把舊版做過的客製修改,自動套到新版的原始檔上。

    apply_mod.py v08.ori v08.modi v09.ori v09.modi

輸入 3 個檔、輸出 1 個檔:

    v08.ori   舊版原廠檔 (base)
    v08.modi  舊版改好的檔 (base + 我們的修改)
    v09.ori   新版原廠檔
    v09.modi  <-- 產生:新版原廠檔 + 同樣那些修改

作法是標準的 three-way merge(等同 diff3 -m / git merge-file),
所以不管是
    //#define X  ->  #define X       (註解切換)
    #define X    ->  //#define X
    新增整段設定 (例如 #define NW_RING、VARIABLE POWER_NAME ...)
都會被帶過去;而新版原廠自己新增/修改的內容也會保留。
行號位移不影響,靠上下文對位。

兩邊改到同一段而且改法不同時,預設寫入衝突標記並回傳 exit code 1;
可用 --prefer 自動選邊。
"""

import argparse
import difflib
import subprocess
import sys

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="backslashreplace")
    except (AttributeError, ValueError):
        pass

# 用 surrogateescape 讀寫,任何位元組都能原樣往返(EDA deck 常混雜非 UTF-8)
ENC_KW = dict(encoding="utf-8", errors="surrogateescape", newline="")


def git_merge(old_ori, old_modi, new_ori, prefer, labels):
    """用 git merge-file 做合併。回傳 (輸出位元組, 衝突數) 或 None(不可用)。"""
    cmd = ["git", "merge-file", "-p", "--diff3"]
    if prefer == "modi":
        cmd.append("--ours")
    elif prefer == "ori":
        cmd.append("--theirs")
    cmd += ["-L", labels[0], "-L", labels[1], "-L", labels[2]]
    cmd += [old_modi, old_ori, new_ori]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = proc.communicate()
    except OSError:
        return None                      # 沒有 git
    if proc.returncode < 0 or proc.returncode > 127:
        sys.stderr.write("git merge-file failed: %s\n"
                         % ascii_safe(err.decode("utf-8", "replace")))
        return None
    return out, proc.returncode


def ascii_safe(text):
    """把一行變成可以在 LANG=C 終端機安全印出的字串。"""
    return text.rstrip("\r\n").encode("ascii", "backslashreplace").decode("ascii")


def read_lines(path):
    try:
        with open(path, "r", **ENC_KW) as fh:
            return fh.read().splitlines(keepends=True)
    except OSError as exc:
        sys.exit("ERROR: cannot read: %s" % exc)


def unchanged_intervals(base, other):
    """base 與 other 相同的區段,回傳 (base_start, base_end, other_start)。"""
    sm = difflib.SequenceMatcher(None, base, other, autojunk=False)
    return [(i, i + n, j) for i, j, n in sm.get_matching_blocks() if n]


def sync_regions(base, a, b):
    """三方都一致的同步點: (base_s, base_e, a_s, b_s)。"""
    ia = unchanged_intervals(base, a)
    ib = unchanged_intervals(base, b)
    out, pa, pb = [], 0, 0
    while pa < len(ia) and pb < len(ib):
        a_s, a_e, aj = ia[pa]
        b_s, b_e, bj = ib[pb]
        s, e = max(a_s, b_s), min(a_e, b_e)
        if s < e:
            out.append((s, e, aj + (s - a_s), bj + (s - b_s)))
        if a_e < b_e:
            pa += 1
        else:
            pb += 1
    return out


def merge3(base, a, b):
    """three-way merge。a=舊版改後, b=新版原廠。

    回傳 (合併後的行, carried, already, conflicts):
      carried  只有我們改過 -> 這次真的把修改帶進新版
      already  新版原廠已經自己改成同樣結果 -> 輸出不會因此有差異
      conflicts 兩邊都改且改法不同
    """
    merged, conflicts, applied, already = [], [], [], []
    p_base = p_a = p_b = 0

    for s, e, aj, bj in sync_regions(base, a, b) + [(len(base), len(base), len(a), len(b))]:
        base_r = base[p_base:s]
        a_r = a[p_a:aj]
        b_r = b[p_b:bj]

        if base_r or a_r or b_r:
            if a_r == base_r:                 # 只有新版原廠動過 -> 用新版
                merged.extend(b_r)
            elif b_r == base_r:               # 只有我們的修改 -> 帶過去
                applied.append((len(merged) + 1, base_r, a_r))
                merged.extend(a_r)
            elif a_r == b_r:                  # 新版原廠已經自己改成一樣了
                already.append((len(merged) + 1, base_r, a_r))
                merged.extend(a_r)
            else:                             # 衝突
                conflicts.append((len(merged) + 1, base_r, a_r, b_r))
                merged.append(None)           # 佔位,稍後填入
        merged.extend(base[s:e])
        p_base, p_a, p_b = e, aj + (e - s), bj + (e - s)

    return merged, applied, already, conflicts


def fill_conflicts(merged, conflicts, mode, names):
    """把佔位的 None 換成選定內容或衝突標記。"""
    old_name, base_name, new_name = names
    out, ci = [], 0
    for line in merged:
        if line is not None:
            out.append(line)
            continue
        _, base_r, a_r, b_r = conflicts[ci]
        ci += 1
        if mode == "modi":
            out.extend(a_r)
        elif mode == "ori":
            out.extend(b_r)
        else:
            out.append("<<<<<<< %s\n" % old_name)
            out.extend(a_r)
            out.append("||||||| %s\n" % base_name)
            out.extend(base_r)
            out.append("=======\n")
            out.extend(b_r)
            out.append(">>>>>>> %s\n" % new_name)
    return out


def main():
    ap = argparse.ArgumentParser(
        description="Port the old.ori->old.modi customizations onto new.ori, producing new.modi (three-way merge).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="example: %(prog)s v08.ori v08.modi v09.ori v09.modi")
    ap.add_argument("old_ori",  help="old vendor file (merge base)")
    ap.add_argument("old_modi", help="old file with our customizations")
    ap.add_argument("new_ori",  help="new vendor file")
    ap.add_argument("new_modi", nargs="?",
                help="output file; prints to stdout if omitted")
    ap.add_argument("--prefer", choices=["ori", "modi"],
                    help="auto-resolve conflicts: ori=new vendor side, modi=our changes")
    ap.add_argument("-n", "--dry-run", action="store_true",
                help="report only, do not write the output file")
    ap.add_argument("-v", "--verbose", action="store_true",
                help="show a unified diff of new.ori vs the merged result")
    ap.add_argument("-r", "--replace", nargs=2, action="append",
                metavar=("OLD", "NEW"),
                help="after merging, replace every literal OLD with NEW in the "
                     "output; may be given more than once")
    ap.add_argument("--engine", choices=["auto", "git", "python"], default="auto",
                help="merge engine; auto uses git merge-file when available "
                     "and falls back to the built-in one")
    args = ap.parse_args()

    base = read_lines(args.old_ori)
    a    = read_lines(args.old_modi)
    b    = read_lines(args.new_ori)

    merged, applied, already, conflicts = merge3(base, a, b)
    labels = ("OURS %s" % args.old_modi, "BASE %s" % args.old_ori,
              "NEW %s" % args.new_ori)
    out_lines = fill_conflicts(merged, conflicts, args.prefer, labels)

    if args.verbose:
        for tag, regions in (("carried", applied), ("already-present", already)):
            for pos, base_r, a_r in regions:
                sys.stderr.write("  [%s] out line %d: %d line(s) -> %d line(s)\n"
                                 % (tag, pos, len(base_r), len(a_r)))
                for kind, rows in (("-", base_r), ("+", a_r)):
                    for row in rows:
                        sys.stderr.write("      %s %s\n" % (kind, ascii_safe(row)))
        for line in difflib.unified_diff(b, out_lines, args.new_ori,
                                         args.new_modi or "(stdout)", n=2):
            sys.stderr.write(line if line.endswith("\n") else line + "\n")

    py_bytes = "".join(out_lines).encode("utf-8", "surrogateescape")
    out_bytes, engine, git_conflicts = py_bytes, "python", None

    if args.engine in ("auto", "git"):
        got = git_merge(args.old_ori, args.old_modi, args.new_ori, args.prefer,
                        labels)
        if got is None:
            if args.engine == "git":
                sys.exit("ERROR: git merge-file is not usable")
        else:
            out_bytes, git_conflicts = got
            engine = "git"
            if not git_conflicts and not conflicts and out_bytes != py_bytes:
                sys.stderr.write(
                    "WARNING: built-in merge disagrees with git merge-file; "
                    "using git's result (rerun with --engine python to compare)\n")

    for old_s, new_s in args.replace or []:
        old_b = old_s.encode("utf-8", "surrogateescape")
        new_b = new_s.encode("utf-8", "surrogateescape")
        hits = out_bytes.count(old_b)
        out_bytes = out_bytes.replace(old_b, new_b)
        sys.stderr.write("replaced %d occurrence(s) of %s -> %s\n"
                         % (hits, ascii_safe(old_s), ascii_safe(new_s)))
        if not hits:
            sys.stderr.write("  WARNING: %s not found in the merged output\n"
                             % ascii_safe(old_s))

    if not args.dry_run:
        if args.new_modi:
            try:
                with open(args.new_modi, "wb") as fh:
                    fh.write(out_bytes)
            except OSError as exc:
                sys.exit("ERROR: cannot write: %s" % exc)
        else:
            getattr(sys.stdout, "buffer", sys.stdout).write(out_bytes)

    if not applied and not already and not conflicts:
        sys.stderr.write("note: %s and %s are identical; nothing to port\n"
                         % (args.old_ori, args.old_modi))
    elif out_bytes == "".join(b).encode("utf-8", "surrogateescape"):
        sys.stderr.write("note: result is byte-identical to %s -- every "
                         "customization is already present there\n" % args.new_ori)
    if applied and out_bytes == "".join(b).encode("utf-8", "surrogateescape"):
        sys.stderr.write("WARNING: %d change(s) counted as carried but the "
                         "output did not change -- rerun with -v\n" % len(applied))

    marks = [i + 1 for i, ln in enumerate(out_bytes.split(b"\n"))
             if ln.startswith(b"<<<<<<<")]
    if marks:
        where = args.new_modi or "(stdout)"
        sys.stderr.write("\n!! %d CONFLICT(S) left in %s -- the file is NOT "
                         "ready to use as is\n" % (len(marks), where))
        sys.stderr.write("   conflict starts at line: %s\n"
                         % ", ".join(str(m) for m in marks[:20]))
        sys.stderr.write("   resolve by hand (search for '<<<<<<<'), or rerun "
                         "with --prefer modi / --prefer ori\n\n")

    n_conf = git_conflicts if git_conflicts is not None else len(conflicts)
    unresolved = n_conf if not args.prefer else 0
    sys.stderr.write("carried %d / already present %d / conflicts %d%s [engine: %s]\n" % (
        len(applied), len(already), n_conf,
        " (auto-resolved with --prefer %s)" % args.prefer
        if args.prefer and n_conf else "", engine))
    for pos, _, a_r, b_r in conflicts if not args.prefer else []:
        sys.stderr.write("  ! conflict near output line %d: "
                         "new.ori %d line(s) vs our changes %d line(s)\n"
                         % (pos, len(b_r), len(a_r)))

    return 1 if unresolved else 0


if __name__ == "__main__":
    sys.exit(main())
