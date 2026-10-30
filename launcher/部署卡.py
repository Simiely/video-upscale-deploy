# -*- coding: utf-8 -*-
"""部署卡 —— App 的「缺失与部署」mixin（v1.5.0 从主文件拆出）。

主文件逻辑行再次逼近千行红线（1219 → 拆分后 9xx），把这块「只跟部署清单打交道」
的界面整体搬出来。依赖方向不变：主程序 → 部署卡 → 部署下载 / 部署清单 / ui_kit，
本模块不 import 业务代码，只通过 self.* 用 App 已建好的东西。

配置的接法同 服务面板.py：本模块的 CONFIG 与主程序是**同一个字典**——
主程序启动时执行 `部署卡.CONFIG = CONFIG` 注入引用。

注意：self.log / self.uiqueue / self.root / self._deploy_row_cells 等都由主文件的
App 提供，本类只作为 App 的基类参与拼装 —— pylint 看不到这层关系会对 no-member
误报，故在类级关闭该检查（真实成员在 App.__init__ 与 _build_deploy_card 里定义）。
"""
import os
import subprocess
import threading
import time

import tkinter as tk

import 部署清单 as dl
import 部署下载 as dw
import 运行时 as rt
from 运行时 import strip_ansi          # 安装脚本输出进日志前必须剥 ANSI（否则满屏方块）
from ui_kit import S, f, BG, CARD, CARD2, BORDER, TXT, TXT2, BLUE, RoundedFrame, RButton

# 主程序启动时注入同一字典（见模块 docstring）；这里给空壳只为 import 时不炸
CONFIG = {}


def _size_text(status, expect, actual, item=None):
    """大小列的显示口径。

    · 就绪 / 不完整 → 磁盘上的**实际占用**（目录递归合计，这才是"已安装多大"）
    · 缺失         → 需要下载的**期望大小**（告诉用户要腾多少空间）
    · 未装且大小随 release 变（Video2X）→ 用条目的 `size_hint` 给个量级
    · 都没有       → "-"
    以前只有权重项写了 expect，目录型条目一律 "-" —— 一列半空，看不出装了多少。
    """
    if status != "缺失" and actual:
        return rt.human_size(actual)
    if expect:
        return rt.human_size(expect)
    if actual:
        return rt.human_size(actual)
    hint = (item or {}).get("size_hint")
    if hint:
        return hint
    return "-"


def _clip_text(txt, limit=52):
    """超长一行截断加省略号。

    缺失明细里的权重文件名是**一整个没有空格的长 token**，Tk 的 wraplength 只在
    空格处折行，超长单词依旧会被列宽切掉 —— 与其硬塞，不如截断（完整内容进日志）。
    """
    return txt if len(txt) <= limit else txt[:limit - 1] + "…"


