# -*- coding: utf-8 -*-
"""工作流图的取用与参数注入用例（纯逻辑，不起 ComfyUI）。

这里守的是"推送前改图"的三件事：认格式、换素材、按类名覆盖参数。
写错不会报错、只会在 ComfyUI 里静默用默认值，所以在本地就该钉死。
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import 运行时 as rt  # noqa: E402


class TestGraphDetect(unittest.TestCase):
    def test_api格式(self):
        self.assertFalse(rt.is_ui_graph({"1": {"class_type": "KSampler", "inputs": {}}}))

    def test_ui格式(self):
        self.assertTrue(rt.is_ui_graph({"nodes": [{"id": 1}], "links": []}))

    def test_裹在api里的ui格式(self):
        self.assertTrue(rt.is_ui_graph({"api": {"nodes": [{"id": 1}]}}))

    def test_非dict(self):
        self.assertFalse(rt.is_ui_graph([]))
        self.assertFalse(rt.is_ui_graph(None))

    def test_节点计数(self):
        api = {"1": {}, "2": {}, "3": {}}
        self.assertEqual(rt.api_node_count(api), 3)
        self.assertEqual(rt.api_node_count({"nodes": [{}, {}]}), 2)
        self.assertEqual(rt.api_node_count({"api": {"nodes": [{}]}}), 1)
        self.assertEqual(rt.api_node_count(None), 0)


class TestApplyInput(unittest.TestCase):
    def test_两种载入节点都换(self):
        api = {
            "1": {"class_type": "VHS_LoadVideoPath", "inputs": {"video": "old.mp4"}},
            "2": {"class_type": "LoadVideoPath", "inputs": {"video": "old.mp4"}},
            "3": {"class_type": "KSampler", "inputs": {}},
        }
        n = rt.apply_input(api, "E:/in/new.mp4")
        self.assertEqual(n, 2)
        self.assertEqual(api["1"]["inputs"]["video"], "E:/in/new.mp4")
        self.assertEqual(api["2"]["inputs"]["video"], "E:/in/new.mp4")
        self.assertNotIn("video", api["3"]["inputs"])

    def test_空素材不动图(self):
        api = {"1": {"class_type": "VHS_LoadVideoPath", "inputs": {"video": "old.mp4"}}}
        self.assertEqual(rt.apply_input(api, ""), 0)
        self.assertEqual(api["1"]["inputs"]["video"], "old.mp4")

    def test_带引号的路径会剥掉(self):
        api = {"1": {"class_type": "LoadVideoPath", "inputs": {}}}
        rt.apply_input(api, '"E:/in/a b.mp4"')
        self.assertEqual(api["1"]["inputs"]["video"], "E:/in/a b.mp4")


class TestApplyPatch(unittest.TestCase):
    def test_按类名覆盖参数(self):
        api = {"1": {"class_type": "FlashVSRNode", "inputs": {"scale": 2}},
               "2": {"class_type": "Other", "inputs": {"scale": 2}}}
        self.assertEqual(rt.apply_patch(api, {"FlashVSRNode": {"scale": 4}}), 1)
        self.assertEqual(api["1"]["inputs"]["scale"], 4)
        self.assertEqual(api["2"]["inputs"]["scale"], 2)   # 别的节点不许误伤

    def test_空补丁(self):
        api = {"1": {"class_type": "X", "inputs": {}}}
        self.assertEqual(rt.apply_patch(api, {}), 0)
        self.assertEqual(rt.apply_patch(api, None), 0)


class TestApplyInputImage(unittest.TestCase):
    def test_图里没有LoadImage就原样返回(self):
        api = {"1": {"class_type": "VHS_LoadVideoPath", "inputs": {}}}
        self.assertEqual(rt.apply_input_image(api, "E:/in/a.mp4", {}), (0, ""))

    def test_有LoadImage但没选素材要给提醒(self):
        api = {"1": {"class_type": "LoadImage", "inputs": {}}}
        n, warn = rt.apply_input_image(api, "", {})
        self.assertEqual(n, 0)
        self.assertIn("首帧", warn)


class TestReadWorkflow(unittest.TestCase):
    def test_文件不存在(self):
        data, err = rt.read_workflow(os.path.join(tempfile.gettempdir(), "不存在的图.json"))
        self.assertIsNone(data)
        self.assertIn("不存在", err)

    def test_坏JSON(self):
        p = os.path.join(tempfile.mkdtemp(), "bad.json")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("{不是 json")
        data, err = rt.read_workflow(p)
        self.assertIsNone(data)
        self.assertIn("解析失败", err)

    def test_正常读取(self):
        p = os.path.join(tempfile.mkdtemp(), "ok.json")
        with open(p, "w", encoding="utf-8") as fh:
            json.dump({"1": {"class_type": "X"}}, fh)
        data, err = rt.read_workflow(p)
        self.assertEqual(err, "")
        self.assertIn("1", data)

    def test_内容不是对象(self):
        p = os.path.join(tempfile.mkdtemp(), "list.json")
        with open(p, "w", encoding="utf-8") as fh:
            json.dump([1, 2], fh)
        data, err = rt.read_workflow(p)
        self.assertIsNone(data)
        self.assertIn("不是 JSON 对象", err)


if __name__ == "__main__":
    unittest.main()
