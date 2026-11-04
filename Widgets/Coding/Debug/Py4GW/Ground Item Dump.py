"""Ground Item Dump — diagnostic widget.

Target an item on the ground, dump it, pick it up, then capture both the saved item object
and the player's actual held-slot identity. The evidence lands in one log file so these
different identity surfaces can be compared without treating one as a substitute for another.

  1. Target an item on the floor.
  2. Press "1. Dump Targeted Ground Item".
  3. Pick it up.
  4. Press "2. Dump Saved Item + Held Slot".

Every accessor is called defensively: if one throws or returns nothing for a ground item,
that fact is recorded in the dump rather than aborting it.

Log file: diagnostics/ground_item_dump.log (appended; "Clear Log" empties it).
"""

import os
import time

import PyImGui
import PyItem
import PySystem

from Py4GWCoreLib import Agent
from Py4GWCoreLib import Color
from Py4GWCoreLib import ImGui
from Py4GWCoreLib import Item
from Py4GWCoreLib import Player
from Py4GWCoreLib import Routines
from Py4GWCoreLib import Utils
from Py4GWCoreLib.py4gwcorelib_src.Settings import Settings

MODULE_NAME = "Ground Item Dump"
WIDGET_KEY = 'Widgets/Coding/Debug/Py4GW/Ground Item Dump'

INI_KEY = ""
INI_PATH = "Widgets/GroundItemDump"
INI_FILENAME = "GroundItemDump.ini"

LOG_RELATIVE_PATH = os.path.join("diagnostics", "ground_item_dump.log")

# --- state -------------------------------------------------------------------
# The item id captured by step 1, so step 2 needs no typing.
pending_item_id = 0
pending_ground_model_id = 0
pending_ground_model_error = ""
pending_label = ""
status_line = ""
last_held_slot_summary = None
initialized = False


# --- helpers -----------------------------------------------------------------
def _log_path() -> str:
    return os.path.join(PySystem.Console.get_projects_path(), LOG_RELATIVE_PATH)


def _write(text: str) -> None:
    """Append a block to the log file, creating the folder on first use."""
    path = _log_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(text)
    except Exception as exc:
        global status_line
        status_line = f"Failed writing log: {exc}"


def _safe(label: str, getter) -> str:
    """Call `getter` and render one 'label: value' line, recording failures inline.

    A ground item is expected to have missing/blank fields; the point of the dump is to see
    WHICH ones, so an exception or a None is data, not an error.
    """
    try:
        value = getter()
    except Exception as exc:
        return f"  {label:<28} !! {type(exc).__name__}: {exc}\n"
    return f"  {label:<28} {_render(value)}\n"


def _try_value(getter):
    """Return one diagnostic observation without allowing an accessor failure to escape."""
    try:
        return getter(), ""
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def _evidence_line(label: str, value, error: str = "") -> str:
    if error:
        return f"  {label:<36} !! {error}\n"
    return f"  {label:<36} {_render(value)}\n"


def _render(value) -> str:
    if value is None:
        return "<None>"
    if isinstance(value, str):
        return f"'{value}'  (len={len(value)})" if value else "'' (EMPTY)"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return f"{value}  (0x{value:X})" if value > 9 else str(value)
    if isinstance(value, (list, tuple)):
        if not value:
            return "[] (EMPTY)"
        if all(isinstance(v, int) for v in value):
            return f"{list(value)}  hex=[{', '.join(f'0x{v:X}' for v in value)}]"
        return str([str(v) for v in value])
    return str(value)


def _decode_interaction(flags: int) -> str:
    """Name the interaction bits the native Item struct derives its properties from."""
    known = [
        (0x00000001, "identified"),
        (0x00000010, "GREEN"),
        (0x00000100, "not_tradable"),
        (0x00002000, "not_sparkly"),
        (0x00004000, "prefix_used"),
        (0x00008000, "suffix_used"),
        (0x00020000, "GOLD"),
        (0x00080000, "stackable"),
        (0x00400000, "PURPLE"),
        (0x01000000, "usable"),
        (0x08000000, "inscribable"),
    ]
    hits = [name for bit, name in known if flags & bit]
    return " | ".join(hits) if hits else "<no known bits>"


