import datetime
from typing import Optional
from Py4GWCoreLib import UIManager
from Py4GWCoreLib import JsonFactory
from Py4GWCoreLib.GlobalCache.ItemCache import Bag_enum
from Py4GWCoreLib.enums import ServerLanguage
import os

# Sanctioned per-account persistence for LootEx settings (JsonFactory, account scope).
# The profile registry (list of profile names) also lives in this document so the
# profile store can be enumerated without scanning a directory.
SETTINGS_DOC = "LootEx/settings.json"


def settings_store() -> JsonFactory:
    """The account-scoped JsonFactory document backing LootEx settings + profile registry."""
    return JsonFactory(SETTINGS_DOC)


class FrameCoords:
    def __init__(self, frame_id: int):
        self.frame_id = frame_id
        self.left, self.top, self.right, self.bottom = UIManager.GetFrameCoords(
            self.frame_id)
        self.height = self.bottom - self.top
        self.width = self.right - self.left


class Settings:
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # only initialize once
        if self._initialized:
            return
        
        self._initialized = True

        from Sources.frenkeyLib.LootEx.filter import Filter
        from Sources.frenkeyLib.LootEx.profile import Profile
        
        self._initialized = True
        self.profile: Profile | None = None
        self.character_profiles: dict[str, str] = {}
        self.profiles: list[Profile] = []
        self.selected_filter: Optional[Filter] = None
        self.automatic_inventory_handling: bool = False
        self.enable_loot_filters: bool = False
        self.window_size: tuple[float, float] = (800, 600)
        self.window_position: tuple[float, float] = (500, 200)
        self.window_collapsed: bool = False
        self.window_visible: bool = False
        self.scraper_window_visible: bool = False


        # NOTE: data_collection_path drives the offline data-collection / scraper tooling
        # (data_collection.py, data.py) which produces bundled catalogs; it is not the
        # config/profile store and is intentionally left as a source-tree path.
        self.data_collection_path = os.path.join(PySystem.Console.get_projects_path(), "Widgets", "Config", "DataCollection")
        self.current_character: str = ""
        
        self.inventory_frame_exists: bool = False
        self.inventory_frame_coords: Optional[FrameCoords] = None
        self.parent_frame_id: Optional[int] = None
                
        self.language : ServerLanguage = ServerLanguage.English
        
        self.collect_items: bool = True
        self.last_xunlai_check : datetime.datetime = datetime.datetime.min
        
        self.max_xunlai_storage : Bag_enum = Bag_enum.Storage_4
        
        self.changed = False
        self.development_mode: bool = os.path.exists("C:\\frenkey_development") 
        self.conversions : dict[str, bool] = {}
        
        self.auto_crafting_enabled : bool = False
        self.auto_withdraw_materials : bool = False
        self.auto_even_consets : bool = False
        
    def set_language(self, lang = ServerLanguage.English):
        self.language = lang
        
    
    def _load_profiles(self):
        """(Re)load every profile named in the account-scoped profile registry."""
        from Sources.frenkeyLib.LootEx.profile import Profile

        self.profiles.clear()

        for profile_name in settings_store().get_json("profiles", []):
            profile = Profile(profile_name)
            profile.load()
            self.profiles.append(profile)

        if not self.profiles:
            default_profile = Profile("Default")
            default_profile.save()  # registers "Default" in the profile registry
            self.profiles.append(default_profile)

    def ReloadProfiles(self):
        """Reloads the profiles from the account-scoped profile registry."""
        self._load_profiles()

    def SetProfile(self, profile_name: str | None):
        from Sources.frenkeyLib.LootEx import loot_handling
        from Sources.frenkeyLib.LootEx import inventory_handling
        from Sources.frenkeyLib.LootEx.filter import Filter
        from Sources.frenkeyLib.LootEx.profile import Profile
        
        self.profile = Profile("Default")
        
        if profile_name is not None:            
            for profile in self.profiles:
                if profile.name == profile_name:
                    self.profile = profile
                    break
                
            if self.profile is None:
                self.profile = self.profiles[0] if self.profiles else Profile("Default")
            
            if not self.profiles:
                self.profiles.append(self.profile)
                
        inventory_handling.InventoryHandler().reset()
        
        if self.enable_loot_filters:
            loot_handling.LootHandler().Start()
        else:
            loot_handling.LootHandler().Stop()

        if self.profile:
            inventory_handling.InventoryHandler().SetPollingInterval(self.profile.polling_interval)

    def save(self):
        """Persist the settings through the sanctioned account-scoped JsonFactory document."""
        doc = settings_store()
        doc.set_json("character_profiles", self.character_profiles)
        doc.set("automatic_inventory_handling", self.automatic_inventory_handling)
        doc.set("enable_loot_filters", self.enable_loot_filters)
        doc.set_json("window_size", list(self.window_size))
        doc.set_json("window_position", list(self.window_position))
        doc.set("window_collapsed", self.window_collapsed)
        doc.set("collect_items", self.collect_items)
        doc.set("max_xunlai_storage", self.max_xunlai_storage.value)
        doc.set("last_xunlai_check", self.last_xunlai_check.isoformat())
        doc.set_json("conversions", self.conversions)
        doc.set("auto_crafting_enabled", self.auto_crafting_enabled)
        doc.set("auto_withdraw_materials", self.auto_withdraw_materials)
        doc.set("auto_even_consets", self.auto_even_consets)

    def load(self):
        """Load the settings from the sanctioned account-scoped JsonFactory document."""
        # Load profiles from the account-scoped registry.
        self._load_profiles()

        doc = settings_store()
        self.character_profiles = doc.get_json("character_profiles", {})
        self.automatic_inventory_handling = doc.get_bool("automatic_inventory_handling", False)
        self.enable_loot_filters = doc.get_bool("enable_loot_filters", False)
        self.window_size = tuple(doc.get_json("window_size", [400, 200]))
        self.window_position = tuple(doc.get_json("window_position", [200, 200]))
        self.window_collapsed = doc.get_bool("window_collapsed", False)
        self.max_xunlai_storage = Bag_enum(
            doc.get_int("max_xunlai_storage", Bag_enum.Storage_4.value))
        last_xunlai_check_str = doc.get_str("last_xunlai_check", "")
        if last_xunlai_check_str:
            self.last_xunlai_check = datetime.datetime.fromisoformat(last_xunlai_check_str)

        self.collect_items = True  # doc.get_bool("collect_items", False)
        self.conversions = doc.get_json("conversions", {})
        self.auto_crafting_enabled = doc.get_bool("auto_crafting_enabled", False)
        self.auto_withdraw_materials = doc.get_bool("auto_withdraw_materials", False)
        self.auto_even_consets = doc.get_bool("auto_even_consets", False)
