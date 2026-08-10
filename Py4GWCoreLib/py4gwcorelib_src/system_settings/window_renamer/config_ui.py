"""Window Renamer settings hosted by the System Settings window."""

import PyImGui

from . import model
from .controller import WindowRenamerController
from .controller import get_controller


_MUTED = (0.60, 0.60, 0.65, 1.0)


def _draw(controller: WindowRenamerController) -> None:
    config = controller.config
    enabled = PyImGui.checkbox("Enable window renaming", config.enabled)
    if enabled != config.enabled:
        controller.set_option("enabled", enabled)

    PyImGui.text_wrapped(
        "Renames the Guild Wars client window from a profiled callback. Settings are account-scoped; "
        "the enable and display options are local to this account."
    )
    PyImGui.separator()

    current_mode = model.DISPLAY_MODES.index(config.display_mode)
    selected_mode = PyImGui.combo("Title identity", current_mode, list(model.DISPLAY_MODE_LABELS))
    if selected_mode != current_mode:
        controller.set_option("display_mode", model.DISPLAY_MODES[selected_mode])

    fallback = PyImGui.checkbox("Fallback to character name when unavailable", config.fallback_to_character)
    if fallback != config.fallback_to_character:
        controller.set_option("fallback_to_character", fallback)

    append_game_name = PyImGui.checkbox("Append ' - Guild Wars'", config.append_game_name)
    if append_game_name != config.append_game_name:
        controller.set_option("append_game_name", append_game_name)

    prefix = PyImGui.input_text("Title prefix", config.prefix)
    if prefix != config.prefix:
        controller.set_option("prefix", prefix)
    suffix = PyImGui.input_text("Title suffix", config.suffix)
    if suffix != config.suffix:
        controller.set_option("suffix", suffix)

    PyImGui.spacing()
    PyImGui.text_colored(
        "Obfuscated name uses the native display-name resolver. Configured aliases below are global "
        "and keyed by account email.",
        _MUTED,
    )

    PyImGui.separator()
    PyImGui.text("Global account aliases")
    PyImGui.text_wrapped(
        "These aliases are shared by every client. The email identifies the account, so changing an "
        "alias here changes the title available to all of its local profiles."
    )

    if PyImGui.button("Refresh account list##window_renamer_refresh_accounts"):
        controller.refresh_account_emails()

    current_email = controller.current_account_email()
    emails = controller.known_account_emails()
    if not emails:
        PyImGui.text_colored("No account email is available yet.", _MUTED)
        return

    for index, email in enumerate(emails):
        PyImGui.text(email)
        alias = controller.alias_for_email(email)
        updated_alias = PyImGui.input_text("Alias##window_renamer_alias_%d" % index, alias)
        if updated_alias != alias:
            controller.set_alias_for_email(email, updated_alias)
        if email == current_email:
            PyImGui.text_colored("Current account", _MUTED)


def add_sections(win, group) -> None:
    """Add the Window Renamer section to the System category."""

    controller = get_controller()
    win.add_section(group, "Window Renamer", lambda c=controller: _draw(c))
