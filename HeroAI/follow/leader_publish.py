import math

from dataclasses import dataclass, field
from typing import Protocol
from typing import SupportsIndex
from typing import SupportsInt

from Py4GWCoreLib import Agent, Party, Player, Range, ThrottledTimer
from Py4GWCoreLib.py4gwcorelib_src.Settings import Settings
from Py4GWCoreLib.Map import Map
from Py4GWCoreLib.Pathing import AutoPathing
from Py4GWCoreLib.py4gwcorelib_src.Utils import Utils
from Py4GWCoreLib.GlobalCache.shared_memory_src.AccountStruct import AccountStruct
from Py4GWCoreLib.GlobalCache.shared_memory_src.AllAccounts import AllAccounts
from Py4GWCoreLib.GlobalCache.shared_memory_src.HeroAIOptionStruct import HeroAIOptionStruct
from Py4GWCoreLib.native_src.internals.types import Vec2f

from HeroAI.follow.placement import PLACEMENT_CFG
from HeroAI.follow.placement import resolve_placement


# Force-load the navmesh on first call. AutoPathing's cache is normally
# populated by get_path() coroutine pumps; leader-side validation skips that.
def _get_navmesh():
    autopath = AutoPathing()
    nav = autopath.get_navmesh()
    if nav is not None:
        return nav
    try:
        for _ in autopath.load_pathing_maps():
            pass
    except Exception:
        return None
    return autopath.get_navmesh()


class SharedMemoryManagerProtocol(Protocol):
    max_num_players: int

    def GetAllAccounts(self) -> AllAccounts:
        ...


class NavMeshProtocol(Protocol):
    def contains(self, x: float, y: float, margin: float) -> bool:
        ...

    def find_nearest_reachable(
        self,
        origin: tuple[float, float],
        margin: float = 20,
    ) -> tuple[float, float] | None:
        ...

    def has_line_of_sight(
        self,
        p1: tuple[float, float],
        p2: tuple[float, float],
        margin: float,
        step_dist: float,
    ) -> bool:
        ...


@dataclass(slots=True)
class FollowIniConfig:
    global_ini_path: str = "HeroAI"
    formations_ini_name: str = "FollowModule_Formations.ini"
    settings_ini_name: str = "FollowModule_Settings.ini"
    runtime_ini_name: str = "FollowRuntime.ini"
    formations_section: str = "Formations"
    runtime_section: str = "FollowRuntime"
    formation_id_prefix: str = "FormationId:"
    formation_name_prefix: str = "Formation:"
    selected_id_key: str = "selected_id"
    selected_name_key: str = "selected"
    formation_count_var_name: str = "formation_count"
    count_key: str = "count"
    point_count_key: str = "point_count"
    point_x_key_template: str = "p{index}_x"
    point_y_key_template: str = "p{index}_y"
    max_follow_slots: int = 11
    ini_reload_ms: int = 1000
    publish_interval_ms: int = 100
    combat_publish_interval_ms: int = 1000


@dataclass(slots=True)
class FollowThresholdConfig:
    default_follow_threshold: float = field(default_factory=lambda: float(Range.Area.value))
    combat_follow_threshold: float = field(default_factory=lambda: float(Range.Adjacent.value))
    flagged_follow_threshold: float = 0.0
    disabled_threshold: float = -1.0


@dataclass(slots=True)
class FollowTuningConfig:
    nonzero_epsilon: float = 0.001
    leader_move_release_distance: float = 1.0
    # Off-mesh snap distance cap. Snaps farther than this fall back to anchor.
    followpos_max_reach: float = field(default_factory=lambda: float(Range.Area.value))
    # Allow a small amount of extra distance from the leader beyond the
    # intended formation radius before we give up and stack at the anchor.
    followpos_anchor_slack: float = 50.0
    # NavMesh.contains margin — points just barely off-mesh still count as on.
    followpos_contains_margin: float = 20.0
    # If the leader itself is reported off-mesh on a ready explorable map, treat
    # that as a stale/bad live navmesh signal and allow a bounded force-reload.
    navmesh_recovery_contains_margin: float = 20.0
    navmesh_recovery_cooldown_ms: int = 1000


@dataclass(slots=True)
class FollowPublisherState:
    ini_vars_registered: bool = False
    registered_follow_sections: set[str] = field(default_factory=set)
    selected_id_cache: str = ""
    points_cache: list[tuple[float, float]] = field(default_factory=list)
    map_signature: tuple[int, int, int, int, int] | None = None
    hold_until_leader_moves: bool = False
    leader_entry_pos: tuple[float, float] | None = None
    leader_in_combat_last: bool = False
    combat_anchor_facing: float | None = None
    navmesh_recovery_attempts: int = 0
    cached_navmesh: NavMeshProtocol | None = None


