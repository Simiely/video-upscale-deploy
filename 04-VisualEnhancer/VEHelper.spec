# -*- mode: python ; coding: utf-8 -*-
"""VEHelper 打包配置：单文件、无控制台，带上 sv-ttk 的主题资源。"""
from PyInstaller.utils.hooks import collect_all

sv_datas, sv_binaries, sv_hiddenimports = collect_all("sv_ttk")

a = Analysis(
    ['VEHelper.py'],
    pathex=[],
    binaries=sv_binaries,
    datas=sv_datas,
    hiddenimports=sv_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='VEHelper',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # 与 launcher 同一取舍：UPX 压缩会显著提高杀软误报率，关掉换稳定
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
