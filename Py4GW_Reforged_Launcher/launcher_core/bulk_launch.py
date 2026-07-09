"""Bulk launch pacing -- the anti-bot throttling applied between each account's
launch during a multi-account (team) bulk launch.

Safety-relevant, not just a feature: ArenaNet does IP-based anti-bot detection on
rapid sequential logins. The numbers below are read directly from Chris's real,
proven GWxLauncher implementation (Services/BulkLaunchThrottlingPolicy.cs on
github.com/Royel-Payne/GWxLauncher) -- not guessed, not tuned here.
"""

from __future__ import annotations

import time
from typing import Callable, Optional

# Locked clamp range, from BulkLaunchThrottlingPolicy.cs. Not a UI-adjustable
# setting: the UI may show/accept any value, but clamp_pacing_seconds() is what
# actually runs before the real wait, so a user can't bypass the safety floor
# even by typing something outside this range.
MIN_PACING_SECONDS = 5
MAX_PACING_SECONDS = 90

# Hard-coded, non-configurable cap on the readiness wait -- prevents a stuck or
# failed login from deadlocking the whole bulk launch. Matches
# BulkLaunchThrottlingPolicy.cs's InternalTimeoutMs exactly.
READINESS_TIMEOUT_SECONDS = 15.0

# Grace period before surfacing "waiting for ready" status text, matching the
# C# reference's ReadinessStatusGraceMs -- avoids flashing an alarming message
# during the normal few seconds it takes a window to appear.
READINESS_STATUS_GRACE_SECONDS = 7.0

_READINESS_POLL_INTERVAL_SECONDS = 0.1


def clamp_pacing_seconds(requested_seconds: int) -> int:
    """The actual safety floor/ceiling enforcement. Called here, in the code that
    executes the wait -- not just validated in the UI or the settings store --
    so the clamp can't be bypassed by typing an out-of-range value, editing the
    settings file directly, or any other path that isn't this function.
    """
    return max(MIN_PACING_SECONDS, min(MAX_PACING_SECONDS, requested_seconds))


def wait_for_readiness(
    is_ready: Callable[[], bool],
    *,
    on_status: Optional[Callable[[str], None]] = None,
    timeout_seconds: float = READINESS_TIMEOUT_SECONDS,
) -> bool:
    """Poll `is_ready` until it returns True or `timeout_seconds` elapses (a hard
    cap, not user-configurable -- see module docstring). Returns whether
    readiness was actually detected before the cap.

    A timeout is not an error: the caller proceeds regardless, same as the C#
    reference -- this only exists to prevent deadlock on a stuck/failed login,
    not to abort the whole bulk launch over one slow account.
    """
    start = time.time()
    while True:
        if is_ready():
            return True

        elapsed = time.time() - start
        if elapsed >= timeout_seconds:
            return False

        if on_status is not None and elapsed >= READINESS_STATUS_GRACE_SECONDS:
            remaining = max(0.0, timeout_seconds - elapsed)
            on_status(f"Waiting for account to be ready -- {remaining:.0f}s remaining...")

        time.sleep(_READINESS_POLL_INTERVAL_SECONDS)


def apply_pacing_delay(requested_seconds: int, *, on_status: Optional[Callable[[str], None]] = None) -> int:
    """Sleep for the clamped pacing delay, counting down second by second and
    reporting live status text each second -- a multi-second wait should never
    leave the UI silent. Returns the effective (clamped) delay actually used.
    """
    effective_seconds = clamp_pacing_seconds(requested_seconds)

    for remaining in range(effective_seconds, 0, -1):
        if on_status is not None:
            message = (
                "Launching next account now..." if remaining == 1
                else f"Launching next account in {remaining}s..."
            )
            on_status(message)
        time.sleep(1.0)

    return effective_seconds
