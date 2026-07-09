# Py4GW_Reforged_Launcher — Project Briefing (fresh session start)

This replaces the old `PY4GW_LAUNCHER_HANDOVER.md`. That file is retired —
Chris has a private copy elsewhere. This document is deliberately written to
contain only project/technical state, safe to exist inside or alongside a
now-public repo. If you're a Claude Code session reading this for the first
time, your first task is to verify the current environment actually matches
what's described below before doing anything else — don't assume it's
already correct.

## Read this first: the one rule that matters most

**Never add a private notes/context document to this repo, under any
filename.** This repo is public and permanent — there is no private staging
area anymore. Earlier in this project, a private handover document was
accidentally swept into a bulk reorg commit and briefly reached a public
fork before being caught. The fix was deleting and recreating the fork from
scratch to fully remove it from history — that's expensive to redo, so don't
recreate the conditions for it. If Chris ever wants a persistent private
notes file maintained again, it must live in a folder **outside** this
repo's directory tree entirely — not just gitignored, not present in the
folder at all. Add a defensive `.gitignore` entry for the old filename
(`PY4GW_LAUNCHER_HANDOVER.md`) as a backstop, but don't rely on it as the
only safeguard.

## Current repo state

- **Primary repo (working + public):** a fresh fork of `apoguita/Py4GW_Reforged`
  at `github.com/Royel-Payne/Py4GW_Reforged`. This is a clean fork created
  after deleting an earlier one that had the exposure incident above — it
  has no tainted history.
- **Remotes:** `origin` = Chris's fork (the one above), `upstream` =
  `apoguita/Py4GW_Reforged` (Apo's real repo, for pulling his future
  updates), `backup` = `Royel-Payne/Py4GW_Reforged-backup` (private,
  disaster-recovery mirror of the code only — unrelated to the privacy
  policy above, just hardware-failure insurance).
- **Branch:** `feature/launcher` (renamed from the old `trial/py4gw-launcher-gw1`
  now that this is past the trial stage).
- **Visibility:** public. Apo already knows this project exists and gave a
  green light in principle ("you've done nice things, let me know when you
  have something to show, we'll look at it") — the code being visible isn't
  a concern anymore. Only the retired handover doc's more candid internal
  content needed to stay private, and that's now handled by physical
  separation, not repo visibility.
- **Python environment:** 32-bit Python 3.13 venv at
  `C:\Users\Chris\Projects\Py4GW\myenv`. This is a hard technical
  requirement, not a preference — no 64-bit `imgui_bundle` wheel exists, and
  DLL injection requires matching bitness with the 32-bit `Gw.exe`.
  `imgui_bundle` had to be source-built (no PyPI wheel for 32-bit).

## Scope (confirmed, GW1-only)

- GW2 stays on the existing C# GWxLauncher — not ported here.
- GWToolbox++ dropped — incompatible with current Py4GW.
- Py4GW and gMod are the only injection targets. Steam login/injection is
  confirmed dead weight — previously tested infeasible, and the reference
  C# implementation's Steam-path code (`SteamLaunchService`,
  `SteamProcessAttachService`) should never be reused or searched for GW1
  launch logic.
- Whether Py4GW actually functions beyond initialization (scripts, widgets,
  API calls) is explicitly **not** this launcher's concern — that's Apo's
  team's responsibility. Reliable injection is the finish line here.

## What's built and confirmed working

All of the following were verified through real interactive testing against
actual running processes (screenshots, PID cross-checks against `tasklist`,
not just code review) — that standard is worth preserving going forward,
since it's what caught every real bug below.

1. **Reliable Py4GW DLL injection into GW1**, confirmed via the in-game
   console showing `Py4GW initialized` / `ImGui initialized on Guild Wars
   render device`.
2. **Root cause of the original injection failures was never elevation,
   AV/EDR, or the OpenProcess access-rights mask** — all three were
   investigated and ruled out. The real causes were (a) occasionally
   catching the game's own update/patch relaunch process mid-teardown, and
   (b) a pipeline bug that blocked for the full wait-timeout before even
   checking whether a window existed.
3. **Stall-based wait logic**, replacing fixed timeouts: uses
   `IsHungAppWindow` to tell "still legitimately busy" (e.g. downloading a
   large update) apart from "actually stuck," with a generous absolute
   ceiling only as a last-resort safety valve. Validated against three real
   scenarios: no-update fast path (~5.4s end to end), exit-and-relaunch via
   a `Gw.tmp` bridge process for major client updates (handled by an
   existing rescan path), and an in-place large data-file re-download (e.g.
   `Gw.dat`, ~7k files) happening entirely inside the already-injected
   process with no hop at all.
