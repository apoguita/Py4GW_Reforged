# Halloween Skeleton Farmer

Status: Draft upstream integration; the combined widget has been installed locally,
but this upstream revision does not yet provide all of its shared dependencies.

The widget presents three independently started jobs in one window:

- Get Mobstoppers: collect batches of three from Mad King's Steward and deposit
  them in storage. Keep storage open. The default target is 402.
- Capture Skeletons: use Dash and a foe shadowstep to approach the Skeleton of
  Dhuum in the Underworld, capture it within 322 units, confirm the inventory
  increase, and collect owned nearby loot. Another player manages instance entry.
- Every Bit Helps: turn captured skeletons in to the steward. The default is
  134 turn-ins.

Only one job can run at a time. Stop the current job before selecting another.
Stopping prevents further scheduling; commands already queued to shared owners
may still finish. All jobs start stopped when the module is loaded.

Capture requires Dash and either Death's Charge or Dark Prison, in any skill
slots. Optional skills are detected from the bar. Capture and defense continue
after the independent ten-second instance-clock resign deadline while the
character remains in the instance. Capture diagnostics persist in
`Logs/HalloweenSkeleton` under the installation root.

## Upstream integration requirements

This draft deliberately preserves the locally installed implementation rather
than changing shared runtime behavior in the widget PR. It is not ready to merge:

- `Routines.Checks.Map.RegisterLocalPlayerUpkeep`, `LocalPlayerReadiness`, and
  `LocalPlayerReady` are required. Their shared upkeep integration must refresh
  local-player caches and dispatch actions without waiting for other party
  members to load. These APIs are absent from the current upstream base.
- `BTMovement.MovePath` must support its optional `resume_key` argument. The
  recorded approach uses that existing local extension; upstream lacks it.

Those dependencies need separate shared-owner integration and review. Removing
the readiness boundary or resumable movement would change the working behavior.
No shared framework changes or local installation scripts are included here.

## Validation scope

The consolidation was checked locally with seven host/isolation tests, 52 capture
regression tests, and the existing turn-in tests. These exercise mocked native
boundaries and do not prove current upstream compatibility. The individual jobs
have prior live use; the combined window still needs injected-client validation
after its upstream dependencies are available. The Halloween event has ended.
