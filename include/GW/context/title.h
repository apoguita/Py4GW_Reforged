#pragma once

#include "base/error_handling.h"

#include "GW/common/constants/constants.h"
#include "GW/common/gw_array.h"

#include <cstdint>

namespace GW::Context {

    struct Title { // total: 0x28/40
        /* +h0000 */ uint32_t props;
        /* +h0004 */ uint32_t current_points;
        /* +h0008 */ uint32_t current_title_tier_index;
        /* +h000C */ uint32_t points_needed_current_rank;
        /* +h0010 */ uint32_t next_title_tier_index;
        /* +h0014 */ uint32_t points_needed_next_rank;
        /* +h0018 */ uint32_t max_title_rank;
        /* +h001C */ uint32_t max_title_tier_index;
        /* +h0020 */ uint32_t h0020;
        /* +h0024 */ wchar_t* points_desc; // Pretty sure these are ptrs to title hash strings
        /* +h0028 */ wchar_t* h0028; // Pretty sure these are ptrs to title hash strings

        inline bool is_percentage_based() { return (props & 1) != 0; };
        inline bool has_tiers() { return (props & 3) == 2; };

    };
    static_assert(sizeof(Title) == 0x2C, "Title size mismatch");

    struct TitleTier {
        uint32_t props;
        uint32_t tier_number;
        wchar_t* tier_name_enc;
        inline bool is_percentage_based() { return (props & 1) != 0; };
    };
    static_assert(sizeof(TitleTier) == 0xC, "TitleTier size mismatch");

    struct TitleClientData {
        uint32_t title_id;
        uint32_t name_id;
    };

    using TitleArray = GW::GWArray<Title>;

    TitleClientData* GetTitleClientData();

}  // namespace GW::Context
