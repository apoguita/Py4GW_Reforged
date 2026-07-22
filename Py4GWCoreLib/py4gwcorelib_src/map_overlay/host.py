"""Map Overlay host — the per-frame orchestrator and public entry point.

Owns the config and every layer, and drives one frame for the **active mode**: refresh the
projection, render terrain, then draw rings + agents + the snap overlay inside a single
input-less draw-list window, handle clicks, and (mission mode) render the floating strips.

``MapOverlay`` is the object the thin widget file drives: :meth:`draw`, :meth:`configure`,
:meth:`tooltip`.
"""

from typing import Optional

import PyImGui

from Py4GWCoreLib import ImGui
from Py4GWCoreLib import Map
from Py4GWCoreLib import Routines
from Py4GWCoreLib.enums import Range
from Py4GWCoreLib.py4gwcorelib_src.Color import Color

from . import persistence
from . import shapes
from .agents import AgentPass
from .interaction import Interaction
from .model import OverlayConfig
from .model import OverlayMode
from .projection import AxisAlignedProjection
from .projection import Projection
from .projection import RotatingProjection
from .terrain import Terrain

MODULE_NAME = "Map Overlay"


class MapOverlay:
    def __init__(self) -> None:
        self.cfg = OverlayConfig()
        persistence.load(self.cfg)

        self.mission_proj = AxisAlignedProjection()
        self.compass_proj = RotatingProjection(self.cfg.position)
        self.terrain = Terrain()
        self.interaction = Interaction(self.cfg)
        self.agent_pass = AgentPass(self.cfg)
        # Interaction reads the very list the agent pass fills — no per-marker callback.
        self.interaction.hit_targets = self.agent_pass.hits

        self._last_map_id = -1
        self._new_custom_name = "Custom Agent Name"   # config UI scratch

    def save(self) -> None:
        persistence.save(self.cfg)

    def on_mode_changed(self) -> None:
        self.terrain.invalidate()
        self.interaction.snap_clear()

    # ── active projection ────────────────────────────────────────────────────────────────
    def _projection(self) -> Projection:
        return self.mission_proj if self.cfg.mode is OverlayMode.MISSION else self.compass_proj

    # ── draw-list window ─────────────────────────────────────────────────────────────────
    @staticmethod
    def _begin_window(proj: Projection) -> bool:
        left, top, right, bottom = proj.content_rect()
        PyImGui.set_next_window_pos(left, top)
        PyImGui.set_next_window_size(max(1.0, right - left), max(1.0, bottom - top))
        flags = (
            PyImGui.WindowFlags.NoTitleBar | PyImGui.WindowFlags.NoScrollbar
            | PyImGui.WindowFlags.NoMove | PyImGui.WindowFlags.NoSavedSettings
            | PyImGui.WindowFlags.NoBackground | PyImGui.WindowFlags.NoInputs
        )
        PyImGui.push_style_var_vec2(ImGui.ImGuiStyleVar.WindowPadding, (0.0, 0.0))
        PyImGui.push_style_var_vec2(ImGui.ImGuiStyleVar.FramePadding, (0.0, 0.0))
        return PyImGui.begin("##map_overlay_drawlist", flags)

    @staticmethod
    def _end_window() -> None:
        PyImGui.end()
        PyImGui.pop_style_var(2)

    def _draw_rings(self, proj: Projection) -> None:
        """Configurable range rings (Touch…Compass) — drawn in both modes."""
        px, py = proj.player_screen()
        for ring in self.cfg.rings:
            if not ring.visible:
                continue
            r = proj.gwinch_to_pixels(ring.range)
            if r <= 0:
                continue
            seg = shapes.segments_for_radius(r)
            PyImGui.draw_list_add_circle_filled(px, py, r, shapes.pack(ring.fill_color), seg)
            PyImGui.draw_list_add_circle(px, py, r, shapes.pack(ring.outline_color), seg, ring.outline_thickness)

    def _draw_player_ranges(self, proj: AxisAlignedProjection) -> None:
        """Mission-map-exclusive aggro bubble + tailored compass-range indicator.

        Distinct from the configurable range rings: the compass range is a black hairline at the
        exact compass radius plus a soft band inset by ``2.85·zoom`` with thickness ``5.7·zoom``,
        so the band stays proportional as the mission map zooms.
        """
        pr = self.cfg.player_ranges
        px, py = proj.player_screen()
        color = shapes.pack(pr.color)
        zoom = proj.zoom + proj.mega_zoom

        if pr.show_aggro_bubble:
            radius = proj.gwinch_to_pixels(Range.Earshot.value)
            if radius > 0:
                seg = shapes.segments_for_radius(radius)
                PyImGui.draw_list_add_circle(px, py, radius - 2, color, seg, 4.0)
                PyImGui.draw_list_add_circle_filled(px, py, radius, color, seg)

        if pr.show_compass_range:
            radius = proj.gwinch_to_pixels(Range.Compass.value)
            if radius > 0:
                seg = shapes.segments_for_radius(radius)
                PyImGui.draw_list_add_circle(px, py, radius, shapes.pack(pr.compass_outline), seg, 1.0)
                PyImGui.draw_list_add_circle(px, py, radius - (2.85 * zoom), color, seg, 5.7 * zoom)

    # ── main frame ───────────────────────────────────────────────────────────────────────
    def draw(self) -> None:
        cfg = self.cfg
        if not Routines.Checks.Map.MapValid():
            return

        map_id = Map.GetMapID()
        if map_id != self._last_map_id:
            self._last_map_id = map_id
            self.interaction.reset_for_map_change()
            self.agent_pass.reset_for_map_change()

        proj = self._projection()
        if cfg.mode is OverlayMode.MISSION:
            self.mission_proj.mega_zoom = cfg.position.mega_zoom

        if not proj.refresh():
            return

        self.interaction.draw_snap_path_3d()

        if cfg.mode is OverlayMode.MISSION:
            self.terrain.draw_mission(self.mission_proj, cfg.terrain)
        else:
            self.terrain.draw_compass(self.compass_proj, cfg.terrain)

        if self._begin_window(proj):
            # Mission's tailored indicators sit underneath; the configurable rings draw on top
            # of them. They are separate features and coexist — neither replaces the other.
            if cfg.mode is OverlayMode.MISSION:
                self._draw_player_ranges(self.mission_proj)
            self._draw_rings(proj)
            self.agent_pass.draw(proj)
            self.interaction.draw_overlay(proj)
        self._end_window()

        self.interaction.update(proj)

        if cfg.mode is OverlayMode.MISSION:
            self._mission_strips(self.mission_proj)

    # ── mission floating strips ──────────────────────────────────────────────────────────
    def _mission_strips(self, proj: AxisAlignedProjection) -> None:
        left, top = proj.left, proj.top
        # Move toggle + Stop
        new_enabled, stop = _floating_move_toggle(left, top, self.cfg.snap.enabled, self.interaction.snap_active)
        if new_enabled != self.cfg.snap.enabled:
            self.cfg.snap.enabled = new_enabled
            self.save()
        if stop:
            self.interaction.snap_clear()

        _floating_map_id_strip(left, top, Map.GetMapID())
        _floating_coords_strip(left, top, self.interaction.last_click_x, self.interaction.last_click_y, proj.width)

        if proj.zoom >= 3.5:
            new_mega = _floating_slider("Mega Zoom", self.cfg.position.mega_zoom, left, proj.bottom - 27, 0.0, 15.0)
            if new_mega != self.cfg.position.mega_zoom:
                self.cfg.position.mega_zoom = new_mega
                self.save()
        else:
            self.cfg.position.mega_zoom = 0.0

    # ── UI hooks ─────────────────────────────────────────────────────────────────────────
    def configure(self) -> None:
        from . import config_ui
        config_ui.draw(self)

    def tooltip(self) -> None:
        PyImGui.begin_tooltip()
        title = Color(255, 200, 100, 255)
        ImGui.push_font("Regular", 20)
        PyImGui.text_colored("Map Overlay", title.to_tuple_normalized())
        ImGui.pop_font()
        PyImGui.spacing()
        PyImGui.separator()
        PyImGui.text("Enhanced agent + terrain overlay for the mission map or the compass.")
        PyImGui.text("Pick a mode in the config; the other is left untouched.")
        PyImGui.spacing()
        PyImGui.text_colored("Features:", title.to_tuple_normalized())
        PyImGui.bullet_text("Customizable agent markers, range rings, spirit auras")
        PyImGui.bullet_text("Terrain / pathing render (mission mega-zoom)")
        PyImGui.bullet_text("Click-to-target, alt-click move, NavMesh snap-move")
        PyImGui.bullet_text("Custom markers by model id")
        PyImGui.spacing()
        PyImGui.separator()
        PyImGui.spacing()
        PyImGui.text_colored("Credits:", title.to_tuple_normalized())
        PyImGui.bullet_text("Mission Map +: Apo, Searinox, Dharmantrix, aC")
        PyImGui.bullet_text("Compass +: jtmele1, frenkey, Apo, RyanNuttall")
        PyImGui.end_tooltip()


