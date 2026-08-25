from __future__ import annotations

from collections.abc import Callable, Sequence
import os
import time

import PySystem

from Py4GWCoreLib import Agent, AgentArray, Player, Party, Map, GLOBAL_CACHE, Inventory, SharedCommandType, ImGui
from Py4GWCoreLib.BottingTree import BottingTree
from Py4GWCoreLib.ImGui_src.types import Alignment
from Py4GWCoreLib.py4gwcorelib_src.Color import Color
from Py4GWCoreLib.py4gwcorelib_src.Settings import Settings
from Py4GWCoreLib.Listeners import Listeners
from Py4GWCoreLib.enums_src.GameData_enums import Range
from Py4GWCoreLib.enums_src.Model_enums import ModelID
from Py4GWCoreLib.enums_src.Player_enums import PlayerStatus
from Py4GWCoreLib.native_src.internals.types import Vec2f
from Py4GWCoreLib.py4gwcorelib_src.BehaviorTree import BehaviorTree
from Py4GWCoreLib.routines_src.behaviourtrees_src.constants.lists import CONSET_UPKEEPS, CONSUMABLE_UPKEEPS as ALL_CONSUMABLE_UPKEEPS
from Py4GWCoreLib.routines_src.behaviourtrees_src.items import BTItems
from Py4GWCoreLib.routines_src.behaviourtrees_src.shared import BTShared
from Py4GWCoreLib.HeroAI.command_api import HeroAICommandAPI
from Sources.ApoSource.ApoBottingLib import wrappers as BT
from Widgets.System.Messaging import get_inventory_count, reset_inventory_count, get_inventory_state, reset_inventory_state
import PyImGui


PathPoint = Vec2f | tuple[float, float] | tuple[int, int]


# =============================================================================
# Metadata
# =============================================================================

MODULE_NAME = "Oola's Lab BT"
MODULE_CATEGORY = "Automation"
MODULE_TAGS = ["Oola's Lab", "Dungeon", "EotN"]
MODULE_ALIASES = ["Oola", "Oolas Lab"]
MODULE_DESCRIPTION = """Fully automated multibox BottingTree run for Oola's Lab.

The bot uses the Shards of Orr BT framework for multibox party control, quest
handling, consumables, inventory maintenance, MerchantRules and persistent
statistics, while keeping Oola's Lab route, keys, Flux Matrix mechanic and
final chest logic.
"""

INI_PATH = "Widgets/Automation/Bots/Missions/Dungeons/Oolas Lab BT"
INI_FILENAME = "Oolas_Lab_BT.ini"
TEXTURE = os.path.join(PySystem.Console.get_projects_path(), "Assets", "Textures", "Module_Icons", "Oola.png")
MODULE_ICON = "Assets\\Textures\\Module_Icons\\Oola.png"


# =============================================================================
# Game identifiers
# =============================================================================

RATA_SUM = 640
MAGUS_STONES = 569
OOLA_LEVEL_1 = 578
OOLA_LEVEL_2 = 579
OOLA_LEVEL_3 = 580

LITTLE_WORKSHOP_OF_HORRORS = 827  # 0x33B
DWARVEN_BLESSING_DIALOG = 0x84

DUNGEON_KEY_MODEL_ID = 25410
OOLA_PARTY_HERO_IDS = [4, 21, 1, 15]  # Master of Whispers, Livia, Norgu, Razah
FLUX_MATRIX_MODEL_ID = 22782
FLUX_GOLEM_MODEL_ID = 6885  # Malfunctioning Enduring Golem

# Force a fresh Rata Sum instance before resolving/retaking the quest.
# We toggle between Europe English 1 and America English 1 so a restart or
# repeated run can never remain in the exact same district instance.
QUEST_REFRESH_EU_REGION = 2
QUEST_REFRESH_US_REGION = 0
QUEST_REFRESH_DISTRICT = 1
QUEST_REFRESH_LANGUAGE = 0

# Original Oola AutoIt summoning-stone priority, executed through the current
# BTItems.UseConsumable helper rather than the legacy inventory code.
SUMMON_MODEL_IDS = (37810,30209,31155)


# =============================================================================
# Runtime configuration / persistent state (SoO framework)
# =============================================================================

_SETTINGS_SECTION = "Settings"
_STATS_SECTION = "Statistics"
_STORM_DROPS_SECTION = "Storm Daggers Drops"
_STORM_SNAPSHOT_SECTION = "Storm Daggers Snapshot"
_STORM_RUN_SECTION = "Storm Daggers Run"
_CHAR_NAMES_SECTION = "Character Names"

_INVENTORY_QUERY_POLL_MS = 200
_INVENTORY_QUERY_TIMEOUT_MS = 10_000

_settings_ini = Settings(f"{INI_PATH}/{INI_FILENAME}", "global")
_settings_loaded = False
_statistics_loaded = False

_use_hard_mode = True
_restock_conset = True
_activate_conset = True
_restock_pcons = True
_activate_pcons = True
_use_summoning_stone = True
_inventory_maintenance_enabled = True
_inventory_min_free_slots = 5
_inventory_min_id_kits = 1
_inventory_min_salvage_kits = 2
_runtime_consumables_enabled = True
_runtime_looting_enabled = True
_inventory_status_snapshot: dict[str, dict[str, object]] = {}

PCON_UPKEEPS = tuple(int(model_id) for model_id in ALL_CONSUMABLE_UPKEEPS if int(model_id) not in CONSET_UPKEEPS)
CONSET_RESTOCK_ITEMS: tuple[tuple[int, int], ...] = tuple((int(model_id), 10) for model_id in CONSET_UPKEEPS)
PCON_RESTOCK_ITEMS: tuple[tuple[int, int], ...] = tuple((int(model_id), 10) for model_id in PCON_UPKEEPS)
SUMMON_RESTOCK_ITEMS: tuple[tuple[int, int], ...] = tuple((int(model_id), 10) for model_id in SUMMON_MODEL_IDS)

STORM_DAGGERS_MODEL_ID = int(ModelID.Storm_Daggers.value)
INVENTORY_BAG_IDS = frozenset((1, 2, 3, 4))
ID_KIT_MODEL_IDS = (int(ModelID.Superior_Identification_Kit.value),)
SALVAGE_KIT_MODEL_IDS = (int(ModelID.Superior_Salvage_Kit.value),)
MERCHANT_RULES_WIDGET_NAME = "MerchantRules"
INVENTORY_PLUS_WIDGET_NAME = "InventoryPlus"
# MerchantRules maintenance is deliberately executed in Eye of the North.
# Map 642 has explicit MerchantRules service selectors and the merchant is
# available immediately after loading the outpost, unlike the Rata Sum spawn.
INVENTORY_MAINTENANCE_OUTPOST = 642
INVENTORY_TRAVEL_REGION = 2
INVENTORY_TRAVEL_DISTRICT = 1
INVENTORY_TRAVEL_LANGUAGE = 0
INVENTORY_MAINTENANCE_RETRY_COUNT = 2
INVENTORY_SNAPSHOT_SETTLE_MS = 2_000
INVENTORY_TRAVEL_TIMEOUT_MS = 60_000
INVENTORY_MERCHANT_TIMEOUT_MS = 240_000
INVENTORY_MERCHANT_POST_TRAVEL_DELAY_MS = 10_000

_total_runs = 0
_total_run_time = 0.0
_fastest_run = float("inf")
_slowest_run = 0.0
_l1_total_time = 0.0
_l1_fastest = float("inf")
_l1_slowest = 0.0
_l2_total_time = 0.0
_l2_fastest = float("inf")
_l2_slowest = 0.0
_l3_total_time = 0.0
_l3_fastest = float("inf")
_l3_slowest = 0.0
_storm_drops: dict[str, int] = {}
_char_names: dict[str, str] = {}
_session_runs = 0
_session_storm: dict[str, int] = {}
_scramble_accounts = False
_t_run_start = 0.0
_t_l2_start = 0.0
_t_l3_start = 0.0
_current_run_time = 0.0
_current_l1_time = 0.0
_current_l2_time = 0.0
_current_l3_time = 0.0

# =============================================================================
# Coordinates / routes from 13 - Oolas Lab.au3
# =============================================================================

OOLA_QUEST_NPC = Vec2f(16024.0, 18468.0)

RATA_EXIT_PATH = [
    Vec2f(15282.0, 16762.0),
    Vec2f(16466.0, 14159.0),
    Vec2f(16350.0, 13500.0),
]

MAGUS_ROUTE = [
    Vec2f(9577.0, 9084.0),
    Vec2f(7546.0, 11131.0),
    Vec2f(5679.0, 14051.0),
    Vec2f(2169.0, 13586.0),
    Vec2f(725.0, 14403.0),
    Vec2f(-2036.0, 12282.0),
    Vec2f(-8071.0, 13775.0),
    Vec2f(-11306.0, 16298.0),
    Vec2f(-18157.0, 12585.0),
    Vec2f(-19310.0, 8216.0),
]
OOLA_ENTRANCE_APPROACH = Vec2f(-20086.0, 8111.0)
OOLA_ENTRANCE_TRIGGER = Vec2f(-20270.0, 8080.0)

L1_BLESSING = Vec2f(18593.0, -2488.0)
L1_ROUTE = [
    Vec2f(16334.0, -1733.0),
    Vec2f(14113.0, -1109.0),
    Vec2f(11413.0, -240.0),
    Vec2f(9894.0, -470.0),
    Vec2f(7283.0, -125.0),
    Vec2f(5417.0, 1050.0),
    Vec2f(3916.0, 3131.0),
    Vec2f(6804.0, 4698.0),
    Vec2f(4373.0, 5661.0),
    Vec2f(1043.0, 5824.0),
    Vec2f(-1053.0, 7664.0),
    Vec2f(-1946.0, 8359.0),
    Vec2f(-1809.0, 11710.0),
    Vec2f(-2475.0, 13801.0),
    Vec2f(-6297.0, 15760.0),
    Vec2f(-8931.0, 16239.0),
    Vec2f(-12272.0, 14565.0),
    Vec2f(-14100.0, 12931.0),
    Vec2f(-17567.0, 7660.0),
    Vec2f(-16947.0, 5722.0),
    Vec2f(-15680.0, 2638.0),
    Vec2f(-14968.0, 1540.0),
]
L1_DUNGEON_LOCK = Vec2f(-16724.0, -889.0)
L1_EXIT_TRIGGER = Vec2f(-17600.0, -570.0)

L2_BLESSING = Vec2f(19087.0, -19809.0)
L2_ROUTE = [
    Vec2f(17841.0, -17192.0),
    Vec2f(18331.0, -13591.0),
    Vec2f(16783.0, -12647.0),
    Vec2f(14750.0, -13529.0),
    Vec2f(13199.0, -12214.0),
    Vec2f(10829.0, -11288.0),
    Vec2f(8812.0, -10670.0),
    Vec2f(6285.0, -9975.0),
    Vec2f(3112.0, -9392.0),
    Vec2f(3511.0, -11050.0),
    Vec2f(2008.0, -11783.0),
    Vec2f(327.0, -12874.0),
    Vec2f(-4523.0, -11588.0),
    Vec2f(-7009.0, -10386.0),
    Vec2f(-10242.0, -10288.0),
]

# Former point 16 from the old Level 2 route.  Keep this as a pure movement
# step with combat disabled immediately before the Flux Golem mechanic.
L2_PRE_FLUX_PATH = [
    Vec2f(-10237.0, -7304.0),
]

FLUX_APPROACH_PATH = [
    Vec2f(-10786.0, -8935.0),
    Vec2f(-9940.0, -10555.0),
]
L2_GOLEM_KEY_PICKUP = [
    Vec2f(-10890.95, -9301.77),
    Vec2f(-10464.18, -7148.66),
]
FLUX_LOADER = Vec2f(-7121.0, -9728.0)

L2_ROUTE_B = [
    Vec2f(-10786.0, -8935.0),
    Vec2f(-9940.0, -10555.0),
    Vec2f(-7428.0, -10507.0),
    Vec2f(-904.0, -14182.0),
    Vec2f(3759.0, -16951.0),
]
L2_BOSS_LOCK = Vec2f(4133.0, -17526.0)
L2_EXIT_ROUTE = [
    Vec2f(4449.0, -17209.0),
    Vec2f(6283.0, -19443.0),
    Vec2f(6785.0, -20737.0),
]
L2_EXIT_TRIGGER = Vec2f(6600.0, -21200.0)

L3_BLESSING = Vec2f(-14843.0, 8081.0)
L3_ROUTE = [
    Vec2f(-12231.0, 10347.0),
    Vec2f(-12898.0, 14540.0),
    Vec2f(-15512.0, 15773.0),
    Vec2f(-17266.0, 14435.0),
    Vec2f(-18527.0, 14353.0),
    Vec2f(-16969.0, 13183.0),
    Vec2f(-18092.0, 13489.0),
]
L3_FINAL_FIGHT_CENTER = Vec2f(-18092.0, 13489.0)
OOLA_FINAL_CHEST = Vec2f(-18550.0, 13076.0)


# =============================================================================
# Small helpers
# =============================================================================


class _PauseWhilePartyNotAliveNode(BehaviorTree.Node):
    """Freeze the current run step while any party member is dead.

    The child tree is deliberately *not* reset while blocked.  HeroAI and the
    BottingTree background services keep running, so resurrection/recovery can
    happen independently; once every party member is alive, the exact current
    child resumes from its previous runtime state.
    """

    def __init__(self, child: BehaviorTree | BehaviorTree.Node, *, name: str) -> None:
        super().__init__(
            name=name,
            node_type="PartyAliveGate",
            node_category="decorator",
        )
        self.child = self._coerce_node(child)
        self._blocked = False
        self._last_block_key = ""

    def get_children(self) -> list[BehaviorTree.Node]:
        return [self.child]

    def reset(self) -> None:
        super().reset()
        self.child.reset()
        self._blocked = False
        self._last_block_key = ""

    @staticmethod
    def _party_member_agent_ids() -> tuple[list[int], int]:
        """Return resolved player/hero/henchman agent IDs and expected party size."""
        try:
            if not Map.IsMapReady() or not Party.IsPartyLoaded():
                return [], 0

            expected_size = max(0, int(Party.GetPartySize() or 0))
            agent_ids: list[int] = []
            seen: set[int] = set()

            for player in Party.GetPlayers() or []:
                login_number = int(getattr(player, "login_number", 0) or 0)
                if login_number <= 0:
                    continue
                agent_id = int(Party.Players.GetAgentIDByLoginNumber(login_number) or 0)
                if agent_id > 0 and agent_id not in seen:
                    seen.add(agent_id)
                    agent_ids.append(agent_id)

            for member in (Party.GetHeroes() or []):
                agent_id = int(getattr(member, "agent_id", 0) or 0)
                if agent_id > 0 and agent_id not in seen:
                    seen.add(agent_id)
                    agent_ids.append(agent_id)

            for member in (Party.GetHenchmen() or []):
                agent_id = int(getattr(member, "agent_id", 0) or 0)
                if agent_id > 0 and agent_id not in seen:
                    seen.add(agent_id)
                    agent_ids.append(agent_id)

            return agent_ids, expected_size
        except Exception:
            return [], 0

    @staticmethod
    def _member_label(agent_id: int) -> str:
        try:
            name = str(Agent.GetNameByID(int(agent_id)) or "").strip()
            if name:
                return name
        except Exception:
            pass
        return f"agent {int(agent_id)}"

    def _tick_impl(self) -> BehaviorTree.NodeState:
        # During map loading, let the child continue handling its own transition.
        # The death gate applies to stable party state in the outpost exit / explorable run.
        try:
            map_ready = bool(Map.IsMapReady())
            party_loaded = bool(Party.IsPartyLoaded()) if map_ready else False
        except Exception:
            map_ready = False
            party_loaded = False

        if not map_ready or not party_loaded:
            if self.blackboard is not None:
                self.child.blackboard = self.blackboard
            return self.child.tick()

        member_ids, expected_size = self._party_member_agent_ids()

        # If the party is loaded but not every party member can be resolved yet,
        # do not advance the run until the party state is complete.
        if expected_size > 0 and len(member_ids) < expected_size:
            block_key = f"unresolved:{len(member_ids)}/{expected_size}"
            if self._last_block_key != block_key:
                PySystem.Console.Log(
                    MODULE_NAME,
                    (
                        "[PartyAlive] Pausing run progression: party state incomplete "
                        f"({len(member_ids)}/{expected_size} members resolved)."
                    ),
                    PySystem.Console.MessageType.Warning,
                )
                self._last_block_key = block_key
            self._blocked = True
            return BehaviorTree.NodeState.RUNNING

        dead_ids: list[int] = []
        for agent_id in member_ids:
            try:
                if Agent.IsDead(int(agent_id)):
                    dead_ids.append(int(agent_id))
            except Exception:
                continue

        if dead_ids:
            dead_labels = tuple(self._member_label(agent_id) for agent_id in dead_ids)
            block_key = "dead:" + "|".join(dead_labels)
            if self._last_block_key != block_key:
                PySystem.Console.Log(
                    MODULE_NAME,
                    (
                        "[PartyAlive] Pausing current run step until every party member "
                        f"is alive. Dead: {', '.join(dead_labels)}."
                    ),
                    PySystem.Console.MessageType.Warning,
                )
                self._last_block_key = block_key
            self._blocked = True
            return BehaviorTree.NodeState.RUNNING

        if self._blocked:
            PySystem.Console.Log(
                MODULE_NAME,
                "[PartyAlive] Every party member is alive. Resuming current run step.",
                PySystem.Console.MessageType.Success,
            )
            self._blocked = False
            self._last_block_key = ""

        if self.blackboard is not None:
            self.child.blackboard = self.blackboard
        return self.child.tick()


