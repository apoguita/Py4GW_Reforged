# ProcessManager LLM Manual

`process_manager` is intentionally small. Keep it that way.

It exists to centralize path and module-handle discovery so other subsystems do not each call `GetModuleFileNameW` in inconsistent ways.

Current notable behavior:

- `SetModuleHandle()` now also caches the resolved DLL path
- `GetModuleDirectory()` is derived from the cached path

Do not turn it into a general process abstraction layer. Its value is predictability and low risk.
