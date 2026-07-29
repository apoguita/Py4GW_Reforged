"""What a beacon preset is, and every parameter it exposes.

**The controls are not invented.** `light_beacon.py` is the reference for the effect *and* for the
controls: every widget kind, label and range below is carried from it verbatim. Nothing was pruned for
being "probably unused" -- most users will only change the beam colours, but full control is available
so a user can mix and match into their own marker.

Two things in the reference deliberately do **not** carry over:

* ``rows`` -- dead. It sits in the reference's state and ``_draw`` never reads it. Verified, not
  assumed.
* ``anchor_mode`` / ``anchor_x`` / ``anchor_y`` / ``anchor_set`` -- alive there, but they pin a beacon
  to a fixed world position. An item beacon follows its drop, so they do not apply.

*Why nothing else was pruned:* the emitter parameters cannot be judged by reading Python.
``_apply_emitter`` loops the groups and ``setattr``s every key onto the C++ emitter config, so a
parameter can look unread in Python while doing real work in the particle system.

**Presets are definitions, not settings.** A script may consume them; it may never author one, so --
unlike the two feature configurations -- a preset has no live copy. There is nothing here for a script
to dirty.
"""

from dataclasses import dataclass
from dataclasses import field

FLOAT = "float"
INT = "int"
BOOL = "bool"
COMBO = "combo"
COLOR = "color"


@dataclass(frozen=True)
class Param:
    """One control: what it edits, how it is drawn, and the range it is drawn over."""

    key: str
    label: str
    kind: str = FLOAT
    lo: float = 0.0
    hi: float = 1.0
    options: tuple[str, ...] = ()
    #: Shown only when this holds. Conditional controls follow the reference: cone sides and the
    #: glow trio appear only for the cone shape, the quad count only for crossed quads.
    only_when: tuple[str, int] | None = None


# ---------------------------------------------------------------- the beacon itself

BEAM_PARAMS: tuple[Param, ...] = (
    Param("beam_shape", "shape", COMBO, options=("crossed quads", "cone (glow)")),
    Param("beam_blend", "blend", COMBO, options=("alpha", "additive", "max (colored glow)")),
    Param("beam_segments", "cone sides", INT, 3, 48, only_when=("beam_shape", 1)),
    Param("beam_glow", "glow strength", FLOAT, 0.0, 1.0, only_when=("beam_shape", 1)),
    Param("beam_glow_scale", "glow width (x radius)", FLOAT, 1.0, 5.0, only_when=("beam_shape", 1)),
    Param("beam_glow_shells", "glow softness (shells)", INT, 1, 10, only_when=("beam_shape", 1)),
    Param("beam_quads", "crossed quads", INT, 1, 8, only_when=("beam_shape", 0)),
    Param("beam_base", "bottom color (alpha = opacity)", COLOR),
    Param("beam_mid", "center color (alpha = opacity)", COLOR),
    Param("beam_top", "top color (alpha = opacity)", COLOR),
    Param("beam_mid_frac", "center height", FLOAT, 0.05, 0.95),
    Param("height", "height", FLOAT, 100.0, 1400.0),
    Param("base_w", "base width", FLOAT, 1.0, 40.0),
    Param("top_w", "top width", FLOAT, 0.5, 40.0),
)

GROUND_PARAMS: tuple[Param, ...] = (
    Param("disc", "ground color", COLOR),
    Param("disc_radius", "disc radius", FLOAT, 5.0, 150.0),
    Param("ground_lift", "ground lift (above terrain)", FLOAT, 0.0, 40.0),
    Param("rings", "ring count", INT, 0, 5),
    Param("ring_speed", "ring speed", FLOAT, 0.1, 4.0),
    Param("ring_thickness", "ring thickness (x radius)", FLOAT, 0.02, 0.4),
)

GLOBAL_PARAMS: tuple[Param, ...] = (
    Param("pulse", "pulse / shimmer", BOOL),
    Param("ground_additive", "ground additive", BOOL),
)

#: The three sections of the beacon body, in editor order.
BEACON_GROUPS: tuple[tuple[str, tuple[Param, ...]], ...] = (
    ("Beam", BEAM_PARAMS),
    ("Ground (disc + rings)", GROUND_PARAMS),
    ("Global", GLOBAL_PARAMS),
)

#: Colours live in their own dict so the "copy a colour between stops" action has one place to work.
COLOR_KEYS: tuple[tuple[str, str], ...] = (
    ("beam_base", "bottom"), ("beam_mid", "center"), ("beam_top", "top"), ("disc", "ground"),
)

