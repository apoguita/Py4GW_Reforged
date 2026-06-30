#pragma once

#include "base/error_handling.h"

#include <cstddef>
#include <cstdint>
#include <windows.h>

namespace GW::Context {

static constexpr size_t CHAT_LOG_LENGTH = 0x200;

#pragma warning(push)
#pragma warning(disable: 4200)
struct ChatMessage {
    uint32_t channel;
    uint32_t unk1;
    FILETIME timestamp;
    wchar_t message[0];
};
#pragma warning(pop)

struct ChatBuffer {
    uint32_t next;
    uint32_t unk1;
    uint32_t unk2;
    ChatMessage* messages[CHAT_LOG_LENGTH];
};

ChatBuffer** GetChatBufferAddress();
uint32_t* GetIsTypingFrameIdAddress();

}  // namespace GW::Context
