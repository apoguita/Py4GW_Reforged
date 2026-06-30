#include "base/error_handling.h"

#include "GW/events/events.h"

#include "base/CrashHandler.h"
#include "base/hooker.h"
#include "base/logger.h"
#include "base/patterns.h"
#include "base/scanner.h"

namespace GW::events {

    using SendEventMessageFn = uint32_t(__cdecl*)(void* event_context, uint32_t unk1, Constants::EventID event_id, void* data_buffer, uint32_t data_length);

    struct CallbackEntry {
        int altitude = 0;
        PY4GW::HookEntry* entry = nullptr;
        EventCallback callback;
    };

    bool ResolveSendEventMessageTarget();
    bool Init();
    void EnableHooks();
    void DisableHooks();
    void Exit();

    SendEventMessageFn g_send_event_message_func = nullptr;
    SendEventMessageFn g_send_event_message_original = nullptr;
    std::unordered_map<Constants::EventID, std::vector<CallbackEntry>> g_callbacks;
    std::atomic<bool> g_initialized = false;

uint32_t __cdecl OnSendEventMessage(
    void* event_context,
    uint32_t unk1,
    Constants::EventID event_id,
    void* data_buffer,
    uint32_t data_length);

uint32_t __cdecl OnSendEventMessage(
    void* event_context,
    uint32_t unk1,
    Constants::EventID event_id,
    void* data_buffer,
    uint32_t data_length) {
    PY4GW::HookBase::EnterHook();
    PY4GW::HookStatus status = {};
    uint32_t result = 1;

    auto found = g_callbacks.find(event_id);
    if (found == g_callbacks.end()) {
        PY4GW::HookBase::LeaveHook();
        return g_send_event_message_original
            ? g_send_event_message_original(event_context, unk1, event_id, data_buffer, data_length)
            : result;
    }

    auto it = found->second.begin();
    const auto end = found->second.end();
    while (it != end) {
        if (it->altitude > 0) {
            break;
        }
        it->callback(&status, event_id, data_buffer, data_length);
        ++status.altitude;
        ++it;
    }

    if (!status.blocked && g_send_event_message_original) {
        result = g_send_event_message_original(event_context, unk1, event_id, data_buffer, data_length);
    }

    while (it != end) {
        it->callback(&status, event_id, data_buffer, data_length);
        ++status.altitude;
        ++it;
    }

    PY4GW::HookBase::LeaveHook();
    return result;
}

bool Init() {
    CrashContextScope context("startup", "events", "init");
    if (!ResolveSendEventMessageTarget()) {
        return false;
    }

    const int status = PY4GW::HookBase::CreateHook(
        reinterpret_cast<void**>(&g_send_event_message_func),
        reinterpret_cast<void*>(&OnSendEventMessage),
        reinterpret_cast<void**>(&g_send_event_message_original));
    return Logger::AssertHook("SendEventMessage_Func", status, "events");
}

void EnableHooks() {
    CrashContextScope context("runtime", "events", "enable_hooks");
    // Legacy GWCA currently keeps this hook disabled.
    return;
}

void DisableHooks() {
    CrashContextScope context("shutdown", "events", "disable_hooks");
    if (g_send_event_message_func) {
        PY4GW::HookBase::DisableHooks(reinterpret_cast<void*>(g_send_event_message_func));
    }
}

void Exit() {
    CrashContextScope context("shutdown", "events", "exit");
    if (g_send_event_message_func) {
        PY4GW::HookBase::RemoveHook(reinterpret_cast<void*>(g_send_event_message_func));
    }

    g_send_event_message_func = nullptr;
    g_send_event_message_original = nullptr;
    g_callbacks.clear();
}

bool Initialize() {
    CrashContextScope context("startup", "events", "initialize");
    if (g_initialized) {
        return true;
    }

    PY4GW_ASSERT(PY4GW::Scanner::Initialize());
    PY4GW_ASSERT(PY4GW::Patterns::Initialize());

    PY4GW::HookBase::Initialize();
    if (!Init()) {
        Exit();
        PY4GW::HookBase::Deinitialize();
        return false;
    }

    EnableHooks();
    g_initialized = true;
    return true;
}

void Shutdown() {
    CrashContextScope context("shutdown", "events", "shutdown");
    if (!g_initialized) {
        return;
    }

    DisableHooks();
    Exit();
    PY4GW::HookBase::Deinitialize();
    g_initialized = false;
}

void RegisterEventCallback(
    PY4GW::HookEntry* entry,
    Constants::EventID event_id,
    const EventCallback& callback,
    int altitude) {
    auto found = g_callbacks.find(event_id);
    if (found == g_callbacks.end()) {
        g_callbacks[event_id] = std::vector<CallbackEntry>();
    }

    auto it = g_callbacks[event_id].begin();
    while (it != g_callbacks[event_id].end()) {
        if (it->altitude > altitude) {
            break;
        }
        ++it;
    }

    g_callbacks[event_id].insert(it, CallbackEntry{altitude, entry, callback});
}

void RemoveEventCallback(PY4GW::HookEntry* entry) {
    for (auto& callbacks : g_callbacks) {
        auto it = callbacks.second.begin();
        while (it != callbacks.second.end()) {
            if (it->entry == entry) {
                callbacks.second.erase(it);
                return;
            }
            ++it;
        }
    }
}

}  // namespace GW::events