class 部署卡:
    # pylint: disable=no-member  # mixin 约定：宿主 App 提供界面成员
    _deploy_running = False   # 类级默认：真实赋值在 _build_deploy_card / _deploy_action
    _deploy_pct = -10

    # ---- 缺失与部署卡（左栏设置区下方；v1.2.25 依用户反馈重做版式）----
    def _build_deploy_card(self, parent):
        """缺失部署清单卡。

        v1.2.25 三条版式规则（直接来自用户反馈）：
          1) **就绪项不进侧栏、也不给「安装」按钮** —— 缺什么才显示什么，不制造"该不该点"的疑问；
          2) 每个未就绪项必须有**可点的动作**：有 `.ps1` 的给「安装」，只有 HF 仓库的给「下载」，
             两样都没有的明写「需手动」，不再摆一个点不动的灰按钮；
          3) 侧栏只列前 4 项未就绪，完整 15 项进弹窗 —— 174px 宽的侧栏塞不下"长名称 + 按钮"。
        """
        tk.Label(parent, text="缺失与部署", bg=CARD, fg=TXT2, font=f(9), anchor="w").pack(
            fill="x", padx=S(2), pady=(S(8), S(2)))
        card = RoundedFrame(parent, outer=BG, pad=(6, 6))
        card.pack(fill="x")
        b = card.body
        head = tk.Frame(b, bg=CARD)
        head.pack(fill="x")
        RButton(head, text="刷新", command=lambda: self._refresh_deploy(verbose=True),
                fill=CARD2, fg=TXT, outer=CARD, font=f(8), pady=2,
                stretch=True).pack(side="right", padx=(S(6), 0))
        self._deploy_sum = tk.Label(head, text="探测中…", bg=CARD, fg=TXT2, font=f(8), anchor="w")
        self._deploy_sum.pack(side="left", fill="x", expand=True)
        # v1.2.25：侧栏只留一行"待处理哪几项"，明细与动作全进弹窗。
        # 原因很硬：侧栏固定 892px，设置区已经吃掉 ~600px，再塞 3 个带按钮的条目
        # 就会连卡片底边一起被窗口裁掉（实测 CARD_BOTTOM 已顶到 960）。
        self._deploy_todo = tk.Label(b, text="", bg=CARD, fg=TXT2, font=f(8), anchor="w",
                                     justify="left", wraplength=S(150))
        self._deploy_todo.pack(fill="x", pady=(S(4), 0))
        RButton(b, text="查看并处理", command=self._open_deploy_window,
                fill="transparent", fg=TXT, border=BORDER, outer=CARD, font=f(8), pady=2,
                stretch=True).pack(fill="x", pady=(S(6), 0))
        self._deploy_win = None          # 弹窗（打开过才有）
        self._deploy_running = False
        self._deploy_pct = -10
        self._refresh_deploy()

    # --- 状态 → 动作（就绪 = 已安装，不给按钮）---
    def _deploy_action(self, parent, item, status):
        if status == "就绪":
            return tk.Label(parent, text="已安装", bg=CARD, fg="#7FB77E", font=f(7))
        if item and item.get("script"):
            return RButton(parent, text="安装",
                           command=lambda: self._install_deploy(item["key"], item["script"]),
                           fill=CARD2, fg=TXT, outer=CARD, font=f(8), pady=1, minwidth=46)
        if item and item.get("restore"):
            return RButton(parent, text="恢复",
                           command=lambda: self._restore_deploy(item["key"]),
                           fill=CARD2, fg=TXT, outer=CARD, font=f(8), pady=1, minwidth=46)
        if item and item.get("installer"):
            return RButton(parent, text="安装",
                           command=lambda: self._install_builtin(item["key"]),
                           fill=CARD2, fg=TXT, outer=CARD, font=f(8), pady=1, minwidth=46)
        if item and item.get("hf"):
            return RButton(parent, text="下载",
                           command=lambda: self._download_deploy(item["key"]),
                           fill=CARD2, fg=TXT, outer=CARD, font=f(8), pady=1, minwidth=46)
        return tk.Label(parent, text="需手动", bg=CARD, fg=TXT2, font=f(7))

    @staticmethod
    def _deploy_brief(status, expect, actual=0):
        """行内状态短句：缺失→「缺失 · 需 X」；不完整→「不完整 · 已有 X / 需 Y」。"""
        if status == "就绪":
            return ""
        if status == "不完整" and actual:
            tail = "已有 " + rt.human_size(actual)
            if expect:
                tail += " / 需 " + rt.human_size(expect)
            return status + " · " + tail
        txt = status
        if expect:
            txt += " · 需 " + rt.human_size(expect)
        return txt

    def _refresh_deploy(self, verbose=False):
        """重跑探测并重建侧栏摘要 + 条目；弹窗开着时同步刷新。

        verbose=True（点「刷新」/ 安装下载完成后）才把每项缺失明细打进日志，
        免得每次启动都刷十几行噪音。
        """
        rows = dw.deploy_inventory(CONFIG)
        ready = sum(1 for r in rows if r[2] == "就绪")
        bad = [r for r in rows if r[2] != "就绪"]
        self._deploy_sum.configure(text="就绪 %d / %d" % (ready, len(rows)))
        if bad:
            names = "、".join(r[1] for r in bad[:3])
            if len(bad) > 3:
                names += " 等 %d 项" % len(bad)
            self._deploy_todo.configure(text="待处理：" + names, fg="#E06C75")
        else:
            self._deploy_todo.configure(text="全部就绪，无需处理", fg="#7FB77E")
        self.log("[部署] 探测 %d 项：就绪 %d / 未就绪 %d" % (len(rows), ready, len(bad)), "dim")
        if verbose:
            for key, name, status, note, expect, actual, script in bad:
                if note:
                    self.log("[部署] %s（%s）：%s" % (name, status, note), "dim")
        self._render_deploy_window()

    # --- 完整清单弹窗：按工作流分组的卡片（v1.2.26）---
    def _open_deploy_window(self):
        win = self._deploy_win
        if win is not None and win.winfo_exists():
            win.deiconify()
            win.lift()
            win.focus_set()
            return
        win = tk.Toplevel(self.root)
        win.title("部署清单")
        win.configure(bg=BG)
        w, h = S(820), S(730)
        win.geometry("%dx%d+%d+%d" % (w, h,
                                      self.root.winfo_rootx() + S(40),
                                      self.root.winfo_rooty() + S(30)))
        win.minsize(S(680), S(460))
        win.transient(self.root)
        self._deploy_win = win
        head = tk.Frame(win, bg=BG)
        head.pack(fill="x", padx=S(16), pady=(S(14), S(4)))
        tk.Label(head, text="部署清单", bg=BG, fg=TXT, font=f(12, True)).pack(side="left")
        RButton(head, text="刷新", command=lambda: self._refresh_deploy(verbose=True),
                fill=CARD2, fg=TXT, outer=BG, font=f(9), pady=3).pack(side="right")
        tk.Label(win, text="按工作流分组：公共组件装一次就够；下面四条方案各装各的，只用哪条就装哪条。"
                           "就绪项显示「已安装」，缺失项给「安装」或「下载」。",
                 bg=BG, fg=TXT2, font=f(8), anchor="w").pack(fill="x", padx=S(16))

        wrap = tk.Frame(win, bg=BG)
        wrap.pack(fill="both", expand=True, padx=S(14), pady=(S(8), S(12)))
        wrap.rowconfigure(0, weight=1)
        wrap.columnconfigure(0, weight=1)
        cv = tk.Canvas(wrap, bg=BG, highlightthickness=0)
        cv.grid(row=0, column=0, sticky="nsew")
        sb = tk.Scrollbar(wrap, orient="vertical", command=cv.yview)
        sb.grid(row=0, column=1, sticky="ns")
        inner = tk.Frame(cv, bg=BG)
        item = cv.create_window((0, 0), window=inner, anchor="nw")
        cv.configure(yscrollcommand=sb.set)
        inner.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))
        cv.bind("<Configure>", lambda e: cv.itemconfigure(item, width=e.width))
        cv.bind("<Enter>", lambda e: cv.bind_all(
            "<MouseWheel>", lambda ev: cv.yview_scroll(-int(ev.delta / 120), "units")))
        cv.bind("<Leave>", lambda e: cv.unbind_all("<MouseWheel>"))
        self._deploy_cv = cv
        self._deploy_inner = inner
        self._deploy_cells = []
        self._render_deploy_window()

    def _render_deploy_window(self):
        inner = getattr(self, "_deploy_inner", None)
        win = getattr(self, "_deploy_win", None)
        if inner is None or win is None or not win.winfo_exists():
            return
        for w in list(inner.winfo_children()):
            w.destroy()
        self._deploy_cells = []
        self._deploy_row_cells = {}       # key → 行内「大小」列（下载/安装进度就地刷新）
        rows = dw.deploy_inventory(CONFIG)
        got = {r[0]: r for r in rows}
        for gkey, gtitle, gdesc in dl.GROUPS:
            grows = [got[it["key"]] for it in dl.items_of(gkey) if it["key"] in got]
            if grows:
                self._deploy_group_card(inner, gtitle, gdesc, grows)

    def _deploy_group_card(self, parent, gtitle, gdesc, grows):
        """一张分组卡：标题 + 组内就绪比 + 说明 + 逐项行。"""
        ready = sum(1 for r in grows if r[2] == "就绪")
        total = len(grows)
        card = RoundedFrame(parent, outer=BG, pad=(10, 7), radius=S(10))
        card.pack(fill="x", pady=(0, S(6)))
        body = card.body
        head = tk.Frame(body, bg=CARD)
        head.pack(fill="x")
        if ready == total:
            chip, color = "全部就绪", "#7FB77E"
        else:
            chip, color = "缺 %d 项" % (total - ready), "#E06C75"
        # 标题前的状态点：不展开卡片也能看出这一组有没有缺口
        dot = tk.Canvas(head, width=S(8), height=S(8), bg=CARD, highlightthickness=0)
        dot.create_oval(1, 1, S(7), S(7), fill=color, outline="")
        dot.pack(side="left", padx=(0, S(6)))
        tk.Label(head, text=gtitle, bg=CARD, fg=TXT, font=f(10, True)).pack(side="left")
        tk.Label(head, text="%s · %d/%d" % (chip, ready, total), bg=CARD, fg=color,
                 font=f(8)).pack(side="right")
        tk.Label(body, text=gdesc, bg=CARD, fg=TXT2, font=f(7), anchor="w",
                 justify="left").pack(fill="x", pady=(S(2), S(4)))

        grid = tk.Frame(body, bg=CARD)
        grid.pack(fill="x")
        for col, minsize in ((0, 0), (1, S(54)), (2, S(76)), (3, S(84))):
            grid.columnconfigure(col, weight=1 if col == 0 else 0, minsize=minsize)

        name_cells = []
        for idx, (key, name, status, note, expect, actual, script) in enumerate(grows):
            item = dl.by_key(key)
            color = {"就绪": "#7FB77E", "缺失": "#E06C75", "不完整": "#E5A04C"}.get(status, TXT2)
            txt = _clip_text("%s（%s）" % (name, note), 46) if note else name
            name_cell = tk.Label(grid, text=txt, bg=CARD, fg=TXT, font=f(9), anchor="w",
                                 justify="left")
            name_cell.grid(row=idx, column=0, sticky="ew", padx=(S(6), S(4)), pady=S(2))
            st_cell = tk.Label(grid, text=status, bg=CARD, fg=color, font=f(8), anchor="w")
            st_cell.grid(row=idx, column=1, sticky="ew", padx=S(4), pady=S(2))
            sz_cell = tk.Label(grid, text=_size_text(status, expect, actual, item),
                               bg=CARD, fg=TXT2, font=f(8), anchor="e")
            sz_cell.grid(row=idx, column=2, sticky="ew", padx=S(4), pady=S(2))
            act = self._deploy_action(grid, item, status)
            act.grid(row=idx, column=3, sticky="e", padx=(S(4), S(6)), pady=S(2))
            self._deploy_cells += [name_cell, st_cell, sz_cell, act]
            self._deploy_row_cells[key] = sz_cell
            name_cells.append(name_cell)

        # 名称列跟着卡片宽折行（窗口可缩放）；超长无空格 token 仍由 _clip_text 兜住
        def _fit(_event=None):
            avail = max(S(180), grid.winfo_width() - S(54 + 76 + 84 + 40))
            for lbl in name_cells:
                try:
                    lbl.configure(wraplength=avail)
                except tk.TclError:
                    pass
        grid.bind("<Configure>", _fit)
        _fit()

    # --- 安装（跑 .ps1）---
    def _disk_gate(self, item):
        """安装/下载前的磁盘预检（v1.4.0）。空间不够就拦下并说清差多少。"""
        ok, free, need, root = dw.disk_check(CONFIG, item)
        if need:
            self.log("[部署] %s 目标盘剩余 %s，需要约 %s"
                     % (root or "目标盘", rt.human_size(free), rt.human_size(need)), "dim")
        if not ok:
            self.log("[部署] 空间不足：%s 只剩 %s，%s 需要约 %s —— 先清理磁盘再试"
                     % (root or "目标盘", rt.human_size(free), item["name"],
                        rt.human_size(need)), "err")
        return ok

    def _install_deploy(self, key, script):
        """一键安装：互斥 + 校验脚本存在 + 后台线程跑安装脚本。"""
        if self._deploy_running:
            self.log("[部署] 已有任务在跑，先等它结束", "warn")
            return
        script_path = os.path.join(CONFIG["deploy_root"], script)
        if not os.path.isfile(script_path):
            self.log("[部署] 找不到安装脚本：%s" % script_path, "err")
            return
        item = dl.by_key(key)
        if item and not self._disk_gate(item):
            return
        self._deploy_running = True
        self.log("[部署] 开始：%s（%s）" % (key, os.path.basename(script_path)), "hi")
        threading.Thread(target=self._run_deploy_install, args=(key, script_path),
                        daemon=True).start()

    def _run_deploy_install(self, key, script_path):
        """后台线程：跑安装脚本，stdout/stderr 逐行清洗后流进统一日志窗。
        与 服务面板._svc_reader 同模式（self.log 内部经 root.after 回主线程落盘/渲染）。"""
        try:
            proc = subprocess.Popen(
                ["powershell", "-ExecutionPolicy", "Bypass", "-File", script_path],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                encoding="utf-8", errors="replace", creationflags=rt.NO_WINDOW)
            for line in proc.stdout:
                self.log("[部署] " + strip_ansi(line).rstrip(), "dim")
            proc.wait()
            if proc.returncode == 0:
                self.log("[部署] %s 完成" % key, "ok")
            else:
                self.log("[部署] %s 失败（退出码 %s）" % (key, proc.returncode), "err")
        except Exception as e:
            self.log("[部署] %s 启动失败：%s" % (key, e), "err")
        finally:
            self._deploy_running = False
            self.root.after(0, lambda: self._refresh_deploy(verbose=True))  # 完成回调：主线程重跑探测刷新清单
            if key.startswith("node_"):
                self.log("[部署] 装了节点，必要时重启 ComfyUI 生效", "warn")

    # --- 安装（内置 Python 安装器，v1.4.0：ffmpeg）---
    def _install_builtin(self, key):
        """内置安装器：不走 .ps1，便于复用 GitHub 镜像回退与 ffmpeg 能力校验。"""
        if self._deploy_running:
            self.log("[部署] 已有任务在跑，先等它结束", "warn")
            return
        item = dl.by_key(key)
        if not item:
            return
        name = item.get("installer")
        if name != "ffmpeg":
            self.log("[部署] 未知的内置安装器：%s" % name, "err")
            return
        if not self._disk_gate(item):
            return
        self._deploy_running = True
        self._deploy_pct = -10
        self._deploy_last_log = 0
        self._deploy_mark = (time.time(), 0)
        self.log("[部署] 开始安装 %s（内置安装器：GitHub 直连 + 镜像回退）" % item["name"], "hi")
        threading.Thread(target=self._run_install_builtin, args=(item,), daemon=True).start()

    def _run_install_builtin(self, item):
        """后台线程：运行时.install_ffmpeg（下载 → 解压 → 能力探测）。"""
        try:
            ok, msg = dw.install_ffmpeg(
                CONFIG,
                on_progress=lambda cur, tot, k=item["key"]: self._deploy_item_progress(
                    k, "安装", cur, tot))
            self.log("[部署] %s：%s" % (item["name"], msg), "ok" if ok else "err")
        except Exception as exc:
            self.log("[部署] %s 安装异常：%s" % (item["name"], exc), "err")
        finally:
            self._deploy_running = False
            self.root.after(0, lambda: self._refresh_deploy(verbose=True))

    # --- 恢复（从部署仓库拷内置资源，如工作流 json）---
    def _restore_deploy(self, key):
        if self._deploy_running:
            self.log("[部署] 已有任务在跑，先等它结束", "warn")
            return
        item = dl.by_key(key)
        if not item:
            return
        self._deploy_running = True
        threading.Thread(target=self._run_deploy_restore, args=(item,), daemon=True).start()

    def _run_deploy_restore(self, item):
        """后台线程：把部署仓库里的内置资源铺到目标目录（幂等，已存在跳过）。"""
        try:
            self.log("[部署] 恢复 %s ← 部署仓库" % item["name"], "hi")
            copied, skipped, msg = dw.restore_workflows(CONFIG)
            if copied or skipped:
                self.log("[部署] %s：新复制 %d 个，已存在跳过 %d 个" % (msg, copied, skipped), "ok")
            else:
                self.log("[部署] 恢复失败：%s" % msg, "err")
        except Exception as exc:
            self.log("[部署] 恢复异常：%s" % exc, "err")
        finally:
            self._deploy_running = False

            def done():
                self._refresh_deploy(verbose=True)
                self._rescan_wf_dir()      # 铺完立刻刷新工作流下拉
            self.root.after(0, done)

    # --- 下载（HF 镜像补单文件，P1）---
    def _download_deploy(self, key):
        if self._deploy_running:
            self.log("[部署] 已有任务在跑，先等它结束", "warn")
            return
        item = dl.by_key(key)
        if not item or not item.get("hf"):
            self.log("[部署] %s 没有下载源，需要手动处理" % key, "warn")
            return
        root = dw._resolve_deploy_root(CONFIG, item["root"])
        if not root:
            self.log("[部署] 目标根目录没配置，无法下载：%s" % item["root"], "err")
            return
        if not self._disk_gate(item):
            return
        self._deploy_running = True
        self._deploy_pct = -10
        self._deploy_last_log = 0
        self._deploy_mark = (time.time(), 0)
        self.log("[部署] 开始下载：%s ← %s（优先 ModelScope，分段并行）" % (item["name"], item["hf"]), "hi")
        threading.Thread(target=self._run_deploy_download, args=(item, root),
                        daemon=True).start()

    def _run_deploy_download(self, item, root):
        """后台线程：逐文件 curl 补下（断点续传），进度按 10% 打一行。"""
        files = list(item["check"])
        paths = dl.hf_paths_of(item)
        exps = dl.expects_of(item)
        shas = dl.sha256_of(item)
        try:
            for rel, hf_path, exp, sha in zip(files, paths, exps, shas):
                dest = os.path.join(root, rel.replace("/", os.sep))
                self.log("[部署] 下载 %s（%s）" % (hf_path, rt.human_size(exp) if exp else "大小未知"),
                         "dim")
                ok, size, msg = dw.hf_pull(
                    item["hf"], hf_path, dest, expect=exp, sha256=sha,
                    on_progress=lambda cur, tot, k=item["key"]: self._deploy_item_progress(
                        k, "下载", cur, tot))
                if not ok:
                    self.log("[部署] %s 失败：%s" % (hf_path, msg), "err")
                    return
                self.log("[部署] %s 完成（%s）" % (hf_path, msg), "ok")
            self.log("[部署] %s 下载完成" % item["name"], "ok")
            if item["key"].startswith("node_"):
                self.log("[部署] 装了节点，必要时重启 ComfyUI 生效", "warn")
        except Exception as e:
            self.log("[部署] 下载异常：%s" % e, "err")
        finally:
            self._deploy_running = False
            self.root.after(0, lambda: self._refresh_deploy(verbose=True))

    def _deploy_item_progress(self, key, verb, cur, total):
        """下载/安装进度（后台线程调）。

        两路输出：① 弹窗里该条目的「大小」列就地刷新（经 uiqueue 回主线程，绝不跨线程碰控件）；
        ② 日志每 10% 一行（20 GB 逐 MB 刷会淹掉日志窗）。
        """
        if not total:
            # 镜像没返回 Content-Length 时按"已下多少"显示，每 100 MB 记一行
            txt = "%s · 已下 %s" % (verb, rt.human_size(cur))
            self.uiqueue.put(lambda: self._set_deploy_row(key, txt))
            if cur - getattr(self, "_deploy_last_log", 0) >= 100 * 1024 * 1024:
                self._deploy_last_log = cur
                self.log("[部署] %s %s：已下 %s" % (key, verb, rt.human_size(cur)), "dim")
            return
        pct = min(100, int(cur * 100 / total))
        txt = "%s %d%% · %s / %s" % (verb, pct, rt.human_size(cur), rt.human_size(total))
        self.uiqueue.put(lambda: self._set_deploy_row(key, txt))
        now = time.time()
        prev_t, prev_b = getattr(self, "_deploy_mark", (now, cur))
        self._deploy_mark = (now, cur)
        speed = ""
        if now - prev_t > 0:
            mbps = (cur - prev_b) / 1048576.0 / (now - prev_t)
            if mbps > 0.05:
                speed = "，%.1f MB/s" % mbps
        if pct >= 100 or pct - self._deploy_pct >= 10:
            self._deploy_pct = pct
            self.log("[部署] %s %s中 %d%%（%s / %s%s）"
                     % (key, verb, pct, rt.human_size(cur), rt.human_size(total), speed), "dim")

    def _set_deploy_row(self, key, text):
        """主线程：把进度写到弹窗里对应条目的「大小」列（弹窗没开/已重建就忽略）。"""
        cell = getattr(self, "_deploy_row_cells", {}).get(key)
        if cell is None:
            return
        try:
            if cell.winfo_exists():
                cell.configure(text=text, fg=BLUE)
        except tk.TclError:
            pass

