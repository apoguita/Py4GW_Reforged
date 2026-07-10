# Launch Surface Provider Guide

Providers are project-owned registration functions. They add stable actions
or components to a `LaunchSurfaceRegistry`; they do not scan folders, import
the Widget Manager, or own user layout.

## Where to add your functions

For the root launch surface, edit:

```text
LaunchSurface_Providers.py
```

Add your registrations inside `register_launch_surface_items(registry)`.
`LaunchSurface.py` loads this function under the provider ID `Project` during
startup. You do not need to edit the framework host or the Widget Catalog.

After changing this file, stop and restart `LaunchSurface.py` in the Py4GW
launcher so the provider is registered again. Then open `Edit`, find the item
under the project actions list, and press `Add`.

## Registering actions

```python
def register_launch_surface_items(registry) -> None:
    def invoke(invocation) -> None:
        # Call the existing project feature here.
        pass

    registry.register_action(
        'project:open_panel',
        'Open panel',
        invoke,
        description='Opens the project panel.',
        category='Project',
        tags=('Project', 'Panel'),
    )
```

The root extension file intentionally uses an untyped registry argument so it
can be imported safely when the launcher executes `LaunchSurface.py` as a
synthetic script module. The runtime registry is still a
`LaunchSurfaceRegistry`.

Action IDs are persistent API. Keep them namespaced and stable. The display
label may change without breaking saved tiles.

Optional metadata includes `icon`, `aliases`, `availability_callback`,
`status_callback`, `configure_callback`, `portal_callback`, and span limits.
Availability should be cheap and side-effect free. Exceptions are treated as
unavailable by the launch model.

## Provider ownership

Use an explicit provider scope when registering a group:

```python
registry.register_provider('ProjectFeature', register_launch_items)
```

The registry records ownership so a provider can later be removed with
`unregister_provider`. Removing a provider removes its definitions but does
not silently delete user tiles from serialized layouts.

## Widget-backed entries

Normal widgets are supplied by the `LaunchCatalogAdapter` and are registered
as generic toggle definitions when selected. A provider should only register a
custom widget definition when it needs behavior beyond enable/disable,
configuration, or catalog metadata. The provider must not duplicate Widget
Handler lifecycle logic.

## Failure boundaries

Providers should register definitions only. Do not perform long-running work
during registration. Callback failures are isolated by the host/model boundary
where possible, and provider IDs prevent unrelated providers from sharing
mutable state.
