"""
Scanner section — native ``PyScanner`` memory-scan surface (pattern find, pointer
validation, section ranges, scan/hook status).

Shape mirrors ``player_demo`` exactly:
  * ``build_scanner()`` instantiates the ``PyScanner.PyScanner`` handle explicitly, calls its
    getters, CASTS every value (section ranges + resolved addresses are legitimately hex ->
    ``casts.hex_of`` / ``casts.ptr``) and returns display Blocks. No handle is ever repr'd raw —
    the raw ``GetScanStatus`` snapshot is read through ``casts.handle_rows`` (explicit accessor list).
  * ``draw_scanner_view()`` renders those blocks and exposes every scan/find/init binding as an
    explicit trigger button (never auto-fired — a stray pattern scan is cheap but still a side call).

Data path: native ``PyScanner`` module (bound ``PyScanner`` class of ``def_static`` methods over
``PY4GW::Scanner``). Section args are raw uint8 indices: 0=.text, 1=.rdata, 2=.data.

R2 coverage — PyScanner (15/15):
  Data getters wired: GetSectionAddressRange, GetScanStatus.
  Action getters wired: Initialize, Find, FindInRange, FunctionFromNearCall, ToFunctionStart,
    IsValidPtr, FindUseOfAddress, FindNthUseOfAddress, FindUseOfStringA, FindUseOfStringW,
    FindNthUseOfStringA, FindNthUseOfStringW, FindAssertion.
  Skipped: none.
"""

import PyImGui
import PyScanner

from . import casts
from . import diagnostics
from . import ui

_SECTION = "Scanner"
_SECTION_NAMES = [".text", ".rdata", ".data"]

# PyScanner.PyScanner exposes only @staticmethod members and has NO constructor — instantiating it
# raises "No constructor defined!". Bind the CLASS (no call) so the static methods resolve and there
# is no import-time side effect (widget scripts must be passive on import).
_scanner = PyScanner.PyScanner


class _State:
    module_name: str = ""
    section_index: int = 0
    address_hex: str = "0x0"
    pattern_hex: str = "E8 ?? ?? ?? ??"
    mask: str = "x????"
    offset: int = 0
    nth: int = 1
    range_start_hex: str = "0x0"
    range_end_hex: str = "0x0"
    call_addr_hex: str = "0x0"
    check_valid_ptr: bool = True
    scan_range: int = 0xFF
    string_ansi: str = ""
    string_wide: str = ""
    assertion_file: str = ""
    assertion_msg: str = ""
    assertion_line: int = 0


state = _State()


# ---------------------------------------------------------------------------
# Small parsers (explicit — not reflection). Addresses can exceed signed-int32,
# so address fields are text and parsed here rather than via input_int.
# ---------------------------------------------------------------------------
def _parse_addr(text) -> int:
    try:
        s = str(text).strip()
        if s.lower().startswith("0x"):
            return int(s, 16)
        return int(s)
    except (TypeError, ValueError):
        return 0


def _parse_pattern(text) -> bytes:
    """Turn a space-separated hex-byte string (``E8 ?? 00``) into bytes (wildcards -> 0x00)."""
    out = bytearray()
    for tok in str(text).replace(",", " ").split():
        if tok in ("??", "?", "**"):
            out.append(0)
            continue
        try:
            out.append(int(tok, 16) & 0xFF)
        except ValueError:
            out.append(0)
    return bytes(out)


def _section_val() -> int:
    idx = state.section_index
    return idx if 0 <= idx < len(_SECTION_NAMES) else 0


# ---------------------------------------------------------------------------
# build_* — call getters, cast, return blocks (shared by render AND dump)
# ---------------------------------------------------------------------------
def _section_ranges_block():
    headers = ["Section", "Index", "Start", "End", "Size"]
    rows = []
    for idx, name in enumerate(_SECTION_NAMES):
        rng = casts.safe(_scanner.GetSectionAddressRange, idx, default=(0, 0)) or (0, 0)
        try:
            start, end = int(rng[0]), int(rng[1])
        except (TypeError, ValueError, IndexError):
            start, end = 0, 0
        size = end - start if end >= start else 0
        rows.append((name, idx, casts.hex_of(start, 8), casts.hex_of(end, 8), casts.flags(size)))
    return ui.multi_block("Section Address Ranges", headers, rows)


