# Launch Surface User Manual

`LaunchSurface.py` is a project-owned configurable launch surface. It can show
widget toggles, registered project actions, and explicitly authored embedded
components. It does not replace Widget Manager and it does not automatically
move an existing widget window into the surface.

## Starting it

1. Select the root-level `LaunchSurface.py` in the Py4GW launcher.
2. Start the script. The launcher calls its `main()` function once per frame.
3. If the surface is hidden, press `Launch` on its small handle.

There are no user-facing standalone test scripts for the Launch Surface. The
actual validation path is to start `LaunchSurface.py` in Py4GW and exercise
the editor, placement, persistence, widget toggles, shortcuts, and docking
with the live runtime.

## Editing a surface

Press `Edit` on the surface. The editor controls the active page and does not
alter other surface instances.

- `Width in slots` and `Height in slots` define the logical canvas.
- `Cell size` controls the visual size of one slot.
- `Cell gap` controls spacing between slots.
- `Presentation` selects `Floating` or `Docked`.
- `Dock edge` selects top, bottom, left, or right docking.
- `Search items` filters catalog widgets and registered actions.
- `Add` places an item in the first free location that fits its preferred span.
- `Active page` switches between independent pages.
- `Create page`, `Duplicate page`, and `Remove page` manage page layouts.
- `Preset` saves, applies, or deletes named layout snapshots.

Page dimensions and visual metrics are staged while editing. Press `Apply page
layout` to validate and commit them, or `Discard` to abandon the pending
change. If a smaller canvas would clip an existing tile, the editor explains
which tile prevents the resize and leaves the last valid layout unchanged.

Other editor changes are auto-saved after successful model validation. `Save
now` explicitly flushes the surface settings document and reports a persistence
failure if the native settings backend rejects the write.

The editor workspace shows occupied tiles and available empty cells. Select a
tile, click an empty cell to move it, or drag it by logical grid cells. The
selected-tile inspector also permits exact `X`, `Y`, width, height, visibility,
and shortcut changes. Invalid moves, overlaps, or spans outside the page are
rejected with a visible editor message and the last valid geometry is retained.

Project actions are added by editing `LaunchSurface_Providers.py` at the
repository root. Register the function with `registry.register_action(...)`,
restart the Launch Surface script, then add the new action from the editor's
project actions list. The callback should import and call the real feature
inside the callback body, not during provider registration.

Empty cells are not tiles. They produce no button, background, or pointer
target.

The host uses a transparent non-input canvas and separate windows for the
toolbar and occupied tiles, so gaps pass mouse input through to the game.

Selected tiles can be grouped into a cluster. A cluster can be moved as a unit,
collapsed to its first representative tile, or ungrouped. Cluster operations
still obey normal page bounds and collision validation.

## Widget tiles

Widgets are selected from the live Widget Catalog. The surface stores the
widget's full catalog ID, so renaming its display label does not change the
saved identity. Activating a widget tile toggles it through the existing
WidgetHandler. System-widget disable confirmation remains owned by that
handler.

If a widget disappears after discovery reload, its tile remains in the saved
layout as an unresolved entry and can be removed or repaired later.

## Actions and shortcuts

Registered actions are shown beside catalog widgets in the editor. Right-click
an occupied tile or select it in the editor grid to edit it. The shortcut control
captures a key and optional Ctrl, Shift, or Alt modifiers. `Clear` removes the
binding.

Shortcuts are registered with the shared `HOTKEY_MANAGER` using a namespaced
identifier containing the surface and tile IDs. Conflicts are reported in the
editor; the surface does not silently overwrite another system's binding.

## Positioning and persistence

Floating positions are persisted as normalized screen coordinates. Docked
surfaces persist their edge and normalized offset. Press `Lock` after
positioning to prevent accidental movement. Page dimensions, tile geometry,
visibility, custom display data, shortcuts, and component state are stored in
the surface's own Settings document under:

```text
Projects/LaunchSurface/main.ini
```

Each additional `LaunchSurface` instance should receive its own settings
document and surface ID.

Surface controls, editor children, tile windows, component panels, and global
shortcut identifiers are namespaced by the surface ID, so multiple instances
can remain open without sharing mutable layout state or ImGui identities.

The model also supports explicit layout export/import and a navigation stack
for portal items. These operations are intended for project providers and do
not merge layouts between surfaces. Profile projection and native frame-anchor
adapters are optional integrations; they can change context or window position
without changing saved tile coordinates.

## Limitations of the current host

Only explicitly registered components render inside a tile. Existing widget
`main()`, `update()`, `draw()`, or `configure()` functions continue to run in
their normal widget windows and are not treated as embedded components.
