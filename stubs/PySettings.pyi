"""Type stubs for the native ``PySettings`` embedded module.

Per-account INI settings backed by ``SettingsManager`` (see the Reforged Native
project ``docs/settings-ini-design.md``). A document is bound to one
``(name, scope)`` pair; the same pair always yields the same document.

Key addressing: a flat ``key`` lands in the default ``settings`` section;
``"section/key"`` addresses an explicit section.
"""

from typing import Any


class settings:
    def __init__(self, name: str, scope: str = "account") -> None:
        """Bind to a named settings document.

        ``scope`` is ``"account"`` or ``"global"`` (both under ``settings/``). No
        open/close/save needed — the manager autosave pump persists changes. There
        is no ``"root"`` scope; the one root file is reached via ``py4gw_ini()``.
        """
        ...

    def write(self, key: str, value: bool | int | float | str) -> None:
        """Set ``key`` to ``value`` (type selected by overload); marks dirty."""
        ...

    def read(self, key: str, default: Any = "") -> Any:
        """Read ``key``.

        ``default`` is either a fallback value (whose type selects the getter)
        or a type token (``bool``/``int``/``float``/``str``) whose zero value is
        the fallback. Missing/unconvertible keys return the fallback.
        """
        ...

    def save(self) -> bool:
        """Force an immediate save (escape hatch; not required in normal flow)."""
        ...

    def reload(self) -> bool:
        """Re-read from disk, discarding unsaved changes."""
        ...

    def is_dirty(self) -> bool: ...

    def is_bound(self) -> bool:
        """Whether the document is attached to disk yet."""
        ...

    def path(self) -> str:
        """Absolute on-disk path of this document (empty until bound)."""
        ...

    def has_key(self, key: str) -> bool: ...

    def keys(self, section: str = "settings") -> list[str]: ...

    def sections(self) -> list[str]: ...

    def delete(self, key: str) -> bool: ...

    def delete_section(self, section: str) -> bool: ...

    # Explicit (section, key) API — section and key are separate arguments and
    # are never parsed for a delimiter, so either may contain '/', '\\', ':' or
    # spaces. Prefer these over write/read for any real section/key names.
    def set(self, section: str, key: str, value: bool | int | float | str) -> None: ...

    def get(self, section: str, key: str, default: Any = "") -> Any: ...

    def has(self, section: str, key: str) -> bool: ...

    def remove(self, section: str, key: str) -> bool: ...

    def items(self, section: str) -> list[tuple[str, str]]: ...


def py4gw_ini() -> settings:
    """The one root-level INI document (``<module>/Py4GW.ini``).

    Hard-coded and path-less: it can only ever be that single file, so it is not a
    jail-escape surface. This is the only sanctioned way to touch the project root.
    """
    ...


def copy_document_to_account(name: str, target_email: str) -> bool:
    """Copy an entire document (all sections) into another account's file on disk."""
    ...


def copy_section_to_account(name: str, section: str, target_email: str) -> bool:
    """Copy one whole section into another account's file on disk."""
    ...


def copy_keys_to_account(name: str, section: str, keys: list[str], target_email: str) -> bool:
    """Copy a named subset of a section's keys into another account's file on disk."""
    ...


def apply_section_to_account(name: str, section: str, values: list[tuple[str, str]], target_email: str) -> bool:
    """Overlay a caller-supplied key/value mapping into another account's section on disk."""
    ...


def is_anchored() -> bool:
    """Whether account-scoped documents are bound to disk yet."""
    ...


def get_settings_directory() -> str:
    """Per-account settings directory (empty until the anchor resolves)."""
    ...
