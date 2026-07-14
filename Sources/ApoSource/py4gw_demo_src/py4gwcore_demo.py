"""
Py4GW-core section — the reduced ``Py4GW`` root module + the shared-memory surface.

Two distinct surfaces reach the same shared-memory block and BOTH are shown here:

  * Native ``Py4GW.SharedMemory`` submodule — the publisher's *status* only. Per the native
    binding (``Py4GW_Reforged_Native/src/base/python_runtime.cpp`` lines 331-346) it exposes
    exactly four getters: ``is_ready``, ``get_name``, ``get_size``, ``get_sequence``. There is no
    pointer/data getter on the submodule itself.
  * Python-side reader ``SystemShaMemMgr`` (``Py4GWCoreLib/native_src/ShMem/SysShaMem.py``) —
    attaches to that same block by name and decodes its full ctypes payload: the header struct,
    the 16 named context pointers (``Pointers_SHMemStruct``), and the agent-array wrapper. This is
    where the "richer" shared-memory data lives; the native submodule only reports status.

Everything here is read-only inspection — no shared memory is ever written (contract §6), so there
is no Actions tab (contract §5: "Actions (if any)").

Shape (mirrors player_demo.py, the canonical template):
  * ``build_py4gwcore()`` calls each getter/field, casts every value via ``casts`` (pointers via
    ``casts.ptr``), and returns display Blocks.
  * ``draw_py4gwcore_view()`` renders those blocks and the dump button.

R2 coverage — wired by hand (no reflection):
  Native getters: Py4GW.version, SharedMemory.is_ready, SharedMemory.get_name,
    SharedMemory.get_size, SharedMemory.get_sequence.
  Python reader (SystemShaMemMgr): shm_name, shm(attached), size, last_error, _enabled,
    expected_size, header_size, agent_array_size, pointers_size; header_struct
    (version/total_size/sequence/process_id/window_handle); get_pointers_struct() (16 named
    context pointers via casts.ptr); get_agent_array_wrapper() (max/count + 13 category counts).
  Actions: none (read-only inspection only).
  Skipped: none.
"""

import PyImGui
import Py4GW

from . import casts
from . import diagnostics
from . import ui

_SECTION = "Py4GWCore"

# 16 named context pointers published in Pointers_SHMemStruct (SysShaMem/structs/PointersSSM.py).
_POINTER_FIELDS = (
    "MissionMapContext", "WorldMapContext", "GameplayContext", "InstanceInfo",
    "MapContext", "GameContext", "PreGameContext", "WorldContext",
    "CharContext", "AgentContext", "CinematicContext", "GuildContext",
    "AvailableCharacters", "PartyContext", "ServerRegionContext", "Camera",
)

# (label, wrapper-getter name) for the agent-array category ref-lists.
_AGENT_CATEGORY_GETTERS = (
    ("All", "get_all_array"),
    ("Ally", "get_ally_array"),
    ("Neutral", "get_neutral_array"),
    ("Enemy", "get_enemy_array"),
    ("SpiritPet", "get_spirit_pet_array"),
    ("Minion", "get_minion_array"),
    ("NPCMinipet", "get_npc_minipet_array"),
    ("Living", "get_living_array"),
    ("Item", "get_item_array"),
    ("OwnedItem", "get_owned_item_array"),
    ("Gadget", "get_gadget_array"),
    ("DeadAlly", "get_dead_ally_array"),
    ("DeadEnemy", "get_dead_enemy_array"),
)

_reader_err = ""


def _reader():
    """Return the SystemShaMemMgr singleton (Python-side reader), or None on import failure."""
    global _reader_err
    try:
        from Py4GWCoreLib.native_src.ShMem.SysShaMem import SystemShaMemMgr
        return SystemShaMemMgr
    except Exception as e:  # noqa: BLE001 - debug tool must survive a missing reader
        _reader_err = f"{type(e).__name__}: {e}"
        return None


# ---------------------------------------------------------------------------
# build_* — call getters, cast, return blocks (shared by render AND dump)
# ---------------------------------------------------------------------------
def _root_block():
    rows = [
        ("Version", casts.safe(Py4GW.version)),
    ]
    return ui.kv_block("Py4GW Root", rows)


def _native_shm_block():
    """The native Py4GW.SharedMemory submodule — publisher status only (4 getters)."""
    rows = [
        ("is_ready()", casts.yesno(casts.safe(Py4GW.SharedMemory.is_ready))),
        ("get_name()", casts.safe(Py4GW.SharedMemory.get_name)),
        ("get_size() (bytes)", casts.safe(Py4GW.SharedMemory.get_size)),
        ("get_sequence()", casts.safe(Py4GW.SharedMemory.get_sequence)),
    ]
    return ui.kv_block("Native Py4GW.SharedMemory (publisher status)", rows)


