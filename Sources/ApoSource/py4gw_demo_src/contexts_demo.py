"""
Contexts section — inspect every native game context via the GWContext facade.

Data path: the **Context path** (ctypes structs read from shared memory), reached through the
unified ``GWContext`` facade (`Py4GWCoreLib.Context`). Each context exposes ``GetPtr()`` (raw
struct address), ``IsValid()`` (is the pointer resolved this frame) and ``GetContext()`` (the
cached, ``.contents``-dereferenced ctypes struct). This is the canonical M1 fix for the tool's
core defect: a raw address becomes a named-field struct.

Coverage — the 15 GWContext facade members are listed EXPLICITLY (no ``vars(GWContext)``
reflection to discover them):
  AccAgent, AgentArray, AvailableCharacterArray, Char, Cinematic, Gameplay, Guild, InstanceInfo,
  Map, MissionMap, Party, PreGame, ServerRegion, World, WorldMap.
Plus the two raw-only contexts that are NOT in GWContext, reached through their own facades:
  GameContext (manual ``cast(SSM.GameContext, POINTER(GameContextStruct)).contents``) and
  TextParser (derived from GameContext + 0x18).

AgentArray is SPECIAL-CASED. Its GWContext facade is not wired in Reforged 2.0 —
``AgentArray.enable()`` only registers ``reset_cache`` (which nulls the cache), never the
``_update_ptr``/``_update_cache`` callbacks — so ``GWContext.AgentArray.GetContext()`` is always
``None`` and ``GetPtr()`` always ``0``. Every consumer in ``Py4GWCoreLib/AgentArray.py`` instead
reads the array from SHARED MEMORY via ``SystemShaMemMgr.get_agent_array_wrapper()``. This section
shows THAT source (the proven path) so the entry actually populates, and resolves the live pointer
via the same pattern-scan symbol (``AgentArray_GetPtr``) the facade would use if wired.

For each context: ``GetPtr()`` (via ``casts.ptr``), ``IsValid()`` (bool), then a full field dump
that iterates the KNOWN struct's ``_fields_`` and reads each value — pointer ctypes rendered with
``casts.ptr``, arrays with ``list()``, nested structs shallow-expanded. The struct object itself is
never printed. Iterating a declared struct's ``_fields_`` is reading a known layout, not API
discovery.
"""

import ctypes
from ctypes import POINTER
from ctypes import cast

import PyImGui

from Py4GWCoreLib.Context import GWContext
from Py4GWCoreLib.native_src.context.GameContext import GameContextStruct
from Py4GWCoreLib.native_src.context.TextContext import TextParser

from . import casts
from . import diagnostics
from . import ui

_SECTION = "Contexts"


class _State:
    selected_index: int = 0


state = _State()


# ---------------------------------------------------------------------------
# GameContext / TextParser accessors (raw-only — not part of GWContext)
# ---------------------------------------------------------------------------
def _game_context_ptr() -> int:
    from Py4GWCoreLib.native_src.ShMem.SysShaMem import SystemShaMemMgr

    ssm = SystemShaMemMgr.get_pointers_struct()
    if ssm is None or not ssm.GameContext:
        return 0
    return int(ssm.GameContext)


def _game_context_ctx():
    ptr = _game_context_ptr()
    if not ptr:
        return None
    return cast(ptr, POINTER(GameContextStruct)).contents


# ---------------------------------------------------------------------------
# EXPLICIT context list — (display name, get_ptr callable, get_context callable)
# ---------------------------------------------------------------------------
_CONTEXTS = [
    ("AccAgent", GWContext.AccAgent.GetPtr, GWContext.AccAgent.GetContext),
    ("AgentArray", GWContext.AgentArray.GetPtr, GWContext.AgentArray.GetContext),
    ("AvailableCharacterArray", GWContext.AvailableCharacterArray.GetPtr, GWContext.AvailableCharacterArray.GetContext),
    ("Char", GWContext.Char.GetPtr, GWContext.Char.GetContext),
    ("Cinematic", GWContext.Cinematic.GetPtr, GWContext.Cinematic.GetContext),
    ("Gameplay", GWContext.Gameplay.GetPtr, GWContext.Gameplay.GetContext),
    ("Guild", GWContext.Guild.GetPtr, GWContext.Guild.GetContext),
    ("InstanceInfo", GWContext.InstanceInfo.GetPtr, GWContext.InstanceInfo.GetContext),
    ("Map", GWContext.Map.GetPtr, GWContext.Map.GetContext),
    ("MissionMap", GWContext.MissionMap.GetPtr, GWContext.MissionMap.GetContext),
    ("Party", GWContext.Party.GetPtr, GWContext.Party.GetContext),
    ("PreGame", GWContext.PreGame.GetPtr, GWContext.PreGame.GetContext),
    ("ServerRegion", GWContext.ServerRegion.GetPtr, GWContext.ServerRegion.GetContext),
    ("World", GWContext.World.GetPtr, GWContext.World.GetContext),
    ("WorldMap", GWContext.WorldMap.GetPtr, GWContext.WorldMap.GetContext),
    # raw-only contexts (not in GWContext)
    ("GameContext (raw)", _game_context_ptr, _game_context_ctx),
    ("TextParser (raw)", TextParser.get_ptr, TextParser.get_context),
]


