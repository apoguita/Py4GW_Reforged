# ProcessManager User Manual

`PY4GW::process_manager` is the shared source of module and process paths.

Main API in `include/base/process_manager.h`:

- `SetModuleHandle(...)`
- `GetModuleHandle()`
- `GetModulePath()`
- `GetModuleDirectory()`
- `GetProcessDirectory()`

Use it when code needs:

- the DLL module handle
- the resolved DLL path
- the DLL directory
- the host process directory

The module handle is set during `DLL_PROCESS_ATTACH`.
