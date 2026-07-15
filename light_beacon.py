# =============================================================================
# Light beacon — the "simple loot beam" look (ref: lightbeam.gif).
# SEPARATE test; loot_beam.py is left completely untouched.
# -----------------------------------------------------------------------------
# * Beam  : two CROSSED vertical quads (world X/Y) + alpha blend, tapering up.
# * Ground: magenta glow disc + expanding, pulsing rings (animated).
# * Life  : fireflies + spiral-up, from the C++ particle system (PyParticles),
#           each fully tunable.
# Fully instrumented: every knob we can drive is a slider / picker below.
# =============================================================================

import math
from pickle import FALSE

import PyImGui
import PyDXOverlay
import PyParticles
import PyOverlay

from Py4GWCoreLib.Player import Player

renderer = PyDXOverlay.get_overlay()
_overlay = PyOverlay.Overlay()

_fc = 0
# One C++ ParticleEmitter handle per config in state["emitters"] (kept in sync).
_emitters: "list[PyParticles.ParticleEmitter]" = []

# full emitter control surface (grouped for the UI)
EMITTER_GROUPS = [
    ("emit", [("rate", 0.0, 150.0)]),
    ("launch", [("dir_x", -1.0, 1.0), ("dir_y", -1.0, 1.0), ("dir_z", -1.0, 1.0),
                ("speed", 0.0, 400.0), ("speed_var", 0.0, 250.0), ("spread", 0.0, 3.1416)]),
    ("physics", [("grav_x", -400.0, 400.0), ("grav_y", -400.0, 400.0), ("grav_z", -600.0, 600.0),
                 ("drag", 0.0, 5.0), ("turbulence", 0.0, 500.0)]),
    ("orbit", [("orbit_radius", 0.0, 150.0), ("orbit_radius_var", 0.0, 80.0),
               ("orbit_radius_end", -1.0, 150.0), ("orbit_spin", -8.0, 8.0),
               ("orbit_rise", -100.0, 250.0), ("orbit_height", 10.0, 1200.0)]),
    ("shape", [("spawn_radius", 0.0, 200.0), ("radial_speed", -250.0, 250.0), ("stretch", 0.0, 0.15)]),
    ("life / size", [("life", 0.2, 12.0), ("life_var", 0.0, 6.0), ("size", 0.05, 6.0),
                     ("size_var", 0.0, 4.0), ("size_end", 0.0, 8.0), ("hot_frac", 0.0, 1.0)]),
]

DEFAULT_EMITTER = {
    "enabled": False, "mode": 1, "additive": False, "color": [0.73, 0.53, 0.93, 0.8],
    "rate": 20.0, "dir_x": 0.0, "dir_y": 0.0, "dir_z": -1.0, "speed": 80.0, "speed_var": 40.0, "spread": 0.5,
    "grav_x": 0.0, "grav_y": 0.0, "grav_z": 0.0, "drag": 0.0, "turbulence": 0.0,
    "orbit_radius": 40.0, "orbit_radius_var": 15.0, "orbit_radius_end": -1.0, "orbit_spin": 2.0,
    "orbit_rise": 40.0, "orbit_height": 250.0, "spawn_radius": 0.0, "radial_speed": 0.0, "stretch": 0.0,
    "life": 5.0, "life_var": 1.0, "size": 1.0, "size_var": 0.3, "size_end": 0.0, "hot_frac": 0.35,
}


def _emitter(name, overrides=None):
    c = dict(DEFAULT_EMITTER)
    c["color"] = DEFAULT_EMITTER["color"][:]
    c["name"] = name
    if overrides:
        c.update(overrides)
    return c


