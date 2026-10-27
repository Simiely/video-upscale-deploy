# -*- coding: utf-8 -*-
"""安装：解压官方 zip，并定位 Visual Enhancer.exe。"""
import os
import zipfile

from .errors import InstallError


def extract(zip_path, dest):
    try:
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(dest)
    except (OSError, zipfile.BadZipFile) as exc:
        raise InstallError("解压失败：%s" % exc) from exc


def find_ve(root):
    gui = cli = ""
    for base, _dirs, files in os.walk(root or ""):
        for name in files:
            low = name.lower()
            if low == "visual enhancer.exe":
                gui = os.path.join(base, name)
            elif low == "ve_cli.exe":
                cli = os.path.join(base, name)
    return gui, cli


def install(zip_path, target):
    extract(zip_path, target)
    gui, _cli = find_ve(target)
    if not gui:
        raise InstallError("解压后没找到 Visual Enhancer.exe")
    return os.path.dirname(gui)
