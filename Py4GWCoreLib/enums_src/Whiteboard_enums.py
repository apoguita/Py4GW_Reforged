from enum import IntEnum


class WhiteboardLockKind(IntEnum):
    SKILL_TARGET = 1
    MINION_CORPSE = 2
    CORPSE_EXPLOIT = 3
    WELL_CORPSE = 4
    RESURRECT_TARGET = 5
    LOOT_ITEM = 6
    INTERACT_AGENT = 7
    MOVEMENT_OBJECTIVE = 8
    CALL_TARGET = 9
    BUFF_TARGET = 10
    INTERRUPT_TARGET = 11
    COOLDOWN = 12
    HEX_REMOVAL_TARGET = 13
    # State-broadcast kinds (not exclusive claims): each account posts its OWN slot, owner-keyed,
    # re-posted on an interval and self-expiring, so party members can read live per-account state.
    RESURRECTION_SCROLL_STATE = 14


class WhiteboardLockMode(IntEnum):
    EXCLUSIVE = 1
    SHARED = 2
    SEMAPHORE = 3
    BARRIER = 4


class WhiteboardReentryPolicy(IntEnum):
    OWNER_REENTRANT = 1
    NON_REENTRANT = 2


class WhiteboardClaimStrength(IntEnum):
    HARD = 1
    SOFT = 2
