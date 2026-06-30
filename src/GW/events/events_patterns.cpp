#include "base/error_handling.h"

#include "base/CrashHandler.h"
#include "base/patterns.h"

#include "GW/events/events.h"

namespace GW::events {

using SendEventMessageFn = uint32_t(__cdecl*)(void* event_context, uint32_t unk1, Constants::EventID event_id, void* data_buffer, uint32_t data_length);

extern SendEventMessageFn g_send_event_message_func;

bool ResolveSendEventMessageTarget() {
    CrashContextScope context("startup", "events", "resolve_send_event_message_target");
    return PY4GW::Patterns::Resolve("events.send_event_message_func", &g_send_event_message_func);
}

}  // namespace GW::events
