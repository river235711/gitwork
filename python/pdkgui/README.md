# pdkgui

A Tkinter GUI modeled on an internal EDA flow manager (PROCESS / ENV / DRC / ANT
/ WB / BUMP / DMDV / DPDO / LVS / XRC / JIVARO / SKIPPER / KLAYOUT / DOC /
LOADING / SYSTEM).

## File layout

Three groups, and which of them a deployed build contains:

**The program** -- shipped, and encrypted except for the bootstrap:

```
pdkgui              launcher (bash): find a tkinter python, then run
pdkgui.py           bootstrap (stays plaintext, no logic): install the
                    encrypted import hook -> pdkgui_app.main()
pdkgui_app.py       main window + left menu + page routing
config.py           central settings (which file each tab reads, paths, constants)
widgets.py          shared widgets (ScrolledText with two scrollbars, LogoPanel)
pages/              per-tab pages
    base.py  process.py  env.py  verify.py  skipper.py
    klayout.py  doc.py  loading.py  system.py  __init__.py (page registry)
data/               files that ship with the release
                    (system.txt / process.txt / env.txt / hosts.txt /
                     verify/*.com)
```

**Decryption, needed at run time** -- also shipped, and necessarily plaintext,
since the build has to be able to decrypt itself:

```
pdkcrypt.py         encryption core (stdlib only: PBKDF2 + HMAC-CTR + encrypt-then-MAC)
pdk_secure.py       runtime loader + encrypted-module import hook
```

**Development only** -- never shipped, no effect on a running pdkgui:

```
pdk_pack.py         single-file encryptor (.py -> .pdkc)
pdk_build.py        produce the full encrypted deploy build dist/
central_migrate.py  convert an old flat central directory to the new layout
central_example/    example central dir (the test suite builds its sandbox from it)
README.md
```

These all sit in one directory on purpose: `pdkgui.py` imports `pdk_secure` at
start-up and the import hook resolves `.pdkc` next to itself, while `pdk_build`
decides what to pack from its own directory. Moving the packaging tools into a
subdirectory would mean changing several path derivations to gain two fewer
files in a listing -- not a trade worth making.

`dist/` and `__pycache__/` are build output and are not committed; delete them
freely and rebuild with `pdk_build.py`.

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

The key has to ship (the build must decrypt itself), pinned into the plaintext
`dist/pdkcrypt.py`, so `pdk_secure.load_source("config.pdkc")` returns the source
to anyone holding the build. That is inherent, and it is why the PBKDF2 iteration
count is low: a high count only slows down *guessing an unknown* passphrase, and
nothing is guessed here -- it cost ~0.4 s per module on the EDA hosts and bought
nothing. The files are equally unreadable at any count.

Every file of a build shares one salt so the key is derived once per process
rather than once per module; the nonce stays random per file. The count is
recorded in each file's header, so builds made before this still load.

## What lives where

Two sources, and the split is deliberate:

- **`data/`, shipped inside each release** -- `system.txt` (the revision
  history), `process.txt` (the selectable processes), `env.txt` (tool versions),
  `hosts.txt` (the machines the LOADING tab watches), and the fallback
  `verify/*.com` templates. These describe *the program*, so
  each release carries its own: `pdkgui v2026.0737` shows the history as of that
  release, and someone on an older one is not told about features it lacks.
  Changing them means a release.
- **the central directory, shared by every release** -- everything that
  describes *a process*: `<DESIGN>/*.com`, `*.inc`, `SKIPPER.conf`, `DOC.txt`
  and the `doc/` PDFs. A deck update is an edit to one `.inc`, picked up on the
  next tab open with no release at all.

There is deliberately no built-in fallback for `DOC.txt`, and nothing seeds the
SKIPPER/KLAYOUT lists: one process's documents are wrong for another, and an
example GDS path helps nobody. When those are missing the tab says so.

## Default command files (central golden directory)

The default command files for the verify pages
(DRC/ANT/WB/BUMP/DMDV/DPDO/LVS/XRC) live in a central directory, one subdir per
design (set via `config.DEFAULT_COM_DIR`, or override with env
`PDKGUI_DEFAULT_DIR`):

