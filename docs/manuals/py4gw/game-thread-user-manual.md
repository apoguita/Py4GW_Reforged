# Game Thread User Manual

`GW::game_thread` is the scheduling surface for code that must execute on the Guild Wars game thread.

Main API:

- `Enqueue(...)`
- `RegisterGameThreadCallback(...)`
- `RemoveGameThreadCallback(...)`
- `ClearCalls()`
- `IsInGameThread()`

Use it when a subsystem needs thread-affine execution and cannot safely run work from the caller’s current thread.
