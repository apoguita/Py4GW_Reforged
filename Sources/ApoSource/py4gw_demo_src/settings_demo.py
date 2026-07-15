"""
Settings section — native ``PySettings`` per-account INI documents.

Shape (mirrors player_demo, the canonical template):
  * ``build_settings()`` opens NOTHING on its own — it reads the already-opened document handle
    cached in ``state.doc`` plus the two module-level free-function getters, CASTS each value via
    ``casts``, and returns display Blocks. All reads are pure getters (no save/load), so running
    them every frame is safe and never fights the manager's autosave debounce.
  * ``draw_settings_view()`` renders those blocks and exposes every mutator/escape-hatch as an
    explicit click-only ``ui.action_button`` — a settings document is NEVER opened, written,
    saved or reloaded on render.

Data path: ``PySettings`` embedded module. Bound class name is ``settings`` (not ``PySettings``);
``PySettings.settings(name, scope)`` returns the document handle. Same ``(name, scope)`` pair
always yields the same document (idempotent open), so caching one handle is correct.

IMPORTANT (project rule): the SettingsManager autosaves on a debounce. This demo NEVER force-saves
or reloads per frame — ``save()`` and ``reload()`` are surfaced only as explicit buttons.

R2 coverage — all 30 methods wired by hand (no reflection/getattr-guessing):
  Instance getters (Data tab, read every frame): read(6), is_dirty(9), is_bound(10), path(11),
    has_key(12), keys(13), sections(14), get(21), has(22), items(24).
  Instance mutators / escape hatches (Actions tab, click-only): __init__(1) via Open Document,
    write(2-5) typed dispatch, save(7), reload(8), delete(15), delete_section(16), set(17-20)
    typed dispatch, remove(23).
  Module free functions: copy_document_to_account(25), copy_section_to_account(26),
    copy_keys_to_account(27), apply_section_to_account(28) [Actions]; is_anchored(29),
    get_settings_directory(30) [Data, module getters].

Contract-term mapping (native PySettings has no ``ensure_key``/``ensure_global_key``/``find`` —
those are Settings-wrapper names): the typed setters are ``write``/``set`` (choose ``scope=global``
for a global document), and ``find`` is served by the native ``has``/``has_key`` probes below.

Skipped: none — every R2 method is wired.
"""

import PySettings

import PyImGui

from . import casts
from . import diagnostics
from . import ui

_SECTION = "Settings"

_SCOPES = ["account", "global", "root"]
_VALUE_TYPES = ["str", "int", "float", "bool"]
_TYPE_TOKENS = {"str": str, "int": int, "float": float, "bool": bool}


class _State:
    # Document identity / handle
    doc_name: str = "Py4GW"
    scope_idx: int = 0
    doc = None
    doc_scope: str = ""

    # Section/key addressing (explicit set/get/has/remove/items/keys — separate args)
    section: str = "settings"
    key: str = "example"

    # Flat "section/key" addressing (write/read/delete/has_key split on '/')
    flat_key: str = "settings/example"

    # Typed value input (used by write + set)
    value_type_idx: int = 0
    value_text: str = ""

    # Cross-account copy inputs (free functions)
    target_email: str = ""
    copy_section: str = "settings"
    copy_keys: str = "example, other"
    apply_values: str = "example=1, other=2"


state = _State()


# ---------------------------------------------------------------------------
# Small explicit helpers (NOT reflection — each names its exact target)
# ---------------------------------------------------------------------------
def _type_token():
    return _TYPE_TOKENS[_VALUE_TYPES[state.value_type_idx]]


def _coerce_value():
    """Turn the typed-value text input into the selected Python type (may raise -> surfaced)."""
    name = _VALUE_TYPES[state.value_type_idx]
    text = state.value_text
    if name == "int":
        return int(text)
    if name == "float":
        return float(text)
    if name == "bool":
        return text.strip().lower() in ("1", "true", "yes", "on")
    return text


def _require_doc():
    if state.doc is None:
        raise RuntimeError("open a document first (Actions tab)")
    return state.doc


def _parse_key_list(text):
    return [p.strip() for p in text.split(",") if p.strip()]


