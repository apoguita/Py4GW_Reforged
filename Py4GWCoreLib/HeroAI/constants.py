"""This file contains the constants and globals used by the HeroAI module."""
from Py4GWCoreLib import Range, GLOBAL_CACHE

TRUE = 1
FALSE = 0
"""module constant"""
MODULE_NAME = "HeroAI"
SMM_MODULE_NAME = "HeroAI - Shared Memory Manager"
CANDIDATES_MODULE_NAME = "HeroAI - Candidates"
GAME_OPTION_MODULE_NAME = "HeroAI - Game Option"
PLAYERS_MODULE_NAME = "HeroAI - Players"
WINDOWS_MODULE_NAME = "HeroAI - Window - "

"""shared memory constants"""
MAX_NUM_PLAYERS = 12
NUMBER_OF_SKILLS = 8
MAX_NUMBER_OF_BUFFS = 240
SHARED_MEMORY_FILE_NAME = "HeroAI_Mem"
LOCK_MUTEX_TIMEOUT = 1 #SECONDS
SUBSCRIBE_TIMEOUT_SECONDS = 500 # milliseconds

""" HELPER CONSTANTS """
MELEE_RANGE_VALUE = Range.Spellcast.value
RANGED_RANGE_VALUE = Range.Spellcast.value
FOLLOW_DISTANCE_ON_COMBAT = Range.Spellcast.value
FOLLOW_DISTANCE_OUT_OF_COMBAT = Range.Area.value

STAY_ALERT_TIME = 750  # milliseconds

BLOOD_IS_POWER = GLOBAL_CACHE.Skill.GetID("Blood_is_Power")
BLOOD_RITUAL = GLOBAL_CACHE.Skill.GetID("Blood_Ritual")  # skill id

PARTY_WINDOW_HASH = 3332025202
PARTY_WINDOW_FRAME_OUTPOST_OFFSETS = [1]
PARTY_WINDOW_FRAME_EXPLORABLE_OFFSETS = [0]
SKILLBAR_WINDOW_HASH = 641635682

""" AI CONSTANTS """


SOUL_IGNITION = GLOBAL_CACHE.Skill.GetID("Soul_Ignition") or 3446


def soul_ignition_overcast_fraction(overcast: float, current_max_energy: float) -> float:
    """Return the grey overcast share of the character's full energy bar."""
    overcast = max(0.0, float(overcast or 0.0))
    # Agent max energy is the currently usable maximum after overcast has
    # reduced it.  Adding the grey amount reconstructs the full bar.
    full_energy_bar = max(0.0, float(current_max_energy or 0.0)) + overcast
    if full_energy_bar <= 0.0:
        return 0.0
    return min(1.0, overcast / full_energy_bar)


def should_activate_soul_ignition(
    player_health: float,
    overcast: float,
    current_max_energy: float,
) -> bool:
    """Use Soul Ignition in its conservative overcast recovery window."""
    overcast_fraction = soul_ignition_overcast_fraction(overcast, current_max_energy)
    return (
        float(player_health or 0.0) > 0.25
        and float(overcast or 0.0) > 0.0
        and overcast_fraction <= 0.60
    )


def should_drop_soul_ignition(
    player_health: float,
    overcast: float,
    current_max_energy: float,
) -> bool:
    """Stop the maintained self-burning enchantment at either safety limit."""
    return (
        float(player_health or 0.0) <= 0.25
        or soul_ignition_overcast_fraction(overcast, current_max_energy) >= 0.90
    )
