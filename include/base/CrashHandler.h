#pragma once

#include "base/error_handling.h"

#include <array>
#include <string>
#include <windows.h>

struct CrashContextSnapshot {
    std::array<char, 64> phase{};
    std::array<char, 64> module{};
    std::array<char, 128> operation{};
    std::array<char, 256> detail{};
};

class CrashContextScope {
public:
    CrashContextScope(const char* phase, const char* module, const char* operation, const char* detail = nullptr);
    ~CrashContextScope();

    CrashContextScope(const CrashContextScope&) = delete;
    CrashContextScope& operator=(const CrashContextScope&) = delete;

private:
    CrashContextSnapshot snapshot_{};
};

class CrashHandler {
public:
    static CrashHandler& Instance();

    static void SetContext(const char* phase, const char* module, const char* operation, const char* detail = nullptr);
    static void ClearContext();
    static CrashContextSnapshot CaptureContext();
    static void RestoreContext(const CrashContextSnapshot& snapshot);

    void Initialize();
    void Terminate();
    void SetDumpGenerationEnabled(bool enabled);
    bool IsDumpGenerationEnabled() const;

    bool OnException(EXCEPTION_POINTERS* info, const char* source, bool recoverable);
    std::string CrashDirUtf8() const;

private:
    CrashHandler() = default;
    CrashHandler(const CrashHandler&) = delete;
    CrashHandler& operator=(const CrashHandler&) = delete;

    static LONG WINAPI TopLevelFilter(EXCEPTION_POINTERS* info);
    static LONG WINAPI VectoredHandler(EXCEPTION_POINTERS* info);
    static void OnPanic(void* context, const char* expr, const char* message,
                        const char* file, unsigned int line, const char* function);
    static uintptr_t __cdecl AppendStackDetour(void* debug_info, uint32_t a2, uint32_t a3,
                                               uint32_t a4, CONTEXT* ctx, uint32_t a6,
                                               uint32_t a7);

    void InstallPathA();
    void InstallPathC();
    void ClearCallbackFilterPolicy();
    void RestoreCallbackFilterPolicy();
    bool EnsureCrashDir();
    void WriteSidecar(EXCEPTION_POINTERS* info, const wchar_t* json_path,
                      const wchar_t* dmp_name, const wchar_t* gwtext_name,
                      const wchar_t* stack_name, const char* source, bool dump_generated);
    void WriteDump(EXCEPTION_POINTERS* info, const wchar_t* dmp_path, const char* comment);
    void WriteStackTrace(EXCEPTION_POINTERS* info, const wchar_t* stack_path);
};
