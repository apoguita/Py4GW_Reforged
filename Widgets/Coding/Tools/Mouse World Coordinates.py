import json

import PyImGui
import PySystem

from Py4GWCoreLib.Agent import Agent
from Py4GWCoreLib.Map import Map
from Py4GWCoreLib.Overlay import Overlay
from Py4GWCoreLib.Player import Player

MODULE_NAME = "Mouse World Coordinates"

_capturing: bool = False
_first_point: tuple[float, float, float] | None = None
_idx: int = 0
_to_map: int = 0
_from_map: int = 0
_outpost_idx: int = 0
_draw_preview: bool = False
_pairs: list[tuple[int, int, tuple[float, float, float], tuple[float, float, float]]] = []
_arrivals: list[tuple[int, float, float, float]] = []
_outpost_arrivals: list[tuple[int, int, float, float, float]] = []
_visited_maps: list[tuple[int, str]] = []


def main() -> None:
    global _capturing, _first_point, _idx, _to_map, _from_map, _draw_preview

    map_ready = Map.IsMapReady()
    map_id = Map.GetMapID() if map_ready else 0
    map_name = Map.GetMapName(map_id) if map_ready else "Unknown"
    if map_ready and all(visited_id != map_id for visited_id, _ in _visited_maps):
        _visited_maps.append((map_id, map_name))
    mouse_position = Overlay().GetMouseWorldPos() if _capturing and map_ready else (0.0, 0.0, 0.0)
    if not map_ready:
        _capturing = False
        _first_point = None

    visible = PyImGui.begin(MODULE_NAME)
    try:
        if not visible:
            return
        PyImGui.text(f"Current map: {map_id} - {map_name}")
        if PyImGui.begin_tab_bar("portal_arrivals_tabs"):
            if PyImGui.begin_tab_item("Portal"):
                _draw_portal(map_ready, map_id, mouse_position)
                PyImGui.end_tab_item()
            if PyImGui.begin_tab_item("Arrivals"):
                _draw_arrivals(map_ready)
                PyImGui.end_tab_item()
            if PyImGui.begin_tab_item("Outpost Arrivals"):
                _draw_outpost_arrivals(map_ready)
                PyImGui.end_tab_item()
            PyImGui.end_tab_bar()

        if map_ready and _draw_preview:
            overlay = Overlay()
            overlay.RefreshDrawList()
            overlay.BeginDraw()
            try:
                if _capturing:
                    mouse_x, mouse_y = overlay.GetMouseCoords()
                    overlay.DrawPoly(mouse_x, mouse_y, 12, color=0xFF00FFFF, thickness=2.0)
                    if _first_point is not None:
                        overlay.DrawLine3D(*_first_point, *mouse_position, color=0xFF00FFFF, thickness=2.0)
                for _, _, point_from, point_to in _pairs:
                    overlay.DrawLine3D(*point_from, *point_to, color=0xFF00FF00, thickness=2.0)
            finally:
                overlay.EndDraw()
    finally:
        PyImGui.end()


def _draw_portal(map_ready: bool, map_id: int, mouse_position: tuple[float, float, float]) -> None:
    global _capturing, _first_point, _idx, _to_map, _draw_preview

    if not map_ready:
        PyImGui.text("Enter a map to capture coordinates.")
        return

    if (
        _capturing
        and PyImGui.is_mouse_clicked(0)
        and not PyImGui.get_io().want_capture_mouse
        and not PyImGui.is_window_hovered(PyImGui.HoveredFlags.AnyWindow)
    ):
        point = Overlay().GetMouseWorldPos()
        point_number = 1 if _first_point is None else 2
        PySystem.Console.Log(
            MODULE_NAME,
            f"Pair {len(_pairs) + 1}, point {point_number}: {point}",
            PySystem.Console.MessageType.Info,
        )
        if _first_point is None:
            _first_point = point
        else:
            _pairs.append((_idx, _to_map, _first_point, point))
            _first_point = None
            _capturing = False

    _idx = PyImGui.input_int("Index", _idx)
    _to_map = _draw_map_selector("To map", _to_map or map_id)
    _draw_preview = PyImGui.checkbox("Draw capture line", _draw_preview)
    if _capturing:
        PyImGui.text(f"Mouse: ({mouse_position[0]:.1f}, {mouse_position[1]:.1f}, {mouse_position[2]:.1f})")
        PyImGui.text(f"Left-click point {1 if _first_point is None else 2} in the world.")
        if _first_point is not None:
            PyImGui.text(f"Point 1: {_first_point}")
        if PyImGui.button("Cancel capture"):
            _capturing = False
            _first_point = None
    elif PyImGui.button("Start capture"):
        _first_point = None
        _capturing = True

    PyImGui.separator()
    PyImGui.text(f"Recorded pairs: {len(_pairs)}")
    if PyImGui.button("Clear data"):
        _pairs.clear()
        _first_point = None
        _capturing = False

    PyImGui.begin_child("coordinate_list", (0, 240), border=1)
    try:
        for row, (idx, to_map, point_from, point_to) in enumerate(_pairs):
            PyImGui.separator()
            PyImGui.text(f"{row}. Index {idx}, to map {to_map}")
            PyImGui.text(f"From: ({point_from[0]:.1f}, {point_from[1]:.1f})")
            PyImGui.text(f"To: ({point_to[0]:.1f}, {point_to[1]:.1f})")
            if PyImGui.button(f"Copy JSON##pair_{row}"):
                entry = {
                    "idx": idx,
                    "to_map": to_map,
                    "from_x": point_from[0],
                    "from_y": point_from[1],
                    "to_x": point_to[0],
                    "to_y": point_to[1],
                }
                PyImGui.set_clipboard_text(json.dumps(entry, indent=2))
    finally:
        PyImGui.end_child()


