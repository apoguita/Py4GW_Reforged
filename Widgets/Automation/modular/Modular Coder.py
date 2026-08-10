"""
Modular Coder widget entry point.

Thin wrapper for the recording-only modular JSON script helper.
"""

from __future__ import annotations

import PyImGui

from Py4GWCoreLib.modular.widget_runtime import guarded_widget_main
from Py4GWCoreLib.modular.ui_scope import tooltip_scope
from Sources.modular_data.tools import script_helper


module_name = "Modular Coder"
MODULE_NAME = "Modular Coder"
MODULE_ICON = "Assets/Textures/Module_Icons/Route Planner.png"
MODULE_TAGS = ["Automation", "modular_bot"]


def main() -> None:
    guarded_widget_main(MODULE_NAME, script_helper.main)


def tooltip() -> None:
    PyImGui.set_next_window_size((430, 0))
    with tooltip_scope():
        PyImGui.text(MODULE_NAME)
        PyImGui.separator()
        PyImGui.text_wrapped("Recording helper for creating canonical modular JSON bot recipes.")
        PyImGui.text_wrapped("Records steps only; replay is intentionally handled by Modular Tester.")


if __name__ == "__main__":
    main()
