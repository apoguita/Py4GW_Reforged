#pragma once

#include <cstdint>

namespace GW::chat {

using Color = uint32_t;

inline constexpr Color MakeColorARGB(uint8_t a, uint8_t r, uint8_t g, uint8_t b) {
    return (static_cast<Color>(a) << 24) | (static_cast<Color>(r) << 16) | (static_cast<Color>(g) << 8) | static_cast<Color>(b);
}

inline constexpr Color MakeColorRGB(uint8_t r, uint8_t g, uint8_t b) {
    return MakeColorARGB(0xff, r, g, b);
}

enum Channel : int {
    CHANNEL_ALLIANCE = 0,
    CHANNEL_ALLIES = 1,
    CHANNEL_GWCA1 = 2,
    CHANNEL_ALL = 3,
    CHANNEL_GWCA2 = 4,
    CHANNEL_MODERATOR = 5,
    CHANNEL_EMOTE = 6,
    CHANNEL_WARNING = 7,
    CHANNEL_GWCA3 = 8,
    CHANNEL_GUILD = 9,
    CHANNEL_GLOBAL = 10,
    CHANNEL_GROUP = 11,
    CHANNEL_TRADE = 12,
    CHANNEL_ADVISORY = 13,
    CHANNEL_WHISPER = 14,
    CHANNEL_COUNT,
    CHANNEL_COMMAND,
    CHANNEL_UNKNOW = -1
};

}  // namespace GW::chat
