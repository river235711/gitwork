#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pdkgui.py  ── bootstrap(明文,不含商業邏輯)
-------------------------------------------------
這是唯一需要保持明文的進入點。它只做兩件事:

  1. 安裝「加密模組 import hook」——之後 import config / widgets / pages /
     pdkgui_app 等,會自動從同目錄的 .pdkc 加密檔解密載入(部署版)。
  2. 載入並執行主程式 pdkgui_app.main()。

在「原始碼開發環境」(沒有對應的 .pdkc 檔)時,import hook 不會攔截,
Python 會照常載入明文 .py,因此同一支 bootstrap 開發/部署都能跑。

實際的程式邏輯都在 pdkgui_app / config / widgets / pages,
部署時這些會是加密的 .pdkc(見 pdk_build.py)。
"""

import io
import os
import sys

# 舊版 Python 在 locale=C 環境下的中文輸出保險
try:
    if sys.stdout.encoding is None or "utf" not in sys.stdout.encoding.lower():
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
except Exception:
    pass

import pdk_secure

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 安裝加密模組載入器(有 .pdkc 才會接管;純原始碼環境自動略過)
pdk_secure.install_import_hook(BASE_DIR)

import pdkgui_app

if __name__ == "__main__":
    pdkgui_app.main()
