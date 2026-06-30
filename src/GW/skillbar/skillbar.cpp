#include "base/error_handling.h"

#include "GW/skillbar/skillbar.h"

#include "base/CrashHandler.h"
#include "base/hooker.h"
#include "base/hook_types.h"
#include "base/logger.h"
#include "base/patterns.h"
#include "base/scanner.h"

#include "GW/context/context.h"
#include "GW/ui/ui.h"

#include <atomic>
#include <cstdio>
#include <cstring>
#include <unordered_map>

namespace GW::skillbar {

using UseSkillFn = void(__cdecl*)(uint32_t, uint32_t, uint32_t, uint32_t);
using LoadSkillsFn = void(__cdecl*)(uint32_t agent_id, uint32_t skill_ids_count, uint32_t* skill_ids);
using LoadAttributesFn = void(__cdecl*)(uint32_t agent_id, uint32_t attribute_count, uint32_t* attribute_ids, uint32_t* attribute_values);
using ChangeSecondaryFn = void(__cdecl*)(uint32_t agent_id, uint32_t profession);

bool ResolveSkillArray();
bool ResolveAttributeArray();
bool ResolveUseSkillFunction();
bool ResolveTemplatesFunctions();

bool Init();
void EnableHooks();
void DisableHooks();
void Exit();

void __cdecl OnUseSkill(uint32_t agent_id, uint32_t slot, uint32_t target, uint32_t call_target);
void OnLoadSkillbar(uint32_t agent_id, uint32_t skill_ids_count, uint32_t* skill_ids);
void OnLoadSkillbarUIMessage(PY4GW::HookStatus* status, ui::UIMessage message_id, void* wparam, void* lparam);

uint32_t g_attribute_array_count = 0x33;
UseSkillFn g_use_skill_func = nullptr;
UseSkillFn g_use_skill_original = nullptr;
LoadSkillsFn g_load_skills_func = nullptr;
LoadSkillsFn g_load_skills_original = nullptr;
LoadAttributesFn g_load_attributes_func = nullptr;
ChangeSecondaryFn g_change_secondary_func = nullptr;
std::unordered_map<PY4GW::HookEntry*, UseSkillCallback> g_use_skill_callbacks;
PY4GW::HookEntry g_load_skillbar_hook_entry;
std::atomic<bool> g_initialized = false;

void __cdecl OnUseSkill(uint32_t agent_id, uint32_t slot, uint32_t target, uint32_t call_target) {
    PY4GW::HookBase::EnterHook();
    PY4GW::HookStatus status;
    for (auto& it : g_use_skill_callbacks) {
        it.second(&status, agent_id, slot, target, call_target);
        ++status.altitude;
    }
    if (!status.blocked)
        g_use_skill_original(agent_id, slot, target, call_target);
    PY4GW::HookBase::LeaveHook();
}

void OnLoadSkillbar(uint32_t agent_id, uint32_t skill_ids_count, uint32_t* skill_ids) {
    PY4GW::HookBase::EnterHook();
    uint32_t skill_ids_buffer[8] = {};
    memcpy(skill_ids_buffer, skill_ids, skill_ids_count * sizeof(*skill_ids));
    ui::packet::kSendLoadSkillbar packet{
        agent_id,
        skill_ids_buffer
    };
    ui::SendUIMessage(ui::UIMessage::kSendLoadSkillbar, &packet);
    PY4GW::HookBase::LeaveHook();
}

void OnLoadSkillbarUIMessage(PY4GW::HookStatus* status, ui::UIMessage message_id, void* wparam, void*) {
    PY4GW_ASSERT(message_id == ui::UIMessage::kSendLoadSkillbar && wparam);
    if (status && status->blocked) {
        return;
    }
    if (g_load_skills_original) {
        auto* pack = static_cast<ui::packet::kSendLoadSkillbar*>(wparam);
        g_load_skills_original(pack->agent_id, 8, pack->skill_ids);
    }
}

const ProfessionState* GetAgentProfessionState(uint32_t agent_id) {
    const auto w = Context::GetWorldContext();
    if (!w) return nullptr;
    for (const auto& it : w->party_profession_states) {
        if (it.agent_id == agent_id)
            return &it;
    }
    return nullptr;
}

Constants::Profession GetSkillProfession(Constants::SkillID skill_id) {
    auto data = GetSkillConstantData(skill_id);
    return data ? static_cast<Constants::Profession>(data->profession) : Constants::Profession::None;
}

Constants::Profession GetAttributeProfession(Constants::Attribute attribute, bool* is_primary_attribute) {
    auto info = GetAttributeConstantData(attribute);
    if (!info)
        return Constants::Profession::None;
    if (is_primary_attribute) {
        switch (attribute) {
        case Constants::Attribute::FastCasting:
        case Constants::Attribute::SoulReaping:
        case Constants::Attribute::EnergyStorage:
        case Constants::Attribute::DivineFavor:
        case Constants::Attribute::Strength:
        case Constants::Attribute::Expertise:
        case Constants::Attribute::CriticalStrikes:
        case Constants::Attribute::SpawningPower:
        case Constants::Attribute::Leadership:
        case Constants::Attribute::Mysticism:
            *is_primary_attribute = true;
            break;
        default:
            *is_primary_attribute = false;
            break;
        }
    }
    return info->profession_id;
}

bool IsPrimaryAttributeRequired(const SkillTemplate& skill_template, const Constants::Profession profession) {
    if (profession == Constants::Profession::None)
        return false;
    bool is_primary_attribute = false;
    for (const auto& attribute : skill_template.attributes) {
        if (GetAttributeProfession(attribute.attribute, &is_primary_attribute) == profession
            && is_primary_attribute)
            return true;
    }
    return false;
}

bool IsProfessionRequired(const SkillTemplate& skill_template, const Constants::Profession profession) {
    if (profession == Constants::Profession::None)
        return false;
    for (size_t i = 0; i < _countof(skill_template.skills); i++) {
        if (GetSkillProfession(skill_template.skills[i]) == profession)
            return true;
    }
    for (size_t i = 0; i < _countof(skill_template.attributes); i++) {
        if (GetAttributeProfession(skill_template.attributes[i].attribute) == profession)
            return true;
    }
    return false;
}

bool Init() {
    CrashContextScope context("startup", "skillbar", "init");
    if (!ResolveSkillArray() ||
        !ResolveAttributeArray() ||
        !ResolveUseSkillFunction() ||
        !ResolveTemplatesFunctions()) {
        return false;
    }

    if (g_use_skill_func) {
        const int result = PY4GW::HookBase::CreateHook(
            reinterpret_cast<void**>(&g_use_skill_func),
            reinterpret_cast<void*>(&OnUseSkill),
            reinterpret_cast<void**>(&g_use_skill_original));
        Logger::AssertHook("UseSkill_Func", result, "skillbar");
    }

    if (g_load_skills_func) {
        const int result = PY4GW::HookBase::CreateHook(
            reinterpret_cast<void**>(&g_load_skills_func),
            reinterpret_cast<void*>(&OnLoadSkillbar),
            reinterpret_cast<void**>(&g_load_skills_original));
        Logger::AssertHook("LoadSkills_Func", result, "skillbar");
    }

    {
        char buf[128];
        snprintf(buf, sizeof(buf), "[SCAN] SkillArray = %p", static_cast<void*>(Context::GetSkillArray()));
        Logger::Instance().LogInfo(buf);
    }
    {
        char buf[128];
        snprintf(buf, sizeof(buf), "[SCAN] AttributeArray = %p", static_cast<void*>(Context::GetAttributeInfoArray()));
        Logger::Instance().LogInfo(buf);
    }
    {
        char buf[128];
        snprintf(buf, sizeof(buf), "[SCAN] ChangeSecondary_Func = %p", reinterpret_cast<void*>(g_change_secondary_func));
        Logger::Instance().LogInfo(buf);
    }
    {
        char buf[128];
        snprintf(buf, sizeof(buf), "[SCAN] LoadAttributes_Func = %p", reinterpret_cast<void*>(g_load_attributes_func));
        Logger::Instance().LogInfo(buf);
    }
    {
        char buf[128];
        snprintf(buf, sizeof(buf), "[SCAN] LoadSkills_Func = %p", reinterpret_cast<void*>(g_load_skills_func));
        Logger::Instance().LogInfo(buf);
    }

    return true;
}

void EnableHooks() {
    CrashContextScope context("runtime", "skillbar", "enable_hooks");
    if (g_use_skill_func) {
        PY4GW::HookBase::EnableHooks(reinterpret_cast<void*>(g_use_skill_func));
    }
    if (g_load_skills_func) {
        PY4GW::HookBase::EnableHooks(reinterpret_cast<void*>(g_load_skills_func));
    }
    ui::RegisterUIMessageCallback(&g_load_skillbar_hook_entry, ui::UIMessage::kSendLoadSkillbar, &OnLoadSkillbarUIMessage, 0x1);
}

void DisableHooks() {
    CrashContextScope context("shutdown", "skillbar", "disable_hooks");
    if (g_use_skill_func) {
        PY4GW::HookBase::DisableHooks(reinterpret_cast<void*>(g_use_skill_func));
    }
    if (g_load_skills_func) {
        PY4GW::HookBase::DisableHooks(reinterpret_cast<void*>(g_load_skills_func));
    }
    ui::RemoveUIMessageCallback(&g_load_skillbar_hook_entry);
}

void Exit() {
    CrashContextScope context("shutdown", "skillbar", "exit");
    if (g_use_skill_func) {
        PY4GW::HookBase::RemoveHook(reinterpret_cast<void*>(g_use_skill_func));
    }
    if (g_load_skills_func) {
        PY4GW::HookBase::RemoveHook(reinterpret_cast<void*>(g_load_skills_func));
    }
    ui::RemoveUIMessageCallback(&g_load_skillbar_hook_entry);

    g_use_skill_callbacks.clear();

    g_use_skill_func = nullptr;
    g_use_skill_original = nullptr;
    g_load_skills_func = nullptr;
    g_load_skills_original = nullptr;
    g_load_attributes_func = nullptr;
    g_change_secondary_func = nullptr;
}

bool Initialize() {
    CrashContextScope context("startup", "skillbar", "initialize");
    if (g_initialized) {
        return true;
    }

    PY4GW_ASSERT(PY4GW::Scanner::Initialize());
    PY4GW_ASSERT(PY4GW::Patterns::Initialize());

    PY4GW::HookBase::Initialize();
    if (!Init()) {
        Exit();
        PY4GW::HookBase::Deinitialize();
        return false;
    }

    EnableHooks();
    g_initialized = true;
    return true;
}

void Shutdown() {
    CrashContextScope context("shutdown", "skillbar", "shutdown");
    if (!g_initialized) {
        return;
    }

    DisableHooks();
    Exit();
    PY4GW::HookBase::Deinitialize();
    g_initialized = false;
}

}  // namespace GW::skillbar
