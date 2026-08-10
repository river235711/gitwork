#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pdkgui_app.py
-------------
Main program logic for pdkgui (main window + left menu + page routing).

* In a deployed build this file (and config / widgets / pages/*) is encrypted
  into a .pdkc and loaded at runtime via the import hook installed by the
  pdkgui.py bootstrap. In a source checkout it simply runs as plaintext (the
  import hook does nothing when no .pdkc are present).
"""

import os
import subprocess
import tkinter as tk
from tkinter import font as tkfont, messagebox, ttk

import config
from pages import build_page


class PdkGui(tk.Tk):
    """The pdkgui window.

    `only` names a single module to show on its own, with no menu down the side
    (`pdkgui -l` -> only="LOADING", the machine chooser). Such a window is a
    means to an end -- pick a machine, open pdkgui there -- so it deliberately
    neither reads nor writes the state that belongs to a working session."""

    def __init__(self, only=None):
        super().__init__()
        self.only = only

        self._apply_fonts()
        # Working directory pdkgui was launched from (default for verify RunFolder)
        self.launch_dir = os.getcwd()
        self._page = None
        self._pages = {}               # built pages, kept for the next visit
        self._menu_buttons = {}        # empty without a sidebar
        self._update_ack = False       # "run anyway" chosen on the Run prompt
        self.current_module = tk.StringVar(value=only or config.MENU_ITEMS[0])

        with config.timed("build window"):
            if only:
                self._build_single(only)
            else:
                self._build_full()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._report_startup()

    def _build_full(self):
        # First start after the upgrade: convert the old
        # ~/.pdkgui/.pdkgui.<tab><design>.{commandfile,gui} files into the
        # session layout
        config.migrate_legacy_user_files()

        # Restore the design chosen on the PROCESS tab (saved in the global session)
        saved_design = config.load_json(config.user_global_file("PROCESS")).get("design")
        if saved_design:
            config.DESIGN_NAME = saved_design

        self.title(config.window_title())
        self.geometry(config.window_geometry())
        self.configure(bg="#d9d9d9")

        # Tool / editor picked on the ENV tab (defaults, then restore saved ones),
        # shared with other tabs
        # imported here, not at module level: it would pull pages/__init__ and
        # pages/env in before the window exists -- two more modules to fetch and
        # decrypt on the way to first paint
        from pages.env import env_defaults
        self.env = env_defaults()
        saved_env = config.load_json(config.user_global_file("ENV"))
        if isinstance(saved_env, dict):
            for k, v in saved_env.items():
                if v:
                    self.env[k] = v

        self._build_sidebar()
        self._build_content_area()
        self.show_module(self._restore_module())
        # The window is up and responsive now, so spend the idle moment loading
        # the verify page module: it is the biggest one, and without this the
        # first DRC/LVS/XRC click pays for it.
        self.after_idle(self._warm_up)

    def _build_single(self, module):
        """One page, no menu: the window is that page.

        No geometry is set -- Tk sizes the window to the page, so a chooser does
        not open as a mostly empty full-size window. What is skipped is as much
        the point as what is done: the ENV/PROCESS session is not read (this page
        uses neither), the legacy migration is not run (a chooser has no business
        rewriting the user's files) and the open tab is not saved on close, which
        would otherwise make the *full* pdkgui open on this page next time."""
        self.title(config.window_title(subject=module.lower()))
        self.configure(bg="white")
        self._build_content_area()
        self.content.configure(bg="white")
        self.show_module(module)

    def _warm_up(self):
        with config.timed("warm up verify module"):
            try:
                import pages.verify        # noqa: F401
            except Exception:
                pass                       # a warm-up must never break start-up

    @staticmethod
    def _report_startup():
        """Total from process start, when the bootstrap passed its own T0 on."""
        started = os.environ.pop("PDKGUI_START", None)
        if started and config.TIMING:
            import sys
            import time
            sys.stderr.write("[pdkgui] %-34s %6.1f ms\n"
                             % ("=> window ready, total",
                                (time.time() - float(started)) * 1000))

    def _apply_fonts(self):
        """Resize Tk's named fonts, which every widget that sets no font of its
        own follows -- entries, labels, buttons, listboxes, text boxes. Doing it
        here means one setting (config.UI_FONT_PX) scales the whole interface."""
        family, size = config.ui_font()
        for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont",
                     "TkIconFont", "TkSmallCaptionFont", "TkTooltipFont"):
            try:
                tkfont.nametofont(name).configure(family=family, size=size)
            except tk.TclError:
                pass
        try:
            mono_family, mono_size = config.mono_font()
            tkfont.nametofont("TkFixedFont").configure(family=mono_family,
                                                       size=mono_size)
        except tk.TclError:
            pass
        # ttk widgets (the PROCESS / ENV comboboxes) and their dropdown lists
        try:
            ttk.Style().configure(".", font=config.ui_font())
        except tk.TclError:
            pass
        self.option_add("*TCombobox*Listbox.font", config.ui_font())

    def _restore_module(self):
        """The tab open when we last exited (so a restart lands where you were)."""
        saved = config.load_json(config.user_global_file("UI")).get("module")
        return saved if saved in config.MENU_ITEMS else config.MENU_ITEMS[0]

    def set_design(self, name):
        """Switch the current design: update the window title so other tabs follow."""
        if name == config.DESIGN_NAME:
            return
        config.DESIGN_NAME = name
        self.title(config.window_title())
        # The built pages belong to the previous design, so drop them; each is
        # rebuilt when next opened. PROCESS is the page this is called from --
        # destroying it here would pull the widget out from under the callback
        # still running on it -- and its content (the list of designs) does not
        # depend on which one is selected, so it is kept.
        self._drop_cached_pages(keep="PROCESS")

    # ------------------------------------------------------------------
    # Left-hand menu
    # ------------------------------------------------------------------
    def _build_sidebar(self):
        sidebar = tk.Frame(self, bg="#d9d9d9", width=190)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        self._menu_buttons = {}
        for name in config.MENU_ITEMS:
            btn = tk.Button(
                sidebar, text=name, relief="raised", bd=1,
                bg="#bcdff0", activebackground="#9fcfe8",
                font=config.ui_font(-1),
                command=lambda n=name: self.show_module(n),
            )
            btn.pack(fill="x", padx=2, pady=1)
            self._menu_buttons[name] = btn

    def _highlight_selected(self, name):
        for n, btn in self._menu_buttons.items():      # nothing to do without a menu
            btn.configure(bg="#e0e0e0" if n == name else "#bcdff0")

    # ------------------------------------------------------------------
    # Right-hand content area (switches by module)
    # ------------------------------------------------------------------
    def _build_content_area(self):
        self.content = tk.Frame(self, bg="#d9d9d9")
        self.content.pack(side="left", fill="both", expand=True)

    def show_module(self, name):
        """Bring a tab to the front, building it the first time.

        Pages are kept and re-shown rather than destroyed and rebuilt: a rebuild
        re-reads the central files and the session and recreates every widget,
        which is slow over NFS and pointless when going back to a tab. Whatever
        must not go stale is refreshed in the page's on_show()."""
        self.current_module.set(name)
        self._highlight_selected(name)

        self._flush_page()          # save the page we are leaving
        if self._page is not None:
            self._page.pack_forget()

        page = self._pages.get(name)
        if page is None:
            page = self._pages[name] = build_page(name, self.content, self)
        self._page = page
        page.pack(fill="both", expand=True, padx=10, pady=10)
        with config.timed("show %s" % name):
            page.on_show()

    def _drop_cached_pages(self, keep=None):
        """Forget the built pages (they were built for one design), except
        `keep`, which stays because it is the one on screen.

        Deliberately no flush: show_module already saved each page on the way
        out, and by the time this runs the design has changed -- flushing now
        would file the previous design's state under the new one."""
        for name in [n for n in self._pages if n != keep]:
            page = self._pages.pop(name)
            try:
                page.destroy()
            except Exception:
                pass
        if keep not in self._pages:
            self._page = None

    def _flush_page(self):
        page = getattr(self, "_page", None)
        if page is not None and hasattr(page, "flush"):
            try:
                page.flush()
            except Exception:
                pass

    def _save_ui_state(self):
        """Remember the open tab. Written when leaving rather than on every tab
        switch, which was an NFS write per click; the worst a crash costs is
        reopening on the previous tab.

        A single-page window has no tab to remember, and writing one would send
        the full pdkgui to that page on its next start."""
        if self.only:
            return
        config.save_json(config.user_global_file("UI"),
                         {"module": self.current_module.get()})

    def _on_close(self):
        self._flush_page()
        self._save_ui_state()
        self.destroy()

    # ------------------------------------------------------------------
    # Deployed-version check: the release we run from can be superseded while
    # the window stays open (an admin repoints the "current" symlink). The
    # SYSTEM tab shows the state; a Run asks before using a superseded release.
    # ------------------------------------------------------------------
    def confirm_if_outdated(self):
        """Called before a Run. False means the caller must not proceed (the user
        chose to restart). Asking once per session is enough -- someone who wants
        to finish on this release should not be nagged on every Run."""
        update = config.pending_update()
        if not update or self._update_ack:
            return True
        running, live, _dir = update
        if messagebox.askyesno(
                "pdkgui",
                "This window is running pdkgui %s, but %s is now the current "
                "release.\n\nRun with the version you have?\n\n"
                "Yes  -- run now with %s\n"
                "No   -- restart into %s first"
                % (running, live, running, live)):
            self._update_ack = True     # respect the choice for this session
            return True
        self.restart()
        return False

    def restart(self):
        """Save everything, start the app again from the entry point, and exit.

        Runs already launched from a tab live in their own terminals, so they are
        unaffected."""
        launcher = config.live_launcher()
        if not launcher:
            messagebox.showerror("pdkgui", "The current release could not be found;\n"
                                           "close pdkgui and start it again manually.")
            return
        self._flush_page()
        self._save_ui_state()       # the new instance opens on this tab
        try:
            subprocess.Popen([launcher], start_new_session=True, close_fds=True)
        except Exception as e:
            messagebox.showerror(
                "pdkgui", "Could not restart from:\n%s\n\n%s\n\n"
                          "Close pdkgui and start it again manually." % (launcher, e))
            return
        self.destroy()


USAGE = """usage: pdkgui [-l]

  -l, --loading   open the machine chooser only: the LOADING page on its own,
                  to see which machine is free and start pdkgui there
  -h, --help      this message

With no options the full window opens on the tab it was last left on.
"""


def parse_argv(argv):
    """(only, message, status): which module to show on its own, and whether to
    print something and stop instead of opening a window."""
    if not argv:
        return None, None, 0
    if len(argv) == 1:
        if argv[0] in ("-l", "--loading"):
            return "LOADING", None, 0
        if argv[0] in ("-h", "--help"):
            return None, USAGE, 0
    return None, "pdkgui: unknown option %s\n\n%s" % (" ".join(argv), USAGE), 2


def main(argv=None):
    import sys
    only, message, status = parse_argv(
        list(sys.argv[1:] if argv is None else argv))
    if message:
        (sys.stderr if status else sys.stdout).write(message)
        return status
    PdkGui(only=only).mainloop()
    return 0
