"""
DXOverlay section — a hand-wired D3D9 draw showcase over the ``Py4GWCoreLib.DXOverlay.DXOverlay``
wrapper (the singleton-style class that other widgets already use successfully).

Why this is a showcase and not a pile of one-shot buttons (the old file's defect):
  * Every DXOverlay draw (``DrawLine``, ``DrawLine3D``, ``DrawCubeFilled``, ...) is an *immediate*
    ``IDirect3DDevice9::DrawPrimitiveUP`` call — it paints the CURRENT frame's back-buffer and is
    gone next frame. Firing it once from an Action button = a single-frame flash = invisible. So,
    exactly like ``overlay_demo.py``, the enabled draws are re-emitted EVERY FRAME from
    ``draw_dxoverlay_view()``.
  * The raw ``PyDXOverlay.DXOverlay`` takes ``GW::Vec2f``/``GW::Vec3f`` objects, NOT tuples
    (verified: overlay_bindings.cpp binds ``Vec2f``/``Vec3f`` as classes with a ``(float,float[,z])``
    ctor and registers NO tuple type-caster / implicit conversion). The old file passed raw tuples,
    which raises ``TypeError`` at the binding boundary. The ``Py4GWCoreLib.DXOverlay`` wrapper takes
    scalar ``x, y[, z]`` args and constructs the ``PyOverlay.Vec2f/Vec3f`` for us — so we drive the
    wrapper, mirroring how ``overlay_demo`` drives the ``Overlay`` wrapper.

Data path: ``Py4GWCoreLib.DXOverlay.DXOverlay`` (scalar-arg wrapper over native
``PyDXOverlay.DXOverlay`` + ``PyOverlay.Vec2f/Vec3f``). 3D draws are anchored at the player (needs
an instance + camera); 2D draws are anchored at a configurable screen point.

Two draw families:
  * IMMEDIATE draws — emitted every frame, toggle-driven:
      2D (screen px): DrawLine, DrawTriangle, DrawTriangleFilled, DrawQuad, DrawQuadFilled,
                      DrawPoly, DrawPolyFilled, DrawTexture.
      3D (world):     DrawLine3D, DrawTriangle3D, DrawTriangleFilled3D, DrawQuad3D, DrawQuadFilled3D,
                      DrawPoly3D, DrawPolyFilled3D, DrawCubeOutline, DrawCubeFilled, DrawTexture3D,
                      DrawQuadTextured3D.
  * RETAINED geometry — the transform/mask pipeline flushed by ``render()`` (only draws the
    ``primitives`` list, shapes of 3-4 verts). Toggle "Render primitives" re-applies the world/
    screen transforms + masks + inverse each frame and calls ``render()`` on either a screen-space
    quad (built via ``set_primitives``) or the map's pathing trapezoids
    (``build_pathing_trapezoid_geometry``). ``ApplyStencilMask`` / ``ResetStencilMask`` /
    ``SaveGeometryToFile`` are one-shot Actions.
"""

import math

import PyImGui

from Py4GWCoreLib.Agent import Agent
from Py4GWCoreLib.DXOverlay import DXOverlay
from Py4GWCoreLib.Player import Player

from . import casts
from . import diagnostics
from . import ui

_SECTION = "DXOverlay"

_overlay = None
_err = ""


def _get_overlay():
    """Lazily construct the DXOverlay wrapper (only importable in-client)."""
    global _overlay, _err
    if _overlay is None and not _err:
        try:
            _overlay = DXOverlay()
        except Exception as e:  # noqa: BLE001
            _err = f"{type(e).__name__}: {e}"
    return _overlay


def _vec2f_module():
    """PyOverlay module for building Vec2f primitives (set_primitives needs real Vec2f)."""
    try:
        import PyOverlay  # embedded module — only present in-client
        return PyOverlay
    except Exception:  # noqa: BLE001
        return None