def _scan_status():
    """Read GetScanStatus once; return the parsed dict (guarded)."""
    status = casts.safe(_scanner.GetScanStatus, default={}) or {}
    if not isinstance(status, dict):
        return {}, {}
    scans = status.get("scans", {}) or {}
    hooks = status.get("hooks", {}) or {}
    return scans, hooks


def _scans_block(scans):
    rows = []
    for name, addr in scans.items():
        rows.append((str(name), casts.ptr(addr)))
    return ui.multi_block(f"Resolved Scans ({len(rows)})", ["Name", "Address"], rows)


def _hooks_block(hooks):
    rows = []
    for name, status in hooks.items():
        rows.append((str(name), str(status)))
    return ui.multi_block(f"Installed Hooks ({len(rows)})", ["Name", "Status"], rows)


def _handle_snapshot_block():
    """Raw accessor snapshot via the explicit handle-accessor mechanism (no reflection)."""
    rows = casts.handle_rows(_scanner, [("GetScanStatus (raw)", "GetScanStatus")])
    return ui.kv_block("Handle Accessor Snapshot", rows)


def build_scanner():
    scans, hooks = _scan_status()
    return [
        _section_ranges_block(),
        _scans_block(scans),
        _hooks_block(hooks),
        _handle_snapshot_block(),
    ]


# ---------------------------------------------------------------------------
# Explicit action wrappers — format the resolved address as hex for the result line.
# These are hand-wired 1:1 onto the native binding (not a reflective dispatch).
# ---------------------------------------------------------------------------
def _do_find():
    return casts.ptr(_scanner.Find(_parse_pattern(state.pattern_hex), state.mask, state.offset, _section_val()))


def _do_find_in_range():
    return casts.ptr(
        _scanner.FindInRange(
            _parse_pattern(state.pattern_hex),
            state.mask,
            state.offset,
            _parse_addr(state.range_start_hex),
            _parse_addr(state.range_end_hex),
        )
    )


def _do_function_from_near_call():
    return casts.ptr(_scanner.FunctionFromNearCall(_parse_addr(state.call_addr_hex), bool(state.check_valid_ptr)))


def _do_to_function_start():
    return casts.ptr(_scanner.ToFunctionStart(_parse_addr(state.address_hex), state.scan_range))


def _do_is_valid_ptr():
    return casts.yesno(_scanner.IsValidPtr(_parse_addr(state.address_hex), _section_val()))


def _do_find_use_of_address():
    return casts.ptr(_scanner.FindUseOfAddress(_parse_addr(state.address_hex), state.offset, _section_val()))


def _do_find_nth_use_of_address():
    return casts.ptr(
        _scanner.FindNthUseOfAddress(_parse_addr(state.address_hex), state.nth, state.offset, _section_val())
    )


def _do_find_use_of_string_a():
    return casts.ptr(_scanner.FindUseOfStringA(state.string_ansi, state.offset, _section_val()))


def _do_find_use_of_string_w():
    return casts.ptr(_scanner.FindUseOfStringW(state.string_wide, state.offset, _section_val()))


def _do_find_nth_use_of_string_a():
    return casts.ptr(_scanner.FindNthUseOfStringA(state.string_ansi, state.nth, state.offset, _section_val()))


def _do_find_nth_use_of_string_w():
    return casts.ptr(_scanner.FindNthUseOfStringW(state.string_wide, state.nth, state.offset, _section_val()))


def _do_find_assertion():
    return casts.ptr(
        _scanner.FindAssertion(state.assertion_file, state.assertion_msg, state.assertion_line, state.offset)
    )


