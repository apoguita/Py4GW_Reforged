# ============================================================================
# Nightfall Leveler - Behavior Tree Conversion
# ============================================================================
# BT re-implementation of the classic FSM-based Nightfall leveler. Each
# original [H] header step becomes a named planner step in BottingTree.
# Party wipe handling is provided by BottingTree party-wipe recovery service
# (equivalent to the original OnPartyDefeated FSM hook.)
# ============================================================================
from __future__ import annotations

import os
from collections.abc import Callable

import PySystem
from Py4GWCoreLib import (
    Agent,
    ConsoleLog,
    GLOBAL_CACHE,
    Inventory,
    Item,
    Map,
    Player,
    Range,
)
from Py4GWCoreLib.BottingTree import BottingTree
from Py4GWCoreLib.enums_src.GameData_enums import EXPERIENCE_PROGRESSION
from Py4GWCoreLib.enums_src.Item_enums import Bags
from Py4GWCoreLib.enums_src.Model_enums import ModelID
from Py4GWCoreLib.native_src.internals.types import Vec2f
from Py4GWCoreLib.py4gwcorelib_src.BehaviorTree import BehaviorTree
from Py4GWCoreLib.routines_src.BehaviourTrees import BT as RoutinesBT
from Py4GWCoreLib.routines_src.behaviourtrees_src.constants.lists import (
    CONSUMABLE_UPKEEPS,
)
from Sources.ApoSource.ApoBottingLib import wrappers as BT

MODULE_NAME = "Nightfall Leveler BT"
MODULE_ICON = "Assets\\Textures\\Module_Icons\\Leveler - Nightfall.png"
ICON_PATH = os.path.join(
    PySystem.Console.get_projects_path(),
    "Assets",
    "Textures",
    "Module_Icons",
    "Leveler - Nightfall.png",
)
MODULE_CATEGORY = "Bots"
MODULE_TAGS = ["automation", "leveling", "nightfall", "campaign", "botting", "bt"]
MODULE_DESCRIPTION = (
    "Behavior Tree based Nightfall campaign leveler. Levels a fresh character "
    "from 1 to 20, unlocks campaign content, EotN pool, Factions routes and "
    "Olias. Supports all Nightfall-primary professions with per-profession "
    "skillbars, armor and weapon crafting.\n\n"
    "• BT-based automation using the BottingTree planner stack\n"
    "• Full Nightfall storyline up to and including Consulate Docks\n"
    "• Crafted armor/weapons for every profession (incl. double-mats crafting)\n"
    "• Profession unlock routes: GTOB trainers, mercenary heroes, Xunlai storage\n"
    "• EotN unlocks: Boreal Station, Eye of the North pool, Kilroy Stonekin\n"
    "• Factions routes: Kaineng Center, Marketplace, Seitung Harbor, Minister Cho\n"
    "• Prophecies routes: Lion's Arch, Olias unlock, Temple of the Ages (D/R)\n\n"
    "Credits:\n"
    "• Classic script by Wick (Divinus) and Kendor\n"
    "• BT conversion for Py4GW widget system by Kendor"
)
ROUTINE_NAME = "NightfallLevelerSequence"

# ---------------------------------------------------------------------------
# Map ids used by the leveler
# ---------------------------------------------------------------------------
KAMADAN = 449
SUNSPEAR_GREAT_HALL = 431
PLAINS_OF_JARIN = 430
CHAMPIONS_DAWN = 479
JOKANUR_DIGGINGS = 491
CONSULATE_DOCKS = 493
GTOB = 248
CHAHBEK_VILLAGE = 544
ICE_CLIFF_CHASMS = 499
NORRHART_DOMAINS = 548
GUNNARS_HOLD = 644
EOTN_OUTPOST = 642
BOREAL_STATION = 675
KAINENG_CENTER = 194
THE_MARKETPLACE = 240
SEITUNG_HARBOR = 250
SHINJEA_MONASTERY = 242
TSUMEI_VILLAGE = 249
MINISTER_CHO = 214
LIONS_ARCH = 55
CLIFFS_OF_DOHJOK = 432
THE_ASTRELARIUM = 502
FAHRANUR_THE_FIRST_CITY = 481
CHAHBEK_VILLAGE_MISSION_MAP = 456
NORTH_KRYTA_PROVINCE = 58
DALESSIO_SEABOARD = 15
NEBO_TERRACE = 59
BERGEN_HOT_SPRINGS = 57
CURSED_LANDS = 56
THE_BLACK_CURTAIN = 18
TEMPLE_OF_THE_AGES = 138

# ---------------------------------------------------------------------------
# NPC encoded name strings (unchanging identifiers for NPCs)
# ---------------------------------------------------------------------------
GWEN_ENC_STRING = "\\x8102\\x11AF"
SCRYING_POOL_ENC_STRING = "\\x8102\\x229B\\xEC49\\xC39A\\x7C4C"
OGDEN_ENC_STRING = "\\x8102\\x0656"
VEKK_ENC_STRING = "\\x8102\\x064F"

# HeroID.MOX — M.O.X., the Dervish golem hero (EotN), Hero_enums.py
MOX_HERO_ID = 16
# Player-level Dervish hero skillbar template for M.O.X.
MOX_SKILLBAR_TEMPLATE = "OgGikys8AdZuD4xrQx+KAKvA"

NEHDUKAH_ENC_STRING = "\\x8101\\x246C\\xFDB5\\xB6AD\\x56AB"

botting_tree: BottingTree | None = None
initialized = False


def ensure_botting_tree() -> BottingTree:
    global botting_tree

    if botting_tree is None:
        botting_tree = BottingTree.Create(
            MODULE_NAME,
            main_routine=get_execution_steps(),
            routine_name=ROUTINE_NAME,
            repeat=False,
            multi_account=False,
            isolation_enabled=True,
            configure_fn=_configure_upkeep,
        )

    return botting_tree


# The Imp summoning stone services are gated by this flag instead of being
# added/removed at runtime: rebuilding the service list mid-run tears down the
# root tree (planner included), which aborts the currently running mission
# step. Toggling the flag takes effect on the next service tick with no rebuild.
_imp_services_enabled: bool = True


