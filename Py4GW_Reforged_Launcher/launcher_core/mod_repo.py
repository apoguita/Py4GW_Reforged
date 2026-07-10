"""Detection, first-run clone, and update-checking for the actual Py4GW_Reforged
mod-code checkout -- a different concern from launcher_core.prereqs (which asks
"is the right *software* installed") and from config_seeding (which asks "do the
right *config files* exist"). This asks "does the mod's actual code exist at the
configured location, and is it current."

Uses dulwich (a pure-Python git implementation, pip-installable, no compiled
extension required at runtime beyond what its own wheel already ships) rather
than shelling out to a system git -- confirmed directly that this environment,
like the target machines this is written for, has no guarantee of a system git
install, and this project already keeps a deliberately short, careful list of
things a fresh machine needs (see launcher_core.prereqs); adding "install Git"
to that list just to clone one repo would be a heavier ask than pulling in a
pure-Python library that ships inside this launcher's own PyInstaller bundle.

Every function here is synchronous and blocking (a clone or fetch takes real
network time) -- same convention as launcher_core.prereqs: callers on the UI
thread run these on a background thread and poll for the result, never call
them directly from the render loop.
"""

from __future__ import annotations

import dataclasses
import shutil
from enum import Enum
from pathlib import Path
from typing import Callable, Optional

from dulwich import porcelain
from dulwich.errors import NotGitRepository, WorkingTreeModifiedError
from dulwich.porcelain import DivergedBranches
from dulwich.repo import Repo
from dulwich.walk import Walker

MOD_REPO_URL = "https://github.com/apoguita/Py4GW_Reforged.git"

# Py4GWCoreLib/ existing is the marker checked for a valid checkout -- not just
# "the folder exists," which would false-positive on an empty directory or an
# unrelated one that happens to be configured by mistake. Chosen because it's a
# real, top-level directory in the actual mod repo (confirmed directly: present
# in a real clone of MOD_REPO_URL) that isn't something a user would plausibly
# create by hand.
MOD_REPO_MARKER_DIR = "Py4GWCoreLib"


class CheckoutStatus(Enum):
    OK = "ok"
    NOT_FOUND = "not_found"  # marker directory doesn't exist at the configured location
    NOT_A_GIT_REPO = "not_a_git_repo"  # marker exists, but no .git next to it


@dataclasses.dataclass
class CheckoutDetectionResult:
    status: CheckoutStatus
    path: Path

    @property
    def is_ok(self) -> bool:
        return self.status == CheckoutStatus.OK


def detect_checkout(path: Path) -> CheckoutDetectionResult:
    """Cheap, synchronous, filesystem-only check -- safe to call on every
    launch and after every clone/update, same as prereqs.py's own checks."""
    path = Path(path)
    if not (path / MOD_REPO_MARKER_DIR).is_dir():
        return CheckoutDetectionResult(CheckoutStatus.NOT_FOUND, path)
    if not (path / ".git").exists():
        return CheckoutDetectionResult(CheckoutStatus.NOT_A_GIT_REPO, path)
    return CheckoutDetectionResult(CheckoutStatus.OK, path)


class _ProgressStream:
    """Adapts dulwich's errstream= (a raw binary-write target it sends git's own
    textual progress lines to, same wire format real git's own stderr progress
    uses) into this project's Callable[[str], None] on_status convention used
    elsewhere (prereqs.py's installers). Splits on both \\r and \\n since git's
    progress lines are \\r-terminated *during* a phase (e.g. "Counting objects:
    N%") and only \\n-terminated once that phase finishes -- without splitting on
    \\r too, on_status would only ever see one giant final blob of text instead
    of live updating percentages.
    """

    def __init__(self, on_status: Callable[[str], None]):
        self._on_status = on_status

    def write(self, data: bytes) -> int:
        text = data.decode("utf-8", errors="replace")
        for line in text.replace("\r", "\n").split("\n"):
            line = line.strip()
            if line:
                self._on_status(line)
        return len(data)

    def flush(self) -> None:
        pass


