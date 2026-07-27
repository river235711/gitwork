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
import re
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


def central_xrc_paths(design):
    """XRC.inc as a 'key = value' file (parsed by read_conf), holding the four
    central XRC files:  hcell, xcell (run-script ln -sf sources), rules (the
    .../include_for_xrc/XRC_calibre.<ver> base) and deck (the DFM_LVS_RC deck).
    Returns {} when the file is absent. Unlike DRC.inc (a single deck-path line)
    XRC.inc is multi-key because XRC needs four paths."""
    return read_conf(central_include_file("XRC", design))


def central_skipper_conf(design):
    """<DEFAULT_COM_DIR>/<DESIGN>/SKIPPER.conf -- skipper viewer paths
    (keys: cdsTech, cdsDisp, cdsLayerMap, init; init optional)."""
    return os.path.join(DEFAULT_COM_DIR, design, "SKIPPER.conf")


# Design-independent central files: these live at the TOP of the central dir
# (not under <DESIGN>/), so every user reads the same file whatever PROCESS /
# design is selected.   <MODULE>: <filename at <DEFAULT_COM_DIR>/>
CENTRAL_SHARED_FILES = {
    "SYSTEM": "system.txt",     # revision history, same for all designs
}


def central_shared_file(module):
    """<DEFAULT_COM_DIR>/<filename> for a design-independent module, or None."""
    name = CENTRAL_SHARED_FILES.get(module)
    return os.path.join(DEFAULT_COM_DIR, name) if name else None


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

# --------------------------------------------------------------------------
# DOC page
# --------------------------------------------------------------------------
# Document index: one line per document, three '|' separated fields
#     <Doc. No.>|<Doc ID>|<Title>
# e.g. DesignRule|T-N22-CL-DR-001|TSMC 22 NM ... DESIGN RULE (CLN22ULP/...)
# It lives in the central dir per PROCESS/design (see central_doc_file); the
# built-in data/doc/DOC.txt is the fallback when central is unreachable.
DOC_INDEX_FALLBACK = os.path.join(DATA_DIR, "doc", "DOC.txt")

# The PDFs live in the central dir too, next to the DOC.txt of that process:
#     <DOC_ROOT>/<DESIGN>/doc/<Doc. No.>/<Doc ID>/*.pdf
# DOC_ROOT defaults to the central dir, so everything belonging to a process
# stays under <DEFAULT_COM_DIR>/<DESIGN>/. Point PDKGUI_DOC_ROOT elsewhere only
# if the PDF tree has to be hosted on a different share.
DOC_ROOT = os.environ.get("PDKGUI_DOC_ROOT", DEFAULT_COM_DIR)
DOC_SUBDIR = "doc"


def central_doc_file(design):
    """<DEFAULT_COM_DIR>/<DESIGN>/DOC.txt -- the document index for this process."""
    return os.path.join(DEFAULT_COM_DIR, design, "DOC.txt")


def doc_index_file(design):
    """The DOC index actually used: central first, built-in data/ as fallback."""
    path = central_doc_file(design)
    return path if os.path.isfile(path) else DOC_INDEX_FALLBACK


def doc_group_dir(design, docno, docid):
    """<DOC_ROOT>/<DESIGN>/doc/<Doc. No.>/<Doc ID> -- that document's .pdf files."""
    return os.path.join(DOC_ROOT, design, DOC_SUBDIR, docno, docid)


