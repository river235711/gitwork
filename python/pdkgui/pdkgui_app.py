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
import tkinter as tk

import config
from pages import build_page
from pages.env import env_defaults


class PdkGui(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("pdkgui - %s" % config.DESIGN_NAME)
        self.geometry("980x560")
        self.configure(bg="#d9d9d9")

        # Working directory pdkgui was launched from (default for verify RunFolder)
        self.launch_dir = os.getcwd()
        self.current_module = tk.StringVar(value=config.MENU_ITEMS[0])
        # Tool / editor picked on the ENV tab (defaults loaded at startup),
        # shared with other tabs
        self.env = env_defaults()
        self._page = None

        self._build_sidebar()
        self._build_content_area()
        self.show_module(config.MENU_ITEMS[0])
        self.protocol("WM_DELETE_WINDOW", self._on_close)

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


def main():
    PdkGui().mainloop()
