"""GW1 launch pipeline: CreateProcessW (suspended) -> multiclient patch -> resume ->
handle the updater/relaunch handoff -> wait for window -> inject a DLL.

Adapted from the proven primitives already in this repo's root ``Patcher.py`` and
``Py4GW_Launcher.py`` (``Patcher.patch``/``launch_and_patch``, ``GWLauncher.inject_dll``/
``wait_for_gw_window``) -- same ctypes calls, same signature bytes, same offsets. Not a
rewrite: this only reshapes that logic around a ``GameProfile`` input and a single
``LaunchResult`` return value instead of the launcher's global ``log_history`` list and
UI/account model.

Scope for this slice (deliberately narrow): Py4GW injection only. No gMod injection yet
(near-identical follow-up once this is proven), no auto-login/credential typing (no
``-email``/``-password``/``-character`` args are passed), no UI wiring. This is a
headless, scriptable entry point: call ``launch_py4gw_profile(profile)`` and read the
``LaunchResult``.

Updater/relaunch handoff (rare, only during a large content update)
---------------------------------------------------------------------
This GW1 client build *can* launch a short-lived update/patcher process first (named
``Gw.tmp``, confirmed via live process-tree monitoring), which exits once the update
is applied, after which the real, final ``Gw.exe`` starts under a new PID -- possibly
from a different install folder than the one launched. Empirically, this only happens
when there's an actual large update to apply: with no update pending, the originally
launched process stays alive and never spawns anything -- confirmed by a clean retest
with no hop, no ``Gw.tmp``, injection straight into the original PID. So this handoff
is real but rare, not the normal case, and shouldn't be assumed to happen on every
launch.

A third variant, also confirmed live: a large individual data-file re-download (e.g.
``Gw.dat``, ~7k files) can happen entirely in-place inside the original process, with
no hop and no hang signal at all -- injection succeeded before the download even
started, and the client (with Py4GW already attached) survived the download running
underneath it. So "large content update" doesn't necessarily imply the exit/relaunch
path; it can also just be silent background I/O in an otherwise-normal, responsive
process.

I looked for the equivalent handling in GWxLauncher's C# GW1 pipeline
(``Gw1LaunchOrchestrator``, ``Gw1InjectionService``, ``Gw1InstanceTracker``,
``Gw1ClientStateProbe``) and did not find an explicit "wait for the first process to
exit, then rescan for the real one" mechanism there for the direct-launch path -- so
this isn't a straight port of existing C# logic the way the injection primitives are.
The one adjacent pattern that *does* exist is ``Gw1InjectionService
.TryApplyMulticlientPatchToRunningProcess`` / ``TryInjectGModBestEffort``, used on the
Steam-launch path to patch/inject into a process the launcher didn't create (and
therefore couldn't suspend) -- ``_apply_multiclient_patch`` here is reused the same
way against the rescanned second-stage process, best-effort, since it can't be
suspended either.

Behavior: after resuming the first (suspended, patched) process, `_wait_for_window_or_exit`
polls once for whichever happens first -- a window on that same still-alive process
(the normal case), or the process exiting (the rare update-hop case). This has to be
a single combined poll and not two sequential waits: waiting out a fixed exit-timeout
before ever checking for a window would burn that entire timeout on every normal
launch, even though the window typically appears within a few seconds. The wait
itself is stall-based, not elapsed-time-based -- see `_wait_for_window_or_exit`'s
docstring for why (short version: a window reporting hung via ``IsHungAppWindow`` is
treated as "still legitimately busy," not a timeout, so a genuinely slow update
doesn't get killed just for taking a while). Only on the "exited" branch do we scan
for a replacement process and re-apply the multiclient patch to it (best-effort,
since it's already running and can't be suspended).

Reserved extension point
-------------------------
``launch_py4gw_profile`` takes an optional ``pre_injection_config`` (see
``PreInjectionConfig`` below). This is an explicit, documented no-op today, not real
logic -- nothing sets it, and `launch_py4gw_profile` does nothing with it even if
something did. It exists because Apo mentioned a name-obfuscation config that will
need to reach the child process before it resumes, and the exact mechanism (env var
vs. file, and the data shape) is still his call to make. See `PreInjectionConfig`'s
docstring for the reasoning behind keeping this inert rather than building real
environment-block-construction logic against a guessed format.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import dataclasses
import os
import time
from typing import Callable, Optional

import psutil
import pywintypes
import win32gui
import win32process

from launcher_core.profile import GameProfile

kernel32 = ctypes.windll.kernel32
ntdll = ctypes.windll.ntdll
user32 = ctypes.windll.user32

# -- process/memory access rights & flags --
# Multiclient-patch mask: matches Patcher.py / Py4GW_Launcher.py, and also matches
# GWxLauncher's own TryApplyGw1MulticlientPatch OpenProcess call byte-for-byte.
PROCESS_VM_OPERATION = 0x0008
PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_QUERY_INFORMATION = 0x0400

# Injection mask: narrowed to match GWxLauncher's Gw1InjectionService.InjectDllIntoProcess
# exactly (PROCESS_CREATE_THREAD | PROCESS_QUERY_INFORMATION | PROCESS_VM_OPERATION |
# PROCESS_VM_WRITE | PROCESS_VM_READ = 0x043A). The original Python launchers (this one's
# first draft included) requested PROCESS_ALL_ACCESS (0x1F0FFF) here instead -- no reason
# to request more than the working reference implementation does.
PROCESS_CREATE_THREAD = 0x0002
PROCESS_INJECTION_ACCESS = (
    PROCESS_CREATE_THREAD | PROCESS_QUERY_INFORMATION | PROCESS_VM_OPERATION | PROCESS_VM_WRITE | PROCESS_VM_READ
)

CREATE_SUSPENDED = 0x00000004

VIRTUAL_MEM = 0x1000 | 0x2000  # MEM_COMMIT | MEM_RESERVE
PAGE_READWRITE = 0x04
MEM_RELEASE = 0x8000
STILL_ACTIVE = 259

# How long a window is allowed to report hung (IsHungAppWindow) before we give up on
# it -- a real freeze/crash, not a legitimate "still installing a big update" stall.
HANG_FAIL_THRESHOLD_DEFAULT = 60.0

# Last-resort safety valve for _wait_for_window_or_exit, not a tuned guess: this
# should only ever be hit if something is silently wrong (no window, no exit, no
# hang reported) since the primary exit conditions are stall-based, not elapsed-time-
# based. 30 minutes is deliberately generous -- a real 15-minute content update
# should never trip this.
ABSOLUTE_CEILING_DEFAULT = 1800.0

# Multiclient patch signature + payload (Patcher.py: byte-for-byte identical).
_MULTICLIENT_SIGNATURE = bytes(
    [0x56, 0x57, 0x68, 0x00, 0x01, 0x00, 0x00, 0x89, 0x85, 0xF4, 0xFE, 0xFF, 0xFF, 0xC7, 0x00, 0x00, 0x00, 0x00, 0x00]
)
_MULTICLIENT_PATCH_PAYLOAD = bytes([0x31, 0xC0, 0x90, 0xC3])
_MULTICLIENT_PATCH_OFFSET = 0x1A
_GW_MODULE_SCAN_SIZE = 0x48D000


class PROCESS_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("Reserved1", ctypes.c_void_p),
        ("PebBaseAddress", ctypes.c_void_p),
        ("Reserved2", ctypes.c_void_p * 2),
        ("UniqueProcessId", ctypes.c_ulong),
        ("Reserved3", ctypes.c_void_p),
    ]


class PEB(ctypes.Structure):
    _fields_ = [
        ("InheritedAddressSpace", ctypes.c_ubyte),
        ("ReadImageFileExecOptions", ctypes.c_ubyte),
        ("BeingDebugged", ctypes.c_ubyte),
        ("BitField", ctypes.c_ubyte),
        ("Mutant", ctypes.c_void_p),
        ("ImageBaseAddress", ctypes.c_void_p),
    ]


class STARTUPINFO(ctypes.Structure):
    _fields_ = [
        ("cb", ctypes.c_ulong),
        ("lpReserved", ctypes.c_wchar_p),
        ("lpDesktop", ctypes.c_wchar_p),
        ("lpTitle", ctypes.c_wchar_p),
        ("dwX", ctypes.c_ulong),
        ("dwY", ctypes.c_ulong),
        ("dwXSize", ctypes.c_ulong),
        ("dwYSize", ctypes.c_ulong),
        ("dwXCountChars", ctypes.c_ulong),
        ("dwYCountChars", ctypes.c_ulong),
        ("dwFillAttribute", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("wShowWindow", ctypes.c_ushort),
        ("cbReserved2", ctypes.c_ushort),
        ("lpReserved2", ctypes.c_void_p),
        ("hStdInput", ctypes.c_void_p),
        ("hStdOutput", ctypes.c_void_p),
        ("hStdError", ctypes.c_void_p),
    ]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("hProcess", ctypes.c_void_p),
        ("hThread", ctypes.c_void_p),
        ("dwProcessId", ctypes.c_ulong),
        ("dwThreadId", ctypes.c_ulong),
    ]


@dataclasses.dataclass
class PreInjectionConfig:
    """Reserved extension point for delivering config to the child process before it
    resumes -- most likely Apo's name-obfuscation hook, which (per the GW1 launcher
    handover, 2026-07-09) needs its config in place before/at injection time, the same
    shape of problem GWxLauncher already solved for GW2 by setting environment
    variables before injecting its folder-redirect hook.

    This is an explicit, documented no-op today, not real logic: `launch_py4gw_profile`
    accepts an instance of this but does nothing with it. The fields below are a guess
    at the eventual shape (env vars and/or a config file path), not a finalized
    contract -- the exact mechanism is still Apo's call to make. Keeping this as an
    inert placeholder (rather than building real environment-block-construction code
    against a guessed format) means there's a stable parameter for future callers to
    target without a signature change, without also carrying speculative, never-
    exercised ctypes code that nothing has ever tested.
    """

    extra_environment: Optional[dict] = None
    config_file_path: Optional[str] = None


@dataclasses.dataclass
class LaunchResult:
    success: bool
    pid: Optional[int]
    error: Optional[str]
    log: list


class _ObservableLog(list):
    """A plain list of log lines that also notifies an optional callback as each line
    is added -- lets a caller (e.g. a UI running this on a background thread) observe
    pipeline progress live, without needing access to internal state. Behaves exactly
    like a list to everything else (iteration, indexing, len, `LaunchResult.log`).
    """

    def __init__(self, on_message: Optional[Callable[[str], None]] = None):
        super().__init__()
        self.on_message = on_message


def _log(log: list, message: str) -> None:
    log.append(message)
    print(f"[gw1_launch] {message}")
    on_message = getattr(log, "on_message", None)
    if on_message is not None:
        on_message(message)


def _get_process_module_base(process_handle: int) -> Optional[int]:
    pbi = PROCESS_BASIC_INFORMATION()
    return_length = ctypes.c_ulong(0)

    if ntdll.NtQueryInformationProcess(
        process_handle, 0, ctypes.byref(pbi), ctypes.sizeof(pbi), ctypes.byref(return_length)
    ) != 0:
        return None

    buffer = ctypes.create_string_buffer(ctypes.sizeof(PEB))
    bytes_read = ctypes.c_size_t()
    if not kernel32.ReadProcessMemory(
        process_handle, pbi.PebBaseAddress, buffer, ctypes.sizeof(PEB), ctypes.byref(bytes_read)
    ):
        return None

    peb = PEB.from_buffer(buffer)
    return peb.ImageBaseAddress


def _apply_multiclient_patch(pid: int, log: list) -> bool:
    process_handle = kernel32.OpenProcess(
        PROCESS_VM_OPERATION | PROCESS_VM_READ | PROCESS_VM_WRITE | PROCESS_QUERY_INFORMATION, False, pid
    )
    if not process_handle:
        _log(log, f"Multiclient patch - could not open process {pid}: {ctypes.GetLastError()}")
        return False

    try:
        module_base = _get_process_module_base(process_handle)
        if module_base is None:
            _log(log, "Multiclient patch - failed to get module base")
            return False

        gwdata = ctypes.create_string_buffer(_GW_MODULE_SCAN_SIZE)
        bytes_read = ctypes.c_size_t()
        if not kernel32.ReadProcessMemory(
            process_handle, module_base, gwdata, _GW_MODULE_SCAN_SIZE, ctypes.byref(bytes_read)
        ):
            _log(log, f"Multiclient patch - failed to read process memory: {ctypes.GetLastError()}")
            return False

        idx = gwdata.raw.find(_MULTICLIENT_SIGNATURE)
        if idx == -1:
            _log(log, "Multiclient patch - failed to find signature")
            return False

        patch_address = module_base + idx - _MULTICLIENT_PATCH_OFFSET
        bytes_written = ctypes.c_size_t()
        if not kernel32.WriteProcessMemory(
            process_handle, patch_address, _MULTICLIENT_PATCH_PAYLOAD, len(_MULTICLIENT_PATCH_PAYLOAD),
            ctypes.byref(bytes_written)
        ):
            _log(log, f"Multiclient patch - failed to write process memory: {ctypes.GetLastError()}")
            return False

        _log(log, f"Multiclient patch - patched at address {hex(patch_address)}")
        return True
    finally:
        kernel32.CloseHandle(process_handle)


def _inject_dll(pid: int, dll_path: str, log: list) -> bool:
    if not dll_path or not os.path.exists(dll_path):
        _log(log, f"Inject DLL - invalid DLL path: {dll_path!r}")
        return False

    _log(log, f"Inject DLL - starting injection of {dll_path} into PID {pid}")
    process_handle = None
    allocated_memory = None
    thread_handle = None

    try:
        process_handle = kernel32.OpenProcess(PROCESS_INJECTION_ACCESS, False, pid)
        if not process_handle:
            _log(log, f"Inject DLL - failed to open process: {ctypes.get_last_error()}")
            return False

        process_exit_code = ctypes.c_ulong(0)
        if (
            not kernel32.GetExitCodeProcess(process_handle, ctypes.byref(process_exit_code))
            or process_exit_code.value != STILL_ACTIVE
        ):
            _log(log, f"Inject DLL - process {pid} is not STILL_ACTIVE (exit code {process_exit_code.value}); aborting")
            return False

        loadlib_addr = kernel32.GetProcAddress(kernel32._handle, b"LoadLibraryA")
        if not loadlib_addr:
            _log(log, "Inject DLL - failed to get LoadLibraryA address")
            return False

        dll_path_bytes = dll_path.encode("ascii") + b"\0"
        path_size = len(dll_path_bytes)

        allocated_memory = kernel32.VirtualAllocEx(process_handle, 0, path_size, VIRTUAL_MEM, PAGE_READWRITE)
        if not allocated_memory:
            _log(log, f"Inject DLL - failed to allocate memory in target process: {ctypes.GetLastError()}")
            return False

        written = ctypes.c_size_t(0)
        if not kernel32.WriteProcessMemory(
            process_handle, allocated_memory, dll_path_bytes, path_size, ctypes.byref(written)
        ) or written.value != path_size:
            _log(log, "Inject DLL - failed to write DLL path to target process")
            return False

        thread_handle = kernel32.CreateRemoteThread(
            process_handle, None, 0, loadlib_addr, allocated_memory, 0, None
        )
        if not thread_handle:
            _log(log, "Inject DLL - failed to create remote thread")
            return False

        kernel32.WaitForSingleObject(thread_handle, 5000)

        exit_code = ctypes.c_ulong(0)
        if kernel32.GetExitCodeThread(thread_handle, ctypes.byref(exit_code)):
            _log(log, f"Inject DLL - injection thread exit code: {exit_code.value}")
            return exit_code.value != 0
        return False
    finally:
        if thread_handle:
            kernel32.CloseHandle(thread_handle)
        if allocated_memory and process_handle:
            kernel32.VirtualFreeEx(process_handle, allocated_memory, 0, MEM_RELEASE)
        if process_handle:
            kernel32.CloseHandle(process_handle)


def _wait_for_gw_window(pid: int, log: list, timeout: float = 30.0) -> bool:
    _log(log, f"Waiting for GW window (PID {pid})")
    start_time = time.time()
    found_windows = []

    def enum_windows_callback(hwnd, _):
        try:
            if win32gui.IsWindowVisible(hwnd):
                _, window_pid = win32process.GetWindowThreadProcessId(hwnd)
                if window_pid == pid:
                    found_windows.append(hwnd)
        except pywintypes.error:
            # A window can be destroyed mid-enumeration; skip it rather than letting
            # one bad handle crash the whole enumeration (see window_control.py).
            pass
        return True

    while time.time() - start_time < timeout:
        try:
            if psutil.Process(pid).status() != psutil.STATUS_RUNNING:
                _log(log, f"Process {pid} is no longer running")
                return False
        except psutil.NoSuchProcess:
            _log(log, f"Process {pid} no longer exists")
            return False

        found_windows.clear()
        win32gui.EnumWindows(enum_windows_callback, None)
        if found_windows:
            _log(log, f"Found {len(found_windows)} window(s) for PID {pid}")
            return True

        time.sleep(0.5)

    _log(log, f"Timed out waiting for a window from PID {pid}")
    return False


def _wait_for_window_or_exit(
    pid: int,
    log: list,
    absolute_ceiling: float = ABSOLUTE_CEILING_DEFAULT,
    hang_fail_threshold: float = HANG_FAIL_THRESHOLD_DEFAULT,
) -> str:
    """Poll `pid` for whichever happens first: a visible, *responsive* window while
    still alive (the normal case -- return "window"), or the process exiting before
    any window appears (the updater/relaunch handoff case -- return "exited").

    Stall-based, not elapsed-time-based: a window that exists but reports hung
    (``IsHungAppWindow``) is treated as "still legitimately busy" -- e.g. GW showing
    a not-responding window while it unpacks a large update -- and polling continues.
    Only two things actually fail this wait: (a) the process exits with no window
    ever appearing, or (b) a window stays hung for `hang_fail_threshold` seconds
    straight, which is treated as an actual freeze/crash rather than a slow update.
    `absolute_ceiling` is a last-resort safety valve for the case where neither of
    those clean signals ever fires, not a tuned duration -- see its docstring.

    This also has to be a single combined poll, not a sequential "wait for exit,
    then wait for a window": sequencing them means the normal (no update pending)
    case always burns the full wait before ever checking for a window, even though
    the window typically appears within a few seconds.
    """
    _log(
        log,
        f"Waiting for a window or process exit on PID {pid} (stall-based; "
        f"hang_fail_threshold={hang_fail_threshold}s, absolute_ceiling={absolute_ceiling}s)",
    )
    start_time = time.time()
    hang_started_at: Optional[float] = None
    found_windows = []

    def enum_windows_callback(hwnd, _):
        try:
            if win32gui.IsWindowVisible(hwnd):
                _, window_pid = win32process.GetWindowThreadProcessId(hwnd)
                if window_pid == pid:
                    found_windows.append(hwnd)
        except pywintypes.error:
            # A window can be destroyed mid-enumeration; skip it rather than letting
            # one bad handle crash the whole enumeration (see window_control.py).
            pass
        return True

    while time.time() - start_time < absolute_ceiling:
        try:
            if psutil.Process(pid).status() != psutil.STATUS_RUNNING:
                _log(log, f"PID {pid} is no longer running")
                return "exited"
        except psutil.NoSuchProcess:
            _log(log, f"PID {pid} no longer exists")
            return "exited"

        found_windows.clear()
        win32gui.EnumWindows(enum_windows_callback, None)
        if found_windows:
            hwnd = found_windows[0]
            if user32.IsHungAppWindow(hwnd):
                if hang_started_at is None:
                    hang_started_at = time.time()
                    _log(log, f"Window found for PID {pid} but reports hung -- may be a legitimate large update, watching")
                elif time.time() - hang_started_at >= hang_fail_threshold:
                    _log(log, f"Window for PID {pid} has been hung for {hang_fail_threshold}s+; treating as actually stuck")
                    return "hung"
            else:
                if hang_started_at is not None:
                    _log(log, f"Window for PID {pid} recovered from hung state")
                _log(log, f"Found {len(found_windows)} window(s) for PID {pid}, responsive")
                return "window"

        time.sleep(0.25)

    _log(log, f"Hit the absolute ceiling ({absolute_ceiling}s) waiting for PID {pid} -- last-resort safety valve, not expected in normal operation")
    return "timeout"


def _find_replacement_process(exe_path: str, exclude_pid: int, launched_after: float, log: list, timeout: float = 15.0) -> Optional[int]:
    """Poll for a new process running `exe_path` that started after `launched_after`.

    Used after the first (updater-stage) process exits, to locate the real, final
    Gw.exe it hands off to. Matches by resolved executable path plus a start-time
    floor (with a small buffer for clock granularity), same idea as GWxLauncher's
    SteamProcessAttachService.TryAttachToSteamProcess, just triggered by "the process
    we launched exited" instead of "Steam spawned something."
    """
    target_path = os.path.normcase(os.path.abspath(exe_path))
    start_time = time.time()

    _log(log, f"Scanning for the follow-up process for {exe_path!r} (excluding PID {exclude_pid})")
    while time.time() - start_time < timeout:
        for proc in psutil.process_iter(["pid", "exe", "create_time"]):
            if proc.info["pid"] == exclude_pid:
                continue
            try:
                proc_exe = proc.info["exe"]
                if not proc_exe or os.path.normcase(os.path.abspath(proc_exe)) != target_path:
                    continue
                if proc.info["create_time"] < launched_after - 2.0:
                    continue
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

            _log(log, f"Found follow-up process PID {proc.info['pid']}")
            return proc.info["pid"]

        time.sleep(0.5)

    _log(log, f"Timed out waiting for a follow-up process for {exe_path!r}")
    return None


def launch_py4gw_profile(
    profile: GameProfile,
    *,
    pre_injection_config: Optional[PreInjectionConfig] = None,
    window_wait_timeout: float = 30.0,
    post_window_settle_delay: float = 5.0,
    absolute_ceiling: float = ABSOLUTE_CEILING_DEFAULT,
    hang_fail_threshold: float = HANG_FAIL_THRESHOLD_DEFAULT,
    replacement_scan_timeout: float = 300.0,
    on_log: Optional[Callable[[str], None]] = None,
) -> LaunchResult:
    """Launch `profile`'s executable and inject Py4GW into it.

    Py4GW only -- gMod injection is a deliberate follow-up, not handled here. No
    auto-login: the child is launched with no ``-email``/``-password``/``-character``
    arguments, only `profile.launch_arguments` if set.

    `LaunchResult.pid` is whichever process ends up injected into -- if the
    updater/relaunch handoff (see module docstring) happens, that's the second,
    replacement process, not the one this function originally created.

    `pre_injection_config` is accepted but intentionally unused -- see
    `PreInjectionConfig`'s docstring for why.

    This function blocks for the full duration of the launch (seconds to, rarely,
    tens of minutes during a large update) -- callers driving a UI from this should
    run it on a background thread and use `on_log` to observe progress live rather
    than blocking the UI thread. `on_log` is called with each raw log line as it's
    produced (same strings that end up in `LaunchResult.log`); it's called from
    whatever thread `launch_py4gw_profile` itself runs on, so it must not touch
    anything that isn't thread-safe (e.g. no direct ImGui calls).
    """
    log: list = _ObservableLog(on_log)

    if not profile.executable_path or not os.path.exists(profile.executable_path):
        return LaunchResult(False, None, f"executable_path not found: {profile.executable_path!r}", log)

    if not profile.py4gw_enabled:
        return LaunchResult(False, None, "profile.py4gw_enabled is False -- nothing to inject", log)

    if not profile.py4gw_dll_path or not os.path.exists(profile.py4gw_dll_path):
        return LaunchResult(False, None, f"py4gw_dll_path not found: {profile.py4gw_dll_path!r}", log)

    command_line = f'"{profile.executable_path}"'
    if profile.launch_arguments:
        command_line += f" {profile.launch_arguments}"

    startup_info = STARTUPINFO()
    startup_info.cb = ctypes.sizeof(startup_info)
    process_info = PROCESS_INFORMATION()

    launch_timestamp = time.time()
    _log(log, f"Launching (suspended): {command_line}")
    success = kernel32.CreateProcessW(
        None,
        command_line,
        None,
        None,
        False,
        CREATE_SUSPENDED,
        None,
        None,
        ctypes.byref(startup_info),
        ctypes.byref(process_info),
    )
    if not success:
        return LaunchResult(False, None, f"CreateProcessW failed: {ctypes.GetLastError()}", log)

    pid = process_info.dwProcessId

    def _abort(reason: str) -> LaunchResult:
        kernel32.TerminateProcess(process_info.hProcess, 0)
        kernel32.CloseHandle(process_info.hProcess)
        kernel32.CloseHandle(process_info.hThread)
        _log(log, reason)
        return LaunchResult(False, pid, reason, log)

    if not _apply_multiclient_patch(pid, log):
        return _abort("Failed to apply multiclient patch; aborting launch")

    if kernel32.ResumeThread(process_info.hThread) == -1:
        return _abort(f"Failed to resume thread: {ctypes.GetLastError()}")

    _log(log, f"Process resumed (PID {pid})")
    kernel32.CloseHandle(process_info.hProcess)
    kernel32.CloseHandle(process_info.hThread)

    outcome = _wait_for_window_or_exit(pid, log, absolute_ceiling=absolute_ceiling, hang_fail_threshold=hang_fail_threshold)

    if outcome == "exited":
        replacement_pid = _find_replacement_process(
            profile.executable_path, exclude_pid=pid, launched_after=launch_timestamp, log=log,
            timeout=replacement_scan_timeout,
        )
        if replacement_pid is None:
            return LaunchResult(False, pid, "Updater process exited but no follow-up Gw.exe process was found", log)

        pid = replacement_pid
        if not _apply_multiclient_patch(pid, log):
            _log(log, "Multiclient patch on the follow-up process failed (best-effort, continuing)")

        if not _wait_for_gw_window(pid, log, timeout=window_wait_timeout):
            return LaunchResult(False, pid, "GW window never appeared", log)

    elif outcome == "hung":
        return LaunchResult(False, pid, f"Window stayed hung for {hang_fail_threshold}s+; treating as stuck, not a slow update", log)

    elif outcome == "timeout":
        return LaunchResult(False, pid, f"Hit the absolute ceiling ({absolute_ceiling}s) with no window, exit, or hang signal", log)

    # outcome == "window": pid's window is already confirmed, fall straight through.

    _log(log, f"Window found; waiting {post_window_settle_delay}s before injecting Py4GW")
    time.sleep(post_window_settle_delay)

    if not _inject_dll(pid, profile.py4gw_dll_path, log):
        return LaunchResult(False, pid, "Py4GW DLL injection failed", log)

    _log(log, "Py4GW DLL injection reported success")
    return LaunchResult(True, pid, None, log)
