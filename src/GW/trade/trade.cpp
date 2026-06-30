#include "base/error_handling.h"

#include "GW/trade/trade.h"

#include "base/CrashHandler.h"
#include "base/logger.h"

#include <atomic>

namespace GW::trade {

std::atomic<bool> g_initialized = false;

bool Initialize() {
    CrashContextScope context("startup", "trade", "initialize");
    if (g_initialized) {
        return true;
    }
    Logger::Instance().LogInfo("[trade] Trade module initialized.");
    g_initialized = true;
    return true;
}

void Shutdown() {
    CrashContextScope context("shutdown", "trade", "shutdown");
    if (!g_initialized) {
        return;
    }
    Logger::Instance().LogInfo("[trade] Trade module shutdown.");
    g_initialized = false;
}

}  // namespace GW::trade
