"""Per-character persistence for hex-removal priority overrides.

Backed by the sanctioned :class:`JsonFactory` (account scope). The account is
already the jail namespace (``json/<email>/...``), so a single per-account
document holds every character's config keyed by character name:

    json/<account_email>/HeroAI/HexRemoval.json
        characters/<character_name>/schema
        characters/<character_name>/debug/hex_removal_locks
        characters/<character_name>/hexes/<hex_name>/{caster,ranged_martial,melee,by_profession}

Each character on the account has an independent subtree. The GUI at
HeroAI Control Panel -> Builds -> Hex Removal edits the active character's
subtree; changes autosave through JsonFactory. Serialization is owned entirely
by JsonFactory - there is no hand-rolled JSON/JSONC handling here.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import PySystem

from Py4GWCoreLib.enums_src.GameData_enums import Profession, Profession_Names
from Py4GWCoreLib.GlobalCache.HexRemovalPriority import (
    HexRemovalEntry,
    HexRemovalPriority,
    _HEX_DEFAULTS,
)
from Py4GWCoreLib.py4gwcorelib_src.JsonFactory import JsonFactory


# ============================================================================
# Constants
# ============================================================================

SCHEMA_ID = "py4gw_hex_removal_v1"
# One per-account JSON document holds every character's config, keyed by
# character name under "characters/<name>".
CONFIG_DOC = "HeroAI/HexRemoval.json"

_PRIORITY_BY_NAME: dict[str, HexRemovalPriority] = {
    "NONE": HexRemovalPriority.NONE,
    "LOW":  HexRemovalPriority.LOW,
    "MED":  HexRemovalPriority.MEDIUM,
    "HIGH": HexRemovalPriority.HIGH,
}
_NAME_BY_PRIORITY: dict[HexRemovalPriority, str] = {
    v: k for k, v in _PRIORITY_BY_NAME.items()
}

_PROFESSION_BY_NAME: dict[str, int] = {
    Profession_Names[p]: int(p)
    for p in Profession if p != Profession._None
}
_NAME_BY_PROFESSION_ID: dict[int, str] = {
    v: k for k, v in _PROFESSION_BY_NAME.items()
}

_PROFESSION_ORDER: list[int] = [
    int(Profession.Warrior), int(Profession.Ranger), int(Profession.Monk),
    int(Profession.Necromancer), int(Profession.Mesmer), int(Profession.Elementalist),
    int(Profession.Assassin), int(Profession.Ritualist), int(Profession.Paragon),
    int(Profession.Dervish),
]


# ============================================================================
# In-memory state
# ============================================================================

@dataclass
class HexEntryState:
    entry: HexRemovalEntry


@dataclass
class ConfigState:
    debug_hex_removal: bool = False
    debug_hex_removal_locks: bool = False
    hexes: dict[str, HexEntryState] = field(default_factory=dict)


# Cache key is (email, character_name); reloads when the active
# character changes mid-session (multibox / character switch).
_cache_key: tuple[str, str] = ("", "")
_cache_state: ConfigState | None = None


# ============================================================================
# Logging + store helpers
# ============================================================================

def _log(msg: str) -> None:
    try:
        from Py4GWCoreLib import ConsoleLog
        ConsoleLog("HexRemoval", msg, PySystem.Console.MessageType.Info)
    except Exception:
        pass


def _config_store() -> JsonFactory:
    """The per-account hex-removal document (account scope; binds to the email)."""
    return JsonFactory(CONFIG_DOC)


def _char_key(character_name: str) -> str:
    """JSON path to a character's subtree within the account document."""
    return f"characters/{character_name}"


def _active_account_key() -> tuple[str, str]:
    """Returns (email, character_name). Either may be empty if not ready."""
    try:
        from Py4GWCoreLib.Player import Player
        email = (Player.GetAccountEmail() or "").strip()
        char = (Player.GetName() or "").strip()
        return email, char
    except Exception:
        return "", ""


# ============================================================================
# Parsing (dict subtree -> ConfigState)
# ============================================================================

def _parse_priority(value: object) -> HexRemovalPriority | None:
    if not isinstance(value, str):
        return None
    return _PRIORITY_BY_NAME.get(value.strip().upper())


def _parse_profession_id(value: object) -> int | None:
    if not isinstance(value, str):
        return None
    return _PROFESSION_BY_NAME.get(value.strip())


