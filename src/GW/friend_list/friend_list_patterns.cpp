#include "base/error_handling.h"

#include "base/CrashHandler.h"
#include "base/patterns.h"

#include "GW/friend_list/friend_list.h"

namespace GW::Context {
extern uintptr_t g_friend_list_addr;
}

namespace GW::friend_list {

using FriendEventHandlerFn = void(__cdecl*)(void*, void*);
using SetOnlineStatusFn = void(__cdecl*)(Constants::FriendStatus status);
using AddFriendFn = void(__cdecl*)(const wchar_t* name, const wchar_t* alias, Constants::FriendType type);
using RemoveFriendFn = void(__cdecl*)(const uint8_t* uuid, const wchar_t* name, uint32_t arg8);

extern FriendEventHandlerFn g_friend_event_handler_func;
extern SetOnlineStatusFn g_set_online_status_func;
extern AddFriendFn g_add_friend_func;
extern RemoveFriendFn g_remove_friend_func;

bool ResolveFriendListPointer() {
    CrashContextScope context("startup", "friend_list", "resolve_friend_list_pointer");
    return PY4GW::Patterns::Resolve("friend_list.friend_list_addr", &Context::g_friend_list_addr);
}

bool ResolveFriendEventHandler() {
    CrashContextScope context("startup", "friend_list", "resolve_friend_event_handler");
    return PY4GW::Patterns::Resolve("friend_list.friend_event_handler_func", &g_friend_event_handler_func);
}

bool ResolveSetOnlineStatus() {
    CrashContextScope context("startup", "friend_list", "resolve_set_online_status");
    return PY4GW::Patterns::Resolve("friend_list.set_online_status_func", &g_set_online_status_func);
}

bool ResolveAddFriend() {
    CrashContextScope context("startup", "friend_list", "resolve_add_friend");
    return PY4GW::Patterns::Resolve("friend_list.add_friend_func", &g_add_friend_func);
}

bool ResolveRemoveFriend() {
    CrashContextScope context("startup", "friend_list", "resolve_remove_friend");
    return PY4GW::Patterns::Resolve("friend_list.remove_friend_func", &g_remove_friend_func);
}

}  // namespace GW::friend_list
