#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pages/doc.py
------------
DOC page: three-column document browser driven by the DOC index.

The index (central per process, see config.doc_index_file) has one line per
document:  <Doc. No.>|<Doc ID>|<Title>

    Doc. No.    left column   -- documents grouped by this name
    Title       middle column -- the titles of the selected Doc. No.
    Doc. Group  right column  -- the .pdf files of the selected title, found in
                                 <DOC_ROOT>/<DESIGN>/doc/<Doc. No.>/<Doc ID>/

Clicking a Doc. No. fills the titles, clicking a title fills the PDF list, and
clicking a PDF opens it in a viewer.
"""

import os
import shutil
import subprocess

import tkinter as tk
from tkinter import messagebox

from .base import BasePage
import config

_PDF_VIEWERS = ("okular", "evince", "atril", "qpdfview", "acroread", "xdg-open")


class DocPage(BasePage):
    module = "DOC"
    bg = "#e5e5e5"

    def build(self):
        self.docs = config.read_doc_index(config.DESIGN_NAME)
        self.titles = []        # [(docid, title)] currently shown in the middle
        self.pdfs = []          # [full path] currently shown on the right
        self.docno = None       # selected Doc. No.

        self.lb_docno = self._column("left", "Doc. No.", 190, self._on_pick_docno)
        self.lb_group = self._column("right", "Doc. Group", 260, self._on_pick_pdf)
        # the middle column takes the remaining width
        self.lb_title = self._column("left", "Title", None, self._on_pick_title)

        for name in sorted({d[0] for d in self.docs}):
            self.lb_docno.insert(tk.END, name)
        if not self.docs:
            self.lb_title.insert(
                tk.END, "(document index not found: %s)"
                % config.doc_index_file(config.DESIGN_NAME))

    # ------------------------------------------------------------------
    def _column(self, side, header, width, on_click):
        """One labelled, scrollable list column."""
        frame = tk.Frame(self, bg=self.bg)
        if width:
            frame.configure(width=width)
            frame.pack(side=side, fill="y")
            frame.pack_propagate(False)
        else:
            frame.pack(side=side, fill="both", expand=True)

        tk.Label(frame, text=header, bg=self.bg, anchor="w").pack(fill="x")
        body = tk.Frame(frame, bg=self.bg)
        body.pack(fill="both", expand=True)

        # vertical + horizontal scrollbars: long titles / file names stay
        # reachable when the window is narrow
        vsb = tk.Scrollbar(body, orient="vertical")
        hsb = tk.Scrollbar(body, orient="horizontal")
        lb = tk.Listbox(body, activestyle="none", exportselection=False,
                        fg="blue", bg=self.bg, bd=1, highlightthickness=0,
                        selectbackground="#a8d3f0", selectforeground="blue",
                        yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        lb.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=1)
        vsb.configure(command=lb.yview)
        hsb.configure(command=lb.xview)
        lb.bind("<<ListboxSelect>>", lambda e: on_click())
        return lb

    @staticmethod
    def _selected(listbox):
        sel = listbox.curselection()
        return sel[0] if sel else None

    # ------------------------------------------------------------------
    def _on_pick_docno(self):
        i = self._selected(self.lb_docno)
        if i is None:
            return
        self.docno = self.lb_docno.get(i)
        self.titles = [(docid, title) for no, docid, title in self.docs
                       if no == self.docno]
        self.lb_title.delete(0, tk.END)
        for _docid, title in self.titles:
            self.lb_title.insert(tk.END, title)
        self.lb_group.delete(0, tk.END)
        self.pdfs = []

    def _on_pick_title(self):
        i = self._selected(self.lb_title)
        if i is None or i >= len(self.titles):
            return
        docid = self.titles[i][0]
        folder = config.doc_group_dir(config.DESIGN_NAME, self.docno, docid)
        self.lb_group.delete(0, tk.END)
        try:
            names = sorted(f for f in os.listdir(folder)
                           if f.lower().endswith(".pdf"))
        except OSError:
            self.pdfs = []
            self.lb_group.insert(tk.END, "(not found: %s)" % folder)
            return
        self.pdfs = [os.path.join(folder, f) for f in names]
        for f in names:
            self.lb_group.insert(tk.END, f)

    def _on_pick_pdf(self):
        i = self._selected(self.lb_group)
        if i is None or i >= len(self.pdfs):
            return
        self._open_pdf(self.pdfs[i])

    @staticmethod
    def _open_pdf(path):
        for prog in _PDF_VIEWERS:
            if shutil.which(prog):
                try:
                    subprocess.Popen([prog, path])
                    return
                except Exception:
                    continue
        messagebox.showinfo("pdkgui", "No PDF viewer found for:\n%s" % path)