def _gated_imp_service(name: str, subtree_factory: Callable[[], BehaviorTree]) -> BehaviorTree:
    """Build an imp service node that only runs while _imp_services_enabled."""
    def _tick(node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        if not _imp_services_enabled:
            state = node.blackboard.get(f"{name}_gate_state")
            if state is not None and state.get("subtree") is not None:
                state["subtree"].reset()
                state["subtree"] = None
            return BehaviorTree.NodeState.RUNNING
        return RoutinesBT.Upkeepers._tick_service_subtree(
            node,
            state_key=f"{name}_gate_state",
            subtree_factory=subtree_factory,
        )

    return BehaviorTree(
        BehaviorTree.ConditionNode(
            name=name,
            condition_fn=_tick,
        )
    )


def _configure_upkeep(tree: BottingTree) -> None:
    tree.Config.ConfigureUpkeep(
        looting_enabled=True,
        resurrection_scroll=True,
        auto_inventory_handler_enabled=True,
        consumable_upkeeps=tuple(
            int(model_id)
            for model_id in CONSUMABLE_UPKEEPS
        ),
        # Igneous Summoning Stone (Fire Imp, model 30847) upkeep is registered
        # below as flag-gated services; UnlockKilroyStonekin flips the gate
        # off for the mission and back on afterwards.
        enable_outpost_imp_service=False,
        enable_explorable_imp_service=False,
        heroai_state_logging=False,
        enable_party_wipe_recovery=True,
    )
    tree.AddServiceTree(
        "OutpostImpService",
        lambda: _gated_imp_service(
            "OutpostImpService",
            lambda: RoutinesBT.Upkeepers.OutpostImpService(),
        ),
    )
    tree.AddServiceTree(
        "ExplorableImpService",
        lambda: _gated_imp_service(
            "ExplorableImpService",
            lambda: RoutinesBT.Upkeepers.ExplorableImpService(),
        ),
    )


# ============================================================================
# Shared environment helpers
# ============================================================================

def _profession_name() -> str:
    primary, _ = Agent.GetProfessionNames(Player.GetAgentID())
    return str(primary or "Warrior")


def _player_level() -> int:
    return int(Agent.GetLevel(Player.GetAgentID()) or 1)


def ConfigureAggressiveEnv() -> BehaviorTree:
    """Standard behavior-tree aggressive environment template."""
    return ensure_botting_tree().Config.ConfigureAggressiveEnv(
        multi_account=False,
        account_isolation=True,
        pause_on_danger=True,
        auto_loot=True,
        resurrection_scroll=True,
        reset_hero_ai=False,
    )


def ConfigurePacifistEnv() -> BehaviorTree:
    """Standard behavior-tree pacifist environment template."""
    return ensure_botting_tree().Config.ConfigurePacifistEnv(
        multi_account=False,
        account_isolation=True,
        pause_on_danger=False,
        auto_loot=True,
        resurrection_scroll=True,
        reset_hero_ai=False,
    )


def _should_run_double_mats_crafting() -> bool:
    """Professions that craft with double materials (common + dust)."""
    return _profession_name() in ("Paragon", "Elementalist", "Monk", "Necromancer")


# ============================================================================
# Per-profession data tables (equivalent of classic GetArmor/Weapon helpers)
# ============================================================================

def _get_armor_material() -> int:
    """Mirrors GetArmorMaterialPerProfession() -> ModelID."""
    primary = _profession_name()
    if primary == "Warrior":
        return ModelID.Iron_Ingot.value
    if primary == "Monk":
        return ModelID.Bolt_Of_Cloth.value
    if primary == "Dervish":
        return ModelID.Tanned_Hide_Square.value
    if primary == "Mesmer":
        return ModelID.Bolt_Of_Cloth.value
    if primary == "Necromancer":
        return ModelID.Tanned_Hide_Square.value
    if primary == "Ritualist":
        return ModelID.Bolt_Of_Cloth.value
    if primary == "Elementalist":
        return ModelID.Bolt_Of_Cloth.value
    return ModelID.Tanned_Hide_Square.value


def _get_weapon_material() -> list[int]:
    """Mirrors GetWeaponMaterialPerProfession() -> list of one material id."""
    primary = _profession_name()
    if primary == "Elementalist":
        return [ModelID.Wood_Plank.value]
    if primary == "Monk":
        return [ModelID.Wood_Plank.value]
    if primary == "Necromancer":
        return [ModelID.Iron_Ingot.value]
    return [ModelID.Iron_Ingot.value]


def _get_first_weapon_material() -> list[int]:
    """Mirrors GetFirstWeaponMaterialPerProfession()."""
    primary = _profession_name()
    if primary == "Elementalist":
        return [ModelID.Wood_Plank.value]
    if primary == "Monk":
        return [ModelID.Wood_Plank.value]
    if primary == "Mesmer":
        return [ModelID.Iron_Ingot.value]
    if primary == "Necromancer":
        return [ModelID.Wood_Plank.value]
    return [ModelID.Iron_Ingot.value]


def _get_armor_pieces() -> tuple[int, int, int, int, int]:
    """Mirrors GetArmorPiecesByProfession() -> (HEAD, CHEST, GLOVES, PANTS, BOOTS)."""
    primary = _profession_name()
    if primary == "Warrior":
        return 17525, 17531, 17532, 17533, 17530
    if primary == "Dervish":
        return 17705, 17676, 17677, 17678, 17675
    if primary == "Ranger":
        return 17619, 17621, 17622, 17623, 17620
    if primary == "Mesmer":
        return 17191, 17196, 17197, 17198, 17195
    if primary == "Paragon":
        return 17777, 17791, 17792, 17793, 17790
    if primary == "Elementalist":
        return 17333, 17350, 17351, 17352, 17349
    if primary == "Monk":
        return 17402, 17406, 17407, 17408, 17405
    return 17249, 17251, 17252, 17253, 17250  # Necromancer


def _get_crafted_weapons() -> list[int]:
    """Mirrors GetWeaponByProfession()."""
    primary = _profession_name()
    if primary == "Warrior":
        return [18910]
    if primary == "Ranger":
        return [18903, 18912]
    if primary == "Paragon":
        return [18913, 18856]
    if primary == "Dervish":
        return [18910]
    if primary == "Elementalist":
        return [18921]
    if primary == "Mesmer":
        return [18914]
    if primary == "Monk":
        return [18926]
    return [18914]  # Necromancer


def _get_first_crafted_weapons() -> list[int]:
    """Mirrors GetFirstWeaponByProfession()."""
    primary = _profession_name()
    if primary == "Warrior":
        return [16227]
    if primary == "Ranger":
        return [15777]
    if primary == "Paragon":
        return [18711]
    if primary == "Dervish":
        return [16227]
    if primary == "Elementalist":
        return [18896]
    if primary == "Mesmer":
        return [18712]
    if primary == "Monk":
        return [18901]
    return [18893]  # Necromancer


# ============================================================================
# Skill bar + equipment helpers
# ============================================================================

def _skillbar_template_for(profession: str, level: int) -> str:
    """Mirrors the classic EquipSkillBar() level-switch tables."""
    if profession == "Dervish":
        if level == 2:
            return "OgChkSj4V6KAGw/X7LCe8C"
        if level in (3, 4, 5):
            return "OgCjkOrCbMiXp74dADAAAAABAA"
        return "OgGjkyrDLTiXSX7gDYPXfXjbYcA"
    if profession == "Paragon":
        if level in (2, 3):
            return "OQCjUOmBqMw4HMQuCHjBAYcBAA"
        if level == 4:
            return "OQCjUWmCaNw4HMQuCDAAAYcBAA"
        if level == 5:
            return "OQGkUemyZgKEM2DmDGQ2VBQoAAGH"
        return "OQGjUymDKTwYPYOYAZLYXFAhYcA"
    if profession == "Elementalist":
        if level in (2, 3):
            return "OgBDozGsAGTrwFbNAAIA"
        if level in (4, 5):
            return "OgBDo2OMNGDahwoYYNAAAAMO"
        return "OgVDErwsN0COwFAoeTzzgVMO"
    if profession == "Monk":
        if level == 2:
            return "OwAU0C38CYEZEltkf5cmAImA"
        if level in (3, 4, 5):
            return "OwAU0CH9CoEtElZkf5EAAImA"
        return "OwUEEqwD6ywBuA308cPAKgSiJA"
    if profession == "Warrior":
        if level in (2, 3, 4, 5):
            return "OQARErprIUAABAuCGHAAAA"
        return "OQojExVTKTdFCF/XDYcFBA7gYcA"
    if profession == "Necromancer":
        if level == 2:
            return "OABDQRJWAplpAAAAAAAA"
        if level in (3, 4):
            return "OABDQTNmMphMRboK8IAAAAMO"
        if level == 5:
            return "OAVDIXN2McgqwFAo2DgCCAMO"
        return "OAVEEqwFZ3wBqCXAgaPAKknx4A"
    if profession == "Mesmer":
        if level == 2:
            return "OQBDAhITAoohAAAAAAAA"
        if level in (3, 4):
            return "OQBDAhgTAooBHEBFAAIA"
        if level == 5:
            return "OQBDAhgTMogLAHgIAF6BAVBA"
        return "OQBEAaYCP2gCuAcg8MUoHAUx4A"
    # Ranger
    if level == 2:
        return "OgATcDskjQx+WAAAAAAAAAA"
    if level == 3:
        return "OgATcDsknQx++4xGAAAACAA"
    if level == 4:
        return "OgAScLsMAAfzxZ5gxBAAABA"
    if level == 5:
        return "OgESIpLNdFfDUBAAA4KXFMO"
    return "OgETI5LjHqrw3AqYHkqQvC1AjDA"


def EquipSkillBar() -> BehaviorTree:
    """Loads the level-appropriate skillbar for the current profession."""

    def _resolve(_node: BehaviorTree.Node) -> BehaviorTree:
        template = _skillbar_template_for(_profession_name(), _player_level())
        return BT.LoadSkillbar(template=template, log=False)

    return BT.Subtree(
        name="Equip Skill Bar",
        subtree_fn=_resolve,
    )


def EquipWeapon() -> BehaviorTree:
    """Mirrors the classic Equip_Weapon() generator (starter weapons)."""
    return BT.GetNodeByProfession(
        DervishNode=BT.EquipItemByModelID(15591, log=True),
        ParagonNode=BT.EquipItemByModelID(15593, log=True),
        ElementalistNode=BT.EquipItemByModelID(2742, log=True),
        MesmerNode=BT.EquipItemByModelID(2652, log=True),
        NecromancerNode=BT.EquipItemByModelID(2694, log=True),
        RangerNode=BT.EquipItemByModelID(477, log=True),
        WarriorNode=BT.EquipItemByModelID(2982, log=True),
        MonkNode=BT.EquipItemByModelID(2787, log=True),
    )


# ============================================================================
# Party helpers
# ============================================================================

def PrepareForBattle(
    hero_list: list[int] | None = None,
    henchman_list: list[int] | None = None,
) -> BehaviorTree:
    """Equivalent of the classic PrepareForBattle(): aggressive + skillbar + fresh party."""
    return BT.Sequence(
        name="Prepare For Battle",
        children=[
            ConfigureAggressiveEnv(),
            EquipSkillBar(),
            BT.CreateParty(
                hero_ids=list(hero_list or []),
                henchman_ids=list(henchman_list or []),
                multibox_invite=False,
                timeout_ms=15000,
                log=True,
            ),
        ],
    )


def StandardHeroTeam(henchman_ids: list[int] | None = None) -> BehaviorTree:
    """Mirrors the classic StandardHeroTeam() (Gwen/Vekk/Ogden for small parties).

    `henchman_ids` composes henchmen into the same LoadParty call, equivalent of
    the classic AddCustomState(StandardHeroTeam) + Party.AddHenchmanList([...]).
    """

    def _resolve(_node: BehaviorTree.Node) -> BehaviorTree:
        party_size = Map.GetMaxPartySize()
        hero_list: list[int] = []
        skill_templates: list[str] = []
        if party_size <= 8:
            hero_list.extend([24, 26, 27])  # Gwen, Vekk, Ogden
            skill_templates = [
                "OQhkAsC8gFKzJY6lDMd40hQG4iB",  # Gwen
                "OgVDI8gsO5gTw0z0hTFAZgiA",     # Vekk
                "OwUUMsG/E4SNgbE3N3ETfQgZAMEA",  # Ogden
            ]

        children: list[BehaviorTree | BehaviorTree.Node] = [
            RoutinesBT.Party.LoadParty(
                hero_ids=hero_list,
                henchman_ids=[],
                log=True,
            ),
        ]
        for position, template in enumerate(skill_templates, start=1):
            children.append(BT.LoadHeroSkillbar(hero_index=position, template=template, log=True))
            children.append(BT.Wait(duration_ms=500))
        return BT.Sequence(name="Standard Hero Team", children=children)

    return BT.Subtree(
        name="Standard Hero Team",
        subtree_fn=_resolve,
    )


def AddHenchmenFC() -> BehaviorTree:
    """Mirrors the classic AddHenchmenFC() (map/party-size henchman list)."""

    def _resolve(_node: BehaviorTree.Node) -> BehaviorTree:
        party_size = Map.GetMaxPartySize()
        henchman_list: list[int] = []
        if party_size <= 4:
            henchman_list.extend([1, 5, 2])
        elif Map.GetMapID() == Map.GetMapIDByName("Seitung Harbor"):
            henchman_list.extend([2, 3, 1, 4, 5])
        elif Map.GetMapID() == Map.GetMapIDByName("The Marketplace"):
            henchman_list.extend([6, 9, 5, 1, 4, 7, 3])
        elif Map.GetMapID() == 213:  # zen_daijun_map_id
            henchman_list.extend([3, 1, 6, 8, 5])
        elif Map.GetMapID() == 194:  # kaineng_map_id
            henchman_list.extend([2, 10, 4, 8, 7, 9, 12])
        elif Map.GetMapID() == Map.GetMapIDByName("Boreal Station"):
            henchman_list.extend([7, 9, 2, 3, 4, 6, 5])
        else:
            henchman_list.extend([2, 3, 5, 6, 7, 9, 10])

        return RoutinesBT.Party.LoadParty(
            hero_ids=[],
            henchman_ids=henchman_list,
            log=True,
        )

    return BT.Subtree(
        name="Add Henchmen FC",
        subtree_fn=_resolve,
    )


def AddHenchmenLA() -> BehaviorTree:
    """Mirrors the classic AddHenchmenLA() (Lion's Arch henchmen)."""

    def _resolve(_node: BehaviorTree.Node) -> BehaviorTree:
        party_size = Map.GetMaxPartySize()
        henchman_list: list[int] = []
        if party_size <= 4:
            henchman_list.extend([2, 3, 1])
        elif Map.GetMapID() == Map.GetMapIDByName("Lions Arch"):
            henchman_list.extend([7, 2, 5, 3, 1])
        elif Map.GetMapID() == Map.GetMapIDByName("Ascalon City"):
            henchman_list.extend([2, 3, 1])
        else:
            henchman_list.extend([2, 8, 6, 7, 3, 5, 1])

        return RoutinesBT.Party.LoadParty(
            hero_ids=[],
            henchman_ids=henchman_list,
            log=True,
        )

    return BT.Subtree(
        name="Add Henchmen LA",
        subtree_fn=_resolve,
    )


# ============================================================================
# Crafting helpers (equivalent of classic generator states)
# ============================================================================

def _RestockForCrafting(pairs: list[tuple[int, int]]) -> BehaviorTree:
    """Withdraw crafting materials from Xunlai storage into inventory.

    BuyMaterials and CraftItem both operate on inventory bags only, so any
    materials parked in storage must be pulled out before the crafter is
    opened. allow_missing=True keeps the trader-purchase path viable when
    storage is empty.
    """
    children: list[BehaviorTree | BehaviorTree.Node] = []
    for model_id, quantity in pairs:
        children.append(
            RoutinesBT.Items.RestockItems(
                model_id=model_id, desired_quantity=quantity, allow_missing=True))
    return BT.Sequence(name="Restock Crafting Materials", children=children)


def BuyMaterials() -> BehaviorTree:
    """Buy 2 batches of the profession armor material."""

    def _resolve(_node: BehaviorTree.Node) -> BehaviorTree:
        material_id = _get_armor_material()
        return RoutinesBT.Items.BuyMaterials(model_id=material_id, batches=2, log=True)

    return BT.Subtree(
        name="Buy Materials",
        subtree_fn=_resolve,
    )


def BuyWeaponMaterials() -> BehaviorTree:
    """Buy 1 batch of the profession weapon material."""

    def _resolve(_node: BehaviorTree.Node) -> BehaviorTree:
        materials = _get_weapon_material()
        if not materials:
            return BT.Succeeder(name="SkipBuyWeaponMaterials")
        return RoutinesBT.Items.BuyMaterials(model_id=materials[0], batches=1, log=True)

    return BT.Subtree(
        name="Buy Weapon Materials",
        subtree_fn=_resolve,
    )


def BuyDoubleMaterials(material_type: str = "common") -> BehaviorTree:
    """Buy the common (and optional rare) materials used for double-mats armor."""

    def _resolve(_node: BehaviorTree.Node) -> BehaviorTree:
        children: list[BehaviorTree | BehaviorTree.Node] = []
        if material_type == "common":
            if _profession_name() in ("Paragon", "Monk", "Elementalist", "Necromancer"):
                children.append(RoutinesBT.Items.BuyMaterials(
                    model_id=_get_armor_material(), batches=2, log=True))
                children.append(BT.Wait(duration_ms=500))
                children.append(RoutinesBT.Items.BuyMaterials(
                    model_id=ModelID.Pile_Of_Glittering_Dust.value, batches=1, log=True))
            else:
                children.append(RoutinesBT.Items.BuyMaterials(
                    model_id=_get_armor_material(), batches=2, log=True))
        else:
            # "rare" material for professions that need it.
            rare_ids: dict[str, list[tuple[int, int]]] = {
                "Warrior": [(ModelID.Deldrimor_Steel_Ingot.value, 20)],
                "Dervish": [(ModelID.Monstrous_Claw.value, 20)],
                "Ranger": [(ModelID.Fur_Square.value, 20)],
                "Monk": [(ModelID.Pile_Of_Glittering_Dust.value, 20)],
                "Mesmer": [(ModelID.Pile_Of_Glittering_Dust.value, 20)],
                "Necromancer": [(ModelID.Pile_Of_Glittering_Dust.value, 20)],
                "Elementalist": [(ModelID.Pile_Of_Glittering_Dust.value, 20)],
                "Paragon": [(ModelID.Deldrimor_Steel_Ingot.value, 20)],
            }
            for model_id, count in rare_ids.get(_profession_name(), []):
                children.append(RoutinesBT.Items.BuyMaterials(
                    model_id=model_id, batches=count // 10, log=True))
        return BT.Sequence(name=f"BuyDoubleMaterials({material_type})", children=children)

    return BT.Subtree(
        name=f"Buy Double Materials {material_type}",
        subtree_fn=_resolve,
    )


def _craft_armor_pieces() -> BehaviorTree:
    """Craft + equip the profession armor set (copy of classic CraftArmor)."""

    def _resolve(_node: BehaviorTree.Node) -> BehaviorTree:
        head, chest, gloves, pants, boots = _get_armor_pieces()
        material = [_get_armor_material()]
        armor_pieces: list[tuple[int, list[int], list[int]]] = [
            (head, material, [2]),
            (gloves, material, [2]),
            (chest, material, [6]),
            (pants, material, [4]),
            (boots, material, [2]),
        ]
        children: list[BehaviorTree | BehaviorTree.Node] = []
        for item_id, mats, qtys in armor_pieces:
            children.append(RoutinesBT.Items.CraftItem(
                output_model_id=item_id, cost=75, trade_model_ids=mats, quantity_list=qtys))
            children.append(BT.EquipItemByModelID(item_id, log=True))
        return BT.Sequence(name="Craft Armor", children=children)

    return BT.Subtree(
        name="Craft Armor",
        subtree_fn=_resolve,
    )


def _craft_double_mats_armor_pieces() -> BehaviorTree:
    """Craft + equip armor using double materials (common + dust for head)."""

    def _resolve(_node: BehaviorTree.Node) -> BehaviorTree:
        head, chest, gloves, pants, boots = _get_armor_pieces()
        primary = _profession_name()

        if primary in ("Paragon", "Monk", "Elementalist", "Necromancer"):
            dust = ModelID.Pile_Of_Glittering_Dust.value
            main_mat = _get_armor_material()
            armor_pieces: list[tuple[int, list[int], list[int]]] = [
                (head, [dust], [2]),
                (chest, [main_mat], [6]),
                (gloves, [main_mat], [2]),
                (pants, [main_mat], [4]),
                (boots, [main_mat], [2]),
            ]
        else:
            material = [_get_armor_material()]
            armor_pieces = [
                (head, material, [2]),
                (chest, material, [6]),
                (gloves, material, [2]),
                (pants, material, [4]),
                (boots, material, [2]),
            ]

        children: list[BehaviorTree | BehaviorTree.Node] = []
        for item_id, mats, qtys in armor_pieces:
            children.append(RoutinesBT.Items.CraftItem(
                output_model_id=item_id, cost=75, trade_model_ids=mats, quantity_list=qtys))
            children.append(BT.EquipItemByModelID(item_id, log=True))
        return BT.Sequence(name="Craft Armor Double Mats", children=children)

    return BT.Subtree(
        name="Craft Armor Double Mats",
        subtree_fn=_resolve,
    )


def _craft_weapons() -> BehaviorTree:
    """Craft + equip the profession weapon set (mirror of classic CraftWeapon)."""

    def _resolve(_node: BehaviorTree.Node) -> BehaviorTree:
        weapon_ids = _get_crafted_weapons()
        materials = _get_weapon_material()
        children: list[BehaviorTree | BehaviorTree.Node] = []
        for weapon_id in weapon_ids:
            children.append(RoutinesBT.Items.CraftItem(
                output_model_id=weapon_id, cost=50,
                trade_model_ids=materials, quantity_list=[1]))
            children.append(BT.EquipItemByModelID(weapon_id, log=True))
        return BT.Sequence(name="Craft Weapons", children=children)

    return BT.Subtree(
        name="Craft Weapons",
        subtree_fn=_resolve,
    )


def _craft_first_weapon() -> BehaviorTree:
    """Craft + equip the first weapon (mirror of classic Craft1stWeapon)."""

    def _resolve(_node: BehaviorTree.Node) -> BehaviorTree:
        weapon_ids = _get_first_crafted_weapons()
        materials = _get_first_weapon_material()
        children: list[BehaviorTree | BehaviorTree.Node] = []
        for weapon_id in weapon_ids:
            children.append(RoutinesBT.Items.CraftItem(
                output_model_id=weapon_id, cost=20,
                trade_model_ids=materials, quantity_list=[1]))
            children.append(BT.EquipItemByModelID(weapon_id, log=True))
        return BT.Sequence(name="Craft First Weapon", children=children)

    return BT.Subtree(
        name="Craft First Weapon",
        subtree_fn=_resolve,
    )


def DestroyStarterArmorAndUselessItems() -> BehaviorTree:
    """Equivalent of the classic destroy_starter_armor_and_useless_items() generator."""
    STARTER_ARMOR_BY_PROFESSION: dict[str, list[int]] = {
        "Dervish": [15712, 15710, 15711, 15713, 15709],
        "Paragon": [15717, 15715, 15716, 15718, 15714],
        "Warrior": [15702, 15700, 15701, 15703, 15699],
        "Ranger": [15707, 15705, 15706, 15708, 15704],
        "Monk": [15697, 15695, 15696, 15698, 15694],
        "Elementalist": [15692, 15690, 15691, 15693, 15689],
        "Mesmer": [15682, 15680, 15681, 15683, 15679],
        "Necromancer": [15687, 15685, 15686, 15688, 15684],
    }
    USELESS_ITEMS: list[int] = [
        17081,  # Battle Commendation
        477, 2787, 2652, 2694, 2982, 2742, 15591, 15593,  # starter weapons
        18901,  # Monk 1st Staff
        16227,  # 1st Scythe (Warrior/Dervish)
        30853,  # MOX Manual
    ]

    def _resolve(_node: BehaviorTree.Node) -> BehaviorTree:
        models = list(STARTER_ARMOR_BY_PROFESSION.get(_profession_name(), []))
        models.extend(USELESS_ITEMS)
        children: list[BehaviorTree | BehaviorTree.Node] = []
        for model in models:
            children.append(RoutinesBT.Items.DestroyItem(modelID_or_encStr=model, log=False))
        return BT.Sequence(name="Destroy Starter Armor And Useless Items", children=children)

    return BT.Subtree(
        name="Destroy Starter Armor And Useless Items",
        subtree_fn=_resolve,
    )


# ============================================================================
# Utility leaf nodes
# ============================================================================

# Total-XP thresholds sourced from the owning game-data table (matches
# https://wiki.guildwars.com/wiki/Experience). The farm loop gates on raw
# total XP (not the displayed level) per design.
def _total_xp_for_level(level: int) -> int:
    """Return the accumulated XP required to reach `level`."""
    for entry_level, total_xp, _xp_to_next in EXPERIENCE_PROGRESSION:
        if entry_level == level:
            return total_xp
    raise ValueError(f"Level {level} not present in EXPERIENCE_PROGRESSION")


LEVEL_10_TOTAL_XP = _total_xp_for_level(10)



def _clear_target() -> BehaviorTree.Node:
    """Classic Hog Hunt 'Player.ChangeTarget(0)' target reset."""

    def _action() -> BehaviorTree.NodeState:
        Player.ChangeTarget(0)
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree.ActionNode(name="Clear Target", action_fn=_action)


class RepeatWhileBelowLevel10XP(BehaviorTree.RepeaterUntilFailureNode):
    """Repeat the farm lap until total XP reaches the level-10 threshold.

    Unlike the base RepeaterUntilFailureNode, a child FAILURE is propagated as
    FAILURE instead of being misread as the stop condition. This matters here:
    a failed lap (map-load timeout, stuck movement) must surface as an error,
    not silently advance the storyline.
    """

    def _tick_impl(self) -> BehaviorTree.NodeState:
        while True:
            xp = int(Player.GetExperience() or 0)
            if xp >= LEVEL_10_TOTAL_XP:
                ConsoleLog("FarmUntilLevel10", f"Level 10 XP threshold reached ({xp} >= {LEVEL_10_TOTAL_XP}).", PySystem.Console.MessageType.Info)
                self._start_time_ms = None
                self.child.reset()
                return BehaviorTree.NodeState.SUCCESS

            result = self._normalize_state(self.child.tick())
            if result is None:
                ConsoleLog("FarmUntilLevel10", f"Farm lap node '{self.child.name}' returned None!", PySystem.Console.MessageType.Error)
                self._start_time_ms = None
                return BehaviorTree.NodeState.FAILURE

            if result == BehaviorTree.NodeState.RUNNING:
                return BehaviorTree.NodeState.RUNNING

            if result == BehaviorTree.NodeState.FAILURE:
                ConsoleLog("FarmUntilLevel10", f"Farm lap '{self.child.name}' failed while still below level 10 XP ({xp}/{LEVEL_10_TOTAL_XP}).", PySystem.Console.MessageType.Error)
                self._start_time_ms = None
                return BehaviorTree.NodeState.FAILURE

            # Lap completed successfully and XP still below threshold: reset and repeat.
            self.child.reset()


# ============================================================================
# Storyline steps (classic order, Armored Transport / Missing Shipment skipped)
# ============================================================================

def SkipTutorial() -> BehaviorTree:
    """Mirror of classic Skip_Tutorial()."""
    return BT.Sequence(
        name="Skip Tutorial",
        children=[
            BT.MoveAndDialog((10289, 6405), 0x82A501, log=True),
            BT.LeaveGH(),
            BT.WaitForMapLoad(map_id=544),
        ],
    )


def IntoChahbekVillage() -> BehaviorTree:
    """Mirror of classic Into_Chahbek_Village()."""
    return BT.Sequence(
        name="Quest: Into Chahbek Village",
        children=[
            BT.Travel(target_map_id=CHAHBEK_VILLAGE, log=True),
            BT.MoveAndDialog((3493, -5247), 0x82A507, log=True),
            BT.MoveAndDialog((3493, -5247), 0x82C501, log=True),
        ],
    )


def QuizTheRecruits() -> BehaviorTree:
    """Mirror of classic Quiz_the_Recruits()."""
    return BT.Sequence(
        name="Quest: Quiz the Recruits",
        children=[
            BT.Travel(target_map_id=CHAHBEK_VILLAGE, log=True),
            BT.Move((4750, -6105)),
            BT.MoveAndDialog((4750, -6105), 0x82C504, log=True),
            BT.MoveAndDialog((5019, -6940), 0x82C504, log=True),
            BT.MoveAndDialog((3540, -6253), 0x82C504, log=True),
            BT.MoveAndDialog((3485, -5246), 0x82C507, log=True),
        ],
    )


def NeverFightAlone() -> BehaviorTree:
    """Mirror of classic Never_Fight_Alone()."""
    return BT.Sequence(
        name="Quest: Never Fight Alone",
        children=[
            BT.Travel(target_map_id=CHAHBEK_VILLAGE, log=True),
            PrepareForBattle(hero_list=[6], henchman_list=[1, 2]),
            BT.SpawnAndDestroyBonusItems(
                exclude_list=[ModelID.Igneous_Summoning_Stone.value]),
            EquipWeapon(),
            BT.MoveAndDialog((3433, -5900), 0x82C701, log=True),
            BT.DialogAtXY((3433, -5900), 0x82C707, log=True),
        ],
    )


def ChahbekVillageMission() -> BehaviorTree:
    """Mirror of classic Chahbek_Village_Mission()."""
    return BT.Sequence(
        name="Chahbek Village Mission",
        children=[
            BT.Travel(target_map_id=CHAHBEK_VILLAGE, log=True),
            BT.LoadHeroSkillbar(
                hero_index=1, template="OQASEF6EC1vcNABWAAAA", log=True),
            BT.DialogAtXY((3485, -5246), 0x81, log=True),
            BT.DialogAtXY((3485, -5246), 0x84, log=True),
            BT.Wait(2000),
            BT.WaitUntilOnExplorable(),
            ConfigureAggressiveEnv(),
            BT.VanquishNode(steps=[(2240, -3535), (227, -5658), (-1144, -4378), (-2058, -3494), (-4725, -1830)]),
            BT.InteractWithGadgetAtXY((-4725, -1830)),  # Oil 1
            BT.Move((-1725, -2551)),
            BT.Wait(1500),
            BT.InteractWithGadgetAtXY((-1725, -2550)),  # Cata load
            BT.Wait(1500),
            BT.InteractWithGadgetAtXY((-1725, -2550)),  # Cata fire
            BT.Move((-4725, -1830)),  # Back to oil
            BT.InteractWithGadgetAtXY((-4725, -1830)),  # Oil 2
            BT.Move((-1731, -4138)),
            BT.InteractWithGadgetAtXY((-1731, -4138)),  # Cata 2 load
            BT.Wait(2000),
            BT.InteractWithGadgetAtXY((-1731, -4138)),  # Cata 2 fire
            BT.VanquishNode(steps=[(-2331, -419), (-1685, 1459), (-2895, -6247), (-3938, -6315)]),  # Boss
            BT.WaitForMapLoad(map_id=456),
        ],
    )


# ---------------------------------------------------------------------------
# Primary Training / vault / inventory
# ---------------------------------------------------------------------------

def _get_skills() -> BehaviorTree:
    """Mirror of classic Get_Skills(): pacifist env, then the profession
    trainer's 'Teach me' dialog. Mesmer and Necromancer trainers don't need
    the walk-back waypoint the other professions use."""
    return BT.Sequence(
        name="Get Skills",
        children=[
            ConfigurePacifistEnv(),
            BT.GetNodeByProfession(
                DervishNode=BT.Sequence(name="Dervish Skills", children=[
                    BT.MoveAndDialog((-12107, -705), 0x7F, log=True),
                    BT.Move((-12200, 473)),
                ]),
                ParagonNode=BT.Sequence(name="Paragon Skills", children=[
                    BT.MoveAndDialog((-10724, -3364), 0x7F, log=True),
                    BT.Move((-12200, 473)),
                ]),
                ElementalistNode=BT.Sequence(name="Elementalist Skills", children=[
                    BT.Move((-12002.54, 24.56)),
                    BT.MoveAndDialog((-12011, -639), 0x7F, log=True),
                    BT.Move((-12200, 473)),
                ]),
                MesmerNode=BT.MoveAndDialog((-7149, 1830), 0x7F, log=True),
                NecromancerNode=BT.MoveAndDialog((-6557, 1837), 0x7F, log=True),
                RangerNode=BT.Sequence(name="Ranger Skills", children=[
                    BT.MoveAndDialog((-9498, 1426), 0x7F, log=True),
                    BT.Move((-12200, 473)),
                ]),
                WarriorNode=BT.Sequence(name="Warrior Skills", children=[
                    BT.MoveAndDialog((-9663, 1506), 0x7F, log=True),
                    BT.Move((-12200, 473)),
                ]),
                MonkNode=BT.Sequence(name="Monk Skills", children=[
                    BT.MoveAndDialog((-11658, -1414), 0x7F, log=True),
                    BT.Move((-12200, 473)),
                ]),
            ),
        ],
    )


def PrimaryTraining() -> BehaviorTree:
    """Mirror of classic Primary_Training()."""
    return BT.Sequence(
        name="Quest: Primary Training",
        children=[
            BT.MoveAndDialog((-7234.90, 4793.62), 0x825801, log=True),
            _get_skills(),
            BT.MoveAndDialog((-7234.90, 4793.62), 0x825807, log=True),
            BT.CancelSkillRewardWindow(),
        ],
    )


def APersonalVault() -> BehaviorTree:
    """Mirror of classic A_Personal_Vault()."""
    return BT.Sequence(
        name="Quest: A Personal Vault",
        children=[
            BT.Travel(target_map_id=KAMADAN, log=True),
            BT.MoveAndDialog((-9251, 11826), 0x82A101, log=True),
            BT.MoveAndDialog((-7761, 14393), 0x84, log=True),
            BT.MoveAndDialog((-9251, 11826), 0x82A107, log=True),
            BT.EqualizeGold(5000),
        ],
    )


def ExtendInventorySpace() -> BehaviorTree:
    """Mirror of classic Extend_Inventory_Space() (bags 1-2 + belt pouch)."""
    merchant = (-4861, -7441)
    return BT.Sequence(
        name="Extend Inventory Space",
        children=[
            BT.Travel(target_map_id=GTOB, log=True),
            BT.EqualizeGold(5000),
            BT.MoveAndBuyMerchantItem(merchant, ModelID.Bag.value, quantity=1, log=True),  # Bag 1
            BT.EquipInventoryBag(ModelID.Bag.value, Bags.Bag1, log=True),
            BT.BuyMerchantItem(ModelID.Bag.value, quantity=1, log=True),  # Bag 2
            BT.EquipInventoryBag(ModelID.Bag.value, Bags.Bag2, log=True),
            BT.BuyMerchantItem(ModelID.Belt_Pouch.value, quantity=1, log=True),
            BT.EquipInventoryBag(ModelID.Belt_Pouch.value, Bags.BeltPouch, log=True),
        ],
    )


def MaterialGirl() -> BehaviorTree:
    """Mirror of classic Material_Girl()."""
    return BT.Sequence(
        name="Quest: Material Girl",
        children=[
            BT.Travel(target_map_id=KAMADAN, log=True),
            BT.Move((-10839.96, 9197.05)),
            BT.MoveAndDialog((-11363, 9066), 0x826101, log=True),
            PrepareForBattle(hero_list=[], henchman_list=[1, 3, 4]),
            BT.MoveAndExitMap(pos=(-9326, 18151), target_map_id=PLAINS_OF_JARIN, log=True),
            ConfigureAggressiveEnv(),
            BT.MoveAndKill(pos=(18460, 1002)),  # Bounty
            BT.MoveAndDialog((18460, 1002), 0x85, log=True),  # Blessing
            BT.MoveAndKill(pos=(9675, 1038)),
            BT.MoveAndDialog((9282, -1199), 0x826104, log=True),
            BT.Wait(2000),
            BT.VanquishNode(steps=[(9464, -2639),(11183, -7728),(9681, -9300),(7555, -6791),(5073, -4850)]),
            BT.MoveAndDialog((9292, -1220), 0x826104, log=True),
            BT.MoveAndDialog((-1782, 2790), 0x828801, log=True),
            BT.Move((-3145, 2412)),
            BT.MoveAndExitMap(pos=(-3236, 4503), target_map_id=SUNSPEAR_GREAT_HALL, log=True),
            BT.Wait(2000),
            BT.Travel(target_map_id=KAMADAN, log=True),
            BT.MoveAndDialog((-10024, 8590), 0x828804, log=True),
            BT.DialogAtXY((-10024, 8590), 0x828807, log=True),
            BT.MoveAndDialog((-11356, 9066), 0x826107, log=True),
        ],
    )


def HogHunt() -> BehaviorTree:
    """Mirror of classic Hog_Hunt().

    The classic's interact_Nehdukah managed coroutine (interact by enc string,
    poll for dialog buttons, send 0x828D01) maps onto the owning
    TargetAgentByModelIDAndSendDialog node, which handles target, interact and
    dialog submission with its own retry handling.
    """
    return BT.Sequence(
        name="Quest: Hog Hunt",
        children=[
            BT.Travel(target_map_id=SUNSPEAR_GREAT_HALL, random_travel=True,
                      log=True),
            PrepareForBattle(hero_list=[], henchman_list=[1, 3, 4]),
            BT.MoveAndExitMap(pos=(-3172, 3271), target_map_id=PLAINS_OF_JARIN, log=True),
            ConfigureAggressiveEnv(),
            BT.MoveAndKill(pos=(-1840.23, 2432.96)),
            BT.MoveAndDialog((-1297.00, 3229.00), 0x85, log=True),  # Insect bounty
            _clear_target(),
            BT.VanquishNode(steps=[(-269.29, 1981.00), (-1894.08, 2403.29)]),
            BT.Wait(90000),
            BT.TargetAgentByModelIDAndSendDialog(
                NEHDUKAH_ENC_STRING, 0x828D01, log=True),  # Accept quest
            BT.VanquishNode(steps=[(-6038.05, 2229.41), (-10117.84, 3935.15), (-12969.55, 9102.46)]),
            BT.WaitUntilOnCombat(),
            BT.MoveAndKill(pos=(-12743.11, 8789.06)),  # 2nd spawn wave
            BT.VanquishNode(steps=[(-8175.91, 7331.07), (-6762.51, 2301.88), (-149.15, 1838.02), (-1158.39, 1917.86)]),
            BT.TargetAgentByModelIDAndSendDialog(4869, 0x828D07, log=True),
            BT.Travel(target_map_id=SUNSPEAR_GREAT_HALL, random_travel=True,
                      log=True),
        ],
    )


def ToChampionsDawn() -> BehaviorTree:
    """Mirror of classic To_Champions_Dawn()."""
    return BT.Sequence(
        name="To Champion's Dawn",
        children=[
            BT.Travel(target_map_id=SUNSPEAR_GREAT_HALL, log=True),
            PrepareForBattle(hero_list=[], henchman_list=[1, 3, 4]),
            BT.MoveAndExitMap(pos=(-3172, 3271), target_map_id=PLAINS_OF_JARIN, log=True),
            ConfigureAggressiveEnv(),
            BT.MoveAndDialog((-1237.25, 3188.38), 0x85, log=True),  # Blessing
            BT.VanquishNode(steps=[(-4507, 616), (-7611, -5953), (-18083, -11907)]),
            BT.MoveAndExitMap(pos=(-19518, -13021), target_map_id=CHAMPIONS_DAWN, log=True),
        ],
    )


def QualitySteel() -> BehaviorTree:
    """Mirror of classic Quality_Steel()."""
    return BT.Sequence(
        name="Quest: Quality Steel",
        children=[
            BT.Travel(target_map_id=KAMADAN, log=True),
            BT.MoveAndDialog((-11208, 8815), 0x826001, log=True),
            BT.Travel(target_map_id=SUNSPEAR_GREAT_HALL, log=True),
            BT.MoveAndDialog((-4076, 5362), 0x826004, log=True),
            BT.MoveAndDialog((-2866, 7093), 0x84, log=True),
            PrepareForBattle(hero_list=[], henchman_list=[1, 3, 4]),
            BT.MoveAndExitMap(pos=(-3172, 3271), target_map_id=PLAINS_OF_JARIN, log=True),
            ConfigureAggressiveEnv(),
            BT.MoveAndDialog((-1237.25, 3188.38), 0x85, log=True),  # Blessing
            BT.VanquishNode(steps=[(-3225, 1749), (-995, -2423), (-513, 67)]),
            BT.Travel(target_map_id=KAMADAN, log=True),
            BT.MoveAndDialog((-11208, 8815), 0x826007, log=True),
        ],
    )


def AttributePointsQuest1() -> BehaviorTree:
    """Mirror of classic Attribute_Points_Quest_1()."""
    return BT.Sequence(
        name="Attribute points quest n. 1",
        children=[
            BT.Travel(target_map_id=SUNSPEAR_GREAT_HALL, log=True),
            BT.MoveAndDialog((-2866, 7093), 0x82CB01, log=True),
        ],
    )


def CraftFirstWeapon() -> BehaviorTree:
    """Mirror of classic Craft_First_Weapon()."""

    def _resolve(_node: BehaviorTree.Node) -> BehaviorTree:
        # One material set for the single first-weapon craft.
        pairs = [
            (model_id, len(_get_first_crafted_weapons()))
            for model_id in _get_first_weapon_material()
        ]
        return BT.Sequence(
            name="Craft first weapon",
            children=[
                _RestockForCrafting(pairs),
                BT.Travel(target_map_id=KAMADAN, log=True),
                BT.MoveAndInteract((-11270, 8785), log=True),
                BT.Wait(1000),
                _craft_first_weapon(),
                EquipSkillBar(),
            ],
        )

    return BT.Subtree(
        name="Craft first weapon",
        subtree_fn=_resolve,
    )


def ProofOfCourageAndSuwashThePirate() -> BehaviorTree:
    """Mirror of classic Proof_of_Courage_and_Suwash_the_Pirate()."""
    return BT.Sequence(
        name="Quests: Proof of Courage and Suwash the Pirate",
        children=[
            BT.Travel(target_map_id=SUNSPEAR_GREAT_HALL, log=True),
            PrepareForBattle(hero_list=[], henchman_list=[1, 2, 4]),
            BT.MoveAndDialog((-4358, 6535), 0x829301, log=True),  # Proof of Courage
            BT.MoveAndDialog((-4558, 4693), 0x826201, log=True),  # Suwash the Pirate
            BT.MoveAndExitMap(pos=(-3172, 3271), target_map_id=PLAINS_OF_JARIN, log=True),
            ConfigureAggressiveEnv(),
            BT.MoveAndDialog((-1237.25, 3188.38), 0x85, log=True),  # Blessing
            BT.VanquishNode(steps=[(-3972, 1703), (-6784, -3484)]),
            BT.InteractWithGadgetAtXY((-6418, -3759)),  # Corsair Chest
            BT.Wait(2000),
            BT.VanquishNode(steps=[(-5950, -6889), (-10278, -7011), (-10581, -11798)]),
            BT.MoveAndDialog((-16795, -12217), 0x85, log=True),  # Blessing
            BT.MoveAndKill(pos=(-15896, -10190)),  # Suwash the Pirate 4
            BT.MoveAndDialog((-15573, -9638), 0x826204, log=True),  # Suwash turn-in
            BT.Travel(target_map_id=SUNSPEAR_GREAT_HALL, log=True),
            BT.MoveAndDialog((-4367, 6542), 0x829307, log=True),  # PoC reward
            BT.MoveAndDialog((-4558, 4693), 0x826207, log=True),  # Suwash reward
            BT.Wait(2000),
        ],
    )


def AHiddenThreat() -> BehaviorTree:
    """Mirror of classic A_Hidden_Threat()."""
    return BT.Sequence(
        name="Quest: A Hidden Threat",
        children=[
            BT.Travel(target_map_id=SUNSPEAR_GREAT_HALL, log=True),
            PrepareForBattle(hero_list=[], henchman_list=[1, 2, 4]),
            BT.MoveAndDialog((-1835, 6505), 0x825A01, log=True),  # Shaurom
            BT.MoveAndExitMap(pos=(-3172, 3271), target_map_id=PLAINS_OF_JARIN, log=True),
            ConfigureAggressiveEnv(),
            BT.VanquishNode(steps=[(-4680.29, 1867.42), (-13276.00, -151.00), (-17946.33, 2426.69), (-17614.74, 11699.77), (-18657.45, 14601.87), (-16911.47, 19039.31)]),
            BT.WaitUntilOnCombat(),
            BT.WaitUntilOutOfCombat(),
            BT.MoveAndExitMap(pos=(-20136, 16757), target_map_id=THE_ASTRELARIUM, log=True),
            BT.Travel(target_map_id=SUNSPEAR_GREAT_HALL, log=True),
            BT.MoveAndDialog((-1835, 6505), 0x825A07, log=True),  # reward
        ],
    )


def IdentityTheft() -> BehaviorTree:
    """Mirror of classic Identity_Theft()."""
    return BT.Sequence(
        name="Quest: Identity Theft",
        children=[
            BT.Travel(target_map_id=KAMADAN, log=True),
            BT.Move((-7519.91, 14468.26)),
            BT.MoveAndDialog((-10461, 15229), 0x827201, log=True),  # take quest
            BT.Travel(target_map_id=CHAMPIONS_DAWN, log=True),
            BT.MoveAndDialog((25345, 8604), 0x827204, log=True),
            PrepareForBattle(hero_list=[], henchman_list=[1, 6, 7]),
            BT.MoveAndExitMap(pos=(22483, 6115), target_map_id=CLIFFS_OF_DOHJOK, log=True),
            ConfigureAggressiveEnv(),
            BT.MoveAndDialog((20215, 5285), 0x85, log=True),  # Blessing
            BT.AddModelToLootWhitelist(15850),
            BT.MoveAndKill(pos=(14429, 10337)),  # kill boss
            ConfigurePacifistEnv(),
            BT.LootItems(distance=Range.Spirit.value),
            BT.Wait(1000),
            BT.Travel(target_map_id=KAMADAN, log=True),
            BT.Move((-7519.91, 14468.26)),
            BT.MoveAndDialog((-10461, 15229), 0x827207, log=True),  # +500xp
        ],
    )
def ConfigurePlayerBuild() -> BehaviorTree:
    """Mirrors the classic Configure_Player_Build() (hero-point skill purchases)."""
    caster_hero_points = BT.Sequence(
        name="Kamadan Caster Hero Points",
        children=[
            BT.Travel(target_map_id=449),
            BT.MoveAndDialog(pos=(-11385, 16140), dialog_id=0x85),
            BT.DialogAtXY(pos=(-11385, 16140), dialog_id=0x853702),  # Wastrel's Demise
            BT.MoveAndDialog(pos=(-11385, 16140), dialog_id=0x85),
            BT.DialogAtXY(pos=(-11385, 16140), dialog_id=0x867902),  # Signet of Clumsiness
            BT.MoveAndDialog(pos=(-11385, 16140), dialog_id=0x85),
            BT.DialogAtXY(pos=(-11385, 16140), dialog_id=0x883603),  # Cry of Pain
        ],
    )
    ranger_hero_points = BT.Sequence(
        name="Kamadan Ranger Hero Points",
        children=[
            # Classic relies on already being in Kamadan after Identity Theft.
            BT.MoveAndDialog(pos=(-11385, 16140), dialog_id=0x85),
            BT.DialogAtXY(pos=(-11385, 16140), dialog_id=0x857A02),  # Critical Chop
            BT.MoveAndDialog(pos=(-11385, 16140), dialog_id=0x85),
            BT.DialogAtXY(pos=(-11385, 16140), dialog_id=0x815402),  # Disrupting Chop
            BT.MoveAndDialog(pos=(-11385, 16140), dialog_id=0x85),
            BT.DialogAtXY(pos=(-11385, 16140), dialog_id=0x81A802),  # Throw Dirt
        ],
    )
    paragon_hero_points = BT.MoveAndDialog(pos=(-11385, 16140), dialog_id=0x860B02)  # Mighty Throw
    sgh_caster_skills = BT.Sequence(
        name="Sunspear Caster Skills",
        children=[
            BT.MoveAndDialog(pos=(-3317, 7053), dialog_id=0x803D02),  # Leech Signet
            BT.DialogAtXY(pos=(-3317, 7053), dialog_id=0x854002),  # Web of Disruption
            BT.DialogAtXY(pos=(-3317, 7053), dialog_id=0x85),  # buy hero point
            BT.DialogAtXY(pos=(-3317, 7053), dialog_id=0x801702),  # Power Spike
        ],
    )
    return BT.Sequence(
        name="Configure Player Build",
        children=[
            BT.GetNodeByProfession(
                DervishNode=BT.Succeeder(),
                ParagonNode=paragon_hero_points,
                ElementalistNode=caster_hero_points,
                MesmerNode=caster_hero_points,
                NecromancerNode=caster_hero_points,
                MonkNode=caster_hero_points,
                RangerNode=ranger_hero_points,
                WarriorNode=BT.Succeeder(),
            ),
            BT.Travel(target_map_id=431),
            BT.WaitForMapLoad(map_id=431),
            BT.MoveAndDialog(pos=(-2864, 7031), dialog_id=0x82CB07),
            BT.GetNodeByProfession(
                DervishNode=BT.Sequence(
                    name="Sunspear Dervish Skills",
                    children=[
                        BT.MoveAndDialog(pos=(-3317, 7053), dialog_id=0x883B03),  # Whirlwind Attack
                        BT.DialogAtXY(pos=(-3317, 7053), dialog_id=0x86E302),  # Zealous Renewal
                        BT.DialogAtXY(pos=(-3317, 7031), dialog_id=0x85CF02),  # Twin Moon Sweep
                        BT.DialogAtXY(pos=(-3317, 7031), dialog_id=0x85),  # buy hero point
                        BT.DialogAtXY(pos=(-3317, 7031), dialog_id=0x85DF02),  # Mystic Vigor
                    ],
                ),
                ParagonNode=BT.Sequence(
                    name="Sunspear Paragon Skills",
                    children=[
                        BT.MoveAndDialog(pos=(-3317, 7053), dialog_id=0x884003),  # There's Nothing to Fear
                        BT.DialogAtXY(pos=(-3317, 7053), dialog_id=0x860E02),  # Unblockable Throw
                    ],
                ),
                ElementalistNode=sgh_caster_skills,
                MesmerNode=sgh_caster_skills,
                NecromancerNode=sgh_caster_skills,
                MonkNode=sgh_caster_skills,
                RangerNode=BT.MoveAndDialog(pos=(-3317, 7053), dialog_id=0x883B03),  # Whirlwind Attack
                WarriorNode=BT.Sequence(
                    name="Sunspear Warrior Skills",
                    children=[
                        BT.MoveAndDialog(pos=(-3317, 7053), dialog_id=0x883B03),  # Whirlwind Attack
                        BT.DialogAtXY(pos=(-3317, 7053), dialog_id=0x86E302),  # Zealous Renewal
                    ],
                ),
            ),
            EquipSkillBar(),
        ],
    )


def HoningYourSkills() -> BehaviorTree:
    """Mirrors the classic Honing_your_Skills()."""
    return BT.Sequence(
        name="Honing Your Skills",
        children=[
            BT.Travel(target_map_id=449),
            BT.MoveAndDialog(pos=(-7874, 9799), dialog_id=0x828901),
            BT.Wait(duration_ms=1000),
            BT.MoveAndDialog(pos=(-7874, 9799), dialog_id=0x828907),
        ],
    )


def CommandTraining() -> BehaviorTree:
    """Mirrors the classic Command_Training() (Churrhir Fields hero flagging)."""
    return BT.Sequence(
        name="Command Training",
        children=[
            BT.Travel(target_map_id=449),
            BT.MoveAndDialog(pos=(-7874, 9799), dialog_id=0x82C801),
            PrepareForBattle(hero_list=[6], henchman_list=[3, 4]),
            BT.Move(pos=(-7558, 6826)),
            BT.MoveAndDialog(pos=(-7525, 6288), dialog_id=0x84),
            BT.WaitForMapLoad(map_id=456),
            BT.MoveAndDialog(pos=(-2000, -2825), dialog_id=0x8B),
            BT.FlagAllHeroes(1110, -4175),
            BT.Wait(duration_ms=35000),
            BT.FlagAllHeroes(-2362, -6126),
            BT.Wait(duration_ms=35000),
            BT.FlagAllHeroes(-222, -5832),
            BT.Wait(duration_ms=7000),
            BT.Travel(target_map_id=449),
            BT.MoveAndDialog(pos=(-7874, 9799), dialog_id=0x82C807),
        ],
    )
def LeavingALegacy() -> BehaviorTree:
    """Mirrors the classic Leaving_A_Legacy() (Cliffs of Dohjok -> Jokanur Diggings)."""
    return BT.Sequence(
        name="Quest: Leaving A Legacy",
        children=[
            BT.Travel(target_map_id=479),
            PrepareForBattle(hero_list=[], henchman_list=[1, 2, 7]),
            BT.MoveAndDialog(pos=(22884, 7641), dialog_id=0x827804),
            BT.MoveAndExitMap(pos=(22483, 6115), target_map_id=432),
            ConfigureAggressiveEnv(),
            BT.MoveAndKill(pos=(20215, 5285)),
            BT.MoveAndDialog(pos=(20215, 5285), dialog_id=0x85),
            BT.Wait(duration_ms=2000),
            BT.MoveAndDialog(pos=(18008, 6024), dialog_id=0x827804),
            BT.VanquishNode(steps=[(13677.0, 6800.0), (7255.0, 5150.0)]),
            BT.MoveAndKill(pos=(-13255, 6535)),
            BT.MoveAndDialog(pos=(-13255, 6535), dialog_id=0x84),
            BT.VanquishNode(steps=[(-11211.0, 5204.0), (-11572.0, 3116.0), (-11532.0, 583.0), (-10282.0, -4254.0), (-6608.0, -711.0)]),
            BT.MoveAndKill(pos=(-25149, 12787)),
            BT.MoveAndExitMap(pos=(-27657, 14482), target_map_id=491),
            BT.MoveAndDialog(pos=(2888, 2207), dialog_id=0x827807),
        ],
    )


def CraftPlayerArmor() -> BehaviorTree:
    """Mirrors the classic armor crafting: double-mats for Paragon/Elementalist/Monk/Necromancer, standard otherwise."""
    standard = BT.Sequence(
        name="Craft Standard Armor",
        children=[
            # Head 2 + chest 6 + gloves 2 + pants 4 + boots 2 = 16 units.
            _RestockForCrafting([(_get_armor_material(), 16)]),
            BT.MoveAndInteract(pos=(3857.42, 1700.62)),  # Material merchant
            BuyMaterials(),
            BT.MoveAndInteract(pos=(3944, 2378)),  # Armor crafter
            BT.Wait(duration_ms=1000),
            _craft_armor_pieces(),
        ],
    )
    double_mats = BT.Sequence(
        name="Craft Double Mats Armor",
        children=[
            # Chest 6 + gloves 2 + pants 4 + boots 2 = 14 main material,
            # plus 2 dust for the head piece.
            _RestockForCrafting([
                (_get_armor_material(), 14),
                (ModelID.Pile_Of_Glittering_Dust.value, 2),
            ]),
            # Classic buys BOTH materials (common + dust) at the dedicated
            # material trader NPC, not the material merchant or the crafter.
            BT.MoveAndInteract(pos=(3839.00, 1618.00)),  # Material trader
            BuyDoubleMaterials(),
            BT.MoveAndInteract(pos=(3944, 2378)),  # Armor crafter
            BT.Wait(duration_ms=1000),
            _craft_double_mats_armor_pieces(),
        ],
    )
    return BT.Sequence(
        name="Craft Player Armor",
        children=[
            BT.Travel(target_map_id=491),
            BT.EqualizeGold(5000),
            BT.GetNodeByProfession(
                ParagonNode=double_mats,
                ElementalistNode=double_mats,
                MonkNode=double_mats,
                NecromancerNode=double_mats,
                WarriorNode=standard,
                RangerNode=standard,
                DervishNode=standard,
                MesmerNode=standard,
            ),
        ],
    )


def CraftPlayerWeapon() -> BehaviorTree:
    """Mirrors the classic Craft_Player_Weapon() (Dec weapon crafter, model 4778)."""

    def _resolve(_node: BehaviorTree.Node) -> BehaviorTree:
        # One full material set per crafted weapon (each CraftItem consumes
        # quantity_list=[1] of every trade material).
        pairs = [
            (model_id, len(_get_crafted_weapons()))
            for model_id in _get_weapon_material()
        ]
        return BT.Sequence(
            name="Craft Weapon",
            children=[
                BT.Travel(target_map_id=491),
                _RestockForCrafting(pairs),
                BT.MoveAndInteract(pos=(3857.42, 1700.62)),
                BuyWeaponMaterials(),
                BT.Move(pos=(4108.39, 2211.65)),
                BT.TargetAndDialogByModelID(modelID_or_encStr=4778, dialog_id=0x86),
                BT.Wait(duration_ms=1000),
                _craft_weapons(),
            ],
        )

    return BT.Subtree(
        name="Craft Weapon",
        subtree_fn=_resolve,
    )


# ============================================================================
# Leveling & region travel
# ============================================================================

# Fahranur: The First City
FAHRANUR = 481


def FarmUntilLevel10() -> BehaviorTree:
    """Mirrors classic Farm_Until_Level_10() but XP-gated (total >= 39600)."""
    single_lap = BT.Sequence(
        name="Fahranur Farm Lap",
        children=[
            EquipSkillBar(),
            BT.Move((1268, -311)),
            BT.Move((-1618, -783)),
            BT.Move((-2600, -1119)),
            BT.Move((-3546, -1444)),
            BT.WaitForMapLoad(map_id=FAHRANUR, timeout_ms=30000),
            ConfigureAggressiveEnv(),
            BT.MoveAndDialog(pos=(19651, 12237), dialog_id=0x85),
            BT.VanquishNode(steps=[(11182, 14880), (11543, 6466), (15193, 5918), (14485, 16), (10256, -1393)]),
            BT.MoveAndDialog(pos=(11238, -2718), dialog_id=0x85),
            BT.MoveAndKill(pos=(13382, -6837)),
            BT.WaitUntilOutOfCombat(timeout_ms=60000),
            BT.Travel(target_map_id=JOKANUR_DIGGINGS),
        ],
    )

    return BT.Sequence(
        name="Farm Until Level 10",
        children=[
            BT.Travel(target_map_id=JOKANUR_DIGGINGS),
            BT.LeaveParty(),
            PrepareForBattle(hero_list=[], henchman_list=[1, 2, 7]),
            RepeatWhileBelowLevel10XP(
                child=BT.Node(single_lap),
                name="Repeat Until Level 10",
            ),
        ],
    )


def ToConsulateDocks() -> BehaviorTree:
    """Mirrors the classic To_Consulate_Docks()."""
    return BT.Sequence(
        name="To Consulate Docks",
        children=[
            BT.Travel(target_map_id=KAMADAN),
            BT.VanquishNode(steps=[(-8075.89, 14592.47), (-6743.29, 16663.21), (-5271.00, 16740.00)]),
            BT.WaitForMapLoad(map_id=429, timeout_ms=30000),
            BT.MoveAndDialog(pos=(-4631.86, 16711.79), dialog_id=0x85),
            BT.WaitForMapLoad(map_id=493, timeout_ms=30000),
        ],
    )


def ToKainengCenter() -> BehaviorTree:
    """Mirrors the classic To_Kaineng_Center()."""
    return BT.Sequence(
        name="To Kaineng Center",
        children=[
            BT.Travel(target_map_id=493),
            BT.WaitForMapLoad(map_id=493, timeout_ms=30000),
            BT.DialogAtXY(pos=(-2546.09, 16203.26), dialog_id=0x88),
            BT.WaitForMapLoad(map_id=290, timeout_ms=30000),
            BT.VanquishNode(steps=[(-4230.84, 8008.28)]),
            BT.MoveAndDialog(pos=(-5134.16, 7004.48), dialog_id=0x817901),
            BT.Travel(target_map_id=194),
            BT.WaitForMapLoad(map_id=194, timeout_ms=30000),
        ],
    )


def ToMarketplace() -> BehaviorTree:
    """Mirrors the classic To_Marketplace()."""
    return BT.Sequence(
        name="To Marketplace",
        children=[
            BT.Travel(target_map_id=194),
            BT.LeaveParty(),
            AddHenchmenFC(),
            EquipSkillBar(),
            BT.VanquishNode(steps=[(3045, -1575), (3007, -2609), (2909, -3629), (3145, -4643), (3372, -5617)]),
            BT.WaitForMapLoad(map_id=240, timeout_ms=30000),
            ConfigureAggressiveEnv(),
            BT.VanquishNode(steps=[(-9467.0, 14207.0), (-10965.0, 9309.0), (-10332.0, 1442.0), (-10254.0, -1759.0), (-10324.0, -1213), (-10402, -2217), (-10704, -3213), (-11051, -4206), (-11483, -5143), (-11382, -6149), (-11024, -7085), (-10720, -8042), (-10404, -9039), (-10950, -9913), (-11937, -10246), (-12922, -10476), (-13745, -11050), (-14565, -11622)]),
            BT.MoveAndExitMap(pos=(-14565, -11622), target_map_name="The Marketplace"),
        ],
    )


def ToSeitungHarbor() -> BehaviorTree:
    """Mirrors the classic To_Seitung_Harbor()."""
    return BT.Sequence(
        name="To Seitung Harbor",
        children=[
            BT.Travel(target_map_id=303),
            BT.VanquishNode(steps=[(12313, 19236), (10343, 20329)]),
            BT.WaitForMapLoad(map_id=302, timeout_ms=30000),
            BT.VanquishNode(steps=[(8392, 20845)]),
            BT.MoveAndDialog(pos=(6912.20, 19912.12), dialog_id=0x84),
                        BT.WaitForMapLoad(map_id=250, timeout_ms=30000),
        ],
    )


def ToShinjeaMonastery() -> BehaviorTree:
    """Mirrors the classic To_Shinjea_Monastery()."""
    return BT.Sequence(
        name="To Shinjea Monastery",
        children=[
            PrepareForBattle(),
            BT.LeaveParty(),
            AddHenchmenFC(),
            BT.Travel(target_map_id=250),
            BT.VanquishNode(steps=[(17367.47, 12161.08)]),
            BT.MoveAndExitMap(pos=(15868.00, 13455.00), target_map_id=313),
            BT.VanquishNode(steps=[(574.21, 10806.26)]),
            BT.MoveAndExitMap(pos=(382.00, 9925.00), target_map_id=252),
            BT.MoveAndExitMap(pos=(-5004.50, 9410.41), target_map_id=242),
        ],
    )


def ToTsumeiVillage() -> BehaviorTree:
    """Mirrors the classic To_Tsumei_Village()."""
    return BT.Sequence(
        name="To Tsumei Village",
        children=[
            BT.LeaveParty(),
            BT.Travel(target_map_id=242),
            BT.LeaveParty(),
            AddHenchmenFC(),
            BT.MoveAndExitMap(pos=(-14961, 11453), target_map_name="Sunqua Vale"),
            ConfigurePacifistEnv(),
            BT.MoveAndExitMap(pos=(-4842, -13267), target_map_id=249),
        ],
    )


def ToMinisterCho() -> BehaviorTree:
    """Mirrors the classic To_Minister_Cho()."""
    return BT.Sequence(
        name="To Minister Cho",
        children=[
            BT.LeaveParty(),
            BT.Travel(target_map_id=242),
            BT.LeaveParty(),
            AddHenchmenFC(),
            BT.MoveAndExitMap(pos=(-14961, 11453), target_map_name="Sunqua Vale"),
            ConfigurePacifistEnv(),
            BT.VanquishNode(steps=[(16182.62, -7841.86), (6611.58, 15847.51)]),
            BT.Move((6874, 16391)),
                        BT.WaitForMapLoad(map_id=214, timeout_ms=30000),
        ],
    )


def ToLionsArch() -> BehaviorTree:
    """Mirrors the classic To_Lions_Arch()."""
    return BT.Sequence(
        name="To Lion's Arch",
        children=[
            BT.Travel(target_map_id=493),
            BT.WaitForMapLoad(map_id=493, timeout_ms=30000),
            BT.MoveAndDialog(pos=(-2546.09, 16203.26), dialog_id=0x89),
            BT.WaitForMapLoad(map_name="Lion's Gate", timeout_ms=30000),
            BT.VanquishNode(steps=[(-1181, 1038)]),
            BT.DialogAtXY(pos=(-1181, 1038), dialog_id=0x85),
            BT.Travel(target_map_id=55),
        ],
    )


def UnlockOlias() -> BehaviorTree:
    """Mirrors the classic Unlock_Olias()."""
    return BT.Sequence(
        name="Unlock Olias",
        children=[
            BT.Travel(target_map_id=493),
            BT.MoveAndDialog(pos=(-2367.00, 16796.00), dialog_id=0x830E01),
            BT.LeaveParty(),
            BT.Travel(target_map_id=55),
            BT.LeaveParty(),
            StandardHeroTeam(henchman_ids=[1, 3]),
            # Add henchmen 1 and 3 separately since StandardHeroTeam didn't add them
            RoutinesBT.Party.LoadParty(hero_ids=[], henchman_ids=[1, 3], clear_existing=False),
            BT.VanquishNode(steps=[(1413.11, 9255.51), (242.96, 6130.82)]),
            BT.MoveAndDialog(pos=(-1137.00, 2501.00), dialog_id=0x84),
            BT.WaitForMapLoad(map_id=471, timeout_ms=30000),
            BT.Wait(duration_ms=3000),
            BT.MoveAndDialog(pos=(5117.00, 10515.00), dialog_id=0x830E04),
            ConfigureAggressiveEnv(),
            BT.VanquishNode(steps=[(8518.10, 9309.66), (8067.40, 5703.23), (5657.20, 4485.55), (4461.65, -710.88), (9973.11, 1581.00)]),
            BT.Wait(duration_ms=30000),
            BT.WaitForMapLoad(map_id=55, timeout_ms=30000),
            BT.LeaveParty(),
            BT.Travel(target_map_id=KAMADAN),
            BT.Move((-8149.02, 14900.65)),
            BT.MoveAndDialog(pos=(-6480.00, 16331.00), dialog_id=0x830E07),
        ],
    )
    


# ============================================================================
# To Temple Of The Ages (Prophecies content, Dervish/Ranger only)
# ============================================================================

# Map IDs along the ToTA path (mirrors classic comments)
NORTH_KRYTA = 58
DALESSIO_SEABOARD_OUTPOST = 15
NEBO_TERRACE = 59
BERGEN_HOT_SPRINGS = 57
CURSED_LANDS = 56
BLACK_CURTAIN = 18
TEMPLE_OF_THE_AGES = 138


def ToTempleOfTheAges() -> BehaviorTree:
    """Mirrors the classic To_Temple_Of_The_Ages()."""
    return BT.Sequence(
        name="To Temple Of The Ages",
        children=[
            BT.Travel(target_map_id=55),
            StandardHeroTeam(henchman_ids=[1, 3]),
            EquipSkillBar(),
            BT.VanquishNode(steps=[(1219, 7222), (1021, 10651), (250, 12350)]),
            BT.WaitForMapLoad(map_id=NORTH_KRYTA, timeout_ms=30000),
            ConfigureAggressiveEnv(),
            BT.VanquishNode(steps=[(5116.0, -17415.0), (2346.0, -17307.0), (757.0, -16768.0), (-1521.0, -16726.0), (-3246.0, -16407.0), (-6042.0, -16126.0), (-7706.0, -17248.0), (-8910.0, -17561.0), (-9893.0, -17625.0), (-11325.0, -18358.0), (-11553.0, -19246.0), (-11600.0, -19500.0), (-11708, -19957)]),
            BT.WaitForMapLoad(map_id=DALESSIO_SEABOARD_OUTPOST, timeout_ms=30000),
            BT.VanquishNode(steps=[(16000, 17080), (16030, 17200)]),
            BT.WaitForMapLoad(map_id=NORTH_KRYTA, timeout_ms=30000),
            ConfigureAggressiveEnv(),
            BT.VanquishNode(steps=[(-11453.0, -18065.0), (-10991.0, -16776.0), (-10791.0, -15737.0), (-10130.0, -14138.0), (-10106.0, -13005.0), (-10558.0, -9708.0), (-10319.0, -7888.0), (-10798.0, -5941.0), (-10958.0, -1009.0), (-10572.0, 2332.0), (-10784.0, 3710.0), (-11125.0, 4650.0), (-11690.0, 5496.0), (-12931.0, 6726.0), (-13340.0, 7971.0), (-13932.0, 9091.0), (-13937.0, 11521.0), (-14639.0, 13496.0), (-15090.0, 14734.0), (-16653.0, 16226.0), (-18944.0, 14799.0), (-19468.0, 15449.0), (-19550.0, 15625.0)]),
            BT.WaitForMapLoad(map_id=NEBO_TERRACE, timeout_ms=30000),
            ConfigureAggressiveEnv(),
            BT.VanquishNode(steps=[(19271.0, 5207.0), (18307.0, 5369.0), (17704.0, 4786.0), (17801.0, 2710.0), (18221.0, 506.0), (18133.0, -1406.0), (16546.0, -4102.0), (15434.0, -6217.0), (14927.0, -8731.0), (14297.0, -10366.0), (14347.0, -12097.0), (15373.0, -14769.0), (15425.0, -15035.0)]),
            BT.WaitForMapLoad(map_id=BERGEN_HOT_SPRINGS, timeout_ms=30000),
            BT.LeaveParty(),
            StandardHeroTeam(henchman_ids=[1, 3]),
            EquipSkillBar(),
            BT.VanquishNode(steps=[(15521, -15378), (15450, -15050)]),
            BT.WaitForMapLoad(map_id=NEBO_TERRACE, timeout_ms=30000),
            BT.VanquishNode(steps=[(15378, -14794)]),
            BT.WaitForMapLoad(map_id=NEBO_TERRACE, timeout_ms=30000),
            ConfigureAggressiveEnv(),
            BT.VanquishNode(steps=[(13276.0, -14317.0), (10761.0, -14522.0), (8660.0, -12109.0), (6637.0, -9216.0), (4995.0, -7951.0), (1522.0, -7990.0), (-924.0, -10670.0), (-3489.0, -11607.0), (-4086.0, -11692.0), (-4290.0, -11599.0)]),
            BT.WaitForMapLoad(map_id=CURSED_LANDS, timeout_ms=30000),
            ConfigureAggressiveEnv(),
            BT.VanquishNode(steps=[(-4523.0, -9755.0), (-4067.0, -8786.0), (-4207.0, -7806.0), (-5497.0, -6137.0), (-7331.0, -6178.0), (-8784.0, -4598.0), (-9053.0, -2929.0), (-9610.0, -2136.0), (-10879.0, -1685.0), (-10731.0, -760.0), (-12517.0, 5459.0), (-15510.0, 7154.0), (-18010.0, 7033.0), (-18717.0, 7537.0), (-19896.0, 8964.0), (-20100.0, 9025.0)]),
            BT.WaitForMapLoad(map_id=BLACK_CURTAIN, timeout_ms=30000),
            ConfigureAggressiveEnv(),
            BT.VanquishNode(steps=[(8716.0, 18587.0), (5616.0, 17732.0), (3795.0, 17750.0), (1938.0, 16994.0), (592.0, 16243.0), (-686.0, 14967.0), (-1968.0, 14407.0), (-3398.0, 14730.0), (-4340.0, 14938.0), (-5004.0, 15424.0), (-5207.0, 15882.0), (-5180.0, 16000.0)]),
                        BT.WaitForMapLoad(map_id=TEMPLE_OF_THE_AGES, timeout_ms=30000),
        ],
    )


# ============================================================================
# Eye of the North expansion
# ============================================================================
def UnlockMOX() -> BehaviorTree:

    return BT.Sequence(
        name="Unlock MOX",
                children=[
                    BT.Travel(target_map_id=KAMADAN),
                    BT.LeaveParty(),
                    BT.MoveAndExitMap(pos=(-9326, 18151), target_map_id=PLAINS_OF_JARIN),
                    BT.MoveAndDialog(pos=(18191, 167), dialog_id=0x85),
                    BT.Travel(target_map_id=KAMADAN),
                ],
    )


def ToBorealStation() -> BehaviorTree:
    """Mirrors the classic To_Boreal_Station()."""
    return BT.Sequence(
        name="To Boreal Station",
        children=[
            BT.Travel(target_map_id=KAMADAN),
            BT.LeaveParty(),
            BT.MoveAndDialog(pos=(-8739, 14200), dialog_id=0x833601),
            # M.O.X. (HeroID 16) joins as hero 1 for the trip to Boreal Station.
            PrepareForBattle(hero_list=[MOX_HERO_ID], henchman_list=[3, 4]),
            EquipSkillBar(),
            BT.LoadHeroSkillbar(hero_index=1, template=MOX_SKILLBAR_TEMPLATE, log=True),
            BT.MoveAndExitMap(pos=(-9326, 18151), target_map_id=PLAINS_OF_JARIN),
            ConfigureAggressiveEnv(),
            BT.MoveAndKill(pos=(15407, 209)),
            BT.MoveAndDialog(pos=(13761, -13108), dialog_id=0x84),  # Yes
            BT.WaitForMapLoad(map_id=693, timeout_ms=30000),
            ConfigureAggressiveEnv(),
            BT.Wait(duration_ms=3000),
            BT.VanquishNode(steps=[(-5475, 8166), (-454, 10163), (4450, 10950), (8435, 14378), (10134, 16742)]),
            BT.Wait(duration_ms=3000),
            ConfigurePacifistEnv(),
            BT.Move(pos=(4523.25, 15448.03)),
            BT.Move(pos=(-43.80, 18365.45)),
            BT.Move(pos=(-10234.92, 16691.96)),
            BT.Move(pos=(-17917.68, 18480.57)),
            BT.Move(pos=(-18775, 19097)),
            BT.Wait(duration_ms=8000),
            BT.WaitForMapLoad(map_id=BOREAL_STATION, timeout_ms=30000),
        ],
    )


def ToEyeOfTheNorthOutpost() -> BehaviorTree:
    """Mirrors the classic To_Eye_Of_The_North_Outpost()."""
    return BT.Sequence(
        name="To Eye Of The North Outpost",
        children=[
            BT.Travel(target_map_id=BOREAL_STATION),
            PrepareForBattle(hero_list=[], henchman_list=[5, 6, 7, 9, 4, 3, 2]),
            BT.MoveAndExitMap(pos=(4684, -27869), target_map_name="Ice Cliff Chasms"),
            ConfigureAggressiveEnv(),
            BT.TakeBlessing(pos=(3579.07, -22007.27)),
            BT.Wait(duration_ms=15000),  # Wait for Jora quest dialog to become available
            BT.DialogAtXY(pos=(3537.00, -21937.00), dialog_id=0x839104),
            BT.VanquishNode(steps=[(3743.31, -15862.36), (8267.89, -12334.58), (3607.21, -6937.32), (2557.23, -275.97)]),
            BT.WaitForMapLoad(map_id=642, timeout_ms=30000),
        ],
    )


def UnlockEyeOfTheNorthPool() -> BehaviorTree:
    """Mirrors the classic Unlock_Eye_Of_The_North_Pool()."""
    return BT.Sequence(
        name="Unlock Eye Of The North Pool",
        children=[
            BT.Travel(target_map_id=642),
            BT.Move((-4416.39, 4932.36)),
            BT.Move((-5198.00, 5595.00)),
            BT.WaitForMapLoad(map_id=646, timeout_ms=30000),
            BT.Move(pos=(-6572.70, 6588.83)),
            BT.MoveAndDialogByModelID(modelID_or_encStr=GWEN_ENC_STRING, dialog_id=0x800001),  # Gwen
            BT.Wait(duration_ms=1000),
            BT.MoveAndDialogByModelID(modelID_or_encStr=SCRYING_POOL_ENC_STRING, dialog_id=0x63D),  # Scrying Pool
            BT.Wait(duration_ms=1000),
            BT.MoveAndDialogByModelID(modelID_or_encStr=SCRYING_POOL_ENC_STRING, dialog_id=0x63F),  # Scrying Pool
            BT.Wait(duration_ms=1000),
            BT.WaitForMapLoad(map_id=646, timeout_ms=30000),
            BT.MoveAndDialogByModelID(modelID_or_encStr=GWEN_ENC_STRING, dialog_id=0x89),  # Gwen
            BT.MoveAndDialogByModelID(modelID_or_encStr=GWEN_ENC_STRING, dialog_id=0x831904),  # Gwen
            BT.DialogAtXY(pos=(-6572.70, 6588.83), dialog_id=0x8A), #for the Keiran Bow
            BT.MoveAndDialogByModelID(modelID_or_encStr=OGDEN_ENC_STRING, dialog_id=0x838904),  # Ogden
            BT.MoveAndDialogByModelID(modelID_or_encStr=VEKK_ENC_STRING, dialog_id=0x839304),  # Vekk
        ],
    )


def ToGunnarsHold() -> BehaviorTree:
    """Mirrors the classic To_Gunnars_Hold()."""
    return BT.Sequence(
        name="To Gunnar's Hold",
        children=[
            BT.Travel(target_map_id=642),
            PrepareForBattle(hero_list=[], henchman_list=[5, 6, 7, 9, 4, 3, 2]),
            BT.Move((-1814.0, 2917.0)),
            BT.Move((-964.0, 2270.0)),
            BT.Move((-115.0, 1677.0)),
            BT.Move((718.0, 1060.0)),
            BT.Move((1522.0, 464.0)),
            BT.WaitForMapLoad(map_id=499, timeout_ms=30000),
            ConfigureAggressiveEnv(),
            BT.MoveAndDialog(pos=(2825, -481), dialog_id=0x832801),
            BT.VanquishNode(steps=[(2548.84, 7266.08), (1233.76, 13803.42), (978.88, 21837.26), (-4031.0, 27872.0)]),
            BT.WaitForMapLoad(map_id=548, timeout_ms=30000),
                        ConfigureAggressiveEnv(),
            BT.MoveAndExitMap(pos=(15578, -6548), target_map_id=644),
            BT.WaitForMapLoad(map_id=644, timeout_ms=30000),
        ],
    )


def _set_imp_services(enabled: bool) -> BehaviorTree:
    """Toggle the Igneous Summoning Stone upkeep services for the current run.

    Only flips the module-level gate flag; the services were registered once
    at tree creation. No tree rebuild happens here, so this is safe to call
    mid-mission (a ConfigureUpkeep re-call would reset the root tree and
    abort the running step).
    """
    def _apply(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        global _imp_services_enabled
        _imp_services_enabled = enabled
        ConsoleLog(
            "UnlockKilroyStonekin",
            f"Imp summoning stone services {'enabled' if enabled else 'disabled'}.",
        )
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name="Enable Imp Stone" if enabled else "Disable Imp Stone",
            action_fn=_apply,
            aftercast_ms=0,
        )
    )


# Weapon/offhand model IDs captured before the Kilroy brass knuckles are
# equipped, so the character can return to whatever they had before.
_stored_kilroy_weapons: dict[str, int] = {"weapon": 0, "offhand": 0}


def _remember_equipped_weapons() -> BehaviorTree:
    """Record the player's currently equipped weapon and offhand model IDs."""
    def _apply(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        agent_id = Player.GetAgentID()
        weapon_item_id, _weapon_type, offhand_item_id, _offhand_type = (
            Agent.GetWeaponExtraData(agent_id)
        )
        _stored_kilroy_weapons["weapon"] = (
            Item.GetModelID(weapon_item_id) if weapon_item_id else 0
        )
        _stored_kilroy_weapons["offhand"] = (
            Item.GetModelID(offhand_item_id) if offhand_item_id else 0
        )
        ConsoleLog(
            "UnlockKilroyStonekin",
            f"Remembered equipped weapons: weapon={_stored_kilroy_weapons['weapon']}, "
            f"offhand={_stored_kilroy_weapons['offhand']}.",
        )
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name="Remember Equipped Weapons",
            action_fn=_apply,
            aftercast_ms=0,
        )
    )


def _restore_equipped_weapons() -> BehaviorTree:
    """Re-equip the weapon/offhand remembered by _remember_equipped_weapons."""
    def _apply(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        agent_id = Player.GetAgentID()
        for key in ("weapon", "offhand"):
            model_id = _stored_kilroy_weapons.get(key, 0)
            if not model_id:
                continue
            item_id = GLOBAL_CACHE.Inventory.GetFirstModelID(model_id)
            if item_id == 0:
                ConsoleLog(
                    "UnlockKilroyStonekin",
                    f"Stored {key} model {model_id} not found in inventory; skipping.",
                )
                continue
            GLOBAL_CACHE.Inventory.EquipItem(item_id, agent_id)
            ConsoleLog(
                "UnlockKilroyStonekin",
                f"Re-equipped stored {key} (model {model_id}, item {item_id}).",
            )
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name="Restore Equipped Weapons",
            action_fn=_apply,
            aftercast_ms=1500,
        )
    )


