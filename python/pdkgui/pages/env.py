#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pages/env.py
------------
ENV page: version / editor menus for each tool.

Settings are read from config.page_file("ENV") (default data/env.txt), format:
    <tool>: <option1>, <option2>, ...
one tool per line; '#' starts a comment; a leading '*' marks the default option.

The first three tools (calibre / jivaro / skipper) provide the `module load`
argument (e.g. module load calibre/2024.1_36.20); the fourth, editor, is the
text-editor command.

The selected value is stored in self.app.env[tool] so other tabs can use it
later (module load / launching the editor).
"""

import tkinter as tk
from tkinter import ttk

from .base import BasePage
from widgets import LogoPanel
import config

# Tools other than editor are treated as "module load tools"
EDITOR_KEY = "editor"

_FALLBACK = {
    "calibre": ["calibre/2024.1_36.20"],
    "jivaro": ["jivaro/2020"],
    "skipper": ["skipper/2019.06-sp3"],
    "editor": ["gvim", "nedit", "gedit"],
}


def env_defaults():
    """Return {tool: default}; used by other tabs (e.g. verify's module load) at startup."""
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
            # reuse a previously selected value, else the file default
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
        """Parse env.txt into {tool: {"values": [...], "default": x}} (order kept)."""
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
