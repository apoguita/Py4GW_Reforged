---
name: py4gw-runtime-investigation
description: Use when a user reports an injected Guild Wars client symptom, state mismatch, crash, read-versus-action divergence, or binding behavior that needs runtime evidence before code changes.
---

# Py4GW Runtime Investigation

## Scope

- Own symptom framing, source/runtime evidence separation, log correlation, and the smallest safe next observation.
- Do not change code unless the user requests implementation after the investigation. Do not treat a caller workaround as a native fix.

## Evidence Order

1. Reproducible observed behavior with expected and actual results.
2. Current owning Python source, stubs, and native binding implementation.
3. Injection/crash logs, timestamps, build, game state, and reproduction.
4. Legacy code only as parity evidence.

## Workflow

1. State the symptom, affected API, client state, expected behavior, and exact observed behavior. Identify whether it is a read path, action path, or both.
2. Use `docs/game-client/research/`, the owning topic map, and `docs/py4gw-ai/project-context.md` to identify the current owner.
3. Inspect the current binding and call path before proposing retries, monkey-patches, or caller-side state substitution.
4. For a live-client report, correlate injection/crash logs with reproduction; distinguish source proof from injected-client proof.
5. Classify the result as verified, inferred, proposed, or unresolved and name the lowest responsible layer for a fix.

## Runtime Boundary

Treat injected-client commands, memory interaction, and dialog/action calls as runtime actions. Perform them only within explicit user scope and report their observed result separately from the request to send them.

## Completion Report

Report the affected owner/API, reproduction, evidence, working versus broken paths, likely fault boundary, smallest safe next test, and any unverified live client dependency.
