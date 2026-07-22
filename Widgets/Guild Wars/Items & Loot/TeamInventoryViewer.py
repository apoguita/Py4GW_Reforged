import json
import os
import re
import traceback
from collections import OrderedDict
from pathlib import Path

import PyImGui
import PyJson
import PySystem

from Py4GWCoreLib import GLOBAL_CACHE
from Py4GWCoreLib import Color
from Py4GWCoreLib import ConsoleLog
from Py4GWCoreLib import DyeColor
from Py4GWCoreLib import ImGui
from Py4GWCoreLib import JsonFactory
from Py4GWCoreLib import Map
from Py4GWCoreLib import Player
from Py4GWCoreLib import Routines
from Py4GWCoreLib import ThrottledTimer
from Py4GWCoreLib import get_texture_for_model
from Py4GWCoreLib.enums import Bags
from Py4GWCoreLib.enums import ModelID
from Py4GWCoreLib.enums_src.Item_enums import ItemType
from Py4GWCoreLib.enums_src.Item_enums import Rarity
from Py4GWCoreLib.Item import Item

from Sources.marks_sources.mods_parser import MatchedRuneInfo
from Sources.marks_sources.mods_parser import MatchedWeaponModInfo
from Sources.marks_sources.mods_parser import ModDatabase
from Sources.marks_sources.mods_parser import parse_modifiers


project_root = PySystem.Console.get_projects_path()

MOD_DB = ModDatabase.load(os.path.join(project_root, "Sources/marks_sources/mods_data"))

MODULE_NAME = "TeamInventoryViewer"

inventory_write_timer = ThrottledTimer(3000)
inventory_read_timer = ThrottledTimer(5000)

on_first_load = True
all_accounts_search_query = ''
search_query = ''
current_character_name = ''

# Read-side cache the widget iterates when drawing every frame. Populated for the
# current account from the JsonFactory doc, and for other accounts from a disk scan.
TEAM_INVENTORY_CACHE = {}

INVENTORY_BAGS = {
    "Backpack": Bags.Backpack.value,
    "BeltPouch": Bags.BeltPouch.value,
    "Bag1": Bags.Bag1.value,
    "Bag2": Bags.Bag2.value,
    "EquipmentPack": Bags.EquipmentPack.value,
    "EquippedItems": Bags.EquippedItems.value,
}

STORAGE_BAGS = {
    "Storage1": Bags.Storage1.value,
    "Storage2": Bags.Storage2.value,
    "Storage3": Bags.Storage3.value,
    "Storage4": Bags.Storage4.value,
    "Storage5": Bags.Storage5.value,
    "Storage6": Bags.Storage6.value,
    "Storage7": Bags.Storage7.value,
    "Storage8": Bags.Storage8.value,
    "Storage9": Bags.Storage9.value,
    "Storage10": Bags.Storage10.value,
    "Storage11": Bags.Storage11.value,
    "Storage12": Bags.Storage12.value,
    "Storage13": Bags.Storage13.value,
    "Storage14": Bags.Storage14.value,
    "MaterialStorage": Bags.MaterialStorage.value,
}

ATTRIBUTES = {
    "Axe Mastery",
    "Hammer Mastery",
    "Swordsmanship",
    "Tactics",
    "Strength",
    "Marksmanship",
    "Beast Mastery",
    "Wilderness Survival",
    "Expertise",
    "Divine Favor",
    "Healing Prayers",
    "Protection Prayers",
    "Smiting Prayers",
    "Blood Magic",
    "Curses",
    "Death Magic",
    "Soul Reaping",
    "Domination Magic",
    "Fast Casting",
    "Illusion Magic",
    "Inspiration Magic",
    "Energy Storage",
    "Air Magic",
    "Earth Magic",
    "Fire Magic",
    "Water Magic",
    "Critical Strikes",
    "Dagger Mastery",
    "Deadly Arts",
    "Shadow Arts",
    "Channeling Magic",
    "Communing",
    "Restoration Magic",
    "Spawning Power",
    "Command",
    "Leadership",
    "Motivation",
    "Spear Mastery",
    "Earth Prayers",
    "Mysticism",
    "Scythe Mastery",
    "Wind Prayers",
}

# 1. Armor runes â†’ "of Vitae", "of Major Vigor", "of Superior Soul Reaping", â€¦
NON_ATTRIBUTE_RUNES = {"Vitae", "Vigor", "Attunement", "Clarity", "Purity", "Recovery", "Restoration", "Absorption"}
ARMOR_RUNE_SUFFIXES = {
    f"of {mod}{rune}" for rune in ATTRIBUTES | NON_ATTRIBUTE_RUNES for mod in ["", "Minor ", "Major ", "Superior "]
}

# 2. Weapon grips / handles / inscriptions â†’ "Grip of Axe Mastery", "Handle of Soul Reaping", â€¦
WEAPON_ATTRIBUTE_SUFFIXES = {f"of {attr}" for attr in ATTRIBUTES}

OTHER_WEAPON_SUFFIXES = {
    "of Defense",
    "of Shelter",
    "of Warding",
    "of Enchanting",
    "of Swiftness",
    "of Aptitude",
    "of Fortitude",
    "of Devotion",
    "of Endurance",
    "of Valor",
    "of Mastery",
    "of Quickening",
    "of Memory",
    # Profession
    "of the Warrior",
    "of the Ranger",
    "of the Necromancer",
    "of the Elementalist",
    "of the Mesmer",
    "of the Monk",
    "of the Ritualist",
    "of the Assassin",
    "of the Paragon",
    "of the Dervish",
    # Slaying
    "of Charrslaying",
    "of Demonslaying",
    "of Dragonslaying",
    "of Dwarfslaying",
    "of Giantslaying",
    "of Ogreslaying",
    "of Pruning",
    "of Tenguslaying",
    "of Trollslaying",
    "of Undeadbane",
    "of Skeletonslaying",
    "of Deathbane",
}

ALL_SUFFIXES = ARMOR_RUNE_SUFFIXES | WEAPON_ATTRIBUTE_SUFFIXES | OTHER_WEAPON_SUFFIXES

