#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pages/base.py
-------------
所有頁面的共用基底類別。

每個頁面繼承 BasePage,並實作 build();
需要讀取的檔案一律透過 config.page_file(self.module) 取得,
不把路徑寫死在頁面裡。
"""

import tkinter as tk


class BasePage(tk.Frame):
    module = ""          # 對應 config.PAGE_FILES 的 key(子類別覆寫)
    bg = "#d9d9d9"

    def __init__(self, master, app):
        super().__init__(master, bg=self.bg)
        self.app = app   # 指向主視窗 PdkGui,方便存取共用狀態
        self.build()

    def build(self):
        raise NotImplementedError
