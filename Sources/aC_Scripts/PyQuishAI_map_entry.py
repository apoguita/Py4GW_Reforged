"""Canonical fixed-dialog map-entry support for Simple Vanquish."""

from collections.abc import Mapping, Sequence
import time
from typing import Any, cast


def _normalize_map_entry(entry_data: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and normalize immutable route data before any game action."""
    name = str(entry_data.get("name", "Map entry")).strip() or "Map entry"
    encoded_name = str(entry_data.get("encoded_name", "")).strip()
    source_map_id = int(entry_data.get("source_map_id", 0) or 0)
    expected_map_id = int(entry_data.get("expected_map_id", 0) or 0)
    timeout_ms = max(1_000, int(entry_data.get("timeout_ms", 60_000) or 60_000))
    raw_positions = entry_data.get("button_positions", ())

    if not encoded_name:
        raise ValueError(f"{name}: encoded_name is required")
    if source_map_id <= 0:
        raise ValueError(f"{name}: source_map_id must be positive")
    if expected_map_id <= 0:
        raise ValueError(f"{name}: expected_map_id must be positive")
    if source_map_id == expected_map_id:
        raise ValueError(f"{name}: source and destination maps must differ")
    if isinstance(raw_positions, (str, bytes)) or not isinstance(raw_positions, Sequence):
        raise ValueError(f"{name}: button_positions must be a sequence")

    button_positions = tuple(int(position) for position in raw_positions)
    if not button_positions:
        raise ValueError(f"{name}: at least one dialog page is required")
    if any(position < 0 for position in button_positions):
        raise ValueError(f"{name}: button positions are zero-based and cannot be negative")

    return {
        "name": name,
        "encoded_name": encoded_name,
        "source_map_id": source_map_id,
        "expected_map_id": expected_map_id,
        "button_positions": button_positions,
        "timeout_ms": timeout_ms,
    }


def build_fixed_map_entry_tree(entry_data: Mapping[str, Any], wrappers=None):
    """Return the canonical owner sequence without adding lifecycle behavior."""
    if wrappers is None:
        from Sources.ApoSource.ApoBottingLib import wrappers

    entry = _normalize_map_entry(entry_data)
    return wrappers.Sequence(
        name=f"Simple Vanquish map entry: {entry['name']}",
        children=[
            cast(Any, wrappers.MoveAndAutoDialogByModelID)(
                modelID_or_encStr=entry["encoded_name"],
                button_number=list(entry["button_positions"]),
                log=True,
            ),
            wrappers.WaitForMapLoad(
                map_id=entry["expected_map_id"],
                timeout_ms=entry["timeout_ms"],
            ),
        ],
    )


def _load_runtime_dependencies():
    from Py4GWCoreLib import Map, Routines
    from Py4GWCoreLib.BottingTree import BottingTree
    from Sources.ApoSource.ApoBottingLib import wrappers
    from Sources.ApoSource.ApoBottingLib.helpers import CanonicalDialogueStateScope

    return BottingTree, Map, Routines, wrappers, CanonicalDialogueStateScope


def run_fixed_map_entry(bot, entry_data: Mapping[str, Any]):
    """Run one fixed-dialog entry and restore the host bot's prior HeroAI pause."""
    planner = None
    scope = None
    saved_pause = False
    pause_restore_required = False
    try:
        try:
            entry = _normalize_map_entry(entry_data)
            (
                BottingTree,
                Map,
                Routines,
                wrappers,
                CanonicalDialogueStateScope,
            ) = _load_runtime_dependencies()
            current_map_id = int(Map.GetMapID() or 0)

            if current_map_id == entry["expected_map_id"]:
                return True
            if current_map_id != entry["source_map_id"]:
                raise RuntimeError(
                    f"{entry['name']}: expected source map {entry['source_map_id']}, "
                    f"found {current_map_id}"
                )

            scope = CanonicalDialogueStateScope()
            canonical_sequence = build_fixed_map_entry_tree(entry, wrappers=wrappers)
            planner = BottingTree.Create(
                bot_name=f"Simple Vanquish map entry: {entry['name']}",
                main_routine=canonical_sequence,
                pause_on_combat=False,
                multi_account=False,
                auto_loot=False,
                isolation_enabled=False,
                manage_account_isolation=False,
                headless_heroai_enabled=False,
            )
            saved_pause = bool(bot.Properties.Get("hero_ai_paused", "active"))
            pause_restore_required = True
            bot.Properties.ApplyNow("hero_ai_paused", "active", True)
            planner.Start()

            deadline = time.monotonic() + (entry["timeout_ms"] / 1_000.0) + 15.0
            while planner.IsStarted():
                if time.monotonic() >= deadline:
                    raise RuntimeError(f"{entry['name']}: canonical map-entry owner timed out")
                scope.run(planner.tick)
                yield from Routines.Yield.wait(50)

            status = str(planner.GetBlackboardValue("PLANNER_STATUS", ""))
            if status != "PLANNER: Completed":
                raise RuntimeError(
                    f"{entry['name']}: canonical map-entry owner failed "
                    f"({status or 'no status'})"
                )
            return True
        finally:
            try:
                if scope is not None:
                    scope.close()
            finally:
                try:
                    if planner is not None:
                        planner.Stop()
                finally:
                    if pause_restore_required:
                        bot.Properties.ApplyNow("hero_ai_paused", "active", saved_pause)
    except Exception:
        bot.Stop()
        raise
