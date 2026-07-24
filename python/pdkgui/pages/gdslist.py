#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pages/gdslist.py
----------------
Shared base for GDS-list pages (SKIPPER, KLAYOUT): a list of GDS rows, each with
Open (file dialog) and View (open in a viewer). The list is remembered in the
user's session (~/.pdkgui/session/<MODULE>.json), falling back to
config.page_file(<MODULE>) on first use.

Subclasses set `module` and implement `_view(gds)`.
"""

import tkinter as tk
from tkinter import filedialog

from .base import BasePage
import config


class GdsListPage(BasePage):
    ROWS = 10

    def build(self):
        self._save_job = None

        tk.Label(self, text=config.DESIGN_NAME, bg=self.bg,
                 font=("Arial", 11)).grid(row=0, column=0, columnspan=4, pady=(0, 10))

        rows = self._load_rows()
        self.entries = []
        for i in range(self.ROWS):
            path = rows[i] if i < len(rows) else ""
            tk.Label(self, text="GDS%d" % (i + 1), bg=self.bg).grid(row=i + 1, column=0, sticky="w")
            ent = tk.Entry(self, width=90)
            ent.insert(0, path)
            ent.grid(row=i + 1, column=1, sticky="we", padx=4)
            ent.bind("<KeyRelease>", lambda e: self._schedule_save())
            tk.Button(self, text="Open",
                      command=lambda e=ent: self._on_open(e)).grid(row=i + 1, column=2, padx=2)
            tk.Button(self, text="View",
                      command=lambda e=ent: self._view(e.get())).grid(row=i + 1, column=3, padx=2)
            self.entries.append(ent)

        self.grid_columnconfigure(1, weight=1)

    # subclasses implement this
    def _view(self, gds):
        raise NotImplementedError

    # ------------------------------------------------------------------
    def _load_rows(self):
        """Restore the saved GDS list; fall back to config.page_file(module)."""
        saved = config.load_json(config.user_global_file(self.module))
        gds = saved.get("gds") if isinstance(saved, dict) else None
        if gds:
            return gds
        return config.read_lines(config.page_file(self.module))

    def _on_open(self, entry):
        path = filedialog.askopenfilename(
            filetypes=[("GDS", "*.gds *.gds.gz"), ("All files", "*")])
        if path:
            entry.delete(0, tk.END)
            entry.insert(0, path)
            self._schedule_save()

    # --- persist the GDS list to the user's session --------------------
    def _save_state(self):
        self._save_job = None
        config.save_json(config.user_global_file(self.module),
                         {"gds": [e.get() for e in self.entries]})

    def _schedule_save(self):
        if self._save_job is not None:
            try:
                self.after_cancel(self._save_job)
            except Exception:
                pass
        self._save_job = self.after(500, self._save_state)

    def flush(self):
        """Save immediately before leaving the page / closing the window."""
        if self._save_job is not None:
            try:
                self.after_cancel(self._save_job)
            except Exception:
                pass
            self._save_job = None
        self._save_state()