class FollowFormationPublisher:
    def __init__(self, shared_memory_manager: SharedMemoryManagerProtocol):
        self.shared_memory_manager = shared_memory_manager
        self.ini = FollowIniConfig()
        self.thresholds = FollowThresholdConfig()
        self.tuning = FollowTuningConfig()
        self.state = FollowPublisherState()
        self.state.selected_id_cache = "builtin_default"
        self.state.points_cache = self._get_default_follow_points()
        # Constructed on first use, not here: SharedMemory imports this module during
        # startup, and HeroAI.fight pulls Py4GWCoreLib.AgentArray. Importing it at
        # module scope closes a startup cycle.
        self.fight_publisher = None
        self.fight_owns_all_flag = False
        self.ini_reload_timer = ThrottledTimer(self.ini.ini_reload_ms)
        self.publish_timer = ThrottledTimer(self.ini.publish_interval_ms)
        self.combat_publish_timer = ThrottledTimer(self.ini.combat_publish_interval_ms)
        self.navmesh_recovery_timer = ThrottledTimer(self.tuning.navmesh_recovery_cooldown_ms)

    def _get_default_follow_points(self) -> list[tuple[float, float]]:
        # Stable built-in fallback so follow publication never collapses to an empty template.
        return [
            (144.0, 180.0),
            (0.0, 180.0),
            (-144.0, 180.0),
            (216.0, 324.0),
            (72.0, 324.0),
            (-72.0, 324.0),
            (-216.0, 324.0),
            (288.0, 468.0),
            (144.0, 468.0),
            (0.0, 468.0),
            (-144.0, 468.0),
        ]

    @staticmethod
    def _as_int(value: object, default: int = 0) -> int:
        try:
            if isinstance(value, bool):
                return int(value)
            if isinstance(value, int):
                return value
            if isinstance(value, float):
                return int(value)
            if isinstance(value, str):
                return int(value)
            if isinstance(value, SupportsInt):
                return int(value)
            if isinstance(value, SupportsIndex):
                return int(value)
        except Exception:
            pass
        return default

    # The three follow documents are process-wide singletons; constructing
    # Settings(name, "global") anywhere returns the same live document, so there
    # is nothing to pre-ensure or look up — just build the accessor and use it.
    def _formations_cfg(self) -> Settings:
        return Settings(f"{self.ini.global_ini_path}/{self.ini.formations_ini_name}", "global")

    def _settings_cfg(self) -> Settings:
        return Settings(f"{self.ini.global_ini_path}/{self.ini.settings_ini_name}", "global")

    def _runtime_cfg(self) -> Settings:
        return Settings(f"{self.ini.global_ini_path}/{self.ini.runtime_ini_name}", "global")

    def _load_ini_vars_once(
        self,
        cfg: Settings,
        force_var_refresh: bool = False,
        reload_from_disk: bool = False,
    ) -> None:
        # Followers pull cross-process edits the leader wrote to disk; reload()
        # is the legitimate escape hatch for that.
        try:
            if reload_from_disk:
                cfg.reload()
        except Exception:
            pass

    def _reload_thresholds(self) -> None:
        cfg = self._runtime_cfg()
        self.thresholds.default_follow_threshold = max(
            0.0,
            float(cfg.get_float(self.ini.runtime_section, "follow_move_threshold_default", float(Range.Area.value)))
        )
        self.thresholds.combat_follow_threshold = max(
            0.0,
            float(cfg.get_float(self.ini.runtime_section, "follow_move_threshold_combat", float(Range.Adjacent.value)))
        )
        self.thresholds.flagged_follow_threshold = max(
            0.0,
            float(cfg.get_float(self.ini.runtime_section, "follow_move_threshold_flagged", 0.0))
        )

    def _resolve_selected_formation_id(self) -> str:
        settings_cfg = self._settings_cfg()
        formations_cfg = self._formations_cfg()
        selected_id = str(settings_cfg.get_str(self.ini.formations_section, self.ini.selected_id_key, "") or "").strip()
        if selected_id:
            return selected_id

        selected_name = str(settings_cfg.get_str(self.ini.formations_section, self.ini.selected_name_key, "") or "").strip()
        formation_count = max(
            0,
            formations_cfg.get_int(self.ini.formations_section, self.ini.count_key, 0),
        )
        for index in range(formation_count):
            name = str(formations_cfg.get_str(self.ini.formations_section, f"name_{index}", "") or "").strip()
            if name == selected_name:
                return str(formations_cfg.get_str(self.ini.formations_section, f"id_{index}", "") or "").strip()
        for index in range(formation_count):
            formation_id = str(formations_cfg.get_str(self.ini.formations_section, f"id_{index}", "") or "").strip()
            if formation_id:
                return formation_id
        return ""

    def _resolve_selected_formation_section(self, selected_id: str) -> str:
        section = f"{self.ini.formation_id_prefix}{selected_id}"
        formations_cfg = self._formations_cfg()
        if formations_cfg.get_str(section, "name", ""):
            return section

        formation_count = max(0, formations_cfg.get_int(self.ini.formations_section, self.ini.count_key, 0))
        for index in range(formation_count):
            formation_id = str(formations_cfg.get_str(self.ini.formations_section, f"id_{index}", "") or "").strip()
            if formation_id == selected_id:
                name = str(formations_cfg.get_str(self.ini.formations_section, f"name_{index}", "") or "").strip()
                if name:
                    return f"{self.ini.formation_name_prefix}{name}"
                break
        return section

    def _reload_follow_points_from_ini(self) -> None:
        try:
            self._load_ini_vars_once(self._settings_cfg(), force_var_refresh=True, reload_from_disk=True)
            self._load_ini_vars_once(self._formations_cfg(), force_var_refresh=True, reload_from_disk=True)
            self._load_ini_vars_once(self._runtime_cfg(), force_var_refresh=True, reload_from_disk=True)
            self._reload_thresholds()

            selected_id = self._resolve_selected_formation_id()
            if not selected_id:
                self.state.selected_id_cache = "builtin_default"
                self.state.points_cache = self._get_default_follow_points()
                return

            section = self._resolve_selected_formation_section(selected_id)
            formations_cfg = self._formations_cfg()
            point_count = max(
                0,
                min(
                    self.ini.max_follow_slots,
                    formations_cfg.get_int(section, self.ini.point_count_key, 0),
                ),
            )
            points: list[tuple[float, float]] = []
            for index in range(point_count):
                x_key = self.ini.point_x_key_template.format(index=index)
                y_key = self.ini.point_y_key_template.format(index=index)
                x = float(formations_cfg.get_float(section, x_key, 0.0))
                y = float(formations_cfg.get_float(section, y_key, 0.0))
                points.append((x, y))

            self.state.selected_id_cache = selected_id
            self.state.points_cache = points if points else self._get_default_follow_points()
        except Exception:
            self.state.selected_id_cache = "builtin_default"
            self.state.points_cache = self._get_default_follow_points()

    def _get_follow_points(self) -> list[tuple[float, float]]:
        if (not self.state.points_cache) or self.ini_reload_timer.IsExpired():
            self._reload_follow_points_from_ini()
            self.ini_reload_timer.Reset()
        return self.state.points_cache

    @staticmethod
    def _rotate_local_to_world(local_x: float, local_y: float, facing_angle: float) -> tuple[float, float]:
        angle = float(facing_angle) - (math.pi / 2.0)
        c = -math.cos(angle)
        s = -math.sin(angle)
        return ((local_x * c) - (local_y * s), (local_x * s) + (local_y * c))

    @staticmethod
    def _same_party_and_map(a: AccountStruct, b: AccountStruct) -> bool:
        return (
            a.AgentPartyData.PartyID == b.AgentPartyData.PartyID and
            a.AgentData.Map.MapID == b.AgentData.Map.MapID and
            a.AgentData.Map.Region == b.AgentData.Map.Region and
            a.AgentData.Map.District == b.AgentData.Map.District and
            a.AgentData.Map.Language == b.AgentData.Map.Language
        )

    def _is_nonzero_vec2(self, vec: Vec2f) -> bool:
        return abs(float(vec.x)) > self.tuning.nonzero_epsilon or abs(float(vec.y)) > self.tuning.nonzero_epsilon

    def _reset_follow_slot(
        self,
        options: HeroAIOptionStruct,
        *,
        invalidate_flags: bool = False,
    ) -> None:
        options.FollowPos.x = 0.0
        options.FollowPos.y = 0.0
        options.FollowPos.z = 0.0
        options.FollowOffset.x = 0.0
        options.FollowOffset.y = 0.0
        options.FollowMoveThreshold = self.thresholds.disabled_threshold
        options.FollowMoveThresholdCombat = self.thresholds.disabled_threshold
        options.LeaderFollowReady = False
        if invalidate_flags:
            options.IsFlagged = False
            options.FlagPos.x = 0.0
            options.FlagPos.y = 0.0
            options.AllFlag.x = 0.0
            options.AllFlag.y = 0.0
            options.FlagFacingAngle = 0.0

    def _clear_follow_publish_state(
        self,
        all_accounts: AllAccounts,
        leader_index: int,
        *,
        invalidate_flags: bool = False,
    ) -> None:
        self.state.map_signature = None
        self.state.hold_until_leader_moves = False
        self.state.leader_entry_pos = None
        self.state.leader_in_combat_last = False
        self.state.combat_anchor_facing = None
        self.state.cached_navmesh = None
        for index in range(self.shared_memory_manager.max_num_players):
            account = all_accounts.AccountData[index]
            if (not account.IsAccount) or all_accounts._is_slot_isolated_from_viewer(index, leader_index):
                continue
            self._reset_follow_slot(all_accounts.HeroAIOptions[index], invalidate_flags=invalidate_flags)

    def _handle_map_signature_change(
        self,
        all_accounts: AllAccounts,
        leader_index: int,
        current_map_signature: tuple[int, int, int, int, int],
        leader_x: float,
        leader_y: float,
    ) -> None:
        self._clear_follow_publish_state(all_accounts, leader_index, invalidate_flags=True)
        self.state.map_signature = current_map_signature
        self.state.hold_until_leader_moves = True
        self.state.leader_entry_pos = (float(leader_x), float(leader_y))
        self.state.navmesh_recovery_attempts = 0
        self.state.cached_navmesh = None
        self.navmesh_recovery_timer.Reset()

    def _ensure_cached_navmesh_is_sane(self, leader_x: float, leader_y: float) -> bool:
        navmesh = self.state.cached_navmesh
        if navmesh is not None:
            return True

        navmesh = _get_navmesh()
        if navmesh is None:
            if not self.navmesh_recovery_timer.IsExpired():
                return False
            self.navmesh_recovery_timer.Reset()
            self.state.navmesh_recovery_attempts += 1
            try:
                Map.Pathing.ForceReloadNavMesh()
            except Exception:
                return False
            recovered = _get_navmesh()
            if recovered is None:
                return False
            try:
                if recovered.contains(leader_x, leader_y, self.tuning.navmesh_recovery_contains_margin):
                    self.state.navmesh_recovery_attempts = 0
                    self.state.cached_navmesh = recovered
                    return True
            except Exception:
                pass
            return False

        try:
            if navmesh.contains(leader_x, leader_y, self.tuning.navmesh_recovery_contains_margin):
                self.state.navmesh_recovery_attempts = 0
                self.state.cached_navmesh = navmesh
                return True
        except Exception:
            pass

        if not self.navmesh_recovery_timer.IsExpired():
            return False

        self.navmesh_recovery_timer.Reset()
        self.state.navmesh_recovery_attempts += 1
        try:
            Map.Pathing.ForceReloadNavMesh()
        except Exception:
            return False
        recovered = _get_navmesh()
        if recovered is None:
            return False
        try:
            if recovered.contains(leader_x, leader_y, self.tuning.navmesh_recovery_contains_margin):
                self.state.navmesh_recovery_attempts = 0
                self.state.cached_navmesh = recovered
                return True
        except Exception:
            pass
        return False

    def _get_cached_navmesh(self) -> NavMeshProtocol | None:
        return self.state.cached_navmesh

    def _apply_idle_slot(self, options: HeroAIOptionStruct) -> None:
        options.FollowPos.x = 0.0
        options.FollowPos.y = 0.0
        options.FollowPos.z = 0.0
        options.FollowOffset.x = 0.0
        options.FollowOffset.y = 0.0
        options.FollowMoveThreshold = self.thresholds.disabled_threshold
        options.FollowMoveThresholdCombat = self.thresholds.disabled_threshold
        options.LeaderFollowReady = False

    def _apply_missing_point_slot(self, options: HeroAIOptionStruct, account: AccountStruct, leader_zplane: int) -> None:
        options.FollowOffset.x = 0.0
        options.FollowOffset.y = 0.0
        if self.state.hold_until_leader_moves:
            options.FollowPos.x = float(account.AgentData.Pos.x)
            options.FollowPos.y = float(account.AgentData.Pos.y)
            options.FollowPos.z = float(leader_zplane)
        else:
            options.FollowPos.x = 0.0
            options.FollowPos.y = 0.0
            options.FollowPos.z = 0.0
        options.FollowMoveThreshold = self.thresholds.disabled_threshold
        options.FollowMoveThresholdCombat = self.thresholds.disabled_threshold
        options.LeaderFollowReady = False

    def _apply_held_slot(self, options: HeroAIOptionStruct, account: AccountStruct, leader_zplane: int) -> None:
        options.FollowPos.x = float(account.AgentData.Pos.x)
        options.FollowPos.y = float(account.AgentData.Pos.y)
        options.FollowPos.z = float(leader_zplane)

    def _get_fight_publisher(self):
        if self.fight_publisher is None:
            from HeroAI.fight.publisher import FightZonePublisher

            self.fight_publisher = FightZonePublisher()
        return self.fight_publisher

    def fight_terrain_probe(self, navmesh_sane: bool):
        """Standability test for the escape plotter, or None to say "no idea".

        Gated on the sanity flag rather than on the cache being populated: a
        cached mesh that failed its own leader-contains check is left in place
        by the recovery path, and a stale mesh reports open ground as wall,
        which would plot an escape route straight into geometry.
        """
        navmesh = self._get_cached_navmesh()
        if navmesh is None or not navmesh_sane:
            return None

        def probe(point: tuple[float, float]) -> bool:
            try:
                return bool(navmesh.contains(point[0], point[1], self.tuning.followpos_contains_margin))
            except Exception:
                return False

        return probe

    def _resolve_fight_plan(
        self,
        all_accounts: AllAccounts,
        leader_index: int,
        leader_account: AccountStruct,
        leader_options: HeroAIOptionStruct,
        leader_x: float,
        leader_y: float,
        navmesh_sane: bool,
    ):
        """Tick the fight zone and hand back its per-member slots.

        A hand-placed all-flag outranks the zone: the zone borrows the same field,
        so `fight_owns_all_flag` is what distinguishes "we wrote this" from "the
        user did". Without it the zone would read its own flag back as manual.
        """
        from HeroAI.fight.assignment import MemberLine

        manual_all_flag = (
            bool(leader_options.IsFlagged)
            and self._is_nonzero_vec2(leader_options.AllFlag)
            and not self.fight_owns_all_flag
        )
        publisher = self._get_fight_publisher()
        if manual_all_flag:
            publisher.assignment.clear()
            return None

        member_lines: list[MemberLine] = []
        member_positions: list[tuple[int, tuple[float, float]]] = []
        party_health: dict[int, float] = {}
        party_target_ids: dict[int, int] = {}
        party_in_aggro = False
        for index in range(self.shared_memory_manager.max_num_players):
            account = all_accounts.AccountData[index]
            if not (account.IsSlotActive and account.IsAccount) or all_accounts._is_slot_isolated_from_viewer(
                index, leader_index
            ):
                continue
            if not self._same_party_and_map(leader_account, account):
                continue
            if bool(getattr(account, "InAggro", False)):
                party_in_aggro = True
            party_position = int(account.AgentPartyData.PartyPosition)
            if party_position <= 0:
                continue
            character_name = str(getattr(account.AgentData, "CharacterName", "") or "")
            primary_profession = int(account.AgentData.Profession[0])
            resolved = publisher.resolve_member_line(character_name, primary_profession)
            member_lines.append(MemberLine(party_position, character_name, resolved.line))
            member_positions.append((party_position, (float(account.AgentData.Pos.x), float(account.AgentData.Pos.y))))
            health = account.AgentData.Health
            max_health = float(getattr(health, "Max", 0.0) or 0.0)
            if max_health > 0.0:
                party_health[party_position] = float(getattr(health, "Current", 0.0)) / max_health
            party_target_ids[party_position] = int(getattr(account.AgentData, "TargetID", 0) or 0)

        plan = publisher.tick(
            leader_xy=(leader_x, leader_y),
            member_lines=member_lines,
            member_positions=member_positions,
            party_in_aggro=party_in_aggro,
            leader_local_aggro=bool(getattr(leader_account, "InAggro", False)),
            loot_pending=self._is_loot_pending(),
            now_ms=int(Utils.GetBaseTimestamp()),
            party_health=party_health,
            party_target_ids=party_target_ids,
            terrain_probe=self.fight_terrain_probe(navmesh_sane),
        )
        self._apply_fight_all_flag(leader_options, plan)
        return plan if plan.is_active() else None

    def _is_loot_pending(self) -> bool:
        try:
            from Py4GWCoreLib.py4gwcorelib_src.loot_filters import LootFilters

            return len(LootFilters().GetLootArray(float(Range.Earshot.value))) > 0
        except Exception:
            return False

    def _apply_fight_all_flag(self, leader_options: HeroAIOptionStruct, plan) -> None:
        if plan.is_active():
            leader_options.IsFlagged = True
            leader_options.AllFlag.x = float(plan.zone.anchor_x)
            leader_options.AllFlag.y = float(plan.zone.anchor_y)
            leader_options.FlagFacingAngle = float(plan.zone.facing)
            self.fight_owns_all_flag = True
            return
        if self.fight_owns_all_flag:
            leader_options.IsFlagged = False
            leader_options.AllFlag.x = 0.0
            leader_options.AllFlag.y = 0.0
            leader_options.FlagFacingAngle = 0.0
            self.fight_owns_all_flag = False

    def _publish_fight_slot(
        self,
        options: HeroAIOptionStruct,
        slot,
        leader_zplane: int,
        anchor_xy: tuple[float, float],
        *,
        bypass_validation: bool = False,
    ) -> None:
        """Fight slots deliberately do NOT pass fallback_candidates.

        Those candidates are party positions, so an off-mesh pin would snap to a
        midpoint between party members — i.e. back into the travelling blob
        behind the leader, while the zone still reads HOLDING. Falling back to
        the zone anchor keeps a bad pin inside the fight.
        """
        options.FollowOffset.x = 0.0
        options.FollowOffset.y = 0.0
        options.FollowMoveThreshold = float(slot.tolerance)
        options.FollowMoveThresholdCombat = float(slot.tolerance)
        pos_x, pos_y = self._validate_followpos(
            float(slot.world_x),
            float(slot.world_y),
            float(anchor_xy[0]),
            float(anchor_xy[1]),
            int(leader_zplane),
            bypass_validation=bypass_validation,
            fallback_candidates=None,
        )
        options.FollowPos.x = pos_x
        options.FollowPos.y = pos_y
        options.FollowPos.z = float(leader_zplane)
        options.LeaderFollowReady = True

    def _apply_personal_flag_slot(self, options: HeroAIOptionStruct, leader_zplane: int) -> None:
        options.FollowPos.x = float(options.FlagPos.x)
        options.FollowPos.y = float(options.FlagPos.y)
        options.FollowPos.z = float(leader_zplane)
        options.FollowMoveThreshold = self.thresholds.flagged_follow_threshold
        options.FollowMoveThresholdCombat = self.thresholds.flagged_follow_threshold

    def _update_combat_anchor_facing(self, leader_in_combat: bool, leader_facing: float) -> None:
        if leader_in_combat:
            if (not self.state.leader_in_combat_last) or self.state.combat_anchor_facing is None:
                self.state.combat_anchor_facing = float(leader_facing)
        else:
            self.state.combat_anchor_facing = None
        self.state.leader_in_combat_last = leader_in_combat

    def _is_combat_active_for_mode(
        self,
        all_accounts: AllAccounts,
        leader_index: int,
        leader_account: AccountStruct,
    ) -> bool:
        from HeroAI.settings import Settings

        mode = Settings().get_combat_range_mode()
        if int(getattr(leader_account.AgentPartyData, "PartyPosition", -1)) == 0:
            return bool(getattr(leader_account, "InAggro", False))
        if mode == Settings.COMBAT_RANGE_MODE_LEGACY:
            return bool(getattr(leader_account, "InAggro", False))

        for index in range(self.shared_memory_manager.max_num_players):
            account = all_accounts.AccountData[index]
            if not (account.IsSlotActive and account.IsAccount) or all_accounts._is_slot_isolated_from_viewer(index, leader_index):
                continue
            if not self._same_party_and_map(leader_account, account):
                continue
            if bool(getattr(account, "InAggro", False)):
                return True
        return False

    def _resolve_anchor(
        self,
        leader_options: HeroAIOptionStruct,
        leader_x: float,
        leader_y: float,
        leader_facing: float,
        leader_in_combat: bool,
    ) -> tuple[float, float, float, float, float]:
        if bool(leader_options.IsFlagged) and self._is_nonzero_vec2(leader_options.AllFlag):
            return (
                float(leader_options.AllFlag.x),
                float(leader_options.AllFlag.y),
                float(leader_options.FlagFacingAngle),
                self.thresholds.flagged_follow_threshold,
                self.thresholds.flagged_follow_threshold,
            )
        return (
            float(leader_x),
            float(leader_y),
            float(self.state.combat_anchor_facing if leader_in_combat and self.state.combat_anchor_facing is not None else leader_facing),
            self.thresholds.default_follow_threshold,
            self.thresholds.combat_follow_threshold,
        )

    def _validate_followpos(
        self,
        raw_x: float,
        raw_y: float,
        fallback_x: float,
        fallback_y: float,
        leader_zplane: int,
        *,
        bypass_validation: bool = False,
        fallback_candidates: list[tuple[float, float]] | None = None,
    ) -> tuple[float, float]:
        """Use the raw FollowPos when a body can stand there AND walk to it.

        Standing and reaching are separate questions and the navmesh answers them
        with separate calls. A point can sit squarely on the mesh and still be a
        ledge, a balcony or the far side of a wall - on-mesh, and impossible to
        enter. Checking only contains() publishes those, and followers walk into
        geometry forever.

        Reachability is measured from the anchor, so "can this member get to its
        pin" is the question actually being asked. A bad anchor makes every slot
        fail it at once, which degrades to the anchor rather than to nothing.
        """

        navmesh = self._get_cached_navmesh()
        if navmesh is None:
            return (raw_x, raw_y)
        # An untrustworthy mesh must not be searched at all: nudging a good pin
        # on bad geometry is worse than publishing it unvalidated.
        if bypass_validation:
            return (raw_x, raw_y)

        origin = (float(fallback_x), float(fallback_y))
        max_fallback_distance = float(Range.Spellcast.value)

        def _resolve_candidate(candidate_x: float, candidate_y: float) -> tuple[float, float] | None:
            try:
                resolved = resolve_placement(navmesh, (float(candidate_x), float(candidate_y)), origin, PLACEMENT_CFG)
            except Exception:
                return None
            if resolved is None:
                return None
            if math.hypot(resolved[0] - fallback_x, resolved[1] - fallback_y) > max_fallback_distance:
                return None
            return (float(resolved[0]), float(resolved[1]))

        placed = _resolve_candidate(raw_x, raw_y)
        if placed is not None:
            return placed

        candidate_centers = [
            (float(candidate_x), float(candidate_y))
            for candidate_x, candidate_y in (fallback_candidates or [])
        ]

        midpoint_candidates: list[tuple[float, float]] = []
        candidate_count = len(candidate_centers)
        for i in range(candidate_count):
            left_x, left_y = candidate_centers[i]
            for j in range(i + 1, candidate_count):
                right_x, right_y = candidate_centers[j]
                midpoint_candidates.append(
                    ((left_x + right_x) / 2.0, (left_y + right_y) / 2.0)
                )

        midpoint_candidates.sort(key=lambda pos: math.hypot(pos[0] - raw_x, pos[1] - raw_y))
        for midpoint_x, midpoint_y in midpoint_candidates:
            resolved_midpoint = _resolve_candidate(midpoint_x, midpoint_y)
            if resolved_midpoint is not None:
                return resolved_midpoint

        candidate_centers.sort(key=lambda pos: math.hypot(pos[0] - raw_x, pos[1] - raw_y))
        adjacent_radius = float(Range.Adjacent.value)
        for center_x, center_y in candidate_centers:
            vec_x = raw_x - center_x
            vec_y = raw_y - center_y
            length = math.hypot(vec_x, vec_y)
            if length <= 0.001:
                norm_x, norm_y = 0.0, -1.0
            else:
                norm_x, norm_y = vec_x / length, vec_y / length

            tang_x, tang_y = -norm_y, norm_x
            search_points = [
                (center_x + (norm_x * adjacent_radius), center_y + (norm_y * adjacent_radius)),
                (center_x - (norm_x * adjacent_radius), center_y - (norm_y * adjacent_radius)),
                (center_x + (tang_x * adjacent_radius), center_y + (tang_y * adjacent_radius)),
                (center_x - (tang_x * adjacent_radius), center_y - (tang_y * adjacent_radius)),
                (center_x, center_y),
            ]

            for candidate_x, candidate_y in search_points:
                resolved_candidate = _resolve_candidate(candidate_x, candidate_y)
                if resolved_candidate is not None:
                    return resolved_candidate

        return (fallback_x, fallback_y)

    def _publish_active_slot(
        self,
        options: HeroAIOptionStruct,
        local_x: float,
        local_y: float,
        anchor_x: float,
        anchor_y: float,
        facing: float,
        leader_zplane: int,
        move_threshold: float,
        combat_threshold: float,
        *,
        bypass_validation: bool = False,
        fallback_candidates: list[tuple[float, float]] | None = None,
    ) -> None:
        options.FollowOffset.x = float(local_x)
        options.FollowOffset.y = float(local_y)
        options.FollowMoveThreshold = float(move_threshold)
        options.FollowMoveThresholdCombat = float(combat_threshold)
        rx, ry = self._rotate_local_to_world(local_x, local_y, facing)
        # Snap-or-fallback against navmesh; bails to anchor on elevated terrain.
        pos_x, pos_y = self._validate_followpos(
            float(anchor_x + rx),
            float(anchor_y + ry),
            float(anchor_x),
            float(anchor_y),
            int(leader_zplane),
            bypass_validation=bypass_validation,
            fallback_candidates=fallback_candidates,
        )
        options.FollowPos.x = pos_x
        options.FollowPos.y = pos_y
        options.FollowPos.z = float(leader_zplane)
        options.LeaderFollowReady = True

    def refresh_from_ini(self) -> None:
        self._reload_follow_points_from_ini()
        self.ini_reload_timer.Reset()

    def publish(self, force: bool = False) -> None:
        account_email = Player.GetAccountEmail()
        if not account_email:
            return
        if Party.GetPartySize() <= 1:
            return

        all_accounts: AllAccounts = self.shared_memory_manager.GetAllAccounts()
        leader_index = all_accounts.GetSlotByEmail(account_email)
        if leader_index < 0:
            return

        leader_account: AccountStruct = all_accounts.AccountData[leader_index]
        leader_options: HeroAIOptionStruct = all_accounts.HeroAIOptions[leader_index]
        if not leader_account.IsSlotActive or not leader_account.IsAccount:
            return

        if (not Map.IsMapReady()) or Map.IsMapLoading() or (not Map.IsExplorable()):
            self._clear_follow_publish_state(all_accounts, leader_index, invalidate_flags=True)
            return

        if not Party.IsPartyLoaded():
            return
        leader_agent_id = Party.GetPartyLeaderID()
        if not Agent.IsValid(leader_agent_id):
            return
        if Player.GetAgentID() != leader_agent_id:
            return

        points = self._get_follow_points()
        leader_x, leader_y = Player.GetXY()
        leader_zplane = int(Agent.GetZPlane(leader_agent_id))
        leader_facing = Agent.GetRotationAngle(leader_agent_id)

        current_map_signature = (
            self._as_int(leader_account.AgentData.Map.MapID),
            self._as_int(leader_account.AgentData.Map.Region),
            self._as_int(leader_account.AgentData.Map.District),
            self._as_int(leader_account.AgentData.Map.Language),
            self._as_int(leader_account.AgentPartyData.PartyID),
        )
        if self.state.map_signature != current_map_signature:
            self._handle_map_signature_change(
                all_accounts,
                leader_index,
                current_map_signature,
                leader_x,
                leader_y,
            )
        leader_navmesh_sane = self._ensure_cached_navmesh_is_sane(leader_x, leader_y)
        bypass_validation = not leader_navmesh_sane

        if self.state.hold_until_leader_moves and self.state.leader_entry_pos is not None:
            entry_x, entry_y = self.state.leader_entry_pos
            if Utils.Distance((leader_x, leader_y), (entry_x, entry_y)) > self.tuning.leader_move_release_distance:
                self.state.hold_until_leader_moves = False

        leader_in_combat = self._is_combat_active_for_mode(all_accounts, leader_index, leader_account)
        if not force:
            if leader_in_combat:
                if not self.combat_publish_timer.IsExpired():
                    return
                self.combat_publish_timer.Reset()
                self.publish_timer.Reset()
            else:
                if not self.publish_timer.IsExpired():
                    return
                self.publish_timer.Reset()
                self.combat_publish_timer.Reset()

        fight_plan = self._resolve_fight_plan(
            all_accounts,
            leader_index,
            leader_account,
            leader_options,
            leader_x,
            leader_y,
            leader_navmesh_sane,
        )

        self._update_combat_anchor_facing(leader_in_combat, leader_facing)
        anchor_x, anchor_y, anchor_facing, move_threshold, combat_threshold = self._resolve_anchor(
            leader_options,
            leader_x,
            leader_y,
            leader_facing,
            leader_in_combat,
        )
        party_positions: list[tuple[float, float]] = []
        for index in range(self.shared_memory_manager.max_num_players):
            account = all_accounts.AccountData[index]
            if not (account.IsSlotActive and account.IsAccount) or all_accounts._is_slot_isolated_from_viewer(index, leader_index):
                continue
            if not self._same_party_and_map(leader_account, account):
                continue
            party_positions.append((float(account.AgentData.Pos.x), float(account.AgentData.Pos.y)))

        for index in range(self.shared_memory_manager.max_num_players):
            account: AccountStruct = all_accounts.AccountData[index]
            if not (account.IsSlotActive and account.IsAccount) or all_accounts._is_slot_isolated_from_viewer(index, leader_index):
                continue
            if not self._same_party_and_map(leader_account, account):
                continue

            party_pos = int(account.AgentPartyData.PartyPosition)
            options: HeroAIOptionStruct = all_accounts.HeroAIOptions[index]

            if party_pos <= 0:
                self._apply_idle_slot(options)
                continue

            slot_index = party_pos - 1
            if slot_index < 0 or slot_index >= len(points):
                self._apply_missing_point_slot(options, account, leader_zplane)
                continue

            local_x, local_y = points[slot_index]
            options.FollowOffset.x = float(local_x)
            options.FollowOffset.y = float(local_y)
            options.FollowMoveThreshold = float(self.thresholds.default_follow_threshold)
            options.FollowMoveThresholdCombat = float(self.thresholds.combat_follow_threshold)
            options.LeaderFollowReady = False
            fallback_candidates = [
                pos for pos in party_positions
                if abs(float(pos[0]) - float(account.AgentData.Pos.x)) > self.tuning.nonzero_epsilon
                or abs(float(pos[1]) - float(account.AgentData.Pos.y)) > self.tuning.nonzero_epsilon
            ]

            if self.state.hold_until_leader_moves:
                self._apply_held_slot(options, account, leader_zplane)
                continue

            if bool(options.IsFlagged) and self._is_nonzero_vec2(options.FlagPos):
                self._apply_personal_flag_slot(options, leader_zplane)
                continue

            if fight_plan is not None:
                fight_slot = fight_plan.slots.get(party_pos)
                if fight_slot is not None:
                    self._publish_fight_slot(
                        options,
                        fight_slot,
                        leader_zplane,
                        fight_plan.zone.anchor(),
                        bypass_validation=bypass_validation,
                    )
                    continue

            if leader_in_combat:
                self._publish_active_slot(
                    options,
                    local_x,
                    local_y,
                    anchor_x,
                    anchor_y,
                    anchor_facing,
                    leader_zplane,
                    move_threshold,
                    combat_threshold,
                    bypass_validation=bypass_validation,
                    fallback_candidates=fallback_candidates,
                )
                continue

            self._publish_active_slot(
                options,
                local_x,
                local_y,
                anchor_x,
                anchor_y,
                anchor_facing,
                leader_zplane,
                move_threshold,
                combat_threshold,
                bypass_validation=bypass_validation,
                fallback_candidates=fallback_candidates,
            )
