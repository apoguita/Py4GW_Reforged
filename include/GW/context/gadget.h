#pragma once

#include "base/error_handling.h"

#include "GW/common/gw_array.h"

#include <cstddef>
#include <cstdint>

namespace GW::Context {

    struct GadgetInfo {
        /* +h0000 */ uint32_t h0000;
        /* +h0004 */ uint32_t h0004;
        /* +h0008 */ uint32_t h0008;
        /* +h000C */ wchar_t* name_enc;
    };
    static_assert(sizeof(GadgetInfo) == 0x10, "GadgetInfo size mismatch");

    struct GadgetContext {
        /* +h0000 */ GW::GWArray<GadgetInfo> gadget_info;
        // ...
    };

    static_assert(sizeof(GadgetContext) == 0x10, "GadgetContext size mismatch");

}  // namespace GW::Context
