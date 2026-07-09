# -*- mode: python ; coding: utf-8 -*-
#
# Build with the project's 32-bit venv (imgui_bundle has no 64-bit wheel for it and
# the GW1 injection pipeline needs same-bitness with GW1's own 32-bit process):
#   C:\Users\Chris\Projects\Py4GW\myenv\Scripts\python.exe -m PyInstaller Py4GW_Reforged_Launcher.spec
#
# collect_all('imgui_bundle') is required, not optional -- imgui_bundle has no
# dedicated PyInstaller hook, and a bare Analysis() misses its compiled extension
# module's sibling DLL (glfw3.dll) and its data assets (fonts, default app_settings)
# since PyInstaller's static import analysis can't discover non-Python data/binary
# files on its own. console=False matches Launch.bat's pythonw.exe behavior (no
# console flash) -- see launcher.py's top-of-file startup guard for how failures
# still get reported via a message box despite that.
from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = []
tmp_ret = collect_all('imgui_bundle')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['launcher.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    name='Py4GW_Reforged_Launcher',
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
)
