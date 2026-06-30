#pragma once

#include "base/error_handling.h"

#include "GW/common/constants/constants.h"
#include "GW/common/gw_array.h"
#include "GW/common/gw_list.h"

#include <cstddef>
#include <cstdint>

namespace GW::Context {
    struct PlayerPartyMember { // total: 0xC/12
        /* +h0000 */ uint32_t login_number;
        /* +h0004 */ uint32_t calledTargetId;
        /* +h0008 */ uint32_t state;

        bool connected() const { return (state & 1) > 0; }
        bool ticked()    const { return (state & 2) > 0; }
    };
    static_assert(sizeof(PlayerPartyMember) == 0xC, "PlayerPartyMember size mismatch");

    struct HeroPartyMember { // total: 0x18/24
        /* +h0000 */ uint32_t agent_id;
        /* +h0004 */ uint32_t owner_player_id;
        /* +h0008 */ uint32_t hero_id;
        /* +h000C */ uint32_t h000C;
        /* +h0010 */ uint32_t h0010;
        /* +h0014 */ uint32_t level;
    };

    struct HenchmanPartyMember { // total: 0x34/52
        /* +h0000 */ uint32_t agent_id;
        /* +h0004 */ uint32_t h0004[10];
        /* +h002C */ uint32_t profession;
        /* +h0030 */ uint32_t level;
    };
    static_assert(sizeof(HenchmanPartyMember) == 0x34, "HenchmanPartyMember size mismatch");

    using HeroPartyMemberArray = GW::GWArray<HeroPartyMember>;
    using PlayerPartyMemberArray = GW::GWArray<PlayerPartyMember>;
    using HenchmanPartyMemberArray = GW::GWArray<HenchmanPartyMember>;

    struct PartyInfo { // total: 0x84/132

        size_t GetPartySize() const {
            return players.size() + henchmen.size() + heroes.size();
        }

        /* +h0000 */ uint32_t party_id;
        /* +h0004 */ GW::GWArray<PlayerPartyMember> players;
        /* +h0014 */ GW::GWArray<HenchmanPartyMember> henchmen;
        /* +h0024 */ GW::GWArray<HeroPartyMember> heroes;
        /* +h0034 */ GW::GWArray<uint32_t> others; // agent id of allies, minions, pets.
        /* +h0044 */ uint32_t h0044[14];
        /* +h007C */ GW::GwLink<PartyInfo> invite_link;
    };
    static_assert(sizeof(PartyInfo) == 0x84, "PartyInfo size mismatch");

    enum PartySearchType {
        PartySearchType_Hunting = 0,
        PartySearchType_Mission = 1,
        PartySearchType_Quest = 2,
        PartySearchType_Trade = 3,
        PartySearchType_Guild = 4,
    };

    struct PartySearch {
        /* +h0000 */ uint32_t party_search_id;
        /* +h0004 */ uint32_t party_search_type;
        /* +h0008 */ uint32_t hardmode;
        /* +h000C */ uint32_t district;
        /* +h0010 */ uint32_t language;
        /* +h0014 */ uint32_t party_size;
        /* +h0018 */ uint32_t hero_count;
        /* +h001C */ wchar_t message[32];
        /* +h005C */ wchar_t party_leader[20];
        /* +h0084 */ uint32_t primary;
        /* +h0088 */ uint32_t secondary;
        /* +h008C */ uint32_t level;
        /* +h0090 */ uint32_t timestamp;
    };
    static_assert(sizeof(PartySearch) == 0x94, "PartySearch size mismatch");

    struct PartyContext { // total: 0x58/88
        /* +h0000 */ uint32_t h0000;
        /* +h0004 */ GW::GWArray<void*> h0004;
        /* +h0014 */ uint32_t flag;
        /* +h0018 */ uint32_t h0018;
        /* +h001C */ GW::GwList<PartyInfo> requests;
        /* +h0028 */ uint32_t requests_count;
        /* +h002C */ GW::GwList<PartyInfo> sending;
        /* +h0038 */ uint32_t sending_count;
        /* +h003C */ uint32_t h003C;
        /* +h0040 */ GW::GWArray<PartyInfo*> parties;
        /* +h0050 */ uint32_t h0050;
        /* +h0054 */ PartyInfo* player_party; // Players party
        /* +h0058 */ uint8_t h0058[104];
        /* +h00C0 */ GW::GWArray<PartySearch*> party_search;

        bool InHardMode() const { return (flag & 0x10) > 0; }
        bool IsDefeated() const { return (flag & 0x20) > 0; }
        bool IsPartyLeader() const { return (flag >> 0x7) & 1; }
    };

    static_assert(offsetof(PartyContext, requests) == 0x1C, "PartyContext::requests offset mismatch");
    static_assert(offsetof(PartyContext, parties) == 0x40, "PartyContext::parties offset mismatch");
    static_assert(offsetof(PartyContext, player_party) == 0x54, "PartyContext::player_party offset mismatch");
    static_assert(offsetof(PartyContext, party_search) == 0xC0, "PartyContext::party_search offset mismatch");
    static_assert(sizeof(PartyContext) == 0xD0, "PartyContext size mismatch");


}  // namespace GW::Context