def _guard_run_step(
    step_name: str,
    factory: Callable[[], BehaviorTree],
) -> tuple[str, Callable[[], BehaviorTree]]:
    """Wrap one planner step with the per-tick party-alive gate."""

    def _build() -> BehaviorTree:
        child = factory()
        return BehaviorTree(
            _PauseWhilePartyNotAliveNode(
                child,
                name=f"Party Alive Guard - {step_name}",
            )
        )

    return step_name, _build


def _inside_oola() -> BehaviorTree:
    return BT.Selector(
        name="Inside Oola's Lab",
        children=[
            BT.IsCurrentMap(OOLA_LEVEL_1, log=False),
            BT.IsCurrentMap(OOLA_LEVEL_2, log=False),
            BT.IsCurrentMap(OOLA_LEVEL_3, log=False),
        ],
    )


def _map_guarded_point(
    name: str,
    map_id: int,
    child: BehaviorTree,
    skip_if_in_maps: Sequence[int] = (),
) -> BehaviorTree:
    """Same point-level resume pattern used by the current Shards of Orr BT."""
    branches: list[BehaviorTree] = [
        BT.Sequence(
            name=f"{name} - Active Map",
            children=[BT.IsCurrentMap(map_id=map_id, log=False), child],
        )
    ]

    for later_map_id in skip_if_in_maps:
        branches.append(
            BT.Sequence(
                name=f"{name} - Later Map {later_map_id}",
                children=[
                    BT.IsCurrentMap(map_id=later_map_id, log=False),
                    BT.Succeeder(f"{name}AlreadyPassed"),
                ],
            )
        )

    if len(branches) == 1:
        return branches[0]
    return BT.Selector(name=name, children=branches)


def _vanquish_point_steps(
    prefix: str,
    map_id: int,
    points: Sequence[PathPoint],
    *,
    clear_area_radius: float = Range.Spellcast.value,
    pause_on_combat: bool | None = None,
    move_tolerance: float = 500.0,
    skip_if_in_maps: Sequence[int] = (),
) -> list[tuple[str, Callable[[], BehaviorTree]]]:
    steps: list[tuple[str, Callable[[], BehaviorTree]]] = []

    for index, point in enumerate(points, start=1):
        name = f"{prefix} - Point {index:02d}"
        steps.append(
            (
                name,
                lambda point=point, name=name: _map_guarded_point(
                    name=name,
                    map_id=map_id,
                    child=BT.VanquishNode(
                        [point],
                        name=name,
                        clear_area_radius=clear_area_radius,
                        pause_on_combat=pause_on_combat,
                        move_tolerance=move_tolerance,
                        log=False,
                    ),
                    skip_if_in_maps=skip_if_in_maps,
                ),
            )
        )

    return steps


def _movement_point_steps(
    prefix: str,
    map_id: int,
    points: Sequence[PathPoint],
    *,
    pause_on_combat: bool = False,
    move_tolerance: float = 500.0,
    skip_if_in_maps: Sequence[int] = (),
    start_index: int = 1,
    disable_combat: bool = False,
) -> list[tuple[str, Callable[[], BehaviorTree]]]:
    """Point-level pure movement steps, optionally with HeroAI combat disabled."""
    steps: list[tuple[str, Callable[[], BehaviorTree]]] = []

    for index, point in enumerate(points, start=start_index):
        name = f"{prefix} - Point {index:02d}"

        def _build_step(
            point: PathPoint = point,
            name: str = name,
        ) -> BehaviorTree:
            movement = BT.Move(
                point,
                pause_on_combat=pause_on_combat,
                tolerance=move_tolerance,
                log=False,
            )

            if not disable_combat:
                return _map_guarded_point(
                    name=name,
                    map_id=map_id,
                    child=movement,
                    skip_if_in_maps=skip_if_in_maps,
                )

            return _map_guarded_point(
                name=name,
                map_id=map_id,
                child=BT.Sequence(
                    name=f"{name} - Combat Disabled",
                    children=[
                        BottingTree.DisableCombatTree(),
                        movement,
                    ],
                ),
                skip_if_in_maps=skip_if_in_maps,
            )

        steps.append((name, _build_step))

    return steps


def _repeat_until_success(
    name: str,
    child: BehaviorTree,
    timeout_ms: int,
) -> BehaviorTree:
    """Expose the core RepeaterUntilSuccessNode without creating a new BT system."""
    return BehaviorTree(
        BehaviorTree.RepeaterUntilSuccessNode(
            child=BT.Node(child),
            timeout_ms=timeout_ms,
            name=name,
        )
    )


def UseAvailableSummoningStone() -> BehaviorTree:
    if not _use_summoning_stone:
        return BT.Succeeder("SummoningStoneDisabled")

    return BT.Selector(
        name="Use Available Summoning Stone",
        children=[BTItems.UseConsumable(int(model_id)) for model_id in SUMMON_MODEL_IDS]
        + [BT.Succeeder("NoSummoningStoneAvailable")],
    )


def _optional_pickup_dungeon_key(
    name: str,
    timeout_ms: int = 1_500,
) -> BehaviorTree:
    """Best-effort Dungeon Key pickup.

    Dungeon Keys never enter inventory, so this node must never be used as a
    possession check. If HeroAI/LootFilter already collected the key, the
    targeted pickup simply times out quickly and the fallback succeeds.
    """
    return BT.Selector(
        name=name,
        children=[
            BT.PickupGroundItemByModelID(
                DUNGEON_KEY_MODEL_ID,
                max_distance=10_000.0,
                timeout_ms=timeout_ms,
                allow_unassigned=True,
                interaction_interval_ms=250,
                log=True,
            ),
            BT.Succeeder("DungeonKeyAlreadyCollectedOrUnavailable"),
        ],
    )


def _agent_player_number_or_model_id(agent_id: int) -> int:
    """Return the living agent PlayerNumber/ModelID used by Guild Wars NPCs."""

    getter = getattr(Agent, "GetPlayerNumber", None)
    if callable(getter):
        try:
            return int(getter(agent_id))
        except Exception:
            pass

    getter = getattr(Agent, "GetModelID", None)
    if callable(getter):
        try:
            return int(getter(agent_id))
        except Exception:
            pass

    get_agent = getattr(Agent, "GetAgentByID", None)
    if callable(get_agent):
        try:
            agent = get_agent(agent_id)
            candidates = (
                agent,
                getattr(agent, "living_agent", None),
                getattr(agent, "living", None),
            )
            for candidate in candidates:
                if candidate is None:
                    continue
                for attr_name in ("player_number", "model_id", "modelID"):
                    value = getattr(candidate, attr_name, None)
                    if value is not None:
                        return int(value)
        except Exception:
            pass

    return 0


def _scan_flux_golem(
    radius: float = Range.Compass.value,
) -> tuple[int, str, float | None]:
    """Find model 6885 inside Compass range around the player.

    Search the living-enemy array first, then dead enemies and finally the full
    agent array.  The extra arrays matter after a restart: a defeated golem can
    disappear from GetEnemyArray() before the planner resumes this named step.

    Returns:
        (agent_id, "alive" | "dead" | "unknown" | "missing", distance)
    """

    try:
        px, py = Player.GetXY()
        radius_sq = float(radius) * float(radius)

        candidate_ids: list[int] = []
        seen_ids: set[int] = set()

        for getter_name in ("GetEnemyArray", "GetDeadEnemyArray", "GetAgentArray"):
            getter = getattr(AgentArray, getter_name, None)
            if not callable(getter):
                continue

            try:
                array = getter() or []
            except Exception:
                continue

            for raw_agent_id in array:
                try:
                    agent_id = int(raw_agent_id)
                except Exception:
                    continue

                if agent_id <= 0 or agent_id in seen_ids:
                    continue

                seen_ids.add(agent_id)
                candidate_ids.append(agent_id)

        for agent_id in candidate_ids:
            try:
                if _agent_player_number_or_model_id(agent_id) != FLUX_GOLEM_MODEL_ID:
                    continue

                ax, ay = Agent.GetXY(agent_id)
                dx = float(ax) - float(px)
                dy = float(ay) - float(py)
                distance_sq = dx * dx + dy * dy

                if distance_sq > radius_sq:
                    continue

                distance = distance_sq ** 0.5

                if Agent.IsDead(agent_id):
                    return agent_id, "dead", distance

                if Agent.IsLiving(agent_id):
                    return agent_id, "alive", distance

                return agent_id, "unknown", distance

            except Exception:
                continue

    except Exception:
        pass

    return 0, "missing", None


def _new_flux_golem_state() -> dict[str, object]:
    return {
        "seen_alive": False,
        "missing_since": 0.0,
        "last_log_key": "",
    }


def _flux_log_once(
    state: dict[str, object],
    key: str,
    message: str,
    message_type=PySystem.Console.MessageType.Info,
) -> None:
    if str(state.get("last_log_key", "")) == key:
        return

    state["last_log_key"] = key
    PySystem.Console.Log(
        MODULE_NAME,
        f"[Flux] {message}",
        message_type,
    )


def _flux_golem_is_alive(
    state: dict[str, object],
) -> BehaviorTree:
    """Require model 6885 to be positively identified alive before Flux starts."""

    def _check(_node: BehaviorTree.Node) -> bool:
        agent_id, status, distance = _scan_flux_golem(Range.Compass.value)

        if status == "alive":
            state["seen_alive"] = True
            state["missing_since"] = 0.0
            _flux_log_once(
                state,
                "alive",
                f"Golem {FLUX_GOLEM_MODEL_ID} found alive: agent={agent_id}, distance={distance:.0f}. Flux mechanic required.",
            )
            return True

        if status == "dead":
            state["missing_since"] = 0.0
            _flux_log_once(
                state,
                "dead",
                f"Golem {FLUX_GOLEM_MODEL_ID} found dead: agent={agent_id}, distance={distance:.0f}.",
            )
            return False

        state["missing_since"] = 0.0
        _flux_log_once(
            state,
            f"not_alive_{status}",
            (
                f"Golem {FLUX_GOLEM_MODEL_ID} not confirmed alive inside Compass range "
                f"(status={status}). Refusing to skip the Flux step."
            ),
            PySystem.Console.MessageType.Warning,
        )
        return False

    return BehaviorTree(
        BehaviorTree.ConditionNode(
            name=f"Flux Golem {FLUX_GOLEM_MODEL_ID} Is Alive",
            condition_fn=_check,
        )
    )


def _flux_golem_is_finished(
    state: dict[str, object],
    missing_confirm_ms: int = 1_500,
) -> BehaviorTree:
    """Finish on an explicit dead golem or on a stable absence.

    The stable-absence branch is required for planner recovery.  If the script
    is restarted after the golem has already died, the newly-built BT has no
    in-memory ``seen_alive`` history and the corpse may already have vanished
    from every agent array.  In that case, remaining absent for the confirmation
    window is treated as "Flux already completed" instead of failing forever.
    """

    def _tick(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        now = time.monotonic()
        agent_id, status, distance = _scan_flux_golem(Range.Compass.value)

        if status == "alive":
            state["seen_alive"] = True
            state["missing_since"] = 0.0
            _flux_log_once(
                state,
                "alive",
                f"Golem {FLUX_GOLEM_MODEL_ID} found alive: agent={agent_id}, distance={distance:.0f}. Flux continues.",
            )
            return BehaviorTree.NodeState.FAILURE

        if status == "dead":
            state["missing_since"] = 0.0
            _flux_log_once(
                state,
                "dead",
                f"Golem {FLUX_GOLEM_MODEL_ID} confirmed dead: agent={agent_id}, distance={distance:.0f}. Flux complete.",
            )
            return BehaviorTree.NodeState.SUCCESS

        missing_since = float(state.get("missing_since", 0.0) or 0.0)
        if missing_since <= 0.0:
            state["missing_since"] = now

            if bool(state.get("seen_alive", False)):
                message = (
                    f"Golem {FLUX_GOLEM_MODEL_ID} disappeared after being seen alive "
                    f"(status={status}). Confirming absence for {missing_confirm_ms} ms."
                )
            else:
                message = (
                    f"Golem {FLUX_GOLEM_MODEL_ID} not found inside Compass range "
                    f"(status={status}). This may be a restart after the kill; "
                    f"confirming absence for {missing_confirm_ms} ms."
                )

            _flux_log_once(
                state,
                "missing_confirm",
                message,
                PySystem.Console.MessageType.Warning,
            )
            return BehaviorTree.NodeState.RUNNING

        elapsed_ms = (now - missing_since) * 1000.0
        if elapsed_ms < max(0, int(missing_confirm_ms)):
            return BehaviorTree.NodeState.RUNNING

        _flux_log_once(
            state,
            "missing_confirmed",
            (
                f"Golem {FLUX_GOLEM_MODEL_ID} absent for {int(elapsed_ms)} ms. "
                "Treating the Flux mechanic as already complete/recovered."
            ),
        )
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name=f"Flux Golem {FLUX_GOLEM_MODEL_ID} Is Finished",
            action_fn=_tick,
            aftercast_ms=100,
        )
    )


