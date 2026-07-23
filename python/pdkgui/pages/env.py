#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pages/env.py
------------
ENV 頁面:各工具的版本 / 編輯器選單。

設定從 config.page_file("ENV")(預設 data/env.txt)讀入,格式:
    <tool>: <選項1>, <選項2>, ...
一行一個工具;'#' 開頭為註解;值前加 '*' 表示預設選項。

前三個工具(calibre / jivaro / skipper)的選值即 `module load` 參數
(例:module load calibre/2024.1_36.20);第四個 editor 為文字編輯器指令。

選到的值會存到 self.app.env[tool],讓其他 tab 之後能取用(module load / 開編輯器)。
"""

import tkinter as tk
from tkinter import ttk

from .base import BasePage
from widgets import LogoPanel
import config

# editor 之外的工具都視為「module load 工具」
EDITOR_KEY = "editor"

_FALLBACK = {
    "calibre": ["calibre/2024.1_36.20"],
    "jivaro": ["jivaro/2020"],
    "skipper": ["skipper/2019.06-sp3"],
    "editor": ["gvim", "nedit", "gedit"],
}


def env_defaults():
    """回傳 {tool: 預設值};供其他 tab(如 verify 的 module load)在啟動時取用。"""
    tools = EnvPage._parse(config.page_file("ENV"))
    if not tools:
        tools = {k: {"values": v, "default": v[0]} for k, v in _FALLBACK.items()}
    return {k: info["default"] for k, info in tools.items()}


class EnvPage(BasePage):
    module = "ENV"

    def build(self):
        tk.Label(self, text="*** Tool Version ***", bg=self.bg,
                 font=("Arial", 11)).pack(pady=(20, 10))

        tools = self._parse(config.page_file(self.module))
        if not tools:
            tools = {k: {"values": v, "default": v[0]} for k, v in _FALLBACK.items()}

        self.combos = {}
        for key, info in tools.items():
            values = info["values"]
            if not values:
                continue
            # 已選過的沿用;否則用檔案預設
            default = self.app.env.get(key, info["default"])
            if default not in values:
                default = info["default"]

            cb = ttk.Combobox(self, values=values, state="readonly", width=40)
            cb.set(default)
            cb.pack(pady=6)
            cb.bind("<<ComboboxSelected>>",
                    lambda e, k=key, c=cb: self._on_select(k, c))
            self.combos[key] = cb
            self.app.env.setdefault(key, default)

        LogoPanel(self, height=110).pack(side="bottom", fill="x")

    def _on_select(self, key, combo):
        self.app.env[key] = combo.get()

    @staticmethod
    def _parse(path):
        """解析 env.txt,回傳 {tool: {"values": [...], "default": x}}(保留順序)。"""
        tools = {}
        for line in config.read_lines(path):
            if ":" not in line:
                continue
            key, rest = line.split(":", 1)
            key = key.strip()
            if not key:
                continue
            values = []
            default = None
            for tok in rest.split(","):
                tok = tok.strip()
                if not tok:
                    continue
                if tok.startswith("*"):
                    tok = tok[1:].strip()
                    default = tok
                values.append(tok)
            if values and default is None:
                default = values[0]
            tools[key] = {"values": values, "default": default}
        return tools
