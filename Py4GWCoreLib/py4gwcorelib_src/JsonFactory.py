"""JsonFactory - the Python front door to Py4GW's per-account JSON persistence.

    +---------------------------------------------------------------------------------------+
    | THIS IS A SELF-THROTTLED, SELF-PERSISTING CLASS.                                       |
    | You do NOT open, load, or save it. Writes are batched and flushed to disk             |
    | automatically on a debounce; the file binds and loads itself. Just call get/set.      |
    | Call save() (force-save) or reload() (force-load) ONLY if the app specifically         |
    | requires it - never as part of normal flow.                                           |
    +---------------------------------------------------------------------------------------+

This is the JSON counterpart of :class:`Settings`. Where ``Settings`` wraps a flat INI document
(``section`` / ``key`` -> string), ``JsonFactory`` wraps a *structured* JSON document: a nested
tree of objects, arrays, and native-typed scalars. It is a thin, typed wrapper over the native
``PyJson`` module (implemented in ``Py4GW_Reforged_Native/src/json``). All persistence policy -
where files live, when they bind to disk, and when they are written - is owned by the native
``JsonFactory`` manager; this class only provides an ergonomic Python surface over one *document*.

What a "document" is
--------------------
A document is one JSON file identified by a ``(name, scope)`` pair. The native side keeps exactly
one document per pair process-wide, and this class mirrors that: constructing ``JsonFactory(name,
scope)`` twice returns the *same* object (see ``__new__``). There is **no open/close/save lifecycle
to manage** - you construct it and read/write; the file takes care of itself. JSON files live under
a **separate ``json/`` folder** so they never collide with the INI ``settings/`` tree.

Addressing (paths, not sections)
--------------------------------
Unlike ``Settings``' ``(section, key)`` pair, a JSON node is addressed by a **slash path** that
walks the tree: ``"ui/window/pos/x"``. A numeric segment indexes an array: ``"waypoints/0/x"``.
Writing a leaf creates the intermediate objects along the path automatically. An empty path
(``""``) refers to the whole document (root object).

Scopes (where the file lives, and when it binds)
------------------------------------------------
- ``"account"`` (default) -> ``json/<email>/<name>``. **Per-account** preferences. Staged in memory
  until the account anchor (the logged-in email) resolves, then binds automatically.
- ``"global"``  -> ``json/Global/<name>``. **Shared across every account/client** on the machine.
  Binds immediately. Because multiple clients (multibox) share the file, Global saves take a
  **cross-process lock** and merge a per-document write journal onto the current on-disk tree, so
  two accounts writing different paths both survive (only same-path writes race, last-writer-wins).
- ``"root"``    -> ``<name>`` at the project root. Shared, binds immediately; reserved for core
  files. Application scripts should prefer ``account`` or ``global``.

Saving is automatic (do not micro-manage it)
--------------------------------------------
Every setter takes effect **in memory immediately** and marks the document dirty. The native
autosave pump then persists it on a debounce: ~2 s after the last write, or at most ~10 s after the
first unsaved change, plus a flush on shutdown. Do **not** write a "save every N ms" loop and do
**not** call ``save()`` to "make it stick"; ``save()``/``reload()`` are escape hatches.

Typical usage
-------------
    cfg = JsonFactory("Widgets/MyWidget/MyWidget.json")     # account scope (default)
    # cfg = JsonFactory("Foo/Bar.json", "global")           # machine-wide, locked

    scale = cfg.get_float("layout/scale", 1.0)              # never throws; default on miss
    cfg.set("layout/scale", 1.25)                           # in memory now; autosaved later

    cfg.set_json("waypoints", [{"x": 1}, {"x": 2}])         # whole subtree from a list
    cfg.append("waypoints", {"x": 3})                       # push onto the array
    pts = cfg.get_json("waypoints")                         # -> [{'x': 1}, {'x': 2}, {'x': 3}]

Autosave and flush cadence are owned entirely by the native side; this module never schedules
writes of its own.
"""

from typing import Any

import PyJson