def UnlockKilroyStonekin() -> BehaviorTree:
    """Mirrors the classic Unlock_Kilroy_Stonekin()."""
    return BT.Sequence(
        name="Unlock Kilroy Stonekin",
        children=[
            # The Imp summoning stone is not allowed in this mission.
            _set_imp_services(enabled=False),
            BT.Travel(target_map_id=644),
            BT.MoveAndDialog(pos=(17341.00, -4796.00), dialog_id=0x835A01),
            BT.DialogAtXY(pos=(17341.00, -4796.00), dialog_id=0x84),
            BT.WaitForMapLoad(map_id=703, timeout_ms=30000),
            BT.Sequence(name="Killroy Combat Template", children=[
                ConfigureAggressiveEnv(),
                # Snapshot what we're wearing so we can swap back after.
                _remember_equipped_weapons(),
                BT.EquipItemByModelID(24897),
            ]),
            # Walk into the arena (mirrors legacy Move.XY(19290.50, -11552.23));
            # without this the bot never engages and the mission never ends.
            BT.Move(pos=(19290.50, -11552.23)),
            BT.WaitUntilOnOutpost(timeout_ms=180000),
            BT.WaitForMapLoad(map_id=644, timeout_ms=30000),
            # Back in Gunnar's Hold: restore the imp stone services and the
            # weapons worn before the brass knuckles went on.
            _set_imp_services(enabled=True),
            _restore_equipped_weapons(),
            BT.MoveAndDialog(pos=(17341.00, -4796.00), dialog_id=0x835A07),
            BT.Succeeder(name="Profession weapons restored from snapshot"),
        ],
    )


