#include "base/error_handling.h"

#include "GW/agent/agent.h"

#include "base/CrashHandler.h"
#include "base/hooker.h"
#include "base/hook_types.h"
#include "base/logger.h"
#include "base/patterns.h"
#include "base/scanner.h"

#include "GW/ui/ui.h"

#include <array>
#include <atomic>
#include <string>

namespace GW::agent {

using SendDialogFn = void(__cdecl*)(uint32_t dialog_id);
using ChangeTargetFn = void(__cdecl*)(uint32_t agent_id, uint32_t auto_target_id);
using CallTargetFn = void(__cdecl*)(Constants::CallTargetType type, uint32_t agent_id);
using MoveToFn = void(__cdecl*)(float* pos);
using DoWorldActionFn = void(__cdecl*)(Constants::WorldActionId action_id, uint32_t agent_id, bool suppress_call_target);

bool ResolveChangeTargetFunction();
bool ResolveAgentArrayAddress();
bool ResolvePlayerAgentIdAddress();
bool ResolveSendAgentDialogFunction();
bool ResolveSendGadgetDialogFunction();
bool ResolveMoveToFunction();
bool ResolveDoWorldActionFunction();
bool ResolveCallTargetFunction();

bool Init();
void EnableHooks();
void DisableHooks();
void Exit();

void __cdecl OnSendAgentDialog(uint32_t dialog_id);
void __cdecl OnSendGadgetDialog(uint32_t dialog_id);
void __cdecl OnChangeTarget(uint32_t agent_id, uint32_t auto_target_id);
void __cdecl OnCallTarget(Constants::CallTargetType type, uint32_t target_id);
void __cdecl OnDoWorldAction(Constants::WorldActionId action_id, uint32_t agent_id, bool suppress_call_target);
void OnUIMessage(PY4GW::HookStatus* status, ui::UIMessage message_id, void* wparam, void* lparam);

SendDialogFn g_send_agent_dialog_func = nullptr;
SendDialogFn g_send_agent_dialog_original = nullptr;
SendDialogFn g_send_gadget_dialog_func = nullptr;
SendDialogFn g_send_gadget_dialog_original = nullptr;
ChangeTargetFn g_change_target_func = nullptr;
ChangeTargetFn g_change_target_original = nullptr;
CallTargetFn g_call_target_func = nullptr;
CallTargetFn g_call_target_original = nullptr;
MoveToFn g_move_to_func = nullptr;
DoWorldActionFn g_do_world_action_func = nullptr;
DoWorldActionFn g_do_world_action_original = nullptr;
uint32_t g_dialog_agent_id = 0;
uint32_t g_current_target_id = 0;
PY4GW::HookEntry g_ui_message_entry;

const std::array<ui::UIMessage, 13> g_ui_messages_to_hook = {
    ui::UIMessage::kDialogBody,
    ui::UIMessage::kSendAgentDialog,
    ui::UIMessage::kSendGadgetDialog,
    ui::UIMessage::kSendMoveToWorldPoint,
    ui::UIMessage::kSendCallTarget,
    ui::UIMessage::kSendInteractGadget,
    ui::UIMessage::kSendInteractItem,
    ui::UIMessage::kSendInteractNPC,
    ui::UIMessage::kSendInteractPlayer,
    ui::UIMessage::kSendInteractEnemy,
    ui::UIMessage::kSendChangeTarget,
    ui::UIMessage::kChangeTarget,
    ui::UIMessage::kSendWorldAction
};
std::atomic<bool> g_initialized = false;

void __cdecl OnSendAgentDialog(uint32_t dialog_id) {
    PY4GW::HookBase::EnterHook();
    ui::SendUIMessage(ui::UIMessage::kSendAgentDialog, reinterpret_cast<void*>(static_cast<uintptr_t>(dialog_id)));
    PY4GW::HookBase::LeaveHook();
}

void __cdecl OnSendGadgetDialog(uint32_t dialog_id) {
    PY4GW::HookBase::EnterHook();
    ui::SendUIMessage(ui::UIMessage::kSendGadgetDialog, reinterpret_cast<void*>(static_cast<uintptr_t>(dialog_id)));
    PY4GW::HookBase::LeaveHook();
}

void __cdecl OnChangeTarget(uint32_t agent_id, uint32_t auto_target_id) {
    PY4GW::HookBase::EnterHook();
    ui::packet::kSendChangeTarget packet{ agent_id, auto_target_id };
    ui::SendUIMessage(ui::UIMessage::kSendChangeTarget, &packet);
    PY4GW::HookBase::LeaveHook();
}

void __cdecl OnCallTarget(Constants::CallTargetType type, uint32_t target_id) {
    PY4GW::HookBase::EnterHook();
    ui::packet::kSendCallTarget packet{ type, target_id };
    ui::SendUIMessage(ui::UIMessage::kSendCallTarget, &packet);
    PY4GW::HookBase::LeaveHook();
}

void __cdecl OnDoWorldAction(Constants::WorldActionId action_id, uint32_t agent_id, bool suppress_call_target) {
    PY4GW::HookBase::EnterHook();
    ui::packet::kSendWorldAction packet{ action_id, agent_id, suppress_call_target };
    ui::SendUIMessage(ui::UIMessage::kSendWorldAction, &packet);
    PY4GW::HookBase::LeaveHook();
}

void OnUIMessage(PY4GW::HookStatus* status, ui::UIMessage message_id, void* wparam, void*) {
    if (status && status->blocked) {
        return;
    }

    switch (message_id) {
    case ui::UIMessage::kDialogBody: {
        const auto* packet = static_cast<Context::DialogBodyInfo*>(wparam);
        g_dialog_agent_id = packet ? packet->agent_id : 0;
        break;
    }
    case ui::UIMessage::kSendAgentDialog:
        if (g_send_agent_dialog_original) {
            g_send_agent_dialog_original(static_cast<uint32_t>(reinterpret_cast<uintptr_t>(wparam)));
        }
        break;
    case ui::UIMessage::kSendChangeTarget:
        if (g_change_target_original) {
            const auto* packet = static_cast<ui::packet::kSendChangeTarget*>(wparam);
            if (packet) {
                g_change_target_original(packet->target_id, packet->auto_target_id);
            }
        }
        break;
    case ui::UIMessage::kSendGadgetDialog:
        if (g_send_gadget_dialog_original) {
            g_send_gadget_dialog_original(static_cast<uint32_t>(reinterpret_cast<uintptr_t>(wparam)));
        }
        break;
    case ui::UIMessage::kChangeTarget: {
        const auto* msg = static_cast<Context::ChangeTargetUIMsg*>(wparam);
        g_current_target_id = msg ? msg->manual_target_id : 0;
        break;
    }
    case ui::UIMessage::kSendCallTarget:
        if (g_call_target_original) {
            const auto* packet = static_cast<ui::packet::kSendCallTarget*>(wparam);
            if (packet) {
                g_call_target_original(packet->call_type, packet->agent_id);
            }
        }
        break;
    case ui::UIMessage::kSendWorldAction:
        if (g_do_world_action_original) {
            const auto* packet = static_cast<ui::packet::kSendWorldAction*>(wparam);
            if (packet) {
                g_do_world_action_original(packet->action_id, packet->agent_id, packet->suppress_call_target);
            }
        }
        break;
    default:
        break;
    }
}

bool Init() {
    CrashContextScope context("startup", "agent", "init");
    if (!ResolveChangeTargetFunction() ||
        !ResolveAgentArrayAddress() ||
        !ResolvePlayerAgentIdAddress() ||
        !ResolveSendAgentDialogFunction() ||
        !ResolveSendGadgetDialogFunction() ||
        !ResolveMoveToFunction() ||
        !ResolveDoWorldActionFunction() ||
        !ResolveCallTargetFunction()) {
        return false;
    }

    const bool do_world_action_ok = Logger::AssertHook(
        "DoWorldAction_Func",
        PY4GW::HookBase::CreateHook(
            reinterpret_cast<void**>(&g_do_world_action_func),
            reinterpret_cast<void*>(&OnDoWorldAction),
            reinterpret_cast<void**>(&g_do_world_action_original)),
        "agent");
    const bool call_target_ok = Logger::AssertHook(
        "CallTarget_Func",
        PY4GW::HookBase::CreateHook(
            reinterpret_cast<void**>(&g_call_target_func),
            reinterpret_cast<void*>(&OnCallTarget),
            reinterpret_cast<void**>(&g_call_target_original)),
        "agent");
    const bool send_agent_dialog_ok = Logger::AssertHook(
        "SendAgentDialog_Func",
        PY4GW::HookBase::CreateHook(
            reinterpret_cast<void**>(&g_send_agent_dialog_func),
            reinterpret_cast<void*>(&OnSendAgentDialog),
            reinterpret_cast<void**>(&g_send_agent_dialog_original)),
        "agent");
    const bool send_gadget_dialog_ok = Logger::AssertHook(
        "SendGadgetDialog_Func",
        PY4GW::HookBase::CreateHook(
            reinterpret_cast<void**>(&g_send_gadget_dialog_func),
            reinterpret_cast<void*>(&OnSendGadgetDialog),
            reinterpret_cast<void**>(&g_send_gadget_dialog_original)),
        "agent");
    const bool change_target_ok = Logger::AssertHook(
        "ChangeTarget_Func",
        PY4GW::HookBase::CreateHook(
            reinterpret_cast<void**>(&g_change_target_func),
            reinterpret_cast<void*>(&OnChangeTarget),
            reinterpret_cast<void**>(&g_change_target_original)),
        "agent");
    return do_world_action_ok && call_target_ok && send_agent_dialog_ok && send_gadget_dialog_ok && change_target_ok;
}

void EnableHooks() {
    CrashContextScope context("runtime", "agent", "enable_hooks");
    if (g_call_target_func) {
        PY4GW::HookBase::EnableHooks(reinterpret_cast<void*>(g_call_target_func));
    }
    if (g_do_world_action_func) {
        PY4GW::HookBase::EnableHooks(reinterpret_cast<void*>(g_do_world_action_func));
    }
    if (g_send_agent_dialog_func) {
        PY4GW::HookBase::EnableHooks(reinterpret_cast<void*>(g_send_agent_dialog_func));
    }
    if (g_send_gadget_dialog_func) {
        PY4GW::HookBase::EnableHooks(reinterpret_cast<void*>(g_send_gadget_dialog_func));
    }
    for (const auto ui_message : g_ui_messages_to_hook) {
        ui::RegisterUIMessageCallback(&g_ui_message_entry, ui_message, &OnUIMessage, 0x1);
    }
}

void DisableHooks() {
    CrashContextScope context("shutdown", "agent", "disable_hooks");
    if (g_call_target_func) {
        PY4GW::HookBase::DisableHooks(reinterpret_cast<void*>(g_call_target_func));
    }
    if (g_do_world_action_func) {
        PY4GW::HookBase::DisableHooks(reinterpret_cast<void*>(g_do_world_action_func));
    }
    if (g_send_agent_dialog_func) {
        PY4GW::HookBase::DisableHooks(reinterpret_cast<void*>(g_send_agent_dialog_func));
    }
    if (g_send_gadget_dialog_func) {
        PY4GW::HookBase::DisableHooks(reinterpret_cast<void*>(g_send_gadget_dialog_func));
    }
    ui::RemoveUIMessageCallback(&g_ui_message_entry);
}

void Exit() {
    CrashContextScope context("shutdown", "agent", "exit");
    if (g_call_target_func) {
        PY4GW::HookBase::RemoveHook(reinterpret_cast<void*>(g_call_target_func));
    }
    if (g_do_world_action_func) {
        PY4GW::HookBase::RemoveHook(reinterpret_cast<void*>(g_do_world_action_func));
    }
    if (g_send_agent_dialog_func) {
        PY4GW::HookBase::RemoveHook(reinterpret_cast<void*>(g_send_agent_dialog_func));
    }
    if (g_send_gadget_dialog_func) {
        PY4GW::HookBase::RemoveHook(reinterpret_cast<void*>(g_send_gadget_dialog_func));
    }

    g_send_agent_dialog_func = nullptr;
    g_send_agent_dialog_original = nullptr;
    g_send_gadget_dialog_func = nullptr;
    g_send_gadget_dialog_original = nullptr;
    g_change_target_func = nullptr;
    g_change_target_original = nullptr;
    g_call_target_func = nullptr;
    g_call_target_original = nullptr;
    g_move_to_func = nullptr;
    g_do_world_action_func = nullptr;
    g_do_world_action_original = nullptr;
    g_dialog_agent_id = 0;
    g_current_target_id = 0;
}

bool Initialize() {
    CrashContextScope context("startup", "agent", "initialize");
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
    CrashContextScope context("shutdown", "agent", "shutdown");
    if (!g_initialized) {
        return;
    }

    DisableHooks();
    Exit();
    PY4GW::HookBase::Deinitialize();
    g_initialized = false;
}

}  // namespace GW::agent
