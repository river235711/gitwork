#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pages/skipper.py
----------------
SKIPPER 頁面:最近開過的 GDS 清單。

清單從 config.page_file("SKIPPER")(預設 data/skipper.txt,一行一個路徑)
讀入,最多顯示 10 列。
"""

import tkinter as tk

from .base import BasePage
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
            tk.Button(self, text="Open").grid(row=i + 1, column=2, padx=2)
            tk.Button(self, text="View").grid(row=i + 1, column=3, padx=2)
            self.entries.append(ent)

        self.grid_columnconfigure(1, weight=1)
