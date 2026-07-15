"""
GameThread section — native ``PyGameThread`` module (safe GW game-thread dispatch).

Shape (mirrors player_demo.py, the canonical template):
  * ``build_gamethread()`` calls the single getter, casts it, and returns display Blocks.
  * ``draw_gamethread_view()`` renders those blocks and exposes the two mutating bindings
    (``clear_calls``, ``enqueue``) as explicit ``ui.action_button`` triggers — fired only on
    click, never on render.

Data path: ``import PyGameThread`` (native embedded module — module-level free functions only).

``enqueue`` takes a ``Callable[[], Any]`` that later runs on the GW game thread; it is a no-op
unless a map is ready. The demo enqueues an explicit, harmless callable (``_demo_task``) that logs
to the Py4GW console when the game thread runs it, so nothing game-moving fires implicitly.

R2 coverage — all 3 methods wired by hand (no reflection):
  Getter (Data tab): is_in_game_thread.
  Actions (Actions tab): clear_calls, enqueue.
  Skipped: none.
"""

import PyImGui
import PyGameThread

from . import casts
from . import diagnostics
from . import ui

_SECTION = "GameThread"

# Counter proving the enqueued callable actually ran on the game thread.
_demo_runs = 0


def _demo_task() -> None:
    """Explicit, side-effect-light callable handed to PyGameThread.enqueue."""
    global _demo_runs
    _demo_runs += 1
    try:
        import PySystem

        PySystem.Console.Log(
            "DEMO2.gamethread",
            f"enqueued task ran on game thread (run #{_demo_runs})",
            PySystem.MessageType.Info,
        )
    except Exception:  # noqa: BLE001 - console optional; never crash the game thread
        pass


class _State:
    pass


state = _State()


# ---------------------------------------------------------------------------
# build_* — call getters, cast, return blocks (shared by render AND dump)
# ---------------------------------------------------------------------------
def build_gamethread():
    rows = [
        ("Is In Game Thread", casts.yesno(casts.safe(PyGameThread.is_in_game_thread))),
        ("Demo Task Runs", _demo_runs),
    ]
    return [ui.kv_block("Game Thread", rows)]


# ---------------------------------------------------------------------------
# Actions — explicit trigger buttons, fired only on click
# ---------------------------------------------------------------------------
def _draw_actions():
    ui.section_header("Dispatch")
    ui.text_muted("enqueue runs _demo_task on the GW game thread (no-op until a map is ready).")
    ui.action_button("enqueue(_demo_task)", PyGameThread.enqueue, _demo_task, key="enqueue")
    PyImGui.same_line(0, 8)
    ui.action_button("clear_calls", PyGameThread.clear_calls, key="clear_calls")


# ---------------------------------------------------------------------------
# draw_*_view — uniform section entry point
# ---------------------------------------------------------------------------
def draw_gamethread_view() -> None:
    blocks = build_gamethread()
    diagnostics.dump_button(_SECTION, blocks)
    PyImGui.separator()
    if PyImGui.begin_tab_bar("GameThreadTabs"):
        if PyImGui.begin_tab_item("Data"):
            ui.draw_blocks(_SECTION, blocks)
            PyImGui.end_tab_item()
        if PyImGui.begin_tab_item("Actions"):
            _draw_actions()
            PyImGui.end_tab_item()
        PyImGui.end_tab_bar()
