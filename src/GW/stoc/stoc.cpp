#include "base/error_handling.h"

#include "GW/stoc/stoc.h"

#include "base/CrashHandler.h"
#include "base/hooker.h"
#include "base/logger.h"
#include "base/patterns.h"
#include "base/scanner.h"
#include "GW/game_thread/game_thread.h"

#include <string>

namespace GW::StoC {

using StoCHandlerFn = bool(__cdecl*)(Packet::StoC::PacketBase* packet);

struct StoCHandler {
    uint32_t* packet_template = nullptr;
    uint32_t template_size = 0;
    StoCHandlerFn handler_func = nullptr;
};

using StoCHandlerArray = GW::GWArray<StoCHandler>;

struct GameServer {
    uint8_t h0000[8];
    struct {
        uint8_t h0000[12];
        struct {
            uint8_t h0000[12];
            void* next;
            uint8_t h0010[12];
            uint32_t client_codec_array[4];
            StoCHandlerArray handlers;
        }* ls_codec;
        uint8_t h0010[12];
        uint32_t client_codec_array[4];
        StoCHandlerArray handlers;
    }* gs_codec;
};

struct CallbackEntry {
    int altitude = 0;
    PY4GW::HookEntry* entry = nullptr;
    PacketCallback callback;
};

CRITICAL_SECTION g_mutex;
bool g_mutex_initialized = false;
bool g_hooks_enabled = false;
std::atomic<bool> g_initialized = false;
size_t g_stoc_handler_count = 0;
uintptr_t g_handler_table_addr = 0;
StoCHandlerArray* g_game_server_handlers = nullptr;
StoCHandler* g_original_functions = nullptr;
std::vector<std::vector<CallbackEntry>> g_packet_entries;

bool ResolveGameServerHandlers();
void SafeInitializeCriticalSection(CRITICAL_SECTION* mtx);
bool __cdecl StoCHandler_Func(Packet::StoC::PacketBase* packet);
bool OriginalHandler(Packet::StoC::PacketBase* packet);
void EnableHooks();
void DisableHooks();
void Init();
void Exit();

void SafeInitializeCriticalSection(CRITICAL_SECTION* mtx) {
    if (!mtx || mtx->DebugInfo) {
        return;
    }
    ::InitializeCriticalSection(&g_mutex);
    g_mutex_initialized = true;
}

bool __cdecl StoCHandler_Func(Packet::StoC::PacketBase* packet) {
    PY4GW::HookBase::EnterHook();
    PY4GW::HookStatus status = {};

    auto it = g_packet_entries[packet->header].begin();
    const auto end = g_packet_entries[packet->header].end();
    while (it != end) {
        if (it->altitude > 0) {
            break;
        }
        it->callback(&status, packet);
        ++status.altitude;
        ++it;
    }

    if (!status.blocked && g_original_functions) {
        g_original_functions[packet->header].handler_func(packet);
    }

    while (it != end) {
        it->callback(&status, packet);
        ++status.altitude;
        ++it;
    }

    PY4GW::HookBase::LeaveHook();
    return true;
}

bool OriginalHandler(Packet::StoC::PacketBase* packet) {
    bool ok = false;
    SafeInitializeCriticalSection(&g_mutex);
    ::EnterCriticalSection(&g_mutex);
    if (g_game_server_handlers &&
        g_original_functions &&
        g_stoc_handler_count > packet->header) {
        g_original_functions[packet->header].handler_func(packet);
    }
    ::LeaveCriticalSection(&g_mutex);
    return ok;
}

void EnableHooks() {
    ::EnterCriticalSection(&g_mutex);
    g_hooks_enabled = true;
    for (uint32_t i = 0; g_original_functions && i < g_stoc_handler_count; ++i) {
        g_original_functions[i] = g_game_server_handlers->at(i);
        if (!g_packet_entries[i].empty()) {
            g_game_server_handlers->at(i).handler_func = &StoCHandler_Func;
        }
    }
    ::LeaveCriticalSection(&g_mutex);
}

void DisableHooks() {
    CrashContextScope context("shutdown", "stoc", "disable_hooks");
    ::EnterCriticalSection(&g_mutex);
    g_hooks_enabled = false;
    if (g_original_functions) {
        for (uint32_t i = 0; g_game_server_handlers && i < g_game_server_handlers->size(); ++i) {
            g_game_server_handlers->at(i).handler_func = g_original_functions[i].handler_func;
        }
    }
    ::LeaveCriticalSection(&g_mutex);
}

void Init() {
    CrashContextScope context("startup", "stoc", "init");
    SafeInitializeCriticalSection(&g_mutex);
    ::EnterCriticalSection(&g_mutex);

    if (!ResolveGameServerHandlers() || !g_game_server_handlers) {
        ::LeaveCriticalSection(&g_mutex);
        return;
    }

    g_stoc_handler_count = g_game_server_handlers->size();
    Logger::Instance().LogInfo("STOC_HEADER_COUNT [" + std::to_string(g_stoc_handler_count) + "]");
    PY4GW_ASSERT(g_stoc_handler_count == kStoCHeaderCount);

    if (!g_original_functions) {
        g_original_functions = new StoCHandler[g_stoc_handler_count];
        g_mutex_initialized = true;
    }
    g_packet_entries.resize(g_stoc_handler_count);

    EnableHooks();
    g_initialized = true;
    ::LeaveCriticalSection(&g_mutex);
}

void Exit() {
    CrashContextScope context("shutdown", "stoc", "exit");
    DisableHooks();

    delete[] g_original_functions;
    g_original_functions = nullptr;
    g_handler_table_addr = 0;
    g_game_server_handlers = nullptr;
    g_stoc_handler_count = 0;
    g_packet_entries.clear();

    if (g_mutex_initialized) {
        ::DeleteCriticalSection(&g_mutex);
        g_mutex_initialized = false;
    }
}

bool Initialize() {
    CrashContextScope context("startup", "stoc", "initialize");
    if (g_initialized) {
        return true;
    }

    PY4GW_ASSERT(PY4GW::Scanner::Initialize());
    PY4GW_ASSERT(PY4GW::Patterns::Initialize());

    SafeInitializeCriticalSection(&g_mutex);
    game_thread::Enqueue([] {
        Init();
    });
    return true;
}

void Shutdown() {
    CrashContextScope context("shutdown", "stoc", "shutdown");
    if (!g_mutex_initialized) {
        return;
    }

    Exit();
    g_initialized = false;
}

}  // namespace GW::StoC
