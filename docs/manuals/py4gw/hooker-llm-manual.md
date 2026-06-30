# Hooker LLM Manual

`HookBase` is a shared subsystem. Treat changes here as high blast radius.

Rules:

- preserve idempotent init/deinit behavior
- do not leak hooks across module shutdown
- keep `EnterHook()` and `LeaveHook()` balanced
- assume callers rely on `GetInHookCount()` during shutdown coordination

`THook<T>` is thin sugar, not the core contract. The real contract is the static `HookBase` API.

When touching hook call sites:

- prefer explicit create/enable/disable/remove stages
- avoid mixing hook lifecycle with unrelated pointer resolution
- keep shutdown ordering clear so subsystems can drain in-flight hooks before removing them