def _modifier_lines(item) -> str:
    """Raw modifier words — the single most important question for ground items."""
    try:
        mods = item.modifiers
    except Exception as exc:
        return f"  modifiers                    !! {type(exc).__name__}: {exc}\n"
    if not mods:
        return "  modifiers                    [] (EMPTY -- no mod data on this item)\n"
    out = f"  modifiers                    count={len(mods)}\n"
    for index, mod in enumerate(mods):
        try:
            out += (
                f"    [{index}] id=0x{mod.GetIdentifier():04X} "
                f"arg1={mod.GetArg1()} arg2={mod.GetArg2()} arg={mod.GetArg()} "
                f"valid={mod.IsValid()} bits={mod.GetModBits()}\n"
            )
        except Exception as exc:
            out += f"    [{index}] !! {type(exc).__name__}: {exc}\n"
    return out


def _dump_pyitem(item_id: int) -> str:
    """Every PyItem field, exactly as the bindings expose it."""
    out = ""
    try:
        item = PyItem.PyItem(item_id)
    except Exception as exc:
        return f"  PyItem({item_id}) construction FAILED: {type(exc).__name__}: {exc}\n"

    out += "-- identity --\n"
    out += _safe("item_id", lambda: item.item_id)
    out += _safe("agent_id", lambda: item.agent_id)
    out += _safe("agent_item_id", lambda: item.agent_item_id)
    out += _safe("model_id", lambda: item.model_id)
    out += _safe("model_file_id", lambda: item.model_file_id)
    out += _safe("item_type.ToInt()", lambda: item.item_type.ToInt())
    out += _safe("item_type.GetName()", lambda: item.item_type.GetName())

    out += "-- name machinery (rarity=Blue depends on the composed name) --\n"
    out += _safe("name", lambda: item.name)
    out += _safe("IsItemNameReady()", lambda: item.IsItemNameReady())
    out += _safe("GetName()", lambda: item.GetName())
    out += _safe("GetNameEnc()", lambda: item.GetNameEnc())
    out += _safe("GetCompleteNameEnc()", lambda: item.GetCompleteNameEnc())
    out += _safe("GetSingleItemName()", lambda: item.GetSingleItemName())
    out += _safe("GetInfoString()", lambda: item.GetInfoString())

    out += "-- rarity --\n"
    out += _safe("rarity", lambda: f"{item.rarity} (value={item.rarity.value}, name={item.rarity.name})")
    out += _safe("is_rarity_blue", lambda: item.is_rarity_blue)
    out += _safe("is_rarity_purple", lambda: item.is_rarity_purple)
    out += _safe("is_rarity_gold", lambda: item.is_rarity_gold)
    out += _safe("is_rarity_green", lambda: item.is_rarity_green)

    out += "-- interaction flags --\n"
    out += _safe("interaction", lambda: item.interaction)
    out += _safe("interaction decoded", lambda: _decode_interaction(item.interaction))

    out += "-- dye --\n"
    out += _safe("dye_info.ToString()", lambda: item.dye_info.ToString())
    out += _safe("dye_info.dye_tint", lambda: item.dye_info.dye_tint)
    out += _safe("dye_info.dye1", lambda: f"{item.dye_info.dye1.ToInt()} ({item.dye_info.dye1.ToString()})")
    out += _safe("dye_info.dye2", lambda: f"{item.dye_info.dye2.ToInt()} ({item.dye_info.dye2.ToString()})")
    out += _safe("dye_info.dye3", lambda: f"{item.dye_info.dye3.ToInt()} ({item.dye_info.dye3.ToString()})")
    out += _safe("dye_info.dye4", lambda: f"{item.dye_info.dye4.ToInt()} ({item.dye_info.dye4.ToString()})")

    out += "-- mods --\n"
    out += _modifier_lines(item)

    out += "-- quantities / value --\n"
    out += _safe("value", lambda: item.value)
    out += _safe("quantity", lambda: item.quantity)
    out += _safe("uses", lambda: item.uses)
    out += _safe("item_formula", lambda: item.item_formula)
    out += _safe("profession", lambda: item.profession)
    out += _safe("slot", lambda: item.slot)
    out += _safe("equipped", lambda: item.equipped)
    out += _safe("is_material_salvageable", lambda: item.is_material_salvageable)

    out += "-- booleans --\n"
    for field in (
        "is_customized", "is_stackable", "is_inscribable", "is_material", "is_zcoin",
        "is_id_kit", "is_salvage_kit", "is_tome", "is_lesser_kit", "is_expert_salvage_kit",
        "is_perfect_salvage_kit", "is_weapon", "is_armor", "is_salvageable",
        "is_inventory_item", "is_storage_item", "is_rare_material", "is_offered_in_trade",
        "is_sparkly", "is_identified", "is_prefix_upgradable", "is_suffix_upgradable",
        "is_usable", "is_tradable", "is_inscription",
    ):
        out += _safe(field, lambda f=field: getattr(item, f))

    return out


