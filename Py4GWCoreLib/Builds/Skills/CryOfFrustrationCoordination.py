"""Cross-account Cry of Frustration packet coordination.

Purpose:
- Multiple Cry holders may coexist (Panic + optional Keystone Mesmers).
- One Cry reserves the dangerous caster packet it will cover, so a second Cry
  does not immediately fire into the same AoE packet.
- A second ready Mesmer may still interrupt a *different* separated packet.
- The reservation is short and never changes the team's canonical damage focus;
  builds cast via CastSkillIDAndRestoreTarget and return to their normal target.

The coordinator is intentionally restricted to high-value enemy activations.
Normal damage/filler casts are not reserved, so Keystone throughput is preserved.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from Py4GWCoreLib import GLOBAL_CACHE, Range
from Py4GWCoreLib.Agent import Agent
from Py4GWCoreLib.Player import Player
from Py4GWCoreLib.Skill import Skill
from Py4GWCoreLib.Builds.Skills.DangerInterruptClaim import (
    get_dangerous_casts_in_range,
    get_casting_skill_id,
    get_game_tick,
    interrupt_is_feasible,
)
from Py4GWCoreLib.Builds.Skills import DangerousSkillPriorities as DSP

Cry_of_Frustration_ID = Skill.GetID("Cry_of_Frustration")

# Keep Cry for genuinely important casts. This includes resurrection, severe
# AoE/KD, hard protection, party healing and hard shutdown, while excluding the
# lower-value 80-93 score filler tier.
CRY_RESERVED_MIN_SCORE = 96
CRY_PACKET_LOCK_ID = 0x43525950  # 'CRYP'
CRY_MEMBER_LOCK_ID = 0x4352594D  # 'CRYM'
CRY_PACKET_LOCK_MS = 950
CRY_ELECTION_STEP_MS = 22

_FIRST_SEEN: dict[tuple[int, str], int] = {}


@dataclass(frozen=True, slots=True)
class CryReservation:
    target_id: int
    enemy_skill_id: int
    packet_key: int
    covered_casts: tuple[tuple[int, int], ...]
    covered_enemy_ids: tuple[int, ...]
    score: int


def _owner_context() -> tuple[str, int]:
    email = str(Player.GetAccountEmail() or "").strip()
    if not email:
        return "", 0
    try:
        gid = int(GLOBAL_CACHE.Party.GetPartyID() or 0)
    except Exception:
        gid = 0
    if gid <= 0:
        try:
            gid = int(GLOBAL_CACHE.ShMem.GetAccountGroupByEmail(email) or 0)
        except Exception:
            gid = 0
    return email, gid


def _xy(agent_id: int) -> tuple[float, float] | None:
    try:
        x, y = Agent.GetXY(int(agent_id))
        return float(x), float(y)
    except Exception:
        return None


def _distance(a: int, b: int) -> float:
    pa, pb = _xy(a), _xy(b)
    if pa is None or pb is None:
        return 10**9
    return math.hypot(pa[0] - pb[0], pa[1] - pb[1])


def _cry_aoe_range() -> float:
    try:
        return float(GLOBAL_CACHE.Skill.Data.GetAoERange(Cry_of_Frustration_ID) or Range.Nearby.value)
    except Exception:
        return float(Range.Nearby.value)


def _score_cast(agent_id: int, skill_id: int) -> int:
    try:
        # Contextual score rewards a cast sitting in a real packet without
        # changing the underlying dangerous-skill classification.
        adjacent = 1
        try:
            ax, ay = Agent.GetXY(int(agent_id))
            r = _cry_aoe_range()
            adjacent = 0
            for other_id, _sid in get_dangerous_casts_in_range(Range.Spellcast.value):
                try:
                    ox, oy = Agent.GetXY(int(other_id))
                    if math.hypot(float(ax) - float(ox), float(ay) - float(oy)) <= r:
                        adjacent += 1
                except Exception:
                    pass
            adjacent = max(1, adjacent)
        except Exception:
            pass
        return int(DSP.contextual_score(int(skill_id), adjacent_enemies=int(adjacent)))
    except Exception:
        try:
            return int(DSP.get_base_score(int(skill_id), 0))
        except Exception:
            return 0


def _is_lock_blocked(lock_id: int, target_id: int) -> bool:
    if int(target_id or 0) <= 0:
        return False
    try:
        from Py4GWCoreLib.enums_src.Whiteboard_enums import (
            WhiteboardClaimStrength, WhiteboardLockKind, WhiteboardLockMode,
            WhiteboardReentryPolicy,
        )
        email, gid = _owner_context()
        now = get_game_tick()
        if not email or now <= 0:
            return False
        shmem = GLOBAL_CACHE.ShMem
        if hasattr(shmem, "SweepExpiredIntents"):
            shmem.SweepExpiredIntents(int(now))
        return bool(shmem.IsLockBlocked(
            int(WhiteboardLockKind.SKILL_TARGET), int(lock_id), int(target_id),
            int(gid), email, int(now), int(WhiteboardLockMode.EXCLUSIVE), 1,
            int(WhiteboardReentryPolicy.NON_REENTRANT),
            int(WhiteboardClaimStrength.HARD),
        ))
    except Exception:
        return False


def _post_lock(lock_id: int, target_id: int, duration_ms: int) -> bool:
    try:
        from Py4GWCoreLib.enums_src.Whiteboard_enums import (
            WhiteboardClaimStrength, WhiteboardLockKind, WhiteboardLockMode,
            WhiteboardReentryPolicy,
        )
        email, gid = _owner_context()
        now = get_game_tick()
        if not email or now <= 0:
            return True
        slot = GLOBAL_CACHE.ShMem.PostLock(
            email, int(WhiteboardLockKind.SKILL_TARGET), int(lock_id), int(target_id),
            int(now) + int(duration_ms), int(gid), int(WhiteboardLockMode.EXCLUSIVE),
            1, int(WhiteboardReentryPolicy.NON_REENTRANT),
            int(WhiteboardClaimStrength.HARD),
        )
        return int(slot) != -1
    except Exception:
        return True


def _clear_lock(lock_id: int, target_id: int) -> None:
    try:
        from Py4GWCoreLib.enums_src.Whiteboard_enums import WhiteboardLockKind
        email, gid = _owner_context()
        if not email:
            return
        GLOBAL_CACHE.ShMem.GetAllAccounts().ClearLockByOwnerKindTarget(
            email, int(WhiteboardLockKind.SKILL_TARGET), int(target_id), int(gid)
        )
    except Exception:
        pass


def _ready_cry_holder_rank() -> int:
    """Deterministic micro-stagger across every ready Cry holder in the group."""
    me = str(Player.GetAccountEmail() or "").strip()
    if not me:
        return 0
    ready: list[str] = []
    try:
        for account in GLOBAL_CACHE.ShMem.GetAllAccountData() or []:
            email = str(getattr(account, "AccountEmail", "") or "").strip()
            if not email:
                continue
            skillbar = getattr(getattr(account, "AgentData", None), "Skillbar", None)
            if skillbar is None or int(getattr(skillbar, "CastingSkillID", 0) or 0) > 0:
                continue
            for skill in getattr(skillbar, "Skills", ()) or ():
                if int(getattr(skill, "Id", 0) or 0) != int(Cry_of_Frustration_ID):
                    continue
                if float(getattr(skill, "Recharge", 0.0) or 0.0) <= 0.0:
                    ready.append(email)
                break
    except Exception:
        return 0
    if me not in ready:
        ready.append(me)
    ready = sorted(set(ready))
    try:
        return ready.index(me)
    except ValueError:
        return 0


def _election_ready(packet_key: int) -> bool:
    email = str(Player.GetAccountEmail() or "").strip()
    now = get_game_tick()
    if not email or now <= 0:
        return True
    key = (int(packet_key), email)
    first = int(_FIRST_SEEN.get(key, 0) or 0)
    if first <= 0 or now - first > 5000:
        _FIRST_SEEN[key] = int(now)
        first = int(now)
    delay = int(_ready_cry_holder_rank()) * int(CRY_ELECTION_STEP_MS)
    return int(now) - int(first) >= int(delay)


def is_enemy_cry_covered(enemy_id: int) -> bool:
    return _is_lock_blocked(CRY_MEMBER_LOCK_ID, int(enemy_id))


def _candidate_packets(min_score: int) -> list[tuple[int, int, int, tuple[tuple[int, int], ...], tuple[int, ...]]]:
    casts: list[tuple[int, int, int]] = []
    for agent_id, skill_id in get_dangerous_casts_in_range(Range.Spellcast.value):
        aid, sid = int(agent_id), int(skill_id)
        if aid <= 0 or sid <= 0:
            continue
        if int(get_casting_skill_id(aid) or 0) != sid:
            continue
        score = _score_cast(aid, sid)
        if score < int(min_score):
            continue
        if not interrupt_is_feasible(aid, Cry_of_Frustration_ID):
            continue
        casts.append((aid, sid, score))

    r = _cry_aoe_range()
    packets = []
    seen: set[tuple[int, tuple[int, ...]]] = set()
    for aid, sid, score in casts:
        covered = tuple((oa, osid) for oa, osid, _sc in casts if _distance(aid, oa) <= r)
        member_ids = tuple(sorted({int(x[0]) for x in covered}))
        if not member_ids:
            member_ids = (int(aid),)
            covered = ((int(aid), int(sid)),)
        packet_key = int(member_ids[0])
        dedupe = (packet_key, member_ids)
        if dedupe in seen:
            continue
        seen.add(dedupe)
        packet_score = sum(_score_cast(ca, cs) for ca, cs in covered)
        packets.append((aid, sid, packet_score, covered, member_ids))
    packets.sort(key=lambda item: (int(item[2]), len(item[3]), _score_cast(item[0], item[1])), reverse=True)
    return packets


def reserve_best_cry_packet(*, min_score: int = CRY_RESERVED_MIN_SCORE) -> CryReservation | None:
    """Reserve one high-value Cry packet, allowing other Cry holders to take other packets."""
    for aid, sid, packet_score, covered, member_ids in _candidate_packets(int(min_score)):
        packet_key = int(min(member_ids))
        if _is_lock_blocked(CRY_PACKET_LOCK_ID, packet_key):
            continue
        if any(is_enemy_cry_covered(mid) for mid in member_ids):
            continue
        if not _election_ready(packet_key):
            continue
        if not _post_lock(CRY_PACKET_LOCK_ID, packet_key, CRY_PACKET_LOCK_MS):
            continue
        # Claim every enemy currently inside the Cry packet. This is the piece
        # that prevents another Cry from selecting a different caster in the same
        # cluster while still leaving a spatially separate packet available.
        posted_members: list[int] = []
        for mid in member_ids:
            if _post_lock(CRY_MEMBER_LOCK_ID, int(mid), CRY_PACKET_LOCK_MS):
                posted_members.append(int(mid))
        try:
            from Py4GWCoreLib.Builds.Skills import CombatDebug
            CombatDebug.log_event(
                "CRY_PACKET_RESERVED",
                target_id=int(aid), enemy_skill_id=int(sid), packet_key=int(packet_key),
                covered_count=int(len(covered)), packet_score=int(packet_score),
                covered_ids=",".join(str(x) for x in member_ids),
            )
        except Exception:
            pass
        return CryReservation(
            target_id=int(aid), enemy_skill_id=int(sid), packet_key=int(packet_key),
            covered_casts=tuple((int(x), int(y)) for x, y in covered),
            covered_enemy_ids=tuple(int(x) for x in member_ids), score=int(packet_score),
        )
    return None


def release_cry_reservation(reservation: CryReservation, *, reason: str = "not_fired") -> None:
    if reservation is None:
        return
    # SharedMemory currently exposes owner+kind+target clearing, not a precise
    # lock-id clear. Do not risk deleting an unrelated Keystone target lock on
    # the same enemy. A failed Cry reservation therefore expires naturally in
    # <1 second; this is safer than a broad clear and still prevents duplicates.
    try:
        from Py4GWCoreLib.Builds.Skills import CombatDebug
        CombatDebug.log_event(
            "CRY_PACKET_RELEASED", packet_key=int(reservation.packet_key), reason=str(reason)
        )
    except Exception:
        pass


def register_cry_fired(reservation: CryReservation, *, source: str) -> None:
    if reservation is None:
        return
    try:
        from Py4GWCoreLib.Builds.Skills import CombatDebug
        for enemy_id, skill_id in reservation.covered_casts:
            CombatDebug.register_interrupt_fired(
                int(enemy_id), int(skill_id), int(Cry_of_Frustration_ID)
            )
        CombatDebug.log_event(
            "CRY_PACKET_FIRED", source=str(source), target_id=int(reservation.target_id),
            enemy_skill_id=int(reservation.enemy_skill_id), packet_key=int(reservation.packet_key),
            covered_count=int(len(reservation.covered_casts)), packet_score=int(reservation.score),
            policy="one_cry_per_aoe_packet_separate_packets_parallel",
        )
    except Exception:
        pass
