"""Find a process's window and bring it to the foreground.

Port of GWxLauncher/Services/Gw2AutoLoginService.cs's ForceForeground -- same calls,
same order, same AttachThreadInput-around-SetForegroundWindow workaround for Windows'
foreground-lock restriction (a plain SetForegroundWindow call is routinely ignored by
Windows unless the calling thread is attached to the current foreground thread's
input queue). Confirmed this is pure Win32 API work with no ImGui-side limitation.
"""

from __future__ import annotations

import ctypes
import os
from typing import Optional

import psutil
import pywintypes
import win32gui
import win32process

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

SW_RESTORE = 9

WM_SETICON = 0x0080
ICON_SMALL = 0
ICON_BIG = 1
IMAGE_ICON = 1
LR_LOADFROMFILE = 0x00000010
SM_CXICON = 11
SM_CYICON = 12
SM_CXSMICON = 49
SM_CYSMICON = 50


def set_window_icon(hwnd: int, icon_path: str) -> bool:
    """Load `icon_path` (.ico) and apply it as `hwnd`'s title-bar/taskbar icon via
    WM_SETICON. hello_imgui/imgui_bundle's RunnerParams has no window-icon option
    (checked directly, see launcher.py's post_init wiring), so this is the documented
    fallback: raw ctypes rather than pywin32's LoadImage wrapper, since loading both
    the small and large icon sizes from one .ico file in one call isn't something
    the wrapper cleanly exposes. Returns False (rather than raising) if the file is
    missing or fails to load -- a missing icon shouldn't be fatal to starting the app.
    """
    cx_small, cy_small = user32.GetSystemMetrics(SM_CXSMICON), user32.GetSystemMetrics(SM_CYSMICON)
    cx_big, cy_big = user32.GetSystemMetrics(SM_CXICON), user32.GetSystemMetrics(SM_CYICON)

    h_small = user32.LoadImageW(None, icon_path, IMAGE_ICON, cx_small, cy_small, LR_LOADFROMFILE)
    h_big = user32.LoadImageW(None, icon_path, IMAGE_ICON, cx_big, cy_big, LR_LOADFROMFILE)

    if h_small:
        user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, h_small)
    if h_big:
        user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, h_big)

    return bool(h_small or h_big)


def find_running_pid_for_exe_path(exe_path: str, exclude_pids: Optional[set] = None) -> Optional[int]:
    """Find a running process whose real executable matches `exe_path` exactly
    (case-insensitive, normalized). Port of GWxLauncher's
    Gw1InstanceTracker.FindProcessesByExactPath (Services/Gw1InstanceTracker.cs:187-201):
    filter candidates by process name first (cheap), then confirm with an exact,
    normalized path match against each survivor's real module path.

    Used to rehydrate "this profile is already running" state for processes this
    launcher didn't itself start -- manual launch, Launch.bat, the old C# launcher,
    or a previous session of this same app that's since closed. `exclude_pids` lets
    a caller matching several profiles in one pass avoid assigning the same PID to
    more than one profile (e.g. two profiles that happen to share an exe path).
    """
    if not exe_path:
        return None

    target_path = os.path.normcase(os.path.abspath(exe_path))
    target_name = os.path.splitext(os.path.basename(exe_path))[0].lower()
    exclude_pids = exclude_pids or set()

    for proc in psutil.process_iter(["pid", "name", "exe"]):
        try:
            if proc.info["pid"] in exclude_pids:
                continue
            name = proc.info["name"] or ""
            if os.path.splitext(name)[0].lower() != target_name:
                continue
            proc_exe = proc.info["exe"]
            if not proc_exe or os.path.normcase(os.path.abspath(proc_exe)) != target_path:
                continue
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

        return proc.info["pid"]

    return None


def find_visible_window_for_pid(pid: int) -> Optional[int]:
    """Return the first visible top-level window handle owned by `pid`, or None."""
    found: list = []

    def enum_windows_callback(hwnd, _):
        try:
            if win32gui.IsWindowVisible(hwnd):
                _, window_pid = win32process.GetWindowThreadProcessId(hwnd)
                if window_pid == pid:
                    found.append(hwnd)
        except pywintypes.error:
            # A window can be destroyed mid-enumeration (e.g. mid-teardown during a
            # relaunch); skip it rather than letting one bad handle crash the whole
            # enumeration -- pywin32 mangles exceptions raised inside this callback
            # into a misleading generic EnumWindows error otherwise.
            pass
        # Deliberately always return True (never stop early): returning False from an
        # EnumWindows callback makes the underlying Win32 call itself report failure
        # (by design, that's how you signal "stop enumerating"), which pywin32 then
        # surfaces as a generic, misleading EnumWindows exception -- this is what
        # actually crashed the app, not a destroyed-window race. Collecting every
        # match and taking the first afterward avoids the early-exit trigger entirely.
        return True

    win32gui.EnumWindows(enum_windows_callback, None)
    return found[0] if found else None


def set_window_title(hwnd: int, title: str) -> bool:
    """Set `hwnd`'s window title (SetWindowTextW). Returns True on success.

    Purely cosmetic, for human clarity in the Windows taskbar/Alt-Tab when multiple
    clients are running at once -- our own instance tracking
    (`find_visible_window_for_pid`) is PID-based and never depends on window title,
    so a failure here has no effect on tracking correctness.
    """
    return bool(user32.SetWindowTextW(hwnd, title))


def foreground_window(hwnd: int) -> None:
    """Bring `hwnd` to the foreground, restoring it first if minimized.

    Best-effort: Windows can still refuse in some edge cases (e.g. another app
    actively holding foreground lock harder than this workaround accounts for);
    this mirrors the reference implementation's behavior exactly rather than
    adding extra retry logic that implementation doesn't have.
    """
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)

    user32.SetForegroundWindow(hwnd)
    user32.BringWindowToTop(hwnd)

    foreground_hwnd = user32.GetForegroundWindow()
    foreground_tid, _ = win32process.GetWindowThreadProcessId(foreground_hwnd)
    my_tid = kernel32.GetCurrentThreadId()
    target_tid, _ = win32process.GetWindowThreadProcessId(hwnd)

    user32.AttachThreadInput(my_tid, foreground_tid, True)
    user32.AttachThreadInput(my_tid, target_tid, True)
    try:
        user32.SetForegroundWindow(hwnd)
        user32.SetFocus(hwnd)
    finally:
        user32.AttachThreadInput(my_tid, target_tid, False)
        user32.AttachThreadInput(my_tid, foreground_tid, False)
