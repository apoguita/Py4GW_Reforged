"""Agent Recolor model — the rule taxonomy (pure data).

NO PyImGui, NO Settings, NO native calls. It only *describes* a color rule and the
vocabulary of criteria the engine can filter agents/gadgets by, plus (de)serialization
so the whole rule list round-trips as JSON (global, shareable, nothing hardcoded).

A ``Rule`` is an ordered, named, toggleable unit: a set of OPTIONAL criteria (all set
ones AND'd; unset = ignored) plus an action (color + mode). The engine walks the rules
in list order and the first enabled rule that matches an agent wins (like the item
precedence chain in the native module).
"""

from dataclasses import dataclass
from dataclasses import field
from typing import List
from typing import Optional

# ── scopes ────────────────────────────────────────────────────────────────────────────────
SCOPE_AGENT = "agent"
SCOPE_GADGET = "gadget"

# ── modes (encoded into the ARGB alpha byte by AgentRecolor.ARGB) ──────────────────────────
MODE_SOLID = "solid"
MODE_FADE = "fade"
MODE_HIDE = "hide"
MODES = (MODE_SOLID, MODE_FADE, MODE_HIDE)

# ── allegiance taxonomy (native PyAgentRecolor ids 1..6) → AgentArray bucket getter ────────
ALLEGIANCE_NAMES = {1: "Ally", 2: "Neutral", 3: "Enemy", 4: "SpiritPet", 5: "Minion", 6: "NpcMinipet"}
ALLEGIANCE_IDS = (1, 2, 3, 4, 5, 6)
# Getter name on Py4GWCoreLib.AgentArray.AgentArray for each allegiance id.
ALLEGIANCE_ARRAY_GETTER = {
    1: "GetAllyArray",
    2: "GetNeutralArray",
    3: "GetEnemyArray",
    4: "GetSpiritPetArray",
    5: "GetMinionArray",
    6: "GetNPCMinipetArray",
}

# ── agent "kind" predicates (key → Agent method name returning bool) ───────────────────────
KIND_PREDICATE = {
    "player": "IsPlayer",
    "npc": "IsNPC",
    "minion": "IsMinion",
    "spirit": "IsSpirit",
    "pet": "IsPet",
    "boss": "HasBossGlow",
}
KIND_KEYS = ("player", "npc", "minion", "spirit", "pet", "boss")

# ── dynamic state predicates (key → Agent method name returning bool) ──────────────────────
STATE_PREDICATE = {
    "targeted": "IsTargeted",
    "attacking": "IsAttacking",
    "casting": "IsCasting",
    "moving": "IsMoving",
    "alive": "IsAlive",
    "dead": "IsDead",
}
STATE_KEYS = ("targeted", "attacking", "casting", "moving", "alive", "dead")


@dataclass
class Rule:
    """One color rule. Unset criteria (None / empty) are ignored when matching."""

    id: str                          # stable id (for UI selection / removal)
    name: str = "New rule"           # user-facing label
    enabled: bool = True
    scope: str = SCOPE_AGENT         # SCOPE_AGENT | SCOPE_GADGET

    # action
    color_rgb: int = 0xFF0000        # 0xRRGGBB
    mode: str = MODE_SOLID           # MODE_SOLID | MODE_FADE | MODE_HIDE
    alpha: int = 0x40                # 1..254, used only when mode == MODE_FADE

    # criteria (all optional; empty containers / None = "don't care")
    allegiance: Optional[int] = None            # 1..6 (agent scope)
    kinds: List[str] = field(default_factory=list)       # subset of KIND_KEYS (any-of)
    model_ids: List[int] = field(default_factory=list)   # any-of
    professions: List[int] = field(default_factory=list) # any-of (primary OR secondary)
    name_substr: Optional[str] = None           # case-insensitive substring of the display name
    enc_substr: Optional[str] = None            # case-insensitive substring of the encoded name
    level_min: Optional[int] = None
    level_max: Optional[int] = None
    hp_min: Optional[float] = None              # percent 0..100
    hp_max: Optional[float] = None              # percent 0..100
    states: List[str] = field(default_factory=list)      # subset of STATE_KEYS (all-of)
    agent_id: Optional[int] = None              # pin one specific agent/gadget id

    # ── serialization ─────────────────────────────────────────────────────────────────────
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "enabled": bool(self.enabled),
            "scope": self.scope,
            "color_rgb": int(self.color_rgb) & 0xFFFFFF,
            "mode": self.mode,
            "alpha": int(self.alpha) & 0xFF,
            "allegiance": self.allegiance,
            "kinds": list(self.kinds),
            "model_ids": list(self.model_ids),
            "professions": list(self.professions),
            "name_substr": self.name_substr,
            "enc_substr": self.enc_substr,
            "level_min": self.level_min,
            "level_max": self.level_max,
            "hp_min": self.hp_min,
            "hp_max": self.hp_max,
            "states": list(self.states),
            "agent_id": self.agent_id,
        }

    @staticmethod
    def from_dict(data: dict) -> "Rule":
        def _int_list(v) -> "List[int]":
            return [int(x) for x in v] if isinstance(v, (list, tuple)) else []

        def _str_list(v) -> "List[str]":
            return [str(x) for x in v] if isinstance(v, (list, tuple)) else []

        def _opt_int(v) -> "Optional[int]":
            return int(v) if isinstance(v, (int, float)) else None

        def _opt_float(v) -> "Optional[float]":
            return float(v) if isinstance(v, (int, float)) else None

        def _opt_str(v) -> "Optional[str]":
            return str(v) if isinstance(v, str) and v != "" else None

        scope = data.get("scope", SCOPE_AGENT)
        return Rule(
            id=str(data.get("id", "")),
            name=str(data.get("name", "Rule")),
            enabled=bool(data.get("enabled", True)),
            scope=scope if scope in (SCOPE_AGENT, SCOPE_GADGET) else SCOPE_AGENT,
            color_rgb=int(data.get("color_rgb", 0xFF0000)) & 0xFFFFFF,
            mode=data.get("mode", MODE_SOLID) if data.get("mode") in MODES else MODE_SOLID,
            alpha=int(data.get("alpha", 0x40)) & 0xFF,
            allegiance=_opt_int(data.get("allegiance")),
            kinds=[k for k in _str_list(data.get("kinds")) if k in KIND_PREDICATE],
            model_ids=_int_list(data.get("model_ids")),
            professions=_int_list(data.get("professions")),
            name_substr=_opt_str(data.get("name_substr")),
            enc_substr=_opt_str(data.get("enc_substr")),
            level_min=_opt_int(data.get("level_min")),
            level_max=_opt_int(data.get("level_max")),
            hp_min=_opt_float(data.get("hp_min")),
            hp_max=_opt_float(data.get("hp_max")),
            states=[s for s in _str_list(data.get("states")) if s in STATE_PREDICATE],
            agent_id=_opt_int(data.get("agent_id")),
        )

    def has_any_criteria(self) -> bool:
        """True if the rule constrains anything at all (else it matches the whole scope)."""
        return any((
            self.allegiance is not None, self.kinds, self.model_ids, self.professions,
            self.name_substr, self.enc_substr, self.level_min is not None,
            self.level_max is not None, self.hp_min is not None, self.hp_max is not None,
            self.states, self.agent_id is not None,
        ))