WEAPON_PREFIXES = {
    "Barbed",
    "Crippling",
    "Cruel",
    "Heavy",
    "Poisonous",
    "Silencing",
    "Ebon",
    "Fiery",
    "Icy",
    "Shocking",
    "Furious",
    "Sundering",
    "Vampiric",
    "Zealous",
    "Adept",
    "Defensive",
    "Hale",
    "Insightful",
    "Swift",
}

INSIGNIAS = {
    "Survivor",
    "Radiant",
    "Stalwart",
    "Brawler's",
    "Blessed",
    "Herald's",
    "Sentry's",
    "Knight's",
    "Stonefist",
    "Dreadnought",
    "Sentinel's",
    "Lieutenant's",
    "Frostbound",
    "Pyrebound",
    "Stormbound",
    "Scout's",
    "Earthbound",
    "Beastmaster's",
    "Wanderer's",
    "Disciple's",
    "Anchorite's",
    "Bloodstained",
    "Tormentor's",
    "Bonelace",
    "Minion Master's",
    "Blighter's",
    "Undertaker's",
    "Virtuoso's",
    "Artificer's",
    "Prodigy's",
    "Hydromancer",
    "Geomancer",
    "Pyromancer",
    "Aeromancer",
    "Prismatic",
    "Vanguard's",
    "Infiltrator's",
    "Saboteur's",
    "Nightstalker's",
    "Shaman's",
    "Ghostforge",
    "Mystic's",
    "Centurion's",
    "Windwalker",
    "Forsaken",
}


def clean_gw_item_name(item_name: str):
    """
    PERFECT Guild Wars 1 item name cleaner for weapons AND armor.
    - Removes at most one prefix/insignia + one suffix/rune.
    - Supports partial matches like: 'Survivor' -> "Survivor's"
    - Returns: (base_name, removed_prefix, removed_suffix)
    """
    if not item_name:
        return "", None, None

    words = item_name.strip().split()
    if not words:
        return "", None, None

    result = []
    removed_prefix = None
    removed_suffix = None

    i = 0
    n = len(words)

    # Normalize prefix/insignia list for flexible matching
    all_prefixes = WEAPON_PREFIXES | INSIGNIAS
    normalized_prefixes = {p.lower().rstrip("'s") for p in all_prefixes}

    if i < n:
        original = words[i].rstrip(".,!?")
        normalized = original.lower().rstrip("'s")

        if normalized in normalized_prefixes:
            removed_prefix = original  # store EXACT original prefix
            i += 1

    while i < n:
        remaining = words[i:]
        suffix_matched = False

        # Try longest suffix first (up to 5 words)
        for length in range(min(5, len(remaining)), 0, -1):
            candidate = " ".join(remaining[:length]).rstrip(".,!?")
            if candidate in ALL_SUFFIXES:
                removed_suffix = candidate  # store EXACT matched suffix phrase
                suffix_matched = True
                break

        if suffix_matched:
            break

        result.append(words[i])
        i += 1

    # Final cleanup of base name
    base_name = " ".join(result).strip()
    base_name = ''.join(c for c in base_name if not c.isdigit())

    return base_name, removed_prefix, removed_suffix


# endregion


# region JSONStore

def _json_root_dir():
    """Root of the per-account JSON tree, i.e. the parent of PyJson.get_json_directory().

    Returns None until the account anchor has resolved (get_json_directory is empty
    up to that point). Everything that needs to enumerate accounts must gate on this.
    """
    try:
        d = PyJson.get_json_directory()
    except Exception:
        return None
    if not d:
        return None
    return Path(d).parent


class ModelIDJSONStore:
    """Shared {model_id: model_name} map, backed by a global-scope JsonFactory doc.

    Global scope is safe under multibox: saves merge every client's discoveries
    through a cross-process lock, so different accounts scanning different items all
    contribute to the same on-disk map without clobbering each other.
    """

    FILE = "TeamInventoryViewer/model_ids.json"

    def __init__(self):
        self.file = JsonFactory(self.FILE, "global")

    def save_model_id(self, model_id, model_name):
        if not model_id or not model_name:
            return
        self.file.set(str(model_id), str(model_name))

    def get(self, model_id, default=""):
        return self.file.get_str(str(model_id), default)


class ModelFileIDJSONStore:
    """Shared {model_id: file_id} lookup so any character can render icons straight
    from GW.dat, even for items they've never held themselves.

    Global scope; same multibox-safe merge semantics as ModelIDJSONStore.
    """

    FILE = "TeamInventoryViewer/model_file_ids.json"

    def __init__(self):
        self.file = JsonFactory(self.FILE, "global")

    def save_model_file_id(self, model_id, file_id):
        if not model_id or not file_id or file_id <= 0:
            return
        self.file.set(str(model_id), int(file_id))

    def get(self, model_id, default=0):
        return self.file.get_int(str(model_id), default)


class ModHashJSONStore:
    """Shared {mod_hash: [prefix, suffix]} map, backed by a global-scope JsonFactory doc."""

    FILE = "TeamInventoryViewer/mod_hash.json"

    def __init__(self):
        self.file = JsonFactory(self.FILE, "global")

    @staticmethod
    def hash_mods(modifiers):
        """Stable 64-bit hash of a list of modifier objects (identifier + args + modbits)."""

        def safe_int(v):
            try:
                return int(v)
            except Exception:
                return 0

        data = []
        for mod in modifiers:
            data.append(
                [
                    safe_int(mod.GetIdentifier()),
                    safe_int(mod.GetArg1()),
                    safe_int(mod.GetArg2()),
                    safe_int(mod.GetArg()),
                    safe_int(mod.GetModBits()),
                ]
            )

        h = 0
        for lst in data:
            for num in lst:
                h = (h * 1315423911) ^ num ^ (h >> 5)
                h &= 0xFFFFFFFFFFFFFFFF

        return hex(h)[2:]

    def save_mod_hash(self, mod_hash, prefix=None, suffix=None):
        if not mod_hash or not (prefix or suffix):
            return
        self.file.set_json(str(mod_hash), [prefix, suffix])

    def get(self, mod_hash, default=None):
        return self.file.get_json(str(mod_hash), default)


