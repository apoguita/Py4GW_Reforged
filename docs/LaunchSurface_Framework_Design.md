# Launch Surface Framework Design

Status: Phase 1 model implementation in progress. The root-level model and validation harness exist; the ImGui host and provider integrations remain pending.

## 1. Purpose

Py4GW needs a project-owned surface for launching widgets and project features from one configurable UI. The original idea was a toolbar, but the required behavior is broader:

- toggle discovered widgets;
- launch or show existing widget windows;
- expose commands such as HeroAI actions;
- provide configurable keyboard shortcuts;
- host explicitly designed embedded UI components;
- support tiles larger than one button, such as `1x2`, `2x3`, or `4x4`;
- let the user define the canvas width and height in logical slots;
- let the user position every tile explicitly on that canvas;
- render only occupied tiles, leaving unused slots completely invisible;
- persist layout, selection, display metadata, and component state.

Existing widgets are independent ImGui scripts that generally create and own their own windows. They cannot safely be treated as embedded controls automatically. This design therefore introduces a separate **Launch Surface Framework**.

The framework is a project package. It is not another Widget Manager, does not discover `.widget` folders, and does not replace `WidgetHandler` or `WidgetCatalog`.

The current Phase 1 entry point is the root-level [LaunchSurface.py](../LaunchSurface.py). It is intentionally outside `Widgets/` discovery. The package may later be split into project submodules without changing the public model API.

## 2. Design principles

1. **Composition over inheritance**

   The framework may use the existing `Settings` class by composition. It must not subclass, extend, monkey-patch, or add launch-surface behavior to `Settings`.

2. **Explicit registration**

   Project features register actions and components through a public registry. The framework must not scan arbitrary modules or infer functionality from unrelated files.

3. **Widget compatibility without widget ownership**

   `WidgetCatalog` can provide selection, names, categories, tags, enabled state, and icons. The launch surface consumes that metadata but does not own widget discovery or callback execution.

4. **Opt-in embedding**

   Existing `main`, `draw`, `update`, `configure`, and `minimal` callbacks are not automatically embedded. A component must explicitly implement the embedded rendering contract.

5. **Stable identity**

   Persist full widget IDs and stable action/component IDs. Never use display names as persistent identity.

6. **Separate model and rendering**

   Selection, registration, layout, persistence, and runtime actions must be testable without importing `PyImGui`.

7. **Failure isolation**

   A broken provider or embedded component must be reported and disabled without taking down the launch surface or unrelated widgets.

8. **User-authored geometry**

   The saved layout is an explicit canvas authored by the user. The runtime must not auto-pack, reorder, or render empty cells unless the user requests an editor operation that changes the layout.

9. **Independent instances**

   `LaunchSurface` is an instance-oriented class. Multiple surfaces may exist at the same time, each with independent pages, tile placement, visibility, presentation mode, shortcuts, and settings. Shared definitions come from the registry; user configuration belongs to the individual surface.

## 3. Existing systems and boundaries

### 3.1 Widget runtime

The authoritative widget runtime is `WidgetHandler` in `Py4GWCoreLib/py4gwcorelib_src/WidgetManager.py`.

It owns:

- discovery;
- module loading;
- enable/disable state;
- callback registration and execution;
- configuring state;
- system-widget disable confirmation;
- widget reloads.

The launch surface must communicate with this runtime through a narrow adapter. It must not call private handler internals from framework code.

### 3.2 Widget catalog

`WidgetCatalogSnapshot` in `WidgetManager.py` and the catalog UI in `Widgets/WidgetCatalog/Py4GW_widget_catalog.py` provide useful metadata:

- `widgets_by_id`;
- full widget ID;
- display name;
- icon path;
- category;
- tags;
- aliases;
- enabled state;
- configuration capability.

The launch framework may consume a snapshot or a catalog adapter. It must not perform a second filesystem scan or rebuild the catalog tree for its own purposes.

The catalog is a metadata source, not the launch registry.

### 3.3 Settings

`Py4GWCoreLib.py4gwcorelib_src.Settings.Settings` remains an independent settings document abstraction.

The launch framework may hold a `Settings` instance:

