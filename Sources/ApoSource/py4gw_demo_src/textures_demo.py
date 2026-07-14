"""
Textures section — native ``PyTexture`` loaders wired to a real file picker + on-screen preview.

The old file only printed handle ints. This one makes the loaders concrete:
  * File textures: a native ImGui file browser (``PyImGui.filebrowser.FileBrowser``) OR a raw path
    input feeds ``get_file_texture(path)``; the returned handle is shown (``casts.ptr``) AND the
    texture is DISPLAYED with ``PyImGui.image(handle, size)``.
  * DAT textures: load by cache key (``get_dat_texture('gwdat://<file_id>')``) or directly by file
    id (``get_texture_by_file_id(file_id)``) — both async — and DISPLAY the result. Because the DAT
    decoders return 0 until the upload finishes, the active loader is re-called every frame so the
    preview appears once the texture is ready.
  * Colored model textures: ``get_colored_model_texture(model_file_id, dye_tint, dye1..dye4)``.

Verified native surface (Py4GW_Reforged_Native/src/GW/textures/texture_bindings.cpp):
  get_file_texture(path:str) -> int
  get_dat_texture(key:str) -> int
  get_texture_by_file_id(file_id:uint32) -> int
  get_colored_model_texture(model_file_id, dye_tint=0, dye1=0, dye2=0, dye3=0, dye4=0) -> int
  cleanup_old_textures(timeout_seconds=30) -> None
Every handle is the D3D9 texture pointer as an int (0 when not ready) — usable directly as an
``PyImGui.image`` texture id. Colors that overflow int32 (ARGB dye tints) use ``ui.input_hex``.
"""

import PyImGui

from . import casts
from . import diagnostics
from . import ui

_SECTION = "Textures"

_err = ""
_browser = None
_browser_err = ""
_browser_open = False
_BROWSER_POPUP = "TextureFileBrowser"
_IMG_TYPES = ".png,.jpg,.jpeg,.bmp,.dds,.tga"


def _mod():
    """Return the native PyTexture module, or None (records the import error once)."""
    global _err
    try:
        import PyTexture  # embedded module — only present in-client
        return PyTexture
    except Exception as e:  # noqa: BLE001
        _err = f"{type(e).__name__}: {e}"
        return None


def _get_browser():
    """Lazily build the ImGui-Addons file browser, or None if unavailable."""
    global _browser, _browser_err
    if _browser is None and not _browser_err:
        try:
            _browser = PyImGui.filebrowser.FileBrowser()
            _browser.set_use_modal(False)
        except Exception as e:  # noqa: BLE001
            _browser_err = f"{type(e).__name__}: {e}"
    return _browser


class _State:
    file_path: str = "Textures/Maps/example.png"
    dat_key: str = "gwdat://0"
    file_id: int = 0
    model_file_id: int = 0
    dye_tint: int = 0xFFFFFFFF
    dye1: int = 0
    dye2: int = 0
    dye3: int = 0
    dye4: int = 0
    cleanup_timeout: int = 30
    disp_w: float = 128.0
    disp_h: float = 128.0

    def __init__(self):
        # slot -> (fn_name, args) of the last requested load (re-resolved each frame so async
        # DAT uploads eventually show), and slot -> last handle int.
        self.active: "dict[str, tuple]" = {}
        self.handles: "dict[str, object]" = {}


state = _State()


# ---------------------------------------------------------------------------
# Loader plumbing — activate a slot, then re-resolve its handle each frame
# ---------------------------------------------------------------------------
def _activate(slot, fn_name, *args):
    mod = _mod()
    if mod is None:
        raise RuntimeError(f"PyTexture unavailable: {_err}")
    state.active[slot] = (fn_name, args)
    handle = _resolve(slot)
    return casts.ptr(handle)


def _resolve(slot):
    """Re-call the slot's stored loader; cache and return the current handle (or None)."""
    req = state.active.get(slot)
    if req is None:
        return None
    mod = _mod()
    if mod is None:
        return None
    fn_name, args = req
    try:
        handle = getattr(mod, fn_name)(*args)
    except Exception:  # noqa: BLE001 - a debug tool must survive a broken loader
        return None
    state.handles[slot] = handle
    return handle


def _cleanup():
    mod = _mod()
    if mod is None:
        raise RuntimeError(f"PyTexture unavailable: {_err}")
    mod.cleanup_old_textures(state.cleanup_timeout)
    return "cleaned"


# ---------------------------------------------------------------------------
# build_* — cast the stored handles into blocks (shared by render AND dump)
# ---------------------------------------------------------------------------
def _handle_rows(entries):
    rows = []
    for slot, source in entries:
        handle = _resolve(slot) if slot in state.active else None
        if handle is None:
            rows.append((source, "0x0", "not loaded"))
        else:
            ready = "ready" if handle else "0 (async — retrying)"
            rows.append((source, casts.ptr(handle), ready))
    return rows