# ---------------------------------------------------------------------------
# ctype classification + field rendering (reads a KNOWN struct — not discovery)
# ---------------------------------------------------------------------------
_PTR_NAME_SUFFIXES = ("_ptr", "_context", "_parser")


def _is_pointer(ctype) -> bool:
    if ctype is ctypes.c_void_p:
        return True
    return isinstance(ctype, type) and issubclass(ctype, ctypes._Pointer)


def _is_array(ctype) -> bool:
    return isinstance(ctype, type) and issubclass(ctype, ctypes.Array)


def _is_struct(ctype) -> bool:
    return isinstance(ctype, type) and issubclass(ctype, ctypes.Structure)


def _ptr_address(value) -> int:
    """Address int behind a c_void_p / POINTER value (0 for null)."""
    if value is None:
        return 0
    try:
        return int(ctypes.cast(value, ctypes.c_void_p).value or 0)
    except (TypeError, ValueError, ctypes.ArgumentError):
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0


def _compact_struct(struct) -> str:
    """One-level field dump of a nested struct (never returns the raw object)."""
    fields = getattr(type(struct), "_fields_", None)
    if not fields:
        return f"<{type(struct).__name__}>"
    parts = []
    for field in fields[:16]:
        fname = field[0]
        fctype = field[1] if len(field) > 1 else None
        try:
            value = getattr(struct, fname)
        except Exception as e:  # noqa: BLE001 - display, don't crash
            parts.append(f"{fname}=<err:{type(e).__name__}>")
            continue
        if _is_pointer(fctype):
            parts.append(f"{fname}={casts.ptr(_ptr_address(value))}")
        elif _is_array(fctype):
            parts.append(f"{fname}=<array[{len(value)}]>")
        elif _is_struct(fctype):
            parts.append(f"{fname}=<{fctype.__name__}>")
        else:
            parts.append(f"{fname}={value}")
    suffix = ", ..." if len(fields) > 16 else ""
    return "(" + ", ".join(parts) + suffix + ")"


def _format_value(value, ctype, fname: str) -> str:
    if _is_pointer(ctype):
        return casts.ptr(_ptr_address(value))
    if _is_array(ctype):
        try:
            return str(list(value))
        except Exception:  # noqa: BLE001
            return "<array>"
    if _is_struct(ctype):
        return _compact_struct(value)
    # scalar — hex-format the u32 pointer-address fields (GameContext hub, *_ptr)
    if isinstance(value, int) and fname.endswith(_PTR_NAME_SUFFIXES):
        return casts.ptr(value)
    return str(value)


# ---------------------------------------------------------------------------
# build_* — one explicit block per context (shared by render AND dump)
# ---------------------------------------------------------------------------
def _context_block(name, get_ptr, get_ctx):
    ptr = casts.safe(get_ptr, default=0) or 0
    ctx = casts.safe(get_ctx, default=None)
    rows = [
        ("GetPtr()", casts.ptr(ptr)),
        ("IsValid()", casts.yesno(ctx is not None)),
    ]
    if ctx is None:
        rows.append(("(struct)", "not available in this state"))
        return ui.kv_block(name, rows)

    fields = getattr(type(ctx), "_fields_", None)
    if not fields:
        rows.append(("(struct)", f"<{type(ctx).__name__}: no _fields_>"))
        return ui.kv_block(name, rows)

    for field in fields:
        fname = field[0]
        fctype = field[1] if len(field) > 1 else None
        try:
            value = getattr(ctx, fname)
            rendered = _format_value(value, fctype, fname)
        except Exception as e:  # noqa: BLE001 - one bad field never blanks the block
            rendered = f"<err: {type(e).__name__}: {e}>"
        rows.append((fname, rendered))
    return ui.kv_block(name, rows)


