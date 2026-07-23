#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pdkgui.py
---------
一個仿照內部 EDA 流程管理工具 (pdkgui) 的 Tkinter GUI。

程式檔案架構:
    pdkgui.py     進入點:主視窗 + 左側選單 + 頁面切換(路由)
    config.py     集中設定;★「每個 tab 讀哪個檔案」都寫在這裡
    widgets.py    共用元件(ScrolledText 雙滾輪 / LogoPanel)
    pages/        各 tab 的頁面(每個 tab 從 config.page_file() 讀取內容)
    data/         各 tab 讀取的內容檔(system.txt / env.txt / ...)

Python 3.6+ 皆可執行;若環境是舊版 Python 在 locale=C 下,
建議搭配下面兩行避免中文輸出出現 UnicodeEncodeError:
    export LANG=en_US.UTF-8
    export LC_ALL=en_US.UTF-8
"""

import io
import sys
import tkinter as tk

import config
from pages import build_page

# 舊版 Python 在 locale=C 環境下的中文輸出保險
try:
    if sys.stdout.encoding is None or "utf" not in sys.stdout.encoding.lower():
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
except Exception:
    pass


class PdkGui(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("pdkgui - %s" % config.DESIGN_NAME)
        self.geometry("980x560")
        self.configure(bg="#d9d9d9")

        self.current_module = tk.StringVar(value=config.MENU_ITEMS[0])

        self._build_sidebar()
        self._build_content_area()
        self.show_module(config.MENU_ITEMS[0])

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
        for w in self.content.winfo_children():
            w.destroy()

        page = build_page(name, self.content, self)
        page.pack(fill="both", expand=True, padx=10, pady=10)


if __name__ == "__main__":
    app = PdkGui()
    app.mainloop()
