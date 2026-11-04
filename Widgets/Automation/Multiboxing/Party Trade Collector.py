"""Party Trade Collector.

The other accounts of the party (same instance) open a trade with the "main",
drop the selected items (and optionally gold) in it, submit, and accept; the
main submits an empty offer and accepts.

What can be collected
---------------------
- Gemstones: each of the four DoA gemstones.
- Common materials and rare materials: one checkbox per material.
- Equipment by rarity (gold / purple / blue / white / green): weapons, shields,
  off-hands and armor pieces, with filters: weapons and/or armor, unidentified
  only, q8 max only.
- Dyes: one checkbox per colour.
- Lockpicks and keys: one checkbox per key (no dungeon keys).
- Tomes (normal / elite).
- Consumables: one checkbox per item (pcons incl. lunar fortunes, conset and
  resurrection scrolls; alcohol; city sweets; summoning stones). The
  alcohol and sweet lists are the library's Routines.Yield.Upkeepers lists.
- Zaishen coins, commendations / decrees / tokens, festival gifts, passage
  scrolls, Zaishen strongboxes: one checkbox per item.
- A custom list of model ids, and a blacklist that wins over everything.
- Gold, keeping a chosen amount on every giver.
A send maximum per item caps the number of units every giver sends of it
(0 = everything); a stack can then be offered partly. A preview lists what each giver would give before any
trade (PartyTradeCollector/preview.ini + the giver's status document).
Customized and non-tradable items are never offered. Only the four inventory
bags are scanned, so equipped items and the equipment pack are never touched.

Reverse direction ("Send to every account")
-------------------------------------------
The main gives the same quantity of chosen items (picked from what it holds) to
EVERY other account, one account at a time. The main's bags are used, plus its
Xunlai storage if that option is on (only the missing units are withdrawn,
before the first trade); an item the main cannot cover for every account is
not sent at all. The receivers only submit an empty offer and accept.
    PartyTradeCollector/distribute.ini         written by the main only
    status_<email>.ini, section [Distribute]   written by each receiver

Design notes
------------
- The widget runs on every account. Pressing the button makes the local account
  the main; it also asks the other accounts to enable this widget through the
  existing SharedCommandType.EnableWidget message.
- Coordination uses global-scope Settings documents (no new persistence system,
  no library change):
    PartyTradeCollector/request.ini            written by the main only
    PartyTradeCollector/status_<email>.ini     written by each giver only
  Readers call Settings.reload() to pick up the other client's writes; writers
  call save() so the other client sees the change immediately.
- The main's selection travels in the request, so givers use the main's choices.
- Givers are served one at a time, at most 7 stacks per trade (game limit), as
  many trades as needed, bounded by the main's free slots and gold room.
- A trade counts as done when the offered item ids have left the giver's bags
  and the offered gold has left the giver.
- Safety: a giver only trades with an account present in shared memory, in the
  same party and the same instance; the main never offers anything (0 gold).
"""

from __future__ import annotations

import importlib
import re
import time
from types import ModuleType
from typing import Callable

import PyGameThread
import PyImGui
import PySystem

from Py4GWCoreLib import GLOBAL_CACHE, Agent, Color, ImGui, Item, ItemArray, Player, Routines, Utils
from Py4GWCoreLib.FrameTree import Frame, FrameId
from Py4GWCoreLib.enums_src.GameData_enums import DyeColor
from Py4GWCoreLib.enums_src.Item_enums import ARMOR_TYPES, WEAPON_TYPES, ItemType
from Py4GWCoreLib.enums_src.Model_enums import ModelID
from Py4GWCoreLib.enums_src.Multiboxing_enums import SharedCommandType
from Py4GWCoreLib.GlobalCache.shared_memory_src.AccountStruct import AccountStruct
from Py4GWCoreLib.py4gwcorelib_src.Settings import Settings
from Py4GWCoreLib.py4gwcorelib_src.WidgetManager import get_widget_handler


def _load_trade_module() -> ModuleType | None:
    """Native trade bindings (open / offer / submit / accept / cancel), if present."""
    try:
        return importlib.import_module("PyTrade")
    except Exception:
        return None


PyTrade: ModuleType | None = _load_trade_module()

MODULE_NAME = "Party Trade Collector"
WIDGET_NAME = "Party Trade Collector"  # file stem, used by the remote EnableWidget command
MODULE_ICON = "Assets/Textures/Module_Icons/Party Quest Log.png"
# Widget Mirror: keep this widget on the main only (the main opens it on the
# other accounts when it starts a collection, and they close it when done).
MIRROR_MAIN_ONLY = True

# --- what can be selected ---------------------------------------------------
def _named_items(*names: str) -> list[tuple[int, str]]:
    """(model id, UI label) by ModelID member name; unknown names are skipped (enum drift)."""
    out: list[tuple[int, str]] = []
    for name in names:
        member = getattr(ModelID, name, None)
        if member is not None:
            label = name.replace("_", " ").replace(" Of ", " of ")
            out.append((int(member.value), label))
    return out


# Item lists: one checkbox per model, stored under [Items] by model id.
GEMSTONE_ITEMS = _named_items("Margonite_Gemstone", "Stygian_Gemstone", "Titan_Gemstone", "Torment_Gemstone")
COMMON_MATERIAL_ITEMS = _named_items(
    "Bolt_Of_Cloth", "Bone", "Chitin_Fragment", "Feather", "Granite_Slab", "Iron_Ingot",
    "Pile_Of_Glittering_Dust", "Plant_Fiber", "Scale", "Tanned_Hide_Square", "Wood_Plank",
)
RARE_MATERIAL_ITEMS = _named_items(
    "Amber_Chunk", "Bolt_Of_Damask", "Bolt_Of_Linen", "Bolt_Of_Silk", "Deldrimor_Steel_Ingot", "Diamond",
    "Elonian_Leather_Square", "Fur_Square", "Glob_Of_Ectoplasm", "Jadeite_Shard", "Leather_Square",
    "Lump_Of_Charcoal", "Monstrous_Claw", "Monstrous_Eye", "Monstrous_Fang", "Obsidian_Shard", "Onyx_Gemstone",
    "Roll_Of_Parchment", "Roll_Of_Vellum", "Ruby", "Sapphire", "Spiritwood_Plank", "Steel_Ingot",
    "Tempered_Glass_Vial", "Vial_Of_Ink",
)
ITEM_LISTS: list[tuple[str, list[tuple[int, str]]]] = [
    ("Common materials", COMMON_MATERIAL_ITEMS),
    ("Rare materials", RARE_MATERIAL_ITEMS),
    ("Gemstones", GEMSTONE_ITEMS),
]
# Selected by default (they were the old "Specific items", on by default).
DEFAULT_ON_MODELS: frozenset[int] = frozenset(
    m for m, label in GEMSTONE_ITEMS + RARE_MATERIAL_ITEMS
    if label in ("Margonite Gemstone", "Stygian Gemstone", "Titan Gemstone", "Torment Gemstone",
                 "Glob of Ectoplasm", "Obsidian Shard")
)


def _models(*names: str) -> frozenset[int]:
    """Model ids by ModelID member name; unknown names are skipped (enum drift)."""
    out: set[int] = set()
    for name in names:
        member = getattr(ModelID, name, None)
        if member is not None:
            out.add(int(member.value))
    return frozenset(out)


CONSET_MODELS = _models("Essence_Of_Celerity", "Grail_Of_Might", "Armor_Of_Salvation")
# Same list as the library's Items.deposit_pcons (minus the resurrection scroll).
PCON_MODELS = _models(
    "Birthday_Cupcake", "Candy_Apple", "Golden_Egg", "Candy_Corn", "Honeycomb", "War_Supplies",
    "Slice_Of_Pumpkin_Pie", "Drake_Kabob", "Bowl_Of_Skalefin_Soup", "Pahnai_Salad",
)
RES_SCROLL_MODELS = _models("Scroll_Of_Resurrection")
ALCOHOL_MODELS: frozenset[int] = frozenset(int(m.value) for m in Routines.Yield.Upkeepers.ALCOHOL_ITEMS)
SWEET_MODELS: frozenset[int] = frozenset(int(m.value) for m in Routines.Yield.Upkeepers.CITY_SPEED_ITEMS)
LOCKPICK_MODELS = _models("Lockpick")
# Regional chest keys (tradable, open the chests of a given area).
CHEST_KEY_MODELS = _models(
    "Ascalonian_Key", "Canthan_Key", "Darkstone_Key", "Deep_Jade_Key", "Elonian_Key", "Forbidden_Key",
    "Istani_Key", "Kournan_Key", "Krytan_Key", "Kurzick_Key", "Luxon_Key", "Maguuma_Key", "Margonite_Key",
    "Miners_Key", "Obsidian_Key", "Phantom_Key", "Shing_Jea_Key", "Shiverpeak_Key", "Steel_Key",
    "Stoneroot_Key", "Vabbian_Key", "Ancient_Elonian_Key", "Zaishen_Key",
)
ELITE_TOME_MODELS = _models(*(f"{p}_Elite_Tome" for p in (
    "Warrior", "Ranger", "Monk", "Necromancer", "Mesmer", "Elementalist", "Assassin", "Ritualist",
    "Paragon", "Dervish")))
NORMAL_TOME_MODELS = _models(*(f"{p}_Tome" for p in (
    "Warrior", "Ranger", "Monk", "Necromancer", "Mesmer", "Elementalist", "Assassin", "Ritualist",
    "Paragon", "Dervish")))
ZCOIN_MODELS = _models("Copper_Zaishen_Coin", "Silver_Zaishen_Coin", "Gold_Zaishen_Coin")
TOKEN_MODELS = _models(
    "Battle_Commendation", "Imperial_Commendation", "Ministerial_Commendation", "Burol_Ironfists_Commendation",
    "Ministerial_Decree", "Victory_Token", "Mursaat_Token",
)
LUNAR_FORTUNE_MODELS = _models(*(n for n in dir(ModelID) if n.startswith("Lunar_Fortune_")))
LUNAR_MODELS = _models("Lunar_Token")  # fortunes and the four-leaf clover are in the Pcons list
FESTIVE_MODELS = _models("Wintersday_Gift", "Trick_Or_Treat_Bag", "Gift_Of_The_Huntsman", "Gift_Of_The_Traveller")
PASSAGE_MODELS = _models("Passage_Scroll_Uw", "Passage_Scroll_Fow", "Passage_Scroll_Urgoz", "Passage_Scroll_Deep")
STRONGBOX_MODELS = _models(
    "Champions_Zaishen_Strongbox", "Heros_Zaishen_Strongbox", "Gladiators_Zaishen_Strongbox",
    "Strategists_Zaishen_Strongbox",
)

# Category key -> model ids (matched first, by model only).
MODEL_GROUPS: dict[str, frozenset[int]] = {
    "conset": CONSET_MODELS,
    "pcons": PCON_MODELS,
    "res_scroll": RES_SCROLL_MODELS,
    "alcohol": ALCOHOL_MODELS,
    "sweets": SWEET_MODELS,
    "lockpicks": LOCKPICK_MODELS,
    "chest_keys": CHEST_KEY_MODELS,
    "tomes_elite": ELITE_TOME_MODELS,
    "tomes": NORMAL_TOME_MODELS,
    "zcoins": ZCOIN_MODELS,
    "tokens": TOKEN_MODELS,
    "lunar": LUNAR_MODELS,
    "festive": FESTIVE_MODELS,
    "passages": PASSAGE_MODELS,
    "strongboxes": STRONGBOX_MODELS,
}



def _items_from_models(models: frozenset[int]) -> list[tuple[int, str]]:
    """(model id, UI label) for a model group, sorted by label."""
    out: list[tuple[int, str]] = []
    for model in models:
        try:
            label = ModelID(model).name.replace("_", " ").replace(" Of ", " of ")
        except Exception:
            label = f"model {model}"
        out.append((model, label))
    return sorted(out, key=lambda e: e[1])


# Summoning stones: the same list as the library's Items.deposit_summoning_stones.
_SUMMON_RAW = _named_items(
    "Legionnaire_Summoning_Crystal", "Igneous_Summoning_Stone", "Amber_Summon", "Arctic_Summon",
    "Automaton_Summon", "Celestial_Summon", "Chitinous_Summon", "Demonic_Summon", "Fossilized_Summon",
    "Frosty_Summon", "Gelatinous_Summon", "Ghastly_Summon", "Imperial_Guard_Summon", "Jadeite_Summon",
    "Merchant_Summon", "Mischievous_Summon", "Mysterious_Summon", "Mystical_Summon", "Shining_Blade_Summon",
    "Tengu_Summon", "Zaishen_Summon",
)
# In-game names where the enum name differs ("Amber Summon" -> "Amber Summoning Stone").
_SUMMON_LABELS = {"Imperial Guard Summon": "Imperial Guard Reinforcement Orders",
                  "Shining Blade Summon": "Shining Blade War Horn", "Tengu Summon": "Tengu Support Flare"}
SUMMONING_STONE_ITEMS = sorted(
    ((m, _SUMMON_LABELS.get(lbl, lbl[: -len(" Summon")] + " Summoning Stone" if lbl.endswith(" Summon") else lbl))
     for m, lbl in _SUMMON_RAW),
    key=lambda e: e[1],
)

# Consumables of the wiki's Consumable page (guildwars.fandom.com/wiki/Consumable)
# that are not already pcons / conset / resurrection scrolls / summoning stones.
# Dungeon Map is on the page but has no ModelID member, so it cannot be listed.
WIKI_EXTRA_MODELS = _models(
    "Star_Of_Transference", "Perfect_Salvage_Kit", "Powerstone_Of_Courage", "Elixir_Of_Valor", "Refined_Jelly",
    "Pumpkin_Cookie", "Four_Leaf_Clover", "Peppermint_Candy_Cane", "Rainbow_Candy_Cane", "Wintergreen_Candy_Cane",
)
# Sweets the wiki lists as consumables: shown in Pcons instead of Sweets (one checkbox per item).
WIKI_SWEET_MODELS = _models(
    "Chocolate_Bunny", "Creme_Brulee", "Red_Bean_Cake", "Fruitcake", "Mandragor_Root_Cake", "Sugary_Blue_Drink",
)

# Consumables, one checkbox per item. A checked item keeps its group key, so the
# send amounts (conset, pcons, res_scroll, alcohol, sweets) still apply to it.
CONSUMABLE_LISTS: list[tuple[str, list[tuple[int, str]]]] = [
    # Pcons list = pcons + lunar fortunes + conset + resurrection scrolls + the wiki's other consumables.
    ("Pcons", _items_from_models(PCON_MODELS | LUNAR_FORTUNE_MODELS | CONSET_MODELS | RES_SCROLL_MODELS
                                 | WIKI_EXTRA_MODELS | WIKI_SWEET_MODELS)),
    ("Alcohol", _items_from_models(ALCOHOL_MODELS)),
    ("Sweets (town speed boost)", _items_from_models(SWEET_MODELS - WIKI_SWEET_MODELS)),
    ("Summoning stones", SUMMONING_STONE_ITEMS),
]
# In-game names where the enum member name reads badly.
_GAME_LABELS: dict[str, str] = {
    "Burol Ironfists Commendation": "Burol Ironfist's Commendation",
    "Trick Or Treat Bag": "Trick-or-Treat Bag",
    "Gift of The Huntsman": "Gift of the Huntsman",
    "Gift of The Traveller": "Gift of the Traveller",
    "Passage Scroll Uw": "Passage Scroll to the Underworld",
    "Passage Scroll Fow": "Passage Scroll to the Fissure of Woe",
    "Passage Scroll Urgoz": "Passage Scroll to Urgoz's Warren",
    "Passage Scroll Deep": "Passage Scroll to the Deep",
    "Miners Key": "Miner's Key",
    "Droknars Key": "Droknar's Key",
    "Champions Zaishen Strongbox": "Champion's Zaishen Strongbox",
    "Heros Zaishen Strongbox": "Hero's Zaishen Strongbox",
    "Gladiators Zaishen Strongbox": "Gladiator's Zaishen Strongbox",
    "Strategists Zaishen Strongbox": "Strategist's Zaishen Strongbox",
}


def _game_named(*names: str) -> list[tuple[int, str]]:
    return [(m, _GAME_LABELS.get(label, label)) for m, label in _named_items(*names)]


