"""System Settings UI — builds the options window from the catalog.

Renders through the shared :class:`ImGui.SidebarWindow` helper (the same window the Hello World
demo uses): one collapsible **group per Category**, one **section per Listener**, and each
section's content is that listener's enable checkbox + its sub-options. All state lives in the
controller, so these draw callables just read/write it.
"""

import PyImGui

from Py4GWCoreLib import ImGui

from . import model

_INFRA_COLOR = (0.95, 0.75, 0.35, 1.0)
_MUTED_COLOR = (0.60, 0.60, 0.65, 1.0)
ERR_COLOR = (0.90, 0.30, 0.30, 1.0)


def _log(msg: str) -> None:
    try:
        import PySystem

        PySystem.Console.Log("System Settings", msg, PySystem.Console.MessageType.Warning)
    except Exception:
        pass


def _glyph(icon_name: str) -> str:
    """Resolve a Font Awesome constant NAME to its glyph char (empty string if unavailable)."""
    if not icon_name:
        return ""
    try:
        from Py4GWCoreLib.ImGui_src.IconsFontAwesome5 import IconsFontAwesome5

        glyph = getattr(IconsFontAwesome5, icon_name, "")
        return glyph if isinstance(glyph, str) else ""
    except Exception:
        return ""


def _draw_option(controller, cat: "model.Category", lsn: "model.Listener", opt) -> None:
    value = controller.option_value(lsn, opt)
    tag = "##%s_%s" % (lsn.name, opt.key)
    if isinstance(opt, model.IntOption):
        new_val = PyImGui.slider_int(opt.label + tag, int(value), opt.min, opt.max)
        if new_val != int(value):
            controller.set_option(cat.key, lsn, opt, int(new_val))
    else:
        new_val = PyImGui.checkbox(opt.label + tag, bool(value))
        if new_val != bool(value):
            controller.set_option(cat.key, lsn, opt, bool(new_val))


def _draw_listener(controller, cat: "model.Category", lsn: "model.Listener") -> None:
    on = controller.is_enabled(lsn)
    new_on = PyImGui.checkbox("Enabled##en_%s" % lsn.name, on)
    if new_on != on:
        controller.set_listener_enabled(cat.key, lsn, new_on)

    if lsn.help:
        PyImGui.spacing()
        PyImGui.text_wrapped(lsn.help)
    if lsn.infra:
        PyImGui.text_colored("Data feed — other widgets may depend on this.", _INFRA_COLOR)

    if lsn.options:
        PyImGui.spacing()
        PyImGui.separator()
        PyImGui.text_colored("Options", _MUTED_COLOR)
        if not new_on:
            PyImGui.text_colored("(enable the listener to use these)", _MUTED_COLOR)
        for opt in lsn.options:
            _draw_option(controller, cat, lsn, opt)


def _draw_chat_commands_monitor() -> None:
    """Read-only view of the ChatCommands registry: usable commands, their aliases, the callee
    they dispatch to, and how many times each has fired."""
    try:
        from Py4GWCoreLib.ChatCommands import ChatCommands
    except Exception as exc:
        PyImGui.text_colored("ChatCommands unavailable: %s" % exc, ERR_COLOR)
        return

    if not ChatCommands.native_available():
        PyImGui.text_colored("PyChatCommands not available (offline or DLL not rebuilt).", _MUTED_COLOR)

    cmds = ChatCommands.commands()
    PyImGui.text_colored("Registered commands (%d)" % len(cmds), _MUTED_COLOR)
    PyImGui.text_wrapped("Type a command in chat, e.g. '/travel gtob' or '/map toggle'. Unknown "
                         "commands pass through to the game.")
    PyImGui.separator()
    if not cmds:
        PyImGui.text_colored("Nothing registered yet (enable the widgets that provide commands).", _MUTED_COLOR)
        return

    if PyImGui.begin_table("##chat_cmds", 4, PyImGui.TableFlags.RowBg | PyImGui.TableFlags.Borders, 0.0, 0.0):
        PyImGui.table_setup_column("Command", PyImGui.TableColumnFlags.WidthFixed, 120.0)
        PyImGui.table_setup_column("Aliases", PyImGui.TableColumnFlags.WidthFixed, 90.0)
        PyImGui.table_setup_column("Callee", PyImGui.TableColumnFlags.WidthStretch, 0.0)
        PyImGui.table_setup_column("Uses", PyImGui.TableColumnFlags.WidthFixed, 45.0)
        PyImGui.table_headers_row()
        for cmd in cmds:
            PyImGui.table_next_row()
            PyImGui.table_next_column()
            PyImGui.text("/%s" % cmd.name)
            if cmd.help:
                ImGui.show_tooltip(cmd.help)
            PyImGui.table_next_column()
            PyImGui.text(", ".join("/%s" % a for a in cmd.aliases) if cmd.aliases else "-")
            PyImGui.table_next_column()
            PyImGui.text_colored(cmd.callee, _MUTED_COLOR)
            if cmd.last_args:
                ImGui.show_tooltip("last args: %r" % (cmd.last_args,))
            PyImGui.table_next_column()
            PyImGui.text(str(cmd.count))
        PyImGui.end_table()


def build_window(controller) -> "ImGui.SidebarWindow":
    """Construct the settings :class:`SidebarWindow` from the catalog (pure construction)."""
    win = ImGui.SidebarWindow(
        "System Settings",
        sidebar_width=240.0,
        content_width=520.0,
        height=560.0,
        collapsible_groups=True,
        show_search=True,
        on_close=controller.close,   # the window's X hides it (same as toggling the cog off)
    )
    for cat in model.CATALOG:
        group = win.add_group(cat.title, icon=_glyph(cat.icon))
        if cat.key == "agents":
            # Custom category rendered by the name_obfuscation feature. Lazy import keeps this module
            # (and the launch_bar toggle path that imports the controller) free of that package until
            # the window is actually built. Never swallow a build failure silently — an empty section
            # with no error is undebuggable; surface it (and add a visible placeholder section).
            try:
                from Py4GWCoreLib.py4gwcorelib_src.name_obfuscation import config_ui as no_ui

                no_ui.add_sections(win, group)
            except Exception as exc:
                import traceback

                _log("Agents / Name Obfuscation section failed to build: %r" % exc)
                _log(traceback.format_exc())
                _err = str(exc)
                win.add_section(group, "Name Obfuscation",
                                (lambda e=_err: PyImGui.text_colored("Failed to build: %s" % e, ERR_COLOR)))
            try:
                from Py4GWCoreLib.py4gwcorelib_src.agent_recolor import config_ui as ar_ui

                ar_ui.add_sections(win, group)
            except Exception as exc:
                import traceback

                _log("Agents / Agent Recolor section failed to build: %r" % exc)
                _log(traceback.format_exc())
                _err = str(exc)
                win.add_section(group, "Agent Recolor",
                                (lambda e=_err: PyImGui.text_colored("Failed to build: %s" % e, ERR_COLOR)))
            continue
        if cat.key == "chat_commands":
            win.add_section(group, "Registered Commands", _draw_chat_commands_monitor)
            continue
        for lsn in cat.listeners:
            # Bind each section to its own listener via default args (avoid late-binding capture).
            win.add_section(
                group,
                lsn.label,
                (lambda c=controller, ca=cat, ls=lsn: _draw_listener(c, ca, ls)),
            )
    return win
