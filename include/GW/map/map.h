#pragma once

#include "GW/common/constants/constants.h"
#include "GW/common/game_pos.h"
#include "GW/context/map.h"
#include "GW/context/pathing.h"

#include <cstdint>

namespace GW::map {

bool Initialize();
void Shutdown();

bool Travel(GW::Constants::MapID map_id, GW::Constants::ServerRegion region, int district_number = 0, GW::Constants::Language language = static_cast<GW::Constants::Language>(0));
bool Travel(GW::Constants::MapID map_id, GW::Constants::District district = static_cast<GW::Constants::District>(0), int district_number = 0);
bool MapTestStart(uint32_t map_id, uint32_t alt_map_id, int number = 2, uint32_t count = 3, uint32_t delay_ms = 0, uint32_t timeout_ms = 10000, uint32_t message_id = 0x10000098);
void MapTestStop();
const char* MapTestGetStatus();
bool MapTestIsActive();
uint32_t MapTestGetCount();
bool EnterChallenge();

int QueryAltitude(const GamePos& pos, float radius, float& altitude, Vec3f* terrain_normal = nullptr);
bool GetIsMapLoaded();
GW::Constants::MapID GetMapID();
bool GetIsMapUnlocked(GW::Constants::MapID map_id);
GW::Constants::ServerRegion GetRegion();
uintptr_t GetServerRegionPtr();
Context::MapTypeInstanceInfo* GetMapTypeInstanceInfo(Constants::RegionType map_type);
GW::Constants::Language GetLanguage();
bool GetIsObserving();
int GetDistrict();
uint32_t GetInstanceTime();
GW::Constants::InstanceType GetInstanceType();
GW::Constants::ServerRegion RegionFromDistrict(GW::Constants::District district);
GW::Constants::Language LanguageFromDistrict(GW::Constants::District district);
Context::PathingMapArray* GetPathingMap();
uint32_t GetFoesKilled();
uint32_t GetFoesToKill();
Context::AreaInfo* GetMapInfo(GW::Constants::MapID map_id = static_cast<GW::Constants::MapID>(0));
uintptr_t GetInstanceInfoPtr();
inline Context::AreaInfo* GetCurrentMapInfo() {
    return GetMapInfo(GetMapID());
}
bool GetIsInCinematic();
bool SkipCinematic();
bool CancelEnterChallenge();

}  // namespace GW::map
