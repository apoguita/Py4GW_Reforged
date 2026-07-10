# Launch Surface Component Guide

An embedded component is an explicit, launch-surface-aware renderer. It is not
an existing widget window inserted into another ImGui window. This separation
prevents two scripts from owning the same window lifecycle or input state.

## Component registration

```python
from LaunchSurface import LaunchComponentContext, LaunchSurfaceRegistry


class CounterPanel:
    def on_mount(self, context: LaunchComponentContext) -> None:
        context.state.setdefault('count', 0)

    def draw(self, context: LaunchComponentContext) -> None:
        import PyImGui

        count = int(context.state.get('count', 0))
        PyImGui.text(f'Count: {count}')
        if PyImGui.button(f'Increment##{context.tile_id}'):
            context.state['count'] = count + 1

    def on_unmount(self, context: LaunchComponentContext) -> None:
        pass


def register_components(registry: LaunchSurfaceRegistry) -> None:
    registry.register_component(
        'project:counter',
        'Counter',
        lambda context: CounterPanel(),
        category='Project',
        preferred_span=(2, 2),
        maximum_span=(4, 4),
    )
```

The factory is called once per tile instance and the resulting component is
cached by the host. `on_mount` is called after creation. `draw(context)` is
called once per frame while the tile is visible. `on_unmount(context)` is
called when the tile is removed from the active host. The host also accepts
legacy no-argument lifecycle hooks.

## Component rules

- Use the supplied `LaunchComponentContext` for identity and state.
- Namespace every ImGui ID with `context.tile_id`.
- Keep persistent values in `context.state` or use `context.set`; do not write
  directly to the Widget Manager settings document.
- Treat `context.tile_rect` as the current requested rectangle, not a promise
  that the component may resize the page.
- Keep rendering fast and avoid blocking operations in `draw`.
- Do not install global mouse or keyboard hooks. The host controls input
  ownership and shortcut suppression.
- Raise no exception intentionally from `draw`; if an exception occurs, the
  host isolates it to the component tile and shows an error placeholder.

## Span behavior

`preferred_span`, `minimum_span`, and `maximum_span` describe valid tile sizes.
The user controls the final placement. The layout engine rejects overlaps,
out-of-bounds geometry, and unsupported spans; it never silently moves other
tiles to make a component fit.

Existing widget scripts remain normal widgets unless they explicitly expose a
separate component factory. Their windows and callbacks are not automatically
embedded.