def read_doc_index(design):
    """Parse the DOC index into [(docno, docid, title), ...] keeping file order.
    Lines that are blank, '#' comments, or lack the two separators are skipped."""
    docs = []
    for line in read_lines(doc_index_file(design)):
        parts = line.split("|", 2)          # title may itself contain '|'
        if len(parts) == 3:
            docno, docid, title = (p.strip() for p in parts)
            if docno and docid:
                docs.append((docno, docid, title))
    return docs

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

    Priority: environment-variable override > central shared copy (if it
    exists) > PAGE_FILES (the built-in file shipped in data/).
    Returns None when there is no setting.
    """
    env_var = _ENV_OVERRIDES.get(module_name)
    if env_var and os.environ.get(env_var):
        return os.path.abspath(os.path.expanduser(os.environ[env_var]))

    shared = central_shared_file(module_name)
    if shared and os.path.isfile(shared):
        return shared

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


# --------------------------------------------------------------------------
# One-time migration from the pre-session layout. Old files sit directly in
# USER_DIR, module and design concatenated without a separator:
#   .pdkgui.<module lowercase><DESIGN>.commandfile   verify tabs, raw command text
#     -> session/<DESIGN>/<MODULE>.json   {"__command__": text}
#   .pdkgui.<module lowercase><DESIGN>.gui           GDS lists, 'layout_pathN <path>'
#     -> session/<DESIGN>/<MODULE>.json   {"gds": [path, ...]}
# The old files are never deleted; the marker records which steps already ran.
# --------------------------------------------------------------------------
LEGACY_PREFIX = ".pdkgui."
LEGACY_MARKER = ".migrated"                 # JSON {"version": n, "done": [step]}
LEGACY_MARKER_V1 = ".migrated_commandfile"  # marker written by the first version
# Bumped whenever the steps change: a marker from an older version is ignored so
# every step runs once more (they merge, so this cannot lose anything).
MIGRATION_VERSION = 2
GDS_LIST_MODULES = ["SKIPPER", "KLAYOUT"]
GDS_LIST_ROWS = 10                          # pad to the row count of the GDS pages

_RE_LEGACY_GDS_ROW = re.compile(r'^layout_path(\d+)\s+(.+?)\s*$', re.IGNORECASE)


def _split_legacy_stem(stem, modules):
    """'drct22_1p7m_4x1z1u' -> ('DRC', 't22_1p7m_4x1z1u').

    Module and design are concatenated without a separator, so match the known
    module names (longest first) against the front of the stem."""
    for module in sorted(modules, key=len, reverse=True):
        low = module.lower()
        if stem.startswith(low) and len(stem) > len(low):
            return module, stem[len(low):]
    return None


def _legacy_command_state(path, existing):
    """Old .commandfile -> verify-tab session state. The old text is used only
    when the session has no command of its own, so newer work is never lost."""
    if (existing.get("__command__") or "").strip():
        return None
    text = read_text(path, default=None)
    if text is None:
        return None
    state = dict(existing)
    state["__command__"] = text
    return state


def _legacy_gds_state(path, existing):
    """Old .gui ('layout_path1 <path>' per line) -> GDS-list session state.

    Rows are placed by their number; a row the user already filled in is kept
    and only the empty ones are taken from the old file."""
    rows = {}
    for line in read_text(path).splitlines():
        m = _RE_LEGACY_GDS_ROW.match(line.strip())
        if m:
            rows[int(m.group(1))] = m.group(2)
    if not rows:
        return None
    current = existing.get("gds") or []
    if not isinstance(current, list):
        current = []
    merged = []
    for i in range(max(GDS_LIST_ROWS, max(rows), len(current))):
        cur = current[i] if i < len(current) and isinstance(current[i], str) else ""
        merged.append(cur if cur.strip() else rows.get(i + 1, ""))
    if merged == current:
        return None             # the list already holds everything
    state = dict(existing)
    state["gds"] = merged
    return state


def _migrate_step(names, suffix, modules, build_state):
    """Convert every USER_DIR file with this suffix, merging into any session
    JSON that already exists (build_state returns None when there is nothing to
    add, so existing work is never overwritten)."""
    migrated = []
    for name in names:
        if not (name.startswith(LEGACY_PREFIX) and name.endswith(suffix)):
            continue
        parsed = _split_legacy_stem(name[len(LEGACY_PREFIX):-len(suffix)], modules)
        if not parsed:
            continue
        module, design = parsed
        dest = user_session_file(module, design)
        existing = load_json(dest) if os.path.exists(dest) else {}
        if not isinstance(existing, dict):
            existing = {}
        state = build_state(os.path.join(USER_DIR, name), existing)
        if not state:
            continue
        save_json(dest, state)
        migrated.append((name, dest))
    return migrated


def _migrations_done():
    """Steps already carried out (understands the first version's marker too).

    A marker written by an older MIGRATION_VERSION is ignored: the steps became
    merge-based (they only fill in what is missing), so running them once more
    is safe and recovers state an earlier, skip-if-present run left behind."""
    data = load_json(os.path.join(USER_DIR, LEGACY_MARKER))
    if data.get("version", 1) < MIGRATION_VERSION:
        return set()
    done = set(data.get("done", []))
    if os.path.exists(os.path.join(USER_DIR, LEGACY_MARKER_V1)):
        done.add("commandfile")
    return done


def migrate_legacy_user_files():
    """Convert the old per-tab files into session JSONs. Returns [(old, new), ...].

    Each step runs at most once; new steps still run for users who already
    migrated with an earlier version."""
    steps = (
        ("commandfile", ".commandfile", VERIFY_MODULES, _legacy_command_state),
        ("gui", ".gui", GDS_LIST_MODULES, _legacy_gds_state),
    )
    done = _migrations_done()
    todo = [s for s in steps if s[0] not in done]
    if not todo:
        return []
    try:
        names = os.listdir(USER_DIR)
    except OSError:
        return []               # no ~/.pdkgui yet: nothing to migrate

    migrated = []
    for step, suffix, modules, build_state in todo:
        migrated += _migrate_step(names, suffix, modules, build_state)
        done.add(step)
    # recorded even when nothing matched, so each scan happens only once
    save_json(os.path.join(USER_DIR, LEGACY_MARKER),
              {"version": MIGRATION_VERSION, "done": sorted(done)})
    return migrated
