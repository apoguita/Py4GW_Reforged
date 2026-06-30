#pragma once

#include <cstdint>

namespace GW::Constants {

enum class Continent : uint32_t {
    Kryta,
    DevContinent,
    Cantha,
    BattleIsles,
    Elona,
    RealmOfTorment
};

enum class RegionType : uint32_t {
    AllianceBattle,
    Arena,
    ExplorableZone,
    GuildBattleArea,
    GuildHall,
    MissionOutpost,
    CooperativeMission,
    CompetitiveMission,
    EliteMission,
    Challenge,
    Outpost,
    ZaishenBattle,
    HeroesAscent,
    City,
    MissionArea,
    HeroBattleOutpost,
    HeroBattleArea,
    EotnMission,
    Dungeon,
    Marketplace,
    Unknown,
    DevRegion
};

}  // namespace GW::Constants
