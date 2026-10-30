# -*- coding: utf-8 -*-
"""两套路径配置的一致性用例（common.ps1 ↔ 启动器 CONFIG）。

背景：`.ps1` 装环境按 `common.ps1` 的 UPSCALE_ROOT/UPSCALE_IO 走，启动器按自己的
CONFIG 找。两边互不读取（2026-10-30 核实），改了一边另一边不知道 —— 症状只是
启动自检变红，不告诉你"为什么红"。这里钉死提示逻辑：该报的报，不该报的别吵。
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import 运行时 as rt  # noqa: E402

PS = """# 配置（本文件必须 UTF-8 with BOM）
$Global:UPSCALE_ROOT = '{root}'
$Global:UPSCALE_IO   = '{io}'
"""


class TestPsParse(unittest.TestCase):
    def _mk(self, root, io_dir):
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "common.ps1"), "w", encoding="utf-8-sig") as fh:
            fh.write(PS.format(root=root, io=io_dir))
        return d

    def test_读得出两个变量(self):
        d = self._mk(r"C:\AI", r"E:\VideoUpscale")
        got = rt.ps_config_paths({"deploy_root": d})
        self.assertEqual(got["UPSCALE_ROOT"], r"C:\AI")
        self.assertEqual(got["UPSCALE_IO"], r"E:\VideoUpscale")

    def test_文件不存在(self):
        self.assertEqual(rt.ps_config_paths({"deploy_root": tempfile.gettempdir() + "/nope"}), {})

    def test_变量缺失时只返回读到的(self):
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "common.ps1"), "w", encoding="utf-8-sig") as fh:
            fh.write("$Global:UPSCALE_ROOT = 'D:\\AI'\n")
        got = rt.ps_config_paths({"deploy_root": d})
        self.assertEqual(list(got), ["UPSCALE_ROOT"])


class TestDrift(unittest.TestCase):
    def _cfg(self, root, io_dir, comfy, inp, out):
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "common.ps1"), "w", encoding="utf-8-sig") as fh:
            fh.write(PS.format(root=root, io=io_dir))
        return {"deploy_root": d, "comfy_dir": comfy, "input_dir": inp, "output_dir": out}

    def test_一致时不吵(self):
        base = tempfile.mkdtemp()
        cfg = self._cfg(os.path.join(base, "AI"), os.path.join(base, "IO"),
                        os.path.join(base, "AI", "ComfyUI"),
                        os.path.join(base, "IO", "input"),
                        os.path.join(base, "IO", "output"))
        self.assertEqual(rt.config_drift_lines(cfg), [])

    def test_comfy_dir_不在_root下要提示(self):
        base = tempfile.mkdtemp()
        cfg = self._cfg(os.path.join(base, "AI"), os.path.join(base, "IO"),
                        os.path.join(base, "OTHER", "ComfyUI"),
                        os.path.join(base, "IO", "input"),
                        os.path.join(base, "IO", "output"))
        lines = rt.config_drift_lines(cfg)
        self.assertEqual(len(lines), 1)
        self.assertIn("UPSCALE_ROOT", lines[0][0])
        self.assertEqual(lines[0][1], "warn")

    def test_输出目录跑偏要提示(self):
        base = tempfile.mkdtemp()
        cfg = self._cfg(os.path.join(base, "AI"), os.path.join(base, "IO"),
                        os.path.join(base, "AI", "ComfyUI"),
                        os.path.join(base, "IO", "input"),
                        os.path.join(base, "ELSEWHERE", "out"))
        lines = rt.config_drift_lines(cfg)
        self.assertEqual(len(lines), 1)
        self.assertIn("输出目录", lines[0][0])

    def test_前缀相同但不是子目录不算一致(self):
        """"/a/AI2" 以 "/a/AI" 开头，但不是它的子目录 —— 不能用裸 startswith。"""
        base = tempfile.mkdtemp()
        cfg = self._cfg(os.path.join(base, "AI"), os.path.join(base, "IO"),
                        os.path.join(base, "AI2", "ComfyUI"),
                        os.path.join(base, "IO", "input"),
                        os.path.join(base, "IO", "output"))
        self.assertEqual(len(rt.config_drift_lines(cfg)), 1)

    def test_没有ps1时安静(self):
        cfg = {"deploy_root": tempfile.mkdtemp(), "comfy_dir": "X:/whatever"}
        self.assertEqual(rt.config_drift_lines(cfg), [])


class TestStartupIntegration(unittest.TestCase):
    def test_启动自检末尾会带上漂移提示(self):
        base = tempfile.mkdtemp()
        d = os.path.join(base, "dep")
        os.makedirs(d)
        with open(os.path.join(d, "common.ps1"), "w", encoding="utf-8-sig") as fh:
            fh.write(PS.format(root=os.path.join(base, "AI"), io=os.path.join(base, "IO")))
        cfg = {"deploy_root": d, "comfy_dir": os.path.join(base, "OTHER"),
               "input_dir": os.path.join(base, "IO", "in"),
               "output_dir": os.path.join(base, "IO", "out")}
        lines = rt.startup_lines(cfg)
        self.assertEqual(len(lines), len(rt.STARTUP_PROBES) + 1)   # 6 项探测 + 1 条提示
        self.assertIn("UPSCALE_ROOT", lines[-1][0])


if __name__ == "__main__":
    unittest.main()
