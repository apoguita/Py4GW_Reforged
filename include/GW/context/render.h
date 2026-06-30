#pragma once

#include "base/error_handling.h"

#include <cstdint>

struct IDirect3DDevice9;

namespace GW::Context {

struct GwDxContext {
    uint8_t h0000_1[0x128];
    uint8_t h0000[24];
    uint32_t h0018;
    uint8_t h001C[44];
    wchar_t gpu_name[32];
    uint8_t h0088[8];
    IDirect3DDevice9* device;
    uint8_t h0094[12];
    uint32_t framecount;
    uint8_t h00A4[2936];
    uint32_t viewport_width;
    uint32_t viewport_height;
    uint8_t h0C24[148];
    uint32_t window_width;
    uint32_t window_height;
    uint8_t h0CC0[952];
};

GwDxContext* GetRenderContext();
uintptr_t GetWindowHandlePtrAddress();

}  // namespace GW::Context
