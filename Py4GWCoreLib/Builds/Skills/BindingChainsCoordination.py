"""Cross-account coordination for Binding Chains on the shared RoJ packet.

The Soul Twisting Ritualist is the preferred caster because Communing adds real
damage.  The PI Mesmer remains a short-delay fallback: its rank-zero copy still
provides the full movement snare when the ST is occupied with core spirits.

Both builds reserve the packet and every current packet member through short
whiteboard leases.  The member leases keep coordination intact when
TeamCombatFocus changes the anchor while the same enemy group is still active.
"""
from __future__ import annotations

from dataclasses import dataclass

from Py4GWCoreLib import GLOBAL_CACHE, Routines
from Py4GWCoreLib.Builds.Skills.DangerInterruptClaim import get_game_tick
from Py4GWCoreLib.Player import Player
from Py4GWCoreLib.Skill import Skill


Binding_Chains_ID = Skill.GetID("Binding_Chains")

BINDING_PACKET_RESERVATION_LOCK_ID = 0x42435250  # 'BCRP'
BINDING_MEMBER_COVERAGE_LOCK_ID = 0x42434D43  # 'BCMC'
# One lease spans the one-second activation, the three-second snare and a small
# propagation margin. A rejected cast releases it immediately.
BINDING_RESERVATION_MS = 4500
BINDING_PI_FALLBACK_DELAY_MS = 450

_PACKET_TARGET_PREFIX = 0x40000000
_MEMBER_TARGET_PREFIX = 0x20000000
_FIRST_SEEN: dict[tuple[int, str, str], int] = {}


@dataclass(frozen=True, slots=True)
class BindingChainsReservation:
    anchor_id: int
    member_ids: tuple[int, ...]
    packet_key: int
    packet_target: int
    role: str
    coordinated: bool


def _log(event: str, **fields: object) -> None:
    try:
        from Py4GWCoreLib.Builds.Skills import CombatDebug

        CombatDebug.log_event(str(event), **fields)
    except Exception:
        pass


def _owner_context() -> tuple[str, int]:
    try:
        email = str(Player.GetAccountEmail() or "").strip()
        if not email:
            return "", 0
        try:
            group_id = int(GLOBAL_CACHE.Party.GetPartyID() or 0)
        except Exception:
            group_id = 0
        if group_id <= 0:
            try:
                group_id = int(GLOBAL_CACHE.ShMem.GetAccountGroupByEmail(email) or 0)
            except Exception:
                group_id = 0
        return email, group_id
    except Exception:
        return "", 0


def _normalise_members(anchor_id: int, member_ids: list[int] | tuple[int, ...]) -> tuple[int, ...]:
    members = {int(member_id) for member_id in member_ids if int(member_id or 0) > 0}
    if int(anchor_id or 0) > 0:
        members.add(int(anchor_id))
    return tuple(sorted(members))


def _packet_key(member_ids: tuple[int, ...]) -> int:
    """Return a deterministic positive key for a packet membership snapshot."""
    value = 2166136261
    for member_id in member_ids:
        value ^= int(member_id) & 0xFFFFFFFF
        value = (value * 16777619) & 0x3FFFFFFF
    return max(1, int(value))


def _packet_target(packet_key: int) -> int:
    return int(_PACKET_TARGET_PREFIX | (int(packet_key) & 0x3FFFFFFF))


def _member_target(member_id: int) -> int:
    return int(_MEMBER_TARGET_PREFIX | (int(member_id) & 0x1FFFFFFF))


def packet_has_binding_chains(member_ids: list[int] | tuple[int, ...]) -> bool:
    for member_id in member_ids:
        try:
            if Routines.Checks.Agents.HasEffect(int(member_id), int(Binding_Chains_ID)):
                return True
        except Exception:
            continue
    return False


