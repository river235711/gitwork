#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
widgets.py
----------
Shared Tkinter widgets for cgui.

- ScrolledText : text box + vertical (right) + horizontal (bottom) scrollbars,
                 with a built-in file loader.
- LogoPanel    : bottom-right company logo area.
"""

import os
import tkinter as tk
from tkinter import ttk

import config


def apply_theme(root):
    """Apply config.THEME (cadsemi.com warm light palette) across Tk/ttk widgets."""
    T = config.THEME
    defaults = (
        ("*Background", T["bg"]),
        ("*Foreground", T["text"]),
        ("*Entry.Background", T["input_bg"]),
        ("*Entry.Foreground", T["text"]),
        ("*Entry.insertBackground", T["text"]),
        ("*Entry.selectBackground", T["selection"]),
        ("*Entry.selectForeground", T["text"]),
        ("*Entry.relief", "flat"),
        ("*Entry.borderWidth", "2"),
        ("*Entry.highlightThickness", "1"),
        ("*Entry.highlightBackground", T["input_border"]),
        ("*Entry.highlightColor", T["accent"]),
        ("*Text.Background", T["input_bg"]),
        ("*Text.Foreground", T["text"]),
        ("*Text.insertBackground", T["text"]),
        ("*Text.selectBackground", T["selection"]),
        ("*Text.selectForeground", T["text"]),
        ("*Text.highlightThickness", "0"),
        ("*Scrollbar.Background", T["bg_alt"]),
        ("*Scrollbar.troughColor", T["bg"]),
        ("*Scrollbar.activeBackground", T["divider"]),
        ("*Scrollbar.highlightThickness", "0"),
        ("*Scrollbar.borderWidth", "0"),
        ("*Scrollbar.relief", "flat"),
        ("*Checkbutton.Background", T["bg"]),
        ("*Checkbutton.Foreground", T["text"]),
        ("*Checkbutton.activeBackground", T["bg"]),
        ("*Checkbutton.activeForeground", T["text"]),
        ("*Checkbutton.selectColor", T["input_bg"]),
        ("*Checkbutton.highlightThickness", "0"),
        ("*Listbox.Background", T["input_bg"]),
        ("*Listbox.Foreground", T["text"]),
        ("*Listbox.selectBackground", T["selection"]),
        ("*Listbox.selectForeground", T["text"]),
    )
    for pattern, val in defaults:
        try:
            root.option_add(pattern, val)
        except tk.TclError:
            pass
    try:
        style = ttk.Style(root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure(".", background=T["bg"], foreground=T["text"])
        style.configure(
            "TCombobox",
            fieldbackground=T["input_bg"],
            background=T["bg_alt"],
            foreground=T["text"],
            bordercolor=T["input_border"],
            arrowcolor=T["text_muted"],
            lightcolor=T["bg"],
            darkcolor=T["border"],
            padding=4,
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", T["input_bg"])],
            selectbackground=[("readonly", T["selection"])],
            selectforeground=[("readonly", T["text"])],
        )
    except tk.TclError:
        pass


def button_kwargs(kind="secondary"):
    """Return Tk Button styling kwargs for 'primary' or 'secondary' actions."""
    T = config.THEME
    if kind == "primary":
        return {
            "bg": T["btn_bg"],
            "fg": T["btn_fg"],
            "activebackground": T["btn_hover"],
            "activeforeground": T["btn_fg"],
            "relief": "flat",
            "bd": 0,
            "highlightthickness": 1,
            "highlightbackground": T["btn_bg"],
            "highlightcolor": T["accent"],
            "font": config.ui_font(0, "bold"),
            "cursor": "hand2",
        }
    return {
        "bg": T["card"],
        "fg": T["text"],
        "activebackground": T["hover"],
        "activeforeground": T["text"],
        "relief": "flat",
        "bd": 0,
        "highlightthickness": 1,
        "highlightbackground": T["input_border"],
        "highlightcolor": T["accent"],
        "cursor": "hand2",
    }


class ScrolledText(tk.Frame):
    """Text box with both right (vertical) and bottom (horizontal) scrollbars.

    Usage:
        st = ScrolledText(parent, readonly=True)
        st.load_file("/path/to/file.txt")   # shows a hint (does not crash) if unreadable
        st.pack(fill="both", expand=True)
    """

    def __init__(self, master, wrap="none", readonly=False, **text_kw):
        T = config.THEME
        super().__init__(
            master,
            bg=T["border"],
            bd=0,
            highlightthickness=1,
            highlightbackground=T["border"],
            highlightcolor=T["accent"],
        )
        self._readonly = readonly

        text_kw.setdefault("bg", T["input_bg"])
        text_kw.setdefault("fg", T["text"])
        text_kw.setdefault("insertbackground", T["text"])
        text_kw.setdefault("selectbackground", T["selection"])
        text_kw.setdefault("selectforeground", T["text"])
        text_kw.setdefault("bd", 0)
        text_kw.setdefault("highlightthickness", 0)
        text_kw.setdefault("padx", 8)
        text_kw.setdefault("pady", 6)

        self.text = tk.Text(self, wrap=wrap, **text_kw)
        sb_kw = dict(
            bg=T["bg_alt"],
            troughcolor=T["bg"],
            activebackground=T["divider"],
            bd=0,
            highlightthickness=0,
            relief="flat",
        )
        yscroll = tk.Scrollbar(self, orient="vertical", command=self.text.yview, **sb_kw)
        xscroll = tk.Scrollbar(self, orient="horizontal", command=self.text.xview, **sb_kw)
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
                font=config.ui_font(5, "bold"),
            ).pack(expand=True, fill="both")