# ── floating strips (mission mode) ───────────────────────────────────────────────────────
def _floating_move_toggle(x: float, y: float, enabled: bool, show_stop: bool, margin: int = 8) -> tuple[bool, bool]:
    PyImGui.set_next_window_pos(x + margin + 2, y + margin + 20)
    flags = (
        PyImGui.WindowFlags.NoCollapse | PyImGui.WindowFlags.NoTitleBar | PyImGui.WindowFlags.NoScrollbar
        | PyImGui.WindowFlags.NoMove | PyImGui.WindowFlags.AlwaysAutoResize | PyImGui.WindowFlags.NoBackground
    )
    PyImGui.push_style_var_vec2(ImGui.ImGuiStyleVar.WindowPadding, (2.0, 2.0))
    PyImGui.push_style_var_vec2(ImGui.ImGuiStyleVar.FramePadding, (1.0, 1.0))
    PyImGui.push_style_var(ImGui.ImGuiStyleVar.WindowRounding, 0.0)
    PyImGui.push_style_color(PyImGui.ImGuiCol.WindowBg, (0.0, 0.0, 0.0, 0.0))
    result = enabled
    stop = False
    if PyImGui.begin("##mo_move_toggle", flags):
        cb = PyImGui.checkbox("Move", bool(enabled))
        result = bool(cb[1]) if isinstance(cb, tuple) and len(cb) == 2 else bool(cb)
        if PyImGui.is_item_hovered():
            ImGui.show_tooltip("Right-click moves to nearest NavMesh point. Shift+Right-click queues waypoints.")
        if show_stop:
            PyImGui.same_line(0, 6)
            if PyImGui.button("Stop", 44, 16):
                stop = True
    PyImGui.end()
    PyImGui.pop_style_color(1)
    PyImGui.pop_style_var(3)
    return result, stop


