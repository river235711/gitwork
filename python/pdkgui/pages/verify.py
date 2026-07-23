#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pages/verify.py
---------------
DRC / ANT / WB / BUMP / DMDV / DPDO(DRC 類,跑法相同)共用的驗證流程頁面,
以及 LVS / XRC / JIVARO 的既有簡易版面。

DRC 類行為:
  - 下方 command file 文字框(右+下滾輪),初始讀 data/verify/<模組>.com。
  - 從文字框內容(略過開頭為 '//' 的行)解析:
        LAYOUT PATH "..."     -> realpath 後填入 LayoutPath 欄
        LAYOUT PRIMARY "..."  -> 填入 LayoutPrimary 欄
  - Run  : 於 RunFolder 建立 run 與 calibre_<DESIGN>_<模組小寫>.com,另開終端機執行 run。
  - Rve  : 把 run 覆寫成 `calibre -rve <results.db>`,另開終端機執行。
  - LoadDefault: 讀 ~/.pdkgui/.pdkgui.<模組小寫><DESIGN>.commandfile 進文字框。
  - Load / Save: 檔案選擇對話框(*.com 或 *)讀 / 寫文字框。
"""

import os
import re
import shutil
import subprocess

import tkinter as tk
from tkinter import filedialog, messagebox

from .base import BasePage
from widgets import ScrolledText
import config

# 跑法相同的 DRC 類模組(calibre -drc)
DRC_CLASS = ("DRC", "ANT", "WB", "BUMP", "DMDV", "DPDO")

_RE_LAYOUT_PATH = re.compile(r'LAYOUT\s+PATH\s+"([^"]+)"', re.IGNORECASE)
_RE_LAYOUT_PRIMARY = re.compile(r'LAYOUT\s+PRIMARY\s+"([^"]+)"', re.IGNORECASE)
_RE_RESULTS_DB = re.compile(r'RESULTS\s+DATABASE\s+"([^"]+)"', re.IGNORECASE)
_RE_SUMMARY_REP = re.compile(r'SUMMARY\s+REPORT\s+"([^"]+)"', re.IGNORECASE)

# 依序嘗試的終端機 / 檔案管理員 / 版圖檢視器
_TERMINALS = (
    ["xterm", "-e"], ["gnome-terminal", "--"], ["konsole", "-e"],
    ["xfce4-terminal", "-e"], ["mate-terminal", "-e"],
)
_FILE_MANAGERS = ("xdg-open", "nautilus", "thunar", "pcmanfm", "dolphin")
_VIEWERS = ("calibredrv", "klayout")


def _strip_comment_lines(text):
    """移除開頭為 '//' 的整行(其餘保留),回傳合併後的內容。"""
    kept = [ln for ln in text.splitlines() if not ln.lstrip().startswith("//")]
    return "\n".join(kept)


class VerifyPage(BasePage):
    def __init__(self, master, app, module_name):
        self.module = module_name
        super().__init__(master, app)

    def build(self):
        if self.module in DRC_CLASS:
            self._build_drc_class()
        else:
            self._build_generic()

    # ==================================================================
    # DRC 類版面
    # ==================================================================
    def _build_drc_class(self):
        tk.Label(self, text=config.DESIGN_NAME, bg=self.bg,
                 font=("Arial", 11)).grid(row=0, column=0, columnspan=4, pady=(0, 10))

        self.entries = {}

        tk.Label(self, text="LayoutPath", bg=self.bg).grid(row=1, column=0, sticky="w")
        ep = tk.Entry(self)
        ep.grid(row=1, column=1, sticky="we", padx=4)
        tk.Button(self, text="Open", command=lambda: self._browse_file(ep)).grid(row=1, column=2, padx=2)
        tk.Button(self, text="View", command=self._on_view).grid(row=1, column=3, padx=2)
        self.entries["LayoutPath"] = ep

        tk.Label(self, text="LayoutPrimary", bg=self.bg).grid(row=2, column=0, sticky="w")
        epr = tk.Entry(self)
        epr.grid(row=2, column=1, sticky="we", padx=4)
        self.entries["LayoutPrimary"] = epr

        tk.Label(self, text="RunFolder", bg=self.bg).grid(row=3, column=0, sticky="w")
        er = tk.Entry(self)
        er.grid(row=3, column=1, sticky="we", padx=4)
        tk.Button(self, text="Open", command=lambda: self._browse_dir(er)).grid(row=3, column=2, padx=2)
        tk.Button(self, text="FileManager", command=self._on_filemanager).grid(row=3, column=3, padx=2)
        self.entries["RunFolder"] = er

        self.grid_columnconfigure(1, weight=1)

        btn_frame = tk.Frame(self, bg=self.bg)
        btn_frame.grid(row=4, column=0, columnspan=4, pady=10)
        for text, cmd in (("Run", self._on_run), ("Rve", self._on_rve),
                          ("LoadDefault", self._on_load_default),
                          ("Load", self._on_load), ("Save", self._on_save)):
            tk.Button(btn_frame, text=text, width=12, command=cmd).pack(side="left", padx=4)

        self.cmd_text = ScrolledText(self, wrap="none")
        self.cmd_text.grid(row=5, column=0, columnspan=4, sticky="nsew", pady=(10, 0))
        self.grid_rowconfigure(5, weight=1)
        self.cmd_text.load_file(config.page_file(self.module))
        self.cmd_text.text.bind("<KeyRelease>", lambda e: self._sync_fields_from_text())
        self._sync_fields_from_text()

    # ------------------------------------------------------------------
    # 從文字框解析 LayoutPath / LayoutPrimary
    # ------------------------------------------------------------------
    def _sync_fields_from_text(self):
        body = _strip_comment_lines(self.cmd_text.get_text())
        m = _RE_LAYOUT_PATH.search(body)
        if m:
            self._set_entry("LayoutPath", os.path.realpath(m.group(1)))
        m = _RE_LAYOUT_PRIMARY.search(body)
        if m:
            self._set_entry("LayoutPrimary", m.group(1))

    def _set_entry(self, key, value):
        ent = self.entries.get(key)
        if ent is not None:
            ent.delete(0, tk.END)
            ent.insert(0, value)

    # ------------------------------------------------------------------
    # run / com 內容產生
    # ------------------------------------------------------------------
    def _calibre_env(self):
        return self.app.env.get("calibre") or "calibre/2024.1_36.20"

    def _com_filename(self):
        return "calibre_%s_%s.com" % (config.DESIGN_NAME, self.module.lower())

    def _report_name(self):
        m = _RE_SUMMARY_REP.search(_strip_comment_lines(self.cmd_text.get_text()))
        return m.group(1) if m else "%s.rep" % self.module

    def _results_db(self):
        m = _RE_RESULTS_DB.search(_strip_comment_lines(self.cmd_text.get_text()))
        return m.group(1) if m else "%s_RES.db" % self.module

    def _run_script_drc(self):
        tab = self.module.lower()
        return (
            "#!/bin/bash -l\n"
            "module load %s\n"
            "rm -rf %s.log %s\n"
            "calibre -64 -drc -hier -turbo -turbo_all %s | tee %s.log\n"
        ) % (self._calibre_env(), tab, self._report_name(), self._com_filename(), tab)

    def _run_script_rve(self):
        return (
            "#!/bin/bash -l\n"
            "module load %s\n"
            "calibre -rve %s\n"
        ) % (self._calibre_env(), self._results_db())

    # ------------------------------------------------------------------
    # 動作按鈕
    # ------------------------------------------------------------------
    def _prepare_folder(self):
        folder = self.entries["RunFolder"].get().strip()
        if not folder:
            messagebox.showerror("pdkgui", "請先填 RunFolder")
            return None
        folder = os.path.expanduser(folder)
        try:
            os.makedirs(folder, exist_ok=True)
        except OSError as e:
            messagebox.showerror("pdkgui", "建立 RunFolder 失敗:\n%s" % e)
            return None
        return folder

    def _write_run(self, folder, content):
        run_path = os.path.join(folder, "run")
        with open(run_path, "w", encoding="utf-8") as f:
            f.write(content)
        os.chmod(run_path, 0o755)
        return run_path

    def _on_run(self):
        folder = self._prepare_folder()
        if not folder:
            return
        try:
            com_path = os.path.join(folder, self._com_filename())
            with open(com_path, "w", encoding="utf-8") as f:
                f.write(self.cmd_text.get_text())
            self._write_run(folder, self._run_script_drc())
        except OSError as e:
            messagebox.showerror("pdkgui", "寫入檔案失敗:\n%s" % e)
            return
        self._launch_terminal(folder)

    def _on_rve(self):
        folder = self._prepare_folder()
        if not folder:
            return
        try:
            self._write_run(folder, self._run_script_rve())
        except OSError as e:
            messagebox.showerror("pdkgui", "寫入 run 失敗:\n%s" % e)
            return
        self._launch_terminal(folder)

    def _default_command_path(self):
        fname = ".pdkgui.%s%s.commandfile" % (self.module.lower(), config.DESIGN_NAME)
        return os.path.join(os.path.expanduser("~/.pdkgui"), fname)

    def _on_load_default(self):
        path = self._default_command_path()
        if os.path.isfile(path):
            self.cmd_text.load_file(path)
            self._sync_fields_from_text()
        else:
            messagebox.showwarning("pdkgui", "找不到預設檔:\n%s" % path)

    def _on_load(self):
        path = filedialog.askopenfilename(
            filetypes=[("Command file", "*.com"), ("All files", "*")])
        if path:
            self.cmd_text.load_file(path)
            self._sync_fields_from_text()

    def _on_save(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".com",
            filetypes=[("Command file", "*.com"), ("All files", "*")])
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(self.cmd_text.get_text())
            except OSError as e:
                messagebox.showerror("pdkgui", "儲存失敗:\n%s" % e)

    # ------------------------------------------------------------------
    # 外部程式:終端機 / 檢視器 / 檔案管理員
    # ------------------------------------------------------------------
    def _launch_terminal(self, folder):
        if not os.environ.get("DISPLAY"):
            messagebox.showerror("pdkgui", "沒有 DISPLAY,無法開啟終端機。\n請手動執行:\n%s/run" % folder)
            return
        wrapper = os.path.join(folder, ".pdkgui_run.sh")
        try:
            with open(wrapper, "w", encoding="utf-8") as f:
                f.write('#!/bin/bash -l\n'
                        'cd "$(dirname "$0")"\n'
                        './run\n'
                        'echo\n'
                        'echo "===== 執行結束,按 Enter 關閉 ====="\n'
                        'read\n')
            os.chmod(wrapper, 0o755)
        except OSError as e:
            messagebox.showerror("pdkgui", "建立執行包裝失敗:\n%s" % e)
            return
        for term in _TERMINALS:
            if shutil.which(term[0]):
                try:
                    subprocess.Popen(term + [wrapper])
                    return
                except Exception:
                    continue
        messagebox.showerror("pdkgui",
                             "找不到可用的終端機(xterm/gnome-terminal/...)。\n"
                             "請手動執行:\n%s/run" % folder)

    def _on_view(self):
        path = self.entries["LayoutPath"].get().strip()
        if not path:
            messagebox.showwarning("pdkgui", "LayoutPath 是空的")
            return
        for viewer in _VIEWERS:
            if shutil.which(viewer):
                try:
                    subprocess.Popen([viewer, path])
                    return
                except Exception:
                    continue
        messagebox.showinfo("pdkgui", "找不到 calibredrv / klayout 檢視器")

    def _on_filemanager(self):
        folder = self.entries["RunFolder"].get().strip()
        folder = os.path.expanduser(folder) if folder else "."
        for fm in _FILE_MANAGERS:
            if shutil.which(fm):
                try:
                    subprocess.Popen([fm, folder])
                    return
                except Exception:
                    continue
        messagebox.showinfo("pdkgui", "找不到檔案管理員")

    # ==================================================================
    # LVS / XRC / JIVARO 既有簡易版面
    # ==================================================================
    def _build_generic(self):
        tk.Label(self, text=config.DESIGN_NAME, bg=self.bg,
                 font=("Arial", 11)).grid(row=0, column=0, columnspan=4, pady=(0, 10))

        fields = [("LayoutPath", True), ("LayoutPrimary", False)]
        if self.module in ("LVS", "XRC"):
            fields += [("SourcePath", True), ("SourcePrimary", False), ("LvsHier", "check")]
        fields.append(("RunFolder", True))

        self.entries = {}
        row = 1
        for label, kind in fields:
            tk.Label(self, text=label, bg=self.bg).grid(row=row, column=0, sticky="w")
            if kind == "check":
                var = tk.BooleanVar()
                tk.Checkbutton(self, variable=var, bg=self.bg).grid(row=row, column=1, sticky="w")
                self.entries[label] = var
            else:
                ent = tk.Entry(self, width=90)
                ent.grid(row=row, column=1, columnspan=2, sticky="we", padx=4)
                self.entries[label] = ent
                if kind is True:
                    tk.Button(self, text="Open",
                              command=lambda e=ent: self._browse_file(e)).grid(row=row, column=3, padx=2)
            row += 1

        self.grid_columnconfigure(2, weight=1)

        btn_frame = tk.Frame(self, bg=self.bg)
        btn_frame.grid(row=row, column=0, columnspan=4, pady=10)
        for text in ("Run", "Rve", "LoadDefault", "Load", "Save"):
            tk.Button(btn_frame, text=text, width=12,
                      command=lambda t=text: self._on_generic_button(t)).pack(side="left", padx=4)
        row += 1

        self.cmd_text = ScrolledText(self, wrap="none")
        self.cmd_text.grid(row=row, column=0, columnspan=4, sticky="nsew", pady=(10, 0))
        self.grid_rowconfigure(row, weight=1)
        self.cmd_text.load_file(config.page_file(self.module))

    def _on_generic_button(self, action):
        if action == "LoadDefault":
            self.cmd_text.load_file(config.page_file(self.module))
        elif action == "Load":
            self._on_load()
        elif action == "Save":
            self._on_save()
        else:
            messagebox.showinfo("pdkgui",
                                "模組: %s\n動作: %s\n(尚未接後端)" % (self.module, action))

    # ------------------------------------------------------------------
    def _browse_file(self, entry_widget):
        path = filedialog.askopenfilename()
        if path:
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, path)

    def _browse_dir(self, entry_widget):
        path = filedialog.askdirectory()
        if path:
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, path)
