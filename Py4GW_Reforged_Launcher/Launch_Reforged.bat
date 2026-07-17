@echo off
REM Double-click entry point for the NEW pywebview-based launcher
REM (pywebview_shell/, RELAY 010+) -- Launch.bat still points at the old
REM imgui launcher.py; there's no packaged .exe for this version yet.
REM
REM Must run via `-m` (not `python run_shell.py` directly) so
REM `pywebview_shell` resolves as a package from the project root instead of
REM putting pywebview_shell/ itself on sys.path -- see run_shell.py's own
REM docstring and elevation.py's relaunch_elevated() for why this exact
REM invocation form matters (RELAY 035 reconstructs it verbatim for its own
REM elevated relaunch).
REM
REM cd /d first so this resolves correctly regardless of Explorer's starting
REM working directory. Deliberately NOT elevated itself -- RELAY 035's own
REM "run as administrator" toggle is what should trigger a real UAC prompt
REM when tested, not this shortcut.
cd /d "%~dp0"
start "" "%~dp0.venv\Scripts\python.exe" -m pywebview_shell.run_shell
