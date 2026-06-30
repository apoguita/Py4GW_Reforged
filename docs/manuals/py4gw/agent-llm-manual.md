# Agent LLM Manual

`agent` is both a data access layer and a UI-message/hook bridge.

Important traits:

- aliases many `GW::Context` types
- owns gameplay action entry points
- participates in UI message hook flow
- depends on pointer resolution for core actions

When editing:

- preserve the distinction between read-only accessors and action methods
- keep `ChangeTarget`, `CallTarget`, and interaction flows aligned with UI/world-action semantics
- prefer the resolver-backed path already present in the subsystem