def _dump_corelib(item_id: int) -> str:
    """The Py4GWCoreLib wrappers a loot rule would actually call."""
    out = "-- Py4GWCoreLib.Item wrappers --\n"
    out += _safe("Item.GetModelID", lambda: Item.GetModelID(item_id))
    out += _safe("Item.GetItemType", lambda: Item.GetItemType(item_id))
    out += _safe("Item.Rarity.GetRarity", lambda: Item.Rarity.GetRarity(item_id))
    out += _safe("Item.Rarity.IsWhite", lambda: Item.Rarity.IsWhite(item_id))
    out += _safe("Item.Rarity.IsBlue", lambda: Item.Rarity.IsBlue(item_id))
    out += _safe("Item.Rarity.IsPurple", lambda: Item.Rarity.IsPurple(item_id))
    out += _safe("Item.Rarity.IsGold", lambda: Item.Rarity.IsGold(item_id))
    out += _safe("Item.Rarity.IsGreen", lambda: Item.Rarity.IsGreen(item_id))
    out += _safe("Item.Dye.GetColor", lambda: Item.Dye.GetColor(item_id))
    out += _safe("Item.Dye.GetChannels", lambda: Item.Dye.GetChannels(item_id))
    out += _safe("Item.GetDyeColor", lambda: Item.GetDyeColor(item_id))
    out += _safe("Item.Properties.GetValue", lambda: Item.Properties.GetValue(item_id))
    out += _safe("Item.Properties.GetQuantity", lambda: Item.Properties.GetQuantity(item_id))
    out += _safe("Item.Properties.GetRequirement", lambda: Item.Properties.GetRequirement(item_id))
    out += _safe("Item.Properties.GetDamage", lambda: Item.Properties.GetDamage(item_id))
    out += _safe("Item.Properties.GetArmor", lambda: Item.Properties.GetArmor(item_id))
    out += _safe("Item.Properties.GetEnergy", lambda: Item.Properties.GetEnergy(item_id))
    out += _safe("Item.Properties.IsMaxDamage", lambda: Item.Properties.IsMaxDamage(item_id))
    out += _safe("Item.Usage.IsIdentified", lambda: Item.Usage.IsIdentified(item_id))
    out += _safe("Item.Usage.IsSalvageable", lambda: Item.Usage.IsSalvageable(item_id))

    out += "-- Item.Mods (decoded mod layer) --\n"
    out += _safe("Item.Mods.GetMods", lambda: [str(m) for m in Item.Mods.GetMods(item_id)])
    out += _safe("Item.Mods.GetUpgrades", lambda: [str(u) for u in Item.Mods.GetUpgrades(item_id)])
    out += _safe("Item.Mods.GetDescriptions", lambda: Item.Mods.GetDescriptions(item_id))
    out += _safe("Item.Mods.GetRawDump", lambda: [str(d) for d in Item.Mods.GetRawDump(item_id)])
    return out


