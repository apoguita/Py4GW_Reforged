"""Settings — the Python front door to Py4GW's per-account INI persistence.

    ┌─────────────────────────────────────────────────────────────────────────────────────┐
    │ THIS IS A SELF-THROTTLED, SELF-PERSISTING CLASS.                                       │
    │ You do NOT open, load, or save it. Writes are batched and flushed to disk             │
    │ automatically on a debounce; the file binds and loads itself. Just call get_*/set_*.  │
    │ Call save() (force-save) or reload() (force-load) ONLY if the app specifically         │
    │ requires it — never as part of normal flow.                                           │
    └─────────────────────────────────────────────────────────────────────────────────────┘

This is a thin, typed wrapper over the native ``PySettings`` module (implemented in
``Py4GW_Reforged_Native/src/settings``). All persistence policy — where files live, when they
bind to disk, and when they are written — is owned by the native ``SettingsManager``; this class
only provides an ergonomic, type-safe Python surface over one *document*.

What a "document" is
--------------------
A document is one INI file identified by a ``(name, scope)`` pair. The native side keeps exactly
one document per pair process-wide, and ``Settings`` mirrors that: constructing ``Settings(name,
scope)`` twice returns the *same* object (see ``__new__``). There is **no open/close/save
lifecycle to manage** — you construct it and read/write; the file takes care of itself.

Scopes (where the file lives, and when it binds)
------------------------------------------------
- ``"account"`` (default) → ``settings/<email>/<name>``. **Per-account** preferences. The file is
  *staged* until the account anchor (the logged-in email) resolves, then binds automatically. In
  practice the email is already present by the time any script runs, so reads/writes behave
  normally from the first frame.
- ``"global"``  → ``settings/Global/<name>``. **Shared across every account** on the machine.
  Binds immediately.

There is deliberately **no ``"root"`` scope** — every named document lives strictly under
``settings/``, so nothing can be written outside the jail by choosing a scope. The single file
allowed at the project root, ``Py4GW.ini`` (a cross-process contract with the external launcher), is
reached only through the path-less :meth:`Settings.py4gw_ini` accessor.

Saving is automatic (do not micro-manage it)
--------------------------------------------
Every setter takes effect **in memory immediately** and marks the document dirty. The native
autosave pump (stepped from the runtime loop) then persists it on a debounce:
- **~2 s after the last write** (it waits for a burst of edits to settle), or
- **at most ~10 s** after the first unsaved change, whichever comes first, and
- a **flush on shutdown** catches anything still dirty.

So the correct pattern is simply: call ``set``/``set_*`` whenever a value changes (or even every
frame — ``set`` skips the write when the value is unchanged) and let the pump do the rest. You do
**not** need a "save every N ms" loop, and you should **not** call ``save()`` to "make it stick";
``save()``/``reload()`` are escape hatches (see their docstrings), not part of normal flow.

Reading and writing
-------------------
Two addressing styles, both backed by the same document:
- **Explicit ``(section, key)``** — ``get_*(section, key, default)`` / ``set_*(section, key, value)``.
  Section and key are separate arguments and are never split on a delimiter, so a name may contain
  ``/``, ``\\``, ``:`` or spaces (e.g. section ``"Widget:Guild Wars\\Triggers/Foo.py"``). Prefer
  this style.
- Typed getters **never raise**: a missing key or text that will not convert returns your default.
- Values are stored as strings on disk (mirroring the legacy configparser format); the typed
  getters parse them back. Keys are **lowercased** (configparser parity); **section names are kept
  verbatim**. ``set`` **dedups** — an unchanged value is not rewritten, so idle re-sets are free.

Typical usage
-------------
    # own a per-account document — just construct it. A document is a process-wide
    # singleton (same (name, scope) -> same object), bound/loaded/seeded automatically
    # by the native side, so there is NO separate ensure/find step: construct where you
    # need it and read/write.
    cfg = Settings("Widgets/MyWidget/MyWidget.ini")                 # account scope (default)
    # cfg = Settings("Foo/Bar.ini", "global")                      # machine-wide

    scale = cfg.get_float("Layout", "scale", 1.0)                   # never throws; default on miss
    cfg.set("Layout", "scale", 1.25)                                # in memory now; autosaved later
    for name, value in cfg.items("Layout").items():
        ...

Autosave and flush cadence are owned entirely by the native side; this module never schedules
writes of its own.
"""

