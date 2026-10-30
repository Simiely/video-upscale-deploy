# -*- coding: utf-8 -*-
"""日志文本 / 体积口径的纯函数用例。

这些断言全部来自**真实踩过的坑**，不是为覆盖率凑数：
  · human_size 曾按 1024³ 除却打印 GB，界面读数与手册/HF 页面差 7%；
  · progress_pct 曾把「宽高比 16/9」当进度，标签写成 177%；
  · strip_ansi 漏了会出现整屏方块（Tk 的 Text 不解析转义序列）。

不依赖 tkinter：任何 python 3.12+ 都能跑。
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import 运行时 as rt  # noqa: E402


class TestHumanSize(unittest.TestCase):
    def test_按十的幂换算而不是1024(self):
        # 旧的 1024 口径会分别写成 19.53 / 2.62 / 577 MB
        self.assertEqual(rt.human_size(20970379616), "20.97 GB")
        self.assertEqual(rt.human_size(2811065184), "2.81 GB")
        self.assertEqual(rt.human_size(605254808), "605 MB")

    def test_边界与零值(self):
        self.assertEqual(rt.human_size(0), "-")
        self.assertEqual(rt.human_size(None), "-")
        self.assertEqual(rt.human_size(999), "999 B")     # 以前一律显示 "0 KB"
        self.assertEqual(rt.human_size(1000), "1 KB")
        self.assertEqual(rt.human_size(10 ** 6), "1 MB")
        self.assertEqual(rt.human_size(10 ** 9), "1.00 GB")


class TestProgress(unittest.TestCase):
    def test_百分比优先(self):
        self.assertEqual(rt.progress_pct("跑批 50%"), 50)
        self.assertEqual(rt.progress_pct("100% 完成"), 100)

    def test_超过100要夹住(self):
        self.assertEqual(rt.progress_pct("177% 出错"), 100)

    def test_这些分数不是进度(self):
        """真实反例：只测正例等于没测。"""
        self.assertIsNone(rt.progress_pct("宽高比 16/9"))
        self.assertIsNone(rt.progress_pct("精度 0.0001/0.0002"))
        self.assertIsNone(rt.progress_pct("显存 7.6/12.0G"))

    def test_合法分数仍然认(self):
        self.assertEqual(rt.progress_pct("3/4 帧"), 75)
        self.assertEqual(rt.progress_pct("1/1"), 100)

    def test_没有数字(self):
        self.assertIsNone(rt.progress_pct("starting server"))


class TestAnsi(unittest.TestCase):
    def test_剥颜色码(self):
        raw = "\x1b[1m\x1b[32m[INFO]\x1b[0m 启动完成"
        self.assertEqual(rt.strip_ansi(raw), "[INFO] 启动完成")

    def test_普通行原样返回(self):
        self.assertEqual(rt.strip_ansi("[INFO] 无转义"), "[INFO] 无转义")


class TestLogLevel(unittest.TestCase):
    def test_机器级别标记(self):
        self.assertEqual(rt.log_level("[ComfyUI] [ERROR] boom"), "error")
        self.assertEqual(rt.log_level("[WARNING] 慢"), "warning")
        self.assertEqual(rt.log_level("[INFO] ok"), "info")
        self.assertEqual(rt.log_level("[DETAIL] 细节"), "detail")
        self.assertIsNone(rt.log_level("没有级别标记"))

    def test_英文日志也能上色(self):
        """ComfyUI 是英文日志，行里没有「失败/错误」这类中文关键词。"""
        self.assertEqual(rt.tag_for("[ComfyUI] [ERROR] CUDA out of memory"), "err")
        self.assertEqual(rt.tag_for("[ComfyUI] [WARNING] fallback"), "warn")

    def test_中文关键词与兜底(self):
        self.assertEqual(rt.tag_for("下载失败"), "warn")
        self.assertEqual(rt.tag_for("全部完成"), "ok")
        self.assertEqual(rt.tag_for("[工作流] 已推送"), "lw")
        self.assertEqual(rt.tag_for("[ComfyUI] 普通一行"), "dim")
        self.assertIsNone(rt.tag_for("普通一行"))


if __name__ == "__main__":
    unittest.main()
