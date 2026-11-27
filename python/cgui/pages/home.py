#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pages/home.py
-------------
Synopsys-style Home start tab for Cadsemi cgui:
  - Header ("CGUI", current version, cadsemi.com)
  - Tools row: DRC (active), GdsViewer (active), LVS & XRC (Coming soon), Help
"""

import tkinter as tk

from .base import BasePage
import config


def _draw_drc_icon(cv, color):
    """Flat IC layout blocks + verification checkmark."""
    # Top-left and bottom-right overlapping layout rectangles
    cv.create_rectangle(10, 10, 34, 30, outline=color, width=2)
    cv.create_rectangle(22, 20, 46, 40, outline=color, width=2)
    # Metal track accents
    cv.create_line(14, 16, 30, 16, fill=color, width=2)
    cv.create_line(14, 22, 20, 22, fill=color, width=2)
    # Checkmark badge
    cv.create_line(40, 42, 46, 48, 56, 34, fill=color, width=2.5,
                   capstyle="round", joinstyle="round")


def _draw_lvs_icon(cv, color):
    """Muted layout block vs schematic gate symbol with comparison arrows."""
    cv.create_rectangle(8, 14, 24, 42, outline=color, width=2)
    cv.create_line(12, 22, 20, 22, fill=color, width=2)
    cv.create_line(12, 30, 20, 30, fill=color, width=2)
    # Schematic triangle buffer on the right
    cv.create_polygon(40, 16, 40, 40, 56, 28, outline=color, fill="", width=2)
    # Comparison double arrow
    cv.create_line(27, 24, 37, 24, fill=color, width=2)
    cv.create_line(27, 32, 37, 32, fill=color, width=2)


def _draw_xrc_icon(cv, color):
    """Muted parasitic R/C network symbol."""
    # Resistor zig-zag
    cv.create_line(10, 18, 16, 18, 19, 12, 25, 24, 31, 12, 37, 24, 40, 18, 52, 18,
                   fill=color, width=2, joinstyle="round")
    # Capacitor plates downward
    cv.create_line(31, 24, 31, 33, fill=color, width=2)
    cv.create_line(22, 33, 40, 33, fill=color, width=2)
    cv.create_line(22, 40, 40, 40, fill=color, width=2)
    cv.create_line(31, 40, 31, 48, fill=color, width=2)


def _draw_gdsviewer_icon(cv, color):
    """Flat layered IC polygons + eye/magnifier outline for GdsViewer."""
    cv.create_rectangle(10, 12, 38, 34, outline=color, width=2)
    cv.create_rectangle(18, 22, 46, 44, outline=color, width=2)
    cv.create_oval(36, 26, 54, 44, outline=color, fill="", width=2)
    cv.create_line(51, 41, 57, 47, fill=color, width=2.5, capstyle="round")


def _draw_help_icon(cv, color):
    """Flat circle with question mark."""
    cv.create_oval(12, 8, 52, 48, outline=color, width=2)
    cv.create_text(32, 28, text="?", fill=color, font=config.ui_font(8, "bold"))


class _AppTile(tk.Frame):
    """Square editorial card holding a vector icon, title, and optional subtitle."""

    def __init__(self, master, title, draw_icon_fn, subtitle="",
                 command=None, enabled=True):
        T = config.THEME
        self.enabled = bool(enabled)
        self._command = command
        self._base_bg = T["card"] if self.enabled else T["bg_alt"]
        self._hover_bg = T["hover"]
        self._border_default = T["border"]
        self._border_hover = T["accent"]

        super().__init__(
            master,
            width=136,
            height=136,
            bg=self._base_bg,
            bd=0,
            highlightthickness=1,
            highlightbackground=self._border_default,
            cursor="hand2" if self.enabled else "arrow",
        )
        self.pack_propagate(False)

        icon_color = T["accent"] if self.enabled else T["divider"]
        title_fg = T["text"] if self.enabled else T["divider"]
        sub_fg = T["text_muted"] if self.enabled else T["divider"]

        self.canvas = tk.Canvas(
            self, width=64, height=54,
            bg=self._base_bg, bd=0, highlightthickness=0,
        )
        self.canvas.pack(pady=(16, 6))
        draw_icon_fn(self.canvas, icon_color)

        self.title_lbl = tk.Label(
            self, text=title, bg=self._base_bg, fg=title_fg,
            font=config.ui_font(0, "bold") if self.enabled else config.ui_font(0),
            wraplength=120, justify="center",
        )
        self.title_lbl.pack(padx=6)

        self.sub_lbl = None
        if subtitle:
            self.sub_lbl = tk.Label(
                self, text=subtitle, bg=self._base_bg, fg=sub_fg,
                font=config.ui_font(-2), wraplength=122, justify="center",
            )
            self.sub_lbl.pack(padx=6, pady=(2, 0))

        if self.enabled and self._command is not None:
            for w in self._interactive_widgets():
                w.bind("<Button-1>", self._on_click)
                w.bind("<Enter>", self._on_enter)
                w.bind("<Leave>", self._on_leave)

    def _interactive_widgets(self):
        widgets = [self, self.canvas, self.title_lbl]
        if self.sub_lbl is not None:
            widgets.append(self.sub_lbl)
        return widgets

    def _set_bg(self, bg, border):
        self.configure(bg=bg, highlightbackground=border)
        for w in (self.canvas, self.title_lbl, self.sub_lbl):
            if w is not None:
                w.configure(bg=bg)

    def _on_enter(self, _event=None):
        self._set_bg(self._hover_bg, self._border_hover)

    def _on_leave(self, _event=None):
        self._set_bg(self._base_bg, self._border_default)

    def _on_click(self, _event=None):
        if self.enabled and self._command is not None:
            self._command()


class HomePage(BasePage):
    module = "HOME"

    def build(self):
        T = config.THEME
        self.app_tiles = {}

        # Generous editorial margins matching cadsemi.com
        body = tk.Frame(self, bg=self.bg)
        body.pack(fill="both", expand=True, padx=16, pady=12)

        # Header section
        self.heading_lbl = tk.Label(
            body, text="PVFlow", bg=self.bg, fg=T["text"],
            font=config.ui_font(10, "bold"), anchor="w",
        )
        self.heading_lbl.pack(anchor="w")
        tk.Label(
            body,
            text="Version %s  |  cadsemi.com" % config.latest_revision(),
            bg=self.bg, fg=T["text_muted"],
            font=config.ui_font(0), anchor="w",
        ).pack(anchor="w", pady=(2, 22))

        # Tools section
        self.tools_lbl = tk.Label(
            body, text="Tools", bg=self.bg, fg=T["text"],
            font=config.ui_font(1, "bold"), anchor="w",
        )
        self.tools_lbl.pack(anchor="w", pady=(0, 10))

        apps_row = tk.Frame(body, bg=self.bg)
        apps_row.pack(anchor="w", pady=(0, 26))

        specs = (
            ("DRC", "DRC Verification", _draw_drc_icon,
             lambda: self.app.new_drc_tab(replace_home=True), True),
            ("GdsViewer", "KLayout GDS", _draw_gdsviewer_icon,
             lambda: self.app.new_gdsviewer_tab(replace_home=True), True),
            ("LVS", "Custom on request", _draw_lvs_icon, None, False),
            ("XRC", "Custom on request", _draw_xrc_icon, None, False),
            ("Help", "User Guide", _draw_help_icon,
             lambda: self.app.open_user_guide(), True),
        )
        for key, subtitle, icon_fn, cmd, enabled in specs:
            tile = _AppTile(
                apps_row, title=key, subtitle=subtitle,
                draw_icon_fn=icon_fn, command=cmd, enabled=enabled,
            )
            tile.pack(side="left", padx=(0, 14))
            self.app_tiles[key] = tile
