# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 构建配置文件 — MC命令生成器

使用方法：
    pyinstaller main.spec

输出位置：dist/MC命令生成器/
"""

import sys
from pathlib import Path

_block_cipher = None

# 项目根目录（spec 文件所在目录）
_here = Path(SPECPATH).resolve()  # type: ignore[name-defined]  # noqa: F821

# ── 需要打包的外部资源 ──
_datas = [
    (str(_here / "data"), "data"),                         # 所有数据文件（效果/附魔/组件/物品/纹理）
    (str(_here / "unifont-16.0.02.otf"), "."),             # Unifont 字体
    (str(_here / "custom"), "custom"),                     # 自定义预设目录（打包空壳）
]

# ── 隐式导入（PyQt6 常见缺失项）──
_hiddenimports = [
    "PyQt6.QtGui",
    "PyQt6.QtCore",
    "PyQt6.QtWidgets",
]

a = Analysis(
    [str(_here / "main.py")],
    pathex=[],
    binaries=[],
    datas=_datas,
    hiddenimports=_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=_block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=_block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="MC命令生成器",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,                   # --noconsole
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(_here / "command_generator.ico"),    # 应用程序图标
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="MC命令生成器",
)
