"""Name Obfuscation — manage & persist the player-name alias identity set (global, multi-account).

A dedicated feature package (layered like ``map_overlay``): :mod:`.model` is pure default data,
:mod:`.store` is the global document, :mod:`.controller` is the process-wide singleton that applies
the alias map to native ``PyNameObfuscator`` and generates fake names, and :mod:`.config_ui` builds
the tabbed 'Name Obfuscation' section hosted by System Settings' Agents group.
"""

from .controller import NameObfuscationController
from .controller import get_controller

__all__ = [
    "NameObfuscationController",
    "get_controller",
]
