#pragma once

#include "base/error_handling.h"

#include "GW/common/constants/constants.h"
#include "GW/common/gw_array.h"
#include "GW/common/constants/skills.h"

#include <cstddef>
#include <cstdint>
#include <windows.h>

namespace GW::Context {

    struct AttributeInfo;

    struct Skill { // total : 0xA0/160
        /* +h0000 */ GW::Constants::SkillID skill_id;
        /* +h0004 */ uint32_t h0004;
        /* +h0008 */ GW::Constants::Campaign campaign;
        /* +h000C */ GW::Constants::SkillType type;
        /* +h0010 */ uint32_t special;
        /* +h0014 */ uint32_t combo_req;
        /* +h0018 */ uint32_t effect1;
        /* +h001C */ uint32_t condition;
        /* +h0020 */ uint32_t effect2;
        /* +h0024 */ uint32_t weapon_req;
        /* +h0028 */ GW::Constants::ProfessionByte profession;
        /* +h0029 */ GW::Constants::AttributeByte attribute;
        /* +h002A */ uint16_t title;
        /* +h002C */ GW::Constants::SkillID skill_id_pvp;
        /* +h0030 */ uint8_t combo;
        /* +h0031 */ uint8_t target;
        /* +h0032 */ uint8_t h0032;
        /* +h0033 */ uint8_t skill_equip_type;
        /* +h0034 */ uint8_t overcast; // only if special flag has 0x000001 set
        /* +h0035 */ uint8_t energy_cost;
        /* +h0036 */ uint8_t health_cost;
        /* +h0037 */ uint8_t h0037;
        /* +h0038 */ uint32_t adrenaline;
        /* +h003C */ float activation;
        /* +h0040 */ float aftercast;
        /* +h0044 */ uint32_t duration0;
        /* +h0048 */ uint32_t duration15;
        /* +h004C */ uint32_t recharge;
        /* +h0050 */ uint16_t h0050[4];
        /* +h0058 */ uint32_t skill_arguments; // 1 - duration set, 2 - scale set, 4 - bonus scale set (3 would mean duration and scale is set/used by the skill)
        /* +h005C */ uint32_t scale0;
        /* +h0060 */ uint32_t scale15;
        /* +h0064 */ uint32_t bonusScale0;
        /* +h0068 */ uint32_t bonusScale15;
        /* +h006C */ float aoe_range;
        /* +h0070 */ float const_effect;
        /* +h0074 */ uint32_t caster_overhead_animation_id; //2077 == max == no animation
        /* +h0078 */ uint32_t caster_body_animation_id;
        /* +h007C */ uint32_t target_body_animation_id;
        /* +h0080 */ uint32_t target_overhead_animation_id;
        /* +h0084 */ uint32_t projectile_animation_1_id;
        /* +h0088 */ uint32_t projectile_animation_2_id;
        /* +h008C */ uint32_t icon_file_id;
        /* +h0090 */ uint32_t icon_file_id_2;
        /* +h0094 */ uint32_t icon_file_id_hi_res;
        /* +h0098 */ uint32_t name; // String id
        /* +h009C */ uint32_t concise; // String id
        /* +h00A0 */ uint32_t description; // String id

        uint8_t GetEnergyCost() const {
            switch (energy_cost) {
            case 11: return 15;
            case 12: return 25;
            default: return energy_cost;
            }
        }

        [[nodiscard]] bool IsTouchRange() const { return (special & 0x2) != 0; }
        [[nodiscard]] bool IsElite() const { return (special & 0x4) != 0; }
        [[nodiscard]] bool IsHalfRange() const { return (special & 0x8) != 0; }
        [[nodiscard]] bool IsPvP() const { return (special & 0x400000) != 0; }
        [[nodiscard]] bool IsPvE() const { return (special & 0x80000) != 0; }
        [[nodiscard]] bool IsPlayable() const { return (special & 0x2000000) == 0; }