state = {
    # Beam: crossed quads OR a cone (thin tube). Three colors, vertical gradient
    # bottom -> mid -> top; alpha of each = its opacity. The cone adds a glow halo
    # (a wider, low-alpha additive copy of the core).
    "beam_shape": 1,                         # 0 = crossed quads, 1 = cone
    "beam_quads": 2,                         # crossed-quads mode: number of quads
    "beam_segments": 16,                     # cone mode: sides (roundness)
    "beam_blend": 2,                         # 0 = alpha, 1 = additive, 2 = MAX (colored glow, no white)
    "beam_glow": 0.5,                        # cone glow strength (0 = off)
    "beam_glow_scale": 2.2,                  # cone glow halo width (x core radius)
    "beam_glow_shells": 5,                   # glow softness: nested shells
    "beam_mid_frac": 0.5,                    # height of the MID color stop (0..1)
    "beam_base": [0.73, 0.53, 0.93, 0.80],   # BOTTOM color
    "beam_mid":  [0.51, 0.05, 0.98, 0.40],   # CENTER color
    "beam_top":  [0.16, 0.00, 0.32, 0.20],   # TOP color
    "disc": [0.73, 0.53, 0.93, 0.80],   # magenta ground glow + rings
    "height": 700.0, "base_w": 8.0, "top_w": 3.0, "rows": 10,
    "disc_radius": 46.0, "rings": 2, "ring_speed": 0.757, "ring_thickness": 0.20,
    "ground_lift": 6.0,        # units the disc/rings sit ABOVE the terrain (anti-clip)
    "anchor_mode": False,      # True = beacon stays at a fixed world pos (don't follow player)
    "anchor_x": 0.0, "anchor_y": 0.0, "anchor_set": False,
    "pulse": False,  # True = shimmer the beam + disc alpha (sine wave)
    "ground_additive": False,   # ground glow + rings read better additive
    # Independent particle emitters. Each is its own full config; add/remove freely.
    "emitters": [
        _emitter("Fireflies", {"rate": 25, "orbit_radius": 15, "orbit_radius_var": 15, "orbit_spin": 0.5,
                               "orbit_rise": 22, "orbit_height": 240, "life": 6.0, "size": 0.5, "hot_frac": 0.4}),
        _emitter("Spiral", {"rate": 7, "orbit_radius": 10, "orbit_radius_var": 6, "orbit_spin": 0.5,
                            "orbit_rise": 130, "orbit_height": 560, "life": 6.0, "size": 0.5, "hot_frac": 0.35}),
    ],
    "status": "idle",
}


def _argb(rgba, af=1.0):
    r = max(0, min(255, int(rgba[0] * 255)))
    g = max(0, min(255, int(rgba[1] * 255)))
    b = max(0, min(255, int(rgba[2] * 255)))
    a = max(0, min(255, int(rgba[3] * 255 * af)))
    return (a << 24) | (r << 16) | (g << 8) | b


def _ground_z(x, y):
    # FindZ now resolves the topmost surface across ALL planes by default
    # (multi_plane), so a fixed point stays on its slope/bridge regardless of the
    # player's plane. No extra call needed.
    try:
        return _overlay.FindZ(x, y)
    except Exception:
        return 0.0


def _beam(x, y, gz, height, base_w, top_w, base_rgba, mid_rgba, top_rgba,
          alpha_mul, num_quads, mid_frac):
    """N crossed vertical quads, evenly rotated around the vertical axis (2 = an X,
    3 = a 6-pointed star from above, etc). Each quad has a 3-STOP vertical gradient:
    base color at the bottom, mid color at height `mid_frac`, top color at the top.
    The GPU interpolates between the stops. Plain alpha blend."""
    hb, ht = base_w * 0.5, top_w * 0.5
    hm = hb + (ht - hb) * mid_frac                    # width at the mid stop
    # (height fraction, half-width, packed color) from bottom -> mid -> top
    levels = (
        (0.0,      hb, _argb(base_rgba, base_rgba[3] * alpha_mul)),
        (mid_frac, hm, _argb(mid_rgba,  mid_rgba[3]  * alpha_mul)),
        (1.0,      ht, _argb(top_rgba,  top_rgba[3]  * alpha_mul)),
    )
    verts = []
    n = max(1, int(num_quads))
    for i in range(n):
        theta = i * math.pi / n                       # planes spread over 180 deg
        ax, ay = math.cos(theta), math.sin(theta)
        rows = [((x - ax * half, y - ay * half, gz - height * f, col),
                 (x + ax * half, y + ay * half, gz - height * f, col))
                for f, half, col in levels]
        for r in range(len(rows) - 1):
            (l0, r0), (l1, r1) = rows[r], rows[r + 1]
            verts.extend([l0, r0, r1, l0, r1, l1])
    return verts


