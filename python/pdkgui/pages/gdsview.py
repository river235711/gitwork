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
    return config.read_conf(config.central_skipper_conf(config.DESIGN_NAME))


def build_skipper_script(app, gds):
    """Return the shell text to open <gds> with skipper."""
    conf = _skipper_conf()
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

    return (
        "#!/bin/bash -l\n"
        "module load %s\n"
        "module load %s\n"
        "%s\n"
    ) % (skipper, calibre, " ".join(cmd))


def open_gds(app, gds):
    """Open a GDS with skipper: write the shell into ~/.pdkgui/ and run it."""
    gds = (gds or "").strip()
    if not gds:
        messagebox.showwarning("pdkgui", "no GDS file specified")
        return
    if not os.environ.get("DISPLAY"):
        messagebox.showerror("pdkgui", "No DISPLAY, cannot open skipper")
        return

    script = build_skipper_script(app, os.path.expanduser(gds))
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
