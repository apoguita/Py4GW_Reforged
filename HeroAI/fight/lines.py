"""Which line a character fights on: manual override > build declaration > profession."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from Py4GWCoreLib import Profession
from Py4GWCoreLib import ThrottledTimer
from Py4GWCoreLib.py4gwcorelib_src.Settings import Settings


class CombatLine(IntEnum):
    AUTO = 0
    FRONT = 1
    MID = 2
    BACK = 3


LINE_BY_NAME: dict[str, CombatLine] = {
    "auto": CombatLine.AUTO,
    "front": CombatLine.FRONT,
    "mid": CombatLine.MID,
    "back": CombatLine.BACK,
}
NAME_BY_LINE: dict[CombatLine, str] = {value: key for key, value in LINE_BY_NAME.items()}


class LineSource(IntEnum):
    INFERRED = 0
    BUILD = 1
    MANUAL = 2


SOURCE_LABELS: dict[LineSource, str] = {
    LineSource.INFERRED: "inferred",
    LineSource.BUILD: "build",
    LineSource.MANUAL: "manual",
}

# Same profession split the rest of the repo already uses: melee_professions in
# HeroAI/commands.py and the caster / ranged_martial / melee taxonomy in
# HeroAI/hex_removal_src/hex_removal_config.py. One answer, not three.
FRONT_PROFESSIONS: frozenset[int] = frozenset(
    {
        int(Profession.Warrior),
        int(Profession.Assassin),
        int(Profession.Dervish),
        int(Profession.Paragon),
    }
)
BACK_PROFESSIONS: frozenset[int] = frozenset(
    {
        int(Profession.Monk),
        int(Profession.Ritualist),
    }
)

LINES_INI_PATH = "HeroAI"
LINES_INI_NAME = "FightLines.ini"
LINES_SECTION = "FightLines"
LINES_RELOAD_MS = 1000


@dataclass(slots=True)
class ResolvedLine:
    line: CombatLine
    source: LineSource

    @property
    def source_label(self) -> str:
        return SOURCE_LABELS[self.source]


def lines_cfg() -> Settings:
    return Settings(f"{LINES_INI_PATH}/{LINES_INI_NAME}", "global")


LINES_RELOAD_TIMER = ThrottledTimer(LINES_RELOAD_MS)


def normalize_line(value: object) -> CombatLine:
    if isinstance(value, CombatLine):
        return value
    if isinstance(value, int):
        try:
            return CombatLine(value)
        except ValueError:
            return CombatLine.AUTO
    if isinstance(value, str):
        return LINE_BY_NAME.get(value.strip().lower(), CombatLine.AUTO)
    return CombatLine.AUTO


def infer_line_from_profession(primary_profession: int) -> CombatLine:
    if int(primary_profession) in FRONT_PROFESSIONS:
        return CombatLine.FRONT
    if int(primary_profession) in BACK_PROFESSIONS:
        return CombatLine.BACK
    return CombatLine.MID


def get_manual_line(character_name: str, reload_from_disk: bool = False) -> CombatLine:
    """Read the leader-authored override. Keyed by character name: party position
    shuffles and an account email does not distinguish characters on one account."""
    key = str(character_name or "").strip()
    if not key:
        return CombatLine.AUTO
    cfg = lines_cfg()
    if reload_from_disk:
        try:
            cfg.reload()
        except Exception:
            pass
    return normalize_line(cfg.get_str(LINES_SECTION, key, "auto"))


def set_manual_line(character_name: str, line: CombatLine) -> None:
    key = str(character_name or "").strip()
    if not key:
        return
    cfg = lines_cfg()
    cfg.set_str(LINES_SECTION, key, NAME_BY_LINE[normalize_line(line)])
    try:
        cfg.save()
    except Exception:
        pass


def get_build_declared_line(build_contract: object) -> CombatLine:
    return normalize_line(getattr(build_contract, "combat_line", None))


def resolve_line(
    character_name: str,
    primary_profession: int,
    build_contract: object | None = None,
) -> ResolvedLine:
    """Followers poll the override INI on a throttle so a leader-side reassignment
    lands within a second without a restart — same pattern as FollowRuntime.ini."""
    should_reload = LINES_RELOAD_TIMER.IsExpired()
    if should_reload:
        LINES_RELOAD_TIMER.Reset()

    manual = get_manual_line(character_name, reload_from_disk=should_reload)
    if manual != CombatLine.AUTO:
        return ResolvedLine(manual, LineSource.MANUAL)

    declared = get_build_declared_line(build_contract) if build_contract is not None else CombatLine.AUTO
    if declared != CombatLine.AUTO:
        return ResolvedLine(declared, LineSource.BUILD)

    return ResolvedLine(infer_line_from_profession(primary_profession), LineSource.INFERRED)
