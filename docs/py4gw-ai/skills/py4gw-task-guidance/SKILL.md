---
name: py4gw-task-guidance
description: Use when a Py4GW request is broad, ambiguous, under-specified, or from a user who needs help turning an idea, bug report, migration, or proposal into a bounded engineering task before implementation.
---

# Py4GW Task Guidance

## Scope

- Own proportionate task framing, assumption checks, and user-facing guidance.
- Do not turn a clear small change into an intake ceremony, require approval for
  routine in-scope work, or create a permanent task dossier by default.
- Route known specialist work to the applicable runtime, native-migration, UI,
  bridge, documentation, or verification skill.

## Workflow

1. Restate the requested outcome in plain language. Separate observed facts,
   desired result, assumptions, and unanswered questions.
2. Inspect enough current source and documentation to identify the likely owner
   and constraints. Use `py4gw-docs-navigation` when the subsystem is unknown.
3. Choose the lightest suitable path:
   - proceed for a clear, low-risk request;
   - state bounded assumptions for a safe interpretation;
   - ask one targeted question only when a missing decision changes scope,
     safety, or the public result;
   - produce a visible plan for multi-step, investigative, or risky work.
4. For a non-trivial task, capture only the working information needed now:
   objective, scope, constraints, evidence, acceptance criteria, risks, and
   the next verification. Keep it in the plan or response unless a durable
   project record is explicitly needed.
5. Explain unfamiliar Py4GW terms and tradeoffs in practical terms. Prefer
   composing existing Py4GWCoreLib, bindings, helpers, and examples before
   proposing a new abstraction or restructuring.

## Output Contract

Report the interpreted objective, owner or next discovery step, material
assumptions, scope boundaries, acceptance evidence, and the next safe action.
State clearly whether work can proceed or needs one specific user decision.