class _State:
    # shared style
    color: int = 0xFF33CCFF
    tex_tint: int = 0xFFFFFFFF
    thickness: float = 2.0
    radius: float = 150.0
    segments: int = 32
    use_occlusion: bool = False
    floor_offset: float = 0.0
    cube_size: float = 100.0

    # 2D anchor (screen pixels) + texture params
    anchor_x: float = 700.0
    anchor_y: float = 450.0
    tex_path: str = "Textures/Maps/example.png"
    tex_w: float = 96.0
    tex_h: float = 96.0

    # 2D toggles (anchored at the screen anchor)
    line2d: bool = False
    tri2d: bool = False
    tri2d_filled: bool = False
    quad2d: bool = False
    quad2d_filled: bool = False
    poly2d: bool = False
    poly2d_filled: bool = False
    tex2d: bool = False

    # 3D toggles (anchored at player)
    line3d_to_target: bool = False
    tri3d: bool = False
    tri3d_filled: bool = False
    quad3d: bool = False
    quad3d_filled: bool = False
    poly3d: bool = False
    poly3d_filled: bool = False
    cube_outline: bool = False
    cube_filled: bool = False
    tex3d: bool = False
    quad_tex3d: bool = False

    # retained-geometry render() pipeline
    render_primitives: bool = False
    prim_source: int = 0  # 0 = screen quad, 1 = pathing trapezoids
    world_space: bool = False
    world_zoom: float = 1.0
    world_pan_x: float = 0.0
    world_pan_y: float = 0.0
    world_rotation: float = 0.0
    world_scale: float = 1.0
    screen_space: bool = False
    screen_zoom: float = 1.0
    screen_pan_x: float = 0.0
    screen_pan_y: float = 0.0
    screen_rotation: float = 0.0
    inverse: bool = False
    # masks (only affect render())
    circ_mask: bool = False
    circ_radius: float = 200.0
    circ_center_x: float = 700.0
    circ_center_y: float = 450.0
    rect_mask: bool = False
    rect_x: float = 400.0
    rect_y: float = 250.0
    rect_w: float = 600.0
    rect_h: float = 400.0
    pathing_color: int = 0xFF00FF00

    # SaveGeometryToFile
    save_filename: str = "geometry.png"
    save_min_x: float = -10000.0
    save_min_y: float = -10000.0
    save_max_x: float = 10000.0
    save_max_y: float = 10000.0


state = _State()


# ---------------------------------------------------------------------------
# anchors
# ---------------------------------------------------------------------------
def _player_pos():
    res = casts.safe(lambda: Agent.GetXYZ(Player.GetAgentID()))
    if not res or len(res) < 3:
        return None
    return res


def _target_pos():
    tid = casts.safe(Player.GetTargetID) or 0
    if not tid:
        return None
    res = casts.safe(lambda: Agent.GetXYZ(tid))
    if not res or len(res) < 3:
        return None
    return res


def _ring(cx, cy, n, radius, rot=0.0):
    pts = []
    n = max(3, n)
    for i in range(n):
        a = rot + 2.0 * math.pi * i / n
        pts.append((cx + math.cos(a) * radius, cy + math.sin(a) * radius))
    return pts


