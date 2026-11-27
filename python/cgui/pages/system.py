#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pages/system.py
---------------
SYSTEM page:

  top     the revision history, read from config.page_file("SYSTEM"), which
          prefers the central shared copy <DEFAULT_COM_DIR>/system.txt
          (design-independent, so every user sees the same history) and falls
          back to the built-in data/system.txt. Read-only, both scrollbars.

  middle  offline Ed25519 license details (customer, domain, expiry, features,
          license file path, and warning/grace status).

  bottom  which release this window runs and which one is current. When they
          differ (an admin repointed the "current" symlink after this window
          opened) a Restart button reopens cgui on the current release.
"""

import tkinter as tk

from .base import BasePage
from widgets import ScrolledText, button_kwargs
import cgui_license
import config


def license_summary(res):
    """Return (bg, fg, status_text, details) matching the cgui license card."""
    T = config.THEME
    if res.status == cgui_license.STATUS_OK:
        bg, fg = T["card"], T["success"]
        status_text = "VALID (%d day(s) remaining)" % (res.days_left or 0)
    elif res.status == cgui_license.STATUS_EXPIRING:
        bg, fg = T["warn_bg"], T["warn_fg"]
        status_text = "EXPIRING SOON (%d day(s) remaining)" % (res.days_left or 0)
    elif res.status == cgui_license.STATUS_GRACE:
        bg, fg = T["grace_bg"], T["grace_fg"]
        status_text = "GRACE PERIOD (%d grace day(s) left)" % (res.grace_left or 0)
    else:
        bg, fg = T["error_bg"], T["error_fg"]
        status_text = res.status.upper()

    details = (
        "Customer     : %s\n"
        "Domain       : %s\n"
        "Expire Date  : %s\n"
        "Features     : %s\n"
        "License File : %s"
        % (
            res.customer or "-",
            res.domain or "-",
            res.expire_date or "-",
            ", ".join(res.features) if res.features else "-",
            res.license_path or "-",
        )
    )
    return bg, fg, status_text, details


class SystemPage(BasePage):
    module = "SYSTEM"

    def build(self):
        T = config.THEME
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=0)
        self.grid_columnconfigure(0, weight=1)

        st = ScrolledText(
            self, wrap="none", readonly=True,
            bg=T["card"], fg=T["text"], font=config.mono_font(),
        )
        st.grid(row=0, column=0, sticky="nsew")
        st.load_file(config.page_file(self.module))

        self._lic_panel = self._build_license_panel()
        self._lic_panel.grid(row=1, column=0, sticky="nsew", pady=(10, 0))

        self._panel = self._build_version_panel()
        self._panel.grid(row=2, column=0, sticky="nsew", pady=(10, 0))

    def on_show(self):
        """Re-check license and current release whenever SYSTEM is opened."""
        self._lic_panel.destroy()
        self._lic_panel = self._build_license_panel()
        self._lic_panel.grid(row=1, column=0, sticky="nsew", pady=(10, 0))

        self._panel.destroy()
        self._panel = self._build_version_panel()
        self._panel.grid(row=2, column=0, sticky="nsew", pady=(10, 0))

    # ------------------------------------------------------------------
    def _build_license_panel(self):
        T = config.THEME
        res = getattr(self.app, "license_result", None)
        if res is None:
            res = cgui_license.check_license(update_state=False)

        bg, fg, status_text, details = license_summary(res)

        frame = tk.Frame(
            self, bg=bg, bd=0,
            highlightthickness=1, highlightbackground=T["border"],
        )
        tk.Label(frame, text="cgui license", bg=bg, fg=T["text"], anchor="w",
                 font=config.ui_font(0, "bold")).pack(anchor="w", padx=12, pady=(10, 2))
        tk.Label(frame, text=status_text, bg=bg, fg=fg, anchor="w",
                 font=config.ui_font(0, "bold")).pack(anchor="w", padx=12)
        tk.Label(frame, text=details, bg=bg, fg=T["text_muted"], anchor="w", justify="left",
                 font=config.mono_font(-1)).pack(anchor="w", padx=12, pady=(4, 10))
        return frame

    # ------------------------------------------------------------------
    def _build_version_panel(self):
        T = config.THEME
        update = config.pending_update()
        outdated = update is not None
        bg = T["warn_bg"] if outdated else T["card"]

        frame = tk.Frame(
            self, bg=bg, bd=0,
            highlightthickness=1, highlightbackground=T["border"],
        )
        tk.Label(frame, text="cgui version", bg=bg, fg=T["text"], anchor="w",
                 font=config.ui_font(0, "bold")).pack(anchor="w", padx=12, pady=(10, 2))

        if outdated:
            running, live, _dir = update
            tk.Label(frame, bg=bg, fg=T["text"], justify="left", anchor="w",
                     text="This window is running %s.\n"
                          "The current release is now %s." % (running, live)
                     ).pack(anchor="w", padx=12)
            tk.Label(frame, bg=bg, justify="left", anchor="w", fg=T["warn_fg"],
                     text="Restarting saves your work and reopens on this tab."
                     ).pack(anchor="w", padx=12, pady=(4, 0))
            tk.Button(frame, text="Restart now", width=14, pady=4,
                      command=self.app.restart,
                      **button_kwargs("primary")).pack(anchor="w", padx=12, pady=8)
        elif config.running_release():
            tk.Label(frame, bg=bg, anchor="w", fg=T["success"], font=config.ui_font(1),
                     text=config.running_release()
                     ).pack(anchor="w", padx=12)
            tk.Label(frame, bg=bg, anchor="w", fg=T["text_muted"],
                     text="This is the current release."
                     ).pack(anchor="w", padx=12, pady=(2, 10))
        else:
            tk.Label(frame, bg=bg, anchor="w", fg=T["text_muted"], justify="left",
                     text="Running from %s" % config.APP_DIR
                     ).pack(anchor="w", padx=12, pady=(0, 10))

        return frame
