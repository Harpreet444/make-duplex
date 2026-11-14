# -*- mode: python ; coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
# make-duplex PyInstaller specification

import os
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

added_files = [
    ('src/make_duplex/resources/*', 'make_duplex/resources'),
    ('LICENSE', '.'),
]

a = Analysis(
    ['run.py'],
    pathex=['src'],
    binaries=[],
    datas=added_files,
    hiddenimports=[
        'fitz',
        'pymupdf',
        'PyQt6',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'PyQt6.QtPrintSupport',
        'make_duplex',
        'make_duplex.engine',
        'make_duplex.printer',
        'make_duplex.ui.main_window',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='make-duplex',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    icon=os.path.abspath('src/make_duplex/resources/icon.ico'),
)
