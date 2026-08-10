---
name: py4gw-change-verification
description: Use when a user asks to test, validate, review, build, or complete a Py4GW change and needs focused evidence rather than an assumed repository-wide test command.
---

# Py4GW Change Verification

## Scope

- Own selection and reporting of focused Python, native, bridge, documentation, and live-client verification.
- Do not claim a check passed when it was not run or treat offline checks as proof of injected-client behavior.

## Workflow

1. Identify the changed owners, public contracts, runtime boundary, and the risk that verification must reduce.
2. Inspect the existing local check before adding a new test framework or inventing a global CI command.
3. Run low-cost focused checks first: formatting, syntax/type checks, targeted tests, documentation index/link checks, help/schema, or native build as appropriate to the owner.
4. Expand to integration, daemon/client, injection, or live Guild Wars proof only when the change crosses that boundary. Capture inputs, observed result, logs, build/runtime context, and failure details.
5. Review `git diff --check` and classify each result as passed, failed, blocked, not applicable, or unverified.

## Report Contract

Report each command/check, target, result, what it proves, what it does not prove, residual risk, and the next safe verification step. For changed Python, include the project's strict type/formatter/linter checks when available.
