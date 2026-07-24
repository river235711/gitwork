#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pages/gdsview.py
----------------
Shared "open a GDS in a viewer" flows, used by the SKIPPER / KLAYOUT tabs and by
the View buttons on other tabs.

It generates a shell script in ~/.pdkgui/ (never in ./, since the user may be
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

import os
import shutil
import subprocess

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
    skipper = app.env.get("skipper") or "skipper/2019.06-sp3"
    calibre = app.env.get("calibre") or "calibre/2024.1_36.20"

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

    # Diagnostic: record which SKIPPER.conf was looked up and whether it was found.
    status = "found" if os.path.isfile(conf_path or "") else "NOT FOUND"
    return (
        "#!/bin/bash -l\n"
        "# DESIGN: %s\n"
        "# SKIPPER.conf: %s (%s)\n"
        "module load %s\n"
        "module load %s\n"
        "%s\n"
    ) % (config.DESIGN_NAME, conf_path, status, skipper, calibre, " ".join(cmd))


def open_gds(app, gds):
    """Open a GDS with skipper."""
    gds = (gds or "").strip()
    if not gds:
        messagebox.showwarning("pdkgui", "no GDS file specified")
        return
    if not os.environ.get("DISPLAY"):
        messagebox.showerror("pdkgui", "No DISPLAY, cannot open skipper")
        return

    conf, conf_path = _skipper_conf()
    if not conf.get("cdsTech"):
        messagebox.showwarning(
            "pdkgui",
            "skipper cds paths are not configured; opening with -i only.\n\n"
            "SKIPPER.conf: %s\n(exists: %s)\n\n"
            "Check config.DEFAULT_COM_DIR / $PDKGUI_DEFAULT_DIR and that the file "
            "sits under <DEFAULT_COM_DIR>/%s/SKIPPER.conf."
            % (conf_path, os.path.isfile(conf_path), config.DESIGN_NAME))

    script = build_skipper_script(app, os.path.expanduser(gds), conf, conf_path)
    _write_and_launch(script, "skipper_view")


# ==========================================================================
# klayout (independent of PROCESS / design)
# ==========================================================================
def build_klayout_script(gds):
    """Return the shell text to open <gds> with klayout."""
    return (
        "#!/bin/bash -l\n"
        "%s %s\n"
    ) % (config.KLAYOUT_BIN, gds)


def open_gds_klayout(app, gds):
    """Open a GDS with klayout."""
    gds = (gds or "").strip()
    if not gds:
        messagebox.showwarning("pdkgui", "no GDS file specified")
        return
    if not os.environ.get("DISPLAY"):
        messagebox.showerror("pdkgui", "No DISPLAY, cannot open klayout")
        return
    script = build_klayout_script(os.path.expanduser(gds))
    _write_and_launch(script, "klayout_view")


# ==========================================================================
# shared launch
# ==========================================================================
def _write_and_launch(script, name):
    """Write ~/.pdkgui/<name>.sh and run it (terminal preferred, else background)."""
    try:
        os.makedirs(config.USER_DIR, exist_ok=True)
        sh_path = os.path.join(config.USER_DIR, name + ".sh")
        with open(sh_path, "w", encoding="utf-8") as f:
            f.write(script)
        os.chmod(sh_path, 0o755)
    except OSError as e:
        messagebox.showerror("pdkgui", "Failed to write viewer script:\n%s" % e)
        return
    if not _launch_in_terminal(sh_path):
        _launch_background(sh_path)


def _launch_in_terminal(sh_path):
    """Open a terminal that runs the viewer shell and stays open afterwards so
    any error is visible. Returns False if no terminal emulator is found."""
    wrapper = sh_path[:-len(".sh")] + ".term.sh"
    try:
        with open(wrapper, "w", encoding="utf-8") as f:
            f.write('#!/bin/bash -l\n'
                    "printf '\\033]10;white\\007\\033]11;black\\007'\n"
                    'bash -l "%s"\n'
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
    output goes to ~/.pdkgui/<name>.log)."""
    log_path = sh_path[:-len(".sh")] + ".log"
    try:
        logf = open(log_path, "w")
        devnull = open(os.devnull, "rb")
        subprocess.Popen(
            ["bash", "-l", sh_path],
            stdin=devnull, stdout=logf, stderr=subprocess.STDOUT,
            start_new_session=True, close_fds=True,
        )
        logf.close()
        devnull.close()
    except Exception as e:
        messagebox.showerror("pdkgui", "Failed to launch viewer:\n%s" % e)
