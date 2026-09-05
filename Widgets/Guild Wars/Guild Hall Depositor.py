"""
Guild Hall Depositor widget.

Detects when a guild hall (or a configured outpost map such as the Great
Temple of Balthazar, map 248, or Embark Beach, map 857) finishes loading,
then runs a one-shot sequence: wait a configurable delay (3-10 s), click
Identify All in the inventory, wait a short gap, then deposit all materials
at the Xunlai chest.

Runs once per load; re-arms whenever the character leaves the target map
(or zones through another one). A manual "Run now" button is available for
testing outside a target map.
"""

from typing import Generator

import PyImGui
import PySystem

from Py4GWCoreLib import GLOBAL_CACHE, ImGui, Map, Routines
from Py4GWCoreLib.py4gwcorelib_src.Console import Console, ConsoleLog
from Py4GWCoreLib.py4gwcorelib_src.Settings import Settings
from Sources.inventory_managment.ui_manipulators.deposit_materials import DepositMaterials
from Sources.inventory_managment.ui_manipulators.identify_all import IdentifyAllItems

MODULE_NAME = "Guild Hall Depositor"
MODULE_ICON = "Assets/Textures/Module_Icons/Compass+.png"
WIDGET_KEY = "Widgets/Guild Wars/Guild Hall Depositor"

INI_PATH = "Widgets/GuildHallDepositor"
INI_FILENAME = "GuildHallDepositor.ini"

_MIN_DELAY_S = 3
_MAX_DELAY_S = 10
_DEFAULT_DELAY_MS = 5000
_MIN_GAP_S = 1
_MAX_GAP_S = 10
_DEFAULT_GAP_MS = 3000
_DEFAULT_EXTRA_MAP_IDS = "248 857"

initialized = False
INI_KEY = ""
_enabled = False
_armed = False
_running = False
_stage = "idle"
_routine: Generator[None, None, None] | None = None


def _cfg() -> Settings:
    return Settings(f"{INI_PATH}/{INI_FILENAME}", "account")


def _set_enabled(value: bool) -> None:
    global _enabled
    _enabled = value
    _cfg().set("Main", "enabled", value)


def _target_map_ids() -> set[int]:
    raw = _cfg().get_str("Target", "map_ids", _DEFAULT_EXTRA_MAP_IDS)
    ids: set[int] = set()
    for part in raw.replace(",", " ").split():
        if part.isdigit():
            ids.add(int(part))
    ids.discard(0)
    return ids


def _in_target_map() -> bool:
    if not Map.IsMapReady():
        return False
    if not Map.IsOutpost():
        return False
    if not bool(GLOBAL_CACHE.Party.IsPartyLoaded()):
        return False
    if Map.IsGuildHall():
        return True
    return Map.GetMapID() in _target_map_ids()


def _start_sequence() -> None:
    global _running, _routine, _stage
    _running = True
    _routine = _sequence()
    _stage = "scheduled"
    ConsoleLog(
        MODULE_NAME,
        "Target map loaded - starting identify/deposit sequence.",
        Console.MessageType.Info,
    )


def _cancel_sequence(reason: str) -> None:
    global _running, _routine, _stage
    if _running:
        ConsoleLog(MODULE_NAME, reason, Console.MessageType.Info)
    _running = False
    _routine = None
    _stage = "idle"


def _sequence() -> Generator[None, None, None]:
    global _stage
    cfg = _cfg()
    delay_ms = cfg.get_int("Sequence", "initial_delay_ms", _DEFAULT_DELAY_MS)
    gap_ms = cfg.get_int("Sequence", "gap_ms", _DEFAULT_GAP_MS)

    _stage = f"identify in {max(delay_ms, 0) / 1000.0:.0f}s"
    yield from Routines.Yield.wait(delay_ms, break_on_map_transition=True)
    if not _in_target_map():
        return

    _stage = "identify all"
    yield from IdentifyAllItems().IdentifyAll()

    _stage = f"deposit in {max(gap_ms, 0) / 1000.0:.0f}s"
    yield from Routines.Yield.wait(gap_ms, break_on_map_transition=True)
    if not _in_target_map():
        return

    _stage = "deposit all"
    yield from DepositMaterials().DepositMaterials()

    ConsoleLog(MODULE_NAME, "Identify + deposit sequence complete.", Console.MessageType.Info)


