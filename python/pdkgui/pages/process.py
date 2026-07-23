#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pages/process.py
----------------
PROCESS 頁面:選擇 process / design。

可選的清單從 config.page_file("PROCESS")(預設 data/process.txt,
一行一個)讀入;讀不到檔時退回使用 config.DESIGN_NAME。
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
        combo = ttk.Combobox(self, values=values, state="readonly", width=40)
        combo.set(values[0])
        combo.pack()

        LogoPanel(self, height=110).pack(side="bottom", fill="x")
