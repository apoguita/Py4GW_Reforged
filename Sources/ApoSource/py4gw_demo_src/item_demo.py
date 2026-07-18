"""
Item section — a subject-id inspector for one item, mirroring the player_demo template.

Shape (see SPEC_reengineer.md §1.2 and R1 §6):
  * ``build_item(item_id)`` calls the item getters (+ every nested namespace), CASTS each value via
    ``casts``, and returns a list of display Blocks. A ``PyItem`` handle, an ``ItemModifier``, an
    ``ItemTypeClass``/``Rarity`` or a ``DyeInfo`` struct NEVER reaches a renderer — each is
    dereferenced field-by-field / method-by-method here (R3 §5 traps).
  * ``draw_item_view()`` builds once, offers the per-section Dump-to-file button, then a subject-id
    input (+ convenience loaders) and a tab bar (Data + Actions). RequestName is the only mutator on
    the wrapper, exposed as an explicit trigger.

Data path: ``GLOBAL_CACHE.Item.*`` (the throttled/cached ``ItemCache``), aligned with the legacy demo
(``Widgets\\Coding\\Py4GW_DEMO.py``) exactly. The cache mirrors the base ``Item`` wrapper API — same
getters and the same sub-namespaces (``Rarity``/``Properties``/``Type``/``Usage``/``Customization`` +
``Customization.Modifiers``) — so this is a pure access-layer swap. Members used here that are NOT on
``ItemCache`` stay on the base ``Item`` wrapper (marked inline with ``# base wrapper: not on
GLOBAL_CACHE``): the top-level ``GetCompositeModelIDs``/``GetTrueModelFileID``/``IsArmorType``/
``IsWeapon``, ``Properties.GetRequirement``/``GetDamage``/``GetArmor``/``GetEnergy``, and the
``Customization`` upgrade getters (``HasUpgrades``/``HasInherentUpgrades``/``GetInherentUpgrades``/
``GetPrefixUpgrade``/``GetSuffixUpgrade``/``GetInscriptionUpgrade``). Hovered-item / first-item loaders
route through ``GLOBAL_CACHE.Inventory.*`` like legacy.

R2 coverage (PyItem b3, 55 rows) — every wrapper-exposed surface is wired by hand (no reflection):
  Common: GetName, IsNameReady, GetItemType->(id,name), GetModelID, GetModelFileID,
    GetCompositeModelIDs, GetTrueModelFileID, GetSlot, GetAgentID, GetAgentItemID, IsArmorType,
    IsWeapon (top-level predicates).
  Rarity: GetRarity->(id,name), IsWhite/IsBlue/IsPurple/IsGold/IsGreen.
  Properties: IsCustomized, GetValue, GetQuantity, IsEquipped, GetProfession, GetInteraction,
    GetRequirement->(Attribute,level), GetDamage->(min,max), GetArmor, GetEnergy.
  Type: IsWeapon, IsArmor, IsInventoryItem, IsStorageItem, IsMaterial, IsRareMaterial, IsZCoin,
    IsTome.
  Usage: IsUsable, GetUses, IsSalvageable, IsMaterialSalvageable, IsSalvageKit, IsLesserKit,
    IsExpertSalvageKit, IsPerfectSalvageKit, IsIDKit, IsIdentified.
  Customization: IsInscription, IsInscribable, IsPrefixUpgradable, IsSuffixUpgradable, GetItemFormula,
    IsStackable, IsSparkly, HasUpgrades, HasInherentUpgrades, GetUpgrades, GetPrefixUpgrade,
    GetSuffixUpgrade, GetInscriptionUpgrade, GetInherentUpgrades.
  Customization.Modifiers: GetModifierCount, GetModifiers -> per-modifier GetIdentifier / IsValid /
    GetArg / GetArg1 / GetArg2 (each dec|hex|bin).
  Customization dye: GetDyeColor, GetDyeInfo -> dye_tint + dye1..dye4 (each .ToInt()/.ToString()).
  Actions: RequestName (async mutator on the wrapper).
Skipped (out of this section's contract):
  * item_instance (internal ctor), GetItemIdFromModelID / GetItemByAgentID (model/agent-id lookups,
    used as convenience loaders in Actions, not subject-bound getters), GetDyeColor's DyeColor filter.
  * Trade namespace (IsOfferedInTrade/IsTradable) — folded into Type/Usage-adjacent bools below.
  * Filter.* (Dye/Weapon predicates) — composite helpers over the getters already covered.
  * HasUpgradeType / HasUpgrade / GetUpgrade — require a caller-supplied upgrade type, no subject-only
    rendering (documented, not wired).
  * PyItem-handle-only R2 methods NOT surfaced by the wrapper: GetContext, GetInfoString, GetNameEnc,
    GetCompleteNameEnc, GetSingleItemName, IsItemValid, ItemModifier.GetModBits, and the module-level
    free functions (use_item_by_id, salvage_start, identify_item, gold/xunlai, …) — those belong to
    Inventory/Merchant sections, not Item.
"""

