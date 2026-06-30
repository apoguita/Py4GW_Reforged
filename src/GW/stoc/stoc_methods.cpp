#include "base/error_handling.h"

#include "GW/stoc/stoc.h"

namespace GW::StoC {

using StoCHandlerFn = bool(__cdecl*)(Packet::StoC::PacketBase* packet);

struct StoCHandler {
    uint32_t* packet_template = nullptr;
    uint32_t template_size = 0;
    StoCHandlerFn handler_func = nullptr;
};

using StoCHandlerArray = GW::GWArray<StoCHandler>;

struct CallbackEntry {
    int altitude = 0;
    PY4GW::HookEntry* entry = nullptr;
    PacketCallback callback;
};

extern CRITICAL_SECTION g_mutex;
extern bool g_mutex_initialized;
extern StoCHandlerArray* g_game_server_handlers;
extern std::vector<std::vector<CallbackEntry>> g_packet_entries;

void SafeInitializeCriticalSection(CRITICAL_SECTION* mtx);
bool __cdecl StoCHandler_Func(Packet::StoC::PacketBase* packet);
bool OriginalHandler(Packet::StoC::PacketBase* packet);

bool RegisterPacketCallback(
    PY4GW::HookEntry* entry,
    uint32_t header,
    const PacketCallback& callback,
    int altitude) {
    bool success = false;
    SafeInitializeCriticalSection(&g_mutex);

    ::EnterCriticalSection(&g_mutex);
    RemoveCallback(header, entry);
    if (g_packet_entries.size() <= header) {
        g_packet_entries.resize(header + 1);
    }

    auto it = g_packet_entries[header].begin();
    while (it != g_packet_entries[header].end()) {
        if (it->altitude > altitude) {
            break;
        }
        ++it;
    }
    g_packet_entries[header].insert(it, CallbackEntry{altitude, entry, callback});

    if (g_game_server_handlers && g_game_server_handlers->size() > header) {
        g_game_server_handlers->at(header).handler_func = &StoCHandler_Func;
        success = true;
    }
    ::LeaveCriticalSection(&g_mutex);
    return success;
}

bool RegisterPostPacketCallback(
    PY4GW::HookEntry* entry,
    uint32_t header,
    const PacketCallback& callback) {
    return RegisterPacketCallback(entry, header, callback, 0x8000);
}

size_t RemoveCallback(uint32_t header, PY4GW::HookEntry* entry) {
    size_t removed = 0;
    SafeInitializeCriticalSection(&g_mutex);
    ::EnterCriticalSection(&g_mutex);
    if (header < g_packet_entries.size()) {
        auto it = g_packet_entries[header].begin();
        while (it != g_packet_entries[header].end()) {
            if (it->entry == entry) {
                g_packet_entries[header].erase(it);
                ++removed;
                break;
            }
            ++it;
        }
    }
    ::LeaveCriticalSection(&g_mutex);
    return removed;
}

size_t RemoveCallbacks(PY4GW::HookEntry* entry) {
    size_t removed = 0;
    SafeInitializeCriticalSection(&g_mutex);
    ::EnterCriticalSection(&g_mutex);
    for (auto& header_entries : g_packet_entries) {
        auto it = header_entries.begin();
        while (it != header_entries.end()) {
            if (it->entry == entry) {
                it = header_entries.erase(it);
                ++removed;
            } else {
                ++it;
            }
        }
    }
    ::LeaveCriticalSection(&g_mutex);
    return removed;
}

void RemovePostCallback(uint32_t header, PY4GW::HookEntry* entry) {
    RemoveCallback(header, entry);
}

bool EmulatePacket(Packet::StoC::PacketBase* packet) {
    return OriginalHandler(packet);
}

}  // namespace GW::StoC
