# -*- mode: python ; coding: utf-8 -*-
#
# Build with the project's 32-bit venv (GW1's own process is 32-bit, and the
# injection pipeline needs same-bitness with it):
#   .venv\Scripts\python.exe -m PyInstaller Py4GW_Reforged_Launcher.spec
#
# RELAY 043: replaces the old ImGui app's spec (Analysis(['launcher.py']),
# collect_all('imgui_bundle')) now that launcher.py itself is retired.
# pywebview needs no collect_all treatment here -- unlike imgui_bundle
# (which had no dedicated PyInstaller hook at all, confirmed via the old
# spec's own comment), pywebview ships its own official hook
# (webview/__pyinstaller/hook-webview.py, auto-discovered by PyInstaller's
# standard hook-directory convention) that already bundles its WebView2
# DLLs (lib/) and JS shim (js/) on its own -- confirmed by reading that
# hook file directly, not assumed.
#
# console=False matches Launch_Reforged.bat's expected no-console-flash
# behavior for real end users (dev testing still uses a visible console via
# that .bat's own python.exe, not pythonw.exe -- see its own comments for
# why that's fine for dev and irrelevant to this packaged build).

datas = []

# pywebview_shell/web/*.html|css|js are loaded by PATH at runtime
# (run_shell.py's WEB_DIR / "index.html"), not via Python import -- the
# same "PyInstaller's static analysis can't discover non-import data on
# its own" problem the old spec's own comments describe for its two
# manual datas entries below. Confirmed via grep: nothing else under
# pywebview_shell/ is loaded by path except this directory.
datas += [('pywebview_shell/web', 'pywebview_shell/web')]

# config_defaults/ (the bundled Py4GW.ini template) -- launcher_core.
# config_seeding still references this via a plain Path join (confirmed
# via source: bridge.py -> config_seeding._mod_root(), and config_seeding
# itself joins _LAUNCHER_DIR / "config_defaults"), same real need the old
# spec's own comment already documented, unchanged by the ImGui app's
# retirement since this module is shared, not old-app-only.
datas += [('config_defaults', 'config_defaults')]

# assets/python_icon.ico is used ONLY for the icon= EXE option below (the
# .exe's own Explorer/taskbar icon) here -- deliberately NOT also added as
# a runtime datas entry the way the old spec needed, since pywebview_shell
# doesn't call anything like the old app's _apply_window_icon/WM_SETICON
# at runtime (confirmed via grep: zero matches for icon-setting code
# anywhere under pywebview_shell/) -- a real, separate gap, not silently
# assumed to already exist just because the old app had it.

a = Analysis(
    ['pywebview_shell/run_shell.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[],
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
    icon='assets/python_icon.ico',
)
