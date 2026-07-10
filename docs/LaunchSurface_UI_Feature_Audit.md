# Launch Surface UI Feature Audit

## Verdict

The Launch Surface is not yet a complete or production-usable editor.

The underlying model has broad coverage—pages, arbitrary tile spans, widget
adapters, actions, components, clusters, shortcuts, presets, portals, and
profiles—but the live UI exposes only a subset of that model. The result is a
feature mismatch: the design promises a configurable launch workspace, while
the current runtime mostly provides a toolbar, a form, and a partially built
grid editor.

This audit is intentionally based on the actual root host in
`LaunchSurface.py`, not on model APIs or documentation claims.

## What pressing `Edit` should do

Pressing `Edit` should enter a clearly distinct layout-authoring mode:

1. A dedicated editor window opens for the active surface instance.
2. The complete page is visible as a logical grid.
3. Occupied tiles are shown at their real coordinates and spans.
4. Empty cells are visibly available as placement targets.
5. Clicking a tile selects it and opens its inspector.
6. Clicking or dragging to an empty cell proposes a placement.
7. Invalid placement shows the reason and preserves the previous layout.
8. The user can add an item at a chosen cell, resize it, change its
   representation, and commit or cancel the edit.
9. The editor shows page, tile, catalog, persistence, and runtime errors in the
   same window.
10. Closing the editor returns to the normal transparent launch surface.

The current implementation now opens a workspace and renders `+` cell
buttons, but it still fails several of the remaining requirements below.

## UI inventory and findings

### 1. Bootstrap and launcher handle — P1

Current behavior:

- The root script creates one hard-coded `main` surface.
- If Widget Manager settings are not initialized, the host waits and prints a
  one-time console message.
- When hidden, the surface provides a small `Launch` handle.

Gaps:

- The wait state is not visible in the UI.
- There is no startup diagnostic window showing whether catalog, WidgetHandler,
  HeroAI, Settings, or the launch registry initialized successfully.
- There is no way to create or select additional surface instances from the
  live UI.
- The `LAUNCHER` presentation enum is not implemented as a distinct host mode;
  it falls through to the normal floating behavior.

Acceptance criteria:

- Show a non-blocking initialization status panel with actionable errors.
- Provide an instance/profile surface selector or explicitly remove the
  multi-instance claim from the user-facing design.
- Define and implement launcher-only, floating, and docked presentation
  behavior separately.

### 2. Normal surface toolbar — P0

Current controls:

- Move handle;
- Edit / Close edit;
- Lock / Unlock;
- Hide;
- close button on the underlying canvas window.

Gaps and defects:

- The lock label was reversed in the earlier host and has now been corrected;
  the remaining requirement is live verification of the locked/unlocked
  interaction.
- `Hide` now attempts an immediate save, but its save failure is not surfaced
  because the editor may close at the same time.
- There is no visible indication that the surface is locked, floating, or
  docked beyond the button text.
- There is no title, surface name, page name, or status indicator in normal
  mode.
- Activation failures appear only as transient tooltips.
- Widget enabled state is not strongly represented on the tile itself; it is
  mostly discoverable through hover text.

Acceptance criteria:

- Correct the lock label and add a persistent lock-state indicator.
- Save hide/show mutations immediately and report save failures.
- Show the active page and runtime state in a compact, optional status area.
- Provide persistent activation error feedback without blocking the game.

### 3. Runtime canvas and input routing — P1

Current behavior:

- The canvas is transparent and marked `NoMouseInputs`.
- Each occupied tile receives its own interactive ImGui window.
- Empty cells and gaps are intended to pass input through.

Gaps:

- The design has no explicit proof that window z-order, child windows, and
  component controls preserve input pass-through in all docking modes.
- Component child windows can capture input inside their rectangle, but there is
  no host-level focus/capture indicator.
- Tile windows are positioned every frame with `Always`; this can interfere
  with normal ImGui movement, focus, and popup behavior.
- There is no collision/z-order visualization in normal mode when tiles overlap
  due to imported or legacy data.

Acceptance criteria:

- Verify input routing in floating and all four docked modes.
- Define focus ownership for tile buttons, embedded components, text fields,
  and shortcut capture.
- Show a diagnostic state when a tile or component fails to draw.

### 4. Editor workspace/grid — P0

Current behavior:

- `Edit` opens a large editor window.
- The workspace renders occupied tiles as span-sized buttons.
- Empty cells render `+` buttons.
- Clicking an empty cell moves the selected tile there.
- Dragging an occupied tile attempts to move it by logical cells.