def UnlockRemainingSecondaryProfessions() -> BehaviorTree:
    """Mirrors the classic Unlock_Remaining_Secondary_Professions()."""
    return _secondary_training_nodes()


def AttributePointsQuest2() -> BehaviorTree:
    """Mirrors the classic Attribute_Points_Quest_2()."""
    return BT.Sequence(
        name="Attribute points quest n. 2",
        children=[
            BT.Travel(target_map_id=431),
            BT.MoveAndDialog(pos=(-2866, 7093), dialog_id=0x82CC01),
            BT.Wait(duration_ms=3000),
            BT.MoveAndDialog(pos=(-2866, 7093), dialog_id=0x82CC07),
        ],
    )


def UnlockSunspearSkills() -> BehaviorTree:
    """Mirrors the classic Unlock_Sunspear_Skills()."""
    return BT.Sequence(
        name="Unlock Sunspear Skills",
        children=[
            BT.Travel(target_map_id=431),
            BT.Sequence(name="Buy Sunspear Skills", children=[
                BT.DialogAtXY(pos=(-3307.00, 6997.56), dialog_id=0x801101),
                BT.DialogAtXY(pos=(-3307.00, 6997.56), dialog_id=0x883503),
                BT.DialogAtXY(pos=(-3307.00, 6997.56), dialog_id=0x883603),
                BT.DialogAtXY(pos=(-3307.00, 6997.56), dialog_id=0x883703),
                BT.DialogAtXY(pos=(-3307.00, 6997.56), dialog_id=0x883803),
                BT.DialogAtXY(pos=(-3307.00, 6997.56), dialog_id=0x883903),
                BT.DialogAtXY(pos=(-3307.00, 6997.56), dialog_id=0x883B03),
                BT.DialogAtXY(pos=(-3307.00, 6997.56), dialog_id=0x883C03),
                BT.DialogAtXY(pos=(-3307.00, 6997.56), dialog_id=0x883D03),
                BT.DialogAtXY(pos=(-3307.00, 6997.56), dialog_id=0x883E03),
                BT.DialogAtXY(pos=(-3307.00, 6997.56), dialog_id=0x884003),
            ]),
        ],
    )