def _is_lock_blocked(lock_id: int, target_id: int, now_tick: int) -> bool:
    try:
        from Py4GWCoreLib.enums_src.Whiteboard_enums import (
            WhiteboardClaimStrength,
            WhiteboardLockKind,
            WhiteboardLockMode,
            WhiteboardReentryPolicy,
        )

        email, group_id = _owner_context()
        if not email or int(now_tick) <= 0:
            return False
        all_accounts = GLOBAL_CACHE.ShMem.GetAllAccounts()
        return bool(
            all_accounts.IsLockBlocked(
                int(WhiteboardLockKind.SKILL_TARGET),
                int(lock_id),
                int(target_id),
                int(group_id),
                email,
                int(now_tick),
                int(WhiteboardLockMode.EXCLUSIVE),
                1,
                int(WhiteboardReentryPolicy.NON_REENTRANT),
                int(WhiteboardClaimStrength.HARD),
            )
        )
    except Exception:
        # Fail open: losing whiteboard access must not disable the skill.
        return False


def _post_lock(lock_id: int, target_id: int, duration_ms: int, now_tick: int) -> int:
    try:
        from Py4GWCoreLib.enums_src.Whiteboard_enums import (
            WhiteboardClaimStrength,
            WhiteboardLockKind,
            WhiteboardLockMode,
            WhiteboardReentryPolicy,
        )

        email, group_id = _owner_context()
        if not email or int(now_tick) <= 0:
            return -2
        return int(
            GLOBAL_CACHE.ShMem.PostLock(
                email,
                int(WhiteboardLockKind.SKILL_TARGET),
                int(lock_id),
                int(target_id),
                int(now_tick) + int(duration_ms),
                int(group_id),
                int(WhiteboardLockMode.EXCLUSIVE),
                1,
                int(WhiteboardReentryPolicy.NON_REENTRANT),
                int(WhiteboardClaimStrength.HARD),
            )
        )
    except Exception:
        return -2


def _clear_own_target(target_id: int) -> None:
    try:
        from Py4GWCoreLib.enums_src.Whiteboard_enums import WhiteboardLockKind

        email, group_id = _owner_context()
        if not email:
            return
        GLOBAL_CACHE.ShMem.GetAllAccounts().ClearLockByOwnerKindTarget(
            email,
            int(WhiteboardLockKind.SKILL_TARGET),
            int(target_id),
            int(group_id),
        )
    except Exception:
        pass


def _verify_packet_owner(packet_target: int, now_tick: int) -> bool:
    email, group_id = _owner_context()
    if not email:
        return True
    try:
        from Py4GWCoreLib.enums_src.Whiteboard_enums import WhiteboardLockKind

        matches: list[tuple[int, object]] = []
        for slot, intent in GLOBAL_CACHE.ShMem.GetAllAccounts().GetActiveIntents() or []:
            if int(getattr(intent, "ExpiresAtTick", 0) or 0) <= int(now_tick):
                continue
            if int(getattr(intent, "KindID", 0) or 0) != int(WhiteboardLockKind.SKILL_TARGET):
                continue
            if int(getattr(intent, "SkillID", 0) or 0) != int(BINDING_PACKET_RESERVATION_LOCK_ID):
                continue
            if int(getattr(intent, "TargetAgentID", 0) or 0) != int(packet_target):
                continue
            if int(getattr(intent, "IsolationGroupID", 0) or 0) != int(group_id):
                continue
            matches.append((int(slot), intent))
        if not matches:
            return True
        _winner_slot, winner = min(
            matches,
            key=lambda pair: (
                int(getattr(pair[1], "PostedAtTick", 0) or 0),
                str(getattr(pair[1], "OwnerEmail", "") or ""),
                int(pair[0]),
            ),
        )
        return str(getattr(winner, "OwnerEmail", "") or "") == email
    except Exception:
        return True