def _build_held_slot_evidence(
    captured_item_id: int,
    captured_ground_model_id: int,
    captured_ground_model_error: str = "",
):
    """Capture log text and a compact UI result from the live player held slot."""
    out = (
        f"\n{'-' * 78}\n"
        "[HELD_SLOT] live player possession evidence (not saved-item evidence)\n"
        f"{'-' * 78}\n"
    )

    player_id, player_error = _try_value(Player.GetAgentID)
    out += _evidence_line("player_id", player_id, player_error)

    if player_error or player_id is None:
        holding, holding_error = None, "unavailable because player_id lookup failed"
        weapon_extra, weapon_error = None, "unavailable because player_id lookup failed"
    else:
        holding, holding_error = _try_value(lambda: Agent.IsHoldingItem(player_id))
        weapon_extra, weapon_error = _try_value(lambda: Agent.GetWeaponExtraData(player_id))

    out += _evidence_line("Agent.IsHoldingItem(player_id)", holding, holding_error)
    out += _evidence_line("Agent.GetWeaponExtraData raw", weapon_extra, weapon_error)

    held_item_id = 0
    held_item_id_error = ""
    if weapon_error or weapon_extra is None:
        held_item_id_error = "unavailable because weapon extra data lookup failed"
    else:
        try:
            held_item_id = int(weapon_extra[0] or 0)
        except Exception as exc:
            held_item_id_error = f"{type(exc).__name__}: tuple index 0 unavailable: {exc}"
    out += _evidence_line("held item id (tuple index 0)", held_item_id, held_item_id_error)
    out += _evidence_line("captured ground item id", captured_item_id)
    out += _evidence_line(
        "held id matches captured item id",
        held_item_id == captured_item_id if not held_item_id_error and held_item_id > 0 else "UNAVAILABLE",
    )
    out += _evidence_line(
        "captured ground model id",
        captured_ground_model_id if not captured_ground_model_error else None,
        captured_ground_model_error,
    )

    held_models = []
    if held_item_id > 0 and not held_item_id_error:
        held_item, held_item_error = _try_value(lambda: PyItem.PyItem(held_item_id))
        out += _evidence_line("PyItem.PyItem(held_item_id)", repr(held_item), held_item_error)
        if held_item_error or held_item is None:
            pyitem_model, pyitem_model_error = None, "unavailable because PyItem construction failed"
            pyitem_type_int, pyitem_type_int_error = None, "unavailable because PyItem construction failed"
            pyitem_type_name, pyitem_type_name_error = None, "unavailable because PyItem construction failed"
            pyitem_name, pyitem_name_error = None, "unavailable because PyItem construction failed"
            pyitem_get_name, pyitem_get_name_error = None, "unavailable because PyItem construction failed"
            pyitem_single_name, pyitem_single_name_error = None, "unavailable because PyItem construction failed"
        else:
            pyitem_model, pyitem_model_error = _try_value(lambda: held_item.model_id)
            pyitem_type_int, pyitem_type_int_error = _try_value(lambda: held_item.item_type.ToInt())
            pyitem_type_name, pyitem_type_name_error = _try_value(lambda: held_item.item_type.GetName())
            pyitem_name, pyitem_name_error = _try_value(lambda: held_item.name)
            pyitem_get_name, pyitem_get_name_error = _try_value(held_item.GetName)
            pyitem_single_name, pyitem_single_name_error = _try_value(held_item.GetSingleItemName)

        out += _evidence_line("PyItem.model_id", pyitem_model, pyitem_model_error)
        out += _evidence_line("PyItem.item_type.ToInt()", pyitem_type_int, pyitem_type_int_error)
        out += _evidence_line("PyItem.item_type.GetName()", pyitem_type_name, pyitem_type_name_error)
        out += _evidence_line("PyItem.name", pyitem_name, pyitem_name_error)
        out += _evidence_line("PyItem.GetName()", pyitem_get_name, pyitem_get_name_error)
        out += _evidence_line("PyItem.GetSingleItemName()", pyitem_single_name, pyitem_single_name_error)

        core_model, core_model_error = _try_value(lambda: Item.GetModelID(held_item_id))
        core_type, core_type_error = _try_value(lambda: Item.GetItemType(held_item_id))
        core_name, core_name_error = _try_value(lambda: Item.GetName(held_item_id))
        out += _evidence_line("Item.GetModelID", core_model, core_model_error)
        out += _evidence_line("Item.GetItemType", core_type, core_type_error)
        out += _evidence_line("Item.GetName", core_name, core_name_error)

        for value, error in ((pyitem_model, pyitem_model_error), (core_model, core_model_error)):
            if not error:
                try:
                    model_id = int(value or 0)
                except Exception:
                    model_id = 0
                if model_id > 0:
                    held_models.append(model_id)
    else:
        out += "  held item detail fields              <SKIPPED: no positive held item id>\n"

    unique_held_models = sorted(set(held_models))
    exact_model_available = len(unique_held_models) == 1
    exact_held_model = unique_held_models[0] if exact_model_available else 0
    if exact_model_available and captured_ground_model_id > 0 and not captured_ground_model_error:
        model_match = exact_held_model == captured_ground_model_id
        match_text = "YES" if model_match else "NO"
    else:
        match_text = "UNAVAILABLE"

    if len(unique_held_models) > 1:
        proof_reason = f"NO (held model APIs disagree: {unique_held_models})"
    elif exact_model_available:
        proof_reason = f"YES (exact held model {exact_held_model})"
    elif held_item_id <= 0 or held_item_id_error:
        proof_reason = "NO (positive held-slot item ID unavailable)"
    else:
        proof_reason = "NO (held-slot model unavailable)"

    out += "-- explicit conclusion --\n"
    out += f"  exact held-model proof available: {proof_reason}\n"
    out += f"  held model matches captured ground model: {match_text}\n"
    summary = {
        "player_id": player_id if not player_error else None,
        "is_holding": holding if not holding_error else None,
        "held_item_id": held_item_id if held_item_id > 0 and not held_item_id_error else None,
        "captured_item_id": captured_item_id,
        "item_id_match": (
            held_item_id == captured_item_id
            if held_item_id > 0 and not held_item_id_error
            else None
        ),
        "held_model_id": exact_held_model if exact_model_available else None,
        "captured_ground_model_id": (
            captured_ground_model_id
            if captured_ground_model_id > 0 and not captured_ground_model_error
            else None
        ),
        "exact_model_available": exact_model_available,
        "model_match": match_text,
        "proof_reason": proof_reason,
    }
    return out, summary


