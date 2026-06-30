# Timer LLM Manual

`Timer` is intentionally simple and clock-based.

Important behavior:

- `reset()` starts the timer immediately
- paused timers report elapsed paused time
- `hasElapsed()` returns false while paused or stopped

Do not over-engineer this subsystem. If you need high-resolution, thread-safe, or monotonic timing semantics beyond `std::clock()`, that is a design change, not a cleanup.

For ordinary Py4GW use, the value is its small API and predictable behavior, not precision.
