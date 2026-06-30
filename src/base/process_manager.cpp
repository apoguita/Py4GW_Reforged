#include "base/error_handling.h"

#include "base/process_manager.h"

namespace PY4GW::process_manager {

namespace {

HMODULE g_module_handle = nullptr;
std::filesystem::path g_module_path;

}

void SetModuleHandle(HMODULE module) {
    g_module_handle = module;
    g_module_path.clear();
    if (!g_module_handle) {
        return;
    }

    wchar_t buffer[MAX_PATH] = {};
    const DWORD length = ::GetModuleFileNameW(g_module_handle, buffer, MAX_PATH);
    if (length == 0 || length >= MAX_PATH) {
        return;
    }

    g_module_path = std::filesystem::path(buffer);
}

HMODULE GetModuleHandle() {
    return g_module_handle;
}

std::filesystem::path GetModulePath() {
    return g_module_path;
}

std::filesystem::path GetModuleDirectory() {
    return g_module_path.empty() ? std::filesystem::path{} : g_module_path.parent_path();
}

std::filesystem::path GetProcessDirectory() {
    wchar_t buffer[MAX_PATH] = {};
    const DWORD length = ::GetModuleFileNameW(nullptr, buffer, MAX_PATH);
    if (length == 0 || length >= MAX_PATH) {
        return {};
    }

    return std::filesystem::path(buffer).parent_path();
}

}  // namespace PY4GW::process_manager