class AccountJSONStore:
    """Per-account inventory (Characters + Storage), backed by an account-scope
    JsonFactory doc for the *current* account only.

    Constructing this class with any other email yields a read-only view: load()
    scans that account's inventory.json off disk and populates TEAM_INVENTORY_CACHE.
    All write/clear methods no-op on non-current accounts (JsonFactory has no
    "write to another account's doc from arbitrary state" primitive we can lean on
    here — the class must own the source of truth).
    """

    FILE = "TeamInventoryViewer/inventory.json"

    def __init__(self, email):
        self.email = email
        current = Player.GetAccountEmail()
        self._is_current = bool(current) and email == current
        self.file = JsonFactory(self.FILE, "account") if self._is_current else None

    # ----- Reads -----

    def load(self):
        if self._is_current and self.file:
            data = self.file.get_json("", None)
        else:
            data = self._read_disk_snapshot()
        if not data:
            data = {"Characters": OrderedDict(), "Storage": OrderedDict()}
        TEAM_INVENTORY_CACHE[self.email] = data
        return data

    def _read_disk_snapshot(self):
        root = _json_root_dir()
        if root is None:
            return None
        p = root / self.email / self.FILE
        if not p.exists():
            return None
        try:
            with open(p, "r") as f:
                return json.load(f, object_pairs_hook=OrderedDict)
        except Exception:
            return None

    # ----- Writes (current account only) -----

    def save_bag(self, char_name=None, storage_name=None, bag_name=None, bag_items=None):
        if not self._is_current or not self.file:
            return
        if bag_items is None:
            bag_items = {}
        if char_name and bag_name:
            path = f"Characters/{char_name}/Inventory/{bag_name}"
        elif storage_name:
            path = f"Storage/{storage_name}"
        else:
            return
        # set_json dedups against the current subtree, so an unchanged assignment is free.
        self.file.set_json(path, dict(bag_items))
        TEAM_INVENTORY_CACHE[self.email] = self.file.get_json("", None) or {
            "Characters": OrderedDict(),
            "Storage": OrderedDict(),
        }

    def clear_character(self, char_name):
        if not self._is_current or not self.file:
            return
        if self.file.delete(f"Characters/{char_name}"):
            ConsoleLog("AccountJSONStore", f"Removed character {char_name} from {self.email}.")
        else:
            ConsoleLog("AccountJSONStore", f"[WARN] Character {char_name} not found for {self.email}.")
        TEAM_INVENTORY_CACHE[self.email] = self.file.get_json("", None) or {
            "Characters": OrderedDict(),
            "Storage": OrderedDict(),
        }

    def clear_account(self):
        if self._is_current and self.file:
            # Can't unlink the file (autosave would just re-persist an empty doc);
            # emptying the tree is the equivalent operation for JsonFactory.
            self.file.set_json("", {"Characters": {}, "Storage": {}})
        TEAM_INVENTORY_CACHE[self.email] = None
        ConsoleLog("AccountJSONStore", f"Cleared all data for {self.email}.")


class MultiAccountInventoryStore:
    def account_store(self, email):
        return AccountJSONStore(email)

    def load_all(self):
        """Populate TEAM_INVENTORY_CACHE with every discoverable account's data.

        Current account: pulled from the in-memory JsonFactory doc (freshest state,
        including writes made this tick that haven't autosaved yet).
        Other accounts: scanned off disk from json/<email>/TeamInventoryViewer/inventory.json.
        """
        current_email = Player.GetAccountEmail()
        if current_email:
            AccountJSONStore(current_email).load()

        root = _json_root_dir()
        if root is not None and root.exists():
            for account_dir in root.iterdir():
                if not account_dir.is_dir():
                    continue
                name = account_dir.name
                if name == "Global" or name == current_email:
                    continue
                if not (account_dir / AccountJSONStore.FILE).exists():
                    continue
                AccountJSONStore(name).load()

        return TEAM_INVENTORY_CACHE

    def clear_all_data(self):
        """Empty the current account's doc; delete other accounts' inventory files off disk."""
        current_email = Player.GetAccountEmail()
        if current_email:
            AccountJSONStore(current_email).clear_account()
        TEAM_INVENTORY_CACHE.clear()

        root = _json_root_dir()
        if root is None or not root.exists():
            return
        for account_dir in root.iterdir():
            if not account_dir.is_dir() or account_dir.name == "Global" or account_dir.name == current_email:
                continue
            f = account_dir / AccountJSONStore.FILE
            if f.exists():
                try:
                    f.unlink()
                except Exception as e:
                    ConsoleLog("MultiAccountInventoryStore", f"[WARN] Failed to delete {f}: {e}")


multi_store = MultiAccountInventoryStore()
inventory_model_ids_store = ModelIDJSONStore()
inventory_mod_hash_store = ModHashJSONStore()
inventory_model_file_ids_store = ModelFileIDJSONStore()


ROW_ICON_SIZE = 36.0
ROW_HEIGHT = 40.0

# ImGuiTableBgTarget values (RowBg targets paint the whole row's background slot;
# TableFlags.RowBg alternates between RowBg0 and RowBg1 for zebra striping, so we
# override BOTH to keep the rarity tint visible on every row regardless of parity).
_TABLE_BG_TARGET_ROW_BG0 = 1
_TABLE_BG_TARGET_ROW_BG1 = 2

# Alpha kept low so item text stays readable over the tint. Missing/unknown rarity
# yields None from the dict, which short-circuits set_bg_color calls in the helper.
RARITY_ROW_BG = {
    Rarity.White.value: Color(64, 64, 72, 55).to_color(),
    Rarity.Blue.value: Color(60, 130, 220, 55).to_color(),
    Rarity.Purple.value: Color(160, 100, 220, 55).to_color(),
    Rarity.Gold.value: Color(220, 180, 60, 55).to_color(),
    Rarity.Green.value: Color(60, 180, 100, 55).to_color(),
}


def _apply_rarity_row_bg(info):
    """Tint the current row's background based on the item's stored rarity.

    Must be called immediately after ``PyImGui.table_next_row(...)`` and before any
    per-cell ``table_set_bg_color`` call in the same row. No-ops on missing/unknown
    rarity or when the item is White (no tint).
    """
    color = RARITY_ROW_BG.get(info.get("rarity"))
    if not color:
        return
    PyImGui.table_set_bg_color(_TABLE_BG_TARGET_ROW_BG0, color, -1)
    PyImGui.table_set_bg_color(_TABLE_BG_TARGET_ROW_BG1, color, -1)


