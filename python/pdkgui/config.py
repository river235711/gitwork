#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
config.py
---------
Central configuration for pdkgui.

* You mainly specify here "which file each tab reads". *
Every page (pages/*.py) obtains its file path via page_file(<module>), so paths
are not hard-coded in the page logic. To swap a file, just edit PAGE_FILES.

Three ways to specify a file:
  1. filename relative to data/ (default)   e.g. "system.txt"
  2. absolute path                           e.g. "/datacenter/proj/system.txt"
  3. environment-variable override           e.g. PDKGUI_SYSTEM_FILE=/path/xxx.txt
"""

import os
import json

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

# --------------------------------------------------------------------------
# Default command files: kept in a central (golden) directory, one subdir per
# design:   <DEFAULT_COM_DIR>/<DESIGN>/<MODULE>.com
# Change the default below to your central path, or override via env
# PDKGUI_DEFAULT_DIR.
# --------------------------------------------------------------------------
DEFAULT_COM_DIR = os.environ.get(
    "PDKGUI_DEFAULT_DIR",
    "/datacenter/users/will.huang/work/tmp2/pdkgui/central_example",   # <- change to your central dir
)


def central_default_file(module, design):
    """<DEFAULT_COM_DIR>/<DESIGN>/<MODULE>.com -- central default command file."""
    return os.path.join(DEFAULT_COM_DIR, design, "%s.com" % module)


def central_include_file(module, design):
    """<DEFAULT_COM_DIR>/<DESIGN>/<MODULE>.inc -- latest fab deck path (one line).

    On tab open / on Run, pdkgui rewrites the command file's include line to the
    path stored here. To update the deck, just edit this one-line file."""
    return os.path.join(DEFAULT_COM_DIR, design, "%s.inc" % module)


def central_skipper_conf(design):
    """<DEFAULT_COM_DIR>/<DESIGN>/SKIPPER.conf -- skipper viewer paths
    (keys: cdsTech, cdsDisp, cdsLayerMap, init; init optional)."""
    return os.path.join(DEFAULT_COM_DIR, design, "SKIPPER.conf")


# --------------------------------------------------------------------------
# Per-user state directory (each user's "last time" working state; override via
# env PDKGUI_USER_DIR).
#   <USER_DIR>/session/<DESIGN>/<MODULE>.json   per-tab fields + command text
# --------------------------------------------------------------------------
USER_DIR = os.path.expanduser(os.environ.get("PDKGUI_USER_DIR", "~/.pdkgui"))
SESSION_SUBDIR = "session"


def user_session_file(module, design):
    """<USER_DIR>/session/<DESIGN>/<MODULE>.json -- each user's last state."""
    return os.path.join(USER_DIR, SESSION_SUBDIR, design, "%s.json" % module)


def user_global_file(name):
    """<USER_DIR>/session/<name>.json -- global (not per-design) session state,
    e.g. the PROCESS design and ENV tool selections."""
    return os.path.join(USER_DIR, SESSION_SUBDIR, "%s.json" % name)


def load_json(path, default=None):
    """Read a JSON file; return default (or {}) on failure."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {} if default is None else default


def save_json(path, obj):
    """Write obj as JSON (no exception on failure)."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
    except OSError:
        pass

# --------------------------------------------------------------------------
# General settings
# --------------------------------------------------------------------------
DESIGN_NAME = "t22_1p7m_4x1z1u"     # window title shows "pdkgui - <DESIGN_NAME>"

# --- Logo settings: point this at your own image ---
LOGO_PATH = os.path.join(BASE_DIR, "company_logo.png")
LOGO_TEXT = "YOUR COMPANY LOGO"     # fallback text when the image is not found
LOGO_BG = "#0b5fa5"
LOGO_FG = "white"

# klayout executable for the KLAYOUT tab (independent of PROCESS / design).
# Override via env PDKGUI_KLAYOUT.
KLAYOUT_BIN = os.environ.get("PDKGUI_KLAYOUT", "/usr/bin/klayout")

# Left-hand menu items (screenshot order)
MENU_ITEMS = [
    "PROCESS", "ENV", "DRC", "ANT", "WB", "BUMP", "DMDV", "DPDO",
    "LVS", "XRC", "JIVARO", "SKIPPER", "KLAYOUT", "DOC", "SYSTEM",
]

# Modules that use the "verification flow" page template
VERIFY_MODULES = ["DRC", "ANT", "WB", "BUMP", "DMDV", "DPDO", "LVS", "XRC", "JIVARO"]

# --------------------------------------------------------------------------
# * Each tab -> the file it reads (path relative to data/) *
# --------------------------------------------------------------------------
PAGE_FILES = {
    "SYSTEM":  "system.txt",     # revision history
    "PROCESS": "process.txt",    # selectable process / design list (one per line)
    "ENV":     "env.txt",        # tool version settings
    "SKIPPER": "skipper.txt",    # recently opened GDS list (one per line)
    # command files for the verify modules:
    "DRC":     "verify/DRC.com",
    "ANT":     "verify/ANT.com",
    "WB":      "verify/WB.com",
    "BUMP":    "verify/BUMP.com",
    "DMDV":    "verify/DMDV.com",
    "DPDO":    "verify/DPDO.com",
    "LVS":     "verify/LVS.com",
    "XRC":     "verify/XRC.com",
    "JIVARO":  "verify/JIVARO.com",
}

# DOC page content directory (one .txt per document; filename == document name)
DOC_DIR = os.path.join(DATA_DIR, "doc")

# Source directory for the XRC hcell / xcell symbolic links (per PDK / process).
# The run script does:  ln -sf <this dir>/hcell   and   ln -sf <this dir>/xcell
# Override via env PDKGUI_XRC_HCELL_DIR.
XRC_HCELL_DIR = os.environ.get(
    "PDKGUI_XRC_HCELL_DIR",
    "/datacenter/techLibs/tsmc/T22N/tools/pdk_sirius/T22N/calibre_layout/"
    "tsmc/T22/T22ULL_1P7M_4X1Z1U/layout_run/xrc",
)

# To override a tab's file via an environment variable, list the mapping here.
# e.g. export PDKGUI_SYSTEM_FILE=/path/to/xxx.txt
_ENV_OVERRIDES = {
    "SYSTEM":  "PDKGUI_SYSTEM_FILE",
    "PROCESS": "PDKGUI_PROCESS_FILE",
    "ENV":     "PDKGUI_ENV_FILE",
    "SKIPPER": "PDKGUI_SKIPPER_FILE",
}


def page_file(module_name):
    """Return the absolute path of the file a tab should read.

    Priority: environment-variable override > PAGE_FILES.
    Returns None when there is no setting.
    """
    env_var = _ENV_OVERRIDES.get(module_name)
    if env_var and os.environ.get(env_var):
        return os.path.abspath(os.path.expanduser(os.environ[env_var]))

    rel = PAGE_FILES.get(module_name)
    if rel is None:
        return None
    if os.path.isabs(rel):
        return rel
    return os.path.join(DATA_DIR, rel)


def read_text(path, default=""):
    """Read a plain text file; return default on failure (no exception)."""
    if not path:
        return default
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return default


def read_lines(path):
    """Read a file and return non-empty, non-comment (#) lines."""
    lines = []
    for raw in read_text(path).splitlines():
        s = raw.strip()
        if s and not s.startswith("#"):
            lines.append(s)
    return lines


def read_conf(path):
    """Parse 'key = value' lines into a dict (uses read_lines, so #-comments and
    blank lines are skipped)."""
    conf = {}
    for line in read_lines(path):
        if "=" in line:
            k, v = line.split("=", 1)
            conf[k.strip()] = v.strip()
    return conf
