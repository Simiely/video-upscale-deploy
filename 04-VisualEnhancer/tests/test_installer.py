# -*- coding: utf-8 -*-
import os
import tempfile
import unittest
import zipfile

from vehelper import installer
from vehelper.errors import InstallError


class TestInstaller(unittest.TestCase):
    def test_extract_and_find(self):
        with tempfile.TemporaryDirectory() as td:
            zip_path = os.path.join(td, "pkg.zip")
            with zipfile.ZipFile(zip_path, "w") as z:
                z.writestr("VisualEnhancer/Visual Enhancer.exe", b"x")
                z.writestr("VisualEnhancer/VE_CLI.exe", b"x")
            dest = os.path.join(td, "out")
            installer.extract(zip_path, dest)
            gui, cli = installer.find_ve(dest)
            self.assertTrue(gui.endswith("Visual Enhancer.exe"))
            self.assertTrue(cli.endswith("VE_CLI.exe"))

    def test_missing_exe(self):
        with tempfile.TemporaryDirectory() as td:
            zip_path = os.path.join(td, "pkg.zip")
            with zipfile.ZipFile(zip_path, "w") as z:
                z.writestr("readme.txt", b"x")
            with self.assertRaises(InstallError):
                installer.install(zip_path, os.path.join(td, "out"))

    def test_bad_zip(self):
        with tempfile.TemporaryDirectory() as td:
            bad = os.path.join(td, "bad.zip")
            with open(bad, "wb") as f:
                f.write(b"not a zip")
            with self.assertRaises(InstallError):
                installer.extract(bad, td)


if __name__ == "__main__":
    unittest.main()
