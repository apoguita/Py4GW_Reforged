# =============================================================================
# Overlay 3D / Occlusion Diagnostic  (fully transparent: call Draw*3D, that's it)
# -----------------------------------------------------------------------------
# main() just calls DXOverlay's Draw*3D methods every frame while showing. Each call
# APPENDS to the class's internal list (the drawing IS the implicit keepalive - no
# register_draw, no heartbeat, no token). The class lazily registers ONE world-pass
# callback that draws the WHOLE list on EVERY world pass (never consuming it, so it
# reaches the visible pass and occludes), and auto-clears ~100ms after Draw*3D calls
# stop (hidden / script closed).
#
# HOW TO USE:
#   1. Stand in-game, camera on your character.
#   2. SHOW (anchors markers at your feet). Walk behind a wall - use_occlusion ON
#      hides them; OFF shows through.
#   3. Close the script -> markers clear on their own shortly after.
# =============================================================================

import math

import PyImGui
import PyDXOverlay
import PyOverlay
import PySystem
import PyWorldRender
import PyCamera
import PyTexture

from Py4GWCoreLib.Player import Player

renderer = PyDXOverlay.get_overlay()   # shared singleton (same object everywhere)
_overlay = PyOverlay.Overlay()

BEAM_TEXTURE = "Textures/loot_beam.png"
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
    "occlude": True,
    "radius": 200.0,
    "height": 400.0,
    "prims": {p: (p in ("disc", "ring", "line", "beam")) for p in PRIMS},

    "color": [0.13, 1.0, 0.25, 1.0],
    "beam_width": 70.0,
    "beam_top_alpha": 0.0,
    "beam_additive": True,

    "draw_opcode": 30,
    "scan_enabled": False,

    "tex_file_id": 0x2381,   # GW.dat file id of the Toolbox loot-ring sprite

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


def _camera_right_2d():
    """Ground-plane 'right' vector, perpendicular to the camera's forward direction.
    Used to billboard the beam: a single upright quad whose flat face turns to always
    point at the camera (so it never goes edge-on)."""
    try:
        cam = PyCamera.PyCamera()
        fx = cam.look_at_target.x - cam.position.x
        fy = cam.look_at_target.y - cam.position.y
    except Exception:
        return (1.0, 0.0)
    length = math.hypot(fx, fy)
    if length < 1e-4:
        return (1.0, 0.0)
    return (fy / length, -fx / length)   # perpendicular to forward in XY


def _build_beam(x, y, ground_z, height, width, argb, solid_frac=0.25):
    """Build a Toolbox-style light beam ENTIRELY IN PYTHON, as a triangle list:
      - camera-facing billboard (one upright quad that turns to face you)
      - 3x3 vertex grid so alpha fades in two directions
      - horizontal: opaque center column, transparent left/right edges -> soft column
      - vertical: bottom `solid_frac` solid, fading to transparent at the top (up = -z)
    Returns a list of (x, y, z, argb) tuples: 24 verts = 8 triangles.
    Feed it to renderer.draw_shaded_3d(). This is the geometry+effect, built in Python;
    C++ only draws the triangles (occluded, HDR-correct)."""
    rx, ry = _camera_right_2d()
    half = width * 0.5
    body = argb & 0x00FFFFFF
    base_a = (argb >> 24) & 0xFF

    def col(af):
        a = max(0, min(255, int(base_a * af)))
        return (a << 24) | body

    rows_z = [ground_z, ground_z - height * solid_frac, ground_z - height]  # base, solid, top
    rows_v = [1.0, 1.0, 0.0]    # vertical alpha: base/solid solid, top fades to 0
    cols_c = [-1.0, 0.0, 1.0]   # left, center, right
    cols_h = [0.0, 1.0, 0.0]    # horizontal alpha: edges transparent, center full

    grid = []
    for r, gz in enumerate(rows_z):
        row = []
        for c, cc in enumerate(cols_c):
            px = x + rx * half * cc
            py = y + ry * half * cc
            row.append((px, py, gz, col(rows_v[r] * cols_h[c])))
        grid.append(row)

    verts = []
    for r in range(2):
        for c in range(2):
            v00, v01 = grid[r][c], grid[r][c + 1]
            v10, v11 = grid[r + 1][c], grid[r + 1][c + 1]
            verts.extend([v00, v01, v11, v00, v11, v10])
    return verts


