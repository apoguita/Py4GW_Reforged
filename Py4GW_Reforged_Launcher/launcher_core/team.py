"""Team model -- a lightweight named grouping of profiles, for multibox bulk launch.

Deliberately minimal: id and name only, nothing else yet. "ALL" is not a real team
and is never represented here -- it's a built-in view mode in the UI layer showing
every profile with no membership checkbox, not stored data.
"""

from __future__ import annotations

import dataclasses
import uuid
from typing import Any


@dataclasses.dataclass
class Team:
    id: str = dataclasses.field(default_factory=lambda: uuid.uuid4().hex)
    name: str = ""

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "Team":
        known_fields = {f.name for f in dataclasses.fields(Team)}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return Team(**filtered)
