"""IniManager — backward-compatible shell over the ``Settings`` wrapper.

Historically ``IniManager`` was a self-contained INI handler (per-account file
grouping, throttled staging, a config-variable system, window persistence). All
of that now lives in native ``PySettings`` (cache + autosave) and the ``Settings``
wrapper. This class keeps its **exact public API** — and the node/``ini_handler``
handle that some scripts reach for — so no caller changes, but every method now
forwards into ``Settings``. It is meant to be deleted once callers use ``Settings``
directly.
"""

from typing import Any
from typing import Optional

from Py4GWCoreLib.Player import Player
from Py4GWCoreLib.py4gwcorelib_src.Settings import Settings


# ------------------------------------------------------------
# Node facade: keeps the shape scripts reach for (`_get_node(key).ini_handler`),
# backed by Settings so it and IniManager persist to the same place.
# ------------------------------------------------------------

class _IniHandlerFacade:
    """IniHandler-shaped handle backed by a ``Settings`` document."""

    def __init__(self, settings: Settings):
        self._s = settings

    @property
    def filename(self) -> str:
        return self._s.resolved_path()

    def reload(self):
        return self._s.reload()

    def save(self, config=None):
        return self._s.save()

    def read_key(self, section: str, key: str, default_value: str = "") -> str:
        return self._s.get_str(section, key, default_value)

    def read_int(self, section: str, key: str, default_value: int = 0) -> int:
        return self._s.get_int(section, key, default_value)

    def read_float(self, section: str, key: str, default_value: float = 0.0) -> float:
        return self._s.get_float(section, key, default_value)

    def read_bool(self, section: str, key: str, default_value: bool = False) -> bool:
        return self._s.get_bool(section, key, default_value)

    def write_key(self, section: str, key: str, value) -> None:
        self._s.set(section, key, value)

    def delete_key(self, section: str, key: str) -> None:
        self._s.delete(section, key)

    def delete_section(self, section: str) -> None:
        self._s.delete_section(section)

    def list_sections(self) -> list:
        return self._s.sections()

    def list_keys(self, section: str) -> dict:
        return self._s.items(section)

    def has_key(self, section: str, key: str) -> bool:
        return self._s.has(section, key)

    def clone_section(self, source_section: str, target_section: str) -> None:
        self._s.clone_section(source_section, target_section)


class _ConfigNode:
    """Minimal stand-in for the old ConfigNode; exposes the handle + legacy fields."""

    def __init__(self, settings: Settings, is_global: bool):
        self.settings = settings
        self.ini_handler = _IniHandlerFacade(settings)
        self.is_global = bool(is_global)
        # Vestigial legacy fields. Some callers poke these directly alongside
        # ini_handler.write_key (the real persistence path via Settings). They are
        # no longer read for persistence; kept as harmless empty containers.
        self.vars_loaded = True
        self.vars_values: dict = {}
        self.cached_values: dict = {}
        self.pending_writes: dict = {}
        self.needs_flush = False


# ------------------------------------------------------------
# Config Manager (Singleton, thin forwarder over Settings)
# ------------------------------------------------------------

