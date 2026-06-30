#include "base/error_handling.h"

#include "base/CrashHandler.h"

#include "base/panic.h"
#include "base/hooker.h"
#include "base/process_manager.h"
#include "base/scanner.h"
#include "base/logger.h"

#include <DbgHelp.h>
#include <cstdio>
#include <cstring>

namespace {

volatile LONG s_handling = 0;
bool s_installed = false;
LPTOP_LEVEL_EXCEPTION_FILTER s_prev_filter = nullptr;
PVOID s_vectored_handler = nullptr;
uintptr_t s_append_stack_fn = 0;
void* s_append_stack_orig = nullptr;
bool s_symbols_ready = false;
DWORD s_prev_policy = 0;
bool s_policy_changed = false;
bool s_dump_generation_enabled = false;

wchar_t s_crash_dir[MAX_PATH] = {0};
bool s_crash_dir_ready = false;
std::string s_crash_dir_utf8;

char s_gw_text[32768] = {0};
char s_panic_expr[512] = {0};
char s_panic_message[1024] = {0};
char s_panic_file[260] = {0};
char s_panic_function[128] = {0};
unsigned int s_panic_line = 0;
char s_context_phase[64] = {0};
char s_context_module[64] = {0};
char s_context_operation[128] = {0};
char s_context_detail[256] = {0};

const char* ExceptionLabel(DWORD code) {
    switch (code) {
    case EXCEPTION_ACCESS_VIOLATION: return "access_violation";
    case EXCEPTION_STACK_OVERFLOW: return "stack_overflow";
    case EXCEPTION_ILLEGAL_INSTRUCTION: return "illegal_instruction";
    case EXCEPTION_INT_DIVIDE_BY_ZERO: return "int_divide_by_zero";
    case EXCEPTION_PRIV_INSTRUCTION: return "priv_instruction";
    case EXCEPTION_IN_PAGE_ERROR: return "in_page_error";
    case 0xC0000409: return "stack_buffer_overrun";
    case 0xE06D7363: return "cpp_exception";
    case 0x80000003: return "breakpoint";
    default: return "exception";
    }
}

const char* SourceLabel(const char* source) {
    if (!source) {
        return "unknown";
    }
    if (strcmp(source, "veh") == 0) {
        return "vectored_exception_handler";
    }
    if (strcmp(source, "seh") == 0) {
        return "structured_exception_handler";
    }
    if (strcmp(source, "gw_engine") == 0) {
        return "guild_wars_crash_handler";
    }
    if (strcmp(source, "panic") == 0) {
        return "py4gw_panic_handler";
    }
    return source;
}

bool ShouldWriteDumpForSource(const char* source) {
    if (!source) {
        return false;
    }
    return strcmp(source, "panic") == 0 || strcmp(source, "seh") == 0;
}

bool IsCrashCandidate(DWORD code) {
    switch (code) {
    case EXCEPTION_ACCESS_VIOLATION:
    case EXCEPTION_STACK_OVERFLOW:
    case EXCEPTION_ILLEGAL_INSTRUCTION:
    case EXCEPTION_INT_DIVIDE_BY_ZERO:
    case EXCEPTION_PRIV_INSTRUCTION:
    case EXCEPTION_IN_PAGE_ERROR:
    case 0xC0000409:
        return true;
    default:
        return false;
    }
}

struct JBuf {
    char* p;
    char* const e;
};

void JAppend(JBuf& buffer, const char* fmt, ...) {
    if (buffer.p >= buffer.e) {
        return;
    }
    va_list args;
    va_start(args, fmt);
    const int written = _vsnprintf_s(buffer.p, static_cast<size_t>(buffer.e - buffer.p), _TRUNCATE, fmt, args);
    va_end(args);
    buffer.p = written >= 0 ? buffer.p + written : buffer.e;
}

void JsonEscape(char* dst, size_t cap, const char* src) {
    if (cap == 0) {
        return;
    }
    size_t j = 0;
    for (size_t i = 0; src && src[i] && j + 2 < cap; ++i) {
        const unsigned char c = static_cast<unsigned char>(src[i]);
        if (c == '\\' || c == '"') {
            dst[j++] = '\\';
            dst[j++] = static_cast<char>(c);
        } else if (c == '\n') {
            dst[j++] = '\\';
            dst[j++] = 'n';
        } else if (c == '\r') {
            dst[j++] = '\\';
            dst[j++] = 'r';
        } else if (c == '\t') {
            dst[j++] = '\\';
            dst[j++] = 't';
        } else if (c >= 0x20) {
            dst[j++] = static_cast<char>(c);
        }
    }
    dst[j] = 0;
}

void MakeDirTree(const wchar_t* path) {
    wchar_t temp[MAX_PATH] = {};
    wcsncpy_s(temp, path, _TRUNCATE);
    for (wchar_t* p = temp + 3; *p; ++p) {
        if (*p == L'\\') {
            *p = 0;
            ::CreateDirectoryW(temp, nullptr);
            *p = L'\\';
        }
    }
    ::CreateDirectoryW(temp, nullptr);
}

void BuildReportFolder(wchar_t* out, size_t cap) {
    SYSTEMTIME time = {};
    ::GetLocalTime(&time);
    _snwprintf_s(
        out,
        cap,
        _TRUNCATE,
        L"%s\\py4gw-%04u%02u%02u-%02u%02u%02u-%lu-%lu",
        s_crash_dir,
        time.wYear,
        time.wMonth,
        time.wDay,
        time.wHour,
        time.wMinute,
        time.wSecond,
        ::GetCurrentProcessId(),
        ::GetCurrentThreadId());
}

void AppendInjectionLog(const char* line) {
    HANDLE file = ::CreateFileW(
        L"Py4GW_injection_log.txt",
        FILE_APPEND_DATA,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        nullptr,
        OPEN_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,
        nullptr);
    if (file == INVALID_HANDLE_VALUE) {
        return;
    }
    DWORD written = 0;
    ::WriteFile(file, line, static_cast<DWORD>(strlen(line)), &written, nullptr);
    ::CloseHandle(file);
}

void WriteGwText(const wchar_t* path, const char* text) {
    HANDLE file = ::CreateFileW(path, GENERIC_WRITE, FILE_SHARE_READ, nullptr, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE) {
        return;
    }
    DWORD written = 0;
    ::WriteFile(file, text, static_cast<DWORD>(strlen(text)), &written, nullptr);
    ::CloseHandle(file);
}

}  // namespace

