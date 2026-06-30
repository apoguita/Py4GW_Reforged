#pragma once

#include <cstdint>

namespace GW::Constants {

enum class EventID : uint32_t {
    kRecvPing = 0x8,
    kSendFriendState = 0x26,
    kLocalFriendState = 0x28,
    kRecvFriendState = 0x2c
};

}  // namespace GW::Constants
