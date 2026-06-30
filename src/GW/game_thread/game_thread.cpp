#include "base/error_handling.h"

#include "GW/game_thread/game_thread.h"

#include "base/CrashHandler.h"
#include "base/hooker.h"
#include "base/logger.h"
#include "base/patterns.h"
#include "base/scanner.h"

namespace GW::game_thread {

using LeaveGameThreadFn = void(__cdecl*)(void*);

struct CallbackEntry {
    int altitude = 0;
    PY4GW::HookEntry* entry = nullptr;
    GameThreadCallback callback;
};

bool ResolveLeaveGameThreadTarget();
bool Init();
void EnableHooks();
void DisableHooks();
void Exit();
void CallFunctions();
void __cdecl OnLeaveGameThread(void* unk);

CRITICAL_SECTION g_mutex;
bool g_mutex_initialized = false;
LeaveGameThreadFn g_leave_game_thread_func = nullptr;
LeaveGameThreadFn g_leave_game_thread_original = nullptr;
std::atomic<bool> g_initialized = false;
std::atomic<bool> g_in_game_thread = false;
std::vector<std::function<void()>> g_singleshot_callbacks;
std::vector<CallbackEntry> g_callbacks;

void CallFunctions() {
    if (!g_initialized) {
        return;
    }

    ::EnterCriticalSection(&g_mutex);
    g_in_game_thread = true;

    if (!g_singleshot_callbacks.empty()) {
        for (const auto& callback : g_singleshot_callbacks) {
            callback();
        }
        g_singleshot_callbacks.clear();
    }

    PY4GW::HookStatus status = {};
    for (auto& entry : g_callbacks) {
        entry.callback(&status);
        ++status.altitude;
    }

    g_in_game_thread = false;
    ::LeaveCriticalSection(&g_mutex);
}

void __cdecl OnLeaveGameThread(void* unk) {
    PY4GW::HookBase::EnterHook();
    CallFunctions();
    g_leave_game_thread_original(unk);
    PY4GW::HookBase::LeaveHook();
}

bool Init() {
    CrashContextScope context("startup", "game_thread", "init");
    if (!ResolveLeaveGameThreadTarget()) {
        return false;
    }

    const int status = PY4GW::HookBase::CreateHook(
        reinterpret_cast<void**>(&g_leave_game_thread_func),
        reinterpret_cast<void*>(&OnLeaveGameThread),
        reinterpret_cast<void**>(&g_leave_game_thread_original));
    return Logger::AssertHook("LeaveGameThread_Func", status, "game_thread");
}

void EnableHooks() {
    CrashContextScope context("runtime", "game_thread", "enable_hooks");
    if (!g_initialized || !g_leave_game_thread_func) {
        return;
    }

    ::EnterCriticalSection(&g_mutex);
    PY4GW::HookBase::EnableHooks(reinterpret_cast<void*>(g_leave_game_thread_func));
    ::LeaveCriticalSection(&g_mutex);
}

void DisableHooks() {
    CrashContextScope context("shutdown", "game_thread", "disable_hooks");
    if (!g_initialized || !g_leave_game_thread_func) {
        return;
    }

    ::EnterCriticalSection(&g_mutex);
    PY4GW::HookBase::DisableHooks(reinterpret_cast<void*>(g_leave_game_thread_func));
    ::LeaveCriticalSection(&g_mutex);
}

void Exit() {
    CrashContextScope context("shutdown", "game_thread", "exit");
    if (!g_initialized) {
        return;
    }

    ClearCalls();
    PY4GW::HookBase::RemoveHook(reinterpret_cast<void*>(g_leave_game_thread_func));

    if (g_mutex_initialized) {
        ::DeleteCriticalSection(&g_mutex);
        g_mutex_initialized = false;
    }

    g_leave_game_thread_func = nullptr;
    g_leave_game_thread_original = nullptr;
    g_in_game_thread = false;
}

bool Initialize() {
    CrashContextScope context("startup", "game_thread", "initialize");
    if (g_initialized) {
        return true;
    }

    PY4GW_ASSERT(PY4GW::Scanner::Initialize());
    PY4GW_ASSERT(PY4GW::Patterns::Initialize());

    ::InitializeCriticalSection(&g_mutex);
    g_mutex_initialized = true;

    PY4GW::HookBase::Initialize();
    if (!Init()) {
        Exit();
        PY4GW::HookBase::Deinitialize();
        return false;
    }

    g_initialized = true;
    EnableHooks();
    return true;
}

void Shutdown() {
    CrashContextScope context("shutdown", "game_thread", "shutdown");
    if (!g_initialized) {
        return;
    }

    DisableHooks();
    Exit();
    PY4GW::HookBase::Deinitialize();
    g_initialized = false;
}

}  // namespace GW::game_thread
