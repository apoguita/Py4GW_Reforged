#include "base/error_handling.h"

#include "base/CrashHandler.h"
#include "base/memory_patcher.h"
#include "base/patterns.h"

#include "GW/chat/chat.h"

namespace GW::Context {
extern ChatBuffer** g_chat_buffer_addr;
extern uint32_t* g_is_typing_frame_id;
}

namespace GW::chat {

using GetChannelColorFn = Color*(__cdecl*)(Color* color, Channel chan);
using SendChatFn = void(__cdecl*)(wchar_t* message, uint32_t agent_id);
using RecvWhisperFn = void(__cdecl*)(uint32_t transaction_id, wchar_t* player_name, wchar_t* message);
using StartWhisperFn = void(__fastcall*)(ui::Frame* ctx, uint32_t edx, wchar_t* name);
using AddToChatLogFn = void(__cdecl*)(wchar_t* message, uint32_t channel);
using PrintChatMessageFn = void(__fastcall*)(void* ctx, uint32_t edx, Channel channel, wchar_t* message, FILETIME timestamp, uint32_t is_reprint);

extern GetChannelColorFn g_get_sender_color_func;
extern GetChannelColorFn g_get_message_color_func;
extern SendChatFn g_send_chat_func;
extern StartWhisperFn g_start_whisper_func;
extern AddToChatLogFn g_add_to_chat_log_func;
extern RecvWhisperFn g_recv_whisper_func;
extern PrintChatMessageFn g_print_chat_message_func;
extern ui::UIInteractionCallback g_uicallback_assign_editable_text_func;
extern ui::UIInteractionCallback g_uicallback_chat_log_line_func;
extern PY4GW::MemoryPatcher g_block_chat_timestamps;

bool ResolveGetSenderColorFunction() {
    CrashContextScope context("startup", "chat", "resolve_get_sender_color");
    return PY4GW::Patterns::Resolve("chat.get_sender_color_func", &g_get_sender_color_func);
}

bool ResolveGetMessageColorFunction() {
    CrashContextScope context("startup", "chat", "resolve_get_message_color");
    return PY4GW::Patterns::Resolve("chat.get_message_color_func", &g_get_message_color_func);
}

bool ResolveSendChatFunction() {
    CrashContextScope context("startup", "chat", "resolve_send_chat");
    return PY4GW::Patterns::Resolve("chat.send_chat_func", &g_send_chat_func);
}

bool ResolveStartWhisperFunction() {
    CrashContextScope context("startup", "chat", "resolve_start_whisper");
    return PY4GW::Patterns::Resolve("chat.start_whisper_func", &g_start_whisper_func);
}

bool ResolveAddToChatLogFunction() {
    CrashContextScope context("startup", "chat", "resolve_add_to_chat_log");
    return PY4GW::Patterns::Resolve("chat.add_to_chat_log_func", &g_add_to_chat_log_func);
}

bool ResolveChatBufferAddress() {
    CrashContextScope context("startup", "chat", "resolve_chat_buffer");
    return PY4GW::Patterns::Resolve("chat.chat_buffer_addr", &Context::g_chat_buffer_addr);
}

bool ResolveRecvWhisperFunction() {
    CrashContextScope context("startup", "chat", "resolve_recv_whisper");
    return PY4GW::Patterns::Resolve("chat.recv_whisper_func", &g_recv_whisper_func);
}

bool ResolvePrintChatMessageFunction() {
    CrashContextScope context("startup", "chat", "resolve_print_chat_message");
    return PY4GW::Patterns::Resolve("chat.print_chat_message_func", &g_print_chat_message_func);
}

bool ResolveIsTypingFrameId() {
    CrashContextScope context("startup", "chat", "resolve_is_typing_frame_id");
    return PY4GW::Patterns::Resolve("chat.is_typing_frame_id", &Context::g_is_typing_frame_id);
}

bool ResolveUICallbackAssignEditableText() {
    CrashContextScope context("startup", "chat", "resolve_uicallback_assign_editable_text");
    return PY4GW::Patterns::Resolve("chat.uicallback_assign_editable_text_func", &g_uicallback_assign_editable_text_func);
}

bool ResolveUICallbackChatLogLine() {
    CrashContextScope context("startup", "chat", "resolve_uicallback_chat_log_line");
    return PY4GW::Patterns::Resolve("chat.uicallback_chat_log_line_func", &g_uicallback_chat_log_line_func);
}

bool ResolveChatTimestampsPatch() {
    CrashContextScope context("startup", "chat", "resolve_chat_timestamps_patch");
    uintptr_t address = 0;
    PY4GW::Patterns::Resolve("chat.chat_timestamps_patch_addr", &address);
    if (address) {
        const uint8_t nop_pair[] = { 0x90, 0x90 };
        g_block_chat_timestamps.SetPatch(address, nop_pair, sizeof(nop_pair));
    }
    return g_block_chat_timestamps.IsValid();
}

}  // namespace GW::chat
