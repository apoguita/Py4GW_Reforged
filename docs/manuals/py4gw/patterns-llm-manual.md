# Patterns LLM Manual

## Goal

This manual is for agents modifying the `Patterns` subsystem or adding new resolvers.

Your target is not "find an address somehow". Your target is:

- express resolution as explicit steps
- end at a final pointer
- preserve meaningful failure logs
- preserve the configured halt/continue behavior
- avoid silent failure

## Ground Truth

Primary files:

- `include/base/patterns.h`
- `src/base/patterns.cpp`
- `offsets/*.json`

Public contract:

- `Patterns::ResolvePointer()` returns a rich `PointerResolutionResult`
- `Patterns::Resolve()` maps that result into a typed output and boolean continuation decision

## Required Mental Model

A resolver is a small pointer program described in JSON.

It:

1. consumes raw scan inputs
2. transforms intermediate values
3. validates assumptions
4. emits `final`

If `final` is missing, the resolver is invalid even if intermediate steps succeeded.

## Existing Operations

Current ops implemented in code:

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

Before adding a new op, verify the needed behavior cannot already be composed from existing ones.

## Failure Policy Rules

Resolvers are policy-bearing objects, not just scan definitions.

They define:

- `log_level`
- `on_fail`

Interpretation:

- `warning` + `continue` means optional surface, log but do not stop the caller
- `error` + `halt` means required surface, log and fail the caller

Do not move this policy into ad hoc code if JSON can represent it.

## What Good Resolver JSON Looks Like

Good resolvers:

- are namespace-qualified or scoped by `namespace`
- use descriptive step names
- use explicit intermediate names
- end with `out: "final"`
- validate section or pointer readability where useful
- keep attempts narrow and intentional

Bad resolvers:

- encode multiple unrelated ideas in one step chain
- rely on implicit assumptions not captured by steps
- omit `final`
- use permissive policy for required pointers
- duplicate old handwritten logic poorly

## Preferred Workflow For New Pointer Surfaces

1. Read the old handwritten resolver in code.
2. Identify the real sequence of transformations.
3. Translate each transformation into the smallest available step op.
4. Add missing raw scan inputs under `patterns`.
5. Add a resolver under `resolvers`.
6. Keep code-side call sites thin:

```cpp
return PY4GW::Patterns::Resolve("module.pointer_name", &g_pointer);
```

7. Preserve prior failure semantics unless there is an explicit reason to change them.

## What To Preserve During Refactors

Always preserve:

- log visibility on failures
- step trace usefulness
- module attribution in logs
- caller-facing halt/continue behavior
- final typed output zeroing on failed resolution

Do not add success logs. This subsystem is intentionally failure-oriented.

## Common Agent Mistakes

Do not:

- reintroduce handwritten address assertions when a resolver already exists
- hide failure by returning `true` without policy support
- collapse multiple attempts into one chain if the semantics differ
- use `continue` simply to make a module initialize
- assume a string scan, near call, or dereference is safe without matching the old intent

## Trace Expectations

Failure traces are part of the product.

When changing behavior, ask:

- will the failing step name still be meaningful?
- will the detail message point to the real reason?
- will the trace still show enough intermediate state?

If not, the refactor is incomplete.

## When Code Changes Are Actually Needed

Code changes in `patterns.cpp` are justified when:

- a new generic step operation is needed
- JSON parsing must support a new field
- failure reporting needs more precision
- existing composition cannot express the desired resolution shape

If a change only affects one pointer and existing ops can model it, prefer JSON only.
