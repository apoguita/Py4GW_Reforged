# Render User Manual

`GW::render` is the Direct3D render hook surface.

Main API:

- `GetIsInRenderLoop()`
- `GetViewportWidth()`
- `GetViewportHeight()`
- `SetRenderCallback(...)`
- `SetResetCallback(...)`

It also exposes render-context types and transform access needed by rendering integrations.

Use it for render-time overlays, viewport queries, and reset handling.