def clone_mod_repo(target: Path, on_status: Callable[[str], None]) -> tuple[bool, str]:
    """Clones MOD_REPO_URL into target via dulwich, reporting real progress
    through on_status as it happens (confirmed directly: cloning the real,
    current MOD_REPO_URL -- about 615MB, ~43000 objects -- took roughly 30
    seconds on a normal connection; on_status is what lets the UI show that
    instead of appearing frozen for half a minute).

    target does not need to be empty or nonexistent -- confirmed directly, on
    the real repo, that this is safe: cloning into an already-populated
    directory only ever writes paths that exist in the source tree (creating
    or overwriting them, including overwriting a pre-existing file whose
    content actually differs), and never touches or deletes anything already
    on disk at a path the source tree doesn't have. This matters because the
    real default target (config_seeding._mod_root()) is this launcher's own
    parent directory, which already contains the running launcher's own
    Py4GW_Reforged_Launcher/ subfolder -- today MOD_REPO_URL's tree has no
    entry at that path at all (this launcher isn't upstreamed yet), so there's
    no overlap in practice, but the behavior above is what makes that safe
    regardless of whether that ever changes.

    Clones into a fresh sibling temp directory first, only merging the result
    into target on success (via shutil.copytree's dirs_exist_ok merge, then
    removing the temp copy) -- guarantees that ANY failure partway through (a
    dropped connection mid-fetch, a disk error mid-checkout, etc.) leaves
    target exactly as it was before this call, with no half-written .git or
    partial checkout left mixed in with whatever's already there (notably,
    this launcher's own files) for a retry to trip over.
    """
    target = Path(target)
    tmp_target = target.parent / f".py4gw_reforged_clone_tmp_{target.name}"
    if tmp_target.exists():
        shutil.rmtree(tmp_target, ignore_errors=True)
    tmp_target.mkdir(parents=True)

    try:
        on_status("Cloning Py4GW_Reforged...")
        repo = porcelain.clone(MOD_REPO_URL, str(tmp_target), errstream=_ProgressStream(on_status))
        repo.close()
    except Exception as e:
        shutil.rmtree(tmp_target, ignore_errors=True)
        return False, f"Clone failed: {e}"

    try:
        on_status(f"Finalizing into {target}...")
        shutil.copytree(tmp_target, target, dirs_exist_ok=True)
    except OSError as e:
        return False, f"Clone succeeded but couldn't be moved into {target}: {e}"
    finally:
        shutil.rmtree(tmp_target, ignore_errors=True)

    return True, f"Py4GW_Reforged cloned to {target}."


class UpdateStatus(Enum):
    UP_TO_DATE = "up_to_date"
    BEHIND = "behind"  # local is a strict ancestor of remote -- fast-forward possible
    AHEAD = "ahead"  # local has commits the remote doesn't -- nothing to update
    DIVERGED = "diverged"  # both sides have commits the other lacks -- not a simple fast-forward
    ERROR = "error"


@dataclasses.dataclass
class UpdateCheckResult:
    status: UpdateStatus
    behind_count: int = 0
    ahead_count: int = 0
    message: str = ""


def check_for_updates(path: Path) -> UpdateCheckResult:
    """Fetches MOD_REPO_URL and compares local HEAD against the remote's
    default branch (whichever ref its own HEAD symref points at -- not a
    hardcoded "main"/"master" guess). A fetch downloads objects and updates
    this repo's remote-tracking refs, exactly like real git's own "git fetch"
    -- it never touches the working tree, the local branch pointer, or any
    uncommitted changes, so this is safe to run speculatively (e.g. on a
    schedule or an explicit "Check for updates" click) without risking
    anything the update step itself would need to worry about.

    Ahead/behind counts come from dulwich's Walker with include/exclude, the
    same technique `git rev-list --left-right --count` uses: "behind" is how
    many commits are reachable from the remote's tip but not from local HEAD,
    "ahead" is the reverse. Both zero means identical; only-behind means a
    plain fast-forward is possible; only-ahead means the local checkout has
    commits of its own (unusual for this use case, but not an error); both
    nonzero means the two have diverged and can't be reconciled by a simple
    fast-forward.
    """
    try:
        repo = Repo(str(path))
    except NotGitRepository as e:
        return UpdateCheckResult(UpdateStatus.ERROR, message=f"Not a git repository: {e}")

    try:
        try:
            local_sha = repo.head()
        except KeyError as e:
            return UpdateCheckResult(UpdateStatus.ERROR, message=f"Could not resolve local HEAD: {e}")

        try:
            fetch_result = porcelain.fetch(repo, MOD_REPO_URL)
        except Exception as e:
            return UpdateCheckResult(UpdateStatus.ERROR, message=f"Fetch failed: {e}")

        default_ref = fetch_result.symrefs.get(b"HEAD")
        remote_sha = fetch_result.refs.get(default_ref) if default_ref is not None else None
        if remote_sha is None:
            return UpdateCheckResult(
                UpdateStatus.ERROR, message="Could not determine the remote's default branch"
            )

        if local_sha == remote_sha:
            return UpdateCheckResult(UpdateStatus.UP_TO_DATE, message="Up to date.")

        behind = sum(1 for _ in Walker(repo.object_store, include=[remote_sha], exclude=[local_sha]))
        ahead = sum(1 for _ in Walker(repo.object_store, include=[local_sha], exclude=[remote_sha]))

        if ahead == 0 and behind > 0:
            return UpdateCheckResult(
                UpdateStatus.BEHIND, behind_count=behind,
                message=f"Behind by {behind} commit{'s' if behind != 1 else ''}.",
            )
        if behind == 0 and ahead > 0:
            return UpdateCheckResult(
                UpdateStatus.AHEAD, ahead_count=ahead,
                message=f"Ahead of the remote by {ahead} commit{'s' if ahead != 1 else ''} -- nothing to update.",
            )
        return UpdateCheckResult(
            UpdateStatus.DIVERGED, behind_count=behind, ahead_count=ahead,
            message=f"Diverged from the remote ({ahead} ahead, {behind} behind) -- can't fast-forward.",
        )
    finally:
        repo.close()


