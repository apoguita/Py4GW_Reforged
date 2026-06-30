# Game Thread LLM Manual

`game_thread` is a thread-affinity boundary.

Rules:

- code that mutates thread-bound game state should usually go through `Enqueue(...)`
- callback registration is shared infrastructure and must stay reliable under shutdown
- preserve leave-game-thread hook behavior because it is the heartbeat for queued work