import PyImGui

from Py4GWCoreLib import GLOBAL_CACHE
from Py4GWCoreLib.Item import Item

from . import casts
from . import diagnostics
from . import ui

_SECTION = "Item"


class _State:
    item_id: int = 0


state = _State()


# ---------------------------------------------------------------------------
# small local casts (explicit deref — never repr a handle/struct)
# ---------------------------------------------------------------------------
def _attr_req(pair) -> str:
    """GetRequirement -> (Attribute enum, level). Render [id] - Name @ req level."""
    try:
        attr, level = pair
        name = getattr(attr, "name", str(attr))
        return f"[{int(attr)}] - {name} @ req {level}"
    except (TypeError, ValueError):
        return str(pair)


def _pair(pair, sep=" - ") -> str:
    """(a, b) -> 'a - b' (e.g. min/max damage)."""
    try:
        a, b = pair
        return f"{a}{sep}{b}"
    except (TypeError, ValueError):
        return str(pair)


def _upgrade_str(upgrade) -> str:
    """Dereference an Upgrade object into a readable summary (never repr the object)."""
    if upgrade is None:
        return "None"
    for attr in ("display_summary", "name_plain", "name"):
        val = casts.safe(getattr, upgrade, attr, default=None)
        if val:
            return str(val)
    return f"<{type(upgrade).__name__}>"


# ---------------------------------------------------------------------------
# build_* — call getters, cast, return blocks (shared by render AND dump)
# ---------------------------------------------------------------------------
def _common_block(item_id):
    mfid = casts.safe(GLOBAL_CACHE.Item.GetModelFileID, item_id, default=0) or 0
    composite = casts.safe(Item.GetCompositeModelIDs, mfid, default=[]) or []  # base wrapper: not on GLOBAL_CACHE
    rows = [
        ("Item ID", item_id),
        ("Hovered Item ID", int(casts.safe(GLOBAL_CACHE.Inventory.GetHoveredItemID, default=0) or 0)),
        ("Name Ready", casts.yesno(casts.safe(GLOBAL_CACHE.Item.IsNameReady, item_id))),
        ("Name", casts.safe(GLOBAL_CACHE.Item.GetName, item_id)),
        ("Item Type", casts.id_name_tuple(casts.safe(GLOBAL_CACHE.Item.GetItemType, item_id, default=(0, "?")))),
        ("Model ID", casts.safe(GLOBAL_CACHE.Item.GetModelID, item_id)),
        ("Model File ID", mfid),
        ("True Model File ID", casts.safe(Item.GetTrueModelFileID, mfid)),  # base wrapper: not on GLOBAL_CACHE
        ("Composite Model IDs", f"[{len(composite)}] {list(composite)}"),
        ("Slot", casts.safe(GLOBAL_CACHE.Item.GetSlot, item_id)),
        ("Agent ID", casts.safe(GLOBAL_CACHE.Item.GetAgentID, item_id)),
        ("Agent Item ID", casts.safe(GLOBAL_CACHE.Item.GetAgentItemID, item_id)),
        ("Is Armor Type (top)", casts.yesno(casts.safe(Item.IsArmorType, item_id))),  # base wrapper: not on GLOBAL_CACHE
        ("Is Weapon (top)", casts.yesno(casts.safe(Item.IsWeapon, item_id))),  # base wrapper: not on GLOBAL_CACHE
    ]
    return ui.kv_block("Common", rows)


