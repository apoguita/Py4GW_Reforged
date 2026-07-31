from time import sleep
import PyUIManager
from Sources.frenkeyLib.LootEx import enum
from Py4GWCoreLib import UIManager
from Py4GWCoreLib.Py4GWcorelib import ConsoleLog
from Py4GWCoreLib.FrameTree import Frame, FrameId


class UIManagerExtensions:
    @staticmethod
    def IsElementVisible(frame_id: int) -> bool:
        """
        Check if a specific frame is open in the UI.

        Args:
            frame_id (int): The ID of the frame to check.

        Returns:
            bool: True if the frame is open, False otherwise.
        """
        return isinstance(frame_id, int) and frame_id > 0

    @staticmethod
    def IsUpgradeWindowOpen() -> bool:
        upgrade_window_frame_id = Frame(FrameId.UpgradeWindow)
        return upgrade_window_frame_id.exists
    
    @staticmethod
    def IsMerchantWindowOpen() -> bool:
        merchant_window_frame_id = Frame(FrameId.Merchant)
        # merchant_window_frame_inner_id = Frame.from_hash(3613855137, [ # 0])
        # merchant_window_funds_id = Frame(FrameId.GoldText)
        # merchant_window_buy_button_id = Frame(FrameId.MerchantBuyButton)

        return merchant_window_frame_id.exists
    
    @staticmethod
    
    @staticmethod
    def IsCollectorOpen() -> bool:        
        merchant_buy_button = 1532320307
        crafter_craft_button = 1517397806
        exchange_collector_button = Frame(FrameId.Merchant.C0.C0.Exchange)
        sell_tab = Frame(FrameId.Merchant.C0.QuoteField)

        return exchange_collector_button.exists and not sell_tab.exists
    
    @staticmethod
    def IsSkillTrainerOpen() -> bool:     
        display_type_button_id = Frame(FrameId.SkillTrainerWindow.DisplayModeButton)
        sell_tab = Frame(FrameId.Merchant.C0.QuoteField)

        return display_type_button_id.exists and not sell_tab.exists
    
    @staticmethod
    def IsCrafterOpen() -> bool:
        crafter_craft_button_id = Frame(FrameId.CraftButton)

        return crafter_craft_button_id.exists

    @staticmethod
    def IsConfirmMaterialsWindowOpen() -> bool:
        return Frame(FrameId.ScreenFrame.C6.LesserSalvageWindow).exists

    @staticmethod
    def ConfirmLesserSalvage():
        salvage_lower_kit_yes_button_id = Frame.from_hash(140452905, [ 6, 110, 6])
        salvage_lower_kit_yes_button_id.click()

    @staticmethod
    def ConfirmModMaterialSalvage():
        salvage_with_mods_yes_button_id = Frame(FrameId.SalvageWindow.OptionsWindowConfirmMaterialsWindow.Confirm)
        salvage_with_mods_yes_button_id.click()
        salvage_with_mods_yes_button_id.mouse_action(8, 0, 0) 
        
    @staticmethod
    def ConfirmModMaterialSalvageVisible():
        salvage_with_mods_yes_button_id = Frame(FrameId.SalvageWindow.OptionsWindowConfirmMaterialsWindow.Confirm)
        return salvage_with_mods_yes_button_id.exists  
        
    @staticmethod
    def CancelLesserSalvage():
        salvage_lower_kit_no_button_id = Frame.from_hash(140452905, [ 6, 100, 4])
        salvage_lower_kit_no_button_id.click()
    
    @staticmethod
    def IsSalvageWindowOpen() -> bool:
        salvage_window_frame_id = Frame(FrameId.SalvageWindow)
        # salvage_window_salvage_button_id = Frame(FrameId.SalvageWindow.Button)
        # salvage_window_cancel_button_id = Frame(FrameId.SalvageWindow.CancelButton)

        return salvage_window_frame_id.exists

    @staticmethod
    def Test():
        salvage_window_frame_id = Frame(FrameId.SalvageWindow)
        
        for i in range(1):
            for j in range(100):
                id = Frame(FrameId.SalvageWindow).find_child(5, i, j)
                if id is None:
                    continue
                
                if id.exists:
                    id.refresh()
                    ConsoleLog("LootEx", f"Found visible element with ID: {id} at ({i}, {j}) | template_type: {id.template_type}")
                    # Frame.from_id(id).click()
                elif id.exists:
                    ConsoleLog("LootEx", f"Element with ID: {id} at ({i}, {j}) is not visible or does not exist.")
        
    @staticmethod
    def SelectSalvageOption(option: enum.SalvageOption) -> bool:
        """
        Select a salvage option in the salvage window.

        Args:
            option (enum.SalvageOption): The salvage option to select.

        Returns:
            bool: True if the option was successfully selected, False otherwise.
        """
        options = UIManagerExtensions.GetSalvageOptions()

        if option in options:
            ConsoleLog("LootEx", f"Selecting salvage option: {option.name}")           
                                
            # Frame.from_id(options[option]).click()
            options[option].mouse_action(8, 0, 0)
            
            return True

        return False
    
    @staticmethod
    def SelectSalvageOptionAndSalvage(option: enum.SalvageOption) -> bool:
        """
        Select a salvage option in the salvage window.

        Args:
            option (enum.SalvageOption): The salvage option to select.

        Returns:
            bool: True if the option was successfully selected, False otherwise.
        """
        options = UIManagerExtensions.GetSalvageOptions()

        if option in options:
            ConsoleLog("LootEx", f"Selecting salvage option: {option.name}")           
                                
            # Frame.from_id(options[option]).click()
            options[option].mouse_action(8, 0, 0)              
            UIManagerExtensions.ConfirmSalvageOption()
            
            return True
        else:
            ConsoleLog("LootEx", f"Salvage option {option.name} not available.")
            UIManagerExtensions.CancelSalvageOption()

        return False

    @staticmethod
    def ConfirmSalvageOption() -> bool:
        salvage_window_salvage_button_id = Frame(FrameId.SalvageWindow.Button)
        visible = salvage_window_salvage_button_id.exists

        if not visible:
            return False

        ConsoleLog("LootEx", f"Confirm salvage.")   
        salvage_window_salvage_button_id.click()
        return True
    
    @staticmethod
    def CancelSalvageOption() -> bool:
        salvage_window_cancel_button_id = Frame(FrameId.SalvageWindow.CancelButton)
        visible = salvage_window_cancel_button_id.exists

        if not visible:
            return False

        ConsoleLog("LootEx", f"Cancel salvage.")   
        salvage_window_cancel_button_id.click()
        return True

    @staticmethod
    def GetSalvageOptions() -> dict[enum.SalvageOption, int]:
        salvage_window_mod_one_id = Frame(FrameId.SalvageWindow.Options.Option1)
        salvage_window_mod_two_id = Frame(FrameId.SalvageWindow.Options.Option2)
        salvage_window_mod_three_id = Frame(FrameId.SalvageWindow.Options.Option3)
        salvage_window_materials_id = Frame(FrameId.SalvageWindow.Options.Option4)

        options: dict[enum.SalvageOption, int] = {}

        if salvage_window_mod_one_id.exists:
            options[enum.SalvageOption.Prefix] = salvage_window_mod_one_id

        if salvage_window_mod_two_id.exists:
            options[enum.SalvageOption.Suffix] = salvage_window_mod_two_id

        if salvage_window_mod_three_id.exists:
            options[enum.SalvageOption.Inherent] = salvage_window_mod_three_id

        if salvage_window_materials_id.exists:
            options[enum.SalvageOption.RareCraftingMaterials] = salvage_window_materials_id
            options[enum.SalvageOption.CraftingMaterials] = salvage_window_materials_id

        return options