```python
class LaunchSurfaceSettings:
    def __init__(self, document: Settings):
        self.document = document
```

`LaunchSurfaceSettings` composes `Settings` and provides launch-specific serialization. It does not modify `Settings` or add methods to it.

## 4. Package location

The implementation is a project-owned module/package, separate from `Widgets/` discovery roots. The current first-stage location is:

```text
LaunchSurface.py
```

If the model grows beyond one module, it may be extracted into a package while retaining the root-level import as a compatibility facade:

```text
Py4GWCoreLib/
    py4gwcorelib_src/
        launch_surface/
            __init__.py
            models.py
            registry.py
            catalog.py
            layout.py
            settings.py
            runtime.py
            surface.py
            errors.py
```

The directory must not contain a `.widget` marker. It must not be placed under a folder whose `.widget` marker would cause the WidgetHandler to load its files as widgets.

The package must remain importable without an injected ImGui runtime when the model, registry, catalog, layout, and persistence layers are used for validation.

The current validation harness is [tests/launch_surface_model_test.py](../tests/launch_surface_model_test.py). It uses fake catalog, runtime, and settings adapters so Phase 1 can be checked without the injected game process.

Because the Py4GW launcher executes selected scripts through a synthetic
`<string>` module, dataclass-bearing entry points must not depend on postponed
annotation resolution that requires the executing module to exist in
`sys.modules`. The Phase 1 root module and test harness therefore use ordinary
runtime-resolvable annotations.

## 5. Core object model

### 5.1 `LaunchSurface`

`LaunchSurface` is the public OOP facade and coordinator.

Responsibilities:

- own the active launch-surface model;
- accept a catalog snapshot or catalog adapter;
- expose selection and layout operations;
- resolve registered actions and components;
- invoke widget-runtime adapter operations;
- load and save launch-specific settings;
- coordinate the renderer/host when a UI integration is added.

It must not own widget discovery and must not execute arbitrary widget callbacks.

Typical construction:

```python
surface = LaunchSurface(
    surface_id='main',
    registry=launch_registry,
    catalog=catalog_adapter,
    settings=launch_settings,
    widget_runtime=widget_runtime_adapter,
)
```

The same process may construct multiple surfaces:

```python
combat_surface = LaunchSurface(surface_id='combat', ...)
heroai_surface = LaunchSurface(surface_id='heroai', ...)
inventory_surface = LaunchSurface(surface_id='inventory', ...)
```

Each instance may have a different:

- selected item set;
- page collection;
- canvas width and height;
- tile coordinates and spans;
- floating position or dock edge;
- button/component visibility;
- shortcut assignments;
- settings scope or settings document;
- catalog filter or provider category filter.

Instances must not store layout state in module-level globals. A class-level registry may be shared, but the surface model and runtime state must be instance-owned.

### 5.1.1 `LaunchSurfaceManager` (optional coordinator)

If a central coordinator is needed, `LaunchSurfaceManager` should only manage instance lifecycle:

- create a surface by stable `surface_id`;
- retrieve an existing surface;
- destroy or unload a surface;
- enumerate active surfaces;
- coordinate shared registry/provider updates;
- detect shortcut conflicts between surfaces.

It must not merge layouts or make all surfaces share one settings document by default.

### 5.2 `LaunchSurfaceRegistry`

The registry is the extension platform for functionality scattered across the project.

It registers stable definitions and capabilities for:

- actions;
- widget-toggle items;
- existing-window launchers;
- embedded components;
- optional pages or groups.

The registry must support:

- registration by stable ID;
- duplicate-ID detection;
- provider ownership;
- provider unregister/reload;
- enabled/available predicates;
- querying by category and tags;
- safe callback invocation;
- error reporting.

Providers should be explicitly registered by the project bootstrap or feature package:

```python
registry.register_provider('HeroAI', register_heroai_launch_items)
registry.register_provider('Inventory', register_inventory_launch_items)
```

The registry must not import every project module automatically.

### 5.3 `LaunchItemDefinition`

All launchable items share common metadata and optional capabilities:

