"""Always-on controller for the supplied Mind Burn fire hero template.

Recognised template core:
Flare / Rodgort's Invocation / Incendiary Bonds / Liquid Flame /
Glowing Gaze / Aura of Restoration / Mind Burn / Fire Attunement.

The controller keeps the two long-duration enchantments active, shares the
team's cluster anchor, staggers multiple fire heroes, and avoids wasting the
large packet spells on isolated or nearly dead enemies.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from Py4GWCoreLib import Agent, AgentArray, Map, Party, Player, Profession, Range, Routines, Skill, SkillBar, Utils

FLARE_ID = int(Skill.GetID('Flare') or 0)
RODGORT_ID = int(Skill.GetID('Rodgorts_Invocation') or Skill.GetID("Rodgort's_Invocation") or 0)
INCENDIARY_BONDS_ID = int(Skill.GetID('Incendiary_Bonds') or 0)
LIQUID_FLAME_ID = int(Skill.GetID('Liquid_Flame') or 0)
GLOWING_GAZE_ID = int(Skill.GetID('Glowing_Gaze') or 0)
AURA_OF_RESTORATION_ID = int(Skill.GetID('Aura_of_Restoration') or 0)
MIND_BURN_ID = int(Skill.GetID('Mind_Burn') or 0)
FIRE_ATTUNEMENT_ID = int(Skill.GetID('Fire_Attunement') or 0)
BURNING_ID = int(Skill.GetID('Burning') or 0)

_REQUIRED_IDS = frozenset(
    sid for sid in (
        FLARE_ID, RODGORT_ID, INCENDIARY_BONDS_ID, LIQUID_FLAME_ID,
        GLOWING_GAZE_ID, AURA_OF_RESTORATION_ID, MIND_BURN_ID,
        FIRE_ATTUNEMENT_ID,
    ) if sid > 0
)
_MANAGED_IDS = _REQUIRED_IDS

_SCAN_INTERVAL_MS = 85
_LOCK_REFRESH_MS = 2500
_COMMAND_TIMEOUT_MS = 3200
_COMMAND_GUARD_MS = 160
_BIG_NUKE_STAGGER_MS = 220
_TARGET_LOCK_MS = 900
_CAST_RANGE = float(Range.Spellcast.value)
_NEARBY = float(Range.Nearby.value)
_ADJACENT = float(Range.Adjacent.value)


@dataclass(slots=True)
class _PendingCommand:
    skill_id: int = 0
    slot: int = 0
    target_id: int = 0
    started_ms: int = 0
    start_recharge: int = 0
    purpose: str = ''


@dataclass(slots=True)
class _ControllerState:
    hero_index: int = 0
    hero_bar_index: int = -1
    hero_agent_id: int = 0
    managed_slots: tuple[int, ...] = ()
    locked_slots: set[int] = field(default_factory=set)
    last_lock_refresh_ms: int = 0
    last_scan_ms: int = 0
    last_command_ms: int = 0
    elite_ready_since_ms: int = 0
    pending: _PendingCommand = field(default_factory=_PendingCommand)
    matched_logged: bool = False
    lock_failed_logged: bool = False


_STATES: dict[int, _ControllerState] = {}
_LAST_MAP_ID = 0
_RUNTIME_LOGGED = False
_NO_MATCH_LOGGED = False
_TARGET_LOCKS: dict[tuple[int, int], int] = {}


def _now_ms() -> int:
    try:
        import PySystem
        return int(PySystem.get_tick_count64() or 0)
    except Exception:
        import time
        return int(time.monotonic() * 1000.0)


def _log(event: str, **fields) -> None:
    try:
        from Py4GWCoreLib.Builds.Skills import CombatDebug
        CombatDebug.log_event(str(event), **fields)
    except Exception:
        pass


def _skill_name(skill_id: int) -> str:
    try:
        return str(Skill.GetName(int(skill_id)) or int(skill_id))
    except Exception:
        return str(int(skill_id or 0))


def _hero_bar(index: int):
    try:
        return list(SkillBar.GetHeroSkillbar(int(index)) or [])
    except Exception:
        return []


def _bar_entries(index: int) -> list[tuple[int, int, object]]:
    rows: list[tuple[int, int, object]] = []
    for slot, data in enumerate(_hero_bar(index), start=1):
        try:
            sid = int(getattr(getattr(data, 'id', None), 'id', 0) or 0)
        except Exception:
            sid = 0
        rows.append((int(slot), sid, data))
    return rows


def _bar_ids(index: int) -> set[int]:
    return {sid for _, sid, _ in _bar_entries(index) if sid > 0}


def _matching_heroes() -> list[tuple[int, int, int]]:
    try:
        heroes = list(Party.GetHeroes() or [])
    except Exception:
        heroes = []
    result: list[tuple[int, int, int]] = []
    for bar_index, hero in enumerate(heroes):
        hero_id = int(getattr(hero, 'agent_id', 0) or 0)
        if hero_id <= 0:
            continue
        ids = _bar_ids(bar_index)
        if _REQUIRED_IDS and _REQUIRED_IDS.issubset(ids):
            result.append((bar_index + 1, bar_index, hero_id))
    return result


def _managed_slots(bar_index: int) -> tuple[int, ...]:
    return tuple(sorted(slot for slot, sid, _ in _bar_entries(bar_index) if sid in _MANAGED_IDS))


def _restore_native_ai(state: _ControllerState) -> None:
    restored = tuple(sorted(state.locked_slots))
    for slot in restored:
        try:
            Party.Heroes.SetSkillAIEnabled(int(state.hero_agent_id), int(slot), True)
        except Exception:
            pass
    if restored:
        _log('HERO_FIRE_NATIVE_AI_RESTORED', hero_index=state.hero_index, hero_id=state.hero_agent_id,
             slots=','.join(map(str, restored)))
    state.locked_slots.clear()


def _reconcile_states() -> list[_ControllerState]:
    matches = _matching_heroes()
    live = {hero_id for _, _, hero_id in matches}
    for hero_id in list(_STATES):
        if hero_id not in live:
            _restore_native_ai(_STATES.pop(hero_id))
    ordered: list[_ControllerState] = []
    for hero_index, bar_index, hero_id in matches:
        state = _STATES.get(hero_id)
        slots = _managed_slots(bar_index)
        if state is None:
            state = _ControllerState(hero_index=hero_index, hero_bar_index=bar_index,
                                     hero_agent_id=hero_id, managed_slots=slots)
            _STATES[hero_id] = state
        else:
            if state.hero_bar_index != bar_index or state.managed_slots != slots:
                _restore_native_ai(state)
                state.pending = _PendingCommand()
            state.hero_index = hero_index
            state.hero_bar_index = bar_index
            state.managed_slots = slots
        if not state.matched_logged:
            state.matched_logged = True
            _log('HERO_FIRE_MATCHED', hero_index=hero_index, hero_id=hero_id,
                 slots=','.join(map(str, slots)))
        ordered.append(state)
    return ordered


def _ensure_locked(state: _ControllerState, now_ms: int) -> bool:
    was_fully_locked = state.locked_slots == set(state.managed_slots)
    if was_fully_locked and now_ms - state.last_lock_refresh_ms < _LOCK_REFRESH_MS:
        return True
    ok = True
    for slot in state.managed_slots:
        try:
            Party.Heroes.SetSkillAIEnabled(int(state.hero_agent_id), int(slot), False)
            state.locked_slots.add(int(slot))
        except Exception:
            ok = False
    state.last_lock_refresh_ms = now_ms
    if ok:
        state.lock_failed_logged = False
        if not was_fully_locked:
            _log('HERO_FIRE_AI_LOCKED', hero_index=state.hero_index, hero_id=state.hero_agent_id,
                 slots=','.join(map(str, state.managed_slots)))
    elif not state.lock_failed_logged:
        state.lock_failed_logged = True
        _log('HERO_FIRE_AI_LOCK_FAILED', hero_index=state.hero_index, hero_id=state.hero_agent_id)
    return ok


def _entry(state: _ControllerState, skill_id: int) -> tuple[int, object] | None:
    for slot, sid, data in _bar_entries(state.hero_bar_index):
        if sid == int(skill_id):
            return slot, data
    return None


def _recharge(state: _ControllerState, skill_id: int) -> int:
    e = _entry(state, skill_id)
    if e is None:
        return -1
    try:
        return int(getattr(e[1], 'recharge', 0) or 0)
    except Exception:
        return 0


def _ready(state: _ControllerState, skill_id: int) -> bool:
    return _entry(state, skill_id) is not None and _recharge(state, skill_id) == 0


def _energy_current(state: _ControllerState) -> int:
    try:
        return int(max(0.0, float(Agent.GetEnergy(state.hero_agent_id) or 0.0)) *
                   max(0, int(Agent.GetMaxEnergy(state.hero_agent_id) or 0)))
    except Exception:
        return 0


def _energy_ratio(state: _ControllerState) -> float:
    try:
        return max(0.0, min(1.0, float(Agent.GetEnergy(state.hero_agent_id) or 0.0)))
    except Exception:
        return 0.0


def _can_pay(state: _ControllerState, skill_id: int) -> bool:
    try:
        return _energy_current(state) >= int(Skill.Data.GetEnergyCost(int(skill_id)) or 0)
    except Exception:
        return True


def _hero_can_cast(state: _ControllerState) -> bool:
    try:
        return not (Agent.IsDead(state.hero_agent_id) or Agent.IsKnockedDown(state.hero_agent_id)
                    or Agent.IsCasting(state.hero_agent_id) or Agent.IsMoving(state.hero_agent_id))
    except Exception:
        return False


def _distance(a_id: int, b_id: int) -> float:
    try:
        return float(Utils.Distance(Agent.GetXY(int(a_id)), Agent.GetXY(int(b_id))))
    except Exception:
        return 999999.0


def _valid_enemy(state: _ControllerState, enemy_id: int, max_range: float = _CAST_RANGE) -> bool:
    try:
        return bool(enemy_id > 0 and Agent.IsValid(enemy_id) and Agent.IsAlive(enemy_id)
                    and _distance(state.hero_agent_id, enemy_id) <= float(max_range))
    except Exception:
        return False


def _health(enemy_id: int) -> float:
    try:
        return float(Routines.Checks.Agents.GetHealth(int(enemy_id)))
    except Exception:
        try:
            return float(Agent.GetHealth(int(enemy_id)))
        except Exception:
            return 1.0


def _has_effect(agent_id: int, skill_id: int) -> bool:
    try:
        return bool(Routines.Checks.Agents.HasEffect(int(agent_id), int(skill_id)))
    except Exception:
        try:
            return bool(Routines.Checks.Effects.HasEffect(int(agent_id), int(skill_id)))
        except Exception:
            return False


def _cluster_anchor(state: _ControllerState) -> int:
    try:
        from Py4GWCoreLib.Builds.Skills import HeroClusterCoordinator
        return int(HeroClusterCoordinator.get_shared_cluster_anchor(
            origin_agent_id=state.hero_agent_id,
            range_value=_CAST_RANGE,
            minimum_enemies=2,
        ) or 0)
    except Exception:
        return int(Player.GetTargetID() or 0)


def _cleanup_anchor(state: _ControllerState) -> int:
    """Return the shared sequential-cleanup target for the Fire hero.

    Slot 3 deliberately pre-switches at the late anti-overkill thresholds, so
    the four Keystone Mesmers remain the primary finishers while the Elementalist
    starts pressure on the next common target.
    """
    try:
        from Py4GWCoreLib.Builds.Skills import CombatSense
        return int(CombatSense.pick_single_target_anchor(
            range_value=_CAST_RANGE,
            assignment_slot=3,
            consumer_role="fire_ele",
        ) or 0)
    except Exception:
        return 0


def _cluster_members(state: _ControllerState, anchor_id: int, radius: float = _NEARBY) -> list[int]:
    try:
        from Py4GWCoreLib.Builds.Skills import HeroClusterCoordinator
        return list(HeroClusterCoordinator.cluster_members(
            anchor_id,
            origin_agent_id=state.hero_agent_id,
            radius=radius,
            range_value=_CAST_RANGE,
        ) or [])
    except Exception:
        return [anchor_id] if _valid_enemy(state, anchor_id) else []


def _count(state: _ControllerState, target_id: int, radius: float) -> int:
    return len(_cluster_members(state, target_id, radius))


def _sweep_locks(now_ms: int) -> None:
    for key, until in list(_TARGET_LOCKS.items()):
        if int(until) <= now_ms:
            _TARGET_LOCKS.pop(key, None)


def _claim_target(skill_id: int, target_id: int, now_ms: int, duration_ms: int = _TARGET_LOCK_MS) -> bool:
    key = (int(skill_id), int(target_id))
    if int(_TARGET_LOCKS.get(key, 0) or 0) > now_ms:
        return False
    _TARGET_LOCKS[key] = now_ms + max(100, int(duration_ms))
    return True


def _pick_cluster_target(state: _ControllerState, skill_id: int, *, radius: float,
                         min_count: int = 2, high_health: bool = False,
                         active_only: bool = False, martial_preferred: bool = False) -> int:
    cleanup = _cleanup_anchor(state)
    if cleanup > 0 and _valid_enemy(state, cleanup):
        if (not high_health or _health(cleanup) >= 0.30) and (not active_only or Agent.IsCasting(cleanup) or Agent.IsAttacking(cleanup)):
            now_ms = _now_ms()
            if _claim_target(skill_id, cleanup, now_ms):
                return int(cleanup)
            return int(cleanup)
    anchor = _cluster_anchor(state)
    candidates = _cluster_members(state, anchor, _NEARBY * 1.35) if anchor > 0 else []
    if not candidates:
        candidates = [int(e) for e in AgentArray.GetEnemyArray() or [] if _valid_enemy(state, int(e))]
    now_ms = _now_ms()

    def profession_score(enemy_id: int) -> int:
        if not martial_preferred:
            return 0
        try:
            primary, _ = Agent.GetProfessions(enemy_id)
            p = int(getattr(primary, 'value', primary) or 0)
            martial = {
                int(getattr(Profession.Warrior, 'value', Profession.Warrior)),
                int(getattr(Profession.Ranger, 'value', Profession.Ranger)),
                int(getattr(Profession.Assassin, 'value', Profession.Assassin)),
                int(getattr(Profession.Dervish, 'value', Profession.Dervish)),
                int(getattr(Profession.Paragon, 'value', Profession.Paragon)),
            }
            return 0 if p in martial else 1
        except Exception:
            return 1

    scored: list[tuple[tuple, int]] = []
    for enemy_id in candidates:
        if not _valid_enemy(state, enemy_id):
            continue
        count = _count(state, enemy_id, radius)
        if count < min_count:
            continue
        if high_health and _health(enemy_id) < 0.30:
            continue
        if active_only:
            try:
                if not (Agent.IsCasting(enemy_id) or Agent.IsAttacking(enemy_id)):
                    continue
            except Exception:
                continue
        locked = int(_TARGET_LOCKS.get((int(skill_id), int(enemy_id)), 0) or 0) > now_ms
        scored.append(((locked, profession_score(enemy_id), -count,
                        -_health(enemy_id) if high_health else _health(enemy_id),
                        _distance(state.hero_agent_id, enemy_id), enemy_id), enemy_id))
    scored.sort(key=lambda item: item[0])
    for _, enemy_id in scored:
        if _claim_target(skill_id, enemy_id, now_ms):
            return int(enemy_id)
    return int(scored[0][1]) if scored else 0


def _log_fire_command(purpose: str) -> bool:
    # Flare is a high-frequency filler.  Keeping every request/confirm/timeout
    # in the synchronous combat log creates avoidable micro-stutter without
    # adding useful diagnostics.  Important maintenance and nuke casts remain.
    return str(purpose or "") != "single_cleanup_flare"


def _pending_confirmed(state: _ControllerState, pending: _PendingCommand) -> bool:
    try:
        if Agent.IsCasting(state.hero_agent_id) and int(Agent.GetCastingSkillID(state.hero_agent_id) or 0) == pending.skill_id:
            return True
    except Exception:
        pass
    if pending.skill_id in (AURA_OF_RESTORATION_ID, FIRE_ATTUNEMENT_ID):
        if _has_effect(state.hero_agent_id, pending.skill_id):
            return True
    return _recharge(state, pending.skill_id) > pending.start_recharge


def _process_pending(state: _ControllerState, now_ms: int) -> bool:
    p = state.pending
    if p.skill_id <= 0:
        return False
    if _pending_confirmed(state, p):
        if _log_fire_command(p.purpose):
            _log('HERO_FIRE_CAST_CONFIRMED', hero_index=state.hero_index, hero_id=state.hero_agent_id,
                 skill_id=p.skill_id, skill=_skill_name(p.skill_id), purpose=p.purpose, target_id=p.target_id)
        state.pending = _PendingCommand()
        return False
    if now_ms - p.started_ms <= _COMMAND_TIMEOUT_MS:
        return True
    if _log_fire_command(p.purpose):
        _log('HERO_FIRE_CAST_TIMEOUT', hero_index=state.hero_index, hero_id=state.hero_agent_id,
             skill_id=p.skill_id, skill=_skill_name(p.skill_id), purpose=p.purpose, target_id=p.target_id)
    state.pending = _PendingCommand()
    return False


def _request_cast(state: _ControllerState, skill_id: int, target_id: int, *, purpose: str) -> bool:
    entry = _entry(state, skill_id)
    if entry is None or not _ready(state, skill_id) or not _can_pay(state, skill_id):
        return False
    if state.pending.skill_id > 0 or not _hero_can_cast(state):
        return False
    now_ms = _now_ms()
    if now_ms - state.last_command_ms < _COMMAND_GUARD_MS:
        return False
    slot, _ = entry
    try:
        SkillBar.HeroUseSkill(int(target_id), int(slot), int(state.hero_index))
    except Exception as exc:
        _log('HERO_FIRE_CAST_ERROR', hero_index=state.hero_index, hero_id=state.hero_agent_id,
             skill_id=skill_id, purpose=purpose, error=type(exc).__name__)
        return False
    state.pending = _PendingCommand(skill_id=skill_id, slot=slot, target_id=int(target_id),
                                    started_ms=now_ms, start_recharge=max(0, _recharge(state, skill_id)),
                                    purpose=str(purpose))
    state.last_command_ms = now_ms
    if _log_fire_command(purpose):
        _log('HERO_FIRE_CAST_REQUESTED', hero_index=state.hero_index, hero_id=state.hero_agent_id,
             skill_id=skill_id, skill=_skill_name(skill_id), purpose=purpose, target_id=int(target_id))
    return True


def _try_maintenance(state: _ControllerState) -> bool:
    # Aura first so Fire Attunement itself already benefits from Aura's trigger.
    if not _has_effect(state.hero_agent_id, AURA_OF_RESTORATION_ID):
        return _request_cast(state, AURA_OF_RESTORATION_ID, state.hero_agent_id, purpose='maintain_aura_of_restoration')
    if not _has_effect(state.hero_agent_id, FIRE_ATTUNEMENT_ID):
        return _request_cast(state, FIRE_ATTUNEMENT_ID, state.hero_agent_id, purpose='maintain_fire_attunement')
    return False


def _try_incendiary(state: _ControllerState) -> bool:
    if not _ready(state, INCENDIARY_BONDS_ID):
        return False
    target = _pick_cluster_target(state, INCENDIARY_BONDS_ID, radius=_NEARBY, min_count=2, high_health=True)
    if target <= 0 or _has_effect(target, INCENDIARY_BONDS_ID):
        return False
    return _request_cast(state, INCENDIARY_BONDS_ID, target, purpose='cluster_incendiary_bonds')


def _try_mind_burn(state: _ControllerState, rank: int, now_ms: int) -> bool:
    if not _ready(state, MIND_BURN_ID) or _energy_ratio(state) < 0.55:
        state.elite_ready_since_ms = 0
        return False
    if state.elite_ready_since_ms <= 0:
        state.elite_ready_since_ms = now_ms
    if now_ms - state.elite_ready_since_ms < rank * _BIG_NUKE_STAGGER_MS:
        return False
    target = _pick_cluster_target(state, MIND_BURN_ID, radius=_ADJACENT, min_count=2,
                                  high_health=True, martial_preferred=True)
    if target <= 0:
        return False
    if _request_cast(state, MIND_BURN_ID, target, purpose='cluster_mind_burn'):
        state.elite_ready_since_ms = 0
        _log('HERO_FIRE_NUKE_TARGET', hero_index=state.hero_index, hero_id=state.hero_agent_id,
             skill='Mind_Burn', target_id=target, adjacent=_count(state, target, _ADJACENT))
        return True
    return False


def _try_rodgort(state: _ControllerState) -> bool:
    if not _ready(state, RODGORT_ID) or _energy_ratio(state) < 0.36:
        return False
    target = _pick_cluster_target(state, RODGORT_ID, radius=_NEARBY, min_count=2, high_health=True)
    if target <= 0:
        return False
    return _request_cast(state, RODGORT_ID, target, purpose='cluster_rodgorts_invocation')


def _try_liquid_flame(state: _ControllerState) -> bool:
    if not _ready(state, LIQUID_FLAME_ID):
        return False
    target = _pick_cluster_target(state, LIQUID_FLAME_ID, radius=_NEARBY, min_count=2, active_only=True)
    if target <= 0:
        return False
    return _request_cast(state, LIQUID_FLAME_ID, target, purpose='active_cluster_liquid_flame')


def _try_glowing_gaze(state: _ControllerState) -> bool:
    if not _ready(state, GLOWING_GAZE_ID):
        return False
    anchor = _cluster_anchor(state)
    candidates = _cluster_members(state, anchor, _NEARBY * 1.35) if anchor > 0 else []
    candidates = [enemy_id for enemy_id in candidates if _has_effect(enemy_id, BURNING_ID)]
    candidates.sort(key=lambda enemy_id: (_health(enemy_id), -_count(state, enemy_id, _NEARBY)))
    if not candidates:
        return False
    return _request_cast(state, GLOWING_GAZE_ID, candidates[0], purpose='burning_energy_glowing_gaze')


def _try_flare(state: _ControllerState) -> bool:
    if not _ready(state, FLARE_ID):
        return False
    target = _cleanup_anchor(state) or _cluster_anchor(state)
    if not _valid_enemy(state, target):
        return False
    return _request_cast(state, FLARE_ID, target, purpose='single_cleanup_flare')


def _run_state(state: _ControllerState, now_ms: int, rank: int) -> None:
    if now_ms - state.last_scan_ms < _SCAN_INTERVAL_MS:
        return
    state.last_scan_ms = now_ms
    if not _ensure_locked(state, now_ms):
        return
    if _process_pending(state, now_ms):
        return
    if not _hero_can_cast(state):
        return
    if _try_maintenance(state):
        return
    anchor = _cluster_anchor(state)
    if not _valid_enemy(state, anchor):
        return
    # Delayed bomb first, then the elite while the hero still has high Energy.
    if _try_incendiary(state):
        return
    if _try_mind_burn(state, rank, now_ms):
        return
    if _try_liquid_flame(state):
        return
    if _try_rodgort(state):
        return
    # Recover Energy as soon as a burning target exists, before falling back to Flare.
    if _try_glowing_gaze(state):
        return
    _try_flare(state)


def _restore_all() -> None:
    for state in list(_STATES.values()):
        _restore_native_ai(state)
    _STATES.clear()


def run(*, enabled: bool = True) -> None:
    global _LAST_MAP_ID, _RUNTIME_LOGGED, _NO_MATCH_LOGGED
    if not enabled:
        _restore_all()
        return
    try:
        map_id = int(Map.GetMapID() or 0)
    except Exception:
        map_id = 0
    if _LAST_MAP_ID and map_id != _LAST_MAP_ID:
        _restore_all()
    _LAST_MAP_ID = map_id
    try:
        if not Map.IsExplorable() or not Party.IsPartyLoaded():
            _restore_all()
            return
    except Exception:
        return
    if not _RUNTIME_LOGGED:
        _RUNTIME_LOGGED = True
        _log('HERO_FIRE_CONTROLLER_ACTIVE')
    states = _reconcile_states()
    if not states:
        if not _NO_MATCH_LOGGED:
            _NO_MATCH_LOGGED = True
            _log('HERO_FIRE_NO_MATCH')
        return
    _NO_MATCH_LOGGED = False
    now_ms = _now_ms()
    _sweep_locks(now_ms)
    for rank, state in enumerate(states):
        try:
            _run_state(state, now_ms, rank)
        except Exception as exc:
            _log('HERO_FIRE_CONTROLLER_ERROR', hero_index=state.hero_index, hero_id=state.hero_agent_id,
                 error=type(exc).__name__, detail=str(exc)[:160])