def _role_delay_ready(packet_key: int, role: str, now_tick: int) -> bool:
    email, _group_id = _owner_context()
    if not email or int(now_tick) <= 0:
        return True

    for key, first_seen in list(_FIRST_SEEN.items()):
        if int(now_tick) - int(first_seen) > 6000:
            _FIRST_SEEN.pop(key, None)

    normalised_role = str(role or "pi").lower()
    key = (int(packet_key), email, normalised_role)
    first_seen = int(_FIRST_SEEN.setdefault(key, int(now_tick)))
    delay_ms = 0 if normalised_role == "st" else int(BINDING_PI_FALLBACK_DELAY_MS)
    return int(now_tick) - first_seen >= delay_ms


def reserve_binding_chains(
    *,
    anchor_id: int,
    member_ids: list[int] | tuple[int, ...],
    role: str,
) -> BindingChainsReservation | None:
    """Reserve one current RoJ packet for either ST-primary or PI-fallback use."""
    members = _normalise_members(int(anchor_id), member_ids)
    if int(anchor_id or 0) <= 0 or len(members) < 2:
        return None
    if packet_has_binding_chains(members):
        return None

    packet_key = _packet_key(members)
    packet_target = _packet_target(packet_key)
    now = int(get_game_tick() or 0)
    if not _role_delay_ready(packet_key, str(role), now):
        return None
    if _is_lock_blocked(BINDING_PACKET_RESERVATION_LOCK_ID, packet_target, now):
        return None
    if any(
        _is_lock_blocked(BINDING_MEMBER_COVERAGE_LOCK_ID, _member_target(member_id), now)
        for member_id in members
    ):
        return None

    posted_slot = _post_lock(
        BINDING_PACKET_RESERVATION_LOCK_ID,
        packet_target,
        BINDING_RESERVATION_MS,
        now,
    )
    coordinated = posted_slot >= 0
    if posted_slot == -1:
        return None
    if coordinated and not _verify_packet_owner(packet_target, now):
        _clear_own_target(packet_target)
        _log(
            "BINDING_CHAINS_RESERVATION_LOST",
            role=str(role),
            anchor_id=int(anchor_id),
            packet_key=int(packet_key),
        )
        return None

    if coordinated:
        for member_id in members:
            _post_lock(
                BINDING_MEMBER_COVERAGE_LOCK_ID,
                _member_target(member_id),
                BINDING_RESERVATION_MS,
                now,
            )

    reservation = BindingChainsReservation(
        anchor_id=int(anchor_id),
        member_ids=members,
        packet_key=int(packet_key),
        packet_target=int(packet_target),
        role=str(role),
        coordinated=bool(coordinated),
    )
    _log(
        "BINDING_CHAINS_PACKET_RESERVED",
        role=str(role),
        anchor_id=int(anchor_id),
        packet_key=int(packet_key),
        packet_size=int(len(members)),
        coordinated=bool(coordinated),
    )
    return reservation


def release_binding_chains_reservation(
    reservation: BindingChainsReservation | None,
    *,
    reason: str,
) -> None:
    if reservation is None or not reservation.coordinated:
        return
    _clear_own_target(int(reservation.packet_target))
    for member_id in reservation.member_ids:
        _clear_own_target(_member_target(int(member_id)))
    _log(
        "BINDING_CHAINS_RESERVATION_RELEASED",
        role=str(reservation.role),
        anchor_id=int(reservation.anchor_id),
        packet_key=int(reservation.packet_key),
        reason=str(reason),
    )


def register_binding_chains_fired(
    reservation: BindingChainsReservation | None,
    *,
    source: str,
) -> None:
    if reservation is None:
        return
    _log(
        "BINDING_CHAINS_PACKET_FIRED",
        role=str(reservation.role),
        source=str(source),
        anchor_id=int(reservation.anchor_id),
        packet_key=int(reservation.packet_key),
        packet_size=int(len(reservation.member_ids)),
        packet_members=",".join(str(member_id) for member_id in reservation.member_ids),
        policy="st_primary_pi_fallback_no_packet_overlap",
    )