# Coins / tokens / gifts, and passages / strongboxes: one checkbox per item, drawn above
# the custom list (the old "Coins, tokens and events" and "Misc" groups are gone).
COIN_LISTS: list[tuple[str, list[tuple[int, str]]]] = [
    ("Zaishen coins", _game_named("Copper_Zaishen_Coin", "Silver_Zaishen_Coin", "Gold_Zaishen_Coin")),
    ("Commendations and tokens", _game_named(
        "Battle_Commendation", "Imperial_Commendation", "Ministerial_Commendation", "Burol_Ironfists_Commendation",
        "Ministerial_Decree", "Victory_Token", "Mursaat_Token", "Lunar_Token")),
    ("Festival gifts", _game_named(
        "Wintersday_Gift", "Trick_Or_Treat_Bag", "Gift_Of_The_Huntsman", "Gift_Of_The_Traveller")),
]
MISC_LISTS: list[tuple[str, list[tuple[int, str]]]] = [
    ("Passage scrolls", _game_named(
        "Passage_Scroll_Uw", "Passage_Scroll_Fow", "Passage_Scroll_Urgoz", "Passage_Scroll_Deep")),
    ("Zaishen strongboxes", _game_named(
        "Champions_Zaishen_Strongbox", "Heros_Zaishen_Strongbox", "Gladiators_Zaishen_Strongbox",
        "Strategists_Zaishen_Strongbox")),
]
# Every tradable key except the dungeon ones (Boss / Dungeon / Bogroots Boss / Cell / Prison
# keys) and the Nightfall mission keys (Ruby / Sapphire / Diamond).
KEY_ITEMS: list[tuple[int, str]] = _game_named(
    "Lockpick", "Zaishen_Key", "Phantom_Key", "Obsidian_Key", "Demonic_Key",
    # Prophecies
    "Ascalonian_Key", "Steel_Key", "Krytan_Key", "Maguuma_Key", "Elonian_Key", "Shiverpeak_Key",
    "Darkstone_Key", "Miners_Key",
    # Factions
    "Shing_Jea_Key", "Canthan_Key", "Kurzick_Key", "Stoneroot_Key", "Luxon_Key", "Deep_Jade_Key",
    "Forbidden_Key",
    # Nightfall
    "Istani_Key", "Kournan_Key", "Vabbian_Key", "Ancient_Elonian_Key", "Margonite_Key",
    # Eye of the North reward trophy
    "Droknars_Key",
)
KEY_LIST_TITLE = "Keys and lockpicks"
# Dyes: every vial shares one model id, the colour tells them apart.
# One checkbox per colour, stored under [Dyes] by DyeColor value.
VIAL_OF_DYE_MODEL: int = int(ModelID.Vial_Of_Dye.value)
DYE_LIST_TITLE = "Dyes"
DYE_ITEMS: list[tuple[int, str]] = [
    (int(c), f"{c.name} Dye") for c in DyeColor if c not in (DyeColor.NoColor, DyeColor.Mixed)
]
# Main -> Alts works with keys: the model id, or DYE_KEY_BASE + colour for a vial of dye.
DYE_KEY_BASE = 1_000_000


def _dye_color(item_id: int) -> int:
    try:
        return int(Item.GetDyeColor(item_id))
    except Exception:
        return 0


def _dist_key(item_id: int) -> int:
    """Distribution key of an item: its model id, or DYE_KEY_BASE + colour for a dye."""
    model = int(Item.GetModelID(item_id))
    if model == VIAL_OF_DYE_MODEL:
        color = _dye_color(item_id)
        if color:
            return DYE_KEY_BASE + color
    return model
ALL_LIST_MODELS: list[int] = [
    m for _, items in ITEM_LISTS + CONSUMABLE_LISTS + COIN_LISTS + MISC_LISTS + [(KEY_LIST_TITLE, KEY_ITEMS)]
    for m, _ in items
]
# Group key of a listed model, for the send amounts.
SEND_GROUP_OF_MODEL: dict[int, str] = {
    m: key for key in ("conset", "pcons", "res_scroll", "alcohol", "sweets") for m in MODEL_GROUPS[key]
}
# Lunar fortunes, the sweets moved to Pcons and the wiki's food / morale items sit in the
# Pcons list: they count toward the "Pcons (total)" send amount. Star of Transference and
# Perfect Salvage Kit have no send amount (not food, and not the regular salvage kits).
SEND_GROUP_OF_MODEL.update({m: "pcons" for m in LUNAR_FORTUNE_MODELS | WIKI_SWEET_MODELS
                            | (WIKI_EXTRA_MODELS - _models("Star_Of_Transference", "Perfect_Salvage_Kit"))})
# Keys: the lockpick keeps the "Lockpicks" amount, every other key the "Chest keys" amount.
SEND_GROUP_OF_MODEL.update({m: ("lockpicks" if m in LOCKPICK_MODELS else "chest_keys") for m, _ in KEY_ITEMS})



GEAR_TYPES: frozenset[int] = frozenset(int(t) for t in (set(WEAPON_TYPES) | set(ARMOR_TYPES)))
ARMOR_TYPE_IDS: frozenset[int] = frozenset(int(t) for t in ARMOR_TYPES)
TROPHY_TYPE: int = int(ItemType.Trophy)
PRESENT_TYPE: int = int(ItemType.Present)
MINIPET_TYPE: int = int(ItemType.Minipet)
GEAR_RARITIES: dict[str, str] = {
    "gear_gold": "Gold",
    "gear_purple": "Purple",
    "gear_blue": "Blue",
    "gear_white": "White",
    "gear_green": "Green",
}

# q8 max rule.
Q8_SWORD_DAMAGE = (15, 22)
Q8_SHIELD_ARMOR = 16
Q8_FOCUS_ENERGY = 12


def _is_q8_max(item_id: int, item_type: int) -> bool:
    """Sword 15-22 / Shield 16 armor / Focus +12 energy, all at requirement 8."""
    try:
        if item_type not in (int(ItemType.Sword), int(ItemType.Shield), int(ItemType.Offhand)):
            return False
        if int(Item.Properties.GetRequirement(item_id)[1]) != 8:
            return False
        if item_type == int(ItemType.Sword):
            return tuple(Item.Properties.GetDamage(item_id)) == Q8_SWORD_DAMAGE
        if item_type == int(ItemType.Shield):
            # IsMaxDamage() reads the damage mod and would reject every shield.
            return int(Item.Properties.GetShieldArmor(item_id)[0]) == Q8_SHIELD_ARMOR
        return int(Item.Properties.GetEnergy(item_id)) == Q8_FOCUS_ENERGY
    except Exception:
        return False


# (category key, UI label) grouped for the UI. Default: not selected.
CATEGORY_GROUPS: list[tuple[str, list[tuple[str, str]]]] = [
    ("Equipment (weapons, shields, focus, armor)", [
        ("gear_gold", "Gold"),
        ("gear_purple", "Purple"),
        ("gear_blue", "Blue"),
        ("gear_white", "White"),
        ("gear_green", "Green (uniques)"),
    ]),
    ("Tomes", [
        ("tomes", "Normal tomes"),
        ("tomes_elite", "Elite tomes"),
    ]),
    # "Coins, tokens and events" (any other present, monster trophies) and "Misc" (minipets,
    # ID and salvage kits) are removed; Selection.match still handles them if they come back.
]
ALL_CATEGORIES: list[str] = [key for _, items in CATEGORY_GROUPS for key, _ in items]

# Equipment filters (apply to the gear_* rarity categories). Key -> (label, default).
GEAR_FILTERS: dict[str, tuple[str, bool]] = {
    "weapons": ("Weapons, shields and focus", True),
    "armor": ("Armor pieces", True),
    "unid_only": ("Unidentified only", False),
    "q8_only": ("q8 max only (swords, shields, focus)", False),
}

# Per item: the most each giver sends of it (0 = everything), stored under [SendItem]
# by item key (model id, or DYE_KEY_BASE + colour for a dye).
SEND_ITEM_SECTION = "SendItem"
SEND_MAX = 99_999

UNNAMED = "Unnamed character"  # shown instead of an account email when a name is missing
MAX_STACKS_PER_TRADE = 7
MAX_CHARACTER_GOLD = 100_000
DEFAULT_PAY_PER_TRADE = 1000
DEFAULT_CLOSE_AFTER = True  # givers switch this widget off when their part is over
DEFAULT_FROM_STORAGE = True  # also withdraw selected items from Xunlai storage
MATERIAL_STORAGE_BAG = 6
STORAGE_BAG_IDS = (MATERIAL_STORAGE_BAG, *range(8, 22))  # material storage + Storage1..14
STORAGE_OPEN_TIMEOUT_S = 4.0
WITHDRAW_GAP_S = 0.5  # gold the main adds to every trade that carries items
APPROACH_RANGE = 220.0
TICK_S = 0.10
POLL_S = 0.5
HEARTBEAT_S = 2.0
STALE_REQUEST_S = 20.0
ALT_NO_RESPONSE_S = 30.0
ALT_TOTAL_TIMEOUT_S = 900.0
APPROACH_TIMEOUT_S = 25.0
OPEN_WAIT_S = 2.5  # interaction is queued: leave time for the trade window
OFFER_GAP_S = 0.3
VERIFY_WAIT_S = 1.0
ACCEPT_EVERY_S = 1.5
ACCEPT_TIMEOUT_S = 45.0
ROUND_PAUSE_S = 1.5
MAX_ATTEMPTS = 3
MAIN_SUBMIT_DELAY_S = 0.8
SUBMIT_DELAY_S = 0.5
SUBMIT_TIMEOUT_S = 5.0
SUMMARY_REFRESH_S = 1.0
PREVIEW_NAME_WAIT_S = 4.0   # how long a giver refreshes its preview while item names load
PREVIEW_STALE_S = 30.0
PREVIEW_MAX_LINES = 40

_MSG = PySystem.Console.MessageType
_SECTION = "Trade"
_PREVIEW = "Preview"


def _log(msg: str, kind: PySystem.Console.MessageType = _MSG.Info) -> None:
    PySystem.Console.Log(MODULE_NAME, msg, kind)


# --- Settings documents ---------------------------------------------------
def _options() -> Settings:
    return Settings("Widgets/PartyTradeCollector/PartyTradeCollector.ini", "global")


def _request_doc() -> Settings:
    return Settings("Widgets/PartyTradeCollector/request.ini", "global")


def _preview_doc() -> Settings:
    return Settings("Widgets/PartyTradeCollector/preview.ini", "global")


def _safe(email: str) -> str:
    return re.sub(r"[^a-z0-9._-]", "_", (email or "").strip().lower())


def _status_doc(email: str) -> Settings:
    return Settings(f"Widgets/PartyTradeCollector/status_{_safe(email)}.ini", "global")


def _publish(doc: Settings, values: dict[str, object], section: str = _SECTION) -> None:
    for key, value in values.items():
        doc.set(section, key, value)
    doc.save()  # the other client must see it now, not after the autosave debounce


def _fresh(doc: Settings) -> Settings:
    doc.reload()  # pick up the other client's latest write
    return doc


def _parse_ids(text: str) -> set[int]:
    """Model ids typed by the user: any separator, non-numbers ignored."""
    return {int(tok) for tok in re.findall(r"\d+", text or "") if 0 < int(tok) < 1_000_000}


def _ids_str(ids: set[int]) -> str:
    return ",".join(str(i) for i in sorted(ids))


# --- selection ------------------------------------------------------------
class Selection:
    """What the main wants; serialized into the request for the givers."""

    def __init__(
        self,
        models: set[int],
        cats: set[str],
        give_gold: bool,
        gold_keep: int,
        custom: set[int] | None = None,
        blacklist: set[int] | None = None,
        filters: dict[str, bool] | None = None,
        send: dict[int, int] | None = None,
    ) -> None:
        self.models = models
        self.cats = cats
        self.give_gold = give_gold
        self.gold_keep = max(0, gold_keep)
        self.custom: set[int] = custom or set()
        self.blacklist: set[int] = blacklist or set()
        self.filters: dict[str, bool] = {k: d for k, (_, d) in GEAR_FILTERS.items()}
        self.filters.update(filters or {})
        self.send: dict[int, int] = {k: v for k, v in (send or {}).items() if v > 0}  # item key -> max
        self.pay_gold: int = 0  # gold the main puts in every trade that carries items
        self.from_storage: bool = False  # givers also withdraw matching items from Xunlai
        self.dyes: set[int] = set()      # DyeColor values

    @staticmethod
    def empty() -> Selection:
        return Selection(set(), set(), False, 0)

    @staticmethod
    def from_options() -> Selection:
        opts = _options()
        models = {m for m in ALL_LIST_MODELS if opts.get_bool("Items", str(m), m in DEFAULT_ON_MODELS)}
        cats = {c for c in ALL_CATEGORIES if opts.get_bool("Categories", c, False)}
        sel = Selection(
            models,
            cats,
            opts.get_bool("Gold", "give", False),
            opts.get_int("Gold", "keep", 1000),
            _parse_ids(opts.get_str("Lists", "custom", "")),
            _parse_ids(opts.get_str("Lists", "blacklist", "")),
            {k: opts.get_bool("Filters", k, d) for k, (_, d) in GEAR_FILTERS.items()},
            {k: v for k in SEND_ITEM_KEYS if (v := opts.get_int(SEND_ITEM_SECTION, str(k), 0)) > 0},
        )
        sel.pay_gold = max(0, min(MAX_CHARACTER_GOLD, opts.get_int("Gold", "pay_per_trade", DEFAULT_PAY_PER_TRADE)))
        sel.from_storage = opts.get_bool("Storage", "use", DEFAULT_FROM_STORAGE)
        sel.dyes = {c for c, _ in DYE_ITEMS if opts.get_bool("Dyes", str(c), False)}
        return sel

    def is_empty(self) -> bool:
        return not self.models and not self.cats and not self.custom and not self.give_gold and not self.dyes

    def to_fields(self) -> dict[str, object]:
        return {
            "models": _ids_str(self.models),
            "cats": ",".join(sorted(self.cats)),
            "give_gold": self.give_gold,
            "gold_keep": self.gold_keep,
            "custom": _ids_str(self.custom),
            "blacklist": _ids_str(self.blacklist),
            "filters": ",".join(k for k, on in sorted(self.filters.items()) if on),
            "send_items": ",".join(f"{k}:{v}" for k, v in sorted(self.send.items()) if v > 0),
            "pay_gold": self.pay_gold,
            "from_storage": self.from_storage,
            "dyes": _ids_str(self.dyes),
        }

    @staticmethod
    def from_doc(doc: Settings, section: str = _SECTION) -> Selection:
        raw_cats = doc.get_str(section, "cats", "")
        on_filters = set(doc.get_str(section, "filters", "weapons,armor").split(","))
        send: dict[int, int] = {}
        for part in doc.get_str(section, "send_items", "").split(","):
            key, _, value = part.partition(":")
            if key.strip().isdigit() and value.strip().isdigit():
                send[int(key)] = int(value)
        sel = Selection(
            _parse_ids(doc.get_str(section, "models", "")),
            {c for c in raw_cats.split(",") if c in ALL_CATEGORIES},
            doc.get_bool(section, "give_gold", False),
            doc.get_int(section, "gold_keep", 0),
            _parse_ids(doc.get_str(section, "custom", "")),
            _parse_ids(doc.get_str(section, "blacklist", "")),
            {k: k in on_filters for k in GEAR_FILTERS},
            send,
        )
        sel.pay_gold = max(0, doc.get_int(section, "pay_gold", 0))
        sel.from_storage = doc.get_bool(section, "from_storage", False)
        sel.dyes = _parse_ids(doc.get_str(section, "dyes", ""))
        return sel

    def _gear_ok(self, item_id: int, item_type: int) -> bool:
        is_armor = item_type in ARMOR_TYPE_IDS
        if is_armor and not self.filters.get("armor", True):
            return False
        if not is_armor and not self.filters.get("weapons", True):
            return False
        if self.filters.get("unid_only", False):
            try:
                if Item.Usage.IsIdentified(item_id):
                    return False
            except Exception:
                return False
        if self.filters.get("q8_only", False) and not _is_q8_max(item_id, item_type):
            return False
        return True

    def match(self, item_id: int) -> str | None:
        """Category key that selects this item ("item" / "custom" for explicit models),
        or None if it must not be traded."""
        try:
            if Item.Properties.IsCustomized(item_id):
                return None
            try:
                if not Item.Properties.IsTradable(item_id):
                    return None
            except Exception:
                pass  # unknown: let the trade window decide (verify step)
            model = int(Item.GetModelID(item_id))
            if model in self.blacklist:
                return None
            if model in self.models:
                return SEND_GROUP_OF_MODEL.get(model, "item")  # consumables keep their send amount
            if model in self.custom:
                return "custom"
            for key, group in MODEL_GROUPS.items():
                if key in self.cats and model in group:
                    return key
            if model == VIAL_OF_DYE_MODEL:
                return "dyes" if self.dyes and _dye_color(item_id) in self.dyes else None
            item_type = int(Item.GetItemType(item_id)[0])
            if "trophies" in self.cats and item_type == TROPHY_TYPE:
                return "trophies"
            if "festive" in self.cats and item_type == PRESENT_TYPE:
                return "festive"
            if "minipets" in self.cats and item_type == MINIPET_TYPE:
                return "minipets"
            if "zcoins" in self.cats and Item.Type.IsZCoin(item_id):
                return "zcoins"
            if "tomes" in self.cats and Item.Type.IsTome(item_id) and model not in ELITE_TOME_MODELS:
                return "tomes"
            if "id_kits" in self.cats and Item.Usage.IsIDKit(item_id):
                return "id_kits"
            if "salvage_kits" in self.cats and Item.Usage.IsSalvageKit(item_id):
                return "salvage_kits"
            if item_type in GEAR_TYPES and self._gear_ok(item_id, item_type):
                rarity = str(Item.Rarity.GetRarity(item_id)[1])
                for key, name in GEAR_RARITIES.items():
                    if key in self.cats and rarity == name:
                        return key
        except Exception:
            return None
        return None

    def wants(self, item_id: int) -> bool:
        """True if this inventory item matches the selection and can be traded."""
        return self.match(item_id) is not None


