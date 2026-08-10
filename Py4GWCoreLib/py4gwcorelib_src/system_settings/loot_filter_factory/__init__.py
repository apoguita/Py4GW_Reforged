"""The Loot Filter Factory -- filters and profiles, owned by neither feature.

Loot Filters and Recolor & Beacons are standalone: neither imports the other, and neither owns the
filters or profiles they both use. Those live here, and both features **consume** them.

* :mod:`model` -- ``Rule`` (a composite resolver, criteria only) and ``Profile`` (a named set of filters).
* :mod:`matcher` -- all evaluation, including the per-criterion breakdown the live preview shows.
* :mod:`upgrades` -- the five slot-based upgrade lists a user picks from, by name.
* :mod:`store` -- the global filter and profile store, with short sequential ids.

The authoring UI is this module's too, and stands on its own: a consumer selects, it never hosts the
authoring surface.

**Not to be confused with ``item_filters``** -- that name is reserved for the full-fledged mod filter
class and must not be used for this.
"""

from .matcher import any_match
from .matcher import evaluate
from .matcher import matches
from .matcher import matching_rules
from .model import MATCH_ALL
from .model import MATCH_ANY
from .model import Profile
from .model import Rule
from .store import by_id
from .store import load_profiles
from .store import load_rules
from .store import next_id
from .store import profile_by_name
from .store import rules_in_profile
from .store import save_profiles
from .store import save_rules

__all__ = [
    "MATCH_ALL", "MATCH_ANY", "Profile", "Rule", "any_match", "by_id", "evaluate", "load_profiles",
    "load_rules", "matches", "matching_rules", "next_id", "profile_by_name", "rules_in_profile",
    "save_profiles", "save_rules",
]
