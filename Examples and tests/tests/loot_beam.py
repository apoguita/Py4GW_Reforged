# =============================================================================
# Loot beam — the complete effect, composed on our primitives.
# -----------------------------------------------------------------------------
# Reusable LootBeam: a laser column + base hotspot (immediate shaded geometry via
# DXOverlay.draw_shaded_3d) PLUS a geyser and an orbital swirl (the C++ particle
# system, PyParticles). C++ runs the particle sim; Python builds the static
# geometry and configures everything. Hold a LootBeam instance to keep it alive;
# drop it (or stop the script) and its emitters free themselves.
# =============================================================================

import math

import PyImGui
import PyDXOverlay
import PyParticles
import PyCamera
import PyOverlay

from Py4GWCoreLib.Player import Player

renderer = PyDXOverlay.get_overlay()
_overlay = PyOverlay.Overlay()


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


def _camera_right_2d():
    """Ground-plane axis perpendicular to the camera forward (billboard the column)."""
    try:
        cam = PyCamera.PyCamera()
        fx = cam.look_at_target.x - cam.position.x
        fy = cam.look_at_target.y - cam.position.y
    except Exception:
        return (1.0, 0.0)
    length = math.hypot(fx, fy)
    if length < 1e-4:
        return (1.0, 0.0)
    return (fy / length, -fx / length)


def _col(argb, af):
    a = max(0, min(255, int(((argb >> 24) & 0xFF) * af)))
    return (a << 24) | (argb & 0x00FFFFFF)


def _build_column(x, y, gz, height, width, argb):
    """Laser column as a camera-facing billboard: a soft colored BLOOM (edges + top
    fade to transparent) plus a thin near-white CORE. Returns (x,y,z,argb) triangles."""
    rx, ry = _camera_right_2d()
    top = gz - height
    solid = gz - height * 0.22
    verts = []

    def grid(half, color_of):
        # 3 columns x 3 rows (base, solid, top); color_of(col_factor, row_factor)
        cols = [-1.0, 0.0, 1.0]
        rows_z = [gz, solid, top]
        row_v = [1.0, 1.0, 0.0]
        col_h = [0.0, 1.0, 0.0]
        g = []
        for r, z in enumerate(rows_z):
            line = []
            for c, cc in enumerate(cols):
                px = x + rx * half * cc
                py = y + ry * half * cc
                line.append((px, py, z, color_of(col_h[c] * row_v[r])))
            g.append(line)
        out = []
        for r in range(2):
            for c in range(2):
                a, b = g[r][c], g[r][c + 1]
                d, e = g[r + 1][c], g[r + 1][c + 1]
                out.extend([a, b, e, a, e, d])
        return out

    # bloom (wide, rarity color) then core (thin, white-hot)
    verts += grid(width * 0.5, lambda f: _col(argb, f * 0.85))
    verts += grid(width * 0.16, lambda f: _col(0xFFFFFFFF, f))
    return verts


def _build_hotspot(x, y, gz, radius, argb, segments=24):
    """Flattened glow disc where the beam meets the ground: a triangle fan, center
    opaque -> rim transparent."""
    verts = []
    center = (x, y, gz, _col(argb, 0.9))
    rim = []
    for i in range(segments + 1):
        a = (i / segments) * math.tau
        rim.append((x + math.cos(a) * radius, y + math.sin(a) * radius, gz, _col(argb, 0.0)))
    for i in range(segments):
        verts.extend([center, rim[i], rim[i + 1]])
    return verts


class LootBeam:
    """One complete loot beam: column + hotspot (drawn each frame) + geyser + swirl
    (C++ particle emitters). Keep the instance alive to keep the effect."""

    def __init__(self):
        self.geyser = PyParticles.create_emitter()
        self.swirl = PyParticles.create_emitter()
        self.geyser.config.mode = PyParticles.BALLISTIC
        self.swirl.config.mode = PyParticles.ORBITAL
        self.height = 300.0
        self.width = 26.0
        self.color = 0xFFFF8A3C
        self.additive = True
        self.configure()

    def configure(self):
        col = self.color
        tail = col & 0x00FFFFFF
        g = self.geyser.config
        g.rate = 55.0; g.speed = 190.0; g.speed_var = 90.0; g.spread = 0.5
        g.grav_z = 340.0; g.life = 1.3; g.life_var = 0.4
        g.size = 6.0; g.size_var = 3.0; g.size_end = 0.0
        g.color = col; g.color_end = tail; g.hot_frac = 0.5; g.additive = self.additive
        s = self.swirl.config
        s.rate = 18.0; s.orbit_radius = self.width * 1.6; s.orbit_radius_var = self.width * 0.5
        s.orbit_spin = 2.2; s.orbit_rise = 70.0; s.orbit_height = self.height
        s.life = 6.0; s.size = 5.0; s.size_end = 0.0
        s.color = col; s.color_end = tail; s.hot_frac = 0.3; s.additive = self.additive

    def draw(self, x, y):
        gz = _ground_z(x, y)
        # static geometry every frame (immediate, occluded)
        renderer.draw_shaded_3d(_build_column(x, y, gz, self.height, self.width, self.color),
                                self.additive, True)
        renderer.draw_shaded_3d(_build_hotspot(x, y, gz, self.width * 1.4, self.color),
                                self.additive, True)
        # particles follow the drop
        self.geyser.set_origin(x, y, gz)
        self.swirl.set_origin(x, y, gz)


beam = None
ui = {"color": [1.0, 0.54, 0.17, 1.0], "height": 300.0, "width": 26.0, "additive": True, "status": "idle"}


def _draw_ui():
    if not PyImGui.begin("Loot beam"):
        PyImGui.end()
        return
    ui["color"] = PyImGui.color_edit4("color", ui["color"])
    ui["height"] = PyImGui.slider_float("height", ui["height"], 80.0, 800.0)
    ui["width"] = PyImGui.slider_float("width", ui["width"], 6.0, 120.0)
    ui["additive"] = PyImGui.checkbox("additive", ui["additive"])
    PyImGui.text("status: " + ui["status"])
    PyImGui.end()


def main():
    global beam
    if beam is None:
        try:
            beam = LootBeam()
            ui["status"] = "beam created"
        except AttributeError:
            ui["status"] = "PyParticles / draw_shaded_3d missing - rebuild the DLL"
            _draw_ui()
            return
        except Exception as e:
            ui["status"] = "setup err: %s" % e
            return

    _draw_ui()
    beam.color = _argb(ui["color"])
    beam.height = ui["height"]
    beam.width = ui["width"]
    beam.additive = ui["additive"]
    beam.configure()

    try:
        x, y = Player.GetXY()
        if x == 0 and y == 0:
            return
        beam.draw(x, y)
    except Exception as e:
        ui["status"] = "no player: %s" % e


if __name__ == "__main__":
    main()