# --- game helpers ---------------------------------------------------------
def _my_email() -> str:
    return str(Player.GetAccountEmail() or "").strip().lower()


def _account(email: str) -> AccountStruct | None:
    try:
        return GLOBAL_CACHE.ShMem.GetAccountDataFromEmail(email)
    except Exception:
        return None


def _same_party_and_instance(a: AccountStruct, b: AccountStruct) -> bool:
    try:
        pa, pb = int(a.AgentPartyData.PartyID), int(b.AgentPartyData.PartyID)
        ma, mb = a.AgentData.Map, b.AgentData.Map
        same_instance = (
            int(ma.MapID) == int(mb.MapID)
            and int(ma.Region) == int(mb.Region)
            and int(ma.District) == int(mb.District)
            and int(ma.Language) == int(mb.Language)
        )
        return pa != 0 and pa == pb and same_instance
    except Exception:
        return False


def _inventory_ids() -> list[int]:
    try:
        return [int(i) for i in ItemArray.GetItemArray(ItemArray.CreateBagList(1, 2, 3, 4))]
    except Exception:
        return []


def _storage_ids() -> list[int]:
    try:
        return [int(i) for i in ItemArray.GetItemArray(ItemArray.CreateBagList(*STORAGE_BAG_IDS))]
    except Exception:
        return []


def _storage_matches(sel: Selection, skip: set[int] | None = None) -> list[tuple[int, int]]:
    """(item id, quantity) of storage items the selection wants, biggest first.
    Send amounts are not applied here (see _storage_still_needed)."""
    found: list[tuple[int, int]] = []
    for item_id in _storage_ids():
        if skip and item_id in skip:
            continue
        if sel.match(item_id) is None:
            continue
        qty = _qty(item_id)
        if qty > 0:
            found.append((item_id, qty))
    found.sort(key=lambda s: -s[1])
    return found


def _free_slots() -> int:
    try:
        return int(GLOBAL_CACHE.Inventory.GetFreeSlotCount())
    except Exception:
        return 0


def _gold() -> int:
    try:
        return int(GLOBAL_CACHE.Inventory.GetGoldOnCharacter())
    except Exception:
        return 0


def _qty(item_id: int) -> int:
    try:
        return int(Item.Properties.GetQuantity(item_id) or 0)
    except Exception:
        return 0


def _send_group(sel: Selection, item_id: int, key: str) -> tuple[str, int] | None:
    """("item", item key) when this item has a send maximum, None if unlimited."""
    item_key = _dist_key(item_id)
    if sel.send.get(item_key, 0) <= 0:
        return None
    return ("item", item_key)


def _stacks_to_give(sel: Selection, limit: int, skip: set[int] | None = None,
                    sent: dict[tuple[str, int], int] | None = None) -> list[tuple[int, int]]:
    """(item id, quantity to offer), biggest first, at most `limit` stacks.

    Send maximums cap what a giver gives of an item, counting what it already
    gave this session (`sent`); the cut is made on the
    smallest stack (offering part of a stack is supported by the trade).
    """
    sent = sent or {}
    stacks: list[tuple[int, int]] = []
    capped: dict[tuple[str, int], list[tuple[int, int]]] = {}
    for item_id in _inventory_ids():
        if skip and item_id in skip:
            continue
        key = sel.match(item_id)
        if key is None:
            continue
        qty = _qty(item_id)
        if qty <= 0:
            continue
        group = _send_group(sel, item_id, key)
        if group is not None:
            capped.setdefault(group, []).append((item_id, qty))
        else:
            stacks.append((item_id, qty))

    for group, items in capped.items():
        to_give = sel.send[group[1]] - sent.get(group, 0)
        for item_id, qty in sorted(items, key=lambda s: -s[1]):
            if to_give <= 0:
                break
            give = min(qty, to_give)
            stacks.append((item_id, give))
            to_give -= give

    stacks.sort(key=lambda s: -s[1])
    return stacks[: max(0, limit)]


def _storage_still_needed(sel: Selection, sent: dict[tuple[str, int], int] | None = None,
                          skip: set[int] | None = None) -> list[tuple[int, int]]:
    """Storage stacks worth taking out: an item with a send amount is only taken
    while the bags plus what was already given do not reach that amount."""
    sent = sent or {}
    in_bags: dict[tuple[str, int], int] = {}
    for item_id in _inventory_ids():
        key = sel.match(item_id)
        group = _send_group(sel, item_id, key) if key is not None else None
        if group is not None:
            in_bags[group] = in_bags.get(group, 0) + _qty(item_id)
    out: list[tuple[int, int]] = []
    for item_id, qty in _storage_matches(sel, skip):
        key = sel.match(item_id)
        group = _send_group(sel, item_id, key) if key is not None else None
        if group is not None:
            if in_bags.get(group, 0) + sent.get(group, 0) >= sel.send[group[1]]:
                continue
            in_bags[group] = in_bags.get(group, 0) + qty  # the next stack may not be needed
        out.append((item_id, qty))
    return out


# --- trade window ----------------------------------------------------------
# False: open the trade like a player (target the main, press the Trade button).
# True: PyTrade.open_trade_window (now on the game thread; called directly
# from update() it crashed the client).
USE_NATIVE_OPEN = False
TRADE_BUTTON_TIMEOUT_S = 4.0


def _on_game_thread(label: str, fn: Callable[[], object]) -> None:
    """Run a game-mutating call on the GW game thread, like the library's
    NativeFunction does ("SAFE - always enqueued"). Calling PyTrade straight
    from update() crashed the client in open_trade_window."""

    def _invoke() -> None:
        try:
            fn()
        except Exception:
            return

    PyGameThread.enqueue(_invoke)


def _trade(fn: str, *args: int) -> bool:
    """Queue a PyTrade action on the game thread. Returns False only if PyTrade is missing."""
    if PyTrade is None:
        return False
    func = getattr(PyTrade, fn)
    _on_game_thread(f"PyTrade.{fn}{args}", lambda: func(*args))
    return True


def _click_frame(label: str, frame_id: str) -> bool:
    """Click a UI button on the game thread if it is on screen."""
    try:
        if not Frame(frame_id).is_usable:
            return False
    except Exception:
        return False
    _on_game_thread(f"click {label}", lambda: Frame(frame_id).click())
    return True


def _is_offered(item_id: int) -> bool:
    if PyTrade is None or not hasattr(PyTrade, "is_item_offered"):
        return True  # cannot check: the final inventory check is the ground truth
    try:
        result = bool(PyTrade.is_item_offered(item_id))
    except Exception:
        return True
    return result


# ==========================================================================
# MAIN (receiver)
# ==========================================================================
class MainCollector:
    def __init__(self) -> None:
        self.running: bool = False
        self.session: str = ""
        self.queue: list[str] = []
        self.current: str = ""
        self.selection: Selection = Selection.empty()
        self.results: dict[str, str] = {}
        self.names: dict[str, str] = {}
        self._last_heartbeat: float = 0.0
        self._last_poll: float = 0.0
        self._alt_started: float = 0.0
        self._handled_offer: int = -1
        self._offer_seen_at: float = 0.0
        self._submitted: bool = False
        self._last_accept: float = 0.0
        self._last_view: float = 0.0
        self.session_accounts: list[str] = []
        self.close_after: bool = DEFAULT_CLOSE_AFTER
        self._pay_pending: int = 0
        self._pay_round: int = 0
        self.paid: dict[str, int] = {}

    def start(self) -> None:
        if PyTrade is None:
            _log("Native PyTrade module not found: trading is impossible.", _MSG.Error)
            return
        me = _my_email()
        me_acc = _account(me)
        if me_acc is None:
            _log("Main account not found in shared memory.", _MSG.Error)
            return
        self.selection = Selection.from_options()
        if self.selection.is_empty():
            _log("Nothing selected.", _MSG.Warning)
            return
        self.queue, self.results, self.names, self.paid = [], {}, {}, {}
        self.close_after = _options().get_bool("Close", "after_trade", DEFAULT_CLOSE_AFTER)
        for acc in GLOBAL_CACHE.ShMem.GetAllAccountData():
            email = str(acc.AccountEmail or "").strip().lower()
            if not email or email == me or not _same_party_and_instance(me_acc, acc):
                continue
            if not _collect_is_target(email):  # unchecked in "Collect from"
                continue
            self.queue.append(email)
            self.names[email] = str(acc.AgentData.CharacterName or UNNAMED)
            self.results[email] = "waiting"
            try:
                GLOBAL_CACHE.ShMem.SendMessage(
                    me, email, SharedCommandType.EnableWidget, (0, 0, 0, 0), (WIDGET_NAME, "", "", "")
                )
            except Exception:
                pass
        if not self.queue:
            _log("No checked account in the same party and instance.", _MSG.Warning)
            return
        self.session_accounts = list(self.queue)
        self.session = str(int(time.time() * 1000))
        self.running = True
        _log(f"Collection started: {len(self.queue)} account(s).")
        self._next_alt()

    def stop(self, reason: str = "stop requested") -> None:
        if not self.running:
            return
        _trade("cancel_trade")
        if self.current:
            self.results[self.current] = f"interrupted ({reason})"
        self.running = False
        self.current = ""
        self.queue = []
        _publish(_request_doc(), {"session": self.session, "cancel": True, "ts": time.time()})
        _log(f"Collection stopped: {reason}.")

    def _write_request(self) -> None:
        fields: dict[str, object] = {
            "session": self.session,
            "cancel": False,
            "target": self.current,
            "main_email": _my_email(),
            "main_agent_id": int(Player.GetAgentID() or 0),
            "accounts": "|".join(self.session_accounts),  # every giver of this session
            "close_after": self.close_after,
            "free_slots": int(GLOBAL_CACHE.Inventory.GetFreeSlotCount()),
            "gold_room": max(0, MAX_CHARACTER_GOLD - _gold()),
            "ts": time.time(),
        }
        fields.update(self.selection.to_fields())
        _publish(_request_doc(), fields)
        self._last_heartbeat = time.monotonic()

    def _next_alt(self) -> None:
        self.current = self.queue.pop(0) if self.queue else ""
        self._handled_offer = -1
        self._submitted = False
        if not self.current:
            self.running = False
            _publish(_request_doc(), {"session": self.session, "cancel": True, "ts": time.time()})
            _log("Collection finished.", _MSG.Success)
            return
        self.results[self.current] = "request sent"
        self._alt_started = time.monotonic()
        self._write_request()

    def _set_payment(self, st: Settings) -> None:
        """Put the main's gold in the trade (before Submit Offer): pay_gold for
        every trade that carries items, bounded by the main's gold and by the
        giver's room under the 100k character cap."""
        self._pay_pending = 0  # an uncounted previous payment means that trade failed
        self._pay_round = st.get_int(_SECTION, "rounds", 0)
        want = self.selection.pay_gold
        items = st.get_int(_SECTION, "offer_items", 0)
        if want <= 0 or items <= 0:
            return
        room = max(0, MAX_CHARACTER_GOLD - st.get_int(_SECTION, "gold_now", 0))
        pay = min(want, _gold(), room)
        if pay < want:
            _log(f"Payment reduced to {pay} gold (main gold {_gold()}, giver room {room}).", _MSG.Warning)
        if pay > 0:
            _trade("submit_offer", pay)  # sets the offered gold amount only
            self._pay_pending = pay

    def _finish_alt(self, result: str) -> None:
        paid = self.paid.get(self.current, 0)
        self.results[self.current] = f"{result}, paid {paid} gold" if paid else result
        _trade("cancel_trade")  # in case a window is still open
        self._next_alt()

    def tick(self) -> None:
        if not self.running or not self.current:
            return
        now = time.monotonic()
        if now - self._last_heartbeat >= HEARTBEAT_S:
            self._write_request()  # also refreshes free slots / gold room for the giver

        # The giver's trade request shows a "View" button: open it.
        if now - self._last_view >= 1.0:
            self._last_view = now
            _click_frame("View button (trade request)", FrameId.ViewButton)

        # Accepting does not need fresh data every tick; reading the giver's status does.
        if now - self._last_poll >= POLL_S:
            self._last_poll = now
            st = _fresh(_status_doc(self.current))
            if st.get_str(_SECTION, "session", "") != self.session:
                if now - self._alt_started > ALT_NO_RESPONSE_S:
                    self._finish_alt("no answer (widget not running on that account?)")
                return
            state = st.get_str(_SECTION, "state", "")
            msg = st.get_str(_SECTION, "msg", "")
            self.results[self.current] = f"{state} - {msg}" if msg else state
            # A completed trade bumps the giver's round counter: count the payment then.
            if self._pay_pending and st.get_int(_SECTION, "rounds", 0) > self._pay_round:
                self.paid[self.current] = self.paid.get(self.current, 0) + self._pay_pending
                self._pay_pending = 0
            if state in ("done", "nothing", "error"):
                self._finish_alt({"done": f"done ({msg})", "nothing": "nothing to give",
                                  "error": f"error: {msg}"}[state])
                return
            if now - self._alt_started > ALT_TOTAL_TIMEOUT_S:
                self._finish_alt("total time limit reached")
                return
            if state == "offered":
                offer_id = st.get_int(_SECTION, "offer_id", 0)
                if offer_id != self._handled_offer:
                    self._handled_offer = offer_id
                    self._offer_seen_at = now
                    self._submitted = False
                    self._last_accept = 0.0
                    self._set_payment(st)
            elif state in ("moving", "opening", "retry"):
                self._handled_offer = -1

        # The giver submitted its offer: press Submit Offer once (empty offer),
        # then Accept. The Submit/Change Offer button toggles, hence "once".
        if self._handled_offer >= 0:
            if not self._submitted and now - self._offer_seen_at >= MAIN_SUBMIT_DELAY_S:
                if now - self._last_accept >= 0.5:
                    self._last_accept = now
                    if _click_frame("Submit Offer button", FrameId.SubmitOfferButton):
                        self._submitted = True
            elif self._submitted and now - self._last_accept >= ACCEPT_EVERY_S:
                _click_frame("Accept button", FrameId.AcceptButton)
                self._last_accept = now


