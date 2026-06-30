#pragma once

#include "GW/common/constants/constants.h"
#include "GW/common/game_pos.h"
#include "GW/context/attribute.h"
#include "GW/context/hero.h"
#include "GW/context/party.h"
#include "GW/context/world.h"

#include <cstdint>

namespace GW::party {

using AgentID = Context::AgentID;

bool Initialize();
void Shutdown();

void set_tick_toggle(bool enable);
bool tick(bool flag = true);
Context::Attribute* get_agent_attributes(uint32_t agent_id);
Context::PartySearch* get_party_search(uint32_t party_search_id = 0);
Context::PartyInfo* get_party_info(uint32_t party_id = 0);
uint32_t get_party_size();
uint32_t get_party_player_count();
uint32_t get_party_hero_count();
uint32_t get_party_henchman_count();
bool get_is_party_defeated();
bool set_hard_mode(bool flag);
bool return_to_outpost();
bool get_is_party_in_hard_mode();
bool get_is_hard_mode_unlocked();
bool get_is_party_ticked();
bool get_is_player_ticked(uint32_t player_index = 0xFFFFFFFF);
bool get_is_player_loaded(uint32_t player_index = 0xFFFFFFFF);
bool get_is_party_loaded();
bool get_is_leader();
bool respond_to_party_request(uint32_t party_id, bool accept);
bool leave_party();
bool add_hero(uint32_t heroid);
bool kick_hero(uint32_t heroid);
bool kick_all_heroes();
bool add_henchman(uint32_t agent_id);
bool kick_henchman(uint32_t agent_id);
bool invite_player(uint32_t player_id);
bool invite_player(const wchar_t* player_name);
bool kick_player(uint32_t player_id);
bool flag_hero(uint32_t hero_index, GamePos pos);
bool flag_hero_agent(AgentID agent_id, GamePos pos);
bool unflag_hero(uint32_t hero_index);
bool flag_all(GamePos pos);
bool unflag_all();
bool set_hero_behavior(uint32_t agent_id, Constants::HeroBehavior behavior);
bool set_hero_skill_ai_enabled(uint32_t hero_agent_id, uint32_t skill_slot, bool enabled);
bool set_pet_behavior(Constants::HeroBehavior behavior, uint32_t lock_target_id = 0);
Context::PetInfo* get_pet_info(uint32_t owner_agent_id = 0);
uint32_t get_hero_agent_id(uint32_t hero_index);
uint32_t get_agent_hero_id(AgentID agent_id);
Context::HeroInfo* get_hero_info(uint32_t hero_id);
bool search_party(uint32_t search_type, const wchar_t* advertisement = nullptr);
bool search_party_cancel();
bool search_party_reply(bool accept);

}  // namespace GW::party

namespace GW {
namespace Party = party;
}
