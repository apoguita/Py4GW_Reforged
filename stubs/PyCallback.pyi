# PyCallback stub — Reforged Native surface (2026-07-06)
# Frame callback scheduler with phased execution and priorities.

from enum import IntEnum
from typing import Callable, Any

class Phase(IntEnum):
    PreUpdate: int
    Data: int
    Update: int

class Context(IntEnum):
    Update: int
    Draw: int
    Main: int

class PyCallback:
    @staticmethod
    def Register(
        name: str,
        fn: Callable[[], Any],
        phase: Phase,
        priority: int = 99,
        context: Context = Context.Draw,
    ) -> int: ...

    @staticmethod
    def RemoveById(id: int) -> None: ...

    @staticmethod
    def RemoveByName(name: str) -> None: ...

    @staticmethod
    def PauseById(id: int) -> None: ...

    @staticmethod
    def ResumeById(id: int) -> None: ...

    @staticmethod
    def IsPaused(id: int) -> bool: ...

    @staticmethod
    def IsRegistered(id: int) -> bool: ...

    @staticmethod
    def Clear() -> None: ...

    @staticmethod
    def GetCallbackInfo() -> list[tuple]: ...