def _approach_flux_golem(
    state: dict[str, object],
    timeout_ms: int = 60_000,
    stop_distance: float = 150.0,
    missing_confirm_ms: int = 1_500,
) -> BehaviorTree:
    """Actively move to the Flux golem and stop next to it before DropBundle.

    ChangeTarget/Interact alone does not make Py4GW walk to a distant living
    agent.  This node therefore sends Player.Move() toward the golem's current
    coordinates while continuously refreshing the target position.
    """

    local_state = {
        "started": 0.0,
        "last_move": 0.0,
        "missing_since": 0.0,
        "cached_target_id": 0,
    }

    def _reset() -> None:
        local_state["started"] = 0.0
        local_state["last_move"] = 0.0
        local_state["missing_since"] = 0.0
        local_state["cached_target_id"] = 0

    def _cached_target_status() -> tuple[int, str, float | None]:
        """Keep using the already identified agent if GetEnemyArray jitters."""
        target_id = int(local_state.get("cached_target_id", 0) or 0)
        if target_id <= 0:
            return 0, "missing", None

        try:
            if _agent_player_number_or_model_id(target_id) != FLUX_GOLEM_MODEL_ID:
                return 0, "missing", None

            px, py = Player.GetXY()
            tx, ty = Agent.GetXY(target_id)
            dx = float(tx) - float(px)
            dy = float(ty) - float(py)
            distance = (dx * dx + dy * dy) ** 0.5

            if distance > Range.Compass.value:
                return 0, "missing", None
            if Agent.IsDead(target_id):
                return target_id, "dead", distance
            if Agent.IsLiving(target_id):
                return target_id, "alive", distance
        except Exception:
            pass

        return 0, "missing", None

    def _tick(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        now = time.monotonic()

        if local_state["started"] <= 0.0:
            local_state["started"] = now

        if (now - float(local_state["started"])) * 1000.0 >= timeout_ms:
            _flux_log_once(
                state,
                "approach_timeout",
                f"Timed out while approaching Golem {FLUX_GOLEM_MODEL_ID}.",
                PySystem.Console.MessageType.Warning,
            )
            _reset()
            return BehaviorTree.NodeState.FAILURE

        target_id, status, distance = _scan_flux_golem(Range.Compass.value)

        if status == "alive":
            local_state["cached_target_id"] = int(target_id)
        elif status != "dead":
            cached_id, cached_status, cached_distance = _cached_target_status()
            if cached_status != "missing":
                target_id, status, distance = cached_id, cached_status, cached_distance

        if status == "dead":
            _flux_log_once(
                state,
                "dead_during_approach",
                f"Golem {FLUX_GOLEM_MODEL_ID} died before bundle drop: agent={target_id}.",
            )
            _reset()
            return BehaviorTree.NodeState.SUCCESS

        if status != "alive":
            if not bool(state.get("seen_alive", False)):
                _flux_log_once(
                    state,
                    "approach_missing_before_seen",
                    (
                        f"Golem {FLUX_GOLEM_MODEL_ID} not found during approach (status={status}) "
                        f"and was never confirmed alive."
                    ),
                    PySystem.Console.MessageType.Warning,
                )
                _reset()
                return BehaviorTree.NodeState.FAILURE

            missing_since = float(local_state.get("missing_since", 0.0) or 0.0)
            if missing_since <= 0.0:
                local_state["missing_since"] = now
                _flux_log_once(
                    state,
                    "approach_missing_confirm",
                    (
                        f"Golem {FLUX_GOLEM_MODEL_ID} disappeared during approach. "
                        f"Waiting {missing_confirm_ms} ms to confirm."
                    ),
                    PySystem.Console.MessageType.Warning,
                )
                return BehaviorTree.NodeState.RUNNING

            if (now - missing_since) * 1000.0 < max(0, int(missing_confirm_ms)):
                return BehaviorTree.NodeState.RUNNING

            _flux_log_once(
                state,
                "approach_missing_confirmed",
                (
                    f"Golem {FLUX_GOLEM_MODEL_ID} remained absent during approach; "
                    "continuing to DropBundle cleanup."
                ),
            )
            _reset()
            return BehaviorTree.NodeState.SUCCESS

        state["seen_alive"] = True
        state["missing_since"] = 0.0
        local_state["missing_since"] = 0.0
        _flux_log_once(
            state,
            "approach_alive",
            f"Approaching Golem {FLUX_GOLEM_MODEL_ID}: agent={target_id}, distance={distance:.0f}.",
        )

        try:
            player_xy = Player.GetXY()
            tx, ty = Agent.GetXY(target_id)
        except Exception:
            return BehaviorTree.NodeState.RUNNING

        try:
            Player.ChangeTarget(target_id)
        except Exception:
            pass

        dx = float(tx) - float(player_xy[0])
        dy = float(ty) - float(player_xy[1])
        current_distance = (dx * dx + dy * dy) ** 0.5

        if current_distance <= float(stop_distance):
            _flux_log_once(
                state,
                "approach_reached",
                (
                    f"Reached Golem {FLUX_GOLEM_MODEL_ID} within {stop_distance:.0f} "
                    "units; dropping charged Flux Matrix."
                ),
            )
            _reset()
            return BehaviorTree.NodeState.SUCCESS

        # This is the important part: Interact() does not path to a distant
        # living target.  Refresh a real movement command toward the golem.
        if now - float(local_state["last_move"]) >= 0.25:
            try:
                Player.Move(float(tx), float(ty))
            except Exception:
                return BehaviorTree.NodeState.RUNNING
            local_state["last_move"] = now

        return BehaviorTree.NodeState.RUNNING

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name=f"Approach Flux Golem Model {FLUX_GOLEM_MODEL_ID}",
            action_fn=_tick,
            aftercast_ms=0,
        )
    )


# =============================================================================
# Bot initialization / preparation
# =============================================================================

initialized = False
botting_tree: BottingTree | None = None


def TravelToMagusStones() -> BehaviorTree:
    skip = BT.Sequence(
        name="Skip Rata Exit - Already Past It",
        children=[
            BT.Selector(
                name="Already In Magus Or Oola",
                children=[BT.IsCurrentMap(MAGUS_STONES, log=False), _inside_oola()],
            ),
            BT.Succeeder("RataExitAlreadyDone"),
        ],
    )

    normal = BT.Sequence(
        name="Leave Rata Sum",
        children=[
            BT.IsCurrentMap(RATA_SUM, log=True),
            BT.MoveAndExitMap(
                RATA_EXIT_PATH,
                target_map_id=MAGUS_STONES,
                timeout_ms=60_000,
                log=True,
            ),
            BT.WaitUntilOnExplorable(timeout_ms=30_000),
            BT.Wait(2_000),
        ],
    )

    return BT.Selector(name="Travel To Magus Stones", children=[skip, normal])


def MagusStonesStart() -> BehaviorTree:
    return _map_guarded_point(
        name="Magus Stones Start",
        map_id=MAGUS_STONES,
        child=BT.Sequence(
            name="Prepare Magus Stones Run",
            children=[UseAvailableSummoningStone()],
        ),
        skip_if_in_maps=(OOLA_LEVEL_1, OOLA_LEVEL_2, OOLA_LEVEL_3),
    )


def EnterOolasLab() -> BehaviorTree:
    name = "Enter Oola's Lab"
    return _map_guarded_point(
        name=name,
        map_id=MAGUS_STONES,
        child=BT.Sequence(
            name=f"{name} From Magus Stones",
            children=[
                BT.MoveAndKill(
                    OOLA_ENTRANCE_APPROACH,
                    clear_area_radius=Range.Spirit.value,
                    move_tolerance=500.0,
                    log=False,
                ),
                BT.MoveAndExitMap(
                    OOLA_ENTRANCE_TRIGGER,
                    target_map_id=OOLA_LEVEL_1,
                    timeout_ms=60_000,
                    log=True,
                ),
                BT.WaitUntilOnExplorable(timeout_ms=30_000),
                BT.Wait(2_000),
            ],
        ),
        skip_if_in_maps=(OOLA_LEVEL_1, OOLA_LEVEL_2, OOLA_LEVEL_3),
    )


# =============================================================================
# Level 1
# =============================================================================
def Level1_KeyLoot() -> BehaviorTree:
    return _map_guarded_point(
        name="Oola Level 1 Key Loot",
        map_id=OOLA_LEVEL_1,
        child=BT.Sequence(
            name="Optional Dungeon Key Pickup And Open Level 1 Lock",
            children=[
                BT.Move(Vec2f(-14968.0, 1540.0),),
                BT.Wait(5000),
                _optional_pickup_dungeon_key(
                                "Optional Level 1 Dungeon Key Pickup",
                                timeout_ms=5_000,
                            ),]))


def Level1_OpenLock() -> BehaviorTree:
    return _map_guarded_point(
        name="Oola Level 1 Open Dungeon Lock",
        map_id=OOLA_LEVEL_1,
        child=BT.Sequence(
            name="Optional Dungeon Key Pickup And Open Level 1 Lock",
            children=[
                BT.MoveAndInteractWithGadget(
                    pos=L1_DUNGEON_LOCK,
                    search_distance=1_000.0,
                    interaction_distance=Range.Nearby.value,
                    interaction_count=2,
                    interaction_interval_ms=1_000,
                    account_settle_ms=2_000,
                    timeout_ms=30_000,
                    pause_on_combat=False,
                    multi_account=False,
                    include_self=True,
                    log=True,
                ),
            ],
        ),
        skip_if_in_maps=(OOLA_LEVEL_2, OOLA_LEVEL_3),
    )


# =============================================================================
# Level 2 / Flux Matrix mechanic
# =============================================================================


def _flux_cycle(state: dict[str, object]) -> BehaviorTree:
    """One translation of AutoIt's LoadFlux -> GoToGolem -> DropBundle cycle."""
    return BT.Sequence(
        name="Load Flux And Drop It On Golem",
        children=[
            BT.PickupGroundItemByModelID(
                FLUX_MATRIX_MODEL_ID,
                max_distance=10_000.0,
                timeout_ms=30_000,
                allow_unassigned=True,
                interaction_interval_ms=500,
                log=True,
            ),
            BT.Wait(2_000),

            # Rejoindre le chargeur de Flux.
            BT.Move(
                FLUX_APPROACH_PATH,
                pause_on_combat=False,
                tolerance=250.0,
                log=False,
            ),

            BT.MoveAndInteractWithGadget(
                pos=FLUX_LOADER,
                search_distance=1_500.0,
                interaction_distance=Range.Nearby.value,
                interaction_count=1,
                interaction_interval_ms=500,
                account_settle_ms=1_000,
                timeout_ms=30_000,
                pause_on_combat=False,
                log=True,
            ),

            BT.Move(
                Vec2f(-10421.80, -9864.97),
                pause_on_combat=False,
                tolerance=250.0,
                log=False,
            ),
            _approach_flux_golem(
                state,
                timeout_ms=60_000,
                stop_distance=150.0,
            ),

            BT.DropBundle(log=True),
            BT.Wait(3_000),
        ],
    )



def Level2_FluxGolem() -> BehaviorTree:
    flux_state = _new_flux_golem_state()

    flux_iteration = BT.Sequence(
        name="Flux Golem Damage Iteration",
        children=[
            _flux_cycle(flux_state),
            _flux_golem_is_finished(flux_state),
        ],
    )

    clear_or_kill = BT.Selector(
        name="Clear Or Kill Flux Golem",
        children=[
            # Recovery case: explicit death, or stable absence for 1.5 s.
            # Stable absence lets a restart resume after the golem was already killed.
            _flux_golem_is_finished(flux_state),

            # If the golem is positively alive, start/repeat the Flux mechanic.
            BT.Sequence(
                name="Confirm Flux Golem Before Starting Mechanic",
                children=[
                    _flux_golem_is_alive(flux_state),
                    _repeat_until_success(
                        name="Repeat Flux Cycles Until Golem Dead",
                        child=flux_iteration,
                        timeout_ms=300_000,
                    ),
                ],
            ),
        ],
    )

    return _map_guarded_point(
        name="Oola Level 2 Flux Golem",
        map_id=OOLA_LEVEL_2,
        child=BT.Sequence(
            name="Flux Golem With HeroAI Combat Disabled",
            children=[
                # Re-assert this on every planner restart of the Flux step.
                BottingTree.DisableCombatTree(),

                clear_or_kill,

                # Once the golem is dead, move onto the Dungeon Key drop.
                BT.Move(
                    L2_GOLEM_KEY_PICKUP,
                    pause_on_combat=False,
                    tolerance=150.0,
                    log=False,
                ),

                BT.Wait(1_000),

                _optional_pickup_dungeon_key(
                    "Optional Level 2 Dungeon Key Pickup",
                    timeout_ms=1_500,
                ),

                # Combat resumes only once the Flux mechanic is finished.
                BottingTree.EnableCombatTree(),
            ],
        ),
        skip_if_in_maps=(OOLA_LEVEL_3,),
    )

def Level2_OpenDungeonLock() -> BehaviorTree:
    return _map_guarded_point(
        name="Oola Level 2 Open Dungeon Lock",
        map_id=OOLA_LEVEL_2,
        child=BT.MoveAndInteractWithGadget(
            pos=L2_BOSS_LOCK,
            search_distance=1_000.0,
            interaction_distance=Range.Nearby.value,
            interaction_count=2,
            interaction_interval_ms=1_000,
            account_settle_ms=2_000,
            timeout_ms=30_000,
            pause_on_combat=False,
            multi_account=False,
            include_self=True,
            log=True,
        ),
        skip_if_in_maps=(OOLA_LEVEL_3,),
    )

# =============================================================================
# Framework: settings / inventory / statistics / multibox
# =============================================================================

def _load_settings() -> None:
    global _settings_loaded
    global _use_hard_mode, _restock_conset, _activate_conset
    global _restock_pcons, _activate_pcons, _use_summoning_stone
    global _inventory_maintenance_enabled, _inventory_min_free_slots
    global _inventory_min_id_kits, _inventory_min_salvage_kits
    if _settings_loaded:
        _load_statistics()
        return
    _use_hard_mode = _settings_ini.get_bool(_SETTINGS_SECTION, "HardMode", True)
    _restock_conset = _settings_ini.get_bool(_SETTINGS_SECTION, "RestockConset", True)
    _activate_conset = _settings_ini.get_bool(_SETTINGS_SECTION, "ActivateConset", True)
    _restock_pcons = _settings_ini.get_bool(_SETTINGS_SECTION, "RestockPcons", True)
    _activate_pcons = _settings_ini.get_bool(_SETTINGS_SECTION, "ActivatePcons", True)
    _use_summoning_stone = _settings_ini.get_bool(_SETTINGS_SECTION, "UseSummoningStone", True)
    _inventory_maintenance_enabled = _settings_ini.get_bool(_SETTINGS_SECTION, "InventoryMaintenanceEnabled", True)
    _inventory_min_free_slots = max(0, _settings_ini.get_int(_SETTINGS_SECTION, "InventoryMinFreeSlots", 5))
    _inventory_min_id_kits = max(0, _settings_ini.get_int(_SETTINGS_SECTION, "InventoryMinIdKits", 1))
    _inventory_min_salvage_kits = max(0, _settings_ini.get_int(_SETTINGS_SECTION, "InventoryMinSalvageKits", 2))
    _settings_loaded = True
    _load_statistics()


def _save_settings() -> None:
    _settings_ini.set(_SETTINGS_SECTION, "HardMode", _use_hard_mode)
    _settings_ini.set(_SETTINGS_SECTION, "RestockConset", _restock_conset)
    _settings_ini.set(_SETTINGS_SECTION, "ActivateConset", _activate_conset)
    _settings_ini.set(_SETTINGS_SECTION, "RestockPcons", _restock_pcons)
    _settings_ini.set(_SETTINGS_SECTION, "ActivatePcons", _activate_pcons)
    _settings_ini.set(_SETTINGS_SECTION, "UseSummoningStone", _use_summoning_stone)
    _settings_ini.set(_SETTINGS_SECTION, "InventoryMaintenanceEnabled", _inventory_maintenance_enabled)
    _settings_ini.set(_SETTINGS_SECTION, "InventoryMinFreeSlots", _inventory_min_free_slots)
    _settings_ini.set(_SETTINGS_SECTION, "InventoryMinIdKits", _inventory_min_id_kits)
    _settings_ini.set(_SETTINGS_SECTION, "InventoryMinSalvageKits", _inventory_min_salvage_kits)


