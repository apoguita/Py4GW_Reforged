"""Launch Bar persistence — the whole ``LaunchBarSet`` as one JSON blob in the account
``Settings`` document ``Widgets/LaunchBar/LaunchBar.ini`` (section ``[State]`` key ``bars``).

This is DURABLE PER-ACCOUNT config (bars, tiles, colors, placement) — it belongs in a settings
file, not shared memory. Favorites are persisted separately in the Widget Manager's own store
(see ``widget_runtime``). ``Settings`` is imported lazily so this module is import-safe offline.
"""

import json

_DOC_PATH = "Widgets/LaunchBar"
_DOC_FILE = "LaunchBar.ini"
_SECTION = "State"
_KEY = "bars"


def _cfg():
    """The account Settings document for the launch bar (opened/cached), or None."""

    try:
        from Py4GWCoreLib.py4gwcorelib_src.Settings import Settings

        name = Settings.ensure_key(_DOC_PATH, _DOC_FILE)   # account scope
        return Settings.find(name)
    except Exception:
        return None


def load_state():
    """Return the persisted ``LaunchBarSet.to_dict()`` mapping, or None if nothing saved."""

    cfg = _cfg()
    if cfg is None:
        return None
    try:
        raw = cfg.get_str(_SECTION, _KEY, "")
    except Exception:
        return None
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def save_state(data) -> bool:
    """Serialize + persist a ``LaunchBarSet.to_dict()`` mapping. ``Settings.set`` dedups an
    unchanged value, so calling this when nothing changed does not rewrite the file."""

    cfg = _cfg()
    if cfg is None:
        return False
    try:
        blob = json.dumps(data, separators=(",", ":"))
    except Exception:
        return False
    try:
        cfg.set(_SECTION, _KEY, blob)
        return True
    except Exception:
        return False