# ---------------------------------------------------------------------------
# build_* — cast the configured state into display blocks (render AND dump)
# ---------------------------------------------------------------------------
def build_dxoverlay():
    ppos = _player_pos()
    anchor = ui.kv_block("Anchors", [
        ("2D screen anchor", casts.vec(state.anchor_x, state.anchor_y)),
        ("Player position (3D)", "N/A" if ppos is None else casts.vec(ppos[0], ppos[1], ppos[2])),
        ("Target position (3D)", "N/A" if _target_pos() is None else casts.vec(*_target_pos())),
    ])
    style = ui.kv_block("Style", [
        ("Color", casts.hex_of(state.color, 8)),
        ("Texture Tint", casts.hex_of(state.tex_tint, 8)),
        ("Thickness", casts.f2(state.thickness)),
        ("Radius", casts.f2(state.radius)),
        ("Segments", state.segments),
        ("Use Occlusion", casts.yesno(state.use_occlusion)),
        ("Floor Offset", casts.f2(state.floor_offset)),
        ("Cube Size", casts.f2(state.cube_size)),
        ("Texture Path", state.tex_path),
        ("Texture Size (w,h)", casts.vec(state.tex_w, state.tex_h)),
    ])
    draws2d = ui.bool_block("Immediate 2D draws (screen)", [
        ("DrawLine", state.line2d),
        ("DrawTriangle", state.tri2d),
        ("DrawTriangleFilled", state.tri2d_filled),
        ("DrawQuad", state.quad2d),
        ("DrawQuadFilled", state.quad2d_filled),
        ("DrawPoly", state.poly2d),
        ("DrawPolyFilled", state.poly2d_filled),
        ("DrawTexture", state.tex2d),
    ])
    draws3d = ui.bool_block("Immediate 3D draws (world, at player)", [
        ("DrawLine3D -> target", state.line3d_to_target),
        ("DrawTriangle3D", state.tri3d),
        ("DrawTriangleFilled3D", state.tri3d_filled),
        ("DrawQuad3D", state.quad3d),
        ("DrawQuadFilled3D", state.quad3d_filled),
        ("DrawPoly3D", state.poly3d),
        ("DrawPolyFilled3D", state.poly3d_filled),
        ("DrawCubeOutline", state.cube_outline),
        ("DrawCubeFilled", state.cube_filled),
        ("DrawTexture3D", state.tex3d),
        ("DrawQuadTextured3D", state.quad_tex3d),
    ])
    pipeline = ui.kv_block("Retained geometry (render pipeline)", [
        ("Render Primitives", casts.yesno(state.render_primitives)),
        ("Primitive Source", "Screen quad" if state.prim_source == 0 else "Pathing trapezoids"),
        ("World Space", casts.yesno(state.world_space)),
        ("World Zoom / Scale", f"{casts.f2(state.world_zoom)} / {casts.f2(state.world_scale)}"),
        ("World Pan", casts.vec(state.world_pan_x, state.world_pan_y)),
        ("World Rotation", casts.f2(state.world_rotation)),
        ("Screen Space", casts.yesno(state.screen_space)),
        ("Screen Zoom", casts.f2(state.screen_zoom)),
        ("Screen Pan", casts.vec(state.screen_pan_x, state.screen_pan_y)),
        ("Screen Rotation", casts.f2(state.screen_rotation)),
        ("Inverse Rendering", casts.yesno(state.inverse)),
    ])
    masks = ui.kv_block("Masks (affect render only)", [
        ("Circular Mask", casts.yesno(state.circ_mask)),
        ("Circular Radius", casts.f2(state.circ_radius)),
        ("Circular Center", casts.vec(state.circ_center_x, state.circ_center_y)),
        ("Rectangle Mask", casts.yesno(state.rect_mask)),
        ("Rect Bounds (x,y,w,h)", casts.vec(state.rect_x, state.rect_y, state.rect_w, state.rect_h)),
        ("Pathing Color", casts.hex_of(state.pathing_color, 8)),
    ])
    return [anchor, style, draws2d, draws3d, pipeline, masks]