def get_uncommitted_changes(path: Path) -> list[str]:
    """Human-readable list of paths with real, content-level uncommitted
    changes (staged, unstaged, or untracked) -- empty means clean.

    Re-validates porcelain.status()'s "staged: modify" entries against actual
    blob content before counting them as dirty, rather than trusting that list
    at face value: confirmed directly (not assumed) that a *pure file-mode*
    difference -- e.g. the executable bit, which NTFS has no real equivalent
    of -- can appear in status()'s staged-modify list with byte-identical file
    content, reproduced via dulwich's own porcelain.reset(). A real content
    difference still counts as dirty -- only a pure mode-only difference is
    excluded.

    Not used to gate update_mod_repo (see its own docstring for why a blanket
    "any uncommitted change anywhere" check over-blocks) -- this is available
    for informational display only, e.g. "N files have local changes," if a
    caller wants to show that without it deciding whether an update can run.
    """
    repo = Repo(str(path))
    try:
        status = porcelain.status(str(path))
        dirty: list[str] = []

        for p in status.staged["add"]:
            dirty.append(f"{p.decode(errors='replace')} [staged, new]")
        for p in status.staged["delete"]:
            dirty.append(f"{p.decode(errors='replace')} [staged, deleted]")
        for p in status.staged["modify"]:
            if _content_actually_differs_from_head(repo, p):
                dirty.append(f"{p.decode(errors='replace')} [staged, modified]")

        for p in status.unstaged:
            dirty.append(f"{p.decode(errors='replace')} [modified]")
        for p in status.untracked:
            dirty.append(f"{p.decode(errors='replace')} [untracked]")
        return dirty
    finally:
        repo.close()


def _content_actually_differs_from_head(repo: Repo, path: bytes) -> bool:
    """True if path's indexed blob content differs from HEAD's tree -- see
    get_uncommitted_changes' docstring for why this, rather than trusting
    porcelain.status()'s raw staged/modify list, which can flag a pure
    mode-only difference as "modify" even when content is identical."""
    try:
        index_entry = repo.open_index()[path]
    except KeyError:
        return True  # Not in the index at all -- not a mode-only situation.
    try:
        head_commit = repo[repo.head()]
        tree = repo[head_commit.tree]
        _mode, tree_sha = tree.lookup_path(repo.object_store.__getitem__, path)
    except KeyError:
        return True  # Not in HEAD's tree either -- a real add, not mode noise.
    return index_entry.sha != tree_sha


def update_mod_repo(path: Path, on_status: Callable[[str], None]) -> tuple[bool, str]:
    """Fast-forward-only update via dulwich's porcelain.pull. ff_only=True
    means a genuine divergence (local commits the remote doesn't have) raises
    rather than merging or rewriting anything -- this never does more than
    fast-forward.

    Deliberately does NOT pre-check get_uncommitted_changes() and refuse up
    front over "any uncommitted change anywhere in the checkout" -- confirmed
    directly (reading dulwich's own porcelain.pull source, not assumed) that
    pull only ever touches paths that are actually part of the incoming
    tree-to-tree diff. Py4GW users routinely drop custom scripts into Bots/,
    Widgets/, etc. -- untracked files like those are never part of either
    tree, so pull never looks at, modifies, or deletes them regardless of how
    many exist. A blanket pre-check would have permanently blocked "Update
    now" for exactly the users most likely to add their own scripts and then
    want an update, which defeats the feature. The same reasoning applies to
    a tracked file edited by hand that the incoming update doesn't touch --
    it's not part of the diff either, so pull leaves it alone.

    Real conflicts -- a tracked file edited by hand where the incoming update
    *does* touch that same file -- are caught precisely by dulwich itself:
    update_working_tree raises WorkingTreeModifiedError naming the exact
    path ("Your local changes to '<path>' would be overwritten by
    checkout..."), which is caught below and surfaced as the failure reason.
    Nothing gets overwritten either way; this only changes how narrowly a
    real conflict is detected.
    """
    try:
        repo = Repo(str(path))
    except NotGitRepository as e:
        return False, f"Not a git repository: {e}"

    try:
        on_status("Fetching updates...")
        porcelain.pull(repo, MOD_REPO_URL, errstream=_ProgressStream(on_status), ff_only=True)
    except WorkingTreeModifiedError as e:
        return False, f"Update refused: {e}"
    except DivergedBranches as e:
        return False, f"Local checkout has diverged from the remote and can't be fast-forwarded: {e}"
    except Exception as e:
        return False, f"Update failed: {e}"
    finally:
        repo.close()

    return True, "Py4GW_Reforged updated."
