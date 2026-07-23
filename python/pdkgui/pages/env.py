#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pages/env.py
------------
ENV 頁面:各工具的版本選單。

設定從 config.page_file("ENV")(預設 data/env.txt)讀入,格式:
    <tool>: <version1>, <version2>, ...
一行一個工具;'#' 開頭為註解。讀不到檔時使用內建預設值。
"""

import tkinter as tk
from tkinter import ttk

from .base import BasePage
from widgets import LogoPanel
import config

_FALLBACK = {
    "calibre": ["2024.1_36.20", "2023.4_20.11"],
    "jivaro": ["2020", "2019"],
    "skipper": ["2019.06-sp3", "2018.09-sp1"],
    "editor": ["gvim", "vim", "emacs"],
}


class EnvPage(BasePage):
    module = "ENV"

    def build(self):
        tk.Label(self, text="*** Tool Version ***", bg=self.bg,
                 font=("Arial", 11)).pack(pady=(20, 10))

        tools = self._parse(config.page_file(self.module)) or _FALLBACK
        self.combos = {}
        for key, values in tools.items():
            if not values:
                continue
            tk.Label(self, text=key, bg=self.bg).pack()
            cb = ttk.Combobox(self, values=values, state="readonly", width=40)
            cb.set(values[0])
            cb.pack(pady=4)
            self.combos[key] = cb

        LogoPanel(self, height=110).pack(side="bottom", fill="x")

    @staticmethod
    def _parse(path):
        tools = {}
        for line in config.read_lines(path):
            if ":" not in line:
                continue
            key, rest = line.split(":", 1)
            versions = [v.strip() for v in rest.split(",") if v.strip()]
            if key.strip():
                tools[key.strip()] = versions
        return tools
