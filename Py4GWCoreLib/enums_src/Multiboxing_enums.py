from enum import auto
from enum import IntEnum

class SharedCommandType(IntEnum):
    NoCommand = auto()
    TravelToMap = auto()
    InviteToParty = auto()
    InteractWithTarget = auto()
    TakeDialogWithTarget = auto()
    GetBlessing = auto()
    OpenChest = auto()
    PickUpLoot = auto()
    UseSkill = auto()
    Resign = auto()
    PixelStack = auto()
    PCon = auto()
    IdentifyItems = auto()
    SalvageItems = auto()
    MerchantItems = auto()
    MerchantMaterials = auto()
    DisableHeroAI = auto()
    EnableHeroAI = auto()
    LeaveParty = auto()
    PressKey = auto()
    DonateToGuild = auto()
    SendDialogToTarget = auto()
    BruteForceUnstuck = auto()
    SetWindowGeometry = auto()
    SetWindowActive = auto()
    SetWindowTitle = auto()
    SetBorderless = auto()
    SetAlwaysOnTop = auto()
    FlashWindow = auto()
    RequestAttention = auto()
    SetTransparentClickThrough = auto()
    SetOpacity = auto()
    UseItem = auto()
    UseSummoningStone = auto()
    PauseWidgets = auto()
    ResumeWidgets = auto()
    SwitchCharacter = auto()
    LoadSkillTemplate = auto()
    LoadSkillTemplateOnHero = auto()
    AddHero = auto()
    KickHero = auto()
    
    SkipCutscene = auto()
    SendDialog = auto()
    SendManualDialog = auto()
    TravelToGuildHall = auto()
    
    SetActiveTitle = auto()
    SetActiveQuest = auto()
    AbandonQuest = auto()

    RestockAllPcons = auto()
    RestockConset = auto()
    RestockResurrectionScroll = auto()
    RestockSummoningStones = auto()
    EnableWidget = auto()
    DisableWidget = auto()
    InventoryQuery = auto()
    EquipItem = auto()
    MerchantRules = auto()
    RefreshHeroAIBuilds = auto()
    WithdrawGold = auto()
    
    Reload = auto()

    #region privately Handled Commands
    MultiBoxing = auto() # privately Handled Command, by frenkey
    ReservedLegacyCommand = auto()
    UseSkillCombatPrep = auto() #handled in CombatPrep only by Mark
    LootEx = auto() # privately Handled Command, by frenkey
    Pycons = auto()
    BroadcastChatCommand = auto()
    ConsoleMessage = auto()
    SetHeadlessLooting = auto()
    SetResurrectionScroll = auto()

    # Nicholas / generic collector exchange.
    # IMPORTANT: appended at the end so existing SharedCommandType values do not shift.
    CollectorExchange = auto()

    # Generic live loot-filter extension for multibox bots.
    # IMPORTANT: appended at the end so existing SharedCommandType values do not shift.
    AddModelToLootWhitelist = auto()
    # Local system-control messages. These are allowlisted to cross gameplay isolation groups.
    # IMPORTANT: append only; persisted/shared enum values must never shift.
    AccountSettingsSync = auto()
    AccountSettingsSyncResult = auto()
    # Generic per-item restock. Append-only: existing shared command values must never shift.
    RestockItem = auto()
    #endregion

class ReloadType(IntEnum):
    Unknown = auto()
    Buying = auto()
    Looting = auto()
    Inventory = auto()
    Crafting = auto()
    Sorting = auto()
    
    Items = auto()
    
    Allies = auto()
    Armorers = auto()
    Artisans = auto()
    Collectors = auto()
    ConsumableCrafters = auto()
    Foes = auto()
    Merchants = auto()
    Traders = auto()
    Weaponsmiths = auto()


class CombatPrepSkillsType(IntEnum):
    SpiritsPrep = auto()
    ShoutsPrep = auto()
