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
        self.spawned = []
        self.dialogs = []
        self.answers = []        # popped by messagebox questions
        self.files = []          # popped by file dialogs
        self._patches = []
        self._install_stubs()

        self.app = pdkgui_app.PdkGui()
        self.app.withdraw()

    def tearDown(self):
        try:
            # the real close path: flushes the page and cancels its pending
            # debounced save, which a bare destroy() would leave to fire against
            # a dead widget
            self.app._on_close()
        except Exception:
            pass
        for obj, name, original in reversed(self._patches):
            setattr(obj, name, original)
        for name, value in self._config_state.items():
            setattr(self.config, name, value)

    # ------------------------------------------------------------------
    # stubbing
    # ------------------------------------------------------------------
    def _patch(self, obj, name, value):
        self._patches.append((obj, name, getattr(obj, name)))
        setattr(obj, name, value)

    def _install_stubs(self):
        import pdkgui_app
        from pages import doc, gdsview, verify

        def popen(cmd, *a, **kw):
            self.spawned.append(list(cmd) if isinstance(cmd, (list, tuple)) else [cmd])
            return _FakeProcess()

        for mod in (verify, gdsview, doc, pdkgui_app):
            self._patch(mod.subprocess, "Popen", popen)
            break        # they all import the same subprocess module object

        # pretend the external programs exist, so the "found nothing" paths in
        # the code are not what we end up testing
        for mod in (verify, gdsview, doc):
            if hasattr(mod, "shutil"):
                self._patch(mod.shutil, "which", lambda prog: "/usr/bin/" + prog)
                break

        for mod in (verify, gdsview, doc, pdkgui_app):
            self._stub_messagebox(mod)
        self._stub_filedialog(verify)

    def _stub_messagebox(self, mod):
        box = getattr(mod, "messagebox", None)
        if box is None:
            return
        for kind in ("showinfo", "showwarning", "showerror"):
            if hasattr(box, kind):
                self._patch(box, kind, self._recorder(kind))
        for kind in ("askyesno", "askokcancel", "askyesnocancel"):
            if hasattr(box, kind):
                self._patch(box, kind, self._asker(kind))

    def _recorder(self, kind):
        def record(title=None, message=None, **kw):
            self.dialogs.append((kind, message))
        return record

    def _asker(self, kind):
        def ask(title=None, message=None, **kw):
            self.dialogs.append((kind, message))
            return self.answers.pop(0) if self.answers else True
        return ask

    def _stub_filedialog(self, mod):
        dlg = getattr(mod, "filedialog", None)
        if dlg is None:
            return
        for kind in ("askopenfilename", "askdirectory", "asksaveasfilename"):
            if hasattr(dlg, kind):
                self._patch(dlg, kind, self._chooser(kind))

    def _chooser(self, kind):
        def choose(**kw):
            self.dialogs.append((kind, None))
            return self.files.pop(0) if self.files else ""
        return choose

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


class _FakeProcess(object):
    """Stand-in for what Popen returns; nothing in pdkgui inspects it."""
    returncode = 0

    def wait(self, *a, **kw):
        return 0

    def poll(self):
        return 0


# set by run_tests.py before the tests are imported
SRC_DIR = os.environ.get("PDKGUI_SRC", "")
