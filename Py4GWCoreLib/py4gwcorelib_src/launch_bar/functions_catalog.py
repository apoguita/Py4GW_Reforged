"""Launch Bar function catalog — the curated list of callable "functions".

A *function* is a fire-and-forget call into another library/system that a tile can be bound
to (the third tile kind alongside widgets and system actions). Each entry carries its own
display metadata and a default Font Awesome icon; the user can override the icon per tile.

HOW TO ADD A FUNCTION
---------------------
Append a :class:`LaunchFunction` to :data:`FUNCTIONS` below. Keep ``callback`` a zero-arg
callable that lazy-imports whatever game/library surface it needs *inside* the call, so this
module stays import-safe offline (it is imported by the runtime, never by the pure model):

    def _my_action():
        from Py4GWCoreLib import GLOBAL_CACHE      # import lazily, inside the callback
        GLOBAL_CACHE.Something.do_it()

    FUNCTIONS.append(LaunchFunction(
        id="travel.toa",            # stable unique key (persisted on the tile)
        name="Travel: ToA",         # display name
        icon="ICON_MAP_MARKER_ALT", # default FA constant NAME (see IconsFontAwesome5)
        group="Travel",             # top-level group in the editor's picker (Roles/Scripts/...)
        category="Cities",          # subgroup under that group
        callback=_my_action,
        tooltip="Travel to the Temple of the Ages.",
    ))

``icon`` is the *name* of an ``ICON_*`` constant on ``IconsFontAwesome5`` (resolved to a glyph
at render time), not the glyph itself — human-readable in the settings file and font-stable.
"""

from dataclasses import dataclass
from typing import Callable


@dataclass
class LaunchFunction:
    """One catalog entry: metadata + a zero-arg fire-and-forget callback.

    Organized two levels deep for the editor's picker: a top-level ``group`` (e.g. "Roles",
    "Scripts", "Travel") and a ``category`` subgroup under it (e.g. "Farmer", "InvPlus").
    Empty ``group``/``category`` fall back to "Uncategorized"/"General".
    """

    id: str
    name: str
    icon: str                       # default Font Awesome constant NAME, e.g. "ICON_BOLT"
    category: str                   # subgroup under `group` (e.g. "Farmer")
    callback: Callable[[], None]
    group: str = ""                 # top-level group (e.g. "Roles", "Scripts", "Travel")
    tooltip: str = ""


# --- example / template entry --------------------------------------------------------------
# Replace or extend this list with real calls into your libraries/systems.
def _demo_hello() -> None:
    try:
        import PySystem

        PySystem.Console.Log("LaunchBar", "Hello from a launch-bar function!", PySystem.Console.MessageType.Info)
    except Exception:
        pass


FUNCTIONS: list[LaunchFunction] = [
    LaunchFunction(
        id="demo.hello",
        name="Say Hello",
        icon="ICON_COMMENT",
        group="Examples",
        category="Demo",
        callback=_demo_hello,
        tooltip="Logs a line to the Py4GW console (example function).",
    ),
]


def register_function(fn: LaunchFunction) -> None:
    """Add or replace a catalog function by ``id`` (idempotent).

    Lets external packages contribute functions without editing this file. Safe to call
    repeatedly — a second call with the same ``id`` replaces the entry rather than duplicating
    it (important because :data:`FUNCTIONS` is rebuilt on every launch-bar boot; see
    ``_EXTERNAL_PROVIDERS``).
    """
    for index, existing in enumerate(FUNCTIONS):
        if existing.id == fn.id:
            FUNCTIONS[index] = fn
            return
    FUNCTIONS.append(fn)


# Optional external providers, referenced by dotted ``"module:callable"`` strings so this core
# module never hard-depends on a higher-level package. Each is imported and called once at catalog
# import — and therefore on every launch-bar boot, since the whole launch_bar package is purged and
# reimported on reload (see LaunchBar._boot). A provider that is absent or raises is skipped, so the
# base catalog always comes up.
_EXTERNAL_PROVIDERS: tuple[str, ...] = (
    "HeroAI.command_api:register_launch_functions",
    "Py4GWCoreLib.py4gwcorelib_src.map_overlay.launch_functions:register_launch_functions",
)


_providers_loaded = False


def ensure_external_functions() -> None:
    """Load the external providers once, populating :data:`FUNCTIONS`. Idempotent.

    Called **lazily** — on the first catalog read (see ``FunctionRuntime``), never at import time.
    This matters: a provider typically imports launch-bar submodules (e.g. ``function_runtime`` for
    the icon helpers), and if we ran providers while this module were still being imported, that
    sibling module would only be *partially* initialized, raising ``ImportError``. Deferring to the
    first read guarantees the whole ``launch_bar`` package has finished importing first.

    Resets to unloaded when the package is purged/reimported on reload, so ``FUNCTIONS`` is rebuilt
    with the external functions each boot.
    """
    global _providers_loaded
    if _providers_loaded:
        return
    _providers_loaded = True  # set first, so a re-entrant read during a provider can't recurse

    import importlib

    for path in _EXTERNAL_PROVIDERS:
        try:
            module_name, _, attr = path.partition(":")
            module = importlib.import_module(module_name)
            getattr(module, attr)()
        except Exception as exc:
            # Optional integration not present / not importable offline — never block the catalog,
            # but log it: a silently-swallowed failure here means the provider's functions just never
            # appear, which is very hard to diagnose from the empty menu alone.
            try:
                import PySystem

                PySystem.Console.Log(
                    "LaunchBar",
                    "external provider '%s' failed to load: %s" % (path, exc),
                    PySystem.Console.MessageType.Warning,
                )
            except Exception:
                pass