```
<DEFAULT_COM_DIR>/<DESIGN>/<MODULE>.com     golden command-file template (LoadDefault reads this)
<DEFAULT_COM_DIR>/<DESIGN>/<MODULE>.inc     latest fab deck path (one line, optional)
<DEFAULT_COM_DIR>/<DESIGN>/XRC.inc          four XRC paths as key=value (hcell/xcell/rules/deck)
<DEFAULT_COM_DIR>/<DESIGN>/DOC.txt          document index: <Doc. No.>|<Doc ID>|<Title> per line
<DEFAULT_COM_DIR>/<DESIGN>/doc/<Doc. No.>/<Doc ID>/*.pdf    the documents themselves
<DEFAULT_COM_DIR>/<DESIGN>/SKIPPER.conf     skipper viewer paths (cdsTech/cdsDisp/cdsLayerMap/init)
```

- The LoadDefault button reads `.com`; if the central file is missing it falls
  back to the built-in template `data/verify/<MODULE>.com`.
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

Three linked columns driven by `<DEFAULT_COM_DIR>/<DESIGN>/DOC.txt`, one line
per document:

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

## LOADING tab (which machine to use)

Users share a handful of hosts, so before starting a verification the question is
always "which one is free". The tab answers it directly:

```
Machine loading                                                    [Refresh]
Best right now: sirius05  (12% CPU, 210 GB free)

  sirius01  ██████░░░░  58%  ███░░░░░░░  79 GB free  busy    [Terminal] [pdkgui]
  sirius05  ██░░░░░░░░  12%  █░░░░░░░░░ 210 GB free  idle    [Terminal] [pdkgui]
  sirius07  no answer (ssh: connect to host sirius07 port 22: No route to host)
```

The machines come from `data/hosts.txt` (one per line, `#` comments; override
with `PDKGUI_LOADING_FILE`). A machine that can only be reached through another
one carries its route:

```
sirius02
sirius03  via will.huang@wswillhuang        # -> ssh -J will.huang@wswillhuang sirius03
will.huang@sirius03 via ...                 # when the login differs there too
```

`-J` makes the hop in one command: the session to the machine is still end to
end, so `BatchMode`, the timeout and X11 forwarding apply to *it* and not merely
to the host in the middle -- a window opened on sirius03 still appears where
pdkgui is running. (`-J` needs OpenSSH 7.3+ on the machine pdkgui runs on;
`ssh -V` says.) The row is labelled with the machine, never the login.

Each machine is asked for its figures with one command that reads `/proc` only
-- no scheduler, no tool that might not be installed:

```
cat /proc/loadavg; nproc; awk '/^Mem(Total|Available):/{print $1, $2}' /proc/meminfo
```

- The machine pdkgui runs on is read directly; the rest over
  `ssh -o BatchMode=yes -o ConnectTimeout=3`, so a host without a key fails at
  once instead of waiting on a password prompt, and the row shows ssh's own
  reason (a host key never accepted looks just like a machine that is down).
- **CPU% = 1-minute load average / core count**, which is what a load figure
  means once you know the machine: load 8 on 32 cores is idle.
- The verdict is the **worse** of cpu and free memory -- an idle machine with
  2 GB left cannot run a verification, so it is not offered as the best pick
  either (`_contention` in `pages/loading.py`).
- All the probes go out together and are collected by a poll on the Tk event
  loop (no threads); each row fills in as its own machine answers, one that
  hangs is given up on after `PROBE_TIMEOUT`, and the recommendation appears from
  whatever has answered so far. Leaving the tab cancels the poll and kills any
  ssh still running (`flush()`, called by `pdkgui_app._flush_page`).
- Refreshed on tab open, on **Refresh**, and every `REFRESH_EVERY` (30 s) while
  this tab is the one on screen -- switching away stops it, so nothing keeps
  ssh-ing in the background. 30 s because the load average is itself a 1-minute
  mean; asking faster cannot make the number fresher.

Two buttons on each row, from `shell_command()`:

- **Terminal** -- `ssh -X -t <host> 'exec $SHELL -l'` in a terminal emulator
  (`config.terminals()`, the same list the Run buttons use). A *login* shell,
  because the EDA tools come from Environment Modules, which a plain
  `ssh host command` shell has never sourced; `-t` because ssh allocates no pty
  when it is given a command.
- **pdkgui** -- the same, with pdkgui started in the background first, so one
  click gives both a shell and a window. The launcher is
  `config.live_launcher()` (the current release), falling back to the one beside
  the running code: an absolute path on the shared filesystem, so it means the
  same thing on the other machine and no site path is hard-coded. Both open in
  the directory this window was started from.

The machine pdkgui is already on gets a plain local shell, no ssh.

