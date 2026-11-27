#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pages/gdsview.py
----------------
Shared "open a GDS in a viewer" flows, used by the SKIPPER / KLAYOUT tabs and by
the View buttons on other tabs.

It generates a shell script in ~/.cgui/ (never in ./, since the user may be
viewing a GDS in someone else's directory with no write permission there) and
runs it in a terminal (so errors are visible and it gets a controlling terminal),
falling back to a detached background launch when no terminal is available.

Two viewers:
  - open_gds        : skipper (module load skipper/calibre from ENV, plus
                      -cdsTech/-cdsDisp/-cdsLayerMap/-init from central SKIPPER.conf).
                      Used by the SKIPPER tab and other tabs' View.
  - open_gds_klayout: klayout (just "<KLAYOUT_BIN> <gds>"; no module/cds needed,
                      independent of the PROCESS selection). Used by the KLAYOUT tab.
"""

import gzip
import os
import shutil
import struct
import subprocess
from xml.sax.saxutils import escape as _xml_escape

from tkinter import messagebox

import config

_TERMINALS = (
    ["xterm", "-fg", "white", "-bg", "black", "-e"],
    ["gnome-terminal", "--"], ["konsole", "-e"],
    ["xfce4-terminal", "-e"], ["mate-terminal", "-e"],
)


# ==========================================================================
# skipper
# ==========================================================================
def _skipper_conf():
    """Return (conf_dict, conf_path) for the current design's SKIPPER.conf."""
    path = config.central_skipper_conf(config.DESIGN_NAME)
    return config.read_conf(path), path


def build_skipper_script(app, gds, conf=None, conf_path=None):
    """Return the shell text to open <gds> with skipper."""
    if conf is None:
        conf, conf_path = _skipper_conf()
    skipper = app.env.get("skipper") or ""
    calibre = app.env.get("calibre") or ""

    cmd = ["skipper", "-noterm", "-i", gds]
    if conf.get("cdsTech"):
        cmd += ["-cdsTech", conf["cdsTech"]]
    if conf.get("cdsDisp"):
        cmd += ["-cdsDisp", conf["cdsDisp"]]
    if conf.get("cdsLayerMap"):
        cmd += ["-cdsLayerMap", conf["cdsLayerMap"]]
    # -init only when configured in central AND the file exists
    init = conf.get("init")
    if init and os.path.isfile(os.path.expanduser(init)):
        cmd += ["-init", init]

    mods = "".join("module load %s\n" % m for m in (skipper, calibre) if m)
    # Diagnostic: record which SKIPPER.conf was looked up and whether it was found.
    status = "found" if os.path.isfile(conf_path or "") else "NOT FOUND"
    return (
        "#!/bin/bash\n"
        "# SKIPPER.conf: %s (%s)\n"
        "%s"
        "%s\n"
    ) % (conf_path, status, mods, " ".join(cmd))


def open_gds(app, gds):
    """Open a GDS with skipper."""
    if hasattr(app, "ensure_license") and not app.ensure_license("open skipper"):
        return
    gds = (gds or "").strip()
    if not gds:
        messagebox.showwarning("pvflow", "no GDS file specified")
        return
    if not os.environ.get("DISPLAY"):
        messagebox.showerror("pvflow", "No DISPLAY, cannot open skipper")
        return

    conf, conf_path = _skipper_conf()
    if not conf.get("cdsTech"):
        messagebox.showwarning(
            "pvflow",
            "skipper cds paths are not configured; opening with -i only.\n\n"
            "SKIPPER.conf: %s\n(exists: %s)\n\n"
            "Check config.DEFAULT_COM_DIR / $PVFLOW_DEFAULT_DIR and that the file "
            "sits under <DEFAULT_COM_DIR>/%s/SKIPPER.conf."
            % (conf_path, os.path.isfile(conf_path), config.DESIGN_NAME))

    script = build_skipper_script(app, os.path.expanduser(gds), conf, conf_path)
    _write_and_launch(script, "skipper_view")


_LAYER_COLORS = (
    "#d9534f", "#0275d8", "#5cb85c", "#f0ad4e", "#9b59b6",
    "#17a2b8", "#e67e22", "#e83e8c", "#20c997", "#795548",
    "#3f51b5", "#607d8b",
)


# ==========================================================================
# klayout discovery, pure-Python GDS cell scanner, and .layermap converter
# ==========================================================================
def find_klayout():
    """Return path to KLayout executable via 3-tier lookup, or None.

    Order:
      1. $PVFLOW_KLAYOUT (or legacy $CGUI_KLAYOUT)
      2. klayout in $PATH (customer's existing installation)
      3. Bundled fallback <install>/tools/klayout/klayout or .../bin/klayout
    """
    env_bin = config.env_get("PVFLOW_KLAYOUT", "CGUI_KLAYOUT").strip()
    if env_bin:
        cand = os.path.abspath(os.path.expanduser(env_bin))
        if os.path.isfile(cand) and os.access(cand, os.X_OK):
            return cand

    which_bin = shutil.which("klayout")
    if which_bin:
        return which_bin

    seen = set()
    install_dir = getattr(config, "INSTALL_DIR", config.APP_DIR)
    for base in (install_dir, config.APP_DIR, config.BASE_DIR):
        if not base:
            continue
        for rel in (
            os.path.join("tools", "klayout", "klayout"),
            os.path.join("tools", "klayout", "bin", "klayout"),
        ):
            cand = os.path.join(base, rel)
            if cand in seen:
                continue
            seen.add(cand)
            if os.path.isfile(cand) and os.access(cand, os.X_OK):
                return cand
    return None


def scan_gds_cells(path):
    """Scan a .gds or .gds.gz binary using stdlib only.

    Returns (top_cells, all_cells): unique structure names in file order,
    where top_cells are defined structures (STRNAME 0x0606) never referenced
    by SNAME (0x1206).
    """
    full = os.path.abspath(os.path.expanduser(path))
    with open(full, "rb") as raw:
        magic = raw.read(2)
    is_gz = (magic == b"\x1f\x8b")
    opener = gzip.open if is_gz else open

    all_cells = []
    seen = set()
    referenced = set()
    with opener(full, "rb") as f:
        while True:
            hdr = f.read(4)
            if len(hdr) < 4:
                break
            length, rec_id = struct.unpack(">HH", hdr)
            if length < 4:
                break
            payload_len = length - 4
            if rec_id in (0x0606, 0x1206):
                data = f.read(payload_len)
                if len(data) < payload_len:
                    break
                name = data.rstrip(b"\x00").decode("ascii", errors="replace").strip()
                if name:
                    if rec_id == 0x0606:
                        if name not in seen:
                            seen.add(name)
                            all_cells.append(name)
                    else:
                        referenced.add(name)
            elif payload_len > 0:
                if is_gz:
                    # gzip.GzipFile.seek(offset, SEEK_CUR) handles forward skips
                    f.seek(payload_len, os.SEEK_CUR)
                else:
                    f.seek(payload_len, os.SEEK_CUR)

    top_cells = [c for c in all_cells if c not in referenced]
    return top_cells, all_cells


def layermap_to_lyp(map_path, out_path=None):
    """Convert a 4-column Virtuoso .layermap file to KLayout XML .lyp."""
    src = os.path.abspath(os.path.expanduser(map_path))
    if out_path is None:
        stem = os.path.splitext(os.path.basename(src))[0] or "layers"
        cache_dir = os.path.join(config.USER_DIR, "cache")
        out_path = os.path.join(cache_dir, "%s.lyp" % stem)
    else:
        out_path = os.path.abspath(os.path.expanduser(out_path))

    entries = []
    with open(src, "r", encoding="utf-8", errors="replace") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith(("#", "//", ";")):
                continue
            parts = line.split()
            if len(parts) < 4:
                continue
            lname, purpose, lnum_s, dtype_s = parts[0], parts[1], parts[2], parts[3]
            try:
                lnum = int(lnum_s)
                dtype = int(dtype_s)
            except ValueError:
                continue
            entries.append((lname, purpose, lnum, dtype))

    parent = os.path.dirname(out_path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    blocks = ['<?xml version="1.0" encoding="utf-8"?>', "<layer-properties>"]
    for idx, (lname, purpose, lnum, dtype) in enumerate(entries):
        color = _LAYER_COLORS[idx % len(_LAYER_COLORS)]
        disp = _xml_escape("%s/%s" % (lname, purpose))
        blocks.extend([
            " <properties>",
            "  <frame-color>%s</frame-color>" % color,
            "  <fill-color>%s</fill-color>" % color,
            "  <frame-brightness>0</frame-brightness>",
            "  <fill-brightness>0</fill-brightness>",
            "  <dither-pattern>I5</dither-pattern>",
            "  <line-style>C0</line-style>",
            "  <valid>true</valid>",
            "  <visible>true</visible>",
            "  <transparent>false</transparent>",
            "  <width>1</width>",
            "  <marked>false</marked>",
            "  <xfill>false</xfill>",
            "  <animation>0</animation>",
            "  <name>%s</name>" % disp,
            "  <source>%d/%d@1</source>" % (lnum, dtype),
            " </properties>",
        ])
    blocks.append("</layer-properties>\n")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(blocks))
    return out_path


def build_klayout_script(gds):
    """Return the shell text to open <gds> with klayout."""
    klayout_bin = find_klayout() or config.KLAYOUT_BIN
    return (
        "#!/bin/bash\n"
        "%s %s\n"
    ) % (klayout_bin, gds)


def open_gds_klayout(app, gds, layer_map=None, edit_mode=False):
    """Open a GDS file in KLayout using 3-tier binary lookup and optional .lyp/.layermap."""
    if hasattr(app, "ensure_license") and not app.ensure_license("open KLayout"):
        return
    gds = (gds or "").strip()
    if not gds:
        messagebox.showwarning("pvflow", "no GDS file specified")
        return
    if not os.environ.get("DISPLAY"):
        messagebox.showerror("pvflow", "No DISPLAY, cannot open KLayout")
        return

    klayout_bin = find_klayout()
    if not klayout_bin:
        messagebox.showerror(
            "pvflow",
            "KLayout executable not found.\n\n"
            "Checked:\n"
            "  1. $PVFLOW_KLAYOUT (or $CGUI_KLAYOUT)\n"
            "  2. klayout in $PATH\n"
            "  3. <pvflow>/tools/klayout/klayout (or tools/klayout/bin/klayout)",
        )
        return

    gds_path = os.path.expanduser(gds)
    cmd = [klayout_bin]
    if edit_mode:
        cmd.append("-e")

    lm = (layer_map or "").strip()
    if lm:
        lm_path = os.path.expanduser(lm)
        if not os.path.isfile(lm_path):
            messagebox.showerror("pvflow", "LayerMap file not found:\n%s" % lm_path)
            return
        if not lm_path.lower().endswith(".lyp"):
            try:
                lm_path = layermap_to_lyp(lm_path)
            except Exception as e:
                messagebox.showerror("pvflow", "Failed to convert layermap:\n%s" % e)
                return
        cmd.extend(["-l", lm_path])

    cmd.append(gds_path)
    try:
        subprocess.Popen(cmd, start_new_session=True, close_fds=True)
    except Exception as e:
        messagebox.showerror("pvflow", "Failed to launch KLayout:\n%s" % e)


# ==========================================================================
# shared launch
# ==========================================================================
def _write_and_launch(script, name):
    """Write ~/.pvflow/<name>.sh and run it (terminal preferred, else background)."""
    try:
        os.makedirs(config.USER_DIR, exist_ok=True)
        sh_path = os.path.join(config.USER_DIR, name + ".sh")
        with open(sh_path, "w", encoding="utf-8") as f:
            f.write(script)
        os.chmod(sh_path, 0o755)
    except OSError as e:
        messagebox.showerror("pvflow", "Failed to write viewer script:\n%s" % e)
        return
    if not _launch_in_terminal(sh_path):
        _launch_background(sh_path)


def _launch_in_terminal(sh_path):
    """Open a terminal that runs the viewer shell and stays open afterwards so
    any error is visible. Returns False if no terminal emulator is found."""
    wrapper = sh_path[:-len(".sh")] + ".term.sh"
    try:
        with open(wrapper, "w", encoding="utf-8") as f:
            f.write('#!/bin/bash\n'
                    "printf '\\033]10;white\\007\\033]11;black\\007'\n"
                    'bash "%s"\n'
                    'echo\n'
                    'echo "===== viewer exited. Press Enter to close ====="\n'
                    'read\n' % sh_path)
        os.chmod(wrapper, 0o755)
    except OSError:
        return False
    for term in _TERMINALS:
        if shutil.which(term[0]):
            try:
                subprocess.Popen(term + [wrapper], start_new_session=True, close_fds=True)
                return True
            except Exception:
                continue
    return False


def _launch_background(sh_path):
    """Detached background launch (own session, immune to the parent's SIGHUP;
    output goes to ~/.pvflow/<name>.log)."""
    log_path = sh_path[:-len(".sh")] + ".log"
    try:
        logf = open(log_path, "w")
        devnull = open(os.devnull, "rb")
        subprocess.Popen(
            ["bash", sh_path],
            stdin=devnull, stdout=logf, stderr=subprocess.STDOUT,
            start_new_session=True, close_fds=True,
        )
        logf.close()
        devnull.close()
    except Exception as e:
        messagebox.showerror("pvflow", "Failed to launch viewer:\n%s" % e)