# ==========================================================================
# GIVER (every other account)
# ==========================================================================
class AltGiver:
    def __init__(self) -> None:
        self.active: bool = False
        self.session: str = ""
        self.done_sessions: set[str] = set()
        self.seen_session: str = ""   # session this account was listed in (widget opened for it)
        self.closed_for: set[str] = set()  # sessions this account already closed itself for
        self.close_after: bool = False
        self.main_email: str = ""
        self.main_agent: int = 0
        self.selection: Selection = Selection.empty()
        self.free_slots: int = 0
        self.gold_room: int = 0
        self.gold_pending: int = 0
        self.state: str = "idle"
        self.msg: str = ""
        self.t: float = 0.0
        self.offer_id: int = 0
        self.rounds: int = 0
        self.given: int = 0
        self.gold_given: int = 0
        self.attempts: int = 0
        self.stacks: list[tuple[int, int]] = []
        self.qty_before: dict[int, int] = {}
        self.round_gold: int = 0
        self.gold_before: int = 0
        self.unofferable: set[int] = set()
        self.storage_tried: set[int] = set()  # storage items already withdrawn (or attempted)
        self.storage_done: bool = False       # storage unavailable or emptied for this session
        self.withdraw_quota: int = 0
        self.withdrawn: int = 0
        self.sent: dict[tuple[str, int], int] = {}          # given this session, per send-amount group
        self.stack_groups: dict[int, tuple[str, int]] = {}  # item id -> group, for the current round
        self._round_done_wall: float = 0.0  # wall time of the last completed trade
        self.offer_index: int = 0
        self._last_accept: float = 0.0
        self._last_move: float = 0.0
        self._last_poll: float = 0.0

    def _status(self, state: str, msg: str = "") -> None:
        self.msg = msg
        _publish(_status_doc(_my_email()), {
            "session": self.session, "state": state, "msg": msg, "offer_id": self.offer_id,
            "rounds": self.rounds, "given": self.given, "gold_given": self.gold_given,
            "offer_items": len(self.stacks), "gold_now": _gold(), "ts": time.time(),
        })

    def _end(self, state: str, msg: str) -> None:
        if self.state in ("press_trade", "offer", "verify", "submitting", "accepting"):
            _trade("cancel_trade")
        self._status(state, msg)
        self.done_sessions.add(self.session)
        self.active = False
        self.state = "idle"
        _log(f"Giving to main: {state} ({msg}).")
        if self.close_after:
            _close_self("trade finished")

    def _go(self, state: str) -> None:
        self.state = state
        self.t = time.monotonic()

    def _summary(self) -> str:
        parts = [f"{self.given} item(s) in {self.rounds} trade(s)"]
        if self.withdrawn:
            parts.append(f"{self.withdrawn} taken from storage")
        if self.gold_given:
            parts.append(f"{self.gold_given} gold")
        return ", ".join(parts)

    def tick(self, main_running_here: bool) -> None:
        me = _my_email()
        if not me or main_running_here:
            return
        now = time.monotonic()
        if now - self._last_poll < POLL_S and not self.active:
            return
        if now - self._last_poll >= POLL_S:
            self._last_poll = now
            req = _fresh(_request_doc())
        else:
            req = _request_doc()
        session = req.get_str(_SECTION, "session", "")
        cancelled = req.get_bool(_SECTION, "cancel", True)
        stale = time.time() - req.get_float(_SECTION, "ts", 0.0) > STALE_REQUEST_S

        if self.active:
            if session != self.session or cancelled or stale:
                self._end("error", "cancelled by the main")
                return
            # Only trust the main's numbers once it has republished after our last trade;
            # until then keep our own (decremented) estimate.
            if req.get_float(_SECTION, "ts", 0.0) > self._round_done_wall:
                self.free_slots = req.get_int(_SECTION, "free_slots", self.free_slots)
                self.gold_room = req.get_int(_SECTION, "gold_room", self.gold_room)
            self._step()
            return

        listed = me in req.get_str(_SECTION, "accounts", "").lower().split("|")
        if session and listed and not cancelled and not stale:
            self.seen_session = session
            self.close_after = req.get_bool(_SECTION, "close_after", False)
        elif session and session not in self.closed_for and session not in self.done_sessions and (
            (self.seen_session == session and (cancelled or stale))   # ended while we waited
            or (listed and cancelled and not stale)                   # stopped before we even looked
        ):
            self.closed_for.add(session)
            self.seen_session = ""
            if req.get_bool(_SECTION, "close_after", False):
                _close_self("collection stopped by the main")
            return
        if cancelled or stale or session in self.done_sessions:
            return
        if req.get_str(_SECTION, "target", "").lower() != me:
            return
        self.session = session
        main_email = req.get_str(_SECTION, "main_email", "").lower()
        main_acc, me_acc = _account(main_email), _account(me)
        if main_acc is None or me_acc is None or not _same_party_and_instance(main_acc, me_acc):
            self._end("error", "the main is not in the same party / instance")
            return
        self.active = True
        self.main_email = main_email
        self.main_agent = req.get_int(_SECTION, "main_agent_id", 0)
        self.selection = Selection.from_doc(req)
        self.free_slots = req.get_int(_SECTION, "free_slots", 0)
        self.gold_room = req.get_int(_SECTION, "gold_room", 0)
        self.gold_pending = max(0, _gold() - self.selection.gold_keep) if self.selection.give_gold else 0
        self.offer_id = 0
        self.rounds = 0
        self.given = 0
        self.gold_given = 0
        self.attempts = 0
        self.unofferable = set()
        self.storage_tried = set()
        self.storage_done = not self.selection.from_storage
        self.withdraw_quota = 0
        self.withdrawn = 0
        self.sent = {}
        self.stack_groups = {}
        self._round_done_wall = 0.0
        _log("Trade request received from the main.")
        self._go("collect")

    def _step(self) -> None:
        now = time.monotonic()
        el = now - self.t

        if self.state == "collect":
            if el < (ROUND_PAUSE_S if self.rounds or self.attempts else 0.0):
                return
            limit = min(MAX_STACKS_PER_TRADE, self.free_slots)
            if not self.storage_done and limit > 0:
                in_bags = len(_stacks_to_give(self.selection, limit, self.unofferable, self.sent))
                quota = min(limit - in_bags, _free_slots())
                if quota > 0 and _storage_still_needed(self.selection, self.sent, self.storage_tried):
                    self.withdraw_quota = quota
                    self._status("storage", f"taking from storage ({quota} stack(s) max)")
                    GLOBAL_CACHE.Inventory.OpenXunlaiWindow()
                    self._go("open_storage")
                    return
                if quota > 0:
                    self.storage_done = True  # nothing (more) to take from storage
            self.stacks = _stacks_to_give(self.selection, limit, self.unofferable, self.sent) if limit > 0 else []
            self.stack_groups = {}
            for item_id, _q in self.stacks:
                key = self.selection.match(item_id)
                group = _send_group(self.selection, item_id, key) if key is not None else None
                if group is not None:
                    self.stack_groups[item_id] = group
            self.round_gold = min(self.gold_pending, self.gold_room)
            if not self.stacks and self.round_gold <= 0:
                leftovers = _stacks_to_give(self.selection, 1, self.unofferable, self.sent)
                if leftovers and limit <= 0:
                    self._end("error", f"the main has no room left ({self._summary()})")
                elif self.rounds == 0:
                    self._end("nothing", "no item to give")
                else:
                    self._end("done", self._summary())
                return
            what = f"{len(self.stacks)} stack(s)" + (f" + {self.round_gold} gold" if self.round_gold else "")
            self._status("moving", f"trade {self.rounds + 1}: {what}")
            self._go("approach")
            return

        if self.state == "open_storage":
            if GLOBAL_CACHE.Inventory.IsStorageOpen():
                self._go("withdraw")
                return
            if el > STORAGE_OPEN_TIMEOUT_S:
                _log("Xunlai storage did not open: only the bags are used.", _MSG.Warning)
                self.storage_done = True
                self._go("collect")
            return

        if self.state == "withdraw":
            if el < WITHDRAW_GAP_S:
                return
            candidates = _storage_still_needed(self.selection, self.sent, self.storage_tried)
            if self.withdraw_quota <= 0 or not candidates or _free_slots() <= 0:
                if not candidates:
                    self.storage_done = True
                self._go("collect")
                return
            item_id, qty = candidates[0]
            self.storage_tried.add(item_id)
            if GLOBAL_CACHE.Inventory.WithdrawItemFromStorage(item_id):
                self.withdraw_quota -= 1
                self.withdrawn += qty
            self._go("withdraw")  # restart the gap timer
            return

        if self.state == "approach":
            if not Agent.IsValid(self.main_agent):
                self._end("error", "main not found on the map")
                return
            mx, my = Agent.GetXY(self.main_agent)
            if Utils.Distance(Player.GetXY(), (mx, my)) <= APPROACH_RANGE:
                self._go("open")
                return
            if el > APPROACH_TIMEOUT_S:
                self._end("error", "cannot reach the main")
                return
            if now - self._last_move >= 1.0:
                Player.Move(mx, my)
                self._last_move = now
            return

        if self.state == "open":
            if el < 0.2:
                return
            if USE_NATIVE_OPEN:
                _trade("open_trade_window", self.main_agent)
                self._status("opening", "opening the trade")
                self.offer_index = 0
                self._go("offer")
                return
            # Same as a player: target the main, then press the Trade button
            # shown next to the target display.
            Player.ChangeTarget(self.main_agent)
            self._status("opening", "opening the trade")
            self._go("press_trade")
            return

        if self.state == "press_trade":
            if el < 0.6:
                return
            if _click_frame("Trade button", FrameId.TradeButton.Button):
                self.offer_index = 0
                self._go("offer")
                return
            if el > TRADE_BUTTON_TIMEOUT_S:
                self._retry("Trade button not found next to the target")
                return
            if now - self._last_move >= 1.0:
                Player.ChangeTarget(self.main_agent)  # target may have been lost
                self._last_move = now
            return

        if self.state == "offer":
            if el < OPEN_WAIT_S + self.offer_index * OFFER_GAP_S:
                return
            if self.offer_index < len(self.stacks):
                item_id, qty = self.stacks[self.offer_index]
                _trade("offer_item", item_id, qty)
                self.offer_index += 1
                return
            self._go("verify")
            return

        if self.state == "verify":
            if el < VERIFY_WAIT_S:
                return
            offered = [(i, q) for i, q in self.stacks if _is_offered(i)]
            refused = [i for i, _ in self.stacks if i not in {o for o, _ in offered}]
            if refused and offered:
                # The game refused some items (untradable...): never try them again.
                self.unofferable.update(refused)
                _log(f"{len(refused)} item(s) refused by the trade window, skipped.", _MSG.Warning)
            if not offered and self.round_gold <= 0:
                self.unofferable.update(refused)
                self._retry("items refused by the trade window")
                return
            self.stacks = offered
            self.qty_before = {i: _qty(i) for i, _ in self.stacks}
            self.gold_before = _gold()
            if self.round_gold > 0:
                # PyTrade.submit_offer only sets the offered gold amount (it does
                # not lock the offer): the Submit Offer button does that.
                _trade("submit_offer", self.round_gold)
            self._go("submitting")
            return

        if self.state == "submitting":
            if el < SUBMIT_DELAY_S:
                return
            # The Submit/Change Offer button toggles: press it exactly once.
            if _click_frame("Submit Offer button", FrameId.SubmitOfferButton):
                self.offer_id += 1
                what = f"{len(self.stacks)} stack(s)" + (f" + {self.round_gold} gold" if self.round_gold else "")
                self._status("offered", f"offer submitted ({what}), waiting for the main")
                self._last_accept = now
                self._go("accepting")
                return
            if el > SUBMIT_TIMEOUT_S:
                self._retry("Submit Offer button not found")
            return

        if self.state == "accepting":
            # A stack may be offered partly (send amounts): check quantities, not presence.
            inv = set(_inventory_ids())
            items_gone = all(
                i not in inv or _qty(i) <= self.qty_before.get(i, q) - q for i, q in self.stacks
            )
            # The main may add gold (pay_gold) to a trade that carries items:
            # the giver's gold then ends at most that much higher.
            paid = self.selection.pay_gold if self.stacks else 0
            gold_gone = self.round_gold <= 0 or _gold() <= self.gold_before - self.round_gold + paid
            if items_gone and gold_gone:
                self.given += sum(q for _, q in self.stacks)
                for item_id, q in self.stacks:
                    group = self.stack_groups.get(item_id)
                    if group is not None:
                        self.sent[group] = self.sent.get(group, 0) + q
                self.gold_given += self.round_gold
                self.gold_pending = max(0, self.gold_pending - self.round_gold)
                self.free_slots = max(0, self.free_slots - len(self.stacks))
                self.gold_room = max(0, self.gold_room - self.round_gold)
                self._round_done_wall = time.time()
                self.rounds += 1
                self.attempts = 0
                self._status("round_done", f"trade {self.rounds} completed")
                self._go("collect")
                return
            if el > ACCEPT_TIMEOUT_S:
                self._retry("the main did not accept in time")
                return
            if now - self._last_accept >= ACCEPT_EVERY_S:
                _click_frame("Accept button", FrameId.AcceptButton)
                self._last_accept = now

    def _retry(self, why: str) -> None:
        _trade("cancel_trade")
        self.attempts += 1
        if self.attempts >= MAX_ATTEMPTS:
            self._end("error", why)
            return
        self._status("retry", f"{why} - new attempt {self.attempts + 1}/{MAX_ATTEMPTS}")
        self._go("collect")


# ==========================================================================
# PREVIEW: each giver lists what it would give, before any trade
# ==========================================================================
def _raw_item_name(item_id: int) -> str:
    """The game's item name, markup included ("<c=@ItemCommon>26 Pumpkin Cookies</c>"),
    or "" while it is still loading (the request is sent)."""
    try:
        if Item.IsNameReady(item_id):
            return str(Item.GetName(item_id) or "").strip()
        Item.RequestName(item_id)
    except Exception:
        pass
    return ""


def _clean_item_name(raw: str) -> str:
    """Visible name only: no colour tags (library ImGui.strip_markdown), no stack count."""
    text = ImGui.strip_markdown(raw)
    text = re.sub(r"<[^>]*>", "", text)    # any tag left inside
    text = re.sub(r"^\d+\s+", "", text)   # "26 Pumpkin Cookies" -> "Pumpkin Cookies"
    return re.sub(r"[|\r\n]", " ", text).strip()


def _item_label(item_id: int, model: int) -> str:
    name = _clean_item_name(_raw_item_name(item_id))
    return name or f"model {model}"


def _preview_lines(sel: Selection) -> tuple[list[str], bool]:
    """('name xQty' lines aggregated by item name, all names ready?)."""
    totals: dict[str, int] = {}
    names_ready = True
    for item_id, qty in _stacks_to_give(sel, 10_000):
        model = int(Item.GetModelID(item_id))
        label = _item_label(item_id, model)
        if label.startswith("model "):
            names_ready = False
        totals[label] = totals.get(label, 0) + qty
    lines = [f"{name} x{qty}" for name, qty in sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))]
    if sel.from_storage:
        stored: dict[str, int] = {}
        for item_id, qty in _storage_still_needed(sel):
            label = _item_label(item_id, int(Item.GetModelID(item_id)))
            if label.startswith("model "):
                names_ready = False
            stored[label] = stored.get(label, 0) + qty
        lines += [f"{name} x{qty} (storage)" for name, qty in sorted(stored.items(), key=lambda kv: (-kv[1], kv[0]))]
    if sel.give_gold:
        gold = max(0, _gold() - sel.gold_keep)
        if gold:
            lines.append(f"Gold: {gold}")
    return lines, names_ready


class PreviewResponder:
    """Giver side: answers the main's preview request (read-only, nothing traded)."""

    def __init__(self) -> None:
        self.session: str = ""
        self.started: float = 0.0
        self.final: bool = True
        self.sig: str = ""
        self._last_poll: float = 0.0

    def tick(self, busy: bool) -> None:
        me = _my_email()
        now = time.monotonic()
        if not me or busy or now - self._last_poll < POLL_S:
            return
        self._last_poll = now
        doc = _fresh(_preview_doc())
        session = doc.get_str(_PREVIEW, "session", "")
        if not session or time.time() - doc.get_float(_PREVIEW, "ts", 0.0) > PREVIEW_STALE_S:
            return
        if session != self.session:
            main_acc, me_acc = _account(doc.get_str(_PREVIEW, "main_email", "").lower()), _account(me)
            if main_acc is None or me_acc is None or not _same_party_and_instance(main_acc, me_acc):
                return
            self.session, self.started, self.final = session, now, False
        sig = doc.get_str(_PREVIEW, "sig", "")
        if sig != self.sig:  # the main changed its selection: recompute
            self.sig, self.started, self.final = sig, now, False
        if self.final:
            return
        lines, names_ready = _preview_lines(Selection.from_doc(doc, _PREVIEW))
        self.final = names_ready or now - self.started > PREVIEW_NAME_WAIT_S
        shown = lines[:PREVIEW_MAX_LINES]
        if len(lines) > PREVIEW_MAX_LINES:
            shown.append(f"... and {len(lines) - PREVIEW_MAX_LINES} more")
        _publish(_status_doc(me), {
            "session": session, "lines": "|".join(shown), "count": len(lines), "ts": time.time(),
        }, _PREVIEW)


