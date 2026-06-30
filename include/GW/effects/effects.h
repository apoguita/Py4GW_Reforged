#pragma once

#include "GW/context/skill.h"

namespace GW::effects {
	bool Initialize();
	void Shutdown();

	uint32_t GetAlcoholLevel();
	void GetDrunkAf(uint32_t intensity, uint32_t tint);

	Context::AgentEffects* GetAgentEffectsArray(uint32_t agent_id);
	Context::AgentEffects* GetPlayerEffectsArray();
	Context::EffectArray* GetAgentEffects(uint32_t agent_id);
	Context::BuffArray* GetAgentBuffs(uint32_t agent_id);
	Context::EffectArray* GetPlayerEffects();
	Context::BuffArray* GetPlayerBuffs();
	bool DropBuff(uint32_t buff_id);
	Context::Effect* GetPlayerEffectBySkillId(GW::Constants::SkillID skill_id);
	Context::Buff* GetPlayerBuffBySkillId(GW::Constants::SkillID skill_id);

}  // namespace GW::effects
