"""Prerequisite checks for the GW1/Py4GW injection pipeline on the *target*
machine: a separate Python installation (whatever ``py -3.13-32`` resolves
to), the Visual C++ Redistributable, and the DirectX End-User Runtime.
Distinct from launcher.py's own ``sys.maxsize`` self-check, which only
verifies *this launcher's own* interpreter is 32-bit -- these check entirely
different, separately-installed software that GW1 injection needs on the
machine, independent of whatever interpreter is running this launcher's own
code.

The Python check is a direct port of GWxLauncher's
Services/PythonPrereqService.cs -- same probe command, same failure
classification. The VC++ Redistributable and DirectX End-User Runtime checks
are new (not present in that reference), included defensively since it
hasn't yet been confirmed safe to omit for Reforged specifically -- the
DirectX one specifically confirmed necessary by Apo directly (Discord,
2026-04-05), linking Microsoft's own download page and stating it's
"necessary for install".

A DirectX *SDK* (DXSDK_DIR) check -- a different thing entirely from the
End-User Runtime above -- was considered separately and deliberately left
out: verified directly against Py4GW_Reforged_Native's actual CMakeLists.txt,
which links d3d9.lib/d3dcompiler.lib (standard Windows SDK components that
ship with the OS/Windows Update) with no D3DX linkage anywhere -- D3DX is
the only reason the legacy DirectX *SDK* would ever be needed, and this
codebase doesn't use it. The End-User *Runtime* is a separate, real
requirement regardless: it's what actually installs the D3DX9/10/11,
XAudio, XInput, and XACT DLLs a running game/DLL loads at runtime, which is
an entirely different concern from whether a *developer* SDK is present.

Every detection function here is a synchronous, cheap call (a subprocess
probe, a registry read, or a filesystem check) meant to be re-run on every
launch -- no caching, no staleness/expiration handling, since a check this
cheap has no real cost to re-running and a cache only buys complexity for a
problem ("this check is slow") that doesn't exist.
"""

from __future__ import annotations

import ctypes
import dataclasses
import hashlib
import os
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
import winreg
from enum import Enum
from pathlib import Path
from typing import Callable, Optional

# -----------------------------------------------------------------------------
# Shared: registry-fresh environment variables, and Authenticode signature
# verification (both reused across the Python/VC++ checks below).
# -----------------------------------------------------------------------------


def _read_env_value(hive, subkey: str, name: str) -> Optional[str]:
    try:
        key = winreg.OpenKey(hive, subkey, 0, winreg.KEY_READ)
        try:
            value, _ = winreg.QueryValueEx(key, name)
            return value
        finally:
            winreg.CloseKey(key)
    except FileNotFoundError:
        return None


def refresh_env_from_registry() -> dict:
    """A fresh, os.environ-shaped dict with PATH rebuilt straight from the
    registry (machine + user Environment keys, machine first per Windows'
    own precedence), rather than this already-running process's own PATH.

    Confirmed directly (not assumed) that a full reboot is *not* needed for a
    freshly-installed program's PATH to be usable: installers write the new
    PATH to HKLM's Session Manager\\Environment (machine-wide) and/or
    HKCU\\Environment (per-user), then broadcast WM_SETTINGCHANGE so already-
    running processes like Explorer pick it up for anything *they* launch
    afterward. But this app is itself a long-running process started before
    any such change -- its own os.environ is a one-time snapshot from process
    start that never updates on its own. A real test on this machine (write a
    scratch registry value, broadcast WM_SETTINGCHANGE, spawn a subprocess)
    confirmed the exact failure mode directly: a subprocess that inherits
    this process's stale os.environ does not see the change (the variable
    came back as the literal, unexpanded "%VAR%"), while a subprocess given
    an environment explicitly rebuilt from a fresh registry read sees it
    immediately -- no reboot, not even a relaunch of this app, required.
    Every subprocess call in this module that might run right after an
    install uses this instead of plain os.environ, so a Python/VC++ install
    can be re-checked in the very same app session.
    """
    machine_path = _read_env_value(
        winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment", "Path"
    ) or ""
    user_path = _read_env_value(winreg.HKEY_CURRENT_USER, "Environment", "Path") or ""
    combined_path = ";".join(p for p in (machine_path, user_path) if p)

    env = dict(os.environ)
    env["PATH"] = combined_path
    return env