def _load_statistics() -> None:
    global _statistics_loaded, _total_runs, _total_run_time, _fastest_run, _slowest_run
    global _l1_total_time, _l1_fastest, _l1_slowest, _l2_total_time, _l2_fastest, _l2_slowest
    global _l3_total_time, _l3_fastest, _l3_slowest
    if _statistics_loaded:
        return
    _total_runs = _settings_ini.get_int(_STATS_SECTION, "total_runs", 0)
    _total_run_time = _settings_ini.get_float(_STATS_SECTION, "total_run_time", 0.0)
    v = _settings_ini.get_float(_STATS_SECTION, "fastest_run", 0.0); _fastest_run = float("inf") if v <= 0 else v
    _slowest_run = _settings_ini.get_float(_STATS_SECTION, "slowest_run", 0.0)
    for floor in (1,2,3):
        total = _settings_ini.get_float(_STATS_SECTION, f"l{floor}_total_time", 0.0)
        fastest = _settings_ini.get_float(_STATS_SECTION, f"l{floor}_fastest", 0.0)
        slowest = _settings_ini.get_float(_STATS_SECTION, f"l{floor}_slowest", 0.0)
        globals()[f"_l{floor}_total_time"] = total
        globals()[f"_l{floor}_fastest"] = float("inf") if fastest <= 0 else fastest
        globals()[f"_l{floor}_slowest"] = slowest
    for key in _settings_ini.items(_STORM_DROPS_SECTION).keys():
        if key != "local": _storm_drops[key] = _settings_ini.get_int(_STORM_DROPS_SECTION, key, 0)
    for section in (_STORM_SNAPSHOT_SECTION, _STORM_RUN_SECTION):
        for key in _settings_ini.items(section).keys():
            if key != "local": _storm_drops.setdefault(key, 0)
    for key in _settings_ini.items(_CHAR_NAMES_SECTION).keys():
        if key == "local": continue
        name = str(_settings_ini.get_str(_CHAR_NAMES_SECTION, key, "") or "").strip()
        if name: _char_names[key] = name
    _statistics_loaded = True


def _save_statistics() -> None:
    _settings_ini.set(_STATS_SECTION, "total_runs", _total_runs)
    _settings_ini.set(_STATS_SECTION, "total_run_time", _total_run_time)
    _settings_ini.set(_STATS_SECTION, "fastest_run", 0.0 if _fastest_run == float("inf") else _fastest_run)
    _settings_ini.set(_STATS_SECTION, "slowest_run", _slowest_run)
    for floor in (1,2,3):
        _settings_ini.set(_STATS_SECTION, f"l{floor}_total_time", globals()[f"_l{floor}_total_time"])
        fast = globals()[f"_l{floor}_fastest"]
        _settings_ini.set(_STATS_SECTION, f"l{floor}_fastest", 0.0 if fast == float("inf") else fast)
        _settings_ini.set(_STATS_SECTION, f"l{floor}_slowest", globals()[f"_l{floor}_slowest"])
    for key,total in _storm_drops.items():
        if key != "local": _settings_ini.set(_STORM_DROPS_SECTION, key, total)
    for key,name in _char_names.items():
        if key != "local": _settings_ini.set(_CHAR_NAMES_SECTION, key, name)


def _enabled_consumable_upkeeps() -> tuple[int, ...]:
    enabled: list[int] = []
    if _activate_conset: enabled.extend(int(x) for x in CONSET_UPKEEPS)
    if _activate_pcons: enabled.extend(PCON_UPKEEPS)
    return tuple(dict.fromkeys(enabled))


def _configure_runtime_upkeeps(
    *,
    consumables_enabled: bool | None = None,
    looting_enabled: bool | None = None,
) -> None:
    global _runtime_consumables_enabled, _runtime_looting_enabled

    if consumables_enabled is not None:
        _runtime_consumables_enabled = bool(consumables_enabled)

    if looting_enabled is not None:
        _runtime_looting_enabled = bool(looting_enabled)

    if botting_tree is None:
        return
    botting_tree.Config.ConfigureUpkeep(
        looting_enabled=_runtime_looting_enabled,
        resurrection_scroll=True,
        auto_inventory_handler_enabled=True,
        consumable_upkeeps=_enabled_consumable_upkeeps() if _runtime_consumables_enabled else (),
        enable_party_wipe_recovery=True,
        heroai_state_logging=False,
    )


def _runtime_consumable_upkeep_node(enabled: bool) -> BehaviorTree:
    def _apply(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        _configure_runtime_upkeeps(consumables_enabled=enabled)
        return BehaviorTree.NodeState.SUCCESS
    return BehaviorTree(
        BehaviorTree.ActionNode(
            name="Resume Consumables" if enabled else "Suspend Consumables",
            action_fn=_apply,
            aftercast_ms=0,
        )
    )


def _runtime_difficulty_node() -> BehaviorTree:
    return BT.Subtree(
        name="Apply Selected Difficulty",
        subtree_fn=lambda _node: BT.SetHardMode(
            _use_hard_mode,
            log=True,
        ),
    )


def _runtime_restock_node() -> BehaviorTree:
    def _build(_node: BehaviorTree.Node) -> BehaviorTree:
        items: list[tuple[int,int]] = []
        if _restock_conset: items.extend(CONSET_RESTOCK_ITEMS)
        if _restock_pcons: items.extend(PCON_RESTOCK_ITEMS)
        if _use_summoning_stone: items.extend(SUMMON_RESTOCK_ITEMS)
        return BT.RestockItemsFromList(tuple(items), allow_missing=True) if items else BT.Succeeder("RestockDisabled")
    return BT.Subtree(name="Restock Selected Consumables", subtree_fn=_build)


def _account_key(email: str) -> str:
    return str(email).replace("@", "_at_").replace(".", "_")


def _display_email(key: str) -> str:
    return str(key).replace("_at_", "@").replace("_", ".")


def _known_account_keys() -> list[str]:
    return sorted(k for k in (set(_storm_drops) | set(_session_storm)) if k and k != "local")


def _account_label(key: str) -> str:
    if not _scramble_accounts:
        return _char_names.get(key) or _display_email(key)

    keys = _known_account_keys()
    player_index = keys.index(key) + 1 if key in keys else 0
    return f"Player {player_index}"


def _shared_accounts() -> list[object]:
    try: accounts = GLOBAL_CACHE.ShMem.GetAllAccountData(sort_results=False, include_isolated=True)
    except TypeError: accounts = GLOBAL_CACHE.ShMem.GetAllAccountData()
    except Exception: accounts = []
    out=[]; seen=set()
    for account in accounts or []:
        email=str(getattr(account,"AccountEmail","") or "").strip()
        if email and email not in seen: seen.add(email); out.append(account)
    return out

def _inventory_accounts() -> list[object]:
    """Return the active accounts targeted by shared BT commands.

    Unlike the statistics view, inventory maintenance respects BottingTree
    account isolation so unrelated active clients are never moved or checked.
    """
    try:
        accounts = GLOBAL_CACHE.ShMem.GetAllAccountData(sort_results=False)
    except TypeError:
        accounts = GLOBAL_CACHE.ShMem.GetAllAccountData()
    except Exception:
        accounts = []

    unique: list[object] = []
    seen: set[str] = set()
    for account in accounts or []:
        email = str(getattr(account, "AccountEmail", "") or "").strip()
        if not email or email in seen:
            continue
        seen.add(email)
        unique.append(account)
    return unique


def _shared_account_label(account: object) -> str:
    agent_data = getattr(account, "AgentData", None)
    character_name = str(getattr(agent_data, 'CharacterName', '') or '').strip()
    if character_name:
        return character_name
    return str(getattr(account, "AccountEmail", "") or "Unknown account")


def _shared_account_map_id(account: object) -> int:
    agent_data = getattr(account, "AgentData", None)
    map_data = getattr(agent_data, "Map", None)
    return int(getattr(map_data, "MapID", 0) or 0)


def _shared_account_map_instance(account: object) -> tuple[int, int, int, int]:
    agent_data = getattr(account, "AgentData", None)
    map_data = getattr(agent_data, "Map", None)

    return (
        int(getattr(map_data, "MapID", 0) or 0),
        int(getattr(map_data, "Region", 0) or 0),
        int(getattr(map_data, "District", 0) or 0),
        int(getattr(map_data, "Language", 0) or 0),
    )


def _iter_shared_inventory_slots(account: object):
    """Yield mirrored slots only for diagnostic item listing.

    Threshold decisions do NOT use this SharedMemory snapshot. Capacity and
    free-slot counts are queried locally on each client through InventoryQuery.
    """
    inventory_bags = getattr(account, "InventoryBags", None)
    if inventory_bags is None:
        return

    for bag in inventory_bags.iter_bags():
        bag_id = int(getattr(bag, "BagID", 0) or 0)
        if bag_id not in INVENTORY_BAG_IDS:
            continue
        for slot in bag.Slots:
            yield bag_id, slot


def _local_inventory_state() -> tuple[int, int, int, int]:
    occupied, capacity = Inventory.GetInventorySpace()
    id_kits = sum(
        int(GLOBAL_CACHE.Inventory.GetModelCount(model_id))
        for model_id in ID_KIT_MODEL_IDS
    )
    salvage_kits = sum(
        int(GLOBAL_CACHE.Inventory.GetModelCount(model_id))
        for model_id in SALVAGE_KIT_MODEL_IDS
    )
    return int(occupied), int(capacity), int(id_kits), int(salvage_kits)


def _inventory_target_accounts() -> list[tuple[str, str]]:
    """Return every active account as (email, display label), including self."""
    targets: list[tuple[str, str]] = []
    seen: set[str] = set()

    for account in _inventory_accounts():
        email = str(getattr(account, "AccountEmail", "") or "").strip()
        if not email or email in seen:
            continue
        seen.add(email)
        targets.append((email, _shared_account_label(account)))

    local_email = str(Player.GetAccountEmail() or "").strip()
    if local_email and local_email not in seen:
        local_name = str(Player.GetName() or "").strip()
        targets.append((local_email, local_name or local_email))

    return targets


def _build_inventory_status(
    email: str,
    label: str,
    state: tuple[int, int, int, int] | None,
) -> dict[str, object]:
    if state is None:
        occupied = capacity = id_kits = salvage_kits = -1
    else:
        occupied, capacity, id_kits, salvage_kits = (int(value) for value in state)

    available = capacity > 0 and occupied >= 0 and occupied <= capacity
    free_slots = max(0, capacity - occupied) if available else 0

    return {
        "email": str(email),
        "label": str(label),
        "available": available,
        "capacity": capacity,
        "occupied": occupied,
        "free_slots": free_slots,
        "id_kits": id_kits,
        "salvage_kits": salvage_kits,
    }


def _inventory_account_statuses() -> list[dict[str, object]]:
    statuses: list[dict[str, object]] = []

    for raw_status in _inventory_status_snapshot.values():
        status = dict(raw_status)
        account_issues: list[str] = []

        if not bool(status.get("available", False)):
            account_issues.append("inventory query unavailable")
        else:
            free_slots = int(status.get("free_slots", 0) or 0)
            id_kits = int(status.get("id_kits", 0) or 0)
            salvage_kits = int(status.get("salvage_kits", 0) or 0)

            if _inventory_min_free_slots > 0 and free_slots < _inventory_min_free_slots:
                account_issues.append(f"free slots {free_slots}/{_inventory_min_free_slots}")
            if _inventory_min_id_kits > 0 and id_kits < _inventory_min_id_kits:
                account_issues.append(f"ID kits {id_kits}/{_inventory_min_id_kits}")
            if _inventory_min_salvage_kits > 0 and salvage_kits < _inventory_min_salvage_kits:
                account_issues.append(f"salvage kits {salvage_kits}/{_inventory_min_salvage_kits}")

        status["issues"] = account_issues
        statuses.append(status)

    return statuses


def _inventory_maintenance_issues() -> list[str]:
    statuses = _inventory_account_statuses()
    if not statuses:
        return ["No active account inventory query result is available."]

    return [
        f"{status['label']}: {', '.join(status['issues'])}"
        for status in statuses
        if status["issues"]
    ]


def _log_inventory_statuses(statuses: list[dict[str, object]]) -> None:
    if not statuses:
        PySystem.Console.Log(
            MODULE_NAME,
            "[Inventory] No active account inventory query result is available.",
            PySystem.Console.MessageType.Warning,
        )
        return

    for status in statuses:
        issues = list(status["issues"])
        result = "MAINTENANCE" if issues else "OK"
        if bool(status.get("available", False)):
            message = (
                f"[Inventory] {status['label']}: free={status['free_slots']}/{status['capacity']}, "
                f"occupied={status['occupied']}, Superior ID kits={status['id_kits']}, "
                f"Superior salvage kits={status['salvage_kits']} -> {result}"
            )
        else:
            message = f"[Inventory] {status['label']}: local inventory query unavailable -> {result}"

        PySystem.Console.Log(
            MODULE_NAME,
            message,
            PySystem.Console.MessageType.Warning if issues else PySystem.Console.MessageType.Info,
        )


def _query_all_inventory_states_node(
    name: str,
    *,
    timeout_ms: int=_INVENTORY_QUERY_TIMEOUT_MS,
) -> BehaviorTree:
    """Query real inventory state locally on every active Guild Wars client."""
    state: dict[str, object] = {
        "started": False,
        "request_id": "",
        "sender_email": "",
        "pending": {},
        "results": {},
        "started_at": 0.0,
    }

    def _reset() -> None:
        state["started"] = False
        state["request_id"] = ""
        state["sender_email"] = ""
        state["pending"] = {}
        state["results"] = {}
        state["started_at"] = 0.0

    def _finish() -> BehaviorTree.NodeState:
        global _inventory_status_snapshot
        _inventory_status_snapshot = dict(state["results"])
        _reset()
        return BehaviorTree.NodeState.SUCCESS

    def _start() -> None:
        request_id = f"oola_inventory_state_{int(time.monotonic() * 1000)}"
        sender_email = str(Player.GetAccountEmail() or "").strip()
        targets = _inventory_target_accounts()

        results: dict[str, dict[str, object]] = {}
        pending: dict[str, str] = {}

        for email, label in targets:
            if email == sender_email:
                try:
                    local_state = _local_inventory_state()
                except Exception as exc:
                    PySystem.Console.Log(
                        MODULE_NAME,
                        f"[Inventory] Local inventory query failed on {label}: {exc}",
                        PySystem.Console.MessageType.Error,
                    )
                    local_state = None
                results[email] = _build_inventory_status(email, label, local_state)
                continue

            if not sender_email:
                results[email] = _build_inventory_status(email, label, None)
                continue

            reset_inventory_state(email, request_id)
            GLOBAL_CACHE.ShMem.SendMessage(
                sender_email,
                email,
                SharedCommandType.InventoryQuery,
                (
                    float(ID_KIT_MODEL_IDS[0] if len(ID_KIT_MODEL_IDS) > 0 else 0),
                    float(ID_KIT_MODEL_IDS[1] if len(ID_KIT_MODEL_IDS) > 1 else 0),
                    float(SALVAGE_KIT_MODEL_IDS[0] if SALVAGE_KIT_MODEL_IDS else 0),
                    0.0,
                ),
                ("report_inventory_state", request_id, "", ""),
            )
            pending[email] = label

        state["started"] = True
        state["request_id"] = request_id
        state["sender_email"] = sender_email
        state["pending"] = pending
        state["results"] = results
        state["started_at"] = time.monotonic()

        PySystem.Console.Log(
            MODULE_NAME,
            f"[Inventory] Requested real inventory state from {len(targets)} active account(s).",
            PySystem.Console.MessageType.Info,
        )

    def _tick(node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        try:
            if bool(node.blackboard.get("USER_INTERRUPT_ACTIVE", False)):
                _reset()
                return BehaviorTree.NodeState.FAILURE

            if not bool(state["started"]):
                _start()

            pending: dict[str, str] = state["pending"]
            request_id = str(state["request_id"])

            for email in list(pending):
                reply = get_inventory_state(email, request_id)
                if reply is None:
                    continue
                label = pending.pop(email)
                state["results"][email] = _build_inventory_status(email, label, reply)

            if not pending:
                return _finish()

            elapsed_ms = int(
                (time.monotonic() - float(state["started_at"])) * 1000.0
            )
            if elapsed_ms < max(0, int(timeout_ms)):
                return BehaviorTree.NodeState.RUNNING

            for email, label in list(pending.items()):
                state["results"][email] = _build_inventory_status(email, label, None)
                PySystem.Console.Log(
                    MODULE_NAME,
                    f"[Inventory] Real inventory query timed out for {label}.",
                    PySystem.Console.MessageType.Warning,
                )
            pending.clear()
            return _finish()

        except Exception as exc:
            PySystem.Console.Log(
                MODULE_NAME,
                f"[Inventory] Multibox inventory-state query failed: {exc}",
                PySystem.Console.MessageType.Error,
            )
            return _finish()

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name=name,
            action_fn=_tick,
            aftercast_ms=_INVENTORY_QUERY_POLL_MS,
        )
    )


