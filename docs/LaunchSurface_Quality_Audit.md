# Launch Surface Quality Audit

For the complete feature-by-feature UI review and release gate, see
[LaunchSurface_UI_Feature_Audit.md](LaunchSurface_UI_Feature_Audit.md).

## Audit scope

This audit evaluates the Launch Surface as a user-facing product rather than
as a collection of passing model classes. It covers the root host, model,
settings adapter, WidgetHandler/Catalog boundary, HeroAI integration,
shortcuts, embedded components, and advanced layout features.

The attached runtime log also exposed an unrelated-but-triggered startup
defect: shared-memory account loading resolved `Range` and `Routines` through
the broad `Py4GWCoreLib` facade during its own initialization. That circular
import path produced repeated `ImportError` messages. `AccountStruct` now uses
targeted imports for `Range` and `Checks` instead.

## Executive assessment

The original implementation had broad feature coverage but weak interaction
semantics. Several controls looked functional while silently rejecting changes,
the editor had no visible grid or commit feedback, and persistence writes were
not explicitly flushed. The
refinement pass changes the shared interaction model to:

1. stage layout edits;
2. validate them atomically on an explicit Apply action;
3. report rejection and persistence errors in the editor;
4. flush the composed Settings document when it supports explicit saving;
5. validate the live occupied-tile host inside the injected client.

## Feature audit

| Feature | Previous quality | Finding | Refinement direction |
| --- | --- | --- | --- |
| Launcher handle | Basic | Reopen behavior existed, but no startup diagnostic when Widget Manager settings were not ready. | Keep retry behavior and report a one-time waiting diagnostic. |
| Floating surface | Basic | Canvas movement and tile placement were coupled to one large ImGui window. | Use a non-input canvas plus independent toolbar/tile windows and an explicit Move handle. |
| Docking | Basic | Edges and offsets persisted, but state changes had limited feedback. | Persist through the same explicit save path and reset control positioning when mode changes. |
| Page dimensions | Weak | Invalid shrinking was swallowed; users saw no reason rows/columns did not change. | Stage width/height/cell values and apply atomically with visible rejection text. |
| Edit mode | Weak | Occupied tiles were shown, but there was no actual grid guide, making layout changes hard to understand. | Draw non-interactive slot guides and tile outlines. |
| Tile placement | Basic | Manual coordinates and drag existed, but invalid movement failed silently. | Preserve last valid geometry and surface an editor error/status message. |
| Tile presentation | Basic | Custom label/icon and representation existed, but representation behavior was not clearly surfaced. | Keep explicit compact/expanded/status/portal selection and document the fallback policy. |
| Catalog selection | Basic | Search/add worked, but the editor did not distinguish catalog metadata from project definitions strongly enough. | Keep the adapter boundary and stable full widget IDs; improve filtering and status feedback. |
| Widget toggles | Good boundary, weak feedback | WidgetHandler safety was preserved, but unresolved widgets could appear actionable. | Resolve runtime availability separately from enabled state and render unresolved tiles as unavailable. |
| HeroAI actions | Useful adapter | Commands were exposed, but import-time shared-memory failures polluted the client log. | Keep explicit provider registration and remove the circular facade import. |
| Shortcuts | Basic | Bindings persisted and registered, but malformed settings could break synchronization and conflicts were only editor text. | Sanitize loaded bindings, namespace IDs, suppress capture conflicts, and keep conflict reporting. |
| Embedded components | Framework-level | Lifecycle and state boundaries existed, but there was little visible proof of the contract. | Keep cached lifecycle and ship a small Runtime Status component as a reference implementation. |
| Pages/presets | Broad but rough | Model APIs existed, while editor operations lacked commit feedback. | Add explicit page-apply/save semantics and preserve independent page state. |
| Clusters | Model-only | Grouping was implemented but not visually obvious. | Keep cluster controls in the tile editor and enforce atomic movement. |
| Multi-instance | Model-safe | State and IDs were mostly independent, but generic ImGui IDs could collide. | Namespace top-level, tile, child, editor, and shortcut IDs by `surface_id`. |
| Settings | Weak persistence contract | Values were written to the document but explicit native flush was not requested. | Flush through the existing Settings object by composition and expose save errors. |
| Validation workflow | Missing | Offline synthetic checks could not validate the live injected runtime and only printed PASS output. | Use the root `LaunchSurface.py` entry point in Py4GW for visual and behavioral validation. |

## Persistence contract

Launch Surface settings are auto-saved after normal mutations through
`LaunchSurface.save()`. The editor additionally exposes `Save now` so users can
force a flush and verify the result. Page dimensions and visual metrics are
different: they are staged locally and require `Apply page layout`, because a
requested size may be invalid when existing tiles no longer fit.

A rejected layout does not move, clip, or delete existing tiles. The editor
shows the validation error. A failed native Settings flush also appears in the
editor instead of being silently treated as success.

## Runtime log finding

The repeated log sequence:

```text
ImportError: cannot import name 'Range' from 'Py4GWCoreLib'
```

originated in `GlobalCache/shared_memory_src/AccountStruct.py`, where shared
memory initialization imported facade names while `Py4GWCoreLib` was still
constructing `GlobalCache`. The corrected targeted imports avoid that circular
startup dependency. The launch surface itself must continue to use targeted
imports for new runtime bridges.

## Verification matrix

The following checks are required before calling the feature ready:

- exact Python 3.13 32-bit compilation;
- real Py4GW visual test of page Apply, edit guides, save/reload, widget toggle,
  HeroAI action availability, shortcut capture, and floating/docked placement.

The live Py4GW check must be performed in the injected client because no
offline fake can prove native ImGui input capture, Settings binding, or live
WidgetHandler behavior. The previous synthetic Launch Surface test scripts
were removed because they only printed PASS output and did not provide a useful
user-facing validation workflow.

## Refinement pass completed in this audit

The host/editor refinement following this review now also provides:

- explicit dock-offset editing for all four dock edges;
- persistent text fields for page, preset, and cluster identifiers;
- visible success and rejection messages for page, preset, tile, and cluster
  operations;
- rollback when a settings flush fails after a page, tile, or add operation;
- surface-scoped selector child IDs for multi-instance safety;
- corrected status-color argument ordering for the current `PyImGui` facade.

The remaining readiness boundary is intentional: native in-client behavior
still needs visual verification with the real WidgetHandler, Settings backend,
HeroAI runtime, hotkey capture, and frame positioning. The offline checks prove
the host contracts and model transitions, but they cannot prove those native
integrations.