def _parse_pairs(text):
    out = []
    for part in text.split(","):
        part = part.strip()
        if not part or "=" not in part:
            continue
        k, v = part.split("=", 1)
        out.append((k.strip(), v.strip()))
    return out


# ---------------------------------------------------------------------------
# Explicit action closures (click-only mutators / probes)
# ---------------------------------------------------------------------------
def _open_document():
    state.doc = PySettings.settings(state.doc_name, _SCOPES[state.scope_idx])
    state.doc_scope = _SCOPES[state.scope_idx]
    return state.doc_scope


def _write_flat():
    _require_doc().write(state.flat_key, _coerce_value())
    return "written"


def _set_explicit():
    _require_doc().set(state.section, state.key, _coerce_value())
    return "set"


def _delete_flat():
    return _require_doc().delete(state.flat_key)


def _delete_section():
    return _require_doc().delete_section(state.section)


def _remove_explicit():
    return _require_doc().remove(state.section, state.key)


def _probe_has():
    return _require_doc().has(state.section, state.key)


def _probe_has_key():
    return _require_doc().has_key(state.flat_key)


def _probe_get():
    return _require_doc().get(state.section, state.key, _type_token())


def _probe_read():
    return _require_doc().read(state.flat_key, _type_token())


def _save():
    return _require_doc().save()


def _reload():
    return _require_doc().reload()


def _copy_document():
    return PySettings.copy_document_to_account(state.doc_name, state.target_email)


def _copy_section():
    return PySettings.copy_section_to_account(state.doc_name, state.copy_section, state.target_email)


def _copy_keys():
    return PySettings.copy_keys_to_account(
        state.doc_name, state.copy_section, _parse_key_list(state.copy_keys), state.target_email
    )


def _apply_section():
    return PySettings.apply_section_to_account(
        state.doc_name, state.copy_section, _parse_pairs(state.apply_values), state.target_email
    )


# ---------------------------------------------------------------------------
# build_* — call getters, cast, return blocks (shared by render AND dump)
# ---------------------------------------------------------------------------
def _module_block():
    rows = [
        ("Is Anchored", casts.yesno(casts.safe(PySettings.is_anchored))),
        ("Settings Directory", casts.safe(PySettings.get_settings_directory, default="")),
    ]
    return ui.kv_block("Module (free functions)", rows)


def _document_block(doc):
    sections = casts.safe(doc.sections, default=[]) or []
    rows = [
        ("Name", state.doc_name),
        ("Scope", state.doc_scope),
        ("Path", casts.safe(doc.path, default="")),
        ("Is Bound", casts.yesno(casts.safe(doc.is_bound))),
        ("Is Dirty", casts.yesno(casts.safe(doc.is_dirty))),
        ("Sections (count)", len(sections)),
        ("Sections", str(list(sections))),
    ]
    return ui.kv_block("Document", rows)


def _section_keys_block(doc):
    keys = casts.safe(doc.keys, state.section, default=[]) or []
    rows = [
        (f"keys('{state.section}') count", len(keys)),
        ("keys", str(list(keys))),
    ]
    return ui.kv_block("Section keys", rows)


def _items_block(doc):
    items = casts.safe(doc.items, state.section, default=[]) or []
    return ui.multi_block("items(section)", ["Key", "Value"], [(k, v) for k, v in items])


def _probe_block(doc):
    """Live read of the current section/key/flat_key targets (getters only)."""
    vt = _VALUE_TYPES[state.value_type_idx]
    rows = [
        ("section", state.section),
        ("key", state.key),
        ("flat_key", state.flat_key),
        ("value type", vt),
        (f"has('{state.section}','{state.key}')", casts.yesno(casts.safe(doc.has, state.section, state.key))),
        (f"has_key('{state.flat_key}')", casts.yesno(casts.safe(doc.has_key, state.flat_key))),
        (f"get(...,{vt})", str(casts.safe(doc.get, state.section, state.key, _type_token(), default="<none>"))),
        (f"read('{state.flat_key}',{vt})", str(casts.safe(doc.read, state.flat_key, _type_token(), default="<none>"))),
    ]
    return ui.kv_block("Probe (typed get / read / has)", rows)


