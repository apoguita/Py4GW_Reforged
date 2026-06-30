#pragma once

#include "base/error_handling.h"

#include <cstddef>
#include <cstdint>

namespace GW::Context {

    struct GameplayContext {
        /* +h0000 */ uint32_t h0000[0x13];
        float mission_map_zoom;
        uint32_t unk[10];
    };

    static_assert(offsetof(GameplayContext, mission_map_zoom) == 0x4C, "GameplayContext::mission_map_zoom offset mismatch");
    static_assert(sizeof(GameplayContext) == 0x78, "GameplayContext size mismatch");

}  // namespace GW::Context