def _draw_arrivals(map_ready: bool) -> None:
    global _from_map

    _from_map = _draw_map_selector("From", _from_map)
    if not map_ready:
        PyImGui.text("Enter a map before recording an arrival.")
        return

    if PyImGui.button("Record arrival"):
        agent_id = Player.GetAgentID()
        x, y = Agent.GetXY(agent_id)
        angle = Agent.GetRotationAngle(agent_id)
        _arrivals.append((_from_map, x, y, angle))
        PySystem.Console.Log(
            MODULE_NAME,
            f"Recorded arrival from { _from_map }: x={x}, y={y}, angle={angle}",
            PySystem.Console.MessageType.Info,
        )

    PyImGui.separator()
    PyImGui.text(f"Recorded arrivals: {len(_arrivals)}")
    if PyImGui.button("Clear entries"):
        _arrivals.clear()
    PyImGui.begin_child("arrival_list", (0, 240), border=1)
    try:
        for row, (from_map, x, y, angle) in enumerate(_arrivals):
            PyImGui.separator()
            PyImGui.text(f"{row}. From {from_map}: ({x:.2f}, {y:.2f}), angle {angle:.2f}")
            if PyImGui.button(f"Copy JSON##arrival_{row}"):
                entry = {"from": from_map, "x": x, "y": y, "angle": angle}
                PyImGui.set_clipboard_text(json.dumps(entry, indent=2))
    finally:
        PyImGui.end_child()


def _draw_outpost_arrivals(map_ready: bool) -> None:
    global _outpost_idx

    _outpost_idx = PyImGui.input_int("Index", _outpost_idx)
    if not map_ready:
        PyImGui.text("Enter a map before recording an outpost arrival.")
        return

    if PyImGui.button("Record outpost arrival"):
        agent_id = Player.GetAgentID()
        x, y = Agent.GetXY(agent_id)
        angle = Agent.GetRotationAngle(agent_id)
        _outpost_arrivals.append((_outpost_idx, 0, x, y, angle))
        PySystem.Console.Log(
            MODULE_NAME,
            f"Recorded outpost arrival: idx={_outpost_idx}, x={x}, y={y}, angle={angle}",
            PySystem.Console.MessageType.Info,
        )

    PyImGui.separator()
    PyImGui.text(f"Recorded outpost arrivals: {len(_outpost_arrivals)}")
    if PyImGui.button("Clear outpost entries"):
        _outpost_arrivals.clear()
    PyImGui.begin_child("outpost_arrival_list", (0, 240), border=1)
    try:
        for row, (idx, plane, x, y, angle) in enumerate(_outpost_arrivals):
            PyImGui.separator()
            PyImGui.text(f"{row}. Index {idx}, plane {plane}: ({x:.2f}, {y:.2f}), angle {angle:.2f}")
            if PyImGui.button(f"Copy JSON##outpost_arrival_{row}"):
                entry = {"idx": idx, "plane": plane, "x": x, "y": y, "angle": angle}
                PyImGui.set_clipboard_text(json.dumps(entry, indent=2))
    finally:
        PyImGui.end_child()


def _draw_map_selector(label: str, map_id: int) -> int:
    map_id = PyImGui.input_int(label, map_id)
    labels = ["Select visited map"] + [f"{visited_id} - {name}" for visited_id, name in _visited_maps]
    selected_index = next(
        (index + 1 for index, (visited_id, _) in enumerate(_visited_maps) if visited_id == map_id),
        0,
    )
    selected = PyImGui.combo(f"{label} visited", selected_index, labels)
    if selected > 0 and selected < len(labels):
        return _visited_maps[selected - 1][0]
    return map_id