def _cone(x, y, gz, height, base_r, top_r, rgbas, alpha_mul, mid_frac, segments):
    """Open frustum tube (a thin cone) around the vertical axis, `segments` sides,
    with a 3-stop vertical gradient (rgbas = (base, mid, top)). Draw the strong core
    with this in alpha, then a wider copy in additive for the glow halo."""
    base_c = _argb(rgbas[0], rgbas[0][3] * alpha_mul)
    mid_c = _argb(rgbas[1], rgbas[1][3] * alpha_mul)
    top_c = _argb(rgbas[2], rgbas[2][3] * alpha_mul)
    hm_r = base_r + (top_r - base_r) * mid_frac        # radius at the mid stop
    levels = ((0.0, base_r, base_c), (mid_frac, hm_r, mid_c), (1.0, top_r, top_c))
    seg = max(3, int(segments))
    ring = [(math.cos(k / seg * math.tau), math.sin(k / seg * math.tau)) for k in range(seg + 1)]
    verts = []
    for li in range(len(levels) - 1):
        f0, r0, c0 = levels[li]
        f1, r1, c1 = levels[li + 1]
        z0, z1 = gz - height * f0, gz - height * f1
        for k in range(seg):
            cx0, cy0 = ring[k]
            cx1, cy1 = ring[k + 1]
            b0 = (x + cx0 * r0, y + cy0 * r0, z0, c0)
            b1 = (x + cx1 * r0, y + cy1 * r0, z0, c0)
            t0 = (x + cx0 * r1, y + cy0 * r1, z1, c1)
            t1 = (x + cx1 * r1, y + cy1 * r1, z1, c1)
            verts.extend([b0, b1, t1, b0, t1, t0])
    return verts


GROUND_SAMPLES = 36
_profile_cache: dict = {"key": None, "profile": None}


def _ground_profile(x, y, radius, lift):
    """Sample the ground at GROUND_SAMPLES points on a circle around the beacon and
    return their lifted Zs (indexed by angle). ONE FindZBatch call for the whole
    ring (falls back to GROUND_SAMPLES individual FindZ). This captures the terrain
    slope cheaply, independent of the disc/ring segment count.

    CACHED: the profile is re-sampled only when the beacon moves to a new ~8-unit
    cell (or radius/lift changes). A fixed/anchored beacon samples the ground ONCE
    and reuses it every frame; a moving one re-samples a few times per second."""
    key = (round(x / 8.0), round(y / 8.0), round(radius), round(lift))
    if _profile_cache["key"] == key and _profile_cache["profile"] is not None:
        return _profile_cache["profile"]
    pts = [(x + math.cos(i / GROUND_SAMPLES * math.tau) * radius,
            y + math.sin(i / GROUND_SAMPLES * math.tau) * radius) for i in range(GROUND_SAMPLES)]
    try:
        zs = _overlay.FindZBatch(pts, True)
    except Exception:
        zs = [_ground_z(px, py) for (px, py) in pts]
    profile = [z - lift for z in zs]
    _profile_cache["key"] = key
    _profile_cache["profile"] = profile
    return profile


def _prof_z(profile, ang):
    """Ground Z from the profile at the nearest sampled angle."""
    return profile[int(round(ang / math.tau * len(profile))) % len(profile)]


