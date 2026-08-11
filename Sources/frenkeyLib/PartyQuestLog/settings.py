
from Py4GWCoreLib.py4gwcorelib_src.Settings import Settings as NativeSettings


_SETTINGS_DOCUMENT = "Widgets/Config/PartyQuestLog.ini"


class Settings:
    _instance = None
    _initialized = False    
        
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Settings, cls).__new__(cls)
        return cls._instance
    
    def __init__(self): 
        # guard: only initialize once
        if self.__class__._initialized:
            return
        
        self.__class__._initialized = True
        
        self.store = NativeSettings(_SETTINGS_DOCUMENT, "global")
        
        self.LogOpen : bool = False
        self.LogPosX : float = 0
        self.LogPosY : float = 0
        self.LogPosHeight : float = 800
        self.LogPosWidth : float = 300
            
        self.ShowOnlyInParty : bool = True
        self.ShowOnlyOnLeader : bool = True
        self.ShowFollowerActiveQuestOnMinimap : bool = True
        self.ShowFollowerActiveQuestOnMissionMap : bool = True
        
        self.show_quests_for_accounts : dict[str, bool] = {}
            
    def save_settings(self):
        self.store.set_bool("Window", "LogOpen", self.LogOpen)
        self.store.set_float("Window", "LogPosX", self.LogPosX)
        self.store.set_float("Window", "LogPosY", self.LogPosY)
        self.store.set_float("Window", "LogPosHeight", self.LogPosHeight)
        self.store.set_float("Window", "LogPosWidth", self.LogPosWidth)

        self.store.set_bool("QuestLog", "ShowOnlyInParty", self.ShowOnlyInParty)
        self.store.set_bool("QuestLog", "ShowOnlyOnLeader", self.ShowOnlyOnLeader)

        self.store.set_bool("Overlays", "ShowFollowerActiveQuestOnMinimap", self.ShowFollowerActiveQuestOnMinimap)
        self.store.set_bool("Overlays", "ShowFollowerActiveQuestOnMissionMap", self.ShowFollowerActiveQuestOnMissionMap)

        for account_email, enabled in self.show_quests_for_accounts.items():
            self.store.set_bool("OverlayAccounts", account_email, enabled)

    def load_settings(self):
        self.store.reload()
        self.LogOpen = self.store.get_bool("Window", "LogOpen", self.LogOpen)
        self.LogPosX = self.store.get_float("Window", "LogPosX", self.LogPosX)
        self.LogPosY = self.store.get_float("Window", "LogPosY", self.LogPosY)
        self.LogPosHeight = self.store.get_float("Window", "LogPosHeight", self.LogPosHeight)
        self.LogPosWidth = self.store.get_float("Window", "LogPosWidth", self.LogPosWidth)

        self.ShowOnlyInParty = self.store.get_bool("QuestLog", "ShowOnlyInParty", self.ShowOnlyInParty)
        self.ShowOnlyOnLeader = self.store.get_bool("QuestLog", "ShowOnlyOnLeader", self.ShowOnlyOnLeader)
        self.ShowFollowerActiveQuestOnMinimap = self.store.get_bool("Overlays", "ShowFollowerActiveQuestOnMinimap", self.ShowFollowerActiveQuestOnMinimap)
        self.ShowFollowerActiveQuestOnMissionMap = self.store.get_bool("Overlays", "ShowFollowerActiveQuestOnMissionMap", self.ShowFollowerActiveQuestOnMissionMap)

        account_section = self.store.items("OverlayAccounts")

        if account_section:
            for account_email, _ in account_section.items():
                self.show_quests_for_accounts[account_email] = self.store.get_bool("OverlayAccounts", account_email, True)

    
