# pdkgui

A Tkinter GUI modeled on an internal EDA flow manager (PROCESS / ENV / DRC / ANT
/ WB / BUMP / DMDV / DPDO / LVS / XRC / JIVARO / SKIPPER / KLAYOUT / DOC / SYSTEM).

## File layout

```
pdkgui/
├── pdkgui              launcher (bash): module-load a tkinter python, then run
├── pdkgui.py           bootstrap (plaintext, no logic): install the encrypted
│                       import hook -> pdkgui_app.main()
├── pdkgui_app.py       main window + left menu + page routing
├── config.py           central settings (which file each tab reads, paths, constants)
├── widgets.py          shared widgets (ScrolledText with two scrollbars, LogoPanel)
├── pages/              per-tab pages
│   ├── base.py  process.py  env.py  verify.py  skipper.py
│   ├── klayout.py  doc.py  system.py  __init__.py (page registry)
├── data/               content files each tab reads (system.txt / env.txt / verify/*.com / doc/*)
├── pdkcrypt.py         encryption core (stdlib only: PBKDF2 + HMAC-CTR + encrypt-then-MAC)
├── pdk_secure.py       runtime loader + encrypted-module import hook
├── pdk_pack.py         single-file encryptor (.py -> .pdkc)
└── pdk_build.py        produce the full encrypted deploy build dist/
```

## Running (development)

Run directly from the source directory (with no .pdkc present the import hook
does nothing and the plaintext .py load as usual):

```bash
./pdkgui                 # or  python3 pdkgui.py
```

The launcher loads a tkinter-capable python via Environment Modules
(`module load python/3.6.3`; override with `PDKGUI_MODULE` / `PDKGUI_PYTHON`) and
starts in the background. Needs an X display (`ssh -X`).

## Encrypted deployment

```bash
python3 pdk_build.py dist        # produce dist/; the key is pinned into dist/pdkcrypt.py
dist/pdkgui                      # run directly, no environment variables needed
```

- In `dist/` only the bootstrap and decryptor are plaintext; the rest
  (`config`/`widgets`/`pdkgui_app`/`pages/*`) are `.pdkc`, so tracing/reading the
  files reveals no logic source.
- The key is **pinned into `dist/pdkcrypt.py`** and env vars are ignored at
  runtime -- it runs anywhere regardless of a stray `PDKGUI_KEY`, no unset needed.
  For a custom key: `PDKGUI_KEY=xxx python3 pdk_build.py dist`.
- `dist/` is a reproducible artifact and is **not committed**; rebuild it with
  `pdk_build.py` when deploying.

### Security level

Client-side protection = **encryption at rest + obfuscation**: the decryption key
ships with the program, so the files on disk are ciphertext and plaintext only
lives briefly in memory. It stops casual `cat`/trace, but not decompilation or a
memory dump. For stronger protection use **Cython** (compile to `.so`) or a tool
like **PyArmor**.

## Default command files (central golden directory)

The default command files for the verify pages
(DRC/ANT/WB/BUMP/DMDV/DPDO/LVS/XRC) live in a central directory, one subdir per
design (set via `config.DEFAULT_COM_DIR`, or override with env
`PDKGUI_DEFAULT_DIR`):

```
<DEFAULT_COM_DIR>/system.txt                SYSTEM revision history (design-independent, shared)
<DEFAULT_COM_DIR>/<DESIGN>/<MODULE>.com     golden command-file template (LoadDefault reads this)
<DEFAULT_COM_DIR>/<DESIGN>/<MODULE>.inc     latest fab deck path (one line, optional)
<DEFAULT_COM_DIR>/<DESIGN>/XRC.inc          four XRC paths as key=value (hcell/xcell/rules/deck)
<DEFAULT_COM_DIR>/<DESIGN>/DOC.txt          document index: <Doc. No.>|<Doc ID>|<Title> per line
<DEFAULT_COM_DIR>/<DESIGN>/doc/<Doc. No.>/<Doc ID>/*.pdf    the documents themselves
<DEFAULT_COM_DIR>/<DESIGN>/SKIPPER.conf     skipper viewer paths (cdsTech/cdsDisp/cdsLayerMap/init)
```

- The LoadDefault button reads `.com`; if the central file is missing it falls
  back to the built-in template `data/verify/<MODULE>.com`.
- `system.txt` is **design-independent** (`config.CENTRAL_SHARED_FILES`): it sits
  at the top of the central dir, not under a design, so the SYSTEM tab shows the
  same revision history to every user regardless of the PROCESS selection. Read
  order is `PDKGUI_SYSTEM_FILE` > `<DEFAULT_COM_DIR>/system.txt` >
  built-in `data/system.txt`.
- `.inc` (optional) holds the **latest fab PDK deck path** (one line). On **tab
  open and on Run**, pdkgui rewrites the `include <...>` line in the command to
  the value of `.inc` -- when the deck is updated you edit just this one-line
  file and everyone picks up the new path on their next open/run. If `.inc` is
  absent the existing include is left untouched (backward compatible).
  e.g. `echo /datacenter/.../CLN22ULP_..._<new>.encrypt > <DEFAULT_COM_DIR>/<DESIGN>/DRC.inc`
