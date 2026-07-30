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

import importlib

import config
from .base import BasePage

# Modules with a dedicated page:  <MODULE>: (module file, class)
# Imported on first use rather than here -- in a deployed build every page is a
# separate encrypted file to fetch from NFS, decrypt and compile, and starting
# up only ever shows one of them.
_SPECIAL = {
    "PROCESS": ("process", "ProcessPage"),
    "ENV": ("env", "EnvPage"),
    "SKIPPER": ("skipper", "SkipperPage"),
    "KLAYOUT": ("klayout", "KlayoutPage"),
    "DOC": ("doc", "DocPage"),
    "LOADING": ("loading", "LoadingPage"),
    "SYSTEM": ("system", "SystemPage"),
}


def _page_class(module_name, class_name):
    module = importlib.import_module("." + module_name, __name__)
    return getattr(module, class_name)


class _PlaceholderPage(BasePage):
    """Not-yet-implemented module: shows placeholder text."""

    def __init__(self, master, app, name):
        self.module = name
        super().__init__(master, app)

    def build(self):
        tk.Label(self, text="*** %s ***\n(not implemented)" % self.module,
                 bg=self.bg, font=config.ui_font(1)).pack(pady=20)


def build_page(name, master, app):
    """Build the page for the given module name."""
    with config.timed("build page %s" % name):
        if name in _SPECIAL:
            return _page_class(*_SPECIAL[name])(master, app)
        if name in config.VERIFY_MODULES:
            verify = _page_class("verify", "VerifyPage")
            return verify(master, app, module_name=name)
        return _PlaceholderPage(master, app, name)