def _base_disc(x, y, cz, profile, radius, rgba, alpha_mul, segments=36):
    """Glow disc; rim follows the terrain via the shared angular profile, center at
    the single center sample cz."""
    cc = _argb(rgba, rgba[3] * 0.8 * alpha_mul)
    ec = _argb(rgba, 0.0)
    center = (x, y, cz, cc)
    rim = []
    for i in range(segments + 1):
        a = i / segments * math.tau
        rim.append((x + math.cos(a) * radius, y + math.sin(a) * radius, _prof_z(profile, a), ec))
    verts = []
    for i in range(segments):
        verts.extend([center, rim[i], rim[i + 1]])
    return verts


def _ring(x, y, profile, r, thickness, rgba, alpha, segments=44):
    """Soft annulus following the terrain via the shared angular profile."""
    mc = _argb(rgba, rgba[3] * alpha)
    ec = _argb(rgba, 0.0)
    ri, ro = max(0.0, r - thickness), r + thickness
    inner, mid, outer = [], [], []
    for i in range(segments + 1):
        a = (i / segments) * math.tau
        ca, sa = math.cos(a), math.sin(a)
        z = _prof_z(profile, a)
        inner.append((x + ca * ri, y + sa * ri, z, ec))
        mid.append((x + ca * r, y + sa * r, z, mc))
        outer.append((x + ca * ro, y + sa * ro, z, ec))
    verts = []
    for i in range(segments):
        verts.extend([inner[i], mid[i], mid[i + 1], inner[i], mid[i + 1], inner[i + 1]])
        verts.extend([mid[i], outer[i], outer[i + 1], mid[i], outer[i + 1], mid[i + 1]])
    return verts


def _apply_emitter(em, cfg):
    c = em.config
    for _, fields in EMITTER_GROUPS:
        for key, _mn, _mx in fields:
            setattr(c, key, float(cfg[key]))
    c.mode = int(cfg["mode"])
    c.additive = bool(cfg["additive"])
    c.enabled = bool(cfg["enabled"])
    col = _argb(cfg["color"])
    c.color = col
    c.color_end = col & 0x00FFFFFF   # fade to transparent, same rgb


def _beam_draw(verts, blend):
    """Draw beam geometry with the chosen blend. 2 = MAX (bright, colored, can't
    exceed the source color so it never washes to white); 1 = additive; 0 = alpha.
    MAX needs draw_shaded_3d_max (rebuilt DLL); falls back to alpha if absent."""
    if blend == 2:
        try:
            renderer.draw_shaded_3d_max(verts, True)
            return
        except AttributeError:
            pass
    renderer.draw_shaded_3d(verts, blend == 1, True)


def _draw(x, y):
    global _fc
    _fc += 1
    s = state
    p = _fc * 0.07
    beam_a = (0.88 + 0.12 * math.sin(p * 2.0)) if s["pulse"] else 1.0
    disc_a = (0.85 + 0.15 * math.sin(p * 1.3)) if s["pulse"] else 1.0
    gz = _ground_z(x, y)
    gnd_add = s["ground_additive"]

    cols = (s["beam_base"], s["beam_mid"], s["beam_top"])
    blend = int(s["beam_blend"])
    # Build ALL beam geometry into one vertex list -> ONE draw call (was up to 6).
    # Triangles render in buffer order, so appending shells (widest->inner) then the
    # core keeps the exact same layering the separate calls had.
    beam_verts = []
    if s["beam_shape"] == 1:
        br, tr = s["base_w"] * 0.5, s["top_w"] * 0.5
        seg, mf = int(s["beam_segments"]), s["beam_mid_frac"]
        if s["beam_glow"] > 0.001:
            gs = s["beam_glow_scale"]
            shells = max(1, int(s["beam_glow_shells"]))
            for si in range(shells, 0, -1):
                t = si / shells                          # 1 = outer edge .. inner
                rs = 1.0 + (gs - 1.0) * t                # radius scale for this shell
                a = s["beam_glow"] * (1.0 - t) * (1.0 - t)   # 0 at outer, grows inward
                beam_verts += _cone(x, y, gz, s["height"], br * rs, tr * rs, cols, beam_a * a, mf, seg)
        beam_verts += _cone(x, y, gz, s["height"], br, tr, cols, beam_a, mf, seg)
    else:
        beam_verts = _beam(x, y, gz, s["height"], s["base_w"], s["top_w"],
                           s["beam_base"], s["beam_mid"], s["beam_top"],
                           beam_a, int(s["beam_quads"]), s["beam_mid_frac"])
    _beam_draw(beam_verts, blend)

    # Ground: one 36-point angular profile per frame (one FindZBatch call), shared
    # by the disc and all rings -> conforms to the terrain slope at a fixed cost.
    lift = s["ground_lift"]
    zc = gz - lift
    R = s["disc_radius"]
    profile = _ground_profile(x, y, R, lift)
    renderer.draw_shaded_3d(_base_disc(x, y, zc, profile, R, s["disc"], disc_a), gnd_add, True)

    nrings = max(0, int(s["rings"]))
    for k in range(nrings):
        ph = (_fc * 0.012 * s["ring_speed"] + k / max(1, nrings)) % 1.0
        rr = R * (0.25 + 1.1 * ph)
        ra = (1.0 - ph) * 0.9
        if ra > 0.02:
            renderer.draw_shaded_3d(_ring(x, y, profile, rr, R * s["ring_thickness"], s["disc"], ra), gnd_add, True)

    for cfg, em in zip(s["emitters"], _emitters):
        _apply_emitter(em, cfg)
        em.set_origin(x, y, gz)


