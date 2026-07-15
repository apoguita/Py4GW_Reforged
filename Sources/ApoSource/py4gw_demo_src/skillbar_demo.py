"""
Skillbar section — own bar slots, hero bars, queries, and use-skill actions.

Follows the player_demo template exactly (SPEC_reengineer.md §1.2):
  * ``build_skillbar()`` calls the base ``SkillBar`` wrapper getters, dereferences every
    ``SkillbarSkill`` struct field-by-field (NEVER repr the handle), casts via ``casts``, and
    returns a list of display Blocks.
  * ``draw_skillbar_view()`` builds once, renders those blocks, offers the per-section dump
    button, and exposes every mutating binding as an explicit trigger button.

Cast traps handled (R3 §10 — Skillbar):
  * ``SkillBar.GetSkillData(slot)`` returns a RAW ``SkillbarSkill`` handle — read its
    ``.id.id`` (double-unwrap SkillbarSkill -> SkillID -> int), ``.adrenaline_a/.adrenaline_b/
    .recharge/.event`` fields explicitly; the handle never reaches a renderer.
  * ``SkillBar.GetHeroSkillbar(hero_index)`` returns ``list[SkillbarSkill]`` — same per-skill deref.
  * ``event`` (uint32 bitfield) rendered dec | hex | bin via ``casts.flags``.

Heroes enumerated via ``GLOBAL_CACHE.Party.GetHeroes()`` (R1 §9); each ``HeroPartyMember`` exposes
``hero_id`` (int in Reforged), ``agent_id``, ``owner_player_id``, ``level``.

R2 coverage (PySkillbar wrapper surface, ``Py4GWCoreLib.Skillbar.SkillBar``):
  Data getters wired: GetSkillIDBySlot, GetSkillData (adrenaline_a/adrenaline_b/recharge/event),
  GetSkillbar, GetZeroFilledSkillbar, GetHeroSkillbar, GetHoveredSkillID, GetAgentID, GetDisabled,
  GetCasting, GetSlotBySkillID, IsSkillUnlocked, IsSkillLearnt.
  Actions wired: UseSkill, UseSkillTargetless, HeroUseSkill, ChangeHeroSecondary,
  LoadSkillTemplate, LoadHeroSkillTemplate.
  Names resolved via ``Skill.GetName`` (Py4GWCoreLib.Skill).
  Skipped (raw PySkillbar-only, not surfaced by the wrapper): SkillbarSkill.get_recharge property,
  Skillbar.__init__/GetContext/skills/skill(s) raw property accessors, GetSkill (wrapper exposes it
  as GetSkillData/GetSkillIDBySlot). These carry no data beyond the wired getters above.
"""

import PyImGui

from Py4GWCoreLib import GLOBAL_CACHE

from . import casts
from . import diagnostics
from . import ui

_SECTION = "Skillbar"

_OWN_HEADERS = ["Slot", "Skill ID", "Name", "Adren A", "Adren B", "Recharge", "Event"]
_HERO_HEADERS = ["#", "Skill ID", "Name", "Adren A", "Adren B", "Recharge", "Event"]


class _State:
    slot: int = 1
    target_id: int = 0
    query_skill_id: int = 0
    hero_index: int = 0
    hero_number: int = 1
    skill_number: int = 1
    secondary_profession: int = 0
    template: str = ""


state = _State()


# ---------------------------------------------------------------------------
# Struct deref helpers (M4) — a SkillbarSkill handle NEVER reaches a renderer
# ---------------------------------------------------------------------------
def _skill_row(label, skill):
    """Deref a raw SkillbarSkill struct into a display row. ``.id.id`` double-unwrap (R3 §10)."""
    if skill is None:
        return (label, "-", "", "", "", "", "")
    sid = casts.safe(lambda s: s.id.id, skill, default=0) or 0
    name = casts.safe(GLOBAL_CACHE.Skill.GetName, sid, default="") if sid else ""
    return (
        label,
        sid,
        name,
        casts.safe(getattr, skill, "adrenaline_a", default="<n/a>"),
        casts.safe(getattr, skill, "adrenaline_b", default="<n/a>"),
        casts.safe(getattr, skill, "recharge", default="<n/a>"),
        casts.flags(casts.safe(getattr, skill, "event", default=0)),
    )


# ---------------------------------------------------------------------------
# build_* — call getters, cast, return blocks (shared by render AND dump)
# ---------------------------------------------------------------------------
def _status_block():
    hovered = casts.safe(GLOBAL_CACHE.SkillBar.GetHoveredSkillID, default=0) or 0
    hovered_name = casts.safe(GLOBAL_CACHE.Skill.GetName, hovered, default="") if hovered else ""
    rows = [
        ("Owner Agent ID", casts.safe(GLOBAL_CACHE.SkillBar.GetAgentID)),
        ("Disabled", casts.safe(GLOBAL_CACHE.SkillBar.GetDisabled)),
        ("Casting", casts.safe(GLOBAL_CACHE.SkillBar.GetCasting)),
        ("Hovered Skill", casts.id_name(hovered, hovered_name) if hovered else "None"),
    ]
    return ui.kv_block("Status", rows)


def _own_bar_block():
    rows = []
    for slot in range(1, 9):
        skill = casts.safe(GLOBAL_CACHE.SkillBar.GetSkillData, slot)
        rows.append(_skill_row(f"Slot {slot}", skill))
    return ui.multi_block("Own Skillbar (slots 1-8)", _OWN_HEADERS, rows)


