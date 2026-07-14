"""
Camera section — live camera state (real values, not a reflection grid), plus control actions.

Shape (mirrors player_demo.py, the canonical template):
  * ``build_camera()`` calls the base ``Camera`` wrapper getters, CASTS each value via ``casts``
    (floats -> f2/f3, vectors -> casts.vec, the look-at handle -> id + resolved Agent name), and
    returns a list of display Blocks. No struct/handle ever reaches a renderer un-dereferenced.
  * ``draw_camera_view()`` builds once, offers the per-section Dump-to-file button, then a tab bar:
    Data (renders the blocks) + Actions (explicit trigger buttons, never auto-fired).

Data path: ``Camera.*`` (thin passthrough over ``PyCamera.PyCamera()`` fields — R3 §14). The
GlobalCache CameraCache mirrors the same returns with no richer casting (R3 §15), so we call the
base wrapper. The one trap: ``GetLookAtAgentID`` returns a bare agent handle -> resolve the name
via ``Agent.GetNameByID`` (R3 §14, §17).

R2 coverage — PyCamera getters wired (State tab, all live, no reflection):
  GetLookAtAgentID (+ Agent name), GetCameraUnlock, GetYaw, GetCurrentYaw, GetPitch,
  GetYawRightClick, GetYawRightClick2, GetPitchRightClick, GetMaxDistance, GetDistance2,
  GetMaxDistance2, GetCameraZoom, GetFieldOfView, GetFielsOfView2, GetYawToGo, GetPitchToGo,
  GetDistanceToGo, GetPosition, GetCameraPositionToGo, GetCameraPositionInverted,
  GetCameraPositionInvertedToGo, GetLookAtTarget, GetAtTargetToGo, GetAccelerationConstant,
  GetTimeSinceLastKeyboardRotation, GetTimeSinceLastMouseRotation, GetTimeSinceLastMouseMove,
  GetTimeSinceLastAgentSelection, GetTimeInTheMap, GetTimeInTheDistrict.
Actions wired: SetYaw, SetPitch, SetMaxDistance, SetFieldOfView, SetCameraUnlock, SetCameraPosition,
  SetLookAtTarget, ForwardMovement, VerticalMovement, SideMovement, RotateMovement, ComputeCameraPos,
  UpdateCameraPos, SetFog.
Skipped R2 methods: camera_instance (infra — returns the raw handle, never displayed);
  IsPointInFOV (predicate needing a target point, and flagged expensive — belongs to a probe, not
  live state).
"""

import PyImGui

from Py4GWCoreLib import Agent
from Py4GWCoreLib.Camera import Camera

from . import casts
from . import diagnostics
from . import ui

_SECTION = "Camera"


class _State:
    yaw: float = 0.0
    pitch: float = 0.0
    max_distance: float = 0.0
    fov: float = 0.0
    unlock: bool = False
    pos_x: float = 0.0
    pos_y: float = 0.0
    pos_z: float = 0.0
    look_x: float = 0.0
    look_y: float = 0.0
    look_z: float = 0.0
    move_amount: float = 100.0
    true_forward: bool = False
    rotate_angle: float = 0.0
    fog: bool = False


state = _State()


# ---------------------------------------------------------------------------
# build_* — call getters, cast, return blocks (shared by render AND dump)
# ---------------------------------------------------------------------------
def _lookat_block():
    agent_id = casts.safe(Camera.GetLookAtAgentID, default=0)
    # M4 trap: GetLookAtAgentID is a bare agent handle — resolve the name explicitly.
    name = casts.safe(Agent.GetNameByID, agent_id, default="?") if agent_id else "-"
    rows = [
        ("Look-At Agent ID", agent_id),
        ("Look-At Agent Name", name),
        ("Camera Unlocked", casts.yesno(casts.safe(Camera.GetCameraUnlock))),
    ]
    return ui.kv_block("Look-At / Lock", rows)


def _orientation_block():
    rows = [
        ("Yaw", casts.f3(casts.safe(Camera.GetYaw))),
        ("Current Yaw (computed)", casts.f3(casts.safe(Camera.GetCurrentYaw))),
        ("Pitch", casts.f3(casts.safe(Camera.GetPitch))),
        ("Yaw Right-Click", casts.f3(casts.safe(Camera.GetYawRightClick))),
        ("Yaw Right-Click 2", casts.f3(casts.safe(Camera.GetYawRightClick2))),
        ("Pitch Right-Click", casts.f3(casts.safe(Camera.GetPitchRightClick))),
    ]
    return ui.kv_block("Orientation", rows)


def _distance_block():
    rows = [
        ("Max Distance", casts.f2(casts.safe(Camera.GetMaxDistance))),
        ("Distance (squared)", casts.f2(casts.safe(Camera.GetDistance2))),
        ("Max Distance (squared)", casts.f2(casts.safe(Camera.GetMaxDistance2))),
        ("Camera Zoom", casts.f2(casts.safe(Camera.GetCameraZoom))),
    ]
    return ui.kv_block("Distance / Zoom", rows)


def _fov_block():
    rows = [
        ("Field Of View", casts.f3(casts.safe(Camera.GetFieldOfView))),
        ("Field Of View 2", casts.f3(casts.safe(Camera.GetFielsOfView2))),
    ]
    return ui.kv_block("Field Of View", rows)


def _togo_block():
    rows = [
        ("Yaw To Go", casts.f3(casts.safe(Camera.GetYawToGo))),
        ("Pitch To Go", casts.f3(casts.safe(Camera.GetPitchToGo))),
        ("Distance To Go", casts.f2(casts.safe(Camera.GetDistanceToGo))),
    ]
    return ui.kv_block("Target (To Go)", rows)