BEACON_DEFAULTS: dict = {
    "beam_shape": 1, "beam_quads": 2, "beam_segments": 16, "beam_blend": 2,
    "beam_glow": 0.5, "beam_glow_scale": 2.2, "beam_glow_shells": 5, "beam_mid_frac": 0.5,
    "height": 700.0, "base_w": 8.0, "top_w": 3.0,
    "disc_radius": 46.0, "rings": 2, "ring_speed": 0.757, "ring_thickness": 0.20,
    "ground_lift": 6.0, "pulse": False, "ground_additive": False,
}

COLOR_DEFAULTS: dict[str, list[float]] = {
    "beam_base": [0.73, 0.53, 0.93, 0.80],
    "beam_mid": [0.51, 0.05, 0.98, 0.40],
    "beam_top": [0.16, 0.00, 0.32, 0.20],
    "disc": [0.73, 0.53, 0.93, 0.80],
}

#: The rarity colours, so a marker can be made to match a rarity in one click.
RARITY_SWATCHES: tuple[tuple[str, tuple[float, float, float]], ...] = (
    ("White", (0.90, 0.90, 0.90)),
    ("Blue", (0.42, 0.58, 0.93)),
    ("Purple", (0.65, 0.42, 0.93)),
    ("Gold", (0.93, 0.78, 0.28)),
    ("Green", (0.36, 0.82, 0.42)),
)


# ---------------------------------------------------------------- emitters

#: Carried verbatim from the reference's ``EMITTER_GROUPS`` -- every key, every range.
EMITTER_GROUPS: tuple[tuple[str, tuple[tuple[str, float, float], ...]], ...] = (
    ("emit", (("rate", 0.0, 150.0),)),
    ("launch", (("dir_x", -1.0, 1.0), ("dir_y", -1.0, 1.0), ("dir_z", -1.0, 1.0),
                ("speed", 0.0, 400.0), ("speed_var", 0.0, 250.0), ("spread", 0.0, 3.1416))),
    ("physics", (("grav_x", -400.0, 400.0), ("grav_y", -400.0, 400.0), ("grav_z", -600.0, 600.0),
                 ("drag", 0.0, 5.0), ("turbulence", 0.0, 500.0))),
    ("orbit", (("orbit_radius", 0.0, 150.0), ("orbit_radius_var", 0.0, 80.0),
               ("orbit_radius_end", -1.0, 150.0), ("orbit_spin", -8.0, 8.0),
               ("orbit_rise", -100.0, 250.0), ("orbit_height", 10.0, 1200.0))),
    ("shape", (("spawn_radius", 0.0, 200.0), ("radial_speed", -250.0, 250.0), ("stretch", 0.0, 0.15))),
    ("life / size", (("life", 0.2, 12.0), ("life_var", 0.0, 6.0), ("size", 0.05, 6.0),
                     ("size_var", 0.0, 4.0), ("size_end", 0.0, 8.0), ("hot_frac", 0.0, 1.0))),
)

EMITTER_DEFAULTS: dict[str, float] = {
    "rate": 20.0, "dir_x": 0.0, "dir_y": 0.0, "dir_z": -1.0, "speed": 80.0, "speed_var": 40.0,
    "spread": 0.5, "grav_x": 0.0, "grav_y": 0.0, "grav_z": 0.0, "drag": 0.0, "turbulence": 0.0,
    "orbit_radius": 40.0, "orbit_radius_var": 15.0, "orbit_radius_end": -1.0, "orbit_spin": 2.0,
    "orbit_rise": 40.0, "orbit_height": 250.0, "spawn_radius": 0.0, "radial_speed": 0.0,
    "stretch": 0.0, "life": 5.0, "life_var": 1.0, "size": 1.0, "size_var": 0.3, "size_end": 0.0,
    "hot_frac": 0.35,
}

EMITTER_KEYS: tuple[str, ...] = tuple(k for _group, fields in EMITTER_GROUPS for k, _lo, _hi in fields)

BALLISTIC, ORBITAL = 0, 1