# ---------------------------------------------------------------------------
# Actions — explicit trigger buttons, fired only on click
# ---------------------------------------------------------------------------
def _draw_actions():
    ui.section_header("Initialize")
    state.module_name = PyImGui.input_text("Module (blank = main)", state.module_name)
    ui.action_button("Initialize", _scanner.Initialize, state.module_name, key="scan_init")

    PyImGui.spacing()
    ui.section_header("Common inputs")
    PyImGui.push_item_width(200)
    state.section_index = PyImGui.combo("Section", state.section_index, _SECTION_NAMES)
    PyImGui.pop_item_width()
    state.address_hex = PyImGui.input_text("Address (hex/dec)", state.address_hex)
    state.offset = PyImGui.input_int("Offset", state.offset)
    state.nth = PyImGui.input_int("Nth", state.nth)

    PyImGui.spacing()
    ui.section_header("Pattern scan")
    state.pattern_hex = PyImGui.input_text("Pattern (E8 ?? 00 ...)", state.pattern_hex)
    state.mask = PyImGui.input_text("Mask (x????)", state.mask)
    ui.action_button("Find", _do_find, key="scan_find")
    state.range_start_hex = PyImGui.input_text("Range Start", state.range_start_hex)
    state.range_end_hex = PyImGui.input_text("Range End", state.range_end_hex)
    ui.action_button("Find In Range", _do_find_in_range, key="scan_find_range")

    PyImGui.spacing()
    ui.section_header("Function resolution / validation")
    state.call_addr_hex = PyImGui.input_text("Call Instruction Addr", state.call_addr_hex)
    state.check_valid_ptr = PyImGui.checkbox("Check Valid Ptr", state.check_valid_ptr)
    ui.action_button("Function From Near Call", _do_function_from_near_call, key="scan_ffnc")
    state.scan_range = PyImGui.input_int("Prologue Scan Range", state.scan_range)
    ui.action_button("To Function Start", _do_to_function_start, key="scan_tofs")
    PyImGui.same_line(0, 8)
    ui.action_button("Is Valid Ptr", _do_is_valid_ptr, key="scan_isvalid")

    PyImGui.spacing()
    ui.section_header("Address usage")
    ui.action_button("Find Use Of Address", _do_find_use_of_address, key="scan_fuoa")
    PyImGui.same_line(0, 8)
    ui.action_button("Find Nth Use Of Address", _do_find_nth_use_of_address, key="scan_fnuoa")

    PyImGui.spacing()
    ui.section_header("String usage")
    state.string_ansi = PyImGui.input_text("ANSI String", state.string_ansi)
    ui.action_button("Find Use Of String (A)", _do_find_use_of_string_a, key="scan_fuosa")
    PyImGui.same_line(0, 8)
    ui.action_button("Find Nth Use Of String (A)", _do_find_nth_use_of_string_a, key="scan_fnuosa")
    state.string_wide = PyImGui.input_text("Wide String", state.string_wide)
    ui.action_button("Find Use Of String (W)", _do_find_use_of_string_w, key="scan_fuosw")
    PyImGui.same_line(0, 8)
    ui.action_button("Find Nth Use Of String (W)", _do_find_nth_use_of_string_w, key="scan_fnuosw")

    PyImGui.spacing()
    ui.section_header("Assertion")
    state.assertion_file = PyImGui.input_text("Assertion File", state.assertion_file)
    state.assertion_msg = PyImGui.input_text("Assertion Msg", state.assertion_msg)
    state.assertion_line = PyImGui.input_int("Line Number", state.assertion_line)
    ui.action_button("Find Assertion", _do_find_assertion, key="scan_assert")


# ---------------------------------------------------------------------------
# draw_*_view — uniform section entry point
# ---------------------------------------------------------------------------
def draw_scanner_view() -> None:
    blocks = build_scanner()
    diagnostics.dump_button(_SECTION, blocks)
    PyImGui.separator()
    if PyImGui.begin_tab_bar("ScannerTabs"):
        if PyImGui.begin_tab_item("Data"):
            ui.draw_blocks(_SECTION, blocks)
            PyImGui.end_tab_item()
        if PyImGui.begin_tab_item("Actions"):
            _draw_actions()
            PyImGui.end_tab_item()
        PyImGui.end_tab_bar()
