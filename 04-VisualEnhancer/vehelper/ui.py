# -*- coding: utf-8 -*-
"""UI 公共件：色板、标题栏、按钮、深色消息框、目录选择器。

只依赖 tkinter/ttk 和 sv-ttk 主题；不包含业务逻辑。
"""
import ctypes
import os
import tkinter as tk
from tkinter import ttk

BG = "#1c1c1c"
CARD = "#242424"
CARD2 = "#2d2d2d"
BORDER = "#3a3a3a"
TXT = "#fafafa"
TXT2 = "#a0a0a0"
BLUE = "#57c8ff"
GREEN = "#7FB77E"
AMBER = "#E5A04C"
RED = "#E06C75"


def set_dark_titlebar(win):
    try:
        win.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
        value = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(value),
                                                   ctypes.sizeof(value))
    except Exception:
        pass


def dark_button(parent, text, cmd, primary=False, width=12):
    return ttk.Button(parent, text=text, command=cmd, width=width,
                      style="Accent.TButton" if primary else "TButton")


def dark_message(parent, title, text, kind="info"):
    win = tk.Toplevel(parent)
    win.withdraw()
    win.title(title)
    win.configure(bg=BG)
    win.transient(parent)
    win.resizable(False, False)
    set_dark_titlebar(win)
    wrap = tk.Frame(win, bg=BG)
    wrap.pack(fill="both", expand=True, padx=18, pady=16)
    color = {"warn": AMBER, "error": RED}.get(kind, TXT)
    tk.Label(wrap, text=title, bg=BG, fg=color,
             font=("Microsoft YaHei", 11, "bold"), anchor="w").pack(fill="x")
    tk.Label(wrap, text=text, bg=BG, fg=TXT, font=("Microsoft YaHei", 9),
             justify="left", anchor="w", wraplength=380).pack(fill="x", pady=(10, 14))
    row = tk.Frame(wrap, bg=BG)
    row.pack(fill="x")
    dark_button(row, "知道了", win.destroy, primary=True).pack(side="right")
    win.update_idletasks()
    x = parent.winfo_rootx() + max(0, (parent.winfo_width() - win.winfo_width()) // 2)
    y = parent.winfo_rooty() + max(0, (parent.winfo_height() - win.winfo_height()) // 2)
    win.geometry("+%d+%d" % (x, y))
    win.deiconify()
    win.grab_set()
    parent.wait_window(win)


class DirPicker(tk.Toplevel):
    """深色目录选择器（系统 filedialog 是白色）。"""

    def __init__(self, parent, initial=""):
        super().__init__(parent)
        self.withdraw()
        self.result = ""
        self.cur = initial if os.path.isdir(initial) else (os.path.dirname(initial) or "D:\\")
        self.entries = []
        self.title("选择 VE 目录")
        self.configure(bg=BG)
        self.transient(parent)
        self.geometry("760x500")
        self.minsize(620, 400)
        set_dark_titlebar(self)

        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=14, pady=(12, 6))
        dark_button(top, "上一级", self._up, width=7).pack(side="left")
        self.var_path = tk.StringVar(value=self.cur)
        ent = ttk.Entry(top, textvariable=self.var_path)
        ent.pack(side="left", fill="x", expand=True, padx=8)
        ent.bind("<Return>", lambda _e: self._goto(self.var_path.get()))
        dark_button(top, "转到", lambda: self._goto(self.var_path.get()), width=6).pack(side="left")

        mid = tk.Frame(self, bg=BG)
        mid.pack(fill="both", expand=True, padx=14, pady=(0, 6))
        mid.rowconfigure(0, weight=1)
        mid.columnconfigure(0, weight=1)
        self.lb = tk.Listbox(mid, bg="#111318", fg=TXT, selectbackground=BLUE,
                             selectforeground="#ffffff", relief="flat", bd=0,
                             font=("Microsoft YaHei", 9), activestyle="none")
        self.lb.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(mid, orient="vertical", command=self.lb.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.lb.configure(yscrollcommand=sb.set)
        self.lb.bind("<Double-Button-1>", self._activate)

        bottom = tk.Frame(self, bg=BG)
        bottom.pack(fill="x", padx=14, pady=(0, 12))
        tk.Label(bottom, text="双击进入目录；确定 = 选中当前目录",
                 bg=BG, fg=TXT2, font=("Microsoft YaHei", 8)).pack(side="left")
        dark_button(bottom, "取消", self.destroy, width=7).pack(side="right")
        dark_button(bottom, "确定", self._ok, primary=True).pack(side="right", padx=8)
        self._refresh()
        self.update_idletasks()
        x = parent.winfo_rootx() + max(0, (parent.winfo_width() - self.winfo_width()) // 2)
        y = parent.winfo_rooty() + max(0, (parent.winfo_height() - self.winfo_height()) // 2)
        self.geometry("+%d+%d" % (x, y))
        self.deiconify()
        self.grab_set()
        self.lb.focus_set()
        parent.wait_window(self)

    def _goto(self, path):
        if path and os.path.isdir(path):
            self.cur = path
            self.var_path.set(path)
            self._refresh()

    def _up(self):
        self._goto(os.path.dirname(self.cur))

    def _refresh(self):
        self.lb.delete(0, "end")
        self.entries = []
        self.var_path.set(self.cur)
        self.lb.insert("end", "  [选择当前目录]")
        self.entries.append(self.cur)
        try:
            names = sorted([n for n in os.listdir(self.cur)
                            if os.path.isdir(os.path.join(self.cur, n))], key=str.lower)
        except OSError:
            names = []
        for name in names:
            self.lb.insert("end", "  " + name + os.sep)
            self.entries.append(os.path.join(self.cur, name))

    def _activate(self, _event=None):
        sel = self.lb.curselection()
        if not sel:
            return
        path = self.entries[sel[0]]
        if path == self.cur and sel[0] == 0:
            self._ok()
        else:
            self._goto(path)

    def _ok(self):
        self.result = self.cur
        self.destroy()
