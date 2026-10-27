# -*- coding: utf-8 -*-
import os
import tempfile
import unittest

from vehelper import downloader as dl


class TestPlanRanges(unittest.TestCase):
    def test_covers_without_overlap(self):
        ranges = dl.plan_ranges(100, 0, 16)
        self.assertLessEqual(len(ranges), 16)
        self.assertEqual(ranges[0][0], 0)
        self.assertEqual(ranges[-1][1], 99)
        for prev, cur in zip(ranges, ranges[1:]):
            self.assertEqual(prev[1] + 1, cur[0])

    def test_small_total(self):
        ranges = dl.plan_ranges(5, 0, 16)
        self.assertEqual(ranges[0][0], 0)
        self.assertEqual(ranges[-1][1], 4)
        self.assertEqual(len(ranges), 5)

    def test_base_at_end(self):
        self.assertEqual(dl.plan_ranges(100, 100, 16), [])

    def test_base_middle(self):
        ranges = dl.plan_ranges(100, 50, 16)
        self.assertEqual(ranges[0][0], 50)
        self.assertEqual(ranges[-1][1], 99)

    def test_invalid_total(self):
        with self.assertRaises(ValueError):
            dl.plan_ranges(0)


class TestMerge(unittest.TestCase):
    def test_merge_and_size(self):
        with tempfile.TemporaryDirectory() as td:
            part_dir = os.path.join(td, "parts")
            os.makedirs(part_dir)
            data = [b"abc", b"de", b"fghi"]
            ranges = []
            start = 0
            for i, chunk in enumerate(data):
                with open(os.path.join(part_dir, "part%03d" % i), "wb") as f:
                    f.write(chunk)
                ranges.append((start, start + len(chunk) - 1))
                start += len(chunk)
            plan = dl.Plan(total=start, base=0, ranges=ranges, tag="v1", asset="a.zip")
            zip_path = os.path.join(td, "a.zip")
            self.assertTrue(dl.merge_parts(zip_path, part_dir, plan))
            with open(zip_path, "rb") as f:
                self.assertEqual(f.read(), b"abcdefghi")
            self.assertEqual(dl.done_bytes(part_dir, plan), 9)


class TestPlanJson(unittest.TestCase):
    def test_roundtrip(self):
        plan = dl.make_plan(100, 10, "v1", "a.zip", 4)
        again = dl.plan_from_dict(dl.plan_to_dict(plan))
        self.assertEqual(again, plan)

    def test_invalid(self):
        self.assertIsNone(dl.plan_from_dict({"total": "x"}))


if __name__ == "__main__":
    unittest.main()
