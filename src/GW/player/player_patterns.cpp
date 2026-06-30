#include "base/error_handling.h"

#include "base/CrashHandler.h"
#include "base/patterns.h"

#include "GW/player/player.h"

namespace GW::Context {
extern TitleClientData* g_title_data_addr;
}

namespace GW::player {

using RemoveActiveTitleFn = void(__cdecl*)();
using SetActiveTitleFn = void(__cdecl*)(uint32_t identifier);
using DepositFactionFn = void(__cdecl*)(uint32_t always_0, uint32_t allegiance, uint32_t amount);

extern RemoveActiveTitleFn g_remove_active_title_func;
extern SetActiveTitleFn g_set_active_title_func;
extern DepositFactionFn g_deposit_faction_func;

bool ResolveSetActiveTitle() {
    CrashContextScope context("startup", "player", "resolve_set_active_title");
    return PY4GW::Patterns::Resolve("player.set_active_title_func", &g_set_active_title_func);
}

bool ResolveRemoveActiveTitle() {
    CrashContextScope context("startup", "player", "resolve_remove_active_title");
    return PY4GW::Patterns::Resolve("player.remove_active_title_func", &g_remove_active_title_func);
}

bool ResolveDepositFaction() {
    CrashContextScope context("startup", "player", "resolve_deposit_faction");
    return PY4GW::Patterns::Resolve("player.deposit_faction_func", &g_deposit_faction_func);
}

bool ResolveTitleData() {
    CrashContextScope context("startup", "player", "resolve_title_data");
    return PY4GW::Patterns::Resolve("player.title_data_addr", &Context::g_title_data_addr);
}

}  // namespace GW::player
