"""Name Obfuscation persistence — the GLOBAL (machine-wide) document.

The alias map, name buckets, master enable and per-surface toggles are **global-scoped** so a single
identity set applies across every account on the machine (name obfuscation is multi-account by
nature — an alias set while on one account must mask that name everywhere). ``Settings`` is imported
lazily (import-safe offline) and self-throttled; the alias map and buckets are stored as JSON in a
single key each so the file stays compact and round-trips cleanly.
"""

import json

from . import model

_DOC = "Widgets/System/Name Obfuscation.ini"


def _settings():
    try:
        from Py4GWCoreLib.py4gwcorelib_src.Settings import Settings

        return Settings(_DOC, "global")   # machine-wide: shared across all accounts
    except Exception:
        return None


def _loads_dict(raw: str) -> "dict[str, str]":
    try:
        data = json.loads(raw) if raw else {}
        return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}
    except Exception:
        return {}


def _loads_list(raw: str, default: "tuple[str, ...]") -> "list[str]":
    try:
        data = json.loads(raw) if raw else None
        if isinstance(data, list):
            return [str(x) for x in data]
    except Exception:
        pass
    return list(default)


def _loads_bool_dict(raw: str) -> "dict[str, bool]":
    try:
        data = json.loads(raw) if raw else {}
        return {str(k): bool(v) for k, v in data.items()} if isinstance(data, dict) else {}
    except Exception:
        return {}


def load(state: dict) -> None:
    """Populate ``state`` from the global document, defaulting buckets on a fresh install."""
    s = _settings()
    if s is None:
        state["enabled"] = False
        state["aliases"] = {}
        state["first_names"] = list(model.DEFAULT_FIRST_NAMES)
        state["surnames"] = list(model.DEFAULT_SURNAMES)
        state["surfaces"] = {}
        return
    state["enabled"] = s.get_bool("general", "enabled", False)
    state["aliases"] = _loads_dict(s.get_str("aliases", "map", ""))
    state["first_names"] = _loads_list(s.get_str("buckets", "first_names", ""), model.DEFAULT_FIRST_NAMES)
    state["surnames"] = _loads_list(s.get_str("buckets", "surnames", ""), model.DEFAULT_SURNAMES)
    state["surfaces"] = _loads_bool_dict(s.get_str("surfaces", "map", ""))


def save_enabled(value: bool) -> None:
    s = _settings()
    if s is not None:
        s.set("general", "enabled", bool(value))


def save_aliases(aliases: "dict[str, str]") -> None:
    s = _settings()
    if s is not None:
        s.set("aliases", "map", json.dumps(aliases))


def save_buckets(first_names: "list[str]", surnames: "list[str]") -> None:
    s = _settings()
    if s is not None:
        s.set("buckets", "first_names", json.dumps(list(first_names)))
        s.set("buckets", "surnames", json.dumps(list(surnames)))


def save_surfaces(surfaces: "dict[str, bool]") -> None:
    s = _settings()
    if s is not None:
        s.set("surfaces", "map", json.dumps(surfaces))
