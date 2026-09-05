import PyImGui

from Py4GWCoreLib import *
from Py4GWCoreLib import ImGui, Color
from Py4GWCoreLib import Map
from Py4GWCoreLib import Routines
from Py4GWCoreLib import ThrottledTimer

MODULE_NAME = "Pop mini on map load"
MODULE_ICON = "Assets/Textures/Module_Icons/Pet Helper.png"

module_name = "Pop mini on map load"


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
    PyImGui.text("Automatically pops a miniature pet from your inventory as you load a new map.")

    PyImGui.spacing()
    PyImGui.separator()
    PyImGui.spacing()

    # Features
    PyImGui.text_colored("Features:", title_color.to_tuple_normalized())
    PyImGui.bullet_text("Mini pets!")

    PyImGui.spacing()
    PyImGui.separator()
    PyImGui.spacing()

    # Credits
    PyImGui.text_colored("Credits:", title_color.to_tuple_normalized())
    PyImGui.bullet_text("Developed by Alice")

    PyImGui.end_tooltip()


mini_game_throttle_timer = ThrottledTimer(100)
mini_load_timer = ThrottledTimer(2500)


def doAction():
    items = ItemArray.GetItemArray([Bag.Backpack, Bag.Belt_Pouch, Bag.Bag_1, Bag.Bag_2])

    matching_items = ItemArray.Filter.ByCondition(items, lambda item_id: Item.GetModelID(item_id) in [
        ModelID.Aatxe_Mini, ModelID.Abomination_Mini, ModelID.Abyssal_Mini, ModelID.Asura_Mini,
        ModelID.Black_Beast_Of_Aaaaarrrrrrggghhh_Mini, ModelID.Black_Moa_Chick_Mini, ModelID.Bone_Dragon_Mini,
        ModelID.Brown_Rabbit_Mini, ModelID.Burning_Titan_Mini, ModelID.Candysmith_Marley_Mini, ModelID.Cave_Spider_Mini,
        ModelID.Celestial_Dog_Mini, ModelID.Celestial_Dragon_Mini, ModelID.Celestial_Horse_Mini,
        ModelID.Celestial_Monkey_Mini, ModelID.Celestial_Ox_Mini, ModelID.Celestial_Pig_Mini,
        ModelID.Celestial_Rabbit_Mini, ModelID.Celestial_Rat_Mini, ModelID.Celestial_Rooster_Mini,
        ModelID.Celestial_Sheep_Mini, ModelID.Celestial_Snake_Mini, ModelID.Celestial_Tiger_Mini,
        ModelID.Ceratadon_Mini, ModelID.Charr_Shaman_Mini, ModelID.Cloudtouched_Simian_Mini,
        ModelID.Cobalt_Scabara_Mini, ModelID.Confessor_Dorian_Mini, ModelID.Confessor_Isaiah_Mini,
        ModelID.Dagnar_Stonepate_Mini, ModelID.Desert_Griffon_Mini, ModelID.Destroyer_Of_Flesh_Mini, ModelID.Dhuum_Mini,
        ModelID.Dredge_Brute_Mini, ModelID.Ecclesiate_Xun_Rao_Mini, ModelID.Elf_Mini, ModelID.Evennia_Mini,
        ModelID.Eye_Of_Janthir_Mini, ModelID.Fire_Drake_Mini, ModelID.Fire_Imp_Mini, ModelID.Flame_Djinn_Mini,
        ModelID.Flowstone_Elemental_Mini, ModelID.Forest_Minotaur_Mini, ModelID.Freezie_Mini,
        ModelID.Fungal_Wallow_Mini, ModelID.Ghostly_Priest_Mini, ModelID.Grawl_Mini, ModelID.Gray_Giant_Mini,
        ModelID.Guild_Lord_Mini, ModelID.Gwen_Doll_Mini, ModelID.Gwen_Mini, ModelID.Harpy_Ranger_Mini,
        ModelID.Heket_Warrior_Mini,
        ModelID.High_Priest_Zhang_Mini, ModelID.Hydra_Mini, ModelID.Irukandji_Mini, ModelID.Jade_Armor_Mini,
        ModelID.Jora_Mini, ModelID.Juggernaut_Mini, ModelID.Jungle_Troll_Mini, ModelID.King_Adelbern_Mini,
        ModelID.Kirin_Mini, ModelID.Koss_Mini, ModelID.Krait_Neoss_Mini, ModelID.Kuunavang_Mini, ModelID.Kveldulf_Mini,
        ModelID.Lich_Mini, ModelID.Livia_Mini, ModelID.Mad_King_Thorn_Mini, ModelID.Mad_Kings_Guard_Mini,
        ModelID.Mallyx_Mini, ModelID.Mandragor_Imp_Mini, ModelID.Minister_Reiko_Mini, ModelID.Mox_Mini,
        ModelID.Mursaat_Mini, ModelID.Naga_Raincaller_Mini, ModelID.Necrid_Horseman_Mini, ModelID.Nian_Mini,
        ModelID.Nornbear_Mini, ModelID.Oni_Mini, ModelID.Oola_Mini, ModelID.Ooze_Mini, ModelID.Ophil_Nahualli_Mini,
        ModelID.Palawa_Joko_Mini, ModelID.Panda_Mini, ModelID.Pig_Mini, ModelID.Polar_Bear_Mini,
        ModelID.Prince_Rurik_Mini, ModelID.Princess_Salma_Mini, ModelID.Quetzal_Sly_Mini, ModelID.Raptor_Mini,
        ModelID.Rift_Warden_Mini, ModelID.Roaring_Ether_Mini, ModelID.Scourge_Manta_Mini, ModelID.Seer_Mini,
        ModelID.Shard_Wolf_Mini, ModelID.Shiro_Mini, ModelID.Shiroken_Assassin_Mini, ModelID.Siege_Turtle_Mini,
        ModelID.Smite_Crawler_Mini, ModelID.Temple_Guardian_Mini, ModelID.Terrorweb_Dryder_Mini,
        ModelID.Thorn_Wolf_Mini, ModelID.Varesh_Ossa_Mini, ModelID.Ventari_Mini, ModelID.Vizu_Mini,
        ModelID.Water_Djinn_Mini, ModelID.Whiptail_Devourer_Mini, ModelID.White_Rabbit_Mini, ModelID.Wind_Rider_Mini,
        ModelID.Word_Of_Madness_Mini, ModelID.World_Famous_Racing_Beetle_Mini, ModelID.Yakkington_Mini,
        ModelID.Zhed_Shadowhoof_Mini, ModelID.Zhu_Hanuku_Mini,
        # Nornbear in pre?
        30617
    ])
    if matching_items:
        print(
            f"Poppin a mini! item={matching_items[0]}, model={Item.GetModelID(matching_items[0])}, name={Item.GetName(matching_items[0])}")
        # ActionQueueManager().AddAction("ACTION", "UseItem", matching_items[0])
        GLOBAL_CACHE.Inventory.UseItem(matching_items[0])
        return  # Exit after using one pcon
    else:
        print(f"No mini to pop")
    pass


def main():
    if not mini_game_throttle_timer.IsExpired():
        return

    mini_game_throttle_timer.Reset()

    is_map_valid = Routines.Checks.Map.MapValid()
    is_explorable = Map.IsExplorable() or Map.IsOutpost()

    if not is_map_valid:
        widget_config.title_applied = False
        mini_load_timer.Reset()
        return

    if not is_explorable:
        widget_config.title_applied = False
        mini_load_timer.Reset()
        return

    map_name = Map.GetMapName()

    if not widget_config.title_applied:
        if not mini_load_timer.IsExpired():
            doAction()
            widget_config.title_applied = True
        else:
            if not mini_load_timer.IsStopped():
                print("New Map - force reset")
                mini_load_timer.Reset()
            else:
                print("New Map - not yet ready")


if __name__ == "__main__":
    main()
