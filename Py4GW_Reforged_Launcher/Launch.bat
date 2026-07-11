@echo off
REM Double-click entry point for ad-hoc dev testing. Runs launcher.py from a
REM 32-bit venv created at .venv INSIDE this folder (py -3.13-32 -m venv .venv;
REM see requirements.txt for dependency setup). %~dp0 makes it work on any
REM machine -- no hardcoded personal path.
REM
REM Uses python.exe (console), not pythonw.exe, on purpose: this venv's
REM pythonw.exe is a stub that re-execs into console python.exe anyway, so it
REM can't actually avoid a console -- confirmed on a freshly-created .venv too
REM (see launcher-console-window-diagnosis in project memory). A visible console
REM during dev testing, showing live [gw1_launch] launch/injection log lines, is
REM useful, not a problem. The real "no console for actual users" requirement is
REM solved independently by Py4GW_Reforged_Launcher.spec's console=False for the
REM packaged exe; this file has never affected that.
start "" "%~dp0.venv\Scripts\python.exe" "%~dp0launcher.py"
