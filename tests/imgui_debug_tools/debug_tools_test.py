"""
In-client smoke test for Dear ImGui_Legacy debug tooling.

What this script is for:
- Open the built-in Dear ImGui_Legacy debug windows from Python.
- Keep them visible with simple checkboxes.
- Provide quick one-shot buttons when you only want to poke them open.

Notes:
- The debug windows are owned by Dear ImGui_Legacy itself.
- They generally need to be called every frame while you want them visible.
- This script does not enable extra native diagnostics; it only exposes the
  windows you already have bound in PyImGui.
"""

import PyImGui

MODULE_NAME = 'ImGui_Legacy Debug Tools Test'

_show_metrics = False
_show_debug_log = False
_show_id_stack = False
_show_demo = False


def _bool_label(value: bool) -> str:
    return 'yes' if value else 'no'


def _draw_debug_windows() -> None:
    if _show_metrics:
        PyImGui.show_metrics_window()
    if _show_debug_log:
        PyImGui.show_debug_log_window()
    if _show_id_stack:
        PyImGui.show_id_stack_tool_window()
    if _show_demo:
        PyImGui.show_demo_window()


def main() -> None:
    global _show_metrics
    global _show_debug_log
    global _show_id_stack
    global _show_demo

    PyImGui.set_next_window_size((540.0, 330.0), PyImGui.ImGuiCond.FirstUseEver)
    if not PyImGui.begin(MODULE_NAME, PyImGui.WindowFlags.NoCollapse):
        PyImGui.end()
        _draw_debug_windows()
        return

    PyImGui.text('Use these toggles to keep Dear ImGui_Legacy debug windows open.')
    PyImGui.text('The red "Message from Dear ImGui_Legacy" tooltip is separate from these windows.')
    PyImGui.separator()

    _show_metrics = PyImGui.checkbox('Keep Metrics/Debugger window open', _show_metrics)
    _show_debug_log = PyImGui.checkbox('Keep Debug Log window open', _show_debug_log)
    _show_id_stack = PyImGui.checkbox('Keep ID Stack Tool window open', _show_id_stack)
    _show_demo = PyImGui.checkbox('Keep Demo window open', _show_demo)

    PyImGui.separator()
    PyImGui.text('One-shot open actions:')

    if PyImGui.button('Open Metrics/Debugger'):
        _show_metrics = True
    PyImGui.same_line(0, -1)
    if PyImGui.button('Open Debug Log'):
        _show_debug_log = True

    if PyImGui.button('Open ID Stack Tool'):
        _show_id_stack = True
    PyImGui.same_line(0, -1)
    if PyImGui.button('Open Demo'):
        _show_demo = True

    PyImGui.separator()
    PyImGui.text('Current state:')
    PyImGui.bullet_text(f'Metrics window: {_bool_label(_show_metrics)}')
    PyImGui.bullet_text(f'Debug log: {_bool_label(_show_debug_log)}')
    PyImGui.bullet_text(f'ID stack tool: {_bool_label(_show_id_stack)}')
    PyImGui.bullet_text(f'Demo window: {_bool_label(_show_demo)}')

    PyImGui.separator()
    PyImGui.text('Useful flow:')
    PyImGui.bullet_text('Use Debug Log for general Dear ImGui_Legacy events and recoverable errors.')
    PyImGui.bullet_text('Use ID Stack Tool when the tooltip mentions duplicate/conflicting IDs.')
    PyImGui.bullet_text('Use Metrics/Debugger to inspect windows, draw lists, docking, and tables.')

    PyImGui.end()

    _draw_debug_windows()
