"""
Callback section — native ``PyCallback`` frame-scheduler registry (register / pause / resume /
remove / clear + a live "trigger" proof).

Shape mirrors ``player_demo`` exactly:
  * ``build_callback()`` instantiates the ``PyCallback.PyCallback`` handle explicitly, reads its
    registry via the handle accessor, CASTS every field (phase/context ints -> enum names via
    ``casts.enum_name``, paused -> yes/no) and returns display Blocks. The raw ``GetCallbackInfo``
    return is also shown once through ``casts.handle_rows`` (explicit accessor list, no reflection).
  * ``draw_callback_view()`` exposes register/pause/resume/remove/clear as explicit trigger buttons.
    "Trigger" is demonstrated by registering a demo tick callback that increments a live counter —
    the scheduler fires it every frame, so the count proves the registration is live.

Data path: native ``PyCallback`` module (bound ``PyCallback`` class of ``def_static`` methods, plus
``Phase`` and ``Context`` IntEnums). ``GetCallbackInfo`` row = (id, name, phase, context, priority,
order, paused).

R2 coverage — PyCallback (9/9):
  Data getters wired: GetCallbackInfo, IsPaused, IsRegistered.
  Actions wired: Register, RemoveById, RemoveByName, PauseById, ResumeById, Clear.
  Skipped: none.
"""

import PyImGui
import PyCallback

from . import casts
from . import diagnostics
from . import ui

_SECTION = "Callback"

# PyCallback.PyCallback exposes only @staticmethod members and has NO constructor — instantiating it
# raises "No constructor defined!". Bind the CLASS (no call); static methods resolve off it and there
# is no import-time side effect (widget scripts must be passive on import).
_callback = PyCallback.PyCallback
_PHASES = [PyCallback.Phase.PreUpdate, PyCallback.Phase.Data, PyCallback.Phase.Update]
_CONTEXTS = [PyCallback.Context.Update, PyCallback.Context.Draw, PyCallback.Context.Main]
_PHASE_NAMES = [p.name for p in _PHASES]
_CONTEXT_NAMES = [c.name for c in _CONTEXTS]


class _State:
    reg_name: str = "demo_tick"
    phase_index: int = 2  # Update
    context_index: int = 1  # Draw
    priority: int = 99
    callback_id: int = 0
    remove_name: str = ""
    last_registered_id: int = -1
    tick_count: int = 0


state = _State()


def _demo_tick():
    """A harmless per-frame callback body — its running count proves the scheduler fired it."""
    state.tick_count += 1


def _register_demo() -> int:
    phase = _PHASES[state.phase_index] if 0 <= state.phase_index < len(_PHASES) else PyCallback.Phase.Update
    context = _CONTEXTS[state.context_index] if 0 <= state.context_index < len(_CONTEXTS) else PyCallback.Context.Draw
    new_id = _callback.Register(state.reg_name, _demo_tick, phase, state.priority, context)
    state.last_registered_id = int(new_id)
    state.callback_id = int(new_id)
    return new_id


# ---------------------------------------------------------------------------
# build_* — call getters, cast, return blocks (shared by render AND dump)
# ---------------------------------------------------------------------------
def _registry_block():
    entries = casts.safe(_callback.GetCallbackInfo, default=[]) or []
    headers = ["ID", "Name", "Phase", "Context", "Priority", "Order", "Paused"]
    rows = []
    for entry in entries:
        try:
            cid, name, phase, context, priority, order, paused = entry
        except (TypeError, ValueError):
            rows.append((str(entry), "", "", "", "", "", ""))
            continue
        rows.append(
            (
                cid,
                str(name),
                casts.enum_name(PyCallback.Phase, phase),
                casts.enum_name(PyCallback.Context, context),
                priority,
                order,
                casts.yesno(paused),
            )
        )
    return ui.multi_block(f"Registered Callbacks ({len(rows)})", headers, rows)


def _inspect_block():
    cid = state.callback_id
    rows = [
        ("Query ID", cid),
        ("Is Registered", casts.yesno(casts.safe(_callback.IsRegistered, cid))),
        ("Is Paused", casts.yesno(casts.safe(_callback.IsPaused, cid))),
        ("Last Registered ID", state.last_registered_id),
        ("Demo Tick Count (live)", state.tick_count),
    ]
    return ui.kv_block("Inspect By ID", rows)


def _handle_snapshot_block():
    """Raw accessor snapshot via the explicit handle-accessor mechanism (no reflection)."""
    rows = casts.handle_rows(_callback, [("GetCallbackInfo (raw)", "GetCallbackInfo")])
    return ui.kv_block("Handle Accessor Snapshot", rows)


def build_callback():
    return [_registry_block(), _inspect_block(), _handle_snapshot_block()]


# ---------------------------------------------------------------------------
# Actions — explicit trigger buttons, fired only on click
# ---------------------------------------------------------------------------
def _draw_actions():
    ui.section_header("Register (trigger a live demo callback)")
    state.reg_name = PyImGui.input_text("Name", state.reg_name)
    PyImGui.push_item_width(200)
    state.phase_index = PyImGui.combo("Phase", state.phase_index, _PHASE_NAMES)
    state.context_index = PyImGui.combo("Context", state.context_index, _CONTEXT_NAMES)
    PyImGui.pop_item_width()
    state.priority = PyImGui.input_int("Priority", state.priority)
    ui.action_button("Register Demo Callback", _register_demo, key="cb_register")
    ui.text_muted(f"Demo tick count (live): {state.tick_count}")

    PyImGui.spacing()
    ui.section_header("Control by ID")
    state.callback_id = PyImGui.input_int("Callback ID", state.callback_id)
    ui.action_button("Pause", _callback.PauseById, state.callback_id, key="cb_pause")
    PyImGui.same_line(0, 8)
    ui.action_button("Resume", _callback.ResumeById, state.callback_id, key="cb_resume")
    PyImGui.same_line(0, 8)
    ui.action_button("Remove By ID", _callback.RemoveById, state.callback_id, key="cb_remove_id")

    PyImGui.spacing()
    ui.section_header("Remove by name / clear")
    state.remove_name = PyImGui.input_text("Name To Remove", state.remove_name)
    ui.action_button("Remove By Name", _callback.RemoveByName, state.remove_name, key="cb_remove_name")
    ui.action_button("Clear All", _callback.Clear, key="cb_clear")


# ---------------------------------------------------------------------------
# draw_*_view — uniform section entry point
# ---------------------------------------------------------------------------
def draw_callback_view() -> None:
    blocks = build_callback()
    diagnostics.dump_button(_SECTION, blocks)
    PyImGui.separator()
    if PyImGui.begin_tab_bar("CallbackTabs"):
        if PyImGui.begin_tab_item("Data"):
            ui.draw_blocks(_SECTION, blocks)
            PyImGui.end_tab_item()
        if PyImGui.begin_tab_item("Actions"):
            _draw_actions()
            PyImGui.end_tab_item()
        PyImGui.end_tab_bar()
