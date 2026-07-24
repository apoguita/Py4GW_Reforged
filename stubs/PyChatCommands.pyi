"""Type stub for the embedded PyChatCommands module.

Dynamic, RUNTIME chat-command registry (Reforged Native). Register a Python callable under a
command name; typing ``/<name> args`` in chat invokes it as ``fn(args, raw)`` on the game thread,
and the ``/<name>`` is swallowed so the game never errors on an unknown slash-command. Same principle
as ``PyCallback`` (native stores the callable and calls it) — the trigger is a command name and the
call carries the parsed arguments (C++ tokenises on whitespace; the handler interprets).

Handler signature: ``def handler(args: list[str], raw: str) -> None`` where ``args`` are the
whitespace-split tokens after the command and ``raw`` is the untouched remainder (escape hatch for
quoting / key=value parsing). Names are case-insensitive. Unknown commands pass through to the game
(so ``/age``, ``/stuck``, ``/resign`` … still work). Aliases = register the same handler under more
than one name.
"""

from typing import Callable
from typing import List

def register(name: str, fn: "Callable[[List[str], str], None]") -> None:
    """Register (or replace) the handler for ``/<name>``. Called as ``fn(args, raw)``."""
    ...

def unregister(name: str) -> bool:
    """Remove a command. Returns True if it existed."""
    ...

def clear() -> None:
    """Drop every registered command."""
    ...

def is_registered(name: str) -> bool: ...

def list() -> "List[str]":
    """List the registered command names (lowercased)."""
    ...