from typing import Any

import PySettings


class Settings:
    """A typed, SELF-THROTTLED, self-persisting INI document backed by native ``PySettings``.

    Self-throttled means: you never schedule writes or reads. Setters mutate memory and the native
    autosave pump flushes to disk on a debounce; the document binds/loads itself. ``save()`` (force
    a write now) and ``reload()`` (force a re-read now) are escape hatches — use them only when the
    app genuinely requires it, not in normal flow.

    One instance corresponds to one on-disk file identified by ``(name, scope)``. Instances are
    cached per ``(name, scope)`` (see :meth:`__new__`), so anyone who asks for the same document
    shares the same object and the same in-memory state — there is no risk of two divergent copies.

    You acquire one simply by constructing it: ``Settings("path/filename")`` (account scope) or
    ``Settings("path/filename", "global")`` (machine-wide). Because instances are cached per
    ``(name, scope)``, any code that constructs the same name/scope shares the one live document —
    there is nothing to "ensure" first and no name to pass around and look up.

    Persistence is automatic and debounced (see the module docstring); treat this object as a live,
    always-saved view of the file rather than something you must explicitly load or flush.
    """

    _instances: dict[tuple[str, str], 'Settings'] = {}

    def __new__(cls, name: str, scope: str = 'account') -> 'Settings':
        """Return the cached instance for ``(name, scope)``, creating it on first request.

        This mirrors the native "one document per (name, scope)" guarantee on the Python side: two
        constructions with the same pair yield the *same* ``Settings`` object, so all callers share
        one in-memory view of the file.

        ``scope`` must be ``"account"`` or ``"global"`` — both resolve strictly under ``settings/``.
        There is deliberately **no** ``"root"`` scope: the project root is not addressable by name
        (that would be a jail-escape surface). The single root file, ``Py4GW.ini``, is reached only
        through the path-less :meth:`py4gw_ini` accessor.
        """
        if str(scope) not in ('account', 'global'):
            raise ValueError(
                f"Settings scope must be 'account' or 'global' (got {scope!r}); "
                "the one root file is reached via Settings.py4gw_ini()"
            )
        instance_key = (str(name), str(scope))
        existing = cls._instances.get(instance_key)
        if existing is not None:
            return existing
        instance = super().__new__(cls)
        cls._instances[instance_key] = instance
        return instance

    @classmethod
    def py4gw_ini(cls) -> 'Settings':
        """The one document permitted outside the ``settings/`` jail: the root ``Py4GW.ini``.

        This is the deliberate, unbypassable exception — a cross-process contract with the external
        (non-injected) launcher, which cannot use the ``settings/`` jail. It takes **no name and no
        scope**, so it can only ever be that single file; there is no argument to redirect it
        elsewhere. Use it ONLY for the root-contract keys (theme override, autoexec, version);
        everything else is per-account or global config via ``Settings(name[, scope])``.
        """
        cache_key = ('\x00Py4GW.ini', '\x00root')
        existing = cls._instances.get(cache_key)
        if existing is not None:
            return existing
        instance = object.__new__(cls)
        instance._name = 'Py4GW.ini'
        instance._scope = 'root'
        instance._doc = PySettings.py4gw_ini()
        instance._initialized = True
        cls._instances[cache_key] = instance
        return instance

    def __init__(self, name: str, scope: str = 'account') -> None:
        """Bind to the ``(name, scope)`` document (opening it on the native side once).

        ``scope`` is ``"account"`` (per-account, default) or ``"global"`` (machine-wide); both live
        under ``settings/``. ``"root"`` is not a valid scope (see :meth:`py4gw_ini`). Guarded so the
        shared instance is only initialized once even though the launcher may construct it repeatedly.
        """
        if getattr(self, '_initialized', False):
            return
        self._name = str(name)
        self._scope = str(scope)
        self._doc = PySettings.settings(self._name, self._scope)
        self._initialized = True

    # ------------------------------------------------------------------
    # Normalization: lowercase the key (configparser parity), keep section
    # ------------------------------------------------------------------

    @staticmethod
    def _s(section: str) -> str:
        """Normalize a section name: trimmed, but preserved verbatim otherwise (case included)."""
        return str(section).strip()

    @staticmethod
    def _k(key: str) -> str:
        """Normalize a key: trimmed and lowercased, matching the legacy on-disk key casing."""
        return str(key).strip().lower()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def is_ready(self) -> bool:
        """True once the document is bound to a file on disk.

        Account-scoped documents bind when the account anchor (email) resolves; global/root bind
        immediately. Reads before binding still succeed against in-memory/default state, so this is
        informational — you rarely need to gate on it (the anchor is present by the time scripts
        run).
        """
        return bool(self._doc.is_bound())

    def reload(self) -> bool:
        """Escape hatch: re-read the file from disk, **discarding unsaved in-memory changes**.

        Not part of normal flow — the document already reflects the latest writes. Use only to pick
        up an external edit to the file (e.g. a cross-account overlay written by another client).
        """
        return bool(self._doc.reload())

    def save(self) -> bool:
        """Escape hatch: force an immediate write to disk, bypassing the autosave debounce.

        **Not needed in normal flow** — every ``set`` is autosaved (~2 s after the last change, or
        within ~10 s, and on shutdown). Reach for this only when you must guarantee the bytes are on
        disk *right now* (e.g. immediately before an intentional hard exit).
        """
        return bool(self._doc.save())

    def path(self) -> str:
        """Absolute on-disk path of this document. Empty string until the document is bound."""
        return str(self._doc.path())

    def resolved_path(self) -> str:
        """The on-disk path if bound, otherwise fall back to the document ``name``.

        Handy for logging/diagnostics where you want a stable identifier even before binding.
        """
        p = str(self._doc.path())
        return p if p else self._name

    @property
    def name(self) -> str:
        """The document's name (``"path/filename"``), i.e. its ``(name, scope)`` identity."""
        return self._name

    @property
    def scope(self) -> str:
        """The document's scope: ``"account"`` or ``"global"`` (or ``"root"`` for the lone
        :meth:`py4gw_ini` document)."""
        return self._scope

    # ------------------------------------------------------------------
    # Typed get / set (explicit section + key)
    #
    # Template seeding (settings/Defaults/*.cfg for a brand-new file) is owned by
    # the native SettingsManager at bind time; nothing to do here.
    # ------------------------------------------------------------------

    def get_str(self, section: str, key: str, default: str = '') -> str:
        """Read a string. Returns ``default`` if the key is missing. Never raises."""
        return str(self._doc.get(self._s(section), self._k(key), str(default)))

    def get_int(self, section: str, key: str, default: int = 0) -> int:
        """Read an int. Returns ``default`` if the key is missing or does not parse. Never raises."""
        return int(self._doc.get(self._s(section), self._k(key), int(default)))

    def get_float(self, section: str, key: str, default: float = 0.0) -> float:
        """Read a float. Returns ``default`` if the key is missing or does not parse. Never raises."""
        return float(self._doc.get(self._s(section), self._k(key), float(default)))

    def get_bool(self, section: str, key: str, default: bool = False) -> bool:
        """Read a bool. Returns ``default`` if the key is missing or does not parse. Never raises."""
        return bool(self._doc.get(self._s(section), self._k(key), bool(default)))

    def get(self, section: str, key: str, default: Any = None) -> Any:
        """Typed read whose return type follows the type of ``default``.

        ``bool``/``int``/``float``/``str`` defaults dispatch to the matching typed getter. For any
        other (or ``None``) default, returns the raw stored string if the key exists, else
        ``default``. Never raises.
        """
        if isinstance(default, bool):
            return self.get_bool(section, key, default)
        if isinstance(default, int):
            return self.get_int(section, key, default)
        if isinstance(default, float):
            return self.get_float(section, key, default)
        if isinstance(default, str):
            return self.get_str(section, key, default)
        s, k = self._s(section), self._k(key)
        if self._doc.has(s, k):
            return str(self._doc.get(s, k, ''))
        return default

    def set(self, section: str, key: str, value: Any) -> None:
        """Write a value (stringified on disk), effective in memory now and autosaved later.

        **Dedups**: if the stored value already equals ``str(value)`` nothing is written and the
        document is not marked dirty, so re-setting an unchanged value every frame is free. There is
        no explicit save step — the native autosave pump persists the change (see module docstring).
        """
        s, k = self._s(section), self._k(key)
        serialized = str(value)
        if self._doc.has(s, k) and str(self._doc.get(s, k, '')) == serialized:
            return
        self._doc.set(s, k, serialized)

    def set_str(self, section: str, key: str, value: str) -> None:
        """Write a string value. See :meth:`set` (dedups; autosaved)."""
        self.set(section, key, str(value))

    def set_int(self, section: str, key: str, value: int) -> None:
        """Write an int value. See :meth:`set` (dedups; autosaved)."""
        self.set(section, key, int(value))

    def set_float(self, section: str, key: str, value: float) -> None:
        """Write a float value. See :meth:`set` (dedups; autosaved)."""
        self.set(section, key, float(value))

    def set_bool(self, section: str, key: str, value: bool) -> None:
        """Write a bool value. See :meth:`set` (dedups; autosaved)."""
        self.set(section, key, bool(value))

    # ------------------------------------------------------------------
    # Section operations
    # ------------------------------------------------------------------

    def has(self, section: str, key: str) -> bool:
        """True if ``(section, key)`` exists in the document."""
        return bool(self._doc.has(self._s(section), self._k(key)))

    def delete(self, section: str, key: str) -> bool:
        """Remove a single key. Returns True if it existed. Autosaved like any other change."""
        return bool(self._doc.remove(self._s(section), self._k(key)))

    def delete_section(self, section: str) -> bool:
        """Remove an entire section and all its keys. Returns True if it existed."""
        return bool(self._doc.delete_section(self._s(section)))

    def sections(self) -> list:
        """All section names currently in the document."""
        return list(self._doc.sections())

    def keys(self, section: str) -> list:
        """All key names within ``section`` (lowercased, as stored)."""
        return list(self._doc.keys(self._s(section)))

    def items(self, section: str) -> dict:
        """A ``{key: value}`` dict of every entry in ``section`` (values as raw strings)."""
        return {key: value for (key, value) in self._doc.items(self._s(section))}

    def clone_section(self, source: str, target: str) -> None:
        """Copy every key/value from section ``source`` into section ``target`` (within this file)."""
        src, dst = self._s(source), self._s(target)
        for (key, value) in self._doc.items(src):
            self._doc.set(dst, key, value)

    # ------------------------------------------------------------------
    # Cross-account copy (this document -> another account's file on disk).
    #
    # Copies from THIS account's document into settings/<target_email>/<name>.
    # Overlay semantics: keys present in the source overwrite the target; other
    # target keys are left untouched. This is a disk write on the target's file;
    # the target's running client picks it up on its next reload (a
    # message-triggered or throttled reload — not instantaneous). Returns True on
    # success (copying zero matching keys is success); False on a rejected email
    # or save failure.
    # ------------------------------------------------------------------

    def copy_document_to_account(self, target_email: str) -> bool:
        """Overlay this **entire** document (all sections) onto ``target_email``'s file on disk.

        Reads from *this* account's live document. Existing target keys not present here are left
        untouched. The target's running client picks up the change on its next reload (not instant).
        Returns True on success (including a zero-key copy); False on a rejected email/save failure.
        """
        return bool(PySettings.copy_document_to_account(self._name, str(target_email)))

    def copy_section_to_account(self, section: str, target_email: str) -> bool:
        """Overlay one whole ``section`` (all its keys) onto ``target_email``'s file. See
        :meth:`copy_document_to_account` for the overlay/reload/return semantics."""
        return bool(PySettings.copy_section_to_account(self._name, self._s(section), str(target_email)))

    def copy_keys_to_account(self, section: str, keys, target_email: str) -> bool:
        """Overlay a named subset of ``section``'s ``keys`` onto ``target_email``'s file.

        Keys are lowercased to match on-disk casing. See :meth:`copy_document_to_account` for the
        overlay/reload/return semantics.
        """
        norm_keys = [self._k(k) for k in keys]
        return bool(PySettings.copy_keys_to_account(self._name, self._s(section), norm_keys, str(target_email)))

    def apply_section_to_account(self, section: str, mapping, target_email: str) -> bool:
        """Overlay a caller-supplied ``{key: value}`` mapping into another account's section.

        Unlike ``copy_*`` (which read from *this* document), the values come from the caller — e.g.
        a saved profile or transformed settings. Keys are lowercased and values stringified to match
        the on-disk format. Same overlay-on-disk / next-reload / return semantics as the copy family.
        """
        items = [(self._k(k), str(v)) for k, v in dict(mapping).items()]
        return bool(PySettings.apply_section_to_account(self._name, self._s(section), items, str(target_email)))