def _verify_authenticode_signer(file_path: Path, expected_signer_substring: str) -> tuple[bool, str]:
    """Verifies a downloaded installer's Authenticode signature via Windows'
    own trust store (PowerShell's Get-AuthenticodeSignature) -- no new
    dependency needed, since this is a Windows-only launcher and every
    installer involved here (python.org's, Microsoft's) is Authenticode-
    signed. Confirmed directly on the real python-3.13.0.exe installer
    (downloaded for real): Status "Valid", signer "CN=Python Software
    Foundation, O=Python Software Foundation, ...", chaining to a trusted
    DigiCert root -- despite the signing certificate's own NotAfter date
    already being in the past, because the signature carries a valid
    timestamp counter-signature (proves it was signed while the cert was
    still valid, which Windows honors indefinitely).

    Returns (ok, message).
    """
    try:
        # Embed the path directly into the script as a single-quoted PowerShell
        # string literal instead of passing it as a trailing positional arg and
        # reading it back via $args[0]. A trailing arg after -Command "<script>"
        # is not reliably bound into $args for an inline script across PowerShell
        # builds -- when it doesn't bind, $args[0] is $null, Get-AuthenticodeSignature
        # receives an empty -LiteralPath, and it returns fast with a blank/"unknown"
        # Status (exactly the failure seen on this machine, where the download and
        # MD5 check both succeed and only this check fails). A single-quoted PS
        # literal is the safe embedding: single-quoting suppresses all $/backtick
        # interpolation, so the only character that needs escaping is the single
        # quote itself, doubled ('' ) per PowerShell's own literal-string rules.
        literal_path = str(file_path).replace("'", "''")
        ps_script = (
            f"$sig = Get-AuthenticodeSignature -LiteralPath '{literal_path}'; "
            "Write-Output \"$($sig.Status)|$($sig.SignerCertificate.Subject)\""
        )
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps_script],
            capture_output=True, text=True, timeout=30.0,
        )
        output = result.stdout.strip()
        status, _, subject = output.partition("|")
        if status.strip() != "Valid":
            return False, f"Authenticode signature status: {status.strip() or 'unknown'}"
        if expected_signer_substring.lower() not in subject.lower():
            return False, f"Signed, but not by the expected signer (got: {subject.strip()})"
        return True, f"Valid signature from {subject.strip()}"
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, f"Could not verify signature: {e}"


def _download_file(url: str, dest: Path, *, on_status: Callable[[str], None]) -> None:
    on_status(f"Downloading {dest.name}...")
    urllib.request.urlretrieve(url, str(dest))


# -----------------------------------------------------------------------------
# Phase 1 -- Python 3.13.0 (32-bit), ported from PythonPrereqService.cs.
# -----------------------------------------------------------------------------

PYTHON_REQUIRED_VERSION_STRING = "3.13.0"
PYTHON_REQUIRED_BITNESS = 32
# Exact pin, not "3.13.x or newer" -- Python's own update nagging has bitten
# users who assumed a newer patch release was fine; the py launcher argument
# below only selects the 3.13 line, so the version string is still checked
# explicitly against PYTHON_REQUIRED_VERSION_STRING after the probe runs.
_PY_LAUNCHER_VERSION_ARG = "-3.13-32"

PYTHON_DOWNLOAD_URL = "https://www.python.org/ftp/python/3.13.0/python-3.13.0.exe"
# Published on python.org's own release page for this exact, pinned file.
# Verified directly: downloaded the real installer and confirmed both this
# MD5 and a valid Authenticode signature from "Python Software Foundation"
# (see _verify_authenticode_signer's docstring) before ever writing this
# constant.
PYTHON_INSTALLER_EXPECTED_MD5 = "8e96d6243623ff7acc61c9dc7cd3638f"
PYTHON_INSTALLER_EXPECTED_SIGNER = "Python Software Foundation"

_PROBE_SCRIPT = (
    "import sys, struct; "
    "print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}'); "
    "print(struct.calcsize('P') * 8); "
    "print(sys.executable)"
)


