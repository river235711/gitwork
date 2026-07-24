#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pages
-----
Page registry: module name -> page class.

To add a tab:
  1. Add xxx.py in this folder, subclassing BasePage.
  2. Register it in _SPECIAL, or (if it is a verification flow) add it to
     config.VERIFY_MODULES.
  3. Point config.PAGE_FILES at the file it reads.
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

# Modules with a dedicated page
_SPECIAL = {
    "PROCESS": ProcessPage,
    "ENV": EnvPage,
    "SKIPPER": SkipperPage,
    "KLAYOUT": KlayoutPage,
    "DOC": DocPage,
    "SYSTEM": SystemPage,
}


class _PlaceholderPage(BasePage):
    """Not-yet-implemented module: shows placeholder text."""

    def __init__(self, master, app, name):
        self.module = name
        super().__init__(master, app)

    def build(self):
        tk.Label(self, text="*** %s ***\n(not implemented)" % self.module,
                 bg=self.bg, font=("Arial", 11)).pack(pady=20)


def build_page(name, master, app):
    """Build the page for the given module name."""
    if name in _SPECIAL:
        return _SPECIAL[name](master, app)
    if name in config.VERIFY_MODULES:
        return VerifyPage(master, app, module_name=name)
    return _PlaceholderPage(master, app, name)
