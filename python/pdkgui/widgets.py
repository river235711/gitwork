#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
widgets.py
----------
Shared Tkinter widgets for pdkgui.

- ScrolledText : text box + vertical (right) + horizontal (bottom) scrollbars,
                 with a built-in file loader.
- LogoPanel    : bottom-right company logo area.
"""

import os
import tkinter as tk

import config


class ScrolledText(tk.Frame):
    """Text box with both right (vertical) and bottom (horizontal) scrollbars.

    Usage:
        st = ScrolledText(parent, readonly=True)
        st.load_file("/path/to/file.txt")   # shows a hint (does not crash) if unreadable
        st.pack(fill="both", expand=True)
    """

    def __init__(self, master, wrap="none", readonly=False, **text_kw):
        super().__init__(master)
        self._readonly = readonly

        self.text = tk.Text(self, wrap=wrap, **text_kw)
        yscroll = tk.Scrollbar(self, orient="vertical", command=self.text.yview)
        xscroll = tk.Scrollbar(self, orient="horizontal", command=self.text.xview)
        self.text.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)

        # grid keeps the vertical scrollbar on the right and horizontal at the bottom
        self.text.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")   # right
        xscroll.grid(row=1, column=0, sticky="we")   # bottom
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
        """Load and show a file's content; show a hint on failure."""
        if not path:
            self.set_text("(no file configured to read)")
            return
        try:
            with open(path, encoding=encoding) as f:
                self.set_text(f.read())
        except OSError as e:
            self.set_text("(cannot read file)\n%s\n%s" % (path, e))


class LogoPanel(tk.Frame):
    """Bottom-right company logo area.

    Point config.LOGO_PATH at your own image (png/gif/jpg) to replace it;
    falls back to config.LOGO_TEXT when the image is not found.
    """

    def __init__(self, master, path=None, text=None, **kwargs):
        super().__init__(master, bg=config.LOGO_BG, **kwargs)
        self._photo = None  # keep a reference so it is not garbage-collected
        self._build(path or config.LOGO_PATH, text or config.LOGO_TEXT)

    def _build(self, path, text):
        img_label = None
        if path and os.path.isfile(path):
            try:
                try:
                    self._photo = tk.PhotoImage(file=path)
                except tk.TclError:
                    from PIL import Image, ImageTk  # needs: pip install pillow
                    self._photo = ImageTk.PhotoImage(Image.open(path))
                img_label = tk.Label(self, image=self._photo, bg=config.LOGO_BG)
            except Exception as e:
                print("Failed to load logo image, showing text instead: %s" % e)

        if img_label is not None:
            img_label.pack(expand=True, fill="both")
        else:
            tk.Label(
                self, text=text, bg=config.LOGO_BG, fg=config.LOGO_FG,
                font=("Arial", 16, "bold"),
            ).pack(expand=True, fill="both")
