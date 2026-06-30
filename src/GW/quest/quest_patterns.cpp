#include "base/error_handling.h"

#include "base/CrashHandler.h"
#include "base/patterns.h"

#include "GW/quest/quest.h"

namespace GW::quest {

using RequestQuestInfoFn = void(__cdecl*)(uint32_t identifier);
using RequestQuestDataFn = void(__cdecl*)(uint32_t identifier, bool update_markers);
using DoActionFn = void(__cdecl*)(uint32_t identifier);

extern RequestQuestInfoFn g_request_quest_info_func;
extern RequestQuestDataFn g_request_quest_data_func;
extern uintptr_t g_request_quest_data_callsite;
extern DoActionFn g_set_active_quest_func;
extern DoActionFn g_abandon_quest_func;

bool ResolveRequestQuestFunctions() {
    CrashContextScope context("startup", "quest", "resolve_request_quest_functions");
    return PY4GW::Patterns::Resolve("quest.request_quest_data_callsite", &g_request_quest_data_callsite) &&
        PY4GW::Patterns::Resolve("quest.request_quest_data_func", &g_request_quest_data_func) &&
        PY4GW::Patterns::Resolve("quest.request_quest_info_func", &g_request_quest_info_func);
}

bool ResolveSetActiveQuestAndAbandon() {
    CrashContextScope context("startup", "quest", "resolve_set_active_quest_and_abandon");
    return PY4GW::Patterns::Resolve("quest.abandon_quest_func", &g_abandon_quest_func) &&
        PY4GW::Patterns::Resolve("quest.set_active_quest_func", &g_set_active_quest_func);
}

}  // namespace GW::quest
