#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pdkgui.py
---------
一個仿照內部 EDA 流程管理工具 (pdkgui) 的 Tkinter GUI 骨架。

左側為模組選單 (PROCESS / ENV / DRC / ANT / WB / BUMP / DMDV / DPDO /
LVS / XRC / JIVARO / SKIPPER / KLAYOUT / DOC / SYSTEM),
右側依照選擇的模組顯示對應的內容頁面。

=== 關於 Logo（圖一、圖二右下角 "Sirius Wireless" 那張圖）===
這張圖只是單純的「公司/團隊 Logo 展示區」，跟程式邏輯完全無關，
所以已經抽成一個獨立的設定與函式，你只要把 LOGO_PATH 改成自己的
圖片路徑（png/gif/jpg 皆可，若要吃 jpg 需安裝 Pillow），
或是把 LOGO_TEXT 改成你想顯示的文字即可完成替換，
不需要動到其他任何程式邏輯。

Python 3.6+ 皆可執行；若環境是舊版 Python (如截圖中的 3.6.3)，
建議搭配下面兩行避免中文輸出出現 UnicodeEncodeError：
    export LANG=en_US.UTF-8
    export LC_ALL=en_US.UTF-8
"""

import os
import sys
import io
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# 若系統的 stdout 不是 UTF-8（例如舊版 Python 在 locale=C 的環境下），
# 這裡做一個保險，避免 print 中文字時發生 UnicodeEncodeError。
try:
    if sys.stdout.encoding is None or "utf" not in sys.stdout.encoding.lower():
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
except Exception:
    pass

# --------------------------------------------------------------------------
# 可自行替換的設定區
# --------------------------------------------------------------------------
DESIGN_NAME = "t22_1p7m_4x1z1u"     # 視窗標題會顯示 "pdkgui - <DESIGN_NAME>"

# --- Logo 設定：把這裡換成你自己的圖檔路徑即可 ---
LOGO_PATH = "./company_logo.png"    # 例如 "./logo/sirius_wireless.png"
LOGO_TEXT = "YOUR COMPANY LOGO"     # 找不到圖檔時，退回顯示的文字
LOGO_BG = "#0b5fa5"                 # 找不到圖檔時，背景色（可自行調整）
LOGO_FG = "white"

# 左側選單項目（依照截圖順序）
MENU_ITEMS = [
    "PROCESS", "ENV", "DRC", "ANT", "WB", "BUMP", "DMDV", "DPDO",
    "LVS", "XRC", "JIVARO", "SKIPPER", "KLAYOUT", "DOC", "SYSTEM",
]

# 需要用「Verification 頁面樣板」(LayoutPath/RunFolder/Run.../command box)
# 呈現的模組
VERIFY_MODULES = ["DRC", "ANT", "WB", "BUMP", "DMDV", "DPDO", "LVS", "XRC", "JIVARO"]


# --------------------------------------------------------------------------
# Logo 元件：獨立成一個 class，方便日後整個抽換或改成其他呈現方式
# --------------------------------------------------------------------------
class LogoPanel(tk.Frame):
    """右下角公司 Logo 展示區（圖一、圖二中的 'Sirius Wireless' 區塊）。"""

    def __init__(self, master, path=LOGO_PATH, text=LOGO_TEXT, **kwargs):
        super().__init__(master, bg=LOGO_BG, **kwargs)
        self._photo = None  # 保留參照，避免被 GC 回收
        self._build(path, text)

    def _build(self, path, text):
        img_label = None
        if path and os.path.isfile(path):
            try:
                # 優先用內建 tk.PhotoImage（支援 png/gif），
                # 若圖檔是 jpg 且環境有安裝 Pillow，會自動改用 Pillow 開啟。
                try:
                    self._photo = tk.PhotoImage(file=path)
                except tk.TclError:
                    from PIL import Image, ImageTk  # 需要 pip install pillow
                    pil_img = Image.open(path)
                    self._photo = ImageTk.PhotoImage(pil_img)
                img_label = tk.Label(self, image=self._photo, bg=LOGO_BG)
            except Exception as e:
                print("Logo 圖片載入失敗，改用文字顯示: %s" % e)

        if img_label is not None:
            img_label.pack(expand=True, fill="both")
        else:
            # 找不到圖檔或載入失敗時，退回用文字當作 Logo 佔位
            tk.Label(
                self, text=text, bg=LOGO_BG, fg=LOGO_FG,
                font=("Arial", 16, "bold")
            ).pack(expand=True, fill="both")


# --------------------------------------------------------------------------
# 主視窗
# --------------------------------------------------------------------------
class PdkGui(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("pdkgui - %s" % DESIGN_NAME)
        self.geometry("980x560")
        self.configure(bg="#d9d9d9")

        self.current_module = tk.StringVar(value="PROCESS")

        self._build_sidebar()
        self._build_content_area()
        self.show_module("PROCESS")

    # ------------------------------------------------------------------
    # 左側選單
    # ------------------------------------------------------------------
    def _build_sidebar(self):
        sidebar = tk.Frame(self, bg="#d9d9d9", width=190)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        self._menu_buttons = {}
        for name in MENU_ITEMS:
            btn = tk.Button(
                sidebar, text=name, relief="raised", bd=1,
                bg="#bcdff0", activebackground="#9fcfe8",
                font=("Arial", 9),
                command=lambda n=name: self.show_module(n),
            )
            btn.pack(fill="x", padx=2, pady=1)
            self._menu_buttons[name] = btn

    def _highlight_selected(self, name):
        for n, btn in self._menu_buttons.items():
            btn.configure(bg="#e0e0e0" if n == name else "#bcdff0")

    # ------------------------------------------------------------------
    # 右側內容區（依模組切換）
    # ------------------------------------------------------------------
    def _build_content_area(self):
        self.content = tk.Frame(self, bg="#d9d9d9")
        self.content.pack(side="left", fill="both", expand=True)

    def show_module(self, name):
        self.current_module.set(name)
        self._highlight_selected(name)
        for w in self.content.winfo_children():
            w.destroy()

        if name == "PROCESS":
            self._build_process_page()
        elif name == "ENV":
            self._build_env_page()
        elif name in VERIFY_MODULES:
            self._build_verify_page(name)
        elif name == "SKIPPER":
            self._build_skipper_page()
        elif name == "KLAYOUT":
            self._build_klayout_page()
        elif name == "DOC":
            self._build_doc_page()
        elif name == "SYSTEM":
            self._build_system_page()

    # ------------------------------------------------------------------
    # PROCESS 頁面（圖一）
    # ------------------------------------------------------------------
    def _build_process_page(self):
        top = tk.Frame(self.content, bg="#d9d9d9")
        top.pack(fill="both", expand=True)

        tk.Label(top, text="*** Process ***", bg="#d9d9d9",
                 font=("Arial", 11)).pack(pady=(20, 10))

        combo = ttk.Combobox(top, values=[DESIGN_NAME], state="readonly", width=40)
        combo.set(DESIGN_NAME)
        combo.pack()

        # 右下角 Logo 展示區
        LogoPanel(top, height=110).pack(side="bottom", fill="x")

    # ------------------------------------------------------------------
    # ENV 頁面（圖二：Tool Version 下拉選單）
    # ------------------------------------------------------------------
    def _build_env_page(self):
        top = tk.Frame(self.content, bg="#d9d9d9")
        top.pack(fill="both", expand=True)

        tk.Label(top, text="*** Tool Version ***", bg="#d9d9d9",
                 font=("Arial", 11)).pack(pady=(20, 10))

        tools = {
            "calibre": ["2024.1_36.20", "2023.4_20.11"],
            "jivaro": ["2020", "2019"],
            "skipper": ["2019.06-sp3", "2018.09-sp1"],
            "editor": ["gvim", "vim", "emacs"],
        }
        for key, values in tools.items():
            cb = ttk.Combobox(top, values=values, state="readonly", width=40)
            cb.set(values[0])
            cb.pack(pady=4)

        LogoPanel(top, height=110).pack(side="bottom", fill="x")

    # ------------------------------------------------------------------
    # DRC / ANT / WB / BUMP / DMDV / DPDO / LVS / XRC / JIVARO
    # 共用的驗證流程頁面樣板（圖三、圖四、圖五）
    # ------------------------------------------------------------------
    def _build_verify_page(self, module_name):
        top = tk.Frame(self.content, bg="#d9d9d9")
        top.pack(fill="both", expand=True, padx=10, pady=10)

        tk.Label(top, text=DESIGN_NAME, bg="#d9d9d9",
                 font=("Arial", 11)).grid(row=0, column=0, columnspan=4, pady=(0, 10))

        fields = [("LayoutPath", True), ("LayoutPrimary", False)]
        if module_name in ("LVS", "XRC"):
            fields += [("SourcePath", True), ("SourcePrimary", False), ("LvsHier", "check")]
        fields.append(("RunFolder", True))

        self._entries = {}
        row = 1
        for label, kind in fields:
            tk.Label(top, text=label, bg="#d9d9d9").grid(row=row, column=0, sticky="w")
            if kind == "check":
                var = tk.BooleanVar()
                tk.Checkbutton(top, variable=var, bg="#d9d9d9").grid(row=row, column=1, sticky="w")
                self._entries[label] = var
            else:
                ent = tk.Entry(top, width=90)
                ent.grid(row=row, column=1, columnspan=2, sticky="we", padx=4)
                self._entries[label] = ent
                if kind is True:
                    tk.Button(top, text="Open",
                              command=lambda e=ent: self._browse_file(e)).grid(row=row, column=3, padx=2)
            row += 1

        top.grid_columnconfigure(2, weight=1)

        btn_frame = tk.Frame(top, bg="#d9d9d9")
        btn_frame.grid(row=row, column=0, columnspan=4, pady=10)
        for text in ("Run", "Rve", "LoadDefault", "Load", "Save"):
            tk.Button(btn_frame, text=text, width=12,
                      command=lambda t=text, m=module_name: self._on_verify_button(m, t)
                      ).pack(side="left", padx=4)
        row += 1

        # 下方的 command file 文字區（顯示/編輯 .com 檔內容）
        text_frame = tk.Frame(top)
        text_frame.grid(row=row, column=0, columnspan=4, sticky="nsew", pady=(10, 0))
        top.grid_rowconfigure(row, weight=1)

        self._cmd_text = tk.Text(text_frame, wrap="none")
        yscroll = tk.Scrollbar(text_frame, orient="vertical", command=self._cmd_text.yview)
        xscroll = tk.Scrollbar(text_frame, orient="horizontal", command=self._cmd_text.xview)
        self._cmd_text.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)

        self._cmd_text.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="we")
        text_frame.grid_rowconfigure(0, weight=1)
        text_frame.grid_columnconfigure(0, weight=1)

        self._cmd_text.insert("1.0", self._default_command_template(module_name))

    def _default_command_template(self, module_name):
        return (
            'LAYOUT PRIMARY "%s"\n'
            'LAYOUT SYSTEM GDSII\n\n'
            '%s RESULTS DATABASE "%s.db"\n'
            '%s SUMMARY REPORT "%s.rep"\n'
        ) % (DESIGN_NAME, module_name, module_name.lower(),
             module_name, module_name.lower())

    def _browse_file(self, entry_widget):
        path = filedialog.askopenfilename()
        if path:
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, path)

    def _on_verify_button(self, module_name, action):
        # 這裡只是示範接口：實際上你會在這裡呼叫 Calibre/skipper 等
        # 後端指令，例如 subprocess.Popen(["calibre", "-drc", cmdfile])
        messagebox.showinfo(
            "pdkgui",
            "模組: %s\n動作: %s\n(這裡接上實際的 EDA 執行指令)" % (module_name, action)
        )

    # ------------------------------------------------------------------
    # SKIPPER 頁面（圖六：GDS 清單）
    # ------------------------------------------------------------------
    def _build_skipper_page(self):
        top = tk.Frame(self.content, bg="#d9d9d9")
        top.pack(fill="both", expand=True, padx=10, pady=10)

        tk.Label(top, text=DESIGN_NAME, bg="#d9d9d9",
                 font=("Arial", 11)).grid(row=0, column=0, columnspan=3, pady=(0, 10))

        # 這裡放最近開過的 GDS 清單，實務上可從歷史紀錄檔讀進來
        recent_gds = [
            "/datacenter/users/example/project/design_top.gds",
        ]
        for i in range(10):
            path = recent_gds[i] if i < len(recent_gds) else ""
            tk.Label(top, text="GDS%d" % (i + 1), bg="#d9d9d9").grid(row=i + 1, column=0, sticky="w")
            ent = tk.Entry(top, width=90)
            ent.insert(0, path)
            ent.grid(row=i + 1, column=1, sticky="we", padx=4)
            tk.Button(top, text="Open").grid(row=i + 1, column=2, padx=2)
            tk.Button(top, text="View").grid(row=i + 1, column=3, padx=2)

        top.grid_columnconfigure(1, weight=1)

    # ------------------------------------------------------------------
    # KLAYOUT 頁面（簡易版本，可視需要擴充）
    # ------------------------------------------------------------------
    def _build_klayout_page(self):
        top = tk.Frame(self.content, bg="#d9d9d9")
        top.pack(fill="both", expand=True, padx=10, pady=10)
        tk.Label(top, text="*** KLayout ***", bg="#d9d9d9",
                 font=("Arial", 11)).pack(pady=10)
        tk.Button(top, text="Open with KLayout",
                  command=lambda: messagebox.showinfo("pdkgui", "呼叫 klayout 開啟 GDS")).pack()

    # ------------------------------------------------------------------
    # DOC 頁面（圖七：三欄式文件瀏覽）
    # ------------------------------------------------------------------
    def _build_doc_page(self):
        top = tk.Frame(self.content, bg="#e5e5e5")
        top.pack(fill="both", expand=True)

        col1 = tk.Frame(top, bg="#e5e5e5", width=180)
        col2 = tk.Frame(top, bg="#e5e5e5")
        col3 = tk.Frame(top, bg="#e5e5e5", width=220)
        col1.pack(side="left", fill="y")
        col2.pack(side="left", fill="both", expand=True)
        col3.pack(side="right", fill="y")
        col1.pack_propagate(False)
        col3.pack_propagate(False)

        tk.Label(col1, text="Doc. No.", bg="#e5e5e5").pack(anchor="w")
        doc_list = ["BEOLRCTable", "Bump", "DRCCommandFile", "GDSLayerUsageDescription",
                    "LVS", "LVSDeviceFormationDoc", "LayoutEditor", "PDK",
                    "QualReport", "Report", "SPICEModels", "Utility", "WireBond"]
        self._doc_titles = tk.Text(col2, wrap="word", bg="#e5e5e5", bd=0)
        self._doc_titles.pack(fill="both", expand=True)
        self._doc_titles.insert("1.0", "Title\n\n(點選左方文件名稱以載入內容)")

        for d in doc_list:
            lbl = tk.Label(col1, text=d, fg="blue", bg="#e5e5e5", cursor="hand2")
            lbl.pack(anchor="w")
            lbl.bind("<Button-1>", lambda e, name=d: self._load_doc(name))

        tk.Label(col3, text="Doc. Group", bg="#e5e5e5").pack(anchor="w")
        for f in ["Release_Note.pdf", "Design_Note.pdf"]:
            tk.Label(col3, text=f, fg="blue", bg="#e5e5e5", cursor="hand2").pack(anchor="w")

    def _load_doc(self, name):
        self._doc_titles.delete("1.0", tk.END)
        self._doc_titles.insert("1.0", "Title\n\n%s\n(這裡載入實際文件內容或開啟 PDF)" % name)

    # ------------------------------------------------------------------
    # SYSTEM 頁面（圖八：版本更新紀錄）
    # ------------------------------------------------------------------
    def _build_system_page(self):
        top = tk.Frame(self.content, bg="white")
        top.pack(fill="both", expand=True)

        text = tk.Text(top, wrap="none")
        yscroll = tk.Scrollbar(top, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=yscroll.set)
        text.pack(side="left", fill="both", expand=True)
        yscroll.pack(side="right", fill="y")

        text.insert("1.0", (
            "pdkgui @SIRIUS\n\n"
            "Revision   Date         Description\n"
            "---------- ----------   ------------------------------------------------\n"
            "2026.0720  2026/07/20   * [Commandfile] t22 lvs deck from v1.2i to v1.2k "
            "in LVS and XRC of t22_4x1z1u and t22_5x1z1u\n"
        ))
        text.configure(state="disabled")


if __name__ == "__main__":
    app = PdkGui()
    app.mainloop()
