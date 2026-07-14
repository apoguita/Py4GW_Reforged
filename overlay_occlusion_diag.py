# =============================================================================
# Overlay 3D / Occlusion Diagnostic  (in-world compositor version)
# -----------------------------------------------------------------------------
# Draws its test primitives via PyWorldRender.register_draw(): the callback runs
# INSIDE GW's world pass (after the world block, before the HUD) where the depth
# buffer is live, so the DXOverlay Draw*3D calls are correctly occluded by
# walls/terrain. Requires the DLL with the world_render module.
#
# HOW TO USE:
#   1. Be standing in-game, camera looking at your character.
#   2. Open the window, click SHOW (anchors the markers at your feet).
#   3. Walk away / behind a wall. With use_occlusion ON the markers HIDE behind
#      world geometry; OFF -> visible through everything.
#
# Untick SHOW (or close the script) to unregister the callback.
# =============================================================================

import PyImGui
import PyDXOverlay
import PyOverlay
import PySystem
import PyWorldRender

from Py4GWCoreLib.Player import Player

renderer = PyDXOverlay.DXOverlay()
_overlay = PyOverlay.Overlay()

BEAM_TEXTURE = "Textures/loot_beam.png"

# Each primitive is individually toggleable so we can isolate what draws.
PRIMS = ["disc", "ring", "line", "triangle", "quad", "cube", "beam", "texture"]

# (label, D3DCMPFUNC value)
ZFUNC_OPTIONS = [
    ("LESS_EQUAL (4)", 4),
    ("GREATER_EQUAL (7)", 7),
    ("LESS (2)", 2),
    ("GREATER (5)", 5),
    ("ALWAYS (8)", 8),
]

state = {
    "show": False,
    "anchor": None,
    "token": None,           # PyWorldRender registration token
    "occlude": True,         # use_occlusion for every primitive
    "radius": 200.0,
    "height": 400.0,
    "prims": {p: (p in ("disc", "ring", "line", "beam")) for p in PRIMS},

    "color": [0.13, 1.0, 0.25, 1.0],   # RGBA (a = beam intensity)
    "beam_width": 70.0,
    "beam_top_alpha": 0.0,
    "beam_additive": True,

    "draw_opcode": 30,       # DDI opcode 0x1E - confirmed occlusion draw point
    "scan_enabled": False,   # heavy per-opcode depth scan (off by default)

    "near": 46.875,
    "far": 48000.0,
    "zfunc_idx": 0,
    "reverse_z": False,

    "status": "idle",
}


def _argb(rgba):
    r = max(0, min(255, int(rgba[0] * 255)))
    g = max(0, min(255, int(rgba[1] * 255)))
    b = max(0, min(255, int(rgba[2] * 255)))
    a = max(0, min(255, int(rgba[3] * 255)))
    return (a << 24) | (r << 16) | (g << 8) | b


def _ground_z(x, y):
    try:
        return _overlay.FindZ(x, y, 0)
    except Exception:
        return 0.0


def _v(x, y, z):
    return PyOverlay.Vec3f(x, y, z)


def _apply_tuning():
    try:
        zfunc = ZFUNC_OPTIONS[state["zfunc_idx"]][1]
        renderer.set_occlusion_tuning(state["near"], state["far"], zfunc, state["reverse_z"])
    except AttributeError:
        state["status"] = "set_occlusion_tuning missing - rebuild the DLL"
    except Exception as e:
        state["status"] = "tuning error: %s" % e


def _world_draw():
    """Invoked by the compositor INSIDE GW's world pass (depth live). The Draw*3D
    calls draw immediately here, so they occlude against world geometry."""
    if state["anchor"] is None:
        return
    _apply_tuning()

    s = state
    x, y = s["anchor"]
    occ = bool(s["occlude"])
    r = s["radius"]
    gz = _ground_z(x, y)
    top_z = gz - s["height"]     # up = decreasing z in this space
    col = _argb(s["color"])
    P = s["prims"]

    if P["disc"]:
        renderer.DrawPolyFilled3D(_v(x, y, gz), r, col, 48, True, occ, 1, 0.0)
    if P["ring"]:
        renderer.DrawPoly3D(_v(x, y, gz), r * 1.1, col, 48, True, occ, 1, 0.0)
    if P["line"]:
        renderer.DrawLine3D(_v(x, y, gz), _v(x, y, top_z), col, occ, 1, 0.0)
    if P["triangle"]:
        renderer.DrawTriangleFilled3D(
            _v(x - r, y - r, gz), _v(x + r, y - r, gz), _v(x, y + r, gz),
            col, occ, 1, 0.0)
    if P["quad"]:
        renderer.DrawQuadFilled3D(
            _v(x - r, y - r, gz), _v(x + r, y - r, gz),
            _v(x + r, y + r, gz), _v(x - r, y + r, gz),
            col, occ, 1, 0.0)
    if P["cube"]:
        renderer.DrawCubeOutline(_v(x, y, gz - r * 0.5), r, col, occ)
    if P["beam"]:
        renderer.DrawBeam3D(x, y, gz, s["height"], s["beam_width"], col,
                            s["beam_top_alpha"], s["beam_additive"])
    if P["texture"]:
        try:
            renderer.DrawTexture3D(BEAM_TEXTURE, x, y, gz - s["height"] * 0.5,
                                   r, s["height"], occ, col)
        except Exception:
            pass


