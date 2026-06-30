# Error Handling LLM Manual

## Goal

This manual is for agents touching `include/base/error_handling.h`.

This file is small, but it controls how shared code routes assertions into the project's failure system.

## Current Contract

The header currently defines:

- `GWCA_ASSERT(expr)` as `PY4GW_ASSERT(expr)`

That means older GWCA-style shared code participates in the same panic/assert path as the rest of the project.

## What To Preserve

Always preserve:

- a single assertion routing path
- non-silent assertion failure
- compatibility for headers already using `GWCA_ASSERT`

## Safe Change Shapes

Safe changes are limited:

- documenting why the alias exists
- adjusting routing only if the global panic/assert design changes deliberately

Unsafe changes:

- removing the alias without updating all consumers
- making the macro a no-op
- splitting shared headers across multiple incompatible assertion systems
