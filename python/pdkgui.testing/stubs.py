#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
stubs.py
--------
Keeps pdkgui from reaching outside the process.

Both the unit tests (harness.py) and the run-folder generator (make_runs.py)
drive the real pdkgui, and neither wants calibre started, a terminal opened, or
a modal dialog waiting for a click that will never come. Installer.install()
replaces those calls with recorders:

    spawned   every subprocess.Popen argv
    dialogs   every message box / file dialog, as (kind, message)
    answers   what the next question should return (default: yes)
    files     what the next file dialog should return (default: "")

install() returns the Installer; call restore() to put everything back.
"""

import contextlib


class Installer(object):
    def __init__(self):
        self.spawned = []
        self.dialogs = []
        self.answers = []
        self.files = []
        self._patches = []

    # ------------------------------------------------------------------
    def install(self, quiet_terminal=False, auto_confirm_update=False):
        """quiet_terminal        : Run writes its files but opens no terminal
        auto_confirm_update  : never ask about a superseded release"""
        import pdkgui_app
        from pages import doc, gdsview, verify

        self._patch(verify.subprocess, "Popen", self._popen)   # one shared module
        self._patch(verify.shutil, "which", lambda prog: "/usr/bin/" + prog)

        for mod in (verify, gdsview, doc, pdkgui_app):
            self._stub_messagebox(mod)
        self._stub_filedialog(verify)

        if quiet_terminal:
            self._patch(verify.VerifyPage, "_launch_terminal",
                        lambda self_, folder: None)
            self._patch(gdsview, "_write_and_launch", lambda script, name: None)
        if auto_confirm_update:
            self._patch(pdkgui_app.PdkGui, "confirm_if_outdated", lambda self_: True)
        return self

    def restore(self):
        for obj, name, original, _stub in reversed(self._patches):
            setattr(obj, name, original)
        self._patches = []

    @contextlib.contextmanager
    def paused(self):
        """Put the real functions back for the duration of the block.

        subprocess.Popen is patched on the module object every import shares, so
        while the stubs are in place nothing -- not even the caller -- can start
        a real process. A test that has to (running a tool as a subprocess) wraps
        that call in this."""
        for obj, name, original, _stub in reversed(self._patches):
            setattr(obj, name, original)
        try:
            yield
        finally:
            for obj, name, _original, stub in self._patches:
                setattr(obj, name, stub)

    # ------------------------------------------------------------------
    def _patch(self, obj, name, value):
        self._patches.append((obj, name, getattr(obj, name), value))
        setattr(obj, name, value)

    def _popen(self, cmd, *a, **kw):
        self.spawned.append(list(cmd) if isinstance(cmd, (list, tuple)) else [cmd])
        return _FakeProcess()

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

    def _stub_filedialog(self, mod):
        dlg = getattr(mod, "filedialog", None)
        if dlg is None:
            return
        for kind in ("askopenfilename", "askdirectory", "asksaveasfilename"):
            if hasattr(dlg, kind):
                self._patch(dlg, kind, self._chooser(kind))

    def _recorder(self, kind):
        def record(title=None, message=None, **kw):
            self.dialogs.append((kind, message))
        return record

    def _asker(self, kind):
        def ask(title=None, message=None, **kw):
            self.dialogs.append((kind, message))
            return self.answers.pop(0) if self.answers else True
        return ask

    def _chooser(self, kind):
        def choose(**kw):
            self.dialogs.append((kind, None))
            return self.files.pop(0) if self.files else ""
        return choose


class _FakeProcess(object):
    """Stand-in for what Popen returns; nothing in pdkgui inspects it."""
    returncode = 0

    def wait(self, *a, **kw):
        return 0

    def poll(self):
        return 0