class PreviewViewer:
    """Main side: sends the preview request and collects the answers."""

    def __init__(self) -> None:
        self.session: str = ""
        self.emails: list[str] = []
        self.names: dict[str, str] = {}
        self.answers: dict[str, list[str]] = {}
        self._last_read: float = 0.0
        self._last_heartbeat: float = 0.0

    @property
    def open(self) -> bool:
        return bool(self.session)

    def start(self) -> None:
        me = _my_email()
        me_acc = _account(me)
        if me_acc is None:
            _log("Main account not found in shared memory.", _MSG.Error)
            return
        sel = Selection.from_options()
        if sel.is_empty():
            _log("Nothing selected.", _MSG.Warning)
            return
        self.emails, self.names, self.answers = [], {}, {}
        for acc in GLOBAL_CACHE.ShMem.GetAllAccountData():
            email = str(acc.AccountEmail or "").strip().lower()
            if not email or email == me or not _same_party_and_instance(me_acc, acc):
                continue
            if not _collect_is_target(email):  # unchecked in "Collect from"
                continue
            self.emails.append(email)
            self.names[email] = str(acc.AgentData.CharacterName or UNNAMED)
            try:
                GLOBAL_CACHE.ShMem.SendMessage(
                    me, email, SharedCommandType.EnableWidget, (0, 0, 0, 0), (WIDGET_NAME, "", "", "")
                )
            except Exception:
                pass
        if not self.emails:
            _log("No checked account in the same party and instance.", _MSG.Warning)
            return
        self.session = f"p{int(time.time() * 1000)}"
        self._publish_request(sel)

    def _publish_request(self, sel: Selection) -> None:
        sel_fields = sel.to_fields()
        fields: dict[str, object] = {
            "session": self.session, "main_email": _my_email(), "ts": time.time(),
            "sig": "|".join(f"{k}={v}" for k, v in sorted(sel_fields.items())),
        }
        fields.update(sel_fields)
        _publish(_preview_doc(), fields, _PREVIEW)
        self._last_heartbeat = time.monotonic()

    def close(self) -> None:
        if self.session:
            _publish(_preview_doc(), {"session": "", "ts": 0.0}, _PREVIEW)
        self.session = ""

    def tick(self) -> None:
        if not self.session:
            return
        now = time.monotonic()
        if now - self._last_heartbeat >= HEARTBEAT_S:
            self._publish_request(Selection.from_options())  # follows checkbox changes
        if now - self._last_read < POLL_S:
            return
        self._last_read = now
        for email in self.emails:
            st = _fresh(_status_doc(email))
            if st.get_str(_PREVIEW, "session", "") != self.session:
                continue
            raw = st.get_str(_PREVIEW, "lines", "")
            self.answers[email] = [line for line in raw.split("|") if line]


# ==========================================================================
# DISTRIBUTION: the main sends the same quantity to every other account
# ==========================================================================
# The roles are reversed: the main opens the trade, drops the items, submits
# and accepts; the other account submits an empty offer and accepts.
# The main's four bags are used, plus its storage when "use_storage" is on.
# An item the main cannot cover for EVERY account is not sent at all.
DIST_SECTION = "Distribute"
DIST_MAX_PER_ACCOUNT = 5000
DIST_DEFAULT_PAY = 1000  # gold each receiving account pays per trade, like the main does when collecting


def _dist_pay_gold() -> int:
    return max(0, min(MAX_CHARACTER_GOLD, _options().get_int(DIST_SECTION, "pay_per_trade", DIST_DEFAULT_PAY)))

DIST_CACHE_S = 1.0


def _dist_doc() -> Settings:
    return Settings("Widgets/PartyTradeCollector/distribute.ini", "global")


# Always listed first, even when the main holds none, and never hidden by the
# tradable flag (the trade window's verify step is the final judge).
DIST_PINNED_MODELS: list[int] = sorted(RES_SCROLL_MODELS)
_dist_labels: dict[int, str] = {}    # model -> item name seen in the main's bags / storage
_dist_colors: dict[int, Color] = {}  # model -> rarity colour of that name

# "Main -> Alts" tab: the main's items grouped in the same sections, in the same order,
# as the "Alts -> Main" tab. Equipment is never sent in this direction.
DIST_TOMES = "Tomes"
DIST_DYES = DYE_LIST_TITLE
DIST_OTHER = "Other items on this character"
DIST_GEAR = "gear"
DIST_HIDDEN: frozenset[str] = frozenset({DIST_GEAR})  # never listed, never sent
_DIST_LIST_SECTIONS: list[tuple[str, list[tuple[int, str]]]] = (
    ITEM_LISTS + [(KEY_LIST_TITLE, KEY_ITEMS)]
    + [(f"Consumables - {t}", items) for t, items in CONSUMABLE_LISTS] + COIN_LISTS + MISC_LISTS
)
DIST_SECTION_ORDER: list[str] = (
    [t for t, _ in ITEM_LISTS] + [DIST_DYES, KEY_LIST_TITLE, DIST_TOMES]
    + [f"Consumables - {t}" for t, _ in CONSUMABLE_LISTS] + [t for t, _ in COIN_LISTS + MISC_LISTS] + [DIST_OTHER]
)
_DIST_SECTION_OF_MODEL: dict[int, str] = {}
for _title, _items in _DIST_LIST_SECTIONS:
    for _m, _ in _items:
        _DIST_SECTION_OF_MODEL.setdefault(_m, _title)
_dist_kinds: dict[int, str] = {}  # model -> section found from the item type ("" = none)
# Every listed item, shown in its section even when the main holds none (dyes by colour key).
DIST_LISTED: list[tuple[str, list[int]]] = [
    (title, [m for m, _ in items]) for title, items in _DIST_LIST_SECTIONS
] + [(DIST_DYES, [DYE_KEY_BASE + c for c, _ in DYE_ITEMS])]
SEND_ITEM_KEYS: list[int] = list(dict.fromkeys(m for _, ms in DIST_LISTED for m in ms))
_DIST_LIST_LABEL: dict[int, str] = {}
for _title, _items in _DIST_LIST_SECTIONS:
    for _m, _label in _items:
        _DIST_LIST_LABEL.setdefault(_m, _label)


def _remember_kind(item_id: int, model: int) -> None:
    if model in _dist_kinds or model in _DIST_SECTION_OF_MODEL:
        return
    kind = ""
    try:
        item_type = int(Item.GetItemType(item_id)[0])
        if item_type in GEAR_TYPES:
            kind = DIST_GEAR
        elif Item.Type.IsTome(item_id):
            kind = DIST_TOMES
    except Exception:
        pass
    _dist_kinds[model] = kind


def _dist_section_of(model: int) -> str:
    if model > DYE_KEY_BASE:
        return DIST_DYES
    return _DIST_SECTION_OF_MODEL.get(model) or _dist_kinds.get(model) or DIST_OTHER


def _dist_qty_key(model: int) -> str:
    return f"m{model}"


def _dist_per_account(model: int) -> int:
    return max(0, min(DIST_MAX_PER_ACCOUNT, _options().get_int(DIST_SECTION, _dist_qty_key(model), 0)))


def _dist_plan_from_options() -> dict[int, int]:
    """model -> quantity to send to EACH account (only models listed for the main)."""
    _n, bags, stored = _dist_context()
    models = set(DIST_PINNED_MODELS) | set(bags) | set(stored) | {m for _, ms in DIST_LISTED for m in ms}
    return {m: q for m in models if _dist_section_of(m) not in DIST_HIDDEN and (q := _dist_per_account(m)) > 0}


def _model_label(model: int) -> str:
    if model > DYE_KEY_BASE:
        return dict(DYE_ITEMS).get(model - DYE_KEY_BASE, "Dye")
    name = _dist_labels.get(model, "") or _DIST_LIST_LABEL.get(model, "")
    if name:
        return name
    try:
        return ModelID(model).name.replace("_", " ")
    except Exception:
        return f"model {model}"


def _giveable(item_id: int) -> bool:
    try:
        if Item.Properties.IsCustomized(item_id):
            return False
        if int(Item.GetModelID(item_id)) in RES_SCROLL_MODELS:
            return True
        try:
            return bool(Item.Properties.IsTradable(item_id))
        except Exception:
            return True  # unknown: the trade window decides (verify step)
    except Exception:
        return False


def _remember_label(item_id: int, model: int) -> None:
    if model in _dist_labels or model > DYE_KEY_BASE:
        return
    raw = _raw_item_name(item_id)
    name = _clean_item_name(raw)
    if name:
        _dist_labels[model] = name
        color = ImGui.get_markdown_color(raw)  # rarity colour from the name's tag
        if color is not None:
            _dist_colors[model] = color


def _bag_stock() -> dict[int, int]:
    """model -> quantity of tradable items in the four bags."""
    stock: dict[int, int] = {}
    for item_id in _inventory_ids():
        qty = _qty(item_id)
        if qty > 0 and _giveable(item_id):
            model = _dist_key(item_id)
            stock[model] = stock.get(model, 0) + qty
            _remember_label(item_id, model)
            _remember_kind(item_id, model)
    return stock


def _storage_stock() -> dict[int, int]:
    """model -> quantity of tradable items in Xunlai storage (incl. material storage)."""
    stock: dict[int, int] = {}
    for item_id in _storage_ids():
        qty = _qty(item_id)
        if qty > 0 and _giveable(item_id):
            model = _dist_key(item_id)
            stock[model] = stock.get(model, 0) + qty
            _remember_label(item_id, model)
            _remember_kind(item_id, model)
    return stock


def _dist_use_storage() -> bool:
    return _options().get_bool(DIST_SECTION, "use_storage", False)


def _party_others(me_acc: AccountStruct) -> list[tuple[str, str]]:
    """(email, character name) of the other accounts in the same party and instance."""
    me = _my_email()
    out: list[tuple[str, str]] = []
    for acc in GLOBAL_CACHE.ShMem.GetAllAccountData():
        email = str(acc.AccountEmail or "").strip().lower()
        if email and email != me and _same_party_and_instance(me_acc, acc):
            out.append((email, str(acc.AgentData.CharacterName or UNNAMED)))
    return out


def _dist_stacks(remaining: dict[int, int], limit: int, skip: set[int]) -> list[tuple[int, int, int]]:
    """(item id, quantity to offer, model) from the bags, biggest stacks first."""
    rem = dict(remaining)
    items: list[tuple[int, int, int]] = []
    for item_id in _inventory_ids():
        if item_id in skip:
            continue
        qty = _qty(item_id)
        if qty <= 0:
            continue
        model = _dist_key(item_id)
        if rem.get(model, 0) > 0 and _giveable(item_id):
            items.append((item_id, qty, model))
    items.sort(key=lambda s: -s[1])
    out: list[tuple[int, int, int]] = []
    for item_id, qty, model in items:
        if len(out) >= limit:
            break
        want = rem.get(model, 0)
        if want <= 0:
            continue
        give = min(qty, want)
        out.append((item_id, give, model))
        rem[model] = want - give
    return out


