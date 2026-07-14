"""
System section — native ``PySystem`` module (system services, console, window, scripts).

Shape (mirrors player_demo.py, the canonical template):
  * ``build_system()`` calls the PySystem getters, CASTS each value via ``casts``, and returns a
    list of display Blocks. A ConsoleMessage handle is never repr'd — its fields are read
    explicitly (``casts.safe(getattr, msg, ...)``), matching the M4 handle-accessor rule.
  * ``draw_system_view()`` renders those blocks, exposes every mutating binding as an explicit
    ``ui.action_button`` (fired only on click, never on render), and offers the dump button.

Data path: ``import PySystem`` (native embedded module). Free functions live at module scope;
the Console / environment / window / script_control / widget_manager submodules are accessed as
``PySystem.Console.*`` etc.

R2 coverage — all 65 methods wired by hand (no reflection).
  Getters (Data tab): get_tick_count64, get_shared_memory_name, get_credits, get_license,
    is_shutdown_prompt_pending, in_character_select_screen, has_account_email, get_account_email,
    get_settings_directory, Console.get_projects_path, Console.get_gw_window_handle,
    Console.get_messages (no-arg #18), Console.get_messages(message_type) (#19),
    Console.filter_messages (#20), Console.get_output_to_file, Console.get_draw_console,
    Console.get_draw_compact_console, environment.get_gw_window_handle,
    environment.get_projects_path, window.get_window_rect, window.get_client_rect,
    window.is_window_active, window.is_window_minimized, window.is_window_in_background,
    window.get_z_order, script_control.status, widget_manager.status.
  Actions (Actions tab): change_working_directory, request_shutdown_prompt, cancel_shutdown_prompt,
    Console.Log, Console.write, Console.clear_messages, Console.set_output_to_file,
    Console.set_draw_console, Console.set_draw_compact_console, Console.toggle_console,
    Console.toggle_compact_console, window.resize_window, window.move_window_to,
    window.set_window_geometry, window.set_window_active, window.set_window_title,
    window.set_borderless, window.set_always_on_top, window.flash_window, window.request_attention,
    window.set_z_order, window.send_window_to_back, window.bring_window_to_front,
    window.transparent_click_through, window.adjust_window_opacity, window.hide_window,
    window.show_window, script_control.load, script_control.run, script_control.stop,
    script_control.pause, script_control.resume, script_control.defer_load_and_run,
    script_control.defer_stop_load_and_run, script_control.defer_stop_and_run,
    widget_manager.start, widget_manager.stop.
  Skipped: none. (MessageType is an enum, ConsoleMessage a return struct — rendered, not "called".)
"""

import PyImGui
import PySystem

from . import casts
from . import diagnostics
from . import ui

_SECTION = "System"

# Explicit MessageType member table (no reflection — named members read via getattr guard).
_MSG_TYPE_NAMES = ["Info", "Warning", "Error", "Debug", "Success", "Performance", "Notice", "Hook"]


def _msg_type(name: str):
    return casts.safe(getattr, PySystem.MessageType, name, default=None)


class _State:
    cwd_path: str = ""
    log_sender: str = "DEMO2"
    log_message: str = "hello from system_demo"
    log_type_idx: int = 0
    write_module: str = "DEMO2"
    write_message: str = "console.write test"
    write_level: str = "INFO"
    output_to_file: bool = False
    draw_console: bool = False
    draw_compact: bool = False
    win_w: int = 1024
    win_h: int = 768
    move_x: int = 0
    move_y: int = 0
    geom_x: int = 0
    geom_y: int = 0
    geom_w: int = 1024
    geom_h: int = 768
    win_title: str = "Guild Wars"
    borderless: bool = False
    always_on_top: bool = False
    click_through: bool = False
    flash_count: int = 3
    z_after: int = 0
    opacity: int = 255
    script_path: str = ""
    defer_delay: int = 1000


state = _State()


