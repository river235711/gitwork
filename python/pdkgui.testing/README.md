# pdkgui tests

Two layers, both driving a real pdkgui window:

| | What it answers |
|---|---|
| `run_tests.py` | Does pdkgui write the right files for every tab and option? Seconds, no calibre. |
| `make_runs.py` | Does **calibre** accept them? Generates a run folder per tab per option from the real central, for you to run. |

Neither touches your `~/.pdkgui` or the central directory.

## Generating run folders to execute (make_runs.py)

```bash
python3 make_runs.py --out ~/pdkgui_runs                       # every process
python3 make_runs.py --out ~/pdkgui_runs --process t22_1p7m_4x1z1u
python3 make_runs.py --out ~/pdkgui_runs --tabs XRC,LVS
python3 make_runs.py --out ~/pdkgui_runs \
    --layout /path/top.gds --primary top \
    --source /path/top.cdl --source-primary top \
    --netlist /path/top.lump          # JIVARO is skipped without this
```

It opens each tab, sets **one** option away from the defaults, and presses Run --
so each folder holds exactly what a user would get, and a failure names the
option that caused it. The cases come from the widgets, so an option added to
pdkgui produces a case here without touching this tool. About 26 cases per
process.

```
~/pdkgui_runs/
├── run_all
├── cases.txt
└── t22_1p7m_4x1z1u/XRC/XrcExtType_rcc/
        calibre_t22_1p7m_4x1z1u_xrc.com
        run                 what you would have got from the GUI
        case.txt            which option this case varies
        run.log  .status    written by run_all
        jivaro.xml          (only where the case turns reduction on)
```

Rve is not among the cases -- `calibre -rve` opens the interactive results
viewer, which does not belong in a batch (and there is nothing to view until the
runs have happened). `--with-rve` generates them anyway.

```bash
./run_all              run every case that has not passed yet
./run_all -n           list what would run
./run_all -j 4         four at a time
./run_all -a           include the ones that already passed
./run_all -x           stop at the first failure
./run_all XRC t22      only cases whose path contains all of these
./run_all -s           show the last result of every case
```

Each case keeps its outcome in `.status` and its output in `run.log`, so a
second `./run_all` picks up only what failed instead of repeating hours of
calibre. Exit status is 1 if anything failed. It reads the central pdkgui is
configured for (`--central` overrides) and writes nothing outside `--out` -- its
session goes to `<out>/.session`, never `~/.pdkgui`.

## Checking the generated files (run_tests.py)

Checks every tab and every option, without touching your `~/.pdkgui`, the
central directory, or launching calibre.

```bash
cd pdkgui.testing
python3 run_tests.py                 # everything (~3 s)
python3 run_tests.py xrc doc         # only matching test files
python3 run_tests.py -v              # one line per test
python3 run_tests.py --keep          # keep .sandbox to inspect what was written
python3 run_tests.py --src /path/to/pdkgui
```

On the EDA hosts the system `python3` has no tkinter -- it comes from a module.
The runner handles that itself: it re-runs under `python/3.6.3` the same way the
`pdkgui` launcher does, so plain `python3 run_tests.py` works there. Override
with `PDKGUI_MODULE=python/<version>` or point `PDKGUI_PYTHON` straight at an
interpreter.

The tests also need a display (they build real Tk widgets, kept hidden). Run
them in an X session or over `ssh -X`; with no `DISPLAY` the runner starts Xvfb
if it is installed, otherwise it stops and says so.

## How it stays out of the way

`sandbox.py` builds `.sandbox/` before pdkgui is imported and points every path
there through the environment, so nothing real is read or written:

```
.sandbox/user/       ~/.pdkgui           PDKGUI_USER_DIR
.sandbox/central/    central dir         PDKGUI_DEFAULT_DIR, PDKGUI_DOC_ROOT
.sandbox/work/       layouts, netlists
.sandbox/releases/   versioned installs  PDKGUI_CURRENT_LINK
```

The command files are copied from the source tree's `central_example`, so the
tests run against the same golden content that ships with pdkgui; a second
design is derived from it so per-process behaviour is genuinely exercised.

`harness.py` replaces everything that would reach outside the process:
`subprocess.Popen` (calibre, skipper, klayout, editors, the restart) is recorded
instead of run, and message boxes and file dialogs are answered from a queue. So
a test presses **Run** and then reads the generated `run` script, and an
unexpected dialog is a failure rather than a hung window.

One deliberate compromise: the editing helpers call the handler a widget is
bound to rather than synthesising `<KeyRelease>`, because Tk only delivers key
events to a window mapped on screen -- synthetic events would make results
depend on the window manager and flash windows across your desktop.
`tests/test_bindings.py` asserts separately that the widgets really are bound to
those handlers, so the wiring stays covered.

## What is covered

| File | Covers |
|------|--------|
| `test_process_env.py` | PROCESS: the design list, selecting each design, persistence. ENV: every tool's versions, defaults, and that the choice reaches `module load` in a run script |
| `test_verify_drc_lvs.py` | DRC/ANT/WB/BUMP/DMDV/DPDO and LVS: fields and buttons, Run/Rve output, field↔text syncing, `//` lines ignored, LoadDefault, the include line following `.inc`, Load/Save, per-tab and per-design state, View and Edit |
| `test_verify_xrc.py` | XRC: option lists and defaults, Format/UseName/Ground rewriting the three `PEX NETLIST` lines, every RC corner rewriting the rules include, ExtType driving `-c`/`-rcc` and the `rm` glob, Reduction adding jivaro and writing `jivaro.xml`, hcell/xcell linked from `XRC.inc`, LvsHier, and SourcePrimary naming the netlists from both the field and the text |
| `test_jivaro_gdslist.py` | JIVARO: File + RunFolder only, `jivaro.xml` contents, `.red` naming for `.lump`/`.dist`. SKIPPER/KLAYOUT: ten rows, per-design lists, skipper's cds paths from `SKIPPER.conf`, klayout independent of the process |
| `test_doc_system.py` | DOC: the three linked columns, PDFs listed for a document, non-PDFs filtered, a missing directory reported, sideways scrolling. SYSTEM: the central history, read-only, split in half, and the release panel up to date / superseded / outside a release |
| `test_session_central.py` | Where files are read from, per-tab and per-design session files, the open tab restored, and the conversion of the old `.commandfile` / `.gui` files including the merge rules |
| `test_bindings.py` | The widgets are wired to the handlers the other tests call |
| `test_make_runs.py` | The generator above: every option gets a case, each case is runnable, `--layout` is applied, `run_all` lists and reports failures, nothing is written outside `--out` |

## Adding a test

Subclass `GuiTestCase`; each test gets a fresh sandbox and a new window.

```python
from harness import GuiTestCase

class MyTab(GuiTestCase):
    def test_run_uses_the_chosen_option(self):
        page = self.open_tab("DRC")
        self.set_entry(page, "RunFolder", self.run_folder())
        self.click(page, "Run")
        self.assertIn("calibre -64 -drc", self.run_script())
```

Useful helpers: `open_tab`, `click`, `button`, `labels`, `widgets`,
`set_entry` / `set_combo` / `set_check` / `set_text`, `set_design`,
`run_script`, `com_file`, `jivaro_xml`, `session`, `active_lines`, and the
`spawned` / `dialogs` / `answers` / `files` recorders.

## Checking the tests still bite

A suite that passes no matter what is worthless. Break something on purpose and
confirm it is caught, e.g. drop `rcc` from `XrcExtType` in `pages/verify.py`, or
swap `lump`/`dist` in `_xrc_netlist_ext` -- both should fail the XRC tests.
