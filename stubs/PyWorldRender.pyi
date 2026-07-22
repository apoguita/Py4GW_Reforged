# PyWorldRender stub - Reforged Native surface.
# Matches GW/world_render/world_render_bindings.cpp.
#
# Register Python draw callbacks that run INSIDE GW's world render pass (after the
# world block, before the HUD) so 3D overlays are occluded by world geometry.
# Callbacks take no args; draw via PyDXOverlay's 3D methods, which fetch the device
# and set up the (now correct) matrices/depth states.

from typing import Callable

# Register a no-arg draw callback invoked in the world pass. Returns a token
# (>= 0, or -1 on failure) to pass back to unregister_draw().
def register_draw(callback: Callable[[], None]) -> int: ...

# Remove a previously registered draw callback.
def unregister_draw(token: int) -> None: ...

# Remove all registered draw callbacks.
def clear() -> None: ...

# True if the world-render hook is installed and enabled.
def is_active() -> bool: ...

# DDI dispatcher / present / callback counts + device pointer.
def get_diagnostics() -> str: ...

# Enable/disable overlay drawing without removing the hook (A/B test).
def set_enabled(enabled: bool) -> None: ...

# DDI opcode to draw at (default 0x1E). Use SCAN best_op from get_diagnostics().
def set_draw_opcode(opcode: int) -> None: ...

# Enable the diagnostic per-opcode depth scan (off by default).
def set_scan_enabled(enabled: bool) -> None: ...

# Ping the idle watchdog. Call every frame while alive; if pings stop (script
# closed) the draw callbacks are cleared so nothing is left drawn.
def heartbeat() -> None: ...
