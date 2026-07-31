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
import time
import socket

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

# --------------------------------------------------------------------------
# Default command files: kept in a central (golden) directory, one subdir per
# design:   <DEFAULT_COM_DIR>/<DESIGN>/<MODULE>.com
# Override via env PDKGUI_DEFAULT_DIR.
#
# It sits NEXT TO the version directories, not inside one:
#   <bin>/_pdkgui/<version>/pdkgui/   the program (one dir per release)
#   <bin>/_pdkgui/current -> <version>
#   <bin>/_pdkgui/central/            this directory, shared by every version
# so a deck update (edit one .inc) needs no release, and rolling the program
# back does not silently roll the decks back with it.
# --------------------------------------------------------------------------
DEFAULT_COM_DIR = os.environ.get(
    "PDKGUI_DEFAULT_DIR",
    "/datacenter/techLibs/cad/bin/_pdkgui/central",   # <- change to your central dir
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
    .../include_for_xrc/XRC_calibre.<ver> base) and deck (the DFM_LVS_RC deck),
    plus an optional fifth:  dfm, exported as TSMC_CAL_DFM_PATH by the run
    script for the processes whose deck needs it.
    Returns {} when the file is absent. Unlike DRC.inc (a single deck-path line)
    XRC.inc is multi-key because XRC needs several paths."""
    return read_conf(central_include_file("XRC", design))


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


# --------------------------------------------------------------------------
# Timing (PDKGUI_TIMING=1)
# --------------------------------------------------------------------------
# The cost that matters is NFS latency on the EDA hosts, which cannot be
# measured anywhere else -- so pdkgui can report its own, to stderr.
TIMING = os.environ.get("PDKGUI_TIMING") not in (None, "", "0")


def timed(label):
    """Context manager printing how long a step took, when timing is on."""
    return _Timer(label) if TIMING else _NoTimer()


class _Timer(object):
    def __init__(self, label):
        self.label = label

    def __enter__(self):
        self._start = time.time()
        return self

    def __exit__(self, *exc):
        import sys
        sys.stderr.write("[pdkgui] %-34s %6.1f ms\n"
                         % (self.label, (time.time() - self._start) * 1000))
        return False


class _NoTimer(object):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


# --------------------------------------------------------------------------
# File cache
# --------------------------------------------------------------------------
# Everything lives on NFS, where each open is a network round trip, and the
# same central files are read several times per action (XRC.inc alone is read
# on tab open and twice more per Run). Contents are cached against the file's
# timestamp and size, so a repeat read costs one stat instead of an open.
#
# This keeps the promise the central layout is built on: edit an .inc and it is
# picked up on the next tab open or Run. A changed file has a new timestamp, so
# the cache misses and the new content is read.
#
# One difference worth knowing on NFS: opening a file revalidates its attributes
# with the server, while a stat can be answered from the client's attribute
# cache (seconds, per the mount's acregmin/acregmax). So a deck edited on
# another host can take a few seconds longer to be noticed than it used to.
# PDKGUI_NO_CACHE=1 turns the cache off and reads every time, for when that
# matters or to rule the cache out while debugging.
# --------------------------------------------------------------------------
CACHE_ENABLED = os.environ.get("PDKGUI_NO_CACHE") in (None, "", "0")

_cache = {}     # path -> (mtime_ns, size, value)


def clear_cache(path=None):
    """Forget one path, or everything (used after a write, and by the tests)."""
    if path is None:
        _cache.clear()
    else:
        _cache.pop(path, None)


def _cached(path, loader):
    """loader() result for path, reused while the file is untouched."""
    if not CACHE_ENABLED:
        return loader()
    try:
        info = os.stat(path)
        stamp = (info.st_mtime_ns, info.st_size)
    except OSError:
        _cache.pop(path, None)
        return loader()          # let the loader deal with the missing file
    hit = _cache.get(path)
    if hit is not None and hit[0] == stamp[0] and hit[1] == stamp[1]:
        return hit[2]
    value = loader()
    _cache[path] = (stamp[0], stamp[1], value)
    return value


def load_json(path, default=None):
    """Read a JSON file; return default (or {}) on failure.

    Parsed fresh each call from the cached text rather than caching the result:
    callers get a dict of their own, so one that modifies what it reads cannot
    corrupt what everyone else sees."""
    text = read_text(path, default=None)
    if text is None:
        return {} if default is None else default
    try:
        return json.loads(text)
    except ValueError:
        return {} if default is None else default


def save_json(path, obj):
    """Write obj as JSON (no exception on failure)."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
    except OSError:
        pass
    finally:
        clear_cache(path)   # the next read must see what we just wrote

