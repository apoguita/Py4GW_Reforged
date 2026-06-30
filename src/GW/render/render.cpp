#include "base/error_handling.h"

#include "GW/render/render.h"

#include "base/panic.h"
#include "base/CrashHandler.h"
#include "base/hooker.h"
#include "base/hook_types.h"
#include "base/patterns.h"
#include "base/scanner.h"
#include "GW/context/context.h"
#include "GW/ui/ui.h"

#include <atomic>

namespace GW::Context {
extern GwDxContext* g_dx_context;
extern uintptr_t g_window_handle_ptr;
}

namespace GW::render {
using EndSceneFn = bool(__cdecl*)(GwDxContext* ctx, void* unk);
using ResetFn = bool(__cdecl*)(GwDxContext* ctx);
using GetTransformFn = Mat4x3f*(__cdecl*)(int transform);

bool ResolveWindowHandlePointer();
bool ResolveResetHook();
bool ResolveEndSceneHook();
bool ResolveGetTransformFunction();
bool ResolveScreenCapture();

bool Init();
void EnableHooks();
void DisableHooks();
void Exit();
bool WaitForRenderHooksToDrain();

bool __cdecl OnEndScene(GwDxContext* ctx, void* unk);
bool __cdecl OnReset(GwDxContext* ctx);
void __cdecl OnScreenCapture(GwDxContext* ctx, void* unk);

EndSceneFn g_end_scene_func = nullptr;
EndSceneFn g_end_scene_original = nullptr;
EndSceneFn g_screen_capture_func = nullptr;
EndSceneFn g_screen_capture_original = nullptr;
ResetFn g_reset_func = nullptr;
ResetFn g_reset_original = nullptr;
GetTransformFn g_get_transform_func = nullptr;

CRITICAL_SECTION g_render_lock;
std::atomic<int> g_active_render_hooks = 0;
std::atomic<bool> g_in_render_loop = false;
bool g_render_lock_initialized = false;
bool g_hooks_enabled = false;
std::atomic<bool> g_initialized = false;
std::atomic<bool> g_shutting_down = false;

RenderCallback g_render_callback = nullptr;
RenderCallback g_reset_callback = nullptr;

bool WaitForRenderHooksToDrain() {
    CrashContextScope context("shutdown", "render", "wait_for_hooks_to_drain");
    for (int i = 0; i < 125; ++i) {
        if (g_active_render_hooks.load() == 0 &&
            !g_in_render_loop.load()) {
            return true;
        }
        ::Sleep(16);
    }

    Logger::Instance().LogWarning("[render] Timed out waiting for in-flight render hooks to drain.", "render");
    return false;
}

bool __cdecl OnEndScene(GwDxContext* ctx, void* unk) {
    PY4GW::HookBase::EnterHook();
    ++g_active_render_hooks;

    if (g_shutting_down || !g_render_lock_initialized) {
        const bool retval = g_end_scene_original ? g_end_scene_original(ctx, unk) : false;
        --g_active_render_hooks;
        PY4GW::HookBase::LeaveHook();
        return retval;
    }

    ::EnterCriticalSection(&g_render_lock);
    g_in_render_loop = true;
    Context::g_dx_context = ctx;
    if (!g_shutting_down && g_render_callback) {
        g_render_callback(ctx->device);
    }
    const bool retval = g_end_scene_original(ctx, unk);
    g_in_render_loop = false;
    ::LeaveCriticalSection(&g_render_lock);
    --g_active_render_hooks;
    PY4GW::HookBase::LeaveHook();
    return retval;
}

bool __cdecl OnReset(GwDxContext* ctx) {
    PY4GW::HookBase::EnterHook();
    ++g_active_render_hooks;
    Context::g_dx_context = ctx;
    if (!g_shutting_down && g_reset_callback) {
        g_reset_callback(ctx->device);
    }
    const bool retval = g_reset_original ? g_reset_original(ctx) : false;
    --g_active_render_hooks;
    PY4GW::HookBase::LeaveHook();
    return retval;
}

void __cdecl OnScreenCapture(GwDxContext* ctx, void* unk) {
    PY4GW::HookBase::EnterHook();
    if (!ui::GetIsShiftScreenShot() && g_render_callback) {
        g_render_callback(ctx->device);
    }
    g_screen_capture_original(ctx, unk);
    PY4GW::HookBase::LeaveHook();
}

bool Init() {
    CrashContextScope context("startup", "render", "init");
    g_shutting_down = false;
    ::InitializeCriticalSection(&g_render_lock);
    g_render_lock_initialized = true;

    if (!ResolveWindowHandlePointer() ||
        !ResolveResetHook() ||
        !ResolveEndSceneHook() ||
        !ResolveScreenCapture() ||
        !ResolveGetTransformFunction()) {
        return false;
    }

    const int end_scene_status = PY4GW::HookBase::CreateHook(
        reinterpret_cast<void**>(&g_end_scene_func),
        reinterpret_cast<void*>(&OnEndScene),
        reinterpret_cast<void**>(&g_end_scene_original));
    const int reset_status = PY4GW::HookBase::CreateHook(
        reinterpret_cast<void**>(&g_reset_func),
        reinterpret_cast<void*>(&OnReset),
        reinterpret_cast<void**>(&g_reset_original));
    const int screen_capture_status = PY4GW::HookBase::CreateHook(
        reinterpret_cast<void**>(&g_screen_capture_func),
        reinterpret_cast<void*>(&OnScreenCapture),
        reinterpret_cast<void**>(&g_screen_capture_original));

    const bool end_scene_ok = Logger::AssertHook("GwEndScene_Func", end_scene_status, "render");
    const bool reset_ok = Logger::AssertHook("GwReset_Func", reset_status, "render");
    const bool screen_capture_ok = Logger::AssertHook("ScreenCapture_Func", screen_capture_status, "render");
    return end_scene_ok && reset_ok && screen_capture_ok;
}

void EnableHooks() {
    CrashContextScope context("runtime", "render", "enable_hooks");
    if (g_end_scene_func) {
        PY4GW::HookBase::EnableHooks(reinterpret_cast<void*>(g_end_scene_func));
    }
    if (g_reset_func) {
        PY4GW::HookBase::EnableHooks(reinterpret_cast<void*>(g_reset_func));
    }
    if (g_screen_capture_func) {
        PY4GW::HookBase::EnableHooks(reinterpret_cast<void*>(g_screen_capture_func));
    }
    g_hooks_enabled = true;
}

void DisableHooks() {
    CrashContextScope context("shutdown", "render", "disable_hooks");
    if (!g_hooks_enabled) {
        return;
    }
    if (g_end_scene_func) {
        PY4GW::HookBase::DisableHooks(reinterpret_cast<void*>(g_end_scene_func));
    }
    if (g_reset_func) {
        PY4GW::HookBase::DisableHooks(reinterpret_cast<void*>(g_reset_func));
    }
    if (g_screen_capture_func) {
        PY4GW::HookBase::DisableHooks(reinterpret_cast<void*>(g_screen_capture_func));
    }
    g_hooks_enabled = false;
}

void Exit() {
    CrashContextScope context("shutdown", "render", "exit");
    g_render_callback = nullptr;
    g_reset_callback = nullptr;
    g_in_render_loop = false;
    if (g_end_scene_func) {
        PY4GW::HookBase::RemoveHook(reinterpret_cast<void*>(g_end_scene_func));
    }
    if (g_reset_func) {
        PY4GW::HookBase::RemoveHook(reinterpret_cast<void*>(g_reset_func));
    }
    if (g_screen_capture_func) {
        PY4GW::HookBase::RemoveHook(reinterpret_cast<void*>(g_screen_capture_func));
    }
    if (g_render_lock_initialized) {
        ::DeleteCriticalSection(&g_render_lock);
        g_render_lock_initialized = false;
    }

    Context::g_dx_context = nullptr;
    Context::g_window_handle_ptr = 0;
    g_end_scene_func = nullptr;
    g_end_scene_original = nullptr;
    g_screen_capture_func = nullptr;
    g_screen_capture_original = nullptr;
    g_reset_func = nullptr;
    g_reset_original = nullptr;
    g_get_transform_func = nullptr;
    g_hooks_enabled = false;
    g_active_render_hooks = 0;
}

bool Initialize() {
    CrashContextScope context("startup", "render", "initialize");
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
    CrashContextScope context("shutdown", "render", "shutdown");
    if (!g_initialized) {
        return;
    }

    g_shutting_down = true;
    g_render_callback = nullptr;
    g_reset_callback = nullptr;
    DisableHooks();
    WaitForRenderHooksToDrain();

    Exit();
    PY4GW::HookBase::Deinitialize();

    g_in_render_loop = false;
    g_shutting_down = false;
    g_initialized = false;
}

}  // namespace GW::render