def build_textures():
    inputs = ui.kv_block("Loader Inputs", [
        ("file_path", state.file_path),
        ("dat_key", state.dat_key),
        ("file_id", state.file_id),
        ("model_file_id", state.model_file_id),
        ("dye_tint", casts.hex_of(state.dye_tint, 8)),
        ("dyes (1..4)", f"{state.dye1}, {state.dye2}, {state.dye3}, {state.dye4}"),
        ("display size (w,h)", casts.vec(state.disp_w, state.disp_h)),
        ("cleanup timeout (s)", state.cleanup_timeout),
    ])
    handles = ui.multi_block("Resolved Handles", ["Source", "Handle", "Status"], _handle_rows([
        ("file", "get_file_texture"),
        ("dat", "get_dat_texture"),
        ("file_id", "get_texture_by_file_id"),
        ("model", "get_colored_model_texture"),
    ]))
    return [inputs, handles]


# ---------------------------------------------------------------------------
# on-screen preview of a slot's texture
# ---------------------------------------------------------------------------
def _preview(slot) -> None:
    handle = _resolve(slot)
    if handle is None:
        ui.text_muted("(not loaded)")
        return
    PyImGui.text_unformatted(f"handle: {casts.ptr(handle)}")
    if handle:
        casts.safe(lambda: PyImGui.image(int(handle), (state.disp_w, state.disp_h)))
    else:
        ui.text_muted("handle 0 — decoding/async, will appear when ready")


# ---------------------------------------------------------------------------
# native file browser (drives an OpenPopup + show_file_dialog each frame)
# ---------------------------------------------------------------------------
def _file_browser_row() -> None:
    # The popup-based native file browser was REMOVED: PyImGui.open_popup puts the dialog in ImGui's
    # GLOBAL popup stack, and if the user opens it then navigates to another demo section (so
    # show_file_dialog stops being called), the popup can orphan and corrupt popups in OTHER widgets
    # (e.g. the travel widget). A debug tool must never leak global ImGui state, so we use the plain
    # path field below instead. (No open_popup anywhere in the demo now.)
    ui.text_muted("Type or paste a texture path below (e.g. Textures/Module_Icons/Py4GW.png).")


# ---------------------------------------------------------------------------
# Actions — explicit loaders + live preview
# ---------------------------------------------------------------------------
def _draw_actions() -> None:
    if _mod() is None:
        ui.not_available(f"PyTexture unavailable — {_err}")
        return

    state.disp_w = PyImGui.input_float("Preview Width", state.disp_w)
    state.disp_h = PyImGui.input_float("Preview Height", state.disp_h)

    PyImGui.spacing()
    ui.section_header("File texture (get_file_texture)")
    _file_browser_row()
    state.file_path = PyImGui.input_text("File Path", state.file_path)
    ui.action_button(
        "Load & Display File Texture",
        lambda: _activate("file", "get_file_texture", state.file_path),
        key="tex_file",
    )
    _preview("file")

    PyImGui.spacing()
    ui.section_header("DAT texture by key (get_dat_texture)")
    state.dat_key = PyImGui.input_text("Dat Key (gwdat://<file_id>)", state.dat_key)
    ui.action_button(
        "Load & Display Dat Texture",
        lambda: _activate("dat", "get_dat_texture", state.dat_key),
        key="tex_dat",
    )
    _preview("dat")

    PyImGui.spacing()
    ui.section_header("DAT texture by file id (get_texture_by_file_id)")
    state.file_id = PyImGui.input_int("File ID", state.file_id)
    ui.action_button(
        "Load & Display By File ID",
        lambda: _activate("file_id", "get_texture_by_file_id", state.file_id),
        key="tex_fileid",
    )
    _preview("file_id")

    PyImGui.spacing()
    ui.section_header("Colored model texture (get_colored_model_texture)")
    state.model_file_id = PyImGui.input_int("Model File ID", state.model_file_id)
    state.dye_tint = ui.input_hex("Dye Tint (ARGB)", state.dye_tint)
    state.dye1 = PyImGui.input_int("Dye 1", state.dye1)
    state.dye2 = PyImGui.input_int("Dye 2", state.dye2)
    state.dye3 = PyImGui.input_int("Dye 3", state.dye3)
    state.dye4 = PyImGui.input_int("Dye 4", state.dye4)
    ui.action_button(
        "Load & Display Colored Model",
        lambda: _activate(
            "model", "get_colored_model_texture",
            state.model_file_id, state.dye_tint, state.dye1, state.dye2, state.dye3, state.dye4,
        ),
        key="tex_model",
    )
    _preview("model")

    PyImGui.spacing()
    ui.section_header("Maintenance")
    state.cleanup_timeout = PyImGui.input_int("Cleanup Timeout (s)", state.cleanup_timeout)
    ui.action_button("Cleanup Old Textures", _cleanup, key="tex_cleanup")


# ---------------------------------------------------------------------------
# draw_*_view — uniform section entry point
# ---------------------------------------------------------------------------
def draw_textures_view() -> None:
    blocks = build_textures()
    diagnostics.dump_button(_SECTION, blocks)
    PyImGui.separator()
    if PyImGui.begin_tab_bar("TexturesTabs"):
        if PyImGui.begin_tab_item("Data"):
            ui.draw_blocks(_SECTION, blocks)
            PyImGui.end_tab_item()
        if PyImGui.begin_tab_item("Actions"):
            _draw_actions()
            PyImGui.end_tab_item()
        PyImGui.end_tab_bar()