def _capture_anchor():
    try:
        if Player.GetAgentID() == 0:
            state["status"] = "NOT IN GAME - load into a map first"
            return False
        state["anchor"] = Player.GetXY()
        state["status"] = "anchored at %s" % (state["anchor"],)
        return True
    except Exception as e:
        state["status"] = "no player pos: %s" % e
        return False


def _sync_registration():
    """Register/unregister the world-draw callback to match `show`."""
    want = state["show"] and state["anchor"] is not None
    if want and state["token"] is None:
        try:
            state["token"] = PyWorldRender.register_draw(_world_draw)
            state["status"] = "registered (in-world), anchor=%s" % (state["anchor"],)
        except AttributeError:
            state["status"] = "PyWorldRender missing - rebuild the DLL"
        except Exception as e:
            state["status"] = "register failed: %s" % e
    elif not want and state["token"] is not None:
        try:
            PyWorldRender.unregister_draw(state["token"])
        except Exception:
            pass
        state["token"] = None
        state["status"] = "unregistered"


def _log(msg):
    try:
        PySystem.Console.Log("OverlayDiag", msg, PySystem.Console.MessageType.Notice)
    except Exception:
        pass


def _wr_diag():
    try:
        return PyWorldRender.get_diagnostics()
    except Exception as e:
        return "wr diag err: %s" % e


def _draw_ui():
    s = state
    if not PyImGui.begin("Overlay 3D Test"):
        PyImGui.end()
        return

    label = "HIDE" if s["show"] else "SHOW"
    if PyImGui.button(label):
        s["show"] = not s["show"]
        if s["show"]:
            _capture_anchor()
    PyImGui.same_line(0, -1)
    if PyImGui.button("Re-anchor here"):
        if _capture_anchor():
            s["show"] = True
    PyImGui.same_line(0, -1)
    if PyImGui.button("Log WR diag"):
        _log("WR | " + _wr_diag())

    PyImGui.separator()
    s["occlude"] = PyImGui.checkbox("use_occlusion (hide behind walls)", s["occlude"])

    PyImGui.text("Primitives:")
    for i, p in enumerate(PRIMS):
        s["prims"][p] = PyImGui.checkbox(p, s["prims"][p])
        if i % 2 == 0 and i != len(PRIMS) - 1:
            PyImGui.same_line(0, -1)

    PyImGui.separator()
    s["radius"] = PyImGui.slider_float("Size (radius)", s["radius"], 20.0, 500.0)
    s["height"] = PyImGui.slider_float("Beam/line height", s["height"], 50.0, 1200.0)
    s["color"] = PyImGui.color_edit4("color (a=beam intensity)", s["color"])
    s["beam_width"] = PyImGui.slider_float("beam width", s["beam_width"], 5.0, 300.0)
    s["beam_top_alpha"] = PyImGui.slider_float("beam top fade (0=full)", s["beam_top_alpha"], 0.0, 1.0)
    s["beam_additive"] = PyImGui.checkbox("beam additive (light) blend", s["beam_additive"])

    PyImGui.separator()
    s["draw_opcode"] = PyImGui.slider_int("draw opcode (0x1E=30)", s["draw_opcode"], 0, 37)
    s["scan_enabled"] = PyImGui.checkbox("depth scan (heavy, diagnostic)", s["scan_enabled"])

    PyImGui.separator()
    if PyImGui.collapsing_header("Depth tuning"):
        s["near"] = PyImGui.slider_float("near", s["near"], 1.0, 2000.0)
        s["far"] = PyImGui.slider_float("far", s["far"], 1000.0, 100000.0)
        s["zfunc_idx"] = PyImGui.combo("depth compare", s["zfunc_idx"], [o[0] for o in ZFUNC_OPTIONS])
        s["reverse_z"] = PyImGui.checkbox("reverse-Z", s["reverse_z"])

    PyImGui.separator()
    PyImGui.text("Status: " + s["status"])
    PyImGui.end()


def main():
    _draw_ui()
    _sync_registration()
    try:
        PyWorldRender.set_enabled(True)
        PyWorldRender.set_draw_opcode(state["draw_opcode"])
        PyWorldRender.set_scan_enabled(state["scan_enabled"])
    except Exception:
        pass


if __name__ == "__main__":
    main()
