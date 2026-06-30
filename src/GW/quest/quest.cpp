#include "base/error_handling.h"

#include "GW/quest/quest.h"

#include "base/CrashHandler.h"
#include "base/hooker.h"
#include "base/logger.h"
#include "base/scanner.h"
#include "GW/ui/ui.h"

#include <atomic>

namespace GW::quest {

using RequestQuestInfoFn = void(__cdecl*)(uint32_t identifier);
using RequestQuestDataFn = void(__cdecl*)(uint32_t identifier, bool update_markers);
using DoActionFn = void(__cdecl*)(uint32_t identifier);

bool ResolveRequestQuestFunctions();
bool ResolveSetActiveQuestAndAbandon();

bool Init();
void EnableHooks();
void DisableHooks();
void Exit();

RequestQuestInfoFn g_request_quest_info_func = nullptr;
RequestQuestDataFn g_request_quest_data_func = nullptr;
uintptr_t g_request_quest_data_callsite = 0;
DoActionFn g_set_active_quest_func = nullptr;
DoActionFn g_set_active_quest_ret = nullptr;
DoActionFn g_abandon_quest_func = nullptr;
DoActionFn g_abandon_quest_ret = nullptr;
PY4GW::HookEntry g_set_active_quest_hook_entry;
PY4GW::HookEntry g_abandon_quest_hook_entry;
std::atomic<bool> g_initialized = false;

namespace {

void OnSetActiveQuest(uint32_t quest_id) {
    ui::SendUIMessage(ui::UIMessage::kSendSetActiveQuest, reinterpret_cast<void*>(static_cast<uintptr_t>(quest_id)));
}

void OnSetActiveQuest_UIMessage(PY4GW::HookStatus* status, ui::UIMessage message_id, void* wparam, void*) {
    if (!status->blocked) {
        g_set_active_quest_ret(static_cast<uint32_t>(reinterpret_cast<uintptr_t>(wparam)));
    }
}

void OnAbandonQuest(uint32_t quest_id) {
    ui::SendUIMessage(ui::UIMessage::kSendAbandonQuest, reinterpret_cast<void*>(static_cast<uintptr_t>(quest_id)));
}

void OnAbandonQuest_UIMessage(PY4GW::HookStatus* status, ui::UIMessage message_id, void* wparam, void*) {
    if (!status->blocked) {
        g_abandon_quest_ret(static_cast<uint32_t>(reinterpret_cast<uintptr_t>(wparam)));
    }
}

}  // namespace

bool Init() {
    CrashContextScope context("startup", "quest", "init");
    return ResolveRequestQuestFunctions() &&
        ResolveSetActiveQuestAndAbandon();
}

void EnableHooks() {
    if (g_abandon_quest_func) {
        PY4GW::HookBase::CreateHook(
            reinterpret_cast<void**>(&g_abandon_quest_func),
            reinterpret_cast<void*>(&OnAbandonQuest),
            reinterpret_cast<void**>(&g_abandon_quest_ret));
        PY4GW::HookBase::EnableHooks(reinterpret_cast<void*>(g_abandon_quest_func));
        ui::RegisterUIMessageCallback(&g_abandon_quest_hook_entry, ui::UIMessage::kSendAbandonQuest, OnAbandonQuest_UIMessage, 0x1);
    }
    if (g_set_active_quest_func) {
        PY4GW::HookBase::CreateHook(
            reinterpret_cast<void**>(&g_set_active_quest_func),
            reinterpret_cast<void*>(&OnSetActiveQuest),
            reinterpret_cast<void**>(&g_set_active_quest_ret));
        PY4GW::HookBase::EnableHooks(reinterpret_cast<void*>(g_set_active_quest_func));
        ui::RegisterUIMessageCallback(&g_set_active_quest_hook_entry, ui::UIMessage::kSendSetActiveQuest, OnSetActiveQuest_UIMessage, 0x1);
    }
}

void DisableHooks() {
    if (g_abandon_quest_func) {
        PY4GW::HookBase::DisableHooks(reinterpret_cast<void*>(g_abandon_quest_func));
    }
    if (g_set_active_quest_func) {
        PY4GW::HookBase::DisableHooks(reinterpret_cast<void*>(g_set_active_quest_func));
    }
}

void Exit() {
    CrashContextScope context("shutdown", "quest", "exit");
    if (g_abandon_quest_func) {
        PY4GW::HookBase::RemoveHook(reinterpret_cast<void*>(g_abandon_quest_func));
    }
    if (g_set_active_quest_func) {
        PY4GW::HookBase::RemoveHook(reinterpret_cast<void*>(g_set_active_quest_func));
    }
    g_request_quest_info_func = nullptr;
    g_request_quest_data_func = nullptr;
    g_request_quest_data_callsite = 0;
    g_set_active_quest_func = nullptr;
    g_set_active_quest_ret = nullptr;
    g_abandon_quest_func = nullptr;
    g_abandon_quest_ret = nullptr;
}

bool Initialize() {
    CrashContextScope context("startup", "quest", "initialize");
    if (g_initialized) {
        return true;
    }

    PY4GW_ASSERT(PY4GW::Scanner::Initialize());
    PY4GW_ASSERT(PY4GW::Patterns::Initialize());

    if (!Init()) {
        Exit();
        return false;
    }

    EnableHooks();
    g_initialized = true;
    return true;
}

void Shutdown() {
    CrashContextScope context("shutdown", "quest", "shutdown");
    if (!g_initialized) {
        return;
    }

    DisableHooks();
    Exit();
    g_initialized = false;
}

}  // namespace GW::quest
