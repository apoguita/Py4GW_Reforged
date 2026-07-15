"""
Skill section — subject-id driven inspector, mirrors the player_demo template.

Shape (see SPEC_reengineer.md §1.2 / R1 §8):
  * ``build_skill(skill_id)`` calls the ``Skill`` wrapper getters for ONE subject skill id, CASTS
    each value via ``casts`` (nested handle chains dereffed explicitly — never a raw ``PySkill``
    handle repr), and returns a list of display Blocks shared by the on-screen view AND the dump.
  * ``draw_skill_view()`` builds once, offers the per-section Dump-to-file button, then a subject-id
    module (``input_int`` + a "Load Hovered" convenience button wired to
    ``GLOBAL_CACHE.SkillBar.GetHoveredSkillID()``), then a single Data tab.

Data path: ``Py4GWCoreLib.Skill.Skill`` (base wrapper over the ``PySkill`` handle chain). The
handle carries no data until an accessor is called and its fields nest — ``.id`` is a ``SkillID``
(``.id.GetName()``), ``.type`` a ``SkillType`` (``.type.id`` / ``.type.GetName()``), ``.profession``
a ``SkillProfession`` (``.ToInt()`` / ``.GetName()``); R3 §9. The wrapper resolves all of these, so
we call the wrapper (which already returns ``(id, name)`` tuples / plain scalars), never the raw
handle. There are NO skill actions in the wrapper (use-skill lives on ``Skillbar``), so no Actions tab.

R2 coverage — PySkill (batch b4) is class-only: ``SkillID``/``SkillType``/``SkillProfession``/``Skill``
(ctors, ``__eq__``/``__ne__``, ``GetName``, ``ToInt``, ``GetContext``) plus ~60 ``def_readonly``
fields, all eagerly populated at construction. Those low-level bindings are consumed transitively
through the ``Skill`` wrapper — this section wires every wrapper getter over them:
  Common: GetName, GetType->(id,name), GetCampaign->(id,name), GetProfession->(id,name),
    GetDescription, GetConciseDescription, GetNameFromWiki, GetURL, GetProgressionData.
  Data: GetCombo, GetComboReq, GetWeaponReq, GetOvercast, GetEnergyCost, GetHealthCost,
    GetAdrenaline, GetAdrenalineA, GetAdrenalineB, GetActivation, GetAftercast, GetRecharge,
    GetRecharge2, GetAoERange.
  Attribute: GetAttribute (int in the current Native first-pass; deref'd to .GetName()/.level/
    .level_base when it is the documented handle form), GetScale->(s0,s15),
    GetBonusScale->(b0,b15), GetDuration->(d0,d15).
  Flags: 38 booleans (IsTouchRange, IsElite, IsHalfRange, IsPvP, IsPvE, IsPlayable, IsStacking,
    IsNonStacking, IsUnused, IsHex, IsBounty, IsScroll, IsStance, IsSpell, IsEnchantment, IsSignet,
    IsCondition, IsWell, IsSkill, IsWard, IsGlyph, IsTitle, IsAttack, IsShout, IsSkill2, IsPassive,
    IsEnvironmental, IsPreparation, IsPetAttack, IsTrap, IsRitual, IsEnvironmentalTrap, IsItemSpell,
    IsWeaponSpell, IsForm, IsChant, IsEchoRefrain, IsDisguise) -> ui.bool_block.
  Animations: GetEffects->(e1,e2), GetSpecial, GetConstEffect, GetCasterOverheadAnimationID,
    GetCasterBodyAnimationID, GetTargetBodyAnimationID, GetTargetOverheadAnimationID,
    GetProjectileAnimationID->(a1,a2), GetIconFileID->(f1,f2).
  ExtraData: GetCondition, GetTitle, GetIDPvP, GetTarget, GetSkillEquipType, GetSkillArguments,
    GetNameID, GetConcise, GetDescriptionID, GetTexturePath.
Skipped (by design, not subject-bound / not renderable): skill_instance (raw handle factory — never
repr'd, R3 §9 trap), GetID(name) (inverse name->id lookup, takes a name not the subject id).
"""

import PyImGui

from Py4GWCoreLib import GLOBAL_CACHE
from Py4GWCoreLib.Skill import Skill

from . import casts
from . import diagnostics
from . import ui

_SECTION = "Skill"


class _State:
    skill_id: int = 0


state = _State()


# ---------------------------------------------------------------------------
# Subject id resolution (state.skill_id, falling back to the hovered skill)
# ---------------------------------------------------------------------------
def _hovered_skill_id() -> int:
    try:
        from Py4GWCoreLib import GLOBAL_CACHE

        return int(GLOBAL_CACHE.SkillBar.GetHoveredSkillID() or 0)
    except Exception:  # noqa: BLE001 - cache/binding may be absent offline
        pass
    try:
        from Py4GWCoreLib.Skillbar import SkillBar

        return int(SkillBar.GetHoveredSkillID() or 0)
    except Exception:  # noqa: BLE001
        return 0


