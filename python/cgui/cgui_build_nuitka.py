#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cgui_build_nuitka.py
--------------------
Compile Cadsemi PVFlow (`pvflow`) into a native Linux ELF binary using Nuitka
(no Python source or .pyc bytecode shipped to customers) and assemble a clean
EDA-style release directory:

    dist/<version>/
    ├── README.md                  # Customer quick-start & install guide
    ├── bin/
    │   ├── pvflow                 # Bash launcher wrapper (add bin/ to PATH)
    │   └── cgui -> pvflow         # Legacy command symlink
    ├── libexec/
    │   ├── pvflow.bin             # Native ELF binary
    │   └── *.so                   # Isolated runtime libraries
    ├── data/                      # Offline help HTML, templates, system.txt
    └── etc/
        └── modulefile.example     # Environment Modules template

Usage:
    .build_venv/bin/python cgui_build_nuitka.py
    .build_venv/bin/python cgui_build_nuitka.py --version 26.11.001 --out dist/26.11.001
    .build_venv/bin/python cgui_build_nuitka.py --mode onefile --out dist/26.11.001
"""

import argparse
import os
import re
import shutil
import subprocess
import sys

SRC = os.path.dirname(os.path.abspath(__file__))
if SRC not in sys.path:
    sys.path.insert(0, SRC)

import cgui_license
import config


def _pick_python(explicit=None):
    if explicit:
        return os.path.abspath(explicit)
    venv_py = os.path.join(SRC, ".build_venv", "bin", "python")
    for cand in (sys.executable, venv_py):
        if cand and os.path.isfile(cand):
            chk = subprocess.run(
                [cand, "-c", "import nuitka"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if chk.returncode == 0:
                return cand
    return sys.executable


def _pin_default_home(launcher_path, install_dir):
    with open(launcher_path, "r", encoding="utf-8") as f:
        src = f.read()
    src = src.replace("\r\n", "\n")
    src = re.sub(
        r'(?m)^DEFAULT_HOME=.*$',
        'DEFAULT_HOME="%s"' % install_dir,
        src,
        count=1,
    )
    with open(launcher_path, "wb") as f:
        f.write(src.encode("utf-8"))
    os.chmod(launcher_path, 0o755)


def _write_modulefile_example(etc_dir, version):
    os.makedirs(etc_dir, exist_ok=True)
    content = (
        "#%%Module1.0\n"
        "## Cadsemi PVFlow %s modulefile\n"
        "proc ModulesHelp { } {\n"
        "    puts stderr \"Adds Cadsemi PVFlow %s to your environment.\"\n"
        "}\n"
        "module-whatis \"Cadsemi PVFlow %s - Physical Verification Flow\"\n"
        "\n"
        "set root /apps/cadsemi/pvflow/%s\n"
        "prepend-path PATH $root/bin\n"
        "setenv PVFLOW_HOME $root\n"
        "# Optional: uncomment to override automatic cadsemi.lic discovery\n"
        "# setenv CADSEMI_LICENSE_FILE /apps/cadsemi/license/cadsemi.lic\n"
    ) % (version, version, version, version)
    path = os.path.join(etc_dir, "modulefile.example")
    with open(path, "wb") as f:
        f.write(content.encode("utf-8"))
    return path


def _write_release_readme(out_dir, version):
    content = (
        "# Cadsemi PVFlow %s\n"
        "\n"
        "## Standard EDA Installation\n"
        "\n"
        "```bash\n"
        "# 1. Extract into your EDA apps tree (e.g. /apps/cadsemi/pvflow)\n"
        "mkdir -p /apps/cadsemi/pvflow /apps/cadsemi/license\n"
        "tar -xzf pvflow_%s_linux_x64.tar.gz -C /apps/cadsemi/pvflow/\n"
        "\n"
        "# 2. Install license file (shared across all PVFlow versions)\n"
        "cp cadsemi.lic /apps/cadsemi/license/cadsemi.lic\n"
        "#    (Alternative: cp cadsemi.lic /apps/cadsemi/pvflow/%s/cadsemi.lic\n"
        "#     or export CADSEMI_LICENSE_FILE=/path/to/cadsemi.lic)\n"
        "\n"
        "# 3. Verify license & environment\n"
        "/apps/cadsemi/pvflow/%s/bin/pvflow -L\n"
        "\n"
        "# 4. (Optional) Point `current` symlink when ready to roll out\n"
        "ln -sfn %s /apps/cadsemi/pvflow/current\n"
        "```\n"
        "\n"
        "## User Setup\n"
        "\n"
        "Add to `~/.bashrc`:\n"
        "```bash\n"
        "export PATH=/apps/cadsemi/pvflow/current/bin:$PATH\n"
        "```\n"
        "\n"
        "Or `~/.cshrc`:\n"
        "```csh\n"
        "set path = (/apps/cadsemi/pvflow/current/bin $path)\n"
        "```\n"
        "\n"
        "Or install `etc/modulefile.example` into your site `MODULEPATH` and run:\n"
        "```bash\n"
        "module load pvflow/%s\n"
        "pvflow\n"
        "```\n"
        "\n"
        "## Directory Layout\n"
        "\n"
        "- `bin/pvflow` : Main launcher wrapper (`bin/cgui` symlink kept for compatibility)\n"
        "- `libexec/`   : Native ELF binary (`pvflow.bin`) and bundled runtime libraries\n"
        "- `data/`      : Offline HTML User Guide (`data/help/index.html`) and templates\n"
        "- `etc/`       : Example Environment Modules file (`modulefile.example`)\n"
        "\n"
        "Support: %s | https://cadsemi.com\n"
    ) % (version, version, version, version, version, version, cgui_license.SUPPORT_EMAIL)
    path = os.path.join(out_dir, "README.md")
    with open(path, "wb") as f:
        f.write(content.encode("utf-8"))
    return path


def _audit_dist(out_dir):
    bad = []
    for root, dirs, files in os.walk(out_dir):
        for d in dirs:
            if d in ("lic_issuer", "keys", "tests", "__pycache__"):
                bad.append(os.path.join(root, d))
        for fn in files:
            low = fn.lower()
            if (low.endswith(".py") or low.endswith(".pyc")
                    or low.endswith(".pem") or low.endswith(".lic")):
                bad.append(os.path.join(root, fn))
    if bad:
        raise RuntimeError(
            "Security audit failed -- forbidden files found in %s:\n  %s"
            % (out_dir, "\n  ".join(bad))
        )


def _parse_ver(ver_str):
    parts = [int(x) for x in ver_str.split(".")]
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def _audit_glibc(out_dir, max_glibc):
    objdump = shutil.which("objdump")
    if not objdump:
        raise RuntimeError("objdump not found; cannot verify --max-glibc %s" % max_glibc)
    limit = _parse_ver(max_glibc)
    highest = None
    offenders = []
    ver_re = re.compile(r'GLIBC_(\d+\.\d+(?:\.\d+)?)')

    for root, _dirs, files in os.walk(out_dir):
        for fn in files:
            path = os.path.join(root, fn)
            if os.path.islink(path):
                continue
            try:
                with open(path, "rb") as f:
                    if f.read(4) != b"\x7fELF":
                        continue
            except OSError:
                continue
            res = subprocess.run(
                [objdump, "-T", path],
                capture_output=True, text=True,
            )
            for m in ver_re.finditer(res.stdout):
                v_str = m.group(1)
                v_tup = _parse_ver(v_str)
                if highest is None or v_tup > highest[0]:
                    highest = (v_tup, v_str)
                if v_tup > limit:
                    offenders.append((os.path.relpath(path, out_dir), v_str))

    if offenders:
        unique = sorted(set(offenders))
        lines = ["%s requires GLIBC_%s" % (rel, ver) for rel, ver in unique[:20]]
        raise RuntimeError(
            "GLIBC audit failed (limit GLIBC_%s):\n  %s"
            % (max_glibc, "\n  ".join(lines))
        )
    return highest[1] if highest else "none"


def _detect_tcltk_dirs(python_exe):
    res = subprocess.run(
        [python_exe, "-c", "import tkinter; print(tkinter.Tcl().eval('info library'))"],
        capture_output=True, text=True,
    )
    if res.returncode != 0:
        return None, None
    tcl_dir = res.stdout.strip()
    if not tcl_dir or not os.path.isfile(os.path.join(tcl_dir, "init.tcl")):
        return None, None
    parent, base = os.path.split(tcl_dir.rstrip(os.sep))
    if base.startswith("tcl"):
        tk_dir = os.path.join(parent, "tk" + base[3:])
        if os.path.isfile(os.path.join(tk_dir, "dialog.tcl")):
            return tcl_dir, tk_dir
    return tcl_dir, None


def build(mode="standalone", out=None, install_dir=None, python_exe=None,
          max_glibc=None, version=None):
    if not cgui_license.is_public_key_configured():
        raise RuntimeError(
            "Embedded Ed25519 public key in cgui_license.py is still all zeros.\n"
            "Run: python3 lic_issuer/cgui_lic_admin.py keygen "
            "--out-dir lic_issuer/keys --embed cgui_license.py"
        )

    version = version or config.latest_revision()
    py = _pick_python(python_exe)
    out = out or os.path.join("dist", version)
    out_dir = out if os.path.isabs(out) else os.path.join(SRC, out)
    out_dir = os.path.abspath(out_dir)
    install_dir = install_dir or "/apps/cadsemi/pvflow/current"
    build_dir = os.path.join(SRC, "build_nuitka")

    if os.path.exists(build_dir):
        shutil.rmtree(build_dir)
    os.makedirs(build_dir, exist_ok=True)
    if os.path.exists(out_dir):
        shutil.rmtree(out_dir)

    env = dict(os.environ)
    py_bin_dir = os.path.dirname(os.path.abspath(py))
    env["PATH"] = py_bin_dir + os.pathsep + env.get("PATH", "")

    tcl_dir, tk_dir = _detect_tcltk_dirs(py)

    cmd = [
        py, "-m", "nuitka",
        "--" + mode,
        "--assume-yes-for-downloads",
        "--enable-plugin=tk-inter",
        "--include-package=pages",
        "--include-module=cgui_eng",
        "--include-data-dir=%s=data" % os.path.join(SRC, "data"),
        "--nofollow-import-to=lic_issuer",
        "--nofollow-import-to=tests",
        "--output-filename=pvflow.bin",
        "--output-dir=%s" % build_dir,
    ]
    if tcl_dir:
        cmd.append("--tcl-library-dir=%s" % tcl_dir)
    if tk_dir:
        cmd.append("--tk-library-dir=%s" % tk_dir)
    cmd.append(os.path.join(SRC, "cgui.py"))
    print("Running Nuitka (%s, version=%s):" % (mode, version))
    print("  " + " ".join(cmd))
    subprocess.check_call(cmd, env=env, cwd=SRC)

    bin_dir = os.path.join(out_dir, "bin")
    libexec_dir = os.path.join(out_dir, "libexec")
    data_dir = os.path.join(out_dir, "data")
    etc_dir = os.path.join(out_dir, "etc")
    os.makedirs(bin_dir, exist_ok=True)

    if mode == "standalone":
        dist_src = os.path.join(build_dir, "cgui.dist")
        if not os.path.isdir(dist_src):
            raise RuntimeError("Expected Nuitka dist directory missing: %s" % dist_src)
        shutil.copytree(dist_src, libexec_dir, symlinks=True)
        libexec_data = os.path.join(libexec_dir, "data")
        if os.path.isdir(libexec_data):
            shutil.move(libexec_data, data_dir)
        else:
            shutil.copytree(os.path.join(SRC, "data"), data_dir)
    else:
        bin_src = os.path.join(build_dir, "pvflow.bin")
        if not os.path.isfile(bin_src):
            raise RuntimeError("Expected Nuitka onefile binary missing: %s" % bin_src)
        os.makedirs(libexec_dir, exist_ok=True)
        shutil.copy2(bin_src, os.path.join(libexec_dir, "pvflow.bin"))
        shutil.copytree(os.path.join(SRC, "data"), data_dir)

    launcher_dst = os.path.join(bin_dir, "pvflow")
    shutil.copy2(os.path.join(SRC, "pvflow"), launcher_dst)
    _pin_default_home(launcher_dst, install_dir)

    legacy_link = os.path.join(bin_dir, "cgui")
    if os.path.lexists(legacy_link):
        os.unlink(legacy_link)
    os.symlink("pvflow", legacy_link)

    mod_path = _write_modulefile_example(etc_dir, version)
    readme_path = _write_release_readme(out_dir, version)

    _audit_dist(out_dir)
    max_found = _audit_glibc(out_dir, max_glibc) if max_glibc else None

    bin_path = os.path.join(libexec_dir, "pvflow.bin")
    file_out = subprocess.run(
        ["file", bin_path], capture_output=True, text=True
    ).stdout.strip()

    print("\nBuild complete:")
    print("  Version      : %s" % version)
    print("  Release dir  : %s" % out_dir)
    print("  Launcher     : %s (DEFAULT_HOME=%s)" % (launcher_dst, install_dir))
    print("  Native binary: %s" % (file_out or bin_path))
    print("  Modulefile   : %s" % mod_path)
    print("  Release notes: %s" % readme_path)
    print("  Audit        : PASS (no .py / .pyc / .pem / .lic / lic_issuer in dist)")
    if max_glibc:
        print("  Max GLIBC    : %s (limit: %s) -- PASS" % (max_found, max_glibc))
    print("\nCustomer installation:")
    print("  mkdir -p /apps/cadsemi/pvflow /apps/cadsemi/license")
    print("  tar -xzf pvflow_%s_linux_x64.tar.gz -C /apps/cadsemi/pvflow/" % version)
    print("  cp cadsemi.lic /apps/cadsemi/license/cadsemi.lic")
    print("  ln -sfn %s /apps/cadsemi/pvflow/current" % version)
    return out_dir


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build native ELF binary for Cadsemi PVFlow via Nuitka")
    parser.add_argument("--mode", choices=("standalone", "onefile"), default="standalone")
    parser.add_argument("--version", default=None,
                        help="Release version string (default: latest revision from data/system.txt)")
    parser.add_argument("--out", default=None, help="Output directory (default: dist/<version>)")
    parser.add_argument("--install-dir", default="/apps/cadsemi/pvflow/current",
                        help="Target install dir pinned into launcher DEFAULT_HOME")
    parser.add_argument("--python", default=None, help="Python executable with Nuitka")
    parser.add_argument("--max-glibc", default=None,
                        help="Fail if any ELF in dist requires GLIBC newer than this (e.g. 2.17)")
    args = parser.parse_args(argv)
    build(mode=args.mode, out=args.out,
          install_dir=args.install_dir, python_exe=args.python,
          max_glibc=args.max_glibc, version=args.version)
    return 0


if __name__ == "__main__":
    sys.exit(main())
