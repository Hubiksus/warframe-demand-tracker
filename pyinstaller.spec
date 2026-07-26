# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['wf_tracker/main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('wf_tracker/templates/*', 'templates'),
        ('wf_tracker/sources/*', 'sources'),
        ('wf_tracker/cache/*', 'cache'),
        ('wf_tracker/output/*', 'output'),
    ],
    hiddenimports=[],
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
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='wf_tracker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name='wf_tracker',
)
