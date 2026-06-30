# Patterns User Manual

## Purpose

`PY4GW::Patterns` is the repository's JSON-backed pointer resolution system.

It exists to:

- load raw scanner inputs from `offsets/*.json`
- load higher-level resolvers from the same JSON files
- resolve a final pointer or function address through one or more explicit steps
- emit failure logs with meaningful trace output
- decide whether failure is fatal or permissive based on resolver policy

The public API is declared in `include/base/patterns.h`.

## Main API

Primary entry points:

- `Patterns::Initialize(const std::filesystem::path& directory = {})`
- `Patterns::Get(const std::string& name)`
- `Patterns::ResolvePointer(const std::string& name)`
- `Patterns::Resolve(const std::string& name, T* out)`

Typical usage:

```cpp
uintptr_t address = 0;
if (!PY4GW::Patterns::Resolve("agent.agent_array_addr", &address)) {
    return false;
}
```

For typed outputs:

```cpp
GW::ui::SendUIMessageFn fn = nullptr;
if (!PY4GW::Patterns::Resolve("ui.send_ui_message_func", &fn)) {
    return false;
}
```

## Initialization Behavior

By default, `Patterns::Initialize()` loads all `.json` files from:

```text
<module directory>\offsets
```

Important behavior:

- initialization is one-shot per process
- files are loaded in sorted order
- duplicate pattern names fail initialization
- duplicate resolver names fail initialization
- zero loaded patterns is treated as an error

## JSON Structure

Each JSON file may define:

- `namespace`
- `patterns`
- `resolvers`

Example shape:

```json
{
  "namespace": "agent",
  "patterns": {
    "call_target_anchor": {
      "pattern": "\\xE8\\x00\\x00\\x00\\x00",
      "mask": "x????",
      "offset": 0,
      "section": "text"
    }
  },
  "resolvers": {
    "call_target_func": {
      "module": "agent",
      "log_level": "error",
      "on_fail": "halt",
      "steps": [
        { "name": "scan_anchor", "op": "scan", "pattern": "call_target_anchor", "out": "anchor" },
        { "name": "resolve_func", "op": "function_from_near_call", "in": "anchor", "out": "final" }
      ]
    }
  }
}
```

## Pattern Entries

Pattern entries are raw scanner inputs. They can describe:

- byte-pattern scans
- assertion-based scans
- section and offset metadata

Common fields:

- `pattern`
- `mask`
- `assertion_file`
- `assertion_message`
- `offset`
- `line_number`
- `range`
- `section`

Pattern names are automatically namespace-qualified unless already fully qualified.

## Resolver Entries

Resolvers define how to transform scanner results into a final pointer.

Supported policy fields:

- `module`
- `log_level`
  - `warning`
  - `error`
- `on_fail`
  - `continue`
  - `halt`

Resolver layouts:

- single-attempt resolver using `steps`
- multi-attempt resolver using `attempts`

If multiple attempts exist, they are tried in order until one succeeds.

## Supported Resolver Operations

Current step operations in `src/base/patterns.cpp`:

- `scan`
- `scan_in_range`
- `to_function_start`
- `function_from_near_call`
- `find_use_of_string`
- `dereference`
- `read_u32`
- `add`
- `divide`
- `validate_section`

All resolvers must eventually populate `out: "final"`.

## Failure Semantics

`Patterns::ResolvePointer()` returns a `PointerResolutionResult`.

Important fields:

- `ok`
- `value`
- `name`
- `module`
- `selected_attempt`
- `failed_attempt`
- `failed_step`
- `message`
- `severity`
- `action`
- `trace`

`Patterns::Resolve()` returns:

- `true` if resolution succeeded
- `true` if resolution failed but resolver policy is `continue`
- `false` if resolution failed and resolver policy is `halt`

If resolution fails, the typed output is zero-initialized.

## Logging

The subsystem only logs failures.

Failure logs include:

- resolver name
- failed attempt
- failed step
- reason
- failure policy
- a compact per-step trace

This means successful resolutions do not spam logs, while failures still carry enough detail to debug the path.

## When To Use This System

Use `Patterns::Resolve()` when:

- an address is owned by JSON configuration
- the resolution process should be transparent and traceable
- multiple fallback attempts may be needed
- the failure policy should be data-driven

Do not bypass the system for pointers already modeled in JSON unless there is a clear technical reason.

## Practical Guidance

When adding a new resolver:

1. Add the raw scan inputs under `patterns` if needed.
2. Add a resolver under `resolvers`.
3. Choose `log_level` and `on_fail` deliberately.
4. Make sure one step writes `out: "final"`.
5. Prefer explicit, readable step names.

When debugging:

1. Check the failure log first.
2. Read the trace from left to right.
3. Confirm the failing step matches the expected source pointer chain.
4. Only then adjust JSON or code.
