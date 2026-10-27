# -*- coding: utf-8 -*-
"""配置读写：默认放在 exe 旁边，保持便携。"""
import json
import os
import sys

APP_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
CFG_PATH = os.path.join(APP_DIR, "ve_helper_config.json")

DEFAULT_CFG = {"ve_dir": r"D:\Tool\VisualEnhancer"}


def load_cfg(path=CFG_PATH):
    cfg = dict(DEFAULT_CFG)
    try:
        with open(path, "r", encoding="utf-8") as f:
            cfg.update(json.load(f))
    except (OSError, ValueError):
        pass
    return cfg


def save_cfg(cfg, path=CFG_PATH):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except OSError:
        pass