def _icon_texture_for(info):
    """Always render from game memory (gwdat://<file_id>) when possible.

    Lookup order:
      1. The item's own stored model_file_id (freshest, gender-correct).
      2. The shared model_id → file_id cache (populated by any scan on any
         character, so we get real icons even for items we haven't held).
      3. On-disk PNG atlas via get_texture_for_model (last resort).
    """
    file_id = int(info.get("model_file_id") or 0)
    if file_id <= 0:
        model_id = info.get("model_id", 0)
        file_id = inventory_model_file_ids_store.get(str(model_id), 0)
    if file_id > 0:
        return f"gwdat://{file_id}"
    return get_texture_for_model(info.get("model_id", 0))


# region Generators
def get_character_bag_items_coroutine(bag, bag_id, email, char_name, bag_name):
    """Updates recorded_data[email]["Characters"][char_name]["Inventory"][bag_name]"""

    store = AccountJSONStore(email)
    if not email or not char_name:
        return

    bag_items = yield from _collect_bag_items(bag, bag_id, email, char_name=char_name)
    store.save_bag(char_name=char_name, bag_name=bag_name, bag_items=bag_items)


def get_storage_bag_items_coroutine(bag, bag_id, email, storage_name):
    """Updates recorded_data[email]["Storage"][bag_name]"""

    store = AccountJSONStore(email)
    if not email:
        return

    bag_items = yield from _collect_bag_items(bag, bag_id, email, storage_name=storage_name)
    store.save_bag(storage_name=storage_name, bag_items=bag_items)


def get_mods_from_item(item_id, model_id):
    """Fetch modifiers via GLOBAL_CACHE — bag.GetItems() returns bag-slot stubs
    without a `.modifiers` attribute; the real PyItem instance is what carries
    them (see Py4GWCoreLib/GlobalCache/ItemCache.py:571)."""
    raw_modifiers = GLOBAL_CACHE.Item.Mods.GetModifiers(item_id) or []
    item_type_int, _item_type_name = GLOBAL_CACHE.Item.GetItemType(item_id)
    if not raw_modifiers:
        return (None, None, None)

    try:
        item_type = ItemType(item_type_int)
    except ValueError:
        return (None, None, None)

    modifiers = []
    for mod in raw_modifiers:
        modifiers.append(
            [
                mod.GetIdentifier(),
                mod.GetArg1(),
                mod.GetArg2(),
            ]
        )
    result = parse_modifiers(
        modifiers=modifiers,
        item_type=item_type,
        model_id=model_id,
        db=MOD_DB,
    )

    prefix = None
    suffix = None
    inherent = None

    if result.prefix and isinstance(result.prefix, MatchedWeaponModInfo):
        prefix = result.prefix.weapon_mod.name
    elif result.prefix and isinstance(result.prefix, MatchedRuneInfo):
        prefix = result.prefix.rune.name

    if result.inherent and isinstance(result.inherent, MatchedWeaponModInfo):
        inherent = result.inherent.weapon_mod.name

    if result.suffix and isinstance(result.suffix, MatchedWeaponModInfo):
        suffix = result.suffix.weapon_mod.name
    elif result.suffix and isinstance(result.suffix, MatchedRuneInfo):
        suffix = result.suffix.rune.name

    return (prefix, suffix, inherent)


