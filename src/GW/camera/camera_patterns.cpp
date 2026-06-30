#include "base/error_handling.h"

#include "base/CrashHandler.h"
#include "base/memory_patcher.h"
#include "base/patterns.h"

#include "GW/camera/camera.h"
#include "GW/context/camera.h"

namespace GW::Context {
extern Camera* g_camera;
}

namespace GW::camera {

extern PY4GW::MemoryPatcher g_patch_cam_update;
extern PY4GW::MemoryPatcher g_patch_fog;

bool ResolveCameraPointer() {
    CrashContextScope context("startup", "camera", "resolve_camera_pointer");
    return PY4GW::Patterns::Resolve("camera.camera_ptr", &Context::g_camera);
}

bool ResolveFogPatch() {
    CrashContextScope context("startup", "camera", "resolve_fog_patch");
    uintptr_t address = 0;
    if (!PY4GW::Patterns::Resolve("camera.fog_patch_addr", &address)) {
        return false;
    }

    static constexpr uint8_t kFogPatch[] = {0x00};
    g_patch_fog.SetPatch(address, kFogPatch, sizeof(kFogPatch));
    return g_patch_fog.IsValid();
}

bool ResolveCameraUpdatePatch() {
    CrashContextScope context("startup", "camera", "resolve_camera_update_patch");
    const auto result = PY4GW::Patterns::ResolvePointer("camera.camera_update_patch_addr");
    if (!result.ok) {
        return result.ShouldContinue();
    }

    if (result.selected_attempt == "vs2017") {
        static constexpr uint8_t kPatchVs2017[] = {0xEB, 0x0C};
        g_patch_cam_update.SetPatch(result.value, kPatchVs2017, sizeof(kPatchVs2017));
        return g_patch_cam_update.IsValid();
    }

    static constexpr uint8_t kPatchVs2022[] = {0xEB, 0x0F};
    g_patch_cam_update.SetPatch(result.value, kPatchVs2022, sizeof(kPatchVs2022));
    return g_patch_cam_update.IsValid();
}

}  // namespace GW::camera
