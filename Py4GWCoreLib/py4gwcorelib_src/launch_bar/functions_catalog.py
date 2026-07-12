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
