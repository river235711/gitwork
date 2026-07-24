#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pdkgui_app.py
-------------
pdkgui 的主程式邏輯(主視窗 + 左側選單 + 頁面路由)。

★ 這支檔案(以及 config / widgets / pages/*)在「部署版」會被加密成 .pdkc,
  由 pdkgui.py bootstrap 透過 import hook 於執行期解密載入。
  在原始碼開發環境則直接以明文執行(沒有 .pdkc 時 import hook 不作用)。
"""

import os
import tkinter as tk

import config
from pages import build_page
from pages.env import env_defaults


class PdkGui(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("pdkgui - %s" % config.DESIGN_NAME)
        self.geometry("980x560")
        self.configure(bg="#d9d9d9")

        # 開啟 pdkgui 的工作目錄(供 verify 頁的 RunFolder 預設值)
        self.launch_dir = os.getcwd()
        self.current_module = tk.StringVar(value=config.MENU_ITEMS[0])
        # ENV tab 選到的工具 / 編輯器(啟動先載入預設),供其他 tab 取用
        self.env = env_defaults()
        self._page = None

        self._build_sidebar()
        self._build_content_area()
        self.show_module(config.MENU_ITEMS[0])
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def set_design(self, name):
        """切換目前 design:更新視窗標題,並讓其他 tab 也跟著使用。"""
        config.DESIGN_NAME = name
        self.title("pdkgui - %s" % name)

    # ------------------------------------------------------------------
    # 左側選單
    # ------------------------------------------------------------------
    def _build_sidebar(self):
        sidebar = tk.Frame(self, bg="#d9d9d9", width=190)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        self._menu_buttons = {}
        for name in config.MENU_ITEMS:
            btn = tk.Button(
                sidebar, text=name, relief="raised", bd=1,
                bg="#bcdff0", activebackground="#9fcfe8",
                font=("Arial", 9),
                command=lambda n=name: self.show_module(n),
            )
            btn.pack(fill="x", padx=2, pady=1)
            self._menu_buttons[name] = btn

    def _highlight_selected(self, name):
        for n, btn in self._menu_buttons.items():
            btn.configure(bg="#e0e0e0" if n == name else "#bcdff0")

    # ------------------------------------------------------------------
    # 右側內容區(依模組切換)
    # ------------------------------------------------------------------
    def _build_content_area(self):
        self.content = tk.Frame(self, bg="#d9d9d9")
        self.content.pack(side="left", fill="both", expand=True)

    def show_module(self, name):
        self.current_module.set(name)
        self._highlight_selected(name)

        # 離開目前頁面前,先把它的狀態存起來
        self._flush_page()
        for w in self.content.winfo_children():
            w.destroy()

        self._page = build_page(name, self.content, self)
        self._page.pack(fill="both", expand=True, padx=10, pady=10)

    def _flush_page(self):
        page = getattr(self, "_page", None)
        if page is not None and hasattr(page, "flush"):
            try:
                page.flush()
            except Exception:
                pass

    def _on_close(self):
        self._flush_page()
        self.destroy()


def main():
    PdkGui().mainloop()
