"""
Overlay section — mouse/screen data rows + a hand-wired world-space & screen-space draw showcase.

Shape (see player_demo.py, the canonical template):
  * ``build_overlay()`` calls the ``Overlay`` wrapper getters, CASTS each value via ``casts``
    (``vec`` for coords, ``f2`` for floats, ``safe()`` around every getter, explicit ``.x/.y``
    deref for the ``Vec2f`` that ``GetDisplaySize`` returns), and returns a list of display Blocks.
    No handle/struct ever reaches a renderer un-dereferenced.
  * ``draw_overlay_view()`` = build once -> ``diagnostics.dump_button`` -> separator -> tab bar with
    a **Data** tab (``ui.draw_blocks``) and a **Draw** tab (toggles + inputs + explicit action
    buttons). The enabled world/screen draws are then emitted EVERY frame, wrapped in
    ``Overlay().BeginDraw()``/``EndDraw()`` (like the prior file). These are known-safe overlay
    calls, not arbitrary binding probes.

NO reflection anywhere — every method is wired by hand.

Data path: ``Py4GWCoreLib.Overlay.Overlay`` (the singleton wrapper over ``PyOverlay.Overlay``). The
stub ``PyOverlay.pyi`` is wrong/incomplete (R2 b7); the wrapper is the real surface and is what we
enumerate/import.

R2 coverage — Overlay wrapper methods WIRED:
  Getters/data:  GetMouseCoords, IsMouseClicked, GetMouseWorldPos, FindZ, WorldToScreen,
                 GetDisplaySize.
  Lifecycle:     BeginDraw, EndDraw, RefreshDrawList, UpkeepTextures, PushClipRect, PopClipRect.
  3D draws:      DrawPoly3D, DrawPolyFilled3D, DrawText3D, DrawLine3D, DrawTriangle3D,
                 DrawTriangleFilled3D, DrawQuad3D, DrawQuadFilled3D, DrawCubeOutline, DrawCubeFilled.
  2D draws:      DrawLine, DrawTriangle, DrawTriangleFilled, DrawQuad, DrawQuadFilled, DrawPoly,
                 DrawPolyFilled, DrawPolyFilledRelative, DrawStar, DrawStarFilled, DrawText.
  Textures:      ImageButton (live, guarded, path-driven).

R2 coverage — SKIPPED (with reason):
  * Texture family DrawTexture / DrawTextureExtended / DrawTexturedRect / DrawTexturedRectExtended /
    DrawTextureInForegound / DrawTextureInDrawList / ImageButtonExtended — need a guaranteed texture
    asset + specific draw-list/window context; out of scope for a safe generic showcase (ImageButton
    stands in as the representative texture call).
  * Native-only methods NOT exposed by the wrapper: FindZPlane, and the coordinate-conversion family
    (GamePosToWorldMap, WorldMapToGamePos, WorldMapToScreen, ScreenToWorldMap, GameMapToScreen,
    ScreenToGameMapPos, NormalizedScreenToScreen, ScreenToNormalizedScreen, NormalizedScreenToWorldMap,
    NormalizedScreenToGameMap, GamePosToNormalizedScreen), plus the whole ``ScreenOverlay`` class
    (create_overlay/destroy/show/begin/draw_rect/draw_rect_filled/draw_text_box/end/get_desktop_size/
    set_auto_expire) — not surfaced by ``Py4GWCoreLib.Overlay.Overlay``.
"""

import math

import PyImGui

from Py4GWCoreLib.Agent import Agent
from Py4GWCoreLib.Overlay import Overlay
from Py4GWCoreLib.Player import Player

from . import casts
from . import diagnostics
from . import ui

_SECTION = "Overlay"

# GW distance rings (label, radius, ABGR ImU32 color) — kept from the prior working file.
_RINGS = [
    ("Aggro (Compass edge)", 5000, 0xFF1E90FF),
    ("Spirit", 2500, 0xFF8A2BE2),
    ("Spellcast", 1248, 0xFF00CED1),
    ("Earshot", 1012, 0xFF3BC154),
    ("Area", 322, 0xFFE3357E),
    ("Nearby", 252, 0xFFE39626),
]


