#include "base/error_handling.h"

#include "GW/game_thread/game_thread.h"

namespace GW::game_thread {

using LeaveGameThreadFn = void(__cdecl*)(void*);

extern LeaveGameThreadFn g_leave_game_thread_func;

bool ResolveLeaveGameThreadTarget() {
    CrashContextScope context("startup", "game_thread", "resolve_leave_game_thread_target");
    return PY4GW::Patterns::Resolve("game_thread.leave_game_thread_func", &g_leave_game_thread_func);
}

}  // namespace GW::game_thread
