"""Always-on offensive controller for the supplied Discord minion hero.

Recognised template core:
Discord / Animate Bone Minions / Death Nova / Putrid Bile / Enfeebling Blood
with Shield of Absorption / Protective Spirit / Aegis left to native GW hero AI.

The controller coordinates corpses, maintains an useful minion body count,
marks expendable front-line minions with Death Nova, primes clustered enemies
with Weakness + Putrid Bile, and then executes valid Discord targets.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from Py4GWCoreLib import Agent, AgentArray, Map, Party, Player, Profession, Range, Routines, Skill, SkillBar, Utils

DISCORD_ID = int(Skill.GetID('Discord') or 0)
ANIMATE_BONE_MINIONS_ID = int(Skill.GetID('Animate_Bone_Minions') or 0)
DEATH_NOVA_ID = int(Skill.GetID('Death_Nova') or 0)
PUTRID_BILE_ID = int(Skill.GetID('Putrid_Bile') or 0)
ENFEEBLING_BLOOD_ID = int(Skill.GetID('Enfeebling_Blood') or 0)
WEAKNESS_ID = int(Skill.GetID('Weakness') or 0)

_REQUIRED_IDS = frozenset(
    sid for sid in (DISCORD_ID, ANIMATE_BONE_MINIONS_ID, DEATH_NOVA_ID, PUTRID_BILE_ID, ENFEEBLING_BLOOD_ID)
    if sid > 0
)
_MANAGED_IDS = _REQUIRED_IDS

_SCAN_INTERVAL_MS = 100
_LOCK_REFRESH_MS = 2500
_COMMAND_TIMEOUT_MS = 3400
_COMMAND_GUARD_MS = 150
_CAST_RANGE = float(Range.Spellcast.value)
_NEARBY = float(Range.Nearby.value)
_ADJACENT = float(Range.Adjacent.value)
_DESIRED_MINIONS = 8
_EMERGENCY_MINIONS = 4
_CORPSE_LOCK_MS = 4200
_TARGET_LOCK_MS = 700


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
    result: list[tuple[int, int, object]] = []
    for slot, data in enumerate(_hero_bar(index), start=1):
        try:
            sid = int(getattr(getattr(data, 'id', None), 'id', 0) or 0)
        except Exception:
            sid = 0
        result.append((int(slot), sid, data))
    return result


def _bar_ids(index: int) -> set[int]:
    return {sid for _, sid, _ in _bar_entries(index) if sid > 0}


def _matching_heroes() -> list[tuple[int, int, int]]:
    try:
        heroes = list(Party.GetHeroes() or [])
    except Exception:
        heroes = []
    matches: list[tuple[int, int, int]] = []
    for bar_index, hero in enumerate(heroes):
        hero_id = int(getattr(hero, 'agent_id', 0) or 0)
        if hero_id <= 0:
            continue
        if _REQUIRED_IDS and _REQUIRED_IDS.issubset(_bar_ids(bar_index)):
            matches.append((bar_index + 1, bar_index, hero_id))
    return matches


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
        _log('HERO_DISCORD_MM_NATIVE_AI_RESTORED', hero_index=state.hero_index, hero_id=state.hero_agent_id,
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
        slots = _managed_slots(bar_index)
        state = _STATES.get(hero_id)
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
            _log('HERO_DISCORD_MM_MATCHED', hero_index=hero_index, hero_id=hero_id,
                 managed_slots=','.join(map(str, slots)), native_protection_slots='6,7,8')
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
            _log('HERO_DISCORD_MM_AI_LOCKED', hero_index=state.hero_index, hero_id=state.hero_agent_id,
                 slots=','.join(map(str, state.managed_slots)))
    elif not state.lock_failed_logged:
        state.lock_failed_logged = True
        _log('HERO_DISCORD_MM_AI_LOCK_FAILED', hero_index=state.hero_index, hero_id=state.hero_agent_id)
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


def _valid_enemy(state: _ControllerState, enemy_id: int) -> bool:
    try:
        return bool(enemy_id > 0 and Agent.IsValid(enemy_id) and Agent.IsAlive(enemy_id)
                    and _distance(state.hero_agent_id, enemy_id) <= _CAST_RANGE)
    except Exception:
        return False


def _health(agent_id: int) -> float:
    try:
        return float(Routines.Checks.Agents.GetHealth(int(agent_id)))
    except Exception:
        try:
            return float(Agent.GetHealth(int(agent_id)))
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
    """Return the common sequential-cleanup target for the Discord MM.

    Slot 2 moves the MM onto the next common target below the late anti-overkill
    threshold while Keystone Mesmers finish the nearly dead foe. Minions remain
    engine-controlled; this coordinates the hero's offensive spells safely.
    """
    try:
        from Py4GWCoreLib.Builds.Skills import CombatSense
        return int(CombatSense.pick_single_target_anchor(
            range_value=_CAST_RANGE,
            assignment_slot=2,
            consumer_role="discord_mm",
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


def _count(state: _ControllerState, target_id: int, radius: float = _NEARBY) -> int:
    return len(_cluster_members(state, target_id, radius))


def _own_minions(state: _ControllerState) -> list[int]:
    result: list[int] = []
    for minion_id in AgentArray.GetMinionArray() or []:
        minion_id = int(minion_id)
        try:
            if not Agent.IsAlive(minion_id):
                continue
            if int(Agent.GetOwnerID(minion_id) or 0) != int(state.hero_agent_id):
                continue
            result.append(minion_id)
        except Exception:
            continue
    return result


def _nearest_exploitable_corpse(state: _ControllerState) -> int:
    try:
        corpses = list(Routines.Agents.GetExploitableCorpses(_CAST_RANGE * 2.0) or [])
    except Exception:
        corpses = []
    corpses = [int(c) for c in corpses if _distance(state.hero_agent_id, int(c)) <= _CAST_RANGE]
    corpses.sort(key=lambda corpse_id: _distance(state.hero_agent_id, corpse_id))
    if not corpses:
        return 0
    return int(corpses[0])


def _death_nova_target(state: _ControllerState) -> int:
    candidates: list[tuple[tuple, int]] = []
    for minion_id in _own_minions(state):
        if _distance(state.hero_agent_id, minion_id) > _CAST_RANGE:
            continue
        if _has_effect(minion_id, DEATH_NOVA_ID):
            continue
        hp = _health(minion_id)
        try:
            near_enemies = sum(
                1 for enemy_id in AgentArray.GetEnemyArray() or []
                if Agent.IsAlive(int(enemy_id)) and Utils.Distance(Agent.GetXY(minion_id), Agent.GetXY(int(enemy_id))) <= _ADJACENT * 1.5
            )
        except Exception:
            near_enemies = 0
        if hp > 0.78 and near_enemies <= 0:
            continue
        candidates.append(((0 if near_enemies > 0 else 1, hp, -near_enemies, minion_id), minion_id))
    candidates.sort(key=lambda item: item[0])
    return int(candidates[0][1]) if candidates else 0


def _physical_profession(enemy_id: int) -> bool:
    try:
        primary, _ = Agent.GetProfessions(enemy_id)
        p = int(getattr(primary, 'value', primary) or 0)
        return p in {
            int(getattr(Profession.Warrior, 'value', Profession.Warrior)),
            int(getattr(Profession.Ranger, 'value', Profession.Ranger)),
            int(getattr(Profession.Assassin, 'value', Profession.Assassin)),
            int(getattr(Profession.Dervish, 'value', Profession.Dervish)),
            int(getattr(Profession.Paragon, 'value', Profession.Paragon)),
        }
    except Exception:
        return False


def _pick_enfeebling_target(state: _ControllerState) -> int:
    anchor = _cluster_anchor(state)
    candidates = _cluster_members(state, anchor, _NEARBY * 1.4) if anchor > 0 else []
    scored: list[tuple[tuple, int]] = []
    for enemy_id in candidates:
        if not _valid_enemy(state, enemy_id) or _has_effect(enemy_id, WEAKNESS_ID):
            continue
        pack = _cluster_members(state, enemy_id, _NEARBY)
        physical = sum(1 for member in pack if _physical_profession(member))
        attacking = 0
        for member in pack:
            try:
                attacking += 1 if Agent.IsAttacking(member) else 0
            except Exception:
                pass
        scored.append(((-physical, -attacking, -len(pack), _health(enemy_id), enemy_id), enemy_id))
    scored.sort(key=lambda item: item[0])
    if scored and (-scored[0][0][0] >= 1 or -scored[0][0][2] >= 3):
        return int(scored[0][1])
    return 0


def _pick_putrid_target(state: _ControllerState) -> int:
    anchor = _cluster_anchor(state)
    candidates = _cluster_members(state, anchor, _NEARBY * 1.4) if anchor > 0 else []
    candidates = [
        enemy_id for enemy_id in candidates
        if _valid_enemy(state, enemy_id) and not _has_effect(enemy_id, PUTRID_BILE_ID)
        and _count(state, enemy_id, _NEARBY) >= 2
    ]
    candidates.sort(key=lambda enemy_id: (
        0 if 0.12 <= _health(enemy_id) <= 0.55 else 1,
        _health(enemy_id),
        -_count(state, enemy_id, _NEARBY),
        enemy_id,
    ))
    return int(candidates[0]) if candidates else 0


def _discord_eligible(enemy_id: int) -> bool:
    try:
        return bool(Agent.IsConditioned(enemy_id) and (Agent.IsHexed(enemy_id) or Agent.IsEnchanted(enemy_id)))
    except Exception:
        return False


def _pick_discord_target(state: _ControllerState) -> int:
    cleanup = _cleanup_anchor(state)
    if cleanup > 0 and _valid_enemy(state, cleanup) and _discord_eligible(cleanup):
        return int(cleanup)
    anchor = _cluster_anchor(state)
    candidates = _cluster_members(state, anchor, _NEARBY * 1.5) if anchor > 0 else []
    if not candidates:
        candidates = [int(e) for e in AgentArray.GetEnemyArray() or [] if _valid_enemy(state, int(e))]
    candidates = [enemy_id for enemy_id in candidates if _discord_eligible(enemy_id)]
    candidates.sort(key=lambda enemy_id: (
        _health(enemy_id),
        -_count(state, enemy_id, _NEARBY),
        _distance(state.hero_agent_id, enemy_id),
        enemy_id,
    ))
    return int(candidates[0]) if candidates else 0


def _pending_confirmed(state: _ControllerState, pending: _PendingCommand) -> bool:
    try:
        if Agent.IsCasting(state.hero_agent_id) and int(Agent.GetCastingSkillID(state.hero_agent_id) or 0) == pending.skill_id:
            return True
    except Exception:
        pass
    return _recharge(state, pending.skill_id) > pending.start_recharge


def _process_pending(state: _ControllerState, now_ms: int) -> bool:
    p = state.pending
    if p.skill_id <= 0:
        return False
    if _pending_confirmed(state, p):
        _log('HERO_DISCORD_MM_CAST_CONFIRMED', hero_index=state.hero_index, hero_id=state.hero_agent_id,
             skill_id=p.skill_id, skill=_skill_name(p.skill_id), purpose=p.purpose, target_id=p.target_id)
        state.pending = _PendingCommand()
        return False
    if now_ms - p.started_ms <= _COMMAND_TIMEOUT_MS:
        return True
    _log('HERO_DISCORD_MM_CAST_TIMEOUT', hero_index=state.hero_index, hero_id=state.hero_agent_id,
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
        _log('HERO_DISCORD_MM_CAST_ERROR', hero_index=state.hero_index, hero_id=state.hero_agent_id,
             skill_id=skill_id, purpose=purpose, error=type(exc).__name__)
        return False
    state.pending = _PendingCommand(skill_id=skill_id, slot=slot, target_id=int(target_id),
                                    started_ms=now_ms, start_recharge=max(0, _recharge(state, skill_id)),
                                    purpose=str(purpose))
    state.last_command_ms = now_ms
    _log('HERO_DISCORD_MM_CAST_REQUESTED', hero_index=state.hero_index, hero_id=state.hero_agent_id,
         skill_id=skill_id, skill=_skill_name(skill_id), purpose=purpose, target_id=int(target_id))
    return True


def _try_animate(state: _ControllerState, *, emergency_only: bool = False) -> bool:
    if not _ready(state, ANIMATE_BONE_MINIONS_ID):
        return False
    count = len(_own_minions(state))
    threshold = _EMERGENCY_MINIONS if emergency_only else _DESIRED_MINIONS
    if count >= threshold:
        return False
    corpse = _nearest_exploitable_corpse(state)
    if corpse <= 0:
        return False
    if _request_cast(state, ANIMATE_BONE_MINIONS_ID, corpse, purpose='rebuild_bone_minions'):
        try:
            from Py4GWCoreLib.GlobalCache.WhiteboardLocks import post_minion_lock
            post_minion_lock(corpse, skill_id=ANIMATE_BONE_MINIONS_ID, aftercast_delay=_CORPSE_LOCK_MS)
        except Exception:
            pass
        _log('HERO_DISCORD_MM_CORPSE_RESERVED', hero_index=state.hero_index, hero_id=state.hero_agent_id,
             corpse_id=corpse, minion_count=count)
        return True
    return False


def _run_state(state: _ControllerState, now_ms: int) -> None:
    if now_ms - state.last_scan_ms < _SCAN_INTERVAL_MS:
        return
    state.last_scan_ms = now_ms
    if not _ensure_locked(state, now_ms):
        return
    if _process_pending(state, now_ms):
        return
    if not _hero_can_cast(state):
        return

    own_minion_count = len(_own_minions(state))
    # Rebuild a collapsed front line before spending time on damage spells.
    if own_minion_count < _EMERGENCY_MINIONS and _try_animate(state, emergency_only=True):
        return

    nova_target = _death_nova_target(state)
    if nova_target > 0 and _ready(state, DEATH_NOVA_ID):
        if _request_cast(state, DEATH_NOVA_ID, nova_target, purpose='frontline_death_nova'):
            return

    anchor = _cluster_anchor(state)
    if _valid_enemy(state, anchor):
        enfeeble_target = _pick_enfeebling_target(state)
        if enfeeble_target > 0 and _ready(state, ENFEEBLING_BLOOD_ID):
            if _request_cast(state, ENFEEBLING_BLOOD_ID, enfeeble_target, purpose='physical_cluster_enfeebling_blood'):
                return

        putrid_target = _pick_putrid_target(state)
        if putrid_target > 0 and _ready(state, PUTRID_BILE_ID):
            if _request_cast(state, PUTRID_BILE_ID, putrid_target, purpose='execution_cluster_putrid_bile'):
                return

        discord_target = _pick_discord_target(state)
        if discord_target > 0 and _ready(state, DISCORD_ID):
            if _request_cast(state, DISCORD_ID, discord_target, purpose='qualified_execution_discord'):
                _log('HERO_DISCORD_MM_DISCORD_TARGET', hero_index=state.hero_index,
                     hero_id=state.hero_agent_id, target_id=discord_target,
                     hp=round(_health(discord_target), 3), nearby=_count(state, discord_target, _NEARBY))
                return

    # Keep building toward the normal cap when there is no urgent Discord target.
    _try_animate(state, emergency_only=False)


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
        _log('HERO_DISCORD_MM_CONTROLLER_ACTIVE')
    states = _reconcile_states()
    if not states:
        if not _NO_MATCH_LOGGED:
            _NO_MATCH_LOGGED = True
            _log('HERO_DISCORD_MM_NO_MATCH')
        return
    _NO_MATCH_LOGGED = False
    now_ms = _now_ms()
    for state in states:
        try:
            _run_state(state, now_ms)
        except Exception as exc:
            _log('HERO_DISCORD_MM_CONTROLLER_ERROR', hero_index=state.hero_index, hero_id=state.hero_agent_id,
                 error=type(exc).__name__, detail=str(exc)[:160])
