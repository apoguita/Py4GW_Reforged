"""
Effects / Buffs section — buffs & effects on a chosen agent, with the DropBuff action.

Shape (mirrors player_demo, the canonical template):
  * ``build_effects(agent_id)`` calls the ``Effects`` wrapper getters, dereferences each
    BuffType/EffectType struct field-by-field (never repr'd — R3 §11), resolves skill names via
    the ``Skill`` wrapper, and returns a list of display Blocks.
  * ``draw_effects_view()`` builds once, offers the per-section Dump-to-file button, a PER-AGENT
    selector (input_int + Self / Nearest Ally / Nearest Enemy / Target buttons), then a Data tab
    (``ui.draw_blocks``) and an Actions tab (explicit trigger buttons, never auto-fired).

Casting notes (R3 §11 — "the classic id-space split"):
  * A buff carries BOTH ``skill_id`` (producing skill) and ``buff_id`` (runtime instance handle).
    ``DropBuff`` requires the ``buff_id`` — passing a skill_id silently fails. The Actions tab
    warns about this and offers a GetBuffID(skill_id) resolver.
  * Effects are keyed by ``skill_id`` (EffectExists / GetEffectTimeRemaining / EffectAttributeLevel);
    ``effect_id`` is a separate, unused-for-lookup field.
  * There is no enum-name casting in this domain — everything stays numeric except the skill name,
    which comes from ``Skill.GetName(skill_id)`` (native ``skill.id.GetName()`` double-hop).

R2 coverage (PyEffects, 19 methods) — wired via the ``Effects`` wrapper:
  __init__ (implicit in every getter via get_instance), GetEffects, GetBuffs, GetEffectCount,
  GetBuffCount, EffectExists, BuffExists, DropBuff (action), GetAlcoholLevel,
  ApplyDrunkEffect (action). Plus wrapper conveniences built on the surface: HasEffect,
  EffectAttributeLevel, GetEffectTimeRemaining, GetBuffID, get_instance.
Skipped: the 9 module-level free functions (get_alcohol_level, get_drunk_af, drop_buff,
  effect_count, buff_count, effect_exists, buff_exists, get_effects, get_buffs) — these are raw
  duplicates of the PyEffects class methods the wrapper already exposes; the wrapper never surfaces
  the free forms, so there is nothing new to wire.
"""

import PyImGui

from Py4GWCoreLib import GLOBAL_CACHE
from Py4GWCoreLib import Agent
from Py4GWCoreLib import Routines
from Py4GWCoreLib.Effect import Effects
from Py4GWCoreLib.Player import Player

from . import casts
from . import diagnostics
from . import ui

_SECTION = "Effects"


class _State:
    agent_id: int = 0
    skill_id_probe: int = 0
    drop_buff_id: int = 0
    resolve_skill_id: int = 0
    drunk_intensity: int = 0
    drunk_tint: int = 0


state = _State()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _skill_name(skill_id) -> str:
    """Resolve a skill_id to its name (Skill.GetName -> native skill.id.GetName())."""
    if not skill_id:
        return ""
    return casts.safe(GLOBAL_CACHE.Skill.GetName, skill_id, default="?")


def _field(struct, name, default=0):
    """Deref a single BuffType/EffectType field — never repr the whole struct (R3 §11)."""
    return casts.safe(getattr, struct, name, default=default)


# ---------------------------------------------------------------------------
# build_* — call getters, cast, return blocks (shared by render AND dump)
# ---------------------------------------------------------------------------
def _summary_block(agent_id):
    rows = [
        ("Agent ID", agent_id),
        ("Agent Name", casts.safe(Agent.GetNameByID, agent_id, default="?")),
        ("Buff Count", casts.safe(GLOBAL_CACHE.Effects.GetBuffCount, agent_id)),
        ("Effect Count", casts.safe(GLOBAL_CACHE.Effects.GetEffectCount, agent_id)),
        # base wrapper: not on GLOBAL_CACHE
        ("Alcohol Level", casts.safe(Effects.GetAlcoholLevel)),
    ]
    return ui.kv_block("Summary", rows)


def _buffs_block(agent_id):
    buffs = casts.safe(GLOBAL_CACHE.Effects.GetBuffs, agent_id, default=[]) or []
    headers = ["buff_id", "skill_id", "skill name", "target_agent_id"]
    rows = []
    for buff in buffs:
        skill_id = _field(buff, "skill_id")
        rows.append(
            (
                _field(buff, "buff_id"),
                skill_id,
                _skill_name(skill_id),
                _field(buff, "target_agent_id"),
            )
        )
    return ui.multi_block(f"Buffs ({len(rows)})", headers, rows)


def _effects_block(agent_id):
    effects = casts.safe(GLOBAL_CACHE.Effects.GetEffects, agent_id, default=[]) or []
    headers = [
        "effect_id",
        "skill_id",
        "skill name",
        "duration",
        "attr_lvl",
        "time_remaining",
        "time_elapsed",
        "timestamp",
        "agent_id",
    ]
    rows = []
    for eff in effects:
        skill_id = _field(eff, "skill_id")
        rows.append(
            (
                _field(eff, "effect_id"),
                skill_id,
                _skill_name(skill_id),
                casts.f2(_field(eff, "duration", default=0.0)),
                _field(eff, "attribute_level"),
                _field(eff, "time_remaining"),
                _field(eff, "time_elapsed"),
                _field(eff, "timestamp"),
                _field(eff, "agent_id"),
            )
        )
    return ui.multi_block(f"Effects ({len(rows)})", headers, rows)