def _inventory_recipient_emails() -> list[str]:
    """Return every currently active account that must receive maintenance."""
    return [email for email, _label in _inventory_target_accounts()]


def _inventory_maintenance_trigger_node() -> BehaviorTree:
    def _log(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        statuses = _inventory_account_statuses()
        trigger_labels = [str(status["label"]) for status in statuses if status["issues"]]
        recipients = _inventory_recipient_emails()
        trigger_text = ", ".join(trigger_labels) if trigger_labels else "inventory verification"
        recipient_text = ", ".join(
            str(status["label"])
            for status in statuses
            if str(status["email"]) in recipients
        )
        PySystem.Console.Log(
            MODULE_NAME,
            (
                f"[Inventory] Maintenance triggered by: {trigger_text}. "
                f"MerchantRules will run on ALL {len(recipients)} active account(s)"
                + (f": {recipient_text}." if recipient_text else ".")
            ),
            PySystem.Console.MessageType.Warning,
        )
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name="Log Collective Inventory Maintenance Trigger",
            action_fn=_log,
            aftercast_ms=0,
        )
    )



def _inventory_model_label(model_id: int) -> str:
    try:
        return str(ModelID(int(model_id)).name)
    except Exception:
        return f"model_{int(model_id)}"


def _log_unhealthy_inventory_contents() -> None:
    """Log mirrored item contents for accounts that still fail local-query thresholds."""
    status_by_email = {
        str(status["email"]): status
        for status in _inventory_account_statuses()
        if status["issues"]
    }

    for account in _inventory_accounts():
        email = str(getattr(account, "AccountEmail", "") or "").strip()
        status = status_by_email.get(email)
        if status is None:
            continue

        label = str(status["label"])
        entries: list[str] = []
        for bag_id, slot in _iter_shared_inventory_slots(account):
            model_id = int(getattr(slot, "ModelID", 0) or 0)
            quantity = int(getattr(slot, "Quantity", 0) or 0)
            if model_id <= 0 or quantity <= 0:
                continue
            slot_no = int(getattr(slot, "Slot", 0) or 0)
            entries.append(
                f"B{bag_id}:S{slot_no} {_inventory_model_label(model_id)}({model_id}) x{quantity}"
            )

        if bool(status.get("available", False)):
            PySystem.Console.Log(
                MODULE_NAME,
                (
                    f"[Inventory diagnostic] {label}: "
                    f"free={status['free_slots']}/{status['capacity']}, "
                    f"Superior ID kits={status['id_kits']}, "
                    f"Superior salvage kits={status['salvage_kits']}, "
                    f"mirrored occupied items={len(entries)}."
                ),
                PySystem.Console.MessageType.Warning,
            )
        else:
            PySystem.Console.Log(
                MODULE_NAME,
                f"[Inventory diagnostic] {label}: local inventory query unavailable; mirrored occupied items={len(entries)}.",
                PySystem.Console.MessageType.Warning,
            )

        chunk_size = 8
        for start_index in range(0, len(entries), chunk_size):
            PySystem.Console.Log(
                MODULE_NAME,
                f"[Inventory diagnostic] {label}: "
                + " | ".join(entries[start_index:start_index + chunk_size]),
                PySystem.Console.MessageType.Info,
            )



def _inventory_is_healthy_node(
    name: str,
    *,
    log_success: bool = True,
) -> BehaviorTree:
    def _check(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        statuses = _inventory_account_statuses()
        _log_inventory_statuses(statuses)

        if not statuses:
            PySystem.Console.Log(
                MODULE_NAME,
                (
                    "Inventory maintenance required - "
                    "no active account inventory snapshot is available."
                ),
                PySystem.Console.MessageType.Warning,
            )
            return BehaviorTree.NodeState.FAILURE

        issues = [
            f"{status['label']}: {', '.join(status['issues'])}"
            for status in statuses
            if status["issues"]
        ]

        if issues:
            PySystem.Console.Log(
                MODULE_NAME,
                "Inventory maintenance required - " + "; ".join(issues),
                PySystem.Console.MessageType.Warning,
            )
            return BehaviorTree.NodeState.FAILURE

        if log_success:
            PySystem.Console.Log(
                MODULE_NAME,
                "Inventory check passed on every active account.",
                PySystem.Console.MessageType.Success,
            )

        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ConditionNode(
            name=name,
            condition_fn=_check,
        )
    )


def _all_accounts_on_map(map_id: int) -> bool:
    accounts = _inventory_accounts()
    return bool(accounts) and all((_shared_account_map_id(account) == int(map_id) for account in accounts))


def _all_accounts_on_map_instance(map_id: int, region: int, district: int, language: int) -> bool:
    expected = (int(map_id), int(region), int(district), int(language))
    accounts = _inventory_accounts()
    return bool(accounts) and all((_shared_account_map_instance(account) == expected for account in accounts))


def _all_accounts_on_map_node(map_id: int, name: str) -> BehaviorTree:
    return BehaviorTree(BehaviorTree.ConditionNode(name=name, condition_fn=lambda _node: _all_accounts_on_map(map_id)))


def _wait_for_all_accounts_on_map(map_id: int, *, name: str, timeout_ms: int=INVENTORY_TRAVEL_TIMEOUT_MS) -> BehaviorTree:
    def _check(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        if _all_accounts_on_map(map_id):
            return BehaviorTree.NodeState.SUCCESS
        return BehaviorTree.NodeState.RUNNING

    return BehaviorTree(BehaviorTree.WaitUntilNode(name=name, condition_fn=_check, throttle_interval_ms=500, timeout_ms=timeout_ms))


def _wait_for_all_accounts_on_inventory_instance(map_id: int, *, name: str, timeout_ms: int=INVENTORY_TRAVEL_TIMEOUT_MS) -> BehaviorTree:
    def _check(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        if _all_accounts_on_map_instance(map_id, INVENTORY_TRAVEL_REGION, INVENTORY_TRAVEL_DISTRICT, INVENTORY_TRAVEL_LANGUAGE):
            return BehaviorTree.NodeState.SUCCESS
        return BehaviorTree.NodeState.RUNNING

    return BehaviorTree(BehaviorTree.WaitUntilNode(name=name, condition_fn=_check, throttle_interval_ms=500, timeout_ms=timeout_ms))


def _send_widget_state(
    widget_name: str,
    *,
    enabled: bool,
    refs_key: str,
) -> BehaviorTree:
    command = (
        SharedCommandType.EnableWidget
        if enabled
        else SharedCommandType.DisableWidget
    )

    return BTShared.SendAndWait(
        command=command,
        extra_data=(widget_name, "", "", ""),
        include_self=True,
        refs_blackboard_key=refs_key,
        timeout_ms=20_000,
        poll_interval_ms=100,
        log=True,
    )


def _set_local_auto_inventory_handler(enabled: bool) -> BehaviorTree:
    def _set(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        if botting_tree is None:
            return BehaviorTree.NodeState.SUCCESS

        fn = getattr(botting_tree, "SetAutoInventoryHandlerEnabled", None)
        if fn is None:
            return BehaviorTree.NodeState.SUCCESS

        try:
            fn(enabled)
        except Exception:
            pass

        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name=(
                "Enable Local Auto Inventory Handler"
                if enabled
                else "Disable Local Auto Inventory Handler"
            ),
            action_fn=_set,
            aftercast_ms=0,
        )
    )


def _travel_all_accounts_to_rata(attempt_key: str) -> BehaviorTree:
    return BT.Sequence(
        name="Travel Every Account To Rata Sum",
        children=[
            BTShared.SendAndWait(
                command=SharedCommandType.TravelToMap,
                params=(
                    float(RATA_SUM),
                    float(INVENTORY_TRAVEL_REGION),
                    float(INVENTORY_TRAVEL_DISTRICT),
                    float(INVENTORY_TRAVEL_LANGUAGE),
                ),
                include_self=True,
                refs_blackboard_key=f"{attempt_key}_travel_rata_refs",
                timeout_ms=INVENTORY_TRAVEL_TIMEOUT_MS,
                poll_interval_ms=250,
                log=True,
            ),
            _wait_for_all_accounts_on_inventory_instance(
                RATA_SUM,
                name="Wait For Every Account In Rata Sum EU-English-1",
            ),
        ],
    )


def _travel_all_accounts_to_inventory_outpost(attempt_key: str) -> BehaviorTree:
    return BT.Sequence(
        name="Travel Every Account To Eye Of The North For Inventory Maintenance",
        children=[
            BTShared.SendAndWait(
                command=SharedCommandType.TravelToMap,
                params=(
                    float(INVENTORY_MAINTENANCE_OUTPOST),
                    float(INVENTORY_TRAVEL_REGION),
                    float(INVENTORY_TRAVEL_DISTRICT),
                    float(INVENTORY_TRAVEL_LANGUAGE),
                ),
                include_self=True,
                refs_blackboard_key=f"{attempt_key}_travel_inventory_outpost_refs",
                timeout_ms=INVENTORY_TRAVEL_TIMEOUT_MS,
                poll_interval_ms=250,
                log=True,
            ),
            _wait_for_all_accounts_on_inventory_instance(
                INVENTORY_MAINTENANCE_OUTPOST,
                name="Wait For Every Account In Eye Of The North EU-English-1",
            ),
        ],
    )


def _return_all_accounts_to_rata(attempt_key: str) -> BehaviorTree:
    currently_in_an_explorable = BT.Selector(
        name="Current Map Can Be Resigned",
        children=[
            BT.IsCurrentMap(map_id=MAGUS_STONES, log=False),
            BT.IsCurrentMap(map_id=OOLA_LEVEL_1, log=False),
            BT.IsCurrentMap(map_id=OOLA_LEVEL_2, log=False),
            BT.IsCurrentMap(map_id=OOLA_LEVEL_3, log=False),
        ],
    )

    resign_from_explorable = BT.Sequence(
        name="Resign Party To Rata Sum",
        children=[
            currently_in_an_explorable,
            BT.Resign(
                wait_for_map_load=True,
                target_map_id=RATA_SUM,
                multi_account=True,
                timeout_ms=INVENTORY_TRAVEL_TIMEOUT_MS,
                log=True,
            ),
            _wait_for_all_accounts_on_map(
                RATA_SUM,
                name="Wait For Party Return To Rata Sum",
            ),
        ],
    )

    return BT.Selector(
        name="Ensure Every Account Is In Rata Sum",
        children=[
            _all_accounts_on_map_node(
                RATA_SUM,
                "Every Account Already In Rata Sum",
            ),
            resign_from_explorable,
            _travel_all_accounts_to_rata(attempt_key),
        ],
    )


def _restore_inventoryplus_after_merchant(
    attempt_key: str,
) -> BehaviorTree:
    return BT.Sequence(
        name="Restore InventoryPlus After MerchantRules",
        children=[
            _send_widget_state(
                INVENTORY_PLUS_WIDGET_NAME,
                enabled=True,
                refs_key=f"{attempt_key}_enable_inventoryplus_refs",
            ),
            _set_local_auto_inventory_handler(True),
        ],
    )


def _merchant_stock_request_spec() -> str:
    """Encode this bot's desired carried Merchant Stock targets for MerchantRules."""
    targets: list[str] = []
    if _inventory_min_id_kits > 0 and ID_KIT_MODEL_IDS:
        targets.append(f"{int(ID_KIT_MODEL_IDS[0])}:{int(_inventory_min_id_kits)}")
    if _inventory_min_salvage_kits > 0 and SALVAGE_KIT_MODEL_IDS:
        targets.append(f"{int(SALVAGE_KIT_MODEL_IDS[0])}:{int(_inventory_min_salvage_kits)}")
    return "stock:" + ",".join(targets)


def _run_merchant_rules(attempt_key: str) -> BehaviorTree:
    def _build(_node: BehaviorTree.Node) -> BehaviorTree:
        recipients = _inventory_recipient_emails()

        if not recipients:
            PySystem.Console.Log(
                MODULE_NAME,
                "[Inventory] MerchantRules aborted: no active account recipients.",
                PySystem.Console.MessageType.Error,
            )
            return BehaviorTree(
                BehaviorTree.FailerNode(
                    name="No Active MerchantRules Recipients",
                )
            )

        request_id = (
            f"oola_inventory_{attempt_key}_"
            f"{int(time.monotonic() * 1000)}"
        )

        PySystem.Console.Log(
            MODULE_NAME,
            (
                "[Inventory] Dispatching MerchantRules to all "
                f"{len(recipients)} active account(s)."
            ),
            PySystem.Console.MessageType.Info,
        )

        execute = BTShared.SendAndWait(
            command=SharedCommandType.MerchantRules,
            params=(3.0, 0.0, 0.0, 0.0),
            extra_data=(
                request_id,
                _merchant_stock_request_spec(),
                "0",
                "0",
            ),
            recipients=recipients,
            include_self=True,
            refs_blackboard_key=f"{attempt_key}_merchant_rules_refs",
            timeout_ms=INVENTORY_MERCHANT_TIMEOUT_MS,
            poll_interval_ms=250,
            log=True,
        )

        success = BT.Sequence(
            name="MerchantRules Completed",
            children=[
                execute,
                _restore_inventoryplus_after_merchant(attempt_key),
            ],
        )

        failure = BT.Sequence(
            name="Restore InventoryPlus After MerchantRules Failure",
            children=[
                _restore_inventoryplus_after_merchant(
                    f"{attempt_key}_failure"
                ),
                BehaviorTree(
                    BehaviorTree.FailerNode(
                        name="Propagate MerchantRules Failure",
                    )
                ),
            ],
        )

        return BT.Selector(
            name="Execute MerchantRules And Restore InventoryPlus",
            children=[
                success,
                failure,
            ],
        )

    return BT.Subtree(
        name="Run MerchantRules On All Active Accounts",
        subtree_fn=_build,
    )


def _inventory_maintenance_attempt(
    attempt_number: int,
) -> BehaviorTree:
    """Run one MerchantRules attempt in Eye of the North, then return to Rata Sum."""

    attempt_key = f"inventory_attempt_{attempt_number}"

    return BT.Sequence(
        name=f"Inventory Maintenance Attempt {attempt_number}",
        children=[
            BT.LogMessage(
                message=(
                    f"Inventory maintenance attempt "
                    f"{attempt_number}/"
                    f"{INVENTORY_MAINTENANCE_RETRY_COUNT} in Eye of the North."
                ),
                module_name=MODULE_NAME,
            ),

            _set_local_auto_inventory_handler(False),

            _send_widget_state(
                INVENTORY_PLUS_WIDGET_NAME,
                enabled=False,
                refs_key=(
                    f"{attempt_key}_disable_inventoryplus_refs"
                ),
            ),

            # Rata Sum's merchant can be outside the loaded compass/agent range at
            # spawn. Eye of the North has explicit MerchantRules service selectors,
            # so perform the actual maintenance there.
            _travel_all_accounts_to_inventory_outpost(attempt_key),

            # Do not let MerchantRules initialize/execute during the map load.
            # With a nearly/full inventory, give Guild Wars and the shared-memory
            # inventory/agent snapshots a full 10 seconds to stabilize first.
            BT.LogMessage(
                message=(
                    "Eye of the North loaded on every account. "
                    "Waiting 10 seconds before MerchantRules takes over."
                ),
                module_name=MODULE_NAME,
            ),
            BT.Wait(INVENTORY_MERCHANT_POST_TRAVEL_DELAY_MS),

            _send_widget_state(
                MERCHANT_RULES_WIDGET_NAME,
                enabled=True,
                refs_key=(
                    f"{attempt_key}_enable_merchant_rules_refs"
                ),
            ),

            BT.Wait(1_000),

            _run_merchant_rules(attempt_key),

            # Oola's quest flow starts from Rata Sum, so always come back after
            # MerchantRules before inventory verification / party reconstruction.
            _return_all_accounts_to_rata(f"{attempt_key}_after_merchant"),

            BT.Wait(INVENTORY_SNAPSHOT_SETTLE_MS),

            _query_all_inventory_states_node(
                name=(
                    "Refresh Real Inventories After Attempt "
                    f"{attempt_number}"
                )
            ),

            _inventory_is_healthy_node(
                f"Verify Inventory After Attempt {attempt_number}",
                log_success=True,
            ),
        ],
    )


def _stop_for_inventory_failure_node() -> BehaviorTree:
    stopped = False

    def _stop(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        nonlocal stopped

        if stopped:
            return BehaviorTree.NodeState.RUNNING

        stopped = True

        issues = _inventory_maintenance_issues()
        issue_text = (
            "; ".join(issues)
            if issues
            else "unknown verification error"
        )

        PySystem.Console.Log(
            MODULE_NAME,
            (
                "Inventory maintenance failed twice. "
                "The bot was paused safely. "
                f"Remaining issue(s): {issue_text}"
            ),
            PySystem.Console.MessageType.Error,
        )

        _log_unhealthy_inventory_contents()

        if botting_tree is not None:
            fn = getattr(
                botting_tree,
                "SetAutoInventoryHandlerEnabled",
                None,
            )
            if callable(fn):
                try:
                    fn(True)
                except Exception:
                    pass

        sender_email = str(
            Player.GetAccountEmail() or ""
        ).strip()

        for account in _inventory_accounts():
            receiver_email = str(
                getattr(account, "AccountEmail", "") or ""
            ).strip()

            if not sender_email or not receiver_email:
                continue

            GLOBAL_CACHE.ShMem.SendMessage(
                sender_email,
                receiver_email,
                SharedCommandType.EnableWidget,
                (0.0, 0.0, 0.0, 0.0),
                (
                    INVENTORY_PLUS_WIDGET_NAME,
                    "",
                    "",
                    "",
                ),
            )

        if botting_tree is not None:
            fn = getattr(
                botting_tree,
                "Pause",
                None,
            )
            if callable(fn):
                try:
                    fn(True)
                except Exception:
                    pass

        return BehaviorTree.NodeState.RUNNING

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name="Pause Bot After Inventory Maintenance Failure",
            action_fn=_stop,
            aftercast_ms=0,
        )
    )


