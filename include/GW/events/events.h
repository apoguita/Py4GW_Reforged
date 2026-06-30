#pragma once

#include "base/hook_types.h"
#include "GW/common/constants/events.h"

#include <cstdint>

namespace GW::events {
bool Initialize();
void Shutdown();

using EventCallback = PY4GW::HookCallback<Constants::EventID, void*, uint32_t>;

void RegisterEventCallback(
    PY4GW::HookEntry* entry,
    Constants::EventID event_id,
    const EventCallback& callback,
    int altitude = -0x8000);
void RemoveEventCallback(PY4GW::HookEntry* entry);

}  // namespace GW::events