Gaps and defects:

- The editor grid uses a fixed visual cell size instead of the page's configured
  cell size and gap, so it is a representation of the layout rather than the
  layout itself.
- Horizontal scrolling is enabled, but large-page rendering is still not
  virtualized and vertical bounds are not explicitly managed.
- There are no row/column headers, coordinate labels, cell indices, or visual
  selection outline.
- Empty cells are generic `+` buttons, not an explicit placement preview for
  the selected tile's span. A user cannot see whether a multi-cell tile fits
  before clicking.
- Adding an item from the catalog always chooses the first free position; the
  user cannot add it directly to a selected empty cell.
- There is no drag-from-catalog-to-grid workflow.
- There is no marquee/multi-selection, alignment, duplicate, copy/paste, or
  reset-to-fit operation.
- Dragging saves during movement rather than staging a move and committing it
  once. This can generate many settings writes and makes cancel/undo
  impossible.
- The runtime surface also enters edit mode and draws a second representation
  of the tiles, so the user sees two editing surfaces instead of one clearly
  owned workspace.
- The editor does not provide undo/redo or a reliable cancel-all-edits action.

Acceptance criteria:

- Make the grid scrollable and virtualized for large pages.
- Use one authoritative coordinate transform shared by runtime and editor.
- Display cell coordinates, span occupancy, selection, invalid placement, and
  available placement space.
- Support add-at-cell, drag-to-cell, resize handles or a staged span editor,
  and Apply/Cancel for geometry changes.
- Keep one editor workspace authoritative while editing.

### 5. Page and presentation controls — P1

Current controls:

- Active page selection;
- create, duplicate, and remove page;
- page width and height;
- cell size and gap;
- floating/docked presentation;
- dock edge and dock offset;
- Apply/Discard page layout;
- Save now.

Gaps:

- Page labels cannot be edited after creation.
- Removing a page has no confirmation or preview of what will be lost.
- Applying a preset can replace all pages immediately without confirmation.
- Width/height values can be entered below one and are clamped only during
  apply, leaving a confusing pending draft.
- There is no visual preview of the final floating/docked bounds.
- There is no control for normalized floating position other than dragging the
  runtime surface.
- There is no responsive handling for a page larger than the display.

Acceptance criteria:

- Add explicit Apply/Cancel semantics for page metadata and presentation.
- Add page rename, confirmation, and reset operations.
- Preview the canvas bounds for every presentation mode.
- Clamp and explain invalid dimensions at input time.

### 6. Tile inspector — P0

Current controls:

- X and Y;
- width and height in slots;
- visible checkbox;
- custom label;
- custom icon path;
- representation;
- configure source;
- cluster controls;
- shortcut binding;
- remove tile.

Gaps and defects:

- Tile fields auto-apply as soon as their combined frame values differ. There
  is no Apply/Cancel transaction for a tile.
- Moving a tile to a destination that requires changing both coordinates can be
  rejected after the first field changes, because intermediate geometry is
  validated immediately.
- Width and height have no visible minimum/preferred/maximum span guidance
  from the selected definition.
- The icon path has no picker, preview, fallback explanation, or file error.
- Representation choices are shown even when the selected item does not
  support them. `supported_representations` is not enforced by the host.
- There is no status preview showing how the tile will render in `1x1`, `2x2`,
  or larger spans.
- Configure reports only a generic failure and does not show a successful
  configuration state.
- Removing a tile has no confirmation.

Acceptance criteria:

- Stage all inspector changes and provide Apply, Cancel, and Reset.
- Show definition constraints and reject unsupported representations before
  mutation.
- Preview label, icon, status, compact, expanded, and component rendering.
- Add safe removal confirmation and clear success/failure status.

### 7. Catalog and add-item workflow — P0

Current behavior:

- Catalog widgets and registry actions are displayed in the inspector.
- Widget search filters catalog widgets.
- Registered actions are listed separately.
- Add places an item at the first available position.

Gaps:

- Actions are not filtered by the search field, while widgets are.
- There are no category, tag, capability, provider, enabled-state, or
  availability filters.
- Rows show labels only; icons, descriptions, provider ownership, capabilities,
  preferred span, and current runtime state are hidden.
- There is no distinction between unresolved saved tiles and currently
  addable catalog entries.
- There is no add-at-selection or drag/drop placement.
- There is no refresh/reload result indicator.
- There is no bulk add, favorite, recent, or pinned item workflow.

