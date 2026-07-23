#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pages/verify.py
---------------
DRC / ANT / WB / BUMP / DMDV / DPDO / LVS / XRC / JIVARO 共用的驗證流程頁面。

下方的 command file 文字框內容從 config.page_file(<模組>)
(預設 data/verify/<模組>.com)讀入,右側 + 下方都有滾輪。
"""

import tkinter as tk
from tkinter import filedialog, messagebox

from .base import BasePage
from widgets import ScrolledText
import config


class VerifyPage(BasePage):
    def __init__(self, master, app, module_name):
        self.module = module_name
        super().__init__(master, app)

    def build(self):
        design = config.DESIGN_NAME
        tk.Label(self, text=design, bg=self.bg,
                 font=("Arial", 11)).grid(row=0, column=0, columnspan=4, pady=(0, 10))

        fields = [("LayoutPath", True), ("LayoutPrimary", False)]
        if self.module in ("LVS", "XRC"):
            fields += [("SourcePath", True), ("SourcePrimary", False), ("LvsHier", "check")]
        fields.append(("RunFolder", True))

        self.entries = {}
        row = 1
        for label, kind in fields:
            tk.Label(self, text=label, bg=self.bg).grid(row=row, column=0, sticky="w")
            if kind == "check":
                var = tk.BooleanVar()
                tk.Checkbutton(self, variable=var, bg=self.bg).grid(row=row, column=1, sticky="w")
                self.entries[label] = var
            else:
                ent = tk.Entry(self, width=90)
                ent.grid(row=row, column=1, columnspan=2, sticky="we", padx=4)
                self.entries[label] = ent
                if kind is True:
                    tk.Button(self, text="Open",
                              command=lambda e=ent: self._browse_file(e)).grid(row=row, column=3, padx=2)
            row += 1

        self.grid_columnconfigure(2, weight=1)

        btn_frame = tk.Frame(self, bg=self.bg)
        btn_frame.grid(row=row, column=0, columnspan=4, pady=10)
        for text in ("Run", "Rve", "LoadDefault", "Load", "Save"):
            tk.Button(btn_frame, text=text, width=12,
                      command=lambda t=text: self._on_button(t)).pack(side="left", padx=4)
        row += 1

        # 下方 command file 文字框(右側 + 下方滾輪)
        self.cmd_text = ScrolledText(self, wrap="none")
        self.cmd_text.grid(row=row, column=0, columnspan=4, sticky="nsew", pady=(10, 0))
        self.grid_rowconfigure(row, weight=1)
        self.cmd_text.load_file(config.page_file(self.module))

    def _browse_file(self, entry_widget):
        path = filedialog.askopenfilename()
        if path:
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, path)

    def _on_button(self, action):
        if action == "LoadDefault":
            self.cmd_text.load_file(config.page_file(self.module))
            return
        # 這裡只是示範接口:實際上會呼叫 Calibre/skipper 等後端指令。
        messagebox.showinfo(
            "pdkgui",
            "模組: %s\n動作: %s\n(這裡接上實際的 EDA 執行指令)" % (self.module, action),
        )