class _State:
    # shared draw params
    color_hex: str = "0xFF33CCFF"
    radius: float = 200.0
    thickness: float = 2.0
    segments: int = 32
    text: str = "DEMO 2.0"
    text_scale: float = 1.5
    cube_size: float = 100.0
    star_outer: float = 90.0
    star_inner: float = 36.0
    star_points: int = 5
    tex_path: str = ""

    # 3D (world-space, anchored at player) toggles
    area_rings: bool = False
    mark_target: bool = False
    line3d_to_target: bool = False
    tri3d: bool = False
    tri3d_filled: bool = False
    quad3d: bool = False
    quad3d_filled: bool = False
    poly3d_filled: bool = False
    cube_outline: bool = False
    cube_filled: bool = False
    text3d: bool = False

    # 2D (screen-space, anchored at mouse) toggles
    line2d: bool = False
    tri2d: bool = False
    tri2d_filled: bool = False
    quad2d: bool = False
    quad2d_filled: bool = False
    poly2d: bool = False
    poly2d_filled: bool = False
    poly2d_relative: bool = False
    star2d: bool = False
    star2d_filled: bool = False
    text2d: bool = False
    clip_2d: bool = False


state = _State()

# Per-draw error isolation: each draw is wrapped so one failing call surfaces its exact error
# (name + exception) instead of throwing and blanking the whole panel. Lets us pinpoint a bad call.
_draw_errors: "dict[str, str]" = {}


