"""Nicholas the Traveller -- resolving the scheduled trophy for a week.

**Default is the current week.** A user who never configures this gets this week's item and nothing
else. Beyond that they enter the dates they want to monitor; several may be active at once.

Ported out of the Calendar widget's logic with its central bug removed. That widget's
``expand_cycle_if_needed`` declared ``global NICHOLAS_CYCLE`` and **rebound it**, growing the shared
list every time a date outside the current range was asked for. Here the schedule is read-only: it is
140 consecutive Mondays, so any date resolves by modular arithmetic and nothing is ever appended.

*(The Calendar widget itself is an **event** calendar and is unrelated to this feature.)*

Resolution is **cached**, because the answer changes at most once a week. The cache is invalidated by
exactly two things: the week turning over, and the selection changing.
"""

from dataclasses import dataclass
from datetime import date
from datetime import timedelta


@dataclass(frozen=True)
class NicholasSelection:
    """One wanted week.

    ``week`` is ``None`` for the rolling current week -- the default -- and a specific Monday for a
    date the user entered.
    """

    week: date | None = None

    @staticmethod
    def current_week() -> "NicholasSelection":
        return NicholasSelection(None)

    @staticmethod
    def on(day: date) -> "NicholasSelection":
        """A date the user entered. Normalised to its Monday, so any day of the week works."""
        return NicholasSelection(monday_of(day))


def monday_of(day: date) -> date:
    """The Monday that starts the given day's week. The schedule is weekly and Monday-aligned."""
    return day - timedelta(days=day.weekday())


def _cycle() -> list[dict]:
    """The shipped schedule. Imported lazily so this module stays import-safe offline."""
    from Py4GWCoreLib.enums import NICHOLAS_CYCLE

    return NICHOLAS_CYCLE


def entry_for_week(week: date) -> dict | None:
    """The cycle entry for a week -- any date, past or far future.

    The schedule repeats, so a week outside the listed range wraps by modular arithmetic. The shared
    list is never modified.
    """
    cycle = _cycle()
    if not cycle:
        return None
    monday = monday_of(week)
    first = cycle[0]["week"]
    return cycle[((monday - first).days // 7) % len(cycle)]


def entry_for_day(day: date) -> dict | None:
    return entry_for_week(monday_of(day))


def resolve(selections, today: date) -> set[int]:
    """Model ids wanted for a set of selections on a given day."""
    wanted: set[int] = set()
    for selection in selections:
        week = monday_of(today) if selection.week is None else selection.week
        entry = entry_for_week(week)
        if entry is None:
            continue
        model_id = entry.get("model_id")
        if model_id is not None:
            wanted.add(int(model_id))
    return wanted


class NicholasCache:
    """Caches the resolved ids; recomputes only when the answer can actually differ."""

    def __init__(self) -> None:
        self._monday: date | None = None
        self._key: tuple = ()
        self._model_ids: set[int] = set()

    def model_ids(self, selections, today: date) -> set[int]:
        monday = monday_of(today)
        key = tuple(sorted((s.week.isoformat() if s.week else "") for s in selections))
        if monday != self._monday or key != self._key:
            self._monday, self._key = monday, key
            self._model_ids = resolve(selections, today)
        return self._model_ids

    def invalidate(self) -> None:
        self._monday = None
        self._key = ()
