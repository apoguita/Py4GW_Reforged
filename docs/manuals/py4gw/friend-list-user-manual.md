# Friend List User Manual

`GW::friend_list` manages the in-game friend and ignore systems.

Main capabilities:

- query friend counts
- set online status
- add and remove friend-list entries
- register status callbacks

Representative API:

- `GetNumberOfFriends(...)`
- `SetFriendListStatus(...)`
- `AddFriend(...)`
- `AddIgnore(...)`
- `RemoveFriend(...)`
- `RegisterFriendStatusCallback(...)`

Use it for roster operations and friend-status observation.