Acceptance criteria:

- Provide a searchable, filterable catalog for widgets and project items using
  the same query model.
- Show metadata and span constraints before adding.
- Add to the selected cell or provide an explicit placement step.
- Show unavailable/unresolved reasons and catalog revision status.

### 8. Widget toggles — P1

Current behavior:

- Widget tiles route through the existing WidgetHandler adapter.
- Full widget IDs are persisted.
- System-widget disable confirmation remains owned by WidgetHandler.

Gaps:

- The tile does not clearly show enabled, disabled, configuring, unresolved,
  or unavailable state.
- Toggle success/failure is not shown persistently.
- Configure opens the existing configuration path but does not explain which
  window was opened or whether configuration mode was accepted.
- A missing widget remains visually similar to a normal actionable tile.

Acceptance criteria:

- Add explicit state badges/colors and a missing-widget repair/remove state.
- Show runtime transition feedback and handler errors.
- Keep system-widget safety behavior while making it visible to the user.

### 9. HeroAI and project actions — P1

Current behavior:

- HeroAI commands are registered as action definitions.
- Availability is evaluated against map type.
- Invocation passes the active account data to the command.

Gaps:

- Provider registration failures are not visible in the UI.
- HeroAI commands have no dedicated category/filter presentation in the editor.
- Command result, refusal, map restriction, or runtime exception is shown only
  as a transient activation tooltip.
- The implementation exposes command buttons, not embedded HeroAI panels or
  contextual HeroAI controls.
- There is no user-facing explanation when HeroAI is unavailable.

Acceptance criteria:

- Add provider health and action availability diagnostics.
- Show command descriptions, restrictions, and action results.
- Define which HeroAI features are actions, toggles, portals, or embedded
  components instead of presenting everything as a button.

### 10. Embedded components — P0

Current behavior:

- Explicit component factories can create cached component instances.
- Components receive a `LaunchComponentContext`.
- Component state can be persisted.
- Mount/update/draw/unmount hooks are attempted.
- A Runtime Status component is available as a reference item.

Gaps and defects:

- Existing widgets are not embeddable by design, but the UI does not explain
  this limitation when a user selects a widget.
- The host does not implement a real representation policy. It mostly chooses
  component rendering whenever `RENDER` is present and the representation is
  not `compact` or `portal`.
- `supported_representations`, minimum span, and maximum span are not fully
  enforced or displayed by the editor.
- Component hover/focus context is sampled after drawing the component label,
  not from the actual component region.
- Component failures are rendered inside the tile every frame, with no disable,
  retry, or diagnostic state.
- Component dirty state can trigger settings writes during rendering.
- There is no component-specific configuration panel or lifecycle diagnostic.

Acceptance criteria:

- Implement explicit compact/status/expanded/portal rendering policy.
- Enforce and display representation/span contracts.
- Add component error state, retry, disable, and lifecycle diagnostics.
- Define focus and input capture behavior for embedded controls.

### 11. Shortcuts — P1

Current behavior:

- A selected tile can receive a key/modifier binding.
- Bindings are persisted and namespaced by surface/tile ID.
- The shared hotkey manager is synchronized.

Gaps and defects:

- The editor only supports tile shortcuts; there is no shortcut management
  overview or page/action shortcut workflow.
- Conflicts between tiles owned by the same surface are not reliably surfaced
  by `LaunchSurfaceHotkeys.conflicts`, because its external-conflict scan skips
  all identifiers owned by the current surface.
- Registration and synchronization failures are swallowed by the host.
- There is no visible indication that a shortcut is currently active,
  unavailable, or suppressed during text/key capture.

Acceptance criteria:

- Detect same-surface and cross-system conflicts before registration.
- Add a shortcut overview with clear, rebind, conflict, and disabled states.
- Show capture/suppression status and registration errors.

### 12. Clusters — P1

Current behavior:

- A cluster can be created from the selected tile.
- A cluster can collapse, expand, move by one cell, or be removed.

Gaps:

- The editor cannot add or remove arbitrary member tiles from an existing
  cluster.
- There is no visual cluster boundary or group selection in the grid.
- There is no cluster label editing, duplicate, or reset operation.
- Cluster movement errors are reported, but there is no preview of the target
  placement before commit.

Acceptance criteria:

- Add group selection and visible group boundaries.
- Provide membership editing and staged group movement.
- Show collapsed representatives and hidden members clearly.

### 13. Pages, presets, portals, and profiles — P0

