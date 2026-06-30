#include "base/error_handling.h"

#include "GW/map/map.h"

#include "base/CrashHandler.h"
#include "base/hooker.h"
#include "base/hook_types.h"
#include "base/logger.h"
#include "base/memory_patcher.h"
#include "GW/game_thread/game_thread.h"
#include "GW/ui/ui.h"

#include <atomic>
#include <string>

namespace GW::Context {
extern GW::Constants::ServerRegion* g_region_id_addr;
extern AreaInfo* g_area_info_addr;
extern MapTypeInstanceInfo* g_map_type_instance_infos;
extern uint32_t g_map_type_instance_infos_size;
extern uintptr_t g_instance_info_ptr;
extern InstanceInfo* g_instance_info;
extern WorldMapContext* g_world_map_context;
extern MissionMapContext* g_mission_map_context;
}

namespace GW::map {

using QueryAltitudeFn = int(__cdecl*)(const GamePos* point, float radius, float* altitude, Vec3f* terrain_normal);
using VoidFn = void(__cdecl*)();
using DoActionFn = void(__cdecl*)(uint32_t);

bool ResolveSkipCinematic();
bool ResolveRegionId();
bool ResolveAreaInfo();
bool ResolveInstanceInfo();
bool ResolveQueryAltitude();
bool ResolveBypassTolerancePatch();
bool ResolveEnterChallengeFunctions();
bool ResolveMapTypeInstanceInfos();

bool Init();
void EnableHooks();
void DisableHooks();
void Exit();

void OnEnterChallengeMission_Hook(uint32_t identifier);
void OnEnterChallengeMission_UIMessage(PY4GW::HookStatus* status, ui::UIMessage msg_id, void* wparam, void*);

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

QueryAltitudeFn g_query_altitude_func = nullptr;
VoidFn g_skip_cinematic_func = nullptr;
VoidFn g_cancel_enter_challenge_mission_func = nullptr;
DoActionFn g_enter_challenge_mission_func = nullptr;
DoActionFn g_enter_challenge_mission_original = nullptr;
PY4GW::MemoryPatcher g_bypass_tolerance_patch;
PY4GW::HookEntry g_enter_challenge_mission_hook_entry;
std::atomic<bool> g_initialized = false;
MapTestState g_map_test_state;

namespace {
    ui::UIInteractionCallback world_map_ui_callback_func = nullptr;
    ui::UIInteractionCallback world_map_ui_callback_ret = nullptr;

    void OnWorldMap_UICallback(ui::InteractionMessage* message, void* wParam, void* lParam) {
        world_map_ui_callback_ret(message, wParam, lParam);
        if (message && message->wParam) {
            Context::g_world_map_context = *reinterpret_cast<Context::WorldMapContext**>(message->wParam);
        }
        if (message && message->message_id == ui::UIMessage::kDestroyFrame) {
            Context::g_world_map_context = nullptr;
        }
    }

    ui::UIInteractionCallback mission_map_ui_callback_func = nullptr;
    ui::UIInteractionCallback mission_map_ui_callback_ret = nullptr;

    void OnMissionMap_UICallback(ui::InteractionMessage* message, void* wParam, void* lParam) {
        mission_map_ui_callback_ret(message, wParam, lParam);
        if (message && message->wParam) {
            Context::g_mission_map_context = *reinterpret_cast<Context::MissionMapContext**>(message->wParam);
        }
        if (message && message->message_id == ui::UIMessage::kDestroyFrame) {
            Context::g_mission_map_context = nullptr;
        }
    }

    static constexpr uint32_t kMtIdle = 0;
    static constexpr uint32_t kMtWait0 = 1;
    static constexpr uint32_t kMtWait1 = 2;
    static constexpr uint32_t kMtRun = 3;
    static constexpr uint32_t kMtWait2 = 4;
    static constexpr uint32_t kMtDone = 5;
    static constexpr uint32_t kMtStop = 6;

    PY4GW::HookEntry mt_ui_entry;
    PY4GW::HookEntry mt_tick_entry;

    void mt_set(uint32_t phase, const char* status_text) {
        g_map_test_state.phase = phase;
        g_map_test_state.status = status_text;
    }

