# pdkgui tests

Drives a real pdkgui window and checks every tab and every option, without
touching your `~/.pdkgui`, the central directory, or launching calibre.

```bash
cd pdkgui.testing
python3 run_tests.py                 # everything (~3 s)
python3 run_tests.py xrc doc         # only matching test files
python3 run_tests.py -v              # one line per test
python3 run_tests.py --keep          # keep .sandbox to inspect what was written
python3 run_tests.py --src /path/to/pdkgui
```

The tests need a display (they build real Tk widgets). Run them in an X session;
with no `DISPLAY` the runner starts Xvfb if it is installed, otherwise it stops
and says so.

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