# ---------------------------------------------------------------------------
# Draw tab — inputs + toggles + one-shot actions
# ---------------------------------------------------------------------------
def _draw_controls(ov) -> None:
    ui.section_header("Shared style")
    state.color = ui.input_hex("Color (ARGB 0xAARRGGBB)", state.color)
    state.tex_tint = ui.input_hex("Texture Tint (ARGB)", state.tex_tint)
    state.thickness = PyImGui.input_float("Thickness", state.thickness)
    state.radius = PyImGui.input_float("Radius", state.radius)
    state.segments = PyImGui.input_int("Segments", state.segments)
    state.use_occlusion = PyImGui.checkbox("Use Occlusion (3D)", state.use_occlusion)
    state.floor_offset = PyImGui.input_float("Floor Offset (3D)", state.floor_offset)
    state.cube_size = PyImGui.input_float("Cube Size", state.cube_size)

    PyImGui.spacing()
    ui.section_header("Screen-space 2D (anchored at screen point)")
    state.anchor_x = PyImGui.input_float("Anchor X", state.anchor_x)
    state.anchor_y = PyImGui.input_float("Anchor Y", state.anchor_y)
    state.line2d = PyImGui.checkbox("DrawLine", state.line2d)
    state.tri2d = PyImGui.checkbox("DrawTriangle", state.tri2d)
    state.tri2d_filled = PyImGui.checkbox("DrawTriangleFilled", state.tri2d_filled)
    state.quad2d = PyImGui.checkbox("DrawQuad", state.quad2d)
    state.quad2d_filled = PyImGui.checkbox("DrawQuadFilled", state.quad2d_filled)
    state.poly2d = PyImGui.checkbox("DrawPoly", state.poly2d)
    state.poly2d_filled = PyImGui.checkbox("DrawPolyFilled", state.poly2d_filled)

    PyImGui.spacing()
    ui.section_header("Texture (needs a valid texture path)")
    state.tex_path = PyImGui.input_text("Texture Path", state.tex_path)
    state.tex_w = PyImGui.input_float("Texture Width", state.tex_w)
    state.tex_h = PyImGui.input_float("Texture Height", state.tex_h)
    state.tex2d = PyImGui.checkbox("DrawTexture (2D at anchor)", state.tex2d)
    state.tex3d = PyImGui.checkbox("DrawTexture3D (at player)", state.tex3d)
    state.quad_tex3d = PyImGui.checkbox("DrawQuadTextured3D (quad at player)", state.quad_tex3d)

    PyImGui.spacing()
    ui.section_header("World-space 3D (anchored at player, needs an instance)")
    state.line3d_to_target = PyImGui.checkbox("DrawLine3D player -> target", state.line3d_to_target)
    state.tri3d = PyImGui.checkbox("DrawTriangle3D", state.tri3d)
    state.tri3d_filled = PyImGui.checkbox("DrawTriangleFilled3D", state.tri3d_filled)
    state.quad3d = PyImGui.checkbox("DrawQuad3D", state.quad3d)
    state.quad3d_filled = PyImGui.checkbox("DrawQuadFilled3D", state.quad3d_filled)
    state.poly3d = PyImGui.checkbox("DrawPoly3D", state.poly3d)
    state.poly3d_filled = PyImGui.checkbox("DrawPolyFilled3D", state.poly3d_filled)
    state.cube_outline = PyImGui.checkbox("DrawCubeOutline", state.cube_outline)
    state.cube_filled = PyImGui.checkbox("DrawCubeFilled", state.cube_filled)

    PyImGui.spacing()
    ui.section_header("Retained geometry — render() pipeline")
    state.render_primitives = PyImGui.checkbox("Render primitives every frame (calls render())", state.render_primitives)
    state.prim_source = PyImGui.radio_button("Screen quad", state.prim_source, 0)
    PyImGui.same_line(0, 8)
    state.prim_source = PyImGui.radio_button("Pathing trapezoids", state.prim_source, 1)
    state.pathing_color = ui.input_hex("Pathing Color (ARGB)", state.pathing_color)
    ui.action_button("Build Pathing Geometry", ov.build_pathing_trapezoid_geometry, state.pathing_color, key="dx_pathgeo")

    PyImGui.spacing()
    ui.section_header("World transform (applied to render())")
    state.world_space = PyImGui.checkbox("World Space", state.world_space)
    state.world_zoom = PyImGui.input_float("World Zoom", state.world_zoom)
    state.world_scale = PyImGui.input_float("World Scale", state.world_scale)
    state.world_pan_x = PyImGui.input_float("World Pan X", state.world_pan_x)
    state.world_pan_y = PyImGui.input_float("World Pan Y", state.world_pan_y)
    state.world_rotation = PyImGui.input_float("World Rotation", state.world_rotation)

    PyImGui.spacing()
    ui.section_header("Screen transform (applied to render())")
    state.screen_space = PyImGui.checkbox("Screen Space", state.screen_space)
    state.screen_zoom = PyImGui.input_float("Screen Zoom", state.screen_zoom)
    state.screen_pan_x = PyImGui.input_float("Screen Pan X", state.screen_pan_x)
    state.screen_pan_y = PyImGui.input_float("Screen Pan Y", state.screen_pan_y)
    state.screen_rotation = PyImGui.input_float("Screen Rotation", state.screen_rotation)
    state.inverse = PyImGui.checkbox("Inverse Rendering", state.inverse)

    PyImGui.spacing()
    ui.section_header("Masks (applied to render())")
    state.circ_mask = PyImGui.checkbox("Circular Mask", state.circ_mask)
    state.circ_radius = PyImGui.input_float("Circular Radius", state.circ_radius)
    state.circ_center_x = PyImGui.input_float("Circular Center X", state.circ_center_x)
    state.circ_center_y = PyImGui.input_float("Circular Center Y", state.circ_center_y)
    state.rect_mask = PyImGui.checkbox("Rectangle Mask", state.rect_mask)
    state.rect_x = PyImGui.input_float("Rect X", state.rect_x)
    state.rect_y = PyImGui.input_float("Rect Y", state.rect_y)
    state.rect_w = PyImGui.input_float("Rect Width", state.rect_w)
    state.rect_h = PyImGui.input_float("Rect Height", state.rect_h)
    ui.action_button("Apply Stencil Mask", ov.ApplyStencilMask, key="dx_applystencil")
    PyImGui.same_line(0, 8)
    ui.action_button("Reset Stencil Mask", ov.ResetStencilMask, key="dx_resetstencil")

    PyImGui.spacing()
    ui.section_header("Save Geometry To File (needs built primitives)")
    state.save_filename = PyImGui.input_text("Save Filename", state.save_filename)
    state.save_min_x = PyImGui.input_float("Save Min X", state.save_min_x)
    state.save_min_y = PyImGui.input_float("Save Min Y", state.save_min_y)
    state.save_max_x = PyImGui.input_float("Save Max X", state.save_max_x)
    state.save_max_y = PyImGui.input_float("Save Max Y", state.save_max_y)
    ui.action_button("Save Geometry To File", ov.SaveGeometryToFile, state.save_filename,
                     state.save_min_x, state.save_min_y, state.save_max_x, state.save_max_y, key="dx_savegeo")


