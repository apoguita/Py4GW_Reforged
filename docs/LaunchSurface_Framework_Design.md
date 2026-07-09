# Launch Surface Framework Design

Status: Design specification only. No framework implementation is defined by this document.

## 1. Purpose

Py4GW needs a project-owned surface for launching widgets and project features from one configurable UI. The original idea was a toolbar, but the required behavior is broader:

- toggle discovered widgets;
- launch or show existing widget windows;
- expose commands such as HeroAI actions;
- provide configurable keyboard shortcuts;
- host explicitly designed embedded UI components;
- support tiles larger than one button, such as `1x2`, `2x3`, or `4x4`;
- persist layout, selection, display metadata, and component state.

Existing widgets are independent ImGui scripts that generally create and own their own windows. They cannot safely be treated as embedded controls automatically. This design therefore introduces a separate **Launch Surface Framework**.

The framework is a project package. It is not another Widget Manager, does not discover `.widget` folders, and does not replace `WidgetHandler` or `WidgetCatalog`.

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

The implementation should be a new project package, separate from `Widgets/` discovery roots:

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

### 5.2 `LaunchSurfaceRegistry`

The registry is the extension platform for functionality scattered across the project.

It registers stable definitions for:

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

All launchable items share common metadata:

```text
item_id       stable identity
kind          widget_toggle | window | action | component | group
label         default display label
description   tooltip/help text
icon          icon reference
category      grouping/filtering category
tags          search/filter tags
aliases       additional search terms
enabled       availability predicate or static state
visible       visibility predicate or static state
shortcut      optional shortcut definition
```

Display labels and icons from `WidgetCatalog` are defaults. The user may override them in the launch layout without changing widget metadata.

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

The launch surface uses a grid-based layout.

```text
LaunchPage
    page_id
    label
    columns
    rows or auto-growth
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

The layout engine is responsible for:

- occupancy calculation;
- collision detection;
- placement validation;
- resizing;
- snapping;
- auto-packing;
- viewport clamping;
- orientation for top/bottom/left/right docking.

The model should support arbitrary positive spans, while the first UI may limit users to `1x1` through `4x4`.

## 10. Launch surface presentation

The framework should support these modes:

1. **Launcher-only**

   Compact handle or bar that opens the surface.

2. **Expanded floating surface**

   A movable grid window.

3. **Expanded edge-docked surface**

   A grid anchored to the top, bottom, left, or right display edge.

4. **Future attached surface**

   Optional adapters for anchoring to known game frames. This is not part of the first implementation.

The presentation layer should be implemented separately from the model so the model can be tested without `PyImGui`.

## 11. Shortcuts

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

## 12. Persistence design

The launch surface receives a composed `Settings` document. It does not modify the `Settings` implementation.

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

[Tiles]
tiles_json

[Shortcuts]
shortcuts_json

[Component State]
state_json
```

JSON is preferred for ordered pages, tile spans, custom display metadata, and component state. Invalid data must fall back safely without deleting the user’s raw configuration until a deliberate migration or reset occurs.

The implementation should provide a `LaunchSurfaceSettings` composition class that owns serialization, schema versioning, migration, and dirty tracking.

## 13. Provider examples

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

## 14. Error and lifecycle behavior

- Duplicate provider IDs are rejected and logged.
- Duplicate item IDs are rejected unless the provider explicitly replaces its own item.
- Missing widgets remain as unresolved tiles and can be repaired or removed.
- Missing icons use a fallback icon.
- Component exceptions are isolated to the component tile.
- Provider registration failures do not prevent the surface from loading.
- Component state is namespaced by component ID and schema version.
- Reloading widgets invalidates catalog metadata but does not destroy user layout.
- Removing a provider hides its entries while preserving their layout data.

## 15. Documentation requirements

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

## 16. Implementation phases

### Phase 1: Model and registry

- package structure;
- definitions and registry;
- catalog adapter;
- widget runtime adapter protocol;
- layout model and validation;
- settings composition and JSON migration;
- pure validation scripts.

### Phase 2: Basic launch surface host

- launcher-only mode;
- floating grid;
- widget-toggle tiles;
- action tiles;
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
- layout presets;
- account/character profiles;
- attached game-frame adapters.

## 17. Acceptance criteria

The design is ready for implementation when:

- the launch package has no dependency on `.widget` discovery;
- `Settings` is used by composition only;
- widget metadata is obtained through a catalog adapter;
- full widget IDs are used for persistence;
- actions can be registered by unrelated project packages;
- embedded components have a separate explicit contract;
- layout can represent arbitrary tile spans;
- the model and persistence layers can be tested without injected ImGui;
- existing widget windows continue to operate unchanged;
- documentation can explain how a user adds a widget, how a provider registers an action, and how a component is embedded.

## 18. Explicit non-goals

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