def _summary_block():
    active = casts.safe(GLOBAL_CACHE.SkillBar.GetSkillbar, default=[]) or []
    zero_filled = casts.safe(GLOBAL_CACHE.SkillBar.GetZeroFilledSkillbar, default={}) or {}
    rows = [
        ("GetSkillbar (non-zero IDs)", f"[{len(active)}] {list(active)}"),
        ("GetZeroFilledSkillbar (slot->id)", str(dict(zero_filled))),
    ]
    return ui.kv_block("Skillbar Summary", rows)


def _queries_block():
    sid = state.query_skill_id
    rows = [
        ("Query Skill ID", sid),
        ("GetSlotBySkillID", casts.safe(GLOBAL_CACHE.SkillBar.GetSlotBySkillID, sid)),
        ("IsSkillUnlocked", casts.yesno(casts.safe(GLOBAL_CACHE.SkillBar.IsSkillUnlocked, sid))),
        ("IsSkillLearnt", casts.yesno(casts.safe(GLOBAL_CACHE.SkillBar.IsSkillLearnt, sid))),
    ]
    return ui.kv_block("Queries (skill id set in Actions tab)", rows)


def _hero_blocks():
    heroes = casts.safe(GLOBAL_CACHE.Party.GetHeroes, default=[]) or []
    blocks = []
    if not heroes:
        return [ui.kv_block("Hero Skillbars", [("Heroes", "none in party")])]
    for hero_index, hero in enumerate(heroes):
        hero_id = casts.safe(getattr, hero, "hero_id", default="?")
        agent_id = casts.safe(getattr, hero, "agent_id", default="?")
        title = f"Hero {hero_index} (hero_id {hero_id}, agent {agent_id})"
        bar = casts.safe(GLOBAL_CACHE.SkillBar.GetHeroSkillbar, hero_index, default=[]) or []
        rows = []
        for idx, skill in enumerate(bar, start=1):
            rows.append(_skill_row(str(idx), skill))
        if not rows:
            rows.append(("-", "-", "empty / unavailable", "", "", "", ""))
        blocks.append(ui.multi_block(title, _HERO_HEADERS, rows))
    return blocks


def build_skillbar():
    blocks = [_status_block(), _own_bar_block(), _summary_block(), _queries_block()]
    blocks.extend(_hero_blocks())
    return blocks


# ---------------------------------------------------------------------------
# Actions — explicit trigger buttons, fired only on click
# ---------------------------------------------------------------------------
def _draw_actions():
    ui.section_header("Own Skillbar — Use")
    state.slot = PyImGui.input_int("Slot (1-8)", state.slot)
    state.target_id = PyImGui.input_int("Target Agent ID", state.target_id)
    ui.action_button("Use Skill", GLOBAL_CACHE.SkillBar.UseSkill, state.slot, state.target_id, key="use_skill")
    PyImGui.same_line(0, 8)
    ui.action_button("Use Skill Targetless", GLOBAL_CACHE.SkillBar.UseSkillTargetless, state.slot, key="use_targetless")

    PyImGui.spacing()
    ui.section_header("Own Skillbar — Quick Use (per slot)")
    for slot in range(1, 9):
        ui.action_button(f"Slot {slot}", GLOBAL_CACHE.SkillBar.UseSkill, slot, state.target_id, key=f"quick_{slot}")
        if slot % 4 != 0:
            PyImGui.same_line(0, 6)

    PyImGui.spacing()
    ui.section_header("Queries")
    state.query_skill_id = PyImGui.input_int("Query Skill ID", state.query_skill_id)

    PyImGui.spacing()
    ui.section_header("Hero Skillbar")
    state.hero_index = PyImGui.input_int("Hero Index", state.hero_index)
    state.hero_number = PyImGui.input_int("Hero Number (1-7)", state.hero_number)
    state.skill_number = PyImGui.input_int("Skill Number (1-8)", state.skill_number)
    ui.action_button(
        "Hero Use Skill", GLOBAL_CACHE.SkillBar.HeroUseSkill,
        state.target_id, state.skill_number, state.hero_number, key="hero_use",
    )
    state.secondary_profession = PyImGui.input_int("Secondary Profession", state.secondary_profession)
    ui.action_button(
        "Change Hero Secondary", GLOBAL_CACHE.SkillBar.ChangeHeroSecondary,
        state.hero_index, state.secondary_profession, key="hero_secondary",
    )

    PyImGui.spacing()
    ui.section_header("Templates")
    state.template = PyImGui.input_text("Skill Template", state.template)
    ui.action_button("Load Skill Template", GLOBAL_CACHE.SkillBar.LoadSkillTemplate, state.template, key="load_tpl")
    PyImGui.same_line(0, 8)
    ui.action_button(
        "Load Hero Skill Template", GLOBAL_CACHE.SkillBar.LoadHeroSkillTemplate,
        state.hero_index, state.template, key="load_hero_tpl",
    )


# ---------------------------------------------------------------------------
# draw_*_view — uniform section entry point
# ---------------------------------------------------------------------------
def draw_skillbar_view() -> None:
    blocks = build_skillbar()
    diagnostics.dump_button(_SECTION, blocks)
    PyImGui.separator()
    if PyImGui.begin_tab_bar("SkillbarTabs"):
        if PyImGui.begin_tab_item("Data"):
            ui.draw_blocks(_SECTION, blocks)
            PyImGui.end_tab_item()
        if PyImGui.begin_tab_item("Actions"):
            _draw_actions()
            PyImGui.end_tab_item()
        PyImGui.end_tab_bar()
