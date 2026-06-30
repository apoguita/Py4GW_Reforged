#include "base/memory_manager.h"

#include "base/error_handling.h"

#include "base/patterns.h"

#include <mmsystem.h>

namespace {

using GetGWVersionFn = uint32_t(__cdecl*)();
using MemAllocHelperFn = void*(__stdcall*)(size_t, uint8_t, const char*, int);
using MemReallocHelperFn = void*(__stdcall*)(void*, size_t, uint8_t, const char*, int);
using MemFreeFn = void*(__cdecl*)(void*);

DWORD* g_skill_timer_ptr = nullptr;
uintptr_t g_window_handle_ptr = 0;
uintptr_t g_get_personal_dir_ptr = 0;
GetGWVersionFn g_get_gw_version_func = nullptr;
MemAllocHelperFn g_mem_alloc_helper_func = nullptr;
MemReallocHelperFn g_mem_realloc_helper_func = nullptr;
MemFreeFn g_mem_free_func = nullptr;

bool ResolveSkillTimer() {
    return PY4GW::Patterns::Resolve("memory.skill_timer_ptr", &g_skill_timer_ptr);
}

bool ResolveWindowHandlePointer() {
    return PY4GW::Patterns::Resolve("memory.window_handle_ptr", &g_window_handle_ptr);
}

bool ResolvePersonalDirFunction() {
    return PY4GW::Patterns::Resolve("memory.personal_dir_ptr", &g_get_personal_dir_ptr);
}

bool ResolveVersionFunction() {
    return PY4GW::Patterns::Resolve("memory.gw_version_func", &g_get_gw_version_func);
}

bool ResolveAllocHelpers() {
    return PY4GW::Patterns::Resolve("memory.mem_alloc_helper_func", &g_mem_alloc_helper_func) &&
        PY4GW::Patterns::Resolve("memory.mem_realloc_helper_func", &g_mem_realloc_helper_func);
}

bool ResolveFreeHelper() {
    return PY4GW::Patterns::Resolve("memory.mem_free_func", &g_mem_free_func);
}

}  // namespace

namespace PY4GW {

bool MemoryManager::Scan() {
    PY4GW_ASSERT(Scanner::Initialize());
    PY4GW_ASSERT(Patterns::Initialize());

    return ResolveSkillTimer() &&
        ResolveWindowHandlePointer() &&
        ResolvePersonalDirFunction() &&
        ResolveVersionFunction() &&
        ResolveAllocHelpers() &&
        ResolveFreeHelper();
}

uint32_t MemoryManager::GetGWVersion() {
    return g_get_gw_version_func ? g_get_gw_version_func() : 0;
}

DWORD MemoryManager::GetSkillTimer() {
    return g_skill_timer_ptr ? timeGetTime() + *g_skill_timer_ptr : timeGetTime();
}

HWND MemoryManager::GetGWWindowHandle() {
    return g_window_handle_ptr ? *reinterpret_cast<HWND*>(g_window_handle_ptr) : nullptr;
}

void* MemoryManager::MemAlloc(size_t size) {
    if (!g_mem_alloc_helper_func) {
        return nullptr;
    }
    return g_mem_alloc_helper_func(size, 0, __FILE__, __LINE__);
}

void* MemoryManager::MemRealloc(void* buffer, size_t new_size) {
    if (!g_mem_realloc_helper_func) {
        return nullptr;
    }
    return g_mem_realloc_helper_func(buffer, new_size, 0, __FILE__, __LINE__);
}

void MemoryManager::MemFree(void* buffer) {
    if (g_mem_free_func) {
        g_mem_free_func(buffer);
    }
}

}  // namespace PY4GW