def _subject_id() -> int:
    if state.skill_id:
        return state.skill_id
    return _hovered_skill_id()


# ---------------------------------------------------------------------------
# build_* — call getters, cast, return blocks (shared by render AND dump)
# ---------------------------------------------------------------------------
def _common_block(skill_id):
    rows = [
        ("Name", casts.safe(GLOBAL_CACHE.Skill.GetName, skill_id)),
        ("Type", casts.id_name_tuple(casts.safe(GLOBAL_CACHE.Skill.GetType, skill_id))),
        ("Campaign", casts.id_name_tuple(casts.safe(GLOBAL_CACHE.Skill.GetCampaign, skill_id))),
        ("Profession", casts.id_name_tuple(casts.safe(GLOBAL_CACHE.Skill.GetProfession, skill_id))),
        ("Wiki Name", casts.safe(GLOBAL_CACHE.Skill.GetNameFromWiki, skill_id)),
        ("Wiki URL", casts.safe(GLOBAL_CACHE.Skill.GetURL, skill_id)),
    ]
    return ui.kv_block("Common", rows)


def _descriptions_block(skill_id):
    full = casts.safe(GLOBAL_CACHE.Skill.GetDescription, skill_id, default="")
    concise = casts.safe(GLOBAL_CACHE.Skill.GetConciseDescription, skill_id, default="")
    # base wrapper: not on GLOBAL_CACHE
    progressions = casts.safe(Skill.GetProgressionData, skill_id, default=[]) or []
    lines = [f"Full: {full}", f"Concise: {concise}", f"Progression entries: {len(progressions)}"]
    for attr, field, values in progressions:
        lines.append(f"  [{attr}] {field}: {values}")
    return ui.text_block("Descriptions", "\n".join(lines))


def _data_block(skill_id):
    D = GLOBAL_CACHE.Skill.Data
    rows = [
        ("Combo", casts.safe(D.GetCombo, skill_id)),
        ("Combo Req", casts.safe(D.GetComboReq, skill_id)),
        ("Weapon Req", casts.safe(D.GetWeaponReq, skill_id)),
        ("Overcast", casts.safe(D.GetOvercast, skill_id)),
        ("Energy Cost", casts.safe(D.GetEnergyCost, skill_id)),
        ("Health Cost", casts.safe(D.GetHealthCost, skill_id)),
        ("Adrenaline", casts.safe(D.GetAdrenaline, skill_id)),
        ("Adrenaline A", casts.safe(D.GetAdrenalineA, skill_id)),
        ("Adrenaline B", casts.safe(D.GetAdrenalineB, skill_id)),
        ("Activation", casts.f2(casts.safe(D.GetActivation, skill_id))),
        ("Aftercast", casts.f2(casts.safe(D.GetAftercast, skill_id))),
        ("Recharge", casts.safe(D.GetRecharge, skill_id)),
        ("Recharge 2", casts.safe(D.GetRecharge2, skill_id)),
        ("AoE Range", casts.f2(casts.safe(D.GetAoERange, skill_id))),
    ]
    return ui.kv_block("Data", rows)


def _attribute_block(skill_id):
    attr = casts.safe(GLOBAL_CACHE.Skill.Attribute.GetAttribute, skill_id)
    if attr is None:
        rows = [("GetAttribute", "None")]
    elif isinstance(attr, int):
        # Native first-pass returns a raw attribute id (R2 disagreements / R3 §9).
        rows = [("Attribute (id)", attr)]
    else:
        # Documented handle form (R1 §8): AttributeClass -> .GetName()/.level/.level_base.
        rows = casts.handle_rows(
            attr, [("Attribute Name", "GetName"), ("Level", "level"), ("Level Base", "level_base")]
        )
    scale = casts.safe(GLOBAL_CACHE.Skill.Attribute.GetScale, skill_id, default=(0, 0)) or (0, 0)
    bonus = casts.safe(GLOBAL_CACHE.Skill.Attribute.GetBonusScale, skill_id, default=(0, 0)) or (0, 0)
    duration = casts.safe(GLOBAL_CACHE.Skill.Attribute.GetDuration, skill_id, default=(0, 0)) or (0, 0)
    rows.extend([
        ("Scale (0 / 15 pts)", casts.vec(scale[0], scale[1])),
        ("Bonus Scale (0 / 15 pts)", casts.vec(bonus[0], bonus[1])),
        ("Duration (0 / 15 pts)", casts.vec(duration[0], duration[1])),
    ])
    return ui.kv_block("Attribute", rows)