# ---------------------------------------------------------------------------
# build_* — call getters, cast, return blocks (shared by render AND dump)
# ---------------------------------------------------------------------------
def _runtime_block():
    rows = [
        ("Tick Count (64)", casts.safe(PySystem.get_tick_count64)),
        ("Shared Memory Name", casts.safe(PySystem.get_shared_memory_name)),
        ("In Character Select", casts.yesno(casts.safe(PySystem.in_character_select_screen))),
        ("Shutdown Prompt Pending", casts.yesno(casts.safe(PySystem.is_shutdown_prompt_pending))),
        ("Has Account Email", casts.yesno(casts.safe(PySystem.has_account_email))),
        ("Account Email", casts.safe(PySystem.get_account_email)),
        ("Settings Directory", casts.safe(PySystem.get_settings_directory)),
    ]
    return ui.kv_block("Runtime", rows)


def _license_block():
    body = casts.safe(PySystem.get_credits, default="<unavailable>")
    return ui.text_block("Credits", body)


def _legal_block():
    body = casts.safe(PySystem.get_license, default="<unavailable>")
    return ui.text_block("License", body)


def _console_state_block():
    all_msgs = casts.safe(PySystem.Console.get_messages, default=[]) or []
    err_type = _msg_type("Error")
    err_msgs = casts.safe(PySystem.Console.get_messages, err_type, default=[]) or [] if err_type is not None else []
    filtered = casts.safe(PySystem.Console.filter_messages, default=[]) or []
    rows = [
        ("Projects Path", casts.safe(PySystem.Console.get_projects_path)),
        ("GW Window Handle", casts.ptr(casts.safe(PySystem.Console.get_gw_window_handle))),
        ("Output To File", casts.yesno(casts.safe(PySystem.Console.get_output_to_file))),
        ("Draw Console", casts.yesno(casts.safe(PySystem.Console.get_draw_console))),
        ("Draw Compact Console", casts.yesno(casts.safe(PySystem.Console.get_draw_compact_console))),
        ("Messages (get_messages)", len(all_msgs)),
        ("Error Messages (by type)", len(err_msgs)),
        ("Filtered (filter_messages)", len(filtered)),
    ]
    return ui.kv_block("Console State", rows)


def _console_messages_block():
    msgs = casts.safe(PySystem.Console.get_messages, default=[]) or []
    headers = ["Time", "Module", "Level", "Type", "Message"]
    rows = []
    for msg in list(msgs)[-15:]:  # last 15, newest-tail
        rows.append(
            (
                casts.safe(getattr, msg, "display_timestamp", default="?"),
                casts.safe(getattr, msg, "module_name", default="?"),
                casts.safe(getattr, msg, "level", default="?"),
                str(casts.safe(getattr, msg, "message_type", default="?")),
                casts.safe(getattr, msg, "message", default=""),
            )
        )
    return ui.multi_block("Console Messages (last 15)", headers, rows)


def _environment_block():
    rows = [
        ("GW Window Handle", casts.ptr(casts.safe(PySystem.environment.get_gw_window_handle))),
        ("Projects Path", casts.safe(PySystem.environment.get_projects_path)),
    ]
    return ui.kv_block("Environment", rows)


def _window_block():
    rows = [
        ("Window Rect (l,t,r,b)", str(casts.safe(PySystem.window.get_window_rect))),
        ("Client Rect (l,t,r,b)", str(casts.safe(PySystem.window.get_client_rect))),
        ("Is Active", casts.yesno(casts.safe(PySystem.window.is_window_active))),
        ("Is Minimized", casts.yesno(casts.safe(PySystem.window.is_window_minimized))),
        ("Is In Background", casts.yesno(casts.safe(PySystem.window.is_window_in_background))),
        ("Z-Order", casts.safe(PySystem.window.get_z_order)),
    ]
    return ui.kv_block("Window", rows)


def _control_block():
    rows = [
        ("Script Status", casts.safe(PySystem.script_control.status)),
        ("Widget Manager Status", casts.safe(PySystem.widget_manager.status)),
    ]
    return ui.kv_block("Script / Widget Control", rows)


