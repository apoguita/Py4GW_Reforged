"""System Settings persistence — the account document backing the library options.

Stores each listener's enabled flag and each sub-option value in one account-scoped document,
``Widgets/System/System Settings.ini``. ``Settings`` is imported lazily so this module is
import-safe offline, and is self-throttled (autosaves on a debounce) — we only ``get``/``set``,
never force a save/load.

Keys: the enable flag lives at ``[<category>] <listener>``; each sub-option at
``[<category>] <listener>.<option>`` — so the file stays human-readable.
Category expand/collapse state lives at ``[Layout] <category-key>``.
"""

from . import model

_DOC = "Widgets/System/System Settings.ini"
_LAYOUT_SECTION = "Layout"


def _settings():
    try:
        from Py4GWCoreLib.py4gwcorelib_src.Settings import Settings

        return Settings(_DOC, "account")
    except Exception:
        return None


def load(enabled: "dict[str, bool]", options: "dict[str, object]") -> None:
    """Fill ``enabled`` (listener name -> bool) and ``options`` (``name.key`` -> value) from disk.

    Missing keys fall back to the catalog defaults, so a clean install works with no file.
    """
    s = _settings()
    for cat in model.CATALOG:
        for lsn in cat.listeners:
            if s is None:
                enabled[lsn.name] = lsn.default_enabled
            else:
                enabled[lsn.name] = s.get_bool(cat.key, lsn.name, lsn.default_enabled)
            for opt in lsn.options:
                okey = "%s.%s" % (lsn.name, opt.key)
                if s is None:
                    options[okey] = opt.default
                elif isinstance(opt, model.IntOption):
                    options[okey] = s.get_int(cat.key, okey, opt.default)
                else:
                    options[okey] = s.get_bool(cat.key, okey, opt.default)


def load_group_open(group_open: "dict[str, bool]") -> None:
    """Fill category expand/collapse state from the account document.

    Missing layout keys default to expanded for backwards compatibility with existing documents.
    """
    s = _settings()
    for cat in model.CATALOG:
        group_open[cat.key] = True if s is None else s.get_bool(_LAYOUT_SECTION, cat.key, True)


def save_enabled(cat_key: str, listener_name: str, value: bool) -> None:
    s = _settings()
    if s is not None:
        s.set(cat_key, listener_name, bool(value))


def save_option(cat_key: str, listener_name: str, option_key: str, value: object) -> None:
    s = _settings()
    if s is not None:
        s.set(cat_key, "%s.%s" % (listener_name, option_key), value)


def save_group_open(cat_key: str, is_open: bool) -> None:
    s = _settings()
    if s is not None:
        s.set(_LAYOUT_SECTION, cat_key, bool(is_open))