def _rarity_block(item_id):
    kv = ui.kv_block("Rarity", [
        ("Rarity", casts.id_name_tuple(casts.safe(GLOBAL_CACHE.Item.Rarity.GetRarity, item_id, default=(0, "?")))),
    ])
    bools = ui.bool_block("Rarity Flags", [
        ("White", bool(casts.safe(GLOBAL_CACHE.Item.Rarity.IsWhite, item_id))),
        ("Blue", bool(casts.safe(GLOBAL_CACHE.Item.Rarity.IsBlue, item_id))),
        ("Purple", bool(casts.safe(GLOBAL_CACHE.Item.Rarity.IsPurple, item_id))),
        ("Gold", bool(casts.safe(GLOBAL_CACHE.Item.Rarity.IsGold, item_id))),
        ("Green", bool(casts.safe(GLOBAL_CACHE.Item.Rarity.IsGreen, item_id))),
    ])
    return [kv, bools]


def _properties_block(item_id):
    rows = [
        ("Is Customized", casts.yesno(casts.safe(GLOBAL_CACHE.Item.Properties.IsCustomized, item_id))),
        ("Value", casts.safe(GLOBAL_CACHE.Item.Properties.GetValue, item_id)),
        ("Quantity", casts.safe(GLOBAL_CACHE.Item.Properties.GetQuantity, item_id)),
        ("Is Equipped", casts.yesno(casts.safe(GLOBAL_CACHE.Item.Properties.IsEquipped, item_id))),
        ("Profession", casts.safe(GLOBAL_CACHE.Item.Properties.GetProfession, item_id)),
        ("Requirement", _attr_req(casts.safe(Item.Properties.GetRequirement, item_id, default=None))),  # base wrapper: not on GLOBAL_CACHE
        ("Damage (min - max)", _pair(casts.safe(Item.Properties.GetDamage, item_id, default=(0, 0)))),  # base wrapper: not on GLOBAL_CACHE
        ("Armor", casts.safe(Item.Properties.GetArmor, item_id)),  # base wrapper: not on GLOBAL_CACHE
        ("Energy", casts.safe(Item.Properties.GetEnergy, item_id)),  # base wrapper: not on GLOBAL_CACHE
    ]
    return ui.kv_block("Properties", rows)


def _bitfields_block(item_id):
    """Interaction + item formula rendered dec / hex / bin (R1 §6, item bitfields)."""
    interaction = casts.safe(GLOBAL_CACHE.Item.Properties.GetInteraction, item_id, default=0)
    formula = casts.safe(GLOBAL_CACHE.Item.Properties.GetItemFormula, item_id, default=0)
    rows = [
        ("Interaction", *casts.dec_hex_bin(interaction)),
        ("Item Formula", *casts.dec_hex_bin(formula)),
    ]
    return ui.multi_block("Bitfields (dec / hex / bin)", ["Field", "Dec", "Hex", "Bin"], rows)


def _type_block(item_id):
    return ui.bool_block("Type", [
        ("Weapon", bool(casts.safe(GLOBAL_CACHE.Item.Type.IsWeapon, item_id))),
        ("Armor", bool(casts.safe(GLOBAL_CACHE.Item.Type.IsArmor, item_id))),
        ("Inventory Item", bool(casts.safe(GLOBAL_CACHE.Item.Type.IsInventoryItem, item_id))),
        ("Storage Item", bool(casts.safe(GLOBAL_CACHE.Item.Type.IsStorageItem, item_id))),
        ("Material", bool(casts.safe(GLOBAL_CACHE.Item.Type.IsMaterial, item_id))),
        ("Rare Material", bool(casts.safe(GLOBAL_CACHE.Item.Type.IsRareMaterial, item_id))),
        ("ZCoin", bool(casts.safe(GLOBAL_CACHE.Item.Type.IsZCoin, item_id))),
        ("Tome", bool(casts.safe(GLOBAL_CACHE.Item.Type.IsTome, item_id))),
    ])