class MainDistributor:
    """Main side: visits every other account and gives it the planned quantities."""

    TRADE_STATES = ("press_trade", "offer", "verify", "submitting", "accepting")

    def __init__(self) -> None:
        self.running: bool = False
        self.session: str = ""
        self.queue: list[str] = []
        self.accounts: list[str] = []
        self.done_accounts: list[str] = []
        self.current: str = ""
        self.names: dict[str, str] = {}
        self.results: dict[str, str] = {}
        self.plan: dict[int, int] = {}
        self.remaining: dict[int, int] = {}
        self.close_after: bool = DEFAULT_CLOSE_AFTER
        self.state: str = "idle"
        self.t: float = 0.0
        self.alt_agent: int = 0
        self.alt_slots: int = 0
        self.alt_started: float = 0.0
        self.alt_ready: bool = False
        self.stacks: list[tuple[int, int, int]] = []
        self.qty_before: dict[int, int] = {}
        self.offer_id: int = 0
        self.offer_index: int = 0
        self.rounds: int = 0
        self.sent: int = 0
        self.attempts: int = 0
        self.unofferable: set[int] = set()
        self._round_done_wall: float = 0.0
        self._last_heartbeat: float = 0.0
        self._last_poll: float = 0.0
        self._last_move: float = 0.0
        self._last_accept: float = 0.0
        self.pay_gold: int = 0                    # gold each receiver pays per trade (0 = nothing)
        self.paid: dict[str, int] = {}            # account -> gold received from it
        self.withdraw_need: dict[int, int] = {}   # model -> units still to take out of storage
        self.withdraw_tried: set[int] = set()     # storage item ids already withdrawn from

    # --- session -----------------------------------------------------------
    def start(self) -> None:
        if PyTrade is None:
            _log("Native PyTrade module not found: trading is impossible.", _MSG.Error)
            return
        me = _my_email()
        me_acc = _account(me)
        if me_acc is None:
            _log("Main account not found in shared memory.", _MSG.Error)
            return
        plan = _dist_plan_from_options()
        if not plan:
            _log("Nothing to send: set a quantity per account first.", _MSG.Warning)
            return
        party = _party_others(me_acc)
        if not party:
            _log("No other account in the same party and instance.", _MSG.Warning)
            return
        others = _dist_targets(party)  # only the accounts checked above the list
        if not others:
            _log("No account checked in 'Send to'.", _MSG.Warning)
            return
        bags, n = _bag_stock(), len(others)
        use_storage = _dist_use_storage()
        stored = _storage_stock() if use_storage else {}
        where = "bags + storage" if use_storage else "bags"
        kept: dict[int, int] = {}
        self.withdraw_need = {}
        for model, qty in plan.items():
            need = _dist_need(model, qty, n)  # what is sent + what the main keeps
            have = bags.get(model, 0) + stored.get(model, 0)
            if have < need:
                keep = _dist_keep(model)
                _log(f"{_model_label(model)}: {need} needed for {n} account(s)"
                     + (f" (incl. {keep} kept)" if keep else "") + f", only {have} in the {where}: not sent.",
                     _MSG.Warning)
                continue
            kept[model] = qty
            if bags.get(model, 0) < need:
                self.withdraw_need[model] = need - bags.get(model, 0)
        if not kept:
            _log(f"Distribution not started: the {where} do not hold enough for every account.", _MSG.Warning)
            return
        self.plan = kept
        self.accounts = [e for e, _ in others]
        self.queue = list(self.accounts)
        self.names = dict(others)
        self.results = {e: "waiting" for e in self.accounts}
        self.done_accounts = []
        self.offer_id = 0
        self.close_after = _options().get_bool("Close", "after_trade", DEFAULT_CLOSE_AFTER)
        self.pay_gold = _dist_pay_gold()
        self.paid = {}
        for email in self.accounts:
            try:
                GLOBAL_CACHE.ShMem.SendMessage(
                    me, email, SharedCommandType.EnableWidget, (0, 0, 0, 0), (WIDGET_NAME, "", "", "")
                )
            except Exception:
                pass
        self.session = f"d{int(time.time() * 1000)}"
        self.running = True
        what = ", ".join(f"{_model_label(m)} x{q}" for m, q in kept.items())
        _log(f"Distribution started: {what} to each of {n} account(s).")
        if self.withdraw_need:
            # Take the missing units out of storage first, then serve the accounts.
            self.current = ""
            self.withdraw_tried = set()
            _log("Taking the missing units out of storage first.")
            GLOBAL_CACHE.Inventory.OpenXunlaiWindow()
            self._publish()
            self._go("open_storage")
            return
        self._next_alt()

    def stop(self, reason: str = "stop requested") -> None:
        if not self.running:
            return
        _trade("cancel_trade")
        if self.current:
            self.results[self.current] = f"interrupted ({reason}), {self._summary()}"
        self.running = False
        self.current = ""
        self.queue = []
        self._publish({"cancel": True})
        _log(f"Distribution stopped: {reason}.")

    def _publish(self, extra: dict[str, object] | None = None) -> None:
        fields: dict[str, object] = {
            "session": self.session,
            "cancel": False,
            "target": self.current,
            "main_email": _my_email(),
            "accounts": "|".join(self.accounts),
            "done": "|".join(self.done_accounts),
            "close_after": self.close_after,
            "offer_id": self.offer_id,
            "pay_gold": self.pay_gold,                      # gold each receiver adds to every trade
            "gold_room": max(0, MAX_CHARACTER_GOLD - _gold()),  # the main's room under the 100k cap
            "ts": time.time(),
        }
        fields.update(extra or {})
        _publish(_dist_doc(), fields, DIST_SECTION)
        self._last_heartbeat = time.monotonic()

    def _summary(self) -> str:
        paid = self.paid.get(self.current, 0)
        return f"{self.sent} item(s) in {self.rounds} trade(s)" + (f", received {paid} gold" if paid else "")

    def _next_alt(self) -> None:
        self.current = self.queue.pop(0) if self.queue else ""
        if not self.current:
            self.running = False
            self._publish({"cancel": True})
            _log("Distribution finished.", _MSG.Success)
            return
        self.remaining = dict(self.plan)
        self.alt_agent = 0
        self.alt_slots = 0
        self.alt_ready = False
        self.rounds = 0
        self.sent = 0
        self.attempts = 0
        self.unofferable = set()
        self._round_done_wall = 0.0
        self.alt_started = time.monotonic()
        self.results[self.current] = "request sent"
        self._go("wait_ready")
        self._publish()

    def _finish_alt(self, result: str) -> None:
        if self.state in self.TRADE_STATES:
            _trade("cancel_trade")
        self.results[self.current] = result
        self.done_accounts.append(self.current)
        self._next_alt()

    def _go(self, state: str) -> None:
        self.state = state
        self.t = time.monotonic()

    def _retry(self, why: str) -> None:
        _trade("cancel_trade")
        self.attempts += 1
        if self.attempts >= MAX_ATTEMPTS:
            self._finish_alt(f"error: {why} ({self._summary()})")
            return
        self.results[self.current] = f"{why} - new attempt {self.attempts + 1}/{MAX_ATTEMPTS}"
        self._go("collect")

    # --- loop --------------------------------------------------------------
    def _prep_step(self, now: float) -> None:
        """Storage phase, before the first account: withdraw only the missing units."""
        el = now - self.t
        if self.state == "open_storage":
            if GLOBAL_CACHE.Inventory.IsStorageOpen():
                self._go("withdraw")
            elif el > STORAGE_OPEN_TIMEOUT_S:
                _log("Xunlai storage did not open: only the bags are used.", _MSG.Warning)
                self._go("prep_check")
            return
        if self.state == "withdraw":
            if el < WITHDRAW_GAP_S:
                return
            pick: tuple[int, int, int] | None = None  # (item id, amount, model)
            if _free_slots() > 0:
                for item_id in _storage_ids():
                    if item_id in self.withdraw_tried:
                        continue
                    model = _dist_key(item_id)
                    want = self.withdraw_need.get(model, 0)
                    qty = _qty(item_id)
                    if want > 0 and qty > 0 and _giveable(item_id):
                        pick = (item_id, min(qty, want), model)
                        break
            if pick is None:
                self._go("prep_check")
                return
            item_id, amount, model = pick
            self.withdraw_tried.add(item_id)
            if GLOBAL_CACHE.Inventory.WithdrawItemFromStorage(item_id, amount):
                self.withdraw_need[model] = max(0, self.withdraw_need.get(model, 0) - amount)
            self._go("withdraw")  # restart the gap timer
            return
        if self.state == "prep_check":
            if el < 1.5:  # let the moves land in the bags
                return
            bags, n = _bag_stock(), len(self.accounts)
            short = any(bags.get(m, 0) < _dist_need(m, q, n) for m, q in self.plan.items())
            if short and el < 6.0:
                return  # queued moves may still be landing

            for model, qty in list(self.plan.items()):
                need, have = _dist_need(model, qty, n), bags.get(model, 0)
                if have < need:
                    _log(f"{_model_label(model)}: only {have} of {need} in the bags after storage "
                         "(bags full?): not sent.", _MSG.Warning)
                    del self.plan[model]
            if not self.plan:
                self.running = False
                self._publish({"cancel": True})
                _log("Distribution stopped: not enough room in the bags for the storage items.", _MSG.Warning)
                return
            self._next_alt()

    def tick(self) -> None:
        if not self.running:
            return
        now = time.monotonic()
        if now - self._last_heartbeat >= HEARTBEAT_S:
            self._publish()
        if self.state in ("open_storage", "withdraw", "prep_check"):
            self._prep_step(now)
            return
        if not self.current:
            return
        if now - self._last_poll >= POLL_S:
            self._last_poll = now
            st = _fresh(_status_doc(self.current))
            if st.get_str(DIST_SECTION, "session", "") == self.session:
                self.alt_ready = True
                self.alt_agent = st.get_int(DIST_SECTION, "agent_id", self.alt_agent)
                self.paid[self.current] = st.get_int(DIST_SECTION, "paid", 0)
                # Our own (decremented) estimate wins until the alt republishes after the last trade.
                if st.get_float(DIST_SECTION, "ts", 0.0) > self._round_done_wall:
                    self.alt_slots = st.get_int(DIST_SECTION, "free_slots", self.alt_slots)
        if now - self.alt_started > ALT_TOTAL_TIMEOUT_S:
            self._finish_alt(f"total time limit reached ({self._summary()})")
            return
        self._step(now)

    def _step(self, now: float) -> None:
        el = now - self.t

        if self.state == "wait_ready":
            if self.alt_ready and self.alt_agent:
                self._go("collect")
            elif el > ALT_NO_RESPONSE_S:
                self._finish_alt("no answer (widget not running on that account?)")
            return

        if self.state == "collect":
            if el < (ROUND_PAUSE_S if self.rounds or self.attempts else 0.0):
                return
            if not any(q > 0 for q in self.remaining.values()):
                self._finish_alt(f"done ({self._summary()})")
                return
            limit = min(MAX_STACKS_PER_TRADE, self.alt_slots)
            if limit <= 0:
                self._finish_alt(f"error: no free slot on that account ({self._summary()})")
                return
            self.stacks = _dist_stacks(self.remaining, limit, self.unofferable)
            if not self.stacks:
                self._finish_alt(f"error: nothing left in the bags ({self._summary()})")
                return
            self.results[self.current] = f"trade {self.rounds + 1}: {len(self.stacks)} stack(s)"
            self._go("approach")
            return

        if self.state == "approach":
            if not Agent.IsValid(self.alt_agent):
                self._finish_alt("error: character not found on the map")
                return
            ax, ay = Agent.GetXY(self.alt_agent)
            if Utils.Distance(Player.GetXY(), (ax, ay)) <= APPROACH_RANGE:
                self._go("open")
                return
            if el > APPROACH_TIMEOUT_S:
                self._finish_alt("error: cannot reach that character")
                return
            if now - self._last_move >= 1.0:
                Player.Move(ax, ay)
                self._last_move = now
            return

        if self.state == "open":
            if el < 0.2:
                return
            if not Agent.IsValid(self.alt_agent):  # never target a despawned agent
                self._finish_alt("error: character not found on the map")
                return
            Player.ChangeTarget(self.alt_agent)
            self._go("press_trade")
            return

        if self.state == "press_trade":
            if el < 0.6:
                return
            if _click_frame("Trade button", FrameId.TradeButton.Button):
                self.offer_index = 0
                self._go("offer")
                return
            if el > TRADE_BUTTON_TIMEOUT_S:
                self._retry("Trade button not found next to the target")
                return
            if now - self._last_move >= 1.0 and Agent.IsValid(self.alt_agent):
                Player.ChangeTarget(self.alt_agent)
                self._last_move = now
            return

        if self.state == "offer":
            if el < OPEN_WAIT_S + self.offer_index * OFFER_GAP_S:
                return
            if self.offer_index < len(self.stacks):
                item_id, qty, _model = self.stacks[self.offer_index]
                _trade("offer_item", item_id, qty)
                self.offer_index += 1
                return
            self._go("verify")
            return

        if self.state == "verify":
            if el < VERIFY_WAIT_S:
                return
            offered = [s for s in self.stacks if _is_offered(s[0])]
            refused = [s[0] for s in self.stacks if s not in offered]
            if refused:
                self.unofferable.update(refused)
                _log(f"{len(refused)} item(s) refused by the trade window, skipped.", _MSG.Warning)
            if not offered:
                self._retry("items refused by the trade window")
                return
            self.stacks = offered
            self.qty_before = {i: _qty(i) for i, _, _ in self.stacks}
            self._go("submitting")
            return

        if self.state == "submitting":
            if el < SUBMIT_DELAY_S:
                return
            if _click_frame("Submit Offer button", FrameId.SubmitOfferButton):
                self.offer_id += 1
                self._publish()  # tells the receiver to submit and accept
                self.results[self.current] = f"trade {self.rounds + 1}: offer submitted, waiting"
                self._last_accept = now
                self._go("accepting")
                return
            if el > SUBMIT_TIMEOUT_S:
                self._retry("Submit Offer button not found")
            return

        if self.state == "accepting":
            inv = set(_inventory_ids())
            gone = all(i not in inv or _qty(i) <= self.qty_before.get(i, q) - q for i, q, _ in self.stacks)
            if gone:
                for _i, q, m in self.stacks:
                    self.remaining[m] = max(0, self.remaining.get(m, 0) - q)
                    self.sent += q
                self.alt_slots = max(0, self.alt_slots - len(self.stacks))
                self._round_done_wall = time.time()
                self.rounds += 1
                self.attempts = 0
                self.results[self.current] = f"trade {self.rounds} completed"
                self._go("collect")
                return
            if el > ACCEPT_TIMEOUT_S:
                self._retry("the other account did not accept in time")
                return
            if now - self._last_accept >= ACCEPT_EVERY_S:
                _click_frame("Accept button", FrameId.AcceptButton)
                self._last_accept = now


class AltReceiver:
    """Other account side: when the main distributes to it, open the main's
    trade request, submit an empty offer, accept. It never offers anything."""

    def __init__(self) -> None:
        self.active: bool = False
        self.session: str = ""
        self.main_email: str = ""
        self.seen_session: str = ""
        self.closed_for: set[str] = set()
        self.close_after: bool = False
        self.handled_offer: int = 0
        self.offer_seen_at: float = 0.0
        self.submitted: bool = False
        self.received_offers: int = 0
        self.paid: int = 0              # gold paid to the main this session (confirmed)
        self.pay_pending: int = 0       # gold put in the current trade, not yet confirmed
        self.gold_before: int = 0
        self._last_accept: float = 0.0
        self._last_view: float = 0.0
        self._last_status: float = 0.0
        self._last_poll: float = 0.0

    def _status(self, state: str) -> None:
        _publish(_status_doc(_my_email()), {
            "session": self.session, "state": state, "agent_id": int(Player.GetAgentID() or 0),
            "free_slots": _free_slots(), "paid": self.paid, "ts": time.time(),
        }, DIST_SECTION)
        self._last_status = time.monotonic()

    def _stop(self, why: str) -> None:
        if self.active:
            if self.submitted:
                _trade("cancel_trade")
            _log(f"Receiving from the main: {why}.")
        self.active = False
        self.submitted = False

    def tick(self, distributing_here: bool) -> None:
        me = _my_email()
        now = time.monotonic()
        if not me or distributing_here or now - self._last_poll < POLL_S:
            return
        self._last_poll = now
        doc = _fresh(_dist_doc())
        session = doc.get_str(DIST_SECTION, "session", "")
        cancelled = doc.get_bool(DIST_SECTION, "cancel", True)
        stale = time.time() - doc.get_float(DIST_SECTION, "ts", 0.0) > STALE_REQUEST_S
        listed = me in doc.get_str(DIST_SECTION, "accounts", "").lower().split("|")
        served = me in doc.get_str(DIST_SECTION, "done", "").lower().split("|")

        if session and listed and not cancelled and not stale and not served:
            self.seen_session = session
            self.close_after = doc.get_bool(DIST_SECTION, "close_after", False)
        if self.seen_session and self.seen_session == session and session not in self.closed_for and (
                cancelled or stale or served):
            self._stop("finished")
            self.closed_for.add(session)
            self.seen_session = ""
            if self.close_after and not _alt.active:
                _close_self("distribution finished")
            return
        if not session or cancelled or stale or doc.get_str(DIST_SECTION, "target", "").lower() != me:
            if self.active:
                self._stop("no longer my turn")
            return

        if not self.active:
            main_email = doc.get_str(DIST_SECTION, "main_email", "").lower()
            main_acc, me_acc = _account(main_email), _account(me)
            if main_email == me or main_acc is None or me_acc is None or not _same_party_and_instance(main_acc, me_acc):
                return
            self.active = True
            self.session = session
            self.main_email = main_email
            self.handled_offer = doc.get_int(DIST_SECTION, "offer_id", 0)  # only offers made from now on count
            self.submitted = False
            self.received_offers = 0
            self.paid = 0
            self.pay_pending = 0
            _log("The main is sending items to this character.")
            self._status("ready")
        elif now - self._last_status >= HEARTBEAT_S:
            self._status("ready")  # keeps free slots fresh for the main

        if now - self._last_view >= 1.0:
            self._last_view = now
            _click_frame("View button (trade request)", FrameId.ViewButton)

        # A completed trade takes our gold: count the payment once it has left.
        if self.pay_pending and _gold() <= self.gold_before - self.pay_pending:
            self.paid += self.pay_pending
            self.pay_pending = 0
            self._status("ready")

        offer_id = doc.get_int(DIST_SECTION, "offer_id", 0)
        if offer_id > self.handled_offer:
            self.handled_offer = offer_id
            self.offer_seen_at = now
            self.submitted = False
            self.received_offers += 1
            self._last_accept = 0.0
            self._set_payment(doc)
        if self.received_offers == 0:
            return
        if not self.submitted:
            if now - self.offer_seen_at >= MAIN_SUBMIT_DELAY_S and _click_frame("Submit Offer button", FrameId.SubmitOfferButton):
                self.submitted = True
                self._last_accept = now
        elif now - self._last_accept >= ACCEPT_EVERY_S:
            _click_frame("Accept button", FrameId.AcceptButton)
            self._last_accept = now

    def _set_payment(self, doc: Settings) -> None:
        """Put our gold in the trade before Submit Offer: the main's pay_gold setting,
        bounded by our gold and by the main's room under the 100k cap."""
        self.pay_pending = 0  # an unconfirmed previous payment means that trade failed
        want = max(0, doc.get_int(DIST_SECTION, "pay_gold", 0))
        if want <= 0:
            return
        room = max(0, doc.get_int(DIST_SECTION, "gold_room", 0))
        pay = min(want, _gold(), room)
        if pay < want:
            _log(f"Payment reduced to {pay} gold (my gold {_gold()}, main room {room}).", _MSG.Warning)
        if pay > 0:
            self.gold_before = _gold()
            _trade("submit_offer", pay)  # sets the offered gold amount only
            self.pay_pending = pay


_main = MainCollector()
_alt = AltGiver()
_dist = MainDistributor()
_recv = AltReceiver()
_dist_cache: tuple[float, int, dict[int, int], dict[int, int]] = (0.0, 0, {}, {})
_dist_others: list[tuple[str, str]] = []  # (email, character name) of the party, for the checkboxes
_dist_filter: str = ""
_preview_responder = PreviewResponder()
_preview = PreviewViewer()
_last_tick: float = 0.0
_summary_cache: tuple[float, int, int] = (0.0, 0, 0)  # (refreshed_at, stacks, items)


# ==========================================================================
# Lifecycle: update() = logic, draw() = UI
# ==========================================================================
def _colored(text: str, rgba: tuple[int, int, int, int]) -> None:
    PyImGui.text_colored(text, Color(*rgba).to_tuple_normalized())


def _local_summary() -> tuple[int, int]:
    """Matching stacks / items on this character for the current selection (throttled)."""
    global _summary_cache
    now = time.monotonic()
    if now - _summary_cache[0] >= SUMMARY_REFRESH_S:
        stacks = _stacks_to_give(Selection.from_options(), 10_000)
        _summary_cache = (now, len(stacks), sum(q for _, q in stacks))
    return _summary_cache[1], _summary_cache[2]


def _option_checkbox(section: str, key: str, label: str, default: bool) -> None:
    opts = _options()
    cur = opts.get_bool(section, key, default)
    new = PyImGui.checkbox(f"{label}##ptc_{section}_{key}", cur)
    if new != cur:
        opts.set(section, key, new)


def _option_int(section: str, key: str, label: str, default: int, lo: int, hi: int) -> None:
    opts = _options()
    cur = opts.get_int(section, key, default)
    new = PyImGui.input_int(f"{label}##ptc_{section}_{key}", cur, 1, 10)
    if new != cur:
        opts.set(section, key, max(lo, min(hi, new)))


def _option_ids(key: str, label: str) -> None:
    opts = _options()
    cur = opts.get_str("Lists", key, "")
    new = PyImGui.input_text(f"{label}##ptc_Lists_{key}", cur)
    if new != cur:
        opts.set("Lists", key, new)
    count = len(_parse_ids(new))
    if count:
        PyImGui.same_line()
        PyImGui.text_disabled(f"({count})")