class PythonPrereqStatus(Enum):
    OK = "ok"
    PY_LAUNCHER_NOT_FOUND = "py_launcher_not_found"
    PYTHON_NOT_FOUND = "python_not_found"
    WRONG_VERSION = "wrong_version"
    WRONG_BITNESS = "wrong_bitness"
    CHECK_FAILED = "check_failed"


@dataclasses.dataclass
class PythonPrereqResult:
    status: PythonPrereqStatus
    detected_version: Optional[str] = None
    detected_bitness: Optional[int] = None
    executable_path: Optional[str] = None
    diagnostic_text: str = ""

    @property
    def is_ok(self) -> bool:
        return self.status == PythonPrereqStatus.OK


def _validate_probe_lines(lines: list[str]) -> PythonPrereqResult:
    """Shared by both the py-launcher probe and the RELAY 062 bare
    python/python3 fallback -- same 3-line (version, bitness, executable
    path) parsing and version/bitness validation either way."""
    version, bitness_str, exec_path = lines[0], lines[1], lines[2]
    try:
        bitness = int(bitness_str)
    except ValueError:
        return PythonPrereqResult(
            PythonPrereqStatus.CHECK_FAILED, diagnostic_text=f"Failed to parse probe output: {lines!r}"
        )

    if version != PYTHON_REQUIRED_VERSION_STRING:
        return PythonPrereqResult(
            PythonPrereqStatus.WRONG_VERSION,
            detected_version=version, detected_bitness=bitness, executable_path=exec_path,
            diagnostic_text=f"Expected {PYTHON_REQUIRED_VERSION_STRING}, found {version}",
        )
    if bitness != PYTHON_REQUIRED_BITNESS:
        return PythonPrereqResult(
            PythonPrereqStatus.WRONG_BITNESS,
            detected_version=version, detected_bitness=bitness, executable_path=exec_path,
            diagnostic_text=f"Expected 32-bit, found {bitness}-bit",
        )

    return PythonPrereqResult(
        PythonPrereqStatus.OK,
        detected_version=version, detected_bitness=bitness, executable_path=exec_path,
        diagnostic_text=f"Python {version} (32-bit) detected at {exec_path}",
    )


def _check_bare_python_fallback(env: dict) -> Optional[PythonPrereqResult]:
    """RELAY 062: when the `py` launcher itself isn't found, or is found but
    can't resolve a matching install, fall back to bare `python`/`python3` on
    PATH. Real cause of Apo's false positive: his Python was genuinely
    installed and working (his own terminal confirmed exactly 3.13.0,
    32-bit), but not discoverable via the `py -3.13-32` launcher mechanism
    specifically -- his own words on Discord: "the library forces us to have
    python 32bit on the path... you can just parse the result of 'python'."
    Tried in order (python, then python3); returns None (not a result, so
    the caller keeps its original py-launcher failure) only if NEITHER name
    resolves on PATH at all -- if a name resolves but the probe against it
    fails to run/parse, that's still reported (not silently skipped to try
    the next name), matching how the primary py-launcher check itself
    reports a real probe failure rather than pretending it didn't happen.
    """
    for candidate in ("python", "python3"):
        candidate_path = shutil.which(candidate, path=env["PATH"])
        if candidate_path is None:
            continue
        try:
            result = subprocess.run(
                [candidate_path, "-c", _PROBE_SCRIPT],
                capture_output=True, text=True, timeout=5.0,
                cwd=str(Path.home()), env=env,
            )
        except subprocess.TimeoutExpired:
            return PythonPrereqResult(PythonPrereqStatus.CHECK_FAILED, diagnostic_text=f"{candidate} timed out")
        except OSError as e:
            return PythonPrereqResult(PythonPrereqStatus.CHECK_FAILED, diagnostic_text=f"Unexpected error: {e}")

        if result.returncode != 0 or not result.stdout.strip():
            return PythonPrereqResult(
                PythonPrereqStatus.CHECK_FAILED,
                diagnostic_text=f"{candidate} failed: {(result.stderr or '').strip()}",
            )

        lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        if len(lines) < 3:
            return PythonPrereqResult(
                PythonPrereqStatus.CHECK_FAILED, diagnostic_text=f"Failed to parse probe output: {result.stdout!r}"
            )
        return _validate_probe_lines(lines)
    return None


