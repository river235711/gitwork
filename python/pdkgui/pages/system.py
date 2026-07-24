#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pages/system.py
---------------
SYSTEM page: shows the revision history.

Content is read from config.page_file("SYSTEM") (default data/system.txt); the
text box has right + bottom scrollbars and is read-only.
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
