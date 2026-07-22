# PyKeystroke stub — Reforged Native surface
# Matches the PyKeystroke module in src/virtual_input/virtual_input_bindings.cpp
# (the same TU also defines the PyMouse module — see PyMouse.pyi).
# PyKeyHandler is the Reforged name for the legacy PyScanCodeKeystroke class.

from typing import List

class PyKeyHandler:
    def __init__(self) -> None: ...
    def PressKey(self, virtualKeyCode: int) -> None:
        """Press a single key using scan code"""
        ...
    def ReleaseKey(self, virtualKeyCode: int) -> None:
        """Release a single key using scan code"""
        ...
    def PushKey(self, virtualKeyCode: int) -> None:
        """Press and release a single key using scan code"""
        ...
    def PressKeyCombo(self, keys: List[int]) -> None:
        """Press a combination of keys using scan codes"""
        ...
    def ReleaseKeyCombo(self, keys: List[int]) -> None:
        """Release a combination of keys using scan codes"""
        ...
    def PushKeyCombo(self, keys: List[int]) -> None:
        """Press and release a combination of keys using scan codes"""
        ...
