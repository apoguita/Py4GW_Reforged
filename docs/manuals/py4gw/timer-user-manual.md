# Timer User Manual

`PY4GW::Timer` is a small utility for elapsed-time checks.

Main operations in `include/base/timer.h`:

- `start()`
- `stop()`
- `Pause()`
- `Resume()`
- `reset()`
- `getElapsedTime()`
- `hasElapsed(...)`

State queries:

- `isStopped()`
- `isRunning()`
- `IsPaused()`
- `HasValidData()`

Use it for lightweight timing such as deferred script actions and simple periodic checks.
