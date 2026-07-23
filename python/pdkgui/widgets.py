#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
widgets.py
----------
pdkgui 共用的 Tkinter 元件。

- ScrolledText : 文字框 + 右側(直向)+ 下方(橫向)滾輪,並可直接讀檔。
- LogoPanel    : 右下角公司 Logo 展示區。
"""

import os
import tkinter as tk

import config


class ScrolledText(tk.Frame):
    """帶「右側 + 下方」雙滾輪的文字框。

    用法:
        st = ScrolledText(parent, readonly=True)
        st.load_file("/path/to/file.txt")   # 讀不到檔會顯示提示,不會崩潰
        st.pack(fill="both", expand=True)
    """

    def __init__(self, master, wrap="none", readonly=False, **text_kw):
        super().__init__(master)
        self._readonly = readonly

        self.text = tk.Text(self, wrap=wrap, **text_kw)
        yscroll = tk.Scrollbar(self, orient="vertical", command=self.text.yview)
        xscroll = tk.Scrollbar(self, orient="horizontal", command=self.text.xview)
        self.text.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)

        # grid 讓右側直滾輪與下方橫滾輪都固定在邊緣
        self.text.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")   # 右側
        xscroll.grid(row=1, column=0, sticky="we")   # 下方
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

    def set_text(self, content):
        self.text.configure(state="normal")
        self.text.delete("1.0", tk.END)
        self.text.insert("1.0", content)
        if self._readonly:
            self.text.configure(state="disabled")

    def get_text(self):
        return self.text.get("1.0", "end-1c")

    def load_file(self, path, encoding="utf-8"):
        """讀取檔案內容並顯示;失敗時顯示提示文字。"""
        if not path:
            self.set_text("(未設定要讀取的檔案)")
            return
        try:
            with open(path, encoding=encoding) as f:
                self.set_text(f.read())
        except OSError as e:
            self.set_text("(無法讀取檔案)\n%s\n%s" % (path, e))


class LogoPanel(tk.Frame):
    """右下角公司 Logo 展示區。

    把 config.LOGO_PATH 改成自己的圖檔路徑(png/gif/jpg)即可替換;
    找不到圖檔時退回顯示 config.LOGO_TEXT。
    """

    def __init__(self, master, path=None, text=None, **kwargs):
        super().__init__(master, bg=config.LOGO_BG, **kwargs)
        self._photo = None  # 保留參照,避免被 GC 回收
        self._build(path or config.LOGO_PATH, text or config.LOGO_TEXT)

    def _build(self, path, text):
        img_label = None
        if path and os.path.isfile(path):
            try:
                try:
                    self._photo = tk.PhotoImage(file=path)
                except tk.TclError:
                    from PIL import Image, ImageTk  # 需要 pip install pillow
                    self._photo = ImageTk.PhotoImage(Image.open(path))
                img_label = tk.Label(self, image=self._photo, bg=config.LOGO_BG)
            except Exception as e:
                print("Logo 圖片載入失敗,改用文字顯示: %s" % e)

        if img_label is not None:
            img_label.pack(expand=True, fill="both")
        else:
            tk.Label(
                self, text=text, bg=config.LOGO_BG, fg=config.LOGO_FG,
                font=("Arial", 16, "bold"),
            ).pack(expand=True, fill="both")
