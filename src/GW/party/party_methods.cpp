#include "base/error_handling.h"

#include "GW/agent/agent.h"
#include "GW/chat/chat.h"
#include "GW/context/context.h"
#include "GW/context/world.h"
#include "GW/game_thread/game_thread.h"
#include "GW/map/map.h"
#include "GW/player/player.h"
#include "GW/party/party.h"
#include "GW/skillbar/skillbar.h"
#include "GW/ui/ui.h"

#include <cstdio>
#include <cmath>

namespace GW::party {

using PartySearchSeekFn = void(__cdecl*)(uint32_t search_type, const wchar_t* advertisement, uint32_t unk);
using PartySearchButtonCallbackFn = void(__fastcall*)(void* context, uint32_t edx, uint32_t* wparam);
using DoActionFn = void(__cdecl*)(uint32_t identifier);
using FlagHeroAgentFn = void(__cdecl*)(uint32_t agent_id, GW::GamePos* pos);
using FlagAllFn = void(__cdecl*)(GW::GamePos* pos);
using SetHeroBehaviorFn = void(__cdecl*)(uint32_t agent_id, Constants::HeroBehavior behavior);
using LockPetTargetFn = bool(__cdecl*)(uint32_t pet_agent_id, uint32_t target_id);
using CommandHotKeyDisableAiFn = void(__cdecl*)(uint32_t hero_agent_id, uint32_t zero_based_skill_slot);

extern PartySearchSeekFn g_party_search_seek_func;
extern PartySearchButtonCallbackFn g_party_search_button_callback_func;
extern PartySearchButtonCallbackFn g_party_window_button_callback_func;
extern DoActionFn g_set_ready_status_func;
extern DoActionFn g_set_difficulty_func;
extern FlagHeroAgentFn g_flag_hero_agent_func;
extern FlagAllFn g_flag_all_func;
extern SetHeroBehaviorFn g_set_hero_behavior_func;
extern LockPetTargetFn g_lock_pet_target_func;
extern CommandHotKeyDisableAiFn g_command_hot_key_disable_ai_func;
extern bool g_tick_work_as_toggle;

void set_tick_toggle(bool enable) {
    g_tick_work_as_toggle = enable;
}

bool tick(bool flag) {
    if (!(g_set_ready_status_func && get_party_info() &&
          map::GetInstanceType() == Constants::InstanceType::Outpost))
        return false;
    if (flag == get_is_player_ticked())
        return true;
    g_set_ready_status_func(flag);
    return true;
}

Context::Attribute* get_agent_attributes(uint32_t agent_id) {
    auto* w = Context::GetWorldContext();
    if (!(w && w->attributes.valid()))
        return nullptr;
    for (auto& agent_attributes : w->attributes) {
        if (agent_attributes.agent_id == agent_id)
            return agent_attributes.attribute;
    }
    return nullptr;
}

Context::PartySearch* get_party_search(uint32_t party_search_id) {
    const auto p = Context::GetPartyContext();
    if (!p) return nullptr;
    for (auto party : p->party_search) {
        if (party && party->party_search_id == party_search_id)
            return party;
    }
    return nullptr;
}

Context::PartyInfo* get_party_info(uint32_t party_id) {
    Context::PartyContext* ctx = Context::GetPartyContext();
    if (!ctx || !ctx->parties.size()) return nullptr;
    if (!party_id) return ctx->player_party;
    if (party_id >= ctx->parties.size())
        return nullptr;
    return ctx->parties[party_id];
}

uint32_t get_party_size() {
    Context::PartyInfo* info = get_party_info();
    return info ? info->players.size() + info->heroes.size() + info->henchmen.size() : 0;
}

uint32_t get_party_player_count() {
    Context::PartyInfo* info = get_party_info();
    return info ? info->players.size() : 0;
}

uint32_t get_party_hero_count() {
    Context::PartyInfo* info = get_party_info();
    return info ? info->heroes.size() : 0;
}

uint32_t get_party_henchman_count() {
    Context::PartyInfo* info = get_party_info();
    return info ? info->henchmen.size() : 0;
}

bool get_is_party_defeated() {
    auto* p = Context::GetPartyContext();
    return p ? p->IsDefeated() : false;
}

bool set_hard_mode(bool flag) {
    auto* p = Context::GetPartyContext();
    if (!(g_set_difficulty_func && p && p->player_party))
        return false;
    if (p->InHardMode() != flag) {
        g_set_difficulty_func(flag);
    }
    return true;
}

bool return_to_outpost() {
    return ui::ButtonClick(ui::GetChildFrame(ui::GetFrameByLabel(L"DlgRedirect"), 0));
}

bool get_is_party_in_hard_mode() {
    auto* p = Context::GetPartyContext();
    return p ? p->InHardMode() : false;
}

bool get_is_hard_mode_unlocked() {
    auto* w = Context::GetWorldContext();
    return w ? w->is_hard_mode_unlocked != 0 : false;
}

bool get_is_party_ticked() {
    Context::PartyInfo* info = get_party_info();
    if (!(info && info->players.valid())) return false;
    for (const Context::PlayerPartyMember& player : info->players) {
        if (!player.ticked()) return false;
    }
    return true;
}

bool get_is_party_loaded() {
    Context::PartyInfo* info = get_party_info();
    if (!(info && info->players.valid())) return false;
    for (const Context::PlayerPartyMember& player : info->players) {
        if (!player.connected()) return false;
    }
    return true;
}

bool get_is_player_ticked(uint32_t player_index) {
    Context::PartyInfo* info = get_party_info();
    if (!(info && info->players.valid())) return false;
    if (player_index == 0xFFFFFFFF) {
        uint32_t player_id = player::GetPlayerNumber();
        for (const Context::PlayerPartyMember& player : info->players) {
            if (player.login_number == player_id)
                return player.ticked();
        }
        return false;
    } else {
        if (player_index >= info->players.size()) return false;
        return (info->players[player_index].ticked());
    }
}

bool get_is_player_loaded(uint32_t player_index) {
    Context::PartyInfo* info = get_party_info();
    if (!(info && info->players.valid())) return false;
    if (player_index == 0xFFFFFFFF) {
        uint32_t player_id = player::GetPlayerNumber();
        for (const Context::PlayerPartyMember& player : info->players) {
            if (player.login_number == player_id)
                return player.connected();
        }
        return false;
    } else {
        if (player_index >= info->players.size()) return false;
        return (info->players[player_index].connected());
    }
}

bool get_is_leader() {
    Context::PartyInfo* info = get_party_info();
    if (!(info && info->players.valid())) return false;
    uint32_t player_id = player::GetPlayerNumber();
    for (const Context::PlayerPartyMember& player : info->players) {
        if (player.connected())
            return player.login_number == player_id;
    }
    return false;
}

bool respond_to_party_request(uint32_t party_id, bool accept) {
    (void)party_id;
    (void)accept;
    return true;
}

bool leave_party() {
    if (!g_party_window_button_callback_func)
        return false;
    if (!get_party_size())
        return true;

    uint32_t ctx[14] = { 0 };
    ctx[0xd] = 1;

    g_party_window_button_callback_func(ctx, 0, 0);
    return true;
}

bool add_hero(uint32_t heroid) {
    if (!g_party_search_button_callback_func)
        return false;

    uint32_t wparam[4] = { 0 };
    wparam[2] = 0x7;
    wparam[1] = 0x1;

    uint32_t ctx[13] = { 0 };
    ctx[0xb] = 1;
    ctx[9] = heroid;

    g_party_search_button_callback_func(ctx, 2, wparam);
    return true;
}

bool kick_hero(uint32_t heroid) {
    if (!g_party_search_button_callback_func)
        return false;

    uint32_t wparam[4] = { 0 };
    wparam[2] = 0x7;
    wparam[1] = 0x6;

    uint32_t ctx[13] = { 0 };
    ctx[0xb] = 1;
    ctx[ctx[0xb] + 8] = heroid;

    g_party_search_button_callback_func(ctx, 0, wparam);
    return true;
}

bool kick_all_heroes() {
    return kick_hero(0x26);
}

bool add_henchman(uint32_t agent_id) {
    if (!g_party_search_button_callback_func)
        return false;

    uint32_t wparam[4] = { 0 };
    wparam[2] = 0x7;
    wparam[1] = 0x2;

    uint32_t ctx[13] = { 0 };
    ctx[0xb] = 2;
    ctx[10] = agent_id;

    g_party_search_button_callback_func(ctx, 0, wparam);
    return true;
}

bool kick_henchman(uint32_t agent_id) {
    if (!g_party_search_button_callback_func)
        return false;

    uint32_t wparam[4] = { 0 };
    wparam[2] = 0x7;
    wparam[1] = 0x6;

    uint32_t ctx[13] = { 0 };
    ctx[0xb] = 2;
    ctx[ctx[0xb] + 8] = agent_id;

    g_party_search_button_callback_func(ctx, 0, wparam);
    return true;
}

static bool kick_player_internal(const wchar_t* player_name) {
    if (!(player_name && player_name[0]))
        return false;
    wchar_t buf[32];
    int len = swprintf(buf, 32, L"kick %s", player_name);
    if (len < 0)
        return false;
    chat::SendChat('/', buf);
    return true;
}

bool kick_player(uint32_t player_id) {
    auto player = player::GetPlayerByID(player_id);
    if (!(player && player->name))
        return false;
    return kick_player_internal(player->name);
}

static bool invite_player_internal(const wchar_t* player_name) {
    if (!(player_name && player_name[0]))
        return false;
    wchar_t buf[32];
    int len = swprintf(buf, 32, L"invite %s", player_name);
    if (len < 0)
        return false;
    chat::SendChat('/', buf);
    return true;
}

bool invite_player(uint32_t player_id) {
    auto player = player::GetPlayerByID(player_id);
    if (!(player && player->name))
        return false;
    return invite_player_internal(player->name);
}

bool invite_player(const wchar_t* player_name) {
    return invite_player_internal(player_name);
}

bool flag_hero(uint32_t hero_index, GamePos pos) {
    return flag_hero_agent(agent::GetHeroAgentID(hero_index), pos);
}

bool flag_hero_agent(AgentID agent_id, GamePos pos) {
    if (!g_flag_hero_agent_func)
        return false;
    if (agent_id == 0) return false;
    if (agent_id == agent::GetControlledCharacterId()) return false;
    g_flag_hero_agent_func(agent_id, &pos);
    return true;
}

bool unflag_hero(uint32_t hero_index) {
    return flag_hero(hero_index, GamePos(HUGE_VALF, HUGE_VALF, 0));
}

bool flag_all(GamePos pos) {
    return g_flag_all_func ? g_flag_all_func(&pos), true : false;
}

bool unflag_all() {
    return flag_all(GamePos(HUGE_VALF, HUGE_VALF, 0));
}

bool set_hero_behavior(uint32_t agent_id, Constants::HeroBehavior behavior) {
    auto w = Context::GetWorldContext();
    if (!(w && g_set_hero_behavior_func && w->hero_flags.size()))
        return false;
    auto& flags = w->hero_flags;
    for (auto& flag : flags) {
        if (flag.agent_id == agent_id) {
            if (flag.hero_behavior != behavior)
                g_set_hero_behavior_func(agent_id, behavior);
            return true;
        }
    }
    return false;
}

bool set_hero_skill_ai_enabled(uint32_t hero_agent_id, uint32_t skill_slot, bool enabled) {
    if (!g_command_hot_key_disable_ai_func || !hero_agent_id || skill_slot < 1 || skill_slot > 8)
        return false;

    skillbar::SkillbarArray* skillbars = Context::GetSkillbarArray();
    if (!skillbars)
        return false;

    const uint32_t zero_based_slot = skill_slot - 1;
    const uint32_t disabled_bit = 1u << zero_based_slot;
    Context::Skillbar* hero_skillbar = nullptr;
    for (Context::Skillbar& skillbar : *skillbars) {
        if (skillbar.agent_id == hero_agent_id) {
            hero_skillbar = &skillbar;
            break;
        }
    }
    if (!hero_skillbar)
        return false;

    const bool is_disabled = (hero_skillbar->disabled & disabled_bit) != 0;
    if (is_disabled == !enabled)
        return true;

    game_thread::Enqueue([hero_agent_id, zero_based_slot] {
        g_command_hot_key_disable_ai_func(hero_agent_id, zero_based_slot);
    });
    return true;
}

bool set_pet_behavior(Constants::HeroBehavior behavior, uint32_t lock_target_id) {
    auto w = Context::GetWorldContext();
    if (!(w && g_set_hero_behavior_func && g_lock_pet_target_func && w->pets.size()))
        return false;

    const auto pet_info = get_pet_info();
    if (!pet_info)
        return false;
    uint32_t target_agent_id = 0;
    if (behavior == Constants::HeroBehavior::Fight) {
        const auto target = static_cast<agent::AgentLiving*>(
            lock_target_id ? agent::GetAgentByID(lock_target_id) : agent::GetTarget());
        if (!(target && target->GetIsLivingType() &&
              target->allegiance == Constants::Allegiance::Enemy))
            return false;
        target_agent_id = target->agent_id;
    }
    if (pet_info->locked_target_id != target_agent_id)
        g_lock_pet_target_func(pet_info->agent_id, target_agent_id);
    if (pet_info->behavior != behavior)
        g_set_hero_behavior_func(pet_info->agent_id, behavior);
    return true;
}

Context::PetInfo* get_pet_info(uint32_t owner_agent_id) {
    auto w = Context::GetWorldContext();
    if (!(w && w->pets.size()))
        return nullptr;
    if (owner_agent_id == 0)
        owner_agent_id = agent::GetControlledCharacterId();
    for (auto& pet : w->pets) {
        if (pet.owner_agent_id == owner_agent_id)
            return &pet;
    }
    return nullptr;
}

uint32_t get_hero_agent_id(uint32_t hero_index) {
    if (hero_index == 0)
        return agent::GetControlledCharacterId();
    hero_index--;
    Context::PartyInfo* party = get_party_info();
    if (!party)
        return 0;
    Context::HeroPartyMemberArray& heroes = party->heroes;
    return heroes.valid() && hero_index < heroes.size() ? heroes[hero_index].agent_id : 0;
}

uint32_t get_agent_hero_id(AgentID agent_id) {
    if (agent_id == 0)
        return 0;
    Context::PartyInfo* party = get_party_info();
    if (!party)
        return 0;
    Context::HeroPartyMemberArray& heroes = party->heroes;
    for (size_t i = 0; i < heroes.size(); i++) {
        auto& hero = heroes[i];
        if (hero.agent_id == agent_id)
            return static_cast<uint32_t>(i + 1);
    }
    return 0;
}

Context::HeroInfo* get_hero_info(uint32_t hero_id) {
    const auto w = Context::GetWorldContext();
    if (!(w && w->hero_info.size())) {
        return nullptr;
    }
    for (auto& a : w->hero_info) {
        if (a.hero_id == hero_id) {
            return &a;
        }
    }
    return nullptr;
}

bool search_party(uint32_t search_type, const wchar_t* advertisement) {
    if (!g_party_search_seek_func)
        return false;
    g_party_search_seek_func(search_type, advertisement ? advertisement : L"", 0);
    return true;
}

bool search_party_cancel() {
    if (!g_party_search_button_callback_func)
        return false;
    uint32_t wparam[4] = { 0 };
    wparam[2] = 0x8;
    uint32_t ctx[13] = { 0 };
    g_party_search_button_callback_func(ctx, 0, wparam);
    return true;
}

bool search_party_reply(bool accept) {
    if (!g_party_search_button_callback_func)
        return false;

    uint32_t wparam[4] = { 0 };
    wparam[2] = 0x6;
    wparam[1] = 0x3;

    uint32_t ctx[13] = { 0 };
    ctx[0xb] = 0;
    ctx[8] = accept;

    g_party_search_button_callback_func(ctx, 0, wparam);
    return true;
}

}  // namespace GW::party
