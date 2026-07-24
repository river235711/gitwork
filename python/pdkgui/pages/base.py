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
