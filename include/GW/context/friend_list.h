#pragma once

#include "base/error_handling.h"

#include "GW/common/constants/friend_list.h"
#include "GW/common/gw_array.h"

#include <cstddef>
#include <cstdint>

namespace GW::Context {

    struct Friend {
        /* +h0000 */ Constants::FriendType type;
        /* +h0004 */ Constants::FriendStatus status;
        /* +h0008 */ uint8_t uuid[16];
        /* +h0018 */ wchar_t alias[20];
        /* +h002C */ wchar_t charname[20];
        /* +h0040 */ uint32_t friend_id;
        /* +h0044 */ uint32_t zone_id;
    };

    using FriendsListArray = GW::GWArray<Friend*>;

    struct FriendList {
        /* +h0000 */ FriendsListArray friends;
        /* +h0010 */ uint8_t  h0010[20];
        /* +h0024 */ uint32_t number_of_friend;
        /* +h0028 */ uint32_t number_of_ignore;
        /* +h002C */ uint32_t number_of_partner;
        /* +h0030 */ uint32_t number_of_trade;
        /* +h0034 */ uint8_t  h0034[108];
        /* +h00A0 */ Constants::FriendStatus player_status;
    };

#pragma warning(push)
#pragma warning(disable : 4200)
    struct FriendEventData {
        uint32_t event_id;
        uint32_t unk;
        uint32_t data_size;
        uint32_t data[];
    };
#pragma warning(pop)

}  // namespace GW::Context
