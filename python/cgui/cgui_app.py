#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cgui_app.py
-----------
Main program logic for cgui (Synopsys-style Home & multi-tab DRC workspace,
top tab strip + menu bar + offline Ed25519 license status/grace checks).
"""

import os
import shutil
import subprocess
import sys
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, font as tkfont, messagebox, ttk

import cgui_license
import config
from pages import build_page
from widgets import apply_theme

_LIC_CHECK_INTERVAL_MS = 3600 * 1000   # hourly runtime re-check


class CGui(tk.Tk):
    """The Cadsemi cgui window.

    In normal mode, opens with a top tab bar (`+` to open a new `Home` launcher
    tab, right-aligned `cadsemi` brand mark), a menu bar below it, and always
    starts on a `Home` tab matching Synopsys Custom Compiler.

    `only` names a single module to show on its own without chrome
    (`cgui -l` -> only="LOADING", the machine chooser). Such a window neither
    reads nor writes working-session state."""

    def __init__(self, only=None, license_result=None):
        super().__init__()
        self.only = only
        self.license_result = (
            license_result or cgui_license.check_license(update_state=False)
        )

        # Inherit caller's terminal environment directly (no hardcoded module load)
        self.env = {}
        self._apply_fonts()
        apply_theme(self)
        # Working directory cgui was launched from (default for verify RunFolder)
        self.launch_dir = os.getcwd()
        self._page = None
        self._pages = {}               # module -> latest built page
        self._menu_buttons = {}        # legacy attr (empty without sidebar)
        self._tabs = []
        self._active_tab_id = None
        self._tab_seq = 0
        self._drc_counter = 0
        self._gds_counter = 0
        self._tabbar = None
        self._tab_strip = None
        self._tab_strip_w = 0
        self._last_tab_width = 0
        self._add_tab_btn = None
        self._brand_label = None
        self._menubar = None
        self._menus = {}
        self._file_menu = None
        self._recent_menu = None
        self._window_menu = None
        self._font_var = tk.IntVar(value=config.UI_FONT_PX)
        self._editor_var = tk.StringVar(value="gvim")
        self._fullscreen_var = tk.BooleanVar(value=False)
        self._saved_license_file = ""
        self._update_ack = False       # "run anyway" chosen on the Run prompt
        self._lic_job = None
        self._lic_bar = None
        self._lic_label = None
        self._lic_bar_packed = False
        self._about_win = None
        self._notices_win = None
        self.current_module = tk.StringVar(value=only or "HOME")

        with config.timed("build window"):
            if only:
                self._build_single(only)
            else:
                self._build_full()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        if self.license_result.status == cgui_license.STATUS_GRACE:
            self.after(200, self._show_grace_popup)
        self._lic_job = self.after(_LIC_CHECK_INTERVAL_MS,
                                   self._periodic_license_check)
        self._report_startup()

    def _build_full(self):
        # Convert legacy ~/.cgui/.pdkgui.<tab><design>.{commandfile,gui} if present
        config.migrate_legacy_user_files()
        self._load_ui_prefs()

        self.title(config.window_title())
        self.geometry(config.window_geometry())
        self.configure(bg=config.THEME["bg"])

        self._build_license_bar()
        self._build_tabbar()
        self._build_menubar()
        self._build_content_area()

        self.bind("<Control-t>", lambda _e: self.new_home_tab())
        self.bind("<Control-n>", lambda _e: self._new_window())
        self.bind("<Control-w>", lambda _e: self._close_current_tab())
        self.bind("<Control-q>", lambda _e: self._on_close())
        self.bind("<F11>", lambda _e: self._toggle_fullscreen(toggle=True))
        self.bind("<F1>", lambda _e: self.open_user_guide())

        # Always start on a fresh Home tab (never restore old DRC tabs on startup)
        self.new_home_tab()
        self.after_idle(self._warm_up)

    def _build_single(self, module):
        """One page, no menu/tabs: the window is that page."""
        self.title(config.window_title(subject=module.lower()))
        self.configure(bg=config.THEME["bg"])
        self._build_license_bar()
        self._build_content_area()
        self.content.configure(bg=config.THEME["bg"])
        self.show_module(module)

    def _build_license_bar(self):
        """Dock bottom license status bar before sidebar/content."""
        T = config.THEME
        self._lic_bar = tk.Frame(self, bd=0, highlightthickness=0)
        tk.Frame(self._lic_bar, bg=T["border"], height=1).pack(side="top", fill="x")
        self._lic_label = tk.Label(self._lic_bar, anchor="w", padx=12, pady=5)
        self._lic_label.pack(side="left", fill="x", expand=True)
        self._update_license_bar(self.license_result)

    def _update_license_bar(self, res):
        if self._lic_bar is None or self._lic_label is None:
            return
        T = config.THEME
        if res.status == cgui_license.STATUS_EXPIRING:
            bg, fg = T["warn_bg"], T["warn_fg"]
            font = config.ui_font(-1, "bold")
            text = res.notice
            show = True
        elif res.status == cgui_license.STATUS_GRACE:
            bg, fg = T["grace_bg"], T["grace_fg"]
            font = config.ui_font(-1, "bold")
            text = res.notice
            show = True
        elif res.status == cgui_license.STATUS_OK:
            bg, fg = T["bg_alt"], T["text_muted"]
            font = config.ui_font(-1)
            text = "License: %s  |  Expires: %s (%d day(s) left)" % (
                res.customer or "-", res.expire_date, res.days_left or 0
            )
            show = False
        else:
            bg, fg = T["error_bg"], T["error_fg"]
            font = config.ui_font(-1, "bold")
            text = res.message.splitlines()[0] if res.message else "License invalid"
            show = True

        self._lic_bar.configure(bg=bg)
        self._lic_label.configure(bg=bg, fg=fg, font=font, text=text)
        if show and not self._lic_bar_packed:
            self._lic_bar.pack(side="bottom", fill="x")
            self._lic_bar_packed = True
        elif not show and self._lic_bar_packed:
            self._lic_bar.pack_forget()
            self._lic_bar_packed = False

    def _show_grace_popup(self):
        res = self.license_result
        if res and res.status == cgui_license.STATUS_GRACE:
            messagebox.showwarning("cgui - License Grace Period", res.notice)

    def _periodic_license_check(self):
        self._lic_job = None
        res = cgui_license.check_license()
        self.license_result = res
        self._update_license_bar(res)
        if not res.allowed:
            messagebox.showerror("cgui - License Error", res.message)
            return
        self._lic_job = self.after(_LIC_CHECK_INTERVAL_MS,
                                   self._periodic_license_check)

    def ensure_license(self, action="perform this action"):
        """Re-check license before key operations. Returns False when blocked."""
        res = cgui_license.check_license()
        self.license_result = res
        self._update_license_bar(res)
        if not res.allowed:
            messagebox.showerror(
                "cgui - License Error",
                "Cannot %s:\n\n%s" % (action, res.message),
            )
            return False
        return True

    def _warm_up(self):
        with config.timed("warm up verify module"):
            try:
                import pages.verify        # noqa: F401
            except Exception:
                pass

    @staticmethod
    def _report_startup():
        """Total from process start, when the bootstrap passed its own T0 on."""
        started = os.environ.pop("CGUI_START", None)
        if started and config.TIMING:
            import time
            sys.stderr.write("[cgui] %-34s %6.1f ms\n"
                             % ("=> window ready, total",
                                (time.time() - float(started)) * 1000))

    def _apply_fonts(self):
        """Resize Tk's named fonts so one setting (config.UI_FONT_PX) scales the UI."""
        family, size = config.ui_font()
        for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont",
                     "TkIconFont", "TkSmallCaptionFont", "TkTooltipFont"):
            try:
                tkfont.nametofont(name).configure(family=family, size=size)
            except tk.TclError:
                pass
        try:
            mono_family, mono_size = config.mono_font()
            tkfont.nametofont("TkFixedFont").configure(family=mono_family,
                                                       size=mono_size)
        except tk.TclError:
            pass
        try:
            ttk.Style().configure(".", font=config.ui_font())
        except tk.TclError:
            pass
        self.option_add("*TCombobox*Listbox.font", config.ui_font())

    def _load_ui_prefs(self):
        """Load persisted UI preferences (font_px, editor, license_file); never restores tabs."""
        prefs = config.load_json(config.user_global_file("UI"))
        if not isinstance(prefs, dict):
            return
        font_px = prefs.get("font_px")
        if isinstance(font_px, int) and 10 <= font_px <= 24 and font_px != config.UI_FONT_PX:
            config.UI_FONT_PX = font_px
            self._apply_fonts()
        self._font_var.set(config.UI_FONT_PX)
        editor = prefs.get("editor")
        if isinstance(editor, str) and editor.strip():
            self.env["editor"] = editor.strip()
        self._editor_var.set(self.env.get("editor", "gvim"))
        saved_lic = prefs.get("license_file")
        if isinstance(saved_lic, str) and saved_lic.strip():
            self._saved_license_file = saved_lic.strip()

    def set_design(self, name):
        """Switch the current design: update the window title so other tabs follow."""
        if name == config.DESIGN_NAME:
            return
        config.DESIGN_NAME = name
        self.title(config.window_title())
        self._drop_cached_pages(keep="PROCESS")

    # ------------------------------------------------------------------
    # Top tab bar (Home + DRC tabs + "+" button + right "cadsemi" mark)
    # ------------------------------------------------------------------
    def _build_tabbar(self):
        T = config.THEME
        self._tabbar = tk.Frame(self, bg=T["bg_alt"])
        self._tabbar.pack(side="top", fill="x")

        bar_row = tk.Frame(self._tabbar, bg=T["bg_alt"])
        bar_row.pack(side="top", fill="x")

        brand_box = tk.Frame(bar_row, bg=T["bg_alt"])
        brand_box.pack(side="right", fill="y", padx=(8, 14), pady=4)
        tk.Frame(brand_box, bg=T["accent"], width=6, height=6).pack(
            side="left", padx=(0, 6)
        )
        self._brand_label = tk.Label(
            brand_box, text=config.LOGO_TEXT, bg=T["bg_alt"], fg=T["text"],
            font=config.ui_font(3, "bold"),
        )
        self._brand_label.pack(side="left")

        self._tab_strip = tk.Frame(bar_row, bg=T["bg_alt"])
        self._tab_strip.pack(side="left", fill="both", expand=True, padx=(8, 4), pady=(5, 0))
        self._tab_strip.bind("<Configure>", self._on_tabbar_resize)

        tk.Frame(self._tabbar, bg=T["border"], height=1).pack(side="bottom", fill="x")

    def _on_tabbar_resize(self, event):
        if event.width > 20 and abs(event.width - self._tab_strip_w) >= 4:
            self._tab_strip_w = event.width
            self._render_tabs()

    @staticmethod
    def _compute_tab_width(strip_w, count):
        """Return (tab_w, gap, overflow) so tabs shrink and '+' stays visible."""
        if strip_w <= 1:
            strip_w = max(320, int(config.WINDOW_W * config.UI_FONT_PX / config.UI_FONT_BASE_PX) - 140)
        count = max(1, count)
        add_btn_w = 34
        avail = max(80, strip_w - add_btn_w - 6)
        gap = 2 if count > 8 else 3
        max_w, min_w = 136, 26
        raw = (avail - gap * count) // count
        tab_w = min(max_w, max(min_w, raw))
        overflow = (count * (tab_w + gap) > avail)
        return tab_w, gap, overflow

    def _render_tabs(self):
        if self._tab_strip is None:
            return
        T = config.THEME
        for child in self._tab_strip.winfo_children():
            child.destroy()

        strip_w = self._tab_strip.winfo_width()
        tab_w, gap, overflow = self._compute_tab_width(strip_w, len(self._tabs))
        self._last_tab_width = tab_w
        tab_h = max(28, config.UI_FONT_PX + 15)

        self._add_tab_btn = tk.Button(
            self._tab_strip, text="+", relief="flat", bd=0,
            highlightthickness=1, highlightbackground=T["border"],
            bg=T["card"], fg=T["text"],
            activebackground=T["hover"], activeforeground=T["accent"],
            font=config.ui_font(0, "bold"), padx=9, pady=3, cursor="hand2",
            command=self.new_home_tab,
        )
        # Pack '+' FIRST on the right when overflowing so left tabs never push it out
        if overflow:
            self._add_tab_btn.pack(side="right", padx=(4, 0), pady=(0, 1))

        for tab in self._tabs:
            active = (tab["id"] == self._active_tab_id)
            tab_bg = T["bg"] if active else T["bg_alt"]
            tab_fg = T["text"] if active else T["text_muted"]
            top_accent = T["accent"] if active else tab_bg

            box = tk.Frame(
                self._tab_strip, width=tab_w, height=tab_h, bg=tab_bg, bd=0,
                highlightthickness=1, highlightbackground=T["border"],
                cursor="hand2",
            )
            box.pack_propagate(False)
            box.pack(side="left", padx=(0, gap))
            tk.Frame(box, bg=top_accent, height=2).pack(side="top", fill="x")

            inner = tk.Frame(box, bg=tab_bg, cursor="hand2")
            inner.pack(side="top", fill="both", expand=True)

            tid = tab["id"]
            if tab["closable"]:
                close_btn = tk.Button(
                    inner, text="\u00d7", relief="flat", bd=0, highlightthickness=0,
                    bg=tab_bg, fg=T["text_muted"],
                    activebackground=T["error_bg"], activeforeground=T["error"],
                    font=config.ui_font(-1),
                    padx=4 if tab_w >= 44 else 2, pady=3, cursor="hand2",
                    command=lambda t=tid: self.close_tab(t),
                )
                close_btn.pack(side="right", fill="y")

            if tab_w >= 42:
                if tab["module"] == "HOME":
                    label_text = "\u2302 " + tab["title"] if tab_w >= 86 else "\u2302"
                elif tab_w >= 64:
                    label_text = tab["title"]
                else:
                    label_text = tab["title"][:4]
                btn = tk.Button(
                    inner, text=label_text, relief="flat", bd=0, highlightthickness=0,
                    bg=tab_bg, fg=tab_fg,
                    activebackground=T["hover"], activeforeground=T["text"],
                    font=config.ui_font(-1, "bold") if active else config.ui_font(-1),
                    anchor="w" if tab_w >= 72 else "center",
                    padx=6 if tab_w >= 72 else 2, pady=3, cursor="hand2",
                    command=lambda t=tid: self._select_tab(t),
                )
                btn.pack(side="left", fill="both", expand=True)
            else:
                box.bind("<Button-1>", lambda _e, t=tid: self._select_tab(t))
                inner.bind("<Button-1>", lambda _e, t=tid: self._select_tab(t))

        if not overflow:
            self._add_tab_btn.pack(side="left", padx=(2, 0), pady=(0, 1))

    # ------------------------------------------------------------------
    # Menu bar (File / Tools / License / Options / Window / Help)
    # ------------------------------------------------------------------
    def _build_menubar(self):
        T = config.THEME
        self._menubar = tk.Frame(self, bg=T["card"])
        self._menubar.pack(side="top", fill="x")
        bar_row = tk.Frame(self._menubar, bg=T["card"])
        bar_row.pack(side="top", fill="x", padx=6, pady=2)
        tk.Frame(self._menubar, bg=T["border"], height=1).pack(side="bottom", fill="x")

        menu_kw = dict(
            tearoff=0, bg=T["card"], fg=T["text"],
            activebackground=T["selection"], activeforeground=T["text"],
            disabledforeground=T["divider"], relief="flat", bd=1,
            font=config.ui_font(-1),
        )
        mb_kw = dict(
            bg=T["card"], fg=T["text"],
            activebackground=T["hover"], activeforeground=T["text"],
            relief="flat", bd=0, highlightthickness=0,
            padx=9, pady=3, font=config.ui_font(-1),
        )

        self._menus = {}

        def _make_menu(label, **extra):
            mb = tk.Menubutton(bar_row, text=label, **mb_kw)
            m = tk.Menu(mb, **menu_kw, **extra)
            mb.configure(menu=m)
            mb.pack(side="left", padx=1)
            self._menus[label] = mb
            return m

        self._file_menu = _make_menu("File", postcommand=self._rebuild_file_menu)
        self._recent_menu = tk.Menu(
            self._file_menu, **menu_kw, postcommand=self._rebuild_recent_menu
        )
        self._rebuild_file_menu()

        m_tools = _make_menu("Tools")
        m_tools.add_command(label="DRC Verification", command=self.new_drc_tab)
        m_tools.add_command(label="GDS Viewer", command=self.new_gdsviewer_tab)
        m_tools.add_command(label="LVS (Custom on request)", state="disabled")
        m_tools.add_command(label="XRC (Custom on request)", state="disabled")
        m_tools.add_separator()
        m_tools.add_command(label="Terminal", command=self._open_terminal)

        m_opt = _make_menu("Options")
        m_font = tk.Menu(m_opt, **menu_kw)
        for px in (13, 15, 17, 19):
            m_font.add_radiobutton(
                label="%d px" % px, variable=self._font_var, value=px,
                command=lambda v=px: self._set_font_px(v),
            )
        m_opt.add_cascade(label="Font Size", menu=m_font)

        m_ed = tk.Menu(m_opt, **menu_kw)
        for ed in ("gvim", "gedit"):
            m_ed.add_radiobutton(
                label=ed, variable=self._editor_var, value=ed,
                command=lambda v=ed: self._set_editor(v),
            )
        m_opt.add_cascade(label="Editor", menu=m_ed)

        self._window_menu = _make_menu("Window", postcommand=self._rebuild_window_menu)
        self._rebuild_window_menu()

        m_lic = _make_menu("License")
        m_lic.add_command(label="License Info...", command=self._show_license_info)
        m_lic.add_command(label="Select License File...", command=self._select_license_file)
        m_lic.add_command(label="Reload License", command=self._reload_license)

        m_help = _make_menu("Help")
        m_help.add_command(label="CGUI Help", accelerator="F1",
                           command=self.open_user_guide)
        m_help.add_command(label="About CGUI", command=self._show_about)

    def _rebuild_recent_menu(self):
        m = self._recent_menu
        if m is None:
            return
        m.delete(0, tk.END)
        items = config.load_recent_runs(max_items=8)
        if not items:
            m.add_command(label="(No recent runs)", state="disabled")
            return
        for item in items:
            state = item.get("state") or {}
            layout = os.path.basename(item.get("layout_path", "")) or item.get("label", "DRC")
            folder = item.get("run_folder", "").strip() or "."
            m.add_command(
                label="%s  \u2014  %s" % (layout, folder),
                command=lambda st=state, lbl=layout: self.new_drc_tab(
                    initial_state=st, title=lbl, replace_home=True
                ),
            )
        m.add_separator()
        m.add_command(label="Clear Recent Runs", command=self._clear_recent_runs)

    def _clear_recent_runs(self):
        config.save_json(config.user_global_file("RECENT_RUNS"), [])
        self._rebuild_recent_menu()

    def _rebuild_file_menu(self):
        m = self._file_menu
        if m is None:
            return
        m.delete(0, tk.END)
        if self._page is not None and hasattr(self._page, "_on_load"):
            m.add_command(label="Open Cmd...", command=self._menu_load_cmd)
            m.add_command(label="Save Cmd...", command=self._menu_save_cmd)
            m.add_separator()
        if self._recent_menu is not None:
            self._rebuild_recent_menu()
            m.add_cascade(label="Recent Runs", menu=self._recent_menu)
            m.add_separator()
        m.add_command(label="Close Current Tab", accelerator="Ctrl+W",
                      command=self._close_current_tab)
        m.add_separator()
        m.add_command(label="Quit", accelerator="Ctrl+Q", command=self._on_close)

    def _rebuild_window_menu(self):
        m = self._window_menu
        if m is None:
            return
        m.delete(0, tk.END)
        m.add_command(label="New Window", accelerator="Ctrl+N",
                      command=self._new_window)
        m.add_command(label="New Tab", accelerator="Ctrl+T",
                      command=self.new_home_tab)
        m.add_checkbutton(label="Full Screen", accelerator="F11",
                          variable=self._fullscreen_var,
                          command=self._toggle_fullscreen)
        m.add_separator()
        m.add_command(label="Keyboard Shortcuts...", command=self._show_shortcuts)
        if self._tabs:
            m.add_separator()
        for i, tab in enumerate(self._tabs, 1):
            prefix = "\u2022 " if tab["id"] == self._active_tab_id else "   "
            m.add_command(
                label="%s%d %s" % (prefix, i, tab["title"]),
                command=lambda tid=tab["id"]: self._select_tab(tid),
            )
        if len(self._tabs) > 1:
            m.add_separator()
            m.add_command(label="Next Tab", command=lambda: self._cycle_tab(1))
            m.add_command(label="Previous Tab", command=lambda: self._cycle_tab(-1))
            m.add_command(label="Close All DRC Tabs", command=self._close_all_drc_tabs)

    # ------------------------------------------------------------------
    # Tab management & content area
    # ------------------------------------------------------------------
    def _build_content_area(self):
        self.content = tk.Frame(self, bg=config.THEME["bg"])
        self.content.pack(side="top", fill="both", expand=True)

    def _add_tab(self, title, module, page, closable=True):
        self._tab_seq += 1
        tid = "tab_%d" % self._tab_seq
        self._tabs.append({
            "id": tid,
            "title": title,
            "module": module,
            "page": page,
            "closable": closable,
        })
        return tid

    def _find_tab(self, tab_id):
        for i, tab in enumerate(self._tabs):
            if tab["id"] == tab_id:
                return i, tab
        return None, None

    def _select_tab(self, tab_id):
        _, tab = self._find_tab(tab_id)
        if tab is None:
            return
        self._flush_page()
        if self._page is not None:
            self._page.pack_forget()

        self._active_tab_id = tab_id
        self.current_module.set(tab["module"])
        self._page = tab["page"]
        self._pages[tab["module"]] = tab["page"]
        tab["page"].pack(fill="both", expand=True, padx=18, pady=12)
        with config.timed("show %s" % tab["title"]):
            tab["page"].on_show()
        self._render_tabs()

    def new_home_tab(self):
        """Open a fresh closable Home launcher tab and activate it."""
        page = build_page("HOME", self.content, self)
        tid = self._add_tab("Home", "HOME", page, closable=True)
        self._select_tab(tid)
        return tid

    def _replace_active_home_tab(self, title, module, page):
        """If the active tab is Home, convert it in-place into (title, module, page)."""
        if not self._active_tab_id:
            return None
        _, active_tab = self._find_tab(self._active_tab_id)
        if active_tab is None or active_tab["module"] != "HOME":
            return None
        old_page = active_tab["page"]
        if self._page is old_page:
            self._page = None
        try:
            old_page.pack_forget()
            old_page.destroy()
        except Exception:
            pass
        active_tab["title"] = title
        active_tab["module"] = module
        active_tab["page"] = page
        active_tab["closable"] = True
        remaining_homes = [t["page"] for t in self._tabs if t["module"] == "HOME"]
        if remaining_homes:
            self._pages["HOME"] = remaining_homes[-1]
        else:
            self._pages.pop("HOME", None)
        return active_tab["id"]

    def _open_module_tab(self, tab_title, module, page, replace_home=False):
        tid = self._replace_active_home_tab(tab_title, module, page) if replace_home else None
        if tid is None:
            tid = self._add_tab(tab_title, module, page, closable=True)
        self._select_tab(tid)
        return tid

    def new_drc_tab(self, initial_state=None, title=None, replace_home=False):
        """Open a fresh independent DRC workspace tab and activate it."""
        self._drc_counter += 1
        tab_title = title or ("DRC %d" % self._drc_counter)
        page = build_page("DRC", self.content, self,
                          initial_state=initial_state, persist_session=False)
        return self._open_module_tab(tab_title, "DRC", page, replace_home=replace_home)

    def new_gdsviewer_tab(self, title=None, replace_home=False):
        """Open a fresh GdsViewer (KLayout) workspace tab and activate it."""
        self._gds_counter += 1
        tab_title = title or ("GdsViewer %d" % self._gds_counter)
        page = build_page("GDSVIEWER", self.content, self)
        return self._open_module_tab(tab_title, "GDSVIEWER", page, replace_home=replace_home)

    def open_system_tab(self, replace_home=False):
        """Activate existing System tab or open a closable System tab."""
        for tab in self._tabs:
            if tab["module"] == "SYSTEM":
                self._select_tab(tab["id"])
                return tab["id"]
        page = build_page("SYSTEM", self.content, self)
        tid = self._replace_active_home_tab("System", "SYSTEM", page) if replace_home else None
        if tid is None:
            tid = self._add_tab("System", "SYSTEM", page, closable=True)
        self._select_tab(tid)
        return tid

    @staticmethod
    def user_guide_path():
        """Return the absolute path to the offline HTML CGUI User Guide."""
        return os.path.abspath(os.path.join(config.DATA_DIR, "help", "index.html"))

    def open_user_guide(self):
        """Open the offline HTML CGUI User Guide in the user's web browser."""
        path = self.user_guide_path()
        if not os.path.isfile(path):
            messagebox.showerror("CGUI Help", "User Guide file not found:\n%s" % path)
            return
        url = Path(path).as_uri()
        base_env = config.desktop_env()
        forced = os.environ.get("CGUI_BROWSER", "").strip()
        candidates = (forced,) if forced else (
            "google-chrome", "chromium", "chromium-browser", "xdg-open", "firefox",
        )
        for cmd in candidates:
            exe = shutil.which(cmd)
            if not exe:
                continue
            cmd_env = dict(base_env)
            if "firefox" in os.path.basename(exe).lower():
                # Avoid GPU/EGL/sandbox crashes on CentOS 7 X11/VNC & NFS homes
                cmd_env.setdefault("MOZ_WEBRENDER", "0")
                cmd_env.setdefault("MOZ_ACCELERATED", "0")
                cmd_env.setdefault("MOZ_X11_EGL", "0")
                cmd_env.setdefault("MOZ_DISABLE_CONTENT_SANDBOX", "1")
                cmd_env.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")
            try:
                subprocess.Popen(
                    [exe, url],
                    env=cmd_env,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                    close_fds=True,
                )
                return url
            except Exception:
                continue
        if not webbrowser.open(url):
            messagebox.showerror(
                "CGUI Help",
                "Could not launch a web browser.\nOpen manually:\n%s" % path,
            )
            return None
        return url

    def close_tab(self, tab_id):
        """Close a tab; opens a fresh Home tab if the last tab is closed."""
        idx, tab = self._find_tab(tab_id)
        if tab is None or not tab["closable"]:
            return False
        page = tab["page"]
        if hasattr(page, "flush"):
            try:
                page.flush()
            except Exception:
                pass
        was_active = (tab_id == self._active_tab_id)
        self._tabs.pop(idx)
        try:
            page.pack_forget()
            page.destroy()
        except Exception:
            pass

        # Refresh self._pages pointer for that module
        remaining = [t["page"] for t in self._tabs if t["module"] == tab["module"]]
        if remaining:
            self._pages[tab["module"]] = remaining[-1]
        else:
            self._pages.pop(tab["module"], None)

        if not self._tabs:
            self._page = None
            self._active_tab_id = None
            self.new_home_tab()
            return True

        if was_active:
            self._page = None
            target = self._tabs[min(idx, len(self._tabs) - 1)]
            self._select_tab(target["id"])
        else:
            self._render_tabs()
        return True

    def _close_current_tab(self):
        if self._active_tab_id:
            self.close_tab(self._active_tab_id)

    def _close_all_drc_tabs(self):
        for tid in [t["id"] for t in self._tabs if t["module"] == "DRC" and t["closable"]]:
            self.close_tab(tid)

    def _cycle_tab(self, step):
        if len(self._tabs) <= 1 or not self._active_tab_id:
            return
        idx, _ = self._find_tab(self._active_tab_id)
        if idx is not None:
            nxt = self._tabs[(idx + step) % len(self._tabs)]
            self._select_tab(nxt["id"])

    def record_recent_run(self, state):
        """Record a DRC run on disk for File -> Recent Runs."""
        if not isinstance(state, dict):
            return
        layout = state.get("LayoutPath", "")
        folder = state.get("RunFolder", "")
        label = os.path.basename(layout) or state.get("LayoutPrimary", "") or "DRC"
        config.record_recent_run(label, layout, folder, state, max_items=8)

    def _menu_load_cmd(self):
        page = self._page
        if page is None or not hasattr(page, "_on_load"):
            self.new_drc_tab()
            page = self._page
        if page is not None and hasattr(page, "_on_load"):
            page._on_load()

    def _menu_save_cmd(self):
        page = self._page
        if page is not None and hasattr(page, "_on_save"):
            page._on_save()
        else:
            messagebox.showinfo("cgui", "Open a DRC tab first to save a command file.")

    def _apply_license_result(self, res):
        self.license_result = res
        self._update_license_bar(res)
        sys_page = self._pages.get("SYSTEM")
        if sys_page is not None:
            try:
                sys_page.on_show()
            except Exception:
                pass

    def _show_license_info(self):
        from pages.system import license_summary
        res = self.license_result or cgui_license.check_license(update_state=False)
        _, _, status_text, details = license_summary(res)
        messagebox.showinfo(
            "License Info",
            "cgui license\n%s\n\n%s" % (status_text, details),
        )

    def _reload_license(self):
        res = cgui_license.check_license(update_state=False)
        self._apply_license_result(res)
        if res.allowed:
            messagebox.showinfo("cgui - License", cgui_license.format_license_info(res))
        else:
            messagebox.showerror("cgui - License Error", res.message)

    def _select_license_file(self):
        path = filedialog.askopenfilename(
            title="Select License File",
            filetypes=[("License files", "*.lic"), ("All files", "*")],
        )
        if not path:
            return
        res = cgui_license.check_license(license_file=path, update_state=False)
        if not res.allowed:
            messagebox.showerror("cgui - License Error", res.message)
            return
        os.environ[cgui_license.LICENSE_ENV_VAR] = path
        self._saved_license_file = path
        self._save_ui_state()
        self._apply_license_result(res)
        messagebox.showinfo("cgui - License", cgui_license.format_license_info(res))

    def _open_terminal(self):
        if not os.environ.get("DISPLAY"):
            messagebox.showerror("cgui", "No DISPLAY, cannot open a terminal.")
            return
        folder = self.launch_dir
        page = self._page
        if page is not None and hasattr(page, "entries"):
            rf = page.entries.get("RunFolder")
            if rf is not None:
                cand = os.path.expanduser(rf.get().strip())
                if cand and os.path.isdir(cand):
                    folder = cand
        shell = os.environ.get("SHELL") or "/bin/bash"
        for term in config.terminals():
            if shutil.which(term[0]):
                try:
                    subprocess.Popen(term + [shell], cwd=folder)
                    return
                except Exception:
                    continue
        messagebox.showerror("cgui", "No usable terminal found.")

    def _new_window(self):
        launcher = config.live_launcher()
        if launcher:
            cmd = [launcher]
        elif "__compiled__" in globals() or getattr(sys, "frozen", False):
            cmd = [sys.executable]
        else:
            cmd = [sys.executable, os.path.abspath(sys.argv[0])]
        try:
            subprocess.Popen(cmd, start_new_session=True, close_fds=True)
        except Exception as e:
            messagebox.showerror("cgui", "Could not open new window:\n%s" % e)

    def _toggle_fullscreen(self, toggle=False):
        if toggle:
            self._fullscreen_var.set(not self._fullscreen_var.get())
        try:
            self.attributes("-fullscreen", bool(self._fullscreen_var.get()))
        except tk.TclError:
            pass

    def _show_shortcuts(self):
        messagebox.showinfo(
            "Keyboard Shortcuts",
            "Ctrl+T   New Home Tab\n"
            "Ctrl+N   New Window\n"
            "Ctrl+W   Close Current Tab\n"
            "Ctrl+Q   Quit\n"
            "F11      Toggle Full Screen\n"
            "F1       CGUI Help",
        )

    def _set_font_px(self, px):
        config.UI_FONT_PX = px
        self._font_var.set(px)
        config.clear_font_cache()
        self._apply_fonts()
        self._save_ui_state()
        self._render_tabs()

    def _set_editor(self, editor):
        self.env["editor"] = editor
        self._editor_var.set(editor)
        self._save_ui_state()

    def _show_about(self):
        if self._about_win is not None:
            try:
                if self._about_win.winfo_exists():
                    self._about_win.lift()
                    self._about_win.focus_force()
                    return
            except tk.TclError:
                self._about_win = None

        T = config.THEME
        win = tk.Toplevel(self)
        self._about_win = win
        win.title("About CGUI")
        win.configure(bg=T["bg"])
        win.resizable(False, False)
        if self.winfo_viewable():
            try:
                win.transient(self)
            except tk.TclError:
                pass

        def _close(_e=None):
            self._about_win = None
            try:
                win.destroy()
            except tk.TclError:
                pass

        win.protocol("WM_DELETE_WINDOW", _close)
        win.bind("<Escape>", _close)

        # Dark editorial hero banner with geometric IC layout pattern
        banner_bg = "#1b1a18"
        banner_w, banner_h = 520, 290
        cv = tk.Canvas(
            win, width=banner_w, height=banner_h,
            bg=banner_bg, bd=0, highlightthickness=0,
        )
        cv.pack(side="top", fill="x")

        # Subtle background layout routing lines & array blocks
        grid_fg = "#2d2a26"
        track_fg = "#5c3624"
        accent = T["accent"]
        for x in range(40, banner_w, 64):
            cv.create_line(x, 0, x, banner_h, fill="#23211f", width=1)
        for y in range(36, banner_h, 48):
            cv.create_line(0, y, banner_w, y, fill="#23211f", width=1)
        # Decorative metal routing tracks & vias on the right half
        for bx in (260, 294, 328, 362, 396, 430, 464):
            cv.create_rectangle(bx, 118, bx + 20, 138, outline=track_fg, fill="#281d17", width=1)
            cv.create_rectangle(bx + 5, 123, bx + 15, 133, outline=accent, fill="", width=1)
        cv.create_line(245, 102, 495, 102, fill=track_fg, width=2)
        cv.create_line(245, 154, 495, 154, fill=track_fg, width=2)
        for bx in (280, 320, 360, 400, 440):
            cv.create_rectangle(bx, 174, bx + 26, 212, outline=grid_fg, fill="#211f1c", width=1)
            cv.create_line(bx + 13, 154, bx + 13, 174, fill=grid_fg, width=1)

        # Large product title & company block
        cv.create_text(
            banner_w // 2, 54, text="CGUI", fill="#fefdfb",
            font=("DejaVu Sans", 30, "bold"), anchor="center",
        )
        cv.create_rectangle(24, 108, 36, 120, fill=accent, outline="")
        cv.create_text(
            44, 114, text="cadsemi", fill="#fefdfb",
            font=("DejaVu Sans", 16, "bold"), anchor="w",
        )
        cv.create_text(
            24, 144,
            text="Cadsemi Co.\nhttps://cadsemi.com\nSupport: %s" % cgui_license.SUPPORT_EMAIL,
            fill="#d6d1c6", font=config.ui_font(-1), anchor="nw", justify="left",
        )

        # Copyright & proprietary block inside dark footer area of banner
        cv.create_line(20, 218, banner_w - 20, 218, fill="#38342e", width=1)
        cv.create_text(
            24, 228,
            text=(
                "Copyright (c) 2026 Cadsemi. All rights reserved.\n"
                "This software and associated documentation are proprietary to Cadsemi and\n"
                "may only be used in accordance with a written license agreement."
            ),
            fill="#b5afa4", font=config.ui_font(-2), anchor="nw", justify="left",
        )

        # Bottom action strip (Version left, Notices + OK right)
        tk.Frame(win, bg=T["border"], height=1).pack(fill="x")
        foot = tk.Frame(win, bg=T["bg_alt"], padx=14, pady=10)
        foot.pack(fill="x")

        ver_box = tk.Frame(foot, bg=T["bg_alt"])
        ver_box.pack(side="left")
        tk.Label(
            ver_box, text="Version", bg=T["bg_alt"], fg=T["text_muted"],
            font=config.ui_font(-2), anchor="w",
        ).pack(anchor="w")
        tk.Label(
            ver_box, text=config.latest_revision(), bg=T["bg_alt"], fg=T["text"],
            font=config.ui_font(-1, "bold"), anchor="w",
        ).pack(anchor="w")

        btn_kw = dict(
            bg=T["card"], fg=T["text"], activebackground=T["hover"],
            activeforeground=T["text"], relief="flat", bd=0,
            highlightthickness=1, highlightbackground=T["input_border"],
            padx=14, pady=5, font=config.ui_font(-1), width=8,
        )
        ok_btn = tk.Button(foot, text="OK", command=_close, **btn_kw)
        ok_btn.pack(side="right")
        notices_btn = tk.Button(
            foot, text="Notices",
            command=lambda: self._show_legal_notices(parent=win), **btn_kw,
        )
        notices_btn.pack(side="right", padx=(0, 8))

        win._notices_btn = notices_btn
        win._ok_btn = ok_btn
        win.update_idletasks()
        return win

    def _show_legal_notices(self, parent=None):
        if self._notices_win is not None:
            try:
                if self._notices_win.winfo_exists():
                    self._notices_win.lift()
                    self._notices_win.focus_force()
                    return self._notices_win
            except tk.TclError:
                self._notices_win = None

        T = config.THEME
        master = parent if (parent is not None and parent.winfo_exists()) else self
        win = tk.Toplevel(master)
        self._notices_win = win
        win.title("Legal Notices")
        win.configure(bg=T["bg"])
        win.geometry("560x360")
        win.minsize(420, 260)
        if master.winfo_viewable():
            try:
                win.transient(master)
            except tk.TclError:
                pass

        def _close(_e=None):
            self._notices_win = None
            try:
                win.destroy()
            except tk.TclError:
                pass

        win.protocol("WM_DELETE_WINDOW", _close)
        win.bind("<Escape>", _close)

        body = tk.Frame(win, bg=T["bg"], padx=14, pady=12)
        body.pack(fill="both", expand=True)

        box = tk.Frame(
            body, bg=T["card"], bd=0,
            highlightthickness=1, highlightbackground=T["border"],
        )
        box.pack(fill="both", expand=True)

        scroll = tk.Scrollbar(box)
        scroll.pack(side="right", fill="y")

        txt = tk.Text(
            box, wrap="word", bg=T["card"], fg=T["text"],
            font=config.ui_font(-1), relief="flat", bd=0,
            padx=12, pady=10, yscrollcommand=scroll.set,
        )
        txt.pack(side="left", fill="both", expand=True)
        scroll.configure(command=txt.yview)

        notices_text = (
            "Third-Party Trademarks & Compatibility Notice\n\n"
            "\"Calibre\" is a registered trademark of Siemens Industry Software Inc. "
            "(Siemens EDA) and may be registered in certain jurisdictions. Cadsemi CGUI "
            "is an independent EDA workflow interface and is not affiliated with, "
            "sponsored by, or endorsed by Siemens EDA. Command-line EDA engines are "
            "invoked only from the user's own licensed environment.\n\n"
            "\"KLayout\" is an open-source layout viewer licensed under the GNU General "
            "Public License (GPL v2 or later / GPL v3; https://www.klayout.de). Cadsemi "
            "CGUI does not redistribute modified KLayout binaries and invokes an external "
            "KLayout executable present in the user's environment.\n\n"
            "Free and Open Source Software Notices\n\n"
            "CGUI includes or relies on open-source runtime components including Python "
            "(PSF License), Tcl/Tk (Tcl/Tk License), Ed25519 signature verification "
            "routines, and Nuitka (Apache License 2.0).\n\n"
            "Trademark & Support Inquiries\n\n"
            "For licensing, customization services, or legal inquiries, contact "
            "%s or visit https://cadsemi.com."
            % cgui_license.SUPPORT_EMAIL
        )
        txt.insert("1.0", notices_text)
        txt.configure(state="disabled")

        foot = tk.Frame(win, bg=T["bg_alt"], padx=14, pady=9)
        foot.pack(side="bottom", fill="x")
        tk.Frame(win, bg=T["border"], height=1).pack(side="bottom", fill="x")

        ok_btn = tk.Button(
            foot, text="OK", command=_close,
            bg=T["card"], fg=T["text"], activebackground=T["hover"],
            activeforeground=T["text"], relief="flat", bd=0,
            highlightthickness=1, highlightbackground=T["input_border"],
            padx=16, pady=4, font=config.ui_font(-1), width=8,
        )
        ok_btn.pack(side="right")

        win._text = txt
        win._ok_btn = ok_btn
        win.update_idletasks()
        return win

    def show_module(self, name):
        """Show a tab by module name (used by -l single mode and shortcuts)."""
        if self.only:
            self.current_module.set(name)
            self._flush_page()
            if self._page is not None:
                self._page.pack_forget()
            page = self._pages.get(name)
            if page is None:
                page = self._pages[name] = build_page(name, self.content, self)
            self._page = page
            page.pack(fill="both", expand=True, padx=18, pady=14)
            with config.timed("show %s" % name):
                page.on_show()
            return

        if name == "HOME":
            for tab in self._tabs:
                if tab["module"] == "HOME":
                    self._select_tab(tab["id"])
                    return
            self.new_home_tab()
        elif name == "SYSTEM":
            self.open_system_tab()
        elif name == "DRC":
            for tab in self._tabs:
                if tab["module"] == "DRC":
                    self._select_tab(tab["id"])
                    return
            self.new_drc_tab()

    def _drop_cached_pages(self, keep=None):
        """Forget the built pages (they were built for one design), except `keep`."""
        for name in [n for n in self._pages if n != keep]:
            page = self._pages.pop(name)
            try:
                page.destroy()
            except Exception:
                pass
        if keep not in self._pages:
            self._page = None

    def _flush_page(self):
        page = getattr(self, "_page", None)
        if page is not None and hasattr(page, "flush"):
            try:
                page.flush()
            except Exception:
                pass

    def _save_ui_state(self):
        """Persist Options preferences (font_px, editor, license_file); startup lands on Home."""
        if self.only:
            return
        prefs = {
            "font_px": config.UI_FONT_PX,
            "editor": self.env.get("editor", "gvim"),
        }
        if self._saved_license_file:
            prefs["license_file"] = self._saved_license_file
        config.save_json(config.user_global_file("UI"), prefs)

    def _on_close(self):
        if self._lic_job is not None:
            try:
                self.after_cancel(self._lic_job)
            except Exception:
                pass
            self._lic_job = None
        self._flush_page()
        self._save_ui_state()
        self.destroy()

    # ------------------------------------------------------------------
    # Deployed-version check
    # ------------------------------------------------------------------
    def confirm_if_outdated(self):
        """Called before a Run. False means the caller must not proceed."""
        update = config.pending_update()
        if not update or self._update_ack:
            return True
        running, live, _dir = update
        if messagebox.askyesno(
                "cgui",
                "This window is running cgui %s, but %s is now the current "
                "release.\n\nRun with the version you have?\n\n"
                "Yes  -- run now with %s\n"
                "No   -- restart into %s first"
                % (running, live, running, live)):
            self._update_ack = True
            return True
        self.restart()
        return False

    def restart(self):
        """Save everything, start the app again from the entry point, and exit."""
        launcher = config.live_launcher()
        if not launcher:
            messagebox.showerror("cgui", "The current release could not be found;\n"
                                         "close cgui and start it again manually.")
            return
        self._flush_page()
        self._save_ui_state()
        try:
            subprocess.Popen([launcher], start_new_session=True, close_fds=True)
        except Exception as e:
            messagebox.showerror(
                "cgui", "Could not restart from:\n%s\n\n%s\n\n"
                        "Close cgui and start it again manually." % (launcher, e))
            return
        self.destroy()


