"""Agent Recolor — global, rule-driven overhead name-tag recoloring for agents & gadgets.

A machine-wide, shareable list of color rules (nothing hardcoded) plus a per-account master
toggle. When enabled, the controller registers a profiled callback on ``PyCallback.Phase.Data``
that filters the ``AgentArray`` class by the rules and hands the matched ``(agent_id, argb)`` set
to the native ``PyAgentRecolor`` bulk setter each frame; the native detours apply the colors.

Layered like ``name_obfuscation`` / ``system_settings``: :mod:`.model` is pure data,
:mod:`.store` is persistence, :mod:`.controller` is the singleton + engine, :mod:`.config_ui`
builds the tabbed section shown in System Settings' Agents category. Ground items are handled by
a separate module (they need richer, item-specific handling).
"""

from .controller import AgentRecolorController
from .controller import get_controller

__all__ = [
    "AgentRecolorController",
    "get_controller",
]
