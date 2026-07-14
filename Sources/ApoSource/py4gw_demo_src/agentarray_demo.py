"""
AgentArray section — the pre-filtered agent arrays by allegiance/type.

Data path: ``AgentArray`` wrapper (`Py4GWCoreLib.AgentArray`). Each getter reads the shared-memory
agent-array wrapper and returns a flat ``list[int]`` of **bare agent ids** (R3 §3 — the array analog
of the Agent trap: an id renders as a number until fed back to ``Agent.*``). This panel:
  * a Counts block — the length of every allegiance/type array, and
  * a Sample table — the first N ids of a selected array resolved to names via ``Agent.GetNameByID``
    (M3 decode), which is the cast that turns a bare id into a readable row.

Coverage — arrays wired (EXPLICIT list, no reflection): GetAgentArray, GetAllyArray,
GetNeutralArray, GetEnemyArray, GetSpiritPetArray, GetMinionArray, GetNPCMinipetArray, GetItemArray,
GetGadgetArray. Name resolution via Agent.GetNameByID.
"""

import PyImGui

from Py4GWCoreLib import Agent
from Py4GWCoreLib.AgentArray import AgentArray

from . import casts
from . import diagnostics
from . import ui

_SECTION = "AgentArray"

# (display name, accessor) — the allegiance/type array surface, listed explicitly.
_ARRAYS = [
    ("All", AgentArray.GetAgentArray),
    ("Ally", AgentArray.GetAllyArray),
    ("Neutral", AgentArray.GetNeutralArray),
    ("Enemy", AgentArray.GetEnemyArray),
    ("SpiritPet", AgentArray.GetSpiritPetArray),
    ("Minion", AgentArray.GetMinionArray),
    ("NPCMinipet", AgentArray.GetNPCMinipetArray),
    ("Item", AgentArray.GetItemArray),
    ("Gadget", AgentArray.GetGadgetArray),
]


class _State:
    selected_index: int = 0
    sample_n: int = 10


state = _State()


def _selected_name() -> str:
    idx = state.selected_index if 0 <= state.selected_index < len(_ARRAYS) else 0
    return _ARRAYS[idx][0]


def _selected_accessor():
    idx = state.selected_index if 0 <= state.selected_index < len(_ARRAYS) else 0
    return _ARRAYS[idx][1]


# ---------------------------------------------------------------------------
# build_* — call getters, cast, return blocks (shared by render AND dump)
# ---------------------------------------------------------------------------
def _counts_block():
    rows = []
    for label, accessor in _ARRAYS:
        arr = casts.safe(accessor, default=[]) or []
        rows.append((label, len(arr)))
    return ui.kv_block("Counts", rows)


def _sample_block():
    name = _selected_name()
    arr = casts.safe(_selected_accessor(), default=[]) or []
    n = max(0, state.sample_n)
    sample = list(arr)[:n]
    rows = []
    for agent_id in sample:
        display = casts.safe(Agent.GetNameByID, agent_id, default="?")
        rows.append((agent_id, display if display else "<unnamed>"))
    title = f"Sample — {name} (first {len(sample)} of {len(arr)})"
    return ui.multi_block(title, ["Agent ID", "Name"], rows)


def build_agent_array():
    return [_counts_block(), _sample_block()]


# ---------------------------------------------------------------------------
# Selector — pick which array to sample + how many rows to resolve
# ---------------------------------------------------------------------------
def _draw_selector() -> None:
    ui.section_header("Sample selector")
    labels = [label for label, _ in _ARRAYS]
    PyImGui.push_item_width(200)
    state.selected_index = PyImGui.combo("Array", state.selected_index, labels)
    PyImGui.pop_item_width()
    if not (0 <= state.selected_index < len(_ARRAYS)):
        state.selected_index = 0
    state.sample_n = PyImGui.input_int("Sample size (N)", state.sample_n)
    if state.sample_n < 0:
        state.sample_n = 0


# ---------------------------------------------------------------------------
# draw_*_view — uniform section entry point
# ---------------------------------------------------------------------------
def draw_agent_array_data() -> None:
    _draw_selector()
    PyImGui.spacing()
    blocks = build_agent_array()
    diagnostics.dump_button(_SECTION, blocks)
    PyImGui.separator()
    ui.draw_blocks(_SECTION, blocks)
