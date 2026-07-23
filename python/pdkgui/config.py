#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
config.py
---------
pdkgui 的集中設定檔。

★ 你只需要在這裡指定「每個 tab 要讀哪個檔案」★
所有頁面(pages/*.py)都透過 page_file(<模組名稱>) 取得檔案路徑,
不會把路徑寫死在頁面邏輯裡。換檔時只要改 PAGE_FILES 即可。

支援三種指定方式:
  1. 相對 data/ 的檔名(預設)         例: "system.txt"
  2. 絕對路徑                         例: "/datacenter/proj/system.txt"
  3. 環境變數覆蓋(執行前 export)     例: PDKGUI_SYSTEM_FILE=/path/xxx.txt
"""

import os

# --------------------------------------------------------------------------
# 路徑
# --------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

# --------------------------------------------------------------------------
# 一般設定
# --------------------------------------------------------------------------
DESIGN_NAME = "t22_1p7m_4x1z1u"     # 視窗標題會顯示 "pdkgui - <DESIGN_NAME>"

# --- Logo 設定:把這裡換成你自己的圖檔路徑即可 ---
LOGO_PATH = os.path.join(BASE_DIR, "company_logo.png")
LOGO_TEXT = "YOUR COMPANY LOGO"     # 找不到圖檔時,退回顯示的文字
LOGO_BG = "#0b5fa5"
LOGO_FG = "white"

# 左側選單項目(依照截圖順序)
MENU_ITEMS = [
    "PROCESS", "ENV", "DRC", "ANT", "WB", "BUMP", "DMDV", "DPDO",
    "LVS", "XRC", "JIVARO", "SKIPPER", "KLAYOUT", "DOC", "SYSTEM",
]

# 使用「驗證流程頁面樣板」的模組
VERIFY_MODULES = ["DRC", "ANT", "WB", "BUMP", "DMDV", "DPDO", "LVS", "XRC", "JIVARO"]

# --------------------------------------------------------------------------
# ★ 每個 tab → 要讀取的檔案(相對 data/ 的路徑)★
# --------------------------------------------------------------------------
PAGE_FILES = {
    "SYSTEM":  "system.txt",     # 版本更新紀錄
    "PROCESS": "process.txt",    # 可選的 process / design 清單(一行一個)
    "ENV":     "env.txt",        # 工具版本設定
    "SKIPPER": "skipper.txt",    # 最近開過的 GDS 清單(一行一個)
    # 驗證模組的 command file:
    "DRC":     "verify/DRC.com",
    "ANT":     "verify/ANT.com",
    "WB":      "verify/WB.com",
    "BUMP":    "verify/BUMP.com",
    "DMDV":    "verify/DMDV.com",
    "DPDO":    "verify/DPDO.com",
    "LVS":     "verify/LVS.com",
    "XRC":     "verify/XRC.com",
    "JIVARO":  "verify/JIVARO.com",
}

# DOC 頁面的文件內容資料夾(每個文件一個 .txt 檔,檔名即文件名稱)
DOC_DIR = os.path.join(DATA_DIR, "doc")

# 若想用環境變數覆蓋某個 tab 的檔案,在這裡列出對應關係即可。
# 例:export PDKGUI_SYSTEM_FILE=/path/to/xxx.txt
_ENV_OVERRIDES = {
    "SYSTEM":  "PDKGUI_SYSTEM_FILE",
    "PROCESS": "PDKGUI_PROCESS_FILE",
    "ENV":     "PDKGUI_ENV_FILE",
    "SKIPPER": "PDKGUI_SKIPPER_FILE",
}


def page_file(module_name):
    """回傳某個 tab 要讀取檔案的「絕對路徑」。

    優先順序:環境變數覆蓋 > PAGE_FILES 設定。
    找不到設定時回傳 None。
    """
    env_var = _ENV_OVERRIDES.get(module_name)
    if env_var and os.environ.get(env_var):
        return os.path.abspath(os.path.expanduser(os.environ[env_var]))

    rel = PAGE_FILES.get(module_name)
    if rel is None:
        return None
    if os.path.isabs(rel):
        return rel
    return os.path.join(DATA_DIR, rel)


def read_text(path, default=""):
    """讀取純文字檔;讀不到就回傳 default(不丟例外)。"""
    if not path:
        return default
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return default


def read_lines(path):
    """讀取檔案並回傳非空、非註解(#)的行清單。"""
    lines = []
    for raw in read_text(path).splitlines():
        s = raw.strip()
        if s and not s.startswith("#"):
            lines.append(s)
    return lines
