"""Predictive collision steering for Py4GW Player.Move calls.

The BT planner keeps its own waypoint/local-avoidance state.  This controller
serves *other* callers (HeroAI followers, direct scripts, FollowXY, etc.) and
restores their originally requested destination after a temporary detour.
It executes independently in every GW client; no shared-memory commands are
used to move a different character.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from ..routines_src.behaviourtrees_src.local_avoidance import (
    CircularObstacle, choose_avoidance_target, find_first_blocker,
)


@dataclass
class _MoveIntent:
    destination: tuple[float, float]
    zplane: int
    map_id: int
    waypoint: tuple[float, float] | None = None
    side: int = 0
    blocker_id: int = 0
    last_command_ms: int = 0
    last_eval_ms: int = 0
    last_progress_xy: tuple[float, float] | None = None
    last_progress_ms: int = 0


# Set True to display informational [ProactiveMove] messages.
SHOW_AVOIDANCE_LOGS = False


class ProactiveMoveController:
    """Frame-based local avoidance, not a global path planner."""

    LOOKAHEAD = 750.0
    STEERING_DISTANCE = 390.0
    CLEARANCE = 65.0
    EVAL_INTERVAL_MS = 200
    MIN_COMMAND_INTERVAL_MS = 550
    ARRIVAL_TOLERANCE = 85.0
    DETOUR_ARRIVAL = 125.0
    PROGRESS_TIMEOUT_MS = 7500

    def __init__(self):
        self.intent: Optional[_MoveIntent] = None
        self._callback_registered = False
        self._navmesh_gen = None
        self._navmesh_map_id = 0

    @staticmethod
    def _now() -> int:
        from ..Py4GWcorelib import Utils
        return int(Utils.GetBaseTimestamp())

    @staticmethod
    def _issue_raw(x: float, y: float, zplane: int) -> None:
        from .ActionQueue import ActionQueueManager
        from ..native_src.methods.PlayerMethods import PlayerMethods
        ActionQueueManager().AddAction('ACTION', PlayerMethods.Move, float(x), float(y), int(zplane))

    def reset(self) -> None:
        self.intent = None
        self._navmesh_gen = None

    @staticmethod
    def _log(message: str) -> None:
        if not SHOW_AVOIDANCE_LOGS:
            return
        try:
            from .Console import ConsoleLog, Console
            ConsoleLog('ProactiveMove', message, Console.MessageType.Info, log=True)
        except Exception:
            pass

    def _register(self) -> None:
        if self._callback_registered:
            return
        import PyCallback
        # Registered once per game client. There is no widget enable dependency.
        PyCallback.PyCallback.Register(
            'Player.ProactiveMoveController', PyCallback.Phase.Update,
            self.tick, priority=86,
        )
        self._callback_registered = True

    def request(self, x: float, y: float, zplane: int = 0) -> None:
        """A new Player.Move replaces previous movement intent."""
        from ..Map import Map
        from ..Player import Player

        dest = (float(x), float(y))
        zplane = int(zplane)
        if not math.isfinite(dest[0]) or not math.isfinite(dest[1]):
            return
        # Preserve old Player.Move(0, 0) stop/reset semantics.
        if dest == (0.0, 0.0) or not Map.IsMapReady():
            self.reset()
            self._issue_raw(*dest, zplane)
            return
        try:
            current = Player.GetXY()
            map_id = int(Map.GetMapID() or 0)
            if not Player.IsPlayerLoaded():
                self.reset()
                self._issue_raw(*dest, zplane)
                return
            previous = self.intent
            if (previous is not None and previous.map_id == map_id
                    and previous.zplane == zplane
                    and math.dist(dest, previous.destination) < 15.0):
                # The follower can refresh the same follow point every tick.
                # Do not override an in-flight local detour with the raw goal.
                return
            self.intent = _MoveIntent(dest, zplane, map_id)
            self._register()
            self._update(force=True)
        except Exception:
            # Movement must never fail just because the predictive helper did.
            self.reset()
            self._issue_raw(*dest, zplane)

    def _navmesh(self, map_id: int):
        from ..Pathing import AutoPathing
        pathing = AutoPathing()
        mesh = pathing.get_navmesh()
        if mesh is not None:
            self._navmesh_gen = None
            return mesh
        if self._navmesh_map_id != map_id:
            self._navmesh_gen = None
            self._navmesh_map_id = map_id
        if self._navmesh_gen is None:
            self._navmesh_gen = pathing.load_pathing_maps()
        try:
            next(self._navmesh_gen)
        except StopIteration:
            self._navmesh_gen = None
        return pathing.get_navmesh()

    @staticmethod
    def _collect(current: tuple[float, float]) -> list[CircularObstacle]:
        from ..Agent import Agent
        from ..AgentArray import AgentArray
        from ..Player import Player
        from ..enums_src.GameData_enums import Allegiance
        from ..routines_src.Party import Party as PartyRoutines

        player_id = int(Player.GetAgentID() or 0)
        player_agent = Agent.GetAgentByID(player_id)
        if not player_agent:
            return []
        plane = int(player_agent.pos.zplane)
        width, _ = Agent.GetModelScale1(player_id)
        width = abs(float(width or 0))
        own_radius = max(32., min(160., width * 0.5)) if 1 < width < 500 else 48.
        passable = {
            int(Allegiance.Ally.value), int(Allegiance.SpiritPet.value),
            int(Allegiance.Minion.value),
        }
        scan_radius_sq = (ProactiveMoveController.LOOKAHEAD + 250.) ** 2
        result = []
        for value in AgentArray.GetAgentArray():
            agent_id = int(value or 0)
            if not agent_id or agent_id == player_id:
                continue
            agent = Agent.GetAgentByID(agent_id)
            if agent is None or int(agent.pos.zplane) != plane:
                continue
            xx, yy = float(agent.pos.x), float(agent.pos.y)
            if (xx-current[0])**2+(yy-current[1])**2 > scan_radius_sq:
                continue
            obstacle_radius = None
            if agent.is_living_type:
                living = agent.GetAsAgentLiving()
                if living is None or living.is_dead or not living.is_alive:
                    continue
                if PartyRoutines.IsPartyMember(agent_id):
                    continue
                if int(living.allegiance or 0) in passable:
                    continue
                if int(living.login_number or 0) and int(living.allegiance or 0) != 3:
                    continue
                width, _ = Agent.GetModelScale1(agent_id)
                width = abs(float(width or 0))
                obstacle_radius = max(32., min(160., width*0.5)) if 1 < width < 500 else 48.
            elif agent.is_gadget_type:
                width = abs(float(agent.width1 or 0.))
                if math.isfinite(width) and 1 < width < 800:
                    obstacle_radius = max(16., min(220., width*0.5))
            if obstacle_radius is not None:
                result.append(CircularObstacle(agent_id, (xx, yy),
                                               own_radius+obstacle_radius+ProactiveMoveController.CLEARANCE))
        return result

    def _update(self, *, force: bool = False) -> None:
        from ..Map import Map
        from ..Player import Player
        from .ActionQueue import ActionQueueManager
        from ..Agent import Agent

        intent = self.intent
        if intent is None:
            return
        if not Map.IsMapReady() or int(Map.GetMapID() or 0) != intent.map_id or not Player.IsPlayerLoaded():
            self.reset()
            return
        pid = int(Player.GetAgentID() or 0)
        if pid <= 0 or Agent.IsDead(pid):
            self.reset()
            return
        current = Player.GetXY()
        now = self._now()
        if math.dist(current, intent.destination) <= self.ARRIVAL_TOLERANCE:
            self.reset()
            return
        if not force and now - intent.last_eval_ms < self.EVAL_INTERVAL_MS:
            return
        intent.last_eval_ms = now
        if intent.last_progress_xy is None or math.dist(current, intent.last_progress_xy) >= 50.:
            intent.last_progress_xy = current
            intent.last_progress_ms = now
        elif not force and now - intent.last_progress_ms > self.PROGRESS_TIMEOUT_MS:
            # Do not fight the caller's own unstuck/combat recovery forever.
            self.reset()
            return
        if not force and not ActionQueueManager().IsEmpty('ACTION'):
            return

        obstacles = self._collect(current)
        blocker = find_first_blocker(current, intent.destination, obstacles, lookahead=self.LOOKAHEAD)
        proposed = intent.destination
        detour_blocker_id = 0
        if blocker is not None:
            # Never steer into a solid wall: temporary points need a navmesh.
            mesh = self._navmesh(intent.map_id)
            if mesh is not None:
                def walkable(start, end):
                    try:
                        return bool(mesh.contains(end[0], end[1], margin=5.)
                            and mesh.has_line_of_sight(start, end, margin=5., step_dist=50.))
                    except Exception:
                        return False
                decision = choose_avoidance_target(
                    current, intent.destination, obstacles,
                    lookahead=self.LOOKAHEAD,
                    steering_distance=self.STEERING_DISTANCE,
                    preferred_side=intent.side,
                    is_walkable=walkable,
                )
                if decision is not None:
                    intent.side = decision.side
                    proposed = decision.target
                    detour_blocker_id = decision.blocker_id

        if intent.waypoint is not None and not force:
            waypoint_distance = math.dist(current, intent.waypoint)
            difference = math.dist(proposed, intent.waypoint)
            # Keep a chosen side until we pass its waypoint. Moving agents
            # should not trigger left/right oscillation on every frame.
            if (waypoint_distance > self.DETOUR_ARRIVAL and difference < 200
                and now - intent.last_command_ms < 1200):
                return
            if (waypoint_distance > self.DETOUR_ARRIVAL and difference < 75):
                return
            if (now - intent.last_command_ms < self.MIN_COMMAND_INTERVAL_MS):
                return
        previous_blocker_id = intent.blocker_id
        intent.blocker_id = detour_blocker_id
        intent.waypoint = proposed
        intent.last_command_ms = now
        self._issue_raw(*proposed, intent.zplane)
        if detour_blocker_id and detour_blocker_id != previous_blocker_id:
            self._log(f'Obstacle {detour_blocker_id} ahead: steering towards '
                      f'({proposed[0]:.0f}, {proposed[1]:.0f}) '
                      f'then destination ({intent.destination[0]:.0f}, {intent.destination[1]:.0f}).')
        elif previous_blocker_id and not detour_blocker_id:
            self._log('Corridor clear: resuming original destination.')
        # Keep checking even after issuing the original destination: a new
        # obstacle can enter the corridor *after* the initial move command.
        # Completion/map change or a later caller's Move resets this intent.

    def tick(self) -> None:
        """Advance current steering after game data is refreshed every frame."""
        if self.intent is None:
            return
        try:
            self._update()
        except Exception:
            # Never throw into PyCallback's update loop.
            self.reset()


PROACTIVE_MOVE = ProactiveMoveController()