# --------------------------------------------------------------------------
# General settings
# --------------------------------------------------------------------------
DESIGN_NAME = "t22_1p7m_4x1z1u"     # see window_title()


def hostname():
    """Short name of the machine, for the window title -- with several sessions
    open across hosts it says which one this window belongs to."""
    try:
        return socket.gethostname().split(".")[0]
    except Exception:
        return ""


def window_title(subject=None):
    """'pdkgui v<release> - <design> (on <host>)'.

    The release and the host are each left out when they cannot be determined
    (not started from a release directory, e.g. a source checkout; no host
    name), so the title never shows an empty field or an invented version.

    `subject` replaces the design, for a window that is not about one -- the
    machine chooser (`pdkgui -l`) passes "loading"."""
    release = running_release()
    title = "pdkgui v%s" % release if release else "pdkgui"
    title += " - %s" % (subject or DESIGN_NAME)
    host = hostname()
    if host:
        title += " (on %s)" % host
    return title

# --------------------------------------------------------------------------
# Fonts -- one place to make the whole GUI bigger.
# Most widgets set no font of their own and follow Tk's named fonts, which the
# app points at UI_FONT_SIZE on start; the few that do ask for one go through
# ui_font()/mono_font(), so everything scales together.
# Raise the number (or set PDKGUI_FONT_SIZE=13) to enlarge the whole interface.
# --------------------------------------------------------------------------
UI_FONT_BASE = 9                    # size the layout was originally drawn at
UI_FONT_SIZE = int(os.environ.get("PDKGUI_FONT_SIZE", "11"))
UI_FONT_FAMILY = "Arial"
MONO_FONT_FAMILY = "Courier New"    # command files / revision history

# Window size at UI_FONT_BASE; scaled with the font so nothing gets cramped.
WINDOW_W, WINDOW_H = 980, 560


def ui_font(delta=0, weight=None):
    """(family, size[, weight]) for a normal widget; delta shifts from the base."""
    size = max(6, UI_FONT_SIZE + delta)
    return (UI_FONT_FAMILY, size, weight) if weight else (UI_FONT_FAMILY, size)


def mono_font(delta=0):
    """Fixed-width font, kept in step with the interface size."""
    return (MONO_FONT_FAMILY, max(6, UI_FONT_SIZE + delta))


def window_geometry():
    """Default window size, grown in proportion to the chosen font size."""
    scale = float(UI_FONT_SIZE) / UI_FONT_BASE
    return "%dx%d" % (int(WINDOW_W * scale), int(WINDOW_H * scale))

# --- Logo settings: point this at your own image ---
LOGO_PATH = os.path.join(BASE_DIR, "company_logo.png")
LOGO_TEXT = "SIRIUS-WIRELESS"     # fallback text when the image is not found
LOGO_BG = "#0b5fa5"
LOGO_FG = "white"

# --------------------------------------------------------------------------
# Desktop helpers (file manager, editor, PDF viewer)
# --------------------------------------------------------------------------
# xdg-open comes last on purpose. On some setups it hands the .desktop Exec
# line to the program without expanding the field codes, so the file manager is
# launched as `dolphin %i -caption "%c" <path>` and opens a tab literally named
# "%i". Calling a file manager directly avoids the whole indirection.
# PDKGUI_FILEMANAGER forces one (e.g. PDKGUI_FILEMANAGER=caja).
FILE_MANAGERS = ("caja", "nautilus", "thunar", "nemo", "pcmanfm", "dolphin",
                 "xdg-open")


def file_managers():
    """File managers to try, best first; PDKGUI_FILEMANAGER wins."""
    forced = os.environ.get("PDKGUI_FILEMANAGER")
    return (forced,) if forced else FILE_MANAGERS


