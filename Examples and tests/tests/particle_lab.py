# =============================================================================
# Particle Lab — explore the whole effect universe.
# -----------------------------------------------------------------------------
# A preset LIBRARY of distinct effects (geyser, explosion, nova, vortex, fire,
# smoke, rain, snow, sparks, fireflies, halo, portal, ...) plus FULL control over
# every emitter property. C++ runs the sim; this only configures.
#
#   * Pick a preset -> it loads into the active slot.
#   * Every knob is a slider / color picker (grouped in collapsing headers).
#   * Up to 6 slots -> view ONE effect alone, or add slots to MIX them.
#   * All slots emit at the player (per-slot height offset for rain/snow).
# =============================================================================

import PyImGui
import PyParticles
import PyOverlay

from Py4GWCoreLib.Player import Player

_overlay = PyOverlay.Overlay()
MAX_SLOTS = 6


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


# grouped float sliders: (group_label, [(field, min, max), ...])
GROUPS = [
    ("Emission", [("rate", 0.0, 400.0)]),
    ("Launch", [("dir_x", -1.0, 1.0), ("dir_y", -1.0, 1.0), ("dir_z", -1.0, 1.0),
                ("speed", 0.0, 500.0), ("speed_var", 0.0, 300.0), ("spread", 0.0, 3.1416)]),
    ("Physics", [("grav_x", -500.0, 500.0), ("grav_y", -500.0, 500.0), ("grav_z", -800.0, 800.0),
                 ("drag", 0.0, 5.0), ("turbulence", 0.0, 600.0)]),
    ("Orbital", [("orbit_radius", 0.0, 200.0), ("orbit_radius_var", 0.0, 100.0),
                 ("orbit_radius_end", -1.0, 200.0), ("orbit_spin", -8.0, 8.0),
                 ("orbit_rise", -150.0, 250.0), ("orbit_height", 10.0, 600.0)]),
    ("Shape / streak", [("spawn_radius", 0.0, 250.0), ("radial_speed", -300.0, 300.0),
                        ("stretch", 0.0, 0.2)]),
    ("Lifetime", [("life", 0.1, 12.0), ("life_var", 0.0, 6.0)]),
    ("Appearance", [("hot_frac", 0.0, 1.0)]),  # size lives up top (it's the one you reach for most)
]

# full default config (every field the UI touches)
DEFAULTS = {
    "mode": 0, "additive": True, "max_particles": 800, "origin_dz": 0.0, "burst": 0,
    "rate": 40.0,
    "dir_x": 0.0, "dir_y": 0.0, "dir_z": -1.0, "speed": 150.0, "speed_var": 60.0, "spread": 0.5,
    "grav_x": 0.0, "grav_y": 0.0, "grav_z": 280.0, "drag": 0.0, "turbulence": 0.0,
    "orbit_radius": 30.0, "orbit_radius_var": 12.0, "orbit_radius_end": -1.0,
    "orbit_spin": 2.0, "orbit_rise": 40.0, "orbit_height": 260.0,
    "spawn_radius": 0.0, "radial_speed": 0.0, "stretch": 0.0,
    "life": 1.5, "life_var": 0.5,
    "size": 1.0, "size_var": 0.5, "size_end": 0.0, "hot_frac": 0.4,
    "color": [1.0, 0.55, 0.17, 1.0], "color_end": [1.0, 0.55, 0.17, 0.0],
}

B, O = 0, 1  # modes
ORANGE = [1.0, 0.55, 0.17]
BLUE = [0.35, 0.6, 1.0]
PURPLE = [0.7, 0.35, 1.0]
GREEN = [0.3, 0.9, 0.4]
WHITE = [0.9, 0.95, 1.0]
RED = [1.0, 0.35, 0.12]