def build_system():
    return [
        _runtime_block(),
        _console_state_block(),
        _console_messages_block(),
        _environment_block(),
        _window_block(),
        _control_block(),
        _license_block(),
        _legal_block(),
    ]


# ---------------------------------------------------------------------------
# Actions — explicit trigger buttons, fired only on click
# ---------------------------------------------------------------------------
def _draw_actions():
    ui.section_header("System")
    state.cwd_path = PyImGui.input_text("Working Directory", state.cwd_path)
    ui.action_button("Change Working Directory", PySystem.change_working_directory, state.cwd_path, key="chdir")
    ui.action_button("Request Shutdown Prompt", PySystem.request_shutdown_prompt, key="shutdown_req")
    PyImGui.same_line(0, 8)
    ui.action_button("Cancel Shutdown Prompt", PySystem.cancel_shutdown_prompt, key="shutdown_cancel")

    PyImGui.spacing()
    ui.section_header("Console")
    state.log_sender = PyImGui.input_text("Log Sender", state.log_sender)
    state.log_message = PyImGui.input_text("Log Message", state.log_message)
    state.log_type_idx = PyImGui.combo("Log MessageType", state.log_type_idx, _MSG_TYPE_NAMES)
    ui.action_button(
        "Console.Log",
        PySystem.Console.Log,
        state.log_sender,
        state.log_message,
        _msg_type(_MSG_TYPE_NAMES[state.log_type_idx]),
        key="console_log",
    )
    state.write_module = PyImGui.input_text("Write Module", state.write_module)
    state.write_message = PyImGui.input_text("Write Message", state.write_message)
    state.write_level = PyImGui.input_text("Write Level", state.write_level)
    ui.action_button(
        "Console.write", PySystem.Console.write, state.write_module, state.write_message, state.write_level, key="console_write"
    )
    ui.action_button("Console.clear_messages", PySystem.Console.clear_messages, key="console_clear")
    state.output_to_file = PyImGui.checkbox("Output To File", state.output_to_file)
    ui.action_button("set_output_to_file", PySystem.Console.set_output_to_file, state.output_to_file, key="out_file")
    state.draw_console = PyImGui.checkbox("Draw Console", state.draw_console)
    ui.action_button("set_draw_console", PySystem.Console.set_draw_console, state.draw_console, key="draw_console")
    state.draw_compact = PyImGui.checkbox("Draw Compact Console", state.draw_compact)
    ui.action_button(
        "set_draw_compact_console", PySystem.Console.set_draw_compact_console, state.draw_compact, key="draw_compact"
    )
    ui.action_button("toggle_console", PySystem.Console.toggle_console, key="toggle_console")
    PyImGui.same_line(0, 8)
    ui.action_button("toggle_compact_console", PySystem.Console.toggle_compact_console, key="toggle_compact")

    PyImGui.spacing()
    ui.section_header("Window — Geometry")
    state.win_w = PyImGui.input_int("Resize Width", state.win_w)
    state.win_h = PyImGui.input_int("Resize Height", state.win_h)
    ui.action_button("resize_window", PySystem.window.resize_window, state.win_w, state.win_h, key="resize")
    state.move_x = PyImGui.input_int("Move X", state.move_x)
    state.move_y = PyImGui.input_int("Move Y", state.move_y)
    ui.action_button("move_window_to", PySystem.window.move_window_to, state.move_x, state.move_y, key="move")
    state.geom_x = PyImGui.input_int("Geom X", state.geom_x)
    state.geom_y = PyImGui.input_int("Geom Y", state.geom_y)
    state.geom_w = PyImGui.input_int("Geom Width", state.geom_w)
    state.geom_h = PyImGui.input_int("Geom Height", state.geom_h)
    ui.action_button(
        "set_window_geometry",
        PySystem.window.set_window_geometry,
        state.geom_x,
        state.geom_y,
        state.geom_w,
        state.geom_h,
        key="geom",
    )

    PyImGui.spacing()
    ui.section_header("Window — State")
    ui.action_button("set_window_active", PySystem.window.set_window_active, key="win_active")
    state.win_title = PyImGui.input_text("Window Title", state.win_title)
    ui.action_button("set_window_title", PySystem.window.set_window_title, state.win_title, key="win_title")
    state.borderless = PyImGui.checkbox("Borderless", state.borderless)
    ui.action_button("set_borderless", PySystem.window.set_borderless, state.borderless, key="borderless")
    state.always_on_top = PyImGui.checkbox("Always On Top", state.always_on_top)
    ui.action_button("set_always_on_top", PySystem.window.set_always_on_top, state.always_on_top, key="on_top")
    state.click_through = PyImGui.checkbox("Click Through", state.click_through)
    ui.action_button(
        "transparent_click_through", PySystem.window.transparent_click_through, state.click_through, key="click_thru"
    )
    state.opacity = PyImGui.input_int("Opacity (0-255)", state.opacity)
    ui.action_button("adjust_window_opacity", PySystem.window.adjust_window_opacity, state.opacity, key="opacity")
    state.flash_count = PyImGui.input_int("Flash Repeat", state.flash_count)
    ui.action_button("flash_window", PySystem.window.flash_window, state.flash_count, key="flash")
    PyImGui.same_line(0, 8)
    ui.action_button("request_attention", PySystem.window.request_attention, key="attention")
    state.z_after = PyImGui.input_int("Z-Order Insert After", state.z_after)
    ui.action_button("set_z_order", PySystem.window.set_z_order, state.z_after, key="z_order")
    ui.action_button("send_window_to_back", PySystem.window.send_window_to_back, key="to_back")
    PyImGui.same_line(0, 8)
    ui.action_button("bring_window_to_front", PySystem.window.bring_window_to_front, key="to_front")
    ui.action_button("hide_window", PySystem.window.hide_window, key="hide")
    PyImGui.same_line(0, 8)
    ui.action_button("show_window", PySystem.window.show_window, key="show")

    PyImGui.spacing()
    ui.section_header("Script Control")
    state.script_path = PyImGui.input_text("Script Path", state.script_path)
    ui.action_button("script.load", PySystem.script_control.load, state.script_path, key="script_load")
    PyImGui.same_line(0, 8)
    ui.action_button("script.run", PySystem.script_control.run, key="script_run")
    PyImGui.same_line(0, 8)
    ui.action_button("script.stop", PySystem.script_control.stop, key="script_stop")
    ui.action_button("script.pause", PySystem.script_control.pause, key="script_pause")
    PyImGui.same_line(0, 8)
    ui.action_button("script.resume", PySystem.script_control.resume, key="script_resume")
    state.defer_delay = PyImGui.input_int("Defer Delay (ms)", state.defer_delay)
    ui.action_button(
        "defer_load_and_run", PySystem.script_control.defer_load_and_run, state.script_path, state.defer_delay, key="defer_lr"
    )
    ui.action_button(
        "defer_stop_load_and_run",
        PySystem.script_control.defer_stop_load_and_run,
        state.script_path,
        state.defer_delay,
        key="defer_slr",
    )
    ui.action_button(
        "defer_stop_and_run", PySystem.script_control.defer_stop_and_run, state.defer_delay, key="defer_sr"
    )

    PyImGui.spacing()
    ui.section_header("Widget Manager")
    ui.action_button("widget_manager.start", PySystem.widget_manager.start, key="wm_start")
    PyImGui.same_line(0, 8)
    ui.action_button("widget_manager.stop", PySystem.widget_manager.stop, key="wm_stop")


# ---------------------------------------------------------------------------
# draw_*_view — uniform section entry point
# ---------------------------------------------------------------------------
def draw_system_view() -> None:
    blocks = build_system()
    diagnostics.dump_button(_SECTION, blocks)
    PyImGui.separator()
    if PyImGui.begin_tab_bar("SystemTabs"):
        if PyImGui.begin_tab_item("Data"):
            ui.draw_blocks(_SECTION, blocks)
            PyImGui.end_tab_item()
        if PyImGui.begin_tab_item("Actions"):
            _draw_actions()
            PyImGui.end_tab_item()
        PyImGui.end_tab_bar()