# ---------------------------------------------------------------------------
# Every-frame emission (immediate draws + optional render() pipeline)
# ---------------------------------------------------------------------------
def _any_immediate() -> bool:
    return any((
        state.line2d, state.tri2d, state.tri2d_filled, state.quad2d, state.quad2d_filled,
        state.poly2d, state.poly2d_filled, state.tex2d,
        state.line3d_to_target, state.tri3d, state.tri3d_filled, state.quad3d, state.quad3d_filled,
        state.poly3d, state.poly3d_filled, state.cube_outline, state.cube_filled,
        state.tex3d, state.quad_tex3d,
    ))


def _emit_2d(ov, color, th) -> None:
    ax, ay, r = state.anchor_x, state.anchor_y, state.radius
    if state.line2d:
        ov.DrawLine(ax - r, ay, ax + r, ay, color, th)
    if state.tri2d:
        p = _ring(ax, ay, 3, r)
        ov.DrawTriangle(p[0][0], p[0][1], p[1][0], p[1][1], p[2][0], p[2][1], color, th)
    if state.tri2d_filled:
        p = _ring(ax, ay, 3, r * 0.7, rot=math.pi)
        ov.DrawTriangleFilled(p[0][0], p[0][1], p[1][0], p[1][1], p[2][0], p[2][1], color)
    if state.quad2d:
        p = _ring(ax, ay, 4, r, rot=math.pi / 4)
        ov.DrawQuad(p[0][0], p[0][1], p[1][0], p[1][1], p[2][0], p[2][1], p[3][0], p[3][1], color, th)
    if state.quad2d_filled:
        p = _ring(ax, ay, 4, r * 0.6, rot=math.pi / 4)
        ov.DrawQuadFilled(p[0][0], p[0][1], p[1][0], p[1][1], p[2][0], p[2][1], p[3][0], p[3][1], color)
    if state.poly2d:
        ov.DrawPoly(ax, ay, r, color, max(3, int(state.segments)), th)
    if state.poly2d_filled:
        ov.DrawPolyFilled(ax, ay, r * 0.5, color, max(3, int(state.segments)))
    if state.tex2d and state.tex_w > 0 and state.tex_h > 0:
        casts.safe(ov.DrawTexture, state.tex_path, ax, ay, state.tex_w, state.tex_h, state.tex_tint)


def _emit_3d(ov, color, th, ppos) -> None:
    px, py, pz = ppos
    occ, seg, floor = state.use_occlusion, max(3, int(state.segments)), state.floor_offset
    r = state.radius
    if state.line3d_to_target:
        tpos = _target_pos()
        if tpos is not None:
            ov.DrawLine3D(px, py, pz, tpos[0], tpos[1], tpos[2], color, occ, 1, floor)
    if state.tri3d:
        p = _ring(px, py, 3, r)
        ov.DrawTriangle3D(p[0][0], p[0][1], pz, p[1][0], p[1][1], pz, p[2][0], p[2][1], pz, color, occ, 1, floor)
    if state.tri3d_filled:
        p = _ring(px, py, 3, r * 0.7, rot=math.pi)
        ov.DrawTriangleFilled3D(p[0][0], p[0][1], pz, p[1][0], p[1][1], pz, p[2][0], p[2][1], pz, color, occ, 1, floor)
    if state.quad3d:
        p = _ring(px, py, 4, r, rot=math.pi / 4)
        ov.DrawQuad3D(p[0][0], p[0][1], pz, p[1][0], p[1][1], pz, p[2][0], p[2][1], pz, p[3][0], p[3][1], pz,
                      color, occ, 1, floor)
    if state.quad3d_filled:
        p = _ring(px, py, 4, r * 0.6, rot=math.pi / 4)
        ov.DrawQuadFilled3D(p[0][0], p[0][1], pz, p[1][0], p[1][1], pz, p[2][0], p[2][1], pz, p[3][0], p[3][1], pz,
                            color, occ, 1, floor)
    if state.poly3d:
        ov.DrawPoly3D(px, py, pz, r, color, seg, occ, 1, floor)
    if state.poly3d_filled:
        ov.DrawPolyFilled3D(px, py, pz, r * 0.5, color, seg, occ, 1, floor)
    if state.cube_outline:
        ov.DrawCubeOutline(px, py, pz, state.cube_size, color, occ)
    if state.cube_filled:
        ov.DrawCubeFilled(px, py, pz, state.cube_size, color, occ)
    if state.tex3d and state.tex_w > 0 and state.tex_h > 0:
        casts.safe(ov.DrawTexture3D, state.tex_path, px, py, pz, state.tex_w, state.tex_h, occ, state.tex_tint)
    if state.quad_tex3d:
        p = _ring(px, py, 4, r, rot=math.pi / 4)
        casts.safe(ov.DrawQuadTextured3D, state.tex_path,
                   p[0][0], p[0][1], pz, p[1][0], p[1][1], pz, p[2][0], p[2][1], pz, p[3][0], p[3][1], pz,
                   occ, state.tex_tint)