def _vectors_block():
    def _v(fn):
        comps = casts.safe(fn, default=(0.0, 0.0, 0.0)) or (0.0, 0.0, 0.0)
        return casts.vec(*comps)

    rows = [
        ("Position", _v(Camera.GetPosition)),
        ("Position To Go", _v(Camera.GetCameraPositionToGo)),
        ("Position Inverted", _v(Camera.GetCameraPositionInverted)),
        ("Position Inverted To Go", _v(Camera.GetCameraPositionInvertedToGo)),
        ("Look-At Target", _v(Camera.GetLookAtTarget)),
        ("Look-At Target To Go", _v(Camera.GetAtTargetToGo)),
    ]
    return ui.kv_block("Vectors (x, y, z)", rows)


def _timers_block():
    rows = [
        ("Acceleration Constant", casts.f3(casts.safe(Camera.GetAccelerationConstant))),
        ("Time Since Last Keyboard Rotation", casts.f2(casts.safe(Camera.GetTimeSinceLastKeyboardRotation))),
        ("Time Since Last Mouse Rotation", casts.f2(casts.safe(Camera.GetTimeSinceLastMouseRotation))),
        ("Time Since Last Mouse Move", casts.f2(casts.safe(Camera.GetTimeSinceLastMouseMove))),
        ("Time Since Last Agent Selection", casts.f2(casts.safe(Camera.GetTimeSinceLastAgentSelection))),
        ("Time In The Map", casts.f2(casts.safe(Camera.GetTimeInTheMap))),
        ("Time In The District", casts.f2(casts.safe(Camera.GetTimeInTheDistrict))),
    ]
    return ui.kv_block("Timers", rows)


def build_camera():
    return [
        _lookat_block(),
        _orientation_block(),
        _distance_block(),
        _fov_block(),
        _togo_block(),
        _vectors_block(),
        _timers_block(),
    ]


# ---------------------------------------------------------------------------
# Actions — explicit trigger buttons, fired only on click
# ---------------------------------------------------------------------------
def _draw_actions():
    ui.section_header("Orientation / FOV / Distance")
    state.yaw = PyImGui.input_float("Yaw", state.yaw)
    ui.action_button("Set Yaw", Camera.SetYaw, state.yaw, key="set_yaw")
    state.pitch = PyImGui.input_float("Pitch", state.pitch)
    ui.action_button("Set Pitch", Camera.SetPitch, state.pitch, key="set_pitch")
    state.max_distance = PyImGui.input_float("Max Distance", state.max_distance)
    ui.action_button("Set Max Distance", Camera.SetMaxDistance, state.max_distance, key="set_maxd")
    state.fov = PyImGui.input_float("Field Of View", state.fov)
    ui.action_button("Set FOV", Camera.SetFieldOfView, state.fov, key="set_fov")

    PyImGui.spacing()
    ui.section_header("Lock / Fog")
    state.unlock = PyImGui.checkbox("Camera Unlock", state.unlock)
    ui.action_button("Apply Unlock", Camera.SetCameraUnlock, state.unlock, key="set_unlock")
    state.fog = PyImGui.checkbox("Fog", state.fog)
    ui.action_button("Apply Fog", Camera.SetFog, state.fog, key="set_fog")

    PyImGui.spacing()
    ui.section_header("Position / Look-At (unlock the camera first)")
    state.pos_x = PyImGui.input_float("Pos X", state.pos_x)
    state.pos_y = PyImGui.input_float("Pos Y", state.pos_y)
    state.pos_z = PyImGui.input_float("Pos Z", state.pos_z)
    ui.action_button("Set Camera Position", Camera.SetCameraPosition, state.pos_x, state.pos_y, state.pos_z, key="set_pos")
    state.look_x = PyImGui.input_float("Look X", state.look_x)
    state.look_y = PyImGui.input_float("Look Y", state.look_y)
    state.look_z = PyImGui.input_float("Look Z", state.look_z)
    ui.action_button("Set Look-At Target", Camera.SetLookAtTarget, state.look_x, state.look_y, state.look_z, key="set_look")

    PyImGui.spacing()
    ui.section_header("Movement")
    state.move_amount = PyImGui.input_float("Move Amount", state.move_amount)
    state.true_forward = PyImGui.checkbox("True Forward", state.true_forward)
    ui.action_button("Forward Movement", Camera.ForwardMovement, state.move_amount, state.true_forward, key="fwd_move")
    PyImGui.same_line(0, 8)
    ui.action_button("Vertical Movement", Camera.VerticalMovement, state.move_amount, key="vert_move")
    PyImGui.same_line(0, 8)
    ui.action_button("Side Movement", Camera.SideMovement, state.move_amount, key="side_move")
    state.rotate_angle = PyImGui.input_float("Rotate Angle", state.rotate_angle)
    ui.action_button("Rotate Movement", Camera.RotateMovement, state.rotate_angle, key="rotate_move")

    PyImGui.spacing()
    ui.section_header("Recompute")
    ui.action_button("Compute Camera Pos", Camera.ComputeCameraPos, key="compute_pos")
    PyImGui.same_line(0, 8)
    ui.action_button("Update Camera Pos", Camera.UpdateCameraPos, key="update_pos")


# ---------------------------------------------------------------------------
# draw_*_view — uniform section entry point
# ---------------------------------------------------------------------------
def draw_camera_view() -> None:
    blocks = build_camera()
    diagnostics.dump_button(_SECTION, blocks)
    PyImGui.separator()
    if PyImGui.begin_tab_bar("CameraTabs"):
        if PyImGui.begin_tab_item("Data"):
            ui.draw_blocks(_SECTION, blocks)
            PyImGui.end_tab_item()
        if PyImGui.begin_tab_item("Actions"):
            _draw_actions()
            PyImGui.end_tab_item()
        PyImGui.end_tab_bar()
