#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pages/system.py
---------------
SYSTEM 頁面:顯示版本更新紀錄。

內容從 config.page_file("SYSTEM")(預設 data/system.txt)讀入,
文字框右側 + 下方都有滾輪,並設為唯讀。
"""

from .base import BasePage
from widgets import ScrolledText
import config


class SystemPage(BasePage):
    module = "SYSTEM"
    bg = "white"

    def build(self):
        st = ScrolledText(
            self, wrap="none", readonly=True,
            bg="white", bd=0, font=("Courier New", 10),
        )
        st.pack(fill="both", expand=True)
        st.load_file(config.page_file(self.module))