CrashHandler& CrashHandler::Instance() {
    static CrashHandler instance;
    return instance;
}

CrashContextScope::CrashContextScope(const char* phase, const char* module, const char* operation, const char* detail) {
    snapshot_ = CrashHandler::CaptureContext();
    CrashHandler::SetContext(phase, module, operation, detail);
}

CrashContextScope::~CrashContextScope() {
    CrashHandler::RestoreContext(snapshot_);
}

void CrashHandler::SetContext(const char* phase, const char* module, const char* operation, const char* detail) {
    strncpy_s(s_context_phase, phase ? phase : "", _TRUNCATE);
    strncpy_s(s_context_module, module ? module : "", _TRUNCATE);
    strncpy_s(s_context_operation, operation ? operation : "", _TRUNCATE);
    strncpy_s(s_context_detail, detail ? detail : "", _TRUNCATE);
}

void CrashHandler::ClearContext() {
    s_context_phase[0] = 0;
    s_context_module[0] = 0;
    s_context_operation[0] = 0;
    s_context_detail[0] = 0;
}

CrashContextSnapshot CrashHandler::CaptureContext() {
    CrashContextSnapshot snapshot;
    strncpy_s(snapshot.phase.data(), snapshot.phase.size(), s_context_phase, _TRUNCATE);
    strncpy_s(snapshot.module.data(), snapshot.module.size(), s_context_module, _TRUNCATE);
    strncpy_s(snapshot.operation.data(), snapshot.operation.size(), s_context_operation, _TRUNCATE);
    strncpy_s(snapshot.detail.data(), snapshot.detail.size(), s_context_detail, _TRUNCATE);
    return snapshot;
}

