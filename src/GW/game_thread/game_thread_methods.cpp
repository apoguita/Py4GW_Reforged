#include "base/error_handling.h"

#include "GW/game_thread/game_thread.h"

#include <algorithm>

namespace GW::game_thread {

struct CallbackEntry {
    int altitude = 0;
    PY4GW::HookEntry* entry = nullptr;
    GameThreadCallback callback;
};

extern CRITICAL_SECTION g_mutex;
extern bool g_mutex_initialized;
extern std::atomic<bool> g_initialized;
extern std::atomic<bool> g_in_game_thread;
extern std::vector<std::function<void()>> g_singleshot_callbacks;
extern std::vector<CallbackEntry> g_callbacks;

void ClearCalls() {
    if (!g_initialized || !g_mutex_initialized) {
        return;
    }

    ::EnterCriticalSection(&g_mutex);
    g_singleshot_callbacks.clear();
    g_callbacks.clear();
    ::LeaveCriticalSection(&g_mutex);
}

void Enqueue(std::function<void()> callback) {
    if (!g_initialized || !g_mutex_initialized || !callback) {
        return;
    }

    ::EnterCriticalSection(&g_mutex);
    if (g_in_game_thread) {
        callback();
    } else {
        g_singleshot_callbacks.push_back(std::move(callback));
    }
    ::LeaveCriticalSection(&g_mutex);
}

void RegisterGameThreadCallback(
    PY4GW::HookEntry* entry,
    const GameThreadCallback& callback,
    int altitude) {
    if (!g_mutex_initialized) {
        return;
    }

    ::EnterCriticalSection(&g_mutex);
    RemoveGameThreadCallback(entry);

    auto it = g_callbacks.begin();
    while (it != g_callbacks.end()) {
        if (it->altitude > altitude) {
            break;
        }
        ++it;
    }
    g_callbacks.insert(it, CallbackEntry{altitude, entry, callback});
    ::LeaveCriticalSection(&g_mutex);
}

void RemoveGameThreadCallback(PY4GW::HookEntry* entry) {
    if (!g_mutex_initialized) {
        return;
    }

    auto it = std::find_if(g_callbacks.begin(), g_callbacks.end(), [entry](const CallbackEntry& value) {
        return value.entry == entry;
    });
    if (it != g_callbacks.end()) {
        g_callbacks.erase(it);
    }
}

bool IsInGameThread() {
    if (!g_initialized || !g_mutex_initialized) {
        return false;
    }

    ::EnterCriticalSection(&g_mutex);
    const bool result = g_in_game_thread;
    ::LeaveCriticalSection(&g_mutex);
    return result;
}

}  // namespace GW::game_thread
