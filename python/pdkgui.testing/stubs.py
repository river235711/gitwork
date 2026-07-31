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
        # what a probed process prints: {argv[-1] fragment or host: (out, err)},
        # plus a default for anything not listed. The LOADING tab reads its
        # subprocess' output, so it needs more than a recorded argv.
        self.outputs = {}
        self.default_output = ("", "")
        # every file dialog as (kind, kwargs) -- what it offered, not just that
        # it was opened
        self.file_dialogs = []
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
        argv = list(cmd) if isinstance(cmd, (list, tuple)) else [cmd]
        self.spawned.append(argv)
        return _FakeProcess(self._output_for(argv))

    def _output_for(self, argv):
        """The (stdout, stderr) a test wants this command to produce, matched on
        any outputs key appearing in the argv (a host name, say). A value of None
        means the process never finishes, for testing a machine that hangs."""
        for key, value in self.outputs.items():
            if any(key in part for part in argv):
                return value
        return self.default_output

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
            self.file_dialogs.append((kind, kw))
            return self.files.pop(0) if self.files else ""
        return choose


class _FakeProcess(object):
    """Stand-in for what Popen returns.

    Most callers ignore it; the LOADING tab polls it and reads its output, so it
    can be given canned output -- or None, to act like a process that never
    finishes."""
    returncode = 0

    def __init__(self, output=("", "")):
        self._output = output
        self.killed = False

    def wait(self, *a, **kw):
        return 0

    def poll(self):
        return None if self._output is None else 0

    def communicate(self, *a, **kw):
        return ("", "") if self._output is None else self._output

    def kill(self):
        self.killed = True
