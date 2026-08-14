#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
harness.py
----------
Base class for the pdkgui tab tests.

It gives each test a real pdkgui window (withdrawn, so nothing flashes on
screen) with everything that would reach the outside world replaced by a
recorder:

    spawned      every subprocess.Popen argv (calibre runs, viewers, editors,
                 file managers, the restart)
    dialogs      every messagebox call, as (kind, message)
    answers      what the next messagebox question should return
    files        what the next file dialog should return

So a test can press Run and then read the generated run script instead of
waiting for calibre, and an unexpected dialog shows up as a failure rather than
a hung window.

Tk needs a display: run under an X session, or the runner starts Xvfb.
"""

import os
import sys
import unittest

import sandbox
import stubs


class GuiTestCase(unittest.TestCase):
    """A withdrawn pdkgui window per test, on a freshly built sandbox."""

    design = sandbox.DESIGN

    # ------------------------------------------------------------------
    def setUp(self):
        import config
        import pdkgui_app

        self.paths = sandbox.build(SRC_DIR)      # a clean sandbox per test
        sandbox.set_current_release(sandbox.OLD_RELEASE)
        self.config = config
        self.pdkgui_app = pdkgui_app

        # config keeps module-level state; snapshot it so one test cannot leak
        # into the next (BASE_DIR in particular is repointed by version tests)
        self._config_state = {name: getattr(config, name)
                              for name in ("DESIGN_NAME", "BASE_DIR")}
        config.DESIGN_NAME = self.design
        config.clear_cache()      # the sandbox is rebuilt per test
        self.stubs = stubs.Installer().install()

        self.app = pdkgui_app.PdkGui()
        self.app.withdraw()

    # The recorders live on the stub installer. They are exposed as properties
    # whose setters replace the contents rather than the list, so a test that
    # does `self.spawned = []` to start counting afresh still shares the list
    # the stubs append to.
    spawned = property(lambda self: self.stubs.spawned,
                       lambda self, v: self.stubs.spawned.__setitem__(slice(None), v))
    dialogs = property(lambda self: self.stubs.dialogs,
                       lambda self, v: self.stubs.dialogs.__setitem__(slice(None), v))
    answers = property(lambda self: self.stubs.answers,
                       lambda self, v: self.stubs.answers.__setitem__(slice(None), v))
    files = property(lambda self: self.stubs.files,
                     lambda self, v: self.stubs.files.__setitem__(slice(None), v))
    # every file dialog opened, as (kind, kwargs)
    file_dialogs = property(
        lambda self: self.stubs.file_dialogs,
        lambda self, v: self.stubs.file_dialogs.__setitem__(slice(None), v))
    # what a subprocess should print, keyed on a fragment of its argv
    outputs = property(lambda self: self.stubs.outputs,
                       lambda self, v: self.stubs.outputs.clear() or
                       self.stubs.outputs.update(v))

    def tearDown(self):
        try:
            # the real close path: flushes the page and cancels its pending
            # debounced save, which a bare destroy() would leave to fire against
            # a dead widget
            self.app._on_close()
        except Exception:
            pass
        self.stubs.restore()
        for name, value in self._config_state.items():
            setattr(self.config, name, value)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def open_tab(self, name):
        """Show a tab and return its page."""
        self.app.show_module(name)
        self.app.update()
        return self.app._page

    def set_design(self, name):
        """Switch process the way a user does -- on the PROCESS tab."""
        page = self.open_tab("PROCESS")
        combo = self.widgets(page, "TCombobox")[0]
        combo.set(name)
        combo.event_generate("<<ComboboxSelected>>")
        page._on_select(name)
        self.app.update()

    def widgets(self, parent, cls):
        """Every descendant widget of a Tk class, in layout order."""
        found = []
        for child in parent.winfo_children():
            if child.winfo_class() == cls:
                found.append(child)
            found.extend(self.widgets(child, cls))
        return found

    def button(self, parent, text):
        """The button with this label (fails the test when absent)."""
        for b in self.widgets(parent, "Button"):
            if b.cget("text") == text:
                return b
        self.fail("no button labelled %r" % text)

    def click(self, parent, text):
        self.button(parent, text).invoke()
        self.app.update()

    def labels(self, parent):
        return [w.cget("text") for w in self.widgets(parent, "Label")]

    # Editing helpers.
    #
    # They change the widget and then call the handler its binding calls, rather
    # than synthesising <KeyRelease>: Tk only delivers key events to a window
    # that is actually mapped on screen, so synthetic events would make the
    # results depend on the window manager (and would flash windows across the
    # tester's desktop). test_bindings.py separately asserts that the widgets
    # really are bound to these handlers, so the wiring itself stays covered.
    def set_entry(self, page, key, value):
        """Type into a field."""
        entry = page.entries[key]
        entry.delete(0, "end")
        entry.insert(0, value)
        page._on_field_change(key)
        self.app.update()

    def set_combo(self, page, key, value):
        """Pick a value from a dropdown."""
        page.entries[key].set(value)
        page._on_field_change(key)
        self.app.update()

    def set_check(self, page, key, value):
        """Tick or untick a checkbox."""
        page.entries[key].set(bool(value))
        page._schedule_save()
        self.app.update()

    def browse(self, page, key, path):
        """Pick a path for a field by pressing the Open button on its row."""
        self.files = [path]
        # a field sharing its row with a checkbox sits in a holder frame, so ask
        # the outermost widget still inside the page which row that is
        w = page.entries[key]
        while w.master is not page and w.master is not None:
            w = w.master
        row = str(w.grid_info().get("row"))
        for b in self.widgets(page, "Button"):
            info = b.grid_info()
            if (b.cget("text") == "Open" and info
                    and str(info.get("row")) == row):
                b.invoke()
                self.app.update()
                return
        self.fail("no Open button on the %s row" % key)

    def set_text(self, page, content):
        """Replace the command text as if typed."""
        page.cmd_text.set_text(content)
        page._on_text_change()
        self.app.update()

    # --- reading what happened ----------------------------------------
    def run_folder(self):
        return self.paths["work"]

    def run_script(self):
        """Contents of the run script the last Run wrote."""
        return self._read(os.path.join(self.run_folder(), "run"))

    def run_wrapper(self):
        """Contents of the wrapper the terminal was opened on."""
        return self._read(os.path.join(self.run_folder(), ".pdkgui_run.sh"))

    def com_file(self, module):
        name = "calibre_%s_%s.com" % (self.config.DESIGN_NAME, module.lower())
        return self._read(os.path.join(self.run_folder(), name))

    def jivaro_xml(self):
        return self._read(os.path.join(self.run_folder(), "jivaro.xml"))

    def session(self, module, design=None):
        return self.config.load_json(
            self.config.user_session_file(module, design or self.config.DESIGN_NAME))

    def _read(self, path):
        self.assertTrue(os.path.isfile(path), "expected file was not written: %s" % path)
        with open(path, encoding="utf-8") as f:
            return f.read()

    def active_lines(self, text, keyword=None):
        """Non-comment lines, optionally only those containing a keyword."""
        out = [ln for ln in text.splitlines() if not ln.lstrip().startswith("//")]
        return [ln for ln in out if keyword in ln] if keyword else out


# set by run_tests.py before the tests are imported
SRC_DIR = os.environ.get("PDKGUI_SRC", "")
