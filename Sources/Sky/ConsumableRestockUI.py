from __future__ import annotations

import os
from collections.abc import Sequence

import PyImGui
import PySystem

from Py4GWCoreLib import ImGui
from Py4GWCoreLib.enums_src.Texture_enums import get_texture_for_model


_ITEM_TEXTURE_DIR = os.path.join(
    PySystem.Console.get_projects_path(),
    "Assets",
    "Textures",
    "Item Models",
)

# A few consumables use historical texture filenames that do not match the
# current ModelID enum member name. Keep those presentation-only aliases here;
# gameplay/restock logic continues to use the real ModelID.
_TEXTURE_FILENAME_OVERRIDES: dict[int, str] = {
    30209: "30209-Tengu_Support_Flare.png",
    31155: "Mysterious_Summoning_Stone.png",
}


def _resolve_item_texture(model_id: int) -> str:
    model_id = int(model_id)

    override = _TEXTURE_FILENAME_OVERRIDES.get(model_id)
    if override:
        candidate = os.path.join(_ITEM_TEXTURE_DIR, override)
        if os.path.isfile(candidate):
            return candidate

    texture = get_texture_for_model(model_id)
    if texture and os.path.isfile(texture):
        return texture

    # Generic fallback for enum aliases / renamed item entries: prefer any PNG
    # whose numeric prefix is the requested ModelID. This remains UI-only.
    prefix = f"{model_id:05d}-"
    try:
        for filename in os.listdir(_ITEM_TEXTURE_DIR):
            if filename.startswith(prefix) and filename.lower().endswith(".png"):
                return os.path.join(_ITEM_TEXTURE_DIR, filename)
    except Exception:
        pass

    return texture


def draw_restock_group_grid(
    group_name: str,
    items: Sequence[tuple[str, int, int]],
    quantities: dict[int, int],
    *,
    group_enabled: bool,
    columns: int = 4,
    icon_size: float = 48.0,
) -> bool:
    """Draw one reusable icon grid for per-item restock targets.

    ``items`` entries are ``(label, model_id, default_quantity)``. Quantities
    are edited in place and the return value tells the caller whether anything
    changed and should be persisted.
    """
    changed = False
    columns = max(1, int(columns))

    PyImGui.separator()
    PyImGui.text(group_name)
    if not group_enabled:
        PyImGui.same_line()
        PyImGui.text_disabled("(restock disabled in Config)")

    table_id = f"##restock_grid_{group_name.replace(' ', '_')}"
    if not PyImGui.begin_table(table_id, columns, 0):
        return False

    try:
        for label, model_id, default in items:
            model_id = int(model_id)
            current = max(0, int(quantities.get(model_id, default)))
            active = bool(group_enabled and current > 0)

            PyImGui.table_next_column()

            texture = _resolve_item_texture(model_id)
            tint = (255, 255, 255, 255) if active else (120, 120, 120, 150)
            ImGui.image(texture, (icon_size, icon_size), tint=tint)

            if PyImGui.is_item_hovered():
                PyImGui.begin_tooltip()
                PyImGui.text(label)
                PyImGui.text(f"Target per account: {current}")
                PyImGui.text(f"ModelID: {model_id}")
                if not group_enabled:
                    PyImGui.text_disabled("Restock disabled for this group in Config")
                elif current <= 0:
                    PyImGui.text_disabled("This item is disabled (target = 0)")
                else:
                    PyImGui.text("Restock active")
                PyImGui.end_tooltip()

            PyImGui.set_next_item_width(88.0)
            value = max(0, int(PyImGui.input_int(f"##restock_qty_{model_id}", current)))
            if value != current:
                quantities[model_id] = value
                changed = True
    finally:
        PyImGui.end_table()

    return changed