def _parse_entry(name: str, blob: object) -> HexEntryState | None:
    if not isinstance(blob, dict):
        _log(f"config: skipping '{name}' - not an object")
        return None
    caster = _parse_priority(blob.get("caster"))
    ranged = _parse_priority(blob.get("ranged_martial"))
    melee = _parse_priority(blob.get("melee"))
    if caster is None or ranged is None or melee is None:
        _log(f"config: skipping '{name}' - invalid role priority")
        return None
    by_prof_blob = blob.get("by_profession", {}) or {}
    by_prof: dict[int, HexRemovalPriority] = {}
    if isinstance(by_prof_blob, dict):
        for prof_name, prio_name in by_prof_blob.items():
            pid = _parse_profession_id(prof_name)
            prio = _parse_priority(prio_name)
            if pid is None:
                _log(f"config: '{name}' - unknown profession '{prof_name}', dropped")
                continue
            if prio is None:
                _log(f"config: '{name}' - invalid priority for '{prof_name}', dropped")
                continue
            by_prof[pid] = prio
    # "modified" field in older files is intentionally ignored (legacy).
    return HexEntryState(
        entry=HexRemovalEntry(
            caster=caster,
            ranged_martial=ranged,
            melee=melee,
            by_profession=by_prof,
        ),
    )


def _state_from_dict(data: object) -> ConfigState | None:
    """Build a ConfigState from a character subtree dict (or None if unrecognized)."""
    if not isinstance(data, dict) or data.get("schema") != SCHEMA_ID:
        return None

    state = ConfigState()
    debug_blob = data.get("debug", {}) or {}
    if isinstance(debug_blob, dict):
        state.debug_hex_removal = False
        state.debug_hex_removal_locks = bool(debug_blob.get("hex_removal_locks", False))

    hexes_blob = data.get("hexes", {}) or {}
    if isinstance(hexes_blob, dict):
        for name, blob in hexes_blob.items():
            if not isinstance(name, str):
                continue
            parsed = _parse_entry(name, blob)
            if parsed is not None:
                state.hexes[name] = parsed
    return state


# ============================================================================
# Serialization (ConfigState -> dict subtree)
# ============================================================================

def _state_to_dict(state: ConfigState) -> dict:
    """Render a ConfigState to the JSON subtree shape JsonFactory persists."""
    hexes: dict[str, object] = {}
    for name, hs in state.hexes.items():
        entry = hs.entry
        by_profession: dict[str, str] = {}
        for pid in _PROFESSION_ORDER:
            if pid in entry.by_profession and pid in _NAME_BY_PROFESSION_ID:
                by_profession[_NAME_BY_PROFESSION_ID[pid]] = _NAME_BY_PRIORITY[entry.by_profession[pid]]
        hexes[name] = {
            "caster": _NAME_BY_PRIORITY[entry.caster],
            "ranged_martial": _NAME_BY_PRIORITY[entry.ranged_martial],
            "melee": _NAME_BY_PRIORITY[entry.melee],
            "by_profession": by_profession,
        }
    return {
        "schema": SCHEMA_ID,
        "debug": {
            "hex_removal": state.debug_hex_removal,
            "hex_removal_locks": state.debug_hex_removal_locks,
        },
        "hexes": hexes,
    }


# ============================================================================
# Load / normalize
# ============================================================================

def _build_initial_state() -> ConfigState:
    state = ConfigState()
    for name, entry in _HEX_DEFAULTS.items():
        state.hexes[name] = HexEntryState(entry=entry)
    return state


def _normalize_loaded(parsed: ConfigState) -> tuple[ConfigState, bool]:
    """Apply migration only. Parsed entries are taken at face value."""
    dirty = False
    state = ConfigState(
        debug_hex_removal=False,
        debug_hex_removal_locks=parsed.debug_hex_removal_locks,
    )

    for name, parsed_state in parsed.hexes.items():
        if name not in _HEX_DEFAULTS:
            _log(
                f"config: '{name}' is not in the default table - "
                f"kept in JSON, ignored at runtime"
            )
        state.hexes[name] = parsed_state

    for name, default_entry in _HEX_DEFAULTS.items():
        if name not in state.hexes:
            state.hexes[name] = HexEntryState(entry=default_entry)
            dirty = True

    return state, dirty


# ============================================================================
# Store IO (JsonFactory-backed)
# ============================================================================

def _load_from_store(email: str, character_name: str) -> ConfigState:
    if not email or not character_name:
        return _build_initial_state()

    raw = _config_store().get_json(_char_key(character_name), None)
    parsed = _state_from_dict(raw)
    if parsed is None:
        state = _build_initial_state()
        _save_to_store(character_name, state)
        return state

    state, dirty = _normalize_loaded(parsed)
    if dirty:
        _save_to_store(character_name, state)
    return state


def _save_to_store(character_name: str, state: ConfigState) -> bool:
    if not character_name:
        return False
    _config_store().set_json(_char_key(character_name), _state_to_dict(state))
    return True


def _save_active(state: ConfigState) -> bool:
    """Save state to the active character's subtree."""
    _email, char = _active_account_key()
    return _save_to_store(char, state)


# ============================================================================
# Runtime debug-flag application
# ============================================================================