class JsonFactory:
    """A typed, SELF-THROTTLED, self-persisting JSON document backed by native ``PyJson``.

    Self-throttled means: you never schedule writes or reads. Setters mutate memory and the native
    autosave pump flushes to disk on a debounce; the document binds/loads itself. ``save()`` (force
    a write now) and ``reload()`` (force a re-read now) are escape hatches - use them only when the
    app genuinely requires it, not in normal flow.

    One instance corresponds to one on-disk file identified by ``(name, scope)``. Instances are
    cached per ``(name, scope)`` (see :meth:`__new__`), so anyone who asks for the same document
    shares the same object and the same in-memory state - there is no risk of two divergent copies.
    """

    _instances: dict[tuple[str, str], 'JsonFactory'] = {}

    def __new__(cls, name: str, scope: str = 'account') -> 'JsonFactory':
        """Return the cached instance for ``(name, scope)``, creating it on first request.

        Mirrors the native "one document per (name, scope)" guarantee on the Python side: two
        constructions with the same pair yield the *same* ``JsonFactory`` object.
        """
        instance_key = (str(name), str(scope))
        existing = cls._instances.get(instance_key)
        if existing is not None:
            return existing
        instance = super().__new__(cls)
        cls._instances[instance_key] = instance
        return instance

    def __init__(self, name: str, scope: str = 'account') -> None:
        """Bind to the ``(name, scope)`` document (opening it on the native side once).

        ``scope`` is ``"account"`` (per-account, default), ``"global"`` (machine-wide), or
        ``"root"`` (project root; reserved for core files). Guarded so the shared instance is only
        initialized once even though callers may construct it repeatedly.
        """
        if getattr(self, '_initialized', False):
            return
        self._name = str(name)
        self._scope = str(scope)
        self._doc = PyJson.JsonFile(self._name, self._scope)
        self._initialized = True

    # ------------------------------------------------------------------
    # Path normalization
    #
    # JSON keys are case-sensitive and paths are explicit tree addresses, so
    # (unlike Settings) paths are NOT lowercased. Leading/trailing slashes and
    # surrounding whitespace are trimmed; internal structure is preserved.
    # ------------------------------------------------------------------

    @staticmethod
    def _p(path: str) -> str:
        """Normalize an access path: trim whitespace and outer slashes, keep the rest verbatim."""
        return str(path).strip().strip('/')

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def is_ready(self) -> bool:
        """True once the document is bound to a file on disk.

        Account-scoped documents bind when the account anchor (email) resolves; global/root bind
        immediately. Reads before binding still succeed against in-memory/default state.
        """
        return bool(self._doc.is_bound())

    def reload(self) -> bool:
        """Escape hatch: re-read the file from disk, **discarding unsaved in-memory changes**.

        Not part of normal flow. Use only to pick up an external edit (e.g. a cross-account overlay
        written by another client, or a peer's write to a Global file).
        """
        return bool(self._doc.reload())

    def save(self) -> bool:
        """Escape hatch: force an immediate write to disk, bypassing the autosave debounce.

        **Not needed in normal flow** - every ``set`` is autosaved. Reach for this only when you
        must guarantee the bytes are on disk *right now* (e.g. immediately before a hard exit).
        """
        return bool(self._doc.save())

    def path(self) -> str:
        """Absolute on-disk path of this document. Empty string until the document is bound."""
        return str(self._doc.path())

    def resolved_path(self) -> str:
        """The on-disk path if bound, otherwise fall back to the document ``name`` (for logging)."""
        p = str(self._doc.path())
        return p if p else self._name

    @property
    def name(self) -> str:
        """The document's name (``"path/filename"``), i.e. its ``(name, scope)`` identity."""
        return self._name

    @property
    def scope(self) -> str:
        """The document's scope: ``"account"``, ``"global"``, or ``"root"``."""
        return self._scope

    # ------------------------------------------------------------------
    # Typed leaf get / set (path-addressed)
    # ------------------------------------------------------------------

    def get_str(self, path: str, default: str = '') -> str:
        """Read a string leaf. Returns ``default`` if the node is missing. Never raises."""
        return str(self._doc.get(self._p(path), str(default)))

    def get_int(self, path: str, default: int = 0) -> int:
        """Read an int leaf. Returns ``default`` if missing or not convertible. Never raises."""
        return int(self._doc.get(self._p(path), int(default)))

    def get_float(self, path: str, default: float = 0.0) -> float:
        """Read a float leaf. Returns ``default`` if missing or not convertible. Never raises."""
        return float(self._doc.get(self._p(path), float(default)))

    def get_bool(self, path: str, default: bool = False) -> bool:
        """Read a bool leaf. Returns ``default`` if missing or not convertible. Never raises."""
        return bool(self._doc.get(self._p(path), bool(default)))

    def get(self, path: str, default: Any = None) -> Any:
        """Typed read whose return type follows the type of ``default``.

        ``bool``/``int``/``float``/``str`` defaults dispatch to the matching typed getter. For any
        other (or ``None``) default, returns the native subtree at ``path`` if present, else
        ``default``. Never raises.
        """
        if isinstance(default, bool):
            return self.get_bool(path, default)
        if isinstance(default, int):
            return self.get_int(path, default)
        if isinstance(default, float):
            return self.get_float(path, default)
        if isinstance(default, str):
            return self.get_str(path, default)
        p = self._p(path)
        if self._doc.has(p):
            return self._doc.get_json(p)
        return default

    def set(self, path: str, value: Any) -> None:
        """Write a scalar leaf (``bool``/``int``/``float``/``str``), effective now and autosaved.

        **Dedups**: if the current value already equals ``value`` nothing is written and the
        document is not marked dirty, so re-setting an unchanged value every frame is free. For
        nested dict/list values use :meth:`set_json`.
        """
        p = self._p(path)
        if self._doc.has(p) and self._doc.get_json(p) == value:
            return
        self._doc.set(p, value)

    def set_str(self, path: str, value: str) -> None:
        """Write a string value. See :meth:`set` (dedups; autosaved)."""
        self.set(path, str(value))

    def set_int(self, path: str, value: int) -> None:
        """Write an int value. See :meth:`set` (dedups; autosaved)."""
        self.set(path, int(value))

    def set_float(self, path: str, value: float) -> None:
        """Write a float value. See :meth:`set` (dedups; autosaved)."""
        self.set(path, float(value))

    def set_bool(self, path: str, value: bool) -> None:
        """Write a bool value. See :meth:`set` (dedups; autosaved)."""
        self.set(path, bool(value))

    # ------------------------------------------------------------------
    # Native subtree access (dict / list / scalars)
    # ------------------------------------------------------------------

    def get_json(self, path: str = '', default: Any = None) -> Any:
        """Return the subtree at ``path`` as a native Python object.

        An empty path returns the whole document (a dict). Returns ``default`` when the node is
        absent (native side returns ``None``).
        """
        value = self._doc.get_json(self._p(path))
        return default if value is None else value

    def set_json(self, path: str, value: Any) -> None:
        """Replace (or create) the subtree at ``path`` with a Python dict/list/scalar/None.

        **Dedups** against the current subtree so an unchanged assignment is free. Autosaved.
        """
        p = self._p(path)
        if self._doc.has(p) and self._doc.get_json(p) == value:
            return
        self._doc.set_json(p, value)

    def append(self, path: str, value: Any) -> None:
        """Push ``value`` onto the array at ``path`` (creating the array if absent). Autosaved."""
        self._doc.append(self._p(path), value)

    # ------------------------------------------------------------------
    # Structure / introspection
    # ------------------------------------------------------------------

    def has(self, path: str) -> bool:
        """True if a node exists at ``path``."""
        return bool(self._doc.has(self._p(path)))

    def delete(self, path: str) -> bool:
        """Remove the node at ``path``. Returns True if it existed. Autosaved like any change."""
        return bool(self._doc.delete(self._p(path)))

    def keys(self, path: str = '') -> list:
        """Object member names at ``path`` (empty list if the node is not an object)."""
        return list(self._doc.keys(self._p(path)))

    def size(self, path: str = '') -> int:
        """Array length / object member count at ``path`` (0 if the node is scalar or absent)."""
        return int(self._doc.size(self._p(path)))

    def is_array(self, path: str = '') -> bool:
        """True if the node at ``path`` is a JSON array."""
        return bool(self._doc.is_array(self._p(path)))

    def is_object(self, path: str = '') -> bool:
        """True if the node at ``path`` is a JSON object."""
        return bool(self._doc.is_object(self._p(path)))

    def items(self, path: str = '') -> dict:
        """A ``{key: value}`` dict of the object at ``path`` (values as native subtrees)."""
        node = self._doc.get_json(self._p(path))
        return dict(node) if isinstance(node, dict) else {}

    # ------------------------------------------------------------------
    # Cross-account copy (this document -> another account's file on disk).
    #
    # Copies from THIS account's document into json/<target_email>/<name>.
    # Overlay is a deep merge (RFC 7396 merge-patch): source paths win, other
    # target paths are left untouched, an explicit ``None`` deletes. This is a
    # disk write on the target's file (taken under the cross-process lock); the
    # target's running client picks it up on its next reload - not instantaneous.
    # Returns True on success (an empty copy is success); False on a rejected
    # email or save failure.
    # ------------------------------------------------------------------

    def copy_document_to_account(self, target_email: str) -> bool:
        """Merge this **entire** document onto ``target_email``'s file on disk.

        Reads from *this* account's live document. Target paths not present here are left untouched.
        The target's running client picks up the change on its next reload (not instant).
        """
        return bool(PyJson.copy_document_to_account(self._name, str(target_email)))

    def copy_path_to_account(self, path: str, target_email: str) -> bool:
        """Merge one subtree (at ``path``) onto ``target_email``'s file. See
        :meth:`copy_document_to_account` for the overlay/reload/return semantics."""
        return bool(PyJson.copy_path_to_account(self._name, self._p(path), str(target_email)))

    def apply_to_account(self, path: str, value: Any, target_email: str) -> bool:
        """Merge a caller-supplied ``value`` (dict/list/scalar) at ``path`` into another account's file.

        Unlike ``copy_*`` (which read from *this* document), the value comes from the caller - e.g. a
        saved profile or transformed config. Same overlay-on-disk / next-reload / return semantics.
        """
        return bool(PyJson.apply_to_account(self._name, self._p(path), value, str(target_email)))
