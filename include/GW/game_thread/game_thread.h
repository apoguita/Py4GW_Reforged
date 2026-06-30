#pragma once

#include "base/error_handling.h"

#include "base/CrashHandler.h"
#include "base/hook_types.h"
#include "base/patterns.h"

#include <atomic>
#include <functional>
#include <vector>
#include <windows.h>

namespace GW::game_thread {
    using GameThreadCallback = PY4GW::HookCallback<>;

    bool Initialize();
    void Shutdown();

    void ClearCalls();
    void Enqueue(std::function<void()> callback);
    void RegisterGameThreadCallback(
        PY4GW::HookEntry* entry,
        const GameThreadCallback& callback,
        int altitude = 0x4000);
    void RemoveGameThreadCallback(PY4GW::HookEntry* entry);
    bool IsInGameThread();

}  // namespace GW::game_thread