def _emitter_ui(idx, cfg):
    """One fully-independent emitter's controls. Returns True if 'remove' clicked.
    All widget IDs are suffixed with the index so emitters never collide, even if
    two share a name."""
    sfx = "##em%d" % idx
    if not PyImGui.collapsing_header("%s%s" % (cfg.get("name", "Emitter"), sfx)):
        return False
    remove = PyImGui.button("remove" + sfx)
    cfg["enabled"] = PyImGui.checkbox("enabled" + sfx, cfg["enabled"])
    PyImGui.same_line(0, -1)
    cfg["additive"] = PyImGui.checkbox("additive" + sfx, cfg["additive"])
    cfg["mode"] = PyImGui.combo("mode" + sfx, int(cfg["mode"]), ["ballistic", "orbital"])
    cfg["color"] = PyImGui.color_edit4("color" + sfx, cfg["color"])
    for glabel, fields in EMITTER_GROUPS:
        PyImGui.text("- " + glabel)
        for key, mn, mx in fields:
            cfg[key] = PyImGui.slider_float(key + sfx, float(cfg[key]), mn, mx)
    return remove


def _ui():
    s = state
    if not PyImGui.begin("Light beacon"):
        PyImGui.end()
        return
    live = 0
    for em in _emitters:
        try:
            live += em.count()
        except Exception:
            pass
    PyImGui.text("status: %s   live particles: %d" % (s["status"], live))

    # anchor: drop the beacon at a fixed spot so you can walk around and view it
    was_anchored = s["anchor_mode"]
    s["anchor_mode"] = PyImGui.checkbox("anchor here (don't follow player)", s["anchor_mode"])
    if s["anchor_mode"] and not was_anchored:   # ticking on drops the anchor here
        try:
            s["anchor_x"], s["anchor_y"] = Player.GetXY()
            s["anchor_set"] = True
        except Exception:
            pass
    if PyImGui.button("re-anchor to my position"):
        try:
            s["anchor_x"], s["anchor_y"] = Player.GetXY()
            s["anchor_set"] = True
        except Exception:
            pass
    PyImGui.separator()

    if PyImGui.collapsing_header("Beam"):
        s["beam_shape"] = PyImGui.combo("shape", int(s["beam_shape"]), ["crossed quads", "cone (glow)"])
        s["beam_blend"] = PyImGui.combo("blend", int(s["beam_blend"]), ["alpha", "additive", "max (colored glow)"])
        if s["beam_shape"] == 1:
            s["beam_segments"] = PyImGui.slider_int("cone sides", int(s["beam_segments"]), 3, 48)
            s["beam_glow"] = PyImGui.slider_float("glow strength", s["beam_glow"], 0.0, 1.0)
            s["beam_glow_scale"] = PyImGui.slider_float("glow width (x radius)", s["beam_glow_scale"], 1.0, 5.0)
            s["beam_glow_shells"] = PyImGui.slider_int("glow softness (shells)", int(s["beam_glow_shells"]), 1, 10)
        else:
            s["beam_quads"] = PyImGui.slider_int("crossed quads", int(s["beam_quads"]), 1, 8)
        s["beam_base"] = PyImGui.color_edit4("bottom color (alpha = opacity)", s["beam_base"])
        s["beam_mid"] = PyImGui.color_edit4("center color (alpha = opacity)", s["beam_mid"])
        s["beam_top"] = PyImGui.color_edit4("top color (alpha = opacity)", s["beam_top"])
        s["beam_mid_frac"] = PyImGui.slider_float("center height", s["beam_mid_frac"], 0.05, 0.95)
        s["height"] = PyImGui.slider_float("height", s["height"], 100.0, 1400.0)
        s["base_w"] = PyImGui.slider_float("base width", s["base_w"], 1.0, 40.0)
        s["top_w"] = PyImGui.slider_float("top width", s["top_w"], 0.5, 40.0)

    if PyImGui.collapsing_header("Ground (disc + rings)"):
        s["disc"] = PyImGui.color_edit4("ground color", s["disc"])
        s["disc_radius"] = PyImGui.slider_float("disc radius", s["disc_radius"], 5.0, 150.0)
        s["ground_lift"] = PyImGui.slider_float("ground lift (above terrain)", s["ground_lift"], 0.0, 40.0)
        s["rings"] = PyImGui.slider_int("ring count", int(s["rings"]), 0, 5)
        s["ring_speed"] = PyImGui.slider_float("ring speed", s["ring_speed"], 0.1, 4.0)
        s["ring_thickness"] = PyImGui.slider_float("ring thickness (x radius)", s["ring_thickness"], 0.02, 0.4)

    PyImGui.separator()
    PyImGui.text("Particle emitters (%d)" % len(s["emitters"]))
    if PyImGui.button("+ add emitter") and len(s["emitters"]) < 12:
        s["emitters"].append(_emitter("Emitter %d" % (len(s["emitters"]) + 1)))
    remove_idx = -1
    for i, cfg in enumerate(s["emitters"]):
        if _emitter_ui(i, cfg):
            remove_idx = i
    if remove_idx >= 0:
        s["emitters"].pop(remove_idx)

    if PyImGui.collapsing_header("Global"):
        s["pulse"] = PyImGui.checkbox("pulse / shimmer", s["pulse"])
        s["ground_additive"] = PyImGui.checkbox("ground additive", s["ground_additive"])
    PyImGui.end()


def _sync_emitters():
    """Keep one C++ emitter handle per config in state["emitters"]. Dropping a handle
    frees its effect (shared_ptr), so add/remove in the UI just works."""
    n = len(state["emitters"])
    while len(_emitters) < n:
        _emitters.append(PyParticles.create_emitter())
    while len(_emitters) > n:
        old = _emitters.pop()
        try:
            old.clear()
        except Exception:
            pass


def main():
    try:
        _sync_emitters()
    except AttributeError:
        state["status"] = "PyParticles missing - rebuild the DLL"
        _ui()
        return
    except Exception as e:
        state["status"] = "setup err: %s" % e
        return

    _ui()
    try:
        x, y = Player.GetXY()
        if x == 0 and y == 0:
            state["status"] = "not in game"
            return
        if state["anchor_mode"] and state["anchor_set"]:
            x, y = state["anchor_x"], state["anchor_y"]
            state["status"] = "anchored"
        else:
            state["status"] = "following player"
        _draw(x, y)
    except AttributeError:
        state["status"] = "draw_shaded_3d missing - rebuild the DLL"
    except Exception as e:
        state["status"] = "err: %s" % e


if __name__ == "__main__":
    main()
