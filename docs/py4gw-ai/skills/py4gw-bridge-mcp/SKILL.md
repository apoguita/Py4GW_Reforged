---
name: py4gw-bridge-mcp
description: Use when a Py4GW bridge daemon, injected bridge widget, CLI, shared-memory path, MCP adapter, command schema, or runtime-control boundary must be investigated, changed, or reviewed.
---

# Py4GW Bridge and MCP

## Scope

- Own bridge/widget/daemon/CLI/MCP boundary analysis, command-schema review, client impact, and end-to-end verification planning.
- Do not expose a new live action or broaden a tool's authority without explicit user scope and an identified server-side owner.

## Evidence Order

1. Current bridge source, CLI/MCP adapter, command schema, and owning runtime widget.
2. `docs/bridge/README.md`, `docs/bridge/mcp/README.md`, and current shared memory records.
3. Local daemon/client/runtime reproduction with known endpoints and build.
4. Historical bridge records as evidence, never as an active contract.

## Current Orientation

- Start with `Widgets/Coding/Tools/Bridge Client.py`, `py4gw_bridge/daemon.py`,
  `py4gw_bridge/cli.py`, and `py4gw_bridge/mcp_server.py`; inspect their current schemas
  before relying on an operator document.
- The injected widget defaults to port `47811`; the daemon control, CLI, and
  MCP adapter default to `47812`. Treat these as defaults to verify, not a
  permission to contact a live client.
- The MCP adapter is intentionally narrow. Preserve the existing read-only
  discovery/state surface before considering any new runtime-control path.

## Workflow

1. Identify the caller, transport, server, injected-client owner, command or data schema, and intended read/write/runtime effect.
2. Classify the operation as read-only, reversible write, external/sibling write, runtime action, or destructive. Stop for confirmation at the boundary required by `AGENTS.md`.
3. Keep MCP tools narrow and typed: document required inputs, structured outputs, errors, authorization, and client-visible compatibility.
4. Reuse existing bridge commands and shared-memory surfaces before adding a parallel control path.
5. Verify the narrowest affected path first: help/schema, daemon, client, adapter, then live injected-client behavior when needed.

## Completion Report

Report the end-to-end owner chain, schema/compatibility impact, risk class, checks actually run, and any live action needing explicit confirmation.
