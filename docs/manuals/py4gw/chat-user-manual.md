# Chat User Manual

`GW::chat` is the in-game chat subsystem.

Main capabilities:

- send chat and whispers
- write messages to chat log or transient display
- inspect typing state
- control channel colors and timestamp formatting
- register slash-style commands

Representative API:

- `SendChat(...)`
- `WriteChat(...)`
- `WriteChatEnc(...)`
- `ToggleTimestamps(...)`
- `SetTimestampsFormat(...)`
- `CreateCommand(...)`
- `DeleteCommand(...)`

Use it for player-facing messaging and chat customization.