def _floating_map_id_strip(x: float, y: float, map_id: int, margin: int = 8) -> None:
    PyImGui.set_next_window_pos(x + margin + 2, y + margin + 76)
    flags = (
        PyImGui.WindowFlags.NoCollapse | PyImGui.WindowFlags.NoTitleBar | PyImGui.WindowFlags.NoScrollbar
        | PyImGui.WindowFlags.NoMove | PyImGui.WindowFlags.AlwaysAutoResize | PyImGui.WindowFlags.NoBackground
    )
    PyImGui.push_style_var_vec2(ImGui.ImGuiStyleVar.WindowPadding, (2.0, 2.0))
    PyImGui.push_style_var(ImGui.ImGuiStyleVar.WindowRounding, 0.0)
    PyImGui.push_style_color(PyImGui.ImGuiCol.WindowBg, (0.0, 0.0, 0.0, 0.0))
    if PyImGui.begin("##mo_map_id_strip", flags):
        PyImGui.text(f"Map ID: {int(map_id)}")
    PyImGui.end()
    PyImGui.pop_style_color(1)
    PyImGui.pop_style_var(2)


def _floating_coords_strip(x: float, y: float, last_x: float, last_y: float, width: float, margin: int = 8) -> None:
    PyImGui.set_next_window_pos(x + margin, y + 15 - margin)
    PyImGui.set_next_window_size(width - (margin * 2), 25)
    flags = (
        PyImGui.WindowFlags.NoCollapse | PyImGui.WindowFlags.NoTitleBar | PyImGui.WindowFlags.NoScrollbar
        | PyImGui.WindowFlags.NoMove | PyImGui.WindowFlags.AlwaysAutoResize | PyImGui.WindowFlags.NoBackground
    )
    PyImGui.push_style_var_vec2(ImGui.ImGuiStyleVar.WindowPadding, (4.0, 4.0))
    PyImGui.push_style_var_vec2(ImGui.ImGuiStyleVar.FramePadding, (2.0, 2.0))
    PyImGui.push_style_var(ImGui.ImGuiStyleVar.WindowRounding, 0.0)
    PyImGui.push_style_color(PyImGui.ImGuiCol.WindowBg, (0.0, 0.0, 0.0, 0.0))
    if PyImGui.begin("##mo_coords_strip", flags):
        if PyImGui.button("Copy"):
            PyImGui.set_clipboard_text(f"{int(last_x)}, {int(last_y)}")
        PyImGui.same_line(0, 6)
        PyImGui.text(f"Coords: ({int(last_x)}, {int(last_y)})")
    PyImGui.end()
    PyImGui.pop_style_color(1)
    PyImGui.pop_style_var(3)


