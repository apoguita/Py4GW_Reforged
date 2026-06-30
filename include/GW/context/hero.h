#pragma once

#include "base/error_handling.h"

#include "GW/common/constants/hero.h"
#include "GW/common/game_pos.h"
#include "GW/common/gw_array.h"

#include <cstdint>

namespace GW::Context {

    using AgentID = uint32_t;

    struct HeroFlag { // total: 0x20/36
        /* +h0000 */ uint32_t hero_id;
        /* +h0004 */ AgentID  agent_id;
        /* +h0008 */ uint32_t level;
        /* +h000C */ Constants::HeroBehavior hero_behavior;
        /* +h0010 */ Vec2f flag;
        /* +h0018 */ uint32_t h0018;
        /* +h001C */ AgentID locked_target_id;
        /* +h0020 */ uint32_t h0020; // type is unknown too, added for padding
    };
    static_assert(sizeof(HeroFlag) == 0x24, "HeroFlag size mismatch");

    struct HeroInfo { // total: 0x78/120
        /* +h0000 */ uint32_t hero_id;
        /* +h0004 */ uint32_t agent_id;
        /* +h0008 */ uint32_t level;
        /* +h000C */ uint32_t primary; // Primary profession 0-10 (None,W,R,Mo,N,Me,E,A,Rt,P,D)
        /* +h0010 */ uint32_t secondary; // Primary profession 0-10 (None,W,R,Mo,N,Me,E,A,Rt,P,D)
        /* +h0014 */ uint32_t hero_file_id;
        /* +h0018 */ uint32_t model_file_id;
        /* +h001C */ uint8_t  h001C[52];
        /* +h0050 */ wchar_t  name[20];
    };
    static_assert(sizeof(HeroInfo) == 0x78, "HeroInfo size mismatch");

    using HeroFlagArray = GW::GWArray<HeroFlag>;
    using HeroInfoArray = GW::GWArray<HeroInfo>;

}  // namespace GW::Context
