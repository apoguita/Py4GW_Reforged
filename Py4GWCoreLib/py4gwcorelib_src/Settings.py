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
- **Legacy var-map.** A plain per-document dict (``var_name -> (section, name,
  type, default)``) used only by IniManager's old ``get``/``set`` path; the
  direct API ignores it.

Autosave and flush cadence are owned entirely by the native side.
"""

import os
from dataclasses import dataclass
from typing import Any
from typing import Optional

import PySettings


@dataclass
class _WindowState:
    initialized: bool = False
    x: int = 0
    y: int = 0
    w: int = 0
    h: int = 0
    collapsed: bool = False
    begin_called: bool = False
    begin_returned_true: bool = False


@dataclass
class _LegacyVar:
    section: str
    name: str
    var_type: str  # 'bool' | 'int' | 'float' | 'str'
    default: Any


class Settings:
    """Typed settings document backed by native ``PySettings``."""

    WINDOW_SECTION = 'Window config'

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
        self._win = _WindowState()
        self._legacy_vars: dict[str, _LegacyVar] = {}
        self._seeded = False
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

    @property
    def name(self) -> str:
        return self._name

    @property
    def scope(self) -> str:
        return self._scope

    # ------------------------------------------------------------------
    # Templates (.cfg seeding, parity with IniManager)
    # ------------------------------------------------------------------

    def _ensure_seeded(self) -> None:
        if self._seeded:
            return
        if not self._doc.is_bound():
            return  # path unknown until bound (account docs bind on anchor)
        self._seeded = True
        if self._doc.sections():
            return  # existing file — never overwrite
        template = self._find_template()
        if template:
            self._apply_template(template)

    def _find_template(self) -> Optional[str]:
        try:
            import PySystem
            base = PySystem.Console.get_projects_path()
        except Exception:
            return None
        defaults = os.path.join(base, 'settings', 'Defaults')
        relative = self._name.replace('.ini', '.cfg')
        specialized = os.path.join(defaults, *relative.split('/'))
        if os.path.exists(specialized):
            return specialized
        fallback = os.path.join(defaults, 'default_template.cfg')
        if os.path.exists(fallback):
            return fallback
        return None

    def _apply_template(self, path: str) -> None:
        import configparser
        parser = configparser.ConfigParser()
        try:
            parser.read(path, encoding='utf-8')
        except Exception:
            return
        for section in parser.sections():
            for key, value in parser.items(section):
                # configparser already lowercased the key; write straight through.
                self._doc.set(section, key, str(value))

    # ------------------------------------------------------------------
    # Typed get / set (explicit section + key)
    # ------------------------------------------------------------------

    def get_str(self, section: str, key: str, default: str = '') -> str:
        self._ensure_seeded()
        return str(self._doc.get(self._s(section), self._k(key), str(default)))

    def get_int(self, section: str, key: str, default: int = 0) -> int:
        self._ensure_seeded()
        return int(self._doc.get(self._s(section), self._k(key), int(default)))

    def get_float(self, section: str, key: str, default: float = 0.0) -> float:
        self._ensure_seeded()
        return float(self._doc.get(self._s(section), self._k(key), float(default)))

    def get_bool(self, section: str, key: str, default: bool = False) -> bool:
        self._ensure_seeded()
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
        self._ensure_seeded()
        s, k = self._s(section), self._k(key)
        if self._doc.has(s, k):
            return str(self._doc.get(s, k, ''))
        return default

    def set(self, section: str, key: str, value: Any) -> None:
        self._ensure_seeded()
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
    # Legacy var-map (compat for IniManager's add_*/get/set path only)
    # ------------------------------------------------------------------

    def register_var(self, var_name: str, section: str, name: str, var_type: str, default: Any) -> None:
        self._legacy_vars[str(var_name)] = _LegacyVar(self._s(section), str(name), str(var_type), default)

    def get_var(self, var_name: str, default: Any = None, section: str = '') -> Any:
        vd = self._legacy_vars.get(var_name)
        if vd is None:
            # Undeclared: address by the passed section + var_name directly.
            return self.get(section, var_name, default)
        # Declared: the fallback is the DECLARED default, addressed at (vd.section, vd.name).
        if vd.var_type == 'bool':
            return self.get_bool(vd.section, vd.name, bool(vd.default))
        if vd.var_type == 'int':
            return self.get_int(vd.section, vd.name, int(vd.default))
        if vd.var_type == 'float':
            return self.get_float(vd.section, vd.name, float(vd.default))
        return self.get_str(vd.section, vd.name, str(vd.default))

    def set_var(self, var_name: str, value: Any, section: str = '') -> None:
        vd = self._legacy_vars.get(var_name)
        if vd is None:
            self.set(section, var_name, value)
            return
        self.set(vd.section, vd.name, value)

    # ------------------------------------------------------------------
    # Window config — ordinary [Window config] keys via get/set
    # ------------------------------------------------------------------

    def begin_window_config(self) -> None:
        import PyImGui

        state = self._win
        state.begin_called = True
        state.begin_returned_true = False
        if state.initialized:
            return

        state.x = self.get_int(self.WINDOW_SECTION, 'x', 0)
        state.y = self.get_int(self.WINDOW_SECTION, 'y', 0)
        state.w = self.get_int(self.WINDOW_SECTION, 'width', 0)
        state.h = self.get_int(self.WINDOW_SECTION, 'height', 0)
        state.collapsed = self.get_bool(self.WINDOW_SECTION, 'collapsed', False)

        PyImGui.set_next_window_pos(state.x, state.y)
        if state.w > 0 and state.h > 0:
            PyImGui.set_next_window_size(state.w, state.h)
        PyImGui.set_next_window_collapsed(state.collapsed, 0)
        state.initialized = True

    def mark_begin_success(self) -> None:
        self._win.begin_returned_true = True

    def track_window_collapsed(self, begin_result: bool) -> None:
        state = self._win
        new_collapsed = not begin_result
        if new_collapsed == state.collapsed:
            return
        state.collapsed = new_collapsed
        self.set_bool(self.WINDOW_SECTION, 'collapsed', state.collapsed)

    def is_window_collapsed(self) -> bool:
        return self._win.collapsed

    def end_window_config(self) -> None:
        import PyImGui

        state = self._win
        if not state.begin_called or not state.begin_returned_true:
            state.begin_called = False
            state.begin_returned_true = False
            return

        end_pos = PyImGui.get_window_pos()
        end_size = PyImGui.get_window_size()
        new_x, new_y = int(end_pos[0]), int(end_pos[1])
        new_w, new_h = int(end_size[0]), int(end_size[1])

        if new_x != state.x:
            state.x = new_x
            self.set_int(self.WINDOW_SECTION, 'x', new_x)
        if new_y != state.y:
            state.y = new_y
            self.set_int(self.WINDOW_SECTION, 'y', new_y)
        if new_w != state.w:
            state.w = new_w
            self.set_int(self.WINDOW_SECTION, 'width', new_w)
        if new_h != state.h:
            state.h = new_h
            self.set_int(self.WINDOW_SECTION, 'height', new_h)

        state.begin_called = False
        state.begin_returned_true = False
