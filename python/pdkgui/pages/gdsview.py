#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pages/gdsview.py
----------------
Shared "open a GDS with the skipper viewer" flow, used by the SKIPPER tab and by
the View buttons on other tabs.

It generates a shell script in ~/.pdkgui/ (never in ./, since the user may be
viewing a GDS in someone else's directory with no write permission there) and
runs it in the background. The shell looks like:

    #!/bin/bash -l
    module load skipper/2019.06-sp3          # from ENV app.env["skipper"]
    module load calibre/2024.1_36.20         # from ENV app.env["calibre"]
    skipper -noterm -i <gds> -cdsTech <..> -cdsDisp <..> -cdsLayerMap <..> [-init <..>]

The -cdsTech / -cdsDisp / -cdsLayerMap / init paths come from the central config
<DEFAULT_COM_DIR>/<DESIGN>/SKIPPER.conf; -init is included only when set there and
the file exists, otherwise it is omitted.
"""

import os
import subprocess

from tkinter import messagebox

import config


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

    # Diagnostic: record which SKIPPER.conf was looked up and whether it was found,
    # so this shell tells you exactly why cds paths are/aren't present.
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
    """Open a GDS with skipper: write the shell into ~/.pdkgui/ and run it."""
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
    try:
        os.makedirs(config.USER_DIR, exist_ok=True)
        sh_path = os.path.join(config.USER_DIR, "skipper_view.sh")
        with open(sh_path, "w", encoding="utf-8") as f:
            f.write(script)
        os.chmod(sh_path, 0o755)
    except OSError as e:
        messagebox.showerror("pdkgui", "Failed to write skipper script:\n%s" % e)
        return

    try:
        log = open(os.path.join(config.USER_DIR, "skipper_view.log"), "w")
        subprocess.Popen([sh_path], stdout=log, stderr=subprocess.STDOUT)
    except Exception as e:
        messagebox.showerror("pdkgui", "Failed to launch skipper:\n%s" % e)
