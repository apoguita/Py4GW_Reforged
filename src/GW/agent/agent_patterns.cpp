#include "base/error_handling.h"

#include "base/CrashHandler.h"
#include "base/patterns.h"
#include "GW/agent/agent.h"

namespace GW::Context {
extern uintptr_t g_agent_array_addr;
extern uintptr_t g_player_agent_id_addr;
}

namespace GW::agent {

using SendDialogFn = void(__cdecl*)(uint32_t dialog_id);
using ChangeTargetFn = void(__cdecl*)(uint32_t agent_id, uint32_t auto_target_id);
using CallTargetFn = void(__cdecl*)(Constants::CallTargetType type, uint32_t agent_id);
using MoveToFn = void(__cdecl*)(float* pos);
using DoWorldActionFn = void(__cdecl*)(Constants::WorldActionId action_id, uint32_t agent_id, bool suppress_call_target);

extern SendDialogFn g_send_agent_dialog_func;
extern SendDialogFn g_send_gadget_dialog_func;
extern ChangeTargetFn g_change_target_func;
extern CallTargetFn g_call_target_func;
extern MoveToFn g_move_to_func;
extern DoWorldActionFn g_do_world_action_func;

bool ResolveChangeTargetFunction() {
    CrashContextScope context("startup", "agent", "resolve_change_target");
    return PY4GW::Patterns::Resolve("agent.change_target_func", &g_change_target_func);
}

bool ResolveAgentArrayAddress() {
    CrashContextScope context("startup", "agent", "resolve_agent_array");
    return PY4GW::Patterns::Resolve("agent.agent_array_addr", &Context::g_agent_array_addr);
}

bool ResolvePlayerAgentIdAddress() {
    CrashContextScope context("startup", "agent", "resolve_player_agent_id");
    return PY4GW::Patterns::Resolve("agent.player_agent_id_addr", &Context::g_player_agent_id_addr);
}

bool ResolveSendAgentDialogFunction() {
    CrashContextScope context("startup", "agent", "resolve_send_agent_dialog");
    return PY4GW::Patterns::Resolve("agent.send_agent_dialog_func", &g_send_agent_dialog_func);
}

bool ResolveSendGadgetDialogFunction() {
    CrashContextScope context("startup", "agent", "resolve_send_gadget_dialog");
    return PY4GW::Patterns::Resolve("agent.send_gadget_dialog_func", &g_send_gadget_dialog_func);
}

bool ResolveMoveToFunction() {
    CrashContextScope context("startup", "agent", "resolve_move_to");
    return PY4GW::Patterns::Resolve("agent.move_to_func", &g_move_to_func);
}

bool ResolveDoWorldActionFunction() {
    CrashContextScope context("startup", "agent", "resolve_do_world_action");
    return PY4GW::Patterns::Resolve("agent.do_world_action_func", &g_do_world_action_func);
}

bool ResolveCallTargetFunction() {
    CrashContextScope context("startup", "agent", "resolve_call_target");
    return PY4GW::Patterns::Resolve("agent.call_target_func", &g_call_target_func);
}

}  // namespace GW::agent
