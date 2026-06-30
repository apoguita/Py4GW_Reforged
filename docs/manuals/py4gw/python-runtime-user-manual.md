# Python Runtime User Manual

`PY4GW::python_runtime` owns the embedded Python interpreter and script execution loop.

Main API in `include/base/python_runtime.h`:

- `Initialize()`
- `Shutdown()`
- `ExecutePythonUpdate()`
- `ExecutePythonDraw()`
- `ProcessDeferredActions()`
- script load/run/stop/pause/resume helpers
- deferred restart helpers
- `ExecuteCommand(...)`
- state inspection helpers

Main script states:

- `Stopped`
- `Running`
- `Paused`

Use it for embedded Python script hosting, not for general application state management.
