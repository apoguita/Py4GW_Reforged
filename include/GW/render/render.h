#pragma once

#include "GW/common/constants/render.h"
#include "GW/common/game_pos.h"
#include "GW/context/render.h"

#include <windows.h>

namespace GW::render {

bool Initialize();
void Shutdown();

using RenderCallback = void(__cdecl*)(IDirect3DDevice9*);
using Transform = Constants::Transform;

HWND GetWindowHandle();
IDirect3DDevice9* GetDevice();
bool GetIsInRenderLoop();
int GetIsFullscreen();
uint32_t GetViewportWidth();
uint32_t GetViewportHeight();
Mat4x3f* GetTransform(Transform transform);
float GetFieldOfView();

RenderCallback GetRenderCallback();
void SetRenderCallback(RenderCallback callback);
void SetResetCallback(RenderCallback callback);

using GwDxContext = Context::GwDxContext;

}  // namespace GW::render