def _emit_render_pipeline(ov, color) -> None:
    """Apply transforms + masks, populate primitives, then flush with render()."""
    # transforms
    ov.world_space.set_world_space(state.world_space)
    ov.world_space.set_zoom(state.world_zoom)
    ov.world_space.set_pan(state.world_pan_x, state.world_pan_y)
    ov.world_space.set_scale(state.world_scale)
    ov.world_space.set_rotation(state.world_rotation)
    ov.screen_space.set_screen_space(state.screen_space)
    ov.screen_space.set_zoom(state.screen_zoom)
    ov.screen_space.set_pan(state.screen_pan_x, state.screen_pan_y)
    ov.screen_space.set_rotation(state.screen_rotation)
    ov.inverse_rendering(state.inverse)
    # masks
    ov.mask.set_circular_mask(state.circ_mask)
    ov.mask.set_mask_radius(state.circ_radius)
    ov.mask.set_mask_center(state.circ_center_x, state.circ_center_y)
    ov.mask.set_rectangle_mask(state.rect_mask)
    ov.mask.set_rectangle_mask_bounds(state.rect_x, state.rect_y, state.rect_w, state.rect_h)

    if state.prim_source == 0:
        # screen-space quad primitive (needs real Vec2f instances for set_primitives)
        py_overlay = _vec2f_module()
        if py_overlay is None:
            return
        ax, ay, r = state.anchor_x, state.anchor_y, state.radius
        quad = [
            py_overlay.Vec2f(ax - r, ay - r),
            py_overlay.Vec2f(ax + r, ay - r),
            py_overlay.Vec2f(ax + r, ay + r),
            py_overlay.Vec2f(ax - r, ay + r),
        ]
        ov.set_primitives([quad], color)
    # prim_source == 1 uses whatever build_pathing_trapezoid_geometry populated (via the button)
    ov.render()


def _render_draws(ov) -> None:
    color = state.color
    th = state.thickness

    if _any_immediate():
        if any((state.line2d, state.tri2d, state.tri2d_filled, state.quad2d, state.quad2d_filled,
                state.poly2d, state.poly2d_filled, state.tex2d)):
            casts.safe(_emit_2d, ov, color, th)
        ppos = _player_pos()
        if ppos is not None:
            casts.safe(_emit_3d, ov, color, th, ppos)

    if state.render_primitives:
        casts.safe(_emit_render_pipeline, ov, color)


# ---------------------------------------------------------------------------
# draw_*_view — uniform section entry point
# ---------------------------------------------------------------------------
def draw_dxoverlay_view() -> None:
    ov = _get_overlay()
    blocks = build_dxoverlay()
    diagnostics.dump_button(_SECTION, blocks)
    PyImGui.separator()
    if PyImGui.begin_tab_bar("DXOverlayTabs"):
        if PyImGui.begin_tab_item("Data"):
            ui.draw_blocks(_SECTION, blocks)
            PyImGui.end_tab_item()
        if PyImGui.begin_tab_item("Draw"):
            if ov is None:
                ui.not_available(f"DXOverlay unavailable — {_err}")
            else:
                _draw_controls(ov)
            PyImGui.end_tab_item()
        PyImGui.end_tab_bar()

    # Enabled draws are emitted EVERY FRAME (immediate device draws vanish next frame otherwise).
    if ov is not None:
        _render_draws(ov)
