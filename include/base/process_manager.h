#pragma once

#include "base/error_handling.h"

#include <filesystem>
#include <windows.h>

namespace PY4GW::process_manager {

void SetModuleHandle(HMODULE module);
HMODULE GetModuleHandle();
std::filesystem::path GetModulePath();
std::filesystem::path GetModuleDirectory();
std::filesystem::path GetProcessDirectory();

}  // namespace PY4GW::process_manager
