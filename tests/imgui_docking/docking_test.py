"""
In-client docking test for the PyImGui docking surface.

What docking is:
- Docking lets multiple ImGui_Legacy windows live inside one dockspace.
- A dockspace is a container that can host tabs, splits, and re-arrangeable panes.
- This is separate from multi-viewport. Docking stays inside the main ImGui_Legacy host window.

Useful patterns:
- Manual docking:
    1. Create a dockspace.
    2. Open normal windows.
    3. Drag one window by its tab/title bar onto another or into a split target.

- Programmatic docking (DockBuilder):
    1. Create/get a dockspace id.
    2. Remove any previous node.
    3. Add a node and set its size.
    4. Split the node into child nodes.
    5. Dock named windows into those child nodes.
    6. Finish the layout.
"""

import PyImGui

MODULE_NAME = 'ImGui_Legacy Docking Test'
DOCK_HOST_TITLE = 'Dock Host'
TOOLS_TITLE = 'Dock Tools'
SCENE_TITLE = 'Dock Scene'
LOG_TITLE = 'Dock Log'

_layout_pending = True
_show_tools = True
_show_scene = True
_show_log = True
_dockable = True   # toggled from the Dock Host window; adds PyImGui.WindowFlags.Docking to the panes
_dockspace_id = 0
_last_host_size = (0.0, 0.0)

# ImGuiDir values from imgui.h.
DIR_LEFT = 0
DIR_RIGHT = 1
DIR_UP = 2
DIR_DOWN = 3


def _bool_label(value: bool) -> str:
    return 'yes' if value else 'no'


def _build_layout(dockspace_id: int, host_size: tuple[float, float]) -> None:
    if dockspace_id == 0 or host_size[0] <= 1.0 or host_size[1] <= 1.0:
        return

    PyImGui.dock_builder_remove_node(dockspace_id)
    PyImGui.dock_builder_add_node(dockspace_id, PyImGui.DockNodeFlags.NoFlag)
    PyImGui.dock_builder_set_node_size(dockspace_id, host_size)

    left_id, remainder_id = PyImGui.dock_builder_split_node(dockspace_id, DIR_LEFT, 0.28)
    center_id, bottom_id = PyImGui.dock_builder_split_node(remainder_id, DIR_DOWN, 0.30)

    PyImGui.dock_builder_dock_window(TOOLS_TITLE, left_id)
    PyImGui.dock_builder_dock_window(SCENE_TITLE, center_id)
    PyImGui.dock_builder_dock_window(LOG_TITLE, bottom_id)
    PyImGui.dock_builder_finish(dockspace_id)


def _draw_host() -> None:
    global _dockspace_id
    global _layout_pending
    global _last_host_size
    global _show_tools
    global _show_scene
    global _show_log
    global _dockable

    PyImGui.set_next_window_size((900.0, 650.0), PyImGui.ImGuiCond.FirstUseEver)
    if not PyImGui.begin(DOCK_HOST_TITLE, PyImGui.WindowFlags.NoCollapse | PyImGui.WindowFlags.MenuBar):
        PyImGui.end()
        return

    if PyImGui.begin_menu_bar():
        if PyImGui.begin_menu('Windows'):
            _show_tools = PyImGui.menu_item(TOOLS_TITLE, selected=_show_tools)
            _show_scene = PyImGui.menu_item(SCENE_TITLE, selected=_show_scene)
            _show_log = PyImGui.menu_item(LOG_TITLE, selected=_show_log)
            PyImGui.end_menu()
        PyImGui.end_menu_bar()

    PyImGui.text('This window owns the dockspace.')
    PyImGui.text('Drag tabs around to test manual docking and splitting.')
    PyImGui.separator()

    if PyImGui.button('Rebuild Example Layout'):
        _layout_pending = True
    PyImGui.same_line(0, -1)
    if PyImGui.button('Clear Saved Layout'):
        PyImGui.dock_builder_remove_node(_dockspace_id)
        _layout_pending = True

    PyImGui.same_line(0, -1)
    PyImGui.text(f'Docking enabled: {_bool_label(PyImGui.is_docking_enabled())}')

    # Toggle: drives ImGui_Legacy.begin(dockable=...) for the panes below.
    _dockable = PyImGui.checkbox('Panes dockable (adds WindowFlags.Docking)', _dockable)

    available_size = PyImGui.get_content_region_avail()
    _last_host_size = available_size
    _dockspace_id = PyImGui.get_id('DockingTestDockSpace')
    PyImGui.dock_space(_dockspace_id, available_size, PyImGui.DockNodeFlags.NoFlag)

    if _layout_pending:
        _build_layout(_dockspace_id, available_size)
        _layout_pending = False

    PyImGui.end()


def _draw_tools() -> None:
    global _show_tools

    if not _show_tools:
        return

    if not PyImGui.begin(TOOLS_TITLE, flags=(PyImGui.WindowFlags.Docking if _dockable else PyImGui.WindowFlags.NoFlag)):
        PyImGui.end()
        return

    PyImGui.text('Tools pane')
    PyImGui.separator()
    PyImGui.bullet_text('Use "Rebuild Example Layout" in Dock Host to reset the split layout.')
    PyImGui.bullet_text('Undock this tab by dragging it outside the dock host window.')
    PyImGui.bullet_text('Redock it by dragging over a highlighted docking target.')
    PyImGui.separator()
    PyImGui.text(f'is_window_docked = {_bool_label(PyImGui.is_window_docked())}')
    PyImGui.text(f'window_dock_id = 0x{PyImGui.get_window_dock_id():08X}')
    PyImGui.end()


def _draw_scene() -> None:
    global _show_scene

    if not _show_scene:
        return

    PyImGui.set_next_window_size((360.0, 260.0), PyImGui.ImGuiCond.FirstUseEver)
    if not PyImGui.begin(SCENE_TITLE, flags=(PyImGui.WindowFlags.Docking if _dockable else PyImGui.WindowFlags.NoFlag)):
        PyImGui.end()
        return

    PyImGui.text('Scene pane')
    PyImGui.separator()
    PyImGui.text('Pseudocode for a typical docking setup:')
    PyImGui.bullet_text('host_begin()')
    PyImGui.bullet_text('dock_id = get_id("MyDockSpace")')
    PyImGui.bullet_text('dock_space(dock_id, available_size)')
    PyImGui.bullet_text('if first_time: split node and dock named windows')
    PyImGui.bullet_text('begin("Tools") / begin("Scene") / begin("Log")')
    PyImGui.separator()
    PyImGui.text(f'is_window_docked = {_bool_label(PyImGui.is_window_docked())}')
    PyImGui.text(f'window_dock_id = 0x{PyImGui.get_window_dock_id():08X}')
    PyImGui.end()


def _draw_log() -> None:
    global _show_log

    if not _show_log:
        return

    if not PyImGui.begin(LOG_TITLE, flags=(PyImGui.WindowFlags.Docking if _dockable else PyImGui.WindowFlags.NoFlag)):
        PyImGui.end()
        return

    PyImGui.text('Log pane')
    PyImGui.separator()
    PyImGui.text(f'dockspace_id = 0x{_dockspace_id:08X}')
    PyImGui.text(f'host_size = ({_last_host_size[0]:.1f}, {_last_host_size[1]:.1f})')
    PyImGui.text(f'is_window_docked = {_bool_label(PyImGui.is_window_docked())}')
    PyImGui.text(f'window_dock_id = 0x{PyImGui.get_window_dock_id():08X}')
    PyImGui.end()


def main() -> None:
    _draw_host()
    _draw_tools()
    _draw_scene()
    _draw_log()