def InventoryCheckAndMaintenance() -> BehaviorTree:
    disabled = BehaviorTree(
        BehaviorTree.ConditionNode(
            name="Inventory Maintenance Disabled",
            condition_fn=lambda _node: not _inventory_maintenance_enabled,
        )
    )

    maintenance_attempts = [
        _inventory_maintenance_attempt(attempt_number)
        for attempt_number in range(
            1,
            INVENTORY_MAINTENANCE_RETRY_COUNT + 1,
        )
    ]
    maintenance_attempts.append(
        _stop_for_inventory_failure_node()
    )

    enabled_flow = BT.Sequence(
        name="Enabled Inventory Check And Maintenance",
        children=[
            _query_all_inventory_states_node(
                name="Query Real Inventory State On Every Active Account"
            ),

            BT.Selector(
                name="Check Inventory Thresholds",
                children=[
                    _inventory_is_healthy_node(
                        "Inventory Thresholds Already Satisfied",
                        log_success=True,
                    ),

                    BT.Sequence(
                        name="Run Inventory Maintenance",
                        children=[
                            _inventory_maintenance_trigger_node(),

                            _return_all_accounts_to_rata(
                                "inventory_maintenance_setup"
                            ),

                            BT.LeaveParty(),
                            BT.Wait(INVENTORY_SNAPSHOT_SETTLE_MS),

                            BT.Selector(
                                name="Retry Inventory Maintenance In Rata Sum",
                                children=maintenance_attempts,
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )

    return BT.Selector(
        name="Inventory Check And Maintenance",
        children=[
            disabled,
            enabled_flow,
        ],
    )


def StartupInventoryCheck() -> BehaviorTree:
    return BT.Selector(
        name="Startup Inventory Check",
        children=[
            BT.Sequence(
                name="Check Inventories Before Leaving Rata Sum",
                children=[
                    BT.IsCurrentMap(
                        map_id=RATA_SUM,
                        log=False,
                    ),
                    InventoryCheckAndMaintenance(),
                ],
            ),
            BT.Succeeder("Skip Startup Inventory Check Outside Rata Sum"),
        ],
    )


def _refresh_character_names() -> bool:
    changed = False

    local_email = str(Player.GetAccountEmail() or "").strip()
    local_name = str(Player.GetName() or "").strip()

    if local_email and local_name:
        key = _account_key(local_email)
        if _char_names.get(key) != local_name:
            _char_names[key] = local_name
            changed = True

    for account in _shared_accounts():
        email = str(getattr(account, "AccountEmail", "") or "").strip()
        name = str(
            getattr(
                getattr(account, "AgentData", None),
                "CharacterName",
                "",
            )
            or ""
        ).strip()

        if not email or not name:
            continue

        key = _account_key(email)
        if _char_names.get(key) != name:
            _char_names[key] = name
            changed = True

    return changed


def _statistics_action_node(
    name: str,
    action: Callable[[], None],
) -> BehaviorTree:
    def _run(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        try:
            action()
        except Exception as exc:
            PySystem.Console.Log(
                MODULE_NAME,
                f"[Statistics] {name} failed: {exc}",
                PySystem.Console.MessageType.Warning,
            )

        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name=name,
            action_fn=_run,
            aftercast_ms=0,
        )
    )


def _mark_run_start_node() -> BehaviorTree:
    def _mark() -> None:
        global _t_run_start, _t_l2_start, _t_l3_start
        global _current_run_time, _current_l1_time
        global _current_l2_time, _current_l3_time

        _t_run_start = time.monotonic()
        _t_l2_start = 0.0
        _t_l3_start = 0.0

        _current_run_time = 0.0
        _current_l1_time = 0.0
        _current_l2_time = 0.0
        _current_l3_time = 0.0

    return _statistics_action_node(
        "Mark Run Start",
        _mark,
    )


def _mark_l2_start_node() -> BehaviorTree:
    def _mark() -> None:
        global _t_l2_start, _current_l1_time

        now = time.monotonic()
        _t_l2_start = now
        _current_l1_time = (
            now - _t_run_start
            if _t_run_start > 0
            else 0.0
        )

    return _statistics_action_node(
        "Mark Level 2 Start",
        _mark,
    )


def _mark_l3_start_node() -> BehaviorTree:
    def _mark() -> None:
        global _t_l3_start, _current_l2_time

        now = time.monotonic()
        _t_l3_start = now
        _current_l2_time = (
            now - _t_l2_start
            if _t_l2_start > 0
            else 0.0
        )

    return _statistics_action_node(
        "Mark Level 3 Start",
        _mark,
    )


def _record_run_end_node() -> BehaviorTree:
    def _record() -> None:
        global _total_runs, _session_runs
        global _total_run_time, _fastest_run, _slowest_run
        global _l1_total_time, _l1_fastest, _l1_slowest
        global _l2_total_time, _l2_fastest, _l2_slowest
        global _l3_total_time, _l3_fastest, _l3_slowest
        global _current_run_time, _current_l1_time
        global _current_l2_time, _current_l3_time
        global _t_run_start, _t_l2_start, _t_l3_start

        now = time.monotonic()
        valid_timing = (
            _t_run_start > 0
            and _t_l2_start > _t_run_start
            and _t_l3_start > _t_l2_start
        )

        if valid_timing:
            run_time = now - _t_run_start
            level_1_time = _t_l2_start - _t_run_start
            level_2_time = _t_l3_start - _t_l2_start
            level_3_time = now - _t_l3_start

            _current_run_time = run_time
            _current_l1_time = level_1_time
            _current_l2_time = level_2_time
            _current_l3_time = level_3_time

            _total_run_time += run_time
            _fastest_run = min(_fastest_run, run_time)
            _slowest_run = max(_slowest_run, run_time)

            _l1_total_time += level_1_time
            _l1_fastest = min(_l1_fastest, level_1_time)
            _l1_slowest = max(_l1_slowest, level_1_time)

            _l2_total_time += level_2_time
            _l2_fastest = min(_l2_fastest, level_2_time)
            _l2_slowest = max(_l2_slowest, level_2_time)

            _l3_total_time += level_3_time
            _l3_fastest = min(_l3_fastest, level_3_time)
            _l3_slowest = max(_l3_slowest, level_3_time)

            PySystem.Console.Log(
                MODULE_NAME,
                (
                    "[Statistics] Run complete - "
                    f"Total {run_time:.0f}s | "
                    f"L1 {level_1_time:.0f}s | "
                    f"L2 {level_2_time:.0f}s | "
                    f"L3 {level_3_time:.0f}s"
                ),
                PySystem.Console.MessageType.Success,
            )

        _total_runs += 1
        _session_runs += 1

        _t_run_start = 0.0
        _t_l2_start = 0.0
        _t_l3_start = 0.0

        _save_statistics()

    return _statistics_action_node(
        "Record Successful Run",
        _record,
    )


def _inventory_count(model_min: int, model_max: int) -> int:
    return sum(int(GLOBAL_CACHE.Inventory.GetModelCount(mid)) for mid in range(int(model_min),int(model_max)+1))


def _inventory_statistics_node(
    *,
    after_chest: bool,
) -> BehaviorTree:
    node_name = (
        "Record Storm Daggers After Final Chest"
        if after_chest
        else "Snapshot Storm Daggers At Dungeon Entry"
    )

    state = {
        "started": False,
        "local_email": "",
        "account_keys": [],
        "requests": [],
        "index": 0,
        "waiting": False,
        "started_at": 0.0,
    }

    def _reset() -> None:
        state.update(
            started=False,
            local_email="",
            account_keys=[],
            requests=[],
            index=0,
            waiting=False,
            started_at=0.0,
        )

    def _start() -> None:
        _load_statistics()
        _refresh_character_names()

        local_email = str(
            Player.GetAccountEmail() or ""
        ).strip()

        if not local_email:
            state.update(
                started=True,
                local_email="",
                account_keys=[],
                requests=[],
            )
            return

        local_key = _account_key(local_email)
        section = (
            _STORM_RUN_SECTION
            if after_chest
            else _STORM_SNAPSHOT_SECTION
        )

        _settings_ini.set(
            section,
            local_key,
            _inventory_count(
                STORM_DAGGERS_MODEL_ID,
                STORM_DAGGERS_MODEL_ID,
            ),
        )

        account_keys = [local_key]
        requests: list[dict[str, str]] = []

        for account in _shared_accounts():
            email = str(
                getattr(account, "AccountEmail", "") or ""
            ).strip()

            if not email or email == local_email:
                continue

            key = _account_key(email)

            if key not in account_keys:
                account_keys.append(key)

            requests.append(
                {
                    "email": email,
                    "key": key,
                    "section": section,
                }
            )

        for key in account_keys:
            _storm_drops.setdefault(key, 0)

        state.update(
            started=True,
            local_email=local_email,
            account_keys=account_keys,
            requests=requests,
            index=0,
            waiting=False,
        )

    def _finish() -> None:
        if after_chest:
            total = 0

            for key in state["account_keys"]:
                key = str(key)

                before = _settings_ini.get_int(
                    _STORM_SNAPSHOT_SECTION,
                    key,
                    -1,
                )
                after = _settings_ini.get_int(
                    _STORM_RUN_SECTION,
                    key,
                    -1,
                )

                delta = (
                    max(0, after - before)
                    if before >= 0 and after >= 0
                    else 0
                )

                if delta > 0:
                    _storm_drops[key] = (
                        _storm_drops.get(key, 0) + delta
                    )
                    _session_storm[key] = (
                        _session_storm.get(key, 0) + delta
                    )

                total += delta

            _save_statistics()

            PySystem.Console.Log(
                MODULE_NAME,
                (
                    "[Statistics] Final chest recorded - "
                    f"Storm Daggers {total}"
                ),
                PySystem.Console.MessageType.Success,
            )
            return

        _save_statistics()

        PySystem.Console.Log(
            MODULE_NAME,
            (
                "[Statistics] Dungeon-entry snapshot completed for "
                f"{len(state['account_keys'])} account(s)."
            ),
            PySystem.Console.MessageType.Info,
        )

    def _tick(
        node: BehaviorTree.Node,
    ) -> BehaviorTree.NodeState:
        try:
            if bool(
                node.blackboard.get(
                    "USER_INTERRUPT_ACTIVE",
                    False,
                )
            ):
                _reset()
                return BehaviorTree.NodeState.FAILURE

            if not state["started"]:
                _start()

            requests = state["requests"]

            while state["index"] < len(requests):
                request = requests[state["index"]]
                email = request["email"]

                if not state["waiting"]:
                    reset_inventory_count(
                        email,
                        STORM_DAGGERS_MODEL_ID,
                        STORM_DAGGERS_MODEL_ID,
                    )

                    _settings_ini.set(
                        request["section"],
                        request["key"],
                        -1,
                    )

                    GLOBAL_CACHE.ShMem.SendMessage(
                        state["local_email"],
                        email,
                        SharedCommandType.InventoryQuery,
                        (
                            float(STORM_DAGGERS_MODEL_ID),
                            float(STORM_DAGGERS_MODEL_ID),
                            0.0,
                            0.0,
                        ),
                        ("report_inventory_count",),
                    )

                    state["waiting"] = True
                    state["started_at"] = time.monotonic()

                    return BehaviorTree.NodeState.RUNNING

                count = int(
                    get_inventory_count(
                        email,
                        STORM_DAGGERS_MODEL_ID,
                        STORM_DAGGERS_MODEL_ID,
                    )
                )

                if count >= 0:
                    _settings_ini.set(
                        request["section"],
                        request["key"],
                        count,
                    )
                    state["index"] += 1
                    state["waiting"] = False
                    continue

                elapsed_ms = (
                    time.monotonic() - state["started_at"]
                ) * 1000

                if elapsed_ms >= _INVENTORY_QUERY_TIMEOUT_MS:
                    PySystem.Console.Log(
                        MODULE_NAME,
                        (
                            "[Statistics] Storm Daggers inventory query "
                            "timed out on "
                            f"{_account_label(request['key'])}."
                        ),
                        PySystem.Console.MessageType.Warning,
                    )
                    state["index"] += 1
                    state["waiting"] = False
                    continue

                return BehaviorTree.NodeState.RUNNING

            _finish()
            _reset()
            return BehaviorTree.NodeState.SUCCESS

        except Exception as exc:
            PySystem.Console.Log(
                MODULE_NAME,
                f"[Statistics] {node_name} failed: {exc}",
                PySystem.Console.MessageType.Warning,
            )
            _reset()
            return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name=node_name,
            action_fn=_tick,
            aftercast_ms=_INVENTORY_QUERY_POLL_MS,
        )
    )


def ensure_botting_tree() -> BottingTree:
    global botting_tree

    _load_settings()

    if botting_tree is None:
        Listeners.AutoReturnOnDefeat.Enable()

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
                auto_inventory_handler_enabled=True,
                consumable_upkeeps=_enabled_consumable_upkeeps(),
                enable_party_wipe_recovery=True,
                heroai_state_logging=False,
            ),
        )

    return botting_tree


def InitializeBot() -> BehaviorTree:
    bot = ensure_botting_tree()

    return BT.Sequence(
        name="Initialize Oola's Lab BT",
        children=[
            bot.Config.Aggressive(
                multi_account=True,
                auto_loot=True,
                resurrection_scroll=True,
                account_isolation=False,
            ),
            BT.SetPlayerStatus(
                PlayerStatus.Offline,
                log=True,
            ),
            BT.LogMessage(
                message="Oola's Lab BT initialized in multibox mode.",
                module_name=MODULE_NAME,
            ),
        ],
    )


def PreparePartyAndSupplies() -> BehaviorTree:
    """Prepare a fresh run from Rata Sum.

    Resume cases inside Oola or in Magus Stones are left untouched.
    A fresh Rata start follows the Shards of Orr pattern: form the multibox
    party, abandon the dungeon quest on every account, then let the quest
    handler take it again cleanly.
    """

    already_inside = BT.Sequence(
        name="Skip Outpost Preparation - Already In Oola",
        children=[
            _inside_oola(),
            BT.Succeeder("OolaPreparationAlreadyDone"),
        ],
    )

    already_magus = BT.Sequence(
        name="Skip Outpost Preparation - Already In Magus Stones",
        children=[
            BT.IsCurrentMap(
                MAGUS_STONES,
                log=False,
            ),
            BT.IsQuestState(
                LITTLE_WORKSHOP_OF_HORRORS,
                state="active",
                log=True,
            ),
            BT.Succeeder("OolaPreparationAlreadyDoneInMagus"),
        ],
    )

    fresh_run = BT.Sequence(
        name="Prepare Party And Supplies From Rata Sum",
        map_id_or_name=RATA_SUM,
        random_travel=True,
        children=[
            StartupInventoryCheck(),

            BT.CreateParty(
                hero_ids=OOLA_PARTY_HERO_IDS,
                multibox_invite=True,
                timeout_ms=30_000,
                log=True,
            ),

            # Same startup quest reset used by Shards of Orr.
            BT.AbandonQuest(
                quest_id=LITTLE_WORKSHOP_OF_HORRORS,
                multi_account=True,
                include_self=True,
                timeout_ms=10_000,
                log=True,
            ),

            _runtime_difficulty_node(),
            _runtime_restock_node(),

            BT.LogMessage(
                message="Party formed and Oola settings applied.",
                module_name=MODULE_NAME,
            ),
        ],
    )

    return BT.Selector(
        name="Prepare Oola Party And Supplies",
        children=[
            already_inside,
            already_magus,
            fresh_run,
        ],
    )


def HandleOolaQuest() -> BehaviorTree:
    already_inside = BT.Sequence(
        name="Skip Oola Quest Handler - Already Inside",
        children=[
            _inside_oola(),
            BT.Succeeder("OolaQuestAlreadyHandled"),
        ],
    )

    already_magus = BT.Sequence(
        name="Skip Oola Quest Handler - Already In Magus",
        children=[
            BT.IsCurrentMap(
                MAGUS_STONES,
                log=False,
            ),
            BT.IsQuestState(
                LITTLE_WORKSHOP_OF_HORRORS,
                state="active",
                log=True,
            ),
            BT.Succeeder("OolaQuestAlreadyActiveInMagus"),
        ],
    )

    active = BT.Sequence(
        name="Little Workshop Already Active",
        children=[
            BT.IsCurrentMap(
                RATA_SUM,
                log=False,
            ),
            BT.IsQuestState(
                LITTLE_WORKSHOP_OF_HORRORS,
                state="active",
                log=True,
            ),
            BT.Succeeder("ContinueWithActiveOolaQuest"),
        ],
    )

    completed = BT.Sequence(
        name="Collect And Retake Little Workshop",
        children=[
            BT.IsCurrentMap(
                RATA_SUM,
                log=True,
            ),
            BT.IsQuestState(
                LITTLE_WORKSHOP_OF_HORRORS,
                state="complete",
                log=True,
            ),

            BT.Move(
                OOLA_QUEST_NPC,
                tolerance=150.0,
                pause_on_combat=False,
                flag_heroes_to_waypoint=False,
                ignore_destination_npcs=True,
                avoid_obstacles=False,
                log=True,
            ),
            BehaviorTree(
                    BehaviorTree.ActionNode(
                        name="Pixel Stack Followers",
                        action_fn=lambda: (
                            HeroAICommandAPI().pixel_stack()
                            or BehaviorTree.NodeState.SUCCESS
                        ),
                        aftercast_ms=0,
                    )
                ),
            BT.Wait(15_000),

            BT.MoveAndAutoDialog(
                OOLA_QUEST_NPC,
                buttons=0,
                pause_on_combat=False,
                multi_account=True,
                log=True,
            ),
            BT.WaitForQuestCleared(
                LITTLE_WORKSHOP_OF_HORRORS,
                timeout_ms=15_000,
            ),

            BT.MoveAndAutoDialog(
                OOLA_QUEST_NPC,
                buttons=0,
                pause_on_combat=False,
                multi_account=True,
                log=True,
            ),
            BT.WaitForActiveQuest(
                LITTLE_WORKSHOP_OF_HORRORS,
                timeout_ms=15_000,
            ),
        ],
    )

    missing = BT.Sequence(
        name="Take Little Workshop Of Horrors",
        children=[
            BT.IsCurrentMap(
                RATA_SUM,
                log=True,
            ),
            BT.IsQuestState(
                LITTLE_WORKSHOP_OF_HORRORS,
                state="missing",
                log=True,
            ),

            BT.Move(
                OOLA_QUEST_NPC,
                tolerance=150.0,
                pause_on_combat=False,
                flag_heroes_to_waypoint=False,
                ignore_destination_npcs=True,
                avoid_obstacles=False,
                log=True,
            ),
            BehaviorTree(
                    BehaviorTree.ActionNode(
                        name="Pixel Stack Followers",
                        action_fn=lambda: (
                            HeroAICommandAPI().pixel_stack()
                            or BehaviorTree.NodeState.SUCCESS
                        ),
                        aftercast_ms=0,
                    )
                ),
            BT.Wait(5_000),

            BT.MoveAndAutoDialog(
                OOLA_QUEST_NPC,
                buttons=0,
                pause_on_combat=False,
                multi_account=True,
                log=True,
            ),
            BT.WaitForActiveQuest(
                LITTLE_WORKSHOP_OF_HORRORS,
                timeout_ms=15_000,
            ),
        ],
    )

    return BT.Selector(
        name="Handle Oola Quest",
        children=[
            already_inside,
            already_magus,
            active,
            completed,
            missing,
        ],
    )


def Level1_Start() -> BehaviorTree:
    return _map_guarded_point(
        "Oola Level 1 Start",
        OOLA_LEVEL_1,
        BT.Sequence(
            name="Start Oola Level 1",
            children=[
                _mark_run_start_node(),
                _inventory_statistics_node(after_chest=False),
                BT.AddModelToLootWhitelist(DUNGEON_KEY_MODEL_ID),
                UseAvailableSummoningStone(),
                BT.MoveAndAutoDialog(
                    L1_BLESSING,
                    buttons=0,
                    pause_on_combat=False,
                    multi_account=True,
                    log=True,
                ),
            ],
        ),
        skip_if_in_maps=(
            OOLA_LEVEL_2,
            OOLA_LEVEL_3,
        ),
    )


def Level1_EnterLevel2() -> BehaviorTree:
    name = "Oola Level 1 Enter Level 2"

    return BT.Sequence(
        name=name,
        children=[
            _map_guarded_point(
                name,
                OOLA_LEVEL_1,
                BT.Sequence(
                    name=f"{name} And Wait For Load",
                    children=[
                        BT.Move(
                            L1_EXIT_TRIGGER,
                            pause_on_combat=False,
                            tolerance=200.0,
                            ignore_destination_obstacles=True,
                            log=False,
                        ),
                        BT.WaitForMapLoad(
                            OOLA_LEVEL_2,
                            timeout_ms=60_000,
                        ),
                    ],
                ),
                skip_if_in_maps=(
                    OOLA_LEVEL_2,
                    OOLA_LEVEL_3,
                ),
            ),
            BT.WaitUntilOnExplorable(timeout_ms=30_000),
            _mark_l2_start_node(),
            BT.Wait(2_000),
        ],
    )


def Level2_Start() -> BehaviorTree:
    return _map_guarded_point(
        "Oola Level 2 Start",
        OOLA_LEVEL_2,
        BT.Sequence(
            name="Start Oola Level 2",
            children=[
                BT.AddModelToLootWhitelist(DUNGEON_KEY_MODEL_ID),
                UseAvailableSummoningStone(),
                BT.MoveAndAutoDialog(
                    L2_BLESSING,
                    buttons=0,
                    pause_on_combat=False,
                    multi_account=True,
                    log=True,
                ),
            ],
        ),
        skip_if_in_maps=(OOLA_LEVEL_3,),
    )


def Level2_EnterLevel3() -> BehaviorTree:
    name = "Oola Level 2 Enter Level 3"

    return BT.Sequence(
        name=name,
        children=[
            _map_guarded_point(
                name,
                OOLA_LEVEL_2,
                BT.Sequence(
                    name=f"{name} And Wait For Load",
                    children=[
                        BT.Move(
                            L2_EXIT_TRIGGER,
                            pause_on_combat=False,
                            tolerance=200.0,
                            ignore_destination_obstacles=True,
                            log=False,
                        ),
                        BT.WaitForMapLoad(
                            OOLA_LEVEL_3,
                            timeout_ms=60_000,
                        ),
                    ],
                ),
                skip_if_in_maps=(OOLA_LEVEL_3,),
            ),
            BT.WaitUntilOnExplorable(timeout_ms=30_000),
            _mark_l3_start_node(),
            BT.Wait(2_000),
        ],
    )


def Level3_Start() -> BehaviorTree:
    return BT.Sequence(
        name="Start Oola Level 3",
        children=[
            BT.IsCurrentMap(
                OOLA_LEVEL_3,
                log=True,
            ),
            UseAvailableSummoningStone(),
            BT.MoveAndAutoDialog(
                L3_BLESSING,
                buttons=0,
                pause_on_combat=False,
                multi_account=True,
                log=True,
            ),
        ],
    )


def Level3_FinalClear() -> BehaviorTree:
    return BT.Sequence(
        name="Oola Level 3 Final Clear",
        children=[
            BT.IsCurrentMap(
                OOLA_LEVEL_3,
                log=True,
            ),
            BT.WaitForClearEnemiesInArea(
                L3_FINAL_FIGHT_CENTER.x,
                L3_FINAL_FIGHT_CENTER.y,
                radius=Range.Spirit.value,
                allowed_alive_enemies=0,
                interact_interval_ms=750,
                stable_clear_ms=5_000,
                keep_player_near_center=False,
                center_tolerance=750.0,
                log=True,
            ),
            _record_run_end_node(),
        ],
    )


def OpenFinalChest() -> BehaviorTree:
    return BT.Sequence(
        name="Open Oola's Chest",
        children=[
            BT.IsCurrentMap(
                OOLA_LEVEL_3,
                log=True,
            ),
            BT.MoveAndInteractWithGadget(
                pos=OOLA_FINAL_CHEST,
                search_distance=1_000.0,
                interaction_distance=Range.Nearby.value,
                interaction_count=2,
                interaction_interval_ms=1_000,
                account_settle_ms=3_000,
                timeout_ms=90_000,
                pause_on_combat=False,
                multi_account=True,
                include_self=True,
                log=True,
            ),
            _inventory_statistics_node(after_chest=True),
        ],
    )


def CollectRewardAndReturnToRata() -> BehaviorTree:
    """Return to Rata, switch region with library travel, then regroup."""

    return BT.Sequence(
        name="Return To Rata Sum After Oola",
        children=[
            _runtime_consumable_upkeep_node(False),

            BT.Resign(
                wait_for_map_load=True,
                target_map_name="Rata Sum",
                multi_account=True,
            ),
            BT.Wait(2_000),

        ],
    )


def ResolveOolaQuestAfterRun() -> BehaviorTree:
    # -------------------------------------------------------------------------
    # Quest already active -> nothing to do.
    # -------------------------------------------------------------------------
    active = BT.Sequence(
        name="Keep Active Oola Quest",
        children=[
            BT.IsQuestState(
                LITTLE_WORKSHOP_OF_HORRORS,
                state="active",
                log=True,
            ),
            BT.Succeeder("OolaQuestReady"),
        ],
    )

    # -------------------------------------------------------------------------
    # COMPLETE -> collect reward only.
    # The quest becomes MISSING after the reward is collected.
    # -------------------------------------------------------------------------
    completed = BT.Sequence(
        name="Collect Oola Reward",
        children=[
            BT.IsQuestState(
                LITTLE_WORKSHOP_OF_HORRORS,
                state="complete",
                log=True,
            ),

            BT.Move(
                OOLA_QUEST_NPC,
                tolerance=150.0,
                pause_on_combat=False,
                flag_heroes_to_waypoint=False,
                ignore_destination_npcs=True,
                avoid_obstacles=False,
                log=True,
            ),

            BehaviorTree(
                BehaviorTree.ActionNode(
                    name="Pixel Stack Followers",
                    action_fn=lambda: (
                        HeroAICommandAPI().pixel_stack()
                        or BehaviorTree.NodeState.SUCCESS
                    ),
                    aftercast_ms=0,
                )
            ),

            BT.Wait(5_000),

            # Collect reward on every account.
            # After this interaction the quest becomes "missing".
            BT.MoveAndAutoDialog(
                OOLA_QUEST_NPC,
                buttons=0,
                pause_on_combat=False,
                multi_account=True,
                log=True,
            ),

            # Give the quest state a moment to update.
            BT.Wait(1_000),
        ],
    )

    # -------------------------------------------------------------------------
    # MISSING -> change Rata Sum region, regroup and retake the quest.
    # -------------------------------------------------------------------------
    missing = BT.Sequence(
        name="Refresh Rata And Retake Oola Quest",
        children=[
            BT.IsQuestState(
                LITTLE_WORKSHOP_OF_HORRORS,
                state="missing",
                log=True,
            ),

            # Change Rata Sum region to force a fresh instance.
            BT.Subtree(
                name="Travel Leader To Alternate Rata Region",
                subtree_fn=lambda _node: BT.TravelToRegion(
                    outpost_id=RATA_SUM,
                    region=(
                        QUEST_REFRESH_US_REGION
                        if int(Map.GetRegion()[0]) == QUEST_REFRESH_EU_REGION
                        else QUEST_REFRESH_EU_REGION
                    ),
                    district=QUEST_REFRESH_DISTRICT,
                    language=QUEST_REFRESH_LANGUAGE,
                    log=True,
                    timeout_ms=30_000,
                ),
            ),

            BT.WaitUntilOnOutpost(timeout_ms=30_000),
            BT.Wait(2_000),

            # Recall the other accounts and configured heroes.
            BT.CreateParty(
                hero_ids=OOLA_PARTY_HERO_IDS,
                multibox_invite=True,
                timeout_ms=30_000,
                log=True,
            ),

            BT.Wait(2_000),

            # Return to Oola.
            BT.Move(
                OOLA_QUEST_NPC,
                tolerance=150.0,
                pause_on_combat=False,
                flag_heroes_to_waypoint=False,
                ignore_destination_npcs=True,
                avoid_obstacles=False,
                log=True,
            ),

            BehaviorTree(
                BehaviorTree.ActionNode(
                    name="Pixel Stack Followers",
                    action_fn=lambda: (
                        HeroAICommandAPI().pixel_stack()
                        or BehaviorTree.NodeState.SUCCESS
                    ),
                    aftercast_ms=0,
                )
            ),

            BT.Wait(5_000),

            # Retake the quest on every account.
            BT.MoveAndAutoDialog(
                OOLA_QUEST_NPC,
                buttons=0,
                pause_on_combat=False,
                multi_account=True,
                log=True,
            ),

            BT.WaitForActiveQuest(
                LITTLE_WORKSHOP_OF_HORRORS,
                timeout_ms=15_000,
            ),
        ],
    )
    resolve_not_active = BT.Sequence(
        name="Resolve Completed Or Missing Oola Quest",
        children=[
            BT.Selector(
                name="Collect Reward If Complete",
                children=[
                    completed,

                    # If already missing, there is no reward to collect.
                    BT.IsQuestState(
                        LITTLE_WORKSHOP_OF_HORRORS,
                        state="missing",
                        log=False,
                    ),
                ],
            ),

            missing,
        ],
    )

    return BT.Selector(
        name="Resolve Oola Quest After Run",
        children=[
            active,
            resolve_not_active,
        ],
    )

def PrepareNextDungeonRun() -> BehaviorTree:
    return BT.Sequence(
        name="Prepare Next Oola Run",
        children=[
            BT.IsCurrentMap(
                RATA_SUM,
                log=True,
            ),
            BT.IsQuestState(
                LITTLE_WORKSHOP_OF_HORRORS,
                state="active",
                log=True,
            ),
            BT.CreateParty(
                hero_ids=OOLA_PARTY_HERO_IDS,
                multibox_invite=True,
                timeout_ms=30_000,
                log=True,
            ),

            _runtime_difficulty_node(),
            _runtime_restock_node(),
            _runtime_consumable_upkeep_node(True),

            TravelToMagusStones(),
            MagusStonesStart(),
            EnterOolasLab(),
        ],
    )


def get_execution_steps() -> list[tuple[str, Callable[[], BehaviorTree]]]:
    # The party-alive guard is active from the Rata Sum exit through the final
    # chest.  It is checked every tick, so a death in the middle of a movement,
    # clear, Flux cycle or floor transition freezes that exact child without
    # resetting it.  HeroAI/background recovery remains free to resurrect.
    guarded_run_steps: list[tuple[str, Callable[[], BehaviorTree]]] = [
        ("Travel To Magus Stones", TravelToMagusStones),
        ("Magus Stones Start", MagusStonesStart),
        *_vanquish_point_steps(
            "Magus Route To Oola",
            MAGUS_STONES,
            MAGUS_ROUTE,
            move_tolerance=500.0,
            skip_if_in_maps=(OOLA_LEVEL_1, OOLA_LEVEL_2, OOLA_LEVEL_3),
        ),
        ("Enter Oola's Lab", EnterOolasLab),

        # ---------------------------------------------------------------------
        # Level 1
        # ---------------------------------------------------------------------
        ("Level 1 Start", Level1_Start),
        *_vanquish_point_steps(
            "Level 1 Main Route",
            OOLA_LEVEL_1,
            L1_ROUTE,
            move_tolerance=500.0,
            skip_if_in_maps=(OOLA_LEVEL_2, OOLA_LEVEL_3),
        ),
        ("Level 1 Secure Key Loot", Level1_KeyLoot),
        ("Level 1 Open Dungeon Lock", Level1_OpenLock),
        ("Level 1 Enter Level 2", Level1_EnterLevel2),

        # ---------------------------------------------------------------------
        # Level 2
        # ---------------------------------------------------------------------
        ("Level 2 Start", Level2_Start),
        *_vanquish_point_steps(
            "Level 2 Main Route",
            OOLA_LEVEL_2,
            L2_ROUTE,
            move_tolerance=500.0,
            skip_if_in_maps=(OOLA_LEVEL_3,),
        ),
        *_movement_point_steps(
            "Level 2 Pre Flux",
            OOLA_LEVEL_2,
            L2_PRE_FLUX_PATH,
            pause_on_combat=False,
            move_tolerance=500.0,
            skip_if_in_maps=(OOLA_LEVEL_3,),
            start_index=16,
            disable_combat=True,
        ),
        ("Level 2 Flux Golem", Level2_FluxGolem),
        *_vanquish_point_steps(
            "Level 2 Route B",
            OOLA_LEVEL_2,
            L2_ROUTE_B,
            move_tolerance=500.0,
            skip_if_in_maps=(OOLA_LEVEL_3,),
        ),
        ("Level 2 Open Dungeon Lock", Level2_OpenDungeonLock),
        *_vanquish_point_steps(
            "Level 2 Exit Route",
            OOLA_LEVEL_2,
            L2_EXIT_ROUTE,
            move_tolerance=500.0,
            skip_if_in_maps=(OOLA_LEVEL_3,),
        ),
        ("Level 2 Enter Level 3", Level2_EnterLevel3),

        # ---------------------------------------------------------------------
        # Level 3
        # ---------------------------------------------------------------------
        ("Level 3 Start", Level3_Start),
        *_vanquish_point_steps(
            "Level 3 Main Route",
            OOLA_LEVEL_3,
            L3_ROUTE,
            move_tolerance=500.0,
        ),
        ("Level 3 Final Clear", Level3_FinalClear),
        ("Open Final Chest", OpenFinalChest),
    ]

    return [
        # ---------------------------------------------------------------------
        # Outpost / quest setup - intentionally outside the death gate.
        # ---------------------------------------------------------------------
        ("Initialize Bot", InitializeBot),
        ("Prepare Party And Supplies", PreparePartyAndSupplies),
        ("Handle Oola Quest", HandleOolaQuest),

        *(
            _guard_run_step(step_name, factory)
            for step_name, factory in guarded_run_steps
        ),

        # ---------------------------------------------------------------------
        # End of run / next run - the guard ends after the chest.
        # ---------------------------------------------------------------------
        ("Return To Rata Sum", CollectRewardAndReturnToRata),
        ("Resolve Oola Quest", ResolveOolaQuestAfterRun),
        ("Inventory Check And Maintenance", InventoryCheckAndMaintenance),
        ("Prepare Next Dungeon Run", PrepareNextDungeonRun),
    ]


def _fmt_time(seconds: float) -> str:
    if seconds == float("inf") or seconds <= 0:
        return "-"

    minutes, seconds = divmod(int(seconds), 60)
    return f"{minutes:02d}:{seconds:02d}"


def _avg_time(total: float) -> str:
    if _total_runs <= 0:
        return "-"

    return _fmt_time(total / _total_runs)



def _reset_statistics() -> None:
    """Reset all Oola run/drop statistics while keeping character names."""
    global _total_runs, _session_runs
    global _total_run_time, _fastest_run, _slowest_run
    global _l1_total_time, _l1_fastest, _l1_slowest
    global _l2_total_time, _l2_fastest, _l2_slowest
    global _l3_total_time, _l3_fastest, _l3_slowest
    global _t_run_start, _t_l2_start, _t_l3_start
    global _current_run_time, _current_l1_time
    global _current_l2_time, _current_l3_time

    _total_runs = 0
    _session_runs = 0

    _total_run_time = 0.0
    _fastest_run = float("inf")
    _slowest_run = 0.0

    _l1_total_time = 0.0
    _l1_fastest = float("inf")
    _l1_slowest = 0.0

    _l2_total_time = 0.0
    _l2_fastest = float("inf")
    _l2_slowest = 0.0

    _l3_total_time = 0.0
    _l3_fastest = float("inf")
    _l3_slowest = 0.0

    _t_run_start = 0.0
    _t_l2_start = 0.0
    _t_l3_start = 0.0

    _current_run_time = 0.0
    _current_l1_time = 0.0
    _current_l2_time = 0.0
    _current_l3_time = 0.0

    # Keep known account keys so _save_statistics() overwrites their
    # persisted all-time drop counters with zero.
    for key in list(_storm_drops):
        if key != "local":
            _storm_drops[key] = 0

    _session_storm.clear()

    # Prevent stale before/after chest snapshots from surviving the reset.
    for section in (
        _STORM_SNAPSHOT_SECTION,
        _STORM_RUN_SECTION,
    ):
        for key in _settings_ini.items(section).keys():
            if key != "local":
                _settings_ini.set(section, key, 0)

    _save_statistics()

    PySystem.Console.Log(
        MODULE_NAME,
        "Oola statistics reset.",
        PySystem.Console.MessageType.Success,
    )


def _draw_statistics() -> None:
    global _scramble_accounts

    _load_statistics()

    if _refresh_character_names():
        _save_statistics()

    gold = Color(255, 210, 80, 255).to_tuple_normalized()
    cyan = Color(80, 210, 255, 255).to_tuple_normalized()

    PyImGui.text_colored(
        "Oola's Lab Statistics",
        gold,
    )
    PyImGui.separator()
    PyImGui.spacing()

    _scramble_accounts = PyImGui.checkbox(
        "Hide account names",
        _scramble_accounts,
    )

    PyImGui.same_line()

    if PyImGui.button("Reset Statistics"):
        _reset_statistics()

    session_total = sum(_session_storm.values())
    all_time_total = sum(_storm_drops.values())

    # Overview ---------------------------------------------------------------
    PyImGui.text_colored("Overview", cyan)

    if PyImGui.begin_table(
        "##oola_overview",
        3,
        PyImGui.TableFlags.Borders | PyImGui.TableFlags.RowBg,
    ):
        for label in (
            "Runs",
            "Storm Daggers",
            "Runs / Drop",
        ):
            PyImGui.table_setup_column(label)

        PyImGui.table_headers_row()
        PyImGui.table_next_row()

        overview_values = (
            _total_runs,
            all_time_total,
            (
                f"{_total_runs / all_time_total:.1f}"
                if all_time_total > 0
                else "-"
            ),
        )

        for column_index, value in enumerate(overview_values):
            PyImGui.table_set_column_index(column_index)
            PyImGui.text(str(value))

        PyImGui.end_table()

    PyImGui.text(
        f"Session: {_session_runs} run(s) | "
        f"{session_total} Storm Daggers"
    )

    # Timings ----------------------------------------------------------------
    PyImGui.spacing()
    PyImGui.text_colored("Run Timings", cyan)

    if PyImGui.begin_table(
        "##oola_timings",
        5,
        PyImGui.TableFlags.Borders | PyImGui.TableFlags.RowBg,
    ):
        for label in (
            "Floor",
            "Current",
            "Avg",
            "Best",
            "Worst",
        ):
            PyImGui.table_setup_column(label)

        PyImGui.table_headers_row()

        now = time.monotonic()

        rows = [
            (
                "Overall",
                (
                    now - _t_run_start
                    if _t_run_start > 0
                    else _current_run_time
                ),
                _total_run_time,
                _fastest_run,
                _slowest_run,
            ),
            (
                "Floor 1",
                (
                    now - _t_run_start
                    if _t_run_start > 0 and _t_l2_start <= 0
                    else _current_l1_time
                ),
                _l1_total_time,
                _l1_fastest,
                _l1_slowest,
            ),
            (
                "Floor 2",
                (
                    now - _t_l2_start
                    if _t_l2_start > 0 and _t_l3_start <= 0
                    else _current_l2_time
                ),
                _l2_total_time,
                _l2_fastest,
                _l2_slowest,
            ),
            (
                "Floor 3",
                (
                    now - _t_l3_start
                    if _t_l3_start > 0
                    else _current_l3_time
                ),
                _l3_total_time,
                _l3_fastest,
                _l3_slowest,
            ),
        ]

        for label, current, total, best, worst in rows:
            PyImGui.table_next_row()

            values = (
                label,
                _fmt_time(current),
                _avg_time(total),
                _fmt_time(best),
                _fmt_time(worst),
            )

            for column_index, value in enumerate(values):
                PyImGui.table_set_column_index(column_index)
                PyImGui.text(str(value))

        PyImGui.end_table()

    # Drops ------------------------------------------------------------------
    PyImGui.spacing()
    PyImGui.text_colored("Storm Daggers Drops", cyan)

    if PyImGui.begin_table(
        "##oola_storm",
        3,
        PyImGui.TableFlags.Borders | PyImGui.TableFlags.RowBg,
    ):
        for label in (
            "Account",
            "Session",
            "All Time",
        ):
            PyImGui.table_setup_column(label)

        PyImGui.table_headers_row()

        for key in _known_account_keys():
            PyImGui.table_next_row()

            values = (
                _account_label(key),
                _session_storm.get(key, 0),
                _storm_drops.get(key, 0),
            )

            for column_index, value in enumerate(values):
                PyImGui.table_set_column_index(column_index)
                PyImGui.text(str(value))

        PyImGui.end_table()


def _draw_run_config() -> None:
    global _use_hard_mode
    global _restock_conset, _activate_conset
    global _restock_pcons, _activate_pcons
    global _use_summoning_stone
    global _inventory_maintenance_enabled
    global _inventory_min_free_slots
    global _inventory_min_id_kits
    global _inventory_min_salvage_kits

    _load_settings()

    settings_changed = False
    upkeep_changed = False

    PyImGui.text("Oola's Lab Run Config")
    PyImGui.separator()

    toggles = (
        ("Hard Mode (HM)", "_use_hard_mode", False),
        ("Restock conset from storage", "_restock_conset", False),
        ("Activate / maintain conset", "_activate_conset", True),
        ("Restock pcons from storage", "_restock_pcons", False),
        ("Activate / maintain pcons", "_activate_pcons", True),
        ("Use summoning stones", "_use_summoning_stone", False),
    )

    for label, variable_name, affects_upkeep in toggles:
        old_value = bool(globals()[variable_name])
        new_value = PyImGui.checkbox(label, old_value)

        if new_value == old_value:
            continue

        globals()[variable_name] = new_value
        settings_changed = True
        upkeep_changed = upkeep_changed or affects_upkeep

    PyImGui.separator()
    PyImGui.text("Inventory maintenance")

    maintenance_enabled = PyImGui.checkbox(
        "Run MerchantRules when inventory is low",
        _inventory_maintenance_enabled,
    )

    if maintenance_enabled != _inventory_maintenance_enabled:
        _inventory_maintenance_enabled = maintenance_enabled
        settings_changed = True

    if _inventory_maintenance_enabled:
        inventory_thresholds = (
            (
                "Minimum free slots",
                "_inventory_min_free_slots",
            ),
            (
                "Minimum Superior ID kits (0 = disabled)",
                "_inventory_min_id_kits",
            ),
            (
                "Minimum Superior salvage kits (0 = disabled)",
                "_inventory_min_salvage_kits",
            ),
        )

        for label, variable_name in inventory_thresholds:
            old_value = int(globals()[variable_name])
            new_value = max(
                0,
                int(PyImGui.input_int(label, old_value)),
            )

            if new_value != old_value:
                globals()[variable_name] = new_value
                settings_changed = True

        PyImGui.text_wrapped(
            "Same multibox inventory logic as Shards of Orr: every active "
            "client is queried locally. If one account is below a threshold, "
            "all active accounts return to Rata Sum, travel to Eye of the North "
            "for MerchantRules maintenance, then return to Rata Sum before the "
            "party is reformed."
        )

    if settings_changed:
        _save_settings()

    if upkeep_changed:
        _configure_runtime_upkeeps()


def tooltip() -> None:
    title = Color(255, 200, 100, 255)

    PyImGui.set_next_window_size((600, 0))
    PyImGui.begin_tooltip()

    ImGui.image(
        MODULE_ICON,
        (32, 32),
    )
    PyImGui.same_line(0, 10)

    ImGui.push_font(
        "Regular",
        20,
    )
    ImGui.text_aligned(
        MODULE_NAME,
        alignment=Alignment.MidLeft,
        color=title.color_tuple,
        height=32,
    )
    ImGui.pop_font()

    PyImGui.spacing()
    PyImGui.separator()

    PyImGui.text_wrapped(
        "Multibox Oola's Lab farm using the Shards of Orr BT framework "
        "for party control, inventory maintenance and persistent statistics."
    )

    PyImGui.bullet_text(
        "Complete Oola route with keys and Flux Matrix mechanic."
    )
    PyImGui.bullet_text(
        "Multibox quest dialogs and final chest interaction."
    )
    PyImGui.bullet_text(
        "Tracks Storm Daggers (model 1986) per account."
    )
    PyImGui.bullet_text(
        "MerchantRules inventory maintenance via Eye of the North."
    )

    PyImGui.end_tooltip()


def main() -> None:
    global initialized

    if not initialized:
        _load_settings()
        ensure_botting_tree()
        initialized = True

    tree = ensure_botting_tree()
    tree.tick()

    tree.UI.draw_window(
        icon_path=TEXTURE,
        iconwidth=96,
        main_child_dimensions=(420, 380),
        extra_tabs=[
            ("Statistics", _draw_statistics),
            ("Config", _draw_run_config),
        ],
    )