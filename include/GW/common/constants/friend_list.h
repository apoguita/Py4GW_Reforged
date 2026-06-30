#pragma once

#include <cstdint>

namespace GW::Constants {

enum class FriendType : uint32_t {
    Unknow = 0,
    Friend = 1,
    Ignore = 2,
    Player = 3,
    Trade = 4,
};

enum class FriendStatus : uint32_t {
    Offline = 0,
    Online = 1,
    DND = 2,
    Away = 3,
    Unknown = 4
};

}  // namespace GW::Constants
