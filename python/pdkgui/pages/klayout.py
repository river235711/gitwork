#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pages/klayout.py
----------------
KLAYOUT 頁面(簡易版本,可視需要擴充)。
"""

import tkinter as tk
from tkinter import messagebox

from .base import BasePage


class KlayoutPage(BasePage):
    module = "KLAYOUT"

    def build(self):
        tk.Label(self, text="*** KLayout ***", bg=self.bg,
                 font=("Arial", 11)).pack(pady=10)
        tk.Button(self, text="Open with KLayout",
                  command=lambda: messagebox.showinfo("pdkgui", "呼叫 klayout 開啟 GDS")).pack()
