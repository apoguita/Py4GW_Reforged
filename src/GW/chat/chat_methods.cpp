#include "base/error_handling.h"

#include "base/logger.h"

#include "GW/chat/chat.h"

#include "GW/game_thread/game_thread.h"
#include "GW/ui/ui.h"

#include <cstdarg>
#include <iomanip>
#include <map>
#include <sstream>
#include <string>
#include <unordered_map>

namespace GW::chat {
    using GetChannelColorFn = Color*(__cdecl*)(Color* color, Channel chan);
    using SendChatFn = void(__cdecl*)(wchar_t* message, uint32_t agent_id);
    using RecvWhisperFn = void(__cdecl*)(uint32_t transaction_id, wchar_t* player_name, wchar_t* message);
    using StartWhisperFn = void(__fastcall*)(ui::Frame* ctx, uint32_t edx, wchar_t* name);
    using AddToChatLogFn = void(__cdecl*)(wchar_t* message, uint32_t channel);
    using PrintChatMessageFn = void(__fastcall*)(void* ctx, uint32_t edx, Channel channel, wchar_t* message, FILETIME timestamp, uint32_t is_reprint);

    extern AddToChatLogFn g_add_to_chat_log_func;
    extern SendChatFn g_send_chat_func;
    extern const wchar_t* g_transient_chat_message;
    extern GetChannelColorFn g_get_sender_color_func;
    extern GetChannelColorFn g_get_message_color_func;
    extern GetChannelColorFn g_get_sender_color_original;
    extern GetChannelColorFn g_get_message_color_original;
    extern std::map<Channel, Color> g_chat_sender_color;
    extern std::map<Channel, Color> g_chat_message_color;
    extern std::unordered_map<std::wstring, ChatCommandCallback> g_chat_command_hook_entries;
    extern bool g_timestamp_24h_format;
    extern bool g_timestamp_seconds;
    extern Color g_timestamps_color;