@dataclass
class Emitter:
    """One particle emitter. Independent: its own full parameter set, added and removed freely."""

    name: str = "Emitter"
    enabled: bool = False
    mode: int = ORBITAL
    additive: bool = False
    color: list[float] = field(default_factory=lambda: [0.73, 0.53, 0.93, 0.8])
    #: Mixer-desk mute, so one emitter can be isolated to see what it actually contributes.
    #: Deliberately NOT persisted -- it is an inspection aid, not part of the preset.
    muted: bool = False
    params: dict[str, float] = field(default_factory=lambda: dict(EMITTER_DEFAULTS))

    def copy(self) -> "Emitter":
        return Emitter(self.name, self.enabled, self.mode, self.additive, list(self.color),
                       self.muted, dict(self.params))

    def to_dict(self) -> dict:
        return {"name": self.name, "enabled": self.enabled, "mode": int(self.mode),
                "additive": self.additive, "color": list(self.color),
                "params": {k: float(self.params.get(k, EMITTER_DEFAULTS[k])) for k in EMITTER_KEYS}}

    @classmethod
    def from_dict(cls, raw: dict) -> "Emitter":
        params = dict(EMITTER_DEFAULTS)
        stored = raw.get("params") or {}
        if isinstance(stored, dict):
            for key in EMITTER_KEYS:
                if key in stored:
                    try:
                        params[key] = float(stored[key])
                    except (TypeError, ValueError):
                        pass
        color = raw.get("color") or [0.73, 0.53, 0.93, 0.8]
        return cls(str(raw.get("name", "Emitter")), bool(raw.get("enabled", False)),
                   int(raw.get("mode", ORBITAL)), bool(raw.get("additive", False)),
                   [float(c) for c in color][:4], False, params)


def make_emitter(name: str, **overrides) -> Emitter:
    """An emitter on the defaults, with the named parameters overridden."""
    emitter = Emitter(name=name)
    for key, value in overrides.items():
        if key in EMITTER_DEFAULTS:
            emitter.params[key] = float(value)
        else:
            setattr(emitter, key, value)
    return emitter


# ---------------------------------------------------------------- the preset

@dataclass
class BeaconPreset:
    """A named, complete beacon. Global -- shared across accounts, like filters and profiles."""

    name: str = "Beacon"
    params: dict = field(default_factory=lambda: dict(BEACON_DEFAULTS))
    colors: dict[str, list[float]] = field(
        default_factory=lambda: {k: list(v) for k, v in COLOR_DEFAULTS.items()})
    emitters: list[Emitter] = field(default_factory=list)

    # -- parameter access; one path per kind, so the editor never reaches into the dicts itself
    #    and never has to narrow a union at the call site --

    def number(self, key: str) -> float:
        return float(self.params.get(key, BEACON_DEFAULTS.get(key, 0.0)) or 0.0)

    def choice(self, key: str) -> int:
        return int(self.params.get(key, BEACON_DEFAULTS.get(key, 0)) or 0)

    def flag(self, key: str) -> bool:
        return bool(self.params.get(key, BEACON_DEFAULTS.get(key, False)))

    def color(self, key: str) -> list[float]:
        return list(self.colors.get(key) or COLOR_DEFAULTS.get(key) or [1.0, 1.0, 1.0, 1.0])

    def set(self, key: str, value) -> None:
        if key in COLOR_DEFAULTS:
            self.colors[key] = [float(c) for c in value][:4]
        else:
            self.params[key] = value

    def reset_param(self, key: str) -> None:
        """Put one parameter back to the base value. One control, not the whole preset."""
        if key in COLOR_DEFAULTS:
            self.colors[key] = list(COLOR_DEFAULTS[key])
        elif key in BEACON_DEFAULTS:
            self.params[key] = BEACON_DEFAULTS[key]

    def copy(self, name: str | None = None) -> "BeaconPreset":
        return BeaconPreset(name or self.name, dict(self.params),
                            {k: list(v) for k, v in self.colors.items()},
                            [e.copy() for e in self.emitters])

    # -- cost --

    def particles_per_second(self) -> float:
        """What this preset costs to run, before twenty of them are running.

        Muted emitters are excluded: mute is what the renderer honours, so the figure must agree
        with what is actually being drawn.
        """
        return sum(e.params.get("rate", 0.0) for e in self.emitters if e.enabled and not e.muted)

    def estimated_live_particles(self) -> float:
        """Steady-state population: each emitter holds roughly ``rate x life`` particles alive."""
        return sum(e.params.get("rate", 0.0) * e.params.get("life", 0.0)
                   for e in self.emitters if e.enabled and not e.muted)

    # -- storage --

    def to_dict(self) -> dict:
        return {"name": self.name,
                "params": {k: self.params.get(k, v) for k, v in BEACON_DEFAULTS.items()},
                "colors": {k: list(self.colors.get(k, v)) for k, v in COLOR_DEFAULTS.items()},
                "emitters": [e.to_dict() for e in self.emitters]}

    @classmethod
    def from_dict(cls, raw: dict) -> "BeaconPreset":
        params = dict(BEACON_DEFAULTS)
        stored = raw.get("params") or {}
        if isinstance(stored, dict):
            for key, default in BEACON_DEFAULTS.items():
                if key in stored:
                    value = stored[key]
                    try:
                        params[key] = bool(value) if isinstance(default, bool) else \
                            (int(value) if isinstance(default, int) else float(value))
                    except (TypeError, ValueError):
                        pass
        colors = {k: list(v) for k, v in COLOR_DEFAULTS.items()}
        stored_colors = raw.get("colors") or {}
        if isinstance(stored_colors, dict):
            for key in COLOR_DEFAULTS:
                if isinstance(stored_colors.get(key), list):
                    colors[key] = [float(c) for c in stored_colors[key]][:4]
        emitters = [Emitter.from_dict(e) for e in (raw.get("emitters") or []) if isinstance(e, dict)]
        return cls(str(raw.get("name", "Beacon")), params, colors, emitters)


