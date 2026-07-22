# PyMouse stub — Reforged Native surface
# Matches the PyMouse module in src/virtual_input/virtual_input_bindings.cpp
# (the same TU also defines the PyKeystroke module).
# Input is posted directly to the Guild Wars window; coordinates are relative
# to the client area. Buttons: Left=0, Right=1, Middle=2.

class PyMouse:
    def __init__(self) -> None: ...
    def MoveMouse(self, x: int, y: int) -> None:
        """Move mouse to (x, y) relative to the client window"""
        ...
    def Click(self, button: int = 0, x: int = 0, y: int = 0) -> None:
        """Click the mouse button at (x, y)"""
        ...
    def DoubleClick(self, button: int = 0, x: int = 0, y: int = 0) -> None:
        """Double click the mouse button at (x, y)"""
        ...
    def Scroll(self, delta: int, x: int = 0, y: int = 0) -> None:
        """Scroll the mouse wheel (positive = up, negative = down)"""
        ...
    def PressButton(self, button: int = 0, x: int = 0, y: int = 0) -> None:
        """Press a mouse button at (x, y)"""
        ...
    def ReleaseButton(self, button: int = 0, x: int = 0, y: int = 0) -> None:
        """Release a mouse button at (x, y)"""
        ...
