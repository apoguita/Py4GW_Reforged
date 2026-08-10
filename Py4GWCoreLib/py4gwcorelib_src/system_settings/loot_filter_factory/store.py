"""The Factory's store -- filters and profiles, global.

**Definitions are shared, selections are local.** Filters and profiles are definitions, so they live
at **global** scope and a filter written once is available to every account. Which profile a feature
runs is a selection and belongs to that feature's per-account settings.

``JsonFactory`` is correct here: these are user-generated, nested, variable-length collections. (The
*catalogs* are the opposite -- shipped reference data, package source, never in the JSON store.)

Ids are short sequential numbers. Not uuids: the pool is a single global store where sequential ids
cannot collide, and the system is a multi-account setup driven by one person, so two clients minting
an id in the same instant is not a real scenario. A readable id also keeps the stored JSON
hand-inspectable.
"""

from .model import Profile
from .model import Rule

_DOC = "Widgets/System/LootFilterFactory.json"


def _doc():
    """The global document. Imported lazily so this module stays import-safe offline."""
    try:
        from Py4GWCoreLib.py4gwcorelib_src.JsonFactory import JsonFactory

        return JsonFactory(_DOC, "global")
    except Exception:
        return None


# ---------------------------------------------------------------- filters


def load_rules() -> list[Rule]:
    doc = _doc()
    if doc is None:
        return []
    raw = doc.get_json("filters", [])
    if not isinstance(raw, list):
        return []
    out: list[Rule] = []
    for entry in raw:
        if isinstance(entry, dict):
            try:
                out.append(Rule.from_dict(entry))
            except Exception:
                continue
    return out


def save_rules(rules) -> None:
    doc = _doc()
    if doc is not None:
        doc.set_json("filters", [r.to_dict() for r in rules])


def next_id(rules) -> str:
    """The next short sequential id, unique within the single global pool."""
    taken = {r.id for r in rules}
    index = 1
    while "filter_%d" % index in taken:
        index += 1
    return "filter_%d" % index


def by_id(rules, rule_id: str) -> Rule | None:
    for rule in rules:
        if rule.id == rule_id:
            return rule
    return None


# ---------------------------------------------------------------- profiles


def load_profiles() -> list[Profile]:
    doc = _doc()
    if doc is None:
        return []
    raw = doc.get_json("profiles", [])
    if not isinstance(raw, list):
        return []
    out: list[Profile] = []
    for entry in raw:
        if isinstance(entry, dict):
            try:
                out.append(Profile.from_dict(entry))
            except Exception:
                continue
    return out


def save_profiles(profiles) -> None:
    doc = _doc()
    if doc is not None:
        doc.set_json("profiles", [p.to_dict() for p in profiles])


def profile_by_name(profiles, name: str) -> Profile | None:
    for profile in profiles:
        if profile.name == name:
            return profile
    return None


def rules_in_profile(rules, profile: Profile | None) -> list[Rule]:
    """The filters a profile names, in the profile's order. Unknown ids are skipped."""
    if profile is None:
        return []
    index = {r.id: r for r in rules}
    return [index[i] for i in profile.filter_ids if i in index]