def _apply_debug_flags_to_runtime(state: ConfigState) -> None:
    try:
        from Py4GWCoreLib.GlobalCache import HexRemovalPriority as hp
        hp.HEX_REMOVAL_DEBUG = False
    except Exception:
        pass
    try:
        from Py4GWCoreLib.GlobalCache.shared_memory_src import AllAccounts as wb
        from Py4GWCoreLib.enums_src.Whiteboard_enums import WhiteboardLockKind
        kind = int(WhiteboardLockKind.HEX_REMOVAL_TARGET)
        if hasattr(wb, "WHITEBOARD_DEBUG_KINDS"):
            wb.WHITEBOARD_DEBUG_KINDS[kind] = bool(state.debug_hex_removal_locks)
    except Exception:
        pass


def _invalidate_priority() -> None:
    try:
        from Py4GWCoreLib.GlobalCache import HexRemovalPriority as hp
        if hasattr(hp, "invalidate_hex_removal_priority"):
            hp.invalidate_hex_removal_priority()
        else:
            hp._HEX_REMOVAL_PRIORITY_BUILT = False
            hp.HEX_REMOVAL_PRIORITY.clear()
    except Exception:
        pass


# ============================================================================
# Public API
# ============================================================================

def _get_state() -> ConfigState:
    """Return cached ConfigState for the active character. Reloads when the
    active (email, character_name) pair changes (e.g. character switch)."""
    global _cache_key, _cache_state
    key = _active_account_key()
    if key != _cache_key or _cache_state is None:
        _cache_state = _load_from_store(*key)
        _cache_key = key
        _apply_debug_flags_to_runtime(_cache_state)
    return _cache_state


def load_active_overrides() -> dict[str, HexRemovalEntry]:
    state = _get_state()
    return {name: hs.entry for name, hs in state.hexes.items()}


def has_override(name: str) -> bool:
    """Legacy stub. Modified-tracking removed; always returns False."""
    return False


def set_override(name: str, entry: HexRemovalEntry) -> None:
    """Save a hex's entry. Logging is performed by the GUI per change."""
    state = _get_state()
    state.hexes[name] = HexEntryState(entry=entry)
    _save_active(state)
    _invalidate_priority()


def clear_override(name: str) -> None:
    """Reset a hex to its current default. Logging by the GUI."""
    state = _get_state()
    if name not in _HEX_DEFAULTS:
        state.hexes.pop(name, None)
    else:
        state.hexes[name] = HexEntryState(entry=_HEX_DEFAULTS[name])
    _save_active(state)
    _invalidate_priority()


def hard_reset_all_to_none() -> None:
    """Set every default-table hex to NONE on every role with no overrides.

    Single batched save + single priority invalidation regardless of count.
    Irreversible - caller is responsible for confirming with the user.
    """
    state = _get_state()
    none_entry = HexRemovalEntry(
        caster=HexRemovalPriority.NONE,
        ranged_martial=HexRemovalPriority.NONE,
        melee=HexRemovalPriority.NONE,
        by_profession={},
    )
    for name in list(state.hexes.keys()):
        if name in _HEX_DEFAULTS:
            state.hexes[name] = HexEntryState(entry=none_entry)
    _save_active(state)
    _invalidate_priority()


def get_debug_flags() -> tuple[bool, bool]:
    state = _get_state()
    return state.debug_hex_removal, state.debug_hex_removal_locks


def set_debug_flags(hex_removal: bool, hex_removal_locks: bool) -> None:
    state = _get_state()
    state.debug_hex_removal = False
    state.debug_hex_removal_locks = bool(hex_removal_locks)
    _save_active(state)
    _apply_debug_flags_to_runtime(state)
    _log(
        f"debug toggles updated: hex_removal={hex_removal}, "
        f"hex_removal_locks={hex_removal_locks}"
    )


# ----- Import / Export -------------------------------------------------------

def export_to_desktop() -> tuple[bool, str]:
    """Point the user at the on-disk config document for a manual backup.

    The old Desktop/JSONC export was retired with the persistence migration:
    the config now lives in a self-persisting JsonFactory document under the
    jail, so there is nothing to hand-serialize or write out-of-jail. Returns
    the document's on-disk path (or a not-ready message before it binds).
    """
    path = _config_store().path()
    if not path:
        return False, "Config not ready (account not bound yet)."
    return True, path


def import_from_text(payload: str) -> tuple[bool, str, ConfigState | None]:
    """Retired: import from pasted text relied on hand-rolled JSONC parsing.

    Kept as a stable no-op so the GUI import button does not crash. Config is
    now managed exclusively through the jailed JsonFactory document.
    """
    return False, "Import from pasted text is no longer supported.", None


def commit_imported(parsed: ConfigState | None) -> bool:
    if parsed is None:
        return False
    state, _dirty = _normalize_loaded(parsed)
    global _cache_state, _cache_key
    _cache_state = state
    _cache_key = _active_account_key()
    if not _save_active(state):
        return False
    _apply_debug_flags_to_runtime(state)
    _invalidate_priority()
    return True
