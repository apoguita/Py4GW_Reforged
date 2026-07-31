"""Map party members onto fight pins by line. Latched — never recomputed per tick."""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field

from .formation import FightFormation
from .lines import CombatLine

# Where a line's overflow goes when it has more members than pins. Front and back
# both spill inward: the midline is the most forgiving place to stand.
SPILL_ORDER: dict[CombatLine, tuple[CombatLine, ...]] = {
    CombatLine.FRONT: (CombatLine.MID, CombatLine.BACK),
    CombatLine.MID: (CombatLine.BACK, CombatLine.FRONT),
    CombatLine.BACK: (CombatLine.MID, CombatLine.FRONT),
}


@dataclass(slots=True)
class MemberLine:
    party_position: int
    character_name: str
    line: CombatLine


@dataclass(slots=True)
class Assignment:
    pin_by_party_position: dict[int, int] = field(default_factory=dict)
    composition: tuple[tuple[int, int], ...] = ()

    def pin_for(self, party_position: int) -> int | None:
        return self.pin_by_party_position.get(int(party_position))


def composition_signature(members: list[MemberLine]) -> tuple[tuple[int, int], ...]:
    """Who is in the party and on which line. Assignment is recomputed only when
    this changes — a death must not reshuffle everyone mid-fight."""
    return tuple(sorted((int(m.party_position), int(m.line)) for m in members))


def assign_pins(formation: FightFormation, members: list[MemberLine]) -> Assignment:
    free_by_line: dict[CombatLine, list[int]] = {
        line: formation.pins_for_line(line) for line in (CombatLine.FRONT, CombatLine.MID, CombatLine.BACK)
    }
    taken: set[int] = set()
    pin_by_party_position: dict[int, int] = {}

    # Party-position order within a line, so the mapping is stable and readable
    # rather than dependent on iteration order of the party scan.
    for member in sorted(members, key=lambda m: int(m.party_position)):
        line = member.line if member.line != CombatLine.AUTO else CombatLine.MID
        candidates = [line, *SPILL_ORDER.get(line, ())]
        chosen: int | None = None
        for candidate_line in candidates:
            for pin_index in free_by_line.get(candidate_line, ()):
                if pin_index not in taken:
                    chosen = pin_index
                    break
            if chosen is not None:
                break
        if chosen is None:
            for pin_index in range(len(formation.pins)):
                if pin_index not in taken:
                    chosen = pin_index
                    break
        if chosen is None:
            continue
        taken.add(chosen)
        pin_by_party_position[int(member.party_position)] = chosen

    return Assignment(pin_by_party_position=pin_by_party_position, composition=composition_signature(members))


@dataclass(slots=True)
class AssignmentLatch:
    current: Assignment | None = None

    def get(self, formation: FightFormation, members: list[MemberLine]) -> Assignment:
        signature = composition_signature(members)
        if self.current is None or self.current.composition != signature:
            self.current = assign_pins(formation, members)
        return self.current

    def clear(self) -> None:
        self.current = None