```text
item_id       stable identity
label         default display label
description   tooltip/help text
icon          icon reference
category      grouping/filtering category
tags          search/filter tags
aliases       additional search terms
enabled       availability predicate or static state
visible       visibility predicate or static state
shortcut      optional shortcut definition

capabilities:
    invoke     can execute an action
    toggle     can read/change a runtime state
    render     can draw an embedded component
    status     can provide a state badge or live summary
    configure  can open/configure the source feature
    portal     can open another page or surface
```

Display labels and icons from `WidgetCatalog` are defaults. The user may override them in the launch layout without changing widget metadata.

An item may expose multiple capabilities. For example, HeroAI may be a toggleable widget, expose command actions, provide a status renderer, and open a larger embedded panel. The tile representation determines which capabilities are visible at a given size.

The model may retain a non-semantic `kind` value for filtering and persistence compatibility, but behavior must be capability-driven rather than controlled by a rigid item-type switch.

### 5.3.1 Tile representations

The same launch item may render differently depending on its tile span or the user’s selected representation:

```text
compact  -> icon or small button
expanded -> embedded panel
status   -> icon plus state indicator
portal   -> page/surface navigation tile
auto     -> provider-selected representation based on available span
```

This allows one registered item to occupy `1x1` as a button and `2x3` as an embedded panel without duplicating its registration or persistence identity.

### 5.4 `WidgetToggleDefinition`

Represents a widget identified by its full `folder_script_name`.

It contains:

- `widget_id`;
- catalog-derived display metadata;
- optional configure operation;
- runtime state adapter;
- system-widget safety behavior.

It must use an explicit `WidgetRuntimePort`, described below, rather than direct private access to `WidgetHandler`.

### 5.5 `LaunchActionDefinition`

Represents an operation supplied by another project package.

Example use cases:

- HeroAI: Flag Heroes;
- HeroAI: Unflag Heroes;
- HeroAI: Open Consumables;
- travel: travel to a selected outpost;
- inventory: deposit or identify items;
- combat: activate a combat preparation mode.

An action definition contains:

- stable ID;
- label and icon;
- callback;
- optional availability predicate;
- optional status provider;
- optional confirmation policy;
- optional shortcut.

The framework does not need to know which subsystem owns the callback.

### 5.6 `EmbeddedComponentDefinition`

Represents a UI component explicitly designed for the launch surface.

It contains:

- stable component ID;
- factory or component instance provider;
- preferred tile span;
- minimum and maximum span;
- draw contract;
- optional lifecycle hooks;
- optional state schema/version;
- optional availability predicate.

It must not reuse the normal widget window callbacks.

## 6. Widget runtime adapter

The framework should define a protocol rather than depend directly on `WidgetHandler`:

```text
WidgetRuntimePort
    get(widget_id)
    is_enabled(widget_id)
    enable(widget_id)
    request_disable(widget_id)
    set_configuring(widget_id, value)
    reload_revision()
```

The adapter used by the current runtime can internally resolve full IDs and bridge to the existing handler. This isolates the launch framework from current handler method names and prevents private handler APIs from becoming part of the new platform.

System-widget confirmation remains owned by the widget runtime. The launch surface requests a disable operation; it does not duplicate confirmation logic.

## 7. Catalog adapter

`LaunchCatalogAdapter` converts a `WidgetCatalogSnapshot` into selectable launch metadata.

It provides:

- `list_widgets()`;
- `search(text)`;
- `filter(category, tag, scope)`;
- `get_widget(widget_id)`;
- `get_display_metadata(widget_id)`;
- `get_catalog_revision()`.

The adapter should use full widget IDs and preserve unresolved IDs when a widget is no longer present.

The launch surface should not store live `Widget` objects in its persisted model. It stores IDs and resolves current metadata from the adapter after reloads.

## 8. Embedded component contract

The first component API should be intentionally narrow.

```text
LaunchComponent
    on_mount(context)
    on_unmount(context)
    update(context)
    draw(context)
```

`LaunchComponentContext` provides:

- item ID and component ID;
- current tile rectangle and available size;
- page and surface identity;
- hover/focus/editing state;
- namespaced state access;
- action invocation;
- request to open an external window;
- request to mark the component dirty;
- logging/error reporting.

