"""Terminate a running client process by PID.

Phase E (individual-launch wiring) needs a "Stop" that kills an already-running,
already-injected GW client -- a different, simpler thing than cancelling an
in-progress launch (which never touches an already-launched client; see TODO.md).
No such utility existed before this: gw1_launch.py's only TerminateProcess is its
own failed-launch abort, which acts on the process HANDLE it created, not an
arbitrary PID. This is the by-PID version.

On Windows psutil's terminate() and kill() are both TerminateProcess (there's no
graceful signal), so a single terminate()+wait is enough; kill() is a belt-and-
suspenders retry if the process somehow outlives the wait.
"""
from __future__ import annotations

import psutil


def terminate_process(pid: int, timeout: float = 5.0) -> bool:
    """Terminate the process with `pid`. Returns True if it's gone afterwards
    (including if it was already gone), False only if it could not be killed."""
    try:
        proc = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return True  # already gone -- Stop's goal is already met
    try:
        proc.terminate()
        try:
            proc.wait(timeout=timeout)
        except psutil.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=timeout)
        return True
    except psutil.NoSuchProcess:
        return True
    except (psutil.AccessDenied, psutil.TimeoutExpired, OSError):
        return False