# ---------------------------------------------------------------------------
# AgentArray — special-cased: its GWContext facade is unwired in Reforged 2.0,
# so read the array from shared memory (the same source Py4GWCoreLib/AgentArray.py
# uses) and dump the AgentArraySHMemStruct sub-arrays by their KNOWN accessors.
# ---------------------------------------------------------------------------
_AGENT_ARRAY_SUBARRAYS = [
    ("AllArray", "get_all_array"),
    ("AllyArray", "get_ally_array"),
    ("NeutralArray", "get_neutral_array"),
    ("EnemyArray", "get_enemy_array"),
    ("SpiritPetArray", "get_spirit_pet_array"),
    ("MinionArray", "get_minion_array"),
    ("NPCMinipetArray", "get_npc_minipet_array"),
    ("LivingArray", "get_living_array"),
    ("ItemArray", "get_item_array"),
    ("OwnedItemArray", "get_owned_item_array"),
    ("GadgetArray", "get_gadget_array"),
    ("DeadAllyArray", "get_dead_ally_array"),
    ("DeadEnemyArray", "get_dead_enemy_array"),
]


def _agent_array_ptr() -> int:
    """Live in-process AgentArray context pointer via the pattern-scan symbol.

    This is the resolver ``AgentArray._update_ptr`` would call if the facade were wired;
    the facade's cached ``get_ptr()`` returns 0 because that callback is never registered.
    """
    try:
        from Py4GWCoreLib.native_src.context.AgentContext import AgentArray_GetPtr

        return int(AgentArray_GetPtr.read_ptr() or 0)
    except Exception:  # noqa: BLE001 - display, don't crash
        return 0


def _agent_array_block():
    from Py4GWCoreLib.native_src.ShMem.SysShaMem import SystemShaMemMgr

    ptr = _agent_array_ptr()
    aaw = casts.safe(SystemShaMemMgr.get_agent_array_wrapper, default=None)
    rows = [
        ("GetPtr()", casts.ptr(ptr)),
        ("source", "shared memory (SystemShaMemMgr.get_agent_array_wrapper)"),
        ("IsValid()", casts.yesno(aaw is not None)),
    ]
    if aaw is None:
        rows.append(("(data)", "agent array wrapper not available in this state"))
        return ui.kv_block("AgentArray", rows)

    all_ids = casts.safe(aaw.to_int_list, default=[]) or []
    rows.append(("AgentArrayCount", str(len(all_ids))))
    for label, method_name in _AGENT_ARRAY_SUBARRAYS:
        getter = getattr(aaw, method_name, None)
        if getter is None:
            rows.append((label, "<no accessor>"))
            continue
        ids = casts.safe(getter, default=[]) or []
        preview = ", ".join(str(i) for i in ids[:12])
        if len(ids) > 12:
            preview += ", ..."
        rows.append((f"{label} (count={len(ids)})", preview if ids else "(empty)"))
    return ui.kv_block("AgentArray", rows)


def build_contexts():
    blocks = []
    for name, get_ptr, get_ctx in _CONTEXTS:
        if name == "AgentArray":
            blocks.append(_agent_array_block())
        else:
            blocks.append(_context_block(name, get_ptr, get_ctx))
    return blocks


# ---------------------------------------------------------------------------
# draw_*_view — uniform section entry point (selector: render one, dump all)
# ---------------------------------------------------------------------------
def draw_contexts_view() -> None:
    global state
    blocks = build_contexts()
    diagnostics.dump_button(_SECTION, blocks)
    PyImGui.same_line(0, 12)
    ui.text_muted("(dump writes ALL contexts; the selector below only picks what to show)")
    PyImGui.separator()

    labels = [name for name, _, _ in _CONTEXTS]
    PyImGui.push_item_width(240)
    state.selected_index = PyImGui.combo("Context", state.selected_index, labels)
    PyImGui.pop_item_width()
    if not (0 <= state.selected_index < len(blocks)):
        state.selected_index = 0

    PyImGui.spacing()
    ui.draw_blocks(_SECTION, [blocks[state.selected_index]])
