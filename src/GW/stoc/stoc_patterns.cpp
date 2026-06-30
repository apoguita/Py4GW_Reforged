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

extern uintptr_t g_handler_table_addr;
extern StoCHandlerArray* g_game_server_handlers;

bool ResolveGameServerHandlers() {
    CrashContextScope context("startup", "stoc", "resolve_game_server_handlers");
    if (!PY4GW::Patterns::Resolve("stoc.handler_table_addr", &g_handler_table_addr)) {
        return false;
    }

    auto** game_server = reinterpret_cast<GameServer**>(g_handler_table_addr);
    if (!(game_server && *game_server && (*game_server)->gs_codec)) {
        Logger::Instance().LogError("Game server handler table is not fully initialized.", "stoc");
        return false;
    }

    g_game_server_handlers = &(*game_server)->gs_codec->handlers;
    return g_game_server_handlers != nullptr;
}

}  // namespace GW::StoC