def _reader_status_block(mgr):
    """SystemShaMemMgr attach state + layout offsets (public attributes)."""
    attached = casts.safe(getattr, mgr, "shm", default=None) is not None
    rows = [
        ("SHM Name", casts.safe(getattr, mgr, "shm_name", default="<n/a>")),
        ("Attached", casts.yesno(attached)),
        ("Callback Enabled", casts.yesno(casts.safe(getattr, mgr, "_enabled", default=False))),
        ("Mapped Size (bytes)", casts.safe(getattr, mgr, "size", default=0)),
        ("Expected Size (bytes)", casts.safe(getattr, mgr, "expected_size", default=0)),
        ("Header Size (bytes)", casts.safe(getattr, mgr, "header_size", default=0)),
        ("Agent-Array Size (bytes)", casts.safe(getattr, mgr, "agent_array_size", default=0)),
        ("Pointers Size (bytes)", casts.safe(getattr, mgr, "pointers_size", default=0)),
        ("Last Error", casts.safe(getattr, mgr, "last_error", default="") or "(none)"),
    ]
    return ui.kv_block("Shared-Memory Reader (SystemShaMemMgr)", rows)


def _reader_header_block(mgr):
    """Decoded SharedMemoryHeader struct (version/total_size/sequence/process_id/window_handle)."""
    header = casts.safe(getattr, mgr, "header_struct", default=None)
    if header is None:
        return ui.kv_block("SHM Header (SharedMemoryHeader)", [("Header", "None (no snapshot yet)")])
    rows = [
        ("version", casts.safe(getattr, header, "version", default="<n/a>")),
        ("total_size (bytes)", casts.safe(getattr, header, "total_size", default="<n/a>")),
        ("sequence", casts.safe(getattr, header, "sequence", default="<n/a>")),
        ("process_id", casts.safe(getattr, header, "process_id", default="<n/a>")),
        ("window_handle", casts.ptr(casts.safe(getattr, header, "window_handle", default=0))),
    ]
    return ui.kv_block("SHM Header (SharedMemoryHeader)", rows)


def _pointers_block(mgr):
    """The 16 named context pointers from Pointers_SHMemStruct, each rendered via casts.ptr."""
    ptrs = casts.safe(mgr.get_pointers_struct)
    if ptrs is None:
        return ui.kv_block("Context Pointers (Pointers_SHMemStruct)", [("Pointers", "None (no snapshot yet)")])
    rows = []
    for name in _POINTER_FIELDS:
        rows.append((name, casts.ptr(casts.safe(getattr, ptrs, name, default=0))))
    return ui.kv_block("Context Pointers (Pointers_SHMemStruct)", rows)


def _agent_array_block(mgr):
    """Agent-array wrapper snapshot: live-agent count + per-category ref-list lengths."""
    wrapper = casts.safe(mgr.get_agent_array_wrapper)
    if wrapper is None:
        return ui.kv_block("Agent Array (AgentArraySHMemWrapper)", [("Wrapper", "None (no snapshot yet)")])
    rows = [
        ("Live Agents (to_int_list len)", len(casts.safe(wrapper.to_int_list, default=[]) or [])),
    ]
    for label, getter_name in _AGENT_CATEGORY_GETTERS:
        getter = casts.safe(getattr, wrapper, getter_name, default=None)
        count = len(casts.safe(getter, default=[]) or []) if callable(getter) else "<n/a>"
        rows.append((f"{label}Array (len)", count))
    return ui.kv_block("Agent Array (AgentArraySHMemWrapper)", rows)


def build_py4gwcore():
    blocks = [_root_block(), _native_shm_block()]
    mgr = _reader()
    if mgr is None:
        blocks.append(ui.text_block("Shared-Memory Reader", f"Not available: {_reader_err}"))
        return blocks
    blocks.append(_reader_status_block(mgr))
    blocks.append(_reader_header_block(mgr))
    blocks.append(_pointers_block(mgr))
    blocks.append(_agent_array_block(mgr))
    return blocks


# ---------------------------------------------------------------------------
# draw_*_view — uniform section entry point (no Actions: module is read-only)
# ---------------------------------------------------------------------------
def draw_py4gwcore_view() -> None:
    blocks = build_py4gwcore()
    diagnostics.dump_button(_SECTION, blocks)
    PyImGui.separator()
    if PyImGui.begin_tab_bar("Py4GWCoreTabs"):
        if PyImGui.begin_tab_item("Data"):
            ui.draw_blocks(_SECTION, blocks)
            PyImGui.end_tab_item()
        PyImGui.end_tab_bar()
