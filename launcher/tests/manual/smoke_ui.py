# -*- coding: utf-8 -*-
"""界面冒烟（手动跑，不参与 unittest 自动发现）：真建 Tk、真建 App、留截图。

**为什么它在仓库里**：拆 mixin（v1.5.0 把部署卡搬去 `部署卡.py`）这类改动，
import 阶段完全看不出问题——方法搬过去了、宿主没接上，只有 App 实例化到那一步才炸。
本脚本就是那道闸：9 条断言 + 一张截图。

跑法（必须用带 tkinter 的解释器）：
    python launcher/tests/manual/smoke_ui.py

依赖：tkinter（必需）、Pillow（可选，仅截图用，没装就跳过）。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LAUNCHER = os.path.dirname(os.path.dirname(HERE))          # launcher/tests/manual → launcher

# ⚠️ 必须**强制覆盖**，不能用 setdefault：父进程可能是别的 PyInstaller 程序，
# 会把 TCL_LIBRARY 留在环境里指向它自己的 _tcl_data，报
# "version conflict for package Tcl: have 8.6.15, need exactly 8.6.12"。
if sys.platform == "win32":
    _base = sys.base_prefix
    os.environ["TCL_LIBRARY"] = os.path.join(_base, "tcl", "tcl8.6")
    os.environ["TK_LIBRARY"] = os.path.join(_base, "tcl", "tk8.6")

sys.path.insert(0, LAUNCHER)
os.chdir(LAUNCHER)

try:
    import tkinter as tk
except ImportError:
    sys.exit("本脚本需要带 tkinter 的 Python（当前解释器没有）。")

import 视频方案启动器 as v  # noqa: E402

fails = []


def check(cond, msg):
    print(("  PASS " if cond else "  FAIL ") + msg)
    if not cond:
        fails.append(msg)


def main():
    root = tk.Tk()
    app = v.App(root)
    for _ in range(6):
        root.update_idletasks()
        root.update()

    # 1) 部署卡搬成 mixin 后，宿主是否真的接上了
    check(hasattr(app, "_build_deploy_card"), "App 继承到 _build_deploy_card")
    check(hasattr(app, "_deploy_action") and hasattr(app, "_set_deploy_row"),
          "部署卡方法齐全（_deploy_action / _set_deploy_row）")
    check(isinstance(app, v.部署卡.部署卡), "App 实例是 部署卡 mixin 的实例")
    check(v.部署卡.CONFIG is v.CONFIG, "部署卡.CONFIG 与主程序是同一个字典")

    # 2) 部署卡真的刷出了 16 项
    rows = v.dw.deploy_inventory(v.CONFIG)
    check(len(rows) == 16, "清单 16 项（实际 %d）" % len(rows))
    print("        就绪 %d / 16" % sum(1 for r in rows if r[2] == "就绪"))
    sum_lab = getattr(app, "_deploy_sum", None)
    check(sum_lab is not None, "侧栏部署摘要控件存在")
    if sum_lab is not None:
        txt = sum_lab.cget("text")
        print("        摘要文案：%s" % txt)
        check(txt.startswith("就绪"), "摘要文案已填充")

    # 3) 日志漏斗没断：日志是「线程写队列 → 主线程 after(150) 取」两段式，
    #    单次 update 吃不到，要让事件循环真跑一会儿。
    app.log("[自检] 冒烟：这是一行测试日志", "dim")
    import time as _t
    for _ in range(20):
        root.update()
        _t.sleep(0.05)
    check("冒烟" in app.logtxt.get("1.0", "end-1c"), "日志能进日志区")

    # 4) 体积口径（1 GB = 10⁹）
    check(v.rt.human_size(20970379616) == "20.97 GB", "human_size 口径正确（20.97 GB）")

    root.update_idletasks()
    w, h = root.winfo_width(), root.winfo_height()
    print("        窗口 %dx%d" % (w, h))

    try:
        import tempfile
        from PIL import ImageGrab
        x, y = root.winfo_rootx(), root.winfo_rooty()
        shot = os.path.join(tempfile.gettempdir(), "launcher-smoke.png")
        ImageGrab.grab(bbox=(x, y, x + w, y + h)).save(shot)
        print("        截图（屏幕抓取）：%s" % shot)
    except Exception as exc:              # 截图只是留证，装不上 Pillow 不算失败
        print("        截图跳过：%r" % (exc,))

    root.destroy()
    print("\n结果：", "全部通过" if not fails else "有 %d 项失败" % len(fails))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
