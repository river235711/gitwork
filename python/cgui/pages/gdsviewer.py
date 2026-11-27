#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pages/gdsviewer.py
------------------
Dedicated KLayout GDS Viewer workspace tab:
  - LayoutFile (.gds / .gds.gz / .oas) with Open / Clear
  - LayerMap (.lyp or Virtuoso .layermap, auto-converted on launch) with Open / Edit
  - TopCell (filled by clicking any scanned cell)
  - Mode: Edit mode (-e)
  - Open KLayout (using 3-tier lookup) & pure-Python Scan Cells listbox
"""

import os
import shutil
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox

from .base import BasePage
from .gdsview import open_gds_klayout, scan_gds_cells
from widgets import button_kwargs
import config


class GdsViewerPage(BasePage):
    module = "GDSVIEWER"

    def build(self):
        T = config.THEME
        self.entries = {}
        self.grid_columnconfigure(1, weight=1)

        tk.Label(
            self, text="GDS Viewer", bg=self.bg, fg=T["text"],
            font=config.ui_font(3, "bold"),
        ).grid(row=0, column=0, columnspan=4, pady=(2, 12))

        r = 1
        self._entry_row(
            r, "LayoutFile",
            [("Open", self._browse_layout), ("Clear", self._clear_layout)],
        ); r += 1
        self._entry_row(
            r, "LayerMap",
            [("Open", self._browse_layermap), ("Edit", self._edit_layermap)],
        ); r += 1
        self._entry_row(r, "TopCell"); r += 1

        # Mode checkbutton row
        tk.Label(self, text="Mode", bg=self.bg, fg=T["text"]).grid(
            row=r, column=0, sticky="w", pady=3
        )
        self._edit_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            self, variable=self._edit_var, text="Edit mode (-e)",
            bg=self.bg, fg=T["text"], activebackground=self.bg,
            selectcolor=T["input_bg"], highlightthickness=0,
        ).grid(row=r, column=1, sticky="w", padx=6, pady=3)
        self.entries["EditMode"] = self._edit_var
        r += 1

        # Primary / secondary action strip
        bf = tk.Frame(self, bg=self.bg)
        bf.grid(row=r, column=0, columnspan=4, pady=12)
        tk.Button(
            bf, text="Open KLayout", width=14, pady=4,
            command=self._on_open_klayout, **button_kwargs("primary"),
        ).pack(side="left", padx=5)
        tk.Button(
            bf, text="Scan Cells", width=14, pady=4,
            command=self._on_scan_cells, **button_kwargs("secondary"),
        ).pack(side="left", padx=5)
        r += 1

        # Cells list panel
        tk.Label(
            self, text="Cells (* = Top Cell)", bg=self.bg,
            fg=T["text_muted"], font=config.ui_font(-1, "bold"), anchor="w",
        ).grid(row=r, column=0, columnspan=4, sticky="w", pady=(2, 4))
        r += 1

        list_frame = tk.Frame(
            self, bg=T["border"], bd=0,
            highlightthickness=1, highlightbackground=T["border"],
            highlightcolor=T["accent"],
        )
        list_frame.grid(row=r, column=0, columnspan=4, sticky="nsew")
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(r, weight=1)

        sb_kw = dict(
            bg=T["bg_alt"], troughcolor=T["bg"],
            activebackground=T["divider"], bd=0,
            highlightthickness=0, relief="flat",
        )
        self.cell_list = tk.Listbox(
            list_frame, bg=T["input_bg"], fg=T["text"],
            selectbackground=T["selection"], selectforeground=T["text"],
            bd=0, highlightthickness=0, activestyle="none",
            font=config.mono_font(),
        )
        yscroll = tk.Scrollbar(list_frame, orient="vertical",
                               command=self.cell_list.yview, **sb_kw)
        xscroll = tk.Scrollbar(list_frame, orient="horizontal",
                               command=self.cell_list.xview, **sb_kw)
        self.cell_list.configure(yscrollcommand=yscroll.set,
                                 xscrollcommand=xscroll.set)
        self.cell_list.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="we")
        self.cell_list.bind("<<ListboxSelect>>", self._on_select_cell)

    def _entry_row(self, row, key, buttons=()):
        T = config.THEME
        tk.Label(self, text=key, bg=self.bg, fg=T["text"]).grid(
            row=row, column=0, sticky="w", pady=3
        )
        e = tk.Entry(self)
        e.grid(row=row, column=1, sticky="we", padx=6, pady=3, ipady=3)
        self.entries[key] = e
        btn_kw = button_kwargs("secondary")
        for col, (text, cmd) in enumerate(buttons, start=2):
            tk.Button(
                self, text=text, command=cmd, padx=10, pady=2, **btn_kw
            ).grid(row=row, column=col, sticky="we", padx=3, pady=3)

    # ------------------------------------------------------------------
    def _entry(self, key):
        w = self.entries.get(key)
        return w.get().strip() if w is not None else ""

    def _set_entry(self, key, val):
        w = self.entries[key]
        w.delete(0, tk.END)
        if val:
            w.insert(0, val)

    def _browse_layout(self):
        path = filedialog.askopenfilename(
            title="Select GDS / Layout File",
            filetypes=[("Layout files", "*.gds *.gds.gz *.oas"), ("All files", "*")],
        )
        if path:
            self._set_entry("LayoutFile", path)

    def _clear_layout(self):
        self._set_entry("LayoutFile", "")
        self._set_entry("TopCell", "")
        self.cell_list.delete(0, tk.END)

    def _browse_layermap(self):
        path = filedialog.askopenfilename(
            title="Select KLayout .lyp or Virtuoso .layermap",
            filetypes=[("Layer map files", "*.lyp *.layermap *.map"), ("All files", "*")],
        )
        if path:
            self._set_entry("LayerMap", path)

    def _edit_layermap(self):
        path = self._entry("LayerMap")
        if not path:
            messagebox.showwarning("cgui", "LayerMap is empty")
            return
        editor = self.app.env.get("editor") or "gvim"
        if not shutil.which(editor):
            messagebox.showinfo("cgui", "editor not found: %s" % editor)
            return
        try:
            subprocess.Popen([editor, os.path.expanduser(path)],
                             env=config.desktop_env())
        except Exception as e:
            messagebox.showerror("cgui", "Failed to launch editor:\n%s" % e)

    def _on_scan_cells(self):
        gds = self._entry("LayoutFile")
        if not gds:
            messagebox.showwarning("cgui", "Please select a LayoutFile first")
            return
        full = os.path.expanduser(gds)
        if not os.path.isfile(full):
            messagebox.showerror("cgui", "LayoutFile not found:\n%s" % full)
            return
        try:
            top_cells, all_cells = scan_gds_cells(full)
        except Exception as e:
            messagebox.showerror("cgui", "Failed to scan GDS cells:\n%s" % e)
            return

        self.cell_list.delete(0, tk.END)
        top_set = set(top_cells)
        for name in top_cells:
            self.cell_list.insert(tk.END, "* " + name)
        for name in all_cells:
            if name not in top_set:
                self.cell_list.insert(tk.END, "  " + name)
        if top_cells and not self._entry("TopCell"):
            self._set_entry("TopCell", top_cells[0])

    def _on_select_cell(self, _event=None):
        sel = self.cell_list.curselection()
        if not sel:
            return
        raw = self.cell_list.get(sel[0])
        name = raw[2:].strip() if raw.startswith(("* ", "  ")) else raw.strip()
        if name:
            self._set_entry("TopCell", name)

    def _on_open_klayout(self):
        open_gds_klayout(
            self.app,
            self._entry("LayoutFile"),
            layer_map=self._entry("LayerMap") or None,
            edit_mode=bool(self._edit_var.get()),
        )