def _dump_held_slot(
    captured_item_id: int,
    captured_ground_model_id: int,
    captured_ground_model_error: str = "",
) -> str:
    """Return the full held-slot log block for focused diagnostics and tests."""
    text, _summary = _build_held_slot_evidence(
        captured_item_id,
        captured_ground_model_id,
        captured_ground_model_error,
    )
    return text


def _format_held_slot_summary(summary) -> list[str]:
    """Render the decisive held-slot observations directly in the widget."""
    if not summary:
        return []

    def shown(value) -> str:
        return "UNAVAILABLE" if value is None else str(value)

    if summary["item_id_match"] is None:
        item_match = "UNAVAILABLE"
    else:
        item_match = "YES" if summary["item_id_match"] else "NO"
    proof = "YES" if summary["exact_model_available"] else "NO"
    return [
        "Held-slot result",
        f"Player: {shown(summary['player_id'])} | IsHoldingItem: {shown(summary['is_holding'])}",
        (
            f"Held item ID: {shown(summary['held_item_id'])} | "
            f"captured item ID: {shown(summary['captured_item_id'])} | match: {item_match}"
        ),
        (
            f"Held model: {shown(summary['held_model_id'])} | "
            f"ground model: {shown(summary['captured_ground_model_id'])} | "
            f"match: {summary['model_match']}"
        ),
        f"Exact held-model proof: {proof}",
    ]


