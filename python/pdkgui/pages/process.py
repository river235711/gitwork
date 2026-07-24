#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pages/process.py
----------------
PROCESS page: choose the process / design.

The selectable list is read from config.page_file("PROCESS") (default
data/process.txt, one per line); falls back to config.DESIGN_NAME when the file
cannot be read.
"""

import tkinter as tk
from tkinter import ttk

from .base import BasePage
from widgets import LogoPanel
import config


class ProcessPage(BasePage):
    module = "PROCESS"

    def build(self):
        tk.Label(self, text="*** Process ***", bg=self.bg,
                 font=("Arial", 11)).pack(pady=(20, 10))

        values = config.read_lines(config.page_file(self.module)) or [config.DESIGN_NAME]
        # select the current design if it is in the list, else the first entry
        current = config.DESIGN_NAME if config.DESIGN_NAME in values else values[0]

        combo = ttk.Combobox(self, values=values, state="readonly", width=40)
        combo.set(current)
        combo.pack()

        # on selection, update the window title "pdkgui - <name>" (other tabs follow)
        combo.bind("<<ComboboxSelected>>",
                   lambda e: self.app.set_design(combo.get()))

        LogoPanel(self, height=110).pack(side="bottom", fill="x")
