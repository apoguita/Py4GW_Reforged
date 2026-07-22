"""System Settings — a persistable, configurable surface for library-wide options.

The always-on ``Widgets/System/System Settings`` widget applies the persisted options to the
native side at boot and renders the (toggled) options window; the System launchpad's undeletable
cog toggles that window via the launch-bar ``"system_settings"`` action. First surface covered:
the native game-event listeners (``Py4GWCoreLib.Listeners``), grouped by category.

Layered like ``map_overlay`` / ``launch_bar``: :mod:`.model` is pure data; :mod:`.persistence`
is the account document; :mod:`.controller` is the process-wide singleton; :mod:`.config_ui`
builds the ``SidebarWindow``.
"""

from .controller import LibrarySettingsController
from .controller import close_window
from .controller import get_controller
from .controller import is_window_open
from .controller import open_window
from .controller import toggle_window

__all__ = [
    "LibrarySettingsController",
    "get_controller",
    "toggle_window",
    "is_window_open",
    "open_window",
    "close_window",
]