#: The name of the beacon that always exists. Protected from deletion, and the target of
#: "reset this preset to the base" -- there is always something to fall back to.
BASE_NAME = "Base beacon"


def base_preset() -> BeaconPreset:
    """The reference beacon, rebuilt from the defaults. The fallback that cannot be removed."""
    return BeaconPreset(
        BASE_NAME, dict(BEACON_DEFAULTS), {k: list(v) for k, v in COLOR_DEFAULTS.items()},
        [make_emitter("Fireflies", enabled=True, rate=25, orbit_radius=15, orbit_radius_var=15,
                      orbit_spin=0.5, orbit_rise=22, orbit_height=240, life=6.0, size=0.5,
                      hot_frac=0.4),
         make_emitter("Spiral", enabled=True, rate=7, orbit_radius=10, orbit_radius_var=6,
                      orbit_spin=0.5, orbit_rise=130, orbit_height=560, life=6.0, size=0.5,
                      hot_frac=0.35)])


# ---------------------------------------------------------------- the shipped rarity beacons

#: The gradient recipe the tuned reference already follows, recovered from its own colours.
#: Its three beam stops are ONE hue at three (saturation, value, alpha) steps:
#:
#:     base [0.73,0.53,0.93] -> h=0.750 s=0.43 v=0.93
#:     mid  [0.51,0.05,0.98] -> h=0.749 s=0.95 v=0.98
#:     top  [0.16,0.00,0.32] -> h=0.750 s=1.00 v=0.32
#:
#: Feeding h=0.75 back through it returns those exact numbers, so a rarity beacon is the tuned
#: beacon at a different hue -- not a new design guessed at.
_STOPS: tuple[tuple[float, float, float], ...] = (
    (0.43, 0.93, 0.80),   # bottom  (saturation, value, alpha)
    (0.95, 0.98, 0.40),   # centre
    (1.00, 0.32, 0.20),   # top
)

#: hue, and a saturation multiplier -- white has no hue, so its saturation is flattened to zero.
RARITY_HUES: tuple[tuple[str, float, float], ...] = (
    ("White", 0.00, 0.0),
    ("Blue", 0.60, 1.0),
    ("Purple", 0.75, 1.0),
    ("Gold", 0.13, 1.0),
    ("Green", 0.33, 1.0),
    ("Red", 0.00, 1.0),
)


def tinted_preset(name: str, hue: float, saturation: float = 1.0) -> BeaconPreset:
    """The base beacon at a different hue. Shape, sizes and emitters are untouched."""
    import colorsys

    preset = base_preset().copy(name)
    stops = []
    for sat, value, alpha in _STOPS:
        r, g, b = colorsys.hsv_to_rgb(hue, sat * saturation, value)
        stops.append([round(r, 3), round(g, 3), round(b, 3), alpha])
    preset.colors["beam_base"] = list(stops[0])
    preset.colors["beam_mid"] = list(stops[1])
    preset.colors["beam_top"] = list(stops[2])
    preset.colors["disc"] = list(stops[0])          # the disc matches the bottom stop, as the base does
    for emitter in preset.emitters:
        emitter.color = stops[0][:3] + [emitter.color[3]]
    return preset


def rarity_presets() -> list[BeaconPreset]:
    """One beacon per rarity, plus Red. Shipped, and the user may edit or delete any of them."""
    return [tinted_preset(name, hue, saturation) for name, hue, saturation in RARITY_HUES]
