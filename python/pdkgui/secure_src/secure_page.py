#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
secure_src/secure_page.py
-------------------------
這是一支「示範被保護的原始碼」。

它會被 pdk_pack.py 加密成 data/secure/secure_page.pdkc,
pdkgui 的 SECURE tab 在執行期才解密並執行 build()。

★ 實際部署時,你可以只發佈 .pdkc,不放這支明文檔(這個 secure_src/ 資料夾
  只是原始碼保管處)。這裡放的是「不想被使用者直接讀到」的核心邏輯範例。
"""

import tkinter as tk
from tkinter import messagebox


def _secret_algorithm():
    """假裝這是不想外流的核心演算法。"""
    seed = "cadsemi-pdk-secure"
    return sum((i + 1) * ord(c) for i, c in enumerate(seed))


def build(page):
    """SECURE tab 的進入點;page 是 pdkgui 的頁面 Frame(有 .bg 屬性)。"""
    bg = getattr(page, "bg", "#d9d9d9")

    tk.Label(page, text="*** SECURE (加密載入) ***", bg=bg,
             font=("Arial", 12, "bold")).pack(pady=(20, 8))
    tk.Label(page, text="這個頁面的程式碼儲存為加密檔 secure_page.pdkc,",
             bg=bg).pack()
    tk.Label(page, text="執行前才在記憶體解密,磁碟上看不到明文原始碼。",
             bg=bg).pack(pady=(0, 12))

    def run():
        messagebox.showinfo(
            "SECURE",
            "由加密模組執行的核心演算法結果 = %d" % _secret_algorithm(),
        )

    tk.Button(page, text="執行加密邏輯", width=20, command=run).pack(pady=6)
