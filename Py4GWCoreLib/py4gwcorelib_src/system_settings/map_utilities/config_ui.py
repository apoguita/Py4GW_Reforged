"""Map & Missions settings UI for the migrated utility overlays."""

from collections.abc import Sequence

import PyImGui

from Py4GWCoreLib import Overlay

from . import model
from .controller import MapUtilitiesController
from .controller import get_controller


_MUTED = (0.60, 0.60, 0.65, 1.0)


def _rgba(color: model.RGBA) -> tuple[float, float, float, float]:
    return tuple(channel / 255.0 for channel in color)  # type: ignore[return-value]


def _color(value: Sequence[float]) -> model.RGBA:
    return tuple(max(0, min(255, int(round(channel * 255)))) for channel in value)  # type: ignore[return-value]


def _draw_style(style: model.OverlayStyle, prefix: str) -> None:
    display = Overlay().GetDisplaySize()
    width = max(1, int(display.x))
    height = max(1, int(display.y))
    style.x = PyImGui.slider_int("X##%s_x" % prefix, style.x, 0, width)
    style.y = PyImGui.slider_int("Y##%s_y" % prefix, style.y, 0, height)
    style.font_size = PyImGui.slider_int("Font size##%s_font" % prefix, style.font_size, 1, 250)
    style.color = _color(PyImGui.color_edit4("Color##%s_color" % prefix, _rgba(style.color)))


def _draw_vanquish(controller: MapUtilitiesController) -> None:
    config = controller.config
    config.vanquish_enabled = PyImGui.checkbox(
        "Enable vanquish tracker##map_utilities_vanquish_enabled", config.vanquish_enabled
    )
    PyImGui.text_wrapped("Shows foes killed versus total foes in explorable hard-mode vanquish maps.")
    _draw_style(config.vanquish, "map_utilities_vanquish")
    controller.save()


def _draw_instance_timer(controller: MapUtilitiesController) -> None:
    config = controller.config
    config.instance_timer_enabled = PyImGui.checkbox(
        "Enable instance timer##map_utilities_instance_enabled", config.instance_timer_enabled
    )
    config.true_instance_timer = PyImGui.checkbox(
        "True instance timer##map_utilities_true_timer", config.true_instance_timer
    )
    PyImGui.text_wrapped(
        "The normal timer starts when the map becomes ready. The true timer includes map-load time."
    )
    _draw_style(config.instance_timer, "map_utilities_instance")
    controller.save()


def _draw_alcohol_effect(controller: MapUtilitiesController) -> None:
    config = controller.config
    config.disable_alcohol_effect = PyImGui.checkbox(
        "Disable alcohol visual effect##map_utilities_alcohol", config.disable_alcohol_effect
    )
    PyImGui.text_wrapped(
        "Clears the drunk visual effect periodically while preserving alcohol level and title progress."
    )
    PyImGui.text_colored("This feature toggle is account-local.", _MUTED)
    controller.save()


def add_sections(win, group) -> None:
    """Add each migrated map feature as its own Map & Missions section."""

    controller = get_controller()
    win.add_section(group, "Vanquish Tracker", lambda c=controller: _draw_vanquish(c))
    win.add_section(group, "Instance Timer", lambda c=controller: _draw_instance_timer(c))
    win.add_section(group, "Disable Alcohol Effect", lambda c=controller: _draw_alcohol_effect(c))