# each preset is a sparse override of DEFAULTS
# sizes are in WORLD units (billboard is 2*size wide) — kept small vs. the geometry.
PRESETS = {
    "geyser":    {"mode": B, "rate": 60, "speed": 190, "speed_var": 90, "spread": 0.5, "grav_z": 340,
                  "life": 1.3, "size": 2.0, "size_end": 0.0, "hot_frac": 0.5, "color": ORANGE + [1], "color_end": ORANGE + [0]},
    "fountain":  {"mode": B, "rate": 100, "speed": 150, "speed_var": 40, "spread": 0.9, "grav_z": 320,
                  "life": 1.6, "size": 1.8, "color": BLUE + [1], "color_end": BLUE + [0]},
    "explosion": {"mode": B, "rate": 0, "burst": 150, "spread": 3.14, "speed": 260, "speed_var": 110,
                  "grav_z": 200, "drag": 1.6, "life": 1.0, "size": 1.8, "stretch": 0.015, "hot_frac": 0.6,
                  "color": ORANGE + [1], "color_end": RED + [0]},
    "nova":      {"mode": B, "rate": 0, "burst": 120, "speed": 30, "spread": 0.12, "radial_speed": 230,
                  "grav_z": 0, "life": 0.9, "size": 2.2, "spawn_radius": 6, "hot_frac": 0.4,
                  "color": BLUE + [1], "color_end": BLUE + [0]},
    "vortex":    {"mode": O, "rate": 45, "orbit_radius": 65, "orbit_radius_end": 6, "orbit_spin": 4.5,
                  "orbit_rise": 95, "orbit_height": 320, "life": 4, "size": 1.4,
                  "color": PURPLE + [1], "color_end": PURPLE + [0]},
    "bloom":     {"mode": O, "rate": 40, "orbit_radius": 8, "orbit_radius_end": 85, "orbit_spin": 2,
                  "orbit_rise": 30, "orbit_height": 200, "life": 3, "size": 1.4,
                  "color": GREEN + [1], "color_end": GREEN + [0]},
    "halo":      {"mode": O, "rate": 55, "orbit_radius": 55, "orbit_radius_end": 55, "orbit_spin": 1.6,
                  "orbit_rise": 0, "orbit_height": 18, "life": 4, "size": 1.5,
                  "color": ORANGE + [1], "color_end": ORANGE + [0]},
    "swirl":     {"mode": O, "rate": 22, "orbit_radius": 42, "orbit_spin": 2.2, "orbit_rise": 70,
                  "orbit_height": 300, "life": 6, "size": 1.8, "color": ORANGE + [1], "color_end": ORANGE + [0]},
    "portal":    {"mode": O, "rate": 70, "orbit_radius": 60, "orbit_radius_end": 60, "orbit_spin": 4.5,
                  "orbit_rise": 6, "orbit_height": 42, "life": 3, "size": 1.8,
                  "color": PURPLE + [1], "color_end": PURPLE + [0]},
    "fire":      {"mode": B, "rate": 90, "speed": 70, "speed_var": 30, "spread": 0.5, "grav_z": -70,
                  "turbulence": 70, "life": 0.9, "size": 2.6, "size_end": 0.5, "hot_frac": 0.5,
                  "color": [1.0, 0.8, 0.2, 1.0], "color_end": RED + [0]},
    "smoke":     {"mode": B, "additive": False, "rate": 30, "speed": 40, "spread": 0.4, "grav_z": -25,
                  "turbulence": 45, "life": 3, "size": 3.0, "size_end": 9.0, "hot_frac": 0.0,
                  "color": [0.5, 0.5, 0.55, 0.5], "color_end": [0.4, 0.4, 0.45, 0.0]},
    "sparks":    {"mode": B, "rate": 0, "burst": 45, "spread": 3.14, "speed": 230, "grav_z": 420,
                  "drag": 1.0, "life": 0.8, "size": 0.9, "stretch": 0.04, "hot_frac": 0.7,
                  "color": [1.0, 0.9, 0.4, 1.0], "color_end": ORANGE + [0]},
    "rain":      {"mode": B, "additive": False, "origin_dz": 420, "spawn_radius": 130, "dir_z": 1.0,
                  "speed": 260, "spread": 0.04, "grav_z": 200, "life": 2.0, "size": 0.8, "stretch": 0.025,
                  "hot_frac": 0.0, "color": [0.6, 0.75, 1.0, 0.7], "color_end": [0.6, 0.75, 1.0, 0.4]},
    "snow":      {"mode": B, "additive": False, "origin_dz": 420, "spawn_radius": 140, "dir_z": 1.0,
                  "speed": 42, "speed_var": 18, "spread": 0.5, "grav_z": 30, "turbulence": 35,
                  "life": 5, "size": 1.1, "hot_frac": 0.0, "color": WHITE + [0.9], "color_end": WHITE + [0.2]},
    "fireflies": {"mode": O, "rate": 8, "orbit_radius": 80, "orbit_radius_var": 40, "orbit_spin": 0.6,
                  "orbit_rise": 20, "orbit_height": 200, "life": 6, "size": 1.1, "hot_frac": 0.3,
                  "color": [0.7, 1.0, 0.4, 1.0], "color_end": [0.7, 1.0, 0.4, 0.0]},
    "dust":      {"mode": B, "additive": False, "rate": 25, "speed": 15, "spread": 1.5, "grav_z": 6,
                  "turbulence": 22, "life": 5, "size": 0.9, "spawn_radius": 40, "hot_frac": 0.0,
                  "color": [0.8, 0.72, 0.55, 0.4], "color_end": [0.8, 0.72, 0.55, 0.0]},
}
PRESET_NAMES = list(PRESETS.keys())


def _make_slot(preset="geyser"):
    cfg = dict(DEFAULTS)
    cfg.update({k: (v[:] if isinstance(v, list) else v) for k, v in PRESETS[preset].items()})
    em = PyParticles.create_emitter()
    return {"em": em, "cfg": cfg, "preset": preset, "on": True}


