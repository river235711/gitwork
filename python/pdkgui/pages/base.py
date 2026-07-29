#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pages/base.py
-------------
Common base class for all pages.

Each page subclasses BasePage and implements build(); any file it needs is
obtained via config.page_file(self.module) rather than hard-coded in the page.
"""

import tkinter as tk


class BasePage(tk.Frame):
    module = ""          # key into config.PAGE_FILES (overridden by subclasses)
    bg = "#d9d9d9"

    def __init__(self, master, app):
        super().__init__(master, bg=self.bg)
        self.app = app   # the main PdkGui window, for shared state
        self.build()

    def build(self):
        raise NotImplementedError

    def on_show(self):
        """Called each time the tab is brought to the front.

        Pages are built once and kept, so anything that has to reflect the
        outside world -- the central deck pointer, which release is current --
        is refreshed here rather than in build()."""