    void ForceRedrawChatLog() {
        game_thread::Enqueue([]() {
            const auto log = ui::GetFrameByLabel(L"Log");
            if (!(log && log->IsCreated() && log->IsVisible())) {
                return;
            }
            struct {
                Constants::FlagPreference pref = Constants::FlagPreference::ShowChatTimestamps;
                uint32_t val = static_cast<uint32_t>(ui::GetPreference(Constants::FlagPreference::ShowChatTimestamps));
            } packet;
            ui::SendUIMessage(ui::UIMessage::kPreferenceFlagChanged, &packet);
            });
    }

Channel GetChannel(char opcode) {
    switch (opcode) {
    case '!': return CHANNEL_ALL;
    case '@': return CHANNEL_GUILD;
    case '#': return CHANNEL_GROUP;
    case '$': return CHANNEL_TRADE;
    case '%': return CHANNEL_ALLIANCE;
    case '"': return CHANNEL_WHISPER;
    case '/': return CHANNEL_COMMAND;
    default:  return CHANNEL_UNKNOW;
    }
}

Channel GetChannel(wchar_t opcode) {
    return GetChannel(static_cast<char>(opcode));
}

Context::ChatBuffer* GetChatLog() {
    auto* chat_buffer_addr = Context::GetChatBufferAddress();
    return chat_buffer_addr ? *chat_buffer_addr : nullptr;
}

bool AddToChatLog(wchar_t* message, uint32_t channel) {
    if (!(g_add_to_chat_log_func && message && *message)) {
        return false;
    }
    ui::packet::kLogChatMessage packet = { message, static_cast<Channel>(channel) };
    return ui::SendUIMessage(ui::UIMessage::kLogChatMessage, &packet);
}

bool GetIsTyping() {
    const auto* is_typing_frame_id = Context::GetIsTypingFrameIdAddress();
    return is_typing_frame_id && *is_typing_frame_id != 0;
}

bool SendChat(char channel, const wchar_t* msg) {
    if (!(g_send_chat_func && msg && *msg && GetChannel(channel) != CHANNEL_UNKNOW)) {
        return false;
    }

    wchar_t buffer[140];

    size_t len = wcslen(msg);
    len = len > 120 ? 120 : len;

    buffer[0] = static_cast<wchar_t>(channel);
    wcsncpy(&buffer[1], msg, len);
    buffer[len + 1] = 0;
    g_send_chat_func(buffer, 0);
    return true;
}

bool SendChat(char channel, const char* msg) {
    wchar_t buffer[140];
    int written = swprintf(buffer, 140, L"%S", msg);
    if (!(written > 0 && written < 140)) {
        return false;
    }
    buffer[written] = 0;
    return SendChat(channel, buffer);
}

bool SendChat(const wchar_t* from, const wchar_t* msg) {
    wchar_t buffer[140];
    if (!(g_send_chat_func && from && *from && msg && *msg)) {
        return false;
    }
    int written = swprintf(buffer, 140, L"\"%s,%s", from, msg);
    if (!(written > 0 && written < 140)) {
        return false;
    }
    buffer[written] = 0;
    g_send_chat_func(buffer, 0);
    return true;
}

bool SendChat(const char* from, const char* msg) {
    GWCA_ASSERT(g_send_chat_func);
    wchar_t buffer[140];
    if (!(g_send_chat_func && from && *from && msg && *msg)) {
        return false;
    }
    int written = swprintf(buffer, 140, L"\"%S,%S", from, msg);
    if (!(written > 0 && written < 140)) {
        return false;
    }
    buffer[written] = 0;
    g_send_chat_func(buffer, 0);
    return true;
}

void WriteChatF(Channel channel, const wchar_t* format, ...) {
    va_list vl;
    va_start(vl, format);
    size_t szbuf = vswprintf(nullptr, 0, format, vl) + 1;
    wchar_t* chat = new wchar_t[szbuf];
    vswprintf(chat, szbuf, format, vl);
    va_end(vl);

    WriteChat(channel, chat);
    delete[] chat;
}

void WriteChat(Channel channel, const wchar_t* message_unencoded, const wchar_t* sender_unencoded, bool transient) {
    size_t len = wcslen(message_unencoded) + 4;
    wchar_t* message_encoded = new wchar_t[len];
    GWCA_ASSERT(swprintf(message_encoded, len, L"\x108\x107%s\x1", message_unencoded) >= 0);
    wchar_t* sender_encoded = nullptr;
    if (sender_unencoded) {
        len = wcslen(sender_unencoded) + 4;
        sender_encoded = new wchar_t[len];
        GWCA_ASSERT(swprintf(sender_encoded, len, L"\x108\x107%s\x1", sender_unencoded) >= 0);
    }
    WriteChatEnc(channel, message_encoded, sender_encoded, transient);
    delete[] message_encoded;
    if (sender_encoded) {
        delete[] sender_encoded;
    }
}

void WriteChatEnc(Channel channel, const wchar_t* message_encoded, const wchar_t* sender_encoded, bool transient) {
    ui::UIChatMessage param;
    param.channel = param.channel2 = static_cast<uint32_t>(channel);
    param.message = const_cast<wchar_t*>(message_encoded);
    bool delete_message = false;
    if (sender_encoded) {
        const wchar_t* format = L"\x76b\x10a%s\x1\x10b%s\x1";
        size_t len = wcslen(message_encoded) + wcslen(sender_encoded) + 6;
        bool has_link_in_message = wcsstr(message_encoded, L"<a=1>") != nullptr;
        bool has_markup = has_link_in_message || wcsstr(message_encoded, L"<c=") != nullptr;
        if (has_markup) {
            if (has_link_in_message) {
                format = L"\x108\x107<a=2>\x1\x2%s\x2\x108\x107</a>\x1\x2\x108\x107: \x1\x2%s";
            }
            else {
                format = L"\x108\x107<a=1>\x1\x2%s\x2\x108\x107</a>\x1\x2\x108\x107: \x1\x2%s";
            }
            len += 19;
        }
        param.message = new wchar_t[len];
        delete_message = true;
        GWCA_ASSERT(swprintf(param.message, len, format, sender_encoded, message_encoded) >= 0);
    }
    g_transient_chat_message = transient ? param.message : nullptr;
    ui::SendUIMessage(ui::UIMessage::kWriteToChatLog, &param);
    g_transient_chat_message = nullptr;
    if (delete_message) {
        delete[] param.message;
    }
}

Color SetSenderColor(Channel chan, Color col) {
    Color old = 0;
    GetChannelColors(chan, &old, nullptr);
    g_chat_sender_color[chan] = col;
    return old;
}

Color SetMessageColor(Channel chan, Color col) {
    Color old = 0;
    GetChannelColors(chan, nullptr, &old);
    g_chat_message_color[chan] = col;
    return old;
}

void GetChannelColors(Channel chan, Color* sender, Color* message) {
    if (sender && g_get_sender_color_func) {
        g_get_sender_color_func(sender, chan);
    }
    if (message && g_get_message_color_func) {
        g_get_message_color_func(message, chan);
    }
}

void GetDefaultColors(Channel chan, Color* sender, Color* message) {
    if (sender && g_get_sender_color_original) {
        g_get_sender_color_original(sender, chan);
    }
    if (message && g_get_message_color_original) {
        g_get_message_color_original(message, chan);
    }
}

void ToggleTimestamps(bool enable) {
    ui::SetPreference(Constants::FlagPreference::ShowChatTimestamps, enable);
}

void SetTimestampsFormat(bool use_24h, bool show_timestamp_seconds) {
    g_timestamp_24h_format = use_24h;
    g_timestamp_seconds = show_timestamp_seconds;
    ForceRedrawChatLog();
}

void SetTimestampsColor(Color color) {
    g_timestamps_color = color;
    ForceRedrawChatLog();
}

void CreateCommand(const wchar_t* cmd, ChatCommandCallback callback) {
    g_chat_command_hook_entries[cmd] = callback;
}

void DeleteCommand(const wchar_t* cmd) {
    const auto found = g_chat_command_hook_entries.find(cmd);
    if (found != g_chat_command_hook_entries.end()) {
        g_chat_command_hook_entries.erase(found);
    }
}

void SendFakeChat(int channel, std::string message) {
    std::wstring wmessage(message.begin(), message.end());
    game_thread::Enqueue([channel, wmessage]() {
        WriteChat(static_cast<Channel>(channel), wmessage.c_str(), nullptr, true);
    });
}

void SendFakeChatColored(int channel, std::string message, int r, int g, int b) {
    std::string formatted_message = FormatChatMessage(message, r, g, b);
    std::wstring wformatted_message(formatted_message.begin(), formatted_message.end());
    game_thread::Enqueue([channel, wformatted_message]() {
        WriteChat(static_cast<Channel>(channel), wformatted_message.c_str(), nullptr, true);
    });
}

std::string FormatChatMessage(const std::string message, int r, int g, int b) {
    r = std::max(1, std::min(255, r));
    g = std::max(1, std::min(255, g));
    b = std::max(1, std::min(255, b));

    std::ostringstream formatted;
    formatted << "<c=#" << std::hex << std::uppercase << std::setfill('0')
        << std::setw(2) << r
        << std::setw(2) << g
        << std::setw(2) << b
        << ">" << message << "</c>";

    return formatted.str();
}

}  // namespace GW::chat