def _apply(slot):
    c = slot["em"].config
    cfg = slot["cfg"]
    for _, fields in GROUPS:
        for key, _mn, _mx in fields:
            setattr(c, key, float(cfg[key]))
    # size lives outside GROUPS, so apply it explicitly (this was the "slider does nothing" bug)
    c.size = float(cfg["size"])
    c.size_var = float(cfg["size_var"])
    c.size_end = float(cfg["size_end"])
    c.mode = int(cfg["mode"])
    c.additive = bool(cfg["additive"])
    c.max_particles = int(cfg["max_particles"])
    c.color = _argb(cfg["color"])
    c.color_end = _argb(cfg["color_end"])
    c.enabled = bool(slot["on"])


slots = []
active = 0
view_solo = True   # SOLO: show only the selected slot. Toggle "mix" to combine them.
status = "idle"


def _controls(slot):
    cfg = slot["cfg"]
    # preset picker
    cur = PRESET_NAMES.index(slot["preset"]) if slot["preset"] in PRESET_NAMES else 0
    sel = PyImGui.combo("preset", cur, PRESET_NAMES)
    if sel != cur:
        slot["preset"] = PRESET_NAMES[sel]
        new = dict(DEFAULTS)
        new.update({k: (v[:] if isinstance(v, list) else v) for k, v in PRESETS[slot["preset"]].items()})
        slot["cfg"] = cfg = new

    slot["on"] = PyImGui.checkbox("enabled", slot["on"])
    PyImGui.same_line(0, -1)
    cfg["additive"] = PyImGui.checkbox("additive", cfg["additive"])
    cfg["mode"] = PyImGui.combo("mode", int(cfg["mode"]), ["ballistic", "orbital"])
    cfg["max_particles"] = PyImGui.slider_int("max_particles", int(cfg["max_particles"]), 10, 3000)
    cfg["origin_dz"] = PyImGui.slider_float("spawn height (rain/snow)", cfg["origin_dz"], 0.0, 700.0)

    PyImGui.separator()
    PyImGui.text("SIZE  (world units; the billboard is 2x this - keep it small)")
    cfg["size"] = PyImGui.slider_float("size", float(cfg["size"]), 0.05, 6.0)
    cfg["size_var"] = PyImGui.slider_float("size variance", float(cfg["size_var"]), 0.0, 4.0)
    cfg["size_end"] = PyImGui.slider_float("size at end of life", float(cfg["size_end"]), 0.0, 10.0)
    if PyImGui.button("burst 60"):
        try:
            slot["em"].emit(60)
        except Exception:
            pass

    PyImGui.separator()
    cfg["color"] = PyImGui.color_edit4("color (start)", cfg["color"])
    cfg["color_end"] = PyImGui.color_edit4("color (end)", cfg["color_end"])

    for label, fields in GROUPS:
        if PyImGui.collapsing_header(label):
            for key, mn, mx in fields:
                cfg[key] = PyImGui.slider_float(key, float(cfg[key]), mn, mx)


def _ui():
    global active, view_solo
    if not PyImGui.begin("Particle Lab"):
        PyImGui.end()
        return
    # SOLO = only the selected slot draws (see each effect on its own); untick to MIX.
    view_solo = PyImGui.checkbox("SOLO - show only the selected slot (untick = mix all)", view_solo)
    # slot bar
    labels = ["%d:%s%s" % (i, s["preset"], "" if s["on"] else "*") for i, s in enumerate(slots)]
    active = PyImGui.combo("slot", min(active, len(slots) - 1), labels)
    if PyImGui.button("+ add slot") and len(slots) < MAX_SLOTS:
        slots.append(_make_slot("swirl")); active = len(slots) - 1
    PyImGui.same_line(0, -1)
    if PyImGui.button("- remove") and len(slots) > 1:
        slots.pop(active); active = max(0, active - 1)
    live = 0
    try:
        live = sum(s["em"].count() for s in slots)
    except Exception:
        pass
    PyImGui.text("slots: %d   live particles: %d" % (len(slots), live))
    PyImGui.separator()
    _controls(slots[active])
    PyImGui.text("status: " + status)
    PyImGui.end()


def main():
    global status
    if not slots:
        try:
            slots.append(_make_slot("geyser"))
            status = "ready"
        except AttributeError:
            status = "PyParticles missing - rebuild the DLL"
            _ui()
            return
        except Exception as e:
            status = "setup err: %s" % e
            return

    _ui()

    try:
        x, y = Player.GetXY()
        if x == 0 and y == 0:
            return
        gz = _ground_z(x, y)
        for i, s in enumerate(slots):
            show = s["on"] and (not view_solo or i == active)
            if show:
                _apply(s)
                s["em"].set_origin(x, y, gz - float(s["cfg"]["origin_dz"]))  # up = -z; feeds timeout
                b = int(s["cfg"].get("burst", 0))
                if b > 0 and s["em"].count() == 0:
                    s["em"].emit(b)   # loop the burst: re-fire once the last one has died
            else:
                # not shown: stop it and clear instantly (and don't feed -> also times out)
                s["em"].config.enabled = False
                s["em"].clear()
    except Exception as e:
        status = "no player: %s" % e


if __name__ == "__main__":
    main()