def _dump_agent(agent_id: int) -> str:
    """The item-agent side: what the ground object itself carries."""
    out = "-- AgentItem (the object on the floor) --\n"
    out += _safe("Agent.IsValid", lambda: Agent.IsValid(agent_id))
    out += _safe("Agent.GetItemAgentOwnerID", lambda: Agent.GetItemAgentOwnerID(agent_id))
    out += _safe("Agent.GetItemAgentItemID", lambda: Agent.GetItemAgentItemID(agent_id))
    out += _safe("Agent.GetItemAgentExtraType", lambda: Agent.GetItemAgentExtraType(agent_id))
    out += _safe("Agent.GetItemAgenth00CC", lambda: Agent.GetItemAgenth00CC(agent_id))
    out += _safe("Agent.GetXY", lambda: Agent.GetXY(agent_id))
    out += _safe("distance to player", lambda: round(Utils.Distance(Player.GetXY(), Agent.GetXY(agent_id)), 1))

    item_agent = None
    try:
        item_agent = Agent.GetItemAgentByID(agent_id)
    except Exception as exc:
        out += f"  GetItemAgentByID             !! {type(exc).__name__}: {exc}\n"
    out += _safe("raw AgentItem repr", lambda: repr(item_agent))
    return out


def dump_by_agent(agent_id: int, tag: str = "GROUND") -> str:
    """Full dump for a ground item, addressed by its AGENT id."""
    header = (
        f"\n{'=' * 78}\n"
        f"[{tag}] agent_id={agent_id}   t={time.strftime('%Y-%m-%d %H:%M:%S')}   "
        f"tick={PySystem.get_tick_count64()}\n"
        f"{'=' * 78}\n"
    )
    body = _dump_agent(agent_id)
    try:
        item_id = Agent.GetItemAgentItemID(agent_id)
    except Exception:
        item_id = 0

    if not item_id:
        body += "\n!! No item_id on this agent — it is probably not an item agent.\n"
    else:
        body += f"\n-- resolved item_id={item_id} --\n"
        body += _dump_pyitem(item_id)
        body += _dump_corelib(item_id)

    text = header + body
    _write(text)
    return text


def dump_by_item(item_id: int, tag: str = "SAVED_ITEM_OBJECT") -> str:
    """Dump the previously captured ITEM id without claiming that it is the held slot."""
    header = (
        f"\n{'=' * 78}\n"
        f"[{tag}] item_id={item_id}   t={time.strftime('%Y-%m-%d %H:%M:%S')}   "
        f"tick={PySystem.get_tick_count64()}\n"
        f"{'=' * 78}\n"
    )
    body = _dump_pyitem(item_id) + _dump_corelib(item_id)
    text = header + body
    _write(text)
    return text


def dump_after_pickup(
    captured_item_id: int,
    captured_ground_model_id: int,
    captured_ground_model_error: str = "",
) -> str:
    """Append saved-item evidence followed by independent live held-slot evidence."""
    global last_held_slot_summary
    saved_item_text = dump_by_item(captured_item_id)
    held_slot_text, last_held_slot_summary = _build_held_slot_evidence(
        captured_item_id,
        captured_ground_model_id,
        captured_ground_model_error,
    )
    _write(held_slot_text)
    return saved_item_text + held_slot_text