4. **Multi-instance/concurrent-client tracking** — verified launching two
   profiles simultaneously with independent per-card running state, correct
   PID-to-profile mapping, bidirectional foreground-switching, and
   independent close-detection (closing one doesn't affect the other).
5. **Window title override** — `SetWindowTextW` applied once a launch is
   confirmed running, format `"Guild Wars Reforged — {profile_name}"`.
6. **Rehydration on launcher restart** — on startup, scans for already-running
   `Gw.exe` processes and matches them back to profiles by exact
   executable path (ported from GWxLauncher's
   `Gw1InstanceTracker.FindProcessesByExactPath` pattern), so closing and
   reopening the launcher doesn't lose track of games that are still running.
7. **Add/edit profile UI** — built into the existing Settings window rather
   than a second duplicate form. Password field never displays the real
   stored value; DPAPI-encrypted password never touches disk in plaintext;
   blank password on edit leaves the stored value untouched. Validates the
   exe path exists before allowing save.
8. **Startup failure safety net** — wrapped in a stdlib-only guard
   (`ctypes.windll.user32.MessageBoxW`) so a missing dependency or wrong
   Python architecture shows a clear message box instead of failing
   completely silently, which is what happened before (the app uses
   `pythonw.exe` to avoid a console flash, which also means unhandled
   exceptions previously produced zero visible feedback at all).
9. **Standalone packaging** — a PyInstaller `--onefile` build confirmed
   working on a genuinely clean machine with no Python ever installed,
   including a real, full Py4GW injection through the frozen exe.
   `imgui_bundle` needed `--collect-all` (no dedicated PyInstaller hook
   exists for it; default analysis misses its compiled extension's sibling
   DLL and data assets). ~32MB, ~1.2s startup. No SmartScreen warning
   observed yet, but that test had no Mark-of-the-Web (built and run
   locally) — a real test against an actual browser-downloaded release is
   still outstanding.
10. **DPI-aware, content-measured window sizing** — both windows size
    themselves from live font/DPI scale (`hello_imgui.em_size()`) and real
    measured text/content rather than hardcoded pixels, fixing clipping that
    showed up specifically on a higher-DPI laptop display. Size and position
    persist across restarts.

## Not yet built / explicitly deferred

- gMod's early-injection timing strategy (fundamentally different from
  Py4GW's late-injection approach — gMod needs precise timing during
  suspended process creation). `GameProfile.gmod_enabled` (and related
  fields) already exist in the data model; no implementation yet.
- A first-run setup wizard for cloning/updating the actual Py4GW_Reforged
  game-code repo itself. Deliberately kept separate from the packaging work
  above — packaging proved the launcher app itself can be a clean standalone
  exe; whether/how it also bootstraps the underlying Py4GW installation is a
  separate, still-open question.
- Legacy `accounts.json` migration/import tool from the old GWxLauncher/
  Py4GW_Launcher setups.
- Name-obfuscation config delivery. The `pre_injection_config`/
  `PreInjectionConfig` parameter exists as an explicit, documented no-op
  stub — intentionally not implemented since the real config format/shape
  isn't confirmed yet.
- Minor UI polish flagged but not yet addressed: the placeholder
  avatar/icon circle on each card has no content (a first-letter treatment
  was suggested), the "N profile(s) loaded from profile_store." status text
  reads like a dev log line rather than end-user copy, and the "Reload
  profiles" button may be redundant now that saving already auto-refreshes
  the grid.

## Working conventions worth preserving

- Test interactively through the real UI and real OS processes, cross-checked
  against actual state (`tasklist`, PIDs, window handles) — not just "the
  code looks right" or "it didn't crash." This standard is what caught every
  real bug so far: an `EnumWindows` crash on a `False` return, a tuple-order
  bug in `AttachThreadInput` args, and the sequential-wait timing bug that
  silently added minutes to every launch.
- Commit selectively — review the actual file list before committing, never
  a blind blanket add. This matters more now than ever given the repo is
  public and permanent.
- 32-bit is a hard architectural requirement tied to DLL injection, not a
  style choice — don't "fix" it toward 64-bit.

## Next step

Confirm the points in "Current repo state" actually match reality (remotes,
branch, folder layout, `.gitignore` entry present) before continuing any
other work. After that, next priorities are Chris's call — the open items
above are the known candidates.
