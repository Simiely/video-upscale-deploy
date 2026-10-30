# -*- coding: utf-8 -*-
"""部署清单 / 探测 / 代理策略的用例。

重点守两件容易退化的东西：
  1. `expect` / `sha256` 的**元组归一**（清单里 None / 整数 / 元组三种写法混用，
     归一错了会把两个文件的大小错配，UI 上的「不完整」判定就全乱）；
  2. `deploy_inventory` 的三态状态机（就绪 / 不完整 / 缺失）——2026-10-30 之前
     verify_deploy 只在临时目录里"看一眼"，没有断言，改坏了也没人知道。
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import 部署下载 as dw  # noqa: E402
import 部署清单 as dl  # noqa: E402


class TestExpectNormalize(unittest.TestCase):
    def test_expect_none_整数_元组(self):
        self.assertEqual(dl.expects_of({"check": ("a", "b"), "expect": None}), [None, None])
        self.assertEqual(dl.expects_of({"check": ("a", "b"), "expect": 7}), [7, 7])
        self.assertEqual(dl.expects_of({"check": ("a", "b"), "expect": (1, 2)}), [1, 2])

    def test_元组长短不齐要补齐截断(self):
        self.assertEqual(dl.expects_of({"check": ("a", "b"), "expect": (1,)}), [1, None])
        self.assertEqual(dl.expects_of({"check": ("a",), "expect": (1, 2)}), [1])

    def test_sha256_同样归一(self):
        self.assertEqual(dl.sha256_of({"check": ("a",), "sha256": "x"}), ["x"])
        self.assertEqual(dl.sha256_of({"check": ("a", "b")}), [None, None])
        self.assertEqual(dl.sha256_of({"check": ("a", "b"), "sha256": ("s",)}), ["s", None])


class TestHfPaths(unittest.TestCase):
    def test_默认推导去掉models前缀(self):
        item = {"check": ("models/diffusion_models/x.safetensors",)}
        self.assertEqual(dl.hf_paths_of(item), ["diffusion_models/x.safetensors"])

    def test_显式覆盖优先(self):
        """SeedVR2 的权重在仓库根目录、本地却在 models/SEEDVR2/ 下 —— 推导会 404。"""
        item = {"check": ("models/SEEDVR2/x.safetensors",),
                "hf_path": "x.safetensors"}
        self.assertEqual(dl.hf_paths_of(item), ["x.safetensors"])
        item2 = {"check": ("models/a", "models/b"), "hf_path": ["a", "b"]}
        self.assertEqual(dl.hf_paths_of(item2), ["a", "b"])

    def test_真实清单里SeedVR2两项都写了覆盖(self):
        for key in ("w_seedvr2_fp8", "w_seedvr2_vae"):
            it = dl.by_key(key)
            self.assertIn("hf_path", it, "%s 缺 hf_path 会按 models/ 前缀推导出 404 路径" % key)
            self.assertNotIn("/", dl.hf_paths_of(it)[0])

    def test_真实清单H3仍走推导(self):
        self.assertEqual(dl.hf_paths_of(dl.by_key("w_h3_dit")),
                         ["diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors"])


class TestInventory(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.comfy = os.path.join(self.tmp, "comfy")
        os.makedirs(os.path.join(self.comfy, "models", "SEEDVR2"))
        os.makedirs(os.path.join(self.comfy, "custom_nodes"))

    def _rows(self):
        cfg = {"comfy_dir": self.comfy, "ffmpeg_dir": ""}
        return {r[0]: r for r in dw.deploy_inventory(cfg)}

    def test_缺失(self):
        self.assertEqual(self._rows()["node_manager"][2], "缺失")

    def test_不完整_文件在但太小(self):
        p = os.path.join(self.comfy, "models", "SEEDVR2", "seedvr2_ema_3b_fp8_e4m3fn.safetensors")
        with open(p, "w") as fh:
            fh.write("x" * 100)
        row = self._rows()["w_seedvr2_fp8"]
        self.assertEqual(row[2], "不完整")
        self.assertIn("大小不足", row[3])

    def test_就绪_文件够大(self):
        p = os.path.join(self.comfy, "models", "SEEDVR2", "ema_vae_fp16.safetensors")
        with open(p, "wb") as fh:                       # 稀疏文件：只占元数据，秒建
            fh.truncate(501324814)
        row = self._rows()["w_seedvr2_vae"]
        self.assertEqual(row[2], "就绪")
        self.assertEqual(row[5], 501324814)             # 实际大小

    def test_返回七元组(self):
        self.assertEqual(len(self._rows()["comfy_base"]), 7)

    def test_根目录不存在时判缺失并说明(self):
        cfg = {"comfy_dir": os.path.join(self.tmp, "nope"), "ffmpeg_dir": ""}
        row = {r[0]: r for r in dw.deploy_inventory(cfg)}["comfy_base"]
        self.assertEqual(row[2], "缺失")


class TestProxyPolicy(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("HF_PROXY", None)

    def test_ModelScope_永远直连(self):
        os.environ.pop("HF_PROXY", None)
        self.assertEqual(dw.proxy_for("ModelScope"), "")

    def test_境外源跟随探测结果(self):
        os.environ.pop("HF_PROXY", None)
        expected = dw.detect_proxy()[0]
        self.assertEqual(dw.proxy_for("hf-mirror"), expected)

    def test_显式指定对所有源生效(self):
        os.environ["HF_PROXY"] = "http://127.0.0.1:1080"
        self.assertEqual(dw.proxy_for("ModelScope"), "http://127.0.0.1:1080")
        self.assertEqual(dw.proxy_for("hf-mirror"), "http://127.0.0.1:1080")

    def test_none_全部直连(self):
        os.environ["HF_PROXY"] = "none"
        self.assertEqual(dw.proxy_for("ModelScope"), "")
        self.assertEqual(dw.proxy_for("hf-mirror"), "")


class TestDiskCheck(unittest.TestCase):
    def test_need_取_expect_之和(self):
        item = dict(dl.by_key("w_h3_vae"))
        ok, free, need, root = dw.disk_check({"comfy_dir": tempfile.gettempdir()}, item)
        self.assertEqual(need, 2811065184 + 605254808)
        self.assertTrue(isinstance(free, int) and free >= 0)
        self.assertTrue(ok)

    def test_体积未知时给0不假装知道(self):
        item = dict(dl.by_key("comfy_base"))
        ok, _free, need, _root = dw.disk_check({"comfy_dir": tempfile.gettempdir()}, item)
        self.assertEqual(need, 0)
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()


class TestRestoreWorkflows(unittest.TestCase):
    """「恢复」铺的是 API 图，ComfyUI 目录里的同名文件是画布原件 —— 撞名会毁数据。"""

    def setUp(self):
        base = tempfile.mkdtemp()
        self.dep = os.path.join(base, "dep")
        os.makedirs(os.path.join(self.dep, "workflows"))
        self.comfy = os.path.join(base, "comfy")
        self.wfdir = os.path.join(self.comfy, "user", "default", "workflows")
        os.makedirs(self.wfdir)
        self.fn = "FlashVSR-放大2x-有声素材.json"
        with open(os.path.join(self.dep, "workflows", self.fn), "w", encoding="utf-8") as fh:
            json.dump({"1": {"class_type": "X"}}, fh)                     # API 格式
        self.canvas = os.path.join(self.wfdir, self.fn)
        with open(self.canvas, "w", encoding="utf-8") as fh:
            json.dump({"nodes": [], "links": []}, fh)                     # 画布原件（UI 格式）
        self.canvas_bytes = open(self.canvas, "rb").read()
        self.cfg = {"deploy_root": self.dep, "comfy_dir": self.comfy}

    def test_铺出来的文件带前缀(self):
        copied, _skipped, _msg = dw.restore_workflows(self.cfg)
        self.assertEqual(copied, 1)
        self.assertTrue(os.path.exists(
            os.path.join(self.wfdir, dw.WORKFLOW_PREFIX + self.fn)))

    def test_画布原件一字节不动(self):
        dw.restore_workflows(self.cfg)
        self.assertEqual(open(self.canvas, "rb").read(), self.canvas_bytes)

    def test_再点一次是幂等跳过(self):
        dw.restore_workflows(self.cfg)
        copied, skipped, _msg = dw.restore_workflows(self.cfg)
        self.assertEqual((copied, skipped), (0, 1))

    def test_清单判定认前缀名(self):
        rows = {r[0]: r for r in dw.deploy_inventory(self.cfg)}
        self.assertEqual(rows["workflows"][2], "缺失")        # 只有画布原件，没有带前缀的 API 图
        dw.restore_workflows(self.cfg)
        rows = {r[0]: r for r in dw.deploy_inventory(self.cfg)}
        self.assertEqual(rows["workflows"][2], "就绪")


if __name__ == "__main__":
    unittest.main()
