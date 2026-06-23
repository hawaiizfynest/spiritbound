# Spiritbound - PyInstaller build spec.
#
# Build the one-file EXE with:
#
#     python build_icon.py            (renders spiritbound.ico - optional)
#     pyinstaller Spiritbound.spec
#
# Unlike a bare PyInstaller command, this spec bundles the whole `assets/`
# folder (music, sound effects, and any sprite art) INTO the EXE via `datas`,
# so audio and sprites work in the packaged build. The output is
# dist/Spiritbound.exe.
import os

from PyInstaller.utils.hooks import collect_submodules

_icon = "spiritbound.ico" if os.path.exists("spiritbound.ico") else None

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[("assets", "assets")],          # <-- bundles music / sfx / sprites
    hiddenimports=collect_submodules("game"),
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
    name="Spiritbound",
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
    icon=_icon,
)
