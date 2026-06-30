#pragma once

#include "base/hook_types.h"

#include "GW/agent/agent.h"
#include "GW/common/constants/constants.h"
#include "GW/context/attribute.h"
#include "GW/context/skill.h"
#include "GW/context/world.h"

#include <cstdint>

namespace GW::skillbar {

using SkillbarArray = Context::SkillbarArray;
using Skill = Context::Skill;
using AttributeInfo = Context::AttributeInfo;
using Skillbar = Context::Skillbar;
using SkillbarSkill = Context::SkillbarSkill;
using PartyAttributeArray = Context::PartyAttributeArray;
using PartyAttribute = Context::PartyAttribute;
using ProfessionState = Context::ProfessionState;
using Attribute = Context::SkillTemplateAttribute;
using SkillTemplate = Context::SkillTemplate;

using UseSkillCallback = PY4GW::HookCallback<uint32_t, uint32_t, uint32_t, uint32_t>;

bool Initialize();
void Shutdown();

int GetSkillSlot(Constants::SkillID skill_id);
bool UseSkill(uint32_t slot, uint32_t target = 0);
bool PointBlankUseSkill(uint32_t slot);
bool UseSkillByID(uint32_t skill_id, uint32_t target = 0);
Skill* GetSkillConstantData(Constants::SkillID skill_id);
AttributeInfo* GetAttributeConstantData(Constants::Attribute attribute_id);
bool ChangeSecondProfession(Constants::Profession profession, uint32_t hero_index = 0);
Skillbar* GetPlayerSkillbar();
Skillbar* GetHeroSkillbar(uint32_t hero_index);
Skill* GetHoveredSkill();
SkillTemplate GetSkillTemplate(uint32_t hero_index = 0);
bool GetIsSkillUnlocked(Constants::SkillID skill_id);
bool GetIsSkillLearnt(Constants::SkillID skill_id);
bool DecodeSkillTemplate(SkillTemplate* result, const char* temp);
bool EncodeSkillTemplate(const SkillTemplate& in, char* result, size_t result_len);
bool LoadSkillbar(Constants::SkillID* skills, size_t n_skills, uint32_t hero_index = 0);
bool LoadSkillTemplate(const char* temp);
bool LoadSkillTemplate(const char* temp, uint32_t hero_index);
bool SetAttributes(uint32_t attribute_count, uint32_t* attribute_ids, uint32_t* attribute_values, uint32_t hero_index = 0);
bool SetAttributes(Attribute* attributes, size_t n_attributes, uint32_t hero_index = 0);
void RegisterUseSkillCallback(PY4GW::HookEntry* entry, const UseSkillCallback& callback);
void RemoveUseSkillCallback(PY4GW::HookEntry* entry);

const ProfessionState* GetAgentProfessionState(uint32_t agent_id);
Constants::Profession GetSkillProfession(Constants::SkillID skill_id);
bool IsPrimaryAttributeRequired(const SkillTemplate& skill_template, Constants::Profession profession);
bool IsProfessionRequired(const SkillTemplate& skill_template, Constants::Profession profession);
Constants::Profession GetAttributeProfession(Constants::Attribute attribute, bool* is_primary_attribute = nullptr);

}  // namespace GW::skillbar

namespace GW {
namespace Skillbar = skillbar;
}