Model support exists for these areas, but the live UI is incomplete:

- export/import has no editor button or file workflow;
- profile selection is not exposed;
- the root host does not create a `LaunchSurfaceManager` or navigation
  coordinator;
- portal callbacks are not wired into the default host;
- there is no child-surface/page navigation UI;
- presets have no preview, overwrite confirmation, or rollback transaction;
- multiple surface instances are not manageable from the root UI.

Acceptance criteria:

- Expose only the features that are wired end-to-end, or finish the UI and
  runtime integration before claiming them as supported.
- Add import/export, profile, navigation, and instance management workflows
  with confirmation and rollback.

### 14. Persistence and error feedback — P0

Current behavior:

- Normal mutations generally call `LaunchSurface.save()`.
- Page geometry has staged Apply/Discard controls.
- The settings adapter can call a native `save()` method and expose errors.

Gaps:

- Save failure rollback is not universal across page creation/removal,
  presets, clusters, docking, visibility, and component state.
- There is no dirty-state indicator for tile inspector changes or pending
  operations other than page geometry.
- Malformed settings fall back silently; there is no recovery message or raw
  data backup workflow.
- Auto-saving every drag step and component state change can be expensive.
- Schema version is persisted, but there is no visible migration or recovery
  report.

Acceptance criteria:

- Use a single transaction/dirty model for all editor mutations.
- Add Save, Apply, Cancel, Undo, and recovery semantics consistently.
- Show the last save time/result and preserve failed raw configuration.
- Batch drag/component writes and flush at transaction boundaries.

### 15. Multi-instance and identity safety — P1

Current behavior:

- The model accepts independent surface instances.
- Many ImGui IDs include `surface_id`.

Gaps:

- The root runtime creates only one surface and one settings document.
- There is no instance lifecycle UI.
- Component instance maps, hotkey registration, and navigation are not
  demonstrated with two live hosts.
- Shared registry definitions are correct in principle, but the UI provides no
  ownership/source information when items come from multiple providers.

Acceptance criteria:

- Provide a manager UI or remove the multi-instance promise from the current
  user feature set.
- Demonstrate two simultaneous surfaces with independent pages, settings,
  editors, component state, and shortcuts.

### 16. Visual design and usability — P1

The current UI is functional-looking but not a complete launch-surface editor:

- mostly text buttons with no consistent iconography or state styling;
- no selected-tile highlight beyond a text prefix;
- no legend, help, tooltips for most controls, or first-run guidance;
- fixed-size editor panels with no responsive layout strategy;
- no empty-state onboarding or sample layout;
- no confirmation dialogs for destructive operations;
- no undo/redo, search history, favorites, or reset controls;
- no clear distinction between runtime mode and authoring mode.

Acceptance criteria:

- Establish a consistent visual language for empty, selected, active,
  unavailable, unresolved, error, and dirty states.
- Add help and first-run guidance directly to the editor.
- Make destructive and transactional operations explicit.

## Priority order for implementation

### P0 — Required before calling the editor usable

1. Make the editor grid authoritative, scrollable, coordinate-aware, and
   visually clear.
2. Add staged tile transactions with Apply/Cancel and valid multi-cell
   placement previews.
3. Fix toolbar lock semantics and hide persistence.
4. Make catalog search/add and item placement coherent.
5. Finish persistence/error transaction behavior.
6. Decide whether portals, profiles, import/export, and multi-instance support
   are shipped now or removed from the claimed feature set.
7. Define and implement the embedded component representation contract.

### P1 — Required for a polished first release

1. Add visible runtime/provider/widget/action states.
2. Add shortcut conflict management and cluster membership editing.
3. Add responsive layout, help, confirmations, and basic visual styling.
4. Add live initialization and provider diagnostics.

### P2 — Quality-of-life improvements

1. Undo/redo, copy/paste, multi-select, alignment, favorites, recent items.
2. Layout import/export previews and profile-aware projections.
3. Advanced component lifecycle and performance diagnostics.

## Release gate

The Launch Surface should not be described as feature-complete until a live
Py4GW pass demonstrates every P0 acceptance criterion with:

- an empty page;
- at least one `1x1` tile;
- at least one multi-cell tile;
- an unresolved widget;
- a disabled/unavailable action;
- an embedded component;
- two pages;
- a docked and floating instance;
- a shortcut conflict;
- a failed and successful save;
- a cluster movement and rollback.

The next implementation pass should use this audit as the checklist and update
the status of each item with evidence from the actual injected UI.