def _collect_bag_items(bag, bag_id, email, storage_name=None, char_name=None):
    """Shared coroutine to fetch all items from a bag with modifier and frenkey DB name support."""

    def _strip_markup(text):
        if not text:
            return ""

        text = re.sub(r"<c=[^>]+>(.*?)</c>", r"\1", text, flags=re.IGNORECASE)
        text = re.sub(r"\{s\}", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\{sc\}", "", text, flags=re.IGNORECASE)
        text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"</?p>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"\{[^}]+\}", "", text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n\s+", "\n", text)

        return text.strip()

    def _find_last_name_stored_model_id(model_id, slot, count, storage_name=None, char_name=None):
        if char_name:
            items = (
                TEAM_INVENTORY_CACHE.get(email, {})
                .get("Characters", {})
                .get(char_name, {})
                .get("Inventory", {})
                .get(Bags(bag_id).name, {})
            )
        elif storage_name:
            items = TEAM_INVENTORY_CACHE.get(email, {}).get("Storage", {}).get(storage_name, {})
        else:
            items = {}

        # Exact match (model + slot + count) — safest for stacks that share a model.
        for item_name, value in items.items():
            if value.get("model_id") == model_id and value.get("slot", {}).get(str(slot), 0) == count:
                return item_name

        # Unique items (armor/weapons, count=1) rarely stack — accept a model-only
        # match on the same slot so the name survives a slot swap or empty scan.
        if count == 1:
            for item_name, value in items.items():
                if value.get("model_id") == model_id and str(slot) in value.get("slot", {}):
                    return item_name

        return None

    def _generate_unique_key(bag_items: dict, base_name: str) -> str:
        if base_name not in bag_items:
            return base_name

        i = 1
        while f"{base_name} #{i}" in bag_items:
            i += 1

        return f"{base_name} #{i}"

    bag_items = OrderedDict()

    # Prefetch: fire a name request for every item up front so the server can
    # resolve them in parallel while we work through the bag. Otherwise each
    # unknown-model item stalls the coroutine for up to 2s waiting on a name.
    for item in bag.GetItems():
        if not item or item.model_id == 0 or not item.item_id:
            continue
        try:
            if not GLOBAL_CACHE.Item.IsNameReady(item.item_id):
                GLOBAL_CACHE.Item.RequestName(item.item_id)
        except Exception:
            pass

    for item in bag.GetItems():
        if not item or item.model_id == 0:
            continue

        model_id = item.model_id
        item_id = item.item_id
        quantity = item.quantity
        slot = item.slot
        final_name = None

        # Try LootEx, will fail if model id data isn't there
        if GLOBAL_CACHE.Item.Type.IsWeapon(item_id) and not GLOBAL_CACHE.Item.Rarity.IsGreen(item_id):
            final_name = get_weapon_name_from_modifiers(item)
        elif GLOBAL_CACHE.Item.Type.IsArmor(item_id):
            final_name = get_armor_name_from_modifiers(item)

        # For generic items, we use Model ID
        if not final_name:
            try:
                final_name = ModelID(model_id).name.replace("_", " ")

                # Special dye handling - maybe need to hadle mods and whatever here too
                if model_id == ModelID.Vial_Of_Dye:
                    dye_int = GLOBAL_CACHE.Item.GetDyeColor(item_id)
                    final_name = f"{final_name} [{DyeColor(dye_int).name}]"
            except ValueError:
                final_name = None

        # Fetch from last state of the account
        if not final_name:
            stored_name = _find_last_name_stored_model_id(
                model_id, slot, quantity, storage_name=storage_name, char_name=char_name
            )
            if stored_name:
                final_name = stored_name

        if not final_name:
            try:
                markedup = yield from Routines.Yield.Items.GetItemNameByItemID(item_id)
                final_name = _strip_markup(markedup)
                if final_name:
                    model_name, prefix, suffix = clean_gw_item_name(final_name)
                    inventory_model_ids_store.save_model_id(model_id, model_name)
                    raw_modifiers = GLOBAL_CACHE.Item.Mods.GetModifiers(item_id) or []
                    if raw_modifiers:
                        mod_hash = ModHashJSONStore.hash_mods(raw_modifiers)
                        inventory_mod_hash_store.save_mod_hash(mod_hash, prefix, suffix)

            except Exception as e:
                print(f"Exception fetching name for {item_id}: {e}")
                final_name = None

        # Nothing worked â†’ cannot name item
        if not final_name:
            continue

        unique_name = final_name
        if final_name in bag_items:
            unique_name = _generate_unique_key(bag_items, final_name)

        try:
            raw_file_id = int(GLOBAL_CACHE.Item.GetModelFileID(item_id) or 0)
            # Composite items (armor, most weapons) point at a manifest — resolve
            # to the actual texture sub-file for the current character's gender.
            model_file_id = int(Item.GetTrueModelFileID(raw_file_id) or raw_file_id) if raw_file_id > 0 else 0
        except Exception:
            model_file_id = 0

        # Feed the shared model_id → file_id cache so other accounts/characters
        # can render this item's icon straight from GW.dat without needing to
        # have held it themselves.
        if model_file_id > 0:
            inventory_model_file_ids_store.save_model_file_id(model_id, model_file_id)

        # Rarity drives the row background tint. Fetched per-instance because it's
        # a live-item property (drop-time value), not derivable from model_id alone.
        try:
            rarity_val = int(GLOBAL_CACHE.Item.Rarity.GetRarity(item_id)[0])
        except Exception:
            rarity_val = -1

        # Always insert or update using the unique name
        if unique_name not in bag_items:
            bag_items[unique_name] = OrderedDict(
                {
                    "model_id": model_id,
                    "model_file_id": model_file_id,
                    "rarity": rarity_val,
                    "slot": OrderedDict(),
                }
            )
        else:
            if model_file_id and not bag_items[unique_name].get("model_file_id"):
                bag_items[unique_name]["model_file_id"] = model_file_id
            if rarity_val >= 0 and bag_items[unique_name].get("rarity", -1) < 0:
                bag_items[unique_name]["rarity"] = rarity_val

        bag_items[unique_name]["slot"][str(slot)] = quantity

    return bag_items


def record_account_data():
    global current_character_name

    current_email = Player.GetAccountEmail()
    login_number = GLOBAL_CACHE.Party.Players.GetLoginNumberByAgentID(Player.GetAgentID())
    char_name = GLOBAL_CACHE.Party.Players.GetPlayerNameByLoginNumber(login_number)

    if not current_email or not char_name:
        yield
        return

    current_character_name = char_name
    raw_item_cache = GLOBAL_CACHE.Inventory._raw_item_cache

    for bag_name, bag_id in INVENTORY_BAGS.items():
        bag = raw_item_cache.get_bags([bag_id])[0]
        yield from (
            get_character_bag_items_coroutine(
                bag,
                bag_id,
                current_email,
                char_name=char_name,
                bag_name=bag_name,
            )
        )

    for storage_name, bag_id in STORAGE_BAGS.items():
        if bag_id is None:
            continue
        bag = raw_item_cache.get_bags([bag_id])[0]
        yield from (
            get_storage_bag_items_coroutine(
                bag,
                bag_id,
                current_email,
                storage_name=storage_name,
            )
        )


# region Helper functions
def search(query: str, items: list[str]) -> list[str]:
    """Return items matching partially or with fuzzy similarity."""
    if not query:
        return items

    query = query.lower()

    # --- Partial match first (fast) ---
    partial_matches = [item for item in items if query in item.lower()]

    return sorted(partial_matches)


def get_armor_name_from_modifiers(item):
    base_name = inventory_model_ids_store.get(str(item.model_id), "")
    if not base_name:
        try:
            base_name = ModelID(item.model_id).name.replace("_", " ")
        except ValueError:
            return None

    # Collect mods
    prefix, suffix, _inherent = get_mods_from_item(item.item_id, item.model_id)

    # --- Construct name ---
    name_parts = []

    name_parts.append(base_name)

    if prefix:
        name_parts.append(f'| {prefix}')

    if suffix:
        name_parts.append(f"| {suffix}")

    return " ".join(name_parts)


def get_weapon_name_from_modifiers(item):
    base_name = inventory_model_ids_store.get(str(item.model_id), "")
    if not base_name:
        try:
            base_name = ModelID(item.model_id).name.replace("_", " ")
        except ValueError:
            return None

    prefix, suffix, inherent = get_mods_from_item(item.item_id, item.model_id)

    # --- Construct name ---
    name_parts = []

    # Inherent mods like â€œVampiricâ€ or â€œInsightfulâ€ go before everything else
    if prefix:
        name_parts.append(prefix)

    name_parts.append(base_name)

    if suffix:
        name_parts.append(f"{suffix}")

    if inherent:
        name_parts.append(f"({inherent})")

    return " ".join(name_parts)


