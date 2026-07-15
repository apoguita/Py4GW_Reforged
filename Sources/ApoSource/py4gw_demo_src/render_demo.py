"""
Render section — native ``PyRender`` module (read-only render-loop / viewport state).

Follows the player_demo.py contract: ``build_render()`` calls the native getters, CASTS each
value via ``casts``, and returns display Blocks; ``draw_render_view()`` renders those blocks and
offers the per-section Dump-to-file button. NO reflection — every method wired by hand.

Data path: ``PyRender.*`` free functions (native module, no stub, no wrapper). All five are
no-arg read-only getters, so they land as Data rows. ``PyRender`` exposes NO mutators (verified
against ``Py4GW_Reforged_Native/src/GW/render/render_bindings.cpp`` — only the five getters are
bound), so there is no Actions tab; the Data view carries a muted note stating so.

R2 coverage — PyRender getters wired (5/5): get_is_in_render_loop, get_is_fullscreen,
get_viewport_width, get_viewport_height, get_field_of_view.
Actions wired: none (PyRender is read-only; module has no mutating/action functions).
Skipped: none.
"""

import PyImGui

from . import casts
from . import diagnostics
from . import ui

_SECTION = "Render"

_err = ""


def _mod():
    """Return the native PyRender module, or None (records the import error once)."""
    global _err
    try:
        import PyRender  # embedded module — only present in-client
        return PyRender
    except Exception as e:  # noqa: BLE001
        _err = f"{type(e).__name__}: {e}"
        return None


class _State:
    pass


state = _State()


# ---------------------------------------------------------------------------
# build_* — call getters, cast, return blocks (shared by render AND dump)
# ---------------------------------------------------------------------------
def build_render():
    mod = _mod()
    if mod is None:
        return [ui.text_block("PyRender", f"Not available: {_err}")]

    in_loop = casts.safe(mod.get_is_in_render_loop)
    fullscreen = casts.safe(mod.get_is_fullscreen)
    vw = casts.safe(mod.get_viewport_width)
    vh = casts.safe(mod.get_viewport_height)
    fov = casts.safe(mod.get_field_of_view)

    rows = [
        ("In Render Loop", casts.yesno(in_loop)),
        ("Is Fullscreen", f"{casts.yesno(fullscreen)} ({fullscreen})"),
        ("Viewport Width", vw),
        ("Viewport Height", vh),
        ("Viewport Size", casts.vec(vw or 0, vh or 0, nd=0)),
        ("Field of View", casts.f3(fov)),
    ]
    return [ui.kv_block("Render State", rows)]


# ---------------------------------------------------------------------------
# draw_*_view — uniform section entry point (no Actions: PyRender is read-only)
# ---------------------------------------------------------------------------
def draw_render_view() -> None:
    blocks = build_render()
    diagnostics.dump_button(_SECTION, blocks)
    PyImGui.separator()
    if PyImGui.begin_tab_bar("RenderTabs"):
        if PyImGui.begin_tab_item("Data"):
            ui.draw_blocks(_SECTION, blocks)
            ui.text_muted("PyRender exposes only read-only getters — no actions.")
            PyImGui.end_tab_item()
        PyImGui.end_tab_bar()