def check_python_prereq() -> PythonPrereqResult:
    """Port of PythonPrereqService.Check(): resolve py.exe, run
    `py -3.13-32 -c "<probe>"`, classify failure by matching substrings in
    the error output (same substrings as the C# reference), parse the
    3-line probe output (version, bitness, executable path) on success, then
    validate version and bitness exactly.

    Resolves py.exe's full path explicitly via shutil.which against a
    registry-fresh PATH, then invokes that resolved path directly, rather
    than just passing the bare command "py" (with a refreshed env=) to
    subprocess and trusting it to find the right one. Confirmed directly
    (not assumed) that this distinction matters: subprocess.run's env=
    parameter only affects the *child's* environment once a process has
    already been found and started -- on Windows, resolving which
    executable "py" even refers to happens via the *calling* process's own
    already-loaded PATH, completely ignoring whatever env= was passed. A
    real test proved this: stripping every Python-related directory from a
    refreshed env['PATH'] and passing that via env= still found py.exe
    every time, because the calling process's own real PATH (unchanged
    since it started) still had it -- only explicitly resolving the
    executable's path via shutil.which(path=...) against the fresh PATH,
    then invoking *that* resolved path, actually respects a PATH change
    without restarting this app.

    RELAY 062: `py -3.13-32` stays the first attempt -- it correctly
    disambiguates when multiple Pythons are installed, which a bare
    `python`/`python3` lookup can't. The bare-name fallback (see
    `_check_bare_python_fallback`) only runs when this check comes up
    completely empty (PY_LAUNCHER_NOT_FOUND or PYTHON_NOT_FOUND) -- not on
    WRONG_VERSION/WRONG_BITNESS, where `py` DID find something and the
    fallback wouldn't disambiguate any better than it already has.
    """
    env = refresh_env_from_registry()
    py_launcher_path = shutil.which("py", path=env["PATH"])
    if py_launcher_path is None:
        fallback = _check_bare_python_fallback(env)
        if fallback is not None:
            return fallback
        return PythonPrereqResult(
            PythonPrereqStatus.PY_LAUNCHER_NOT_FOUND,
            diagnostic_text="Python Launcher (py.exe) not found in PATH",
        )

    try:
        result = subprocess.run(
            [py_launcher_path, _PY_LAUNCHER_VERSION_ARG, "-c", _PROBE_SCRIPT],
            capture_output=True, text=True, timeout=5.0,
            cwd=str(Path.home()), env=env,
        )
    except subprocess.TimeoutExpired:
        return PythonPrereqResult(PythonPrereqStatus.CHECK_FAILED, diagnostic_text="py launcher timed out")
    except OSError as e:
        return PythonPrereqResult(PythonPrereqStatus.CHECK_FAILED, diagnostic_text=f"Unexpected error: {e}")

    if result.returncode != 0 or not result.stdout.strip():
        stderr_lower = (result.stderr or "").lower()
        if "no python at" in stderr_lower or "not found" in stderr_lower:
            fallback = _check_bare_python_fallback(env)
            if fallback is not None:
                return fallback
            return PythonPrereqResult(
                PythonPrereqStatus.PYTHON_NOT_FOUND,
                diagnostic_text=f"Python {PYTHON_REQUIRED_VERSION_STRING} (32-bit) not found by py launcher",
            )
        if "py" in stderr_lower and "not recognized" in stderr_lower:
            fallback = _check_bare_python_fallback(env)
            if fallback is not None:
                return fallback
            return PythonPrereqResult(
                PythonPrereqStatus.PY_LAUNCHER_NOT_FOUND,
                diagnostic_text="Python Launcher (py.exe) not found in PATH",
            )
        return PythonPrereqResult(
            PythonPrereqStatus.CHECK_FAILED,
            diagnostic_text=f"py launcher failed: {(result.stderr or '').strip()}",
        )

    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if len(lines) < 3:
        return PythonPrereqResult(
            PythonPrereqStatus.CHECK_FAILED, diagnostic_text=f"Failed to parse probe output: {result.stdout!r}"
        )

    return _validate_probe_lines(lines)


