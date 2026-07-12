"""Check whether a newer Py4GW_Reforged_Launcher release exists on GitHub, by
comparing launcher_core.version.__version__ against the latest release's
tag_name. A single stdlib urllib.request GET + JSON parse against GitHub's
releases API -- no new dependency (requests, etc.) needed for something
this simple.

Comparison is deliberately simple: a numeric (major, minor, patch) tuple,
not real semver-with-prerelease ordering. Every tag this project has ever
cut is "X.Y.Z-alpha" -- the "-alpha" suffix never varies and carries no
ordering information, so it's stripped rather than compared. This is a
low-stakes informational notice, not a release gate, so building real
semver/prerelease-ordering logic isn't worth the complexity here.

Every function here is synchronous and blocking (a real network call) --
same convention as launcher_core.prereqs/mod_repo: callers on the UI thread
run this on a background thread and poll for the result, never call it
directly from the render loop.
"""

from __future__ import annotations

import dataclasses
import json
import urllib.error
import urllib.request
from typing import Optional, Tuple

from launcher_core.settings_store import load_launcher_release_repo


def _parse_version_tuple(version: str) -> Optional[Tuple[int, ...]]:
    """Parse "0.2.2-alpha" into (0, 2, 2), ignoring the prerelease suffix.
    Returns None on anything that doesn't cleanly parse as dot-separated
    integers -- callers treat that as "can't compare" rather than raising.
    """
    base = version.split("-", 1)[0]
    parts = base.split(".")
    try:
        return tuple(int(part) for part in parts)
    except ValueError:
        return None


def is_newer_version_available(latest_tag: str, current_version: str) -> bool:
    """True only if latest_tag is a real, strictly newer version than
    current_version. False (i.e. "you're up to date") both when they're
    equal and when either fails to parse -- deliberately the same fallback
    as an unparseable tag, so a local build that happens to run ahead of
    the last published tag (e.g. mid-release, before publishing) shows the
    same "up to date" message instead of a misleading "newer version
    available" pointing at an actually-older release.
    """
    latest = _parse_version_tuple(latest_tag)
    current = _parse_version_tuple(current_version)
    if latest is None or current is None:
        return False
    return latest > current


def _releases_api_url() -> str:
    return f"https://api.github.com/repos/{load_launcher_release_repo()}/releases/latest"


def releases_page_url() -> str:
    """Read fresh each call (not a module-level constant) so a manual
    launcher_release_repo edit in launcher_settings.json takes effect on the
    very next check/click, same as _releases_api_url below -- no restart
    needed, matching every other settings_store-backed value in this app.
    """
    return f"https://github.com/{load_launcher_release_repo()}/releases"


@dataclasses.dataclass
class UpdateCheckResult:
    # None means the check itself failed (no internet, GitHub down, rate
    # limited, unexpected response shape) -- never raised, always this.
    latest_tag: Optional[str]
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.latest_tag is not None


def fetch_latest_release_tag(timeout: float = 5.0) -> UpdateCheckResult:
    """Blocking. Any failure returns a result with latest_tag=None rather
    than raising -- an update check failing silently (no internet, GitHub
    down, rate-limited) is the entire point; see launcher.py's
    UpdateCheckState, which never surfaces this as an error or delays
    startup on it.
    """
    try:
        # GitHub's API rejects requests with no User-Agent header (403), so
        # this can't be a bare urlopen(url) call.
        request = urllib.request.Request(
            _releases_api_url(),
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "Py4GW_Reforged_Launcher",
            },
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
        tag = data.get("tag_name")
        if not tag:
            return UpdateCheckResult(latest_tag=None, error="Unexpected response shape (no tag_name)")
        # Confirmed live against the real repo: its actual release tags are
        # "v0.1.0-alpha"-style (leading "v"), while launcher_core.version's
        # __version__ deliberately isn't (that's a git-tag convention, not
        # how this app displays its own version elsewhere) -- strip it here
        # so the equality check in show_app_settings_window compares two
        # values in the same format instead of always mismatching on the
        # prefix alone.
        tag = str(tag)
        if tag.lower().startswith("v") and tag[1:2].isdigit():
            tag = tag[1:]
        return UpdateCheckResult(latest_tag=tag)
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as e:
        return UpdateCheckResult(latest_tag=None, error=str(e))
