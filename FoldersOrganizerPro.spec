# -*- mode: python ; coding: utf-8 -*-
import sys
import os
import re
import subprocess
from pathlib import Path

block_cipher = None

# Dynamically generate active version info with current git commit SHA
spec_dir = Path(SPECPATH) if 'SPECPATH' in globals() else Path('.').resolve()
build_dir = spec_dir / 'build'
build_dir.mkdir(exist_ok=True)

try:
    commit_sha = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], cwd=str(spec_dir), text=True).strip()
except Exception:
    commit_sha = "139094a"

version_template = spec_dir / 'file_version_info.txt'
active_version_file = build_dir / 'file_version_info_active.txt'
if version_template.exists():
    raw_content = version_template.read_text(encoding='utf-8')
    updated_content = re.sub(r"StringStruct\('Comments',\s*'Commit [^']*'\)", f"StringStruct('Comments', 'Commit {commit_sha}')", raw_content)
    active_version_file.write_text(updated_content, encoding='utf-8')
    version_file_to_use = str(active_version_file)
else:
    version_file_to_use = str(version_template)

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
    version=version_file_to_use,
)