def build_settings():
    blocks = [_module_block()]
    doc = state.doc
    if doc is None:
        blocks.append(ui.text_block("Document", "No document open — use the Actions tab to Open Document."))
        return blocks
    blocks.append(_document_block(doc))
    blocks.append(_section_keys_block(doc))
    blocks.append(_items_block(doc))
    blocks.append(_probe_block(doc))
    return blocks


# ---------------------------------------------------------------------------
# Actions — explicit trigger buttons, fired only on click
# ---------------------------------------------------------------------------
def _draw_actions():
    ui.section_header("Document (open / escape hatches)")
    state.doc_name = PyImGui.input_text("Document Name", state.doc_name)
    state.scope_idx = PyImGui.combo("Scope", state.scope_idx, _SCOPES)
    ui.action_button("Open Document", _open_document, key="open_doc")
    PyImGui.same_line(0, 8)
    ui.action_button("Save (escape hatch)", _save, key="save")
    PyImGui.same_line(0, 8)
    ui.action_button("Reload (escape hatch)", _reload, key="reload")

    PyImGui.spacing()
    ui.section_header("Typed value")
    state.value_type_idx = PyImGui.combo("Value Type", state.value_type_idx, _VALUE_TYPES)
    state.value_text = PyImGui.input_text("Value", state.value_text)

    PyImGui.spacing()
    ui.section_header("Explicit (section, key) — set / get / has / remove")
    state.section = PyImGui.input_text("Section", state.section)
    state.key = PyImGui.input_text("Key", state.key)
    ui.action_button("set(section, key, value)", _set_explicit, key="set")
    PyImGui.same_line(0, 8)
    ui.action_button("get(section, key)", _probe_get, key="get")
    ui.action_button("has(section, key)", _probe_has, key="has")
    PyImGui.same_line(0, 8)
    ui.action_button("remove(section, key)", _remove_explicit, key="remove")
    PyImGui.same_line(0, 8)
    ui.action_button("delete_section(section)", _delete_section, key="del_section")

    PyImGui.spacing()
    ui.section_header("Flat 'section/key' — write / read / delete / has_key")
    state.flat_key = PyImGui.input_text("Flat Key", state.flat_key)
    ui.action_button("write(flat_key, value)", _write_flat, key="write")
    PyImGui.same_line(0, 8)
    ui.action_button("read(flat_key)", _probe_read, key="read")
    ui.action_button("has_key(flat_key)", _probe_has_key, key="has_key")
    PyImGui.same_line(0, 8)
    ui.action_button("delete(flat_key)", _delete_flat, key="delete")

    PyImGui.spacing()
    ui.section_header("Cross-account copy (free functions -> another account's file)")
    state.target_email = PyImGui.input_text("Target Email", state.target_email)
    state.copy_section = PyImGui.input_text("Copy Section", state.copy_section)
    state.copy_keys = PyImGui.input_text("Copy Keys (comma-sep)", state.copy_keys)
    state.apply_values = PyImGui.input_text("Apply Values (k=v, comma-sep)", state.apply_values)
    ui.action_button("copy_document_to_account", _copy_document, key="copy_doc")
    PyImGui.same_line(0, 8)
    ui.action_button("copy_section_to_account", _copy_section, key="copy_section")
    ui.action_button("copy_keys_to_account", _copy_keys, key="copy_keys")
    PyImGui.same_line(0, 8)
    ui.action_button("apply_section_to_account", _apply_section, key="apply_section")


# ---------------------------------------------------------------------------
# draw_*_view — uniform section entry point
# ---------------------------------------------------------------------------
def draw_settings_view() -> None:
    blocks = build_settings()
    diagnostics.dump_button(_SECTION, blocks)
    PyImGui.separator()
    if PyImGui.begin_tab_bar("SettingsTabs"):
        if PyImGui.begin_tab_item("Data"):
            ui.draw_blocks(_SECTION, blocks)
            PyImGui.end_tab_item()
        if PyImGui.begin_tab_item("Actions"):
            _draw_actions()
            PyImGui.end_tab_item()
        PyImGui.end_tab_bar()
