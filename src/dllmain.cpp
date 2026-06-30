#include "base/error_handling.h"

#include "Py4GW.h"
#include "base/CrashHandler.h"
#include "base/logger.h"
#include "base/process_manager.h"

#include <string_view>
#include <windows.h>

namespace {

void AppendDetachMessage() {
    const auto log_path = PY4GW::process_manager::GetProcessDirectory() / "Py4GW_injection_log.txt";
    if (log_path.empty()) {
        return;
    }

    HANDLE file = ::CreateFileW(
        log_path.c_str(),
        FILE_APPEND_DATA,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        nullptr,
        OPEN_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,
        nullptr);
    if (file == INVALID_HANDLE_VALUE) {
        return;
    }

    constexpr std::string_view message = "[Py4GW] [INFO] process detached\r\n";
    DWORD written = 0;
    ::WriteFile(file, message.data(), static_cast<DWORD>(message.size()), &written, nullptr);
    ::CloseHandle(file);
}

}

BOOL APIENTRY DllMain(HMODULE module, DWORD reason, LPVOID reserved) {
    switch (reason) {
    case DLL_PROCESS_ATTACH: {
        ::DisableThreadLibraryCalls(module);
        PY4GW::process_manager::SetModuleHandle(module);
        HANDLE thread_handle = ::CreateThread(nullptr, 0, &PY4GW::RuntimeThread, nullptr, 0, nullptr);
        if (thread_handle != nullptr) {
            ::CloseHandle(thread_handle);
        } else {
            Logger::Instance().SetLogFile("Py4GW_injection_log.txt");
            Logger::Instance().LogError("Unable to create main thread.");
        }
        break;
    }
    case DLL_PROCESS_DETACH:
        AppendDetachMessage();
        if (reserved == nullptr) {
            Py4GW_Shutdown();
            CrashHandler::Instance().Terminate();
        }
        break;
    default:
        break;
    }
    return TRUE;
}
