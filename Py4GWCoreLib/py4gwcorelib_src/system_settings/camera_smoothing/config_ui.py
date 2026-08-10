"""Camera settings UI hosted by System Settings."""

import PyImGui

from .controller import CameraSmoothingController
from .controller import get_controller


_MUTED = (0.60, 0.60, 0.65, 1.0)


def _draw(controller: CameraSmoothingController) -> None:
    enabled = PyImGui.checkbox("Disable camera smoothing", controller.config.disable_smoothing)
    if enabled != controller.config.disable_smoothing:
        controller.set_disabled(enabled)
    PyImGui.text_wrapped(
        "Sets the camera position directly each frame so camera movement responds immediately."
    )
    PyImGui.text_colored("The setting is account-scoped and applies through a native callback.", _MUTED)


def add_sections(win, group) -> None:
    """Add the camera-smoothing settings section to the Camera category."""

    controller = get_controller()
    win.add_section(group, "Disable Camera Smoothing", lambda c=controller: _draw(c))
