@echo off
REM Double-click entry point for ad-hoc testing -- runs launcher.py with the
REM project's actual 32-bit venv (imgui_bundle is built for it specifically,
REM the system Python won't have it). Uses pythonw.exe so no console window
REM flashes up alongside the app. %~dp0 resolves to this .bat's own folder,
REM so it works regardless of where it's double-clicked from.
start "" "C:\Users\Chris\Projects\Py4GW\myenv\Scripts\pythonw.exe" "%~dp0launcher.py"
