from dataclasses import dataclass, field
from typing import Any

import PyImGui

from .._legacy_facade import ImGui_Legacy
from ..py4gwcorelib_src.Settings import Settings


@dataclass
class WindowVarSpec:
    kind: str
    key: str
    section: str
    name: str
    default: Any


@dataclass
class ManagedWindowSpec:
    identifier: str
    filename: str
    title: str
    flags: int = PyImGui.WindowFlags.NoFlag
    vars: list[WindowVarSpec] = field(default_factory=list)
    open_var_name: str | None = None
    open_default: bool = False
    ini_key: str = ""


class WindowFactory:
    def __init__(self, ini_path: str) -> None:
        self.ini_path = ini_path
        self._windows: dict[str, ManagedWindowSpec] = {}

    def register_window(self, spec: ManagedWindowSpec) -> None:
        self._windows[spec.identifier] = spec

    def ensure_ini(self) -> bool:
        for spec in self._windows.values():
            spec.ini_key = Settings(f"{self.ini_path}/{spec.filename}", "account").name
            if not spec.ini_key:
                return False

        for spec in self._windows.values():
            cfg = Settings.find(spec.ini_key)
            if cfg:
                cfg.set("Window config", "init", True)

        return True

    def key(self, identifier: str) -> str:
        return self._windows[identifier].ini_key

    def begin(self, identifier: str, p_open=None) -> tuple[bool, bool]:
        spec = self._windows[identifier]
        return ImGui_Legacy.BeginWithClose(
            ini_key=spec.ini_key,
            name=spec.title,
            p_open=p_open,
            flags=spec.flags,
        )

    def is_open(self, identifier: str) -> bool:
        spec = self._windows[identifier]
        if spec.open_var_name is None:
            return False
        cfg = Settings.find(spec.ini_key)
        return cfg.get_bool("Configuration", spec.open_var_name, spec.open_default) if cfg else spec.open_default

    def set_open(self, identifier: str, value: bool) -> None:
        spec = self._windows[identifier]
        if spec.open_var_name is None:
            return
        cfg = Settings.find(spec.ini_key)
        if cfg:
            cfg.set("Configuration", spec.open_var_name, bool(value))