The context must not expose the entire `WidgetHandler` or raw settings document by default.

Embedded components may use ImGui controls, but the host owns:

- the top-level window;
- grid layout;
- clipping boundaries;
- tile identity;
- component mount/unmount;
- exception isolation.

The component may request a different span, but the layout engine decides whether the request is valid.

## 9. Layout model

The launch surface uses a user-configurable logical grid. The grid is a layout coordinate system, not a visible table. Empty cells have no visual representation and do not create buttons, borders, background panels, or spacing artifacts.

```text
LaunchPage
    page_id
    label
    columns              # user-defined canvas width in slots
    rows                 # user-defined canvas height in slots
    cell_size
    gap
    tiles[]
```

```text
LaunchTile
    tile_id
    item_id
    x
    y
    column_span
    row_span
    visible
    custom_label
    custom_icon
```

Tile coordinates use zero-based logical slots. A tile at `(x=2, y=1)` with a span of `(column_span=2, row_span=3)` occupies columns `2..3` and rows `1..3`.

The runtime draws a tile at its calculated rectangle. It does not draw the underlying grid. This produces a surface containing only the user’s floating buttons and floating embedded widgets.

The layout engine is responsible for:

- occupancy calculation;
- collision detection;
- placement validation;
- resizing;
- snapping;
- optional editor-only auto-packing;
- viewport clamping;
- orientation for top/bottom/left/right docking.

The model must support arbitrary positive spans that fit inside the page. The first editor may constrain users to `1x1` through `4x4`, but the serialized model must not hard-code that limitation.

### 9.1 User layout operations

The editor must allow the user to:

- set page width in slots;
- set page height in slots;
- move each tile independently;
- set each tile’s width in slots;
- set each tile’s height in slots;
- drag a tile to a new position;
- resize a tile;
- choose whether overlapping placement is rejected or resolved;
- hide a tile without deleting its layout;
- reset one tile or the complete page;
- optionally invoke auto-pack as an explicit command.

When the page dimensions are reduced, the editor must report or resolve tiles that no longer fit. It must not silently move user tiles during normal loading.

### 9.2 Rendering rules

The renderer must:

- calculate rectangles only for occupied, visible tiles;
- skip empty slots entirely;
- avoid placeholder buttons or invisible click targets for empty slots;
- avoid drawing a background grid unless the user enters layout-edit mode;
- allow adjacent tiles to visually touch or use configured gap spacing;
- clip embedded content to its tile rectangle;
- give every tile and embedded component a stable namespaced ImGui ID.

In normal mode, the result should look like floating buttons and floating embedded panels placed on a transparent canvas. In edit mode, optional grid guides and occupied-cell outlines may be shown.

### 9.3 Responsive tile behavior

Tile geometry is user-authored and must remain stable during normal loading. Providers may declare:

- minimum span;
- preferred span;
- maximum span;
- supported representations;
- a compact fallback.

When the user resizes a tile, the editor may select a compatible representation. The runtime must not silently move or resize other tiles to make a component fit.

If the current span cannot support a component, the renderer should use one of these explicit policies:

1. render the provider’s compact fallback;
2. show an unavailable state with an explanatory tooltip;
3. preserve the tile but allow the user to resize it.

The default policy is to preserve the tile and use the compact fallback when available.

### 9.4 Clusters and portals

A group of related tiles may be represented as a `LaunchCluster`:

- clusters can move as a unit in edit mode;
- clusters may collapse to one representative tile;
- clusters may contain their own local layout;
- clusters may open a child page or a second surface instance.

A `portal` capability navigates to another page or surface without duplicating the underlying item definitions. This allows a compact main surface to open dedicated HeroAI, Combat, or Inventory surfaces.

## 10. Launch surface presentation

The framework should support these modes:

1. **Launcher-only**

   Compact handle or bar that opens the surface.

2. **Expanded floating surface**

   A movable transparent canvas containing only occupied floating tiles.

3. **Expanded edge-docked surface**

   A canvas anchored to the top, bottom, left, or right display edge. The canvas still uses the user-defined logical width and height; empty slots remain invisible.