        // NB: Guild Wars uses the skill array to build mods for weapons, so stuff like runes are skills too, and use stacking/non-stacking flags
        [[nodiscard]] bool IsStacking() const { return (special & 0x10000) != 0; }
        [[nodiscard]] bool IsNonStacking() const { return (special & 0x20000) != 0; }
        [[nodiscard]] bool IsUnused() const;
    };
    static_assert(sizeof(Skill) == 0xA4, "Skill size mismatch");

    using SkillArray = GW::GWArray<Skill>;

    struct SkillbarSkill { // total: 0x14/20
        /* +h0000 */ uint32_t adrenaline_a;
        /* +h0004 */ uint32_t adrenaline_b;
        /* +h0008 */ uint32_t recharge;
        /* +h000C */ Constants::SkillID skill_id; // see GWConst::SkillIds
        /* +h0010 */ uint32_t event;

        uint32_t GetRecharge() const; // returns recharge time remaining in milliseconds, or 0 if recharged
    };

    struct SkillbarCast {
        /* +h0000 */ uint16_t h0000;
        /* +h0002 */ Constants::SkillID skill_id;
        /* +h0004 */ uint32_t h0004;
    };

    using SkillbarCastArray = GW::GWArray<SkillbarCast>;

    struct Skillbar { // total: 0xBC/188
        /* +h0000 */ uint32_t agent_id; // id of the agent whose skillbar this is
        /* +h0004 */ SkillbarSkill skills[8];
        /* +h00A4 */ uint32_t disabled;
        /* +h00A8 */ uint32_t h00A8[2];
        /* +h00B0 */ uint32_t casting;
        /* +h00B4 */ uint32_t h00B4[2];

        bool IsValid() const { return agent_id > 0; }

        SkillbarSkill* GetSkillById(Constants::SkillID skill_id, size_t* slot_out = nullptr);
    };

    using SkillbarArray = GW::GWArray<Skillbar>;

    struct Effect { // total: 0x18/24
        /* +h0000 */ GW::Constants::SkillID skill_id; // skill id of the effect
        /* +h0004 */ uint32_t attribute_level; // attribute level for the skill used
        /* +h0008 */ uint32_t effect_id; // unique identifier of effect
        /* +h000C */ uint32_t agent_id; // non-zero means maintained enchantment - caster id
        /* +h0010 */ float duration; // non-zero if effect has a duration
        /* +h0014 */ DWORD timestamp; // GW-timestamp of when effect was applied - only with duration

        DWORD GetTimeElapsed() const;
        DWORD GetTimeRemaining() const;
    };

    struct Buff { // total: 0x10/16
        /* +h0000 */ GW::Constants::SkillID skill_id; // skill id of the buff
        /* +h0004 */ uint32_t h0004;
        /* +h0008 */ uint32_t buff_id; // id of buff in the buff array
        /* +h000C */ uint32_t target_agent_id; // agent id of the target (0 if no target)
    };

    using BuffArray = GW::GWArray<Buff>;
    using EffectArray = GW::GWArray<Effect>;

    struct AgentEffects { // total: 0x24/36
        /* +h0000 */ uint32_t agent_id;
        /* +h0004 */ BuffArray buffs;
        /* +h0014 */ EffectArray effects;
    };

    using AgentEffectsArray = GW::GWArray<AgentEffects>;

    static_assert(sizeof(SkillbarSkill) == 0x14, "SkillbarSkill size mismatch");
    static_assert(sizeof(Skillbar) == 0xBC, "Skillbar size mismatch");
    static_assert(sizeof(Effect) == 0x18, "Effect size mismatch");
    static_assert(sizeof(Buff) == 0x10, "Buff size mismatch");
    static_assert(sizeof(AgentEffects) == 0x24, "AgentEffects size mismatch");

    struct SkillTemplateAttribute {
        Constants::Attribute attribute = Constants::Attribute::None;
        uint32_t points = 0;
    };

    struct SkillTemplate {
        Constants::Profession primary = Constants::Profession::None;
        Constants::Profession secondary = Constants::Profession::None;
        Constants::SkillID skills[8] = {};
        SkillTemplateAttribute attributes[16] = {};
    };

    Skill* GetSkillArray();
    AttributeInfo* GetAttributeInfoArray();

}  // namespace GW::Context