### `pdkgui -l` -- the chooser on its own

Choosing a machine comes *before* deciding to work anywhere, so it should not
need the whole window:

```bash
pdkgui -l          # or --loading
```

opens the LOADING page alone -- white, no menu down the side, sized to its own
content -- and the `pdkgui` button on the machine you pick starts the **full**
window there. Implemented as `PdkGui(only="LOADING")`; what that mode skips is as
much the point as what it does:

- **the open tab is not saved on close** (`_save_ui_state`), or the full pdkgui
  would open on LOADING next time instead of where the user left it;
- the ENV/PROCESS session is not read (this page uses neither, and the title says
  `- loading` rather than a design);
- the legacy migration does not run -- a chooser has no business rewriting the
  user's files;
- `pages.verify` is not warmed up, since no tab in this window can reach it.

`pdkgui --help` lists the options; an unknown one exits 2 rather than being
ignored.

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

### Revision history convention (`data/system.txt`)

Every change to the program gets a line at the **top** of the table, so users on
the SYSTEM tab can see what the release they are running actually changed:

```
Revision     Date          Description
----------   ----------    ---------------------------------------------------
2026.073001  2026/07/30    * [Function] New function of LOADING ...
                           * [Function] LVS and XRC of RVE always open svdb
```

- Revision = `<YYYY>.<MMDD>` for the first entry of a day, then `01`, `02` ...
  appended for further ones the same day (`2026.073001`).
- A software change needs only `[Function]` items. `[Commandfile]` is for a deck
  swap, which is a central `.inc` edit rather than a release.
- Column widths: revision 13, date 14, continuation lines indented 27.

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

## Speed on the EDA hosts

Everything pdkgui reads sits on NFS, where each open is a network round trip, so
the work went into not paying the same cost twice:

- **Starting up** -- the launcher tries the python already on PATH first and only
  touches Environment Modules if it has no tkinter, which skips `module purge`
  (the slowest step, and it would unload whatever you had loaded). Set
  `PDKGUI_MODULE_PURGE=0` to keep the purge out of the way when a load is needed
  anyway. Page modules are imported when their tab is first opened rather than
  all nine at start-up.
- **Switching tabs** -- pages are built once and re-shown, instead of being
  destroyed and rebuilt from the central files every time. Anything that must
  not go stale is refreshed in the page's `on_show()`: the verify tabs re-read
  the deck pointer, SYSTEM re-checks which release is current. The open tab is
  saved when you leave rather than on every click.
- **Repeat reads** -- `config` caches file contents against the timestamp, so a
  second read costs one `stat`. Editing a central `.inc` still takes effect on
  the next tab open or Run: the new timestamp misses the cache. Every Run does
  check -- three Runs stat the `.inc` three times and only re-read it when it
  changed.

  One NFS caveat: opening a file revalidates its attributes with the server,
  while a `stat` can be answered from the client's attribute cache for a few
  seconds. A deck edited on *another* host can therefore take those few seconds
  longer to be noticed than before. `PDKGUI_NO_CACHE=1` reads every time, for
  when that matters or to rule the cache out while debugging.

Measured locally (the NFS saving is larger): switching between six tabs went
from 18.3 ms and 5 central reads per round to 4.0 ms and none; an XRC Run reads
`XRC.inc` zero times instead of twice.

`PDKGUI_TIMING=1 pdkgui` prints what each step cost to stderr, which is the way
to see the real numbers on a host where the files are remote.

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

## Opening things outside pdkgui

The **FileManager** button, **Edit**, and clicking a PDF on the DOC tab start
ordinary desktop programs. Two things are deliberate there:

- **`xdg-open` is the last resort, not the first.** On some setups it hands the
  `.desktop` `Exec` line over without expanding the field codes, so the file
  manager is launched as `dolphin %i -caption "%c" <path>` and opens a tab
  literally named `%i`. Calling a file manager directly avoids that. The order
  is `caja, nautilus, thunar, nemo, pcmanfm, dolphin, xdg-open`; set
  `PDKGUI_FILEMANAGER=<name>` to force one.
- **They do not inherit `LD_LIBRARY_PATH`.** pdkgui runs in a shell with EDA
  modules loaded, so that variable points into the tool trees -- dolphin picked
  up calibre's `libpng15` from it and failed to start properly. Desktop programs
  are built against the system libraries, so `config.desktop_env()` drops it for
  them. The GDS viewers keep theirs: they run from a shell script that does its
  own `module load`.

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
