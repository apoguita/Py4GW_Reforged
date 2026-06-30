#include "base/error_handling.h"

#include "GW/map/map.h"

#include "GW/context/agent.h"
#include "GW/context/cinematic.h"
#include "GW/context/character.h"
#include "GW/context/context.h"
#include "GW/context/game.h"
#include "GW/context/map.h"
#include "GW/context/world.h"
#include "GW/ui/ui.h"

#include <string>

namespace GW::map {

using QueryAltitudeFn = int(__cdecl*)(const GamePos* point, float radius, float* altitude, Vec3f* terrain_normal);
using VoidFn = void(__cdecl*)();
using DoActionFn = void(__cdecl*)(uint32_t);

struct MapTestState {
    bool active = false;
    uint32_t map_id = 0;
    uint32_t alt_map_id = 0;
    int number = 2;
    uint32_t count = 3;
    uint32_t delay_ms = 0;
    uint32_t timeout_ms = 10000;
    uint32_t message_id = 0;
    uint32_t tries = 0;
    uint64_t t0 = 0;
    uint64_t t1 = 0;
    uint64_t t2 = 0;
    bool seen = false;
    uint32_t phase = 0;
    std::string status = "idle";
};

extern QueryAltitudeFn g_query_altitude_func;
extern VoidFn g_skip_cinematic_func;
extern VoidFn g_cancel_enter_challenge_mission_func;
extern MapTestState g_map_test_state;
void MapTestStep0();
void MapTestSetPhase(uint32_t phase, const char* status_text);

int QueryAltitude(const GamePos& pos, float radius, float& altitude, Vec3f* terrain_normal) {
    if (!g_query_altitude_func) {
        return 0;
    }
    return g_query_altitude_func(&pos, radius, &altitude, terrain_normal);
}

bool GetIsMapLoaded() {
    auto* game = Context::GetGameContext();
    return game && game->map != nullptr;
}

GW::Constants::MapID GetMapID() {
    auto* character = Context::GetCharContext();
    return character ? character->current_map_id : GW::Constants::MapID::Longeyes_Ledge_outpost;
}

bool GetIsMapUnlocked(GW::Constants::MapID map_id) {
    auto* world = Context::GetWorldContext();
    auto* unlocked_map = world && world->unlocked_map.valid() ? &world->unlocked_map : nullptr;
    if (!unlocked_map) {
        return false;
    }

    const uint32_t real_index = static_cast<uint32_t>(map_id) / 32U;
    if (real_index >= unlocked_map->size()) {
        return false;
    }
    const uint32_t shift = static_cast<uint32_t>(map_id) % 32U;
    const uint32_t flag = 1U << shift;
    return (unlocked_map->at(real_index) & flag) != 0;
}

GW::Constants::ServerRegion GetRegion() {
    auto* region_id = Context::GetRegionIdPtr();
    return region_id ? *region_id : GW::Constants::ServerRegion::Unknown;
}

uintptr_t GetServerRegionPtr() {
    return reinterpret_cast<uintptr_t>(Context::GetRegionIdPtr());
}

Context::MapTypeInstanceInfo* GetMapTypeInstanceInfo(Constants::RegionType map_type) {
    const bool is_outpost = !(map_type == Constants::RegionType::ExplorableZone ||
        map_type == Constants::RegionType::MissionArea ||
        map_type == Constants::RegionType::Dungeon);
    auto* infos = Context::GetMapTypeInstanceInfos();
    const auto count = Context::GetMapTypeInstanceInfosSize();
    for (size_t i = 0; infos && i < count; ++i) {
        if (infos[i].map_region_type == map_type &&
            infos[i].is_outpost == is_outpost) {
            return &infos[i];
        }
    }
    return nullptr;
}

GW::Constants::Language GetLanguage() {
    auto* character = Context::GetCharContext();
    return character ? character->language : GW::Constants::Language::English;
}

bool GetIsObserving() {
    auto* character = Context::GetCharContext();
    return character ? character->current_map_id != character->observe_map_id : false;
}

int GetDistrict() {
    auto* character = Context::GetCharContext();
    return character ? character->district_number : 0;
}

uint32_t GetInstanceTime() {
    auto* agent = Context::GetAgentContext();
    return agent ? agent->instance_timer : 0;
}

GW::Constants::InstanceType GetInstanceType() {
    const auto instance_info_ptr = Context::GetInstanceInfoPtr();
    auto* info = instance_info_ptr
        ? *reinterpret_cast<Context::InstanceInfo**>(instance_info_ptr)
        : nullptr;
    return info ? info->instance_type : GW::Constants::InstanceType::Loading;
}

GW::Constants::ServerRegion RegionFromDistrict(GW::Constants::District district) {
    switch (district) {
    case GW::Constants::District::International:
        return GW::Constants::ServerRegion::International;
    case GW::Constants::District::American:
        return GW::Constants::ServerRegion::America;
    case GW::Constants::District::EuropeEnglish:
    case GW::Constants::District::EuropeFrench:
    case GW::Constants::District::EuropeGerman:
    case GW::Constants::District::EuropeItalian:
    case GW::Constants::District::EuropeSpanish:
    case GW::Constants::District::EuropePolish:
    case GW::Constants::District::EuropeRussian:
        return GW::Constants::ServerRegion::Europe;
    case GW::Constants::District::AsiaKorean:
        return GW::Constants::ServerRegion::Korea;
    case GW::Constants::District::AsiaChinese:
        return GW::Constants::ServerRegion::China;
    case GW::Constants::District::AsiaJapanese:
        return GW::Constants::ServerRegion::Japan;
    default:
        break;
    }
    return GetRegion();
}

GW::Constants::Language LanguageFromDistrict(GW::Constants::District district) {
    switch (district) {
    case GW::Constants::District::EuropeFrench:
        return GW::Constants::Language::French;
    case GW::Constants::District::EuropeGerman:
        return GW::Constants::Language::German;
    case GW::Constants::District::EuropeItalian:
        return GW::Constants::Language::Italian;
    case GW::Constants::District::EuropeSpanish:
        return GW::Constants::Language::Spanish;
    case GW::Constants::District::EuropePolish:
        return GW::Constants::Language::Polish;
    case GW::Constants::District::EuropeRussian:
        return GW::Constants::Language::Russian;
    case GW::Constants::District::EuropeEnglish:
    case GW::Constants::District::AsiaKorean:
    case GW::Constants::District::AsiaChinese:
    case GW::Constants::District::AsiaJapanese:
    case GW::Constants::District::International:
    case GW::Constants::District::American:
        return GW::Constants::Language::English;
    default:
        break;
    }
    return GetLanguage();
}

Context::PathingMapArray* GetPathingMap() {
    auto* map_context = Context::GetMapContext();
    if (!(map_context && map_context->sub1 && map_context->sub1->sub2)) {
        return nullptr;
    }
    return &map_context->sub1->sub2->pmaps;
}

uint32_t GetFoesKilled() {
    auto* world = Context::GetWorldContext();
    return world ? world->foes_killed : 0;
}

uint32_t GetFoesToKill() {
    auto* world = Context::GetWorldContext();
    return world ? world->foes_to_kill : 0;
}

Context::AreaInfo* GetMapInfo(GW::Constants::MapID map_id) {
    if (map_id == GW::Constants::MapID::None) {
        map_id = GetMapID();
    }
    auto* area_info = Context::GetAreaInfoArray();
    return area_info &&
        map_id > GW::Constants::MapID::None &&
        map_id < GW::Constants::MapID::Count
        ? &area_info[static_cast<uint32_t>(map_id)]
        : nullptr;
}

uintptr_t GetInstanceInfoPtr() {
    return Context::GetInstanceInfoPtr();
}

bool GetIsInCinematic() {
    auto* game = Context::GetGameContext();
    return game && game->cinematic ? game->cinematic->h0004 != 0 : false;
}

bool SkipCinematic() {
    if (!g_skip_cinematic_func) {
        return false;
    }
    g_skip_cinematic_func();
    return true;
}

bool CancelEnterChallenge() {
    if (!g_cancel_enter_challenge_mission_func) {
        return false;
    }
    g_cancel_enter_challenge_mission_func();
    return true;
}

bool Travel(GW::Constants::MapID map_id, GW::Constants::ServerRegion region, int district_number, GW::Constants::Language language) {
    struct MapStruct {
        GW::Constants::MapID map_id;
        GW::Constants::ServerRegion region;
        GW::Constants::Language language;
        int district_number;
    };
    MapStruct t;
    t.map_id = map_id;
    t.district_number = district_number;
    t.region = region;
    t.language = language;
    return ui::SendUIMessage(ui::UIMessage::kTravel, &t);
}

bool Travel(GW::Constants::MapID map_id, GW::Constants::District district, int district_number) {
    return Travel(map_id, RegionFromDistrict(district), district_number, LanguageFromDistrict(district));
}

bool MapTestStart(uint32_t map_id, uint32_t alt_map_id, int number, uint32_t count, uint32_t delay_ms, uint32_t timeout_ms, uint32_t message_id) {
    if (!map_id || !alt_map_id) {
        return false;
    }
    g_map_test_state.active = true;
    g_map_test_state.map_id = map_id;
    g_map_test_state.alt_map_id = alt_map_id;
    g_map_test_state.number = number;
    g_map_test_state.count = count;
    g_map_test_state.delay_ms = delay_ms;
    g_map_test_state.timeout_ms = timeout_ms;
    g_map_test_state.message_id = message_id;
    g_map_test_state.tries = 0;
    MapTestSetPhase(0 /* kMtIdle */, "start");
    MapTestStep0();
    return true;
}

void MapTestStop() {
    g_map_test_state.active = false;
    MapTestSetPhase(6 /* kMtStop */, "stop");
}

const char* MapTestGetStatus() {
    return g_map_test_state.status.c_str();
}

bool MapTestIsActive() {
    return g_map_test_state.active;
}

uint32_t MapTestGetCount() {
    return g_map_test_state.tries;
}

bool EnterChallenge() {
    return ui::SendUIMessage(ui::UIMessage::kSendEnterMission, reinterpret_cast<void*>(static_cast<uintptr_t>(GW::Constants::MapID::Count)));
}

}  // namespace GW::map
