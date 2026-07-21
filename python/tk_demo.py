"""Tk GUI 測試環境：左邊 tab 切換右邊 frame，frame 內按鈕會 print + 跳 msgbox。"""

import tkinter as tk
from tkinter import messagebox, ttk


class PageFrame(ttk.Frame):
    """右側的一個頁面，可以直接複製這個 class 來加新頁面。"""

    def __init__(self, master, title):
        super().__init__(master, padding=20)
        self.title = title

        ttk.Label(self, text=title, font=("TkDefaultFont", 14, "bold")).pack(
            anchor="w", pady=(0, 10)
        )
        ttk.Separator(self).pack(fill="x", pady=(0, 15))

        ttk.Button(self, text="說 Hello", command=self.say_hello).pack(
            anchor="w", pady=4
        )
        ttk.Button(self, text="只 print 不跳窗", command=self.print_only).pack(
            anchor="w", pady=4
        )

        self.log = tk.Text(self, height=8, width=50)
        self.log.pack(fill="both", expand=True, pady=(15, 0))

    def say_hello(self):
        msg = f"Hello from {self.title}!"
        print(msg)
        self.write_log(msg)
        messagebox.showinfo("Hello", msg, parent=self)

    def print_only(self):
        msg = f"[{self.title}] 按鈕被按了"
        print(msg)
        self.write_log(msg)

    def write_log(self, msg):
        self.log.insert("end", msg + "\n")
        self.log.see("end")


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Tk 測試環境")
        self.geometry("720x480")

        # tabposition "wn" = 西邊(左)、靠上對齊，讓 tab 出現在左側
        style = ttk.Style(self)
        style.configure("Left.TNotebook", tabposition="wn")

        nb = ttk.Notebook(self, style="Left.TNotebook")
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        for name in ("頁面 A", "頁面 B", "頁面 C"):
            nb.add(PageFrame(nb, name), text=name)


if __name__ == "__main__":
    App().mainloop()
