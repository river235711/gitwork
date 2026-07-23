#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pages/secure.py
---------------
SECURE 頁面:示範「pdkgui 執行加密程式碼」。

本頁不含實際 UI 邏輯 —— 它在執行期把 data/secure/secure_page.pdkc
解密成模組後,呼叫其中的 build(page) 來建立畫面。
"""

import os
import tkinter as tk

from .base import BasePage
import config
import pdk_secure

SECURE_BLOB = os.path.join(config.DATA_DIR, "secure", "secure_page.pdkc")


class SecurePage(BasePage):
    module = "SECURE"

    def build(self):
        try:
            mod = pdk_secure.import_from_encrypted(SECURE_BLOB, "pdkgui_secure_page")
        except Exception as e:
            tk.Label(
                self, bg=self.bg, fg="red", justify="left",
                text="無法載入加密模組:\n%s\n\n檔案: %s" % (e, SECURE_BLOB),
            ).pack(padx=20, pady=20)
            return

        entry = getattr(mod, "build", None)
        if callable(entry):
            entry(self)
        else:
            tk.Label(self, bg=self.bg,
                     text="加密模組缺少 build() 進入點").pack(padx=20, pady=20)
