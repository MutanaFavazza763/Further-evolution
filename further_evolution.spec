# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置：单文件、无控制台窗口的 展台再进化（Further-evolution） 桌面应用。

用法：pyinstaller --clean --noconfirm further_evolution.spec
产物：dist/FurtherEvolution.exe
"""

import os

import latex2mathml

block_cipher = None

_latex2mathml_dir = os.path.dirname(latex2mathml.__file__)

a = Analysis(
    ['run.py'],
    pathex=[
        os.path.abspath('.'),
        os.path.abspath('phase0'),
    ],
    binaries=[],
    datas=[
        (os.path.join(_latex2mathml_dir, 'unimathsymbols.txt'), 'latex2mathml'),
    ],
    # phase1/pipeline.py 用「无包前缀」方式导入 phase0 模块，需显式声明
    hiddenimports=[
        'docx_builder',
        'ocrdoc_schema',
        'provider',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='FurtherEvolution',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)
