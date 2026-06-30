# MemoryManager LLM Manual

`MemoryManager` is a thin bridge over scanned engine helpers.

Current design:

- `Scan()` resolves required surfaces
- public methods call through resolved pointers or addresses

Do not turn it into a stateful allocator framework. Its scope is narrow and engine-facing.

When changing it:

- prefer JSON-backed `Patterns::Resolve()` for new surfaces
- preserve the meaning of existing helpers
- keep failure behavior strict for required primitives