def main():
    global initialized, INI_KEY, _enabled, _armed, _running, _stage, _routine

    if not Routines.Checks.Map.MapValid():
        _cancel_sequence("Sequence cancelled - map not valid.")
        _armed = False
        return

    if not INI_KEY:
        INI_KEY = _cfg().name
        if not INI_KEY:
            return
        initialized = True
        _enabled = _cfg().get_bool("Main", "enabled", False)

    if not _enabled:
        _cancel_sequence("Sequence cancelled - widget disabled.")
        _armed = False
        return

    in_target = _in_target_map()

    if _running:
        if _routine is None:
            _running = False
            return
        if not in_target:
            _cancel_sequence("Sequence cancelled - left the target map.")
            return
        try:
            next(_routine)
        except StopIteration:
            _routine = None
            _running = False
            _armed = True
            _stage = "done"
        return

    if in_target:
        if not _armed:
            _armed = True
            _start_sequence()
    else:
        _armed = False
        _stage = "idle"


def draw_widget():
    global INI_KEY, _enabled, _running
    cfg = _cfg()

    if ImGui.Begin(INI_KEY, MODULE_NAME, flags=PyImGui.WindowFlags.AlwaysAutoResize):
        new_enabled = PyImGui.checkbox("Enabled##ghd", _enabled)
        if new_enabled != _enabled:
            _set_enabled(new_enabled)
            ConsoleLog(
                MODULE_NAME,
                "Guild Hall Depositor enabled."
                if new_enabled
                else "Guild Hall Depositor disabled.",
                Console.MessageType.Info,
            )

        PyImGui.separator()

        PyImGui.text(f"State: {_stage}")
        PyImGui.text(f"Map: {Map.GetMapID()}")
        PyImGui.text(
            f"Target loaded: {'yes' if _in_target_map() else 'no'}"
        )
        PyImGui.text(f"Routine: {'running' if _running else 'idle'}")

        PyImGui.separator()

        delay_s = cfg.get_int("Sequence", "initial_delay_ms", _DEFAULT_DELAY_MS) // 1000
        delay_s = max(_MIN_DELAY_S, min(_MAX_DELAY_S, delay_s))
        new_delay = PyImGui.slider_int("Delay after load (s)", delay_s, _MIN_DELAY_S, _MAX_DELAY_S)
        if new_delay != delay_s:
            cfg.set("Sequence", "initial_delay_ms", new_delay * 1000)

        gap_s = cfg.get_int("Sequence", "gap_ms", _DEFAULT_GAP_MS) // 1000
        gap_s = max(_MIN_GAP_S, min(_MAX_GAP_S, gap_s))
        new_gap = PyImGui.slider_int("Delay between actions (s)", gap_s, _MIN_GAP_S, _MAX_GAP_S)
        if new_gap != gap_s:
            cfg.set("Sequence", "gap_ms", new_gap * 1000)

        PyImGui.separator()

        map_ids = cfg.get_str("Target", "map_ids", _DEFAULT_EXTRA_MAP_IDS)
        new_ids = PyImGui.input_text("Extra map IDs", map_ids)
        if new_ids != map_ids:
            cfg.set("Target", "map_ids", new_ids)

        PyImGui.separator()

        if PyImGui.button("Run now"):
            _armed = True
            if not _running:
                _start_sequence()
            else:
                ConsoleLog(MODULE_NAME, "Sequence already running.", Console.MessageType.Info)

        PyImGui.separator()

        PyImGui.text_wrapped(
            "On each target map load (any guild hall, plus the extra map IDs "
            "above): waits, clicks Identify All in the inventory, waits again, "
            "then deposits all materials at the Xunlai chest. Runs once per "
            "load; run it manually from any outpost."
        )

    ImGui.End(INI_KEY)


def draw():
    global initialized
    if initialized:
        draw_widget()


if __name__ == "__main__":
    main()