- **XRC.inc is special**: XRC needs four central paths, so its `.inc` is a
  `key = value` file with keys `hcell`, `xcell`, `rules`, `deck`. On tab open /
  Run, pdkgui symlinks `hcell`/`xcell` in the run folder (`ln -sf`), rebuilds the
  rules include as `include <rules>/<corner>/rules` (corner from the XrcRCCorner
  field) and the deck include as `include <deck>`.

## DOC tab (document browser)

Three linked columns driven by `<DEFAULT_COM_DIR>/<DESIGN>/DOC.txt` (built-in
fallback `data/doc/DOC.txt`), one line per document:

```
<Doc. No.>|<Doc ID>|<Title>
DesignRule|T-N22-CL-DR-001|TSMC 22 NM CMOS LOGIC ULTRA LOW POWER DESIGN RULE (...)
```

- **Doc. No.** (left) -- the unique first fields; clicking one lists its titles.
- **Title** (middle) -- the third field; clicking one lists that document's PDFs.
- **Doc. Group** (right) -- `*.pdf` in
  `<DEFAULT_COM_DIR>/<DESIGN>/doc/<Doc. No.>/<Doc ID>/`; clicking one opens it in
  a viewer (okular / evince / xdg-open ...).

The PDFs sit in the central dir next to that process's `DOC.txt`, so everything
belonging to a process stays under `<DEFAULT_COM_DIR>/<DESIGN>/`. Adding a
document = add its line to `DOC.txt` + drop the PDFs in the matching directory.
Set env `PDKGUI_DOC_ROOT` only if the PDF tree must live on another share (the
`<DESIGN>/doc/...` structure below it is unchanged).

## Deployment layout (versioned install + shared central)

Users always run one stable entry point; releases are switched by repointing a
symlink, and the central configuration is shared by every version:

```
/datacenter/techLibs/cad/bin/
├── pdkgui -> _pdkgui/current/pdkgui/pdkgui   what users run (symlink)
└── _pdkgui/
    ├── 2026.0728/pdkgui/    one release = the contents of dist/
    ├── current -> 2026.0728  flip this to switch or roll back
    └── central/              config.DEFAULT_COM_DIR, shared by all versions
        ├── system.txt
        └── <DESIGN>/{*.com,*.inc,SKIPPER.conf,DOC.txt,doc/}
```

Releasing a new version:

```bash
V=2026.0728
python3 pdk_build.py dist /datacenter/techLibs/cad/bin/_pdkgui/$V/pdkgui
cp -r dist /datacenter/techLibs/cad/bin/_pdkgui/$V/pdkgui
cd /datacenter/techLibs/cad/bin/_pdkgui && ln -sfn $V current
```

Pin the install dir to **that version**, not to `current`: the build is then
self-consistent, and a launcher copied out of it runs the version it came from.
Pinning `current` instead would make a release's behaviour depend on where the
symlink happens to point -- validating a new release before flipping `current`
would silently run the old one.

"Always the newest" is the symlink's job, not `DEFAULT_HOME`'s. Since
`bin/pdkgui` is a symlink, the launcher resolves it, finds `pdkgui.py` in the
release directory and never reads `DEFAULT_HOME` at all; `PDKGUI_HOME` covers
pointing at another version temporarily. `DEFAULT_HOME` is only the fallback for
a launcher *copied* elsewhere.

Keeping `central/` outside the version directories is deliberate: a deck update
is just an edit to one `.inc` and needs no release, and rolling the program back
does not silently roll the decks back with it.

### Telling users a new release is out

Repointing `current` does not affect windows that are already open -- they keep
running the release they started from. pdkgui compares the release it runs from
(`config.BASE_DIR`) with the one `_pdkgui/current` points at:

- The **SYSTEM tab** is split in half: the revision history on top, the version
  panel below. When up to date it shows just the release, e.g. `2026.0729`; when
  the current release has moved on it names both and offers **Restart now**. The
  check runs when the tab is opened, so revisiting SYSTEM refreshes it.
- **Run** on a verification tab asks first -- running a verification from a
  superseded release is the case worth catching. Choosing "run with the version
  you have" is remembered for the rest of the session, so repeated runs are not
  interrupted.
- Restarting saves the session first and reopens on the same tab. Runs already
  launched are in their own terminals and are unaffected.

Two details worth knowing:

- The live release is read from the `current` **symlink**, not from `bin/pdkgui`:
  that entry point may be a *copy* of the launcher rather than a symlink into a
  release, in which case resolving it just yields `bin`. The link is located
  relative to the running release, so no absolute path is baked in (override with
  `PDKGUI_CURRENT_LINK`).
- It compares *directories*, not version numbers -- version names are not
  reliably ordered (`3.6` vs `3.601` vs `2026.0401`), and after a rollback the
  release to move to is the older one. The wording stays neutral for that reason.

Outside a release layout (a source checkout, an unreachable share) the panel just
reports the directory it is running from and nothing else happens.

