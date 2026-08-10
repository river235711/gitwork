#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pages/system.py
---------------
SYSTEM page, split in two halves:

  top     the revision history, read from config.page_file("SYSTEM"), which
          prefers the central shared copy <DEFAULT_COM_DIR>/system.txt
          (design-independent, so every user sees the same history) and falls
          back to the built-in data/system.txt. Read-only, both scrollbars.

  bottom  which release this window runs and which one is current. When they
          differ (an admin repointed the "current" symlink after this window
          opened) a Restart button reopens pdkgui on the current release.

The check runs whenever the tab is opened, so simply revisiting SYSTEM refreshes
it; a Run on a verification tab asks separately (see pdkgui_app).
"""

import tkinter as tk

from .base import BasePage
from widgets import ScrolledText
import config

_OK_FG = "#1a7f37"
_WARN_BG = "#ffe9a8"


class SystemPage(BasePage):
    module = "SYSTEM"
    bg = "white"

    def build(self):
        # two equal halves
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        st = ScrolledText(
            self, wrap="none", readonly=True,
            bg="white", bd=0, font=config.mono_font(),
        )
        st.grid(row=0, column=0, sticky="nsew")
        st.load_file(config.page_file(self.module))

        self._panel = self._build_version_panel()
        self._panel.grid(row=1, column=0, sticky="nsew", pady=(8, 0))

    def on_show(self):
        """Re-check which release is current: the page is kept between visits,
        so opening SYSTEM is what refreshes it."""
        self._panel.destroy()
        self._panel = self._build_version_panel()
        self._panel.grid(row=1, column=0, sticky="nsew", pady=(8, 0))

    # ------------------------------------------------------------------
    def _build_version_panel(self):
        update = config.pending_update()
        outdated = update is not None
        bg = _WARN_BG if outdated else self.bg

        frame = tk.Frame(self, bg=bg, bd=1, relief="solid")
        tk.Label(frame, text="pdkgui version", bg=bg, anchor="w",
                 font=config.ui_font(0, "bold")).pack(anchor="w", padx=10, pady=(8, 2))

        if outdated:
            running, live, _dir = update
            tk.Label(frame, bg=bg, justify="left", anchor="w",
                     text="This window is running %s.\n"
                          "The current release is now %s." % (running, live)
                     ).pack(anchor="w", padx=10)
            tk.Label(frame, bg=bg, justify="left", anchor="w", fg="#7a5c00",
                     text="Restarting saves your work and reopens on this tab."
                     ).pack(anchor="w", padx=10, pady=(4, 0))
            tk.Button(frame, text="Restart now", width=14,
                      command=self.app.restart).pack(anchor="w", padx=10, pady=8)
        elif config.running_release():
            tk.Label(frame, bg=bg, anchor="w", fg=_OK_FG, font=config.ui_font(1),
                     text=config.running_release()
                     ).pack(anchor="w", padx=10)
            tk.Label(frame, bg=bg, anchor="w", fg="#555",
                     text="This is the current release."
                     ).pack(anchor="w", padx=10, pady=(2, 8))
        else:
            # not started from a release directory (source checkout, or the
            # "current" link is unreachable): no version to claim
            tk.Label(frame, bg=bg, anchor="w", fg="#555", justify="left",
                     text="Running from %s" % config.BASE_DIR
                     ).pack(anchor="w", padx=10, pady=(0, 8))

        # Which fonts this machine actually resolved to. A named font that is
        # not installed is substituted silently, so two machines can look
        # different with no sign of why; this is where to look first.
        tk.Label(frame, bg=bg, anchor="w", fg="#777", font=config.ui_font(-1),
                 text="Fonts: %s" % config.font_report()
                 ).pack(anchor="w", padx=10, pady=(0, 8))
        return frame
