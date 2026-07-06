# PyGameThread stub — Reforged Native surface (2026-07-06)
# Provides safe game-thread dispatch (replaces legacy Py4GW.Game.enqueue).

from typing import Callable, Any

def clear_calls() -> None: ...

def is_in_game_thread() -> bool: ...

def enqueue(fn: Callable[[], Any]) -> None:
    """
    Enqueue a Python callable to run on the GW game thread.
    The callback runs with the GIL acquired. Map-ready guard is applied.
    """
    ...