def download_and_install_python(on_status: Callable[[str], None]) -> tuple[bool, str]:
    """Downloads python-3.13.0.exe over HTTPS, verifies it (MD5 against the
    published value, then an Authenticode signature check for "Python
    Software Foundation"), then runs it with the installer UI fully visible
    (no /quiet or /passive -- transparency over "ninja mode") and
    `PrependPath=1` on the command line.

    PrependPath=1 pre-checks the "Add python.exe to PATH" checkbox instead
    of leaving it unchecked (confirmed directly against python.org's own
    docs: "these options may also be set without suppressing the UI in
    order to change some of the defaults" -- a default, not an unoverridable
    lock, but that removes the single most common documented failure mode
    (forgetting to check the box) since the common click-through case is
    now correct by default.

    Does not require a restart afterward -- see refresh_env_from_registry's
    docstring for the real, tested reason why -- so a caller can immediately
    call check_python_prereq() again once this returns.
    """
    try:
        with tempfile.TemporaryDirectory(prefix="py4gw_prereq_") as tmp_dir:
            installer_path = Path(tmp_dir) / "python-3.13.0.exe"
            _download_file(PYTHON_DOWNLOAD_URL, installer_path, on_status=on_status)

            on_status("Verifying download...")
            actual_md5 = hashlib.md5(installer_path.read_bytes()).hexdigest()
            if actual_md5 != PYTHON_INSTALLER_EXPECTED_MD5:
                return False, f"Downloaded file's MD5 ({actual_md5}) doesn't match the published value -- not installing."

            sig_ok, sig_message = _verify_authenticode_signer(installer_path, PYTHON_INSTALLER_EXPECTED_SIGNER)
            if not sig_ok:
                return False, f"Signature check failed -- not installing. {sig_message}"

            on_status("Installing Python 3.13.0 (32-bit)...")
            # Fully interactive (no /quiet, no /passive): the installer's
            # normal UI stays visible, matching this project's transparency-
            # over-silence choice elsewhere. PrependPath=1 is still honored
            # as a UI default even without a suppressing flag.
            proc = subprocess.run([str(installer_path), "PrependPath=1"], timeout=600.0)
            if proc.returncode != 0:
                return False, f"Installer exited with code {proc.returncode} (may have been cancelled)."

            on_status("Done.")
            return True, "Python 3.13.0 (32-bit) installed."
    except urllib.error.URLError as e:
        return False, f"Download failed: {e}"
    except subprocess.TimeoutExpired:
        return False, "Installer timed out (over 10 minutes) -- may still be running in the background."
    except OSError as e:
        return False, f"Unexpected error: {e}"


# -----------------------------------------------------------------------------
# Phase 2 -- Visual C++ Redistributable. Included defensively: not yet
# confirmed safe to omit for Reforged specifically. Doesn't exist in the
# GWxLauncher reference at all -- new territory, detection researched and
# verified fresh (including live registry probing on a real machine) rather
# than guessed.
# -----------------------------------------------------------------------------

# Named "VC++ Redistributable v14" in the original task description, but the
# actual, tested-and-working download links Chris confirmed (from the same
# Discord install guides this project already points users to) resolve to
# the Visual C++ 2013 (v12.0) Redistributable specifically -- confirmed via
# Microsoft's own docs: aka.ms/highdpimfc2013{x86,x64}enu redirects to
# vcredist_{x86,x64}.exe version 12.0.40664.0, listed under the "Visual
# Studio 2013 (VC++ 12.0)" section, not the unified "v14" runtime. Built
# against what's actually confirmed working rather than the version number
# in the task text.
VCREDIST_2013_X86_URL = "https://aka.ms/highdpimfc2013x86enu"
VCREDIST_2013_X64_URL = "https://aka.ms/highdpimfc2013x64enu"
VCREDIST_EXPECTED_SIGNER = "Microsoft Corporation"


class VcRedistStatus(Enum):
    OK = "ok"
    NOT_FOUND = "not_found"


@dataclasses.dataclass
class VcRedistResult:
    x86_status: VcRedistStatus
    x64_status: VcRedistStatus
    x86_version: Optional[str] = None
    x64_version: Optional[str] = None

    @property
    def is_ok(self) -> bool:
        return self.x86_status == VcRedistStatus.OK and self.x64_status == VcRedistStatus.OK