## Converting an old central directory (central_migrate.py)

The old central directory was flat -- one file per tab+process. `central_migrate.py`
converts it to the new per-process layout:

```
<OLD>/.pdkgui.<tab lowercase><PROCESS>.commandfile  ->  <NEW>/<PROCESS>/<MODULE>.com
<OLD>/.pdkgui.<tab lowercase><PROCESS>.fab          ->  <NEW>/<PROCESS>/<MODULE>.inc
<OLD>/.pdkgui.skipper<PROCESS>.fab                  ->  <NEW>/<PROCESS>/SKIPPER.conf
```

`.fab` holds `key <value>` lines. For DRC/ANT/WB/BUMP/DMDV/DPDO/LVS the `.inc` is
just the `deck` path; for XRC it becomes the four-key file, with `rules` derived
from `rccorner_typical` by stripping the trailing `/typical/rules` (the other
corners carry no extra information -- pdkgui appends `/<corner>/rules` itself --
and are reported if they point somewhere else). The skipper tab has no command
file: its `.fab` (`cdsTech` / `cdsDisp` / `cdsLayerMap` / `init`) becomes
`SKIPPER.conf` in `key = value` form, and any process still without one is
listed at the end of the run.

```bash
python3 central_migrate.py                  # dry run, default paths
python3 central_migrate.py --write          # write
python3 central_migrate.py OLD NEW --write  # explicit paths
```

It is a dry run unless `--write` is given, never overwrites a file that exists
and differs unless `--force`, and prints anything that needs attention (a
missing `deck`, a `.com` with no `.fab`, ...).

## Upgrading from the pre-session version

The older pdkgui stored each tab's state as one flat file per tab+process:

```
~/.pdkgui/.pdkgui.<tab lowercase><PROCESS>.commandfile   verify tabs: the command text
~/.pdkgui/.pdkgui.<tab lowercase><PROCESS>.gui           SKIPPER / KLAYOUT: 'layout_pathN <path>'
```

On the **first start** of this version those are converted automatically into the
session layout (`~/.pdkgui/session/<DESIGN>/<MODULE>.json`) -- `.commandfile`
becomes `{"__command__": ...}` and `.gui` becomes `{"gds": [...]}`. The
conversion:

- never deletes the originals -- the old files stay where they are;
- **merges** rather than replaces: a GDS row you have already filled in is kept
  and only the empty rows are taken from the old file; a command text is only
  taken when the session does not have one. So a tab you already used in the new
  version still picks up the rest of its old state;
- records each step in `~/.pdkgui/.migrated` (with a `version`), so a step runs
  once, and a new or changed step still runs for users who upgraded earlier.
  Delete that file to rescan.

A converted verify session holds only the command text, so the Layout/Source
fields are re-derived from it when the tab opens.

## Interface size

One setting scales the whole GUI -- `config.UI_FONT_SIZE` (default 11), or per
user without editing anything:

```bash
PDKGUI_FONT_SIZE=13 pdkgui
```

Most widgets set no font of their own and follow Tk's named fonts, which the app
resizes on start; the few that do ask for one go through `config.ui_font()` /
`config.mono_font()`, so titles, the menu buttons, command boxes and the ttk
comboboxes all move together. The default window size grows in proportion
(`config.window_geometry()`), so a larger font does not leave the layout cramped.

## GDS viewers (skipper / klayout)

- **SKIPPER** tab and the **View** button on other tabs -> open with `skipper`.
- **KLAYOUT** tab -> same GDS-list UI, but opens with `klayout`
  (`config.KLAYOUT_BIN`, default `/usr/bin/klayout`; override via env
  `PDKGUI_KLAYOUT`). Independent of the PROCESS selection -- no SKIPPER.conf /
  module load needed.

Both generate a shell in `~/.pdkgui/` (never in `./`, so it works even when viewing
a GDS in a directory you cannot write to) and run it in a terminal (falling back to
a detached background launch). Both tabs remember their GDS list **per design** in the
user session (`~/.pdkgui/session/<DESIGN>/SKIPPER.json` / `KLAYOUT.json`), so different
PROCESS selections keep separate GDS lists.

The skipper shell is:

```
#!/bin/bash -l
module load <skipper>      # from the ENV tab
module load <calibre>      # from the ENV tab
skipper -noterm -i <gds> -cdsTech <..> -cdsDisp <..> -cdsLayerMap <..> [-init <..>]
```

The `-cdsTech` / `-cdsDisp` / `-cdsLayerMap` / `init` paths come from
`<DEFAULT_COM_DIR>/<DESIGN>/SKIPPER.conf` (`key = value` lines). `init` is optional:
`-init` is added only when it is set and the file exists, otherwise it is omitted.

## Per-user state `~/.pdkgui/`

Each user's "last time" fields and command text are stored here (override the
root with `PDKGUI_USER_DIR`):

```
~/.pdkgui/session/<DESIGN>/<MODULE>.json    per-tab last working state (fields + command)
```

Tab open read order: **session (last time) -> central default -> built-in template**.