def _apply_tuning():
    try:
        zfunc = ZFUNC_OPTIONS[state["zfunc_idx"]][1]
        renderer.set_occlusion_tuning(state["near"], state["far"], zfunc, state["reverse_z"])
    except AttributeError:
        state["status"] = "set_occlusion_tuning missing - rebuild the DLL"
    except Exception as e:
        state["status"] = "tuning error: %s" % e


def _draw_markers():
    """Called every frame from main(). Each Draw*3D APPENDS to the class's internal
    list (implicit keepalive); the class draws them (occluded) in the world pass on
    every pass. No callback/register/heartbeat here."""
    if state["anchor"] is None:
        return
    _apply_tuning()

    s = state
    x, y = s["anchor"]
    occ = bool(s["occlude"])
    r = s["radius"]
    gz = _ground_z(x, y)
    top_z = gz - s["height"]
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
            _v(x - r, y - r, gz), _v(x + r, y - r, gz), _v(x, y + r, gz), col, occ, 1, 0.0)
    if P["quad"]:
        renderer.DrawQuadFilled3D(
            _v(x - r, y - r, gz), _v(x + r, y - r, gz),
            _v(x + r, y + r, gz), _v(x - r, y + r, gz), col, occ, 1, 0.0)
    if P["cube"]:
        renderer.DrawCubeOutline(_v(x, y, gz - r * 0.5), r, col, occ)
    if P["beam"]:
        # Toolbox-style beam, geometry + effect built in Python, drawn via the generic
        # shader-geometry primitive. (The old C++ renderer.DrawBeam3D still exists.)
        beam_verts = _build_beam(x, y, gz, s["height"], s["beam_width"], col, 0.25)
        try:
            renderer.draw_shaded_3d(beam_verts, s["beam_additive"], True)
        except AttributeError:
            renderer.DrawBeam3D(x, y, gz, s["height"], s["beam_width"], col,
                                s["beam_top_alpha"], s["beam_additive"])  # DLL not rebuilt yet
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
    if PyImGui.collapsing_header("DAT texture viewer (see the ring sprite)"):
        try:
            s["tex_file_id"] = PyImGui.input_int("dat file id (0x2381=ring)", s["tex_file_id"], 1, 16, 0)
        except Exception:
            PyImGui.text("file id = 0x%X" % s["tex_file_id"])
        try:
            tex = PyTexture.get_texture_by_file_id(s["tex_file_id"] & 0xFFFFFFFF)
            if tex:
                PyImGui.text("handle: 0x%X  (id 0x%X)" % (tex, s["tex_file_id"]))
                # draw the raw sprite so we can see exactly what the ring texture is
                PyImGui.image(tex, (160.0, 160.0), (0.0, 0.0), (1.0, 1.0))
            else:
                PyImGui.text("loading... (async - decodes over a few frames, keep it open)")
        except Exception as e:
            PyImGui.text("texture err: %s" % e)

    PyImGui.separator()
    PyImGui.text("Status: " + s["status"])
    PyImGui.end()


def main():
    _draw_ui()
    try:
        PyWorldRender.set_draw_opcode(state["draw_opcode"])
        PyWorldRender.set_scan_enabled(state["scan_enabled"])
    except Exception:
        pass
    # Fully transparent: just call the draws each frame. Each Draw*3D appends to the
    # class's list (implicit keepalive - no register, no heartbeat, no token); the class
    # draws them occluded in the world pass and auto-clears ~100ms after you stop.
    if state["show"] and state["anchor"] is not None:
        _draw_markers()


if __name__ == "__main__":
    main()
