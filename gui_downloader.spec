# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, collect_data_files, collect_dynamic_libs

# Collect all pymupdf related modules and files
pymupdf_imports = collect_submodules('pymupdf')
pymupdf_datas = collect_data_files('pymupdf', include_py_files=True)
pymupdf_binaries = collect_dynamic_libs('pymupdf')

# Manually add pymupdf extension files if not collected
if sys.platform == 'win32':
    venv_path = Path('.venv/lib/site-packages/pymupdf')
    if venv_path.exists():
        for ext_file in ['_mupdf.pyd', '_extra.pyd', 'mupdfcpp64.dll']:
            ext_path = venv_path / ext_file
            if ext_path.exists():
                pymupdf_binaries.append((str(ext_path), 'pymupdf'))

a = Analysis(
    ['gui_downloader.py'],
    pathex=[],
    binaries=pymupdf_binaries,
    datas=pymupdf_datas,
    hiddenimports=pymupdf_imports + [
        'pymupdf',
        'pymupdf._mupdf',
        'pymupdf.mupdf',
        'pymupdf._extra',
        'pymupdf.extra',
        'pymupdf._build',
        'pymupdf.table',
        'pymupdf.utils',
        'PyInquirer',
        'prompt_toolkit',
        'prompt_toolkit.formatted_text',
        'prompt_toolkit.styles',
        'lxml',
        'lxml.etree',
        'lxml._elementpath',
        'bs4',
        'beautifulsoup4',
        'requests',
        'PySide6',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['pyi_rth_pymupdf.py'],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='gui_downloader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='gui_downloader',
)
