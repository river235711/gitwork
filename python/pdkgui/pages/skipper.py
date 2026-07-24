#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pages/skipper.py
----------------
SKIPPER page: list of recently opened GDS files with a skipper viewer.

The list is read from config.page_file("SKIPPER") (default data/skipper.txt, one
path per line), showing up to 10 rows. Per row:
  - Open : pick a GDS file (file dialog) into the entry.
  - View : open that GDS with skipper (see pages/gdsview.open_gds).
"""

import tkinter as tk
from tkinter import filedialog

from .base import BasePage
from .gdsview import open_gds
import config


class SkipperPage(BasePage):
    module = "SKIPPER"
    ROWS = 10

    def build(self):
        tk.Label(self, text=config.DESIGN_NAME, bg=self.bg,
                 font=("Arial", 11)).grid(row=0, column=0, columnspan=4, pady=(0, 10))

        recent = config.read_lines(config.page_file(self.module))
        self.entries = []
        for i in range(self.ROWS):
            path = recent[i] if i < len(recent) else ""
            tk.Label(self, text="GDS%d" % (i + 1), bg=self.bg).grid(row=i + 1, column=0, sticky="w")
            ent = tk.Entry(self, width=90)
            ent.insert(0, path)
            ent.grid(row=i + 1, column=1, sticky="we", padx=4)
            tk.Button(self, text="Open",
                      command=lambda e=ent: self._on_open(e)).grid(row=i + 1, column=2, padx=2)
            tk.Button(self, text="View",
                      command=lambda e=ent: open_gds(self.app, e.get())).grid(row=i + 1, column=3, padx=2)
            self.entries.append(ent)

        self.grid_columnconfigure(1, weight=1)

    def _on_open(self, entry):
        path = filedialog.askopenfilename(
            filetypes=[("GDS", "*.gds *.gds.gz"), ("All files", "*")])
        if path:
            entry.delete(0, tk.END)
            entry.insert(0, path)
