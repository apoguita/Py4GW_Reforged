from Py4GWCoreLib import Agent, AgentArray, Player
from Py4GWCoreLib.GlobalCache import GLOBAL_CACHE
from Sources.frenkeyLib.LootEx.cache import Cached_Item
from Sources.frenkeyLib.LootEx.enum import ItemAction
from Py4GWCoreLib.Py4GWcorelib import ConsoleLog
from Py4GWCoreLib.py4gwcorelib_src.system_settings.loot_filters import LootFilters
from Py4GWCoreLib.enums import Console, ItemType, ModelID, Range, SharedCommandType

LOG_LOOTHANDLING = False

class LootHandler:
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        from Sources.frenkeyLib.LootEx.settings import Settings
        
        # only initialize once
        if self._initialized:
            return
        self._initialized = True
        self.settings = Settings()

    def reset(self):                
        if self.settings.profile is None:
            return
        
        pass
    
    def Stop(self):
        ConsoleLog("LootEx", "Stopping Loot Handler", Console.MessageType.Info)

        # Nothing to uninstall: LootEx no longer registers a predicate with the loot class.
        # Whatever it added is live-only, so it is gone on reset or restart anyway.
        LootFilters().reset_live()
        
        from Sources.frenkeyLib.LootEx.settings import Settings
        settings = Settings()
        settings.enable_loot_filters = False
        settings.save()
        

    def Start(self):
        ConsoleLog("LootEx", "Starting Loot Handler", Console.MessageType.Info)        
    
        # MIGRATED off `AddCustomItemCheck`. Custom item checks were dropped deliberately:
        # they are an override, and they let a script hand the loot class its own ruling to run.
        # A script may hand over VALUES -- a model id, an item id -- never something that decides.
        #
        # So LootEx keeps its own decision (`Should_Loot_Item`) and simply publishes the RESULT:
        # `Publish` walks nearby drops, evaluates them itself, and adds the ones it wants as item
        # ids. Same behaviour, and the loot class stays the only thing that decides.
        # The two quest bundles LootEx used to blacklist here (6102 Spear of Archemorus,
        # 6104 Urn of Saint Viktor) are NOT injected any more. Writing hard-coded entries into the
        # user's live configuration is the library deciding on their behalf; if those should be
        # skipped, they belong in the user's own blacklist where they can see and change them.
        LootFilters()
        
        from Sources.frenkeyLib.LootEx.settings import Settings
        settings = Settings()
        settings.enable_loot_filters = True
        settings.save()
        

    def SetLootRange(self, loot_range: int):
        if self.settings.profile is None:
            ConsoleLog("LootEx", "No profile selected. Cannot set loot range.", Console.MessageType.Warning)
            return
                
        for index, message in GLOBAL_CACHE.ShMem.GetAllMessages():            
            if message.Command == SharedCommandType.PickUpLoot:
                GLOBAL_CACHE.ShMem.MarkMessageAsFinished(message.ReceiverEmail, index)                  
    
    def LootingRoutineActive(self):
        account_email = Player.GetAccountEmail()
        index, message = GLOBAL_CACHE.ShMem.PreviewNextMessage(account_email)
        
        if index == -1 or message is None:
            return False
        
        if message.Command != SharedCommandType.PickUpLoot:
            return False
        
        return True
                  
    def IsEnabled(self) -> bool:
        return self.settings.enable_loot_filters and self.settings.profile is not None
                        
    def Publish(self, distance: float = Range.SafeCompass.value) -> int:
        """Evaluate nearby drops and add the wanted ones as item ids. Returns how many.

        This replaces the custom-item-check hook. Call it each pass while LootEx is running --
        an item id means nothing after a map change, so the entries are naturally short-lived and
        the loot class clears them itself.
        """
        if not self.IsEnabled():
            return 0

        loot = LootFilters()
        added = 0
        for agent_id in AgentArray.Filter.ByDistance(
                AgentArray.GetItemArray(), Player.GetXY(), distance):
            if not Agent.IsValid(agent_id):
                continue
            item_agent = Agent.GetItemAgentByID(agent_id)
            if item_agent is None:
                continue
            if self.Should_Loot_Item(item_agent.item_id):
                loot.add_item(agent_id)
                added += 1
        return added

    def Should_Loot_Item(self, item_id: int) -> bool:
        # ConsoleLog("LootEx", f"Checking if item {item_id} should be looted.", Console.MessageType.Debug)
                
        if self.settings.profile is None:
            ConsoleLog("LootEx", "No profile selected. Cannot determine loot action.", Console.MessageType.Warning)
            return False
        
        if self.settings.enable_loot_filters == False:
            return False
        
        cached_item = Cached_Item(item_id)
                
        if not cached_item.data:
            if cached_item.item_type != ItemType.Bundle:
                ConsoleLog("LootEx", f"Item {item_id} has no cached data. Cannot determine loot action.", Console.MessageType.Warning)
                return True
        
        if cached_item.model_id == ModelID.Vial_Of_Dye:
            if cached_item.IsVial_Of_DyeToKeep():
                # ConsoleLog("LootEx", f"Item {item_id} is a Vial of Dye that we want to keep.", Console.MessageType.Debug)
                return True
            else:
                # ConsoleLog("LootEx", f"Item {item_id} is a Vial of Dye that we do not want to keep.", Console.MessageType.Debug)
                return False
        
        if cached_item.matches_weapon_rule:
            ConsoleLog("LootEx", f"Item {item_id} matches weapon rule. Should loot.", Console.MessageType.Debug, LOG_LOOTHANDLING)
            return True
        
        if cached_item.matches_skin_rule:
            ConsoleLog("LootEx", f"Item {item_id} matches skin rule. Should loot.", Console.MessageType.Debug, LOG_LOOTHANDLING)
            return True

        for filter in self.settings.profile.filters:
            action = filter.get_action(cached_item)

            if action == ItemAction.Loot:
                ConsoleLog("LootEx", f"Item {item_id} matches filter rule. Should loot.", Console.MessageType.Debug, LOG_LOOTHANDLING)
                return True
        
        # If the item is a salvage item we check for runes we want to pick up and sell
        if cached_item.is_armor:
            if cached_item.runes_to_keep:
                ConsoleLog("LootEx", f"Item {item_id} is armor with runes to keep. Should loot.", Console.MessageType.Debug, LOG_LOOTHANDLING)
                return True
        
        # If the item is a weapon we check if it has a weapon mod we want to keep
        if cached_item.is_weapon:
            if cached_item.weapon_mods_to_keep:
                ConsoleLog("LootEx", f"Item {item_id} is weapon with mods to keep. Should loot.", Console.MessageType.Debug, LOG_LOOTHANDLING)
                return True
            
        return False