void CrashHandler::RestoreContext(const CrashContextSnapshot& snapshot) {
    strncpy_s(s_context_phase, snapshot.phase.data(), _TRUNCATE);
    strncpy_s(s_context_module, snapshot.module.data(), _TRUNCATE);
    strncpy_s(s_context_operation, snapshot.operation.data(), _TRUNCATE);
    strncpy_s(s_context_detail, snapshot.detail.data(), _TRUNCATE);
}

std::string CrashHandler::CrashDirUtf8() const {
    return s_crash_dir_utf8;
}

bool CrashHandler::EnsureCrashDir() {
    if (s_crash_dir_ready) {
        return true;
    }

    wchar_t base[MAX_PATH] = {};
    const DWORD length = ::GetCurrentDirectoryW(MAX_PATH, base);
    if (length == 0 || length >= MAX_PATH) {
        const std::filesystem::path module_dir = PY4GW::process_manager::GetModuleDirectory();
        if (module_dir.empty()) {
            return false;
        }
        wcsncpy_s(base, module_dir.c_str(), _TRUNCATE);
    }

    _snwprintf_s(s_crash_dir, MAX_PATH, _TRUNCATE, L"%s\\crashes", base);
    MakeDirTree(s_crash_dir);
    s_crash_dir_ready = true;

    char utf8[MAX_PATH * 2] = {};
    if (::WideCharToMultiByte(CP_UTF8, 0, s_crash_dir, -1, utf8, sizeof(utf8), nullptr, nullptr) > 0) {
        s_crash_dir_utf8 = utf8;
    }
    return true;
}

void CrashHandler::Initialize() {
    if (s_installed) {
        return;
    }

    s_installed = true;
    EnsureCrashDir();
    ClearCallbackFilterPolicy();
    ::SetErrorMode(SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX | SEM_NOOPENFILEERRORBOX);
    ::SymSetOptions(SYMOPT_UNDNAME | SYMOPT_LOAD_LINES | SYMOPT_DEFERRED_LOADS);
    s_symbols_ready = !!::SymInitialize(::GetCurrentProcess(), nullptr, TRUE);
    PY4GW::RegisterPanicHandler(&CrashHandler::OnPanic, this);
    s_vectored_handler = ::AddVectoredExceptionHandler(1, &CrashHandler::VectoredHandler);
    InstallPathA();
    InstallPathC();
    Logger::Instance().LogInfo("[CrashHandler] installed.");
}

void CrashHandler::Terminate() {
    if (!s_installed) {
        return;
    }

    s_installed = false;
    if (s_append_stack_fn) {
        PY4GW::HookBase::DisableHooks(reinterpret_cast<void*>(s_append_stack_fn));
        PY4GW::HookBase::RemoveHook(reinterpret_cast<void*>(s_append_stack_fn));
        s_append_stack_fn = 0;
        s_append_stack_orig = nullptr;
    }
    if (s_vectored_handler) {
        ::RemoveVectoredExceptionHandler(s_vectored_handler);
        s_vectored_handler = nullptr;
    }
    if (s_symbols_ready) {
        ::SymCleanup(::GetCurrentProcess());
        s_symbols_ready = false;
    }
    ::SetUnhandledExceptionFilter(s_prev_filter);
    PY4GW::RegisterPanicHandler(nullptr, nullptr);
    RestoreCallbackFilterPolicy();
    ::InterlockedExchange(&s_handling, 0);
    Logger::Instance().LogInfo("[CrashHandler] torn down.");
}

void CrashHandler::SetDumpGenerationEnabled(bool enabled) {
    s_dump_generation_enabled = enabled;
}

bool CrashHandler::IsDumpGenerationEnabled() const {
    return s_dump_generation_enabled;
}

