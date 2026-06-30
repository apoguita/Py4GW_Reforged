#pragma once

#include <cstdint>

namespace GW::Constants {

enum class WorldActionId : uint32_t {
    InteractEnemy,
    InteractPlayerOrOther,
    InteractNPC,
    InteractItem,
    InteractTrade,
    InteractGadget
};

enum class CallTargetType : uint32_t {
    Following = 0x3,
    Morale = 0x7,
    AttackingOrTargetting = 0xA,
    None = 0xFF
};

}  // namespace GW::Constants