_FLAG_METHODS = [
    ("Touch Range", "IsTouchRange"), ("Elite", "IsElite"), ("Half Range", "IsHalfRange"),
    ("PvP", "IsPvP"), ("PvE", "IsPvE"), ("Playable", "IsPlayable"),
    ("Stacking", "IsStacking"), ("Non-Stacking", "IsNonStacking"), ("Unused", "IsUnused"),
    ("Hex", "IsHex"), ("Bounty", "IsBounty"), ("Scroll", "IsScroll"),
    ("Stance", "IsStance"), ("Spell", "IsSpell"), ("Enchantment", "IsEnchantment"),
    ("Signet", "IsSignet"), ("Condition", "IsCondition"), ("Well", "IsWell"),
    ("Skill", "IsSkill"), ("Ward", "IsWard"), ("Glyph", "IsGlyph"),
    ("Title", "IsTitle"), ("Attack", "IsAttack"), ("Shout", "IsShout"),
    ("Skill2", "IsSkill2"), ("Passive", "IsPassive"), ("Environmental", "IsEnvironmental"),
    ("Preparation", "IsPreparation"), ("Pet Attack", "IsPetAttack"), ("Trap", "IsTrap"),
    ("Ritual", "IsRitual"), ("Environmental Trap", "IsEnvironmentalTrap"), ("Item Spell", "IsItemSpell"),
    ("Weapon Spell", "IsWeaponSpell"), ("Form", "IsForm"), ("Chant", "IsChant"),
    ("Echo/Refrain", "IsEchoRefrain"), ("Disguise", "IsDisguise"),
]


def _flags_block(skill_id):
    items = []
    for label, method in _FLAG_METHODS:
        fn = getattr(GLOBAL_CACHE.Skill.Flags, method)
        items.append((label, bool(casts.safe(fn, skill_id))))
    return ui.bool_block("Flags", items)


def _animations_block(skill_id):
    A = GLOBAL_CACHE.Skill.Animations
    effects = casts.safe(A.GetEffects, skill_id, default=(0, 0)) or (0, 0)
    proj = casts.safe(A.GetProjectileAnimationID, skill_id, default=(0, 0)) or (0, 0)
    icons = casts.safe(A.GetIconFileID, skill_id, default=(0, 0)) or (0, 0)
    rows = [
        ("Effects (1 / 2)", f"{effects[0]} / {effects[1]}"),
        ("Special", casts.safe(A.GetSpecial, skill_id)),
        ("Const Effect", casts.f2(casts.safe(A.GetConstEffect, skill_id))),
        ("Caster Overhead Anim ID", casts.safe(A.GetCasterOverheadAnimationID, skill_id)),
        ("Caster Body Anim ID", casts.safe(A.GetCasterBodyAnimationID, skill_id)),
        ("Target Body Anim ID", casts.safe(A.GetTargetBodyAnimationID, skill_id)),
        ("Target Overhead Anim ID", casts.safe(A.GetTargetOverheadAnimationID, skill_id)),
        ("Projectile Anim ID (1 / 2)", f"{proj[0]} / {proj[1]}"),
        ("Icon File ID (1 / 2)", f"{icons[0]} / {icons[1]}"),
    ]
    return ui.kv_block("Animations", rows)


def _extradata_block(skill_id):
    E = GLOBAL_CACHE.Skill.ExtraData
    rows = [
        ("Condition", casts.safe(E.GetCondition, skill_id)),
        ("Title", casts.safe(E.GetTitle, skill_id)),
        ("ID PvP", casts.safe(E.GetIDPvP, skill_id)),
        ("Target", casts.safe(E.GetTarget, skill_id)),
        ("Skill Equip Type", casts.safe(E.GetSkillEquipType, skill_id)),
        ("Skill Arguments", casts.safe(E.GetSkillArguments, skill_id)),
        ("Name ID", casts.safe(E.GetNameID, skill_id)),
        ("Concise", casts.safe(E.GetConcise, skill_id)),
        ("Description ID", casts.safe(E.GetDescriptionID, skill_id)),
        ("Texture Path", casts.safe(E.GetTexturePath, skill_id)),
    ]
    return ui.kv_block("ExtraData", rows)


def build_skill(skill_id):
    if not skill_id:
        return [ui.text_block("Skill", "No skill selected or hovered. Enter a Skill ID below.")]
    return [
        ui.kv_block("Subject", [("Skill ID", skill_id)]),
        _common_block(skill_id),
        _descriptions_block(skill_id),
        _data_block(skill_id),
        _attribute_block(skill_id),
        _flags_block(skill_id),
        _animations_block(skill_id),
        _extradata_block(skill_id),
    ]


# ---------------------------------------------------------------------------
# draw_*_view — uniform section entry point
# ---------------------------------------------------------------------------
def draw_skill_view() -> None:
    skill_id = _subject_id()
    blocks = build_skill(skill_id)
    diagnostics.dump_button(_SECTION, blocks)
    PyImGui.separator()

    # Subject-id module: explicit id + a convenience "load hovered" button.
    state.skill_id = PyImGui.input_int("Skill ID (0 = hovered)", state.skill_id)
    if PyImGui.button("Load Hovered Skill"):
        state.skill_id = _hovered_skill_id()
    PyImGui.same_line(0, 8)
    ui.text_muted(f"Subject skill id: {skill_id}")
    PyImGui.separator()

    if PyImGui.begin_tab_bar("SkillTabs"):
        if PyImGui.begin_tab_item("Data"):
            ui.draw_blocks(_SECTION, blocks)
            PyImGui.end_tab_item()
        PyImGui.end_tab_bar()
