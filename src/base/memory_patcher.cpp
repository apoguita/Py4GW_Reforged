#include "base/error_handling.h"

#include "base/CrashHandler.h"
#include "base/logger.h"
#include "base/memory_patcher.h"

#include <algorithm>
#include <cstring>
#include <vector>
#include <windows.h>

namespace {

std::vector<PY4GW::MemoryPatcher*> g_patches;
bool g_patching_enabled = true;

}  // namespace

namespace PY4GW {

MemoryPatcher::~MemoryPatcher() {
    if (!(IsValid() && GetIsActive())) {
        return;
    }

    CrashContextScope context("shutdown", "memory_patcher", "destructor_restore");
    Logger::Instance().LogWarning(
        "[memory_patcher] Active patch survived to destructor; restoring original bytes during teardown.",
        "memory_patcher");

    if (g_patching_enabled) {
        PatchActual(false);
    }
    active_ = false;
}

void MemoryPatcher::EnableHooks() {
    CrashContextScope context("runtime", "memory_patcher", "enable_hooks");
    if (g_patching_enabled) {
        return;
    }

    g_patching_enabled = true;
    for (MemoryPatcher* patcher : g_patches) {
        if (!(patcher->IsValid() && patcher->GetIsActive())) {
            continue;
        }
        patcher->PatchActual(true);
    }
}

void MemoryPatcher::DisableHooks() {
    CrashContextScope context("shutdown", "memory_patcher", "disable_hooks");
    if (!g_patching_enabled) {
        return;
    }

    for (MemoryPatcher* patcher : g_patches) {
        if (!(patcher->IsValid() && patcher->GetIsActive())) {
            continue;
        }
        patcher->PatchActual(false);
    }
    g_patching_enabled = false;
}

void MemoryPatcher::Reset() {
    CrashContextScope context("shutdown", "memory_patcher", "reset_patch");
    if (GetIsActive()) {
        TogglePatch(false);
    }

    delete[] patch_;
    patch_ = nullptr;
    delete[] backup_;
    backup_ = nullptr;

    address_ = nullptr;
    size_ = 0;
    active_ = false;

    g_patches.erase(std::remove(g_patches.begin(), g_patches.end(), this), g_patches.end());
}

bool MemoryPatcher::IsValid() const {
    return address_ != nullptr;
}

void MemoryPatcher::SetPatch(uintptr_t address, const void* patch, size_t size) {
    CrashContextScope context("startup", "memory_patcher", "set_patch");
    Reset();
    if (!(address && patch && size)) {
        return;
    }

    address_ = reinterpret_cast<void*>(address);
    size_ = size;
    active_ = false;

    patch_ = new uint8_t[size_];
    backup_ = new uint8_t[size_];
    std::memcpy(patch_, patch, size_);

    DWORD old_protect = 0;
    ::VirtualProtect(address_, size_, PAGE_EXECUTE_READWRITE, &old_protect);
    std::memcpy(backup_, address_, size_);
    ::VirtualProtect(address_, size_, old_protect, &old_protect);

    g_patches.push_back(this);
}

void MemoryPatcher::PatchActual(bool patch) {
    CrashContextScope context(patch ? "runtime" : "shutdown", "memory_patcher", patch ? "apply_patch" : "restore_patch");
    if (!IsValid() || !g_patching_enabled) {
        return;
    }

    DWORD old_protect = 0;
    ::VirtualProtect(address_, size_, PAGE_EXECUTE_READWRITE, &old_protect);
    std::memcpy(address_, patch ? patch_ : backup_, size_);
    ::FlushInstructionCache(::GetCurrentProcess(), address_, size_);
    ::VirtualProtect(address_, size_, old_protect, &old_protect);
}

bool MemoryPatcher::SetRedirect(uintptr_t call_instruction_address, void* redirect_func) {
    CrashContextScope context("startup", "memory_patcher", "set_redirect");
    if (!(call_instruction_address && redirect_func)) {
        return false;
    }

    const char instruction_type = static_cast<char>(*reinterpret_cast<uint8_t*>(call_instruction_address));
    if (instruction_type != static_cast<char>(0xE8) && instruction_type != static_cast<char>(0xE9)) {
        return false;
    }

    const uintptr_t call_offset = reinterpret_cast<uintptr_t>(redirect_func) - call_instruction_address - 5;
    const char patch[5] = {
        instruction_type,
        static_cast<char>(call_offset),
        static_cast<char>(call_offset >> 8),
        static_cast<char>(call_offset >> 16),
        static_cast<char>(call_offset >> 24),
    };

    SetPatch(call_instruction_address, patch, sizeof(patch));
    return true;
}

bool MemoryPatcher::TogglePatch(bool enabled) {
    CrashContextScope context(enabled ? "runtime" : "shutdown", "memory_patcher", enabled ? "toggle_on" : "toggle_off");
    if (!IsValid()) {
        return false;
    }

    active_ = enabled;
    PatchActual(active_);
    return enabled;
}

}  // namespace PY4GW
