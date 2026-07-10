"""Settings — Python wrapper over the native ``PySettings`` module.

All settings logic lives here, on top of the native (cached + autosaved)
``PySettings`` document. Design points that make the migration correct:

- **Explicit ``(section, key)`` addressing.** Uses the native ``get``/``set``/
  ``has``/``remove`` API where section and key are separate arguments, so names
  may contain ``/``, ``\\``, ``:`` or spaces (e.g. ``[Widget:Guild Wars\\Triggers/
  Foo.py]``). Nothing is slash-joined.
- **Key case.** The legacy configparser backend lowercased option keys on disk,
  so keys are lowercased here; **section names are preserved verbatim**.
- **Values.** Written as ``str(value)`` to mirror the legacy on-disk format; typed
  getters let native parse them back. ``set`` dedups against the current value so
  unchanged existing files are not rewritten.
- **No readiness gate.** Native binds account documents synchronously in
  ``Open()`` once the anchor is resolved, so a read right after open sees disk.

Autosave and flush cadence are owned entirely by the native side.
"""

from typing import Any
from typing import Optional

import PySettings


class Settings:
    """Typed settings document backed by native ``PySettings``."""

    _instances: dict[tuple[str, str], 'Settings'] = {}

    def __new__(cls, name: str, scope: str = 'account') -> 'Settings':
        instance_key = (str(name), str(scope))
        existing = cls._instances.get(instance_key)
        if existing is not None:
            return existing
        instance = super().__new__(cls)
        cls._instances[instance_key] = instance
        return instance

    def __init__(self, name: str, scope: str = 'account') -> None:
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
        return str(section).strip()

    @staticmethod
    def _k(key: str) -> str:
        return str(key).strip().lower()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def is_ready(self) -> bool:
        return bool(self._doc.is_bound())

    def reload(self) -> bool:
        return bool(self._doc.reload())

    def save(self) -> bool:
        return bool(self._doc.save())

    def path(self) -> str:
        return str(self._doc.path())

    def resolved_path(self) -> str:
        p = str(self._doc.path())
        return p if p else self._name

    @classmethod
    def ensure_key(cls, path: str, filename: str, scope: str = 'account') -> str:
        """Open/cache the document and return its name (the old ``ini_key``).

        No account-readiness gate: the native side won't initialize until the
        account email is acquired, so the email is always present by the time any
        script runs. The returned string is the ``Settings`` document name and can
        be passed to ``ImGui_Legacy.Begin/End`` and ``Settings.find``.
        """
        path = str(path).strip('/')
        filename = str(filename).strip('/')
        name = f"{path}/{filename}" if path else filename
        if not name:
            return ""
        cls(name, scope)
        return name

    @classmethod
    def ensure_global_key(cls, path: str, filename: str) -> str:
        return cls.ensure_key(path, filename, scope='global')

    @classmethod
    def find(cls, name: str) -> Optional['Settings']:
        """Return the already-open Settings for this document name (any scope).

        Used by window wrappers that are handed only the document name (the old
        ``ini_key``) and need the document the caller already created. Returns
        None if nothing has opened that name yet.
        """
        name = str(name)
        for (n, _scope), inst in cls._instances.items():
            if n == name:
                return inst
        return None

    @property
    def name(self) -> str:
        return self._name

    @property
    def scope(self) -> str:
        return self._scope

    # ------------------------------------------------------------------
    # Typed get / set (explicit section + key)
    #
    # Template seeding (settings/Defaults/*.cfg for a brand-new file) is owned by
    # the native SettingsManager at bind time; nothing to do here.
    # ------------------------------------------------------------------

    def get_str(self, section: str, key: str, default: str = '') -> str:
        return str(self._doc.get(self._s(section), self._k(key), str(default)))

    def get_int(self, section: str, key: str, default: int = 0) -> int:
        return int(self._doc.get(self._s(section), self._k(key), int(default)))

    def get_float(self, section: str, key: str, default: float = 0.0) -> float:
        return float(self._doc.get(self._s(section), self._k(key), float(default)))

    def get_bool(self, section: str, key: str, default: bool = False) -> bool:
        return bool(self._doc.get(self._s(section), self._k(key), bool(default)))

    def get(self, section: str, key: str, default: Any = None) -> Any:
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
        s, k = self._s(section), self._k(key)
        serialized = str(value)
        if self._doc.has(s, k) and str(self._doc.get(s, k, '')) == serialized:
            return
        self._doc.set(s, k, serialized)

    def set_str(self, section: str, key: str, value: str) -> None:
        self.set(section, key, str(value))

    def set_int(self, section: str, key: str, value: int) -> None:
        self.set(section, key, int(value))

    def set_float(self, section: str, key: str, value: float) -> None:
        self.set(section, key, float(value))

    def set_bool(self, section: str, key: str, value: bool) -> None:
        self.set(section, key, bool(value))

    # ------------------------------------------------------------------
    # Section operations
    # ------------------------------------------------------------------

    def has(self, section: str, key: str) -> bool:
        return bool(self._doc.has(self._s(section), self._k(key)))

    def delete(self, section: str, key: str) -> bool:
        return bool(self._doc.remove(self._s(section), self._k(key)))

    def delete_section(self, section: str) -> bool:
        return bool(self._doc.delete_section(self._s(section)))

    def sections(self) -> list:
        return list(self._doc.sections())

    def keys(self, section: str) -> list:
        return list(self._doc.keys(self._s(section)))

    def items(self, section: str) -> dict:
        return {key: value for (key, value) in self._doc.items(self._s(section))}

    def clone_section(self, source: str, target: str) -> None:
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
        return bool(PySettings.copy_document_to_account(self._name, str(target_email)))

    def copy_section_to_account(self, section: str, target_email: str) -> bool:
        return bool(PySettings.copy_section_to_account(self._name, self._s(section), str(target_email)))

    def copy_keys_to_account(self, section: str, keys, target_email: str) -> bool:
        norm_keys = [self._k(k) for k in keys]
        return bool(PySettings.copy_keys_to_account(self._name, self._s(section), norm_keys, str(target_email)))

    def apply_section_to_account(self, section: str, mapping, target_email: str) -> bool:
        """Overlay a caller-supplied {key: value} mapping into another account's section.

        Unlike copy_*, the values come from the caller (e.g. a saved profile or
        transformed settings), not from this document. Keys are lowercased and values
        stringified to match on-disk format.
        """
        items = [(self._k(k), str(v)) for k, v in dict(mapping).items()]
        return bool(PySettings.apply_section_to_account(self._name, self._s(section), items, str(target_email)))
