"""Underworld BT migration (Planner-first, harmonized with Shards).

This is a genuine BottingTree script: no legacy Botting FSM, no FSM jump,
no generator-managed legacy movement. Implemented through Dhuum (last sections require in-game validation).

START: outpost preparation or already inside Underworld, as party leader.
Dhuum completes the current Underworld itinerary; see the Dhuum tab before running.
Requires Sources.ApoSource.ApoBottingLib.wrappers and current BottingTree.
"""
from __future__ import annotations

import time
import os
import json
from datetime import datetime, timezone
from collections.abc import Callable

import PyImGui
import PySystem
from Py4GWCoreLib import Agent, AgentArray, Map, GLOBAL_CACHE, Player, SharedCommandType
from Py4GWCoreLib.Quest import Quest
from Py4GWCoreLib.enums import CONSUMABLE_MODELID_TO_EFFECT_NAME
from Py4GWCoreLib.BottingTree import BottingTree
from Py4GWCoreLib.py4gwcorelib_src.BehaviorTree import BehaviorTree
from Py4GWCoreLib.native_src.internals.types import Vec2f
from Py4GWCoreLib.enums_src.Player_enums import PlayerStatus
from Py4GWCoreLib.EnemyBlacklist import EnemyBlacklist
from Py4GWCoreLib.py4gwcorelib_src.Settings import Settings
from Py4GWCoreLib.enums_src.Model_enums import ModelID
from Py4GWCoreLib.enums_src.Map_enums import name_to_map_id
from Py4GWCoreLib.routines_src.behaviourtrees_src.constants.lists import CONSET_UPKEEPS, CONSUMABLE_UPKEEPS as ALL_CONSUMABLE_UPKEEPS
from Py4GWCoreLib.routines_src.behaviourtrees_src.shared import BTShared
from Sources.Sky.DungeonParty import DungeonPartyConfig
from Sources.Sky.Support import attach_botting_tree_support
from Sources.Sky.ConsumableRestockUI import draw_restock_group_grid
from Sources.ApoSource.ApoBottingLib import wrappers as BT

MODULE_NAME = "Underworld BT"
MODULE_CATEGORY = "Automation"
MODULE_TAGS = ["Underworld", "UW", "Multibox", "BottingTree"]
MODULE_DESCRIPTION = "BT-only UW migration: Chamber through Dhuum, with configurable Dhuum party options."
UW_MAP_ID = 72

# Original Underworld.py dialogue and quest IDs; kept unmodified.
QUEST_CLEAR = 101
QUEST_RESTORE_MONUMENTS = 109
QUEST_DEMON_ASSASSIN = 104
QUEST_FOUR_HORSEMEN = 106
QUEST_TERRORWEB_QUEEN = 107
NPC_LOST_SOUL = 2425
NPC_REAPER = 2399

# Same shared Settings + Party + Restock UI components used by Shards.
INI_PATH = "Widgets/Automation/Bots/Missions/Dungeons/Underworld BT"
INI_FILENAME = "Underworld_BT.ini"
_settings = Settings(f"{INI_PATH}/{INI_FILENAME}", "global")
_party_config = DungeonPartyConfig(_settings)
_settings_loaded = False
_use_hard_mode = True
_restock_conset = True
_restock_uw_scrolls = True
_activate_conset = True
_restock_pcons = True
_activate_pcons = True
_restock_morale = True
_activate_morale = True
_use_summoning_stone = True
_enable_inventory_handler = True
# Selection matches the legacy UW entry points, where scroll use is mandatory.
ENTRYPOINTS = (
    ("Embark Beach", int(name_to_map_id["Embark Beach"])),
    ("Temple of the Ages", int(name_to_map_id["Temple of the Ages"])),
    ("Chantry of Secrets", int(name_to_map_id["Chantry of Secrets"])),
    ("Zin Ku Corridor", int(name_to_map_id["Zin Ku Corridor"])),
)
_entrypoint_index = 0
UW_SCROLL_MODEL_ID = 3746
MORALE_MODELS = (int(ModelID.Four_Leaf_Clover.value), int(ModelID.Honeycomb.value))
PCON_MODELS = tuple(int(mid) for mid in ALL_CONSUMABLE_UPKEEPS
                    if int(mid) not in CONSET_UPKEEPS and int(mid) not in MORALE_MODELS)
# Share the Restock design and item definitions with Shards, without importing
# its bot instance or any of its runtime state.
RESTOCK_DEFS = (
    ("Conset", "Essence of Celerity", int(ModelID.Essence_Of_Celerity.value), "Essence", 10),
    ("Conset", "Grail of Might", int(ModelID.Grail_Of_Might.value), "Grail", 10),
    ("Conset", "Armor of Salvation", int(ModelID.Armor_Of_Salvation.value), "Armor", 10),
    ("Personal PCons", "Birthday Cupcake", int(ModelID.Birthday_Cupcake.value), "Cupcake", 10),
    ("Personal PCons", "Golden Egg", int(ModelID.Golden_Egg.value), "Egg", 10),
    ("Personal PCons", "Candy Corn", int(ModelID.Candy_Corn.value), "CandyCorn", 10),
    ("Personal PCons", "Candy Apple", int(ModelID.Candy_Apple.value), "CandyApple", 10),
    ("Personal PCons", "Pumpkin Pie", int(ModelID.Slice_Of_Pumpkin_Pie.value), "PumpkinPie", 10),
    ("Personal PCons", "Drake Kabob", int(ModelID.Drake_Kabob.value), "DrakeKabob", 10),
    ("Personal PCons", "Skalefin Soup", int(ModelID.Bowl_Of_Skalefin_Soup.value), "SkalefinSoup", 10),
    ("Personal PCons", "Pahnai Salad", int(ModelID.Pahnai_Salad.value), "PahnaiSalad", 10),
    ("Personal PCons", "War Supplies", int(ModelID.War_Supplies.value), "WarSupplies", 10),
    ("Morale", "Four-Leaf Clover", int(ModelID.Four_Leaf_Clover.value), "Clover", 10),
    ("Morale", "Honeycomb", int(ModelID.Honeycomb.value), "Honeycomb", 10),
    ("Summoning", "Legionnaire Crystal", int(ModelID.Legionnaire_Summoning_Crystal.value), "Legionnaire", 10),
    ("Summoning", "Tengu Stone", int(ModelID.Tengu_Summon.value), "Tengu", 10),
    ("Summoning", "Mysterious Stone", int(ModelID.Mysterious_Summon.value), "Mysterious", 10),
    ("UW Entry", "Passage Scroll to the Underworld", UW_SCROLL_MODEL_ID, "UWScroll", 5),
)
_restock_quantities = {mid:default for _,_,mid,_,default in RESTOCK_DEFS}
_configured_upkeeps = None

# Exact Shards direct PCon upkeep mechanics, adapted to Underworld (map 72).
# Core ConfigureUpkeep continues managing consets only.
_PCON_DIRECT_DISPATCH_INTERVAL_MS = 650
PCON_USAGE_LOG = False
_pcon_direct_index = 0
_pcon_direct_last_dispatch_ms = 0
_pcon_direct_runtime_logged = False
_pcon_direct_last_recipient_signature: tuple[str, ...] = ()
_pcon_direct_morale_remote_index = 0
_PCON_PARTY_MORALE_TARGET_BY_MODEL = {
    int(ModelID.Four_Leaf_Clover.value): 100,
    int(ModelID.Honeycomb.value): 110,
}


def _load_settings() -> None:
    global _settings_loaded, _use_hard_mode, _restock_conset, _restock_uw_scrolls, _activate_conset
    global _restock_pcons, _activate_pcons, _restock_morale, _activate_morale
    global _use_summoning_stone, _enable_inventory_handler, _entrypoint_index
    if _settings_loaded:
        return
    values = (
        ("HardMode", "_use_hard_mode"),
        ("RestockUWScrolls", "_restock_uw_scrolls"),
        ("RestockConset", "_restock_conset"), ("ActivateConset", "_activate_conset"),
        ("RestockPcons", "_restock_pcons"), ("ActivatePcons", "_activate_pcons"),
        ("RestockMorale", "_restock_morale"), ("ActivateMorale", "_activate_morale"),
        ("UseSummoningStone", "_use_summoning_stone"),
        ("InventoryHandler", "_enable_inventory_handler"),
    )
    for key, var in values:
        globals()[var] = bool(_settings.get_bool("Settings", key, globals()[var]))
    _entrypoint_index = max(0, min(len(ENTRYPOINTS)-1,
        int(_settings.get_int("Settings", "Entrypoint", 0))))
    for _group, _label, mid, key, default in RESTOCK_DEFS:
        _restock_quantities[mid] = max(0, int(_settings.get_int("Settings", "Restock"+key, default)))
    _settings_loaded = True


def _save_settings() -> None:
    flags = {
        "HardMode": _use_hard_mode,
        "RestockUWScrolls": _restock_uw_scrolls,
        "RestockConset": _restock_conset, "ActivateConset": _activate_conset,
        "RestockPcons": _restock_pcons, "ActivatePcons": _activate_pcons,
        "RestockMorale": _restock_morale, "ActivateMorale": _activate_morale,
        "UseSummoningStone": _use_summoning_stone,
        "InventoryHandler": _enable_inventory_handler,
        "Entrypoint": _entrypoint_index,
    }
    for key,value in flags.items():
        _settings.set("Settings", key, value)
    for _group, _label, mid, key, _default in RESTOCK_DEFS:
        _settings.set("Settings", "Restock"+key, int(_restock_quantities.get(mid,0)))


def _draw_run_config() -> None:
    global _use_hard_mode, _restock_conset, _restock_uw_scrolls, _activate_conset
    global _restock_pcons, _activate_pcons, _restock_morale, _activate_morale
    global _use_summoning_stone, _enable_inventory_handler, _entrypoint_index
    _load_settings()
    PyImGui.text("Underworld Run Config")
    PyImGui.separator()
    index = int(PyImGui.combo("Entry point", _entrypoint_index, [name for name,_ in ENTRYPOINTS]))
    if index != _entrypoint_index:
        _entrypoint_index = max(0,min(len(ENTRYPOINTS)-1,index))
        _save_settings()
    new = PyImGui.checkbox("Hard Mode (HM)",_use_hard_mode)
    if new != _use_hard_mode:
        _use_hard_mode=new; _save_settings()
    PyImGui.separator()
    previous_group = None
    for group, label, name in (
        ("UW Entry", "Restock UW passage scrolls (leader only)", "_restock_uw_scrolls"),
        ("Conset", "Restock conset from storage", "_restock_conset"),
        ("Conset", "Activate / maintain conset", "_activate_conset"),
        ("Personal PCons", "Restock pcons from storage", "_restock_pcons"),
        ("Personal PCons", "Activate / maintain pcons", "_activate_pcons"),
        ("Morale", "Restock morale cons from storage", "_restock_morale"),
        ("Morale", "Activate / maintain morale cons", "_activate_morale"),
        ("Summoning", "Use summoning stones", "_use_summoning_stone"),
        ("Inventory", "Enable Core auto inventory handler", "_enable_inventory_handler"),
    ):
        if group != previous_group:
            PyImGui.separator(); PyImGui.text(group)
        previous_group = group
        old=globals()[name]
        new=PyImGui.checkbox(label,old)
        if new != old:
            globals()[name]=new
            _save_settings()
            if name in ("_activate_conset", "_enable_inventory_handler"):
                _sync_upkeeps(force=True)
    PyImGui.text_wrapped("Party heroes are configured in Party. UW passage scroll stock is configured in Restock and withdrawn only by the leader before entry.")
    PyImGui.text_wrapped("Inventory: uses the Core auto handler, not Shards' MerchantRules multi-account threshold workflow.")
    PyImGui.text_wrapped("PCons are maintained on the UW party via Shards direct multibox dispatcher. Morale items are triggered only below their targets.")


def _draw_restock_config() -> None:
    _load_settings()
    PyImGui.text("Restock targets (same UI component as Shards)")
    PyImGui.text_wrapped("A target of 0 disables that item. UW Entry scrolls are restocked on the leader only; other groups are per account.")
    enabled={"UW Entry":_restock_uw_scrolls, "Conset":_restock_conset,"Personal PCons":_restock_pcons,
             "Morale":_restock_morale,"Summoning":_use_summoning_stone}
    changed=False
    for group in ("UW Entry","Conset","Personal PCons","Morale","Summoning"):
        items=[(label,mid,default) for grp,label,mid,key,default in RESTOCK_DEFS if grp==group]
        changed=draw_restock_group_grid(group, items, _restock_quantities,
                   group_enabled=enabled[group],columns=4,icon_size=48.0) or changed
    if changed: _save_settings()


def _restock_node() -> BehaviorTree:
    def _build(_node: BehaviorTree.Node) -> BehaviorTree:
        enabled={"Conset":_restock_conset,"Personal PCons":_restock_pcons,
                 "Morale":_restock_morale,"Summoning":_use_summoning_stone}
        items=[(mid,int(_restock_quantities.get(mid,0))) for grp,label,mid,key,default in RESTOCK_DEFS
               if grp != "UW Entry" and enabled[grp] and int(_restock_quantities.get(mid,0))>0]
        if not items:
            return BT.Succeeder("NoRestockItemsSelected")
        return BTShared.RestockItems(items,party_only=True,include_self=True,
                   allow_missing=True,refs_blackboard_prefix="uw_restock",
                   timeout_ms=30_000,poll_interval_ms=100,log=True)
    return BT.Subtree(name="Restock Selected Consumables", subtree_fn=_build)


def _uw_scroll_restock_node() -> BehaviorTree:
    """Native local BT restock; only the leader needs the entry scroll.

    This must NOT use BTShared.RestockItems, which would withdraw from each
    follower account's storage too.
    """
    def _build(_node: BehaviorTree.Node) -> BehaviorTree:
        quantity = int(_restock_quantities.get(UW_SCROLL_MODEL_ID, 0))
        if not _restock_uw_scrolls or quantity <= 0:
            return BT.Succeeder("UW Scroll Restock Disabled")
        return BT.RestockItems(
            model_id=UW_SCROLL_MODEL_ID,
            desired_quantity=quantity,
            allow_missing=False,
        )
    return BT.Subtree(name="Restock UW Passage Scrolls on Leader", subtree_fn=_build)


def _pcon_effect_name(model_id: int) -> str:
    """Resolve the persistent effect used by SharedCommandType.PCon."""
    model_id = int(model_id)
    overrides = {
        int(ModelID.Blue_Rock_Candy.value): "Blue_Rock_Candy_Rush",
        int(ModelID.Green_Rock_Candy.value): "Green_Rock_Candy_Rush",
        int(ModelID.Red_Rock_Candy.value): "Red_Rock_Candy_Rush",
        int(ModelID.Birthday_Cupcake.value): "Birthday_Cupcake_skill",
        int(ModelID.Bowl_Of_Skalefin_Soup.value): "Skale_Vigor",
        int(ModelID.Candy_Apple.value): "Candy_Apple_skill",
        int(ModelID.Candy_Corn.value): "Candy_Corn_skill",
        int(ModelID.Drake_Kabob.value): "Drake_Skin",
        int(ModelID.Golden_Egg.value): "Golden_Egg_skill",
        int(ModelID.Pahnai_Salad.value): "Pahnai_Salad_item_effect",
        int(ModelID.Slice_Of_Pumpkin_Pie.value): "Pie_Induced_Ecstasy",
        int(ModelID.War_Supplies.value): "Well_Supplied",
    }
    if model_id in overrides:
        return overrides[model_id]
    return str(CONSUMABLE_MODELID_TO_EFFECT_NAME.get(model_id, "") or "")


