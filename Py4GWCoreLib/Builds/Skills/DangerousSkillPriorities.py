"""Central dangerous-skill priority model for Simple-Power HeroAI.

The module intentionally separates data from interrupt execution.  Builds do
not need large hard-coded allow-lists; they ask for a score and interrupt only
when the final contextual score reaches the configured threshold.

Scores:
    100+  S tier: fight-resetting resurrection, party-wiping AoE, hard denial
     80+  A tier: major healing/protection/shutdown
     60+  B tier: meaningful pressure/utility (normally not reserved)
      <60 C tier: incidental pressure; never receives a reserved interrupt
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from Py4GWCoreLib.Skill import Skill

DEFAULT_RESERVED_INTERRUPT_THRESHOLD = 80

@dataclass(frozen=True, slots=True)
class SkillPriority:
    score: int
    category: str
    aliases: tuple[str, ...] = ()

# This table is deliberately conservative.  Incidental attacks, preparations,
# weak projectiles and common filler skills are omitted so a dedicated
# interrupt is not wasted on them.  Keystone/SoJ AoE can still interrupt those
# incidentally, which is desirable and requires no claim.
_PRIORITY_BY_NAME: dict[str, SkillPriority] = {}


def _register(score: int, category: str, *names: str) -> None:
    cleaned = tuple(str(n) for n in names if str(n))
    if not cleaned:
        return
    entry = SkillPriority(int(score), str(category), cleaned[1:])
    for name in cleaned:
        _PRIORITY_BY_NAME[name] = entry

# S tier — resurrection / complete fight reset.
_register(110, "resurrection",
    "Death_Pact_Signet", "Flesh_of_My_Flesh", "Renew_Life", "Restore_Life",
    "Resurrection_Chant", "Resurrection_Signet", "Rebirth", "Light_of_Dwayna",
    "Unyielding_Aura", "Vengeance", "Signet_of_Return", "Sunspear_Rebirth_Signet")

# S tier — prolonged or severe packet AoE / repeated knockdown.
_register(106, "lethal_aoe",
    "Meteor_Shower", "Savannah_Heat", "Searing_Heat", "Teinais_Heat",
    "Teinai's_Heat", "Bed_of_Coals", "Ray_of_Judgment", "Fire_Storm",
    "Maelstrom", "Churning_Earth", "Sandstorm", "Eruption", "Deep_Freeze",
    "Earthquake", "Dragon's_Stomp", "Dragons_Stomp", "Unsteady_Ground",
    "Shockwave", "Spirit_Rift", "Rodgorts_Invocation", "Rodgort's_Invocation")
_register(101, "lethal_aoe",
    "Invoke_Lightning", "Chain_Lightning", "Obsidian_Flame", "Mind_Burn",
    "Mind_Freeze", "Shatterstone", "Thunderclap", "Stoning")

# S/A tier — defenses that can completely negate the team's spike.
_register(102, "hard_protection",
    "Aegis", "Protective_Spirit", "Spirit_Bond", "Shield_of_Absorption",
    "Life_Sheath", "Mark_of_Protection", "Aura_of_Stability", "Shelter",
    "Union", "Displacement", "Protective_Was_Kaolai")
_register(92, "protection",
    "Guardian", "Shielding_Hands", "Protective_Bond", "Life_Barrier",
    "Life_Bond", "Reversal_of_Fortune", "Shield_Guardian", "Weapon_of_Warding",
    "Weapon_of_Shadow", "Xinraes_Weapon", "Xinrae's_Weapon", "Weapon_of_Remedy",
    "Preservation", "Recuperation", "Recovery")

# A/S tier — party recovery and large single-target swing heals.
_register(100, "party_heal",
    "Heal_Party", "Light_of_Deliverance", "Healing_Burst", "Divine_Healing",
    "Heavens_Delight", "Heaven's_Delight", "Kareis_Healing_Circle",
    "Karei's_Healing_Circle")
_register(94, "major_heal",
    "Word_of_Healing", "Infuse_Health", "Spirit_Transfer", "Spirit_Light",
    "Mend_Body_and_Soul", "Restore_Condition", "Healing_Seed", "Seed_of_Life",
    "Gift_of_Health", "Jameis_Gaze", "Jamei's_Gaze", "Ethereal_Light",
    "Healing_Ribbon", "Healing_Light", "Dwaynas_Kiss", "Dwayna's_Kiss")
_register(82, "heal_cleanse",
    "Patient_Spirit", "Orison_of_Healing", "Heal_Other", "Healing_Touch",
    "Heal_Area", "Mend_Condition", "Mend_Ailment", "Convert_Hexes",
    "Deny_Hexes", "Purge_Signet", "Soothing_Memories", "Wielders_Boon",
    "Wielder's_Boon", "Generous_Was_Tsungrai", "Mend_Soul")

# S/A tier — shutdown that can collapse casting chains or disable a whole ball.
_register(104, "hard_shutdown",
    "Panic", "Power_Block", "Psychic_Instability", "Broad_Head_Arrow",
    "Dissonance", "Wanderlust", "Frozen_Soil")
_register(96, "shutdown",
    "Energy_Surge", "Mistrust", "Cry_of_Frustration", "Diversion", "Shame",
    "Backfire", "Migraine", "Complicate", "Hex_Eater_Vortex",
    "Visions_of_Regret", "Shared_Burden", "Frustration")
_register(84, "shutdown",
    "Power_Leak", "Power_Drain", "Leech_Signet", "Ineptitude", "Clumsiness",
    "Wandering_Eye", "Empathy", "Arcane_Conundrum")

# A tier — packet pressure, corpse explosions and severe melee punishment.
_register(93, "packet_pressure",
    "Spiteful_Spirit", "Spoil_Victor", "Mark_of_Pain", "Feast_of_Corruption",
    "Rising_Bile", "Putrid_Explosion", "Discord", "Soul_Barbs")
_register(82, "pressure",
    "Barbs", "Insidious_Parasite", "Defile_Defenses", "Enfeebling_Blood",
    "Weaken_Armor", "Price_of_Failure", "Reckless_Haste", "Tainted_Flesh",
    "Order_of_Pain", "Order_of_the_Vampire")

# A tier — smite/control and high-impact spirits/nature rituals.
_register(96, "control",
    "Signet_of_Judgment", "Shield_of_Judgment", "Gale", "Bane_Signet")
_register(90, "spirit_pressure",
    "Signet_of_Spirits", "Pain", "Bloodsong", "Shadowsong", "Anguish",
    "Destruction", "Doom", "Clamor_of_Souls", "Caretakers_Charge",
    "Caretaker's_Charge")
_register(92, "nature_ritual",
    "Edge_of_Extinction", "Greater_Conflagration")

# B tier — meaningful but normally not worth a reserved interrupt.
_register(72, "medium_pressure",
    "Symbol_of_Wrath", "Scourge_Healing", "Balthazars_Aura", "Balthazar's_Aura",
    "Ancestors_Rage", "Ancestor's_Rage", "Sliver_Armor", "Ward_Against_Harm",
    "Ward_Against_Melee", "Ward_Against_Foes", "Ward_Against_Elements")


def _resolve_ids() -> tuple[dict[int, SkillPriority], dict[int, str]]:
    by_id: dict[int, SkillPriority] = {}
    names: dict[int, str] = {}
    for name, priority in _PRIORITY_BY_NAME.items():
        try:
            sid = int(Skill.GetID(name) or 0)
        except Exception:
            sid = 0
        if sid <= 0:
            continue
        old = by_id.get(sid)
        if old is None or int(priority.score) > int(old.score):
            by_id[sid] = priority
            names[sid] = name
    return by_id, names

_PRIORITY_BY_ID, _CANONICAL_NAME_BY_ID = _resolve_ids()


def get_registered_skill_ids(min_score: int = 0) -> frozenset[int]:
    threshold = int(min_score)
    return frozenset(sid for sid, entry in _PRIORITY_BY_ID.items() if int(entry.score) >= threshold)


def get_base_score(skill_id: int, default: int = 0) -> int:
    entry = _PRIORITY_BY_ID.get(int(skill_id or 0))
    return int(entry.score) if entry is not None else int(default)


def get_category(skill_id: int, default: str = "unknown") -> str:
    entry = _PRIORITY_BY_ID.get(int(skill_id or 0))
    return str(entry.category) if entry is not None else str(default)


def get_canonical_name(skill_id: int) -> str:
    return str(_CANONICAL_NAME_BY_ID.get(int(skill_id or 0), ""))


def is_reserved_interrupt_candidate(skill_id: int, threshold: int = DEFAULT_RESERVED_INTERRUPT_THRESHOLD) -> bool:
    return get_base_score(int(skill_id or 0), 0) >= int(threshold)


def contextual_score(
    skill_id: int,
    *,
    adjacent_enemies: int = 1,
    team_low_health: bool = False,
    enemy_low_health: bool = False,
    threat_memory_bonus: int = 0,
) -> int:
    """Return a bounded context-aware score without expensive game queries."""
    sid = int(skill_id or 0)
    base = get_base_score(sid, 0)
    if base <= 0:
        return 0
    category = get_category(sid)
    score = int(base)
    packed = max(1, int(adjacent_enemies))

    if category in {"lethal_aoe", "hard_shutdown", "packet_pressure", "party_heal"}:
        score += min(18, max(0, packed - 1) * 4)
    if team_low_health and category in {"lethal_aoe", "hard_shutdown", "packet_pressure", "control"}:
        score += 12
    if enemy_low_health and category in {"major_heal", "party_heal", "hard_protection", "protection", "resurrection"}:
        score += 10
    score += max(0, min(18, int(threat_memory_bonus)))
    return max(0, min(130, int(score)))