# region Widget
def draw_widget():
    global TEAM_INVENTORY_CACHE
    global all_accounts_search_query
    global search_query
    global on_first_load

    if on_first_load:
        PyImGui.set_next_window_size(1000, 1250)
        # Window geometry delegated to ImGui native persistence
        on_first_load = False

        TEAM_INVENTORY_CACHE = multi_store.load_all()

    # This triggers a reload of and save of bag data
    if inventory_write_timer.IsExpired() and Routines.Checks.Map.IsOutpost():
        GLOBAL_CACHE.Coroutines.append(record_account_data())
        inventory_write_timer.Reset()

    if inventory_read_timer.IsExpired() and Routines.Checks.Map.IsOutpost():
        TEAM_INVENTORY_CACHE = multi_store.load_all()
        inventory_read_timer.Reset()

    if PyImGui.begin("Team Inventory Viewer"):
        PyImGui.text("Inventory + Storage Viewer")
        PyImGui.separator()

        # === SCROLLABLE AREA START ===
        # Compute space for footer
        available_height = PyImGui.get_window_height() - 190  # leave room for buttons + footer
        PyImGui.begin_child("ScrollableContent", (0.0, float(available_height)), True, 1)

        # === TABS BY ACCOUNT ===
        if TEAM_INVENTORY_CACHE:
            if PyImGui.begin_tab_bar("AccountTabs"):
                # === GLOBAL SEARCH TAB ===
                if PyImGui.begin_tab_item("Search View"):
                    PyImGui.text("Search for items across all accounts")
                    PyImGui.separator()

                    all_accounts_search_query = PyImGui.input_text("##GlobalSearchBar", all_accounts_search_query, 128)
                    PyImGui.separator()

                    if all_accounts_search_query:
                        # === Gather all matching results across accounts ===
                        search_results = []
                        for email, account_data in TEAM_INVENTORY_CACHE.items():
                            # Build a neat identifier like: email â€” [Char1, Char2]
                            character_names = list(account_data.get("Characters", {}).keys())
                            if character_names:
                                character_block = "\n".join(f"   - {name}" for name in character_names)
                                account_label = f"{character_block}"
                            else:
                                account_label = "[No Characters]"

                            # --- Characters ---
                            if "Characters" in account_data:
                                for char_name, char_info in account_data["Characters"].items():
                                    inv_data = char_info.get("Inventory", {})
                                    for bag_name, items in inv_data.items():
                                        for item_name, info in items.items():
                                            if all_accounts_search_query.lower() in item_name.lower():
                                                count = 0
                                                for slot_count in info.get("slot", {}).values():
                                                    count += slot_count
                                                search_results.append(
                                                    {
                                                        "account_label": account_label,
                                                        "email": email,
                                                        "character": char_name,
                                                        "bag": bag_name,
                                                        "item_name": item_name,
                                                        "model_id": info.get("model_id", 0),
                                                        "model_file_id": info.get("model_file_id", 0),
                                                        "rarity": info.get("rarity", -1),
                                                        "count": count or str(info.get('count', 0)),
                                                        "location_type": "Character",
                                                    }
                                                )

                            # --- Storage ---
                            if "Storage" in account_data:
                                for storage_name, items in account_data["Storage"].items():
                                    for item_name, info in items.items():
                                        if all_accounts_search_query.lower() in item_name.lower():
                                            count = 0
                                            for slot_count in info.get("slot", {}).values():
                                                count += slot_count
                                            search_results.append(
                                                {
                                                    "account_label": account_label,
                                                    "email": email,
                                                    "character": None,
                                                    "bag": storage_name,
                                                    "item_name": item_name,
                                                    "model_id": info.get("model_id", 0),
                                                    "model_file_id": info.get("model_file_id", 0),
                                                    "rarity": info.get("rarity", -1),
                                                    "count": count or str(info.get('count', 0)),
                                                    "location_type": "Storage",
                                                }
                                            )

                        # === Display results ===
                        if search_results:
                            # Sort alphabetically ignoring leading numbers
                            search_results.sort(key=lambda entry: re.sub(r'^\d+\s*', '', entry["item_name"]).lower())
                            if PyImGui.begin_table(
                                "SearchResultsTable",
                                5,
                                PyImGui.TableFlags.Borders | PyImGui.TableFlags.RowBg | PyImGui.TableFlags.ScrollY,
                            ):
                                PyImGui.table_setup_column("Icon", PyImGui.TableColumnFlags.WidthFixed, 40.0)
                                PyImGui.table_setup_column("Item Name", PyImGui.TableColumnFlags.WidthStretch, 1.0)
                                PyImGui.table_setup_column("Count", PyImGui.TableColumnFlags.WidthFixed, 40.0)
                                PyImGui.table_setup_column("Location", PyImGui.TableColumnFlags.WidthFixed, 150.0)
                                PyImGui.table_setup_column("Account", PyImGui.TableColumnFlags.WidthFixed, 150.0)
                                PyImGui.table_headers_row()

                                for index, entry in enumerate(search_results):
                                    texture = _icon_texture_for(entry)

                                    PyImGui.table_next_row(0, ROW_HEIGHT)
                                    _apply_rarity_row_bg(entry)

                                    # === ICON ===
                                    PyImGui.table_next_column()
                                    if texture:
                                        ImGui.DrawTexture(texture, ROW_ICON_SIZE, ROW_ICON_SIZE)
                                    else:
                                        PyImGui.text("N/A")

                                    # === ITEM NAME ===
                                    PyImGui.table_next_column()
                                    PyImGui.text(re.sub(r'^\d+\s*', '', entry["item_name"]))

                                    # === COUNT ===
                                    PyImGui.table_next_column()
                                    count = 0
                                    for slot_count in entry.get("slot", {}).values():
                                        count += slot_count
                                    PyImGui.text(str(count) if count else str(entry.get('count', 0)))

                                    # === LOCATION ===
                                    PyImGui.table_next_column()
                                    if entry["location_type"] == "Character":
                                        PyImGui.text(f"{entry['character']}\n  - {entry['bag']}")
                                    else:
                                        PyImGui.text(f"Storage\n  - {entry['bag']}")

                                    # === ACCOUNT IDENTIFIER ===
                                    PyImGui.table_next_column()
                                    if PyImGui.collapsing_header(f'{entry["email"]}##{index}'):
                                        PyImGui.text(entry["account_label"])

                                PyImGui.end_table()
                        else:
                            PyImGui.text("No matching items found.")
                    else:
                        PyImGui.text("Type above to search across all accounts.")
                    PyImGui.end_tab_item()
                for email, account_data in TEAM_INVENTORY_CACHE.items():
                    if PyImGui.begin_tab_item(email):
                        PyImGui.text(f"Account: {email}")
                        PyImGui.separator()

                        # === SEARCH BAR ===
                        PyImGui.text("Search Items:")
                        search_query = PyImGui.input_text("##SearchBar", search_query, 128)
                        PyImGui.separator()

                        PyImGui.begin_child(f"Child_{email}")

                        # === CHARACTER INVENTORIES ===
                        if "Characters" in account_data:
                            for char_name, char_info in account_data["Characters"].items():
                                if char_name == "Invalid ID":
                                    continue

                                if PyImGui.collapsing_header(char_name, True):
                                    inv_data = char_info.get("Inventory", {})
                                    ordered_inv_data = {
                                        bag_name: inv_data.get(bag_name, [])
                                        for bag_name in INVENTORY_BAGS.keys()
                                        if bag_name in inv_data
                                    }
                                    for bag_name, items in ordered_inv_data.items():
                                        if not items:
                                            continue

                                        # Filter visible items
                                        item_names = list(items.keys())
                                        filtered_items = item_names
                                        if search_query:
                                            filtered_items = search(search_query, item_names)
                                        if not filtered_items:
                                            continue

                                        PyImGui.text(bag_name)
                                        if PyImGui.begin_table(
                                            f"InvTable_{email}_{char_name}_{bag_name}",
                                            3,
                                            PyImGui.TableFlags.Borders | PyImGui.TableFlags.RowBg,
                                        ):
                                            PyImGui.table_setup_column("Icon", PyImGui.TableColumnFlags.WidthFixed, 40.0)
                                            PyImGui.table_setup_column("Item Name", PyImGui.TableColumnFlags.WidthStretch, 1.0)
                                            PyImGui.table_setup_column("Count", PyImGui.TableColumnFlags.WidthFixed, 40.0)
                                            PyImGui.table_headers_row()

                                            for item_name in filtered_items:
                                                info = items[item_name]
                                                texture = _icon_texture_for(info)

                                                PyImGui.table_next_row(0, ROW_HEIGHT)
                                                _apply_rarity_row_bg(info)

                                                # === ICON COLUMN ===
                                                PyImGui.table_next_column()
                                                if texture:
                                                    ImGui.DrawTexture(texture, ROW_ICON_SIZE, ROW_ICON_SIZE)
                                                else:
                                                    PyImGui.text("N/A")

                                                # === ITEM NAME COLUMN ===
                                                PyImGui.table_next_column()
                                                PyImGui.text(re.sub(r'^\d+\s*', '', item_name))

                                                # === COUNT COLUMN ===
                                                PyImGui.table_next_column()
                                                count = 0
                                                for slot_count in info.get("slot", {}).values():
                                                    count += slot_count
                                                PyImGui.text(str(count) if count else str(info.get('count', 0)))
                                            PyImGui.end_table()
                                        PyImGui.separator()

                        # === STORAGE SECTION ===
                        if "Storage" in account_data:
                            if PyImGui.collapsing_header("Shared Storage", True):
                                account_storage = account_data.get("Storage", {})
                                ordered_storage_data = {
                                    storage_name: account_storage.get(storage_name, [])
                                    for storage_name in STORAGE_BAGS.keys()
                                    if storage_name in account_storage
                                }
                                for storage_name, items in ordered_storage_data.items():
                                    if not items:
                                        continue

                                    item_names = list(items.keys())
                                    filtered_items = item_names
                                    if search_query:
                                        filtered_items = search(search_query, item_names)
                                    if not filtered_items:
                                        continue

                                    PyImGui.text(storage_name)
                                    if PyImGui.begin_table(
                                        f"StorageTable_{email}_{storage_name}",
                                        3,
                                        PyImGui.TableFlags.Borders | PyImGui.TableFlags.RowBg,
                                    ):
                                        PyImGui.table_setup_column("Icon", PyImGui.TableColumnFlags.WidthFixed, 40.0)
                                        PyImGui.table_setup_column("Item Name", PyImGui.TableColumnFlags.WidthStretch, 1.0)
                                        PyImGui.table_setup_column("Count", PyImGui.TableColumnFlags.WidthFixed, 40.0)
                                        PyImGui.table_headers_row()

                                        for item_name in filtered_items:
                                            info = items[item_name]
                                            texture = _icon_texture_for(info)

                                            PyImGui.table_next_row(0, ROW_HEIGHT)
                                            _apply_rarity_row_bg(info)

                                            # === ICON COLUMN ===
                                            PyImGui.table_next_column()
                                            if texture:
                                                ImGui.DrawTexture(texture, ROW_ICON_SIZE, ROW_ICON_SIZE)
                                            else:
                                                PyImGui.text("N/A")

                                            # === ITEM NAME COLUMN ===
                                            PyImGui.table_next_column()
                                            PyImGui.text(re.sub(r'^\d+\s*', '', item_name))

                                            # === COUNT COLUMN ===
                                            PyImGui.table_next_column()
                                            count = 0
                                            for slot_count in info.get("slot", {}).values():
                                                count += slot_count
                                            PyImGui.text(str(count) if count else str(info.get('count', 0)))
                                        PyImGui.end_table()
                                    PyImGui.separator()

                        PyImGui.end_child()
                        PyImGui.end_tab_item()
                PyImGui.end_tab_bar()
        else:
            PyImGui.text("No recorded accounts found yet.")
        PyImGui.end_child()  # End scrollable section

        PyImGui.separator()
        current_character = f'Current Character: {current_character_name}'
        PyImGui.text(f"{"Waiting for ..." if not current_character_name else current_character}")
        if PyImGui.collapsing_header("Advanced Clearing", True):
            PyImGui.text(
                f'Save timer: {(inventory_write_timer.GetTimeRemaining() / 1000):.1f}(s), Read timer: {(inventory_read_timer.GetTimeRemaining() / 1000):.1f}(s)'
            )
            if PyImGui.begin_table("clear_buttons_table", 3, PyImGui.TableFlags.BordersInnerV):
                # Define colors
                orange_color = Color(255, 165, 0, 255).to_tuple_normalized()  # orange
                orange_hover = Color(255, 200, 50, 255).to_tuple_normalized()
                orange_active = Color(255, 140, 0, 255).to_tuple_normalized()

                red_color = Color(220, 20, 60, 255).to_tuple_normalized()  # crimson red
                red_hover = Color(255, 50, 80, 255).to_tuple_normalized()
                red_active = Color(180, 0, 40, 255).to_tuple_normalized()

                green_color = Color(50, 205, 50, 255).to_tuple_normalized()  # lime green
                green_hover = Color(80, 230, 80, 255).to_tuple_normalized()
                green_active = Color(0, 180, 0, 255).to_tuple_normalized()

                PyImGui.table_next_row()
                # === CLEAR CHARACTER ===
                PyImGui.table_set_column_index(0)
                col_width = PyImGui.get_content_region_avail()[0]
                PyImGui.push_style_color(PyImGui.ImGuiCol.Button, green_color)
                PyImGui.push_style_color(PyImGui.ImGuiCol.ButtonHovered, green_hover)
                PyImGui.push_style_color(PyImGui.ImGuiCol.ButtonActive, green_active)
                if PyImGui.button("Clear Character", width=col_width):
                    current_email = Player.GetAccountEmail()
                    login_number = GLOBAL_CACHE.Party.Players.GetLoginNumberByAgentID(Player.GetAgentID())
                    char_name = GLOBAL_CACHE.Party.Players.GetPlayerNameByLoginNumber(login_number)
                    if current_email and char_name:
                        store = AccountJSONStore(current_email)
                        store.clear_character(char_name)
                    else:
                        ConsoleLog("Inventory Recorder", "No data found for this character.")
                PyImGui.pop_style_color(3)

                # === CLEAR CURRENT ACCOUNT ===
                PyImGui.table_set_column_index(1)
                col_width = PyImGui.get_content_region_avail()[0]
                PyImGui.push_style_color(PyImGui.ImGuiCol.Button, orange_color)
                PyImGui.push_style_color(PyImGui.ImGuiCol.ButtonHovered, orange_hover)
                PyImGui.push_style_color(PyImGui.ImGuiCol.ButtonActive, orange_active)
                if PyImGui.button("Clear Current account", width=col_width):
                    current_email = Player.GetAccountEmail()
                    if current_email:
                        store = AccountJSONStore(current_email)
                        store.clear_account()
                        TEAM_INVENTORY_CACHE = multi_store.load_all()
                    else:
                        ConsoleLog("Inventory Recorder", "No data found for this account.")
                PyImGui.pop_style_color(3)

                # === CLEAR ALL ACCOUNTS ===
                PyImGui.table_set_column_index(2)
                col_width = PyImGui.get_content_region_avail()[0]
                PyImGui.push_style_color(PyImGui.ImGuiCol.Button, red_color)
                PyImGui.push_style_color(PyImGui.ImGuiCol.ButtonHovered, red_hover)
                PyImGui.push_style_color(PyImGui.ImGuiCol.ButtonActive, red_active)
                if PyImGui.button("Clear all accounts", width=col_width):
                    multi_store.clear_all_data()
                    TEAM_INVENTORY_CACHE = multi_store.load_all()
                PyImGui.pop_style_color(3)
                PyImGui.end_table()
    PyImGui.end()

    # Window geometry delegated to ImGui native persistence


