#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pages/doc.py
------------
DOC page: three-column document browser.

The document list in the left column comes from the files under config.DOC_DIR
(default data/doc/); clicking one loads its content into the middle text box
(with right + bottom scrollbars).
"""

import os
import tkinter as tk

from .base import BasePage
from widgets import ScrolledText
import config


class DocPage(BasePage):
    module = "DOC"
    bg = "#e5e5e5"

    def build(self):
        col1 = tk.Frame(self, bg=self.bg, width=180)
        col2 = tk.Frame(self, bg=self.bg)
        col3 = tk.Frame(self, bg=self.bg, width=220)
        col1.pack(side="left", fill="y")
        col2.pack(side="left", fill="both", expand=True)
        col3.pack(side="right", fill="y")
        col1.pack_propagate(False)
        col3.pack_propagate(False)

        tk.Label(col1, text="Doc. No.", bg=self.bg).pack(anchor="w")

        self.viewer = ScrolledText(col2, wrap="word", readonly=True, bg="white", bd=1)
        self.viewer.pack(fill="both", expand=True)
        self.viewer.set_text("Title\n\n(click a document name on the left to load it)")

        for name in self._doc_names():
            lbl = tk.Label(col1, text=name, fg="blue", bg=self.bg, cursor="hand2")
            lbl.pack(anchor="w")
            lbl.bind("<Button-1>", lambda e, n=name: self._load_doc(n))

        tk.Label(col3, text="Doc. Group", bg=self.bg).pack(anchor="w")
        for f in ["Release_Note.pdf", "Design_Note.pdf"]:
            tk.Label(col3, text=f, fg="blue", bg=self.bg, cursor="hand2").pack(anchor="w")

    @staticmethod
    def _doc_names():
        try:
            files = sorted(os.listdir(config.DOC_DIR))
        except OSError:
            return []
        return [os.path.splitext(f)[0] for f in files if f.endswith(".txt")]

    def _load_doc(self, name):
        path = os.path.join(config.DOC_DIR, name + ".txt")
        content = config.read_text(path, default="(document content not found: %s)" % path)
        self.viewer.set_text("Title\n\n%s\n\n%s" % (name, content))
