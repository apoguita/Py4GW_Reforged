"""ChatCommands — the Python registry over the embedded ``PyChatCommands`` module.

Same principle as ``PyCallback``: native holds the callable and invokes it. Here the trigger is a
chat command (``/name args``) and the call carries the parsed args. This layer adds the ergonomics
on top of the raw native surface:

  * **aliases** — register the same handler under several names (``tp`` -> ``travel``);
  * **arity-adaptive dispatch** — a handler may take ``()``, ``(args)``, or ``(args, raw)``;
  * **bookkeeping for the monitor** — per-command help, the callee (module:qualname), invocation
    count and last args, surfaced by the System Settings "Chat Commands" view;
  * **built-ins** — ``/help`` lists everything registered.

``PyChatCommands`` is imported lazily so this stays import-safe offline; registrations made while
native is unavailable are tracked here and are simply not live until native exists. Handlers run on
the game thread (native dispatches under the GIL), so a handler may call game actions directly.
"""

import inspect

from typing import Callable
from typing import Dict
from typing import List
from typing import Optional


def _native():
    try:
        import PyChatCommands

        return PyChatCommands
    except Exception:
        return None


def _log(msg: str) -> None:
    try:
        import PySystem

        PySystem.Console.Log("ChatCommands", msg, PySystem.Console.MessageType.Warning)
    except Exception:
        pass


def _callee_of(handler: Callable) -> str:
    mod = getattr(handler, "__module__", "?")
    qual = getattr(handler, "__qualname__", getattr(handler, "__name__", repr(handler)))
    return "%s.%s" % (mod, qual)


def _param_count(handler: Callable) -> int:
    """Positional params the handler accepts (2+ means it wants (args, raw))."""
    try:
        params = inspect.signature(handler).parameters.values()
        n = 0
        for p in params:
            if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD):
                n += 1
            elif p.kind == inspect.Parameter.VAR_POSITIONAL:
                return 2   # *args -> give it everything
        return n
    except Exception:
        return 2   # unknown signature -> pass both, handler can ignore raw


class Command:
    """Registry record for one command (its primary name owns the metadata)."""

    def __init__(self, name: str, handler: Callable, aliases: "List[str]", help: str) -> None:
        self.name = name
        self.handler = handler
        self.aliases = aliases
        self.help = help
        self.callee = _callee_of(handler)
        self.count = 0
        self.last_args: "List[str]" = []
        self.last_raw = ""


class _Registry:
    def __init__(self) -> None:
        self._commands: "Dict[str, Command]" = {}          # primary name -> Command
        self._alias_to_primary: "Dict[str, str]" = {}      # any usable name -> primary
        self._booted = False

    # ── registration ─────────────────────────────────────────────────────────────────────
    def register(self, name: str, handler: Callable, aliases: "Optional[List[str]]" = None,
                 help: str = "") -> "Command":
        name = (name or "").strip().lower()
        if not name:
            return Command("", handler, [], help)
        alias_list = [a.strip().lower() for a in (aliases or []) if a and a.strip()]
        cmd = Command(name, handler, alias_list, help)
        self._commands[name] = cmd
        native = _native()
        dispatch = self._make_dispatch(name)
        for n in [name] + alias_list:
            self._alias_to_primary[n] = name
            if native is not None:
                try:
                    native.register(n, dispatch)
                except Exception as exc:
                    _log("native register '%s' failed: %r" % (n, exc))
        return cmd

    def unregister(self, name: str) -> bool:
        name = (name or "").strip().lower()
        primary = self._alias_to_primary.get(name, name)
        cmd = self._commands.pop(primary, None)
        if cmd is None:
            return False
        native = _native()
        for n in [cmd.name] + cmd.aliases:
            self._alias_to_primary.pop(n, None)
            if native is not None:
                try:
                    native.unregister(n)
                except Exception:
                    pass
        return True

    def _make_dispatch(self, primary: str) -> "Callable[[List[str], str], None]":
        # Native calls this as fn(args, raw). We record, then adapt to the handler's arity.
        def _dispatch(args, raw) -> None:
            cmd = self._commands.get(primary)
            if cmd is None:
                return
            args = list(args)
            cmd.count += 1
            cmd.last_args = args
            cmd.last_raw = raw
            try:
                n = _param_count(cmd.handler)
                if n <= 0:
                    cmd.handler()
                elif n == 1:
                    cmd.handler(args)
                else:
                    cmd.handler(args, raw)
            except Exception as exc:
                _log("command '/%s' handler raised: %r" % (primary, exc))

        return _dispatch

    # ── queries (for the monitor UI) ─────────────────────────────────────────────────────
    def commands(self) -> "List[Command]":
        return sorted(self._commands.values(), key=lambda c: c.name)

    def usable_names(self) -> "List[str]":
        return sorted(self._alias_to_primary.keys())

    def native_available(self) -> bool:
        return _native() is not None

    # ── built-ins ────────────────────────────────────────────────────────────────────────
    def boot(self) -> None:
        """Register framework built-ins once (native is ready by boot time)."""
        if self._booted:
            return
        self._booted = True
        self.register("help", self._help_handler, aliases=["commands"],
                      help="List all registered chat commands.")

    def _help_handler(self, args, raw) -> None:
        try:
            import PyChat
        except Exception:
            return
        cmds = self.commands()
        if not cmds:
            PyChat.write_chat(0, "No chat commands registered.")
            return
        PyChat.write_chat(0, "Registered chat commands:")
        for cmd in cmds:
            names = "/" + cmd.name + ("".join(" /" + a for a in cmd.aliases))
            PyChat.write_chat(0, "%s  %s" % (names, cmd.help or ""))


_registry: Optional[_Registry] = None


def _get() -> "_Registry":
    global _registry
    if _registry is None:
        _registry = _Registry()
    return _registry


class ChatCommands:
    """Static facade over the process-wide chat-command registry."""

    @staticmethod
    def register(name: str, handler: Callable, aliases: "Optional[List[str]]" = None,
                 help: str = "") -> "Command":
        """Register ``/name`` (and any ``aliases``) → ``handler``. Handler may take
        ``()``, ``(args: list[str])``, or ``(args, raw: str)``. Re-registering replaces."""
        return _get().register(name, handler, aliases, help)

    @staticmethod
    def unregister(name: str) -> bool:
        return _get().unregister(name)

    @staticmethod
    def commands() -> "List[Command]":
        return _get().commands()

    @staticmethod
    def usable_names() -> "List[str]":
        return _get().usable_names()

    @staticmethod
    def native_available() -> bool:
        return _get().native_available()

    @staticmethod
    def boot() -> None:
        _get().boot()