def tooltip():
    PyImGui.begin_tooltip()

    # Title
    title_color = Color(255, 200, 100, 255)
    ImGui.push_font("Regular", 20)
    PyImGui.text_colored("Team Inventory Viewer", title_color.to_tuple_normalized())
    ImGui.pop_font()
    PyImGui.spacing()
    PyImGui.separator()

    # Description
    PyImGui.text("This widget allows you to view and search the inventories and storages of all")
    PyImGui.text("your characters across different accounts. It records item data when you are in")
    PyImGui.text("outposts and provides a convenient interface to browse through collected items.")

    PyImGui.spacing()

    # Features
    PyImGui.text_colored("Features:", title_color.to_tuple_normalized())
    PyImGui.bullet_text("Records inventories and storages of all characters across accounts.")
    PyImGui.bullet_text("Provides a searchable interface to quickly find items.")
    PyImGui.bullet_text("Displays item icons using model IDs and LootEx textures.")

    PyImGui.spacing()

    # Credits
    PyImGui.text_colored("Credits:", title_color.to_tuple_normalized())
    PyImGui.bullet_text("Developed by Mark")

    PyImGui.end_tooltip()


def json_tree_view(data):
    # Convert JSON to pretty string
    json_str = json.dumps(data, indent=2)

    # --- In your PyImGui render loop ---
    PyImGui.begin("JSON Viewer", True)

    # Display the JSON string
    PyImGui.text_unformatted(json_str)

    PyImGui.end_child()
    PyImGui.end()


