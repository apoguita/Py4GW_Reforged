# =============================================================================
# Particle system test — C++ sim, Python config.
# -----------------------------------------------------------------------------
# Creates two emitters at the player: a GEYSER (ballistic, gravity) erupting from
# the ground, and an ORBITAL swirl spiraling up around it. C++ runs the simulation
# and draws them (occluded, additive billboard quads); this script only configures
# and positions them. Drop the script (stop it) and the emitters are freed and stop.
# =============================================================================

import PyImGui
import PyParticles
import PyOverlay

from Py4GWCoreLib.Player import Player

_overlay = PyOverlay.Overlay()

geyser: "PyParticles.ParticleEmitter | None" = None
swirl: "PyParticles.ParticleEmitter | None" = None

state = {
    "color": [1.0, 0.54, 0.17, 1.0],   # rarity color (orange-ish), RGBA
    "geyser_rate": 60.0,
    "geyser_speed": 190.0,
    "geyser_grav": 320.0,
    "geyser_size": 6.0,
    "swirl_rate": 20.0,
    "swirl_radius": 42.0,
    "swirl_spin": 2.2,
    "swirl_size": 5.0,
    "additive": True,
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


def _setup():
    global geyser, swirl
    geyser = PyParticles.create_emitter()
    swirl = PyParticles.create_emitter()
    geyser.config.mode = PyParticles.BALLISTIC
    swirl.config.mode = PyParticles.ORBITAL
    _apply()


def _apply():
    if geyser is None or swirl is None:
        return
    col = _argb(state["color"])
    tail = col & 0x00FFFFFF   # same rgb, alpha 0 -> fades out

    g = geyser.config
    g.rate = state["geyser_rate"]
    g.speed = state["geyser_speed"]; g.speed_var = state["geyser_speed"] * 0.4
    g.spread = 0.5
    g.grav_z = state["geyser_grav"]
    g.life = 1.4; g.life_var = 0.5
    g.size = state["geyser_size"]; g.size_var = state["geyser_size"] * 0.5; g.size_end = 0.0
    g.color = col; g.color_end = tail
    g.hot_frac = 0.5
    g.additive = state["additive"]

    s = swirl.config
    s.rate = state["swirl_rate"]
    s.orbit_radius = state["swirl_radius"]; s.orbit_radius_var = state["swirl_radius"] * 0.3
    s.orbit_spin = state["swirl_spin"]
    s.orbit_rise = 60.0
    s.orbit_height = 300.0
    s.life = 6.0
    s.size = state["swirl_size"]; s.size_end = 0.0
    s.color = col; s.color_end = tail
    s.hot_frac = 0.3
    s.additive = state["additive"]


def _ui():
    s = state
    if not PyImGui.begin("Particle test"):
        PyImGui.end()
        return
    changed = False
    new_col = PyImGui.color_edit4("color", s["color"])
    if new_col != s["color"]:
        s["color"] = new_col; changed = True

    PyImGui.separator()
    PyImGui.text("GEYSER")
    s["geyser_rate"] = PyImGui.slider_float("g rate", s["geyser_rate"], 0.0, 200.0);
    s["geyser_speed"] = PyImGui.slider_float("g speed", s["geyser_speed"], 40.0, 400.0)
    s["geyser_grav"] = PyImGui.slider_float("g gravity", s["geyser_grav"], 0.0, 800.0)
    s["geyser_size"] = PyImGui.slider_float("g size", s["geyser_size"], 1.0, 20.0)

    PyImGui.separator()
    PyImGui.text("SWIRL")
    s["swirl_rate"] = PyImGui.slider_float("s rate", s["swirl_rate"], 0.0, 80.0)
    s["swirl_radius"] = PyImGui.slider_float("s radius", s["swirl_radius"], 5.0, 120.0)
    s["swirl_spin"] = PyImGui.slider_float("s spin", s["swirl_spin"], -6.0, 6.0)
    s["swirl_size"] = PyImGui.slider_float("s size", s["swirl_size"], 1.0, 20.0)

    PyImGui.separator()
    s["additive"] = PyImGui.checkbox("additive", s["additive"])
    try:
        live = (geyser.count() if geyser else 0) + (swirl.count() if swirl else 0)
        PyImGui.text("live particles: %d" % live)
    except Exception:
        pass
    PyImGui.text("status: " + s["status"])
    PyImGui.end()
    # controls change every frame; just re-apply (cheap)
    _apply()


def main():
    global geyser, swirl
    if geyser is None:
        try:
            _setup()
            state["status"] = "emitters created"
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
            return
        z = _ground_z(x, y)
        if geyser is not None and swirl is not None:
            geyser.set_origin(x, y, z)
            swirl.set_origin(x, y, z)
    except Exception as e:
        state["status"] = "no player: %s" % e


if __name__ == "__main__":
    main()
