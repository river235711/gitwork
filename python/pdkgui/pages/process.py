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
        # 目前 design 若在清單中就選它,否則預設第一個
        current = config.DESIGN_NAME if config.DESIGN_NAME in values else values[0]

        combo = ttk.Combobox(self, values=values, state="readonly", width=40)
        combo.set(current)
        combo.pack()

        # 選擇後更新視窗標題 "pdkgui - <名稱>"(其他 tab 也會跟著使用)
        combo.bind("<<ComboboxSelected>>",
                   lambda e: self.app.set_design(combo.get()))

        LogoPanel(self, height=110).pack(side="bottom", fill="x")
