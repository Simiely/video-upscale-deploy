# -*- coding: utf-8 -*-
"""exe 冒烟（手动跑）：启动打包好的 exe → 确认真的开窗 → 截图 → 关掉。

**为什么它在仓库里**：这是"假发版"唯一能当场抓住的手段。两个坑都写在这里了：

1. **不能按父进程 PID 找窗口**：PyInstaller 单文件是「引导进程 + 子进程」两段，
   Tk 窗口属于子进程 —— 按父 PID 枚举永远返回空（我最初就是这么判成"没开窗"的）。
   所以这里按**窗口标题**匹配。
2. **`PrintWindow` 抓 Tk 窗口是全黑的**（GDI 合成拿不到位图）。这里先试 PrintWindow，
   整幅全黑就降级 `ImageGrab` + 置前，并在输出里明确写出用的是哪种。

跑法：
    python launcher/tests/manual/smoke_exe.py
前置：先有 `launcher/dist/ComfyUI启动器.exe`（`python launcher/发版.py ... --dry-run` 会产出）。
依赖：ctypes（标准库）；Pillow 可选，仅降级截图用。
"""
import ctypes
import ctypes.wintypes as wt
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
LAUNCHER = os.path.dirname(os.path.dirname(HERE))
EXE = os.path.join(LAUNCHER, "dist", "ComfyUI启动器.exe")
KEYWORD = "ComfyUI"

u32 = ctypes.windll.user32
g32 = ctypes.windll.gdi32
WNDENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
u32.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
u32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
u32.IsWindowVisible.argtypes = [wt.HWND]
u32.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]


def windows_of(keyword):
    """标题含 keyword 的可见顶层窗口 [(hwnd, 标题, (l,t,r,b))]。"""
    out = []

    def cb(hwnd, _lp):
        if not u32.IsWindowVisible(hwnd):
            return True
        buf = ctypes.create_unicode_buffer(512)
        u32.GetWindowTextW(hwnd, buf, 512)
        if keyword.lower() in buf.value.lower():
            rc = wt.RECT()
            u32.GetWindowRect(hwnd, ctypes.byref(rc))
            out.append((hwnd, buf.value, (rc.left, rc.top, rc.right, rc.bottom)))
        return True

    u32.EnumWindows(WNDENUMPROC(cb), 0)
    return out


def grab_printwindow(hwnd):
    """PrintWindow 抓窗口自身；返回 (w, h, 全黑?) 或用 None 表示失败。"""
    rc = wt.RECT()
    u32.GetWindowRect(hwnd, ctypes.byref(rc))
    w, h = rc.right - rc.left, rc.bottom - rc.top
    if w <= 0 or h <= 0:
        return None
    hdc = u32.GetWindowDC(hwnd)
    mdc = g32.CreateCompatibleDC(hdc)
    bmp = g32.CreateCompatibleBitmap(hdc, w, h)
    g32.SelectObject(mdc, bmp)

    class BIH(ctypes.Structure):
        _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG),
                    ("biPlanes", wt.WORD), ("biBitCount", wt.WORD),
                    ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD),
                    ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG),
                    ("biClrUsed", wt.DWORD), ("biClrImportant", wt.DWORD)]

    bi = BIH()
    bi.biSize = ctypes.sizeof(BIH)
    bi.biWidth, bi.biHeight = w, -h
    bi.biPlanes, bi.biBitCount, bi.biCompression = 1, 32, 0
    buf = ctypes.create_string_buffer(w * h * 4)
    g32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bi), 0)
    g32.DeleteObject(bmp)
    g32.DeleteDC(mdc)
    u32.ReleaseDC(hwnd, hdc)
    blank = not any(buf.raw[::4096])          # 抽样几个字节，全 0 = 没画上
    return w, h, blank, buf.raw


def save_bmp(path, w, h, raw):
    row = w * 4
    with open(path, "wb") as fh:
        fh.write(b"BM")
        fh.write((54 + row * h).to_bytes(4, "little"))
        fh.write(b"\0\0\0\0")
        fh.write((54).to_bytes(4, "little"))
        fh.write((40).to_bytes(4, "little"))
        fh.write(w.to_bytes(4, "little"))
        fh.write(h.to_bytes(4, "little"))
        fh.write((1).to_bytes(2, "little"))
        fh.write((32).to_bytes(2, "little"))
        fh.write((0).to_bytes(4, "little"))
        fh.write((row * h).to_bytes(4, "little"))
        fh.write(b"\0" * 16)
        fh.write(raw)


def main():
    if not os.path.isfile(EXE):
        print("找不到 exe：%s\n先跑 python launcher/发版.py --version ... --launcher ... --dry-run" % EXE)
        return 2
    p = subprocess.Popen([EXE])
    titles, waited = [], 0
    for waited in range(1, 26):
        time.sleep(1)
        titles = windows_of(KEYWORD)
        if titles:
            break
    print("PID=%d 等待=%ds" % (p.pid, waited))
    print("窗口: %s" % (" | ".join("%s %s" % (t[1], t[2]) for t in titles) or "（无）"))
    crash = os.path.join(os.path.dirname(EXE), "崩溃日志.log")
    print("崩溃日志: %s" % ("存在！" if os.path.exists(crash) else "无"))
    if not titles:
        p.terminate()
        print("结果: FAIL 没等到窗口")
        return 1

    hwnd, title, _rc = titles[0]
    got = grab_printwindow(hwnd)
    out = os.path.join(tempfile.gettempdir(), "launcher-exe-smoke")
    if got and not got[2]:
        save_bmp(out + ".bmp", got[0], got[1], got[3])
        print("截图: %s.bmp（PrintWindow）" % out)
    else:
        try:
            from PIL import ImageGrab
            u32.SetForegroundWindow(hwnd)
            time.sleep(0.8)
            ImageGrab.grab(bbox=_rc).save(out + ".png")
            print("截图: %s.png（PrintWindow 全黑 → 降级屏幕抓取）" % out)
        except Exception as exc:
            print("截图跳过：%r" % (exc,))

    p.terminate()
    try:
        p.wait(timeout=10)
    except subprocess.TimeoutExpired:
        p.kill()
    print("结果: PASS 窗口正常打开（%s）" % title)
    return 0


if __name__ == "__main__":
    sys.exit(main())
