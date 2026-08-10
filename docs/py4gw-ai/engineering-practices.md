# Engineering Practices

Status: current delegated guidance
Scope: code quality, architecture, configuration, security, platform, and project coverage

## Code Quality and Style


- Match local style and conventions; keep changes minimal and focused, avoid unrelated fixes, and fix root causes rather than masking symptoms.
- Prefer existing Py4GW code, abstractions, and approved libraries; adapt them instead of duplicating or replacing functionality in parallel.
- For script work, search the current Py4GW library, bindings, helpers, and
  examples before introducing a new abstraction or restructuring an existing
  area. Prefer composition through the owning surface; restructure only when
  evidence proves the current owner cannot meet the requested behavior.
- Apply the applicable Python or C++ formatter and idioms. Python scripts must follow PEP 8 and use explicit meaningful typing for public APIs, parameters, returns, and important state; treat typing errors as real defects.
- Prefer clear, idiomatic APIs: avoid ambiguous booleans/options, use explicit names or dedicated types, keep public surfaces intentional, and keep implementation details private where practical.
- Handle supported cases explicitly; avoid wildcard handling that hides unhandled states.
- Avoid one-use helpers unless they clarify ownership, testing, or a meaningful abstraction; keep modules focused and appropriately sized.

## Architecture and Module Boundaries


- Keep public APIs small and intentional; keep implementation details private and tests near their owning implementation.
- Reuse existing abstractions, code, and libraries before adding functionality; do not create parallel abstractions or duplicate behavior.
- Preserve ownership and integration points when extending behavior; introduce a new module only when it provides necessary ownership or isolation.
- Keep layers and boundaries explicit, minimize plumbing, and keep orchestration focused on coordination.
- Do not add unrelated behavior to central/core modules; respect Python, native C++, runtime, bridge, UI, and shared-state boundaries.

## Configuration and API Contracts


- Follow the owning subsystem's configuration loading rules and keep configuration/schema definitions synchronized.
- Preserve established naming, wire-format casing, serialization, identifier, timestamp, and optional-field compatibility across Python, native, bridge, and runtime boundaries.
- Mark experimental APIs or runtime interfaces according to project conventions and review compatibility for persisted or transported data before changing them.

## Runtime, Sandbox, and Security


- Execute within the active workspace, host sandbox, and Py4GW runtime boundaries; follow host approval/escalation rules for commands, tools, network, and privileged operations.
- Respect environment-variable and process-spawn constraints, pass only required environment, respect network restrictions, and never modify sandbox-control variables or bypass host controls.
- Analyze and explicitly review security-sensitive changes across injection, native memory, process, shared-state, credentials, network, and runtime boundaries.
- Require appropriate confirmation before security-impacting or externally consequential actions.

## Language and Platform Rules


- Support Python 3 using the repository's supported version; follow the native project's C++ standard, compiler, ABI, naming, and formatting conventions.
- Preserve Python/C++ bridge contracts, conversions, ownership, calling conventions, and ABI compatibility.
- Respect the Windows injected Py4GW/Guild Wars process context; add cross-platform behavior only when explicitly supported and evidenced.

## Py4GW Expansion Slots


- Python script lifecycle/API/packaging: discovery, loading/reload, frame callbacks, shutdown, entry points, canonical imports, ownership, errors, registration, enable/disable, and collisions.
- Native architecture and injection: C++/DLL modules, ownership, initialization/shutdown, hook timing/ownership, thread/context assumptions, unload behavior, and prerequisites.
- Guild Wars runtime and memory: process lifetime, game-state availability/invalidation, runtime-only constraints, pointer validity/lifetime/nullability, safe access, offset sources/versioning/validation, and update failure behavior.
- Packets, events, threading, and synchronization: sources, ownership, dispatch order, thread affinity, shared state, locks/queues, and race/deadlock handling.
- ImGui lifecycle/state/layout: frame begin/end, per-frame rebuilding, persistent state, identity/settings/stack ownership, cleanup, approved PyImGui bindings, IDs, popups, child surfaces, and input ownership.
- Python/C++ bridge: ABI, conversions, lifetime, exceptions, callbacks, ownership transfer, and boundary contracts.
- Diagnostics and failures: approved console logging/levels/correlation, injected-client crash-log and injection-log evidence, error taxonomy, recovery paths, and escalation boundaries.
- Performance: per-frame cost, polling, allocations, blocking work, frame budgets, and degradation behavior.
- Build and runtime verification: supported configurations, artifacts, injection prerequisites, native checks, offline tests, injected-client/live-game checks, fixtures, and verification boundaries.
- Configuration and compatibility: settings, environment assumptions, version compatibility, migration requirements, and deployment/update/rollback behavior.
- Project map and controls: authoritative owners/public entry points/generated artifacts, forbidden changes, review evidence/checklist, version identification, and release requirements.
