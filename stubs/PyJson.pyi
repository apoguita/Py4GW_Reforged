"""Type stubs for the native ``PyJson`` embedded module.

Per-account structured JSON documents backed by ``JsonFactory`` (see the Reforged
Native project ``docs/json-factory-design.md``). This is the JSON counterpart of
``PySettings``: same lifecycle (per-``(name, scope)`` document, debounced
autosave, atomic writes, account staging, cross-account copy), but the document
is a nested tree instead of a flat INI.

Addressing is a slash path that walks the tree: ``"ui/window/pos/x"``. A numeric
segment indexes an array: ``"waypoints/0/x"``. Reads never raise — a missing node
or an unconvertible value returns the caller's default.

Global-scope documents are shared by every running client (multibox): their
saves take a cross-process lock and merge a per-document write journal onto the
current on-disk tree, so concurrent accounts do not clobber each other.
"""

from typing import Any


class JsonFile:
    def __init__(self, name: str, scope: str = "account") -> None:
        """Bind to a named JSON document.

        ``scope`` is ``"account"`` or ``"global"`` (both under ``json/``). No
        open/close/save needed — the factory autosave pump persists changes. JSON
        has no ``"root"`` scope; every document lives under ``json/``.
        """
        ...

    def set(self, path: str, value: bool | int | float | str) -> None:
        """Set the leaf at ``path`` to ``value`` (type selected by overload).

        Intermediate objects along the path are created as needed; marks dirty.
        """
        ...

    def get(self, path: str, default: Any = "") -> Any:
        """Read the leaf at ``path``.

        ``default`` is either a fallback value (whose type selects the getter)
        or a type token (``bool``/``int``/``float``/``str``) whose zero value is
        the fallback. Missing/unconvertible nodes return the fallback.
        """
        ...

    def set_json(self, path: str, value: Any) -> None:
        """Replace the subtree at ``path`` with a Python dict/list/scalar/None."""
        ...

    def get_json(self, path: str = "") -> Any:
        """Return the subtree at ``path`` as a native Python object (``None`` if absent).

        With no path (or ``""``) returns the whole document as a dict.
        """
        ...

    def append(self, path: str, value: Any) -> None:
        """Push ``value`` onto the array at ``path`` (creating the array if absent)."""
        ...

    def has(self, path: str) -> bool:
        """True if a node exists at ``path``."""
        ...

    def delete(self, path: str) -> bool:
        """Remove the node at ``path``. True if it existed."""
        ...

    def keys(self, path: str = "") -> list[str]:
        """Object member names at ``path`` (empty if the node is not an object)."""
        ...

    def size(self, path: str = "") -> int:
        """Array length / object member count at ``path`` (0 if scalar/absent)."""
        ...

    def is_array(self, path: str = "") -> bool: ...

    def is_object(self, path: str = "") -> bool: ...

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


def copy_document_to_account(name: str, target_email: str) -> bool:
    """Merge an entire document into another account's file on disk."""
    ...


def copy_path_to_account(name: str, path: str, target_email: str) -> bool:
    """Merge one subtree into another account's file on disk."""
    ...


def apply_to_account(name: str, path: str, value: Any, target_email: str) -> bool:
    """Merge a caller-supplied subtree at ``path`` into another account's file on disk."""
    ...


def is_anchored() -> bool:
    """Whether account-scoped documents are bound to disk yet."""
    ...


def get_json_directory() -> str:
    """Per-account JSON directory (empty until the anchor resolves)."""
    ...