void CrashHandler::ClearCallbackFilterPolicy() {
    HMODULE kernel32 = ::GetModuleHandleW(L"kernel32.dll");
    if (!kernel32) {
        return;
    }
    using GetFn = BOOL(WINAPI*)(LPDWORD);
    using SetFn = BOOL(WINAPI*)(DWORD);
    const auto get = reinterpret_cast<GetFn>(::GetProcAddress(kernel32, "GetProcessUserModeExceptionPolicy"));
    const auto set = reinterpret_cast<SetFn>(::GetProcAddress(kernel32, "SetProcessUserModeExceptionPolicy"));
    if (!get || !set) {
        return;
    }
    DWORD policy = 0;
    if (!get(&policy)) {
        return;
    }
    s_prev_policy = policy;
    if (set(policy & 0xFFFFFFFEu)) {
        s_policy_changed = true;
    }
}

void CrashHandler::RestoreCallbackFilterPolicy() {
    if (!s_policy_changed) {
        return;
    }
    HMODULE kernel32 = ::GetModuleHandleW(L"kernel32.dll");
    if (!kernel32) {
        return;
    }
    using SetFn = BOOL(WINAPI*)(DWORD);
    const auto set = reinterpret_cast<SetFn>(::GetProcAddress(kernel32, "SetProcessUserModeExceptionPolicy"));
    if (set) {
        set(s_prev_policy);
    }
    s_policy_changed = false;
}

void CrashHandler::InstallPathA() {
    s_prev_filter = ::SetUnhandledExceptionFilter(&CrashHandler::TopLevelFilter);
}

void CrashHandler::InstallPathC() {
    const uintptr_t use = PY4GW::Scanner::FindUseOfString("%p  %08x %08x %08x %08x ");
    if (!Logger::AssertAddress("append_stack_anchor_use", use, "crash")) {
        Logger::Instance().LogWarning("[CrashHandler] Path C anchor miss; SEH/VEH only.");
        return;
    }

    s_append_stack_fn = PY4GW::Scanner::ToFunctionStart(use, 0xFFF);
    if (!Logger::AssertAddress("append_stack_target", s_append_stack_fn, "crash")) {
        Logger::Instance().LogWarning("[CrashHandler] Path C prologue miss; SEH/VEH only.");
        return;
    }

    void* target = reinterpret_cast<void*>(s_append_stack_fn);
    const int status = PY4GW::HookBase::CreateHookRaw(target, reinterpret_cast<void*>(&CrashHandler::AppendStackDetour), &s_append_stack_orig);
    if (status != 0 || !s_append_stack_orig) {
        Logger::Instance().LogWarning("[CrashHandler] Path C CreateHook failed.");
        s_append_stack_fn = 0;
        s_append_stack_orig = nullptr;
        return;
    }

    PY4GW::HookBase::EnableHooks(target);
    Logger::Instance().LogInfo("[CrashHandler] Path C attached.");
}

LONG WINAPI CrashHandler::TopLevelFilter(EXCEPTION_POINTERS* info) {
    Instance().OnException(info, "seh", false);
    return EXCEPTION_EXECUTE_HANDLER;
}

LONG WINAPI CrashHandler::VectoredHandler(EXCEPTION_POINTERS* info) {
    if (!s_installed || !info || !info->ExceptionRecord) {
        return EXCEPTION_CONTINUE_SEARCH;
    }
    if (!IsCrashCandidate(info->ExceptionRecord->ExceptionCode)) {
        return EXCEPTION_CONTINUE_SEARCH;
    }
    if (::InterlockedCompareExchange(&s_handling, 0, 0) != 0) {
        return EXCEPTION_CONTINUE_SEARCH;
    }
    Instance().OnException(info, "veh", true);
    return EXCEPTION_CONTINUE_SEARCH;
}

void CrashHandler::OnPanic(
    void*,
    const char* expr,
    const char* message,
    const char* file,
    unsigned int line,
    const char* function) {
    strncpy_s(s_panic_expr, expr ? expr : "", _TRUNCATE);
    strncpy_s(s_panic_message, message ? message : "", _TRUNCATE);
    strncpy_s(s_panic_file, file ? file : "", _TRUNCATE);
    strncpy_s(s_panic_function, function ? function : "", _TRUNCATE);
    s_panic_line = line;
}

