# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

block_cipher = None

added_files = [
    ('ui/dist', 'ui/dist'),
    ('icon.ico', '.'),
    ('branding', 'branding'),
]

hidden_imports = [
    'webview',
    'webview.platforms.winforms',
    'webview.platforms.edgechromium',
    'clr',
    'miniaudio',
    'pypdf',
    'py7zr',
    'rarfile',
    'PIL',
    'PIL.Image',
    'send2trash',
]

a = Analysis(
    ['organizer.py'],
    pathex=['.'],
    binaries=[],
    datas=added_files,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# 1. Standalone Portable Single Executable
exe_portable = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='FoldersOrganizerPro_Portable',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',
)