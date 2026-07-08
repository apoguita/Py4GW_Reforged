"""
In-client smoke test for Dear ImGui_Legacy multi-viewport support.

Workflow:
1. Rebuild and inject the current native DLL.
2. Load this script in-client.
3. Confirm backend support reports True.
4. Drag the "Viewport Probe" window outside the Guild Wars client.
"""

import PyImGui

MODULE_NAME = 'ImGui_Legacy Multi-Viewport Test'
_show_probe = True
_show_demo = False
_initialized = False
_detach_probe = True


def _bool_label(value: bool) -> str:
    return 'yes' if value else 'no'


def _draw_probe_window() -> None:
    global _show_probe
    global _detach_probe

    if not _show_probe:
        return

    if _detach_probe:
        PyImGui.set_next_window_detached(True)
    PyImGui.set_next_window_size((420.0, 220.0), PyImGui.ImGuiCond.FirstUseEver)
    visible = PyImGui.begin('Viewport Probe', PyImGui.WindowFlags.NoCollapse)
    if visible:
        PyImGui.text('Drag this window outside the GW client.')
        PyImGui.text('If multi-viewport is working, it becomes its own OS window.')
        PyImGui.separator()
        PyImGui.text(f'Enabled: {_bool_label(PyImGui.is_multi_viewport_enabled())}')
        PyImGui.text(f'Supported: {_bool_label(PyImGui.has_multi_viewport_support())}')
        PyImGui.text(f'Window DPI scale: {PyImGui.get_window_dpi_scale():.2f}')
        PyImGui.text('Tip: keep WindowBg opaque when detached windows look washed out.')
    PyImGui.end()


def main() -> None:
    global _show_demo
    global _show_probe
    global _initialized
    global _detach_probe

    if not _initialized:
        PyImGui.set_multi_viewport_enabled(True)
        _initialized = True

    PyImGui.set_next_window_size((520.0, 260.0), PyImGui.ImGuiCond.FirstUseEver)
    if not PyImGui.begin(MODULE_NAME, PyImGui.WindowFlags.NoCollapse):
        PyImGui.end()
        _draw_probe_window()
        return

    enabled = PyImGui.is_multi_viewport_enabled()
    supported = PyImGui.has_multi_viewport_support()
    io = PyImGui.get_io()

    PyImGui.text('Detached ImGui_Legacy windows require ViewportsEnable plus backend support.')
    PyImGui.separator()

    new_enabled = PyImGui.checkbox('Enable multi-viewport', enabled)
    if new_enabled != enabled:
        PyImGui.set_multi_viewport_enabled(new_enabled)
        enabled = new_enabled

    _show_probe = PyImGui.checkbox('Show detachable probe window', _show_probe)
    _detach_probe = PyImGui.checkbox('Detach probe window only', _detach_probe)
    _show_demo = PyImGui.checkbox('Show Dear ImGui_Legacy demo window', _show_demo)

    PyImGui.separator()
    PyImGui.text(f'Docking enabled: {_bool_label(PyImGui.is_docking_enabled())}')
    PyImGui.text(f'Viewport enabled: {_bool_label(enabled)}')
    PyImGui.text(f'Backend support: {_bool_label(supported)}')
    PyImGui.text(f'io.config_flags = 0x{io.config_flags:08X}')
    PyImGui.text(f'io.backend_flags = 0x{io.backend_flags:08X}')

    if not supported:
        PyImGui.separator()
        PyImGui.text_colored(
            'Backend support is missing. Detached windows will not appear until both Win32 and DX9 viewport flags are set.',
            (1.0, 0.45, 0.45, 1.0),
        )

    PyImGui.end()

    _draw_probe_window()
    if _show_demo:
        PyImGui.show_demo_window()
