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
from tkinter import messagebox

import config
from pages import build_page
from pages.env import env_defaults


class PdkGui(tk.Tk):
    def __init__(self):
        super().__init__()

        # First start after the upgrade: convert the old
        # ~/.pdkgui/.pdkgui.<tab><design>.{commandfile,gui} files into the
        # session layout
        config.migrate_legacy_user_files()

        # Restore the design chosen on the PROCESS tab (saved in the global session)
        saved_design = config.load_json(config.user_global_file("PROCESS")).get("design")
        if saved_design:
            config.DESIGN_NAME = saved_design

        self.title("pdkgui - %s" % config.DESIGN_NAME)
        self.geometry("980x560")
        self.configure(bg="#d9d9d9")

        # Working directory pdkgui was launched from (default for verify RunFolder)
        self.launch_dir = os.getcwd()
        self.current_module = tk.StringVar(value=config.MENU_ITEMS[0])
        # Tool / editor picked on the ENV tab (defaults, then restore saved ones),
        # shared with other tabs
        self.env = env_defaults()
        saved_env = config.load_json(config.user_global_file("ENV"))
        if isinstance(saved_env, dict):
            for k, v in saved_env.items():
                if v:
                    self.env[k] = v
        self._page = None
        self._update_ack = False       # "run anyway" chosen on the Run prompt

        self._build_sidebar()
        self._build_content_area()
        self.show_module(self._restore_module())
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _restore_module(self):
        """The tab open when we last exited (so a restart lands where you were)."""
        saved = config.load_json(config.user_global_file("UI")).get("module")
        return saved if saved in config.MENU_ITEMS else config.MENU_ITEMS[0]

    def set_design(self, name):
        """Switch the current design: update the window title so other tabs follow."""
        config.DESIGN_NAME = name
        self.title("pdkgui - %s" % name)

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
                font=("Arial", 9),
                command=lambda n=name: self.show_module(n),
            )
            btn.pack(fill="x", padx=2, pady=1)
            self._menu_buttons[name] = btn

    def _highlight_selected(self, name):
        for n, btn in self._menu_buttons.items():
            btn.configure(bg="#e0e0e0" if n == name else "#bcdff0")

    # ------------------------------------------------------------------
    # Right-hand content area (switches by module)
    # ------------------------------------------------------------------
    def _build_content_area(self):
        self.content = tk.Frame(self, bg="#d9d9d9")
        self.content.pack(side="left", fill="both", expand=True)

    def show_module(self, name):
        self.current_module.set(name)
        self._highlight_selected(name)
        config.save_json(config.user_global_file("UI"), {"module": name})

        # Save the current page's state before leaving it
        self._flush_page()
        for w in self.content.winfo_children():
            w.destroy()

        self._page = build_page(name, self.content, self)
        self._page.pack(fill="both", expand=True, padx=10, pady=10)

    def _flush_page(self):
        page = getattr(self, "_page", None)
        if page is not None and hasattr(page, "flush"):
            try:
                page.flush()
            except Exception:
                pass

    def _on_close(self):
        self._flush_page()
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
        try:
            subprocess.Popen([launcher], start_new_session=True, close_fds=True)
        except Exception as e:
            messagebox.showerror(
                "pdkgui", "Could not restart from:\n%s\n\n%s\n\n"
                          "Close pdkgui and start it again manually." % (launcher, e))
            return
        self.destroy()


def main():
    PdkGui().mainloop()