# --------------------------------------------------------------------------
# What each Open dialog offers in its "files of type" list. Kept here because
# the layout list is wanted by two different pages (the verify tabs and the GDS
# viewers), and because these are the site's naming habits rather than logic:
# netlists are not named consistently enough to filter on an extension, so the
# patterns match anywhere in the name.
#
# The first entry is what the dialog opens on; "All types" is always last so a
# file that follows no convention is still reachable.
# --------------------------------------------------------------------------
_ALL_TYPES = ("All types", "*")
FILE_TYPES = {
    # layouts: the compressed ones do not match *.gds, hence the second entry
    "layout": [("*.gds", "*.gds"), ("*.gds.gz", "*.gds.gz"), _ALL_TYPES],
    # schematic netlists for LVS/XRC
    "source": [("*sp*", "*sp*"), ("*spi*", "*spi*"), ("*netlist*", "*netlist*"),
               _ALL_TYPES],
    # JIVARO reduces an extracted netlist, so it sees the XRC output too
    "extracted": [("*sp*", "*sp*"), ("*spi*", "*spi*"), ("*netlist*", "*netlist*"),
                  ("*dist*", "*dist*"), ("*dspf*", "*dspf*"), ("*lump*", "*lump*"),
                  _ALL_TYPES],
}


def file_types(kind):
    """The 'files of type' list for an Open dialog; () when anything goes."""
    return FILE_TYPES.get(kind, ())


# Terminal emulators to try, best first, each with the flag that means "run this
# command". Shared by the Run buttons (a verification in its own window) and the
# LOADING tab (a shell on another machine).
# PDKGUI_TERMINAL forces one, e.g. PDKGUI_TERMINAL=mate-terminal.
TERMINALS = (
    ["xterm", "-fg", "white", "-bg", "black", "-e"],
    ["gnome-terminal", "--"], ["konsole", "-e"],
    ["xfce4-terminal", "-e"], ["mate-terminal", "-e"],
)


def terminals():
    """Terminal emulators to try, best first; PDKGUI_TERMINAL wins.

    A forced one is given "-e", which every emulator here but gnome-terminal
    understands; use PDKGUI_TERMINAL only to pick between the known ones."""
    forced = os.environ.get("PDKGUI_TERMINAL")
    if not forced:
        return TERMINALS
    for term in TERMINALS:
        if term[0] == forced:
            return (term,)
    return ([forced, "-e"],)


def desktop_env():
    """Environment for launching an ordinary desktop application.

    pdkgui runs in a shell with EDA modules loaded, so LD_LIBRARY_PATH points
    into the tool trees; a desktop program inheriting it loads those libraries
    instead of the system ones (dolphin failed on calibre's libpng15 exactly
    this way). These programs are built against the system libraries, so the
    variable is dropped for them. The GDS viewers are unaffected -- they are
    started from a shell script that does its own `module load`."""
    env = dict(os.environ)
    env.pop("LD_LIBRARY_PATH", None)
    return env


# klayout executable for the KLAYOUT tab (independent of PROCESS / design).
# Override via env PDKGUI_KLAYOUT.
KLAYOUT_BIN = os.environ.get("PDKGUI_KLAYOUT", "/usr/bin/klayout")

# Left-hand menu items (screenshot order)
MENU_ITEMS = [
    "PROCESS", "ENV", "DRC", "ANT", "WB", "BUMP", "DMDV", "DPDO",
    "LVS", "LVL", "XRC", "JIVARO", "SKIPPER", "KLAYOUT", "DOC", "LOADING",
    "SYSTEM",
]

# Modules that use the "verification flow" page template
VERIFY_MODULES = ["DRC", "ANT", "WB", "BUMP", "DMDV", "DPDO", "LVS", "LVL",
                  "XRC", "JIVARO"]

