from __future__ import annotations

from typing import Callable

from Py4GWCoreLib import get_texture_for_model
from Py4GWCoreLib.BottingTree import BottingTree
from Py4GWCoreLib.enums_src.GameData_enums import Range
from Py4GWCoreLib.enums_src.Model_enums import ModelID
from Py4GWCoreLib.native_src.internals.types import Vec2f
from Py4GWCoreLib.py4gwcorelib_src.BehaviorTree import BehaviorTree
from Sources.ApoSource.ApoBottingLib import wrappers as BT


BOT_NAME = "Topaz_Crests Farmer"
MODULE_NAME = "Topaz Crest Farm (Nicholas the Traveler)"
MODEL_ID_TO_FARM = ModelID.Topaz_Crest

OUTPOST_TO_TRAVEL = 118
EXPLORABLE_TO_TRAVEL = 110

COORD_TO_EXIT_MAP = Vec2f(17300.0, 6600.0)
KILLING_PATH = [
    Vec2f(-5421,3557),
    Vec2f(-4438,5558),
    Vec2f(-1525,6435),
    Vec2f(897,7734),
    Vec2f(3740,6540),
    Vec2f(7039,5698),
    Vec2f(8794,6997),
    Vec2f(10057,8506),
    Vec2f(5846,8681),
    Vec2f(6267,11138),
    Vec2f(7320,13384),
    Vec2f(9812,13209),
    Vec2f(12023,12121),
    Vec2f(14374,9313),
    Vec2f(14655,7523),
    Vec2f(12690,8365),
]

initialized = False
botting_tree: BottingTree | None = None


def ensure_botting_tree() -> BottingTree:
    global botting_tree


    if botting_tree is None:


        botting_tree = BottingTree.Create(
            MODULE_NAME,
            main_routine=get_execution_steps(),
            routine_name="MultiAccountSequence",
            repeat=True,
            multi_account=True,
            isolation_enabled=False,
            configure_fn=lambda tree: tree.Config.ConfigureUpkeep(
                looting_enabled=True,
                resurrection_scroll=True,
                auto_inventory_handler_enabled=False,
                activate_widget_list=(
                    "LootManager",
                ),
                heroai_state_logging=False,
            ),
        )

    return botting_tree


def InitializeBot() -> BehaviorTree:
    tree = ensure_botting_tree()

    return BT.Sequence(
        name="Initialize Bot",
        hard_mode=False,
        children=[
            tree.Config.Aggressive(
                multi_account=True,
                auto_loot=True,
                resurrection_scroll=False,
            ),
        ],
    )


def TravelToFarm() -> BehaviorTree:
    return BT.Sequence(
        name="Travel To Farm",
        map_id_or_name=OUTPOST_TO_TRAVEL,
        hard_mode=False,
        children=[
            BT.WaitUntilOnOutpost(timeout_ms=30_000),

            BT.CreateParty(
                multibox_invite=True,
                timeout_ms=30_000,
                log=True,
            ),
        ],
    )

def Exit() -> BehaviorTree:
    return BT.Sequence(
        name="Farm Topaz Crests",
        children=[
            BT.MoveAndExitMap(
                Vec2f(17517, 6829),
                target_map_id=EXPLORABLE_TO_TRAVEL,
                log=True,
            ),
            BT.WaitUntilOnExplorable(timeout_ms=30_000),
            ]
    )

def FarmTopazCrests() -> BehaviorTree:
    return BT.Sequence(
        name="Farm Topaz Crests",
        children=[
            
            BT.VanquishNode(
                name="Clear Topaz Crest Path",
                steps=KILLING_PATH,
                pause_on_combat=True,
                clear_area_radius=Range.SafeCompass.value,
                log=True
            ),
            BT.Resign(
                wait_for_map_load=True,
                target_map_id=OUTPOST_TO_TRAVEL,
                multi_account=False,
                timeout_ms=30_000,
                log=True,
            ),
            BT.Wait(1_000),
            BT.WaitUntilOnOutpost(timeout_ms=30_000),
        ],
    )


def get_execution_steps() -> list[tuple[str, Callable[[], BehaviorTree]]]:
    return [
        ("Initialize Bot", InitializeBot),
        ("Travel To Farm", TravelToFarm),
        ("Exit", Exit),
        ("Farm Topaz Crests", FarmTopazCrests),
    ]


def main() -> None:
    global initialized

    if not initialized:
        ensure_botting_tree()
        initialized = True

    tree = ensure_botting_tree()
    tree.tick()

    texture = get_texture_for_model(model_id=MODEL_ID_TO_FARM)
    tree.UI.draw_window(icon_path=texture)


if __name__ == "__main__":
    main()
