"""
Render kit for Py4GW DEMO 2.0 — raw PyImGui only (no ImGui_Legacy, no reflection).

Design (see docs/demo_replacement/reengineer/SPEC_reengineer.md):
  * A section's ``build_*()`` returns a list of **Blocks** — already-cast display data.
  * ``draw_blocks()`` renders them; ``diagnostics.dump()`` serializes the SAME blocks to file,
    so the on-screen view and the log never diverge.
  * There is deliberately **no** generic ``fmt_value``/``repr`` fallback and **no** probe/
    auto-discovery harness — every value is cast by the section via ``casts.py`` before it gets
    here. A struct must never reach a renderer un-dereferenced.

Block model (a plain tuple, kept trivial so it serializes cleanly):
  ("kv",    title, rows)            rows = list[(field:str, value:str)]
  ("multi", title, (headers, rows)) headers = list[str], rows = list[tuple]
  ("bools", title, items)          items = list[(label:str, value:bool)]
  ("text",  title, body:str)
"""

import PyImGui

# ---------------------------------------------------------------------------
# Colors (normalized 0..1 tuples, which PyImGui.text_colored expects)
# ---------------------------------------------------------------------------
OK_COLOR = (0.35, 0.85, 0.40, 1.0)
ERR_COLOR = (0.90, 0.30, 0.30, 1.0)
MUTED_COLOR = (0.60, 0.60, 0.65, 1.0)
ACCENT_COLOR = (1.00, 0.78, 0.39, 1.0)


def colored_bool(value: bool) -> tuple:
    return OK_COLOR if value else ERR_COLOR


def text_muted(text: str) -> None:
    PyImGui.text_colored(text, MUTED_COLOR)


def not_available(reason: str) -> None:
    PyImGui.text_colored(f"Not available: {reason}", MUTED_COLOR)


def section_header(text: str) -> None:
    PyImGui.text_colored(text, ACCENT_COLOR)
    PyImGui.separator()


# ---------------------------------------------------------------------------
# Block constructors (sections build these; draw_blocks + diagnostics consume them)
# ---------------------------------------------------------------------------
def kv_block(title, rows):
    """rows: list[(field, value)] — values should already be cast strings."""
    return ("kv", title, [(str(f), str(v)) for f, v in rows])


def multi_block(title, headers, rows):
    return ("multi", title, ([str(h) for h in headers], list(rows)))


def bool_block(title, items):
    """items: list[(label, bool)]."""
    return ("bools", title, [(str(lbl), bool(val)) for lbl, val in items])


def text_block(title, body):
    return ("text", title, str(body))


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------
def draw_kv_table(table_id: str, rows: "list[tuple[str, object]]") -> None:
    flags = (
        PyImGui.TableFlags.BordersInnerV
        | PyImGui.TableFlags.RowBg
        | PyImGui.TableFlags.SizingStretchProp
    )
    if PyImGui.begin_table(table_id, 2, flags):
        PyImGui.table_setup_column("Field", PyImGui.TableColumnFlags.WidthFixed, 220)
        PyImGui.table_setup_column("Value", PyImGui.TableColumnFlags.WidthStretch)
        PyImGui.table_headers_row()
        for field, value in rows:
            PyImGui.table_next_row()
            PyImGui.table_next_column()
            PyImGui.text_unformatted(str(field))
            PyImGui.table_next_column()
            PyImGui.text_unformatted(str(value))
        PyImGui.end_table()


def draw_multi_table(table_id: str, headers: "list[str]", rows: "list[tuple]") -> None:
    ncols = len(headers)
    if ncols == 0:
        return
    flags = (
        PyImGui.TableFlags.Borders
        | PyImGui.TableFlags.RowBg
        | PyImGui.TableFlags.SizingStretchProp
    )
    if PyImGui.begin_table(table_id, ncols, flags):
        for h in headers:
            PyImGui.table_setup_column(str(h), PyImGui.TableColumnFlags.WidthStretch)
        PyImGui.table_headers_row()
        for row in rows:
            PyImGui.table_next_row()
            for i in range(ncols):
                PyImGui.table_next_column()
                cell = row[i] if i < len(row) else ""
                PyImGui.text_unformatted(str(cell))
        PyImGui.end_table()


def draw_bool_grid(table_id: str, items: "list[tuple[str, bool]]", cols: int = 3) -> None:
    """Colored green/red status flags (agent_demo idiom) laid out in `cols` columns."""
    if not items:
        return
    flags = PyImGui.TableFlags.BordersInnerV | PyImGui.TableFlags.RowBg
    if PyImGui.begin_table(table_id, cols, flags):
        for idx, (label, value) in enumerate(items):
            if idx % cols == 0:
                PyImGui.table_next_row()
            PyImGui.table_next_column()
            PyImGui.text_colored(f"{label}: {'Yes' if value else 'No'}", colored_bool(value))
        PyImGui.end_table()


def draw_blocks(section_id: str, blocks) -> None:
    """Render a section's Block list. Header per block, right renderer per kind."""
    for bidx, block in enumerate(blocks):
        kind, title, payload = block
        if title:
            section_header(str(title))
        tid = f"{section_id}_b{bidx}"
        if kind == "kv":
            draw_kv_table(tid, payload)
        elif kind == "multi":
            headers, rows = payload
            draw_multi_table(tid, headers, rows)
        elif kind == "bools":
            draw_bool_grid(tid, payload)
        elif kind == "text":
            PyImGui.text_unformatted(str(payload))
        PyImGui.spacing()


# ---------------------------------------------------------------------------
# Explicit action triggers (NOT reflection) — a button that fires a known action
# ---------------------------------------------------------------------------
class _Result:
    __slots__ = ("ok", "value", "error")

    def __init__(self, ok, value=None, error=""):
        self.ok = ok
        self.value = value
        self.error = error


_action_results: "dict[str, _Result]" = {}


def input_hex(label: str, value: int) -> int:
    """Hex text input for values that overflow signed int32 (ARGB colors, handles, hashes).

    PyImGui.input_int is int32-backed, so a color like 0xFFFF0000 (> 2^31) raises. This renders
    the value as an editable ``0xAARRGGBB`` string and parses it back to an int each frame.
    """
    try:
        current = f"0x{int(value) & 0xFFFFFFFF:08X}"
    except (TypeError, ValueError):
        current = "0x00000000"
    text = PyImGui.input_text(label, current)
    try:
        s = str(text).strip()
        return int(s, 16) if s.lower().startswith("0x") else int(s)
    except (TypeError, ValueError):
        return value


def action_button(label: str, fn, *args, key: str = "", **kwargs) -> None:
    """A button that invokes an explicit action binding and shows its last outcome inline.

    For mutate/send bindings (travel, use-skill, invite, drop-buff, ...). The action fires only
    on click — never on render — so this is safe for game-moving calls.
    """
    slot = key or label
    if PyImGui.button(label):
        try:
            _action_results[slot] = _Result(True, fn(*args, **kwargs))
        except Exception as e:  # noqa: BLE001 - surface the error, keep the widget alive
            _action_results[slot] = _Result(False, None, f"{type(e).__name__}: {e}")
    res = _action_results.get(slot)
    if res is not None:
        PyImGui.same_line(0, 8)
        if res.ok:
            val = res.value
            PyImGui.text_colored("ok" if val is None else f"ok: {val}", OK_COLOR)
        else:
            PyImGui.text_colored(res.error, ERR_COLOR)
