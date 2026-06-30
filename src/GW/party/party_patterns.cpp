#include "base/error_handling.h"

#include "base/CrashHandler.h"
#include "base/patterns.h"

#include "GW/party/party.h"
#include "GW/ui/ui.h"

namespace GW::party {

using PartySearchSeekFn = void(__cdecl*)(uint32_t search_type, const wchar_t* advertisement, uint32_t unk);
using PartySearchButtonCallbackFn = void(__fastcall*)(void* context, uint32_t edx, uint32_t* wparam);
using DoActionFn = void(__cdecl*)(uint32_t identifier);
using FlagHeroAgentFn = void(__cdecl*)(uint32_t agent_id, GW::GamePos* pos);
using FlagAllFn = void(__cdecl*)(GW::GamePos* pos);
using SetHeroBehaviorFn = void(__cdecl*)(uint32_t agent_id, Constants::HeroBehavior behavior);
using LockPetTargetFn = bool(__cdecl*)(uint32_t pet_agent_id, uint32_t target_id);
using CommandHotKeyDisableAiFn = void(__cdecl*)(uint32_t hero_agent_id, uint32_t zero_based_skill_slot);

extern ui::UIInteractionCallback g_tick_button_ui_callback;
extern ui::UIInteractionCallback g_party_player_member_ui_callback;
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

bool resolve_tick_button_ui_callback() {
    CrashContextScope context("startup", "party", "resolve_tick_button_ui_callback");
    return PY4GW::Patterns::Resolve("party.tick_button_ui_callback_func", &g_tick_button_ui_callback);
}

bool resolve_set_difficulty_func() {
    CrashContextScope context("startup", "party", "resolve_set_difficulty_func");
    return PY4GW::Patterns::Resolve("party.set_difficulty_func", &g_set_difficulty_func);
}

bool resolve_party_search_seek_func() {
    CrashContextScope context("startup", "party", "resolve_party_search_seek_func");
    return PY4GW::Patterns::Resolve("party.party_search_seek_func", &g_party_search_seek_func);
}

bool resolve_party_search_button_callback_func() {
    CrashContextScope context("startup", "party", "resolve_party_search_button_callback");
    return PY4GW::Patterns::Resolve("party.party_search_button_callback_func", &g_party_search_button_callback_func);
}

bool resolve_party_window_button_callback_func() {
    CrashContextScope context("startup", "party", "resolve_party_window_button_callback");
    return PY4GW::Patterns::Resolve("party.party_window_button_callback_func", &g_party_window_button_callback_func);
}

bool resolve_party_player_member_ui_callback() {
    CrashContextScope context("startup", "party", "resolve_party_player_member_ui_callback");
    return PY4GW::Patterns::Resolve("party.party_player_member_ui_callback_func", &g_party_player_member_ui_callback);
}

bool resolve_set_ready_status_func() {
    CrashContextScope context("startup", "party", "resolve_set_ready_status_func");
    return PY4GW::Patterns::Resolve("party.set_ready_status_func", &g_set_ready_status_func);
}

bool resolve_flag_functions() {
    CrashContextScope context("startup", "party", "resolve_flag_functions");
    return PY4GW::Patterns::Resolve("party.flag_hero_agent_func", &g_flag_hero_agent_func) &&
        PY4GW::Patterns::Resolve("party.flag_all_func", &g_flag_all_func);
}

bool resolve_set_hero_behavior_funcs() {
    CrashContextScope context("startup", "party", "resolve_set_hero_behavior_funcs");
    return PY4GW::Patterns::Resolve("party.lock_pet_target_func", &g_lock_pet_target_func) &&
        PY4GW::Patterns::Resolve("party.set_hero_behavior_func", &g_set_hero_behavior_func);
}

bool resolve_command_hotkey_disable_ai_func() {
    CrashContextScope context("startup", "party", "resolve_command_hotkey_disable_ai");
    return PY4GW::Patterns::Resolve("party.command_hotkey_disable_ai_func", &g_command_hot_key_disable_ai_func);
}

}  // namespace GW::party
