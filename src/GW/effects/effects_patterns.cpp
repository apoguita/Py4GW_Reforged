#include "base/error_handling.h"

#include "base/CrashHandler.h"
#include "base/patterns.h"

#include "GW/effects/effects.h"

namespace GW::effects {

using PostProcessEffectFn = void(__cdecl*)(uint32_t intensity, uint32_t tint);
using DropBuffFn = void(__cdecl*)(uint32_t buff_id);

extern PostProcessEffectFn g_post_process_effect_func;
extern DropBuffFn g_drop_buff_func;

bool ResolvePostProcessEffect() {
    CrashContextScope context("startup", "effects", "resolve_post_process_effect");
    return PY4GW::Patterns::Resolve("effects.post_process_effect_func", &g_post_process_effect_func);
}

bool ResolveDropBuff() {
    CrashContextScope context("startup", "effects", "resolve_drop_buff");
    return PY4GW::Patterns::Resolve("effects.drop_buff_func", &g_drop_buff_func);
}

}  // namespace GW::effects
