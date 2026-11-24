"""Registry key constants for FrameTree.

Branch nodes are classes carrying KEY; leaves are plain strings.  Frame()
accepts either, so both of these work:

    Frame(FrameId.Skillbar)                    # branch, uses .KEY
    Frame(FrameId.Skillbar.Skill1.Frame.Number)  # leaf, a plain str

Generated from frame_registry.py - do not hand-edit.
"""


class FrameId:
    AcceptButton = 'AcceptButton'

    class ArmorDye:
        KEY = 'ArmorDye'
        BlueDye = 'ArmorDye.BlueDye'
        BrownDye = 'ArmorDye.BrownDye'
        GreenDye = 'ArmorDye.GreenDye'
        GreyDye = 'ArmorDye.GreyDye'
        OrangeDye = 'ArmorDye.OrangeDye'
        PurpleDye = 'ArmorDye.PurpleDye'
        RedDye = 'ArmorDye.RedDye'
        YellowDye = 'ArmorDye.YellowDye'

    ArmorFrame = 'ArmorFrame'

    ArmorIcon = 'ArmorIcon'

    Arrow = 'Arrow'

    BackButton = 'BackButton'

    BackButton2 = 'BackButton2'

    BackButton3 = 'BackButton3'

    BodyScaleFrame = 'BodyScaleFrame'

    Boots = 'Boots'

    CancelButton = 'CancelButton'

    Cape = 'Cape'

    Caption = 'Caption'

    class CharacerNameFrame:
        KEY = 'CharacerNameFrame'
        class Child:
            KEY = 'CharacerNameFrame.Child'
            CharacterNameCheck1 = 'CharacerNameFrame.Child.CharacterNameCheck1'
            CharacterNameCheck2 = 'CharacerNameFrame.Child.CharacterNameCheck2'
            CharacterNameCheck3 = 'CharacerNameFrame.Child.CharacterNameCheck3'
            CharacterNameCheck4 = 'CharacerNameFrame.Child.CharacterNameCheck4'
            CharacterNameInput = 'CharacerNameFrame.Child.CharacterNameInput'
            MiddleText = 'CharacerNameFrame.Child.MiddleText'
            UnderInputText = 'CharacerNameFrame.Child.UnderInputText'
        TitleText = 'CharacerNameFrame.TitleText'

    CharacterCreateCharacterAppearanceFrame = 'CharacterCreateCharacterAppearanceFrame'

    class CharacterCreateCharacterProfessionFrame:
        KEY = 'CharacterCreateCharacterProfessionFrame'
        BottomText = 'CharacterCreateCharacterProfessionFrame.BottomText'
        Child = 'CharacterCreateCharacterProfessionFrame.Child'

    class CharacterCreateCharacterSexFrame:
        KEY = 'CharacterCreateCharacterSexFrame'
        Child = 'CharacterCreateCharacterSexFrame.Child'

    class CharacterFrame:
        KEY = 'CharacterFrame'
        Child = 'CharacterFrame.Child'

    class CharacterInfoFrame:
        KEY = 'CharacterInfoFrame'
        Text = 'CharacterInfoFrame.Text'
        Text2 = 'CharacterInfoFrame.Text2'
        Text3 = 'CharacterInfoFrame.Text3'
        Text4 = 'CharacterInfoFrame.Text4'
        Text5 = 'CharacterInfoFrame.Text5'
        Text6 = 'CharacterInfoFrame.Text6'

    CharacterPreviewFrame = 'CharacterPreviewFrame'

    CharacterSlotsInUseFrame = 'CharacterSlotsInUseFrame'

    Chat = 'Chat'

    class ChatChannels:
        KEY = 'ChatChannels'
        AlianceText = 'ChatChannels.AlianceText'
        All = 'ChatChannels.All'
        AllText = 'ChatChannels.AllText'
        Alliance = 'ChatChannels.Alliance'
        Guild = 'ChatChannels.Guild'
        GuildText = 'ChatChannels.GuildText'
        Team = 'ChatChannels.Team'
        TeamText = 'ChatChannels.TeamText'
        Trade = 'ChatChannels.Trade'
        TradeText = 'ChatChannels.TradeText'
        Whisper = 'ChatChannels.Whisper'
        WhisperText = 'ChatChannels.WhisperText'

    class ChatChannelsToggle:
        KEY = 'ChatChannelsToggle'
        Alliance = 'ChatChannelsToggle.Alliance'
        Emotes = 'ChatChannelsToggle.Emotes'
        Guild = 'ChatChannelsToggle.Guild'
        Local = 'ChatChannelsToggle.Local'
        Team = 'ChatChannelsToggle.Team'
        Trade = 'ChatChannelsToggle.Trade'

    class ChatLog:
        KEY = 'ChatLog'
        class Frame:
            KEY = 'ChatLog.Frame'
            Scrollbar = 'ChatLog.Frame.Scrollbar'
            class Text:
                KEY = 'ChatLog.Frame.Text'
                class Area:
                    KEY = 'ChatLog.Frame.Text.Area'
                    class Line1:
                        KEY = 'ChatLog.Frame.Text.Area.Line1'
                        class Text:
                            KEY = 'ChatLog.Frame.Text.Area.Line1.Text'
                            Sender = 'ChatLog.Frame.Text.Area.Line1.Text.Sender'

    Chest = 'Chest'

    ChestFrame = 'ChestFrame'

    ChestText = 'ChestText'

    ChooseYourCharacterTypeText = 'ChooseYourCharacterTypeText'

    CloseWindowButton = 'CloseWindowButton'

    Compass = 'Compass'

    Costume = 'Costume'

    CostumeHeadpiece = 'CostumeHeadpiece'

    CraftButton = 'CraftButton'

    CreateButton = 'CreateButton'

    CreateButton2 = 'CreateButton2'

    CreateButtonGreyedOut = 'CreateButtonGreyedOut'

    class CreateCharacterBottomFrame:
        KEY = 'CreateCharacterBottomFrame'
        class AppearanceTab:
            KEY = 'CreateCharacterBottomFrame.AppearanceTab'
            Text = 'CreateCharacterBottomFrame.AppearanceTab.Text'
        class BodyTab:
            KEY = 'CreateCharacterBottomFrame.BodyTab'
            Text = 'CreateCharacterBottomFrame.BodyTab.Text'
        class CampaignTab:
            KEY = 'CreateCharacterBottomFrame.CampaignTab'
            Text = 'CreateCharacterBottomFrame.CampaignTab.Text'
        class NameTab:
            KEY = 'CreateCharacterBottomFrame.NameTab'
            Text = 'CreateCharacterBottomFrame.NameTab.Text'
        class ProfessionTab:
            KEY = 'CreateCharacterBottomFrame.ProfessionTab'
            Text = 'CreateCharacterBottomFrame.ProfessionTab.Text'
        class SexTab:
            KEY = 'CreateCharacterBottomFrame.SexTab'
            Text = 'CreateCharacterBottomFrame.SexTab.Text'

    CustomizeWeaponButton = 'CustomizeWeaponButton'

    DamageMonitor = 'DamageMonitor'

    DeclineButton = 'DeclineButton'

    DeleteButton = 'DeleteButton'

    DestroyItemSlot = 'DestroyItemSlot'

    Dialogue1 = 'Dialogue1'

    Dialogue2 = 'Dialogue2'

    DidNotCleaningDisconnectPopupCharselectNoButton = 'DidNotCleaningDisconnectPopupCharselectNoButton'

    DidNotCleaningDisconnectPopupCharselectQuestionMark = 'DidNotCleaningDisconnectPopupCharselectQuestionMark'

    DidNotCleaningDisconnectPopupCharselectTextFrame = 'DidNotCleaningDisconnectPopupCharselectTextFrame'

    DidNotCleaningDisconnectPopupCharselectYesButton = 'DidNotCleaningDisconnectPopupCharselectYesButton'

    class DistrictList:
        KEY = 'DistrictList'
        Dropdown = 'DistrictList.Dropdown'

    DropBundleButton = 'DropBundleButton'

    EditAccountButton = 'EditAccountButton'

    EffectsMonitor = 'EffectsMonitor'

    EnableWeaponSetsWindow = 'EnableWeaponSetsWindow'

    class EnergyBar:
        KEY = 'EnergyBar'
        Frame = 'EnergyBar.Frame'

    EquipNow = 'EquipNow'

    EquipSkillWindow = 'EquipSkillWindow'

    EquipmentPackSlot = 'EquipmentPackSlot'

    class ExperienceBar:
        KEY = 'ExperienceBar'
        Frame = 'ExperienceBar.Frame'

    FaceFrame = 'FaceFrame'

    FeetFrame = 'FeetFrame'

    FeetText = 'FeetText'

    Frame = 'Frame'

    FrameSpacer = 'FrameSpacer'

    FriendsWindow = 'FriendsWindow'

    Gloves = 'Gloves'

    class GoldInfo:
        KEY = 'GoldInfo'
        Gold = 'GoldInfo.Gold'
        Platinum = 'GoldInfo.Platinum'
        PlatinumQty = 'GoldInfo.PlatinumQty'
        Qty = 'GoldInfo.Qty'

    GoldOffer = 'GoldOffer'

    GoldOffered = 'GoldOffered'

    GoldText = 'GoldText'

    GuildBattleWindow = 'GuildBattleWindow'

    GuildWindow = 'GuildWindow'

    HairColorFrame = 'HairColorFrame'

    HairStyleFrame = 'HairStyleFrame'

    HandsFrame = 'HandsFrame'

    HandsText = 'HandsText'

    Head = 'Head'

    HeadFrame = 'HeadFrame'

    HeadText = 'HeadText'

    class HealthBar:
        KEY = 'HealthBar'
        Frame = 'HealthBar.Frame'

    HelpWindow = 'HelpWindow'

    class Hero1Window:
        KEY = 'Hero1Window'
        class AvatarFrame:
            KEY = 'Hero1Window.AvatarFrame'
            Content = 'Hero1Window.AvatarFrame.Content'
            Content1 = 'Hero1Window.AvatarFrame.Content1'
        AvoidButton = 'Hero1Window.AvoidButton'
        BuffFrame = 'Hero1Window.BuffFrame'
        EnergyBar = 'Hero1Window.EnergyBar'
        FightButton = 'Hero1Window.FightButton'
        GuardButton = 'Hero1Window.GuardButton'
        HealthBar = 'Hero1Window.HealthBar'
        class SkillBar:
            KEY = 'Hero1Window.SkillBar'
            Skill1 = 'Hero1Window.SkillBar.Skill1'
            Skill2 = 'Hero1Window.SkillBar.Skill2'
            Skill3 = 'Hero1Window.SkillBar.Skill3'
            Skill4 = 'Hero1Window.SkillBar.Skill4'
            Skill5 = 'Hero1Window.SkillBar.Skill5'
            Skill6 = 'Hero1Window.SkillBar.Skill6'
            Skill7 = 'Hero1Window.SkillBar.Skill7'
            Skill8 = 'Hero1Window.SkillBar.Skill8'
        TargetButton = 'Hero1Window.TargetButton'

    class Hero2Window:
        KEY = 'Hero2Window'
        AvatarFrame = 'Hero2Window.AvatarFrame'
        AvoidButton = 'Hero2Window.AvoidButton'
        BuffFrame = 'Hero2Window.BuffFrame'
        EnergyBar = 'Hero2Window.EnergyBar'
        FightButton = 'Hero2Window.FightButton'
        GuardButton = 'Hero2Window.GuardButton'
        HealthBar = 'Hero2Window.HealthBar'
        class SkillBar:
            KEY = 'Hero2Window.SkillBar'
            Skill1 = 'Hero2Window.SkillBar.Skill1'
            Skill2 = 'Hero2Window.SkillBar.Skill2'
            Skill3 = 'Hero2Window.SkillBar.Skill3'
            Skill4 = 'Hero2Window.SkillBar.Skill4'
            Skill5 = 'Hero2Window.SkillBar.Skill5'
            Skill6 = 'Hero2Window.SkillBar.Skill6'
            Skill7 = 'Hero2Window.SkillBar.Skill7'
            Skill8 = 'Hero2Window.SkillBar.Skill8'
        TargetButton = 'Hero2Window.TargetButton'

    class Hero3Window:
        KEY = 'Hero3Window'
        AvatarFrame = 'Hero3Window.AvatarFrame'
        AvoidButton = 'Hero3Window.AvoidButton'
        BuffFrame = 'Hero3Window.BuffFrame'
        EnergyBar = 'Hero3Window.EnergyBar'
        FightButton = 'Hero3Window.FightButton'
        GuardButton = 'Hero3Window.GuardButton'
        HealthBar = 'Hero3Window.HealthBar'
        class SkillBar:
            KEY = 'Hero3Window.SkillBar'
            Skill1 = 'Hero3Window.SkillBar.Skill1'
            Skill2 = 'Hero3Window.SkillBar.Skill2'
            Skill3 = 'Hero3Window.SkillBar.Skill3'
            Skill4 = 'Hero3Window.SkillBar.Skill4'
            Skill5 = 'Hero3Window.SkillBar.Skill5'
            Skill6 = 'Hero3Window.SkillBar.Skill6'
            Skill7 = 'Hero3Window.SkillBar.Skill7'
            Skill8 = 'Hero3Window.SkillBar.Skill8'
        TargetButton = 'Hero3Window.TargetButton'

    class Hero4Window:
        KEY = 'Hero4Window'
        AvatarFrame = 'Hero4Window.AvatarFrame'
        AvoidButton = 'Hero4Window.AvoidButton'
        BuffFrame = 'Hero4Window.BuffFrame'
        EnergyBar = 'Hero4Window.EnergyBar'
        FightButton = 'Hero4Window.FightButton'
        GuardButton = 'Hero4Window.GuardButton'
        HealthBar = 'Hero4Window.HealthBar'
        class SkillBar:
            KEY = 'Hero4Window.SkillBar'
            Skill1 = 'Hero4Window.SkillBar.Skill1'
            Skill2 = 'Hero4Window.SkillBar.Skill2'
            Skill3 = 'Hero4Window.SkillBar.Skill3'
            Skill4 = 'Hero4Window.SkillBar.Skill4'
            Skill5 = 'Hero4Window.SkillBar.Skill5'
            Skill6 = 'Hero4Window.SkillBar.Skill6'
            Skill7 = 'Hero4Window.SkillBar.Skill7'
            Skill8 = 'Hero4Window.SkillBar.Skill8'
        TargetButton = 'Hero4Window.TargetButton'

    class Hero5Window:
        KEY = 'Hero5Window'
        AvatarFrame = 'Hero5Window.AvatarFrame'
        AvoidButton = 'Hero5Window.AvoidButton'
        BuffFrame = 'Hero5Window.BuffFrame'
        EnergyBar = 'Hero5Window.EnergyBar'
        FightButton = 'Hero5Window.FightButton'
        GuardButton = 'Hero5Window.GuardButton'
        HealthBar = 'Hero5Window.HealthBar'
        class SkillBar:
            KEY = 'Hero5Window.SkillBar'
            Skill1 = 'Hero5Window.SkillBar.Skill1'
            Skill2 = 'Hero5Window.SkillBar.Skill2'
            Skill3 = 'Hero5Window.SkillBar.Skill3'
            Skill4 = 'Hero5Window.SkillBar.Skill4'
            Skill5 = 'Hero5Window.SkillBar.Skill5'
            Skill6 = 'Hero5Window.SkillBar.Skill6'
            Skill7 = 'Hero5Window.SkillBar.Skill7'
            Skill8 = 'Hero5Window.SkillBar.Skill8'
        TargetButton = 'Hero5Window.TargetButton'

    class Hero6Window:
        KEY = 'Hero6Window'
        AvatarFrame = 'Hero6Window.AvatarFrame'
        AvoidButton = 'Hero6Window.AvoidButton'
        BuffFrame = 'Hero6Window.BuffFrame'
        EnergyBar = 'Hero6Window.EnergyBar'
        FightButton = 'Hero6Window.FightButton'
        GuardButton = 'Hero6Window.GuardButton'
        HealthBar = 'Hero6Window.HealthBar'
        class SkillBar:
            KEY = 'Hero6Window.SkillBar'
            Skill1 = 'Hero6Window.SkillBar.Skill1'
            Skill2 = 'Hero6Window.SkillBar.Skill2'
            Skill3 = 'Hero6Window.SkillBar.Skill3'
            Skill4 = 'Hero6Window.SkillBar.Skill4'
            Skill5 = 'Hero6Window.SkillBar.Skill5'
            Skill6 = 'Hero6Window.SkillBar.Skill6'
            Skill7 = 'Hero6Window.SkillBar.Skill7'
            Skill8 = 'Hero6Window.SkillBar.Skill8'
        TargetButton = 'Hero6Window.TargetButton'

    class Hero7Window:
        KEY = 'Hero7Window'
        AvatarFrame = 'Hero7Window.AvatarFrame'
        AvoidButton = 'Hero7Window.AvoidButton'
        BuffFrame = 'Hero7Window.BuffFrame'
        EnergyBar = 'Hero7Window.EnergyBar'
        FightButton = 'Hero7Window.FightButton'
        GuardButton = 'Hero7Window.GuardButton'
        HealthBar = 'Hero7Window.HealthBar'
        class SkillBar:
            KEY = 'Hero7Window.SkillBar'
            Skill1 = 'Hero7Window.SkillBar.Skill1'
            Skill2 = 'Hero7Window.SkillBar.Skill2'
            Skill3 = 'Hero7Window.SkillBar.Skill3'
            Skill4 = 'Hero7Window.SkillBar.Skill4'
            Skill5 = 'Hero7Window.SkillBar.Skill5'
            Skill6 = 'Hero7Window.SkillBar.Skill6'
            Skill7 = 'Hero7Window.SkillBar.Skill7'
            Skill8 = 'Hero7Window.SkillBar.Skill8'
        TargetButton = 'Hero7Window.TargetButton'

    class HeroWindow:
        KEY = 'HeroWindow'
        CharacterAvatar = 'HeroWindow.CharacterAvatar'
        CharacterName = 'HeroWindow.CharacterName'
        Class = 'HeroWindow.Class'
        class Info:
            KEY = 'HeroWindow.Info'
            Level = 'HeroWindow.Info.Level'
            SkillPoints = 'HeroWindow.Info.SkillPoints'
            XpBar = 'HeroWindow.Info.XpBar'
        class Tabs:
            KEY = 'HeroWindow.Tabs'
            AccountTab = 'HeroWindow.Tabs.AccountTab'
            class Content:
                KEY = 'HeroWindow.Tabs.Content'
                class Inner:
                    KEY = 'HeroWindow.Tabs.Content.Inner'
                    class Account:
                        KEY = 'HeroWindow.Tabs.Content.Inner.Account'
                        Name = 'HeroWindow.Tabs.Content.Inner.Account.Name'
                        class TournamentData:
                            KEY = 'HeroWindow.Tabs.Content.Inner.Account.TournamentData'
                            RewardPoints = 'HeroWindow.Tabs.Content.Inner.Account.TournamentData.RewardPoints'
                            TournamentLabel = 'HeroWindow.Tabs.Content.Inner.Account.TournamentData.TournamentLabel'
                        TournamentInfo = 'HeroWindow.Tabs.Content.Inner.Account.TournamentInfo'
            class Content2:
                KEY = 'HeroWindow.Tabs.Content2'
                class Inner:
                    KEY = 'HeroWindow.Tabs.Content2.Inner'
                    class Factions:
                        KEY = 'HeroWindow.Tabs.Content2.Inner.Factions'
                        class Bars:
                            KEY = 'HeroWindow.Tabs.Content2.Inner.Factions.Bars'
                            Balthazar = 'HeroWindow.Tabs.Content2.Inner.Factions.Bars.Balthazar'
                            Imperial = 'HeroWindow.Tabs.Content2.Inner.Factions.Bars.Imperial'
                            Kurzick = 'HeroWindow.Tabs.Content2.Inner.Factions.Bars.Kurzick'
                            Luxon = 'HeroWindow.Tabs.Content2.Inner.Factions.Bars.Luxon'
            class Content3:
                KEY = 'HeroWindow.Tabs.Content3'
                class Inner:
                    KEY = 'HeroWindow.Tabs.Content3.Inner'
                    ScrollBar = 'HeroWindow.Tabs.Content3.Inner.ScrollBar'
                    class Titles:
                        KEY = 'HeroWindow.Tabs.Content3.Inner.Titles'
                        class Area:
                            KEY = 'HeroWindow.Tabs.Content3.Inner.Titles.Area'
                            Asura = 'HeroWindow.Tabs.Content3.Inner.Titles.Area.Asura'
                            CanthaExplorationTitleTrack = 'HeroWindow.Tabs.Content3.Inner.Titles.Area.CanthaExplorationTitleTrack'
                            CanthanEliteSkillHunter = 'HeroWindow.Tabs.Content3.Inner.Titles.Area.CanthanEliteSkillHunter'
                            CanthanVanquisher = 'HeroWindow.Tabs.Content3.Inner.Titles.Area.CanthanVanquisher'
                            Deldrimor = 'HeroWindow.Tabs.Content3.Inner.Titles.Area.Deldrimor'
                            Drunkard = 'HeroWindow.Tabs.Content3.Inner.Titles.Area.Drunkard'
                            EbonVanguard = 'HeroWindow.Tabs.Content3.Inner.Titles.Area.EbonVanguard'
                            ElonaExploration = 'HeroWindow.Tabs.Content3.Inner.Titles.Area.ElonaExploration'
                            EotnMastery = 'HeroWindow.Tabs.Content3.Inner.Titles.Area.EotnMastery'
                            Gamer = 'HeroWindow.Tabs.Content3.Inner.Titles.Area.Gamer'
                            GuardianofTyria = 'HeroWindow.Tabs.Content3.Inner.Titles.Area.GuardianofTyria'
                            Gwamm = 'HeroWindow.Tabs.Content3.Inner.Titles.Area.Gwamm'
                            KurzickSupporter = 'HeroWindow.Tabs.Content3.Inner.Titles.Area.KurzickSupporter'
                            Ldoa = 'HeroWindow.Tabs.Content3.Inner.Titles.Area.Ldoa'
                            LegendaryGuardian = 'HeroWindow.Tabs.Content3.Inner.Titles.Area.LegendaryGuardian'
                            LegendaryVanquisher = 'HeroWindow.Tabs.Content3.Inner.Titles.Area.LegendaryVanquisher'
                            Lightbringer = 'HeroWindow.Tabs.Content3.Inner.Titles.Area.Lightbringer'
                            Lucky = 'HeroWindow.Tabs.Content3.Inner.Titles.Area.Lucky'
                            Norn = 'HeroWindow.Tabs.Content3.Inner.Titles.Area.Norn'
                            PartyAnimal = 'HeroWindow.Tabs.Content3.Inner.Titles.Area.PartyAnimal'
                            ProtectorofCantha = 'HeroWindow.Tabs.Content3.Inner.Titles.Area.ProtectorofCantha'
                            ProtectorofElona = 'HeroWindow.Tabs.Content3.Inner.Titles.Area.ProtectorofElona'
                            ProtectorofTyria = 'HeroWindow.Tabs.Content3.Inner.Titles.Area.ProtectorofTyria'
                            Sunspear = 'HeroWindow.Tabs.Content3.Inner.Titles.Area.Sunspear'
                            Survivor = 'HeroWindow.Tabs.Content3.Inner.Titles.Area.Survivor'
                            SweetTooth = 'HeroWindow.Tabs.Content3.Inner.Titles.Area.SweetTooth'
                            TreasureHunter = 'HeroWindow.Tabs.Content3.Inner.Titles.Area.TreasureHunter'
                            TyrianEliteSkillHunter = 'HeroWindow.Tabs.Content3.Inner.Titles.Area.TyrianEliteSkillHunter'
                            TyrianEliteSkillHunter2 = 'HeroWindow.Tabs.Content3.Inner.Titles.Area.TyrianEliteSkillHunter2'
                            TyrianExploration = 'HeroWindow.Tabs.Content3.Inner.Titles.Area.TyrianExploration'
                            TyrianVanquisher = 'HeroWindow.Tabs.Content3.Inner.Titles.Area.TyrianVanquisher'
                            Unlucky = 'HeroWindow.Tabs.Content3.Inner.Titles.Area.Unlucky'
                            Wisdom = 'HeroWindow.Tabs.Content3.Inner.Titles.Area.Wisdom'
                            Zaishen = 'HeroWindow.Tabs.Content3.Inner.Titles.Area.Zaishen'
            FactionTab = 'HeroWindow.Tabs.FactionTab'
            TitlesTab = 'HeroWindow.Tabs.TitlesTab'

    HideUiCheckbox = 'HideUiCheckbox'

    Hints = 'Hints'

    Icons = 'Icons'

    IdentifyAll = 'IdentifyAll'

    InGameClock = 'InGameClock'

    class InventoryBagsWindow:
        KEY = 'InventoryBagsWindow'
        class Content:
            KEY = 'InventoryBagsWindow.Content'
            class C0:
                KEY = 'InventoryBagsWindow.Content.C0'
                class C0:
                    KEY = 'InventoryBagsWindow.Content.C0.C0'
                    class Bag1:
                        KEY = 'InventoryBagsWindow.Content.C0.C0.Bag1'
                        Slot1 = 'InventoryBagsWindow.Content.C0.C0.Bag1.Slot1'
                        Slot10 = 'InventoryBagsWindow.Content.C0.C0.Bag1.Slot10'
                        Slot11 = 'InventoryBagsWindow.Content.C0.C0.Bag1.Slot11'
                        Slot12 = 'InventoryBagsWindow.Content.C0.C0.Bag1.Slot12'
                        Slot13 = 'InventoryBagsWindow.Content.C0.C0.Bag1.Slot13'
                        Slot14 = 'InventoryBagsWindow.Content.C0.C0.Bag1.Slot14'
                        Slot15 = 'InventoryBagsWindow.Content.C0.C0.Bag1.Slot15'
                        Slot16 = 'InventoryBagsWindow.Content.C0.C0.Bag1.Slot16'
                        Slot17 = 'InventoryBagsWindow.Content.C0.C0.Bag1.Slot17'
                        Slot18 = 'InventoryBagsWindow.Content.C0.C0.Bag1.Slot18'
                        Slot19 = 'InventoryBagsWindow.Content.C0.C0.Bag1.Slot19'
                        Slot2 = 'InventoryBagsWindow.Content.C0.C0.Bag1.Slot2'
                        Slot20 = 'InventoryBagsWindow.Content.C0.C0.Bag1.Slot20'
                        Slot3 = 'InventoryBagsWindow.Content.C0.C0.Bag1.Slot3'
                        Slot4 = 'InventoryBagsWindow.Content.C0.C0.Bag1.Slot4'
                        Slot5 = 'InventoryBagsWindow.Content.C0.C0.Bag1.Slot5'
                        Slot6 = 'InventoryBagsWindow.Content.C0.C0.Bag1.Slot6'
                        Slot7 = 'InventoryBagsWindow.Content.C0.C0.Bag1.Slot7'
                        Slot8 = 'InventoryBagsWindow.Content.C0.C0.Bag1.Slot8'
                        Slot9 = 'InventoryBagsWindow.Content.C0.C0.Bag1.Slot9'
                    class C1:
                        KEY = 'InventoryBagsWindow.Content.C0.C0.C1'
                        Slot1 = 'InventoryBagsWindow.Content.C0.C0.C1.Slot1'
                        Slot2 = 'InventoryBagsWindow.Content.C0.C0.C1.Slot2'
                        Slot3 = 'InventoryBagsWindow.Content.C0.C0.C1.Slot3'
                        Slot4 = 'InventoryBagsWindow.Content.C0.C0.C1.Slot4'
                        Slot5 = 'InventoryBagsWindow.Content.C0.C0.C1.Slot5'
                    class C2:
                        KEY = 'InventoryBagsWindow.Content.C0.C0.C2'
                        Slot1 = 'InventoryBagsWindow.Content.C0.C0.C2.Slot1'
                        Slot10 = 'InventoryBagsWindow.Content.C0.C0.C2.Slot10'
                        Slot2 = 'InventoryBagsWindow.Content.C0.C0.C2.Slot2'
                        Slot3 = 'InventoryBagsWindow.Content.C0.C0.C2.Slot3'
                        Slot4 = 'InventoryBagsWindow.Content.C0.C0.C2.Slot4'
                        Slot5 = 'InventoryBagsWindow.Content.C0.C0.C2.Slot5'
                        Slot6 = 'InventoryBagsWindow.Content.C0.C0.C2.Slot6'
                        Slot7 = 'InventoryBagsWindow.Content.C0.C0.C2.Slot7'
                        Slot8 = 'InventoryBagsWindow.Content.C0.C0.C2.Slot8'
                        Slot9 = 'InventoryBagsWindow.Content.C0.C0.C2.Slot9'
                    class C3:
                        KEY = 'InventoryBagsWindow.Content.C0.C0.C3'
                        Slot1 = 'InventoryBagsWindow.Content.C0.C0.C3.Slot1'
                        Slot10 = 'InventoryBagsWindow.Content.C0.C0.C3.Slot10'
                        Slot2 = 'InventoryBagsWindow.Content.C0.C0.C3.Slot2'
                        Slot3 = 'InventoryBagsWindow.Content.C0.C0.C3.Slot3'
                        Slot4 = 'InventoryBagsWindow.Content.C0.C0.C3.Slot4'
                        Slot5 = 'InventoryBagsWindow.Content.C0.C0.C3.Slot5'
                        Slot6 = 'InventoryBagsWindow.Content.C0.C0.C3.Slot6'
                        Slot7 = 'InventoryBagsWindow.Content.C0.C0.C3.Slot7'
                        Slot8 = 'InventoryBagsWindow.Content.C0.C0.C3.Slot8'
                        Slot9 = 'InventoryBagsWindow.Content.C0.C0.C3.Slot9'

    class InventoryWindow:
        KEY = 'InventoryWindow'
        class Backpack:
            KEY = 'InventoryWindow.Backpack'
            Slot1 = 'InventoryWindow.Backpack.Slot1'
            Slot2 = 'InventoryWindow.Backpack.Slot2'
        class Bag1:
            KEY = 'InventoryWindow.Bag1'
            Slot1 = 'InventoryWindow.Bag1.Slot1'
            Slot2 = 'InventoryWindow.Bag1.Slot2'
        class Bag2:
            KEY = 'InventoryWindow.Bag2'
            Slot1 = 'InventoryWindow.Bag2.Slot1'
            Slot2 = 'InventoryWindow.Bag2.Slot2'
        BagsBar = 'InventoryWindow.BagsBar'
        class BeltPouch:
            KEY = 'InventoryWindow.BeltPouch'
            Slot1 = 'InventoryWindow.BeltPouch.Slot1'
            Slot10 = 'InventoryWindow.BeltPouch.Slot10'
            Slot2 = 'InventoryWindow.BeltPouch.Slot2'
        CharacterInfo = 'InventoryWindow.CharacterInfo'
        DividerBelowHeroes = 'InventoryWindow.DividerBelowHeroes'
        class EquipmentPack:
            KEY = 'InventoryWindow.EquipmentPack'
            Slot1 = 'InventoryWindow.EquipmentPack.Slot1'
            Slot15 = 'InventoryWindow.EquipmentPack.Slot15'
            Slot2 = 'InventoryWindow.EquipmentPack.Slot2'
            Slot20 = 'InventoryWindow.EquipmentPack.Slot20'
        class PartyPortraits:
            KEY = 'InventoryWindow.PartyPortraits'
            Player1 = 'InventoryWindow.PartyPortraits.Player1'
            Player2 = 'InventoryWindow.PartyPortraits.Player2'
            Player3 = 'InventoryWindow.PartyPortraits.Player3'
            Player4 = 'InventoryWindow.PartyPortraits.Player4'
            Player5 = 'InventoryWindow.PartyPortraits.Player5'
            Player6 = 'InventoryWindow.PartyPortraits.Player6'
            Player7 = 'InventoryWindow.PartyPortraits.Player7'
            Player8 = 'InventoryWindow.PartyPortraits.Player8'
            Portrait1 = 'InventoryWindow.PartyPortraits.Portrait1'
            Portrait2 = 'InventoryWindow.PartyPortraits.Portrait2'
            Portrait3 = 'InventoryWindow.PartyPortraits.Portrait3'
            Portrait4 = 'InventoryWindow.PartyPortraits.Portrait4'
            Portrait5 = 'InventoryWindow.PartyPortraits.Portrait5'
            Portrait6 = 'InventoryWindow.PartyPortraits.Portrait6'
            Portrait7 = 'InventoryWindow.PartyPortraits.Portrait7'
            Portrait8 = 'InventoryWindow.PartyPortraits.Portrait8'

    ItemsOffered = 'ItemsOffered'

    Label = 'Label'

    LegsFrame = 'LegsFrame'

    LegsText = 'LegsText'

    LogOutButton = 'LogOutButton'

    MaxButton = 'MaxButton'

    class MenuButton:
        KEY = 'MenuButton'
        class Menu:
            KEY = 'MenuButton.Menu'
            HeroMenu = 'MenuButton.Menu.HeroMenu'
            Seperator = 'MenuButton.Menu.Seperator'

    class MercenarySlotAd:
        KEY = 'MercenarySlotAd'
        EnterStoreButton = 'MercenarySlotAd.EnterStoreButton'
        LargeText = 'MercenarySlotAd.LargeText'
        SmallText = 'MercenarySlotAd.SmallText'

    class Merchant:
        KEY = 'Merchant'
        class C0:
            KEY = 'Merchant.C0'
            class C0:
                KEY = 'Merchant.C0.C0'
                BuyButton = 'Merchant.C0.C0.BuyButton'
                class C4:
                    KEY = 'Merchant.C0.C0.C4'
                    class C0:
                        KEY = 'Merchant.C0.C0.C4.C0'
                        class ItemContainer:
                            KEY = 'Merchant.C0.C0.C4.C0.ItemContainer'
                            Item1 = 'Merchant.C0.C0.C4.C0.ItemContainer.Item1'
                            Item2 = 'Merchant.C0.C0.C4.C0.ItemContainer.Item2'
                CloseButton = 'Merchant.C0.C0.CloseButton'
                Exchange = 'Merchant.C0.C0.Exchange'
                Goodbye = 'Merchant.C0.C0.Goodbye'
                RequestQuoteButton = 'Merchant.C0.C0.RequestQuoteButton'
                TraderCloseButton = 'Merchant.C0.C0.TraderCloseButton'
            class C1:
                KEY = 'Merchant.C0.C1'
                CustomizeButton = 'Merchant.C0.C1.CustomizeButton'
            QuoteField = 'Merchant.C0.QuoteField'

    MerchantBuyButton = 'MerchantBuyButton'

    MinimizeWindowButton = 'MinimizeWindowButton'

    MissionGoals = 'MissionGoals'

    MissionMap = 'MissionMap'

    MissionProgress = 'MissionProgress'

    class MissionStatusAndScoreDisplay:
        KEY = 'MissionStatusAndScoreDisplay'
        class C0:
            KEY = 'MissionStatusAndScoreDisplay.C0'
            class C1:
                KEY = 'MissionStatusAndScoreDisplay.C0.C1'
                CancelEnterMissionButton = 'MissionStatusAndScoreDisplay.C0.C1.CancelEnterMissionButton'

    MouseInstructionsFrame = 'MouseInstructionsFrame'

    NextButton = 'NextButton'

    NextButton2 = 'NextButton2'

    Notifications = 'Notifications'

    class NpcDialog:
        KEY = 'NpcDialog'
        class C2:
            KEY = 'NpcDialog.C2'
            class C0:
                KEY = 'NpcDialog.C2.C0'
                class C0:
                    KEY = 'NpcDialog.C2.C0.C0'
                    class Option:
                        KEY = 'NpcDialog.C2.C0.C0.Option'
                        Icon = 'NpcDialog.C2.C0.C0.Option.Icon'
                        Icon2 = 'NpcDialog.C2.C0.C0.Option.Icon2'
            ScrollBar = 'NpcDialog.C2.ScrollBar'
        UseLockpickButton = 'NpcDialog.UseLockpickButton'

    ObserveWindow = 'ObserveWindow'

    class OfferedItems:
        KEY = 'OfferedItems'
        class C1:
            KEY = 'OfferedItems.C1'
            Item1 = 'OfferedItems.C1.Item1'
            Item2 = 'OfferedItems.C1.Item2'
            Item3 = 'OfferedItems.C1.Item3'
            Item4 = 'OfferedItems.C1.Item4'
            Item5 = 'OfferedItems.C1.Item5'
            Item6 = 'OfferedItems.C1.Item6'
            Item7 = 'OfferedItems.C1.Item7'

    OfferedItems2 = 'OfferedItems2'

    Offhand = 'Offhand'

    OkButton = 'OkButton'

    Option1 = 'Option1'

    Option10 = 'Option10'

    Option11 = 'Option11'

    Option12 = 'Option12'

    Option13 = 'Option13'

    Option14 = 'Option14'

    Option15 = 'Option15'

    Option16 = 'Option16'

    Option2 = 'Option2'

    Option3 = 'Option3'

    Option4 = 'Option4'

    Option5 = 'Option5'

    Option6 = 'Option6'

    Option7 = 'Option7'

    Option8 = 'Option8'

    Option9 = 'Option9'

    OptionsButton = 'OptionsButton'

    class OptionsWindow:
        KEY = 'OptionsWindow'
        GwVersion = 'OptionsWindow.GwVersion'
        class InnerFrame:
            KEY = 'OptionsWindow.InnerFrame'
            ControlOptionsTab = 'OptionsWindow.InnerFrame.ControlOptionsTab'
            ControlOptionsTabInternal = 'OptionsWindow.InnerFrame.ControlOptionsTabInternal'
            GamepadOptionsTab = 'OptionsWindow.InnerFrame.GamepadOptionsTab'
            GeneralOptionsTab = 'OptionsWindow.InnerFrame.GeneralOptionsTab'
            GeneralOptionsTabInternal = 'OptionsWindow.InnerFrame.GeneralOptionsTabInternal'
            GraphicsOptionsTab = 'OptionsWindow.InnerFrame.GraphicsOptionsTab'
            GraphicsOptionsTabInternal = 'OptionsWindow.InnerFrame.GraphicsOptionsTabInternal'
            InterfaceOptionsTab = 'OptionsWindow.InnerFrame.InterfaceOptionsTab'
            InterfaceOptionsTabInternal = 'OptionsWindow.InnerFrame.InterfaceOptionsTabInternal'
            SoundOptionsTab = 'OptionsWindow.InnerFrame.SoundOptionsTab'
            SoundOptionsTabInternal = 'OptionsWindow.InnerFrame.SoundOptionsTabInternal'

    Pants = 'Pants'

    class PartyFormation:
        KEY = 'PartyFormation'
        class Explorable:
            KEY = 'PartyFormation.Explorable'
            class C0:
                KEY = 'PartyFormation.Explorable.C0'
                class C0:
                    KEY = 'PartyFormation.Explorable.C0.C0'
                    MembersParentExplorable = 'PartyFormation.Explorable.C0.C0.MembersParentExplorable'
                    class PetsHeader:
                        KEY = 'PartyFormation.Explorable.C0.C0.PetsHeader'
                        Expand = 'PartyFormation.Explorable.C0.C0.PetsHeader.Expand'
                        Title = 'PartyFormation.Explorable.C0.C0.PetsHeader.Title'
        class Outpost:
            KEY = 'PartyFormation.Outpost'
            ButtonKick = 'PartyFormation.Outpost.ButtonKick'
            ButtonLeave = 'PartyFormation.Outpost.ButtonLeave'
            ButtonSearch = 'PartyFormation.Outpost.ButtonSearch'
            class GameMode:
                KEY = 'PartyFormation.Outpost.GameMode'
                HardMode = 'PartyFormation.Outpost.GameMode.HardMode'
                NormalMode = 'PartyFormation.Outpost.GameMode.NormalMode'
                Text = 'PartyFormation.Outpost.GameMode.Text'
            class Members:
                KEY = 'PartyFormation.Outpost.Members'
                class Frame:
                    KEY = 'PartyFormation.Outpost.Members.Frame'
                    class C0:
                        KEY = 'PartyFormation.Outpost.Members.Frame.C0'
                        class C0:
                            KEY = 'PartyFormation.Outpost.Members.Frame.C0.C0'
                            class Parent:
                                KEY = 'PartyFormation.Outpost.Members.Frame.C0.C0.Parent'
                                class C1:
                                    KEY = 'PartyFormation.Outpost.Members.Frame.C0.C0.Parent.C1'
                                    ReadyToggle = 'PartyFormation.Outpost.Members.Frame.C0.C0.Parent.C1.ReadyToggle'
                                class C10:
                                    KEY = 'PartyFormation.Outpost.Members.Frame.C0.C0.Parent.C10'
                                    Player1 = 'PartyFormation.Outpost.Members.Frame.C0.C0.Parent.C10.Player1'
                                    class Player2:
                                        KEY = 'PartyFormation.Outpost.Members.Frame.C0.C0.Parent.C10.Player2'
                                        class Frame:
                                            KEY = 'PartyFormation.Outpost.Members.Frame.C0.C0.Parent.C10.Player2.Frame'
                                            PlayerName = 'PartyFormation.Outpost.Members.Frame.C0.C0.Parent.C10.Player2.Frame.PlayerName'
                                        HeroWindowToggle = 'PartyFormation.Outpost.Members.Frame.C0.C0.Parent.C10.Player2.HeroWindowToggle'
                                    class Player3:
                                        KEY = 'PartyFormation.Outpost.Members.Frame.C0.C0.Parent.C10.Player3'
                                        HeroWindowToggle = 'PartyFormation.Outpost.Members.Frame.C0.C0.Parent.C10.Player3.HeroWindowToggle'
                                    class Player4:
                                        KEY = 'PartyFormation.Outpost.Members.Frame.C0.C0.Parent.C10.Player4'
                                        HeroWindowToggle = 'PartyFormation.Outpost.Members.Frame.C0.C0.Parent.C10.Player4.HeroWindowToggle'
                                    class Player5:
                                        KEY = 'PartyFormation.Outpost.Members.Frame.C0.C0.Parent.C10.Player5'
                                        HeroWindowToggle = 'PartyFormation.Outpost.Members.Frame.C0.C0.Parent.C10.Player5.HeroWindowToggle'
                                    class Player6:
                                        KEY = 'PartyFormation.Outpost.Members.Frame.C0.C0.Parent.C10.Player6'
                                        HeroWindowToggle = 'PartyFormation.Outpost.Members.Frame.C0.C0.Parent.C10.Player6.HeroWindowToggle'
                                    class Player7:
                                        KEY = 'PartyFormation.Outpost.Members.Frame.C0.C0.Parent.C10.Player7'
                                        HeroWindowToggle = 'PartyFormation.Outpost.Members.Frame.C0.C0.Parent.C10.Player7.HeroWindowToggle'
                                    class Player8:
                                        KEY = 'PartyFormation.Outpost.Members.Frame.C0.C0.Parent.C10.Player8'
                                        HeroWindowToggle = 'PartyFormation.Outpost.Members.Frame.C0.C0.Parent.C10.Player8.HeroWindowToggle'
                                    ReadyFlag = 'PartyFormation.Outpost.Members.Frame.C0.C0.Parent.C10.ReadyFlag'
                                Member7 = 'PartyFormation.Outpost.Members.Frame.C0.C0.Parent.Member7'

    class PartySearchWindow:
        KEY = 'PartySearchWindow'
        class Panel:
            KEY = 'PartySearchWindow.Panel'
            SlotLast = 'PartySearchWindow.Panel.SlotLast'
            SlotPrev = 'PartySearchWindow.Panel.SlotPrev'
            SlotPrev2 = 'PartySearchWindow.Panel.SlotPrev2'

    class PerformanceMonitor:
        KEY = 'PerformanceMonitor'
        Frame = 'PerformanceMonitor.Frame'

    PetControl = 'PetControl'

    PlayButton = 'PlayButton'

    PlayButtonGreyedOut = 'PlayButtonGreyedOut'

    class QuestLogWindow:
        KEY = 'QuestLogWindow'
        class C3:
            KEY = 'QuestLogWindow.C3'
            ScrollBar = 'QuestLogWindow.C3.ScrollBar'

    RestoreWindowButton = 'RestoreWindowButton'

    class Root:
        KEY = 'Root'
        class C2:
            KEY = 'Root.C2'
            class C6:
                KEY = 'Root.C2.C6'
                class C100:
                    KEY = 'Root.C2.C6.C100'
                    class C2:
                        KEY = 'Root.C2.C6.C100.C2'
                        ConfirmEnterMissionButton = 'Root.C2.C6.C100.C2.ConfirmEnterMissionButton'

    Ruler = 'Ruler'

    class SalvageWindow:
        KEY = 'SalvageWindow'
        Button = 'SalvageWindow.Button'
        CancelButton = 'SalvageWindow.CancelButton'
        Details = 'SalvageWindow.Details'
        HeaderLabel = 'SalvageWindow.HeaderLabel'
        class Options:
            KEY = 'SalvageWindow.Options'
            Option1 = 'SalvageWindow.Options.Option1'
            Option2 = 'SalvageWindow.Options.Option2'
            Option3 = 'SalvageWindow.Options.Option3'
            Option4 = 'SalvageWindow.Options.Option4'
        class OptionsWindowConfirmMaterialsWindow:
            KEY = 'SalvageWindow.OptionsWindowConfirmMaterialsWindow'
            Cancel = 'SalvageWindow.OptionsWindowConfirmMaterialsWindow.Cancel'
            Confirm = 'SalvageWindow.OptionsWindowConfirmMaterialsWindow.Confirm'

    class ScreenFrame:
        KEY = 'ScreenFrame'
        class C17:
            KEY = 'ScreenFrame.C17'
            class GuildWarsWasUnableToCompleteTheOperationPopupCharselect:
                KEY = 'ScreenFrame.C17.GuildWarsWasUnableToCompleteTheOperationPopupCharselect'
                ExclimationMark = 'ScreenFrame.C17.GuildWarsWasUnableToCompleteTheOperationPopupCharselect.ExclimationMark'
                OkButton = 'ScreenFrame.C17.GuildWarsWasUnableToCompleteTheOperationPopupCharselect.OkButton'
                TextFrame = 'ScreenFrame.C17.GuildWarsWasUnableToCompleteTheOperationPopupCharselect.TextFrame'
        class C6:
            KEY = 'ScreenFrame.C6'
            class ExpertSalvageUnidentifiedItem:
                KEY = 'ScreenFrame.C6.ExpertSalvageUnidentifiedItem'
                Cancel = 'ScreenFrame.C6.ExpertSalvageUnidentifiedItem.Cancel'
                Confirm = 'ScreenFrame.C6.ExpertSalvageUnidentifiedItem.Confirm'
            class LesserSalvageWindow:
                KEY = 'ScreenFrame.C6.LesserSalvageWindow'
                SalvageWithLesserKitCancel = 'ScreenFrame.C6.LesserSalvageWindow.SalvageWithLesserKitCancel'
                SalvageWithLesserKitConfirm = 'ScreenFrame.C6.LesserSalvageWindow.SalvageWithLesserKitConfirm'
            LogOut = 'ScreenFrame.C6.LogOut'
            NpcNameplateFrame = 'ScreenFrame.C6.NpcNameplateFrame'
            NpcNameplateFrame10 = 'ScreenFrame.C6.NpcNameplateFrame10'
            NpcNameplateFrame11 = 'ScreenFrame.C6.NpcNameplateFrame11'
            NpcNameplateFrame12 = 'ScreenFrame.C6.NpcNameplateFrame12'
            NpcNameplateFrame13 = 'ScreenFrame.C6.NpcNameplateFrame13'
            NpcNameplateFrame14 = 'ScreenFrame.C6.NpcNameplateFrame14'
            NpcNameplateFrame15 = 'ScreenFrame.C6.NpcNameplateFrame15'
            NpcNameplateFrame16 = 'ScreenFrame.C6.NpcNameplateFrame16'
            NpcNameplateFrame17 = 'ScreenFrame.C6.NpcNameplateFrame17'
            NpcNameplateFrame18 = 'ScreenFrame.C6.NpcNameplateFrame18'
            NpcNameplateFrame19 = 'ScreenFrame.C6.NpcNameplateFrame19'
            NpcNameplateFrame2 = 'ScreenFrame.C6.NpcNameplateFrame2'
            NpcNameplateFrame20 = 'ScreenFrame.C6.NpcNameplateFrame20'
            NpcNameplateFrame21 = 'ScreenFrame.C6.NpcNameplateFrame21'
            NpcNameplateFrame22 = 'ScreenFrame.C6.NpcNameplateFrame22'
            NpcNameplateFrame23 = 'ScreenFrame.C6.NpcNameplateFrame23'
            class NpcNameplateFrame24:
                KEY = 'ScreenFrame.C6.NpcNameplateFrame24'
                NpcNameplateFrame = 'ScreenFrame.C6.NpcNameplateFrame24.NpcNameplateFrame'
            class NpcNameplateFrame25:
                KEY = 'ScreenFrame.C6.NpcNameplateFrame25'
                NpcNameplateFrame = 'ScreenFrame.C6.NpcNameplateFrame25.NpcNameplateFrame'
            class NpcNameplateFrame26:
                KEY = 'ScreenFrame.C6.NpcNameplateFrame26'
                NpcNameplateFrame = 'ScreenFrame.C6.NpcNameplateFrame26.NpcNameplateFrame'
            NpcNameplateFrame27 = 'ScreenFrame.C6.NpcNameplateFrame27'
            NpcNameplateFrame28 = 'ScreenFrame.C6.NpcNameplateFrame28'
            NpcNameplateFrame29 = 'ScreenFrame.C6.NpcNameplateFrame29'
            NpcNameplateFrame3 = 'ScreenFrame.C6.NpcNameplateFrame3'
            NpcNameplateFrame30 = 'ScreenFrame.C6.NpcNameplateFrame30'
            NpcNameplateFrame31 = 'ScreenFrame.C6.NpcNameplateFrame31'
            NpcNameplateFrame32 = 'ScreenFrame.C6.NpcNameplateFrame32'
            class NpcNameplateFrame33:
                KEY = 'ScreenFrame.C6.NpcNameplateFrame33'
                NpcNameplateFrame = 'ScreenFrame.C6.NpcNameplateFrame33.NpcNameplateFrame'
            NpcNameplateFrame34 = 'ScreenFrame.C6.NpcNameplateFrame34'
            NpcNameplateFrame35 = 'ScreenFrame.C6.NpcNameplateFrame35'
            NpcNameplateFrame36 = 'ScreenFrame.C6.NpcNameplateFrame36'
            NpcNameplateFrame37 = 'ScreenFrame.C6.NpcNameplateFrame37'
            NpcNameplateFrame38 = 'ScreenFrame.C6.NpcNameplateFrame38'
            NpcNameplateFrame39 = 'ScreenFrame.C6.NpcNameplateFrame39'
            NpcNameplateFrame4 = 'ScreenFrame.C6.NpcNameplateFrame4'
            NpcNameplateFrame40 = 'ScreenFrame.C6.NpcNameplateFrame40'
            NpcNameplateFrame41 = 'ScreenFrame.C6.NpcNameplateFrame41'
            NpcNameplateFrame42 = 'ScreenFrame.C6.NpcNameplateFrame42'
            NpcNameplateFrame43 = 'ScreenFrame.C6.NpcNameplateFrame43'
            NpcNameplateFrame44 = 'ScreenFrame.C6.NpcNameplateFrame44'
            NpcNameplateFrame45 = 'ScreenFrame.C6.NpcNameplateFrame45'
            NpcNameplateFrame46 = 'ScreenFrame.C6.NpcNameplateFrame46'
            NpcNameplateFrame47 = 'ScreenFrame.C6.NpcNameplateFrame47'
            NpcNameplateFrame48 = 'ScreenFrame.C6.NpcNameplateFrame48'
            NpcNameplateFrame49 = 'ScreenFrame.C6.NpcNameplateFrame49'
            NpcNameplateFrame5 = 'ScreenFrame.C6.NpcNameplateFrame5'
            NpcNameplateFrame50 = 'ScreenFrame.C6.NpcNameplateFrame50'
            NpcNameplateFrame51 = 'ScreenFrame.C6.NpcNameplateFrame51'
            NpcNameplateFrame52 = 'ScreenFrame.C6.NpcNameplateFrame52'
            NpcNameplateFrame53 = 'ScreenFrame.C6.NpcNameplateFrame53'
            NpcNameplateFrame54 = 'ScreenFrame.C6.NpcNameplateFrame54'
            NpcNameplateFrame55 = 'ScreenFrame.C6.NpcNameplateFrame55'
            NpcNameplateFrame56 = 'ScreenFrame.C6.NpcNameplateFrame56'
            NpcNameplateFrame57 = 'ScreenFrame.C6.NpcNameplateFrame57'
            NpcNameplateFrame58 = 'ScreenFrame.C6.NpcNameplateFrame58'
            NpcNameplateFrame59 = 'ScreenFrame.C6.NpcNameplateFrame59'
            NpcNameplateFrame6 = 'ScreenFrame.C6.NpcNameplateFrame6'
            NpcNameplateFrame60 = 'ScreenFrame.C6.NpcNameplateFrame60'
            NpcNameplateFrame61 = 'ScreenFrame.C6.NpcNameplateFrame61'
            NpcNameplateFrame62 = 'ScreenFrame.C6.NpcNameplateFrame62'
            NpcNameplateFrame63 = 'ScreenFrame.C6.NpcNameplateFrame63'
            NpcNameplateFrame64 = 'ScreenFrame.C6.NpcNameplateFrame64'
            NpcNameplateFrame65 = 'ScreenFrame.C6.NpcNameplateFrame65'
            NpcNameplateFrame66 = 'ScreenFrame.C6.NpcNameplateFrame66'
            NpcNameplateFrame67 = 'ScreenFrame.C6.NpcNameplateFrame67'
            NpcNameplateFrame68 = 'ScreenFrame.C6.NpcNameplateFrame68'
            NpcNameplateFrame69 = 'ScreenFrame.C6.NpcNameplateFrame69'
            NpcNameplateFrame7 = 'ScreenFrame.C6.NpcNameplateFrame7'
            NpcNameplateFrame70 = 'ScreenFrame.C6.NpcNameplateFrame70'
            NpcNameplateFrame71 = 'ScreenFrame.C6.NpcNameplateFrame71'
            NpcNameplateFrame72 = 'ScreenFrame.C6.NpcNameplateFrame72'
            NpcNameplateFrame73 = 'ScreenFrame.C6.NpcNameplateFrame73'
            NpcNameplateFrame74 = 'ScreenFrame.C6.NpcNameplateFrame74'
            NpcNameplateFrame75 = 'ScreenFrame.C6.NpcNameplateFrame75'
            NpcNameplateFrame76 = 'ScreenFrame.C6.NpcNameplateFrame76'
            NpcNameplateFrame77 = 'ScreenFrame.C6.NpcNameplateFrame77'
            NpcNameplateFrame78 = 'ScreenFrame.C6.NpcNameplateFrame78'
            NpcNameplateFrame79 = 'ScreenFrame.C6.NpcNameplateFrame79'
            NpcNameplateFrame8 = 'ScreenFrame.C6.NpcNameplateFrame8'
            NpcNameplateFrame80 = 'ScreenFrame.C6.NpcNameplateFrame80'
            NpcNameplateFrame81 = 'ScreenFrame.C6.NpcNameplateFrame81'
            NpcNameplateFrame82 = 'ScreenFrame.C6.NpcNameplateFrame82'
            NpcNameplateFrame83 = 'ScreenFrame.C6.NpcNameplateFrame83'
            NpcNameplateFrame84 = 'ScreenFrame.C6.NpcNameplateFrame84'
            NpcNameplateFrame85 = 'ScreenFrame.C6.NpcNameplateFrame85'
            NpcNameplateFrame86 = 'ScreenFrame.C6.NpcNameplateFrame86'
            NpcNameplateFrame87 = 'ScreenFrame.C6.NpcNameplateFrame87'
            NpcNameplateFrame88 = 'ScreenFrame.C6.NpcNameplateFrame88'
            NpcNameplateFrame89 = 'ScreenFrame.C6.NpcNameplateFrame89'
            NpcNameplateFrame9 = 'ScreenFrame.C6.NpcNameplateFrame9'
            Options = 'ScreenFrame.C6.Options'
            class SalvageMaterialsDialog:
                KEY = 'ScreenFrame.C6.SalvageMaterialsDialog'
                Label = 'ScreenFrame.C6.SalvageMaterialsDialog.Label'
                NoButton = 'ScreenFrame.C6.SalvageMaterialsDialog.NoButton'
                QuestionFrame = 'ScreenFrame.C6.SalvageMaterialsDialog.QuestionFrame'
                YesButton = 'ScreenFrame.C6.SalvageMaterialsDialog.YesButton'
            class ScreenFrame:
                KEY = 'ScreenFrame.C6.ScreenFrame'
                SkipCutsceneButton = 'ScreenFrame.C6.ScreenFrame.SkipCutsceneButton'
        CharacterCreateCharacterFrame = 'ScreenFrame.CharacterCreateCharacterFrame'
        class Child:
            KEY = 'ScreenFrame.Child'
            CharacterCreateCharacterTypeFrame = 'ScreenFrame.Child.CharacterCreateCharacterTypeFrame'
            class CharacterSelectFrame:
                KEY = 'ScreenFrame.Child.CharacterSelectFrame'
                class DeleteCharacterFrame:
                    KEY = 'ScreenFrame.Child.CharacterSelectFrame.DeleteCharacterFrame'
                    CancelButton = 'ScreenFrame.Child.CharacterSelectFrame.DeleteCharacterFrame.CancelButton'
                    DeleteButton = 'ScreenFrame.Child.CharacterSelectFrame.DeleteCharacterFrame.DeleteButton'
                    NameInput = 'ScreenFrame.Child.CharacterSelectFrame.DeleteCharacterFrame.NameInput'
                    Text = 'ScreenFrame.Child.CharacterSelectFrame.DeleteCharacterFrame.Text'
        DidNotCleaningDisconnectPopupCharselect = 'ScreenFrame.DidNotCleaningDisconnectPopupCharselect'
        class LeaveYourPartyDialog:
            KEY = 'ScreenFrame.LeaveYourPartyDialog'
            NoLeaveYourPartyButton = 'ScreenFrame.LeaveYourPartyDialog.NoLeaveYourPartyButton'
            YesLeaveYourPartyButton = 'ScreenFrame.LeaveYourPartyDialog.YesLeaveYourPartyButton'

    class SelectCampaignSliderFrame:
        KEY = 'SelectCampaignSliderFrame'
        Child = 'SelectCampaignSliderFrame.Child'

    SelectedOption = 'SelectedOption'

    Set1 = 'Set1'

    Set2 = 'Set2'

    Set3 = 'Set3'

    Set4 = 'Set4'

    ShowCheckbox = 'ShowCheckbox'

    class SkillCaptureDialog:
        KEY = 'SkillCaptureDialog'
        Content = 'SkillCaptureDialog.Content'

    SkillMonitor = 'SkillMonitor'

    SkillTome = 'SkillTome'

    class SkillTrainerWindow:
        KEY = 'SkillTrainerWindow'
        DisplayModeButton = 'SkillTrainerWindow.DisplayModeButton'

    SkillWarmup = 'SkillWarmup'

    class Skillbar:
        KEY = 'Skillbar'
        class Skill1:
            KEY = 'Skillbar.Skill1'
            class Frame:
                KEY = 'Skillbar.Skill1.Frame'
                Frame = 'Skillbar.Skill1.Frame.Frame'
                Number = 'Skillbar.Skill1.Frame.Number'
        class Skill2:
            KEY = 'Skillbar.Skill2'
            class Frame:
                KEY = 'Skillbar.Skill2.Frame'
                Number = 'Skillbar.Skill2.Frame.Number'
        class Skill3:
            KEY = 'Skillbar.Skill3'
            class Frame:
                KEY = 'Skillbar.Skill3.Frame'
                Number = 'Skillbar.Skill3.Frame.Number'
        class Skill4:
            KEY = 'Skillbar.Skill4'
            class Frame:
                KEY = 'Skillbar.Skill4.Frame'
                Frame = 'Skillbar.Skill4.Frame.Frame'
                Number = 'Skillbar.Skill4.Frame.Number'
        class Skill5:
            KEY = 'Skillbar.Skill5'
            class Frame:
                KEY = 'Skillbar.Skill5.Frame'
                Number = 'Skillbar.Skill5.Frame.Number'
        class Skill6:
            KEY = 'Skillbar.Skill6'
            class Frame:
                KEY = 'Skillbar.Skill6.Frame'
                Frame = 'Skillbar.Skill6.Frame.Frame'
                Number = 'Skillbar.Skill6.Frame.Number'
        class Skill7:
            KEY = 'Skillbar.Skill7'
            class Frame:
                KEY = 'Skillbar.Skill7.Frame'
                Number = 'Skillbar.Skill7.Frame.Number'
        class Skill8:
            KEY = 'Skillbar.Skill8'
            class Frame:
                KEY = 'Skillbar.Skill8.Frame'
                Number = 'Skillbar.Skill8.Frame.Number'

    SkillsAndAttributesWindow = 'SkillsAndAttributesWindow'

    SkinColorFrame = 'SkinColorFrame'

    class SortFrame:
        KEY = 'SortFrame'
        class Dropdown:
            KEY = 'SortFrame.Dropdown'
            DropdownWindow = 'SortFrame.Dropdown.DropdownWindow'
        Text = 'SortFrame.Text'

    StatusDropdown = 'StatusDropdown'

    SubmitOfferButton = 'SubmitOfferButton'

    TargetDisplay = 'TargetDisplay'

    Text = 'Text'

    Text2 = 'Text2'

    TextArea = 'TextArea'

    ToggleCape = 'ToggleCape'

    ToggleChatButton = 'ToggleChatButton'

    ToggleCostume = 'ToggleCostume'

    ToggleCostumeHeadpiece = 'ToggleCostumeHeadpiece'

    ToggleHeadpiece = 'ToggleHeadpiece'

    TopText = 'TopText'

    class TradeButton:
        KEY = 'TradeButton'
        Button = 'TradeButton.Button'

    TradePartner = 'TradePartner'

    TradeWindow = 'TradeWindow'

    class UpgradeWindow:
        KEY = 'UpgradeWindow'
        Cancel = 'UpgradeWindow.Cancel'
        Confirm = 'UpgradeWindow.Confirm'

    UpkeepMonitor = 'UpkeepMonitor'

    ViewButton = 'ViewButton'

    Weapon = 'Weapon'

    WeaponBar = 'WeaponBar'

    WeaponSet1 = 'WeaponSet1'

    WeaponSet2 = 'WeaponSet2'

    WeaponSet3 = 'WeaponSet3'

    WeaponSet4 = 'WeaponSet4'

    WeaponSetsButton = 'WeaponSetsButton'

    WhisperReciever = 'WhisperReciever'

    class XunlaiWindow:
        KEY = 'XunlaiWindow'
        DepositAllMaterials = 'XunlaiWindow.DepositAllMaterials'
        DepositFundsButton = 'XunlaiWindow.DepositFundsButton'
        GoldFrame = 'XunlaiWindow.GoldFrame'
        class GoldFrame2:
            KEY = 'XunlaiWindow.GoldFrame2'
            GoldIcon = 'XunlaiWindow.GoldFrame2.GoldIcon'
            GoldValue = 'XunlaiWindow.GoldFrame2.GoldValue'
            PlatinumIcon = 'XunlaiWindow.GoldFrame2.PlatinumIcon'
            PlatinumValue = 'XunlaiWindow.GoldFrame2.PlatinumValue'
        class StorageFrame:
            KEY = 'XunlaiWindow.StorageFrame'
            class Content:
                KEY = 'XunlaiWindow.StorageFrame.Content'
                Item1 = 'XunlaiWindow.StorageFrame.Content.Item1'
                Item10 = 'XunlaiWindow.StorageFrame.Content.Item10'
                Item11 = 'XunlaiWindow.StorageFrame.Content.Item11'
                Item12 = 'XunlaiWindow.StorageFrame.Content.Item12'
                Item13 = 'XunlaiWindow.StorageFrame.Content.Item13'
                Item14 = 'XunlaiWindow.StorageFrame.Content.Item14'
                Item15 = 'XunlaiWindow.StorageFrame.Content.Item15'
                Item16 = 'XunlaiWindow.StorageFrame.Content.Item16'
                Item17 = 'XunlaiWindow.StorageFrame.Content.Item17'
                Item18 = 'XunlaiWindow.StorageFrame.Content.Item18'
                Item19 = 'XunlaiWindow.StorageFrame.Content.Item19'
                Item2 = 'XunlaiWindow.StorageFrame.Content.Item2'
                Item20 = 'XunlaiWindow.StorageFrame.Content.Item20'
                Item21 = 'XunlaiWindow.StorageFrame.Content.Item21'
                Item22 = 'XunlaiWindow.StorageFrame.Content.Item22'
                Item23 = 'XunlaiWindow.StorageFrame.Content.Item23'
                Item24 = 'XunlaiWindow.StorageFrame.Content.Item24'
                Item25 = 'XunlaiWindow.StorageFrame.Content.Item25'
                Item3 = 'XunlaiWindow.StorageFrame.Content.Item3'
                Item4 = 'XunlaiWindow.StorageFrame.Content.Item4'
                Item5 = 'XunlaiWindow.StorageFrame.Content.Item5'
                Item6 = 'XunlaiWindow.StorageFrame.Content.Item6'
                Item7 = 'XunlaiWindow.StorageFrame.Content.Item7'
                Item8 = 'XunlaiWindow.StorageFrame.Content.Item8'
                Item9 = 'XunlaiWindow.StorageFrame.Content.Item9'
            class Content10:
                KEY = 'XunlaiWindow.StorageFrame.Content10'
                Item1 = 'XunlaiWindow.StorageFrame.Content10.Item1'
                Item10 = 'XunlaiWindow.StorageFrame.Content10.Item10'
                Item11 = 'XunlaiWindow.StorageFrame.Content10.Item11'
                Item12 = 'XunlaiWindow.StorageFrame.Content10.Item12'
                Item13 = 'XunlaiWindow.StorageFrame.Content10.Item13'
                Item14 = 'XunlaiWindow.StorageFrame.Content10.Item14'
                Item15 = 'XunlaiWindow.StorageFrame.Content10.Item15'
                Item16 = 'XunlaiWindow.StorageFrame.Content10.Item16'
                Item17 = 'XunlaiWindow.StorageFrame.Content10.Item17'
                Item18 = 'XunlaiWindow.StorageFrame.Content10.Item18'
                Item19 = 'XunlaiWindow.StorageFrame.Content10.Item19'
                Item2 = 'XunlaiWindow.StorageFrame.Content10.Item2'
                Item20 = 'XunlaiWindow.StorageFrame.Content10.Item20'
                Item21 = 'XunlaiWindow.StorageFrame.Content10.Item21'
                Item22 = 'XunlaiWindow.StorageFrame.Content10.Item22'
                Item23 = 'XunlaiWindow.StorageFrame.Content10.Item23'
                Item24 = 'XunlaiWindow.StorageFrame.Content10.Item24'
                Item25 = 'XunlaiWindow.StorageFrame.Content10.Item25'
                Item3 = 'XunlaiWindow.StorageFrame.Content10.Item3'
                Item4 = 'XunlaiWindow.StorageFrame.Content10.Item4'
                Item5 = 'XunlaiWindow.StorageFrame.Content10.Item5'
                Item6 = 'XunlaiWindow.StorageFrame.Content10.Item6'
                Item7 = 'XunlaiWindow.StorageFrame.Content10.Item7'
                Item8 = 'XunlaiWindow.StorageFrame.Content10.Item8'
                Item9 = 'XunlaiWindow.StorageFrame.Content10.Item9'
            class Content11:
                KEY = 'XunlaiWindow.StorageFrame.Content11'
                Item1 = 'XunlaiWindow.StorageFrame.Content11.Item1'
                Item10 = 'XunlaiWindow.StorageFrame.Content11.Item10'
                Item11 = 'XunlaiWindow.StorageFrame.Content11.Item11'
                Item12 = 'XunlaiWindow.StorageFrame.Content11.Item12'
                Item13 = 'XunlaiWindow.StorageFrame.Content11.Item13'
                Item14 = 'XunlaiWindow.StorageFrame.Content11.Item14'
                Item15 = 'XunlaiWindow.StorageFrame.Content11.Item15'
                Item16 = 'XunlaiWindow.StorageFrame.Content11.Item16'
                Item17 = 'XunlaiWindow.StorageFrame.Content11.Item17'
                Item18 = 'XunlaiWindow.StorageFrame.Content11.Item18'
                Item19 = 'XunlaiWindow.StorageFrame.Content11.Item19'
                Item2 = 'XunlaiWindow.StorageFrame.Content11.Item2'
                Item20 = 'XunlaiWindow.StorageFrame.Content11.Item20'
                Item21 = 'XunlaiWindow.StorageFrame.Content11.Item21'
                Item22 = 'XunlaiWindow.StorageFrame.Content11.Item22'
                Item23 = 'XunlaiWindow.StorageFrame.Content11.Item23'
                Item24 = 'XunlaiWindow.StorageFrame.Content11.Item24'
                Item25 = 'XunlaiWindow.StorageFrame.Content11.Item25'
                Item3 = 'XunlaiWindow.StorageFrame.Content11.Item3'
                Item4 = 'XunlaiWindow.StorageFrame.Content11.Item4'
                Item5 = 'XunlaiWindow.StorageFrame.Content11.Item5'
                Item6 = 'XunlaiWindow.StorageFrame.Content11.Item6'
                Item7 = 'XunlaiWindow.StorageFrame.Content11.Item7'
                Item8 = 'XunlaiWindow.StorageFrame.Content11.Item8'
                Item9 = 'XunlaiWindow.StorageFrame.Content11.Item9'
            class Content12:
                KEY = 'XunlaiWindow.StorageFrame.Content12'
                Item1 = 'XunlaiWindow.StorageFrame.Content12.Item1'
                Item10 = 'XunlaiWindow.StorageFrame.Content12.Item10'
                Item11 = 'XunlaiWindow.StorageFrame.Content12.Item11'
                Item12 = 'XunlaiWindow.StorageFrame.Content12.Item12'
                Item13 = 'XunlaiWindow.StorageFrame.Content12.Item13'
                Item14 = 'XunlaiWindow.StorageFrame.Content12.Item14'
                Item15 = 'XunlaiWindow.StorageFrame.Content12.Item15'
                Item16 = 'XunlaiWindow.StorageFrame.Content12.Item16'
                Item17 = 'XunlaiWindow.StorageFrame.Content12.Item17'
                Item18 = 'XunlaiWindow.StorageFrame.Content12.Item18'
                Item19 = 'XunlaiWindow.StorageFrame.Content12.Item19'
                Item2 = 'XunlaiWindow.StorageFrame.Content12.Item2'
                Item20 = 'XunlaiWindow.StorageFrame.Content12.Item20'
                Item21 = 'XunlaiWindow.StorageFrame.Content12.Item21'
                Item22 = 'XunlaiWindow.StorageFrame.Content12.Item22'
                Item23 = 'XunlaiWindow.StorageFrame.Content12.Item23'
                Item24 = 'XunlaiWindow.StorageFrame.Content12.Item24'
                Item25 = 'XunlaiWindow.StorageFrame.Content12.Item25'
                Item3 = 'XunlaiWindow.StorageFrame.Content12.Item3'
                Item4 = 'XunlaiWindow.StorageFrame.Content12.Item4'
                Item5 = 'XunlaiWindow.StorageFrame.Content12.Item5'
                Item6 = 'XunlaiWindow.StorageFrame.Content12.Item6'
                Item7 = 'XunlaiWindow.StorageFrame.Content12.Item7'
                Item8 = 'XunlaiWindow.StorageFrame.Content12.Item8'
                Item9 = 'XunlaiWindow.StorageFrame.Content12.Item9'
            class Content13:
                KEY = 'XunlaiWindow.StorageFrame.Content13'
                Item1 = 'XunlaiWindow.StorageFrame.Content13.Item1'
                Item10 = 'XunlaiWindow.StorageFrame.Content13.Item10'
                Item11 = 'XunlaiWindow.StorageFrame.Content13.Item11'
                Item12 = 'XunlaiWindow.StorageFrame.Content13.Item12'
                Item13 = 'XunlaiWindow.StorageFrame.Content13.Item13'
                Item14 = 'XunlaiWindow.StorageFrame.Content13.Item14'
                Item15 = 'XunlaiWindow.StorageFrame.Content13.Item15'
                Item16 = 'XunlaiWindow.StorageFrame.Content13.Item16'
                Item17 = 'XunlaiWindow.StorageFrame.Content13.Item17'
                Item18 = 'XunlaiWindow.StorageFrame.Content13.Item18'
                Item19 = 'XunlaiWindow.StorageFrame.Content13.Item19'
                Item2 = 'XunlaiWindow.StorageFrame.Content13.Item2'
                Item20 = 'XunlaiWindow.StorageFrame.Content13.Item20'
                Item21 = 'XunlaiWindow.StorageFrame.Content13.Item21'
                Item22 = 'XunlaiWindow.StorageFrame.Content13.Item22'
                Item23 = 'XunlaiWindow.StorageFrame.Content13.Item23'
                Item24 = 'XunlaiWindow.StorageFrame.Content13.Item24'
                Item25 = 'XunlaiWindow.StorageFrame.Content13.Item25'
                Item3 = 'XunlaiWindow.StorageFrame.Content13.Item3'
                Item4 = 'XunlaiWindow.StorageFrame.Content13.Item4'
                Item5 = 'XunlaiWindow.StorageFrame.Content13.Item5'
                Item6 = 'XunlaiWindow.StorageFrame.Content13.Item6'
                Item7 = 'XunlaiWindow.StorageFrame.Content13.Item7'
                Item8 = 'XunlaiWindow.StorageFrame.Content13.Item8'
                Item9 = 'XunlaiWindow.StorageFrame.Content13.Item9'
            class Content14:
                KEY = 'XunlaiWindow.StorageFrame.Content14'
                Item1 = 'XunlaiWindow.StorageFrame.Content14.Item1'
                Item10 = 'XunlaiWindow.StorageFrame.Content14.Item10'
                Item11 = 'XunlaiWindow.StorageFrame.Content14.Item11'
                Item12 = 'XunlaiWindow.StorageFrame.Content14.Item12'
                Item13 = 'XunlaiWindow.StorageFrame.Content14.Item13'
                Item14 = 'XunlaiWindow.StorageFrame.Content14.Item14'
                Item15 = 'XunlaiWindow.StorageFrame.Content14.Item15'
                Item16 = 'XunlaiWindow.StorageFrame.Content14.Item16'
                Item17 = 'XunlaiWindow.StorageFrame.Content14.Item17'
                Item18 = 'XunlaiWindow.StorageFrame.Content14.Item18'
                Item19 = 'XunlaiWindow.StorageFrame.Content14.Item19'
                Item2 = 'XunlaiWindow.StorageFrame.Content14.Item2'
                Item20 = 'XunlaiWindow.StorageFrame.Content14.Item20'
                Item21 = 'XunlaiWindow.StorageFrame.Content14.Item21'
                Item22 = 'XunlaiWindow.StorageFrame.Content14.Item22'
                Item23 = 'XunlaiWindow.StorageFrame.Content14.Item23'
                Item24 = 'XunlaiWindow.StorageFrame.Content14.Item24'
                Item25 = 'XunlaiWindow.StorageFrame.Content14.Item25'
                Item3 = 'XunlaiWindow.StorageFrame.Content14.Item3'
                Item4 = 'XunlaiWindow.StorageFrame.Content14.Item4'
                Item5 = 'XunlaiWindow.StorageFrame.Content14.Item5'
                Item6 = 'XunlaiWindow.StorageFrame.Content14.Item6'
                Item7 = 'XunlaiWindow.StorageFrame.Content14.Item7'
                Item8 = 'XunlaiWindow.StorageFrame.Content14.Item8'
                Item9 = 'XunlaiWindow.StorageFrame.Content14.Item9'
            class Content15:
                KEY = 'XunlaiWindow.StorageFrame.Content15'
                Amber = 'XunlaiWindow.StorageFrame.Content15.Amber'
                Bones = 'XunlaiWindow.StorageFrame.Content15.Bones'
                Charcoal = 'XunlaiWindow.StorageFrame.Content15.Charcoal'
                Chitin = 'XunlaiWindow.StorageFrame.Content15.Chitin'
                Cloth = 'XunlaiWindow.StorageFrame.Content15.Cloth'
                Damask = 'XunlaiWindow.StorageFrame.Content15.Damask'
                DeldrimorSteel = 'XunlaiWindow.StorageFrame.Content15.DeldrimorSteel'
                Diamond = 'XunlaiWindow.StorageFrame.Content15.Diamond'
                Dust = 'XunlaiWindow.StorageFrame.Content15.Dust'
                Ectoplasm = 'XunlaiWindow.StorageFrame.Content15.Ectoplasm'
                ElonianLeather = 'XunlaiWindow.StorageFrame.Content15.ElonianLeather'
                Feather = 'XunlaiWindow.StorageFrame.Content15.Feather'
                Fur = 'XunlaiWindow.StorageFrame.Content15.Fur'
                GlassVial = 'XunlaiWindow.StorageFrame.Content15.GlassVial'
                Granite = 'XunlaiWindow.StorageFrame.Content15.Granite'
                Ink = 'XunlaiWindow.StorageFrame.Content15.Ink'
                Iron = 'XunlaiWindow.StorageFrame.Content15.Iron'
                Jadeite = 'XunlaiWindow.StorageFrame.Content15.Jadeite'
                Leather = 'XunlaiWindow.StorageFrame.Content15.Leather'
                Linen = 'XunlaiWindow.StorageFrame.Content15.Linen'
                MonstrousClaws = 'XunlaiWindow.StorageFrame.Content15.MonstrousClaws'
                MonstrousEye = 'XunlaiWindow.StorageFrame.Content15.MonstrousEye'
                MonstrousFang = 'XunlaiWindow.StorageFrame.Content15.MonstrousFang'
                ObsidianShard = 'XunlaiWindow.StorageFrame.Content15.ObsidianShard'
                Onyx = 'XunlaiWindow.StorageFrame.Content15.Onyx'
                Parchment = 'XunlaiWindow.StorageFrame.Content15.Parchment'
                PlantFibers = 'XunlaiWindow.StorageFrame.Content15.PlantFibers'
                Ruby = 'XunlaiWindow.StorageFrame.Content15.Ruby'
                Sapphire = 'XunlaiWindow.StorageFrame.Content15.Sapphire'
                Scale = 'XunlaiWindow.StorageFrame.Content15.Scale'
                Silk = 'XunlaiWindow.StorageFrame.Content15.Silk'
                Spiritwood = 'XunlaiWindow.StorageFrame.Content15.Spiritwood'
                Steel = 'XunlaiWindow.StorageFrame.Content15.Steel'
                TannedHide = 'XunlaiWindow.StorageFrame.Content15.TannedHide'
                Vellum = 'XunlaiWindow.StorageFrame.Content15.Vellum'
                Wood = 'XunlaiWindow.StorageFrame.Content15.Wood'
            class Content2:
                KEY = 'XunlaiWindow.StorageFrame.Content2'
                Item1 = 'XunlaiWindow.StorageFrame.Content2.Item1'
                Item10 = 'XunlaiWindow.StorageFrame.Content2.Item10'
                Item11 = 'XunlaiWindow.StorageFrame.Content2.Item11'
                Item12 = 'XunlaiWindow.StorageFrame.Content2.Item12'
                Item13 = 'XunlaiWindow.StorageFrame.Content2.Item13'
                Item14 = 'XunlaiWindow.StorageFrame.Content2.Item14'
                Item15 = 'XunlaiWindow.StorageFrame.Content2.Item15'
                Item16 = 'XunlaiWindow.StorageFrame.Content2.Item16'
                Item17 = 'XunlaiWindow.StorageFrame.Content2.Item17'
                Item18 = 'XunlaiWindow.StorageFrame.Content2.Item18'
                Item19 = 'XunlaiWindow.StorageFrame.Content2.Item19'
                Item2 = 'XunlaiWindow.StorageFrame.Content2.Item2'
                Item20 = 'XunlaiWindow.StorageFrame.Content2.Item20'
                Item21 = 'XunlaiWindow.StorageFrame.Content2.Item21'
                Item22 = 'XunlaiWindow.StorageFrame.Content2.Item22'
                Item23 = 'XunlaiWindow.StorageFrame.Content2.Item23'
                Item24 = 'XunlaiWindow.StorageFrame.Content2.Item24'
                Item25 = 'XunlaiWindow.StorageFrame.Content2.Item25'
                Item3 = 'XunlaiWindow.StorageFrame.Content2.Item3'
                Item4 = 'XunlaiWindow.StorageFrame.Content2.Item4'
                Item5 = 'XunlaiWindow.StorageFrame.Content2.Item5'
                Item6 = 'XunlaiWindow.StorageFrame.Content2.Item6'
                Item7 = 'XunlaiWindow.StorageFrame.Content2.Item7'
                Item8 = 'XunlaiWindow.StorageFrame.Content2.Item8'
                Item9 = 'XunlaiWindow.StorageFrame.Content2.Item9'
            class Content3:
                KEY = 'XunlaiWindow.StorageFrame.Content3'
                Item1 = 'XunlaiWindow.StorageFrame.Content3.Item1'
                Item10 = 'XunlaiWindow.StorageFrame.Content3.Item10'
                Item11 = 'XunlaiWindow.StorageFrame.Content3.Item11'
                Item12 = 'XunlaiWindow.StorageFrame.Content3.Item12'
                Item13 = 'XunlaiWindow.StorageFrame.Content3.Item13'
                Item14 = 'XunlaiWindow.StorageFrame.Content3.Item14'
                Item15 = 'XunlaiWindow.StorageFrame.Content3.Item15'
                Item16 = 'XunlaiWindow.StorageFrame.Content3.Item16'
                Item17 = 'XunlaiWindow.StorageFrame.Content3.Item17'
                Item18 = 'XunlaiWindow.StorageFrame.Content3.Item18'
                Item19 = 'XunlaiWindow.StorageFrame.Content3.Item19'
                Item2 = 'XunlaiWindow.StorageFrame.Content3.Item2'
                Item20 = 'XunlaiWindow.StorageFrame.Content3.Item20'
                Item21 = 'XunlaiWindow.StorageFrame.Content3.Item21'
                Item22 = 'XunlaiWindow.StorageFrame.Content3.Item22'
                Item23 = 'XunlaiWindow.StorageFrame.Content3.Item23'
                Item24 = 'XunlaiWindow.StorageFrame.Content3.Item24'
                Item25 = 'XunlaiWindow.StorageFrame.Content3.Item25'
                Item3 = 'XunlaiWindow.StorageFrame.Content3.Item3'
                Item4 = 'XunlaiWindow.StorageFrame.Content3.Item4'
                Item5 = 'XunlaiWindow.StorageFrame.Content3.Item5'
                Item6 = 'XunlaiWindow.StorageFrame.Content3.Item6'
                Item7 = 'XunlaiWindow.StorageFrame.Content3.Item7'
                Item8 = 'XunlaiWindow.StorageFrame.Content3.Item8'
                Item9 = 'XunlaiWindow.StorageFrame.Content3.Item9'
            class Content4:
                KEY = 'XunlaiWindow.StorageFrame.Content4'
                Item1 = 'XunlaiWindow.StorageFrame.Content4.Item1'
                Item10 = 'XunlaiWindow.StorageFrame.Content4.Item10'
                Item11 = 'XunlaiWindow.StorageFrame.Content4.Item11'
                Item12 = 'XunlaiWindow.StorageFrame.Content4.Item12'
                Item13 = 'XunlaiWindow.StorageFrame.Content4.Item13'
                Item14 = 'XunlaiWindow.StorageFrame.Content4.Item14'
                Item15 = 'XunlaiWindow.StorageFrame.Content4.Item15'
                Item16 = 'XunlaiWindow.StorageFrame.Content4.Item16'
                Item17 = 'XunlaiWindow.StorageFrame.Content4.Item17'
                Item18 = 'XunlaiWindow.StorageFrame.Content4.Item18'
                Item19 = 'XunlaiWindow.StorageFrame.Content4.Item19'
                Item2 = 'XunlaiWindow.StorageFrame.Content4.Item2'
                Item20 = 'XunlaiWindow.StorageFrame.Content4.Item20'
                Item21 = 'XunlaiWindow.StorageFrame.Content4.Item21'
                Item22 = 'XunlaiWindow.StorageFrame.Content4.Item22'
                Item23 = 'XunlaiWindow.StorageFrame.Content4.Item23'
                Item24 = 'XunlaiWindow.StorageFrame.Content4.Item24'
                Item25 = 'XunlaiWindow.StorageFrame.Content4.Item25'
                Item3 = 'XunlaiWindow.StorageFrame.Content4.Item3'
                Item4 = 'XunlaiWindow.StorageFrame.Content4.Item4'
                Item5 = 'XunlaiWindow.StorageFrame.Content4.Item5'
                Item6 = 'XunlaiWindow.StorageFrame.Content4.Item6'
                Item7 = 'XunlaiWindow.StorageFrame.Content4.Item7'
                Item8 = 'XunlaiWindow.StorageFrame.Content4.Item8'
                Item9 = 'XunlaiWindow.StorageFrame.Content4.Item9'
            class Content5:
                KEY = 'XunlaiWindow.StorageFrame.Content5'
                Item1 = 'XunlaiWindow.StorageFrame.Content5.Item1'
                Item10 = 'XunlaiWindow.StorageFrame.Content5.Item10'
                Item11 = 'XunlaiWindow.StorageFrame.Content5.Item11'
                Item12 = 'XunlaiWindow.StorageFrame.Content5.Item12'
                Item13 = 'XunlaiWindow.StorageFrame.Content5.Item13'
                Item14 = 'XunlaiWindow.StorageFrame.Content5.Item14'
                Item15 = 'XunlaiWindow.StorageFrame.Content5.Item15'
                Item16 = 'XunlaiWindow.StorageFrame.Content5.Item16'
                Item17 = 'XunlaiWindow.StorageFrame.Content5.Item17'
                Item18 = 'XunlaiWindow.StorageFrame.Content5.Item18'
                Item19 = 'XunlaiWindow.StorageFrame.Content5.Item19'
                Item2 = 'XunlaiWindow.StorageFrame.Content5.Item2'
                Item20 = 'XunlaiWindow.StorageFrame.Content5.Item20'
                Item21 = 'XunlaiWindow.StorageFrame.Content5.Item21'
                Item22 = 'XunlaiWindow.StorageFrame.Content5.Item22'
                Item23 = 'XunlaiWindow.StorageFrame.Content5.Item23'
                Item24 = 'XunlaiWindow.StorageFrame.Content5.Item24'
                Item25 = 'XunlaiWindow.StorageFrame.Content5.Item25'
                Item3 = 'XunlaiWindow.StorageFrame.Content5.Item3'
                Item4 = 'XunlaiWindow.StorageFrame.Content5.Item4'
                Item5 = 'XunlaiWindow.StorageFrame.Content5.Item5'
                Item6 = 'XunlaiWindow.StorageFrame.Content5.Item6'
                Item7 = 'XunlaiWindow.StorageFrame.Content5.Item7'
                Item8 = 'XunlaiWindow.StorageFrame.Content5.Item8'
                Item9 = 'XunlaiWindow.StorageFrame.Content5.Item9'
            class Content6:
                KEY = 'XunlaiWindow.StorageFrame.Content6'
                Item1 = 'XunlaiWindow.StorageFrame.Content6.Item1'
                Item10 = 'XunlaiWindow.StorageFrame.Content6.Item10'
                Item11 = 'XunlaiWindow.StorageFrame.Content6.Item11'
                Item12 = 'XunlaiWindow.StorageFrame.Content6.Item12'
                Item13 = 'XunlaiWindow.StorageFrame.Content6.Item13'
                Item14 = 'XunlaiWindow.StorageFrame.Content6.Item14'
                Item15 = 'XunlaiWindow.StorageFrame.Content6.Item15'
                Item16 = 'XunlaiWindow.StorageFrame.Content6.Item16'
                Item17 = 'XunlaiWindow.StorageFrame.Content6.Item17'
                Item18 = 'XunlaiWindow.StorageFrame.Content6.Item18'
                Item19 = 'XunlaiWindow.StorageFrame.Content6.Item19'
                Item2 = 'XunlaiWindow.StorageFrame.Content6.Item2'
                Item20 = 'XunlaiWindow.StorageFrame.Content6.Item20'
                Item21 = 'XunlaiWindow.StorageFrame.Content6.Item21'
                Item22 = 'XunlaiWindow.StorageFrame.Content6.Item22'
                Item23 = 'XunlaiWindow.StorageFrame.Content6.Item23'
                Item24 = 'XunlaiWindow.StorageFrame.Content6.Item24'
                Item25 = 'XunlaiWindow.StorageFrame.Content6.Item25'
                Item3 = 'XunlaiWindow.StorageFrame.Content6.Item3'
                Item4 = 'XunlaiWindow.StorageFrame.Content6.Item4'
                Item5 = 'XunlaiWindow.StorageFrame.Content6.Item5'
                Item6 = 'XunlaiWindow.StorageFrame.Content6.Item6'
                Item7 = 'XunlaiWindow.StorageFrame.Content6.Item7'
                Item8 = 'XunlaiWindow.StorageFrame.Content6.Item8'
                Item9 = 'XunlaiWindow.StorageFrame.Content6.Item9'
            class Content7:
                KEY = 'XunlaiWindow.StorageFrame.Content7'
                Item1 = 'XunlaiWindow.StorageFrame.Content7.Item1'
                Item10 = 'XunlaiWindow.StorageFrame.Content7.Item10'
                Item11 = 'XunlaiWindow.StorageFrame.Content7.Item11'
                Item12 = 'XunlaiWindow.StorageFrame.Content7.Item12'
                Item13 = 'XunlaiWindow.StorageFrame.Content7.Item13'
                Item14 = 'XunlaiWindow.StorageFrame.Content7.Item14'
                Item15 = 'XunlaiWindow.StorageFrame.Content7.Item15'
                Item16 = 'XunlaiWindow.StorageFrame.Content7.Item16'
                Item17 = 'XunlaiWindow.StorageFrame.Content7.Item17'
                Item18 = 'XunlaiWindow.StorageFrame.Content7.Item18'
                Item19 = 'XunlaiWindow.StorageFrame.Content7.Item19'
                Item2 = 'XunlaiWindow.StorageFrame.Content7.Item2'
                Item20 = 'XunlaiWindow.StorageFrame.Content7.Item20'
                Item21 = 'XunlaiWindow.StorageFrame.Content7.Item21'
                Item22 = 'XunlaiWindow.StorageFrame.Content7.Item22'
                Item23 = 'XunlaiWindow.StorageFrame.Content7.Item23'
                Item24 = 'XunlaiWindow.StorageFrame.Content7.Item24'
                Item25 = 'XunlaiWindow.StorageFrame.Content7.Item25'
                Item3 = 'XunlaiWindow.StorageFrame.Content7.Item3'
                Item4 = 'XunlaiWindow.StorageFrame.Content7.Item4'
                Item5 = 'XunlaiWindow.StorageFrame.Content7.Item5'
                Item6 = 'XunlaiWindow.StorageFrame.Content7.Item6'
                Item7 = 'XunlaiWindow.StorageFrame.Content7.Item7'
                Item8 = 'XunlaiWindow.StorageFrame.Content7.Item8'
                Item9 = 'XunlaiWindow.StorageFrame.Content7.Item9'
            class Content8:
                KEY = 'XunlaiWindow.StorageFrame.Content8'
                Item1 = 'XunlaiWindow.StorageFrame.Content8.Item1'
                Item10 = 'XunlaiWindow.StorageFrame.Content8.Item10'
                Item11 = 'XunlaiWindow.StorageFrame.Content8.Item11'
                Item12 = 'XunlaiWindow.StorageFrame.Content8.Item12'
                Item13 = 'XunlaiWindow.StorageFrame.Content8.Item13'
                Item14 = 'XunlaiWindow.StorageFrame.Content8.Item14'
                Item15 = 'XunlaiWindow.StorageFrame.Content8.Item15'
                Item16 = 'XunlaiWindow.StorageFrame.Content8.Item16'
                Item17 = 'XunlaiWindow.StorageFrame.Content8.Item17'
                Item18 = 'XunlaiWindow.StorageFrame.Content8.Item18'
                Item19 = 'XunlaiWindow.StorageFrame.Content8.Item19'
                Item2 = 'XunlaiWindow.StorageFrame.Content8.Item2'
                Item20 = 'XunlaiWindow.StorageFrame.Content8.Item20'
                Item21 = 'XunlaiWindow.StorageFrame.Content8.Item21'
                Item22 = 'XunlaiWindow.StorageFrame.Content8.Item22'
                Item23 = 'XunlaiWindow.StorageFrame.Content8.Item23'
                Item24 = 'XunlaiWindow.StorageFrame.Content8.Item24'
                Item25 = 'XunlaiWindow.StorageFrame.Content8.Item25'
                Item3 = 'XunlaiWindow.StorageFrame.Content8.Item3'
                Item4 = 'XunlaiWindow.StorageFrame.Content8.Item4'
                Item5 = 'XunlaiWindow.StorageFrame.Content8.Item5'
                Item6 = 'XunlaiWindow.StorageFrame.Content8.Item6'
                Item7 = 'XunlaiWindow.StorageFrame.Content8.Item7'
                Item8 = 'XunlaiWindow.StorageFrame.Content8.Item8'
                Item9 = 'XunlaiWindow.StorageFrame.Content8.Item9'
            class Content9:
                KEY = 'XunlaiWindow.StorageFrame.Content9'
                Item1 = 'XunlaiWindow.StorageFrame.Content9.Item1'
                Item10 = 'XunlaiWindow.StorageFrame.Content9.Item10'
                Item11 = 'XunlaiWindow.StorageFrame.Content9.Item11'
                Item12 = 'XunlaiWindow.StorageFrame.Content9.Item12'
                Item13 = 'XunlaiWindow.StorageFrame.Content9.Item13'
                Item14 = 'XunlaiWindow.StorageFrame.Content9.Item14'
                Item15 = 'XunlaiWindow.StorageFrame.Content9.Item15'
                Item16 = 'XunlaiWindow.StorageFrame.Content9.Item16'
                Item17 = 'XunlaiWindow.StorageFrame.Content9.Item17'
                Item18 = 'XunlaiWindow.StorageFrame.Content9.Item18'
                Item19 = 'XunlaiWindow.StorageFrame.Content9.Item19'
                Item2 = 'XunlaiWindow.StorageFrame.Content9.Item2'
                Item20 = 'XunlaiWindow.StorageFrame.Content9.Item20'
                Item21 = 'XunlaiWindow.StorageFrame.Content9.Item21'
                Item22 = 'XunlaiWindow.StorageFrame.Content9.Item22'
                Item23 = 'XunlaiWindow.StorageFrame.Content9.Item23'
                Item24 = 'XunlaiWindow.StorageFrame.Content9.Item24'
                Item25 = 'XunlaiWindow.StorageFrame.Content9.Item25'
                Item3 = 'XunlaiWindow.StorageFrame.Content9.Item3'
                Item4 = 'XunlaiWindow.StorageFrame.Content9.Item4'
                Item5 = 'XunlaiWindow.StorageFrame.Content9.Item5'
                Item6 = 'XunlaiWindow.StorageFrame.Content9.Item6'
                Item7 = 'XunlaiWindow.StorageFrame.Content9.Item7'
                Item8 = 'XunlaiWindow.StorageFrame.Content9.Item8'
                Item9 = 'XunlaiWindow.StorageFrame.Content9.Item9'
            Tab1 = 'XunlaiWindow.StorageFrame.Tab1'
            Tab10 = 'XunlaiWindow.StorageFrame.Tab10'
            Tab11 = 'XunlaiWindow.StorageFrame.Tab11'
            Tab12 = 'XunlaiWindow.StorageFrame.Tab12'
            Tab13 = 'XunlaiWindow.StorageFrame.Tab13'
            Tab14As = 'XunlaiWindow.StorageFrame.Tab14As'
            Tab2 = 'XunlaiWindow.StorageFrame.Tab2'
            Tab3 = 'XunlaiWindow.StorageFrame.Tab3'
            Tab4 = 'XunlaiWindow.StorageFrame.Tab4'
            Tab5 = 'XunlaiWindow.StorageFrame.Tab5'
            Tab6 = 'XunlaiWindow.StorageFrame.Tab6'
            Tab7 = 'XunlaiWindow.StorageFrame.Tab7'
            Tab8 = 'XunlaiWindow.StorageFrame.Tab8'
            Tab9 = 'XunlaiWindow.StorageFrame.Tab9'
            TabMaterialStorage = 'XunlaiWindow.StorageFrame.TabMaterialStorage'
        WithdrawFundsButton = 'XunlaiWindow.WithdrawFundsButton'

    YourOfferLabel = 'YourOfferLabel'

