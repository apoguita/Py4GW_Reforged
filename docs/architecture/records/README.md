# Architecture Project Records

This directory contains project-level architecture records that track active
issues and coordination designs without pretending they are current runtime
implementations.

- `pending-fixes.md` is the project issue pool. Each item has its own status,
  evidence, blast radius, and scope boundary; do not fix an item opportunistically.
- `whiteboard-architecture-cross-hero-cast-coordination.md` records the
  cross-hero lock design and its current implementation/verification notes.
- `pr-review-working-record.md` is the in-progress ledger for the open
  pull-request snapshot: per-PR base and head commits, verdicts, merge
  placement, checks performed or omitted, and unresolved facts. Status:
  current. It records review evidence; it is not a GitHub approval and never
  authorizes a merge.
- Current source, tests, and runtime evidence outrank either record when they
  conflict with an observed implementation.
