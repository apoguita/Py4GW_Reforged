#include "base/error_handling.h"

#include "base/memory_patcher.h"

#include "GW/camera/camera.h"
#include "GW/context/camera.h"
#include "GW/context/context.h"

namespace GW::camera {
    extern PY4GW::MemoryPatcher g_patch_cam_update;
    extern PY4GW::MemoryPatcher g_patch_fog;

    bool ForwardMovement(float amount, bool true_forward) {
        Context::Camera* camera = Context::GetCamera();
        if (!camera || amount == 0.0f) {
            return false;
        }

        if (true_forward) {
            const float pitch_x = std::sqrt(1.0f - camera->pitch * camera->pitch);
            camera->look_at_target.x += amount * pitch_x * std::cos(camera->yaw);
            camera->look_at_target.y += amount * pitch_x * std::sin(camera->yaw);
            camera->look_at_target.z += amount * camera->pitch;
            return true;
        }

        camera->look_at_target.x += amount * std::cos(camera->yaw);
        camera->look_at_target.y += amount * std::sin(camera->yaw);
        return true;
    }

    bool VerticalMovement(float amount) {
        Context::Camera* camera = Context::GetCamera();
        if (!camera) {
            return false;
        }

        camera->look_at_target.z += amount;
        return true;
    }

    bool RotateMovement(float angle) {
        if (angle == 0.0f) {
            return false;
        }

        Context::Camera* camera = Context::GetCamera();
        if (!camera) {
            return false;
        }

        const float pos_x = camera->position.x;
        const float pos_y = camera->position.y;
        const float px = camera->look_at_target.x - pos_x;
        const float py = camera->look_at_target.y - pos_y;

        Vec3f new_position = {};
        new_position.x = pos_x + (std::cos(angle) * px - std::sin(angle) * py);
        new_position.y = pos_y + (std::sin(angle) * px + std::cos(angle) * py);
        new_position.z = camera->look_at_target.z;

        camera->SetYaw(camera->yaw + angle);
        camera->look_at_target = new_position;
        return true;
    }

    bool SideMovement(float amount) {
        Context::Camera* camera = Context::GetCamera();
        if (!camera || amount == 0.0f) {
            return false;
        }

        camera->look_at_target.x += amount * -std::sin(camera->yaw);
        camera->look_at_target.y += amount * std::cos(camera->yaw);
        return true;
    }

    bool SetMaxDist(float dist) {
        Context::Camera* camera = Context::GetCamera();
        if (!camera) {
            return false;
        }
        camera->max_distance2 = dist;
        return true;
    }

    bool SetFieldOfView(float fov) {
        Context::Camera* camera = Context::GetCamera();
        if (!camera) {
            return false;
        }
        camera->field_of_view = fov;
        return true;
    }

    Vec3f ComputeCamPos(float dist) {
        Context::Camera* camera = Context::GetCamera();
        if (!camera) {
            return {};
        }

        if (dist == 0.0f) {
            dist = camera->GetCameraZoom();
        }

        Vec3f new_position = camera->GetLookAtTarget();
        const float pitch_x = std::sqrt(1.0f - camera->pitch * camera->pitch);

        new_position.x -= dist * pitch_x * std::cos(camera->yaw);
        new_position.y -= dist * pitch_x * std::sin(camera->yaw);
        new_position.z -= dist * 0.95f * camera->pitch;

        return new_position;
    }

    bool UpdateCameraPos() {
        Context::Camera* camera = Context::GetCamera();
        if (!camera) {
            return false;
        }

        camera->SetCameraPos(ComputeCamPos());
        return true;
    }

    float GetFieldOfView() {
        Context::Camera* camera = Context::GetCamera();
        return camera ? camera->GetFieldOfView() : 0.0f;
    }

    float GetYaw() {
        Context::Camera* camera = Context::GetCamera();
        return camera ? camera->GetYaw() : 0.0f;
    }


    bool UnlockCam(bool flag) {
        return g_patch_cam_update.TogglePatch(flag);
    }

    bool GetCameraUnlock() {
        return g_patch_cam_update.GetIsActive();
    }

    bool SetFog(bool flag) {
        return g_patch_fog.TogglePatch(flag);
    }



}  // namespace GW::camera
