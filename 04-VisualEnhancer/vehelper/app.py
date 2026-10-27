# -*- coding: utf-8 -*-
"""主窗口与控制器：只做事件编排和 UI 更新，不直接碰 curl/zip。"""
import logging
import logging.handlers
import os
import queue
import subprocess
import threading
import tkinter as tk

import sv_ttk

from . import config, installer, release, ui
from .downloader import Downloader
from .errors import VEHelperError

log = logging.getLogger("vehelper")


def human(n):
    if not n:
        return "-"
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return "%.1f %s" % (n, unit) if unit != "B" else "%d B" % n
        n /= 1024.0
    return "-"


def setup_logging():
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    log_dir = os.path.join(base, "VEHelper", "logs")
    try:
        os.makedirs(log_dir, exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(
            os.path.join(log_dir, "vehelper.log"), maxBytes=1 << 20,
            backupCount=3, encoding="utf-8")
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s: %(message)s"))
        root = logging.getLogger()
        root.setLevel(logging.INFO)
        root.addHandler(handler)
    except OSError:
        pass


class App:
    def __init__(self, root):
        self.root = root
        self.cfg = config.load_cfg()
        self.q = queue.Queue()
        self.downloader = Downloader()
        self.stop_event = threading.Event()
        self.downloading = False
        self.current_release = release.FALLBACK
        self.ve_gui, _cli = installer.find_ve(self.cfg["ve_dir"])
        root.title("VEHelper · DLSS 5 启动器")
        sv_ttk.set_theme("dark")
        root.configure(bg=ui.BG)
        root.geometry("640x360+80+60")
        root.minsize(560, 330)
        ui.set_dark_titlebar(root)
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        self._build()
        self._refresh_ve_status()
        self._drain()
        threading.Thread(target=self._version_worker, daemon=True).start()

    # ---------------------------------------------------------------- 界面
    def _build(self):
        head = tk.Frame(self.root, bg=ui.BG)
        head.pack(fill="x", padx=16, pady=(14, 4))
        tk.Label(head, text="VEHelper", bg=ui.BG, fg=ui.TXT,
                 font=("Microsoft YaHei", 16, "bold")).pack(side="left")
        tk.Label(head, text="DLSS 5 Visual Enhancer 启动器", bg=ui.BG, fg=ui.TXT2,
                 font=("Microsoft YaHei", 9)).pack(side="left", padx=(10, 0))
        self.lbl_ver = tk.Label(head, text=self.current_release.tag, bg=ui.CARD2,
                                fg=ui.BLUE, padx=8, pady=2, font=("Consolas", 9))
        self.lbl_ver.pack(side="right")

        card = tk.Frame(self.root, bg=ui.CARD, highlightthickness=1,
                        highlightbackground=ui.BORDER)
        card.pack(fill="x", padx=16, pady=(10, 0))
        body = tk.Frame(card, bg=ui.CARD)
        body.pack(fill="x", padx=12, pady=12)

        self.lbl_ve = tk.Label(body, text="VE：检测中…", bg=ui.CARD, fg=ui.TXT2,
                               font=("Microsoft YaHei", 9), anchor="w",
                               justify="left", wraplength=560)
        self.lbl_ve.pack(fill="x")

        row = tk.Frame(body, bg=ui.CARD)
        row.pack(fill="x", pady=(10, 0))
        ui.dark_button(row, "选择目录", self.choose_dir, width=10).pack(side="left")
        ui.dark_button(row, "下载并安装最新版", self.start_download,
                       primary=True, width=17).pack(side="left", padx=(8, 0))
        ui.dark_button(row, "启动官方 GUI", self.launch_ve, width=13).pack(
            side="left", padx=(8, 0))

        self.bar = tk.Canvas(body, height=8, bg=ui.CARD, highlightthickness=0, bd=0)
        self.bar.pack(fill="x", pady=(14, 4))
        self.bar.bind("<Configure>", lambda _e: self._render_bar())
        self._pct = 0.0
        self._render_bar()

        self.lbl_status = tk.Label(body, text="就绪", bg=ui.CARD, fg=ui.TXT2,
                                   font=("Microsoft YaHei", 8), anchor="w")
        self.lbl_status.pack(fill="x")

        tk.Label(self.root,
                 text="模型提示：VisionNext / SharpNext / MoGe-2 源不可用；"
                      "神经渲染、DLSS SR、RTX VSR 都不需要这三个模型。",
                 bg=ui.BG, fg=ui.AMBER, font=("Microsoft YaHei", 8),
                 justify="left", anchor="w", wraplength=600).pack(
                     fill="x", padx=16, pady=(10, 0))

    def _refresh_ve_status(self):
        self.ve_gui, _cli = installer.find_ve(self.cfg["ve_dir"])
        state = "已安装" if self.ve_gui else "未安装"
        if self.ve_gui and self.cfg.get("installed_tag"):
            state += "（%s）" % self.cfg["installed_tag"]
        self.lbl_ve.configure(
            text="VE 目录：%s（%s）" % (self.cfg["ve_dir"], state),
            fg=ui.GREEN if self.ve_gui else ui.RED)

    # ---------------------------------------------------------------- 版本
    def _version_worker(self):
        try:
            self._post("release", release.resolve_latest())
        except Exception:
            log.warning("查询最新版失败", exc_info=True)
            self._post("release_fail", release.FALLBACK.tag)

    def _apply_release(self, rel):
        self.current_release = rel
        self.lbl_ver.configure(text=rel.tag)
        self.lbl_status.configure(text="已检测到最新版 %s" % rel.tag, fg=ui.TXT2)

    # ---------------------------------------------------------------- 动作
    def choose_dir(self):
        picker = ui.DirPicker(self.root, self.cfg["ve_dir"])
        if picker.result:
            self.cfg["ve_dir"] = picker.result
            config.save_cfg(self.cfg)
            self._refresh_ve_status()

    def launch_ve(self):
        if not self.ve_gui:
            self.ve_gui, _cli = installer.find_ve(self.cfg["ve_dir"])
        if not self.ve_gui:
            ui.dark_message(self.root, "未安装",
                            "先点「下载并安装最新版」，或把 VE 目录指到已有安装位置。",
                            "warn")
            return
        try:
            subprocess.Popen([self.ve_gui], cwd=os.path.dirname(self.ve_gui))
            self.lbl_status.configure(text="已启动官方 GUI", fg=ui.GREEN)
        except Exception as exc:
            log.exception("启动官方 GUI 失败")
            ui.dark_message(self.root, "启动失败", str(exc), "error")

    # ---------------------------------------------------------------- 下载
    def start_download(self):
        if self.downloading:
            return
        target = self.cfg["ve_dir"]
        os.makedirs(target, exist_ok=True)
        self.downloading = True
        self.stop_event.clear()
        self._pct = 0.0
        self._render_bar()
        self.lbl_status.configure(text="开始下载…", fg=ui.AMBER)
        threading.Thread(target=self._download_worker, args=(target,), daemon=True).start()

    def _download_worker(self, target):
        proxy = release.detect_proxy()
        rel = self.current_release
        try:
            rel = release.resolve_latest(proxy)
            self._post("release", rel)
            self._post("status", "检测到最新版 %s，开始下载" % rel.tag)
        except Exception:
            log.warning("下载前查询最新版失败，使用 %s", rel.tag, exc_info=True)
            self._post("status", "查询最新版失败，使用 %s" % rel.tag)
        try:
            zip_path = self.downloader.download(
                rel, target, proxy=proxy,
                progress=lambda *a: self._post("dl", *a),
                stop_event=self.stop_event)
            if self.stop_event.is_set():
                return
            self._post("status", "解压中…")
            gui_dir = installer.install(zip_path, target)
            try:
                os.remove(zip_path)
            except OSError:
                pass
            self._post("installed", gui_dir, rel.tag,
                       "安装完成 %s：%s" % (rel.tag, gui_dir))
        except VEHelperError as exc:
            log.error("下载/安装失败", exc_info=True)
            self._post("fail", str(exc))
        except Exception as exc:
            log.exception("下载/安装出现未预期错误")
            self._post("fail", str(exc))
        finally:
            self._post("finish")

    # ---------------------------------------------------------------- 进度/事件
    def _render_bar(self):
        c = self.bar
        c.delete("all")
        w = max(c.winfo_width(), 8)
        h = 8
        r = h / 2.0
        c.create_rectangle(r, 0, w - r, h, fill=ui.CARD2, outline="")
        c.create_oval(0, 0, h, h, fill=ui.CARD2, outline="")
        c.create_oval(w - h, 0, w, h, fill=ui.CARD2, outline="")
        pct = max(0.0, min(100.0, getattr(self, "_pct", 0.0)))
        if pct <= 0:
            return
        fw = max(h, w * pct / 100.0)
        c.create_rectangle(r, 0, max(r, fw - r), h, fill=ui.BLUE, outline="")
        c.create_oval(0, 0, h, h, fill=ui.BLUE, outline="")
        c.create_oval(fw - h, 0, fw, h, fill=ui.BLUE, outline="")

    def _draw_bar(self, done, total, mbps=0, eta=0):
        pct = (done * 100.0 / total) if total else 0
        self._pct = pct
        self._render_bar()
        eta_txt = " · 剩 %d:%02d" % (eta // 60, eta % 60) if eta else ""
        self.lbl_status.configure(
            text="%s / %s（%.0f%%）· %.2f MB/s%s"
                 % (human(done), human(total), pct, mbps, eta_txt),
            fg=ui.TXT)

    def _post(self, kind, *args):
        self.q.put((kind, args))

    def _drain(self):
        try:
            while True:
                kind, args = self.q.get_nowait()
                if kind == "status":
                    self.lbl_status.configure(text=args[0], fg=ui.TXT)
                elif kind == "release":
                    self._apply_release(args[0])
                elif kind == "release_fail":
                    self.lbl_ver.configure(text=args[0])
                    self.lbl_status.configure(
                        text="未能查询最新版，将使用内置 %s" % args[0], fg=ui.AMBER)
                elif kind == "dl":
                    self._draw_bar(*args)
                elif kind == "installed":
                    gui_dir, tag, msg = args
                    self.cfg["ve_dir"] = gui_dir
                    self.cfg["installed_tag"] = tag
                    config.save_cfg(self.cfg)
                    self.lbl_status.configure(text=msg, fg=ui.GREEN)
                    self._refresh_ve_status()
                    ui.dark_message(self.root, "完成", msg)
                elif kind == "fail":
                    self.lbl_status.configure(text="失败：%s" % args[0], fg=ui.RED)
                    ui.dark_message(self.root, "失败", args[0], "error")
                elif kind == "finish":
                    self.downloading = False
        except queue.Empty:
            pass
        finally:
            self.root.after(150, self._drain)

    def on_close(self):
        self.stop_event.set()
        self.downloader.cancel()
        self.root.destroy()


def main():
    setup_logging()
    root = tk.Tk()
    App(root)
    root.mainloop()
