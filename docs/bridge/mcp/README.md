# Bridge and MCP Documentation Map

This folder contains the architecture note for exposing Py4GW capabilities to
external operators and MCP clients. It is separate from the shared-memory
implementation records and from `py4gw_bridge/`, which contains the bridge
implementation and its local operator guide.

## Authority and status

- `mcp-bridge.md` is the MCP-facing architecture and planning note, not the
  complete conceptual architecture source.
- `docs/architecture/reference/py4-gw-conceptual-model.md` remains the conceptual source of truth.
- `py4gw_bridge/README.md` documents daemon, injected client, CLI, MCP, and
  transport operation.
- `py4gw_bridge/mcp_server.py`, `py4gw_bridge/daemon.py`, and `py4gw_bridge/cli.py` are current
  implementation entry points; inspect them before treating the note's
  "missing" list as current.
- The adapter intentionally exposes a narrow safe tool set. Do not infer that
  arbitrary reflective or mutating bridge calls are supported.

## Related integration records

- `../shared_memory/README.md` — Python/C++ shared-memory writer migration and
  layout invariants.
- `../../Py4GWCoreLib/GlobalCache/SharedMemory.py` — shared-memory consumer
  implementation.
- `../../Widgets/Coding/Tools/Bridge Client.py` — injected bridge client.

## Review order

1. Read the conceptual model for layer ownership.
2. Read `mcp-bridge.md` for bridge namespace and exposure assumptions.
3. Inspect the daemon, CLI, MCP adapter, and injected client for current
   behavior.
4. Consult `py4gw_bridge/README.md` for bridge operator procedures.