# --- look -------------------------------------------------------------------
C_OK = (140, 230, 140, 255)
C_BUSY = (255, 210, 120, 255)
C_BAD = (255, 123, 123, 255)
C_IDLE = (125, 125, 125, 255)
C_COUNT = (143, 180, 230, 255)
# (normal, hovered, active) button colours
BTN_GREEN = ((47, 125, 74), (58, 148, 90), (38, 104, 61))
BTN_BLUE = ((47, 95, 158), (60, 114, 184), (38, 79, 134))
BTN_RED = ((158, 52, 52), (184, 66, 66), (134, 42, 42))
BTN_GREY = ((52, 52, 52), (68, 68, 68), (42, 42, 42))
BIG_BUTTON_HEIGHT = 30.0
SIDE_BUTTON_WIDTH = 110.0
WINDOW_DEFAULT_SIZE = (700.0, 760.0)


def _rgba(rgba: tuple[int, int, int, int]) -> tuple[float, float, float, float]:
    return Color(*rgba).to_tuple_normalized()


def _dot(rgba: tuple[int, int, int, int]) -> None:
    """A small coloured bullet, then stays on the same line."""
    PyImGui.push_style_color(int(PyImGui.ImGuiCol.Text), _rgba(rgba))
    PyImGui.bullet()
    PyImGui.pop_style_color(1)
    PyImGui.same_line()


def _button(label: str, colors: tuple[tuple[int, int, int], ...], width: float) -> bool:
    """A coloured button BIG_BUTTON_HEIGHT high (width <= 0: the rest of the line)."""
    if width <= 0:
        width = max(120.0, float(PyImGui.get_content_region_avail()[0]) + width)
    for idx, rgb in zip(("Button", "ButtonHovered", "ButtonActive"), colors):
        PyImGui.push_style_color(int(getattr(PyImGui.ImGuiCol, idx)), _rgba((*rgb, 255)))
    clicked = PyImGui.button(label, width, BIG_BUTTON_HEIGHT)
    PyImGui.pop_style_color(3)
    return clicked


def _header(title: str, count: str, uid: str) -> bool:
    """Collapsing header with its count drawn at the right end of the bar."""
    x = float(PyImGui.get_cursor_pos_x())
    width = float(PyImGui.get_content_region_avail()[0])
    opened = PyImGui.collapsing_header(f"{title}###{uid}")
    if count:
        PyImGui.same_line()
        PyImGui.set_cursor_pos_x(x + width - float(PyImGui.calc_text_size(count)[0]) - 8.0)
        _colored(count, C_COUNT)
    return opened


def _all_none(section: str, keys: list[str], uid: str) -> None:
    opts = _options()
    if PyImGui.small_button(f"All##ptc_all_{uid}"):
        for k in keys:
            opts.set(section, k, True)
    PyImGui.same_line()
    if PyImGui.small_button(f"None##ptc_none_{uid}"):
        for k in keys:
            opts.set(section, k, False)


GRID_COLUMN_WIDTH = 220.0  # one column of checkboxes per 220 px of window width
GRID_MAX_COLUMNS = 4


