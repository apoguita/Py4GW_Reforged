# PyNameObfuscator stub — Reforged Native surface
# Matches src/GW/name_obfuscator/name_obfuscator_bindings.cpp.
# DLL initialization owns the StoC hooks; Python controls enable/disable,
# aliases, per-surface gates, and caches. Name arguments/returns are wide
# strings on the C++ side (std::wstring) and plain str in Python.

from typing import Any, Dict, List

class ObservedPlayer:
    # All members are read-only (def_readonly).
    player_number: int
    agent_id: int
    real_name: str
    display_name: str
    aliased: bool

def enable() -> None:
    """Turn name obfuscation on. Hooks are owned by DLL initialization."""
    ...

def disable() -> None:
    """Turn name obfuscation off. Names already cached by the game persist until re-zone."""
    ...

def is_enabled() -> bool: ...

def is_map_ready() -> bool: ...

def set_alias(real_name: str, fake_name: str) -> None:
    """Register or update a real -> fake player-name mapping."""
    ...

def remove_alias(real_name: str) -> bool: ...

def clear_aliases() -> None:
    """Drop every alias."""
    ...

def clear() -> None:
    """Alias for clear_aliases()."""
    ...

def alias_count() -> int: ...

def get_aliases() -> Dict[str, str]:
    """Snapshot of real_name -> fake_name mappings."""
    ...

def get_real_name(display_name: str) -> str:
    """Resolve an obfuscated display name back to the real name (observed cache, then alias reverse)."""
    ...

def get_display_name(real_name: str) -> str:
    """Resolve a real name to its current display (observed cache, then alias)."""
    ...

def require_real_name(name: str) -> str:
    """Return the resolved real name if known, otherwise the input unchanged."""
    ...

def set_surface_enabled(surface: str, enabled: bool) -> bool:
    """Toggle a single name surface. Returns False for an unknown surface name."""
    ...

def is_surface_enabled(surface: str) -> bool: ...

def list_surfaces() -> List[str]: ...

def scrub_guild_roster() -> int:
    """Phase 4 fallback (not yet implemented): scrub the durable guild member table; returns count scrubbed."""
    ...

def scrub_guild_identity() -> int:
    """Rewrite already-loaded guild name+tag (Guild struct) for aliased guilds; returns guilds changed.
    Use after aliasing a guild so masking applies without re-zoning."""
    ...

def clear_observed_cache() -> None:
    """Drop the map-scoped observed player cache."""
    ...

def observed_count() -> int: ...

def get_observed_players() -> List[ObservedPlayer]: ...

def get_diagnostics() -> Dict[str, Any]:
    """Diagnostics snapshot as a plain dict. Keys (bool then int counters):
    initialized, player_join_hook_registered, class_observer_hook_registered,
    enabled, current_map_ready, player_packets_seen, player_packets_empty_name,
    player_packets_disabled, player_packets_map_not_ready, observed_captures,
    observed_trylock_skips, alias_hits, class_observer_hits, message_global_hits,
    item_custom_hits, mercenary_hits, mercenary_self_skips, guild_info_hits,
    party_search_hits, acct_name_hits, acct_name_self_skips, score_summary_hits,
    score_summary_mode_skips, score_summary_self_skips, guild_charname_hits,
    guild_identity_hits, guild_invite_hits, guild_motd_hits, own_name_hits,
    reverse_alias_collisions."""
    ...

def reset_diagnostics() -> None: ...