def UnlockXunlaiMaterialStorage() -> BehaviorTree:
    """Mirrors the classic Unlock_Xunlai_Material_Storage()."""
    return BT.Sequence(
        name="Unlock Xunlai Material Storage",
        children=[
            BT.LeaveParty(),
            BT.Travel(target_map_id=248),
            BT.Move((-5540.40, -5733.11)),
            BT.Move((-7050.04, -6392.59)),
            BT.DialogAtXY(pos=(-7050.04, -6392.59), dialog_id=0x800001),
            BT.DialogAtXY(pos=(-7050.04, -6392.59), dialog_id=0x800002),
        ],
    )


def UnlockMercenaryHeroes() -> BehaviorTree:
    """Mirrors the classic Unlock_Mercenary_Heroes()."""
    return BT.Sequence(
        name="Unlock Mercenary Heroes",
        children=[
            BT.LeaveParty(),
            BT.Travel(target_map_id=248),
            BT.Move((-4231.87, -8965.95)),
            BT.DialogAtXY(pos=(-4231.87, -8965.95), dialog_id=0x800004),
        ],
    )


def SecondaryTraining() -> BehaviorTree:
    """Mirror of classic Secondary_Training() (2nd profession selection)."""

    def _resolve(_node: BehaviorTree.Node) -> BehaviorTree:
        profession = _profession_name()

        # First gate: which profession trainer to visit
        if profession == "Necromancer":
            trainer_dialog = BT.MoveAndDialog(
                pos=(-7149, 1830), dialog_id=0x7F, log=True)
        else:
            trainer_dialog = BT.MoveAndDialog(
                pos=(-6557, 1837), dialog_id=0x7F, log=True)

        # Second gate: profession-specific 2nd-profession dialogs
        if profession == "Warrior":
            select_2nd = BT.Sequence(name="Select 2nd Profession (Warrior)", children=[
                BT.MoveAndDialog(pos=(-7161, 4808), dialog_id=0x8A, log=True),
                BT.DialogAtXY(pos=(-7161, 4808), dialog_id=0x825407),
                BT.DialogAtXY(pos=(-7161, 4808), dialog_id=0x827801),
            ])
        elif profession in ("Necromancer", "Monk", "Elementalist"):
            select_2nd = BT.Sequence(name="Select 2nd Profession (Caster)", children=[
                BT.MoveAndDialog(pos=(-7161, 4808), dialog_id=0x84, log=True),
                BT.DialogAtXY(pos=(-7161, 4808), dialog_id=0x825407),
                BT.DialogAtXY(pos=(-7161, 4808), dialog_id=0x827801),
            ])
        else:
            select_2nd = BT.Sequence(name="Select 2nd Profession (Default)", children=[
                BT.DialogAtXY(pos=(-7161, 4808), dialog_id=0x88),
                BT.DialogAtXY(pos=(-7161, 4808), dialog_id=0x825407),
                BT.DialogAtXY(pos=(-7161, 4808), dialog_id=0x827801),
            ])

        return BT.Sequence(
            name="Quest: Secondary Training",
            children=[
                BT.Travel(target_map_id=KAMADAN, log=True),
                BT.LeaveParty(),
                BT.MoveAndDialog(pos=(-7910, 9740), dialog_id=0x825901, log=True),
                BT.MoveAndDialog(pos=(-7525, 6288), dialog_id=0x84, log=True),
                BT.WaitForMapToChange(map_id=456),
                ConfigurePacifistEnv(),
                trainer_dialog,
                BT.MoveAndDialog(
                    pos=(-7161, 4808), dialog_id=0x825907, log=True),
                select_2nd,
            ],
        )

    return BT.Subtree(
        name="Quest: Secondary Training",
        subtree_fn=_resolve,
    )