    bool mt_loading() {
        return GW::map::GetInstanceType() == GW::Constants::InstanceType::Loading;
    }

    bool SendTravelPacket(uint32_t map_id, uint32_t region, int district_number, uint32_t language) {
        struct MapStruct {
            uint32_t map_id;
            uint32_t region;
            uint32_t language;
            int district_number;
        } packet;
        packet.map_id = map_id;
        packet.region = region;
        packet.language = language;
        packet.district_number = district_number;
        return ui::SendUIMessage(ui::UIMessage::kTravel, &packet);
    }

    void mt_step1() {
        for (uint32_t i = 0; i < g_map_test_state.count; ++i) {
            SendTravelPacket(g_map_test_state.alt_map_id, 0, g_map_test_state.number, 0);
        }
        g_map_test_state.t1 = GetTickCount64();
        g_map_test_state.t2 = 0;
        g_map_test_state.seen = false;
        mt_set(kMtRun, "run");
    }

    void mt_step0() {
        g_map_test_state.tries += 1;
        g_map_test_state.t0 = 0;
        g_map_test_state.t1 = 0;
        g_map_test_state.t2 = 0;
        g_map_test_state.seen = false;
        SendTravelPacket(
            g_map_test_state.map_id,
            static_cast<uint32_t>(GW::map::GetRegion()),
            0,
            static_cast<uint32_t>(GW::map::GetLanguage()));
        mt_set(kMtWait0, "wait0");
    }

    bool mt_read(uint32_t message_id, void* wparam, uint32_t* out_map_id) {
        if (!wparam || !out_map_id) {
            return false;
        }
        if (message_id == static_cast<uint32_t>(ui::UIMessage::kLoadMapContext)) {
            if (IsBadReadPtr(wparam, 8)) {
                return false;
            }
            *out_map_id = *reinterpret_cast<uint32_t*>(static_cast<uint8_t*>(wparam) + 4);
            return true;
        }
        if (message_id == static_cast<uint32_t>(ui::UIMessage::kStartMapLoad)) {
            if (IsBadReadPtr(wparam, 4)) {
                return false;
            }
            *out_map_id = *reinterpret_cast<uint32_t*>(wparam);
            return true;
        }
        return false;
    }

    bool mt_match(uint32_t message_id) {
        const uint32_t configured = g_map_test_state.message_id;
        if (message_id == configured) {
            return true;
        }
        return configured == static_cast<uint32_t>(ui::UIMessage::kStartMapLoad)
            && message_id == static_cast<uint32_t>(ui::UIMessage::kLoadMapContext);
    }

    void OnMapTestUIMessage(PY4GW::HookStatus* status, ui::UIMessage message_id, void* wparam, void*) {
        const uint32_t msg = static_cast<uint32_t>(message_id);
        if (status->blocked || !g_map_test_state.active) {
            return;
        }
        if (!mt_match(msg)) {
            return;
        }
        if (g_map_test_state.phase != kMtWait0) {
            return;
        }

        uint32_t anchor_map_id = 0;
        if (!mt_read(msg, wparam, &anchor_map_id)) {
            return;
        }
        if (anchor_map_id != g_map_test_state.map_id) {
            return;
        }

        g_map_test_state.t0 = GetTickCount64();
        mt_set(kMtWait1, "wait1");
    }

    void OnMapTestTick(PY4GW::HookStatus*) {
        if (!g_map_test_state.active) {
            return;
        }

        const uint64_t now = GetTickCount64();
        switch (g_map_test_state.phase) {
        case kMtWait1:
            if (now - g_map_test_state.t0 < g_map_test_state.delay_ms) {
                return;
            }
            mt_step1();
            return;
        case kMtRun: {
            const uint32_t current_map = static_cast<uint32_t>(GW::map::GetMapID());
            const bool is_loading = mt_loading();
            if (current_map == g_map_test_state.map_id && !is_loading) {
                g_map_test_state.seen = true;
            }
            if (current_map != g_map_test_state.map_id && !is_loading) {
                g_map_test_state.t2 = 0;
                mt_set(kMtWait2, "wait2");
                return;
            }
            if (now - g_map_test_state.t1 <= g_map_test_state.timeout_ms) {
                return;
            }
            if (g_map_test_state.seen && current_map == g_map_test_state.map_id && !is_loading) {
                g_map_test_state.active = false;
                mt_set(kMtDone, "done");
                return;
            }
            g_map_test_state.t2 = 0;
            mt_set(kMtWait2, "wait2");
            return;
        }
        case kMtWait2:
            if (mt_loading()) {
                return;
            }
            if (!g_map_test_state.t2) {
                g_map_test_state.t2 = now;
                return;
            }
            if (now - g_map_test_state.t2 < 100) {
                return;
            }
            mt_step0();
            return;
        default:
            return;
        }
    }

