---
name: py4gw-ui-imgui
description: Use when a user asks to investigate, design, change, review, or validate a Py4GW PyImGui, widget, overlay, input, popup, window-state, or native UI boundary behavior.
---

# Py4GW UI and ImGui

## Scope

- Own PyImGui lifecycle/state ownership, widget and overlay boundaries, input behavior, and UI-specific runtime verification.
- Do not apply web layout assumptions or create a competing settings/runtime state owner.

## Evidence Order

1. Current UI/widget source, PyImGui binding, and owning settings/runtime path.
2. `docs/ui/README.md`, the relevant UI topic map, and current native UI research when the issue crosses the boundary.
3. Reproducible injected-client observation.
4. Historical UI plans and legacy bindings as supporting evidence only.

## Workflow

1. Identify the rendered surface, per-frame callback, persistent state owner, input/focus/popup behavior, and native dependency.
2. Inspect the established widget, settings, and PyImGui patterns before adding a helper, persistence path, or structural abstraction.
3. Preserve immediate-mode rebuild semantics, ID namespace, stack balance, context-managed structural scopes, and one authoritative persistence owner.
4. Separate visual layout issues from native input/state failures. Use the native UI research path before masking a lower-layer defect in Python.
5. Run the focused static and live-client checks the change needs; source-only review cannot prove focus, input capture, or injected rendering behavior.

## Completion Report

Report the UI owner, callback/lifecycle, state and persistence owner, native boundary if any, changed surface, checks run, and remaining live-client proof.