# --- UI ----------------------------------------------------------------------
def draw_widget():
    global pending_item_id, pending_ground_model_id, pending_ground_model_error, pending_label, status_line
    global last_held_slot_summary

    if ImGui.Begin(INI_KEY, MODULE_NAME, flags=PyImGui.WindowFlags.AlwaysAutoResize):
        target_id = Player.GetTargetID()
        target_item_id = Agent.GetItemAgentItemID(target_id) if target_id else 0

        if target_item_id:
            PyImGui.text(f"Target: agent {target_id}  ->  item {target_item_id}")
        elif target_id:
            PyImGui.text(f"Target: agent {target_id} (not an item)")
        else:
            PyImGui.text("Target: none")

        PyImGui.separator()

        # -- step 1: on the ground --------------------------------------------
        if PyImGui.button("1. Dump Targeted Ground Item"):
            if target_item_id:
                dump_by_agent(target_id)
                pending_item_id = target_item_id
                ground_model, pending_ground_model_error = _try_value(lambda: Item.GetModelID(target_item_id))
                try:
                    pending_ground_model_id = int(ground_model or 0) if not pending_ground_model_error else 0
                except Exception as exc:
                    pending_ground_model_id = 0
                    pending_ground_model_error = f"{type(exc).__name__}: {exc}"
                pending_label = f"item {target_item_id}"
                last_held_slot_summary = None
                status_line = "Ground dump written. Now pick it up, then press 2."
            elif target_id:
                status_line = "That target is not an item."
            else:
                status_line = "Target an item on the ground first."

        # -- step 2: after pickup ---------------------------------------------
        if pending_item_id:
            if PyImGui.button(f"2. Dump Saved Item + Held Slot — {pending_label}###dump2"):
                dump_after_pickup(pending_item_id, pending_ground_model_id, pending_ground_model_error)
                status_line = f"Saved-item and held-slot evidence written for {pending_label}. Pair complete."
                pending_item_id = 0
                pending_ground_model_id = 0
                pending_ground_model_error = ""
                pending_label = ""
        else:
            PyImGui.text("2. (do step 1 first)")

        PyImGui.separator()
        if PyImGui.button("Clear Log"):
            try:
                path = _log_path()
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8") as handle:
                    handle.write("")
                status_line = "Log cleared."
                pending_item_id = 0
                pending_ground_model_id = 0
                pending_ground_model_error = ""
                pending_label = ""
                last_held_slot_summary = None
            except Exception as exc:
                status_line = f"Clear failed: {exc}"

        if status_line:
            PyImGui.text_colored(status_line, Color(150, 255, 150, 255).to_tuple_normalized())

        summary_lines = _format_held_slot_summary(last_held_slot_summary)
        if summary_lines:
            PyImGui.separator()
            PyImGui.text_colored(summary_lines[0], Color(255, 200, 100, 255).to_tuple_normalized())
            for line in summary_lines[1:]:
                PyImGui.text(line)

        PyImGui.text_disabled(f"Log: {LOG_RELATIVE_PATH}")

    ImGui.End(INI_KEY)


# --- lifecycle ---------------------------------------------------------------
def tooltip():
    PyImGui.begin_tooltip()
    title_color = Color(255, 200, 100, 255)
    ImGui.push_font("Regular", 20)
    PyImGui.text_colored(MODULE_NAME, title_color.to_tuple_normalized())
    ImGui.pop_font()
    PyImGui.spacing()
    PyImGui.separator()
    PyImGui.text("Dumps every readable field of an item lying on the ground,")
    PyImGui.text("then the saved item object and the live held slot after pickup.")
    PyImGui.spacing()
    PyImGui.text_colored("Usage:", title_color.to_tuple_normalized())
    PyImGui.bullet_text("Target an item on the ground, press button 1.")
    PyImGui.bullet_text("Pick it up, press button 2 to capture both identity surfaces.")
    PyImGui.bullet_text("Evidence lands in diagnostics/ground_item_dump.log")
    PyImGui.end_tooltip()


def draw():
    if initialized:
        draw_widget()


def main():
    global INI_KEY, initialized
    if initialized:
        return
    if not Routines.Checks.Map.MapValid():
        return
    if not INI_KEY:
        INI_KEY = Settings(f"{INI_PATH}/{INI_FILENAME}", "account").name
        if not INI_KEY:
            return
    initialized = True


__all__ = ['main', 'draw', 'tooltip']