def _queries_block(agent_id, skill_id):
    """The rest of the by-skill_id surface, evaluated for the current query skill_id."""
    rows = [
        ("Query skill_id", skill_id),
        ("EffectExists(agent, skill_id)", casts.yesno(casts.safe(GLOBAL_CACHE.Effects.EffectExists, agent_id, skill_id))),
        ("BuffExists(agent, skill_id)", casts.yesno(casts.safe(GLOBAL_CACHE.Effects.BuffExists, agent_id, skill_id))),
        ("HasEffect(agent, skill_id)", casts.yesno(casts.safe(GLOBAL_CACHE.Effects.HasEffect, agent_id, skill_id))),
        ("EffectAttributeLevel(agent, skill_id)", casts.safe(GLOBAL_CACHE.Effects.EffectAttributeLevel, agent_id, skill_id)),
        ("GetEffectTimeRemaining(agent, skill_id)", casts.safe(GLOBAL_CACHE.Effects.GetEffectTimeRemaining, agent_id, skill_id)),
        ("GetBuffID(skill_id) -> buff_id [player-scoped]", casts.safe(GLOBAL_CACHE.Effects.GetBuffID, skill_id)),
    ]
    return ui.kv_block("Queries by skill_id", rows)


def build_effects(agent_id):
    return [
        _summary_block(agent_id),
        _buffs_block(agent_id),
        _effects_block(agent_id),
        _queries_block(agent_id, state.skill_id_probe),
    ]


# ---------------------------------------------------------------------------
# Per-agent selector (input_int + load buttons) — drawn between separator and tabs
# ---------------------------------------------------------------------------
def _draw_selector():
    state.agent_id = PyImGui.input_int("Agent ID", state.agent_id)
    if PyImGui.button("Load Self"):
        state.agent_id = casts.safe(Player.GetAgentID, default=0) or 0
    PyImGui.same_line(0, 8)
    if PyImGui.button("Nearest Ally"):
        state.agent_id = casts.safe(Routines.Agents.GetNearestAlly, default=0) or state.agent_id
    PyImGui.same_line(0, 8)
    if PyImGui.button("Nearest Enemy"):
        state.agent_id = casts.safe(Routines.Agents.GetNearestEnemy, default=0) or state.agent_id
    PyImGui.same_line(0, 8)
    if PyImGui.button("Target"):
        state.agent_id = casts.safe(Player.GetTargetID, default=0) or state.agent_id
    state.skill_id_probe = PyImGui.input_int("Query skill_id (drives Data queries)", state.skill_id_probe)


# ---------------------------------------------------------------------------
# Actions — explicit trigger buttons, fired only on click
# ---------------------------------------------------------------------------
def _resolve_buff_id():
    """GetBuffID(skill_id) -> buff_id, stashed into the DropBuff field. Player-scoped (R3 §11)."""
    buff_id = GLOBAL_CACHE.Effects.GetBuffID(state.resolve_skill_id)
    state.drop_buff_id = buff_id
    return buff_id


def _draw_actions():
    ui.section_header("Drop Buff  (needs buff_id, NOT skill_id!)")
    ui.text_muted("DropBuff takes the runtime buff_id. Passing a skill_id silently fails (R3 §11).")
    state.drop_buff_id = PyImGui.input_int("buff_id", state.drop_buff_id)
    ui.action_button("Drop Buff", GLOBAL_CACHE.Effects.DropBuff, state.drop_buff_id, key="drop_buff")

    PyImGui.spacing()
    ui.text_muted("Helper: resolve a buff_id from a skill_id (player-scoped GetBuffID).")
    state.resolve_skill_id = PyImGui.input_int("skill_id -> buff_id", state.resolve_skill_id)
    ui.action_button("Resolve buff_id", _resolve_buff_id, key="resolve_buff")

    PyImGui.spacing()
    ui.section_header("Alcohol / Drunk")
    state.drunk_intensity = PyImGui.input_int("Intensity", state.drunk_intensity)
    state.drunk_tint = PyImGui.input_int("Tint", state.drunk_tint)
    ui.action_button(
        "Apply Drunk Effect",
        # base wrapper: not on GLOBAL_CACHE
        Effects.ApplyDrunkEffect,
        state.drunk_intensity,
        state.drunk_tint,
        key="drunk",
    )


# ---------------------------------------------------------------------------
# draw_*_view — uniform section entry point
# ---------------------------------------------------------------------------
def draw_effects_view() -> None:
    if state.agent_id == 0:
        state.agent_id = casts.safe(Player.GetAgentID, default=0) or 0
    blocks = build_effects(state.agent_id)
    diagnostics.dump_button(_SECTION, blocks)
    PyImGui.separator()
    _draw_selector()
    PyImGui.separator()
    if PyImGui.begin_tab_bar("EffectsTabs"):
        if PyImGui.begin_tab_item("Data"):
            ui.draw_blocks(_SECTION, blocks)
            PyImGui.end_tab_item()
        if PyImGui.begin_tab_item("Actions"):
            _draw_actions()
            PyImGui.end_tab_item()
        PyImGui.end_tab_bar()