uintptr_t __cdecl CrashHandler::AppendStackDetour(void* debug_info, uint32_t a2, uint32_t a3,
                                                  uint32_t a4, CONTEXT* ctx, uint32_t a6,
                                                  uint32_t a7) {
    static_assert(sizeof(void*) == 4, "Py4GW crash handler is x86 only.");
    using Fn = uintptr_t(__cdecl*)(void*, uint32_t, uint32_t, uint32_t, CONTEXT*, uint32_t, uint32_t);

    if (!s_append_stack_orig) {
        return 0;
    }

    const uintptr_t result = reinterpret_cast<Fn>(s_append_stack_orig)(debug_info, a2, a3, a4, ctx, a6, a7);

    __try {
        const char* text = reinterpret_cast<const char*>(reinterpret_cast<uintptr_t>(debug_info) + 0x20c);
        if (text && *text) {
            strncpy_s(s_gw_text, text, _TRUNCATE);
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }

    if (ctx) {
        EXCEPTION_RECORD record = {};
        record.ExceptionCode = 0x80000003;
        record.ExceptionFlags = EXCEPTION_NONCONTINUABLE;
        record.ExceptionAddress = reinterpret_cast<void*>(ctx->Eip);
        EXCEPTION_POINTERS info = { &record, ctx };
        Instance().OnException(&info, "gw_engine", false);
    }
    return result;
}

bool CrashHandler::OnException(EXCEPTION_POINTERS* info, const char* source, bool recoverable) {
    const char* source_label = SourceLabel(source);
    const bool write_dump = s_dump_generation_enabled && ShouldWriteDumpForSource(source);
    if (::InterlockedCompareExchange(&s_handling, 1, 0) != 0) {
        if (!recoverable) {
            ::TerminateProcess(::GetCurrentProcess(), 1);
        }
        return false;
    }

    if (s_crash_dir_ready) {
        wchar_t report_dir[MAX_PATH] = {};
        wchar_t report_name[128] = L"report";
        wchar_t dump_path[MAX_PATH] = {};
        wchar_t json_path[MAX_PATH] = {};
        wchar_t stack_path[MAX_PATH] = {};
        BuildReportFolder(report_dir, MAX_PATH);
        MakeDirTree(report_dir);
        const wchar_t* folder_name = wcsrchr(report_dir, L'\\');
        folder_name = folder_name ? folder_name + 1 : report_dir;
        wcsncpy_s(report_name, folder_name, _TRUNCATE);

        _snwprintf_s(dump_path, MAX_PATH, _TRUNCATE, L"%s\\%s.dmp", report_dir, report_name);
        _snwprintf_s(json_path, MAX_PATH, _TRUNCATE, L"%s\\%s.json", report_dir, report_name);
        _snwprintf_s(stack_path, MAX_PATH, _TRUNCATE, L"%s\\%s-stack.txt", report_dir, report_name);

        const wchar_t* dump_name = wcsrchr(dump_path, L'\\');
        dump_name = dump_name ? dump_name + 1 : dump_path;
        const wchar_t* stack_name = wcsrchr(stack_path, L'\\');
        stack_name = stack_name ? stack_name + 1 : stack_path;

        wchar_t gw_text_path[MAX_PATH] = {};
        const wchar_t* gw_text_name = L"";
        if (s_gw_text[0]) {
            _snwprintf_s(gw_text_path, MAX_PATH, _TRUNCATE, L"%s\\%s-gwtext.txt", report_dir, report_name);
            const wchar_t* slash = wcsrchr(gw_text_path, L'\\');
            gw_text_name = slash ? slash + 1 : gw_text_path;
        }

        char comment[512] = {};
        const DWORD code = (info && info->ExceptionRecord) ? info->ExceptionRecord->ExceptionCode : 0;
        _snprintf_s(
            comment,
            sizeof(comment),
            _TRUNCATE,
            "Py4GW | %s | 0x%08lX | panic:%s | %s",
            source_label,
            static_cast<unsigned long>(code),
            s_panic_expr[0] ? s_panic_expr : "?",
            s_panic_message[0] ? s_panic_message : "");

        WriteStackTrace(info, stack_path);
        WriteSidecar(info, json_path, dump_name, gw_text_name, stack_name, source_label, write_dump);
        if (write_dump) {
            WriteDump(info, dump_path, comment);
        }
        if (gw_text_path[0]) {
            WriteGwText(gw_text_path, s_gw_text);
        }

        char dump_name_u8[MAX_PATH] = {};
        if (::WideCharToMultiByte(CP_UTF8, 0, dump_name, -1, dump_name_u8, sizeof(dump_name_u8), nullptr, nullptr) <= 0) {
            dump_name_u8[0] = 0;
        }
        char log_line[320] = {};
        const char* artifact_name = nullptr;
        if (write_dump) {
            artifact_name = dump_name_u8;
        } else {
            artifact_name = "report sidecars";
        }
        char folder_name_u8[MAX_PATH] = {};
        if (::WideCharToMultiByte(CP_UTF8, 0, folder_name, -1, folder_name_u8, sizeof(folder_name_u8), nullptr, nullptr) <= 0) {
            folder_name_u8[0] = 0;
        }
        _snprintf_s(
            log_line,
            sizeof(log_line),
            _TRUNCATE,
            "CRASH %s 0x%08lX -> see crashes\\%s\\%s\r\n",
            source_label,
            static_cast<unsigned long>(code),
            folder_name_u8[0] ? folder_name_u8 : "?",
            artifact_name);
        AppendInjectionLog(log_line);
    }

    if (recoverable) {
        ::InterlockedExchange(&s_handling, 0);
    }
    return true;
}

void CrashHandler::WriteSidecar(EXCEPTION_POINTERS* info, const wchar_t* json_path,
                                const wchar_t* dmp_name, const wchar_t* gwtext_name,
                                const wchar_t* stack_name, const char* source, bool dump_generated) {
    HANDLE file = ::CreateFileW(json_path, GENERIC_WRITE, FILE_SHARE_READ, nullptr, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE) {
        return;
    }

    const DWORD code = (info && info->ExceptionRecord) ? info->ExceptionRecord->ExceptionCode : 0;
    const uintptr_t address =
        (info && info->ExceptionRecord) ? reinterpret_cast<uintptr_t>(info->ExceptionRecord->ExceptionAddress) : 0;

    char escaped_dump[160] = {};
    char escaped_gw[1100] = {};
    char escaped_gw_name[MAX_PATH] = {};
    char escaped_stack_name[MAX_PATH] = {};
    char escaped_panic_expr[600] = {};
    char escaped_panic_message[1200] = {};
    char escaped_panic_file[320] = {};
    char escaped_panic_function[180] = {};
    char escaped_context_phase[96] = {};
    char escaped_context_module[96] = {};
    char escaped_context_operation[160] = {};
    char escaped_context_detail[320] = {};

    char dump_u8[MAX_PATH] = {};
    if (dmp_name && dmp_name[0] &&
        ::WideCharToMultiByte(CP_UTF8, 0, dmp_name, -1, dump_u8, sizeof(dump_u8), nullptr, nullptr) > 0) {
        JsonEscape(escaped_dump, sizeof(escaped_dump), dump_u8);
    }
    JsonEscape(escaped_gw, sizeof(escaped_gw), s_gw_text);
    JsonEscape(escaped_panic_expr, sizeof(escaped_panic_expr), s_panic_expr);
    JsonEscape(escaped_panic_message, sizeof(escaped_panic_message), s_panic_message);
    JsonEscape(escaped_panic_file, sizeof(escaped_panic_file), s_panic_file);
    JsonEscape(escaped_panic_function, sizeof(escaped_panic_function), s_panic_function);
    JsonEscape(escaped_context_phase, sizeof(escaped_context_phase), s_context_phase);
    JsonEscape(escaped_context_module, sizeof(escaped_context_module), s_context_module);
    JsonEscape(escaped_context_operation, sizeof(escaped_context_operation), s_context_operation);
    JsonEscape(escaped_context_detail, sizeof(escaped_context_detail), s_context_detail);
    if (gwtext_name && gwtext_name[0]) {
        char gw_name_u8[MAX_PATH] = {};
        if (::WideCharToMultiByte(CP_UTF8, 0, gwtext_name, -1, gw_name_u8, sizeof(gw_name_u8), nullptr, nullptr) > 0) {
            JsonEscape(escaped_gw_name, sizeof(escaped_gw_name), gw_name_u8);
        }
    }
    if (stack_name && stack_name[0]) {
        char stack_name_u8[MAX_PATH] = {};
        if (::WideCharToMultiByte(CP_UTF8, 0, stack_name, -1, stack_name_u8, sizeof(stack_name_u8), nullptr, nullptr) > 0) {
            JsonEscape(escaped_stack_name, sizeof(escaped_stack_name), stack_name_u8);
        }
    }

    char buffer[4096] = {};
    JBuf json{ buffer, buffer + sizeof(buffer) };
    JAppend(json, "{\n");
    JAppend(json, "  \"source\": \"%s\",\n", source);
    JAppend(json, "  \"crash_class\": \"%s\",\n", ExceptionLabel(code));
    JAppend(json, "  \"exception_code\": \"0x%08lX\",\n", static_cast<unsigned long>(code));
    JAppend(json, "  \"fault_address\": \"0x%08lX\",\n",
            static_cast<unsigned long>(address));
    JAppend(json, "  \"faulting_tid\": %lu,\n", ::GetCurrentThreadId());
    JAppend(json, "  \"dump_generated\": %s,\n", dump_generated ? "true" : "false");
    JAppend(json, "  \"dump_file\": \"%s\"", dump_generated ? escaped_dump : "");
    if (escaped_gw_name[0]) {
        JAppend(json, ",\n  \"gw_text_file\": \"%s\"", escaped_gw_name);
    }
    if (escaped_stack_name[0]) {
        JAppend(json, ",\n  \"stack_trace_file\": \"%s\"", escaped_stack_name);
    }
    JAppend(json, ",\n");
    JAppend(json, "  \"panic\": {\n");
    JAppend(json, "    \"expr\": \"%s\",\n", escaped_panic_expr);
    JAppend(json, "    \"message\": \"%s\",\n", escaped_panic_message);
    JAppend(json, "    \"file\": \"%s\",\n", escaped_panic_file);
    JAppend(json, "    \"line\": %u,\n", s_panic_line);
    JAppend(json, "    \"function\": \"%s\"\n", escaped_panic_function);
    JAppend(json, "  },\n");
    JAppend(json, "  \"context\": {\n");
    JAppend(json, "    \"phase\": \"%s\",\n", escaped_context_phase);
    JAppend(json, "    \"module\": \"%s\",\n", escaped_context_module);
    JAppend(json, "    \"operation\": \"%s\",\n", escaped_context_operation);
    JAppend(json, "    \"detail\": \"%s\"\n", escaped_context_detail);
    JAppend(json, "  },\n");
    JAppend(json, "  \"gw_text\": \"%s\"\n", escaped_gw);
    JAppend(json, "}\n");

    DWORD written = 0;
    ::WriteFile(file, buffer, static_cast<DWORD>(json.p - buffer), &written, nullptr);
    ::CloseHandle(file);
}

void CrashHandler::WriteStackTrace(EXCEPTION_POINTERS* info, const wchar_t* stack_path) {
    HANDLE file = ::CreateFileW(stack_path, GENERIC_WRITE, FILE_SHARE_READ, nullptr, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE) {
        return;
    }

    if (!info || !info->ContextRecord || !s_symbols_ready) {
        const char* message = "Stack trace unavailable.\r\n";
        DWORD written = 0;
        ::WriteFile(file, message, static_cast<DWORD>(strlen(message)), &written, nullptr);
        ::CloseHandle(file);
        return;
    }

    CONTEXT context = *info->ContextRecord;
    STACKFRAME64 frame = {};
    DWORD machine = IMAGE_FILE_MACHINE_I386;
    frame.AddrPC.Offset = context.Eip;
    frame.AddrPC.Mode = AddrModeFlat;
    frame.AddrFrame.Offset = context.Ebp;
    frame.AddrFrame.Mode = AddrModeFlat;
    frame.AddrStack.Offset = context.Esp;
    frame.AddrStack.Mode = AddrModeFlat;

    HANDLE process = ::GetCurrentProcess();
    HANDLE thread = ::GetCurrentThread();
    char line[1024] = {};
    DWORD written = 0;
    for (int index = 0; index < 32; ++index) {
        if (!::StackWalk64(
                machine,
                process,
                thread,
                &frame,
                &context,
                nullptr,
                ::SymFunctionTableAccess64,
                ::SymGetModuleBase64,
                nullptr) ||
            frame.AddrPC.Offset == 0) {
            break;
        }

        char symbol_buffer[sizeof(SYMBOL_INFO) + 256] = {};
        auto* symbol = reinterpret_cast<SYMBOL_INFO*>(symbol_buffer);
        symbol->SizeOfStruct = sizeof(SYMBOL_INFO);
        symbol->MaxNameLen = 255;
        DWORD64 displacement = 0;
        IMAGEHLP_LINE64 line_info = {};
        line_info.SizeOfStruct = sizeof(IMAGEHLP_LINE64);
        DWORD line_displacement = 0;
        const BOOL have_symbol = ::SymFromAddr(process, frame.AddrPC.Offset, &displacement, symbol);
        const BOOL have_line = ::SymGetLineFromAddr64(process, frame.AddrPC.Offset, &line_displacement, &line_info);

        char module_name[MAX_PATH] = "<unknown>";
        if (DWORD64 module_base = ::SymGetModuleBase64(process, frame.AddrPC.Offset)) {
            ::GetModuleFileNameA(reinterpret_cast<HMODULE>(module_base), module_name, MAX_PATH);
        }

        if (have_symbol && have_line) {
            _snprintf_s(
                line,
                sizeof(line),
                _TRUNCATE,
                "#%02d 0x%08llX %s!%s +0x%llX (%s:%lu)\r\n",
                index,
                frame.AddrPC.Offset,
                module_name,
                symbol->Name,
                displacement,
                line_info.FileName,
                line_info.LineNumber);
        } else if (have_symbol) {
            _snprintf_s(
                line,
                sizeof(line),
                _TRUNCATE,
                "#%02d 0x%08llX %s!%s +0x%llX\r\n",
                index,
                frame.AddrPC.Offset,
                module_name,
                symbol->Name,
                displacement);
        } else {
            _snprintf_s(
                line,
                sizeof(line),
                _TRUNCATE,
                "#%02d 0x%08llX %s\r\n",
                index,
                frame.AddrPC.Offset,
                module_name);
        }
        ::WriteFile(file, line, static_cast<DWORD>(strlen(line)), &written, nullptr);
    }

    ::CloseHandle(file);
}

void CrashHandler::WriteDump(EXCEPTION_POINTERS* info, const wchar_t* dmp_path, const char* comment) {
    HANDLE file = ::CreateFileW(dmp_path, GENERIC_WRITE, 0, nullptr, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE) {
        return;
    }

    MINIDUMP_EXCEPTION_INFORMATION exception_info = {};
    exception_info.ThreadId = ::GetCurrentThreadId();
    exception_info.ExceptionPointers = info;
    exception_info.ClientPointers = FALSE;

    MINIDUMP_USER_STREAM stream = {};
    stream.Type = CommentStreamA;
    stream.BufferSize = static_cast<ULONG>(strlen(comment) + 1);
    stream.Buffer = const_cast<char*>(comment);
    MINIDUMP_USER_STREAM_INFORMATION stream_info = { 1, &stream };
    const auto flags = static_cast<MINIDUMP_TYPE>(0x1041);

    __try {
        ::MiniDumpWriteDump(
            ::GetCurrentProcess(),
            ::GetCurrentProcessId(),
            file,
            flags,
            info ? &exception_info : nullptr,
            &stream_info,
            nullptr);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }

    ::CloseHandle(file);
}
