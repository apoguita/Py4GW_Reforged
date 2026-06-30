# Agent User Manual

`GW::agent` is the gameplay-facing agent subsystem.

Main capabilities from `include/GW/agent/agent.h`:

- agent array access
- target inspection and target changes
- controlled-character access
- movement and world interaction
- dialog sending
- name lookup and async decode helpers

Representative API:

- `GetAgentArray()`
- `GetAgentByID(...)`
- `GetTarget()`
- `GetControlledCharacter()`
- `ChangeTarget(...)`
- `Move(...)`
- `InteractAgent(...)`
- `CallTarget(...)`
- `AsyncGetAgentName(...)`

Use it when you need agent-level game interaction instead of raw context traversal.
