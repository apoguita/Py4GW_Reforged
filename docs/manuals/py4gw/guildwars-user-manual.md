# GuildWars User Manual

`GW::Initialize()` and `GW::Shutdown()` are the top-level orchestration entry points for the Guild Wars subsystem layer.

Public API:

- `GW::Initialize()`
- `GW::Shutdown()`

What it does:

- initializes manager modules in a defined order
- shuts them down in reverse order
- enables and disables shared patch/hook infrastructure around that lifecycle

Use this as the single entry point for the GW layer. Do not manually initialize a random subset unless you are intentionally building a special test path.
