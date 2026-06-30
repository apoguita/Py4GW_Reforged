# CrashHandler User Manual

## Purpose

`CrashHandler` is the repository's structured crash capture subsystem.

It exists to:

- install process-level crash interception paths
- preserve panic and runtime context data
- write stack traces and JSON sidecars
- optionally write `.dmp` files
- capture Guild Wars engine crash text when available

The public API is declared in `include/base/CrashHandler.h`.

## Main API

Primary entry points:

- `CrashHandler::Instance().Initialize()`
- `CrashHandler::Instance().Terminate()`
- `CrashHandler::Instance().SetDumpGenerationEnabled(bool)`
- `CrashHandler::Instance().IsDumpGenerationEnabled()`
- `CrashHandler::SetContext(...)`
- `CrashHandler::ClearContext()`
- `CrashHandler::CaptureContext()`
- `CrashHandler::RestoreContext(...)`

Context-scoped helper:

- `CrashContextScope`

## Crash Context

The crash context model stores:

- `phase`
- `module`
- `operation`
- `detail`

Typical usage:

```cpp
CrashContextScope context("startup", "ui", "initialize");
```

That pattern lets crash reports say what the process was doing when it failed.

## Installation Paths

The crash handler installs multiple paths:

- top-level unhandled exception filter
- vectored exception handler
- panic handler integration
- Guild Wars stack append detour when the target can be found

This gives coverage for:

- standard access violations
- panic/assert failures
- some Guild Wars internal crash surfaces

## Output Location

Crash artifacts are written under:

```text
<current working directory>\crashes
```

If the current directory cannot be used, the subsystem falls back to the module directory.

Each crash report now gets its own folder:

```text
crashes\py4gw-YYYYMMDD-HHMMSS-PID-TID\
```

## Report Contents

Each report folder may contain:

- `<name>.json`
- `<name>-stack.txt`
- `<name>-gwtext.txt`
- `<name>.dmp`

The dump file is optional.

## Dump Generation

Dump generation is configurable and currently defaults to disabled.

Use:

```cpp
CrashHandler::Instance().SetDumpGenerationEnabled(true);
```

Current behavior:

- `false` by default
- when disabled, JSON and stack trace still get written
- when enabled, supported crash sources also emit a `.dmp`

## JSON Sidecar

The sidecar JSON includes:

- source label
- crash class
- exception code
- fault address
- thread id
- dump generation flag
- dump file name
- stack trace file name
- panic metadata
- crash context
- inline Guild Wars text

This makes the JSON the fastest first-pass artifact for diagnosis.

## Injection Log Behavior

The crash handler also appends a one-line crash notice to `Py4GW_injection_log.txt`.

If dump generation is disabled, the log points at the report sidecars instead of a dump.

## Recommended Usage

Initialization:

1. initialize the subsystem once during bootstrap
2. set context before major startup phases
3. wrap sensitive phase boundaries in `CrashContextScope`

Shutdown:

1. call `Terminate()` only during orderly shutdown
2. do not assume orderly shutdown runs during process termination

## Practical Guidance

Use `CrashContextScope` around:

- module initialization
- hook enable/disable operations
- patch application and restoration
- shutdown-sensitive teardown

This is what makes crash reports useful instead of generic.
