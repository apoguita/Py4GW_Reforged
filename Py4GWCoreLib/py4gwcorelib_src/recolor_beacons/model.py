"""The marking feature's configuration -- the same class twice: persisted and live.

Everything a script can touch is doubled. The persisted copy is the user's, written only by the user
through System Settings; the live copy is what runs, and a script writes only that. There is no path
from live to a writer, so **a script never persists**. A restart is a reset by construction.

**The outcome itself is not here.** A filter carries its own recolour / beacon (see the Factory's
``Rule.mark_*``). What lives here is the feature's own settings: the master switch, the active
profile, and the beacon budget.

**The budget is the user's, not ours.** The class imposes no hidden cap; it gives the controls --
maximum live beacons, a distance limit, and a cheap stand-in for distant ones -- and the user decides
the trade-off.
"""

from dataclasses import dataclass
from dataclasses import field
from dataclasses import fields as dataclass_fields


@dataclass
class MarkConfig:
    """Per account. Two instances exist: what the user saved, and what is running."""

    #: The feature's own master switch. Symmetric with Loot Filters -- each feature is standalone,
    #: so neither can be switched off from the other's section.
    enabled: bool = False
    #: The active marking profile. One at a time, and independent of the loot feature's choice.
    profile: str = ""

    # -- recolour --
    #: Blank loot that is assigned to somebody else. A stated use of BLANK: it is not ours to take,
    #: so it does not need to be on screen. Visual only -- it changes nothing about what is wanted.
    blank_unassigned: bool = False

    # -- the beacon budget, all the user's to set --
    #: How many beacons may be alive at once. Nearest first when there are more.
    max_beacons: int = 8
    #: Beacons only within this range.
    beacon_distance: float = 2500.0
    #: Beyond ``cheap_distance``, draw a stripped-down stand-in instead of the full effect.
    cheap_distant: bool = True
    cheap_distance: float = 1200.0

    def copy(self) -> "MarkConfig":
        return MarkConfig(**{f.name: getattr(self, f.name) for f in dataclass_fields(self)})

    def differs_from(self, other: "MarkConfig") -> bool:
        return any(getattr(self, f.name) != getattr(other, f.name) for f in dataclass_fields(self))

    def diff(self, other: "MarkConfig") -> list[str]:
        """What a script changed, in words -- this feeds the live-state label and its detail view."""
        labels = {
            "enabled": "Marking", "profile": "Profile", "blank_unassigned": "Blank unassigned loot",
            "max_beacons": "Max beacons", "beacon_distance": "Beacon distance",
            "cheap_distant": "Cheap distant beacons", "cheap_distance": "Cheap beacon distance",
        }
        out: list[str] = []
        for spec in dataclass_fields(self):
            mine, theirs = getattr(self, spec.name), getattr(other, spec.name)
            if mine != theirs:
                out.append("%s: %s -> %s" % (labels.get(spec.name, spec.name),
                                             theirs if theirs != "" else "(none)",
                                             mine if mine != "" else "(none)"))
        return out