def _check_vcredist_runtimes_key(arch: str) -> Optional[str]:
    """Primary check: the Microsoft-documented `Runtimes\\{x86|x64}` key
    under VisualStudio\\12.0\\VC, opened with the matching *explicit* WOW64
    view (KEY_WOW64_32KEY for x86, KEY_WOW64_64KEY for x64) rather than
    relying on this process's own default (redirected) view. Confirmed
    directly on a real machine that the implicit/default view isn't
    something to rely on here (it happened to transparently reach the x64
    key too on the one machine tested, which isn't guaranteed OS behavior --
    being explicit removes any doubt).
    """
    flag = winreg.KEY_WOW64_32KEY if arch == "x86" else winreg.KEY_WOW64_64KEY
    try:
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, rf"SOFTWARE\Microsoft\VisualStudio\12.0\VC\Runtimes\{arch}", 0,
            winreg.KEY_READ | flag,
        )
        try:
            version, _ = winreg.QueryValueEx(key, "Version")
            return version
        finally:
            winreg.CloseKey(key)
    except FileNotFoundError:
        return None


def _check_vcredist_uninstall_key(arch: str) -> Optional[str]:
    """Fallback check: scan the Uninstall registry entries for a
    "Microsoft Visual C++ 2013 Redistributable ({arch})" display name.

    Needed because the Runtimes key above -- while Microsoft's own
    documented mechanism -- was confirmed directly on a real machine to be
    unreliable for VC++ 2013 specifically: Runtimes\\x64 was completely
    absent even though "Microsoft Visual C++ 2013 Redistributable (x64) -
    12.0.40664" was demonstrably present in the Uninstall entries on that
    same machine (matches a documented category of issue: VC++
    redistributable *updates* have been known to leave the Runtimes key
    stale/deleted while the software itself remains installed). The x86
    Runtimes key worked correctly in that same test, so this fallback only
    runs when the primary check comes up empty rather than replacing it.
    """
    marker = f"visual c++ 2013 redistributable ({arch})"
    for hive, subkey in (
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ):
        try:
            key = winreg.OpenKey(hive, subkey, 0, winreg.KEY_READ)
        except FileNotFoundError:
            continue
        try:
            i = 0
            while True:
                try:
                    subkey_name = winreg.EnumKey(key, i)
                except OSError:
                    break
                i += 1
                try:
                    entry = winreg.OpenKey(key, subkey_name)
                    try:
                        display_name, _ = winreg.QueryValueEx(entry, "DisplayName")
                        display_version, _ = winreg.QueryValueEx(entry, "DisplayVersion")
                    finally:
                        winreg.CloseKey(entry)
                except (FileNotFoundError, OSError):
                    continue
                if marker in display_name.lower():
                    return display_version
        finally:
            winreg.CloseKey(key)
    return None


def check_vcredist_prereq() -> VcRedistResult:
    """Checks both the x86 and x64 Visual C++ 2013 Redistributable, each via
    the documented Runtimes key first, falling back to an Uninstall-entry
    scan if that key isn't found -- confirmed necessary via real testing on
    this project's own dev machine, not speculative (see
    _check_vcredist_uninstall_key).
    """
    x86_version = _check_vcredist_runtimes_key("x86") or _check_vcredist_uninstall_key("x86")
    x64_version = _check_vcredist_runtimes_key("x64") or _check_vcredist_uninstall_key("x64")
    return VcRedistResult(
        x86_status=VcRedistStatus.OK if x86_version else VcRedistStatus.NOT_FOUND,
        x64_status=VcRedistStatus.OK if x64_version else VcRedistStatus.NOT_FOUND,
        x86_version=x86_version,
        x64_version=x64_version,
    )


def _download_and_run_signed_installer(
    url: str, filename: str, expected_signer: str, *, args: list, on_status: Callable[[str], None],
) -> tuple[bool, str]:
    """Shared download-verify-run flow for installers that, unlike the Python
    one, have no documented hash to pin against (VC++'s "latest" package is
    updated in place by Microsoft with no fixed hash) -- Authenticode signer
    verification is the real, available integrity check, so it's the only
    one applied here.
    """
    try:
        with tempfile.TemporaryDirectory(prefix="py4gw_prereq_") as tmp_dir:
            installer_path = Path(tmp_dir) / filename
            _download_file(url, installer_path, on_status=on_status)

            on_status("Verifying download...")
            sig_ok, sig_message = _verify_authenticode_signer(installer_path, expected_signer)
            if not sig_ok:
                return False, f"Signature check failed -- not installing. {sig_message}"

            on_status(f"Installing {filename}...")
            proc = subprocess.run([str(installer_path), *args], timeout=900.0)
            if proc.returncode != 0:
                return False, f"Installer exited with code {proc.returncode} (may have been cancelled)."

            on_status("Done.")
            return True, f"{filename} installed."
    except urllib.error.URLError as e:
        return False, f"Download failed: {e}"
    except subprocess.TimeoutExpired:
        return False, "Installer timed out -- may still be running in the background."
    except OSError as e:
        return False, f"Unexpected error: {e}"


