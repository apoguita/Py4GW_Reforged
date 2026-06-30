#pragma once

#include "GW/common/game_pos.h"

namespace GW::camera {
	bool Initialize();
	void Shutdown();

	bool ForwardMovement(float amount, bool true_forward);
	bool VerticalMovement(float amount);
	bool RotateMovement(float angle);
	bool SideMovement(float amount);

	bool SetMaxDist(float dist = 900.0f);
	bool SetFieldOfView(float fov);
	Vec3f ComputeCamPos(float dist = 0.0f);
	bool UpdateCameraPos();

	float GetFieldOfView();
	float GetYaw();

	bool UnlockCam(bool flag);
	bool GetCameraUnlock();
	bool SetFog(bool flag);
}  // namespace GW::camera