def _grid(uid: str, cells: list[Callable[[], None]], max_columns: int = GRID_MAX_COLUMNS,
          column_width: float = GRID_COLUMN_WIDTH) -> None:
    """Draws the cells in columns, filled top to bottom then left to right."""
    if not cells:
        return
    avail = float(PyImGui.get_content_region_avail()[0])
    cols = max(1, min(max_columns, len(cells), int(avail // column_width)))
    if cols == 1 or not PyImGui.begin_table(f"##ptc_grid_{uid}", cols, 0):
        for cell in cells:
            cell()
        return
    rows = -(-len(cells) // cols)
    for r in range(rows):
        PyImGui.table_next_row()
        for c in range(cols):
            PyImGui.table_next_column()
            i = c * rows + r
            if i < len(cells):
                cells[i]()
    PyImGui.end_table()


def _check_cell(section: str, key: str, label: str, default: bool) -> Callable[[], None]:
    return lambda: _option_checkbox(section, key, label, default)


COLLECT_CELL_WIDTH = 330.0
SEND_BOX_WIDTH = 95.0


def _collect_cell(section: str, key: str, label: str, default: bool, item_key: int) -> Callable[[], None]:
    """[most each alt sends] [checkbox] Item name, like the Main -> Alts cells. 0 = everything."""
    def draw() -> None:
        opts = _options()
        cur = opts.get_int(SEND_ITEM_SECTION, str(item_key), 0)
        PyImGui.push_item_width(SEND_BOX_WIDTH)
        new = PyImGui.input_int(f"##ptc_send_{item_key}", cur, 1, 10)
        PyImGui.pop_item_width()
        if new != cur:
            opts.set(SEND_ITEM_SECTION, str(item_key), max(0, min(SEND_MAX, new)))
        PyImGui.same_line()
        _option_checkbox(section, key, label, default)
        if new <= 0:
            PyImGui.same_line()
            PyImGui.text_disabled("(all)")
    return draw


def _picked(items: list[tuple[int, str]]) -> int:
    opts = _options()
    return sum(1 for m, _ in items if opts.get_bool("Items", str(m), m in DEFAULT_ON_MODELS))


def _draw_item_checks(items: list[tuple[int, str]], uid: str) -> None:
    _all_none("Items", [str(m) for m, _ in items], uid)
    _grid(uid, [_collect_cell("Items", str(m), label, m in DEFAULT_ON_MODELS, m) for m, label in items],
          GRID_MAX_COLUMNS, COLLECT_CELL_WIDTH)


_collect_filter: str = ""


SEARCH_MIN_CHARS = 3  # shorter searches would match (and open) almost every section


def _search_text(raw: str) -> str:
    """What a search box really searches for: nothing until SEARCH_MIN_CHARS are typed."""
    text = raw.strip().lower()
    return text if len(text) >= SEARCH_MIN_CHARS else ""


def _search_hit(needle: str, text: str) -> bool:
    """True when a word of `text` starts with the search ("ob" finds Obsidian, not Glob)."""
    return re.search(r"(?:^|[^a-z0-9])" + re.escape(needle), text.lower()) is not None


def _search_hint(raw: str) -> None:
    if 0 < len(raw.strip()) < SEARCH_MIN_CHARS:
        PyImGui.text_disabled(f"Type at least {SEARCH_MIN_CHARS} letters to search.")


def _collect_needle() -> str:
    return _search_text(_collect_filter)


def _matching(title: str, entries: list[tuple[object, str]]) -> list[tuple[object, str]]:
    """Entries shown for the search: all of them when the search names the section."""
    needle = _collect_needle()
    if not needle or _search_hit(needle, title):
        return entries
    return [(k, label) for k, label in entries if _search_hit(needle, label)]


def _open_if_searching() -> None:
    if _collect_needle():
        PyImGui.set_next_item_open(True)  # a search opens the sections it found something in


def _draw_item_list(title: str, items: list[tuple[int, str]]) -> None:
    """Collapsible list with one checkbox per model, plus All / None (on the shown items)."""
    shown = [(int(m), label) for m, label in _matching(title, list(items))]  # type: ignore[arg-type]
    if not shown:
        return
    _open_if_searching()
    if _header(title, f"{_picked(items)}/{len(items)}", f"ptc_list_{title}"):
        _draw_item_checks(shown, title)


def _draw_dye_list() -> None:
    """Collapsible list with one checkbox per dye colour, plus All / None (on the shown colours)."""
    shown = [(int(c), label) for c, label in _matching(DYE_LIST_TITLE, list(DYE_ITEMS))]  # type: ignore[arg-type]
    if not shown:
        return
    opts = _options()
    picked = sum(1 for c, _ in DYE_ITEMS if opts.get_bool("Dyes", str(c), False))
    _open_if_searching()
    if not _header(DYE_LIST_TITLE, f"{picked}/{len(DYE_ITEMS)}", "ptc_list_dyes"):
        return
    _all_none("Dyes", [str(c) for c, _ in shown], "dyes")
    _grid("dyes", [_collect_cell("Dyes", str(c), label, False, DYE_KEY_BASE + c) for c, label in shown],
          GRID_MAX_COLUMNS, COLLECT_CELL_WIDTH)


def _draw_category_group(title: str, items: list[tuple[str, str]]) -> None:
    short = "Equipment" if title.startswith("Equipment") else title
    shown = [(str(k), label) for k, label in _matching(short, list(items))]  # type: ignore[arg-type]
    if not shown:
        return
    opts = _options()
    picked = sum(1 for key, _ in items if opts.get_bool("Categories", key, False))
    _open_if_searching()
    if not _header(short, f"{picked}/{len(items)}", f"ptc_{title}"):
        return
    _grid(f"cat_{title}", [_check_cell("Categories", key, label, False) for key, label in shown])
    if title.startswith("Equipment"):
        PyImGui.text_disabled("Filters:")
        _grid("filters", [_check_cell("Filters", k, lbl, d) for k, (lbl, d) in GEAR_FILTERS.items()], 2)


def _draw_selection() -> None:
    """"What to collect": a search, then every section, in the same order as the other tab."""
    global _collect_filter
    PyImGui.push_item_width(-1.0)
    _collect_filter = PyImGui.input_text_with_hint("##ptc_collect_filter", "Search...", _collect_filter)
    PyImGui.pop_item_width()
    _search_hint(_collect_filter)
    PyImGui.text_disabled("Left of each item: the most each alt sends of it once checked (0 = all).")
    for title, items in ITEM_LISTS:
        _draw_item_list(title, items)
    for title, items in CATEGORY_GROUPS:
        if title == "Tomes":
            _draw_item_list(KEY_LIST_TITLE, KEY_ITEMS)
        _draw_category_group(title, items)
        if title.startswith("Equipment"):
            _draw_dye_list()
        if title == "Tomes":  # same sections, same order as the Main -> Alts tab
            for ctitle, citems in CONSUMABLE_LISTS:
                _draw_item_list(f"Consumables - {ctitle}", citems)
    for ltitle, litems in COIN_LISTS + MISC_LISTS:
        _draw_item_list(ltitle, litems)
    opts = _options()
    lists = len(_parse_ids(opts.get_str("Lists", "custom", ""))) + len(_parse_ids(opts.get_str("Lists", "blacklist", "")))
    needle = _collect_needle()
    if needle and not _search_hit(needle, "custom list / blacklist"):
        return
    _open_if_searching()
    if _header("Custom list / blacklist", str(lists) if lists else "", "ptc_lists"):
        PyImGui.text_disabled("Model ids separated by commas. The blacklist wins over everything else.")
        _option_ids("custom", "Always give")
        _option_ids("blacklist", "Never give")


def _draw_collect_options() -> None:
    _option_checkbox("Storage", "use", "Also take from Xunlai storage (and material storage)", DEFAULT_FROM_STORAGE)
    _option_checkbox("Close", "after_trade", "Close the widget on the alts when they are done", DEFAULT_CLOSE_AFTER)
    opts = _options()
    if PyImGui.tree_node("Gold##ptc_gold"):
        pay = opts.get_int("Gold", "pay_per_trade", DEFAULT_PAY_PER_TRADE)
        new_pay = PyImGui.input_int("Paid by the main per trade##ptc_pay", pay, 100, 1000)
        if new_pay != pay:
            opts.set("Gold", "pay_per_trade", max(0, min(MAX_CHARACTER_GOLD, new_pay)))
        _option_checkbox("Gold", "give", "Alts also give their gold", False)
        keep = opts.get_int("Gold", "keep", 1000)
        new_keep = PyImGui.input_int("Gold kept on each alt##ptc_keep", keep, 100, 1000)
        if new_keep != keep:
            opts.set("Gold", "keep", max(0, min(MAX_CHARACTER_GOLD, new_keep)))
        PyImGui.tree_pop()


def _draw_preview() -> None:
    PyImGui.separator_text("Preview (nothing is traded)")
    for email in _preview.emails:
        name = _preview.names.get(email, UNNAMED)
        lines = _preview.answers.get(email)
        if lines is None:
            _dot(C_IDLE)
            PyImGui.text_disabled(f"{name}: waiting for an answer")
            continue
        if not lines:
            _dot(C_IDLE)
            PyImGui.text(f"{name}: nothing to give")
            continue
        _dot(C_OK)
        if PyImGui.tree_node(f"{name}: {len(lines)} line(s)##ptc_prev_{email}"):
            for line in lines:
                PyImGui.bullet_text(line)
            PyImGui.tree_pop()


def _dist_target_key(email: str) -> str:
    return _safe(email)


def _dist_is_target(email: str) -> bool:
    """Per-account checkbox above the list: True (default) = this account receives."""
    return _options().get_bool("DistTargets", _dist_target_key(email), True)


def _dist_targets(others: list[tuple[str, str]]) -> list[tuple[str, str]]:
    return [(e, name) for e, name in others if _dist_is_target(e)]


def _dist_context() -> tuple[int, dict[int, int], dict[int, int]]:
    """(number of CHECKED accounts in party + instance, bag stock, storage stock), refreshed every second."""
    global _dist_cache, _dist_others
    now = time.monotonic()
    if now - _dist_cache[0] >= DIST_CACHE_S:
        me_acc = _account(_my_email())
        _dist_others = _party_others(me_acc) if me_acc is not None else []
        n = len(_dist_targets(_dist_others))
        _dist_cache = (now, n, _bag_stock(), _storage_stock() if _dist_use_storage() else {})
    return _dist_cache[1], _dist_cache[2], _dist_cache[3]


def _collect_is_target(email: str) -> bool:
    """Per-account checkbox of the Alts -> Main tab: True (default) = collect from it."""
    return _options().get_bool("CollectTargets", _dist_target_key(email), True)


def _draw_collect_targets() -> None:
    """One checkbox per account of the party (same instance): who brings its items."""
    others = _dist_others
    if not others:
        PyImGui.text_disabled("No other account in the party / instance.")
        return
    _all_none("CollectTargets", [_dist_target_key(e) for e, _ in others], "collect_targets")
    _grid("collect_targets", [_check_cell("CollectTargets", _dist_target_key(e), name, True) for e, name in others])


def _draw_dist_targets() -> None:
    """One checkbox per account of the party (same instance): who receives."""
    others = _dist_others
    if not others:
        PyImGui.text_disabled("No other account in the party / instance.")
        return
    _all_none("DistTargets", [_dist_target_key(e) for e, _ in others], "dist_targets")
    _grid("dist_targets", [_check_cell("DistTargets", _dist_target_key(e), name, True) for e, name in others])


def _dist_have(model: int, bags: dict[int, int], stored: dict[int, int]) -> int:
    return bags.get(model, 0) + (stored.get(model, 0) if _dist_use_storage() else 0)


DIST_KEEP_SECTION = "DistKeep"


def _dist_keep(model: int) -> int:
    """Units of this item the main keeps for itself when it sends (0 = none)."""
    return max(0, min(SEND_MAX, _options().get_int(DIST_KEEP_SECTION, str(model), 0)))


def _dist_need(model: int, qty: int, n: int) -> int:
    """What the main must hold to send `qty` to each of `n` accounts and keep its reserve."""
    return qty * n + _dist_keep(model)


DIST_CELL_WIDTH = 330.0   # one item per 330 px of window width
DIST_QTY_WIDTH = 105.0


def _draw_dist_cell(model: int, n: int, bags: dict[int, int], stored: dict[int, int]) -> None:
    """[quantity per account] Item name  (have) or OK / short."""
    cur = _dist_per_account(model)
    PyImGui.push_item_width(DIST_QTY_WIDTH)
    new = PyImGui.input_int(f"##ptc_dist_m{model}", cur, 1, 10)
    PyImGui.pop_item_width()
    if new != cur:
        _options().set(DIST_SECTION, _dist_qty_key(model), max(0, min(DIST_MAX_PER_ACCOUNT, new)))
    qty = max(0, min(DIST_MAX_PER_ACCOUNT, new))
    PyImGui.same_line()
    label = _model_label(model)
    color = _dist_colors.get(model)
    if color is not None:
        PyImGui.text_colored(label, color.to_tuple_normalized())
    else:
        PyImGui.text(label)
    PyImGui.same_line()
    have = _dist_have(model, bags, stored)
    need = _dist_need(model, qty, n)
    if qty <= 0:
        PyImGui.text_disabled(f"({have})")
    elif n and have >= need:
        _colored(f"OK {need}/{have}", C_OK)
    else:
        _colored(f"{have}/{need}", C_BAD)


def _draw_dist_table(section: str, models: list[int], n: int,
                     bags: dict[int, int], stored: dict[int, int]) -> None:
    """The section's items in columns: quantity per account, name, then what the main has
    (grey) or, once a quantity is set, OK / short for every checked account."""
    _grid(f"dist_{section}",
          [(lambda m=m: _draw_dist_cell(m, n, bags, stored)) for m in models],
          GRID_MAX_COLUMNS, DIST_CELL_WIDTH)


def _draw_dist_items(n: int, bags: dict[int, int], stored: dict[int, int]) -> None:
    """"What to send": the main's items in sections, with a search."""
    global _dist_filter
    PyImGui.push_item_width(-1.0)
    _dist_filter = PyImGui.input_text_with_hint("##ptc_dist_filter", "Search...", _dist_filter)
    PyImGui.pop_item_width()
    PyImGui.text_disabled("(n) = held by this character" + (" (bags + storage)" if _dist_use_storage() else "")
                          + ". Green: enough for every account. Red: not enough, not sent.")
    needle = _search_text(_dist_filter)
    _search_hint(_dist_filter)
    # Every listed item in its section (in list order), then whatever else the main holds.
    by_section: dict[str, list[int]] = {}
    listed: set[int] = set()
    for section, models in DIST_LISTED:
        for model in models:
            if model not in listed:
                listed.add(model)
                by_section.setdefault(section, []).append(model)
    held = sorted((set(DIST_PINNED_MODELS) | set(bags) | set(stored)) - listed, key=lambda m: _model_label(m).lower())
    for model in held:
        by_section.setdefault(_dist_section_of(model), []).append(model)
    for section in DIST_SECTION_ORDER:
        if section in DIST_HIDDEN:
            continue
        models = [m for m in by_section.get(section, [])
                  if not needle or _search_hit(needle, _model_label(m)) or _search_hit(needle, section)]
        if needle and not models:
            continue
        if needle:
            PyImGui.set_next_item_open(True)  # a search opens the sections it found something in
        title = "Other items" if section == DIST_OTHER else section
        chosen = sum(1 for m in models if _dist_per_account(m) > 0)
        if _header(title, f"{chosen}/{len(models)}", f"ptc_dist_sec_{section}"):
            if models:
                _draw_dist_table(section, models, n, bags, stored)
            else:
                PyImGui.text_disabled("Nothing of this kind on this character.")


def _draw_dist_options() -> None:
    _option_checkbox(DIST_SECTION, "use_storage", "Also take from this character's storage (and material storage)",
                     False)
    pay = _dist_pay_gold()
    PyImGui.push_item_width(160.0)
    new_pay = PyImGui.input_int("Gold each alt pays per trade##ptc_dist_pay", pay, 100, 1000)
    PyImGui.pop_item_width()
    if new_pay != pay:
        _options().set(DIST_SECTION, "pay_per_trade", max(0, min(MAX_CHARACTER_GOLD, new_pay)))
    _option_checkbox("Close", "after_trade", "Close the widget on the alts when they are done", DEFAULT_CLOSE_AFTER)
    _draw_dist_keep()


_keep_filter: str = ""


def _draw_dist_keep() -> None:
    """Every item this character holds (bags, plus storage when it is used), with how many
    it keeps for itself when it sends (0 = none). Equipment is never sent, so not listed."""
    global _keep_filter
    _n, bags, stored = _dist_context()
    held = {m for m in set(bags) | set(stored) if _dist_section_of(m) not in DIST_HIDDEN}
    held |= {m for m in _dist_plan_from_options() if _dist_section_of(m) not in DIST_HIDDEN}
    kept = sum(1 for m in held if _dist_keep(m) > 0)
    if not PyImGui.tree_node(f"Keep on this character ({kept})###ptc_dist_keep"):
        return
    PyImGui.text_disabled("Units this character keeps for itself, on top of what it sends (0 = none).")
    PyImGui.push_item_width(-1.0)
    _keep_filter = PyImGui.input_text_with_hint("##ptc_keep_filter", "Search...", _keep_filter)
    PyImGui.pop_item_width()
    _search_hint(_keep_filter)
    needle = _search_text(_keep_filter)
    models = sorted((m for m in held if not needle or _search_hit(needle, _model_label(m))),
                    key=lambda m: _model_label(m).lower())
    if not models:
        PyImGui.text_disabled("Nothing on this character." if not needle else "Nothing found.")
    else:
        opts = _options()

        def cell(model: int) -> Callable[[], None]:
            def draw() -> None:
                cur = _dist_keep(model)
                PyImGui.push_item_width(DIST_QTY_WIDTH)
                new = PyImGui.input_int(f"##ptc_dist_keep_{model}", cur, 1, 10)
                PyImGui.pop_item_width()
                if new != cur:
                    opts.set(DIST_KEEP_SECTION, str(model), max(0, min(SEND_MAX, new)))
                PyImGui.same_line()
                label = _model_label(model)
                color = _dist_colors.get(model)
                if color is not None:
                    PyImGui.text_colored(label, color.to_tuple_normalized())
                else:
                    PyImGui.text(label)
                PyImGui.same_line()
                PyImGui.text_disabled(f"({_dist_have(model, bags, stored)})")
            return draw

        _grid("dist_keep", [cell(m) for m in models], GRID_MAX_COLUMNS, DIST_CELL_WIDTH)
    PyImGui.tree_pop()


def _close_self(reason: str) -> None:
    """Switch this widget off on a giver so its window does not stay on screen.
    The main re-enables it (EnableWidget) at the next collection."""
    _log(f"Closing {WIDGET_NAME} on this account: {reason}.")
    try:
        get_widget_handler().disable_widget(WIDGET_NAME)
    except Exception as exc:
        _log(f"Could not close the widget: {exc}", _MSG.Warning)


def _shutdown(reason: str) -> None:
    """Leave no trade half-done: stop the collection (main) or the giving (alt)."""
    if _main.running:
        _main.stop(reason)
    if _alt.active:
        _alt.close_after = False  # already being switched off: do not ask twice
        _alt._end("error", reason)  # pyright: ignore[reportPrivateUsage]
    if _dist.running:
        _dist.stop(reason)
    if _recv.active:
        _recv._stop(reason)  # pyright: ignore[reportPrivateUsage]
    if _preview.open:
        _preview.close()


def on_disable() -> None:
    """Called by the widget manager when the widget is switched off (catalog or X)."""
    _shutdown("widget closed")


TAB_COLLECT = "Alts -> Main"
TAB_DISTRIBUTE = "Main -> Alts"


def _result_color(res: str) -> tuple[int, int, int, int]:
    low = res.lower()
    if low.startswith(("done", "nothing")):
        return C_OK
    if low.startswith(("error", "no answer", "interrupted", "total time")):
        return C_BAD
    if low.startswith("waiting"):
        return C_IDLE
    return C_BUSY


def _draw_progress(uid: str, results: dict[str, str], names: dict[str, str],
                   current: str, queue: list[str]) -> None:
    """Progress bar + one coloured line per account."""
    if not results:
        return
    PyImGui.separator_text("Progress")
    total = len(results)
    waiting = set(queue)
    finished = sum(1 for e, r in results.items()
                   if e != current and e not in waiting and not r.lower().startswith("waiting"))
    PyImGui.progress_bar(finished / total if total else 0.0, -1.0, 0.0, f"{finished} / {total} accounts")
    table_flags = int(PyImGui.TableFlags.RowBg)
    fixed, stretch = int(PyImGui.TableColumnFlags.WidthFixed), int(PyImGui.TableColumnFlags.WidthStretch)
    if not PyImGui.begin_table(f"##ptc_progress_{uid}", 2, table_flags):
        return
    PyImGui.table_setup_column("Account", fixed, 180.0)
    PyImGui.table_setup_column("Status", stretch, 0.0)
    for email, res in results.items():
        PyImGui.table_next_row()
        PyImGui.table_next_column()
        _dot(_result_color(res))
        PyImGui.text(names.get(email, UNNAMED))
        PyImGui.table_next_column()
        PyImGui.text(res[:1].upper() + res[1:])
    PyImGui.end_table()


def _selected_count(sel: Selection) -> int:
    return len(sel.models) + len(sel.cats) + len(sel.dyes) + len(sel.custom) + (1 if sel.give_gold else 0)


def _draw_collect_tab(busy: bool) -> None:
    """The other accounts bring the checked items to this character."""
    if not busy:
        PyImGui.separator_text("Collect from")
        _draw_collect_targets()
        PyImGui.separator_text("What to collect")
        _draw_selection()
        PyImGui.separator_text("Options")
        _draw_collect_options()
    PyImGui.separator_text("Collect")
    if _main.running:
        if _button("Stop##ptc_stop", BTN_RED, 0):
            _main.stop()
    elif _alt.active:
        _colored("Giving items to the main...", C_BUSY)
        PyImGui.text_disabled(f"{_alt.state} - {_alt.msg}")
    elif busy:
        PyImGui.text_disabled("Busy with the other tab.")
    else:
        count = _selected_count(Selection.from_options())
        spacing = 8.0
        if _button(f"Collect on this character  -  {count} selected##ptc_start", BTN_GREEN,
                   -(SIDE_BUTTON_WIDTH + spacing)):
            _preview.close()
            _main.start()
        PyImGui.same_line(0.0, spacing)
        if _preview.open:
            if _button("Close preview##ptc_prev_close", BTN_GREY, SIDE_BUTTON_WIDTH):
                _preview.close()
        elif _button("Preview##ptc_preview", BTN_GREY, SIDE_BUTTON_WIDTH):
            _preview.start()
        pay_now = _options().get_int("Gold", "pay_per_trade", DEFAULT_PAY_PER_TRADE)
        stacks, items = _local_summary()
        PyImGui.text_disabled(
            f"The main pays {pay_now} gold per trade."
            if pay_now > 0 else "The main pays nothing."
        )
        PyImGui.text_disabled(f"On this character: {stacks} matching stack(s), {items} item(s).")
        PyImGui.text_disabled("Never given: customized, untradable or equipped items.")
        if _preview.open:
            _draw_preview()
    _draw_progress("collect", _main.results, _main.names, _main.current, _main.queue)


def _draw_distribute_tab(busy: bool) -> None:
    """This character gives the same quantity to every checked account."""
    n, bags, stored = _dist_context()
    if not busy:
        PyImGui.separator_text("Send to")
        _draw_dist_targets()
        PyImGui.separator_text("What to send (per account)")
        _draw_dist_items(n, bags, stored)
        PyImGui.separator_text("Options")
        _draw_dist_options()
    PyImGui.separator_text("Send")
    if _dist.running:
        if _button("Stop sending##ptc_dist_stop", BTN_RED, 0):
            _dist.stop()
    elif _recv.active:
        _colored("Receiving items from the main...", C_BUSY)
    elif busy:
        PyImGui.text_disabled("Busy with the other tab.")
    else:
        plan = _dist_plan_from_options()
        for model, qty in sorted(plan.items(), key=lambda kv: _model_label(kv[0]).lower()):
            need, have = _dist_need(model, qty, n), _dist_have(model, bags, stored)
            if have < need:
                keep = _dist_keep(model)
                _colored(f"x {_model_label(model)}: {have} / {need}" + (f" (incl. {keep} kept)" if keep else "")
                         + " - will not be sent", C_BAD)
        spacing = 8.0
        if _button(f"Send to {n} account(s)  -  {len(plan)} item(s)##ptc_dist_start", BTN_BLUE,
                   -(SIDE_BUTTON_WIDTH + spacing)):
            _preview.close()
            _dist.start()
        PyImGui.same_line(0.0, spacing)
        if _button("Reset##ptc_dist_reset", BTN_GREY, SIDE_BUTTON_WIDTH):
            opts = _options()
            for model in plan:
                opts.set(DIST_SECTION, _dist_qty_key(model), 0)
        pay = _dist_pay_gold()
        PyImGui.text_disabled(f"Each alt pays {pay} gold per trade." if pay > 0 else "The alts pay nothing.")
        if _dist_use_storage():
            PyImGui.text_disabled("Missing units are taken from the storage before the first trade.")
        PyImGui.text_disabled("Equipment is never sent.")
    _draw_progress("dist", _dist.results, _dist.names, _dist.current, _dist.queue)


def _draw_status_line() -> None:
    """Coloured dot + what this account is doing, above the tabs."""
    _dist_context()  # refreshes the party list (cached)
    if PyTrade is None:
        color, text = C_BAD, "Trading unavailable: native PyTrade module not found"
    elif _main.running:
        done = sum(1 for e in _main.results if e != _main.current and e not in _main.queue)
        color, text = C_BUSY, f"Collecting  |  {done} / {len(_main.results)} accounts"
    elif _dist.running:
        color, text = C_BUSY, f"Sending  |  {len(_dist.done_accounts)} / {len(_dist.accounts)} accounts"
    elif _alt.active:
        color, text = C_BUSY, "Giving items to the main"
    elif _recv.active:
        color, text = C_BUSY, "Receiving items from the main"
    else:
        others = len(_dist_others)
        color = C_OK if others else C_IDLE
        text = f"Ready  |  {others} other account(s) in the party" if others else "Ready  |  no other account in the party"
    _dot(color)
    PyImGui.text(text)


TAB_FONT = ("Regular", 16)  # tab titles: plain font, a little bigger than the text


def _with_tab_font(fn: Callable[[], bool]) -> bool:
    """Runs fn with TAB_FONT pushed (falls back to the normal font)."""
    pushed = False
    try:
        ImGui.push_font(*TAB_FONT)
        pushed = True
    except Exception:
        pass
    result = fn()
    if pushed:
        ImGui.pop_font()
    return result


def _tab_item(label: str) -> bool:
    """begin_tab_item with the tab title in TAB_FONT (the tab content keeps the normal font)."""
    return _with_tab_font(lambda: PyImGui.begin_tab_item(label))


MAP_SETTLE_S = 3.0  # wait this long after the map is loaded before reading the game
_map_ready_since: float = 0.0


def _map_ready() -> bool:
    """True once the map has been loaded for MAP_SETTLE_S. While the game is loading
    (character select, loading screen, map change) nothing in the game may be read:
    inventory, storage, party and item names are not there yet."""
    global _map_ready_since
    try:
        valid = bool(Routines.Checks.Map.MapValid())
    except Exception:
        valid = False
    now = time.monotonic()
    if not valid:
        _map_ready_since = 0.0
        return False
    if _map_ready_since <= 0.0:
        _map_ready_since = now
    return now - _map_ready_since >= MAP_SETTLE_S


def draw() -> None:
    # Resizable by the player (drag the bottom-right corner); ImGui remembers the size.
    # This only sets the size of the very first opening.
    PyImGui.set_next_window_size(WINDOW_DEFAULT_SIZE, int(PyImGui.ImGuiCond.FirstUseEver))
    expanded, keep_open = ImGui.BeginWithClose(
        MODULE_NAME, MODULE_NAME, p_open=True, flags=PyImGui.WindowFlags.HorizontalScrollbar
    )
    if expanded and not _map_ready():
        PyImGui.text_disabled("Waiting for the game to finish loading...")
    elif expanded:
        busy = _main.running or _alt.active or _dist.running or _recv.active
        _draw_status_line()
        PyImGui.spacing()
        # The bar takes its height from the font active here: same font as the titles,
        # so the bigger titles stay centred inside their tabs.
        if _with_tab_font(lambda: PyImGui.begin_tab_bar("##ptc_tabs")):
            if _tab_item(TAB_DISTRIBUTE):
                _draw_distribute_tab(busy)
                PyImGui.end_tab_item()
            if _tab_item(TAB_COLLECT):
                _draw_collect_tab(busy)
                PyImGui.end_tab_item()
            PyImGui.end_tab_bar()
    ImGui.End(MODULE_NAME)
    if not keep_open:
        # The window's X switches the widget off, like the catalog toggle
        # (on_disable then stops any running trade).
        get_widget_handler().disable_widget(WIDGET_NAME)


def tooltip() -> None:
    PyImGui.begin_tooltip()
    PyImGui.text(MODULE_NAME)
    PyImGui.separator()
    PyImGui.text("Alts -> Main: your alts bring the checked items to the main:")
    PyImGui.text("materials, equipment, dyes, keys, tomes, consumables,")
    PyImGui.text("tokens, passages, strongboxes, custom list, gold.")
    PyImGui.text("Can also take these items out of the characters' Xunlai storage.")
    PyImGui.text("Main -> Alts: the main gives the same quantity to every alt.")
    PyImGui.end_tooltip()


def update() -> None:
    global _last_tick
    if not _map_ready():
        return
    now = time.monotonic()
    if now - _last_tick < TICK_S:
        return
    _last_tick = now
    try:
        _main.tick()
        _alt.tick(main_running_here=_main.running or _dist.running)
        _dist.tick()
        _recv.tick(distributing_here=_dist.running or _main.running or _alt.active)
        _preview.tick()
        _preview_responder.tick(busy=_main.running or _alt.active or _preview.open or _dist.running or _recv.active)
    except Exception as exc:
        _log(f"Error: {exc}", _MSG.Error)
