#pragma once

#include "base/hook_types.h"
#include "GW/common/constants/chat.h"
#include "GW/context/chat.h"
#include "GW/ui/ui.h"

#include <cstdint>
#include <string>
#include <windows.h>

namespace GW::chat {
	using ChatCommandCallback = void(__cdecl*)(PY4GW::HookStatus*, const wchar_t* cmd, int argc, const wchar_t** argv);
	bool Initialize();
	void Shutdown();

	void ForceRedrawChatLog();
	Channel GetChannel(char opcode);
	Channel GetChannel(wchar_t opcode);

	Context::ChatBuffer* GetChatLog();
	bool AddToChatLog(wchar_t* message, uint32_t channel);
	bool GetIsTyping();

	bool SendChat(char channel, const wchar_t* msg);
	bool SendChat(char channel, const char* msg);
	bool SendChat(const wchar_t* from, const wchar_t* msg);
	bool SendChat(const char* from, const char* msg);

	void WriteChatF(Channel channel, const wchar_t* format, ...);
	void WriteChat(Channel channel, const wchar_t* message, const wchar_t* sender = nullptr, bool transient = false);
	void WriteChatEnc(Channel channel, const wchar_t* message, const wchar_t* sender = nullptr, bool transient = false);

	Color SetSenderColor(Channel chan, Color col);
	Color SetMessageColor(Channel chan, Color col);
	void GetChannelColors(Channel chan, Color* sender, Color* message);
	void GetDefaultColors(Channel chan, Color* sender, Color* message);

	void ToggleTimestamps(bool enable);
	void SetTimestampsFormat(bool use_24h, bool show_timestamp_seconds = false);
	void SetTimestampsColor(Color color);

	void CreateCommand(const wchar_t* cmd, ChatCommandCallback callback);
	void DeleteCommand(const wchar_t* cmd);

	void SendFakeChat(int channel, std::string message);
	void SendFakeChatColored(int channel, std::string message, int r, int g, int b);
	std::string FormatChatMessage(const std::string message, int r, int g, int b);

}  // namespace GW::chat

namespace GW {
namespace Chat = chat;
}
