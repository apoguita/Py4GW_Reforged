"""Crash-safe enemy knowledge for coordinated HeroAI builds.

This module combines stable live information (map, mode, model id, level,
profession and observed casts) with small static role profiles.  It does not
hook native damage/combat events and therefore avoids the crash-prone telemetry
path used by earlier experiments.

The knowledge is deliberately advisory: every lookup fails open and returns a
neutral score when the runtime cannot provide a value.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from Py4GWCoreLib import Profession
from Py4GWCoreLib.Agent import Agent
from Py4GWCoreLib.Map import Map
from Py4GWCoreLib.Party import Party
from Py4GWCoreLib.Skill import Skill
from Py4GWCoreLib.Builds.Knowledge import OfflineKnowledge

RETENTION_MS = 180000


def _now_ms() -> int:
    try:
        import PySystem
        return int(PySystem.get_tick_count64() or 0)
    except Exception:
        try:
            import time
            return int(time.monotonic() * 1000.0)
        except Exception:
            return 0


def _skill_ids(names: tuple[str, ...]) -> frozenset[int]:
    result: set[int] = set()
    for name in names:
        try:
            sid = int(Skill.GetID(name) or 0)
        except Exception:
            sid = 0
        if sid > 0:
            result.add(sid)
    return frozenset(result)


HEAL_SKILLS = _skill_ids((
    "Word_of_Healing", "Heal_Party", "Healing_Burst", "Patient_Spirit",
    "Dwaynas_Kiss", "Dwayna's_Kiss", "Orison_of_Healing", "Infuse_Health",
    "Spirit_Light", "Mend_Body_and_Soul", "Soothing_Memories",
    "Protective_Was_Kaolai", "Recuperation", "Life", "Preservation",
))
PROT_SKILLS = _skill_ids((
    "Protective_Spirit", "Spirit_Bond", "Aegis", "Guardian",
    "Shield_of_Absorption", "Life_Sheath", "Reversal_of_Fortune",
    "Shield_Guardian", "Weapon_of_Warding", "Shelter", "Union",
    "Displacement", "Protective_Was_Kaolai",
))
REZ_SKILLS = _skill_ids((
    "Resurrection_Signet", "Resurrection_Chant", "Restore_Life", "Rebirth",
    "Flesh_of_My_Flesh", "Death_Pact_Signet", "Renew_Life",
    "Light_of_Dwayna", "Signet_of_Return", "Unyielding_Aura",
))
DANGEROUS_OFFENSE_SKILLS = _skill_ids((
    "Panic", "Energy_Surge", "Mistrust", "Cry_of_Frustration", "Backfire",
    "Shame", "Diversion", "Meteor_Shower", "Savannah_Heat", "Searing_Heat",
    "Maelstrom", "Deep_Freeze", "Earthquake", "Churning_Earth", "Sandstorm",
    "Ray_of_Judgment", "Spiteful_Spirit", "Mark_of_Pain", "Barbs",
    "Spoil_Victor", "Putrid_Explosion",
))


@dataclass(slots=True)
class EnemyRecord:
    model_id: int = 0
    name: str = ""
    level: int = 0
    primary: int = 0
    secondary: int = 0
    map_id: int = 0
    hard_mode: bool = False
    observed_skills: set[int] = field(default_factory=set)
    heal_casts: int = 0
    prot_casts: int = 0
    rez_casts: int = 0
    dangerous_casts: int = 0
    total_casts: int = 0
    finished_casts: int = 0
    stopped_casts: int = 0
    interrupted_casts: int = 0
    last_cast_skill_id: int = 0
    last_cast_seen_ms: int = 0
    last_seen_ms: int = 0


_RECORDS: dict[int, EnemyRecord] = {}
_MODEL_MEMORY: dict[tuple[int, int, bool], set[int]] = {}
_LAST_OUTCOME_SYNC_MS: int = 0
_LAST_CONTEXT: tuple[int, bool] = (0, False)
_LOGGED_PROFILE_HASH: dict[int, int] = {}
_LOGGED_PROFILE_TICK: dict[int, int] = {}
PROFILE_LOG_MIN_INTERVAL_MS = 2500
_PROCESSED_OUTCOMES: set[tuple[int, int]] = set()

_HEALER_NAME_TOKENS = ("monk", "priest", "healer", "mender", "shaman", "ritualist", "spirit shepherd")
_SUPPORT_NAME_TOKENS = ("protector", "guardian", "binder", "chanter", "keeper", "caretaker")
_CASTER_NAME_TOKENS = ("mesmer", "elementalist", "necromancer", "sorcerer", "mage", "warlock", "seeker")


def _profession_ids() -> tuple[int, int, int, int, int, int]:
    def val(p) -> int:
        try:
            return int(getattr(p, "value", p) or 0)
        except Exception:
            return 0
    return (
        val(Profession.Monk), val(Profession.Ritualist), val(Profession.Mesmer),
        val(Profession.Elementalist), val(Profession.Necromancer),
        val(Profession.Paragon),
    )


def _safe_context() -> tuple[int, bool]:
    try:
        map_id = int(Map.GetMapID() or 0)
    except Exception:
        map_id = 0
    try:
        hard_mode = bool(Party.IsHardMode())
    except Exception:
        hard_mode = False
    return map_id, hard_mode


def _safe_static(agent_id: int) -> EnemyRecord:
    aid = int(agent_id or 0)
    map_id, hard_mode = _safe_context()
    try:
        model_id = int(Agent.GetModelID(aid) or 0)
    except Exception:
        model_id = 0
    try:
        name = str(Agent.GetNameByID(aid) or "")
    except Exception:
        name = ""
    try:
        level = int(Agent.GetLevel(aid) or 0)
    except Exception:
        level = 0
    try:
        p, s = Agent.GetProfessions(aid)
        primary = int(getattr(p, "value", p) or 0)
        secondary = int(getattr(s, "value", s) or 0)
    except Exception:
        primary = secondary = 0
    return EnemyRecord(
        model_id=model_id, name=name, level=level, primary=primary,
        secondary=secondary, map_id=map_id, hard_mode=hard_mode,
        last_seen_ms=_now_ms(),
    )


def observe(agent_id: int, casting_skill_id: int = 0) -> EnemyRecord:
    aid = int(agent_id or 0)
    if aid <= 0:
        return EnemyRecord()
    rec = _RECORDS.get(aid)
    if rec is None:
        rec = _safe_static(aid)
        _RECORDS[aid] = rec
    rec.last_seen_ms = _now_ms()
    sid = int(casting_skill_id or 0)
    now = _now_ms()
    if sid > 0:
        # Polling sees the same cast over several frames. Count a new cast only
        # when the skill changed or a practical cast window elapsed.
        is_new_cast = sid != int(rec.last_cast_skill_id or 0) or now - int(rec.last_cast_seen_ms or 0) >= 650
        rec.observed_skills.add(sid)
        if is_new_cast:
            rec.total_casts += 1
            if sid in HEAL_SKILLS:
                rec.heal_casts += 1
            if sid in PROT_SKILLS:
                rec.prot_casts += 1
            if sid in REZ_SKILLS:
                rec.rez_casts += 1
            if sid in DANGEROUS_OFFENSE_SKILLS:
                rec.dangerous_casts += 1
            rec.last_cast_skill_id = sid
            rec.last_cast_seen_ms = now
        if rec.model_id > 0:
            _MODEL_MEMORY.setdefault((rec.map_id, rec.model_id, rec.hard_mode), set()).add(sid)
    return rec


def known_skills(agent_id: int) -> frozenset[int]:
    rec = observe(agent_id)
    merged = set(rec.observed_skills)
    try:
        profile = OfflineKnowledge.enemy_profile(rec.model_id, rec.name)
        merged.update(int(v) for v in profile.get('known_skill_ids', ()) if int(v or 0) > 0)
    except Exception:
        pass
    if rec.model_id > 0:
        merged.update(_MODEL_MEMORY.get((rec.map_id, rec.model_id, rec.hard_mode), ()))
    return frozenset(merged)


def role_scores(agent_id: int) -> dict[str, int]:
    rec = observe(agent_id)
    monk, ritualist, mesmer, elementalist, necromancer, paragon = _profession_ids()
    profs = (rec.primary, rec.secondary)
    healer = 0
    caster = 0
    support = 0
    offense = 0
    if monk and monk in profs:
        healer += 95; support += 90; caster += 65
    if ritualist and ritualist in profs:
        healer += 70; support += 85; caster += 60
    if mesmer and mesmer in profs:
        caster += 90; offense += 85
    if elementalist and elementalist in profs:
        caster += 85; offense += 80
    if necromancer and necromancer in profs:
        caster += 75; offense += 70
    if paragon and paragon in profs:
        support += 45; offense += 35

    lname = str(rec.name or "").casefold()
    if any(token in lname for token in _HEALER_NAME_TOKENS):
        healer += 35; support += 25; caster += 20
    if any(token in lname for token in _SUPPORT_NAME_TOKENS):
        support += 30; caster += 15
    if any(token in lname for token in _CASTER_NAME_TOKENS):
        caster += 30; offense += 20

    skills = known_skills(agent_id)
    healer += 40 * len(skills.intersection(HEAL_SKILLS))
    support += 34 * len(skills.intersection(PROT_SKILLS))
    support += 55 * len(skills.intersection(REZ_SKILLS))
    offense += 28 * len(skills.intersection(DANGEROUS_OFFENSE_SKILLS))
    caster += min(90, len(skills) * 8)

    # Offline profiles provide immediate first-contact knowledge. Live behaviour
    # below can still outweigh or correct the static assumptions.
    try:
        enemy_profile = OfflineKnowledge.enemy_profile(rec.model_id, rec.name)
        roles = set(enemy_profile.get("roles", ()))
        priority_bonus = int(enemy_profile.get("priority_bonus", 0) or 0)
        if "healer" in roles:
            healer += 85 + priority_bonus
        if "support" in roles:
            support += 70 + priority_bonus
        if "caster" in roles or "dangerous_caster" in roles:
            caster += 55
            offense += 45 + priority_bonus
        if "room_object" in roles:
            offense += 180 + priority_bonus

        for sid in skills:
            skill_profile = OfflineKnowledge.skill_profile(int(sid))
            categories = set(skill_profile.get("categories", ()))
            threat = int(skill_profile.get("threat", 0) or 0)
            if "heal" in categories:
                healer += max(20, threat // 2)
            if "protection" in categories or "party_protection" in categories:
                support += max(20, threat // 2)
            if "resurrection" in categories:
                support += max(70, threat)
            if "dangerous_offense" in categories or "shutdown" in categories:
                offense += max(20, threat // 2)
                caster += 15

        area = OfflineKnowledge.area_profile(rec.map_id)
        area_multiplier = float(area.get("threat_multiplier", 1.0) or 1.0)
        if area_multiplier > 1.0:
            healer = int(healer * area_multiplier)
            support = int(support * area_multiplier)
            caster = int(caster * min(1.15, area_multiplier))
            offense = int(offense * area_multiplier)
    except Exception:
        pass

    # Repeated live behaviour outweighs profession assumptions.
    healer += min(180, rec.heal_casts * 45)
    support += min(160, rec.prot_casts * 38 + rec.rez_casts * 70)
    offense += min(150, rec.dangerous_casts * 35)
    return {
        "healer": int(healer), "support": int(support),
        "caster": int(caster), "offense": int(offense),
    }


def threat_bonus(agent_id: int) -> int:
    scores = role_scores(agent_id)
    rec = observe(agent_id)
    bonus = max(scores["healer"], scores["support"], scores["offense"])
    if rec.hard_mode:
        bonus += 18
    if rec.level >= 28:
        bonus += min(25, rec.level - 27)
    return min(260, int(bonus * 0.55))


def mistrust_priority(agent_id: int) -> int:
    scores = role_scores(agent_id)
    # Mistrust is valuable on every real caster. Healers are not excluded:
    # preventing a heal/protection spell is often the fastest route to a kill.
    return int(scores["caster"] + scores["healer"] * 0.65 + scores["offense"] * 0.45)


def estimated_max_health(agent_id: int) -> int:
    """Conservative relative HP estimate for overkill planning.

    Guild Wars does not expose a universally reliable absolute max-HP value for
    every foe through the stable Python layer.  This estimate is therefore used
    only as a relative saturation hint; live health fraction remains the truth.
    """
    rec = observe(agent_id)
    level = max(1, int(rec.level or 1))
    base = 140 + level * 18
    if rec.hard_mode:
        base = int(base * 1.35)
    scores = role_scores(agent_id)
    if scores["healer"] > 120 or scores["support"] > 140:
        base = int(base * 1.08)
    return max(150, base)


def map_context() -> dict[str, object]:
    map_id, hard_mode = _safe_context()
    try:
        map_name = str(Map.GetMapName(map_id) or "")
    except Exception:
        map_name = ""
    return {"map_id": map_id, "map_name": map_name, "hard_mode": hard_mode}


def prune(live_agent_ids=()) -> None:
    now = _now_ms()
    live = {int(x) for x in live_agent_ids if int(x or 0) > 0}
    for aid, rec in list(_RECORDS.items()):
        if (live and aid not in live) or now - int(rec.last_seen_ms or 0) > RETENTION_MS:
            _RECORDS.pop(aid, None)


def reset() -> None:
    _RECORDS.clear()


def sync_event_outcomes(max_age_ms: int = 9000) -> None:
    """Learn from native cast outcomes without subscribing to damage events."""
    global _LAST_OUTCOME_SYNC_MS, _LAST_CONTEXT
    now = _now_ms()
    if now and _LAST_OUTCOME_SYNC_MS and now - _LAST_OUTCOME_SYNC_MS < 180:
        return
    _LAST_OUTCOME_SYNC_MS = now
    context = _safe_context()
    if context != _LAST_CONTEXT:
        _LAST_CONTEXT = context
        _RECORDS.clear()
        _LOGGED_PROFILE_HASH.clear()
        _LOGGED_PROFILE_TICK.clear()
    try:
        from Py4GWCoreLib.Builds.Skills import ReforgedSupport
        outcomes = ReforgedSupport.get_recent_cast_outcomes(max_age_ms=max_age_ms)
    except Exception:
        outcomes = ()
    for ts, aid, sid, outcome in outcomes:
        rec = observe(int(aid), int(sid))
        marker = (int(ts), int(sid), str(outcome))
        # Keep a tiny per-record marker dynamically; slots forbid new attrs, so
        # use a module cache keyed by agent and marker hash.
        key = (int(aid), hash(marker))
        if key in _PROCESSED_OUTCOMES:
            continue
        _PROCESSED_OUTCOMES.add(key)
        if outcome == "finished": rec.finished_casts += 1
        elif outcome == "interrupted": rec.interrupted_casts += 1
        elif outcome == "stopped": rec.stopped_casts += 1
    if len(_PROCESSED_OUTCOMES) > 2048:
        _PROCESSED_OUTCOMES.clear()
    purge_stale(now)


def purge_stale(now_ms: int = 0) -> None:
    now = int(now_ms or _now_ms())
    cutoff = now - int(RETENTION_MS)
    for aid, rec in list(_RECORDS.items()):
        if int(rec.last_seen_ms or 0) < cutoff:
            _RECORDS.pop(aid, None)
            _LOGGED_PROFILE_HASH.pop(aid, None)
            _LOGGED_PROFILE_TICK.pop(aid, None)


def profile_summary(agent_id: int) -> dict[str, object]:
    rec = observe(agent_id)
    scores = role_scores(agent_id)
    return {
        "agent_id": int(agent_id or 0), "name": str(rec.name or "?"),
        "model_id": int(rec.model_id), "level": int(rec.level),
        "hard_mode": bool(rec.hard_mode), "known_skill_count": len(known_skills(agent_id)),
        "casts": int(rec.total_casts), "finished": int(rec.finished_casts),
        "interrupted": int(rec.interrupted_casts), "stopped": int(rec.stopped_casts),
        **scores, "threat_bonus": int(threat_bonus(agent_id)),
    }


def log_profile_if_changed(agent_id: int) -> None:
    """Log only meaningful profile changes, heavily throttled.

    Raw counters can change every cast and previously produced thousands of
    lines.  The semantic signature below changes only when knowledge useful to
    target selection changes: new skills, role tier, or cast-outcome bucket.
    """
    try:
        summary = profile_summary(agent_id)
        aid = int(agent_id or 0)
        now = _now_ms()
        semantic = (
            int(summary.get("known_skill_count", 0)),
            int(summary.get("healer", 0)) // 40,
            int(summary.get("support", 0)) // 40,
            int(summary.get("caster", 0)) // 40,
            int(summary.get("offense", 0)) // 40,
            int(summary.get("finished", 0)) // 10,
            int(summary.get("interrupted", 0)) // 5,
            int(summary.get("stopped", 0)) // 5,
        )
        digest = hash(semantic)
        previous_digest = _LOGGED_PROFILE_HASH.get(aid)
        previous_tick = int(_LOGGED_PROFILE_TICK.get(aid, 0) or 0)
        if previous_digest == digest:
            return
        if previous_digest is not None and now - previous_tick < int(PROFILE_LOG_MIN_INTERVAL_MS):
            return
        _LOGGED_PROFILE_HASH[aid] = digest
        _LOGGED_PROFILE_TICK[aid] = int(now)
        # Make unnamed foes readable without relying on unstable name lookup.
        if str(summary.get("name", "?") or "?") == "?":
            summary["name"] = f"model:{int(summary.get('model_id', 0))}/prof:{int(observe(aid).primary)}"
        from Py4GWCoreLib.Builds.Skills import CombatDebug
        CombatDebug.log_event("ENEMY_KNOWLEDGE_PROFILE", **summary)
    except Exception:
        pass
