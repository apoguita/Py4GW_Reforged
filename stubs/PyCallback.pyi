# PyCallback stub — Reforged Native surface.
# Exact counterpart of src/callback/callback_bindings.cpp in Py4GW_Reforged_Native
# (PYBIND11_EMBEDDED_MODULE(PyCallback)). Frame callback scheduler with phased
# execution and priorities. Enum values from include/callback/callback.h.

from enum import IntEnum
from typing import Any, Callable, List, Tuple


class Phase(IntEnum):
    PreUpdate = 0
    Data = 1
    Update = 2


class Context(IntEnum):
    Update = 0
    Draw = 1
    Main = 2


# Both enums are registered with .export_values(), so their value names are also
# module-level attributes. NOTE the collision: Phase.Update and Context.Update
# share the name "Update"; Context is registered last, so module-level `Update`
# resolves to Context.Update. Prefer the qualified `Phase.X` / `Context.X` forms.
PreUpdate: Phase
Data: Phase
Update: Context
Draw: Context
Main: Context


class PyCallback:
    # NOTE: the C++ py::arg() labels are mis-ordered relative to the underlying
    # Register(name, phase, fn, priority, context) signature — the 2nd parameter
    # (Phase) is labelled "fn" and the 3rd (the callable) is labelled "phase".
    # Positional order below is the real one; the first three are therefore
    # marked positional-only, since the bound keyword names are misleading.
    @staticmethod
    def Register(
        name: str,
        phase: Phase,
        fn: Callable[[], Any],
        /,
        priority: int = 99,
        context: Context = Context.Draw,
    ) -> int: ...

    @staticmethod
    def RemoveById(id: int) -> bool: ...

    @staticmethod
    def RemoveByName(name: str) -> bool: ...

    @staticmethod
    def PauseById(id: int) -> bool: ...

    @staticmethod
    def ResumeById(id: int) -> bool: ...

    @staticmethod
    def IsPaused(id: int) -> bool: ...

    @staticmethod
    def IsRegistered(id: int) -> bool: ...

    @staticmethod
    def Clear() -> None: ...

    # One tuple per registered task:
    #   (id, name, phase, context, priority, order, paused)
    # `phase`/`context` come back as raw ints (the enum's underlying value).
    @staticmethod
    def GetCallbackInfo() -> List[Tuple[int, str, int, int, int, int, bool]]: ...
