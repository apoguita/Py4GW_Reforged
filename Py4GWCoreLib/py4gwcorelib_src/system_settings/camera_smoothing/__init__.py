"""Callback-driven camera-smoothing feature hosted by System Settings."""

from .controller import CameraSmoothingController
from .controller import get_controller

__all__ = ["CameraSmoothingController", "get_controller"]