def _secondary_training_nodes() -> BehaviorTree:
    """Build the GTOB trainer-dialog sequence for the primary profession.

    Classic Unlock_Remaining_Secondary_Professions() calls
    Dialogs.WithModel(201, dialog_id) for every profession trainer except the
    character's own primary.
    """
    PROFESSION_TRAINERS: dict[str, int] = {
        "Warrior": 0x184,
        "Ranger": 0x284,
        "Monk": 0x384,
        "Necromancer": 0x484,
        "Mesmer": 0x584,
        "Elementalist": 0x684,
        "Assassin": 0x784,
        "Ritualist": 0x884,
        "Paragon": 0x984,
        "Dervish": 0xA84,
    }
    ALL_TRAINERS = [0x184, 0x284, 0x384, 0x484, 0x584,
                   0x684, 0x784, 0x884, 0x984, 0xA84]

    def _resolve(_node: BehaviorTree.Node) -> BehaviorTree:
        primary = _profession_name()
        skip = PROFESSION_TRAINERS.get(primary)
        children: list[BehaviorTree | BehaviorTree.Node] = [
            BT.Travel(target_map_id=GTOB, log=True),
            BT.EqualizeGold(5000),
            BT.Move(pos=(-3151.22, -7255.13)),
        ]
        for dialog_id in ALL_TRAINERS:
            if dialog_id == skip:
                continue
            children.append(
                BT.TargetAndDialogByModelID(201, dialog_id, log=True))
        return BT.Sequence(
            name="Unlock Remaining Secondary Professions",
            children=children,
        )

    return BT.Subtree(
        name="Unlock Remaining Secondary Professions",
        subtree_fn=_resolve,
    )


