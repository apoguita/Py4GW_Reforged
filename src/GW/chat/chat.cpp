#include "base/error_handling.h"

#include "GW/chat/chat.h"

#include "base/CrashHandler.h"
#include "base/hooker.h"
#include "base/hook_types.h"
#include "base/logger.h"
#include "base/memory_patcher.h"
#include "base/patterns.h"
#include "base/scanner.h"

#include "GW/ui/ui.h"

#include <array>
#include <atomic>
#include <map>
#include <string>
#include <unordered_map>
#include <cwctype>
#include <shellapi.h>

namespace GW::chat {

using GetChannelColorFn = Color*(__cdecl*)(Color* color, Channel chan);
using SendChatFn = void(__cdecl*)(wchar_t* message, uint32_t agent_id);
using RecvWhisperFn = void(__cdecl*)(uint32_t transaction_id, wchar_t* player_name, wchar_t* message);
using StartWhisperFn = void(__fastcall*)(ui::Frame* ctx, uint32_t edx, wchar_t* name);
using AddToChatLogFn = void(__cdecl*)(wchar_t* message, uint32_t channel);
using PrintChatMessageFn = void(__fastcall*)(void* ctx, uint32_t edx, Channel channel, wchar_t* message, FILETIME timestamp, uint32_t is_reprint);

bool ResolveGetSenderColorFunction();
bool ResolveGetMessageColorFunction();
bool ResolveSendChatFunction();
bool ResolveStartWhisperFunction();
bool ResolveAddToChatLogFunction();
bool ResolveChatBufferAddress();
bool ResolveRecvWhisperFunction();
bool ResolvePrintChatMessageFunction();
bool ResolveIsTypingFrameId();
bool ResolveUICallbackAssignEditableText();
bool ResolveUICallbackChatLogLine();
bool ResolveChatTimestampsPatch();
Color* __cdecl OnGetSenderColor(Color* color, Channel chan);
Color* __cdecl OnGetMessageColor(Color* color, Channel chan);
void __cdecl OnSendChat(wchar_t* message, uint32_t agent_id);
void __cdecl OnRecvWhisper(uint32_t transaction_id, wchar_t* player_name, wchar_t* message);
void __fastcall OnStartWhisper(ui::Frame* ctx, uint32_t edx, wchar_t* name);
void __cdecl OnAddToChatLog(wchar_t* message, uint32_t channel);
void __fastcall OnPrintChatMessage(void* ctx, uint32_t edx, Channel channel, wchar_t* message, FILETIME timestamp, uint32_t is_reprint);
void __cdecl OnUICallback_ChatLogLine(ui::InteractionMessage* message, void* wParam, void* lParam);
void __cdecl OnUICallback_AssignEditableText(ui::InteractionMessage* message, void* wParam, void* lParam);
void OnUIMessage(PY4GW::HookStatus* status, ui::UIMessage message_id, void* wparam, void* lparam);
bool Init();
void EnableHooks();
void DisableHooks();
void Exit();

GetChannelColorFn g_get_sender_color_func = nullptr;
GetChannelColorFn g_get_sender_color_original = nullptr;
GetChannelColorFn g_get_message_color_func = nullptr;
GetChannelColorFn g_get_message_color_original = nullptr;
SendChatFn g_send_chat_func = nullptr;
SendChatFn g_send_chat_original = nullptr;
RecvWhisperFn g_recv_whisper_func = nullptr;
RecvWhisperFn g_recv_whisper_original = nullptr;
StartWhisperFn g_start_whisper_func = nullptr;
StartWhisperFn g_start_whisper_original = nullptr;
AddToChatLogFn g_add_to_chat_log_func = nullptr;
AddToChatLogFn g_add_to_chat_log_original = nullptr;
PrintChatMessageFn g_print_chat_message_func = nullptr;
PrintChatMessageFn g_print_chat_message_original = nullptr;
ui::UIInteractionCallback g_uicallback_chat_log_line_func = nullptr;
ui::UIInteractionCallback g_uicallback_chat_log_line_original = nullptr;
ui::UIInteractionCallback g_uicallback_assign_editable_text_func = nullptr;
ui::UIInteractionCallback g_uicallback_assign_editable_text_original = nullptr;
void* g_chat_window_context = nullptr;
PY4GW::MemoryPatcher g_block_chat_timestamps;
std::map<Channel, Color> g_chat_sender_color;
std::map<Channel, Color> g_chat_message_color;
std::unordered_map<std::wstring, ChatCommandCallback> g_chat_command_hook_entries;
std::array<bool, static_cast<size_t>(Channel::CHANNEL_COUNT)> g_channel_that_parse_color_tag = {
    true, true, true, true, true, true, true,
    false,
    true, true, true, true, true,
    false,
    true
};
bool g_show_timestamps = false;
bool g_timestamp_24h_format = false;
bool g_timestamp_seconds = false;
Color g_timestamps_color = MakeColorRGB(0xff, 0xff, 0xff);
const wchar_t* g_transient_chat_message = nullptr;
PY4GW::HookEntry g_ui_message_entry;
const std::array<ui::UIMessage, 5> g_ui_messages_to_hook = {
    ui::UIMessage::kSendChatMessage,
    ui::UIMessage::kStartWhisper,
    ui::UIMessage::kLogChatMessage,
    ui::UIMessage::kPrintChatMessage,
    ui::UIMessage::kRecvWhisper
};
std::atomic<bool> g_initialized = false;

static void wcs_tolower(wchar_t* s) {
    for (size_t i = 0; s[i]; i++) {
        s[i] = std::towlower(s[i]);
    }
}


static wchar_t* ChatMessageWithTimestamp(const wchar_t* message, const Channel channel, const FILETIME timestamp) {
    FILETIME timestamp2;
    SYSTEMTIME localtime;

    FileTimeToLocalFileTime(&timestamp, &timestamp2);
    FileTimeToSystemTime(&timestamp2, &localtime);
    if (!localtime.wYear) {
        return nullptr;
    }

    WORD hour = localtime.wHour;
    WORD minute = localtime.wMinute;
    WORD second = localtime.wSecond;

    if (!g_timestamp_24h_format) {
        hour %= 12;
    }

    const size_t buffer_size = 29;
    wchar_t time_buffer[buffer_size];

    if (g_timestamp_seconds) {
        GWCA_ASSERT(swprintf(time_buffer, buffer_size, L"[lbracket]%02d:%02d:%02d[rbracket]", hour, minute, second) > 0);
    }
    else {
        GWCA_ASSERT(swprintf(time_buffer, buffer_size, L"[lbracket]%02d:%02d[rbracket]", hour, minute) > 0);
    }

    size_t buf_len = 21 + buffer_size + wcslen(message) + 1;
    auto buffer = new wchar_t[buf_len];
    if (g_channel_that_parse_color_tag[static_cast<size_t>(channel)]) {
        GWCA_ASSERT(swprintf(buffer, buf_len, L"\x108\x107<c=#%06x>%s </c>\x01\x02%s", (g_timestamps_color & 0x00FFFFFF), time_buffer, message) > 0);
    }
    else {
        GWCA_ASSERT(swprintf(buffer, buf_len, L"\x108\x107%s \x01\x02%s", time_buffer, message) > 0);
    }
    return buffer;
}


Color* __cdecl OnGetSenderColor(Color* color, Channel chan) {
    PY4GW::HookBase::EnterHook();
    ui::packet::kGetColor packet = { color, chan };
    *packet.color = g_chat_sender_color[chan];
    ui::SendUIMessage(ui::UIMessage::kGetSenderColor, &packet);
    PY4GW::HookBase::LeaveHook();
    return packet.color;
}

Color* __cdecl OnGetMessageColor(Color* color, Channel chan) {
    PY4GW::HookBase::EnterHook();
    ui::packet::kGetColor packet = { color, chan };
    *packet.color = g_chat_message_color[chan];
    ui::SendUIMessage(ui::UIMessage::kGetMessageColor, &packet);
    PY4GW::HookBase::LeaveHook();
    return packet.color;
}

void __cdecl OnSendChat(wchar_t* message, uint32_t agent_id) {
    PY4GW::HookBase::EnterHook();
    ui::packet::kSendChatMessage packet = { message, agent_id };
    ui::SendUIMessage(ui::UIMessage::kSendChatMessage, &packet);
    PY4GW::HookBase::LeaveHook();
}

void __cdecl OnRecvWhisper(uint32_t transaction_id, wchar_t* player_name, wchar_t* message) {
    PY4GW::HookBase::EnterHook();
    ui::packet::kRecvWhisper packet = { transaction_id, player_name, message };
    ui::SendUIMessage(ui::UIMessage::kRecvWhisper, &packet);
    PY4GW::HookBase::LeaveHook();
}

void __fastcall OnStartWhisper(ui::Frame* ctx, uint32_t, wchar_t* name) {
    PY4GW::HookBase::EnterHook();
    ui::packet::kStartWhisper packet = { name };
    ui::SendUIMessage(ui::UIMessage::kStartWhisper, &packet, ctx);
    PY4GW::HookBase::LeaveHook();
}

void __cdecl OnAddToChatLog(wchar_t* message, uint32_t channel) {
    PY4GW::HookBase::EnterHook();
    ui::packet::kLogChatMessage packet = { message, static_cast<Channel>(channel) };
    ui::SendUIMessage(ui::UIMessage::kLogChatMessage, &packet);
    PY4GW::HookBase::LeaveHook();
}

void __fastcall OnPrintChatMessage(void* ctx, uint32_t, Channel channel, wchar_t* message, FILETIME timestamp, uint32_t is_reprint) {
    PY4GW::HookBase::EnterHook();
    g_chat_window_context = ctx;
    ui::packet::kPrintChatMessage packet = { channel, message, timestamp, is_reprint };
    ui::SendUIMessage(ui::UIMessage::kPrintChatMessage, &packet);
    PY4GW::HookBase::LeaveHook();
}

void __cdecl OnUICallback_ChatLogLine(ui::InteractionMessage* message, void* wParam, void* lParam) {
    PY4GW::HookBase::EnterHook();
    switch (static_cast<uint32_t>(message->message_id)) {
    case 0x4A: {
        g_show_timestamps = ui::GetPreference(Constants::FlagPreference::ShowChatTimestamps);
        if (g_show_timestamps != g_block_chat_timestamps.GetIsActive()) {
            g_block_chat_timestamps.TogglePatch();
        }

        auto* packet = static_cast<ui::packet::ChatLogLine*>(wParam);

        const auto old_message = packet->message;

        auto new_message = g_show_timestamps ? ChatMessageWithTimestamp(packet->message, packet->channel, packet->timestamp) : nullptr;
        if (new_message) {
            packet->message = new_message;
        }
        g_uicallback_chat_log_line_original(message, wParam, lParam);
        packet->message = old_message;
        if (new_message) {
            delete[] new_message;
        }
    } break;
    default:
        g_uicallback_chat_log_line_original(message, wParam, lParam);
        break;
    }
    PY4GW::HookBase::LeaveHook();
}

void __cdecl OnUICallback_AssignEditableText(ui::InteractionMessage* message, void* wParam, void* lParam) {
    PY4GW::HookBase::EnterHook();
    auto* is_typing_frame_id = Context::GetIsTypingFrameIdAddress();
    if (message->message_id == ui::UIMessage::kDestroyFrame && is_typing_frame_id && *is_typing_frame_id == message->frame_id) {
        *is_typing_frame_id = 0;
    }
    g_uicallback_assign_editable_text_original(message, wParam, lParam);
    PY4GW::HookBase::LeaveHook();
}

void OnUIMessage(PY4GW::HookStatus* status, ui::UIMessage message_id, void* wparam, void* lparam) {
    if (status->blocked) {
        return;
    }
    switch (message_id) {
    case ui::UIMessage::kSendChatMessage: {
        const auto packet = static_cast<ui::packet::kSendChatMessage*>(wparam);
        if (GetChannel(*packet->message) == CHANNEL_COMMAND) {
            int argc = 0;
            LPWSTR* argv = CommandLineToArgvW(packet->message + 1, &argc);
            GWCA_ASSERT(argv && argc);
            wcs_tolower(*argv);

            for (const auto& [command_str, callback_handler] : g_chat_command_hook_entries) {
                if (command_str != *argv) {
                    continue;
                }
                status->blocked = true;
                callback_handler(status, packet->message, argc, const_cast<const wchar_t**>(argv));
            }
            LocalFree(argv);
        }
        if (!status->blocked && g_send_chat_original) {
            g_send_chat_original(packet->message, packet->agent_id);
            return;
        }
    } break;
    case ui::UIMessage::kStartWhisper: {
        if (g_start_whisper_original) {
            const auto packet = static_cast<ui::packet::kStartWhisper*>(wparam);
            const auto frame = lparam ? static_cast<ui::Frame*>(lparam) : ui::GetFrameByLabel(L"Chat");
            if (frame) {
                g_start_whisper_original(frame, 0, packet->player_name);
                return;
            }
        }
    } break;
    case ui::UIMessage::kLogChatMessage: {
        const auto packet = static_cast<ui::packet::kLogChatMessage*>(wparam);
        if (g_transient_chat_message && wcscmp(packet->message, g_transient_chat_message) == 0) {
            status->blocked = true;
            return;
        }
        if (g_add_to_chat_log_original) {
            g_add_to_chat_log_original(packet->message, static_cast<uint32_t>(packet->channel));
            return;
        }
    } break;
    case ui::UIMessage::kPrintChatMessage: {
        const auto packet = static_cast<ui::packet::kPrintChatMessage*>(wparam);
        if (g_print_chat_message_original) {
            g_print_chat_message_original(g_chat_window_context, 0, packet->channel, packet->message, packet->timestamp, packet->is_reprint);
            return;
        }
    } break;
    case ui::UIMessage::kRecvWhisper: {
        const auto packet = static_cast<ui::packet::kRecvWhisper*>(wparam);
        if (g_recv_whisper_original) {
            g_recv_whisper_original(packet->transaction_id, packet->from, packet->message);
            return;
        }
    } break;
    default:
        break;
    }
    status->blocked = true;
}

bool Init() {
    CrashContextScope context("startup", "chat", "init");
    if (!ResolveGetSenderColorFunction() ||
        !ResolveGetMessageColorFunction() ||
        !ResolveSendChatFunction() ||
        !ResolveStartWhisperFunction() ||
        !ResolveAddToChatLogFunction() ||
        !ResolveChatBufferAddress() ||
        !ResolveRecvWhisperFunction() ||
        !ResolvePrintChatMessageFunction() ||
        !ResolveIsTypingFrameId() ||
        !ResolveUICallbackAssignEditableText() ||
        !ResolveUICallbackChatLogLine()) {
        return false;
    }

    ResolveChatTimestampsPatch();

    const bool chat_log_line_ok = Logger::AssertHook(
        "UICallback_ChatLogLine_Func",
        PY4GW::HookBase::CreateHook(
            reinterpret_cast<void**>(&g_uicallback_chat_log_line_func),
            reinterpret_cast<void*>(&OnUICallback_ChatLogLine),
            reinterpret_cast<void**>(&g_uicallback_chat_log_line_original)),
        "chat");
    const bool start_whisper_ok = Logger::AssertHook(
        "StartWhisper_Func",
        PY4GW::HookBase::CreateHook(
            reinterpret_cast<void**>(&g_start_whisper_func),
            reinterpret_cast<void*>(&OnStartWhisper),
            reinterpret_cast<void**>(&g_start_whisper_original)),
        "chat");
    const bool get_sender_color_ok = Logger::AssertHook(
        "GetSenderColor_Func",
        PY4GW::HookBase::CreateHook(
            reinterpret_cast<void**>(&g_get_sender_color_func),
            reinterpret_cast<void*>(&OnGetSenderColor),
            reinterpret_cast<void**>(&g_get_sender_color_original)),
        "chat");
    const bool get_message_color_ok = Logger::AssertHook(
        "GetMessageColor_Func",
        PY4GW::HookBase::CreateHook(
            reinterpret_cast<void**>(&g_get_message_color_func),
            reinterpret_cast<void*>(&OnGetMessageColor),
            reinterpret_cast<void**>(&g_get_message_color_original)),
        "chat");
    const bool send_chat_ok = Logger::AssertHook(
        "SendChat_Func",
        PY4GW::HookBase::CreateHook(
            reinterpret_cast<void**>(&g_send_chat_func),
            reinterpret_cast<void*>(&OnSendChat),
            reinterpret_cast<void**>(&g_send_chat_original)),
        "chat");
    const bool recv_whisper_ok = Logger::AssertHook(
        "RecvWhisper_Func",
        PY4GW::HookBase::CreateHook(
            reinterpret_cast<void**>(&g_recv_whisper_func),
            reinterpret_cast<void*>(&OnRecvWhisper),
            reinterpret_cast<void**>(&g_recv_whisper_original)),
        "chat");
    const bool add_to_chat_log_ok = Logger::AssertHook(
        "AddToChatLog_Func",
        PY4GW::HookBase::CreateHook(
            reinterpret_cast<void**>(&g_add_to_chat_log_func),
            reinterpret_cast<void*>(&OnAddToChatLog),
            reinterpret_cast<void**>(&g_add_to_chat_log_original)),
        "chat");
    const bool assign_editable_text_ok = Logger::AssertHook(
        "UICallback_AssignEditableText_Func",
        PY4GW::HookBase::CreateHook(
            reinterpret_cast<void**>(&g_uicallback_assign_editable_text_func),
            reinterpret_cast<void*>(&OnUICallback_AssignEditableText),
            reinterpret_cast<void**>(&g_uicallback_assign_editable_text_original)),
        "chat");
    const bool print_chat_ok = Logger::AssertHook(
        "PrintChatMessage_Func",
        PY4GW::HookBase::CreateHook(
            reinterpret_cast<void**>(&g_print_chat_message_func),
            reinterpret_cast<void*>(&OnPrintChatMessage),
            reinterpret_cast<void**>(&g_print_chat_message_original)),
        "chat");

    for (size_t i = 0; i < static_cast<size_t>(Channel::CHANNEL_COUNT) && g_get_sender_color_original && g_get_message_color_original; i++) {
        const auto chan = static_cast<Channel>(i);
        g_chat_sender_color[chan] = 0;
        g_get_sender_color_original(&g_chat_sender_color[chan], chan);
        g_chat_message_color[chan] = 0;
        g_get_message_color_original(&g_chat_message_color[chan], chan);
    }

    return chat_log_line_ok && start_whisper_ok && get_sender_color_ok && get_message_color_ok &&
           send_chat_ok && recv_whisper_ok && add_to_chat_log_ok && assign_editable_text_ok && print_chat_ok;
}

void EnableHooks() {
    CrashContextScope context("runtime", "chat", "enable_hooks");
    if (g_uicallback_chat_log_line_func) {
        PY4GW::HookBase::EnableHooks(reinterpret_cast<void*>(g_uicallback_chat_log_line_func));
    }
    if (g_start_whisper_func) {
        PY4GW::HookBase::EnableHooks(reinterpret_cast<void*>(g_start_whisper_func));
    }
    if (g_get_sender_color_func) {
        PY4GW::HookBase::EnableHooks(reinterpret_cast<void*>(g_get_sender_color_func));
    }
    if (g_get_message_color_func) {
        PY4GW::HookBase::EnableHooks(reinterpret_cast<void*>(g_get_message_color_func));
    }
    if (g_send_chat_func) {
        PY4GW::HookBase::EnableHooks(reinterpret_cast<void*>(g_send_chat_func));
    }
    if (g_recv_whisper_func) {
        PY4GW::HookBase::EnableHooks(reinterpret_cast<void*>(g_recv_whisper_func));
    }
    if (g_add_to_chat_log_func) {
        PY4GW::HookBase::EnableHooks(reinterpret_cast<void*>(g_add_to_chat_log_func));
    }
    if (g_uicallback_assign_editable_text_func) {
        PY4GW::HookBase::EnableHooks(reinterpret_cast<void*>(g_uicallback_assign_editable_text_func));
    }
    for (const auto ui_message : g_ui_messages_to_hook) {
        ui::RegisterUIMessageCallback(&g_ui_message_entry, ui_message, &OnUIMessage, 0x1);
    }
}

void DisableHooks() {
    CrashContextScope context("shutdown", "chat", "disable_hooks");
    if (g_uicallback_chat_log_line_func) {
        PY4GW::HookBase::DisableHooks(reinterpret_cast<void*>(g_uicallback_chat_log_line_func));
    }
    if (g_start_whisper_func) {
        PY4GW::HookBase::DisableHooks(reinterpret_cast<void*>(g_start_whisper_func));
    }
    if (g_get_sender_color_func) {
        PY4GW::HookBase::DisableHooks(reinterpret_cast<void*>(g_get_sender_color_func));
    }
    if (g_get_message_color_func) {
        PY4GW::HookBase::DisableHooks(reinterpret_cast<void*>(g_get_message_color_func));
    }
    if (g_send_chat_func) {
        PY4GW::HookBase::DisableHooks(reinterpret_cast<void*>(g_send_chat_func));
    }
    if (g_recv_whisper_func) {
        PY4GW::HookBase::DisableHooks(reinterpret_cast<void*>(g_recv_whisper_func));
    }
    if (g_add_to_chat_log_func) {
        PY4GW::HookBase::DisableHooks(reinterpret_cast<void*>(g_add_to_chat_log_func));
    }
    if (g_uicallback_assign_editable_text_func) {
        PY4GW::HookBase::DisableHooks(reinterpret_cast<void*>(g_uicallback_assign_editable_text_func));
    }
    ui::RemoveUIMessageCallback(&g_ui_message_entry);
}

void Exit() {
    CrashContextScope context("shutdown", "chat", "exit");
    if (g_uicallback_chat_log_line_func) {
        PY4GW::HookBase::RemoveHook(reinterpret_cast<void*>(g_uicallback_chat_log_line_func));
    }
    if (g_start_whisper_func) {
        PY4GW::HookBase::RemoveHook(reinterpret_cast<void*>(g_start_whisper_func));
    }
    if (g_get_sender_color_func) {
        PY4GW::HookBase::RemoveHook(reinterpret_cast<void*>(g_get_sender_color_func));
    }
    if (g_get_message_color_func) {
        PY4GW::HookBase::RemoveHook(reinterpret_cast<void*>(g_get_message_color_func));
    }
    if (g_send_chat_func) {
        PY4GW::HookBase::RemoveHook(reinterpret_cast<void*>(g_send_chat_func));
    }
    if (g_recv_whisper_func) {
        PY4GW::HookBase::RemoveHook(reinterpret_cast<void*>(g_recv_whisper_func));
    }
    if (g_add_to_chat_log_func) {
        PY4GW::HookBase::RemoveHook(reinterpret_cast<void*>(g_add_to_chat_log_func));
    }
    if (g_uicallback_assign_editable_text_func) {
        PY4GW::HookBase::RemoveHook(reinterpret_cast<void*>(g_uicallback_assign_editable_text_func));
    }

    g_block_chat_timestamps.Reset();

    while (!g_chat_command_hook_entries.empty()) {
        DeleteCommand(g_chat_command_hook_entries.begin()->first.c_str());
    }

    g_get_sender_color_func = nullptr;
    g_get_sender_color_original = nullptr;
    g_get_message_color_func = nullptr;
    g_get_message_color_original = nullptr;
    g_send_chat_func = nullptr;
    g_send_chat_original = nullptr;
    g_recv_whisper_func = nullptr;
    g_recv_whisper_original = nullptr;
    g_start_whisper_func = nullptr;
    g_start_whisper_original = nullptr;
    g_add_to_chat_log_func = nullptr;
    g_add_to_chat_log_original = nullptr;
    g_print_chat_message_func = nullptr;
    g_print_chat_message_original = nullptr;
    g_uicallback_chat_log_line_func = nullptr;
    g_uicallback_chat_log_line_original = nullptr;
    g_uicallback_assign_editable_text_func = nullptr;
    g_uicallback_assign_editable_text_original = nullptr;
    g_chat_window_context = nullptr;
    g_transient_chat_message = nullptr;
    g_chat_sender_color.clear();
    g_chat_message_color.clear();
}

bool Initialize() {
    CrashContextScope context("startup", "chat", "initialize");
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
    CrashContextScope context("shutdown", "chat", "shutdown");
    if (!g_initialized) {
        return;
    }

    DisableHooks();
    Exit();
    PY4GW::HookBase::Deinitialize();
    g_initialized = false;
}

}  // namespace GW::chat