def _floating_slider(caption: str, value: float, x: float, y: float, min_v: float, max_v: float) -> float:
    PyImGui.set_next_window_pos(x, y)
    PyImGui.set_next_window_size(0, 25)
    flags = (
        PyImGui.WindowFlags.NoCollapse | PyImGui.WindowFlags.NoTitleBar
        | PyImGui.WindowFlags.NoScrollbar | PyImGui.WindowFlags.AlwaysAutoResize
    )
    PyImGui.push_style_var_vec2(ImGui.ImGuiStyleVar.WindowPadding, (0.0, 0.0))
    PyImGui.push_style_var(ImGui.ImGuiStyleVar.WindowRounding, 0.0)
    result = value
    if PyImGui.begin(f"##mo_slider_{caption}", flags):
        result = PyImGui.slider_float(f"##mo_sliderval_{caption}", value, min_v, max_v)
        if PyImGui.is_item_hovered():
            ImGui.show_tooltip("Enhance the zoom level of the map.")
    PyImGui.end()
    PyImGui.pop_style_var(2)
    return result


# ── shared singleton ─────────────────────────────────────────────────────────────────────
# One MapOverlay per process, shared by the widget host (which renders it every frame) and any
# external caller that wants to drive it — e.g. the launch-bar "toggle mode" command. Both reach
# the SAME instance, so a toggle from the launchpad takes effect on the live overlay immediately
# (rather than mutating a throwaway copy). The instance lives in this cached library module, so it
# also survives a widget reload.
_active: "Optional[MapOverlay]" = None


def get_overlay() -> MapOverlay:
    """Return the process-wide :class:`MapOverlay`, creating it on first use."""
    global _active
    if _active is None:
        _active = MapOverlay()
    return _active


def toggle_mode() -> OverlayMode:
    """Flip the shared overlay between Mission Map and Compass, persist, and return the new mode.

    Mirrors the config window's Mode combo (set ``cfg.mode`` -> :meth:`MapOverlay.on_mode_changed`)
    and additionally calls :meth:`MapOverlay.save`, since — unlike the config UI, which saves once
    at the end of its frame — an external caller (e.g. a launch-bar command) has no such save pass.
    """
    ov = get_overlay()
    ov.cfg.mode = OverlayMode.COMPASS if ov.cfg.mode is OverlayMode.MISSION else OverlayMode.MISSION
    ov.on_mode_changed()
    ov.save()
    try:
        import PySystem

        PySystem.Console.Log(MODULE_NAME, "Mode -> %s" % ov.cfg.mode.value, PySystem.Console.MessageType.Info)
    except Exception:
        pass
    return ov.cfg.mode
