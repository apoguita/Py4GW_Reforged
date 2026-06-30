#include "base/error_handling.h"

#include "GW/effects/effects.h"

#include "base/CrashHandler.h"
#include "base/hooker.h"
#include "base/logger.h"
#include "base/patterns.h"
#include "base/scanner.h"

#include <atomic>

namespace GW::effects {

using PostProcessEffectFn = void(__cdecl*)(uint32_t intensity, uint32_t tint);
using DropBuffFn = void(__cdecl*)(uint32_t buff_id);

bool ResolvePostProcessEffect();
bool ResolveDropBuff();
bool Init();
void EnableHooks();
void DisableHooks();
void Exit();
void __cdecl OnPostProcessEffect(uint32_t intensity, uint32_t tint);

PostProcessEffectFn g_post_process_effect_func = nullptr;
PostProcessEffectFn g_post_process_effect_original = nullptr;
DropBuffFn g_drop_buff_func = nullptr;
std::atomic<uint32_t> g_alcohol_level = 0;
std::atomic<bool> g_initialized = false;

void __cdecl OnPostProcessEffect(uint32_t intensity, uint32_t tint) {
    PY4GW::HookBase::EnterHook();
    g_alcohol_level = intensity;

    if (g_post_process_effect_original) {
        g_post_process_effect_original(intensity, tint);
    }

    PY4GW::HookBase::LeaveHook();
}

bool Init() {
    CrashContextScope context("startup", "effects", "init");

    if (!ResolvePostProcessEffect() || 
        !ResolveDropBuff()) {
        return false;
    }

    const int status = PY4GW::HookBase::CreateHook(
        reinterpret_cast<void**>(&g_post_process_effect_func),
        reinterpret_cast<void*>(&OnPostProcessEffect),
        reinterpret_cast<void**>(&g_post_process_effect_original));
    return Logger::AssertHook("PostProcessEffect_Func", status, "effects");
}

void EnableHooks() {
    CrashContextScope context("runtime", "effects", "enable_hooks");
    if (g_post_process_effect_func) {
        PY4GW::HookBase::EnableHooks(reinterpret_cast<void*>(g_post_process_effect_func));
    }
}

void DisableHooks() {
    CrashContextScope context("shutdown", "effects", "disable_hooks");
    if (g_post_process_effect_func) {
        PY4GW::HookBase::DisableHooks(reinterpret_cast<void*>(g_post_process_effect_func));
    }
}

void Exit() {
    CrashContextScope context("shutdown", "effects", "exit");
    if (g_post_process_effect_func) {
        PY4GW::HookBase::RemoveHook(reinterpret_cast<void*>(g_post_process_effect_func));
    }

    g_post_process_effect_func = nullptr;
    g_post_process_effect_original = nullptr;
    g_drop_buff_func = nullptr;
    g_alcohol_level = 0;
}

bool Initialize() {
    CrashContextScope context("startup", "effects", "initialize");
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
    CrashContextScope context("shutdown", "effects", "shutdown");
    if (!g_initialized) {
        return;
    }

    DisableHooks();
    Exit();
    PY4GW::HookBase::Deinitialize();
    g_initialized = false;
}

}  // namespace GW::effects