def main():
    try:
        if not Routines.Checks.Map.MapValid() or Map.Pregame.InCharacterSelectScreen():
            # When swapping characters, reset everything
            return

        if Routines.Checks.Map.IsMapReady():
            draw_widget()

    except ImportError as e:
        PySystem.Console.Log(MODULE_NAME, f"ImportError encountered: {str(e)}", PySystem.Console.MessageType.Error)
        PySystem.Console.Log(MODULE_NAME, f"Stack trace: {traceback.format_exc()}", PySystem.Console.MessageType.Error)
    except ValueError as e:
        PySystem.Console.Log(MODULE_NAME, f"ValueError encountered: {str(e)}", PySystem.Console.MessageType.Error)
        PySystem.Console.Log(MODULE_NAME, f"Stack trace: {traceback.format_exc()}", PySystem.Console.MessageType.Error)
    except TypeError as e:
        PySystem.Console.Log(MODULE_NAME, f"TypeError encountered: {str(e)}", PySystem.Console.MessageType.Error)
        PySystem.Console.Log(MODULE_NAME, f"Stack trace: {traceback.format_exc()}", PySystem.Console.MessageType.Error)
    except Exception as e:
        # Catch-all for any other unexpected exceptions
        PySystem.Console.Log(MODULE_NAME, f"Unexpected error encountered: {str(e)}", PySystem.Console.MessageType.Error)
        PySystem.Console.Log(MODULE_NAME, f"Stack trace: {traceback.format_exc()}", PySystem.Console.MessageType.Error)
    finally:
        pass


if __name__ == "__main__":
    main()