def download_and_install_vcredist(arch: str, on_status: Callable[[str], None]) -> tuple[bool, str]:
    """arch is "x86" or "x64". Runs the installer with its normal UI visible
    (no /quiet or /passive), matching this project's transparency choice."""
    url = VCREDIST_2013_X86_URL if arch == "x86" else VCREDIST_2013_X64_URL
    return _download_and_run_signed_installer(
        url, f"vcredist_2013_{arch}.exe", VCREDIST_EXPECTED_SIGNER, args=[], on_status=on_status
    )


# -----------------------------------------------------------------------------
# Phase 2 (continued) -- DirectX End-User Runtime (June 2010). Confirmed
# necessary by Apo directly (Discord, 2026-04-05), linking Microsoft's own
# download page and stating it's "necessary for install" -- a real, separate
# requirement from the DirectX *SDK* check considered and deliberately left
# out above (see this module's own docstring for the distinction).
# -----------------------------------------------------------------------------

DIRECTX_RUNTIME_DOWNLOAD_URL = (
    "https://download.microsoft.com/download/8/4/a/84a35bf1-dafe-4ae8-82af-ad2ae20b6b14/directx_Jun2010_redist.exe"
)
DIRECTX_RUNTIME_INFO_PAGE_URL = "https://www.microsoft.com/en-us/download/details.aspx?id=8109"
DIRECTX_RUNTIME_EXPECTED_SIGNER = "Microsoft Corporation"
# Quoted directly from Microsoft's own download page (id=8109) -- shown in
# the confirm-before-install UI so the user knows this *before* agreeing to
# install, not after.
DIRECTX_RUNTIME_CANNOT_UNINSTALL_NOTICE = "The DirectX runtime cannot be uninstalled."

# GW.exe is a 2005-era DirectX 9 title, so D3DX9 is the most likely actual
# dependency -- the June 2010 package also covers D3DX10/11, XAudio 2.7,
# XInput 1.3, XACT, and Managed DirectX, but those read as less relevant to
# this specific game. d3dx9_43.dll is the *last* D3DX9 sub-version this
# package installs (confirmed directly: extracting the real installer and
# inspecting its cabinet files shows every D3DX9 sub-version from _24
# through _43 present cumulatively) -- checking for the highest one means
# checking for "the package has fully run", not just some older partial
# install from something else.
DIRECTX_RUNTIME_MARKER_DLL = "d3dx9_43.dll"


class DirectXRuntimeStatus(Enum):
    OK = "ok"
    NOT_FOUND = "not_found"


@dataclasses.dataclass
class DirectXRuntimeResult:
    status: DirectXRuntimeStatus
    marker_path: Optional[str] = None

    @property
    def is_ok(self) -> bool:
        return self.status == DirectXRuntimeStatus.OK

    @property
    def diagnostic_text(self) -> str:
        if self.is_ok:
            return f"{DIRECTX_RUNTIME_MARKER_DLL} found at {self.marker_path}"
        return f"{DIRECTX_RUNTIME_MARKER_DLL} not found"


def _syswow64_dir() -> Optional[str]:
    """The real SysWOW64 directory, via the WinAPI function built exactly
    for this (GetSystemWow64DirectoryW) rather than hardcoding
    "C:\\Windows\\SysWOW64" -- handles a non-standard Windows install drive
    correctly, and cleanly returns None on a true 32-bit OS (vanishingly
    rare today) where no such directory exists at all, rather than guessing
    a path that wouldn't exist there anyway. Confirmed directly on a real
    machine: returns "C:\\windows\\SysWOW64", and the marker DLL was found
    there (that machine already had some DirectX runtime installed).
    """
    buf = ctypes.create_unicode_buffer(260)
    n = ctypes.windll.kernel32.GetSystemWow64DirectoryW(buf, 260)
    return buf.value if n > 0 else None


