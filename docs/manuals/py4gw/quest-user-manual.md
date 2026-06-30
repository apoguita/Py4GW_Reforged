# Quest User Manual

`GW::quest` handles active-quest operations and async quest text decoding.

Main capabilities:

- set or abandon active quests
- request quest info and marker updates
- decode quest name, description, objectives, location, and NPC text asynchronously

Representative API:

- `SetActiveQuestId(...)`
- `AbandonQuestId(...)`
- `RequestQuestInfo(...)`
- `AsyncGetQuestName(...)`
- `AsyncGetQuestDescription(...)`

Use it for quest interaction and user-facing quest text retrieval.