    bool ResolveMissionMapUICallback() {
        CrashContextScope context("startup", "map", "resolve_mission_map_ui_callback");
        return PY4GW::Patterns::Resolve("map.mission_map_ui_callback_func", &mission_map_ui_callback_func);
    }

    bool ResolveWorldMapUICallback() {
        CrashContextScope context("startup", "map", "resolve_world_map_ui_callback");
        return PY4GW::Patterns::Resolve("map.world_map_ui_callback_func", &world_map_ui_callback_func);
    }
}  // namespace

void OnEnterChallengeMission_Hook(uint32_t identifier) {
    PY4GW::HookBase::EnterHook();
    ui::SendUIMessage(ui::UIMessage::kSendEnterMission, reinterpret_cast<void*>(static_cast<uintptr_t>(identifier)));
    PY4GW::HookBase::LeaveHook();
}

void OnEnterChallengeMission_UIMessage(PY4GW::HookStatus* status, ui::UIMessage msg_id, void* wparam, void*) {
    if (status && status->blocked) {
        return;
    }
    if (g_enter_challenge_mission_original && wparam) {
        g_enter_challenge_mission_original(static_cast<uint32_t>(reinterpret_cast<uintptr_t>(wparam)));
    }
}

void MapTestStep0() {
    mt_step0();
}

void MapTestSetPhase(uint32_t phase, const char* status_text) {
    mt_set(phase, status_text);
}

bool Init() {
    CrashContextScope context("startup", "map", "init");
    if (!(ResolveSkipCinematic() &&
        ResolveRegionId() &&
        ResolveAreaInfo() &&
        ResolveInstanceInfo() &&
        ResolveQueryAltitude() &&
        ResolveBypassTolerancePatch() &&
        ResolveEnterChallengeFunctions() &&
        ResolveMapTypeInstanceInfos() &&
        ResolveMissionMapUICallback() &&
        ResolveWorldMapUICallback())) {
        return false;
    }

    if (g_enter_challenge_mission_func) {
        PY4GW::HookBase::CreateHook(
            reinterpret_cast<void**>(&g_enter_challenge_mission_func),
            reinterpret_cast<void*>(&OnEnterChallengeMission_Hook),
            reinterpret_cast<void**>(&g_enter_challenge_mission_original));
        ui::RegisterUIMessageCallback(
            &g_enter_challenge_mission_hook_entry,
            ui::UIMessage::kSendEnterMission,
            OnEnterChallengeMission_UIMessage,
            0x1);
    }

    return true;
}

void EnableHooks() {
    if (world_map_ui_callback_func) {
        PY4GW::HookBase::CreateHook(
            reinterpret_cast<void**>(&world_map_ui_callback_func),
            reinterpret_cast<void*>(&OnWorldMap_UICallback),
            reinterpret_cast<void**>(&world_map_ui_callback_ret));
        PY4GW::HookBase::EnableHooks(reinterpret_cast<void*>(world_map_ui_callback_func));
    }
    if (mission_map_ui_callback_func) {
        PY4GW::HookBase::CreateHook(
            reinterpret_cast<void**>(&mission_map_ui_callback_func),
            reinterpret_cast<void*>(&OnMissionMap_UICallback),
            reinterpret_cast<void**>(&mission_map_ui_callback_ret));
        PY4GW::HookBase::EnableHooks(reinterpret_cast<void*>(mission_map_ui_callback_func));
    }
    ui::RegisterUIMessageCallback(&mt_ui_entry, ui::UIMessage::kLoadMapContext, OnMapTestUIMessage, 0x1);
    ui::RegisterUIMessageCallback(&mt_ui_entry, ui::UIMessage::kStartMapLoad, OnMapTestUIMessage, 0x1);
    game_thread::RegisterGameThreadCallback(&mt_tick_entry, OnMapTestTick, 0x1);
    if (g_enter_challenge_mission_func) {
        PY4GW::HookBase::EnableHooks(reinterpret_cast<void*>(g_enter_challenge_mission_func));
    }
    if (g_bypass_tolerance_patch.IsValid()) {
        g_bypass_tolerance_patch.TogglePatch(true);
    }
}

void DisableHooks() {
    if (world_map_ui_callback_func) {
        PY4GW::HookBase::DisableHooks(reinterpret_cast<void*>(world_map_ui_callback_func));
    }
    if (mission_map_ui_callback_func) {
        PY4GW::HookBase::DisableHooks(reinterpret_cast<void*>(mission_map_ui_callback_func));
    }
    ui::RemoveUIMessageCallback(&mt_ui_entry, ui::UIMessage::kLoadMapContext);
    ui::RemoveUIMessageCallback(&mt_ui_entry, ui::UIMessage::kStartMapLoad);
    game_thread::RemoveGameThreadCallback(&mt_tick_entry);
    if (g_enter_challenge_mission_func) {
        PY4GW::HookBase::DisableHooks(reinterpret_cast<void*>(g_enter_challenge_mission_func));
    }
    if (g_bypass_tolerance_patch.IsValid()) {
        g_bypass_tolerance_patch.TogglePatch(false);
    }
}

void Exit() {
    CrashContextScope context("shutdown", "map", "exit");
    ui::RemoveUIMessageCallback(&mt_ui_entry, ui::UIMessage::kLoadMapContext);
    ui::RemoveUIMessageCallback(&mt_ui_entry, ui::UIMessage::kStartMapLoad);
    ui::RemoveUIMessageCallback(&g_enter_challenge_mission_hook_entry, ui::UIMessage::kSendEnterMission);
    game_thread::RemoveGameThreadCallback(&mt_tick_entry);
    if (world_map_ui_callback_func) {
        PY4GW::HookBase::RemoveHook(reinterpret_cast<void*>(world_map_ui_callback_func));
    }
    if (mission_map_ui_callback_func) {
        PY4GW::HookBase::RemoveHook(reinterpret_cast<void*>(mission_map_ui_callback_func));
    }
    if (g_enter_challenge_mission_func) {
        PY4GW::HookBase::RemoveHook(reinterpret_cast<void*>(g_enter_challenge_mission_func));
    }
    g_bypass_tolerance_patch.TogglePatch(false);
    g_bypass_tolerance_patch.Reset();
    world_map_ui_callback_func = nullptr;
    world_map_ui_callback_ret = nullptr;
    mission_map_ui_callback_func = nullptr;
    mission_map_ui_callback_ret = nullptr;
    Context::g_world_map_context = nullptr;
    Context::g_mission_map_context = nullptr;
    Context::g_instance_info = nullptr;
    g_skip_cinematic_func = nullptr;
    g_cancel_enter_challenge_mission_func = nullptr;
    g_enter_challenge_mission_func = nullptr;
    g_enter_challenge_mission_original = nullptr;
    g_query_altitude_func = nullptr;
    Context::g_region_id_addr = nullptr;
    Context::g_area_info_addr = nullptr;
    Context::g_map_type_instance_infos = nullptr;
    Context::g_map_type_instance_infos_size = 0;
    Context::g_instance_info_ptr = 0;
}

bool Initialize() {
    CrashContextScope context("startup", "map", "initialize");
    if (g_initialized) {
        return true;
    }

    PY4GW_ASSERT(PY4GW::Scanner::Initialize());
    PY4GW_ASSERT(PY4GW::Patterns::Initialize());

    if (!Init()) {
        Exit();
        return false;
    }

    EnableHooks();
    g_initialized = true;
    return true;
}

void Shutdown() {
    CrashContextScope context("shutdown", "map", "shutdown");
    if (!g_initialized) {
        return;
    }

    DisableHooks();
    Exit();
    g_initialized = false;
}

}  // namespace GW::map
