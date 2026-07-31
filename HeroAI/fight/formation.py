"""Fight formation pins: authored per-line, with a hard reach budget.

Pins live in fight-local coordinates — origin is the zone pin (where the front
line stands) and +Y points at the enemies, so depth reads directly off the Y
spread in the editor.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from dataclasses import field

from Py4GWCoreLib import Range
from Py4GWCoreLib import ThrottledTimer
from Py4GWCoreLib.py4gwcorelib_src.Settings import Settings

from .lines import CombatLine

FIGHT_INI_PATH = "HeroAI"
FIGHT_INI_NAME = "FightModule_Formations.ini"
FIGHT_SECTION = "FightFormations"
SELECTED_KEY = "selected_id"
PIN_COUNT_KEY = "pin_count"
FORMATION_ID_PREFIX = "FightFormationId:"
RELOAD_MS = 1000
MAX_PINS = 11

# Max cast range is Spellcast, not Earshot. The backline must sit inside it with
# room to spare: a monk parked exactly at the edge has to walk before it can
# answer a spike, which is precisely when it cannot afford to.
CAST_RANGE = float(Range.Spellcast.value)
CAST_SAFETY_MARGIN = 100.0


@dataclass(slots=True)
class FightPin:
    x: float
    y: float
    line: CombatLine


@dataclass(slots=True)
class LineTolerances:
    front: float = 120.0
    # Wide so the build's own kiting owns movement instead of fighting the zone.
    mid: float = 300.0
    back: float = 150.0

    def get(self, line: CombatLine) -> float:
        if line == CombatLine.FRONT:
            return self.front
        if line == CombatLine.BACK:
            return self.back
        return self.mid


# The budget is on worst-case separation, not on the authored depth: front and
# back can each drift a full tolerance apart, and the heal still has to land at
# that moment. Exceeding it is the failure that silently kills runs — the
# formation looks fine on screen and people just die out of range.
def max_depth_for(tolerances: LineTolerances) -> float:
    drift = float(tolerances.front) + float(tolerances.back)
    return max(200.0, CAST_RANGE - CAST_SAFETY_MARGIN - drift)


@dataclass(slots=True)
class FightFormation:
    pins: list[FightPin] = field(default_factory=list)
    tolerances: LineTolerances = field(default_factory=LineTolerances)

    def worst_case_separation(self) -> float:
        return self.depth() + float(self.tolerances.front) + float(self.tolerances.back)

    def pins_for_line(self, line: CombatLine) -> list[int]:
        return [index for index, pin in enumerate(self.pins) if pin.line == line]

    def midline_depth(self) -> float:
        """How far the middle rank sits behind the front line, positive.

        What "the blob has overrun us" is measured against, so it comes from the
        authored formation rather than a constant: a shallow formation is
        overrun sooner than a deep one, and should say so.
        """
        ys = [pin.y for pin in self.pins if pin.line == CombatLine.MID]
        if not ys:
            return self.depth() / 2.0
        return abs(sum(ys) / len(ys))

    def backline_depth(self) -> float:
        """How far the rear rank sits behind the front line, positive.

        Where the panic ring is centred, so it comes from the authored formation
        for the same reason midline_depth does — a compressed formation must not
        end up with its panic ring floating behind everybody.
        """
        ys = [pin.y for pin in self.pins if pin.line == CombatLine.BACK]
        if not ys:
            return self.depth()
        return abs(sum(ys) / len(ys))

    def depth(self) -> float:
        if not self.pins:
            return 0.0
        ys = [pin.y for pin in self.pins]
        return max(ys) - min(ys)


def default_fight_formation() -> FightFormation:
    return FightFormation(
        pins=[
            FightPin(-160.0, 0.0, CombatLine.FRONT),
            FightPin(0.0, 0.0, CombatLine.FRONT),
            FightPin(160.0, 0.0, CombatLine.FRONT),
            FightPin(-260.0, -320.0, CombatLine.MID),
            FightPin(-90.0, -320.0, CombatLine.MID),
            FightPin(90.0, -320.0, CombatLine.MID),
            FightPin(260.0, -320.0, CombatLine.MID),
            FightPin(-180.0, -620.0, CombatLine.BACK),
            FightPin(0.0, -620.0, CombatLine.BACK),
            FightPin(180.0, -620.0, CombatLine.BACK),
            FightPin(360.0, -620.0, CombatLine.BACK),
        ]
    )


def clamp_depth(formation: FightFormation, max_depth: float | None = None) -> tuple[FightFormation, bool]:
    """Compress the formation along Y until it fits the reach budget.

    Runtime clamps rather than trusting the INI — an over-deep formation puts
    healers out of range of the people taking damage, which reads as random
    deaths rather than as a configuration error.
    """
    if max_depth is None:
        max_depth = max_depth_for(formation.tolerances)
    depth = formation.depth()
    if depth <= max_depth or depth <= 0.001:
        return formation, False

    scale = max_depth / depth
    front_y = max(pin.y for pin in formation.pins)
    formation.pins = [FightPin(pin.x, front_y + ((pin.y - front_y) * scale), pin.line) for pin in formation.pins]
    return formation, True


def fight_cfg() -> Settings:
    return Settings(f"{FIGHT_INI_PATH}/{FIGHT_INI_NAME}", "global")


class FightFormationLoader:
    def __init__(self) -> None:
        self.formation = default_fight_formation()
        self.reload_timer = ThrottledTimer(RELOAD_MS)
        self.depth_was_clamped = False
        self.loaded_once = False

    def get(self) -> FightFormation:
        if (not self.loaded_once) or self.reload_timer.IsExpired():
            self.reload()
            self.reload_timer.Reset()
        return self.formation

    def reload(self) -> None:
        self.loaded_once = True
        try:
            cfg = fight_cfg()
            try:
                cfg.reload()
            except Exception:
                pass

            selected_id = str(cfg.get_str(FIGHT_SECTION, SELECTED_KEY, "") or "").strip()
            if not selected_id:
                self.formation, self.depth_was_clamped = clamp_depth(default_fight_formation())
                return

            section = f"{FORMATION_ID_PREFIX}{selected_id}"
            pin_count = max(0, min(MAX_PINS, cfg.get_int(section, PIN_COUNT_KEY, 0)))
            pins: list[FightPin] = []
            for index in range(pin_count):
                x = float(cfg.get_float(section, f"p{index}_x", 0.0))
                y = float(cfg.get_float(section, f"p{index}_y", 0.0))
                line = CombatLine(max(1, min(3, cfg.get_int(section, f"p{index}_line", int(CombatLine.MID)))))
                pins.append(FightPin(x, y, line))

            tolerances = LineTolerances(
                front=max(50.0, float(cfg.get_float(section, "tolerance_front", 120.0))),
                mid=max(50.0, float(cfg.get_float(section, "tolerance_mid", 300.0))),
                back=max(50.0, float(cfg.get_float(section, "tolerance_back", 150.0))),
            )

            loaded = FightFormation(pins=pins, tolerances=tolerances) if pins else default_fight_formation()
            self.formation, self.depth_was_clamped = clamp_depth(loaded)
        except Exception:
            self.formation, self.depth_was_clamped = clamp_depth(default_fight_formation())


def rotate_fight_local_to_world(local_x: float, local_y: float, facing: float) -> tuple[float, float]:
    """+Y in fight-local space points at the enemies, i.e. along `facing`."""
    cos_f = math.cos(facing)
    sin_f = math.sin(facing)
    return ((local_y * cos_f) - (local_x * sin_f), (local_y * sin_f) + (local_x * cos_f))