class IniManager:
    _instance = None
    _callback_name = "ConfigManager.FlushDiskData"

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(IniManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._handlers: dict[str, _ConfigNode] = {}
        self._initialized = True

    # --------------------------------------------------------
    # Callbacks (dead paths — native autosave replaces the flush callback)
    # --------------------------------------------------------
    @staticmethod
    def enable():
        return

    @staticmethod
    def disable():
        return

    @staticmethod
    def _flush_callback(*args, **kwargs):
        return

    # --------------------------------------------------------
    # Account / Path helpers
    # --------------------------------------------------------
    def get_account_email(self) -> str:
        return Player.GetAccountEmail()

    def get_defaults_path(self) -> str:
        return ""

    def get_path(self) -> Optional[str]:
        try:
            import PySettings
            directory = PySettings.get_settings_directory()
            return directory if directory else None
        except Exception:
            return None

    def _is_account_ready(self) -> bool:
        return self.get_account_email() != ""

    def _make_key(self, path: str, filename: str) -> str:
        path = path.strip("/")
        filename = filename.strip("/")
        return f"{path}/{filename}" if path else filename

    # --------------------------------------------------------
    # Node creation / lookup
    # --------------------------------------------------------
    def AddIniHandler(self, path: str, filename: str, is_global: bool = False) -> str:
        path = path.strip("/")
        filename = filename.strip("/")

        # account guard only for NON-global (the original signal)
        if not is_global and not self._is_account_ready():
            return ""

        key = self._make_key(path, filename)
        if not key:
            return ""

        node = self._handlers.get(key)
        if node is None:
            scope = "global" if is_global else "account"
            node = _ConfigNode(Settings(key, scope=scope), is_global)
            self._handlers[key] = node
        return key

    def _get_node(self, key: str) -> Optional[_ConfigNode]:
        return self._handlers.get(key)

    # ----------------------------
    # IniHandler API — forwarded to Settings
    # ----------------------------
    def reload(self, key: str):
        node = self._handlers.get(key)
        return node.settings.reload() if node else None

    def save(self, key: str, config=None):
        return

    def read_key(self, key: str, section: str, name: str, default=""):
        node = self._handlers.get(key)
        return node.settings.get_str(section, name, default) if node else default

    def read_int(self, key: str, section: str, name: str, default=0):
        node = self._handlers.get(key)
        return node.settings.get_int(section, name, default) if node else default

    def read_float(self, key: str, section: str, name: str, default=0.0):
        node = self._handlers.get(key)
        return node.settings.get_float(section, name, default) if node else default

    def read_bool(self, key: str, section: str, name: str, default=False):
        node = self._handlers.get(key)
        return node.settings.get_bool(section, name, default) if node else default

    def write_key(self, key: str, section: str, name: str, value):
        node = self._handlers.get(key)
        if node:
            node.settings.set(section, name, value)

    def delete_key(self, key: str, section: str, name: str):
        node = self._handlers.get(key)
        if node:
            node.settings.delete(section, name)

    def delete_section(self, key: str, section: str):
        node = self._handlers.get(key)
        if node:
            node.settings.delete_section(section)

    def list_sections(self, key: str) -> list:
        node = self._handlers.get(key)
        return node.settings.sections() if node else []

    def list_keys(self, key: str, section: str) -> dict:
        node = self._handlers.get(key)
        return node.settings.items(section) if node else {}

    def has_key(self, key: str, section: str, name: str) -> bool:
        node = self._handlers.get(key)
        return node.settings.has(section, name) if node else False

    def clone_section(self, key: str, src: str, dst: str):
        node = self._handlers.get(key)
        if node:
            node.settings.clone_section(src, dst)

    # ----------------------------
    # Window config management — forwarded to Settings
    # ----------------------------
    def begin_window_config(self, key: str):
        if not key:
            return
        node = self._handlers.get(key)
        if node:
            node.settings.begin_window_config()

    def mark_begin_success(self, key: str):
        node = self._handlers.get(key)
        if node:
            node.settings.mark_begin_success()

    def track_window_collapsed(self, key: str, begin_result: bool):
        if not key:
            return
        node = self._handlers.get(key)
        if node:
            node.settings.track_window_collapsed(begin_result)

    def IsWindowCollapsed(self, key: str) -> bool:
        if not key:
            return False
        node = self._handlers.get(key)
        return node.settings.is_window_collapsed() if node else False

    def end_window_config(self, key: str):
        if not key:
            return
        node = self._handlers.get(key)
        if node:
            node.settings.end_window_config()

    # ----------------------------
    # Key Factory (document creation)
    # ----------------------------
    def ensure_key(self, path: str, filename: str) -> str:
        return self.AddIniHandler(path, filename, is_global=False)

    def ensure_global_key(self, path: str, filename: str) -> str:
        return self.AddIniHandler(path, filename, is_global=True)

    # ----------------------------
    # Config-variable system — forwarded to the Settings legacy var-map.
    # add_* records the var_name -> (section, name, type, default) mapping;
    # load_once/save_vars are no-ops (native is the cache + flush); get/set
    # resolve var_name through the map.
    # ----------------------------
    def _add_var_def(self, key: str, var_name: str, section: str, name: str, default: Any, vtype: str):
        node = self._handlers.get(key)
        if node:
            node.settings.register_var(var_name, section, name, vtype, default)

    def add_bool(self, key: str, var_name: str, section: str, name: str, default: bool = False):
        self._add_var_def(key, var_name, section, name, default, "bool")

    def add_int(self, key: str, var_name: str, section: str, name: str, default: int = 0):
        self._add_var_def(key, var_name, section, name, default, "int")

    def add_float(self, key: str, var_name: str, section: str, name: str, default: float = 0.0):
        self._add_var_def(key, var_name, section, name, default, "float")

    def add_str(self, key: str, var_name: str, section: str, name: str, default: str = ""):
        self._add_var_def(key, var_name, section, name, default, "str")

    def load_once(self, key: str):
        return

    def save_vars(self, key: str):
        return

    def get(self, key: str, var_name: str, default=None, section: str = ""):
        node = self._handlers.get(key)
        return node.settings.get_var(var_name, default, section) if node else default

    def getInt(self, key: str, var_name: str, default=0, section: str = "") -> int:
        node = self._handlers.get(key)
        if not node:
            return default
        try:
            val = node.settings.get_var(var_name, default, section)
            return int(val) if val is not None else default
        except Exception:
            return default

    def getFloat(self, key: str, var_name: str, default=0.0, section: str = "") -> float:
        node = self._handlers.get(key)
        if not node:
            return default
        try:
            val = node.settings.get_var(var_name, default, section)
            return float(val) if val is not None else default
        except Exception:
            return default

    def getBool(self, key: str, var_name: str, default=False, section: str = "") -> bool:
        node = self._handlers.get(key)
        if not node:
            return default
        try:
            val = node.settings.get_var(var_name, default, section)
            return bool(val) if val is not None else default
        except Exception:
            return default

    def getStr(self, key: str, var_name: str, default="", section: str = "") -> str:
        node = self._handlers.get(key)
        if not node:
            return default
        try:
            val = node.settings.get_var(var_name, default, section)
            return str(val) if val is not None else default
        except Exception:
            return default

    def set(self, key: str, var_name: str, value, section: str = ""):
        node = self._handlers.get(key)
        if node:
            node.settings.set_var(var_name, value, section)