def _pcon_account_map_tuple(account: object) -> tuple[int, int, int, int]:
    map_obj = getattr(getattr(account, "AgentData", None), "Map", None)
    return (
        int(getattr(account, "MapID", 0) or getattr(map_obj, "MapID", 0) or 0),
        int(getattr(account, "MapRegion", 0) or getattr(map_obj, "Region", 0) or 0),
        int(getattr(account, "MapDistrict", 0) or getattr(map_obj, "District", 0) or 0),
        int(getattr(account, "MapLanguage", 0) or getattr(map_obj, "Language", 0) or 0),
    )


def _pcon_account_party_id(account: object) -> int:
    return int(getattr(getattr(account, "AgentPartyData", None), "PartyID", 0) or 0)


def _direct_pcon_party_emails() -> list[str]:
    local_email = str(Player.GetAccountEmail() or "").strip()
    if not local_email:
        return []

    try:
        local_account = GLOBAL_CACHE.ShMem.GetAccountDataFromEmail(local_email)
    except Exception:
        local_account = None

    try:
        accounts = list(GLOBAL_CACHE.ShMem.GetAllAccountData(sort_results=False) or [])
    except TypeError:
        accounts = list(GLOBAL_CACHE.ShMem.GetAllAccountData() or [])
    except Exception:
        accounts = []

    local_party_id = _pcon_account_party_id(local_account) if local_account is not None else 0
    local_map = _pcon_account_map_tuple(local_account) if local_account is not None else None

    result: list[str] = []
    seen: set[str] = set()
    for account in accounts:
        email = str(getattr(account, "AccountEmail", "") or "").strip()
        if not email or email in seen:
            continue
        if bool(getattr(account, "IsHero", False)) or bool(getattr(account, "IsNPC", False)):
            continue

        account_party_id = _pcon_account_party_id(account)
        same_party = local_party_id > 0 and account_party_id == local_party_id
        same_map_fallback = (
            local_party_id <= 0
            and local_map is not None
            and _pcon_account_map_tuple(account) == local_map
        )
        if not same_party and not same_map_fallback:
            continue

        seen.add(email)
        result.append(email)

    if local_email not in seen:
        result.append(local_email)
    return result


def _reset_direct_pcon_runtime() -> None:
    global _pcon_direct_index, _pcon_direct_last_dispatch_ms
    global _pcon_direct_runtime_logged, _pcon_direct_last_recipient_signature
    global _pcon_direct_morale_remote_index
    _pcon_direct_index = 0
    _pcon_direct_last_dispatch_ms = 0
    _pcon_direct_runtime_logged = False
    _pcon_direct_last_recipient_signature = ()
    _pcon_direct_morale_remote_index = 0


def _bot_is_started() -> bool:
    if botting_tree is None:
        return False
    try:
        fn = getattr(botting_tree, "IsStarted", None)
        if callable(fn):
            return bool(fn())
    except Exception:
        pass
    return bool(getattr(botting_tree, "started", False))


def _shared_party_min_morale_for_direct_pcons() -> int | None:
    """Return the lowest valid shared party morale, or None while unavailable."""
    try:
        entries = GLOBAL_CACHE.ShMem.GetSharedPartyMorale() or []
    except Exception:
        return None

    values: list[int] = []
    for entry in entries:
        try:
            morale = int(entry[1] or 0)
        except (TypeError, ValueError, IndexError):
            continue
        if morale > 0:
            values.append(morale)
    return min(values) if values else None


def _dispatch_party_morale_pcon(model_id: int, recipients: list[str], sender_email: str) -> None:
    """Use one party-wide morale PCon when the shared morale is below its target.

    Only one account is allowed to attempt the party-wide item per service pass;
    this prevents Four-Leaf Clover / Honeycomb from being consumed by several
    multibox clients at the same time before SharedMemory reflects the new morale.
    """
    global _pcon_direct_morale_remote_index

    target_morale = _PCON_PARTY_MORALE_TARGET_BY_MODEL.get(int(model_id))
    if target_morale is None:
        return

    party_min_morale = _shared_party_min_morale_for_direct_pcons()
    if party_min_morale is None or party_min_morale >= int(target_morale):
        return

    local_agent_id = int(Player.GetAgentID() or 0)
    local_is_dead = bool(local_agent_id and Agent.IsDead(local_agent_id))
    if (
        not local_is_dead
        and GLOBAL_CACHE.Inventory.GetModelCount(int(model_id)) > 0
    ):
        item_id = int(GLOBAL_CACHE.Item.GetItemIdFromModelID(int(model_id)) or 0)
        if item_id > 0:
            GLOBAL_CACHE.Inventory.UseItem(item_id)
            if PCON_USAGE_LOG:
                PySystem.Console.Log(
                    MODULE_NAME,
                    (
                        f"[PCons] Party morale use: model={int(model_id)}, "
                        f"morale={party_min_morale} -> target={int(target_morale)}."
                    ),
                    PySystem.Console.MessageType.Info,
                )
            return

    remote_recipients = [
        email for email in recipients
        if email and email != sender_email
    ]
    if not remote_recipients:
        return

    # If the leader cannot consume it (dead/missing item), rotate the single
    # remote attempt so another account gets a chance on the next service pass.
    receiver_email = remote_recipients[
        _pcon_direct_morale_remote_index % len(remote_recipients)
    ]
    _pcon_direct_morale_remote_index = (
        _pcon_direct_morale_remote_index + 1
    ) % max(1, len(remote_recipients))

    try:
        GLOBAL_CACHE.ShMem.SendMessage(
            sender_email,
            receiver_email,
            SharedCommandType.PCon,
            (int(model_id), 0, 0, 0),
        )
    except Exception:
        return


def _tick_direct_pcon_upkeep() -> None:
    """Maintain persistent PCons plus party-wide morale consumables directly."""
    global _pcon_direct_index, _pcon_direct_last_dispatch_ms
    global _pcon_direct_runtime_logged, _pcon_direct_last_recipient_signature

    if not _bot_is_started() or not (_activate_pcons or _activate_morale):
        if _pcon_direct_runtime_logged or _pcon_direct_last_dispatch_ms:
            _reset_direct_pcon_runtime()
        return

    try:
        if not Map.IsMapReady() or not Map.IsExplorable():
            return
        if int(Map.GetMapID() or 0) != UW_MAP_ID:
            return
    except Exception:
        return

    enabled_models = ((PCON_MODELS if _activate_pcons else ()) +
                      (MORALE_MODELS if _activate_morale else ()))
    if not enabled_models:
        return

    now_ms = int(time.monotonic() * 1000.0)
    if now_ms - int(_pcon_direct_last_dispatch_ms) < _PCON_DIRECT_DISPATCH_INTERVAL_MS:
        return
    _pcon_direct_last_dispatch_ms = now_ms

    recipients = _direct_pcon_party_emails()
    if not recipients:
        return

    recipient_signature = tuple(sorted(recipients))
    if not _pcon_direct_runtime_logged or recipient_signature != _pcon_direct_last_recipient_signature:
        _pcon_direct_runtime_logged = True
        _pcon_direct_last_recipient_signature = recipient_signature
        PySystem.Console.Log(
            MODULE_NAME,
            f"[Consumables] Direct multibox upkeep: pcons={len(PCON_MODELS) if _activate_pcons else 0}, "
            f"morale_cons={len(MORALE_MODELS) if _activate_morale else 0}, accounts={len(recipients)}.",
            PySystem.Console.MessageType.Info,
        )

    model_id = int(enabled_models[_pcon_direct_index % len(enabled_models)])
    _pcon_direct_index = (_pcon_direct_index + 1) % len(enabled_models)

    sender_email = str(Player.GetAccountEmail() or "").strip()
    if not sender_email:
        return

    # Four-Leaf Clover and Honeycomb are morale consumables, not persistent
    # effects.  They are driven by the same party-morale thresholds used by
    # Messaging.UsePcon: Clover <100, Honeycomb <110.
    if model_id in _PCON_PARTY_MORALE_TARGET_BY_MODEL:
        _dispatch_party_morale_pcon(model_id, recipients, sender_email)
        return

    effect_name = _pcon_effect_name(model_id)
    effect_id = int(GLOBAL_CACHE.Skill.GetID(effect_name) or 0) if effect_name else 0
    if effect_id <= 0:
        return

    local_agent_id = int(Player.GetAgentID() or 0)
    local_is_dead = bool(local_agent_id and Agent.IsDead(local_agent_id))
    local_has_effect = bool(
        local_agent_id and GLOBAL_CACHE.Effects.HasEffect(local_agent_id, effect_id)
    )
    if (
        not local_is_dead
        and not local_has_effect
        and GLOBAL_CACHE.Inventory.GetModelCount(model_id) > 0
    ):
        item_id = int(GLOBAL_CACHE.Item.GetItemIdFromModelID(model_id) or 0)
        if item_id > 0:
            GLOBAL_CACHE.Inventory.UseItem(item_id)
            if PCON_USAGE_LOG:
                PySystem.Console.Log(
                    MODULE_NAME,
                    f"[PCons] Local use: model={model_id}, effect={effect_id} ({effect_name}).",
                    PySystem.Console.MessageType.Info,
                )

    # Persistent effects are personal: every remote client receives the same
    # request and Messaging.UsePcon checks its own effect/inventory before use.
    params = (model_id, effect_id, 0, 0)
    for receiver_email in recipients:
        if not receiver_email or receiver_email == sender_email:
            continue
        try:
            GLOBAL_CACHE.ShMem.SendMessage(
                sender_email,
                receiver_email,
                SharedCommandType.PCon,
                params,
            )
        except Exception:
            continue


def _enabled_upkeeps() -> tuple[int,...]:
    return tuple(int(mid) for mid in CONSET_UPKEEPS) if _activate_conset else ()


def _sync_upkeeps(*, force: bool=False) -> None:
    global _configured_upkeeps
    if botting_tree is None:
        return
    target=_enabled_upkeeps()
    if not force and target==_configured_upkeeps:
        return
    _configure(botting_tree)
    _configured_upkeeps=target


