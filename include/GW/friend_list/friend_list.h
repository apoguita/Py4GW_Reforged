#pragma once

#include "base/hook_types.h"
#include "GW/common/constants/friend_list.h"
#include "GW/context/friend_list.h"

#include <cstdint>

namespace GW::friend_list {
    bool Initialize();
    void Shutdown();

    using FriendStatusCallback = PY4GW::HookCallback<const Context::Friend*, const Context::Friend*>;
    void RegisterFriendStatusCallback(
        PY4GW::HookEntry* entry,
        const FriendStatusCallback& callback);
    void RemoveFriendStatusCallback(PY4GW::HookEntry* entry);

    Context::Friend* GetFriend(const wchar_t* alias, const wchar_t* charname, Constants::FriendType type = Constants::FriendType::Friend);
    Context::Friend* GetFriend(uint32_t index);
    Context::Friend* GetFriend(const uint8_t* uuid);

    uint32_t GetNumberOfFriends(Constants::FriendType type = Constants::FriendType::Friend);
    uint32_t GetNumberOfIgnores();
    uint32_t GetNumberOfPartners();
    uint32_t GetNumberOfTraders();

    Constants::FriendStatus GetMyStatus();
    bool SetFriendListStatus(Constants::FriendStatus status);

    bool AddFriend(const wchar_t* name, const wchar_t* alias = nullptr);
    bool AddIgnore(const wchar_t* name, const wchar_t* alias = nullptr);
    bool RemoveFriend(Context::Friend* friend_entry);

}  // namespace GW::friend_list
