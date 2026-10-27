# -*- coding: utf-8 -*-
import unittest

from vehelper import release
from vehelper.errors import ReleaseError


ATOM = """<?xml version="1.0"?><feed>
<entry><title>Visual Enhancer v19.5</title>
<link href="https://github.com/Merserk/dlss5-visual-enhancer/releases/tag/v19.5"/></entry>
<entry><title>Visual Enhancer v19.0</title>
<link href="https://github.com/Merserk/dlss5-visual-enhancer/releases/tag/v19.0"/></entry>
</feed>"""

ASSETS = """<div>
<a href="/Merserk/dlss5-visual-enhancer/archive/refs/tags/v19.5.zip">Source</a>
<a href="/Merserk/dlss5-visual-enhancer/releases/download/v19.5/Visual.Enhancer.v19.5.zip">zip</a>
<span>Visual.Enhancer.v19.5.zip</span>
</div>"""


class TestRelease(unittest.TestCase):
    def test_parse_latest_tag(self):
        self.assertEqual(release.parse_latest_tag(ATOM), "v19.5")

    def test_parse_latest_tag_empty(self):
        with self.assertRaises(ReleaseError):
            release.parse_latest_tag("<feed></feed>")

    def test_parse_asset_prefers_tag_name(self):
        self.assertEqual(release.parse_asset(ASSETS, "v19.5"),
                         "Visual.Enhancer.v19.5.zip")

    def test_parse_asset_ignores_archive(self):
        html = '<a href="/archive/refs/tags/v1.zip">src</a>'
        with self.assertRaises(ReleaseError):
            release.parse_asset(html, "v1")

    def test_parse_asset_custom_name(self):
        html = '<span>Visual.Enhancer-hotfix.zip</span>'
        self.assertEqual(release.parse_asset(html, "v20.0"),
                         "Visual.Enhancer-hotfix.zip")


if __name__ == "__main__":
    unittest.main()
