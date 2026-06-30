#include "base/error_handling.h"

#include "GW/player/player.h"

#include "base/CrashHandler.h"
#include "base/logger.h"
#include "base/patterns.h"
#include "base/scanner.h"

#include <atomic>

namespace GW::player {

using RemoveActiveTitleFn = void(__cdecl*)();
using SetActiveTitleFn = void(__cdecl*)(uint32_t identifier);
using DepositFactionFn = void(__cdecl*)(uint32_t always_0, uint32_t allegiance, uint32_t amount);

bool ResolveSetActiveTitle();
bool ResolveRemoveActiveTitle();
bool ResolveDepositFaction();
bool ResolveTitleData();

bool Init();
void EnableHooks();
void DisableHooks();
void Exit();

RemoveActiveTitleFn g_remove_active_title_func = nullptr;
SetActiveTitleFn g_set_active_title_func = nullptr;
DepositFactionFn g_deposit_faction_func = nullptr;
std::atomic<bool> g_initialized = false;

bool Init() {
    CrashContextScope context("startup", "player", "init");
    return ResolveSetActiveTitle() &&
        ResolveRemoveActiveTitle() &&
        ResolveDepositFaction() &&
        ResolveTitleData();
}

void EnableHooks() {
}

void DisableHooks() {
}

void Exit() {
    CrashContextScope context("shutdown", "player", "exit");
    g_remove_active_title_func = nullptr;
    g_set_active_title_func = nullptr;
    g_deposit_faction_func = nullptr;
}

bool Initialize() {
    CrashContextScope context("startup", "player", "initialize");
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
    CrashContextScope context("shutdown", "player", "shutdown");
    if (!g_initialized) {
        return;
    }

    DisableHooks();
    Exit();
    g_initialized = false;
}

}  // namespace GW::player
