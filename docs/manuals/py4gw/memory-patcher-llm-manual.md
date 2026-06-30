# MemoryPatcher LLM Manual

`MemoryPatcher` is a lifecycle-sensitive subsystem.

Important semantics:

- `SetPatch()` captures original bytes
- `TogglePatch()` changes `active_`
- `PatchActual()` applies or restores bytes
- tracked patchers participate in global enable/disable

Recent practical constraint:

- process exit may bypass orderly shutdown, so teardown logic must avoid turning surviving patchers into hard process failures

When changing it:

- preserve restoration-before-destruction intent
- keep patch application small and explicit
- avoid introducing hidden ownership or dynamic indirection
- log abnormal teardown conditions, but do not force new crash paths without a strong reason
