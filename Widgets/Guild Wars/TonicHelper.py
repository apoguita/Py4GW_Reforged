import PyImGui

from Py4GWCoreLib import *
from Py4GWCoreLib import ImGui, Color
from Py4GWCoreLib import Map
from Py4GWCoreLib import Routines
from Py4GWCoreLib import ThrottledTimer

MODULE_NAME = "Eat tonic on map load"
MODULE_ICON = "Assets/Textures/Module_Icons/Pycons.png"

module_name = "Eat tonic on map load"


class config:
    def __init__(self):
        self.title_applied = False


widget_config = config()


def tooltip():
    PyImGui.begin_tooltip()

    # Title
    title_color = Color(255, 200, 100, 255)
    ImGui.push_font("Regular", 20)
    PyImGui.text_colored(MODULE_NAME, title_color.to_tuple_normalized())
    ImGui.pop_font()

    PyImGui.spacing()
    PyImGui.separator()
    PyImGui.spacing()

    # Description
    PyImGui.text("Automatically eats an everlasting tonic as you load the map you enter.")
    
    PyImGui.spacing()
    PyImGui.separator()
    PyImGui.spacing()
    
    # Features
    PyImGui.text_colored("Features:", title_color.to_tuple_normalized())
    PyImGui.bullet_text("Tonics!")
    
    PyImGui.spacing()
    PyImGui.separator()
    PyImGui.spacing()
    
    # Credits
    PyImGui.text_colored("Credits:", title_color.to_tuple_normalized())
    PyImGui.bullet_text("Developed by Alice")
    
    PyImGui.end_tooltip()


game_throttle_timer = ThrottledTimer(100)
load_timer = ThrottledTimer(2500)


def doAction():
    
    items = ItemArray.GetItemArray([Bag.Backpack, Bag.Belt_Pouch, Bag.Bag_1, Bag.Bag_2])

    matching_items = ItemArray.Filter.ByCondition(items, lambda item_id: Item.GetModelID(item_id) in [
          ModelID.El_Abominable_Tonic,
          ModelID.El_Abyssal_Tonic,
          ModelID.El_Acolyte_Jin_Tonic,
          ModelID.El_Acolyte_Sousuke_Tonic,
          ModelID.El_Anton_Tonic,
          ModelID.El_Automatonic_Tonic,
          ModelID.El_Avatar_Of_Balthazar_Tonic,
          ModelID.El_Balthazars_Champion_Tonic,
          ModelID.El_Boreal_Tonic,
          ModelID.El_Cerebral_Tonic,
          ModelID.El_Cottontail_Tonic,
          ModelID.El_Destroyer_Tonic,
          ModelID.El_Dunkoro_Tonic,
          ModelID.El_Flame_Sentinel_Tonic,
          ModelID.El_Gelatinous_Tonic,
          ModelID.El_Ghostly_Hero_Tonic,
          ModelID.El_Ghostly_Priest_Tonic,
          ModelID.El_Goren_Tonic,
          ModelID.El_Guild_Lord_Tonic,
          ModelID.El_Gwen_Tonic,
          ModelID.El_Hayda_Tonic,
          ModelID.El_Henchman_Tonic,
          ModelID.El_Jora_Tonic,
          ModelID.El_Kahmu_Tonic,
          ModelID.El_Keiran_Thackeray_Tonic,
          ModelID.El_Koss_Tonic,
          ModelID.El_Kuunavang_Tonic,
          ModelID.El_Livia_Tonic,
          ModelID.El_Macabre_Tonic,
          ModelID.El_Magrid_The_Sly_Tonic,
          ModelID.El_Margonite_Tonic,
          ModelID.El_Master_Of_Whispers_Tonic,
          ModelID.El_Melonni_Tonic,
          ModelID.El_Miku_Tonic,
          ModelID.El_Mischievious_Tonic,
          ModelID.El_Morgahn_Tonic,
          ModelID.El_Mox_Tonic,
          ModelID.El_Norgu_Tonic,
          ModelID.El_Ogden_Stonehealer_Tonic,
          ModelID.El_Olias_Tonic,
          ModelID.El_Phantasmal_Tonic,
          ModelID.El_Priest_Of_Balthazar_Tonic,
          ModelID.El_Prince_Rurik_Tonic,
          ModelID.El_Pyre_Fiercehot_Tonic,
          ModelID.El_Queen_Salma_Tonic,
          ModelID.El_Razah_Tonic,
          ModelID.El_Reindeer_Tonic,
          ModelID.El_Searing_Tonic,
          ModelID.El_Shiro_Tonic,
          ModelID.El_Sinister_Automatonic_Tonic,
          ModelID.El_Skeletonic_Tonic,
          ModelID.El_Slightly_Mad_King_Tonic,
          ModelID.El_Tahlkora_Tonic,
          ModelID.El_Transmogrifier_Tonic,
          ModelID.El_Trapdoor_Tonic,
          ModelID.El_Unseen_Tonic,
          ModelID.El_Vekk_Tonic,
          ModelID.El_Xandra_Tonic,
          ModelID.El_Yuletide_Tonic,
          ModelID.El_Zenmai_Tonic,
          ModelID.El_Zhed_Shadowhoof_Tonic,
    ])
    if matching_items:
        print(f"Eating a tonic! item={matching_items[0]}, model={Item.GetModelID(matching_items[0])}, name={Item.GetName(matching_items[0])}")
        # ActionQueueManager().AddAction("ACTION", "UseItem", matching_items[0])
        GLOBAL_CACHE.Inventory.UseItem(matching_items[0])
        return  # Exit after using one pcon
    pass


def main():
    
    if not game_throttle_timer.IsExpired():
        return
    
    game_throttle_timer.Reset()
    
    is_map_valid = Routines.Checks.Map.MapValid()
    is_explorable = Map.IsExplorable() or Map.IsOutpost()
    
    if not is_map_valid:
        widget_config.title_applied = False
        load_timer.Reset()
        return
    
    if not is_explorable:
        widget_config.title_applied = False
        load_timer.Reset()
        return
    
    map_name = Map.GetMapName()

    if not widget_config.title_applied:
        if not load_timer.IsExpired():
            doAction()
            widget_config.title_applied = True
        else:
            if not load_timer.IsStopped():
                print("New Map - force reset")
                load_timer.Reset()
            else:
                print("New Map - not yet ready")


if __name__ == "__main__":
    main()

