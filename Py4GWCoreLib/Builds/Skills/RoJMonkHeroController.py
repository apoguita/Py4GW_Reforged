"""Low-overhead controller for owned Mo/Me Ray of Judgment heroes.

Designed for Kay's HR/RoJ adaptive team:
- two or more owned RoJ Monk heroes can copy RoJ from one another with Arcane Mimicry;
- Mimicry is always resolved before Arcane Echo, so Echo never copies Mimicry;
- Auspicious Incantation may prime Arcane Echo when equipped;
- Arcane Echo then copies the next Ray of Judgment;
- all resulting RoJ copies are cast on the shared HeroAI/team cluster;
- only the RoJ/copy engine is locked. Healing/cleanse/support skills remain under native Hero AI.

Logging is event-only (match, request, confirmation, error); there is no per-frame
combat telemetry or target-history scan.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from Py4GWCoreLib import Agent, Map, Party, Player, Range, Routines, Skill, SkillBar, Utils

RAY_OF_JUDGMENT_ID = int(Skill.GetID("Ray_of_Judgment") or 0)
ARCANE_MIMICRY_ID = int(Skill.GetID("Arcane_Mimicry") or 0)
ARCANE_ECHO_ID = int(Skill.GetID("Arcane_Echo") or 0)
AUSPICIOUS_INCANTATION_ID = int(Skill.GetID("Auspicious_Incantation") or 0)

_MANAGED_BASE_IDS = frozenset(
    sid for sid in (
        RAY_OF_JUDGMENT_ID,
        ARCANE_MIMICRY_ID,
        ARCANE_ECHO_ID,
        AUSPICIOUS_INCANTATION_ID,
    ) if sid > 0
)

_SCAN_INTERVAL_MS = 90
_LOCK_REFRESH_MS = 2500
_COMMAND_TIMEOUT_MS = 3300
_COMMAND_GUARD_MS = 170
_ROJ_TEAM_STAGGER_MS = 420
_CAST_RANGE = float(Range.Spellcast.value)
_NEARBY = float(Range.Nearby.value)


@dataclass(slots=True)
class _PendingCommand:
    skill_id: int = 0
    slot: int = 0
    target_id: int = 0
    started_ms: int = 0
    start_recharge: int = 0
    purpose: str = ""


@dataclass(slots=True)
class _ControllerState:
    hero_index: int
    hero_bar_index: int
    hero_agent_id: int
    managed_slots: tuple[int, ...] = ()
    locked_slots: set[int] = field(default_factory=set)
    base_roj_slot: int = 0
    mimicry_slot: int = 0
    echo_slot: int = 0
    auspicious_slot: int = 0
    transaction_locked: bool = False
    last_lock_refresh_ms: int = 0
    last_scan_ms: int = 0
    last_command_ms: int = 0
    pending: _PendingCommand = field(default_factory=_PendingCommand)
    matched_logged: bool = False


_STATES: dict[int, _ControllerState] = {}
_LAST_MAP_ID = 0
_RUNTIME_LOGGED = False
_LAST_ROJ_TEAM_CAST_MS = 0
_LAST_ROJ_TEAM_TARGET = 0
_DISCOVERED_HEROES: set[int] = set()


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


def _hero_bar(index: int):
    try:
        return list(SkillBar.GetHeroSkillbar(int(index)) or [])
    except Exception:
        return []


def _bar_entries(index: int) -> list[tuple[int, int, object]]:
    rows: list[tuple[int, int, object]] = []
    for slot, data in enumerate(_hero_bar(index), start=1):
        try:
            sid = int(getattr(getattr(data, "id", None), "id", 0) or 0)
        except Exception:
            sid = 0
        rows.append((slot, sid, data))
    return rows


def _bar_ids(index: int) -> set[int]:
    return {sid for _, sid, _ in _bar_entries(index) if sid > 0}


def _matching_heroes() -> list[tuple[int, int, int]]:
    """Return only heroes proven to have a *native* RoJ bar.

    A transient RoJ created by Arcane Mimicry / Arcane Echo must never make a
    SoJ hero eligible as a donor.  We therefore discover a RoJ hero only while
    all three base skills are simultaneously visible: native RoJ + Mimicry +
    Arcane Echo.  Once discovered, the hero stays eligible while copy slots
    temporarily transform.
    """
    try:
        heroes = list(Party.GetHeroes() or [])
    except Exception:
        heroes = []
    result: list[tuple[int, int, int]] = []
    for bar_index, hero in enumerate(heroes):
        hero_id = int(getattr(hero, "agent_id", 0) or 0)
        if hero_id <= 0:
            continue
        ids = _bar_ids(bar_index)
        if (RAY_OF_JUDGMENT_ID > 0 and ARCANE_MIMICRY_ID > 0 and ARCANE_ECHO_ID > 0
                and RAY_OF_JUDGMENT_ID in ids
                and ARCANE_MIMICRY_ID in ids
                and ARCANE_ECHO_ID in ids):
            _DISCOVERED_HEROES.add(hero_id)
        if hero_id in _DISCOVERED_HEROES:
            result.append((bar_index + 1, bar_index, hero_id))
    return result


def _managed_slots(bar_index: int) -> tuple[int, ...]:
    # Copies transform Echo/Mimicry slots into Ray of Judgment. Keep those slots
    # locked by remembering their original slots in state.
    return tuple(sorted(
        slot for slot, sid, _ in _bar_entries(bar_index)
        if sid in _MANAGED_BASE_IDS
    ))


def _restore_native_ai(state: _ControllerState) -> None:
    state.transaction_locked = False
    for slot in range(1, 9):
        try:
            Party.Heroes.SetSkillAIEnabled(int(state.hero_agent_id), int(slot), True)
        except Exception:
            pass
    for slot in tuple(sorted(state.locked_slots)):
        try:
            Party.Heroes.SetSkillAIEnabled(int(state.hero_agent_id), int(slot), True)
        except Exception:
            pass
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
            entries = _bar_entries(bar_index)
            roj_slot = next((slot for slot, sid, _ in entries if sid == RAY_OF_JUDGMENT_ID), 0)
            mimic_slot = next((slot for slot, sid, _ in entries if sid == ARCANE_MIMICRY_ID), 0)
            echo_slot = next((slot for slot, sid, _ in entries if sid == ARCANE_ECHO_ID), 0)
            ausp_slot = next((slot for slot, sid, _ in entries if sid == AUSPICIOUS_INCANTATION_ID), 0)
            state = _ControllerState(
                hero_index, bar_index, hero_id, managed_slots=slots,
                base_roj_slot=roj_slot, mimicry_slot=mimic_slot, echo_slot=echo_slot,
                auspicious_slot=ausp_slot,
            )
            _STATES[hero_id] = state
        else:
            state.hero_index = hero_index
            state.hero_bar_index = bar_index
            # Preserve original managed slots while Mimicry/Echo are transformed.
            if slots:
                state.managed_slots = tuple(sorted(set(state.managed_slots) | set(slots)))
        if not state.matched_logged:
            state.matched_logged = True
            _log("HERO_ROJ_MATCHED", hero_index=hero_index, hero_id=hero_id,
                 managed_slots=",".join(map(str, state.managed_slots)))
        ordered.append(state)
    return ordered


def _ensure_locked(state: _ControllerState, now_ms: int) -> bool:
    if state.locked_slots == set(state.managed_slots) and now_ms - state.last_lock_refresh_ms < _LOCK_REFRESH_MS:
        return True
    ok = True
    for slot in state.managed_slots:
        try:
            Party.Heroes.SetSkillAIEnabled(int(state.hero_agent_id), int(slot), False)
            state.locked_slots.add(int(slot))
        except Exception:
            ok = False
    state.last_lock_refresh_ms = now_ms
    return ok


def _set_transaction_lock(state: _ControllerState, enabled: bool) -> None:
    """Temporarily suppress native Hero AI during the Echo transaction.

    This is intentionally short-lived: from just before Arcane Echo until the
    mandatory next Ray of Judgment has been issued.  It prevents a heal/cleanse
    spell from being the spell copied by Arcane Echo.
    """
    if enabled == state.transaction_locked:
        return
    state.transaction_locked = enabled
    if enabled:
        for slot in range(1, 9):
            try:
                Party.Heroes.SetSkillAIEnabled(int(state.hero_agent_id), int(slot), False)
            except Exception:
                pass
        _log("HERO_ROJ_TRANSACTION_LOCK", hero_index=state.hero_index, hero_id=state.hero_agent_id, enabled=True)
    else:
        # Keep copy-engine slots disabled, return all other slots to native Hero AI.
        for slot in range(1, 9):
            if slot in state.managed_slots:
                continue
            try:
                Party.Heroes.SetSkillAIEnabled(int(state.hero_agent_id), int(slot), True)
            except Exception:
                pass
        _log("HERO_ROJ_TRANSACTION_LOCK", hero_index=state.hero_index, hero_id=state.hero_agent_id, enabled=False)


def _slot_skill_id(state: _ControllerState, slot: int) -> int:
    for s, sid, _ in _bar_entries(state.hero_bar_index):
        if s == int(slot):
            return int(sid)
    return 0


def _entry_for_slot(state: _ControllerState, slot: int):
    for s, sid, data in _bar_entries(state.hero_bar_index):
        if s == int(slot):
            return int(sid), data
    return None


def _entry_by_id(state: _ControllerState, skill_id: int):
    for slot, sid, data in _bar_entries(state.hero_bar_index):
        if sid == int(skill_id):
            return slot, data
    return None


def _entries_by_id(state: _ControllerState, skill_id: int) -> list[tuple[int, object]]:
    return [(slot, data) for slot, sid, data in _bar_entries(state.hero_bar_index) if sid == int(skill_id)]


def _recharge_data(data: object) -> int:
    try:
        return int(getattr(data, "recharge", 0) or 0)
    except Exception:
        return 0


def _ready_entry(state: _ControllerState, skill_id: int):
    for slot, data in _entries_by_id(state, skill_id):
        if _recharge_data(data) == 0:
            return slot, data
    return None


def _energy_current(state: _ControllerState) -> int:
    try:
        return int(float(Agent.GetEnergy(state.hero_agent_id) or 0.0) *
                   int(Agent.GetMaxEnergy(state.hero_agent_id) or 0))
    except Exception:
        return 0


def _can_pay(state: _ControllerState, skill_id: int) -> bool:
    try:
        return _energy_current(state) >= int(Skill.Data.GetEnergyCost(int(skill_id)) or 0)
    except Exception:
        return True


def _hero_can_cast(state: _ControllerState) -> bool:
    try:
        return not (
            Agent.IsDead(state.hero_agent_id)
            or Agent.IsKnockedDown(state.hero_agent_id)
            or Agent.IsCasting(state.hero_agent_id)
            or Agent.IsMoving(state.hero_agent_id)
        )
    except Exception:
        return False


def _distance(a_id: int, b_id: int) -> float:
    try:
        return float(Utils.Distance(Agent.GetXY(int(a_id)), Agent.GetXY(int(b_id))))
    except Exception:
        return 999999.0


def _valid_enemy(state: _ControllerState, enemy_id: int) -> bool:
    try:
        return bool(
            enemy_id > 0 and Agent.IsValid(enemy_id) and Agent.IsAlive(enemy_id)
            and _distance(state.hero_agent_id, enemy_id) <= _CAST_RANGE
        )
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
        return 0


def _cleanup_anchor(state: _ControllerState) -> int:
    try:
        from Py4GWCoreLib.Builds.Skills import CombatSense
        return int(CombatSense.pick_single_target_anchor(
            range_value=_CAST_RANGE,
            assignment_slot=0,
            consumer_role="hero_roj",
        ) or 0)
    except Exception:
        return 0


def _count_packet(state: _ControllerState, anchor_id: int) -> int:
    if anchor_id <= 0:
        return 0
    try:
        from Py4GWCoreLib.Builds.Skills import HeroClusterCoordinator
        return len(list(HeroClusterCoordinator.cluster_members(
            int(anchor_id),
            origin_agent_id=state.hero_agent_id,
            radius=_NEARBY,
            range_value=_CAST_RANGE,
        ) or []))
    except Exception:
        return 1 if _valid_enemy(state, anchor_id) else 0


def _roj_target(state: _ControllerState) -> tuple[int, int]:
    anchor = _cluster_anchor(state)
    if _valid_enemy(state, anchor):
        return int(anchor), max(1, _count_packet(state, anchor))
    cleanup = _cleanup_anchor(state)
    if _valid_enemy(state, cleanup):
        try:
            hp = float(Agent.GetHealth(cleanup))
        except Exception:
            hp = 1.0
        # Avoid spending RoJ on an almost dead cleanup target.
        if hp >= 0.35:
            return int(cleanup), 1
    return 0, 0


def _pending_confirmed(state: _ControllerState, pending: _PendingCommand) -> bool:
    try:
        if Agent.IsCasting(state.hero_agent_id) and int(Agent.GetCastingSkillID(state.hero_agent_id) or 0) == pending.skill_id:
            return True
    except Exception:
        pass
    # Recharge or slot transformation both count as a confirmed activation.
    for slot, sid, data in _bar_entries(state.hero_bar_index):
        if slot != pending.slot:
            continue
        if sid != pending.skill_id:
            return True
        if _recharge_data(data) > pending.start_recharge:
            return True
    return False


def _process_pending(state: _ControllerState, now_ms: int) -> bool:
    p = state.pending
    if p.skill_id <= 0:
        return False
    if _pending_confirmed(state, p):
        _log("HERO_ROJ_CAST_CONFIRMED", hero_index=state.hero_index, hero_id=state.hero_agent_id,
             skill_id=p.skill_id, slot=p.slot, target_id=p.target_id, purpose=p.purpose)
        state.pending = _PendingCommand()
        return False
    if now_ms - p.started_ms <= _COMMAND_TIMEOUT_MS:
        return True
    _log("HERO_ROJ_CAST_TIMEOUT", hero_index=state.hero_index, hero_id=state.hero_agent_id,
         skill_id=p.skill_id, slot=p.slot, purpose=p.purpose)
    state.pending = _PendingCommand()
    return False


def _request_slot(state: _ControllerState, slot: int, skill_id: int, target_id: int, *, purpose: str) -> bool:
    if state.pending.skill_id > 0 or not _hero_can_cast(state):
        return False
    if not _can_pay(state, skill_id):
        return False
    now_ms = _now_ms()
    if now_ms - state.last_command_ms < _COMMAND_GUARD_MS:
        return False
    current = next(((sid, data) for s, sid, data in _bar_entries(state.hero_bar_index) if s == slot), None)
    if current is None or int(current[0]) != int(skill_id) or _recharge_data(current[1]) != 0:
        return False
    try:
        SkillBar.HeroUseSkill(int(target_id), int(slot), int(state.hero_index))
    except Exception as exc:
        _log("HERO_ROJ_CAST_ERROR", hero_index=state.hero_index, hero_id=state.hero_agent_id,
             skill_id=skill_id, slot=slot, purpose=purpose, error=type(exc).__name__)
        return False
    state.pending = _PendingCommand(
        skill_id=int(skill_id), slot=int(slot), target_id=int(target_id),
        started_ms=now_ms, start_recharge=_recharge_data(current[1]), purpose=str(purpose)
    )
    state.last_command_ms = now_ms
    _log("HERO_ROJ_CAST_REQUESTED", hero_index=state.hero_index, hero_id=state.hero_agent_id,
         skill_id=skill_id, slot=slot, target_id=int(target_id), purpose=purpose)
    return True


def _other_roj_donor(state: _ControllerState, states: list[_ControllerState]) -> int:
    donors = [
        other for other in states
        if other.hero_agent_id != state.hero_agent_id
        and other.hero_agent_id in _DISCOVERED_HEROES
        and other.base_roj_slot > 0
        and Agent.IsAlive(other.hero_agent_id)
        and _distance(state.hero_agent_id, other.hero_agent_id) <= _CAST_RANGE
    ]
    donors.sort(key=lambda other: (other.hero_index, other.hero_agent_id))
    return int(donors[0].hero_agent_id) if donors else 0


def _try_mimicry(state: _ControllerState, states: list[_ControllerState]) -> bool:
    entry = _ready_entry(state, ARCANE_MIMICRY_ID)
    if entry is None:
        return False
    donor = _other_roj_donor(state, states)
    if donor <= 0:
        return False
    return _request_slot(state, entry[0], ARCANE_MIMICRY_ID, donor, purpose="copy_other_hero_roj")


def _try_auspicious(state: _ControllerState) -> bool:
    # Auspicious must be immediately before Arcane Echo whenever both are ready.
    if state.echo_slot <= 0 or state.auspicious_slot <= 0:
        return False
    echo = _entry_for_slot(state, state.echo_slot)
    ausp = _entry_for_slot(state, state.auspicious_slot)
    if not echo or not ausp:
        return False
    if int(echo[0]) != ARCANE_ECHO_ID or _recharge_data(echo[1]) != 0:
        return False
    if int(ausp[0]) != AUSPICIOUS_INCANTATION_ID or _recharge_data(ausp[1]) != 0:
        return False
    return _request_slot(state, state.auspicious_slot, AUSPICIOUS_INCANTATION_ID,
                         state.hero_agent_id, purpose="prime_arcane_echo_energy")


def _try_arcane_echo(state: _ControllerState) -> bool:
    # Echo is allowed only after Mimicry has resolved away from its base skill.
    # Once Echo is requested we freeze native Hero AI until the next RoJ request,
    # guaranteeing that Arcane Echo can only copy Ray of Judgment.
    if state.echo_slot <= 0:
        return False
    if state.mimicry_slot > 0 and _slot_skill_id(state, state.mimicry_slot) == ARCANE_MIMICRY_ID:
        # Mimicry is still visible/ready; resolve that copy first.
        mim = _entry_for_slot(state, state.mimicry_slot)
        if mim and _recharge_data(mim[1]) == 0:
            return False
    echo = _entry_for_slot(state, state.echo_slot)
    if not echo or int(echo[0]) != ARCANE_ECHO_ID or _recharge_data(echo[1]) != 0:
        return False
    target, _packet = _roj_target(state)
    if target <= 0:
        return False
    _set_transaction_lock(state, True)
    if _request_slot(state, state.echo_slot, ARCANE_ECHO_ID, state.hero_agent_id, purpose="echo_next_roj"):
        return True
    _set_transaction_lock(state, False)
    return False


def _try_roj(state: _ControllerState, now_ms: int, rank: int) -> bool:
    global _LAST_ROJ_TEAM_CAST_MS, _LAST_ROJ_TEAM_TARGET
    target, packet_size = _roj_target(state)
    if target <= 0:
        return False

    ready = None
    # During the Echo transaction, force the *native* RoJ slot as the very next
    # spell.  Outside that transaction, consume any available RoJ copy.
    if state.transaction_locked and state.base_roj_slot > 0:
        cur = _entry_for_slot(state, state.base_roj_slot)
        if cur and int(cur[0]) == RAY_OF_JUDGMENT_ID and _recharge_data(cur[1]) == 0:
            ready = (state.base_roj_slot, cur[1])
    if ready is None:
        ready = _ready_entry(state, RAY_OF_JUDGMENT_ID)
    if ready is None:
        return False

    elapsed = now_ms - int(_LAST_ROJ_TEAM_CAST_MS or 0)
    required = int(rank) * _ROJ_TEAM_STAGGER_MS
    if target == int(_LAST_ROJ_TEAM_TARGET or 0) and elapsed < required:
        return False

    purpose = "echo_mandatory_next_roj" if state.transaction_locked else f"adaptive_cluster_roj_packet{packet_size}"
    if _request_slot(state, ready[0], RAY_OF_JUDGMENT_ID, target, purpose=purpose):
        _LAST_ROJ_TEAM_CAST_MS = now_ms
        _LAST_ROJ_TEAM_TARGET = target
        _log("HERO_ROJ_PACKET_CAST", hero_index=state.hero_index, hero_id=state.hero_agent_id,
             target_id=target, packet_size=packet_size, copied_slot=int(ready[0]), purpose=purpose)
        if state.transaction_locked:
            # The command has been issued atomically while every other Hero skill
            # is disabled; safe to return support slots to native AI now.
            _set_transaction_lock(state, False)
        return True
    return False


def _run_state(state: _ControllerState, states: list[_ControllerState], now_ms: int, rank: int) -> None:
    if now_ms - state.last_scan_ms < _SCAN_INTERVAL_MS:
        return
    state.last_scan_ms = now_ms
    if not _ensure_locked(state, now_ms):
        return
    if _process_pending(state, now_ms):
        return
    if not _hero_can_cast(state):
        return

    # Hard validation: if Mimicry transformed, it is allowed to become RoJ only.
    if state.mimicry_slot > 0:
        mim_sid = _slot_skill_id(state, state.mimicry_slot)
        if mim_sid not in (0, ARCANE_MIMICRY_ID, RAY_OF_JUDGMENT_ID):
            _log("HERO_ROJ_MIMICRY_WRONG_COPY", hero_index=state.hero_index, hero_id=state.hero_agent_id,
                 slot=state.mimicry_slot, copied_skill_id=mim_sid, expected_skill_id=RAY_OF_JUDGMENT_ID)
            return

    # 1) Native-RoJ donor only.  2) Auspicious immediately before Echo whenever
    # available.  3) Echo.  4) mandatory next cast = native RoJ under transaction
    # lock.  5) consume remaining copied RoJs normally.
    if _try_mimicry(state, states):
        return

    # If Mimicry has transformed to RoJ, setup may proceed. If it is still the
    # base skill but on recharge, we may still use Echo on native RoJ.
    if _try_auspicious(state):
        return
    if _try_arcane_echo(state):
        return
    _try_roj(state, now_ms, rank)


def _restore_all() -> None:
    for state in list(_STATES.values()):
        _restore_native_ai(state)
    _STATES.clear()
    _DISCOVERED_HEROES.clear()


def run(*, enabled: bool = True) -> None:
    global _LAST_MAP_ID, _RUNTIME_LOGGED
    if not enabled:
        _restore_all()
        return
    try:
        map_id = int(Map.GetMapID() or 0)
        if not Map.IsExplorable() or not Party.IsPartyLoaded():
            _restore_all()
            return
        # Only the leader/owner process should issue hero commands.
        if int(Player.GetAgentID() or 0) != int(Party.GetPartyLeaderID() or 0):
            return
    except Exception:
        return

    if _LAST_MAP_ID and map_id != _LAST_MAP_ID:
        _restore_all()
    _LAST_MAP_ID = map_id

    if not _RUNTIME_LOGGED:
        _RUNTIME_LOGGED = True
        _log("HERO_ROJ_CONTROLLER_ACTIVE")

    states = _reconcile_states()
    if not states:
        return

    now_ms = _now_ms()
    for rank, state in enumerate(states):
        try:
            _run_state(state, states, now_ms, rank)
        except Exception as exc:
            _log("HERO_ROJ_CONTROLLER_ERROR", hero_index=state.hero_index, hero_id=state.hero_agent_id,
                 error=type(exc).__name__, detail=str(exc)[:160])
