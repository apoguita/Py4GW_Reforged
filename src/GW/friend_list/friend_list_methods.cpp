#include "base/error_handling.h"

#include "GW/context/context.h"
#include "GW/friend_list/friend_list.h"

#include <array>
#include <cwchar>
#include <cstring>
#include <unordered_map>

namespace GW::friend_list {

using SetOnlineStatusFn = void(__cdecl*)(Constants::FriendStatus status);
using AddFriendFn = void(__cdecl*)(const wchar_t* name, const wchar_t* alias, Constants::FriendType type);
using RemoveFriendFn = void(__cdecl*)(const uint8_t* uuid, const wchar_t* name, uint32_t arg8);

extern SetOnlineStatusFn g_set_online_status_func;
extern AddFriendFn g_add_friend_func;
extern RemoveFriendFn g_remove_friend_func;
extern std::unordered_map<PY4GW::HookEntry*, FriendStatusCallback> g_friend_status_callbacks;

void RegisterFriendStatusCallback(
    PY4GW::HookEntry* entry,
    const FriendStatusCallback& callback) {
    RemoveFriendStatusCallback(entry);
    g_friend_status_callbacks[entry] = callback;
}

void RemoveFriendStatusCallback(PY4GW::HookEntry* entry) {
    const auto found = g_friend_status_callbacks.find(entry);
    if (found != g_friend_status_callbacks.end()) {
        g_friend_status_callbacks.erase(found);
    }
}

Context::Friend* GetFriend(const wchar_t* alias, const wchar_t* charname, Constants::FriendType type) {
    if (!(alias || charname)) {
        return nullptr;
    }

    const auto* friend_list = Context::GetFriendList();
    if (!friend_list) {
        return nullptr;
    }

    auto& friends = friend_list->friends;
    for (auto friend_entry : friends) {
        if (!(friend_entry && (type == Constants::FriendType::Unknow || friend_entry->type == type))) {
            continue;
        }
        if (alias && std::wcsncmp(friend_entry->alias, alias, std::size(friend_entry->alias)) == 0) {
            return friend_entry;
        }
        if (charname && std::wcsncmp(friend_entry->charname, charname, std::size(friend_entry->charname)) == 0) {
            return friend_entry;
        }
    }
    return nullptr;
}

Context::Friend* GetFriend(uint32_t index) {
    const auto* friend_list = Context::GetFriendList();
    if (!friend_list || index >= friend_list->friends.size()) {
        return nullptr;
    }
    return friend_list->friends[index];
}

Context::Friend* GetFriend(const uint8_t* uuid) {
    const auto* friend_list = Context::GetFriendList();
    if (!friend_list) {
        return nullptr;
    }

    auto& friends = friend_list->friends;
    for (auto friend_entry : friends) {
        if (friend_entry && std::memcmp(friend_entry->uuid, uuid, 16) == 0) {
            return friend_entry;
        }
    }
    return nullptr;
}

uint32_t GetNumberOfFriends(Constants::FriendType type) {
    const auto* friend_list = Context::GetFriendList();
    if (!friend_list) {
        return 0;
    }

    switch (type) {
    case Constants::FriendType::Friend:
        return friend_list->number_of_friend;
    case Constants::FriendType::Ignore:
        return friend_list->number_of_ignore;
    case Constants::FriendType::Player:
        return friend_list->number_of_partner;
    case Constants::FriendType::Trade:
        return friend_list->number_of_trade;
    default:
        return 0;
    }
}

uint32_t GetNumberOfIgnores() {
    return GetNumberOfFriends(Constants::FriendType::Ignore);
}

uint32_t GetNumberOfPartners() {
    return GetNumberOfFriends(Constants::FriendType::Player);
}

uint32_t GetNumberOfTraders() {
    return GetNumberOfFriends(Constants::FriendType::Trade);
}

Constants::FriendStatus GetMyStatus() {
    const auto* friend_list = Context::GetFriendList();
    return friend_list ? friend_list->player_status : Constants::FriendStatus::Offline;
}

bool SetFriendListStatus(Constants::FriendStatus status) {
    if (!g_set_online_status_func) {
        return false;
    }
    g_set_online_status_func(status);
    return true;
}

bool AddFriend(const wchar_t* name, const wchar_t* alias) {
    if (!(g_add_friend_func && name && name[0])) {
        return false;
    }

    wchar_t* buffer = nullptr;
    const wchar_t* use_alias = alias;
    if (!use_alias) {
        const size_t length = std::wcslen(name);
        buffer = new wchar_t[length + 1];
        PY4GW_ASSERT(buffer);
        std::wcscpy(buffer, name);
        use_alias = buffer;
    }

    g_add_friend_func(name, use_alias, Constants::FriendType::Friend);
    delete[] buffer;
    return true;
}

bool AddIgnore(const wchar_t* name, const wchar_t* alias) {
    if (!(g_add_friend_func && name && name[0])) {
        return false;
    }

    wchar_t* buffer = nullptr;
    const wchar_t* use_alias = alias;
    if (!use_alias) {
        const size_t length = std::wcslen(name);
        buffer = new wchar_t[length + 1];
        PY4GW_ASSERT(buffer);
        std::wcscpy(buffer, name);
        use_alias = buffer;
    }

    g_add_friend_func(name, use_alias, Constants::FriendType::Ignore);
    delete[] buffer;
    return true;
}

bool RemoveFriend(Context::Friend* friend_entry) {
    if (!(friend_entry && g_remove_friend_func)) {
        return false;
    }

    g_remove_friend_func(friend_entry->uuid, friend_entry->alias, 0);
    return true;
}

}  // namespace GW::friend_list
