from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import types
from pathlib import Path


CANDIDATE = Path(__file__).resolve().parents[2] / "Py4GW_widget_manager.py"


class FakePyImGui(types.ModuleType):
    def __init__(self) -> None:
        super().__init__("PyImGui")
        self.context_ready = False
        self.probes = 0
        self.unrelated_error = False

    def StyleConfig(self):
        self.probes += 1
        if self.unrelated_error:
            raise RuntimeError("unrelated style error")
        if not self.context_ready:
            raise RuntimeError("no ImGui context")
        return object()


class FakeSettings:
    def __init__(self, path: str, scope: str) -> None:
        self.name = f"{scope}:{path}"

    def get_bool(self, section: str, key: str, default: bool) -> bool:
        return default


class FakeHandler:
    def __init__(self) -> None:
        self.MANAGER_INI_KEY = ""
        self.enable_all = False
        self.discover_calls = 0
        self.apply_calls = 0

    def discover(self) -> None:
        self.discover_calls += 1

    def _apply_ini_configuration(self) -> None:
        self.apply_calls += 1


def _module(name: str, **attributes):
    module = types.ModuleType(name)
    for key, value in attributes.items():
        setattr(module, key, value)
    return module


def main() -> None:
    original_modules = dict(sys.modules)
    fake_imgui = FakePyImGui()
    sys.modules["PyImGui"] = fake_imgui
    try:
        spec = importlib.util.spec_from_file_location("Py4GW_widget_manager", CANDIDATE)
        assert spec is not None and spec.loader is not None
        host = importlib.util.module_from_spec(spec)
        sys.modules["Py4GW_widget_manager"] = host
        spec.loader.exec_module(host)

        imported: dict[str, object] = {}
        exec("from Py4GW_widget_manager import get_widget_handler", imported)
        assert imported["get_widget_handler"] is host.get_widget_handler
        host.main()
        assert "Py4GWCoreLib" not in sys.modules, (
            "core library imported before the ImGui context existed"
        )
        assert host.widget_manager is None

        try:
            host.get_widget_handler()
        except RuntimeError as exc:
            assert "no ImGui context" in str(exc)
        else:
            raise AssertionError("pre-context compatibility call did not fail explicitly")

        fake_imgui.unrelated_error = True
        try:
            host.main()
        except RuntimeError as exc:
            assert str(exc) == "unrelated style error"
        else:
            raise AssertionError("unrelated startup error was swallowed")
        fake_imgui.unrelated_error = False

        handler = FakeHandler()
        launch_calls: list[str] = []
        fake_imgui.context_ready = True
        sys.modules["Py4GWCoreLib"] = _module("Py4GWCoreLib")
        sys.modules["Py4GWCoreLib.py4gwcorelib_src"] = _module(
            "Py4GWCoreLib.py4gwcorelib_src"
        )
        sys.modules["Py4GWCoreLib.py4gwcorelib_src.Settings"] = _module(
            "Py4GWCoreLib.py4gwcorelib_src.Settings",
            Settings=FakeSettings,
        )
        sys.modules["Py4GWCoreLib.py4gwcorelib_src.WidgetManager"] = _module(
            "Py4GWCoreLib.py4gwcorelib_src.WidgetManager",
            WidgetHandler=FakeHandler,
            get_widget_handler=lambda: handler,
        )
        sys.modules["Py4GWCoreLib.py4gwcorelib_src.launch_bar"] = _module(
            "Py4GWCoreLib.py4gwcorelib_src.launch_bar"
        )
        sys.modules["Py4GWCoreLib.py4gwcorelib_src.launch_bar.launchpad"] = _module(
            "Py4GWCoreLib.py4gwcorelib_src.launch_bar.launchpad",
            register_launchpad_once=lambda: launch_calls.append("registered"),
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            previous_cwd = Path.cwd()
            try:
                os.chdir(temp_dir)
                host.main()
                host.main()
            finally:
                os.chdir(previous_cwd)

        assert host.widget_manager is handler
        assert host.get_widget_handler() is handler
        assert handler.discover_calls == 1
        assert handler.apply_calls == 1
        assert handler.MANAGER_INI_KEY
        assert launch_calls == ["registered", "registered"]
        assert fake_imgui.probes == 4
        print(
            "PASS: legacy get_widget_handler import survives the no-context frame "
            "and returns the singleton after deferred bootstrap"
        )
    finally:
        sys.modules.clear()
        sys.modules.update(original_modules)


if __name__ == "__main__":
    main()
