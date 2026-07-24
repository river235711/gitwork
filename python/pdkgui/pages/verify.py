#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pages/verify.py
---------------
Verification-flow pages:
  - DRC class (DRC/ANT/WB/BUMP/DMDV/DPDO): calibre -drc, same run flow.
  - LVS: calibre -lvs (LvsHier toggles -hier -turbo -turbo_all).
  - XRC: calibre -lvs/-xrc + jivaro (LvsHier as in LVS; XrcReduction gates the
    jivaro step).
  - JIVARO: reuses the existing simple layout.

Common:
  - Bottom command-file text box (right + bottom scrollbars); initially loads
    data/verify/<MODULE>.com.
  - Parses LAYOUT/SOURCE PATH (-> realpath) and PRIMARY from the text (ignoring
    lines starting with '//') into the fields.
  - Run: create RunFolder, write calibre_<DESIGN>_<module>.com and run, open a
    terminal to execute run.
  - Rve: rewrite run as calibre -rve <db>, open a terminal.
  - LoadDefault: load the central default command file.
  - Load/Save: *.com / * file dialogs.
"""

import os
import re
import json
import shutil
import subprocess

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from .base import BasePage
from widgets import ScrolledText
import config

DRC_CLASS = ("DRC", "ANT", "WB", "BUMP", "DMDV", "DPDO")

_RE_LAYOUT_PATH = re.compile(r'LAYOUT\s+PATH\s+"([^"]+)"', re.IGNORECASE)
_RE_LAYOUT_PRIMARY = re.compile(r'LAYOUT\s+PRIMARY\s+"([^"]+)"', re.IGNORECASE)
_RE_SOURCE_PATH = re.compile(r'SOURCE\s+PATH\s+"([^"]+)"', re.IGNORECASE)
_RE_SOURCE_PRIMARY = re.compile(r'SOURCE\s+PRIMARY\s+"([^"]+)"', re.IGNORECASE)
_RE_RESULTS_DB = re.compile(r'RESULTS\s+DATABASE\s+"([^"]+)"', re.IGNORECASE)
_RE_SUMMARY_REP = re.compile(r'SUMMARY\s+REPORT\s+"([^"]+)"', re.IGNORECASE)
_RE_INCLUDE = re.compile(r'^\s*include\b', re.IGNORECASE)   # calibre include directive

# Field <-> text mapping: which text line to update when a field changes
# (keyword, regex, realpath?)
_FIELD_KEYWORDS = {
    "LayoutPath": ("LAYOUT PATH", _RE_LAYOUT_PATH, True),
    "LayoutPrimary": ("LAYOUT PRIMARY", _RE_LAYOUT_PRIMARY, False),
    "SourcePath": ("SOURCE PATH", _RE_SOURCE_PATH, True),
    "SourcePrimary": ("SOURCE PRIMARY", _RE_SOURCE_PRIMARY, False),
}

_TERMINALS = (
    ["xterm", "-fg", "white", "-bg", "black", "-e"],
    ["gnome-terminal", "--"], ["konsole", "-e"],
    ["xfce4-terminal", "-e"], ["mate-terminal", "-e"],
)
_FILE_MANAGERS = ("xdg-open", "nautilus", "thunar", "pcmanfm", "dolphin")
_VIEWERS = ("calibredrv", "klayout")


def _strip_comment_lines(text):
    """Drop whole lines starting with '//', return the joined remainder."""
    return "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("//"))


class VerifyPage(BasePage):
    def __init__(self, master, app, module_name):
        self.module = module_name
        super().__init__(master, app)

    def build(self):
        self.entries = {}
        self._syncing = False      # prevent field<->text feedback loops
        self._save_job = None       # after() id for the debounced save
        if self.module == "LVS":
            self._build_lvs()
        elif self.module == "XRC":
            self._build_xrc()
        elif self.module in DRC_CLASS:
            self._build_drc_class()
        else:
            self._build_generic()

    # ==================================================================
    # Layout builder helpers
    # ==================================================================
    def _title(self):
        tk.Label(self, text=config.DESIGN_NAME, bg=self.bg,
                 font=("Arial", 11)).grid(row=0, column=0, columnspan=4, pady=(0, 10))

    def _entry_row(self, row, key, buttons=(), default=None):
        tk.Label(self, text=key, bg=self.bg).grid(row=row, column=0, sticky="w")
        e = tk.Entry(self)
        e.grid(row=row, column=1, sticky="we", padx=4)
        if default:
            e.insert(0, default)
        self.entries[key] = e
        col = 2
        for text, cmd in buttons:
            tk.Button(self, text=text, command=cmd).grid(row=row, column=col, padx=2)
            col += 1

    def _combo_row(self, row, key, values, default=None):
        tk.Label(self, text=key, bg=self.bg).grid(row=row, column=0, sticky="w")
        cb = ttk.Combobox(self, values=values, state="readonly")
        cb.set(default if default is not None else (values[0] if values else ""))
        cb.grid(row=row, column=1, sticky="we", padx=4)
        self.entries[key] = cb

    def _check_row(self, row, key, text=""):
        tk.Label(self, text=key, bg=self.bg).grid(row=row, column=0, sticky="w")
        var = tk.BooleanVar()
        tk.Checkbutton(self, variable=var, text=text, bg=self.bg,
                       command=self._schedule_save).grid(row=row, column=1, sticky="w")
        self.entries[key] = var

    def _open_btn(self, key):
        return ("Open", lambda: self._browse_file(self.entries[key]))

    def _opendir_btn(self, key):
        return ("Open", lambda: self._browse_dir(self.entries[key]))

    def _action_buttons(self, row):
        bf = tk.Frame(self, bg=self.bg)
        bf.grid(row=row, column=0, columnspan=4, pady=10)
        for text, cmd in (("Run", self._on_run), ("Rve", self._on_rve),
                          ("LoadDefault", self._on_load_default),
                          ("Load", self._on_load), ("Save", self._on_save)):
            tk.Button(bf, text=text, width=12, command=cmd).pack(side="left", padx=4)

    def _command_box(self, row):
        self.cmd_text = ScrolledText(self, wrap="none")
        self.cmd_text.grid(row=row, column=0, columnspan=4, sticky="nsew", pady=(10, 0))
        self.grid_rowconfigure(row, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self._finalize()

    def _finalize(self):
        # RunFolder default = the directory pdkgui was launched from
        rf = self.entries.get("RunFolder")
        if rf is not None and not rf.get().strip():
            rf.insert(0, self.app.launch_dir)

        # Read order: 1) last session  2) else the default (seeded from the
        # built-in template if needed)
        if not self._load_state():
            self._load_default()

        # On open: refresh the include line to the latest fab deck from central .inc
        self._refresh_include()

        self._bind_changes()

    def _central_deck_path(self):
        """First valid line of <CENTRAL>/<DESIGN>/<MODULE>.inc (latest deck path);
        None when absent."""
        for line in config.read_lines(config.central_include_file(self.module, config.DESIGN_NAME)):
            return line
        return None

    def _refresh_include(self):
        """Rewrite the command-text include line to the latest deck path from
        central .inc. If .inc is absent (no deck path), leave the command as-is."""
        deck = self._central_deck_path()
        if not deck:
            return
        new_line = "include %s" % deck
        lines = self.cmd_text.get_text().split("\n")
        replaced = False
        for i, ln in enumerate(lines):
            if ln.lstrip().startswith("//"):
                continue
            if _RE_INCLUDE.match(ln):
                if lines[i] != new_line:
                    lines[i] = new_line
                replaced = True
                break   # only the first (the fab deck usually has one include)
        if not replaced:
            if lines and lines[-1].strip() != "":
                lines.append("")
            lines.append(new_line)
        self._syncing = True
        try:
            self.cmd_text.set_text("\n".join(lines))
        finally:
            self._syncing = False

    def _bind_changes(self):
        # text change -> update the fields above + save
        self.cmd_text.text.bind("<KeyRelease>", lambda e: self._on_text_change())
        # field change -> push down to the text (Layout/Source) + save
        for key, w in self.entries.items():
            if isinstance(w, tk.BooleanVar):
                continue  # checkbutton already bound in _check_row
            if isinstance(w, ttk.Combobox):
                w.bind("<<ComboboxSelected>>", lambda e: self._schedule_save())
            else:
                w.bind("<KeyRelease>", lambda e, k=key: self._on_field_change(k))

    # ==================================================================
    # Per-family layouts
    # ==================================================================
    def _build_drc_class(self):
        self._title()
        r = 1
        self._entry_row(r, "LayoutPath",
                        [self._open_btn("LayoutPath"), ("View", self._on_view)]); r += 1
        self._entry_row(r, "LayoutPrimary"); r += 1
        self._entry_row(r, "RunFolder",
                        [self._opendir_btn("RunFolder"), ("FileManager", self._on_filemanager)]); r += 1
        self._action_buttons(r); r += 1
        self._command_box(r)

    def _build_lvs(self):
        self._title()
        r = 1
        self._entry_row(r, "LayoutPath",
                        [self._open_btn("LayoutPath"), ("View", self._on_view)]); r += 1
        self._entry_row(r, "LayoutPrimary"); r += 1
        self._entry_row(r, "SourcePath",
                        [self._open_btn("SourcePath"), ("Edit", self._on_edit_source)]); r += 1
        self._entry_row(r, "SourcePrimary"); r += 1
        self._check_row(r, "LvsHier"); r += 1
        self._entry_row(r, "RunFolder",
                        [self._opendir_btn("RunFolder"), ("FileManager", self._on_filemanager)]); r += 1
        self._action_buttons(r); r += 1
        self._command_box(r)

    def _build_xrc(self):
        self._title()
        r = 1
        self._entry_row(r, "LayoutPath",
                        [self._open_btn("LayoutPath"), ("View", self._on_view)]); r += 1
        self._entry_row(r, "LayoutPrimary"); r += 1
        self._entry_row(r, "SourcePath",
                        [self._open_btn("SourcePath"), ("Edit", self._on_edit_source)]); r += 1
        self._entry_row(r, "SourcePrimary"); r += 1
        self._check_row(r, "LvsHier"); r += 1
        self._combo_row(r, "XrcFormat", ["SPECTRE", "HSPICE", "ELDO", "CALIBREVIEW", "DSPF"], "SPECTRE"); r += 1
        self._combo_row(r, "XrcUseName", ["SOURCE", "LAYOUT"], "SOURCE"); r += 1
        self._entry_row(r, "XrcGround", default="GND"); r += 1
        self._combo_row(r, "XrcRCCorner", ["typical", "cbest", "cworst", "rcbest", "rcworst"], "typical"); r += 1
        self._combo_row(r, "XrcExtType", ["c", "rcc", "rccl"], "c"); r += 1
        self._check_row(r, "XrcReduction", "run"); r += 1
        self._entry_row(r, "RunFolder",
                        [self._opendir_btn("RunFolder"), ("FileManager", self._on_filemanager)]); r += 1
        self._action_buttons(r); r += 1
        self._command_box(r)

    # ==================================================================
    # Parse fields from the text (ignoring lines starting with '//')
    # ==================================================================
    def _sync_fields_from_text(self):
        if self._syncing:
            return
        self._syncing = True
        try:
            body = _strip_comment_lines(self.cmd_text.get_text())

            def fill(regex, key, real=False):
                w = self.entries.get(key)
                if w is None or not hasattr(w, "delete"):
                    return
                m = regex.search(body)
                if m:
                    val = os.path.realpath(m.group(1)) if real else m.group(1)
                    w.delete(0, tk.END)
                    w.insert(0, val)

            fill(_RE_LAYOUT_PATH, "LayoutPath", real=True)
            fill(_RE_LAYOUT_PRIMARY, "LayoutPrimary")
            fill(_RE_SOURCE_PATH, "SourcePath", real=True)
            fill(_RE_SOURCE_PRIMARY, "SourcePrimary")
        finally:
            self._syncing = False

    def _sync_text_from_field(self, key):
        """When a field changes, write its value back to the matching text line
        (ignoring '//' lines)."""
        if self._syncing or key not in _FIELD_KEYWORDS:
            return
        _kw, regex, real = _FIELD_KEYWORDS[key]
        val = self.entries[key].get()
        if real and val:
            val = os.path.realpath(val)

        lines = self.cmd_text.get_text().split("\n")
        changed = False
        for i, ln in enumerate(lines):
            if ln.lstrip().startswith("//"):
                continue
            if regex.search(ln):
                lines[i] = regex.sub(
                    lambda m: m.group(0)[:m.start(1) - m.start()] + val + '"', ln, count=1)
                changed = True
                break
        if changed:
            self._syncing = True
            try:
                pos = self.cmd_text.text.index("insert")
                self.cmd_text.set_text("\n".join(lines))
                try:
                    self.cmd_text.text.mark_set("insert", pos)
                except Exception:
                    pass
            finally:
                self._syncing = False

    def _on_field_change(self, key):
        self._sync_text_from_field(key)
        self._schedule_save()

    def _on_text_change(self):
        self._sync_fields_from_text()
        self._schedule_save()

    # ==================================================================
    # State save / restore (~/.pdkgui/session/<DESIGN>/<MODULE>.json)
    # ==================================================================
    def _state_path(self):
        return config.user_session_file(self.module, config.DESIGN_NAME)

    def _collect_state(self):
        st = {}
        for key, w in self.entries.items():
            st[key] = bool(w.get()) if isinstance(w, tk.BooleanVar) else w.get()
        st["__command__"] = self.cmd_text.get_text()
        return st

    def _apply_state(self, st):
        for key, w in self.entries.items():
            if key not in st:
                continue
            val = st[key]
            if isinstance(w, tk.BooleanVar):
                w.set(bool(val))
            elif isinstance(w, ttk.Combobox):
                w.set(val)
            elif hasattr(w, "delete"):
                w.delete(0, tk.END)
                w.insert(0, val)
        if "__command__" in st:
            self.cmd_text.set_text(st["__command__"])

    def _load_state(self):
        path = self._state_path()
        if not os.path.isfile(path):
            return False
        try:
            with open(path, encoding="utf-8") as f:
                st = json.load(f)
        except (OSError, ValueError):
            return False
        self._syncing = True
        try:
            self._apply_state(st)
        finally:
            self._syncing = False
        return True

    def _save_state(self):
        self._save_job = None
        path = self._state_path()
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._collect_state(), f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def _schedule_save(self):
        """Debounced save (avoids writing on every keystroke; NFS-home friendly)."""
        if self._save_job is not None:
            try:
                self.after_cancel(self._save_job)
            except Exception:
                pass
        self._save_job = self.after(500, self._save_state)

    def flush(self):
        """Save immediately before leaving the page / closing the window."""
        if self._save_job is not None:
            try:
                self.after_cancel(self._save_job)
            except Exception:
                pass
            self._save_job = None
        self._save_state()

    # ==================================================================
    # run / com content
    # ==================================================================
    def _calibre_env(self):
        return self.app.env.get("calibre") or "calibre/2024.1_36.20"

    def _jivaro_env(self):
        return self.app.env.get("jivaro") or "jivaro/2020"

    def _com_filename(self):
        return "calibre_%s_%s.com" % (config.DESIGN_NAME, self.module.lower())

    def _checked(self, key):
        w = self.entries.get(key)
        return bool(w.get()) if isinstance(w, tk.BooleanVar) else False

    def _text(self):
        return _strip_comment_lines(self.cmd_text.get_text())

    def _report_name(self):
        m = _RE_SUMMARY_REP.search(self._text())
        return m.group(1) if m else "%s.rep" % self.module

    def _results_db(self):
        m = _RE_RESULTS_DB.search(self._text())
        if m:
            return m.group(1)
        return "svdb" if self.module in ("LVS", "XRC") else "%s_RES.db" % self.module

    # --- DRC class ---
    def _run_script_drc(self):
        tab = self.module.lower()
        return (
            "#!/bin/bash -l\n"
            "module load %s\n"
            "rm -rf %s.log %s\n"
            "calibre -64 -drc -hier -turbo -turbo_all %s | tee %s.log\n"
        ) % (self._calibre_env(), tab, self._report_name(), self._com_filename(), tab)

    # --- LVS ---
    def _run_script_lvs(self):
        hier = "-hier -turbo -turbo_all " if self._checked("LvsHier") else ""
        tab = self.module.lower()
        return (
            "#!/bin/bash -l\n"
            "module load %s\n"
            "rm -rf %s.log %s.rep svdb/\n"
            "calibre -64 -lvs %s%s | tee %s.log\n"
        ) % (self._calibre_env(), tab, tab, hier, self._com_filename(), tab)

    # --- XRC ---
    def _run_script_xrc(self):
        hier = "-hier -turbo -turbo_all " if self._checked("LvsHier") else ""
        w = self.entries.get("XrcExtType")
        exttype = w.get() if w is not None else "c"
        primary = self.entries["LayoutPrimary"].get().strip() or "top"
        com = self._com_filename()
        d = config.XRC_HCELL_DIR
        script = (
            "#!/bin/bash -l\n"
            "module load %s\n"
            "module load %s\n"
            "\n"
            "rm -rf lvs.log pdb.log fmt.log %s.lump* svdb/\n"
            "if [ ! -e hcell ] && [ ! -L hcell ]; then ln -sf %s/hcell; fi\n"
            "if [ ! -e xcell ] && [ ! -L xcell ]; then ln -sf %s/xcell; fi\n"
            "calibre -64 -lvs %s-hcell hcell %s | tee lvs.log\n"
            "calibre -64 -xrc -pdb -turbo -turbo_all -xcell xcell -%s %s | tee pdb.log\n"
            "calibre -64 -xrc -fmt -xcell xcell -%s %s | tee fmt.log\n"
        ) % (self._calibre_env(), self._jivaro_env(), primary, d, d,
             hier, com, exttype, com, exttype, com)
        if self._checked("XrcReduction"):
            script += "jivaro -xml jivaro.xml\n"
        return script

    def _run_script(self):
        if self.module == "LVS":
            return self._run_script_lvs()
        if self.module == "XRC":
            return self._run_script_xrc()
        return self._run_script_drc()

    def _run_script_rve(self):
        return (
            "#!/bin/bash -l\n"
            "module load %s\n"
            "calibre -rve %s\n"
        ) % (self._calibre_env(), self._results_db())

    # ==================================================================
    # Action buttons
    # ==================================================================
    def _prepare_folder(self):
        folder = self.entries["RunFolder"].get().strip()
        if not folder:
            messagebox.showerror("pdkgui", "Please fill in RunFolder first")
            return None
        folder = os.path.expanduser(folder)
        try:
            os.makedirs(folder, exist_ok=True)
        except OSError as e:
            messagebox.showerror("pdkgui", "Failed to create RunFolder:\n%s" % e)
            return None
        return folder

    def _write_run(self, folder, content):
        run_path = os.path.join(folder, "run")
        with open(run_path, "w", encoding="utf-8") as f:
            f.write(content)
        os.chmod(run_path, 0o755)

    def _on_run(self):
        folder = self._prepare_folder()
        if not folder:
            return
        self._refresh_include()   # before Run, ensure include = latest central deck
        try:
            com_path = os.path.join(folder, self._com_filename())
            with open(com_path, "w", encoding="utf-8") as f:
                f.write(self.cmd_text.get_text())
            self._write_run(folder, self._run_script())
        except OSError as e:
            messagebox.showerror("pdkgui", "Failed to write files:\n%s" % e)
            return
        self._launch_terminal(folder)

    def _on_rve(self):
        folder = self._prepare_folder()
        if not folder:
            return
        try:
            self._write_run(folder, self._run_script_rve())
        except OSError as e:
            messagebox.showerror("pdkgui", "Failed to write run:\n%s" % e)
            return
        self._launch_terminal(folder)

    def _load_default(self):
        """Load the command file from the central default dir; fall back to the
        built-in template if not found."""
        path = config.central_default_file(self.module, config.DESIGN_NAME)
        if os.path.isfile(path):
            self.cmd_text.load_file(path)
        else:
            self.cmd_text.load_file(config.page_file(self.module))
        self._sync_fields_from_text()

    def _on_load_default(self):
        self._load_default()
        self._schedule_save()

    def _on_load(self):
        path = filedialog.askopenfilename(
            filetypes=[("Command file", "*.com"), ("All files", "*")])
        if path:
            self.cmd_text.load_file(path)
            self._sync_fields_from_text()
            self._schedule_save()

    def _on_save(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".com",
            filetypes=[("Command file", "*.com"), ("All files", "*")])
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(self.cmd_text.get_text())
            except OSError as e:
                messagebox.showerror("pdkgui", "Save failed:\n%s" % e)

    # ==================================================================
    # External programs
    # ==================================================================
    def _launch_terminal(self, folder):
        if not os.environ.get("DISPLAY"):
            messagebox.showerror("pdkgui", "No DISPLAY, cannot open a terminal.\n"
                                           "Run it manually:\n%s/run" % folder)
            return
        wrapper = os.path.join(folder, ".pdkgui_run.sh")
        try:
            with open(wrapper, "w", encoding="utf-8") as f:
                f.write('#!/bin/bash -l\n'
                        # set terminal foreground white / background black (OSC 10/11)
                        "printf '\\033]10;white\\007\\033]11;black\\007'\n"
                        'cd "$(dirname "$0")"\n'
                        './run\n'
                        'echo\n'
                        'echo "===== Done. Press Enter to close ====="\n'
                        'read\n')
            os.chmod(wrapper, 0o755)
        except OSError as e:
            messagebox.showerror("pdkgui", "Failed to create run wrapper:\n%s" % e)
            return
        for term in _TERMINALS:
            if shutil.which(term[0]):
                try:
                    subprocess.Popen(term + [wrapper])
                    return
                except Exception:
                    continue
        messagebox.showerror("pdkgui",
                             "No usable terminal found. Run it manually:\n%s/run" % folder)

    def _on_view(self):
        path = self.entries["LayoutPath"].get().strip()
        if not path:
            messagebox.showwarning("pdkgui", "LayoutPath is empty")
            return
        self._spawn(_VIEWERS, path, "calibredrv / klayout viewer not found")

    def _on_edit_source(self):
        path = self.entries["SourcePath"].get().strip()
        if not path:
            messagebox.showwarning("pdkgui", "SourcePath is empty")
            return
        editor = self.app.env.get("editor") or "gvim"
        self._spawn([editor], path, "editor not found: %s" % editor)

    def _on_filemanager(self):
        folder = self.entries["RunFolder"].get().strip()
        folder = os.path.expanduser(folder) if folder else "."
        self._spawn(_FILE_MANAGERS, folder, "no file manager found")

    def _spawn(self, candidates, arg, not_found_msg):
        for prog in candidates:
            if shutil.which(prog):
                try:
                    subprocess.Popen([prog, arg])
                    return
                except Exception:
                    continue
        messagebox.showinfo("pdkgui", not_found_msg)

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

    # ==================================================================
    # JIVARO etc.: existing simple layout
    # ==================================================================
    def _build_generic(self):
        self._title()
        fields = [("LayoutPath", True), ("LayoutPrimary", False), ("RunFolder", True)]
        row = 1
        for label, has_open in fields:
            tk.Label(self, text=label, bg=self.bg).grid(row=row, column=0, sticky="w")
            ent = tk.Entry(self, width=90)
            ent.grid(row=row, column=1, columnspan=2, sticky="we", padx=4)
            self.entries[label] = ent
            if has_open:
                tk.Button(self, text="Open",
                          command=lambda e=ent: self._browse_file(e)).grid(row=row, column=3, padx=2)
            row += 1
        self.grid_columnconfigure(1, weight=1)
        self._action_buttons(row); row += 1
        self._command_box(row)
