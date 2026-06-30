#pragma once

#include <cstdint>

namespace GW::Constants {

enum class BagType {
    None,
    Inventory,
    Equipped,
    NotCollected,
    Storage,
    MaterialStorage
};

enum class DyeColor : uint8_t {
    None = 0,
    Blue = 2,
    Green = 3,
    Purple = 4,
    Red = 5,
    Yellow = 6,
    Brown = 7,
    Orange = 8,
    Silver = 9,
    Black = 10,
    Gray = 11,
    White = 12,
    Pink = 13
};

}  // namespace GW::Constants