USAGE = """usage: cgui [-l | -e <engineer-mode options> | -L]

  -l, --loading   open the machine chooser only: the LOADING page on its own,
                  to see which machine is free and start cgui there
  -e, --engineer  engineer mode: the command-line tools, run in this terminal
                  instead of opening a window. `cgui -e -h` lists them.
  -L, --license   print license status and details, then exit
  -h, --help      this message

With no options the full window opens on the tab it was last left on.
"""


def parse_argv(argv):
    """(only, message, status): which module/action to run, or message to print."""
    if not argv:
        return None, None, 0
    if len(argv) == 1:
        if argv[0] in ("-l", "--loading"):
            return "LOADING", None, 0
        if argv[0] in ("-L", "--license", "--license-info"):
            return "__LICENSE__", None, 0
        if argv[0] in ("-h", "--help"):
            return None, USAGE, 0
    return None, "cgui: unknown option %s\n\n%s" % (" ".join(argv), USAGE), 2


def _show_gui_license_error(message):
    if not os.environ.get("DISPLAY"):
        return
    try:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("cgui - License Error", message)
        root.destroy()
    except tk.TclError:
        pass


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)

    # Engineer mode is a terminal program, not a window.
    if argv and argv[0] in ("-e", "--engineer"):
        import cgui_eng
        if not any(a in ("-h", "--help") for a in argv[1:]):
            res = cgui_license.check_license()
            if not res.allowed:
                sys.stderr.write("cgui: %s\n" % res.message)
                return 3
            if res.notice:
                sys.stderr.write(cgui_license.format_terminal_notice(res) + "\n")
        return cgui_eng.main(argv[1:])

    only, message, status = parse_argv(argv)
    if message:
        (sys.stderr if status else sys.stdout).write(message)
        return status

    if only == "__LICENSE__":
        res = cgui_license.check_license(update_state=False)
        sys.stdout.write(cgui_license.format_license_info(res) + "\n")
        if res.notice:
            sys.stderr.write(cgui_license.format_terminal_notice(res) + "\n")
        elif not res.allowed and res.message:
            sys.stderr.write(res.message + "\n")
        return 0 if res.allowed else 3

    res = cgui_license.check_license()
    if not res.allowed:
        sys.stderr.write("cgui: %s\n" % res.message)
        _show_gui_license_error(res.message)
        return 3
    if res.notice:
        sys.stderr.write(cgui_license.format_terminal_notice(res) + "\n")

    CGui(only=only, license_result=res).mainloop()
    return 0
