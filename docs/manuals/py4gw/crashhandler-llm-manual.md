# CrashHandler LLM Manual

## Goal

This manual is for agents changing `CrashHandler` behavior.

The subsystem is not just a dump writer. It is a crash reporting pipeline that must:

- survive bad states well enough to emit artifacts
- avoid making shutdown or detach problems worse
- preserve context fidelity
- keep artifacts understandable

## Ground Truth

Primary files:

- `include/base/CrashHandler.h`
- `src/base/CrashHandler.cpp`

Secondary dependencies:

- `base/panic.h`
- `base/logger.h`
- `base/process_manager.h`
- `base/scanner.h`
- `base/hooker.h`

## Core Responsibilities

The subsystem currently handles:

- crash directory discovery
- crash context storage
- SEH and VEH registration
- panic bridging
- Guild Wars path-C attachment
- stack trace writing
- JSON sidecar writing
- optional minidump writing

Keep those responsibilities separated when extending the code.

## Required Safety Model

Crash-path code runs in unstable conditions.

That means:

- avoid heavy abstractions when raw Win32 is enough
- avoid assumptions that heap, hooks, or other subsystems are healthy
- do not require the normal logger to succeed for crash artifacts to exist
- keep artifact writing straightforward and local

## Current Artifact Layout

Each crash now has its own folder under `crashes`.

Inside that folder:

- sidecar JSON is mandatory if file creation succeeds
- stack trace text is mandatory if file creation succeeds
- Guild Wars text file is conditional
- dump file is conditional and controlled by configuration

This folder-per-report layout should be preserved unless there is a strong reason to change it.

## Dump Policy

Dump generation is now explicitly configurable:

- default: disabled
- opt-in through `SetDumpGenerationEnabled(true)`

Do not silently re-enable dumps by default. They are intentionally expensive and large.

## Crash Context Rules

`CrashContextScope` is part of the operational contract.

When changing calling code or adding new subsystems:

- set `phase`, `module`, and `operation` to something meaningful
- use `detail` sparingly for dynamic or high-value context
- restore context correctly after scoped work

Poor context labels make crash artifacts much less useful.

## Source Semantics

Current source labels include:

- `veh`
- `seh`
- `gw_engine`
- `panic`

`ShouldWriteDumpForSource()` defines which sources are dump-eligible. That eligibility is still gated by the runtime dump-enabled flag.

If you add a new source, update:

- source labeling
- dump eligibility
- sidecar expectations

## Common Agent Mistakes

Do not:

- add complex logger-dependent behavior to `DllMain` or detach paths
- assume `Terminate()` always runs
- move crash-path reporting into higher-level subsystems that may already be corrupted
- make dump generation unconditional
- produce file naming schemes that cannot be correlated from the injection log

## Good Change Shapes

Good changes:

- add a new sidecar field with cheap, deterministic data
- improve folder structure
- make dump policy configurable
- tighten source labeling
- preserve minimal artifact generation even when optional pieces fail

Bad changes:

- require multiple subsystems to be healthy before any report is written
- add success-noise logging to the crash path
- perform large allocations or complex container work while handling an exception

## When To Change Code Versus Call Sites

Change `CrashHandler.cpp` when:

- the artifact model changes
- dump policy changes
- new crash metadata must be captured globally
- installation or teardown behavior changes

Change call sites when:

- context labels are missing or weak
- subsystem phases are not scoped correctly
- startup or shutdown order needs better context coverage

## Agent Checklist

Before finalizing a `CrashHandler` change, verify:

1. crash folders still group all artifacts for one event
2. sidecars still write when dumps are disabled
3. default dump generation state is still intentional
4. injection log wording still points to the correct artifact location
5. no new dependency on unsafe detach-time logging was introduced
