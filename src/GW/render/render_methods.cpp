#include "base/error_handling.h"

#include "base/CrashHandler.h"
#include "GW/context/camera.h"
#include "GW/context/context.h"
#include "GW/render/render.h"

#include <atomic>
#include <cmath>

namespace GW::render {

using EndSceneFn = bool(__cdecl*)(GwDxContext* ctx, void* unk);
using ResetFn = bool(__cdecl*)(GwDxContext* ctx);
using GetTransformFn = Mat4x3f*(__cdecl*)(int transform);

extern GetTransformFn g_get_transform_func;
extern CRITICAL_SECTION g_render_lock;
extern std::atomic<bool> g_in_render_loop;
extern bool g_render_lock_initialized;
extern std::atomic<bool> g_shutting_down;
extern RenderCallback g_render_callback;
extern RenderCallback g_reset_callback;

HWND GetWindowHandle() {
    const auto window_handle_ptr = Context::GetWindowHandlePtrAddress();
    return window_handle_ptr ? *reinterpret_cast<HWND*>(window_handle_ptr) : nullptr;
}

IDirect3DDevice9* GetDevice() {
    const auto* dx_context = Context::GetRenderContext();
    return dx_context ? dx_context->device : nullptr;
}

bool GetIsInRenderLoop() {
    if (!g_render_lock_initialized) {
        return false;
    }
    ::EnterCriticalSection(&g_render_lock);
    const bool ret = g_in_render_loop;
    ::LeaveCriticalSection(&g_render_lock);
    return ret;
}

int GetIsFullscreen() {
    const auto* dx_context = Context::GetRenderContext();
    if (!dx_context) {
        return -1;
    }
    return dx_context->viewport_height == dx_context->window_height &&
            dx_context->viewport_width == dx_context->window_width
        ? 1
        : 0;
}

uint32_t GetViewportWidth() {
    const auto* dx_context = Context::GetRenderContext();
    return dx_context ? dx_context->viewport_width : 0;
}

uint32_t GetViewportHeight() {
    const auto* dx_context = Context::GetRenderContext();
    return dx_context ? dx_context->viewport_height : 0;
}

Mat4x3f* GetTransform(Transform transform) {
    return g_get_transform_func ? g_get_transform_func(static_cast<int>(transform)) : nullptr;
}

float GetFieldOfView() {
    const Context::Camera* camera = Context::GetCamera();
    if (!camera) {
        return 0.0f;
    }

    constexpr float kDividend = 2.0f / 3.0f + 1.0f;
    return std::atan2(1.0f, kDividend / std::tan(camera->GetFieldOfView() * 0.5f)) * 2.0f;
}

RenderCallback GetRenderCallback() {
    return g_render_callback;
}

void SetRenderCallback(RenderCallback callback) {
    CrashContextScope context("runtime", "render", "set_render_callback", callback ? "assign" : "clear");
    if (g_shutting_down && callback) {
        return;
    }
    g_render_callback = callback;
}

void SetResetCallback(RenderCallback callback) {
    CrashContextScope context("runtime", "render", "set_reset_callback", callback ? "assign" : "clear");
    if (g_shutting_down && callback) {
        return;
    }
    g_reset_callback = callback;
}

}  // namespace GW::render
