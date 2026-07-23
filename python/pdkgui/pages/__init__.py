#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pages
-----
頁面註冊表:module 名稱 → 頁面類別。

新增一個 tab 的步驟:
  1. 在此資料夾新增 xxx_page.py,繼承 BasePage。
  2. 在 _SPECIAL 註冊,或(若屬驗證流程)加入 config.VERIFY_MODULES。
  3. 在 config.PAGE_FILES 指定它要讀的檔案。
"""

import tkinter as tk

import config
from .base import BasePage
from .process import ProcessPage
from .env import EnvPage
from .verify import VerifyPage
from .skipper import SkipperPage
from .klayout import KlayoutPage
from .doc import DocPage
from .system import SystemPage

# 有專屬頁面的模組
_SPECIAL = {
    "PROCESS": ProcessPage,
    "ENV": EnvPage,
    "SKIPPER": SkipperPage,
    "KLAYOUT": KlayoutPage,
    "DOC": DocPage,
    "SYSTEM": SystemPage,
}


class _PlaceholderPage(BasePage):
    """尚未實作的模組:顯示佔位文字。"""

    def __init__(self, master, app, name):
        self.module = name
        super().__init__(master, app)

    def build(self):
        tk.Label(self, text="*** %s ***\n(尚未實作)" % self.module,
                 bg=self.bg, font=("Arial", 11)).pack(pady=20)


def build_page(name, master, app):
    """依模組名稱建立對應頁面。"""
    if name in _SPECIAL:
        return _SPECIAL[name](master, app)
    if name in config.VERIFY_MODULES:
        return VerifyPage(master, app, module_name=name)
    return _PlaceholderPage(master, app, name)