def _usage_block(item_id):
    kv = ui.kv_block("Usage", [
        ("Uses", casts.safe(GLOBAL_CACHE.Item.Usage.GetUses, item_id)),
    ])
    bools = ui.bool_block("Usage Flags", [
        ("Usable", bool(casts.safe(GLOBAL_CACHE.Item.Usage.IsUsable, item_id))),
        ("Salvageable", bool(casts.safe(GLOBAL_CACHE.Item.Usage.IsSalvageable, item_id))),
        ("Material Salvageable", bool(casts.safe(GLOBAL_CACHE.Item.Usage.IsMaterialSalvageable, item_id))),
        ("Salvage Kit", bool(casts.safe(GLOBAL_CACHE.Item.Usage.IsSalvageKit, item_id))),
        ("Lesser Kit", bool(casts.safe(GLOBAL_CACHE.Item.Usage.IsLesserKit, item_id))),
        ("Expert Salvage Kit", bool(casts.safe(GLOBAL_CACHE.Item.Usage.IsExpertSalvageKit, item_id))),
        ("Perfect Salvage Kit", bool(casts.safe(GLOBAL_CACHE.Item.Usage.IsPerfectSalvageKit, item_id))),
        ("ID Kit", bool(casts.safe(GLOBAL_CACHE.Item.Usage.IsIDKit, item_id))),
        ("Identified", bool(casts.safe(GLOBAL_CACHE.Item.Usage.IsIdentified, item_id))),
    ])
    return [kv, bools]


def _customization_block(item_id):
    bools = ui.bool_block("Customization Flags", [
        ("Inscription", bool(casts.safe(GLOBAL_CACHE.Item.Properties.IsInscription, item_id))),
        ("Inscribable", bool(casts.safe(GLOBAL_CACHE.Item.Properties.IsInscribable, item_id))),
        ("Prefix Upgradable", bool(casts.safe(GLOBAL_CACHE.Item.Properties.IsPrefixUpgradable, item_id))),
        ("Suffix Upgradable", bool(casts.safe(GLOBAL_CACHE.Item.Properties.IsSuffixUpgradable, item_id))),
        ("Stackable", bool(casts.safe(GLOBAL_CACHE.Item.Properties.IsStackable, item_id))),
        ("Sparkly", bool(casts.safe(GLOBAL_CACHE.Item.Properties.IsSparkly, item_id))),
        ("Has Upgrades", bool(casts.safe(Item.Mods.GetUpgrades, item_id))),
        ("Has Inherent Upgrades", bool(casts.safe(Item.Mods.HasUpgradeInSlot, item_id, Item.Mods.Slot.Inherent))),
    ])
    _Slot = Item.Mods.Slot
    kv = ui.kv_block("Upgrades", [
        ("Prefix", casts.safe(Item.Mods.GetUpgradeInSlot, item_id, _Slot.Prefix) or "None"),
        ("Suffix", casts.safe(Item.Mods.GetUpgradeInSlot, item_id, _Slot.Suffix) or "None"),
        ("Inscription", casts.safe(Item.Mods.GetUpgradeInSlot, item_id, _Slot.Inscription) or "None"),
        ("Inherent", casts.safe(Item.Mods.GetUpgradeInSlot, item_id, _Slot.Inherent) or "None"),
    ])
    return [bools, kv]


def _modifiers_block(item_id):
    count = casts.safe(GLOBAL_CACHE.Item.Mods.GetModifierCount, item_id, default=0)
    mods = casts.safe(GLOBAL_CACHE.Item.Mods.GetModifiers, item_id, default=[]) or []
    headers = ["#", "Identifier", "Valid", "Arg", "Arg1", "Arg2"]
    rows = []
    for idx, mod in enumerate(mods):
        rows.append((
            idx,
            casts.flags(casts.safe(mod.GetIdentifier)),
            casts.yesno(casts.safe(mod.IsValid)),
            casts.flags(casts.safe(mod.GetArg)),
            casts.flags(casts.safe(mod.GetArg1)),
            casts.flags(casts.safe(mod.GetArg2)),
        ))
    return ui.multi_block(f"Modifiers (count={count})", headers, rows)