# --------------------------------------------------------------------------
# * Each tab -> the file it reads (path relative to data/) *
# --------------------------------------------------------------------------
PAGE_FILES = {
    "SYSTEM":  "system.txt",     # revision history (ships with the release)
    "PROCESS": "process.txt",    # selectable process / design list (one per line)
    "ENV":     "env.txt",        # tool version settings
    "LOADING": "hosts.txt",      # machines whose load the LOADING tab watches
    # SKIPPER / KLAYOUT have no entry on purpose: their GDS lists come from the
    # user's own session, and seeding them from a file only put an example path
    # nobody wants in front of everyone.
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
# It lives in the central dir per PROCESS/design (see central_doc_file). There
# is deliberately no built-in fallback: one process's document list is wrong for
# another, so a missing index says so rather than showing someone else's.

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
    """The DOC index for this process (may not exist; the page says so)."""
    return central_doc_file(design)


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


# --------------------------------------------------------------------------
# Deployed-version detection
# --------------------------------------------------------------------------
# Releases live in <bin>/_pdkgui/<version>/pdkgui/ and <bin>/_pdkgui/current is
# the symlink naming the release everyone should be on. Switching version just
# repoints it, so an instance that is already running stays on the release it
# started from.
#
# The live release is read from that symlink, not from <bin>/pdkgui: the entry
# point users type may be a *copy* of the launcher rather than a symlink into a
# release, in which case resolving it yields <bin> and tells us nothing.
#
# The link is derived from where we are running (BASE_DIR is this file's
# directory -- also correct in a build, where the import hook sets __file__ to
# the .pdkc path), so no absolute path is hard-coded and a source checkout simply
# finds nothing. Override with PDKGUI_CURRENT_LINK.
RELEASE_LINK = "current"


def current_link():
    """<releases root>/current -- sibling of the release we run from."""
    return (os.environ.get("PDKGUI_CURRENT_LINK")
            or os.path.join(os.path.dirname(os.path.dirname(BASE_DIR)), RELEASE_LINK))


def live_install_dir():
    """Install directory inside the release <current> points at, else None."""
    try:
        link = current_link()
        if not os.path.exists(link):
            return None
        # keep our own sub-directory name (…/<version>/pdkgui)
        live = os.path.join(os.path.realpath(link), os.path.basename(BASE_DIR))
        return live if os.path.isdir(live) else None
    except OSError:
        return None


def live_launcher():
    """The launcher script inside the live release (what a restart should run)."""
    live = live_install_dir()
    return os.path.join(live, "pdkgui") if live else None


def release_name(path):
    """Display name of a release directory: '/..._pdkgui/2026.0728/pdkgui'
    -> '2026.0728' (the version dir), otherwise the directory's own name."""
    path = path.rstrip(os.sep)
    head, tail = os.path.split(path)
    return os.path.basename(head) if tail == "pdkgui" and head else tail


def running_release():
    """Name of the release this instance is installed as, else None.

    None means we are not part of the tree the 'current' symlink governs -- a
    source checkout, or a link pointing at someone else's tree -- in which case
    that symlink says nothing about us and no version should be claimed."""
    try:
        link = current_link()
        if not os.path.exists(link):
            return None
        releases_root = os.path.dirname(os.path.realpath(link))
        running = os.path.realpath(BASE_DIR)
        if (os.path.normpath(os.path.dirname(os.path.dirname(running)))
                != os.path.normpath(releases_root)):
            return None
        return release_name(running)
    except OSError:
        return None


def pending_update():
    """(running release, live release, live dir) when the deployed version has
    moved on, else None.

    None also when the link is missing or unreadable, or we are not installed in
    its tree -- a source checkout or a broken share must never disturb the GUI."""
    live = live_install_dir()
    running_name = running_release()
    if not live or not running_name:
        return None
    if os.path.normpath(live) == os.path.normpath(os.path.realpath(BASE_DIR)):
        return None
    return running_name, release_name(live), live


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
    "LOADING": "PDKGUI_LOADING_FILE",
}


def page_file(module_name):
    """Return the absolute path of the file a tab should read.

    Priority: environment-variable override > PAGE_FILES (the file shipped in
    data/, alongside the release). Returns None when there is no setting.
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
    """Read a plain text file; return default on failure (no exception).

    Cached against the file's timestamp (see _cached), which is what spares the
    repeat reads: read_lines and read_conf are built on this, so every central
    file benefits and only the parsing is redone."""
    if not path:
        return default

    def read():
        try:
            with open(path, encoding="utf-8") as f:
                return f.read()
        except OSError:
            return default
    return _cached(path, read)


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