4. **Future attached surface**

   Optional adapters for anchoring to known game frames. This is not part of the first implementation.

The presentation layer should be implemented separately from the model so the model can be tested without `PyImGui`.

### 10.1 Surface context and projections

A surface may define visibility rules based on runtime context without changing its saved layout:

```text
map state
party loaded
HeroAI available
combat state
bot state
inventory state
active account
```

These rules form a **projection** of the saved layout. A projection can hide or disable items, but it must not reorder or reposition them automatically.

Examples:

- show travel actions in outposts;
- show combat actions during combat;
- show HeroAI actions only when HeroAI is available;
- show bot controls while a bot is running.

The same layout can therefore serve multiple contexts without requiring a separate hard-coded UI for every situation.

### 10.2 Surface stack

Surfaces may open other surfaces or pages through the `portal` capability. A lightweight coordinator can maintain a navigation stack:

```text
Main Surface
    -> HeroAI Surface
    -> Combat Surface
    -> Inventory Surface
```

Navigation must remain instance-based. Opening a child surface must not copy or mutate the parent surface’s layout.

### 10.3 Optional semantic zones

The editor may offer optional zones such as `global actions`, `main content`, and `status`, but zones are advisory. They provide layout suggestions and editor affordances; they must not override explicit user coordinates.

## 11. Input routing

The surface host must own input routing for the transparent canvas. Empty canvas areas must be visually and interactively transparent.

The runtime should track:

- hovered tile;
- focused tile;
- active drag or resize operation;
- edit mode;
- shortcut capture mode;
- component input capture;
- whether input should pass through to the game or other overlays.

Only occupied tile rectangles may consume pointer input. Embedded components receive input through their `LaunchComponentContext`; they must not install global mouse hooks or assume ownership of the entire frame.

Shortcuts must be suppressed while text input or key-binding capture is active. A component may request temporary keyboard focus, but the host decides whether that request is granted.

## 12. Shortcuts

Shortcuts belong to launch items, not only widgets.

They may:

- toggle a widget;
- invoke a registered action;
- open a launch page;
- show/hide the launch surface;
- open an external widget window.

The framework may compose the existing `HOTKEY_MANAGER`, but it must:

- use stable registration IDs;
- unregister removed bindings;
- detect conflicts;
- avoid duplicate registration on reload;
- suppress activation while key-binding capture or text input is active.

## 13. Persistence design

The launch surface receives a composed `Settings` document. It does not modify the `Settings` implementation.

Every persisted surface configuration must be namespaced by `surface_id`. The recommended default is one settings document per surface, for example:

```text
Projects/LaunchSurface/combat.ini
Projects/LaunchSurface/heroai.ini
Projects/LaunchSurface/inventory.ini
```

An implementation may store several surfaces in one document, but then every section and serialized record must include an unambiguous surface namespace. One document per surface is preferred because it prevents accidental layout coupling and makes reset/export operations straightforward.

Recommended sections:

```text
[Launch Surface]
schema_version
visible
presentation_mode
dock_edge
dock_offset
floating_x
floating_y
locked

[Pages]
pages_json
active_page

[Layout Presets]
presets_json

[Tiles]
tiles_json

[Shortcuts]
shortcuts_json

[Component State]
state_json
```

JSON is preferred for ordered pages, tile spans, custom display metadata, and component state. Invalid data must fall back safely without deleting the user’s raw configuration until a deliberate migration or reset occurs.

The implementation should provide a `LaunchSurfaceSettings` composition class that owns serialization, schema versioning, migration, and dirty tracking.

Each serialized page must include its explicit `columns` and `rows` values. Each serialized tile must include its explicit `x`, `y`, `column_span`, and `row_span` values. These values are the source of truth for visual placement.

Settings objects must be created and passed into each surface instance. The framework must not use a singleton settings object for all surfaces.

Layout presets contain page dimensions and tile placements, but not provider implementation code. Presets may be duplicated between surface instances through an explicit import/export operation.

## 14. Provider examples

### HeroAI provider

HeroAI should expose a provider such as:

```python
def register_heroai_launch_items(registry):
    registry.add_action(...)
    registry.add_action(...)
    registry.add_component(...)
```

The provider may wrap existing HeroAI command functions. It must not make the launch framework import or depend on HeroAI internals.

### Existing widget provider

The launch surface can generate generic widget-toggle entries from the catalog. A widget that wants richer integration may explicitly register:

```python
def register_launch_items(registry):
    registry.add_window_launcher(...)
    registry.add_component(...)
```

This is opt-in and does not change the widget’s normal lifecycle.

## 15. Error and lifecycle behavior

- Duplicate provider IDs are rejected and logged.
- Duplicate item IDs are rejected unless the provider explicitly replaces its own item.
- Missing widgets remain as unresolved tiles and can be repaired or removed.
- Missing icons use a fallback icon.
- Component exceptions are isolated to the component tile.
- Provider registration failures do not prevent the surface from loading.
- Component state is namespaced by component ID and schema version.
- Reloading widgets invalidates catalog metadata but does not destroy user layout.
- Removing a provider hides its entries while preserving their layout data.

## 16. Documentation requirements

The framework implementation must include:

- module docstrings for every public module;
- class docstrings describing ownership and lifecycle;
- method docstrings describing inputs, outputs, side effects, and failure behavior;
- a provider-author guide;
- a component-author guide;
- a user manual for configuring pages, tiles, shortcuts, and docking;
- migration notes explaining why existing widget windows are not automatically embedded.

Recommended documentation files:

```text
docs/LaunchSurface_Framework_Design.md
docs/LaunchSurface_User_Manual.md
docs/LaunchSurface_Provider_Guide.md
docs/LaunchSurface_Component_Guide.md
```

## 17. Implementation phases

### Phase 1: Model and registry

- package structure;
- definitions and registry;
- capability-based item model;
- catalog adapter;
- widget runtime adapter protocol;
- layout model and validation;
- settings composition and JSON migration;
- pure validation scripts.

### Phase 2: Basic launch surface host

- launcher-only mode;
- user-sized floating canvas;
- widget-toggle tiles;
- action tiles;
- explicit tile coordinates and spans;
- invisible empty slots;
- edit mode;
- persistence.

### Phase 3: Provider integrations

- HeroAI action provider;
- additional project action providers;
- shortcut integration;
- status and availability indicators.

### Phase 4: Embedded components

- component context;
- mount/unmount lifecycle;
- tile rendering;
- first project-owned embedded components;
- component state persistence.

### Phase 5: Advanced presentation

- edge docking;
- multiple pages;
- multiple simultaneous surface instances;
- per-instance settings and layout export/import;
- layout presets;
- contextual projections;
- surface portals and navigation stack;
- tile clusters;
- account/character profiles;
- attached game-frame adapters.

## 18. Acceptance criteria

The design is ready for implementation when:

- the launch package has no dependency on `.widget` discovery;
- `Settings` is used by composition only;
- widget metadata is obtained through a catalog adapter;
- full widget IDs are used for persistence;
- actions can be registered by unrelated project packages;
- embedded components have a separate explicit contract;
- launch items expose optional capabilities instead of requiring one rigid item type;
- layout can represent arbitrary tile spans;
- users can set page width and height in slots;
- users can position and resize each tile independently;
- empty slots produce no visible UI or interaction targets;
- multiple surfaces can coexist without sharing mutable layout state;
- changing one surface’s settings does not move, hide, or reorder another surface;
- empty canvas areas do not consume pointer input;
- contextual visibility does not mutate saved tile coordinates;
- the model and persistence layers can be tested without injected ImGui;
- existing widget windows continue to operate unchanged;
- documentation can explain how a user adds a widget, how a provider registers an action, and how a component is embedded.

## 19. Explicit non-goals

The first implementation must not:

- modify or extend `Settings`;
- replace `WidgetHandler`;
- replace `WidgetCatalog`;
- automatically embed existing widget `draw()` functions;
- scan all project files for callbacks;
- copy the legacy QuickDock implementation;
- copy the HeroAI hotbar implementation;
- require every widget to implement the new framework;
- make the launch surface responsible for widget discovery.
