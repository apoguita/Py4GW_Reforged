"""Public facade for the standalone Reforged ImGui API.

``ImGui`` is the shared module-level singleton runtime instance.
This module is intentionally separate from ``ImGui_Legacy``.
Legacy callers must import ``ImGui_Legacy`` explicitly.
"""

from .ImGui_src._runtime import ImGuiRuntime

ImGui = ImGuiRuntime()

__all__ = ['ImGui']
