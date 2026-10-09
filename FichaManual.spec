# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

root = Path(SPECPATH)
assets = root / "assets"

a = Analysis(
    ["main.py"],
    pathex=[str(root / "src")],
    binaries=[],
    datas=[
        (str(assets / "fichamanual.ico"), "assets"),
        (str(assets / "fichamanual.png"), "assets"),
    ],
    hiddenimports=["pypdf", "openai"],
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
    [],
    exclude_binaries=True,
    name="FichaManual",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    icon=str(assets / "fichamanual.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="FichaManual",
)