def _dye_block(item_id):
    dye_info = casts.safe(GLOBAL_CACHE.Item.Dye.GetInfo, item_id, default=None)
    tint = casts.safe(getattr, dye_info, "dye_tint", default="<n/a>") if dye_info is not None else "<n/a>"
    kv = ui.kv_block("Dye", [
        ("Dye Color (first non-zero Arg1)", casts.safe(GLOBAL_CACHE.Item.GetDyeColor, item_id)),
        ("Dye Tint", tint),
    ])
    headers = ["Dye Slot", "ToInt", "ToString"]
    rows = []
    if dye_info is not None:
        for i in range(1, 5):
            dye = casts.safe(getattr, dye_info, f"dye{i}", default=None)
            if dye is None:
                rows.append((f"dye{i}", "<n/a>", "<n/a>"))
                continue
            rows.append((f"dye{i}", casts.safe(dye.ToInt), casts.safe(dye.ToString)))
    return [kv, ui.multi_block("Dye Colors", headers, rows)]


def build_item(item_id):
    blocks = [_common_block(item_id)]
    blocks.extend(_rarity_block(item_id))
    blocks.append(_properties_block(item_id))
    blocks.append(_bitfields_block(item_id))
    blocks.append(_type_block(item_id))
    blocks.extend(_usage_block(item_id))
    blocks.extend(_customization_block(item_id))
    blocks.append(_modifiers_block(item_id))
    blocks.extend(_dye_block(item_id))
    return blocks


# ---------------------------------------------------------------------------
# Subject id + convenience loaders
# ---------------------------------------------------------------------------
def _draw_subject_selector():
    state.item_id = PyImGui.input_int("Item ID", state.item_id)
    if PyImGui.button("Load Hovered"):
        state.item_id = int(casts.safe(GLOBAL_CACHE.Inventory.GetHoveredItemID, default=0) or 0)
    PyImGui.same_line(0, 8)
    if PyImGui.button("First Unidentified"):
        state.item_id = int(casts.safe(GLOBAL_CACHE.Inventory.GetFirstUnidentifiedItem, default=0) or 0)
    PyImGui.same_line(0, 8)
    if PyImGui.button("First Salvageable"):
        state.item_id = int(casts.safe(GLOBAL_CACHE.Inventory.GetFirstSalvageableItem, default=0) or 0)
    ui.text_muted(f"Subject item id: {state.item_id}")


# ---------------------------------------------------------------------------
# Actions — explicit trigger buttons, fired only on click
# ---------------------------------------------------------------------------
def _draw_actions():
    ui.section_header("Name (async request/poll)")
    ui.text_muted("RequestName spawns an async fetch; poll 'Name Ready' on the Data tab, then read Name.")
    ui.action_button("Request Name", GLOBAL_CACHE.Item.RequestName, state.item_id, key="req_name")
    PyImGui.same_line(0, 8)
    ready = casts.yesno(casts.safe(GLOBAL_CACHE.Item.IsNameReady, state.item_id))
    PyImGui.text_colored(f"Name Ready: {ready}", ui.MUTED_COLOR)


# ---------------------------------------------------------------------------
# draw_*_view — uniform section entry point
# ---------------------------------------------------------------------------
def draw_item_view() -> None:
    blocks = build_item(state.item_id)
    diagnostics.dump_button(_SECTION, blocks)
    PyImGui.separator()
    _draw_subject_selector()
    PyImGui.separator()
    if PyImGui.begin_tab_bar("ItemTabs"):
        if PyImGui.begin_tab_item("Data"):
            ui.draw_blocks(_SECTION, blocks)
            PyImGui.end_tab_item()
        if PyImGui.begin_tab_item("Actions"):
            _draw_actions()
            PyImGui.end_tab_item()
        PyImGui.end_tab_bar()
