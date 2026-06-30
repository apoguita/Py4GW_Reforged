#include "base/error_handling.h"

#include "base/CrashHandler.h"
#include "base/patterns.h"

#include "GW/render/render.h"

namespace GW::Context {
extern uintptr_t g_window_handle_ptr;
}

namespace GW::render {

using EndSceneFn = bool(__cdecl*)(GwDxContext* ctx, void* unk);
using ResetFn = bool(__cdecl*)(GwDxContext* ctx);
using GetTransformFn = Mat4x3f*(__cdecl*)(int transform);

extern ResetFn g_reset_func;
extern EndSceneFn g_end_scene_func;
extern GetTransformFn g_get_transform_func;
extern EndSceneFn g_screen_capture_func;

bool ResolveWindowHandlePointer() {
    CrashContextScope context("startup", "render", "resolve_window_handle_ptr");
    return PY4GW::Patterns::Resolve("render.window_handle_ptr", &Context::g_window_handle_ptr);
}

bool ResolveResetHook() {
    CrashContextScope context("startup", "render", "resolve_reset_hook");
    return PY4GW::Patterns::Resolve("render.reset_func", &g_reset_func);
}

bool ResolveEndSceneHook() {
    CrashContextScope context("startup", "render", "resolve_end_scene_hook");
    return PY4GW::Patterns::Resolve("render.end_scene_func", &g_end_scene_func);
}

bool ResolveGetTransformFunction() {
    CrashContextScope context("startup", "render", "resolve_get_transform");
    return PY4GW::Patterns::Resolve("render.get_transform_func", &g_get_transform_func);
}

bool ResolveScreenCapture() {
    CrashContextScope context("startup", "render", "resolve_screen_capture");
    return PY4GW::Patterns::Resolve("render.screen_capture_func", &g_screen_capture_func);
}

}  // namespace GW::render
