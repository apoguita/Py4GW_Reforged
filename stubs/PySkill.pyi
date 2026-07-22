# PySkill.pyi - type stub for the PySkill embedded module.
#
# Mirrors src/GW/skillbar/skill_bindings.cpp exactly: skill constant-data over
# GW::Context::Skill. Exposes four classes (SkillID, SkillType, SkillProfession,
# Skill); no free functions and no enums.

from typing import overload

class SkillID:
    id: int  # read-only

    @overload
    def __init__(self) -> None: ...
    @overload
    def __init__(self, id: int) -> None: ...
    @overload
    def __init__(self, skillname: str) -> None: ...
    # The bindings only accept an int operand (comparison against a raw skill id).
    def __eq__(self, other: object) -> bool: ...
    def __ne__(self, other: object) -> bool: ...
    def GetName(self) -> str: ...

class SkillType:
    id: int  # read-only

    @overload
    def __init__(self) -> None: ...
    @overload
    def __init__(self, arg0: int, /) -> None: ...  # py::init<int> declared without py::arg -> positional only
    # The bindings only accept an int operand.
    def __eq__(self, other: object) -> bool: ...
    def __ne__(self, other: object) -> bool: ...
    def GetName(self) -> str: ...

# Minimal profession wrapper used by Skill.profession. Legacy exposed a full
# PyAgent.Profession object; skill consumers only need ToInt()/GetName().
class SkillProfession:
    id: int  # read-only

    @overload
    def __init__(self) -> None: ...
    @overload
    def __init__(self, id: int) -> None: ...
    def ToInt(self) -> int: ...
    def GetName(self) -> str: ...

class Skill:
    id: SkillID
    campaign: int
    type: SkillType
    special: int
    combo_req: int
    effect1: int
    condition: int
    effect2: int
    weapon_req: int
    profession: SkillProfession
    attribute: int  # raw attribute id (legacy exposed an AttributeClass object)
    title: int
    id_pvp: int
    combo: int
    target: int
    skill_equip_type: int
    overcast: int
    energy_cost: int
    health_cost: int
    adrenaline: int
    activation: float
    aftercast: float
    duration_0pts: int
    duration_15pts: int
    recharge: int
    skill_arguments: int
    scale_0pts: int
    scale_15pts: int
    bonus_scale_0pts: int
    bonus_scale_15pts: int
    aoe_range: float
    const_effect: float
    caster_overhead_animation_id: int
    caster_body_animation_id: int
    target_body_animation_id: int
    target_overhead_animation_id: int
    projectile_animation1_id: int
    projectile_animation2_id: int
    icon_file_id: int
    icon_file2_id: int
    icon_file_hi_res_id: int
    name_id: int
    concise: int
    description_id: int
    is_touch_range: bool
    is_elite: bool
    is_half_range: bool
    is_pvp: bool
    is_pve: bool
    is_playable: bool
    is_stacking: bool
    is_non_stacking: bool
    is_unused: bool
    # Vestigial in legacy (never populated); kept for surface parity.
    adrenaline_a: int
    adrenaline_b: int
    recharge2: int
    h0004: int
    h0032: int
    h0037: int

    @overload
    def __init__(self) -> None: ...
    @overload
    def __init__(self, id: int) -> None: ...
    @overload
    def __init__(self, skillname: str) -> None: ...
    def GetContext(self) -> None: ...
