from __future__ import annotations

import os
from collections.abc import Sequence

import PyImGui
import PySystem

from Py4GWCoreLib import ImGui
from Py4GWCoreLib.enums_src.Texture_enums import get_texture_for_model
from Py4GWCoreLib.enums_src.Model_enums import ModelID

DEFAULT_RESTOCK_ITEM_DEFINITIONS: tuple[tuple[str, str, int, str, int], ...] = (
    ("Conset", "Essence of Celerity", int(ModelID.Essence_Of_Celerity.value), "RestockQtyEssenceOfCelerity", 10),
    ("Conset", "Grail of Might", int(ModelID.Grail_Of_Might.value), "RestockQtyGrailOfMight", 10),
    ("Conset", "Armor of Salvation", int(ModelID.Armor_Of_Salvation.value), "RestockQtyArmorOfSalvation", 10),
    ("Personal PCons", "Birthday Cupcake", int(ModelID.Birthday_Cupcake.value), "RestockQtyBirthdayCupcake", 10),
    ("Personal PCons", "Golden Egg", int(ModelID.Golden_Egg.value), "RestockQtyGoldenEgg", 10),
    ("Personal PCons", "Candy Corn", int(ModelID.Candy_Corn.value), "RestockQtyCandyCorn", 10),
    ("Personal PCons", "Candy Apple", int(ModelID.Candy_Apple.value), "RestockQtyCandyApple", 10),
    ("Personal PCons", "Pumpkin Pie", int(ModelID.Slice_Of_Pumpkin_Pie.value), "RestockQtyPumpkinPie", 10),
    ("Personal PCons", "Drake Kabob", int(ModelID.Drake_Kabob.value), "RestockQtyDrakeKabob", 10),
    ("Personal PCons", "Bowl of Skalefin Soup", int(ModelID.Bowl_Of_Skalefin_Soup.value), "RestockQtySkalefinSoup", 10),
    ("Personal PCons", "Pahnai Salad", int(ModelID.Pahnai_Salad.value), "RestockQtyPahnaiSalad", 10),
    ("Personal PCons", "War Supplies", int(ModelID.War_Supplies.value), "RestockQtyWarSupplies", 10),
    ("Morale", "Four-Leaf Clover", int(ModelID.Four_Leaf_Clover.value), "RestockQtyFourLeafClover", 10),
    ("Morale", "Honeycomb", int(ModelID.Honeycomb.value), "RestockQtyHoneycomb", 10),
    ("Summoning", "Legionnaire Summoning Crystal", int(ModelID.Legionnaire_Summoning_Crystal.value), "RestockQtyLegionnaireCrystal", 10),
    ("Summoning", "Tengu Summoning Stone", int(ModelID.Tengu_Summon.value), "RestockQtyTenguSummon", 10),
    ("Summoning", "Mysterious Summoning Stone", int(ModelID.Mysterious_Summon.value), "RestockQtyMysteriousSummon", 10),
)
DEFAULT_RESTOCK_DEFAULTS = {model_id: default for _group, _label, model_id, _key, default in DEFAULT_RESTOCK_ITEM_DEFINITIONS}
DEFAULT_RESTOCK_SETTING_KEYS = {model_id: key for _group, _label, model_id, key, _default in DEFAULT_RESTOCK_ITEM_DEFINITIONS}

def load_restock_quantities(settings, section: str) -> dict[int, int]:
    return {
        model_id: max(0, settings.get_int(section, setting_key, DEFAULT_RESTOCK_DEFAULTS[model_id]))
        for model_id, setting_key in DEFAULT_RESTOCK_SETTING_KEYS.items()
    }

def save_restock_quantities(settings, section: str, quantities: dict[int, int]) -> None:
    for model_id, setting_key in DEFAULT_RESTOCK_SETTING_KEYS.items():
        settings.set(section, setting_key, max(0, int(quantities.get(model_id, 0))))



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
