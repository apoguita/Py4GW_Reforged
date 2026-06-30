#pragma once

#include "base/error_handling.h"

#include "GW/common/constants/maps.h"
#include "GW/common/gw_array.h"

#include <algorithm>
#include <cstdint>

namespace GW::Context {

    struct GHKey {
        uint32_t k[4]{};

        explicit operator bool() const {
            return std::any_of(std::begin(k), std::end(k), [](uint32_t i) { return i != 0; });
        }
    };

    struct GuildPlayer { // total: 0x174/372
        /* +h0000 */ void* vtable;
        /* +h0004 */ wchar_t* name_ptr; // ptr to invitedname, why? dunno
        /* +h0008 */ wchar_t invited_name[20]; // name of character that was invited in
        /* +h0030 */ wchar_t current_name[20]; // name of character currently being played
        /* +h0058 */ wchar_t inviter_name[20]; // name of character that invited player
        /* +h0080 */ uint32_t invite_time; // time in ms from game creation ??
        /* +h0084 */ wchar_t promoter_name[20]; // name of player that last modified rank
        /* +h00AC */ uint32_t h00AC[12];
        /* +h00DC */ uint32_t offline;
        /* +h00E0 */ uint32_t member_type;
        /* +h00E4 */ uint32_t status;
        /* +h00E8 */ uint32_t h00E8[35];
    };
    static_assert(sizeof(GuildPlayer) == 0x174, "GuildPlayer size mismatch");

    using GuildRoster = GW::GWArray<GuildPlayer*>;

    struct GuildHistoryEvent { // total: 0x208/520
        /* +h0000 */ uint32_t time1; // Guessing one of these is time in ms
        /* +h0004 */ uint32_t time2;
        /* +h0008 */ wchar_t name[256]; // Name of added/kicked person, then the adder/kicker, they seem to be in the same array
    };
    static_assert(sizeof(GuildHistoryEvent) == 0x208, "GuildHistoryEvent size mismatch");

    using GuildHistory = GW::GWArray<GuildHistoryEvent*>;

    struct CapeDesign { // total: 0x1C/28
        /* +h0000 */ uint32_t cape_bg_color;
        /* +h0004 */ uint32_t cape_detail_color;
        /* +h0008 */ uint32_t cape_emblem_color;
        /* +h000C */ uint32_t cape_shape;
        /* +h0010 */ uint32_t cape_detail;
        /* +h0014 */ uint32_t cape_emblem;
        /* +h0018 */ uint32_t cape_trim;
    };
    static_assert(sizeof(CapeDesign) == 0x1C, "CapeDesign size mismatch");

    struct Guild { // total: 0xAC/172
        /* +h0000 */ GHKey key;
        /* +h0010 */ uint32_t h0010[5];
        /* +h0024 */ uint32_t index; // Same as PlayerGuildIndex
        /* +h0028 */ uint32_t rank;
        /* +h002C */ uint32_t features;
        /* +h0030 */ wchar_t name[32];
        /* +h0070 */ uint32_t rating;
        /* +h0074 */ uint32_t faction; // 0=kurzick, 1=luxon
        /* +h0078 */ uint32_t faction_point;
        /* +h007C */ uint32_t qualifier_point;
        /* +h0080 */ wchar_t tag[8];
        /* +h0090 */ CapeDesign cape;
    };
    static_assert(sizeof(Guild) == 0xAC, "Guild size mismatch");

    typedef GW::GWArray<Guild*> GuildArray;

    struct TownAlliance { // total: 0x78/120
        /* +h0000 */ uint32_t rank;
        /* +h0004 */ uint32_t allegiance;
        /* +h0008 */ uint32_t faction;
        /* +h000C */ wchar_t name[32];
        /* +h004C */ wchar_t tag[5];
        /* +h0056 */ uint8_t _padding[2];
        /* +h0058 */ CapeDesign cape;
        /* +h0074 */ GW::Constants::MapID map_id;
    };
    static_assert(sizeof(TownAlliance) == 0x78, "TownAlliance size mismatch");

    struct GuildContext { // total: 0x3BC/956
        /* +h0000 */ uint32_t h0000;
        /* +h0004 */ uint32_t h0004;
        /* +h0008 */ uint32_t h0008;
        /* +h000C */ uint32_t h000C;
        /* +h0010 */ uint32_t h0010;
        /* +h0014 */ uint32_t h0014;
        /* +h0018 */ uint32_t h0018;
        /* +h001C */ uint32_t h001C;
        /* +h0020 */ GW::GWArray<void*> h0020;
        /* +h0030 */ uint32_t h0030;
        /* +h0034 */ wchar_t player_name[20];
        /* +h005C */ uint32_t h005C;
        /* +h0060 */ uint32_t player_guild_index;
        /* +h0064 */ GHKey player_gh_key;
        /* +h0074 */ uint32_t h0074;
        /* +h0078 */ wchar_t announcement[256];
        /* +h0278 */ wchar_t announcement_author[20];
        /* +h02A0 */ uint32_t player_guild_rank;
        /* +h02A4 */ uint32_t h02A4;
        /* +h02A8 */ GW::GWArray<TownAlliance> factions_outpost_guilds;
        /* +h02B8 */ uint32_t kurzick_town_count;
        /* +h02BC */ uint32_t luxon_town_count;
        /* +h02C0 */ uint32_t h02C0;
        /* +h02C4 */ uint32_t h02C4;
        /* +h02C8 */ uint32_t h02C8;
        /* +h02CC */ GuildHistory player_guild_history;
        /* +h02DC */ uint32_t h02DC[7];
        /* +h02F8 */ GuildArray guilds;
        /* +h0308 */ uint32_t h0308[4];
        /* +h0318 */ GW::GWArray<void*> h0318;
        /* +h0328 */ uint32_t h0328;
        /* +h032C */ GW::GWArray<void*> h032C;
        /* +h033C */ uint32_t h033C[7];
        /* +h0358 */ GuildRoster player_roster;
        //... end of what i care about
    };

    static_assert(offsetof(GuildContext, player_name) == 0x34, "GuildContext::player_name offset mismatch");
    static_assert(offsetof(GuildContext, player_gh_key) == 0x64, "GuildContext::player_gh_key offset mismatch");
    static_assert(offsetof(GuildContext, announcement) == 0x78, "GuildContext::announcement offset mismatch");
    static_assert(offsetof(GuildContext, factions_outpost_guilds) == 0x2A8, "GuildContext::factions_outpost_guilds offset mismatch");
    static_assert(offsetof(GuildContext, guilds) == 0x2F8, "GuildContext::guilds offset mismatch");
    static_assert(offsetof(GuildContext, player_roster) == 0x358, "GuildContext::player_roster offset mismatch");

    GuildArray* GetGuildArray();

}  // namespace GW::Context
