#include "base/error_handling.h"

#include "GW/guild/guild.h"

#include <atomic>

namespace GW::guild {

std::atomic<bool> g_initialized = false;

bool Initialize() {
    if (g_initialized) {
        return true;
    }
    g_initialized = true;
    return true;
}

void Shutdown() {
    g_initialized = false;
}

}  // namespace GW::guild