def _scroll_use_node() -> BehaviorTree:
    """Use UW scroll in the outpost, unlike explorable-only UseConsumable."""
    def _use(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        if Map.GetMapID()==UW_MAP_ID:
            return BehaviorTree.NodeState.SUCCESS
        iid=GLOBAL_CACHE.Inventory.GetFirstModelID(UW_SCROLL_MODEL_ID)
        if not iid:
            PySystem.Console.Log(MODULE_NAME, "No Passage Scroll to the Underworld (3746) in inventory.",PySystem.Console.MessageType.Error)
            return BehaviorTree.NodeState.FAILURE
        GLOBAL_CACHE.Inventory.UseItem(iid)
        return BehaviorTree.NodeState.SUCCESS
    return BehaviorTree(BehaviorTree.ActionNode(name="Use Underworld Passage Scroll",action_fn=_use,aftercast_ms=500))


def _when_not_inside(factory: Callable[[],BehaviorTree], name: str) -> BehaviorTree:
    """Skip outpost-only preparation if debugging from map 72."""
    return BT.Selector(name=name,children=[
        BT.IsCurrentMap(map_id=UW_MAP_ID, log=False),factory(),
    ])


def _entrypoint_travel() -> BehaviorTree:
    return BT.Subtree(name="Travel To Selected UW Outpost",
        subtree_fn=lambda _node: BT.Travel(target_map_id=ENTRYPOINTS[_entrypoint_index][1],
                                           random_travel=True,log=True))


def _entrypoint_check() -> BehaviorTree:
    return BT.Subtree(name="Verify Selected UW Outpost",
        subtree_fn=lambda _node: BT.IsCurrentMap(map_id=ENTRYPOINTS[_entrypoint_index][1],log=True))


def _difficulty_node() -> BehaviorTree:
    return BT.Subtree(name="Apply Selected Difficulty",
        subtree_fn=lambda _node: BT.SetHardMode(hard_mode=_use_hard_mode,log=True))


def _party_node() -> BehaviorTree:
    return _party_config.create_party_node(multibox_invite=True,timeout_ms=30_000,log=True)


def _entry_steps() -> list[tuple[str,Callable[[],BehaviorTree]]]:
    """Planner-friendly individual preparation substeps, matching Shards."""
    return [
       ("Prepare UW - 01 - Travel to entry point", lambda: _when_not_inside(_entrypoint_travel,"UW Travel / already inside")),
       ("Prepare UW - 02 - Verify outpost", lambda: _when_not_inside(_entrypoint_check,"UW Outpost / already inside")),
       ("Prepare UW - 03 - Create Party", lambda: _when_not_inside(_party_node,"UW Party / already inside")),
       ("Prepare UW - 04 - Apply difficulty", lambda: _when_not_inside(_difficulty_node,"UW Difficulty / already inside")),
       ("Prepare UW - 05 - Restock supplies", lambda: _when_not_inside(_restock_node,"UW Restock / already inside")),
       ("Prepare UW - 05A - Restock passage scrolls (leader)", lambda: _when_not_inside(_uw_scroll_restock_node,"UW Scroll Restock / already inside")),
       ("Enter UW - 06 - Use UW Scroll", lambda: _when_not_inside(_scroll_use_node,"UW Scroll / already inside")),
       ("Enter UW - 07 - Wait for map 72", lambda: BT.Selector(
           name="Wait For Underworld Entry", children=[
               BT.IsCurrentMap(map_id=UW_MAP_ID, log=False),
               BT.WaitForMapLoad(map_id=UW_MAP_ID, timeout_ms=60_000),
           ])),
       ("Enter UW - 08 - Wait until explorable", lambda: BT.WaitUntilOnExplorable(timeout_ms=30_000)),
       ("Enter UW - 09 - Settle", lambda: BT.Wait(2_000)),
    ]


botting_tree: BottingTree | None = None
initialized = False

# Detect a completed dungeon->outpost transition, including when the client
# returns automatically before the generic party-wipe service observes the death.
_uw_instance_seen = False
_uw_outpost_restarted = False


def _recover_after_uw_outpost(tree: BottingTree) -> bool:
    """Restart the *whole preparation* once after leaving a known UW instance.

    The native party-wipe service restarts the failed named step. That is correct
    for recoverable shrine wipes in Shards, but not for an Underworld defeat:
    resuming a waypoint after returning to an outpost cannot work.
    """
    global _uw_instance_seen, _uw_outpost_restarted, run_start_ms

    if not Map.IsMapReady():
        return False

    if Map.GetMapID() == UW_MAP_ID and Map.IsExplorable():
        _uw_instance_seen = True
        _uw_outpost_restarted = False
        return False

    if not _uw_instance_seen or _uw_outpost_restarted or not Map.IsOutpost():
        return False

    # Latch before restarting so subsequent ticks in the outpost do not reset
    # the newly-running CreateParty/Restock/Scroll preparation.
    _uw_outpost_restarted = True
    _uw_instance_seen = False
    _stats().finish("return_to_outpost")
    restarted = tree.RestartFromNamedPlannerStep("Initialize Bot", auto_start=True)
    if restarted:
        section_times.clear()
        run_start_ms = 0
        PySystem.Console.Log(
            MODULE_NAME,
            "[UW Recovery] Returned from UW (wipe/exit). "
            "Restarting from Initialize Bot and outpost preparation.",
            PySystem.Console.MessageType.Warning,
        )
    else:
        # Allow retry on the next frame if the Planner was not built yet.
        _uw_instance_seen = True
        _uw_outpost_restarted = False
        PySystem.Console.Log(
            MODULE_NAME,
            "[UW Recovery] Could not restart named step 'Initialize Bot'.",
            PySystem.Console.MessageType.Error,
        )
    return bool(restarted)

run_start_ms = 0
section_times: dict[str, int] = {}

# Section order follows the original UW.py (including sections not migrated yet).
UW_TRACKED_SECTIONS = (
    "Clear the Chamber", "Pass the Mountains", "Restore Mountains",
    "Demon Assassin", "Restore Planes", "The Four Horsemen",
    "Restore Pools", "Terrorweb Queen", "Restore Pit", "Imprisoned Spirits",
    "Restore Vale", "Wrathful Spirits", "Unwanted Guests",
    "Restore Wastes", "Servants of Grenth", "Dhuum",
)
UW_LAST_MIGRATED_SECTION = "Dhuum"
UW_STATS_MAX_HISTORY = 100


class UWRunTracker:
    """Non-blocking UW progress tracker; only writes JSON on milestones/end.

    Times are monotonic elapsed real time, independent of Map.GetInstanceUptime.
    A jump during Planner debugging marks the run ineligible for best/averages.
    Outpost returns are labeled as transitions, not automatically as defeats.
    """

    def __init__(self) -> None:
        self.active = False
        self.started = 0.0
        self.run_id = ""
        self.hard_mode = False
        self.completed: dict[str, float] = {}
        self.last_split_at = 0.0
        self.step_name = ""
        self.last_step_index: int | None = None
        self.debug_run = False
        self._last_map_in_uw = False
        self._finished_this_instance = False
        self._history: list[dict] = []
        self._path = self._get_path()
        self._read_history()

    @staticmethod
    def _get_path() -> str:
        try:
            project_root = PySystem.Console.get_projects_path()
        except Exception:
            project_root = os.getcwd()
        return os.path.join(str(project_root), "Widgets", "Config", "Underworld_BT_statistics.json")

    def _read_history(self) -> None:
        try:
            with open(self._path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, dict) and isinstance(data.get("runs"), list):
                self._history = [x for x in data["runs"] if isinstance(x, dict)][-UW_STATS_MAX_HISTORY:]
        except (OSError, ValueError, TypeError):
            self._history = []

    def _save_history(self) -> None:
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            temp = self._path + ".tmp"
            with open(temp, "w", encoding="utf-8") as handle:
                json.dump({"version": 1, "runs": self._history[-UW_STATS_MAX_HISTORY:]},
                          handle, ensure_ascii=False, indent=2)
            os.replace(temp, self._path)
        except OSError as exc:
            PySystem.Console.Log(MODULE_NAME, f"[Statistics] Save failed: {exc}",
                                 PySystem.Console.MessageType.Warning)

    def start_if_necessary(self) -> None:
        if self.active or not Map.IsMapReady():
            return
        if Map.GetMapID() != UW_MAP_ID or not Map.IsExplorable():
            self._finished_this_instance = False
            return
        # Do not create a second phantom run while the Planner is sitting at
        # its development STOP/checkpoint in the very same UW instance.
        if self._finished_this_instance:
            return
        self.active = True
        self.started = time.monotonic()
        self.run_id = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.hard_mode = bool(_use_hard_mode)
        self.completed = {}
        self.last_split_at = self.started
        self.step_name = ""
        self.last_step_index = None
        self.debug_run = False
        self._last_map_in_uw = True

    def elapsed(self) -> float:
        return max(0.0, time.monotonic() - self.started) if self.active else 0.0

    def watch_planner(self, tree: BottingTree) -> None:
        if not self.active:
            return
        try:
            step = str(tree.GetBlackboardValue("current_step_name", "") or "")
        except Exception:
            return
        if not step or step == self.step_name:
            return
        self.step_name = step
        # Recognize explicit backwards jumps. Forward gaps can be normal when
        # instant BT steps complete between display frames, so do not infer skips.
        try:
            step_names = tree.GetNamedPlannerStepNames()
            index = list(step_names).index(step)
            if self.last_step_index is not None and index < self.last_step_index:
                self.debug_run = True
            if self.last_step_index is None and index > 10 and not self.completed:
                self.debug_run = True
            self.last_step_index = index
        except (AttributeError, ValueError, TypeError):
            pass

    def record_section(self, section: str) -> None:
        self.start_if_necessary()
        if not self.active or section not in UW_TRACKED_SECTIONS or section in self.completed:
            return
        now = time.monotonic()
        self.completed[section] = round(now - self.started, 3)
        self.last_split_at = now
        PySystem.Console.Log(
            MODULE_NAME,
            f"[Statistics] {section}: cumulative {self.format_time(self.completed[section])}",
            PySystem.Console.MessageType.Info,
        )
        if section == UW_LAST_MIGRATED_SECTION:
            self.finish("success" if not self.debug_run and len(self.completed) >= 16 else "checkpoint")

    def split_seconds(self, section: str) -> float | None:
        if section not in self.completed:
            return None
        index = UW_TRACKED_SECTIONS.index(section)
        for previous in reversed(UW_TRACKED_SECTIONS[:index]):
            if previous in self.completed:
                return max(0.0, self.completed[section] - self.completed[previous])
        return self.completed[section]

    def finish(self, outcome: str) -> None:
        if not self.active:
            return
        total = round(self.elapsed(), 3)
        splits = {name: round(v, 3) for name in self.completed
                  if (v := self.split_seconds(name)) is not None}
        record = {
            "run_id": self.run_id,
            "ended_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "mode": "HM" if self.hard_mode else "NM",
            "outcome": outcome,
            "total_seconds": total,
            "sections_cumulative_seconds": dict(self.completed),
            "sections_split_seconds": splits,
            "last_planner_step": self.step_name,
            "debug_run": self.debug_run,
        }
        self._history.append(record)
        self._history = self._history[-UW_STATS_MAX_HISTORY:]
        self._save_history()
        PySystem.Console.Log(MODULE_NAME,
             f"[Statistics] Saved {outcome}, {self.format_time(total)} at {self.step_name!r}.",
             PySystem.Console.MessageType.Info)
        self.active = False
        self._last_map_in_uw = False
        self._finished_this_instance = True

    def reset_saved_statistics(self) -> bool:
        """Clear persisted run history; preserve an active run and its current splits.

        The JSON file is rewritten with an empty list, so old records cannot
        reappear when this script or the Statistics tab reloads.
        """
        previous = list(self._history)
        self._history = []
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            temp = self._path + ".tmp"
            with open(temp, "w", encoding="utf-8") as handle:
                json.dump({"version": 1, "runs": []}, handle,
                          ensure_ascii=False, indent=2)
            os.replace(temp, self._path)
        except OSError as exc:
            self._history = previous
            PySystem.Console.Log(MODULE_NAME,
                                 f"[Statistics] Reset failed: {exc}",
                                 PySystem.Console.MessageType.Warning)
            return False
        PySystem.Console.Log(MODULE_NAME,
                             "[Statistics] Saved history and records reset.",
                             PySystem.Console.MessageType.Info)
        return True

    def successful_runs(self) -> list[dict]:
        mode = "HM" if _use_hard_mode else "NM"
        return [record for record in self._history
                if record.get("outcome") == "success"
                and not record.get("debug_run") and record.get("mode") == mode][-5:]

    def section_average(self, section: str) -> float | None:
        values = [float(r["sections_split_seconds"][section]) for r in self.successful_runs()
                  if section in r.get("sections_split_seconds", {})]
        return sum(values) / len(values) if values else None

    @staticmethod
    def format_time(seconds: float | None) -> str:
        if seconds is None:
            return "--:--"
        n = max(0, int(seconds))
        return f"{n // 3600:02d}:{(n // 60) % 60:02d}:{n % 60:02d}"


_uw_stats_reset_confirm = False
_uw_tracker: UWRunTracker | None = None


def _stats() -> UWRunTracker:
    global _uw_tracker
    if _uw_tracker is None:
        _uw_tracker = UWRunTracker()
    return _uw_tracker


def _draw_statistics() -> None:
    """Render statistics as compact, readable native PyImGui tables.

    Presentation only: collection, timing, eligibility rules and JSON schema
    remain unchanged.
    """
    global _uw_stats_reset_confirm
    tracker = _stats()
    if not tracker.active and not tracker._history:
        tracker._read_history()

    mode = "HM" if _use_hard_mode else "NM"
    successful = tracker.successful_runs()
    best_total = (min(float(r["total_seconds"]) for r in successful)
                  if successful else None)
    average_total = (sum(float(r["total_seconds"]) for r in successful) / len(successful)
                     if successful else None)
    time_fmt = tracker.format_time

    PyImGui.text("UNDERWORLD  |  RUN STATISTICS")
    PyImGui.separator()
    PyImGui.text(f"Mode: {mode}   |   Status: {'RUNNING' if tracker.active else 'IDLE'}"
                  f"   |   Current: {time_fmt(tracker.elapsed()) if tracker.active else '--:--'}")
    PyImGui.text(f"Best complete: {time_fmt(best_total)}   |   "
                  f"Average (last {len(successful)}): {time_fmt(average_total)}")
    if tracker.active:
        PyImGui.text(f"Run type: {'Debug / manual restart' if tracker.debug_run else 'Normal'}")
    PyImGui.text_wrapped(f"Planner: {tracker.step_name or '(no active step)'}")

    PyImGui.separator()
    PyImGui.text("STATISTICS MANAGEMENT")
    if not _uw_stats_reset_confirm:
        if PyImGui.button("Reset saved statistics##uw_stats_reset"):
            _uw_stats_reset_confirm = True
    else:
        PyImGui.text_wrapped("Confirm reset? This permanently clears saved runs, "
                              "averages and personal bests for BOTH NM and HM. "
                              "The current run and its splits will be kept.")
        if PyImGui.button("Confirm reset##uw_stats_confirm"):
            if tracker.reset_saved_statistics():
                _uw_stats_reset_confirm = False
        PyImGui.same_line()
        if PyImGui.button("Cancel##uw_stats_cancel"):
            _uw_stats_reset_confirm = False


    PyImGui.separator()
    PyImGui.text("QUEST PROGRESS")
    table_flags = (PyImGui.TableFlags.RowBg |
                   PyImGui.TableFlags.Borders |
                   PyImGui.TableFlags.ScrollY)
    if PyImGui.begin_table("##uw_statistics_quests", 5, table_flags, 0.0, 350.0):
        PyImGui.table_setup_column("Quest", PyImGui.TableColumnFlags.WidthStretch, 0.0)
        PyImGui.table_setup_column("Split", PyImGui.TableColumnFlags.WidthFixed, 80.0)
        PyImGui.table_setup_column("Cumulative", PyImGui.TableColumnFlags.WidthFixed, 88.0)
        PyImGui.table_setup_column("Avg split", PyImGui.TableColumnFlags.WidthFixed, 86.0)
        PyImGui.table_setup_column("Best split", PyImGui.TableColumnFlags.WidthFixed, 86.0)
        PyImGui.table_headers_row()

        for section in UW_TRACKED_SECTIONS:
            cumulative = tracker.completed.get(section)
            split = tracker.split_seconds(section)
            historical = [float(r["sections_split_seconds"][section])
                          for r in successful
                          if section in r.get("sections_split_seconds", {})]
            best_split = min(historical) if historical else None
            is_migrated = (UW_TRACKED_SECTIONS.index(section) <=
                           UW_TRACKED_SECTIONS.index(UW_LAST_MIGRATED_SECTION))

            PyImGui.table_next_row()
            PyImGui.table_next_column()
            marker = "[OK] " if cumulative is not None else ("[ ] " if is_migrated else "[-] ")
            PyImGui.text(marker + section)
            PyImGui.table_next_column()
            PyImGui.text(time_fmt(split))
            PyImGui.table_next_column()
            PyImGui.text(time_fmt(cumulative))
            PyImGui.table_next_column()
            PyImGui.text(time_fmt(tracker.section_average(section)))
            PyImGui.table_next_column()
            PyImGui.text(time_fmt(best_split))
        PyImGui.end_table()

    PyImGui.separator()
    PyImGui.text("RECENT RUNS  |  latest first")
    if PyImGui.begin_table("##uw_statistics_history", 5, table_flags, 0.0, 180.0):
        PyImGui.table_setup_column("Date (UTC)", PyImGui.TableColumnFlags.WidthFixed, 118.0)
        PyImGui.table_setup_column("Mode", PyImGui.TableColumnFlags.WidthFixed, 40.0)
        PyImGui.table_setup_column("Result", PyImGui.TableColumnFlags.WidthFixed, 118.0)
        PyImGui.table_setup_column("Duration", PyImGui.TableColumnFlags.WidthFixed, 78.0)
        PyImGui.table_setup_column("Last Planner step", PyImGui.TableColumnFlags.WidthStretch, 0.0)
        PyImGui.table_headers_row()
        for record in reversed(tracker._history[-20:]):
            ended = str(record.get("ended_utc", ""))
            pretty_date = ended[:16].replace("T", " ") if ended else "--"
            outcome = str(record.get("outcome", "?"))
            if record.get("debug_run"):
                outcome += " (debug)"
            PyImGui.table_next_row()
            for field in (pretty_date,
                          str(record.get("mode", "?")),
                          outcome,
                          time_fmt(record.get("total_seconds")),
                          str(record.get("last_planner_step", ""))):
                PyImGui.table_next_column()
                PyImGui.text(field)
        PyImGui.end_table()

    if not successful:
        PyImGui.text_wrapped("Averages and records require a complete, non-debug "
                              "UW clear through Dhuum; checkpoints do not qualify.")
    PyImGui.text_wrapped("Dhuum success is recorded only after the chest and combat. "
                          "Return to outpost can indicate a wipe or manual exit.")



def _v(x: float, y: float) -> Vec2f:
    return Vec2f(float(x), float(y))


def _action(name: str, func: Callable[[], None]) -> BehaviorTree:
    """A one-shot, synchronous BT action. Any error FAILS the node."""
    def _run(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        try:
            func()
            return BehaviorTree.NodeState.SUCCESS
        except Exception as ex:
            PySystem.Console.Log(MODULE_NAME, f"[{name}] {ex}", PySystem.Console.MessageType.Error)
            return BehaviorTree.NodeState.FAILURE
    return BehaviorTree(BehaviorTree.ActionNode(name=name, action_fn=_run, aftercast_ms=0))


def _ensure_uw() -> BehaviorTree:
    """Use the existing BT map guard rather than another custom action."""
    return BT.IsCurrentMap(map_id=UW_MAP_ID, log=False)


def _blacklist(name: str, enabled: bool) -> BehaviorTree:
    def _apply() -> None:
        blacklist = EnemyBlacklist()
        if enabled:
            blacklist.add_name(name)
        else:
            blacklist.remove_name(name)
    verb = "Blacklist" if enabled else "Unblacklist"
    return _action(f"{verb}: {name}", _apply)


# Obsidian Guardians can appear after Clear the Chamber (notably Terrorweb).
# The original name-only blacklist depends on an exact decoded enemy name;
# resolve live model IDs as they spawn and add those to the SAME shared filter.
# This is deliberately UW-scoped and leaves all routes and HeroAI settings intact.
_uw_guardian_scan_at = 0.0
_uw_guardian_known_models: set[int] = set()
_uw_guardian_reported_unmatched: set[tuple[int, str]] = set()


def _sync_uw_guardian_blacklist(force: bool = False) -> None:
    global _uw_guardian_scan_at
    if not Map.IsMapReady() or Map.GetMapID() != UW_MAP_ID:
        _uw_guardian_scan_at = 0.0
        return
    now = time.monotonic()
    if not force and now - _uw_guardian_scan_at < 0.5:
        return
    _uw_guardian_scan_at = now
    blacklist = EnemyBlacklist()
    # Keep the original name entry as fallback, including for name resolution
    # during the first few frames after a map load.
    if "obsidian guardian" not in blacklist.get_all_names():
        blacklist.add_name("obsidian guardian")

    for enemy_id in AgentArray.GetEnemyArray() or []:
        if not Agent.IsValid(enemy_id):
            continue
        model_id = int(Agent.GetModelID(enemy_id) or 0)
        if model_id <= 0:
            continue
        name = str(Agent.GetNameByID(enemy_id) or "").strip().casefold()
        # English and French GW client names; allow optional apostrophe variants.
        is_guardian = ("obsidian guardian" in name or
                       ("gardien" in name and "obsidien" in name))
        if is_guardian:
            if not blacklist.contains(model_id):
                blacklist.add(model_id)
            if model_id not in _uw_guardian_known_models:
                _uw_guardian_known_models.add(model_id)
                PySystem.Console.Log(
                    MODULE_NAME,
                    f"[UW Blacklist] Obsidian Guardian model={model_id}, "
                    f"name='{name}', blacklisted={blacklist.is_blacklisted(enemy_id)}",
                    PySystem.Console.MessageType.Info,
                )
        elif ("guardian" in name or "gardien" in name) and (model_id, name) not in _uw_guardian_reported_unmatched:
            _uw_guardian_reported_unmatched.add((model_id, name))
            PySystem.Console.Log(
                MODULE_NAME,
                f"[UW Blacklist] Unrecognized guardian candidate model={model_id} name='{name}' (not auto-blocked)",
                PySystem.Console.MessageType.Warning,
            )


def _guardian_blacklist_checkpoint() -> BehaviorTree:
    return _action("Verify live Guardian blacklist", lambda: _sync_uw_guardian_blacklist(force=True))


def _record(label: str) -> BehaviorTree:
    def _do() -> None:
        section_times[label] = Map.GetInstanceUptime()
        normalized = "Demon Assassin" if label == "Deamon Assassin" else label
        _stats().record_section(normalized)
        PySystem.Console.Log(MODULE_NAME, f"Section complete: {label}", PySystem.Console.MessageType.Info)
    return _action(f"Record {label}", _do)


def _quest_npc(model: int, dialog: int, quest_id: int, name: str) -> BehaviorTree:
    # Do not silently advance when a dialog failed. The original script retried
    # via active quest checks; here BT reports FAILURE if not accepted.
    return BT.Sequence(name=name, children=[
        BT.MoveAndDialogByModelID(model, dialog_id=dialog, multi_account=False, log=False),
        BT.WaitForActiveQuest(quest_id, timeout_ms=20_000),
    ])


def _wait_quest_completed(quest_id: int, timeout_ms: int = 90_000) -> BehaviorTree:
    """Native BT condition: avoid the broken BT.WaitForQuestState wrapper.

    Quest.IsQuestCompleted is used in the original Underworld.py. Timeout and
    map transitions fail explicitly rather than silently skipping a quest.
    """
    started_at: float | None = None

    def _tick(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        nonlocal started_at
        if Map.GetMapID() != UW_MAP_ID:
            return BehaviorTree.NodeState.FAILURE
        if Quest.IsQuestCompleted(quest_id):
            return BehaviorTree.NodeState.SUCCESS
        now = time.monotonic()
        if started_at is None:
            started_at = now
        if (now - started_at) * 1000 >= timeout_ms:
            PySystem.Console.Log(
                MODULE_NAME,
                f"Quest {quest_id} not completed after {timeout_ms}ms. Stopping this section.",
                PySystem.Console.MessageType.Warning,
            )
            started_at = None
            return BehaviorTree.NodeState.FAILURE
        return BehaviorTree.NodeState.RUNNING

    return BehaviorTree(BehaviorTree.ActionNode(
        name=f"Wait quest {quest_id} completed", action_fn=_tick, aftercast_ms=0,
    ))


def InitializeBot() -> BehaviorTree:
    def _set_run_start() -> None:
        global run_start_ms
        run_start_ms = Map.GetInstanceUptime()
        section_times.clear()
    bot = ensure_botting_tree()
    return BT.Sequence(name="Initialize UW BT", children=[
        bot.Config.Aggressive(multi_account=True, auto_loot=True, resurrection_scroll=True, account_isolation=False),
        BT.SetPlayerStatus(PlayerStatus.Offline, log=False),
        _action("Start run clock", _set_run_start),
    ])


def _wait_for_mindblades(name: str, timeout_s: float = 20.0) -> BehaviorTree:
    """UW-specific ModelID 2380 check with legacy 20-second fallback.

    Unlike a map-wide clear, this waits only for the relevant Mindblades.
    The BT node keeps its own deadline between ticks.
    """
    def _check(node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        if Map.GetMapID() != UW_MAP_ID:
            return BehaviorTree.NodeState.FAILURE
        alive = any(
            Agent.IsAlive(e) and Agent.GetModelID(e) == 2380
            for e in AgentArray.GetEnemyArray()
        )
        if not alive:
            node.blackboard.pop("uw_mindblade_started", None)
            return BehaviorTree.NodeState.SUCCESS
        start = node.blackboard.setdefault("uw_mindblade_started", time.monotonic())
        if time.monotonic() - start >= timeout_s:
            PySystem.Console.Log(
                MODULE_NAME,
                f"Mindblade wait timed out ({name}); continuing as in legacy UW",
                PySystem.Console.MessageType.Warning,
            )
            node.blackboard.pop("uw_mindblade_started", None)
            return BehaviorTree.NodeState.SUCCESS
        return BehaviorTree.NodeState.RUNNING
    return BehaviorTree(BehaviorTree.ActionNode(
        name=f"Wait for Mindblades: {name}", action_fn=_check, aftercast_ms=0,
    ))


# Dedicated Four Horsemen mechanics. The BT's other sections and travel remain
# unchanged from the version already tested through Restore Planes.
HORSEMEN_HOLD_X = 11510.0
HORSEMEN_HOLD_Y = -18234.0

# The original HeroAI adapter continually re-enforced Following/Looting every
# frame. Replicate this here, rather than issuing an unreliable one-shot toggle.
_horsemen_policy: str | None = None  # None / 'staging' / 'defense'
_horsemen_options_snapshot: dict[str, tuple[bool, bool]] = {}


def _horsemen_accounts():
    """Active, non-isolated player accounts belonging to the leader's party."""
    party_id = int(GLOBAL_CACHE.Party.GetPartyID() or 0)
    if party_id <= 0:
        return []
    result = []
    for account, options in GLOBAL_CACHE.ShMem.GetAllActiveAccountHeroAIPairs(sort_results=False):
        if (not account or options is None or not account.IsSlotActive
                or account.IsHero or getattr(account, 'IsIsolated', False)):
            continue
        if int(account.AgentPartyData.PartyID or 0) != party_id:
            continue
        result.append((account, options))
    return result


def _horsemen_apply_policy() -> None:
    """Maintain the actual old HeroAI options through multibox snapshot updates."""
    if _horsemen_policy is None or Map.GetMapID() != UW_MAP_ID:
        return
    for account, options in _horsemen_accounts():
        email = str(account.AccountEmail)
        if email not in _horsemen_options_snapshot:
            _horsemen_options_snapshot[email] = (bool(options.Following), bool(options.Looting))
        options.Looting = False
        if _horsemen_policy == 'staging':
            options.Following = False
            # Original adapter pins followers at their current positions when
            # following is disabled. Do NOT use the unused seven-point array.
            # The one-shot anchor is set in _horsemen_start_staging().
        else:
            options.Following = True


def _horsemen_start_staging() -> None:
    global _horsemen_policy
    _horsemen_policy = 'staging'
    _horsemen_apply_policy()
    for account, options in _horsemen_accounts():
        try:
            x, y = float(account.AgentData.Pos.x), float(account.AgentData.Pos.y)
            options.IsFlagged = True
            options.FlagPos.x, options.FlagPos.y = x, y
            options.FlagFacingAngle = 0.0
        except (AttributeError, TypeError, ValueError):
            pass
    PySystem.Console.Log(MODULE_NAME, '[4H] Following OFF, looting OFF; followers anchored in place.',
                         PySystem.Console.MessageType.Info)


def _horsemen_start_defense() -> None:
    global _horsemen_policy
    _horsemen_policy = 'defense'
    _horsemen_apply_policy()


def _horsemen_restore_policy() -> None:
    global _horsemen_policy
    for account, options in _horsemen_accounts():
        snapshot = _horsemen_options_snapshot.get(str(account.AccountEmail))
        if snapshot is not None:
            options.Following, options.Looting = snapshot
        else:
            options.Following, options.Looting = True, True
    _horsemen_options_snapshot.clear()
    _horsemen_policy = None
    PySystem.Console.Log(MODULE_NAME, '[4H] Original Following/Looting options restored.',
                         PySystem.Console.MessageType.Info)


def _horsemen_hold_until_complete(timeout_ms: int = 360_000) -> BehaviorTree:
    """Keep the *leader* in place while the quest runs.

    The normal BT movement nodes return once a waypoint is reached; they cannot
    counter intermittent HeroAI reposition commands. This single UW-specific
    action therefore maintains the old hold point, while the ordinary native
    BT.FlagAllHeroes handles heroes and multibox accounts.
    """
    def _tick(node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        if Map.GetMapID() != UW_MAP_ID:
            node.blackboard.pop("uw_horsemen_hold_since", None)
            return BehaviorTree.NodeState.FAILURE
        if Quest.IsQuestCompleted(QUEST_FOUR_HORSEMEN):
            node.blackboard.pop("uw_horsemen_hold_since", None)
            return BehaviorTree.NodeState.SUCCESS

        agent_id = Player.GetAgentID()
        if not agent_id or not Agent.IsValid(agent_id) or Agent.IsDead(agent_id):
            node.blackboard.pop("uw_horsemen_hold_since", None)
            return BehaviorTree.NodeState.FAILURE

        now = time.monotonic()
        started = node.blackboard.setdefault("uw_horsemen_hold_since", now)
        if (now - started) * 1000 >= timeout_ms:
            PySystem.Console.Log(
                MODULE_NAME, "Four Horsemen hold timed out; quest 106 not completed.",
                PySystem.Console.MessageType.Warning,
            )
            node.blackboard.pop("uw_horsemen_hold_since", None)
            return BehaviorTree.NodeState.FAILURE

        px, py = Player.GetXY()
        if (px - HORSEMEN_HOLD_X) ** 2 + (py - HORSEMEN_HOLD_Y) ** 2 > 80.0 ** 2:
            Player.Move(HORSEMEN_HOLD_X, HORSEMEN_HOLD_Y)
        return BehaviorTree.NodeState.RUNNING

    return BehaviorTree(BehaviorTree.ActionNode(
        name="Maintain hold and verify Four Horsemen quest",
        action_fn=_tick,
        aftercast_ms=0,
    ))


def _horsemen_clear_stale_target() -> BehaviorTree:
    """Avoid retaining a despawned Horseman target after the encounter."""
    return _action("Clear stale Horsemen target",
                   lambda: Player.ChangeTarget(Player.GetAgentID()))


def _stop_before_restore_vale() -> BehaviorTree:
    """Development checkpoint. This is not a full UW run."""
    def _stop(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        PySystem.Console.Log(
            MODULE_NAME,
            "BT checkpoint reached: Imprisoned Spirits complete. Restore Vale pending migration.",
            PySystem.Console.MessageType.Warning,
        )
        return BehaviorTree.NodeState.FAILURE
    return BehaviorTree(BehaviorTree.ActionNode(
        name="STOP: Restore Vale pending", action_fn=_stop, aftercast_ms=0,
    ))


# Imprisoned Spirits: slots are the visible, 1-based party roster positions.
# Players come first (including leader in slot 1), followed by native heroes.
# Follower account flags use HeroAI ShMem; hero flags use the native party API.
IMPRISONED_QUEST_ID = 105
IMPRISONED_LEFT_POINTS = ((13849, 6602), (13876, 6752), (13985, 6840),
                          (13598, 6779), (13845, 6489))
IMPRISONED_RIGHT_POINTS = ((12871, 2512), (12640, 2485), (12402, 2472),
                           (12137, 2444), (12150, 2139), (12239, 2324))
_imprisoned_team_assignments: dict[int, str] = {}
_imprisoned_runtime_active = False
_imprisoned_snapshot: dict[str, tuple[bool, bool]] = {}
_imprisoned_target_flags: dict[str, tuple[float, float]] = {}
_imprisoned_hero_flags: dict[int, tuple[float, float]] = {}
_imprisoned_timer_started: float | None = None


def _imprisoned_accounts() -> list[tuple[object, object]]:
    local_email = str(Player.GetAccountEmail() or '').strip().lower()
    party_id = int(GLOBAL_CACHE.Party.GetPartyID() or 0)
    result = []
    for account, options in _horsemen_accounts():
        if str(account.AccountEmail or '').strip().lower() == local_email:
            continue
        if int(account.AgentPartyData.PartyID or 0) != party_id:
            continue
        if bool(getattr(account, 'IsHero', False)):
            continue
        result.append((account, options))
    return result


def _imprisoned_slots() -> list[tuple[int, str, str, object, object]]:
    """(UI slot, kind, display name, account/agent, options/hero index).

    GW places human party players first. ShMem PartyPosition is 0-based;
    hero indices for GetHeroAgentIDByPartyPosition are 1-based amongst heroes.
    """
    from Py4GWCoreLib import Party
    player_count = int(Party.GetPlayerCount() or 0)
    hero_count = int(Party.GetHeroCount() or 0)
    slots = []
    for account, options in _imprisoned_accounts():
        party_pos = int(account.AgentPartyData.PartyPosition)
        slot = party_pos + 1
        if not 2 <= slot <= player_count:
            continue
        char = str(getattr(account.AgentData, 'CharacterName', '') or account.AccountEmail)
        slots.append((slot, 'Follower', char, account, options))
    for hero_index in range(1, hero_count + 1):
        agent_id = int(Party.Heroes.GetHeroAgentIDByPartyPosition(hero_index) or 0)
        slot = player_count + hero_index
        if agent_id <= 0:
            continue
        name = str(Agent.GetNameByID(agent_id) or f'Hero {hero_index}')
        slots.append((slot, 'Hero', name, agent_id, hero_index))
    return sorted(slots, key=lambda entry: entry[0])


def _imprisoned_read_team(slot: int) -> str:
    slot = int(slot)
    cached = _imprisoned_team_assignments.get(slot)
    if cached in ('left', 'right'):
        return cached
    stored = str(_settings.get_str('ImprisonedSpiritsSlots', f'slot_{slot}', '') or '').lower()
    if stored not in ('left', 'right'):
        # An editable initial example for 4 players + 4 heroes: 2/3 right,
        # 4 left, then alternating the heroes. No hard-coded account names.
        stored = {2: 'right', 3: 'right', 4: 'left', 5: 'left',
                  6: 'right', 7: 'left', 8: 'right'}.get(slot,
                  'left' if slot % 2 else 'right')
    _imprisoned_team_assignments[slot] = stored
    return stored


def _imprisoned_set_team(slot: int, team: str) -> None:
    if team not in ('left', 'right'):
        raise ValueError(f'Invalid Imprisoned Spirits side: {team}')
    slot = int(slot)
    _imprisoned_team_assignments[slot] = team
    _settings.set('ImprisonedSpiritsSlots', f'slot_{slot}', team)


def _draw_imprisoned_config() -> None:
    PyImGui.text('Imprisoned Spirits - assign party members by slot')
    PyImGui.text_wrapped('Slot 1 (leader) moves with the BT and is not flagged. '
                          'Assign each slot 2..8 LEFT or RIGHT; this includes heroes and multibox followers.')
    roster = _imprisoned_slots()
    if not roster:
        PyImGui.text('No party roster detected. Join the group first.')
        return
    flags = PyImGui.TableFlags.RowBg | PyImGui.TableFlags.BordersInnerV | PyImGui.TableFlags.BordersOuterH
    if PyImGui.begin_table('##uw_imprisoned_slot_teams', 4, flags, 0.0, 0.0):
        PyImGui.table_setup_column('Slot', PyImGui.TableColumnFlags.WidthFixed, 42.0)
        PyImGui.table_setup_column('Character', PyImGui.TableColumnFlags.WidthStretch, 0.0)
        PyImGui.table_setup_column('Left', PyImGui.TableColumnFlags.WidthFixed, 55.0)
        PyImGui.table_setup_column('Right', PyImGui.TableColumnFlags.WidthFixed, 55.0)
        PyImGui.table_headers_row()
        for slot, kind, name, _, _ in roster:
            team = _imprisoned_read_team(slot)
            PyImGui.table_next_row()
            PyImGui.table_next_column()
            PyImGui.text(str(slot))
            PyImGui.table_next_column()
            PyImGui.text(f'{name} ({kind})')
            PyImGui.table_next_column()
            if PyImGui.button(f'{"[X]" if team == "left" else "[ ]"}##uw_left_{slot}'):
                _imprisoned_set_team(slot, 'left')
            PyImGui.table_next_column()
            if PyImGui.button(f'{"[X]" if team == "right" else "[ ]"}##uw_right_{slot}'):
                _imprisoned_set_team(slot, 'right')
        PyImGui.end_table()
    left = sum(_imprisoned_read_team(slot) == 'left' for slot, *_ in roster)
    right = len(roster) - left
    PyImGui.text(f'Allocation: {left} LEFT / {right} RIGHT')
    if not left or not right:
        PyImGui.text('WARNING: assign at least one party member to each side.')
    if len(roster) != 7:
        PyImGui.text(f'WARNING: found {len(roster)}/7 secondary members; verify party composition and ShMem.')
    PyImGui.text_wrapped('Settings are saved by party slot. Changes made during an active event '
                          'take effect at the next flag assignment (Planner step 02).')


def _imprisoned_apply_policy() -> None:
    if not _imprisoned_runtime_active or Map.GetMapID() != UW_MAP_ID:
        return
    for account, options in _imprisoned_accounts():
        email = str(account.AccountEmail)
        if email not in _imprisoned_snapshot:
            _imprisoned_snapshot[email] = (bool(options.Following), bool(options.Looting))
        options.Looting = False
        if email in _imprisoned_target_flags:
            x, y = _imprisoned_target_flags[email]
            options.IsFlagged = True
            options.FlagPos.x = x
            options.FlagPos.y = y
            options.FlagFacingAngle = 0.0


def _imprisoned_stage_flags() -> None:
    global _imprisoned_runtime_active
    roster = _imprisoned_slots()
    if len(roster) != 7 or [slot for slot, *_ in roster] != list(range(2, 9)):
        raise RuntimeError('Imprisoned Spirits: party slots 2..8 must be available; check ShMem and hero roster.')
    left = [entry for entry in roster if _imprisoned_read_team(entry[0]) == 'left']
    right = [entry for entry in roster if _imprisoned_read_team(entry[0]) == 'right']
    if not left or not right:
        raise RuntimeError('Imprisoned Spirits: assign at least one party slot to LEFT and RIGHT.')
    if len(left) > len(IMPRISONED_LEFT_POINTS) or len(right) > len(IMPRISONED_RIGHT_POINTS):
        raise RuntimeError('Imprisoned Spirits: too many members for available team coordinates.')
    _imprisoned_target_flags.clear()
    _imprisoned_hero_flags.clear()
    GLOBAL_CACHE.Party.Heroes.UnflagAllHeroes()
    for _, options in _imprisoned_accounts():
        options.IsFlagged = False
        options.AllFlag.x = 0.0
        options.AllFlag.y = 0.0
    for side, members, points in (('LEFT', left, IMPRISONED_LEFT_POINTS),
                                  ('RIGHT', right, IMPRISONED_RIGHT_POINTS)):
        for (slot, kind, name, target, aux), (x, y) in zip(members, points):
            if kind == 'Follower':
                email = str(target.AccountEmail)
                _imprisoned_target_flags[email] = (float(x), float(y))
            else:
                agent_id = int(target)
                GLOBAL_CACHE.Party.Heroes.FlagHero(agent_id, float(x), float(y))
                _imprisoned_hero_flags[agent_id] = (float(x), float(y))
            PySystem.Console.Log(MODULE_NAME,
                f'[Imprisoned] Slot {slot} {name} ({kind}) -> {side} ({x},{y})',
                PySystem.Console.MessageType.Info)
    _imprisoned_runtime_active = True
    _imprisoned_apply_policy()


def _imprisoned_clear_flags() -> None:
    _imprisoned_target_flags.clear()
    _imprisoned_hero_flags.clear()
    GLOBAL_CACHE.Party.Heroes.UnflagAllHeroes()
    for _, options in _imprisoned_accounts():
        options.IsFlagged = False
        options.FlagPos.x = 0.0
        options.FlagPos.y = 0.0
        options.AllFlag.x = 0.0
        options.AllFlag.y = 0.0
    PySystem.Console.Log(MODULE_NAME,
        '[Imprisoned] Cleared left/right flags; party resumes movement.',
        PySystem.Console.MessageType.Info)


def _imprisoned_restore_policy() -> None:
    global _imprisoned_runtime_active, _imprisoned_timer_started
    _imprisoned_clear_flags()
    for account, options in _imprisoned_accounts():
        email = str(account.AccountEmail)
        old = _imprisoned_snapshot.get(email)
        options.Following = old[0] if old is not None else True
        options.Looting = old[1] if old is not None else True
    _imprisoned_runtime_active = False
    _imprisoned_timer_started = None
    _imprisoned_snapshot.clear()


def _imprisoned_start_timer() -> None:
    global _imprisoned_timer_started
    _imprisoned_timer_started = time.monotonic()
    PySystem.Console.Log(MODULE_NAME, "[Imprisoned] Timer started: left 28s, chained souls 90s.", PySystem.Console.MessageType.Info)


def _imprisoned_wait_elapsed(seconds: float) -> BehaviorTree:
    def _tick(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        if Map.GetMapID() != UW_MAP_ID or _imprisoned_timer_started is None:
            return BehaviorTree.NodeState.FAILURE
        return (BehaviorTree.NodeState.SUCCESS if time.monotonic() - _imprisoned_timer_started >= seconds
                else BehaviorTree.NodeState.RUNNING)
    return BehaviorTree(BehaviorTree.ActionNode(
        name=f"Wait until {seconds:g}s from Imprisoned quest start", action_fn=_tick, aftercast_ms=0))


# Planner is the sole execution source: each tuple is independently selectable.
# A selected waypoint deliberately does NOT redo preceding dialogues or routes.
CHAMBER_ROUTE = [(-1505, 6352), (-755, 8982), (1259, 10214),
                 (-3729, 13414), (-5855, 11202), (-5806, 12831)]
MOUNTAIN_PASSAGE = [(-2740, 10133), (-728, 8910), (-1807, 5883),
                    (-3486, 1176), (536, 1321), (3418, 2213),
                    (4911, 1425), (7938, 616), (8001, -2390),
                    (8705, -5293), (6528, -7283)]
MOUNTAIN_RESTORE = [(4455, -7967), (2008, -10290), (-542, -9046),
                    (-2408, -7698), (-4233, -5583), (-6140, -5230),
                    (-7923, -4567)]

# Coordinates and order copied from Restore_Pools / Restore_Pit of original
# Underworld.py; labels are new, not route modifications.
POOLS_RESTORE_ROUTE = [
    (6869, -17771), (2867, -19746), (1753, -14703),
    (-12703, -10990), (-11849, -11986), (-5974, -19739),
    (-7217, -19394), (-5688, -19471),
]
PIT_RESTORE_ROUTE_INITIAL = [(14178, -57)]
PIT_RESTORE_ROUTE_APPROACH = [(15323, 2970), (15393, 406)]
PIT_BRIDGE_PATH = [(15252, 316), (13451, 1123), (13181, 1419), (13076, 1547)]
PIT_RESTORE_ROUTE_FINAL = [
    (13216, 1428), (13896, 3670), (15382, 6581),
    (10620, 2665), (8644, 6242),
]



def _planner_step(name: str, factory: Callable[[], BehaviorTree]) -> tuple[str, Callable[[], BehaviorTree]]:
    """Check map when the selected step starts, without replaying earlier steps."""
    def _build() -> BehaviorTree:
        return BT.Sequence(name=name, children=[_ensure_uw(), factory()])
    return name, _build


def _vanquish_point(name: str, x: float, y: float) -> BehaviorTree:
    """Shards-style native one-point VanquishNode, independently restartable."""
    return BT.VanquishNode(
        steps=[_v(x, y)],
        name=name,
        pause_on_combat=True,
        log=False,
    )


def _planner_move_steps(section: str, label: str,
                        points: list[tuple[int, int]], *,
                        combat: bool = True, first_index: int = 1
                        ) -> list[tuple[str, Callable[[], BehaviorTree]]]:
    """One selectable Planner entry per old Move.XY waypoint.

    Capture coordinates in default arguments to avoid late-binding bugs.
    No hidden 'resume' state: a user-selected point starts at exactly that point.
    """
    result = []
    for index, (x, y) in enumerate(points, start=first_index):
        name = f"{section} - {label} Point {index:02d} ({x}, {y})"
        def _build(x=x, y=y, name=name):
            return _planner_step(name, lambda: (
                _vanquish_point(name, x, y) if combat
                else BT.Move(_v(x, y), pause_on_combat=False, log=False)
            ))[1]()
        result.append((name, _build))
    return result


def _planner_action(section: str, label: str,
                    factory: Callable[[], BehaviorTree]
                    ) -> tuple[str, Callable[[], BehaviorTree]]:
    return _planner_step(f"{section} - {label}", factory)


def _spawn_planner_steps(spawn: int, point: tuple[int, int]) -> list[tuple[str, Callable[[], BehaviorTree]]]:
    result = []
    for attempt in range(1, 5):
        x, y = point
        result.append(_planner_action(
            "Restore Planes", f"0{3 + spawn} - Spawn {spawn} - Approach {attempt:02d} ({x}, {y})",
            lambda x=x, y=y: BT.Move(_v(x, y), log=False),
        ))
        result.append(_planner_action(
            "Restore Planes", f"0{3 + spawn} - Spawn {spawn} - Mindblades check {attempt:02d}",
            lambda spawn=spawn, attempt=attempt: _wait_for_mindblades(f"Spawn {spawn} check {attempt}"),
        ))
        if attempt < 4:
            result.append(_planner_action(
                "Restore Planes", f"0{3 + spawn} - Spawn {spawn} - Retry pause {attempt:02d}",
                lambda: BT.Wait(1_000),
            ))
    return result


# ---------------------------------------------------------------------------
# Remaining original sections: Restore Vale -> Dhuum.
# Keep every operation as a named Planner step. The original script's timing
# and model IDs are retained; high-risk behavior is guarded by timeouts.
# ---------------------------------------------------------------------------
UW_QUEST_ESCORT = 108
UW_QUEST_WRATHFUL = 110
UW_QUEST_UNWANTED = 103
UW_QUEST_SERVANTS = 102
UW_QUEST_NIGHTMARE = 1129
UW_KEEPER_ID = 2373
UW_KING_ID = 2403
UW_SPIRIT_FORM_BUFF = 3134
UW_SERVANTS_SPREAD = ((2559, 20301), (3032, 20148), (2813, 20590),
                      (2516, 19665), (3231, 19472), (3691, 19979),
                      (2039, 20175))
_dhuum_sacrifice_emails: set[str] = set()
_dhuum_min_spiritforms = 2
_dhuum_ready = False
_dhuum_combat_hold = False
_dhuum_policy_snapshot: dict[str, tuple[bool, bool, bool]] = {}
_servants_policy_active = False
_uw_pacifist_active = False
_servants_flag_cache: dict[str, tuple[float, float]] = {}


def _uw_log(message: str, error: bool = False) -> None:
    PySystem.Console.Log(MODULE_NAME, message, PySystem.Console.MessageType.Warning if error else PySystem.Console.MessageType.Info)


def _wait_until(label: str, condition: Callable[[], bool], timeout_s: float = 180.0) -> BehaviorTree:
    started = None
    def _tick(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        nonlocal started
        if not Map.IsMapReady() or Map.GetMapID() != UW_MAP_ID:
            started = None
            return BehaviorTree.NodeState.FAILURE
        if condition():
            started = None
            return BehaviorTree.NodeState.SUCCESS
        now = time.monotonic()
        if started is None:
            started = now
        if now-started > timeout_s:
            _uw_log(f'[{label}] Timeout {timeout_s:.0f}s: condition was never met.', True)
            started = None
            return BehaviorTree.NodeState.FAILURE
        return BehaviorTree.NodeState.RUNNING
    return BehaviorTree(BehaviorTree.ActionNode(name=label, action_fn=_tick, aftercast_ms=0))


def _wait_npc_near(model: int, radius: float, timeout_s: float, label: str) -> BehaviorTree:
    def _condition() -> bool:
        px, py = Player.GetXY()
        return any(Agent.IsValid(a) and int(Agent.GetModelID(a)) == model and
                   (Agent.GetXY(a)[0]-px)**2+(Agent.GetXY(a)[1]-py)**2 <= radius**2
                   for a in AgentArray.GetAgentArray() or [])
    return _wait_until(label, _condition, timeout_s)


def _uw_focus_keeper() -> None:
    candidates = [a for a in AgentArray.GetEnemyArray() or []
                  if Agent.IsValid(a) and Agent.IsAlive(a) and int(Agent.GetModelID(a)) == UW_KEEPER_ID]
    if not candidates:
        _uw_log('[Keeper] No living Keeper of Souls currently detectable.', True)
        return
    px, py = Player.GetXY()
    target = min(candidates, key=lambda a: (Agent.GetXY(a)[0]-px)**2+(Agent.GetXY(a)[1]-py)**2)
    Player.ChangeTarget(target)
    _uw_log(f'[Keeper] Targeted agent {target}.')


def _uw_set_follow_policy(following: bool, looting: bool | None = None) -> None:
    for _account, opts in _horsemen_accounts():
        opts.Following = following
        if looting is not None:
            opts.Looting = looting


def _uw_wrathful_pacifist(enabled: bool) -> None:
    global _uw_pacifist_active
    _uw_pacifist_active = bool(enabled)
    for _account, opts in _horsemen_accounts():
        opts.Combat = not enabled


def _uw_wrathful_tick() -> None:
    if _uw_pacifist_active and Map.GetMapID() == UW_MAP_ID:
        for _account, opts in _horsemen_accounts():
            opts.Combat = False


def _uw_set_combat_policy(enabled: bool) -> None:
    global _dhuum_combat_hold
    _dhuum_combat_hold = not enabled
    for _account, opts in _horsemen_accounts():
        opts.Combat = bool(enabled)


def _uw_set_servants_flags() -> None:
    global _servants_policy_active
    roster = _imprisoned_slots()
    if [entry[0] for entry in roster] != list(range(2, 9)):
        raise RuntimeError('Servants: party roster slots 2..8 are not available.')
    _imprisoned_clear_flags()
    _servants_flag_cache.clear()
    for (_, kind, name, target, _aux), (x, y) in zip(roster, UW_SERVANTS_SPREAD):
        if kind == 'Hero':
            GLOBAL_CACHE.Party.Heroes.FlagHero(int(target), float(x), float(y))
        else:
            account = target
            _servants_flag_cache[str(account.AccountEmail).lower()] = (float(x), float(y))
    _servants_policy_active = True
    _uw_log('[Servants] Set all 7 individual defense flags.')


def _uw_servants_tick() -> None:
    if not _servants_policy_active or Map.GetMapID() != UW_MAP_ID:
        return
    for account, options in _horsemen_accounts():
        point = _servants_flag_cache.get(str(account.AccountEmail).lower())
        if point:
            options.IsFlagged = True
            options.FlagPos.x, options.FlagPos.y = point
            options.FlagFacingAngle = 0.0
        options.Looting = False


def _uw_clear_servants() -> None:
    global _servants_policy_active
    _servants_policy_active = False
    _servants_flag_cache.clear()
    GLOBAL_CACHE.Party.Heroes.UnflagAllHeroes()
    for _account, opts in _horsemen_accounts():
        opts.IsFlagged = False
        opts.FlagPos.x = opts.FlagPos.y = 0.0
        opts.AllFlag.x = opts.AllFlag.y = 0.0
        opts.Following = True
        opts.Looting = True


def _dhuum_settings_load() -> None:
    global _dhuum_sacrifice_emails, _dhuum_min_spiritforms
    raw = _settings.get_str('DhuumBT', 'SacrificeEmails', '') or ''
    _dhuum_sacrifice_emails = {e.strip().lower() for e in raw.split(';') if e.strip()}
    _dhuum_min_spiritforms = max(1, min(8, int(_settings.get_int('DhuumBT', 'MinSpiritforms', 2))))


def _dhuum_settings_save() -> None:
    _settings.set('DhuumBT', 'SacrificeEmails', ';'.join(sorted(_dhuum_sacrifice_emails)))
    _settings.set('DhuumBT', 'MinSpiritforms', int(_dhuum_min_spiritforms))


def _draw_dhuum_config() -> None:
    global _dhuum_min_spiritforms
    PyImGui.text('Dhuum - party setup')
    PyImGui.text_wrapped('Select follower accounts to sacrifice. All unselected followers '
                          'will be flagged as survivors. The leader is never sacrificed.')
    local = str(Player.GetAccountEmail() or '').lower()
    for account, _opts in _horsemen_accounts():
        email = str(account.AccountEmail or '').lower()
        if not email or email == local:
            continue
        label = str(getattr(account.AgentData, 'CharacterName', '') or email)
        updated = PyImGui.checkbox(f'Sacrifice: {label}##dhuum_{email}', email in _dhuum_sacrifice_emails)
        if updated != (email in _dhuum_sacrifice_emails):
            if updated: _dhuum_sacrifice_emails.add(email)
            else: _dhuum_sacrifice_emails.discard(email)
            _dhuum_settings_save()
    new = PyImGui.input_int('Min Spirit Form accounts', int(_dhuum_min_spiritforms))
    if isinstance(new, tuple): new = new[-1]
    new = max(1, min(8, int(new)))
    if new != _dhuum_min_spiritforms:
        _dhuum_min_spiritforms = new
        _dhuum_settings_save()
    if not _dhuum_sacrifice_emails:
        PyImGui.text_wrapped('WARNING: no sacrifice account selected; Dhuum flag step will fail safely.')
    PyImGui.separator()
    PyImGui.text_wrapped('Armor switching from the legacy EquippedArmor.json is not automated '
                          'in this BT version. Set the desired armor manually before the fight.')
    PyImGui.text_wrapped('Dhuum Helper must be enabled on the selected accounts.')


def _dhuum_validate_party() -> None:
    local = str(Player.GetAccountEmail() or '').lower()
    follower_emails = {str(account.AccountEmail or '').lower()
                       for account, _opts in _horsemen_accounts() if str(account.AccountEmail or '').lower() != local}
    if not _dhuum_sacrifice_emails:
        raise RuntimeError('Select sacrifice accounts in the Dhuum tab first.')
    if _dhuum_sacrifice_emails - follower_emails:
        raise RuntimeError(f'Dhuum sacrifice account(s) missing: {_dhuum_sacrifice_emails - follower_emails}')
    if _dhuum_min_spiritforms > len(follower_emails) + 1:
        raise RuntimeError('Dhuum: Spirit Form threshold exceeds connected player count.')


def _dhuum_flag_groups() -> None:
    _dhuum_validate_party()
    local = str(Player.GetAccountEmail() or '').lower()
    GLOBAL_CACHE.Party.Heroes.UnflagAllHeroes()
    for account, opts in _horsemen_accounts():
        email = str(account.AccountEmail or '').lower()
        if email == local: continue
        x, y = (-15386.0, 17295.0) if email in _dhuum_sacrifice_emails else (-14374.0, 17261.0)
        opts.Following = False
        opts.IsFlagged = True
        opts.FlagPos.x, opts.FlagPos.y = x, y
        opts.FlagFacingAngle = 0.0
        _uw_log(f'[Dhuum] {email} -> {"sacrifice" if email in _dhuum_sacrifice_emails else "survivor"} ({x:.0f},{y:.0f})')
    GLOBAL_CACHE.Party.Heroes.FlagAllHeroes(-14374.0, 17261.0)


def _dhuum_start_fight() -> None:
    global _dhuum_ready
    _dhuum_validate_party()
    _dhuum_ready = True
    _dhuum_policy_snapshot.clear()
    for account, opts in _horsemen_accounts():
        _dhuum_policy_snapshot[str(account.AccountEmail).lower()] = (
            bool(opts.Combat), bool(opts.Following), bool(opts.Looting))
    _uw_set_combat_policy(False)


def _dhuum_tick() -> None:
    if not _dhuum_ready or Map.GetMapID() != UW_MAP_ID:
        return
    for account, opts in _horsemen_accounts():
        email = str(account.AccountEmail or '').lower()
        if _dhuum_combat_hold:
            opts.Combat = False
        if email != str(Player.GetAccountEmail() or '').lower():
            x, y = (-15386.,17295.) if email in _dhuum_sacrifice_emails else (-14374.,17261.)
            opts.IsFlagged = True
            opts.FlagPos.x, opts.FlagPos.y = x, y
            opts.Following = False


def _dhuum_spirit_count() -> int:
    count = 0
    for account, _opts in _horsemen_accounts():
        try:
            if int(account.AgentData.Map.MapID) != UW_MAP_ID:
                continue
            if any(int(buff.SkillId) == UW_SPIRIT_FORM_BUFF for buff in account.AgentData.Buffs.Buffs):
                count += 1
        except (AttributeError, TypeError, ValueError):
            pass
    return count


def _dhuum_enable_combat_if_ready() -> bool:
    if _dhuum_spirit_count() < _dhuum_min_spiritforms:
        return False
    _uw_set_combat_policy(True)
    _uw_log(f'[Dhuum] Spirit Form ready: {_dhuum_spirit_count()}/{_dhuum_min_spiritforms}; combat enabled.')
    return True


def _dhuum_chest_id() -> int:
    for agent_id in AgentArray.GetAgentArray() or []:
        if not Agent.IsValid(agent_id) or not Agent.IsGadget(agent_id):
            continue
        if 'underworld chest' not in str(Agent.GetNameByID(agent_id) or '').strip().lower():
            continue
        x, y = Agent.GetXY(agent_id)
        if (x+14381.)**2 + (y-17283.)**2 <= 300.**2:
            return int(agent_id)
    return 0


def _dhuum_finish() -> None:
    global _dhuum_ready, _dhuum_combat_hold
    _dhuum_ready = False
    _dhuum_combat_hold = False
    GLOBAL_CACHE.Party.Heroes.UnflagAllHeroes()
    local = str(Player.GetAccountEmail() or '').lower()
    for account, opts in _horsemen_accounts():
        email = str(account.AccountEmail or '').lower()
        original = _dhuum_policy_snapshot.get(email)
        opts.IsFlagged = False
        opts.FlagPos.x = opts.FlagPos.y = 0.0
        opts.AllFlag.x = opts.AllFlag.y = 0.0
        opts.Combat = original[0] if original else True
        opts.Following = original[1] if original else True
        opts.Looting = original[2] if original else True
    _dhuum_policy_snapshot.clear()


def _dhuum_chest_interaction() -> BehaviorTree:
    def _build(_node: BehaviorTree.Node) -> BehaviorTree:
        chest = _dhuum_chest_id()
        if not chest:
            return BT.Sequence(name='Missing chest', children=[
                _action('Missing UW Chest', lambda: (_ for _ in ()).throw(RuntimeError('UW chest missing')))])
        return BTShared.SendAndWait(
            command=SharedCommandType.InteractWithTarget,
            params=(float(chest), 0., 0., 0.),
            include_self=True, timeout_ms=30_000, poll_interval_ms=150, log=False)
    return BT.Subtree(name='Loot chest on party accounts', subtree_fn=_build)


def _dhuum_enable_helper() -> BehaviorTree:
    return BTShared.SendAndWait(
        command=SharedCommandType.EnableWidget,
        extra_data=('Dhuum Helper', '', '', ''),
        include_self=True, timeout_ms=30_000, poll_interval_ms=150, log=False)


def _uw_route(section: str, points: tuple[tuple[int, int], ...], prefix: str) -> list[tuple[str, Callable[[], BehaviorTree]]]:
    return [_planner_action(section, f'{prefix} {index:02d} ({x}, {y})',
                            lambda x=x, y=y: BT.Move(_v(x,y), log=False))
            for index, (x,y) in enumerate(points, 1)]


def _keeper_approach_steps(number: int, coords: tuple[tuple[int, int], ...]) -> list[tuple[str, Callable[[], BehaviorTree]]]:
    result = []
    for i, (x,y) in enumerate(coords, 1):
        result.append(_planner_action('Unwanted Guests', f'{number:02d} - Keeper {number} approach {i} ({x},{y})',
                                      lambda x=x,y=y: BT.Move(_v(x,y), log=False)))
    result.append(_planner_action('Unwanted Guests', f'{number:02d} - Target Keeper {number}',
                                  lambda: _action('Focus Keeper of Souls', _uw_focus_keeper)))
    result.append(_planner_action('Unwanted Guests', f'{number:02d} - Target settle',lambda: BT.Wait(500)))
    result.append(_planner_action('Unwanted Guests', f'{number:02d} - Retarget Keeper {number}',
                                  lambda: _action('Focus Keeper of Souls again', _uw_focus_keeper)))
    return result

def _uw_follow_king() -> BehaviorTree:
    started = None
    last_move = 0.0
    def _tick(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        nonlocal started, last_move
        if Map.GetMapID() != UW_MAP_ID:
            return BehaviorTree.NodeState.FAILURE
        now = time.monotonic()
        if started is None:
            started = now
        if now-started > 600.:
            _uw_log('[Dhuum] King did not reach destination within 600 seconds.',True)
            return BehaviorTree.NodeState.FAILURE
        kings = [a for a in AgentArray.GetAgentArray() or []
                 if Agent.IsValid(a) and int(Agent.GetModelID(a)) == UW_KING_ID]
        if not kings:
            return BehaviorTree.NodeState.RUNNING
        king = kings[0]
        x,y = Agent.GetXY(king)
        if (x+11278.)**2 + (y-17297.)**2 < 1500.**2:
            return BehaviorTree.NodeState.SUCCESS
        px,py = Player.GetXY()
        if (px-x)**2+(py-y)**2>1000.**2 and now-last_move>.5:
            Player.Move(x,y)
            last_move=now
        return BehaviorTree.NodeState.RUNNING
    return BehaviorTree(BehaviorTree.ActionNode(name='Follow King Frozenwind',action_fn=_tick,aftercast_ms=0))


def get_execution_steps() -> list[tuple[str, Callable[[], BehaviorTree]]]:
    """Shards-style selectable Planner steps, without duplicate section trees.

    Important: jumping to a waypoint does not recreate previous preconditions.
    For testing, select the required setup/quest-accept step first when needed.
    """
    return [
        ("Initialize Bot", InitializeBot),
        *_entry_steps(),

        _planner_action("Clear the Chamber", "01 - Configure blacklists", lambda: BT.Sequence(
            name="Chamber combat filters", children=[
                _blacklist("obsidian guardian", True),
                _blacklist("vengeful aatxe", True),
                _blacklist("chained soul", True),
                _blacklist("wastfull spirit", False),
                _blacklist("obsidian behemoth", False),
                _blacklist("banished dream rider", False),
            ])),
        _planner_action("Clear the Chamber", "02 - Accept quest (101)",
                        lambda: _quest_npc(NPC_LOST_SOUL, 0x806501, QUEST_CLEAR, "Accept Chamber quest")),
        _planner_action("Clear the Chamber", "03 - Approach (769, 6564)",
                        lambda: BT.Move(_v(769, 6564), pause_on_combat=False, log=False)),
        _planner_action("Clear the Chamber", "04 - Settle 5 seconds", lambda: BT.Wait(5_000)),
        *_planner_move_steps("Clear the Chamber", "05 - Route", CHAMBER_ROUTE),
        _planner_action("Clear the Chamber", "06 - Verify quest complete (101)",
                        lambda: _wait_quest_completed(QUEST_CLEAR, timeout_ms=90_000)),
        _planner_action("Clear the Chamber", "07 - Claim Reaper reward",
                        lambda: BT.MoveAndDialogByModelID(NPC_REAPER, dialog_id=0x806507, multi_account=True)),
        _planner_action("Clear the Chamber", "08 - Reward settle", lambda: BT.Wait(1_000)),
        _planner_action("Clear the Chamber", "09 - Accept Restore Monuments (109)",
                        lambda: _quest_npc(NPC_REAPER, 0x806D01, QUEST_RESTORE_MONUMENTS, "Accept Monuments")),
        _planner_action("Clear the Chamber", "10 - Completed", lambda: _record("Clear the Chamber")),

        *_planner_move_steps("Pass the Mountains", "Route", MOUNTAIN_PASSAGE),
        _planner_action("Pass the Mountains", "Completed", lambda: _record("Pass the Mountains")),

        *_planner_move_steps("Restore Mountains", "Route", MOUNTAIN_RESTORE),
        _planner_action("Restore Mountains", "Settle 5 seconds", lambda: BT.Wait(5_000)),
        _planner_action("Restore Mountains", "Completed", lambda: _record("Restore Mountains")),

        _planner_action("Demon Assassin", "01 - Approach Reaper (-8250, -5171)",
                        lambda: BT.Move(_v(-8250, -5171), log=False)),
        _planner_action("Demon Assassin", "02 - Accept quest (104)",
                        lambda: _quest_npc(NPC_REAPER, 0x806801, QUEST_DEMON_ASSASSIN, "Accept Demon Assassin")),
        _planner_action("Demon Assassin", "03 - Fight (-3645, -5820)",
                        lambda: _vanquish_point("Demon Assassin fight", -3645, -5820)),
        _planner_action("Demon Assassin", "04 - Verify quest complete (104)",
                        lambda: _wait_quest_completed(QUEST_DEMON_ASSASSIN, timeout_ms=120_000)),
        _planner_action("Demon Assassin", "05 - Completed", lambda: _record("Deamon Assassin")),

        _planner_action("Restore Planes", "01 - Blacklist Dream Rider",
                        lambda: _blacklist("banished dream rider", True)),
        _planner_action("Restore Planes", "02 - Bypass Rider (13837, -14736)",
                        lambda: BT.Move(_v(13837, -14736), pause_on_combat=True, log=False)),
        _planner_action("Restore Planes", "03 - Unblacklist Dream Rider",
                        lambda: _blacklist("banished dream rider", False)),
        *_spawn_planner_steps(1, (13790, -15568)),
        *_spawn_planner_steps(2, (11287, -17921)),
        _planner_action("Restore Planes", "06 - Completed", lambda: _record("Restore Planes")),

        # Matches original encounter, excluding optional follower quest reward dialogs.
        # The seven early spread coordinates were DECLARED but never applied
        # in the original HeroAI version; disable following anchors followers
        # at their current positions instead. Each step is Planner-selectable.
        _planner_action("The Four Horsemen", "00 - Check Obsidian Guardian blacklist",
                        _guardian_blacklist_checkpoint),
        _planner_action("The Four Horsemen", "01 - Approach staging point (13473, -12091)",
                        lambda: _vanquish_point("Horsemen staging", 13473, -12091)),
        _planner_action("The Four Horsemen", "02 - Staging settle 10 seconds",
                        lambda: BT.Wait(10_000)),
        _planner_action("The Four Horsemen", "03 - Disable following and loot; anchor followers",
                        lambda: _action("4H staging options", _horsemen_start_staging)),
        _planner_action("The Four Horsemen", "04 - Approach Chaos Reaper (11371, -17990)",
                        lambda: BT.Move(_v(11371, -17990), pause_on_combat=False, log=False)),
        _planner_action("The Four Horsemen", "05 - Accept quest (106)",
                        lambda: _quest_npc(NPC_REAPER, 0x806A01,
                                           QUEST_FOUR_HORSEMEN, "Accept Four Horsemen")),
        _planner_action("The Four Horsemen", "06 - Spawn settle 32 seconds",
                        lambda: BT.Wait(32_000)),
        _planner_action("The Four Horsemen", "07 - Return to Chaos Reaper",
                        lambda: BT.Move(_v(11371, -17990), pause_on_combat=False, log=False)),
        _planner_action("The Four Horsemen", "08 - Reaper teleport to Lab (0x8D)",
                        lambda: BT.MoveAndDialogByModelID(
                            NPC_REAPER, dialog_id=0x8D, multi_account=False, log=False)),
        _planner_action("The Four Horsemen", "09 - Clear staging flags",
                        lambda: BT.UnflagAllHeroes(log=False)),
        _planner_action("The Four Horsemen", "10 - Resume following, keep looting off",
                        lambda: _action("4H defense following", _horsemen_start_defense)),
        _planner_action("The Four Horsemen", "11 - Move to Labyrinth Reaper (-5782, 12819)",
                        lambda: BT.Move(_v(-5782, 12819), pause_on_combat=False, log=False)),
        _planner_action("The Four Horsemen", "12 - Teleport settle 1 second",
                        lambda: BT.Wait(1_000)),
        _planner_action("The Four Horsemen", "13 - Reaper teleport to Chaos (0x8B)",
                        lambda: BT.MoveAndDialogByModelID(
                            NPC_REAPER, dialog_id=0x8B, multi_account=False, log=False)),
        _planner_action("The Four Horsemen", "14 - Teleport settle 1 second",
                        lambda: BT.Wait(1_000)),
        _planner_action("The Four Horsemen", "15 - Unflag old positions",
                        lambda: BT.UnflagAllHeroes(log=False)),
        # BT.FlagHero distinguishes local hero indices from HeroAI party slots
        # by total hero count; with mixed players/heroes this is not a reliable
        # way to flag all party members. FlagAllHeroes explicitly flags all
        # native heroes and sets the HeroAI group flag for remote accounts.
        _planner_action("The Four Horsemen", "16 - Flag ALL heroes and multibox followers at defense",
                        lambda: BT.FlagAllHeroes(
                            x=HORSEMEN_HOLD_X, y=HORSEMEN_HOLD_Y)),
        _planner_action("The Four Horsemen", "17 - Move leader to defense position",
                        lambda: BT.Move(_v(HORSEMEN_HOLD_X, HORSEMEN_HOLD_Y),
                                        pause_on_combat=False, log=False)),
        _planner_action("The Four Horsemen", "18 - Hold leader until quest 106 complete",
                        lambda: _horsemen_hold_until_complete()),
        _planner_action("The Four Horsemen", "19 - Clear despawned target",
                        _horsemen_clear_stale_target),
        _planner_action("The Four Horsemen", "20 - Clear flags",
                        lambda: BT.UnflagAllHeroes(log=False)),
        _planner_action("The Four Horsemen", "21 - Recover 10 seconds",
                        lambda: BT.Wait(10_000)),
        _planner_action("The Four Horsemen", "22 - Return to Chaos Reaper",
                        lambda: BT.Move(_v(11371, -17990), pause_on_combat=False, log=False)),
        _planner_action("The Four Horsemen", "23 - Claim local reward (0x806A07)",
                        lambda: BT.MoveAndDialogByModelID(
                            NPC_REAPER, dialog_id=0x806A07, multi_account=False, log=False)),
        _planner_action("The Four Horsemen", "24 - Restore following and looting",
                        lambda: _action("4H restore options", _horsemen_restore_policy)),
        _planner_action("The Four Horsemen", "25 - Verify quest 106 completed",
                        lambda: _wait_quest_completed(QUEST_FOUR_HORSEMEN, timeout_ms=10_000)),
        _planner_action("The Four Horsemen", "26 - Record completion",
                        lambda: _record("The Four Horsemen")),

        # Source: Underworld.py Restore_Pools. One named Planner entry per
        # old Move.XY. Unlike Four Horsemen, this section has no quest dialog.
        _planner_action("Restore Pools", "01 - Restore normal combat filters",
                        lambda: BT.Sequence(name="Restore Pools policy", children=[
                            _action("Restore follower following and looting", _horsemen_restore_policy),
                            _blacklist("banished dream rider", True),
                        ])),
        *_planner_move_steps("Restore Pools", "02 - Route", POOLS_RESTORE_ROUTE),
        _planner_action("Restore Pools", "03 - Record completion",
                        lambda: _record("Restore Pools")),

        # Terrorweb Queen: original quest ID 107, accept dialog 0x806B01,
        # reward dialog 0x806B07, Reaper teleport dialog 0x8B.
        # Followers do NOT claim quests or rewards, per the latest user choice.
        _planner_action("Terrorweb Queen", "00 - Check Obsidian Guardian blacklist",
                        _guardian_blacklist_checkpoint),
        _planner_action("Terrorweb Queen", "01 - Move to Pools Reaper (-6957, -19478)",
                        lambda: _vanquish_point("Pools Reaper approach", -6957, -19478)),
        _planner_action("Terrorweb Queen", "02 - Accept quest 107 (0x806B01)",
                        lambda: _quest_npc(NPC_REAPER, 0x806B01, QUEST_TERRORWEB_QUEEN,
                                           "Accept Terrorweb Queen")),
        _planner_action("Terrorweb Queen", "03 - Approach Queen (-12432, -15874)",
                        lambda: _vanquish_point("Terrorweb Queen fight", -12432, -15874)),
        _planner_action("Terrorweb Queen", "04 - Return to Pools Reaper (-6957, -19478)",
                        lambda: _vanquish_point("Return to Pools Reaper", -6957, -19478)),
        _planner_action("Terrorweb Queen", "05 - Wait 10 seconds",
                        lambda: BT.Wait(10_000)),
        _planner_action("Terrorweb Queen", "06 - Claim leader reward (0x806B07)",
                        lambda: BT.MoveAndDialogByModelID(
                            NPC_REAPER, dialog_id=0x806B07, multi_account=False, log=False)),
        _planner_action("Terrorweb Queen", "07 - Wait 3 seconds",
                        lambda: BT.Wait(3_000)),
        _planner_action("Terrorweb Queen", "08 - Reaper teleport (0x8B)",
                        lambda: BT.MoveAndDialogByModelID(
                            NPC_REAPER, dialog_id=0x8B, multi_account=False, log=False)),
        _planner_action("Terrorweb Queen", "09 - Record completion",
                        lambda: _record("Terrorweb Queen")),

        # Restore Pit: preserve original waypoints exactly, including the
        # four-point bridge passage. Named bridge node can be restarted alone.
        *_planner_move_steps("Restore Pit", "01 - First approach", PIT_RESTORE_ROUTE_INITIAL),
        _planner_action("Restore Pit", "02 - Remove Dream Rider blacklist",
                        lambda: _blacklist("banished dream rider", False)),
        *_planner_move_steps("Restore Pit", "03 - Approach bridge", PIT_RESTORE_ROUTE_APPROACH),
        _planner_action("Restore Pit", "04 - Cross bridge (MoveDirect)",
                        lambda: BT.MoveDirect(
                            [_v(x,y) for x,y in PIT_BRIDGE_PATH],
                            pause_on_combat=True,
                            log=False)),
        *_planner_move_steps("Restore Pit", "05 - Final route", PIT_RESTORE_ROUTE_FINAL),
        _planner_action("Restore Pit", "06 - Wait 3 seconds",
                        lambda: BT.Wait(3_000)),
        _planner_action("Restore Pit", "07 - Record completion",
                        lambda: _record("Restore Pit")),

        # Imprisoned Spirits: configured party-slot teams, timed left/right phases,
        # temporary Chained Soul blacklist exception, teleport back to Chamber.
        _planner_action("Imprisoned Spirits", "01 - Approach staging (13212, 4978)",
                        lambda: BT.Move(_v(13212, 4978), log=False)),
        _planner_action("Imprisoned Spirits", "02 - Assign left/right party-slot flags",
                        lambda: _action("Set original Imprisoned teams", _imprisoned_stage_flags)),
        _planner_action("Imprisoned Spirits", "03 - Approach Bone Pits Reaper (8692, 6292)",
                        lambda: BT.Move(_v(8692, 6292), log=False)),
        _planner_action("Imprisoned Spirits", "04 - Reaper final approach (8666, 6308)",
                        lambda: BT.Move(_v(8666, 6308), log=False)),
        _planner_action("Imprisoned Spirits", "05 - Accept quest 105 (0x806901)",
                        lambda: _quest_npc(NPC_REAPER, 0x806901, IMPRISONED_QUEST_ID, "Accept Imprisoned Spirits")),
        _planner_action("Imprisoned Spirits", "06 - Start timed event clock",
                        lambda: _action("Start Imprisoned clock", _imprisoned_start_timer)),
        _planner_action("Imprisoned Spirits", "07 - Move toward left side (13652, 6117)",
                        lambda: BT.Move(_v(13652, 6117), pause_on_combat=False, log=False)),
        # Extend the original leader sweep into the LEFT defense area.
        # This waypoint is drawn from the original left-team flag positions.
        _planner_action("Imprisoned Spirits", "07A - Push deeper left (13985, 6840)",
                        lambda: BT.Move(_v(13985, 6840), pause_on_combat=False, log=False)),
        _planner_action("Imprisoned Spirits", "08 - Wait for 28-second mark",
                        lambda: _imprisoned_wait_elapsed(28.0)),
        _planner_action("Imprisoned Spirits", "09 - Release left/right team flags",
                        lambda: _action("Release Imprisoned flags", _imprisoned_clear_flags)),
        _planner_action("Imprisoned Spirits", "10 - Move toward right side (12593, 1814)",
                        lambda: BT.Move(_v(12593, 1814), pause_on_combat=False, log=False)),
        # Push the leader closer to the RIGHT defense positions before holding.
        _planner_action("Imprisoned Spirits", "10A - Push deeper right (12150, 2139)",
                        lambda: BT.Move(_v(12150, 2139), pause_on_combat=False, log=False)),
        _planner_action("Imprisoned Spirits", "11 - Hold right side 40 seconds",
                        lambda: BT.Wait(40_000)),
        _planner_action("Imprisoned Spirits", "12 - Wait for 90-second mark",
                        lambda: _imprisoned_wait_elapsed(90.0)),
        _planner_action("Imprisoned Spirits", "13 - Allow Chained Soul targets",
                        lambda: _blacklist("chained soul", False)),
        _planner_action("Imprisoned Spirits", "14 - Move toward center (10437, 5005)",
                        lambda: BT.Move(_v(10437, 5005), log=False)),
        # Explicit full deflag after reaching center: clear native GW hero flags,
        # HeroAI account flags/AllFlag, AND the event's persistent flag cache.
        # Both children are necessary: the runtime policy would otherwise
        # reapply cached follower flags on subsequent frames.
        _planner_action("Imprisoned Spirits", "14A - Full party deflag after center",
                        lambda: BT.Sequence(name="Imprisoned full deflag", children=[
                            BT.UnflagAllHeroes(log=False),
                            _action("Clear Imprisoned flag cache", _imprisoned_clear_flags),
                        ])),
        _planner_action("Imprisoned Spirits", "15 - Verify quest 105 completed",
                        lambda: _wait_quest_completed(IMPRISONED_QUEST_ID, timeout_ms=360_000)),
        _planner_action("Imprisoned Spirits", "16 - Re-blacklist Chained Souls",
                        lambda: _blacklist("chained soul", True)),
        _planner_action("Imprisoned Spirits", "17 - Restore party looting/following",
                        lambda: _action("Restore party options", _imprisoned_restore_policy)),
        _planner_action("Imprisoned Spirits", "18 - Return to Bone Pits Reaper (8692, 6292)",
                        lambda: BT.Move(_v(8692, 6292), log=False)),
        _planner_action("Imprisoned Spirits", "19 - Teleport to Chamber (0x8D)",
                        lambda: BT.MoveAndDialogByModelID(
                            NPC_REAPER, dialog_id=0x8D, multi_account=False, log=False)),
        _planner_action("Imprisoned Spirits", "20 - Record completion",
                        lambda: _record("Imprisoned Spirits")),

        # Restore Vale - Escort of Souls (quest 108).
        _planner_action('Restore Vale', '01 - Travel to Reaper (-5806,12831)',
                        lambda: BT.Move(_v(-5806,12831), log=False)),
        _planner_action('Restore Vale', '02 - Reaper dialog 0x806C03',
                        lambda: BT.MoveAndDialogByModelID(NPC_REAPER, dialog_id=0x806C03, log=False)),
        _planner_action('Restore Vale', '03 - Accept Escort of Souls (108)',
                        lambda: _quest_npc(NPC_REAPER,0x806C01,UW_QUEST_ESCORT,'Accept Escort of Souls')),
        *_uw_route('Restore Vale', ((-8660,5655),(-9431,1659),(-11123,2531),
                                     (-11926,1146),(-10691,98),(-15424,1319),(-13246,5110)), '04 - Travel'),
        _planner_action('Restore Vale','05 - Settle 3s',lambda: BT.Wait(3000)),
        _planner_action('Restore Vale','06 - Record',lambda: _record('Restore Vale')),

        # Wrathful Spirits - first pass is pacifist around Tortured Spirits.
        _planner_action('Wrathful Spirits','01 - Approach Reaper (5755,12769)',
                        lambda: BT.Move(_v(5755,12769),log=False)),
        _planner_action('Wrathful Spirits','02 - Reaper dialog 0x806E03',
                        lambda: BT.MoveAndDialogByModelID(NPC_REAPER,dialog_id=0x806E03,log=False)),
        _planner_action('Wrathful Spirits','03 - Accept quest 110',
                        lambda: _quest_npc(NPC_REAPER,0x806E01,UW_QUEST_WRATHFUL,'Accept Wrathful Spirits')),
        _planner_action('Wrathful Spirits','03A - Disable combat for pacifist approach',
                        lambda: _action('Wrathful pacifist combat',lambda: _uw_wrathful_pacifist(True))),
        _planner_action('Wrathful Spirits','04 - Blacklist tortured spirit',
                        lambda: _blacklist('tortured spirit',True)),
        _planner_action('Wrathful Spirits','05 - Disable followers during first approach',
                        lambda: _action('Disable following',lambda: _uw_set_follow_policy(False))),
        _planner_action('Wrathful Spirits','06 - Cross pacifist part (-13422,973)',
                        lambda: BT.Move(_v(-13422,973),pause_on_combat=False,log=False)),
        _planner_action('Wrathful Spirits','06A - Re-enable combat',
                        lambda: _action('Wrathful restore combat',lambda: _uw_wrathful_pacifist(False))),
        _planner_action('Wrathful Spirits','07 - Restore following',
                        lambda: _action('Restore following',lambda: _uw_set_follow_policy(True))),
        _planner_action('Wrathful Spirits','08 - Unblacklist tortured spirit',
                        lambda: _blacklist('tortured spirit',False)),
        *_uw_route('Wrathful Spirits', ((-13791,1642),(-12889,963),(-11445,1154),
            (-10554,1695),(-9481,963),(-9949,177),(-11498,-173),(-12677,-205),
            (-13622,336),(-12974,4116),(-14184,7279),(-15055,3755),(-13409,4933)), '09 - Loop'),
        _planner_action('Wrathful Spirits','10 - Reaper approach (5755,12769)',
                        lambda: BT.Move(_v(5755,12769),log=False)),
        _planner_action('Wrathful Spirits','11 - Verify quest 110 completed',
                        lambda: _wait_quest_completed(UW_QUEST_WRATHFUL,timeout_ms=120_000)),
        _planner_action('Wrathful Spirits','12 - Claim reward leader 0x806E07',
                        lambda: BT.MoveAndDialogByModelID(NPC_REAPER,dialog_id=0x806E07,log=False)),
        _planner_action('Wrathful Spirits','13 - Teleport Chamber 0x8D',
                        lambda: BT.MoveAndDialogByModelID(NPC_REAPER,dialog_id=0x8D,log=False)),
        _planner_action('Wrathful Spirits','14 - Settle 3s',lambda: BT.Wait(3000)),
        _planner_action('Wrathful Spirits','15 - Record',lambda: _record('Wrathful Spirits')),

        # Unwanted Guests: original six-Keeper route and target cadence.
        # The original script leaves the party at the first staging point while
        # the leader accepts the quest at the Reaper. Unlike the legacy CB
        # CLOSE_TO_AGGRO mode (a no-op under HeroAI), explicitly protect the
        # stationary party using BT's shared hero/follower flags and keep Combat on.
        _planner_action('Unwanted Guests','01 - Blacklist Obsidian Behemoth',
                        lambda: _blacklist('obsidian behemoth',True)),
        _planner_action('Unwanted Guests','02 - Stage party near Keeper 1 (-2965,10260)',
                        lambda: BT.Move(_v(-2965,10260), log=False)),
        _planner_action('Unwanted Guests','03 - Wait for party (5s)',lambda: BT.Wait(5000)),
        _planner_action('Unwanted Guests','04 - Enable combat for followers',
                        lambda: _action('Enable HeroAI combat',lambda: _uw_set_combat_policy(True))),
        _planner_action('Unwanted Guests','04A - Flag ALL secondary members at Keeper 1',
                        lambda: BT.FlagAllHeroes(x=-2965,y=10260)),
        _planner_action('Unwanted Guests','04B - Disable follower following',
                        lambda: _action('Hold follower position',lambda: _uw_set_follow_policy(False))),
        _planner_action('Unwanted Guests','05 - Leader goes to Reaper (-5806,12831)',
                        lambda: BT.Move(_v(-5806,12831),log=False)),
        _planner_action('Unwanted Guests','06 - Accept quest 103',
                        lambda: _quest_npc(NPC_REAPER,0x806701,UW_QUEST_UNWANTED,'Accept Unwanted Guests')),
        # The original issues THREE focus commands for Keeper 1, with 500ms
        # between calls. This is kept separate from the fixed 20s defense hold.
        _planner_action('Unwanted Guests','07A - Focus Keeper 1 (first)',
                        lambda: _action('Focus Keeper 1 first',_uw_focus_keeper)),
        _planner_action('Unwanted Guests','07B - Wait 0.5s',lambda: BT.Wait(500)),
        _planner_action('Unwanted Guests','07C - Focus Keeper 1 (second)',
                        lambda: _action('Focus Keeper 1 second',_uw_focus_keeper)),
        _planner_action('Unwanted Guests','07D - Wait 0.5s',lambda: BT.Wait(500)),
        _planner_action('Unwanted Guests','07E - Focus Keeper 1 (third)',
                        lambda: _action('Focus Keeper 1 third',_uw_focus_keeper)),
        _planner_action('Unwanted Guests','07F - Hold Keeper 1 defense 20s',lambda: BT.Wait(20_000)),
        _planner_action('Unwanted Guests','08A - Clear initial party defense flags',
                        lambda: BT.UnflagAllHeroes()),
        _planner_action('Unwanted Guests','08B - Restore follower following',
                        lambda: _action('Restore follower following',lambda: _uw_set_follow_policy(True))),
        # Original teleports from the Reaper to Vale before Keeper 2.
        _planner_action('Unwanted Guests','09 - Teleport Vale 0x91',
                        lambda: BT.MoveAndDialogByModelID(NPC_REAPER,dialog_id=0x91,log=False)),
        *_keeper_approach_steps(2, ((-12953,750),(-8371,4865))),
        _planner_action('Unwanted Guests','10 - Keeper 2 depart (-7589,6801)',
                        lambda: BT.Move(_v(-7589,6801),log=False)),
        *_keeper_approach_steps(3, ((-4095,12964),)),
        _planner_action('Unwanted Guests','11 - Keeper 3 depart (-647,13356)',
                        lambda: BT.Move(_v(-647,13356),log=False)),
        *_keeper_approach_steps(4, ((1098,12215),)),
        _planner_action('Unwanted Guests','12 - Keeper 4 depart (3113,9503)',
                        lambda: BT.Move(_v(3113,9503),log=False)),
        *_keeper_approach_steps(5, ((1586,10362),)),
        _planner_action('Unwanted Guests','13 - Keeper 5 depart (367,7214)',
                        lambda: BT.Move(_v(367,7214),log=False)),
        *_keeper_approach_steps(6, ((-3125,916),(-597,-537),(-344,2155))),
        _planner_action('Unwanted Guests','14 - Keeper 6 depart (1256,4623)',
                        lambda: BT.Move(_v(1256,4623),log=False)),
        # The original records here without checking the quest. In BT, protect
        # downstream Restore Wastes from silent partial completion.
        _planner_action('Unwanted Guests','14A - Verify quest 103 completed',
                        lambda: _wait_quest_completed(UW_QUEST_UNWANTED, timeout_ms=120_000)),
        _planner_action('Unwanted Guests','15 - Remove Behemoth blacklist',
                        lambda: _blacklist('obsidian behemoth',False)),
        _planner_action('Unwanted Guests','16 - Record',lambda: _record('Unwanted Guests')),

        *_uw_route('Restore Wastes', ((3891,7572),(4106,16031),(2486,21723),
             (-1452,21202),(542,18310)), '01 - Travel'),
        _planner_action('Restore Wastes','02 - Settle 3s',lambda: BT.Wait(3000)),
        _planner_action('Restore Wastes','03 - Record',lambda: _record('Restore Wastes')),

        # Servants of Grenth: spread 7 secondary members using their actual
        # roster positions, not BT.FlagHero's mixed hero/player numbering.
        _planner_action('Servants of Grenth','01 - Staging (2700,19952)',
                        lambda: BT.Move(_v(2700,19952),log=False)),
        _planner_action('Servants of Grenth','02 - Spread defense flags (all 7 slots)',
                        lambda: _action('Spread Servants flags',_uw_set_servants_flags)),
        _planner_action('Servants of Grenth','03 - Leader approaches Reaper (554,18384)',
                        lambda: BT.Move(_v(554,18384),log=False)),
        _planner_action('Servants of Grenth','04 - Accept quest 102',
                        lambda: _quest_npc(NPC_REAPER,0x806601,UW_QUEST_SERVANTS,'Accept Servants of Grenth')),
        _planner_action('Servants of Grenth','05 - Return to defense (2700,19952)',
                        lambda: BT.Move(_v(2700,19952),log=False)),
        _planner_action('Servants of Grenth','06 - Clear defense flags',
                        lambda: BT.Sequence(name='Clear Servants flags',children=[BT.UnflagAllHeroes(),
                            _action('Clear Servants cache',_uw_clear_servants)])),
        _planner_action('Servants of Grenth','07 - Wait quest 102 completed',
                        lambda: _wait_quest_completed(UW_QUEST_SERVANTS,timeout_ms=360_000)),
        _planner_action('Servants of Grenth','08 - Reward settle 30 seconds',
                        lambda: BT.Wait(30_000)),
        _planner_action('Servants of Grenth','09 - Reaper approach (554,18384)',
                        lambda: BT.Move(_v(554,18384),log=False)),
        _planner_action('Servants of Grenth','10 - Claim reward leader 0x806607',
                        lambda: BT.MoveAndDialogByModelID(NPC_REAPER,dialog_id=0x806607,log=False)),
        _planner_action('Servants of Grenth','11 - Record',lambda: _record('Servants of Grenth')),

        # Dhuum - the last stage needs explicit configuration and live validation.
        _planner_action('Dhuum','01 - Verify sacrifice configuration',
                        lambda: _action('Check Dhuum config',_dhuum_validate_party)),
        _planner_action('Dhuum','02 - Follow King Frozenwind to destination',
                        lambda: _uw_follow_king()),
        _planner_action('Dhuum','03 - Move to King destination (-11278,17297)',
                        lambda: BT.Move(_v(-11278,17297),log=False)),
        _planner_action('Dhuum','04 - Wait King in interact range',
                        lambda: _wait_npc_near(UW_KING_ID,1100.,180.,'Wait King Frozenwind')),
        _planner_action('Dhuum','05 - King settle 10 seconds',lambda: BT.Wait(10_000)),
        _planner_action('Dhuum','06 - Accept Nightmare Cometh (1129)',
                        lambda: _quest_npc(UW_KING_ID,0x846901,UW_QUEST_NIGHTMARE,'Accept Nightmare Cometh')),
        _planner_action('Dhuum','07 - Start fight hold / disable combat',
                        lambda: _action('Hold Dhuum combat',_dhuum_start_fight)),
        _planner_action('Dhuum','08 - Flag sacrifice and survivor accounts',
                        lambda: _action('Flag Dhuum groups',_dhuum_flag_groups)),
        _planner_action('Dhuum','09 - Enable Dhuum Helper on all accounts',
                        _dhuum_enable_helper),
        _planner_action('Dhuum','10 - Move into Dhuum fight (-14007,17287)',
                        lambda: BT.Move(_v(-14007,17287),pause_on_combat=False,log=False)),
        _planner_action('Dhuum','11 - Wait for Spirit Form threshold, enable combat',
                        lambda: _wait_until('Spirit Form readiness',_dhuum_enable_combat_if_ready,240.)),
        _planner_action('Dhuum','12 - Wait for Underworld chest',
                        lambda: _wait_until('Dhuum chest appears',lambda: _dhuum_chest_id()>0,1200.)),
        _planner_action('Dhuum','13 - Restore combat, clear all flags',
                        lambda: BT.Sequence(name='Dhuum cleanup',children=[BT.UnflagAllHeroes(),
                            _action('Restore Dhuum options',_dhuum_finish)])),
        _planner_action('Dhuum','14 - Loot chest party (pass 1)',_dhuum_chest_interaction),
        _planner_action('Dhuum','15 - Wait 5s',lambda: BT.Wait(5000)),
        _planner_action('Dhuum','16 - Loot chest party (pass 2)',_dhuum_chest_interaction),
        _planner_action('Dhuum','17 - Wait 5s',lambda: BT.Wait(5000)),
        _planner_action('Dhuum','18 - Loot sweep A (-14324,17549)',
                        lambda: BT.Move(_v(-14324,17549),log=False)),
        _planner_action('Dhuum','19 - Loot sweep B (-14243,17017)',
                        lambda: BT.Move(_v(-14243,17017),log=False)),
        _planner_action('Dhuum','20 - Quest completion leader 0x846907',
                        lambda: BT.MoveAndDialogByModelID(UW_KING_ID,dialog_id=0x846907,log=False)),
        _planner_action('Dhuum','21 - Verify quest 1129 completed',
                        lambda: _wait_quest_completed(UW_QUEST_NIGHTMARE,timeout_ms=30_000)),
        _planner_action('Dhuum','22 - Record full UW completion',lambda: _record('Dhuum')),

    ]


def _configure(tree: BottingTree) -> None:
    tree.Config.ConfigureUpkeep(
        looting_enabled=True,
        auto_inventory_handler_enabled=_enable_inventory_handler,
        consumable_upkeeps=_enabled_upkeeps(),
        enable_party_wipe_recovery=False,
        heroai_state_logging=False,
    )
    tree.EnsureSummoningStonePartyService(
        enabled=lambda: _use_summoning_stone and Map.GetMapID()==UW_MAP_ID,
        map_ids=(UW_MAP_ID,),
        initial_grace_ms=2_000,
        attempt_interval_ms=5_000,
        retry_cycle_delay_ms=15_000,
        log=True,
    )


def ensure_botting_tree() -> BottingTree:
    global botting_tree
    _load_settings()
    if botting_tree is None:
        botting_tree = BottingTree.Create(
            MODULE_NAME,
            main_routine=get_execution_steps(),
            routine_name="MultiAccountSequence",
            repeat=False,
            multi_account=True,
            isolation_enabled=False,
            configure_fn=_configure,
        )
        _sync_upkeeps(force=True)
    return botting_tree


def main() -> None:
    global initialized
    if not initialized:
        _dhuum_settings_load()
        ensure_botting_tree()
        initialized = True
    tree = ensure_botting_tree()
    _sync_upkeeps()
    _stats().start_if_necessary()
    if _horsemen_policy is not None:
        if Map.IsMapReady() and Map.IsOutpost():
            _horsemen_restore_policy()
        else:
            _horsemen_apply_policy()
    _recover_after_uw_outpost(tree)
    if _imprisoned_runtime_active:
        if Map.IsMapReady() and Map.IsOutpost():
            _imprisoned_restore_policy()
        else:
            _imprisoned_apply_policy()
    if Map.IsMapReady() and Map.IsOutpost():
        if _servants_policy_active: _uw_clear_servants()
        if _uw_pacifist_active: _uw_wrathful_pacifist(False)
        if _dhuum_ready: _dhuum_finish()
    _sync_uw_guardian_blacklist()
    _uw_servants_tick()
    _uw_wrathful_tick()
    _dhuum_tick()
    tree.tick()
    _stats().watch_planner(tree)
    _tick_direct_pcon_upkeep()
    attach_botting_tree_support(tree)
    tree.UI.draw_window(icon_path="Assets/Textures/Module_Icons/Underworld.png", iconwidth=80, main_child_dimensions=(550, 380), extra_tabs=[
        ("Party", _party_config.draw_tab),
        ("Config", _draw_run_config),
        ("Restock", _draw_restock_config),
        ("Imprisoned Spirits", _draw_imprisoned_config),
        ("Statistics", _draw_statistics),
        ("Dhuum", _draw_dhuum_config),
    ])


if __name__ == "__main__":
    main()
