# Gadget interactions

Status: proposed
Scope: shared `BTAgents.MoveAndInteractWithGadget` transaction
Authority: owning library implementation and focused offline tests; no new injected-game validation

## Purpose and owner

Use the existing public owner to approach and interact with a static gadget,
such as a known lever, lock or chest. This proposal strengthens that owner; it
does not introduce a parallel controller or establish upstream approval of a
new canonical standard. Full mission and dungeon consumers are not bundled.

The library owns target resolution, approach, interaction dispatch, optional
combat yielding, account sequencing, timeout, cancellation and cleanup. A
consumer supplies mechanic data and verifies the resulting world state.

## Local account example

The following is a call shape, not a captured route. Supply the real object's
captured position and gadget identity; do not substitute a nearby route endpoint.

```python
from Py4GWCoreLib.routines_src.behaviourtrees_src.agents import BTAgents
from Py4GWCoreLib.native_src.internals.types import Vec2f

interaction = BTAgents.MoveAndInteractWithGadget(
    gadget_id=known_gadget_id,
    pos=Vec2f(*captured_object_xy),
    search_distance=captured_search_radius,
)
```

`gadget_id` is the gadget identity accepted by the owner, not a cached runtime
agent ID. `pos` anchors the search; it is not itself proof that the selected
object is the correct mechanic. Use a bounded search radius appropriate to the
captured occurrence. Repeated objects still require unambiguous mechanic data.

With the default `suspend_hero_ai=True`, the owner snapshots HeroAI options,
including individual skill toggles, before final-approach movement. Failure to
acquire that protection fails without moving or interacting. Completion,
timeout, failure, user interruption, exception and external `reset()` restore
the saved state and stop owned movement. Cleanup preserves an outer
`INTERACTION_SCOPE_ACTIVE` flag instead of clearing another transaction's scope.

Set `pause_on_combat=True` only when the mechanic should yield during combat.
The owner releases its local HeroAI suspension for combat and reacquires it
before approach resumes. The default remains `False`.

## Multiple accounts and cancellation

Set `multi_account=True` to process eligible accounts sequentially after the
local interaction. Existing same-map-instance filtering remains in force.

Shared-memory remote commands have no cancellation API. A command still active
when its transaction resets is therefore retained in module-owned quarantine.
A successor cannot issue a duplicate until the original is observed complete.
Unreadable or mismatched status is treated as unknown, never as completion.
`detached_command_unknown_timeout_ms` bounds a successor's wait for unknown
status; expiry fails the successor but does not forget the outstanding command.
Thus reset does not promise that remote side effects have been cancelled.

## Dispatch is not world-state proof

`SUCCESS` means the requested interaction dispatches and settle stages finished.
It does **not** prove a door opened, a lock was consumed, a chest yielded loot,
or the party crossed a boundary. Keep the appropriate concrete observation in
the caller's successor, or use an existing higher-level mechanic owner that
already provides that proof. NPC dialogue, blessings and ground-item pickup
retain their own owners.

## Evidence and limits

`Examples and tests/tests/native_interaction/test_gadget_interaction.py` executes
the actual gadget owner with game/shared-memory boundaries doubled. It covers
approach ownership, exact option restoration, nested scope preservation,
combat handoff, reset/error cleanup and detached remote-command handling.
This is offline transaction evidence, not proof of live collision, response
timing, activation or account-side execution. No local registry is activated by
this upstream proposal.