def _safe_draw(name, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
        _draw_errors.pop(name, None)
    except Exception as e:  # noqa: BLE001 - record which draw failed and why
        _draw_errors[name] = f"{type(e).__name__}: {e}"


# ---------------------------------------------------------------------------
# small casting helpers
# ---------------------------------------------------------------------------
def _parse_color(text, default: int = 0xFFFFFFFF) -> int:
    """Parse a user-typed color into an ImU32 int; tolerant of ``0x`` prefix and decimals."""
    try:
        s = str(text).strip()
        return int(s, 16) if s.lower().startswith("0x") else int(s)
    except (TypeError, ValueError):
        return default


def _display_size(overlay) -> "tuple":
    ds = casts.safe(overlay.GetDisplaySize)
    if ds is None:
        return (None, None)
    # GetDisplaySize returns a Vec2f handle — deref its fields explicitly (never repr the struct).
    return (casts.safe(lambda: ds.x), casts.safe(lambda: ds.y))


def _player_pos() -> "tuple | None":
    res = casts.safe(lambda: Agent.GetXYZ(Player.GetAgentID()))
    if not res or len(res) < 3:
        return None
    return res


def _target_pos() -> "tuple | None":
    tid = casts.safe(Player.GetTargetID) or 0
    if not tid:
        return None
    res = casts.safe(lambda: Agent.GetXYZ(tid))
    if not res or len(res) < 3:
        return None
    return res


def _ring_points(cx: float, cy: float, n: int, radius: float, rot: float = 0.0) -> "list":
    pts = []
    for i in range(max(3, n)):
        a = rot + 2.0 * math.pi * i / max(3, n)
        pts.append((cx + math.cos(a) * radius, cy + math.sin(a) * radius))
    return pts


# ---------------------------------------------------------------------------
# build_overlay — call getters, cast, return blocks (shared by render AND dump)
# ---------------------------------------------------------------------------
def build_overlay():
    overlay = Overlay()

    mouse = casts.safe(overlay.GetMouseCoords) or (None, None)
    mx, my = mouse[0], mouse[1]
    world = casts.safe(overlay.GetMouseWorldPos) or (None, None, None)
    wx, wy, wz = world[0], world[1], world[2]
    dw, dh = _display_size(overlay)

    rows = [
        ("Mouse Coords (screen)", casts.vec(mx, my)),
        ("Is Mouse Clicked", casts.yesno(casts.safe(overlay.IsMouseClicked))),
        ("Mouse World Pos", casts.vec(wx, wy, wz)),
        ("FindZ(mouse.x, mouse.y)", casts.f2(casts.safe(Overlay.FindZ, mx, my))),
        ("Display Size", casts.vec(dw, dh)),
    ]

    # WorldToScreen of the mouse's world position (round-trip demo).
    if wx is not None and wy is not None:
        sx, sy = casts.safe(Overlay.WorldToScreen, wx, wy) or (None, None)
        rows.append(("WorldToScreen(mouse world)", casts.vec(sx, sy)))

    blocks = [ui.kv_block("Mouse / Screen", rows)]

    # Player anchor block — position + its screen projection (drives the world-space draws).
    ppos = _player_pos()
    if ppos is None:
        prows = [("Player Position", "N/A (not in an instance?)")]
    else:
        px, py, pz = ppos
        psx, psy = casts.safe(Overlay.WorldToScreen, px, py, pz) or (None, None)
        prows = [
            ("Player Position (x,y,z)", casts.vec(px, py, pz, nd=2)),
            ("Player -> Screen", casts.vec(psx, psy)),
        ]
    blocks.append(ui.kv_block("Player Anchor", prows))

    # Active draw toggles — mirror the on-screen Draw tab so the dump reflects current state.
    toggles = [
        ("Area Rings", state.area_rings),
        ("Mark Target", state.mark_target),
        ("Line3D -> Target", state.line3d_to_target),
        ("Triangle3D", state.tri3d),
        ("TriangleFilled3D", state.tri3d_filled),
        ("Quad3D", state.quad3d),
        ("QuadFilled3D", state.quad3d_filled),
        ("PolyFilled3D", state.poly3d_filled),
        ("Cube Outline", state.cube_outline),
        ("Cube Filled", state.cube_filled),
        ("Text3D", state.text3d),
        ("Line2D", state.line2d),
        ("Triangle2D", state.tri2d),
        ("TriangleFilled2D", state.tri2d_filled),
        ("Quad2D", state.quad2d),
        ("QuadFilled2D", state.quad2d_filled),
        ("Poly2D", state.poly2d),
        ("PolyFilled2D", state.poly2d_filled),
        ("PolyFilledRelative2D", state.poly2d_relative),
        ("Star2D", state.star2d),
        ("StarFilled2D", state.star2d_filled),
        ("Text2D", state.text2d),
        ("Clip 2D draws", state.clip_2d),
    ]
    blocks.append(ui.bool_block("Active Draws", toggles))

    params = [
        ("Color", casts.hex_of(_parse_color(state.color_hex), 8)),
        ("Radius", casts.f2(state.radius)),
        ("Thickness", casts.f2(state.thickness)),
        ("Segments", state.segments),
        ("Cube Size", casts.f2(state.cube_size)),
        ("Star Outer / Inner", f"{casts.f2(state.star_outer)} / {casts.f2(state.star_inner)}"),
        ("Star Points", state.star_points),
        ("Text", state.text),
        ("Text Scale", casts.f2(state.text_scale)),
    ]
    blocks.append(ui.kv_block("Draw Params", params))

    # Surface any per-draw failures (exact call + error) so a bad draw is pinpointed, not hidden.
    if _draw_errors:
        blocks.append(ui.kv_block("Draw Errors (last failure per call)", list(_draw_errors.items())))
    return blocks


# ---------------------------------------------------------------------------
# Draw tab — toggles + inputs + explicit action buttons (no auto-fire beyond the known draws)
# ---------------------------------------------------------------------------
def _draw_controls(overlay) -> None:
    ui.section_header("Draw-list actions")
    ui.action_button("Refresh Draw List", overlay.RefreshDrawList, key="ov_refresh")
    PyImGui.same_line(0, 8)
    ui.action_button("Upkeep Textures", overlay.UpkeepTextures, 30, key="ov_upkeep")

    PyImGui.spacing()
    ui.section_header("Shared params")
    state.color_hex = PyImGui.input_text("Color (hex ABGR, e.g. 0xFF33CCFF)", state.color_hex)
    state.radius = PyImGui.input_float("Radius", state.radius)
    state.thickness = PyImGui.input_float("Thickness", state.thickness)
    state.segments = PyImGui.input_int("Segments", state.segments)
    state.cube_size = PyImGui.input_float("Cube Size", state.cube_size)
    state.star_outer = PyImGui.input_float("Star Outer Radius", state.star_outer)
    state.star_inner = PyImGui.input_float("Star Inner Radius", state.star_inner)
    state.star_points = PyImGui.input_int("Star Points", state.star_points)
    state.text = PyImGui.input_text("Text", state.text)
    state.text_scale = PyImGui.input_float("Text Scale", state.text_scale)

    PyImGui.spacing()
    ui.section_header("World-space (3D, anchored at player)")
    state.area_rings = PyImGui.checkbox("Area Rings (DrawPoly3D)", state.area_rings)
    state.mark_target = PyImGui.checkbox("Mark Target (DrawPoly3D + DrawText3D)", state.mark_target)
    state.line3d_to_target = PyImGui.checkbox("Line3D player -> target (DrawLine3D)", state.line3d_to_target)
    state.tri3d = PyImGui.checkbox("Triangle3D (DrawTriangle3D)", state.tri3d)
    state.tri3d_filled = PyImGui.checkbox("TriangleFilled3D (DrawTriangleFilled3D)", state.tri3d_filled)
    state.quad3d = PyImGui.checkbox("Quad3D (DrawQuad3D)", state.quad3d)
    state.quad3d_filled = PyImGui.checkbox("QuadFilled3D (DrawQuadFilled3D)", state.quad3d_filled)
    state.poly3d_filled = PyImGui.checkbox("PolyFilled3D (DrawPolyFilled3D)", state.poly3d_filled)
    state.cube_outline = PyImGui.checkbox("Cube Outline (DrawCubeOutline)", state.cube_outline)
    state.cube_filled = PyImGui.checkbox("Cube Filled (DrawCubeFilled)", state.cube_filled)
    state.text3d = PyImGui.checkbox("Text3D at player (DrawText3D)", state.text3d)

    PyImGui.spacing()
    ui.section_header("Screen-space (2D, anchored at mouse)")
    state.line2d = PyImGui.checkbox("Line2D (DrawLine)", state.line2d)
    state.tri2d = PyImGui.checkbox("Triangle2D (DrawTriangle)", state.tri2d)
    state.tri2d_filled = PyImGui.checkbox("TriangleFilled2D (DrawTriangleFilled)", state.tri2d_filled)
    state.quad2d = PyImGui.checkbox("Quad2D (DrawQuad)", state.quad2d)
    state.quad2d_filled = PyImGui.checkbox("QuadFilled2D (DrawQuadFilled)", state.quad2d_filled)
    state.poly2d = PyImGui.checkbox("Poly2D (DrawPoly)", state.poly2d)
    state.poly2d_filled = PyImGui.checkbox("PolyFilled2D (DrawPolyFilled)", state.poly2d_filled)
    state.poly2d_relative = PyImGui.checkbox("PolyFilledRelative2D (DrawPolyFilledRelative)", state.poly2d_relative)
    state.star2d = PyImGui.checkbox("Star2D (DrawStar)", state.star2d)
    state.star2d_filled = PyImGui.checkbox("StarFilled2D (DrawStarFilled)", state.star2d_filled)
    state.text2d = PyImGui.checkbox("Text2D at mouse (DrawText)", state.text2d)
    state.clip_2d = PyImGui.checkbox("Clip 2D draws to region (Push/PopClipRect)", state.clip_2d)

    PyImGui.spacing()
    ui.section_header("Texture (ImageButton — needs a valid texture path)")
    state.tex_path = PyImGui.input_text("Texture Path", state.tex_path)
    if state.tex_path:
        clicked = casts.safe(lambda: overlay.ImageButton("ov_img", state.tex_path, 48.0, 48.0))
        if clicked:
            ui.text_muted("ImageButton clicked")
    else:
        ui.text_muted("Enter a texture path to render an ImageButton.")


# ---------------------------------------------------------------------------
# Every-frame world/screen draws (known-safe overlay calls, wrapped in BeginDraw/EndDraw)
# ---------------------------------------------------------------------------
def _any_enabled() -> bool:
    return any((
        state.area_rings, state.mark_target, state.line3d_to_target, state.tri3d, state.tri3d_filled,
        state.quad3d, state.quad3d_filled, state.poly3d_filled, state.cube_outline, state.cube_filled,
        state.text3d, state.line2d, state.tri2d, state.tri2d_filled, state.quad2d, state.quad2d_filled,
        state.poly2d, state.poly2d_filled, state.poly2d_relative, state.star2d, state.star2d_filled,
        state.text2d,
    ))


def _render_draws(overlay) -> None:
    if not _any_enabled():
        return

    color = _parse_color(state.color_hex)
    r = state.radius
    th = state.thickness
    segs = max(3, int(state.segments))
    ppos = _player_pos()
    mouse = casts.safe(overlay.GetMouseCoords)

    overlay.BeginDraw()
    try:
        # --- 3D (anchored at player) --- each draw isolated so one bad call can't blank the rest.
        if ppos is not None:
            px, py, pz = ppos
            if state.area_rings:
                for _label, radius, ring_color in _RINGS:
                    _safe_draw("DrawPoly3D(rings)", overlay.DrawPoly3D, px, py, pz, radius=radius, color=ring_color, numsegments=64, thickness=3.0)
            if state.mark_target:
                tpos = _target_pos()
                if tpos is not None:
                    tx, ty, tz = tpos
                    _safe_draw("DrawPoly3D(target)", overlay.DrawPoly3D, tx, ty, tz, radius=72, color=0xFFFF0000, numsegments=32, thickness=5.0)
                    _safe_draw("DrawText3D(target)", overlay.DrawText3D, tx, ty, tz - 130, "TARGET", color=0xFFFF0000, autoZ=False, centered=True, scale=2.0)
            if state.line3d_to_target:
                tpos = _target_pos()
                if tpos is not None:
                    tx, ty, tz = tpos
                    _safe_draw("DrawLine3D", overlay.DrawLine3D, px, py, pz, tx, ty, tz, color=color, thickness=th)
            if state.tri3d:
                p = _ring_points(px, py, 3, r)
                _safe_draw("DrawTriangle3D", overlay.DrawTriangle3D, p[0][0], p[0][1], pz, p[1][0], p[1][1], pz, p[2][0], p[2][1], pz, color=color, thickness=th)
            if state.tri3d_filled:
                p = _ring_points(px, py, 3, r, rot=math.pi)
                _safe_draw("DrawTriangleFilled3D", overlay.DrawTriangleFilled3D, p[0][0], p[0][1], pz, p[1][0], p[1][1], pz, p[2][0], p[2][1], pz, color=color)
            if state.quad3d:
                p = _ring_points(px, py, 4, r, rot=math.pi / 4)
                _safe_draw("DrawQuad3D", overlay.DrawQuad3D, p[0][0], p[0][1], pz, p[1][0], p[1][1], pz, p[2][0], p[2][1], pz, p[3][0], p[3][1], pz, color=color, thickness=th)
            if state.quad3d_filled:
                p = _ring_points(px, py, 4, r * 0.6, rot=math.pi / 4)
                _safe_draw("DrawQuadFilled3D", overlay.DrawQuadFilled3D, p[0][0], p[0][1], pz, p[1][0], p[1][1], pz, p[2][0], p[2][1], pz, p[3][0], p[3][1], pz, color=color)
            if state.poly3d_filled:
                _safe_draw("DrawPolyFilled3D", overlay.DrawPolyFilled3D, px, py, pz, radius=r * 0.5, color=color, numsegments=segs)
            if state.cube_outline:
                _safe_draw("DrawCubeOutline", overlay.DrawCubeOutline, px, py, pz, size=state.cube_size, color=color)
            if state.cube_filled:
                _safe_draw("DrawCubeFilled", overlay.DrawCubeFilled, px, py, pz, size=state.cube_size, color=color)
            if state.text3d:
                _safe_draw("DrawText3D(text)", overlay.DrawText3D, px, py, pz + 150, state.text, color=color, autoZ=False, centered=True, scale=state.text_scale)

        # --- 2D (anchored at mouse cursor) ---
        if mouse is not None:
            mx, my = mouse[0], mouse[1]
            clipped = False
            if state.clip_2d:
                casts.safe(overlay.PushClipRect, mx - r, my - r, mx + r, my + r)
                clipped = True
            try:
                if state.line2d:
                    _safe_draw("DrawLine", overlay.DrawLine, mx - r, my, mx + r, my, color=color, thickness=th)
                if state.tri2d:
                    p = _ring_points(mx, my, 3, r)
                    _safe_draw("DrawTriangle", overlay.DrawTriangle, p[0][0], p[0][1], p[1][0], p[1][1], p[2][0], p[2][1], color=color, thickness=th)
                if state.tri2d_filled:
                    p = _ring_points(mx, my, 3, r * 0.7, rot=math.pi)
                    _safe_draw("DrawTriangleFilled", overlay.DrawTriangleFilled, p[0][0], p[0][1], p[1][0], p[1][1], p[2][0], p[2][1], color=color)
                if state.quad2d:
                    p = _ring_points(mx, my, 4, r, rot=math.pi / 4)
                    _safe_draw("DrawQuad", overlay.DrawQuad, p[0][0], p[0][1], p[1][0], p[1][1], p[2][0], p[2][1], p[3][0], p[3][1], color=color, thickness=th)
                if state.quad2d_filled:
                    p = _ring_points(mx, my, 4, r * 0.6, rot=math.pi / 4)
                    _safe_draw("DrawQuadFilled", overlay.DrawQuadFilled, p[0][0], p[0][1], p[1][0], p[1][1], p[2][0], p[2][1], p[3][0], p[3][1], color=color)
                if state.poly2d:
                    _safe_draw("DrawPoly", overlay.DrawPoly, mx, my, r, color=color, numsegments=segs, thickness=th)
                if state.poly2d_filled:
                    _safe_draw("DrawPolyFilled", overlay.DrawPolyFilled, mx, my, r * 0.5, color=color, numsegments=segs)
                if state.poly2d_relative:
                    _safe_draw("DrawPolyFilledRelative", overlay.DrawPolyFilledRelative, 120, 120, r * 0.4, color=color, numsegments=segs)
                if state.star2d:
                    _safe_draw("DrawStar", overlay.DrawStar, mx, my, state.star_outer, state.star_inner, color=color, points=max(2, int(state.star_points)), thickness=th)
                if state.star2d_filled:
                    _safe_draw("DrawStarFilled", overlay.DrawStarFilled, mx, my, state.star_outer, state.star_inner, color=color, points=max(2, int(state.star_points)))
                if state.text2d:
                    _safe_draw("DrawText", overlay.DrawText, mx, my - r - 20, state.text, color=color, centered=True, scale=state.text_scale)
            finally:
                if clipped:
                    casts.safe(overlay.PopClipRect)
    finally:
        overlay.EndDraw()


# ---------------------------------------------------------------------------
# draw_overlay_view — uniform section entry point
# ---------------------------------------------------------------------------
def draw_overlay_view() -> None:
    overlay = Overlay()
    blocks = build_overlay()
    diagnostics.dump_button(_SECTION, blocks)
    PyImGui.separator()
    if PyImGui.begin_tab_bar("OverlayTabs"):
        if PyImGui.begin_tab_item("Data"):
            ui.draw_blocks(_SECTION, blocks)
            PyImGui.end_tab_item()
        if PyImGui.begin_tab_item("Draw"):
            _draw_controls(overlay)
            PyImGui.end_tab_item()
        PyImGui.end_tab_bar()

    # World/screen draws are emitted every frame (like the prior file) regardless of the active tab.
    _render_draws(overlay)