def check_directx_runtime_prereq() -> DirectXRuntimeResult:
    """Checks for DIRECTX_RUNTIME_MARKER_DLL directly in SysWOW64 (this
    launcher targets 32-bit, so the 32-bit copy of the DLL is what matters,
    regardless of whether a 64-bit copy also exists in System32) rather than
    an Add/Remove Programs registry entry, unlike the VC++ check -- this
    installer is documented (and widely reported in game-dev/Steamworks
    circles) not to reliably register one at all, so a registry-based check
    isn't a fallback-worthy option here, it's just not reliable, period.
    """
    wow64_dir = _syswow64_dir()
    if wow64_dir is None:
        return DirectXRuntimeResult(DirectXRuntimeStatus.NOT_FOUND)
    marker_path = os.path.join(wow64_dir, DIRECTX_RUNTIME_MARKER_DLL)
    if os.path.isfile(marker_path):
        return DirectXRuntimeResult(DirectXRuntimeStatus.OK, marker_path=marker_path)
    return DirectXRuntimeResult(DirectXRuntimeStatus.NOT_FOUND)


def download_and_install_directx_runtime(on_status: Callable[[str], None]) -> tuple[bool, str]:
    """The DirectX End-User Runtime installer is a self-extracting archive,
    not a direct installer. Confirmed directly against the real download
    (not assumed): its own /? help dialog documents `/Q` (quiet), `/T:<path>`
    (temp working folder), and `/C` ("extract files only to the folder when
    used also with /T") -- /C is required *alongside* /T to get extract-only
    behavior; a first attempt with just `/Q /T:<path>` produced a real
    "Command line option syntax error" dialog. `/Q /T:<path> /C` together
    were then confirmed to correctly extract DXSETUP.exe plus its .cab files
    with no UI at all.

    DXSETUP.exe itself is then run with `/silent` -- confirmed both by the
    literal string "/silent" embedded in the real DXSETUP.exe binary and by
    actually running it for real: completed in ~14s, genuinely no UI, exit
    code 0, no stray processes left behind afterward.

    Microsoft's own download page states directly: "The DirectX runtime
    cannot be uninstalled" -- surfaced in the confirm-before-install UI (see
    DIRECTX_RUNTIME_CANNOT_UNINSTALL_NOTICE) so the user knows that before
    agreeing, not after.
    """
    try:
        with tempfile.TemporaryDirectory(prefix="py4gw_prereq_") as tmp_dir:
            tmp_path = Path(tmp_dir)
            installer_path = tmp_path / "directx_Jun2010_redist.exe"
            _download_file(DIRECTX_RUNTIME_DOWNLOAD_URL, installer_path, on_status=on_status)

            on_status("Verifying download...")
            sig_ok, sig_message = _verify_authenticode_signer(installer_path, DIRECTX_RUNTIME_EXPECTED_SIGNER)
            if not sig_ok:
                return False, f"Signature check failed -- not installing. {sig_message}"

            extract_dir = tmp_path / "extracted"
            extract_dir.mkdir()
            on_status("Extracting...")
            extract_proc = subprocess.run(
                [str(installer_path), "/Q", f"/T:{extract_dir}", "/C"], timeout=300.0
            )
            if extract_proc.returncode != 0:
                return False, f"Extraction exited with code {extract_proc.returncode}."

            dxsetup_path = extract_dir / "DXSETUP.exe"
            if not dxsetup_path.exists():
                return False, "Extraction finished but DXSETUP.exe wasn't where it was expected."

            on_status("Installing DirectX End-User Runtime...")
            install_proc = subprocess.run([str(dxsetup_path), "/silent"], timeout=300.0)
            if install_proc.returncode != 0:
                return False, f"Installer exited with code {install_proc.returncode}."

            on_status("Done.")
            return True, "DirectX End-User Runtime installed."
    except urllib.error.URLError as e:
        return False, f"Download failed: {e}"
    except subprocess.TimeoutExpired:
        return False, "Installer timed out -- may still be running in the background."
    except OSError as e:
        return False, f"Unexpected error: {e}"