# ============================================================================
# Execution steps registration
# ============================================================================

def get_execution_steps() -> list[tuple[str, Callable[[], BehaviorTree]]]:
    """Returns the ordered (step_name, builder) list consumed by the BT runtime."""
    from Py4GWCoreLib.Agent import Agent

    steps: list[tuple[str, Callable[[], BehaviorTree]]] = [
        ("Skip Tutorial", SkipTutorial),
        ("Into Chahbek Village", IntoChahbekVillage),
        ("Quiz the Recruits", QuizTheRecruits),
        ("Never Fight Alone", NeverFightAlone),
        ("Chahbek Village Mission", ChahbekVillageMission),
        ("Primary Training", PrimaryTraining),
        ("A Personal Vault", APersonalVault),
        ("Extend Inventory Space", ExtendInventorySpace),
        # Armored_Transport is intentionally skipped (classic was commented out).
        ("Material Girl", MaterialGirl),
        ("Hog Hunt", HogHunt),
        ("To Champions Dawn", ToChampionsDawn),
        ("Quality Steel", QualitySteel),
        ("Attribute Points Quest 1", AttributePointsQuest1),
        ("Craft First Weapon", CraftFirstWeapon),
        # Missing_Shipment is intentionally skipped (classic was commented out).
        ("Proof of Courage and Suwash the Pirate", ProofOfCourageAndSuwashThePirate),
        ("A Hidden Threat", AHiddenThreat),
        ("Identity Theft", IdentityTheft),
        ("Configure Player Build", ConfigurePlayerBuild),
        ("Honing Your Skills", HoningYourSkills),
        ("Command Training", CommandTraining),
        ("Secondary Training", SecondaryTraining),
        ("Leaving A Legacy", LeavingALegacy),
    ]

    # Equipment crafting
    steps.append(("Craft Player Armor", CraftPlayerArmor))
    steps.append(("Craft Player Weapon", CraftPlayerWeapon))
    steps.append(("Destroy Starter Armor", DestroyStarterArmorAndUselessItems))

    # Leveling
    steps.append(("Farm Until Level 10", FarmUntilLevel10))
    steps.append(("To Consulate Docks", ToConsulateDocks))
    steps.append(("Unlock Remaining Secondary Professions", UnlockRemainingSecondaryProfessions))
    steps.append(("Unlock Mercenary Heroes", UnlockMercenaryHeroes))
    steps.append(("Unlock Xunlai Material Storage", UnlockXunlaiMaterialStorage))
    steps.append(("Attribute Points Quest 2", AttributePointsQuest2))
    steps.append(("Unlock Sunspear Skills", UnlockSunspearSkills))

    # Eye of the North expansion
    steps.append(("Unlock M.O.X.", UnlockMOX))
    steps.append(("To Boreal Station", ToBorealStation))
    steps.append(("To Eye Of The North Outpost", ToEyeOfTheNorthOutpost))
    steps.append(("Unlock Eye Of The North Pool", UnlockEyeOfTheNorthPool))
    steps.append(("To Gunnar's Hold", ToGunnarsHold))
    steps.append(("Unlock Kilroy Stonekin", UnlockKilroyStonekin))

    # Factions content
    steps.append(("To Kaineng Center", ToKainengCenter))
    steps.append(("To Marketplace", ToMarketplace))
    steps.append(("To Seitung Harbor", ToSeitungHarbor))
    steps.append(("To Shinjea Monastery", ToShinjeaMonastery))
    steps.append(("To Tsumei Village", ToTsumeiVillage))
    steps.append(("To Minister Cho", ToMinisterCho))

    # Prophecies content
    steps.append(("To Lion's Arch", ToLionsArch))
    steps.append(("Unlock Olias", UnlockOlias))

    # Temple of the Ages — Dervish / Ranger only (matches classic profession gate)
    primary, _ = Agent.GetProfessionNames(Player.GetAgentID())
    if primary in ["Dervish", "Ranger"]:
        steps.append(("To Temple Of The Ages", ToTempleOfTheAges))

    return steps


# ============================================================================
# Widget wiring
# ============================================================================

def main() -> None:
    global initialized

    if not initialized:
        ensure_botting_tree()
        initialized = True

    tree = ensure_botting_tree()
    tree.tick()
    tree.UI.draw_window(
        icon_path=ICON_PATH,
        main_child_dimensions=(500, 350),
    )


def tooltip() -> str:
    return MODULE_NAME + " - Nightfall storyline leveling bot (BT)."

