#include "base/error_handling.h"

#include "base/CrashHandler.h"
#include "base/memory_patcher.h"
#include "base/patterns.h"

#include "GW/map/map.h"

namespace GW::Context {
extern GW::Constants::ServerRegion* g_region_id_addr;
extern AreaInfo* g_area_info_addr;
extern MapTypeInstanceInfo* g_map_type_instance_infos;
extern uint32_t g_map_type_instance_infos_size;
extern uintptr_t g_instance_info_ptr;
extern InstanceInfo* g_instance_info;
}

namespace GW::map {

using QueryAltitudeFn = int(__cdecl*)(const GamePos* point, float radius, float* altitude, Vec3f* terrain_normal);
using VoidFn = void(__cdecl*)();
using DoActionFn = void(__cdecl*)(uint32_t);

extern QueryAltitudeFn g_query_altitude_func;
extern VoidFn g_skip_cinematic_func;
extern VoidFn g_cancel_enter_challenge_mission_func;
extern DoActionFn g_enter_challenge_mission_func;
extern PY4GW::MemoryPatcher g_bypass_tolerance_patch;

bool ResolveSkipCinematic() {
    CrashContextScope context("startup", "map", "resolve_skip_cinematic");
    return PY4GW::Patterns::Resolve("map.skip_cinematic_func", &g_skip_cinematic_func);
}

bool ResolveRegionId() {
    CrashContextScope context("startup", "map", "resolve_region_id");
    return PY4GW::Patterns::Resolve("map.region_id_addr", &Context::g_region_id_addr);
}

bool ResolveAreaInfo() {
    CrashContextScope context("startup", "map", "resolve_area_info");
    return PY4GW::Patterns::Resolve("map.area_info_addr", &Context::g_area_info_addr);
}

bool ResolveInstanceInfo() {
    CrashContextScope context("startup", "map", "resolve_instance_info");
    Context::g_instance_info_ptr = 0;
    return PY4GW::Patterns::Resolve("map.instance_info_addr", &Context::g_instance_info) &&
        PY4GW::Patterns::Resolve("map.instance_info_ptr_ref", &Context::g_instance_info_ptr);
}

bool ResolveQueryAltitude() {
    CrashContextScope context("startup", "map", "resolve_query_altitude");
    return PY4GW::Patterns::Resolve("map.query_altitude_func", &g_query_altitude_func);
}

bool ResolveBypassTolerancePatch() {
    CrashContextScope context("startup", "map", "resolve_bypass_tolerance_patch");
    uintptr_t address = 0;
    if (!PY4GW::Patterns::Resolve("map.bypass_tolerance_patch_addr", &address)) {
        return false;
    }

    static constexpr char patch[] = "\xEB";
    g_bypass_tolerance_patch.SetPatch(address, patch, 1);
    return g_bypass_tolerance_patch.IsValid();
}

bool ResolveEnterChallengeFunctions() {
    CrashContextScope context("startup", "map", "resolve_enter_challenge_functions");
    return PY4GW::Patterns::Resolve("map.cancel_enter_challenge_mission_func", &g_cancel_enter_challenge_mission_func) &&
        PY4GW::Patterns::Resolve("map.enter_challenge_mission_func", &g_enter_challenge_mission_func);
}

bool ResolveMapTypeInstanceInfos() {
    CrashContextScope context("startup", "map", "resolve_map_type_instance_infos");
    return PY4GW::Patterns::Resolve("map.map_type_instance_infos_size", &Context::g_map_type_instance_infos_size) &&
        PY4GW::Patterns::Resolve("map.map_type_instance_infos_ptr", &Context::g_map_type_instance_infos);
}

}  // namespace GW::map
