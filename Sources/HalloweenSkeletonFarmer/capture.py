"""Named movement/skill pilot with retained capture/resign; initially stopped."""
import math
import time
import json
import traceback
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import PyImGui
from Py4GWCoreLib import Agent, AgentArray, GLOBAL_CACHE, ImGui, Item, Map, Party, Player, Routines
from Py4GWCoreLib.py4gwcorelib_src.Settings import Settings
from Py4GWCoreLib.py4gwcorelib_src.BehaviorTree import BehaviorTree
from Py4GWCoreLib.routines_src.BehaviourTrees import BT
from Py4GWCoreLib.routines_src.behaviourtrees_src.movement import BTMovement
from Py4GWCoreLib.routines_src.behaviourtrees_src.items import BTItems

MODULE_NAME = "Capture Skeleton (Halloween)"
BUILD_ID = "skelly-movement-skills-20261031-v32-generic-bar"
SKELETON_IDENTITY = r"\x8102\x5C24\xD4AD\xA729\x57DF"
MOBSTOPPER = 32558
CAPTURED_SKELETON = 32559
CONFIRM_TIMEOUT = 5.0
POLL_INTERVAL = 0.5
VISIT_LIMIT_MS = 10_000
LOOT_RANGE = 600.0
LOOT_TIMEOUT_MS = 2500
SHADOWSTEP_RANGE = 1248.0
FALLBACK_MIN_GAIN = 200.0
FALLBACK_TIMEOUT = 2.0
SKELETON_ORIGIN = (-1199.33, 6765.72)
SKELETON_SEARCH_RADIUS = 1000.0
# ROUTE-20261019-153642-769: stale map-entry/outpost samples excluded.
HALLOWEEN_ROUTE = ((643.88, 6949.83), (216.58, 6685.64), (-287.84, 6589.93),
                   (-787.58, 6636.70), (-1291.56, 6621.59))
EXPECTED_SKILLS = ("Whirling_Defense", "Dash", "Deaths_Charge", "Light_of_Deldrimor",
                   "You_Move_Like_a_Dwarf", "Finish_Him")
MONK_SKILLS = ("Dash", "Deaths_Charge", "Light_of_Deldrimor", "You_Move_Like_a_Dwarf",
               "Protective_Spirit", "Shielding_Hands", "Mark_of_Protection", "Unseen_Fury")
SKILL_ROLES = {
    1: ('Dash',), 2: ('Deaths_Charge','Dark_Prison'),
    3: ('Light_of_Deldrimor',), 4: ('You_Move_Like_a_Dwarf',),
    5: ('Protective_Spirit',), 6: ('Shielding_Hands',), 7: ('Mark_of_Protection',),
    8: ('Unseen_Fury',), 9: ('Finish_Him',),
    10: ('Deaths_Retreat','Return'), 11: ('Whirling_Defense',),
    12: ('By_Urals_Hammer',),
}


def capturable(agent_id: int) -> bool:
    """Positive current identity/life evidence; zero HP alone is not death."""
    if (not Agent.IsValid(agent_id) or not Agent.IsLiving(agent_id)
            or Agent.GetEncNameStrByID(agent_id, literal=True) != SKELETON_IDENTITY):
        return False
    return Agent.IsDead(agent_id) or 0 < Agent.GetHealth(agent_id) <= 0.25


def _log_directory() -> Path:
    source = Path(__file__).resolve()
    for parent in source.parents:
        if parent.name in ("Widgets", "Sources"):
            return parent.parent / "Logs" / "HalloweenSkeleton"
    return source.parent / "Logs" / "HalloweenSkeleton"


class RunJournal:
    """Durable bounded-event telemetry. Failure files are never pruned."""
    KEEP_SUCCESSES = 30
    MAX_VISIT_BYTES = 262144

    def __init__(self, root: Path) -> None:
        self.root = root
        self.path: Path | None = None
        self.run_id = ""
        self.failed = False
        self.bytes_written = 0
        self.error = ""
        self.readiness_path = self.root / f"readiness-{uuid4().hex}.jsonl"

    def readiness(self, event: str, **data) -> None:
        """Pre-visit evidence: bounded separate stream, copied into visit files."""
        if self.error:
            return
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            record = dict(utc=datetime.now(timezone.utc).isoformat(), build=BUILD_ID,
                          run=self.run_id, event=event, data=data)
            with self.readiness_path.open('a', encoding='utf-8', newline='\n') as handle:
                handle.write(json.dumps(record, default=repr) + '\n')
                handle.flush()
            if self.readiness_path.stat().st_size >= 262144:
                self.readiness_path = self.root / f"readiness-{uuid4().hex}.jsonl"
            traces = sorted(self.root.glob('readiness-*.jsonl'),
                            key=lambda p:p.stat().st_mtime_ns, reverse=True)
            for old in traces[3:]:
                if old.is_file() and not old.is_symlink():
                    old.unlink()
        except Exception as exc:
            self._error(exc)

    def _error(self, exc) -> None:
        if not self.error:
            self.error = f"{type(exc).__name__}: {exc}"
            print(f"[{MODULE_NAME}] Persistent logging unavailable: {self.error}")

    def begin(self, **data) -> None:
        if self.path is not None:
            return
        self.run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid4().hex
        self.path = self.root / f"active-{self.run_id}.jsonl"
        self.failed = False
        self.bytes_written = 0
        self.emit('visit_started', **data)

    def emit(self, event: str, **data) -> None:
        if self.path is None or self.error:
            return
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            record = dict(utc=datetime.now(timezone.utc).isoformat(), build=BUILD_ID,
                          run=self.run_id, event=event, data=data)
            payload = json.dumps(record, default=repr, ensure_ascii=True) + '\n'
            if self.bytes_written + len(payload.encode('utf-8')) > self.MAX_VISIT_BYTES:
                return
            self.bytes_written += len(payload.encode('utf-8'))
            # Close each event so it remains readable after game termination.
            with self.path.open('a', encoding='utf-8', newline='\n') as handle:
                handle.write(payload)
                handle.flush()
        except Exception as exc:
            self._error(exc)

    def failure(self, reason: str, **data) -> None:
        self.failed = True
        self.emit('failure', reason=reason, **data)
        if self.path is not None and not self.error and not self.path.name.startswith('failure-'):
            try:
                target = self.root / f"failure-{self.run_id}.jsonl"
                self.path.rename(target)
                self.path = target
            except Exception as exc:
                self.emit('retention_warning', message=f"Could not rename failure log: {exc}")

    def finish(self, outcome: str) -> None:
        if self.path is None:
            return
        self.emit('visit_finished', outcome=outcome)
        try:
            if not self.error and outcome == 'confirmed' and not self.failed:
                target = self.root / f"success-{self.run_id}.jsonl"
                self.path.rename(target)
                # Only our clean-success files are eligible for deletion.
                successes = sorted((p for p in self.root.glob('success-*.jsonl')
                                    if p.is_file() and not p.is_symlink()),
                                   key=lambda p: (p.stat().st_mtime_ns, p.name), reverse=True)
                for old in successes[self.KEEP_SUCCESSES:]:
                    old.unlink()
        except Exception as exc:
            self.emit('retention_warning', message=f"Could not rotate successful log: {exc}")
        self.path = None


def _walking_route() -> BehaviorTree:
    return BTMovement.MovePath(pos=list(HALLOWEEN_ROUTE), pause_on_combat=False,
                               tolerance=100.0, resume_key="halloween_skellies_v6", log=True)


def _corpse_approach(xy: tuple[float, float]) -> BehaviorTree:
    return BTMovement.MovePath(pos=xy, pause_on_combat=False,
                               tolerance=100.0, log=True)


class ApproachAndSkills:
    """One-visit orchestration of existing route and checked skill owners."""
    def __init__(self) -> None:
        self.phase = "dash"
        self.route: BehaviorTree | None = None
        self.route_active = False
        self.route_complete = False
        self.route_failed = False
        self.route_checkpoint_at = 0.0
        self.final_tree = None
        self.final_attempted = False
        self.final_target = 0
        self.cast: BehaviorTree | None = None
        self.cast_done = False
        self.slot = 0
        self.receipt_at: float | None = None
        self.cast_started = 0.0
        self.dead_since: float | None = None
        self.wait_started: float | None = None
        self.target_id = 0
        self.last_target_id = 0
        self.next_scan_at = 0.0
        self.matches: list[int] = []
        self.validated = False
        self.attempted: set[int] = set()
        self.shadowstep_failed = False
        self.fallback_attempted: set[int] = set()
        self.fallback_done = False
        self.fallback_tree: BehaviorTree | None = None
        self.fallback_slot = 0
        self.fallback_target = 0
        self.fallback_started = 0.0
        self.fallback_before = 0.0
        self.fallback_goal = SKELETON_ORIGIN
        self.fallback_receipt_at: float | None = None
        self.fallback_cast_done = False
        self.fallback_scan_at = 0.0
        self.fallback_candidates: dict[int, list[int]] = {3: [], 7: []}

    def cancel(self) -> None:
        if self.final_tree is not None:
            self.final_tree.reset()
            self.final_tree = None
            # A lifecycle interruption can resume after live readiness/life returns.
            # A terminal path failure keeps final_attempted latched instead.
            self.final_attempted = False
        if self.fallback_tree is not None:
            self.fallback_tree.reset()
            self.fallback_tree = None
            self.fallback_done = True
        if self.route_active and self.route is not None:
            self.route.reset()
        self.route_active = False
        if self.cast is not None:
            self.cast.reset()
            self.cast = None
            self.phase = "observe"

    def fail(self, parent, message: str) -> bool:
        self.cancel()
        parent.halt(message)
        return False

    def approach_corpse(self, parent, allow_alive: bool = False) -> bool:
        """Separate terminal leg; route completion never proves capture range."""
        target = self.target_id
        valid = (target and Agent.IsValid(target) and Agent.IsLiving(target)
            and Agent.GetEncNameStrByID(target,literal=True) == SKELETON_IDENTITY
            and (allow_alive or Agent.IsDead(target))
            and math.dist(Agent.GetXY(target),SKELETON_ORIGIN) <= SKELETON_SEARCH_RADIUS)
        if not valid or (self.final_tree is not None and target != self.final_target):
            if self.final_tree is not None:
                self.final_tree.reset()
                self.final_tree = None
                self.final_attempted = False
                parent.journal.emit('final_approach_cancelled', reason='corpse_unavailable')
            parent.message = "At the skeleton's usual location; searching until the ten-second limit."
            return False
        distance = math.dist(Player.GetXY(),Agent.GetXY(target))
        xy = tuple(Agent.GetXY(target))
        if (allow_alive and self.final_tree is not None
                and math.dist(xy,self.final_xy) >= 100.0):
            self.final_tree.reset()
            self.final_tree = None
            self.final_attempted = False
            parent.journal.emit('final_approach_cancelled', reason='target_moved', target=target)
        if distance <= parent.radius:
            if self.final_tree is not None:
                self.final_tree.reset()
                self.final_tree = None
            return False
        if self.final_tree is None:
            if self.final_attempted:
                parent.message = "Final approach ended outside capture range; waiting for the ten-second limit."
                return False
            if self.route_active and self.route is not None:
                self.route.reset()
                self.route_active = False
            self.final_attempted = True
            self.final_target = target
            self.final_xy = xy
            self.final_tree = _corpse_approach(xy)
            parent.journal.emit('final_approach_requested', corpse=target, corpse_xy=xy,
                player_xy=Player.GetXY(), distance=distance)
        result = self.final_tree.tick()
        now = time.monotonic()
        if now >= self.route_checkpoint_at:
            self.route_checkpoint_at = now + 1.0
            parent.journal.emit('final_approach_progress', corpse=target,
                player_xy=Player.GetXY(), distance=distance,
                movement={key:self.final_tree.blackboard.get(key) for key in
                    ('move_state','move_reason','move_last_move_point','move_avoidance_blocker_id')})
        parent.message = "Moving closer to the skeleton to capture it."
        if result != BehaviorTree.NodeState.RUNNING:
            distance = math.dist(Player.GetXY(),Agent.GetXY(target))
            movement = dict(self.final_tree.blackboard)
            self.final_tree.reset()
            self.final_tree = None
            if distance > parent.radius:
                parent.journal.failure('final_approach_outside_range', corpse=target,
                    distance=distance, result=str(result), movement=movement)
            else:
                parent.journal.emit('final_approach_finished', corpse=target,distance=distance)
        return False

    def walk(self, parent) -> bool:
        target = self.target_id
        known = (target and Agent.IsValid(target) and Agent.IsLiving(target)
            and Agent.GetEncNameStrByID(target,literal=True)==SKELETON_IDENTITY
            and math.dist(Agent.GetXY(target),SKELETON_ORIGIN)<=SKELETON_SEARCH_RADIUS)
        if known:
            return self.approach_corpse(parent,allow_alive=True)
        if self.final_tree is not None:
            self.final_tree.reset()
            self.final_tree = None
            self.final_attempted = False
            parent.journal.emit('final_approach_cancelled', reason='target_unavailable')
        if self.route_failed:
            parent.message = "Walking route unavailable. Looking for a shadowstep; resigning at the ten-second limit."
            return False
        if self.route_complete:
            return self.approach_corpse(parent)
        if self.route is None:
            self.route = _walking_route()
        self.route_active = True
        self.advance_route(parent)
        return False

    def advance_route(self, parent) -> None:
        """Service the active shared owner each frame; scans remain throttled."""
        if not self.route_active or self.route is None:
            return
        if Agent.IsDead(Player.GetAgentID()):
            self.cancel()
            return
        result = self.route.tick()
        # Observe the selected owner; never drive or alter its lifecycle here.
        now = time.monotonic()
        if now >= self.route_checkpoint_at:
            self.route_checkpoint_at = now + 1.0
            board = self.route.blackboard
            parent.journal.emit('route_progress', phase=self.phase, player_xy=Player.GetXY(),
                target=self.target_id, node_state=str(result),
                movement={key: board.get(key) for key in (
                    'move_state', 'move_reason', 'move_target', 'move_path_index',
                    'move_path_count', 'move_current_waypoint', 'move_last_move_point',
                    'move_avoidance_blocker_id', 'move_avoidance_target')})
            print(f"[{MODULE_NAME}] WALK phase={self.phase} result={result} "
                  f"player={Player.GetXY()} target={self.target_id} "
                  f"move_state={board.get('move_state')} reason={board.get('move_reason')} "
                  f"destination={board.get('move_target')} "
                  f"path={board.get('move_path_index')}/{board.get('move_path_count')} "
                  f"last_command={board.get('move_last_move_point')}")
        if result == BehaviorTree.NodeState.FAILURE:
            self.route_active = False
            self.route_failed = True
            parent.journal.failure('autopath_failed', phase=self.phase,
                player_xy=Player.GetXY(), movement=dict(self.route.blackboard))
            parent.message = "Walking route unavailable. Looking for a shadowstep; resigning at the ten-second limit."
            print(f"[{MODULE_NAME}] {BUILD_ID}: ROUTE_UNAVAILABLE "
                  f"reason={self.route.blackboard.get('move_reason')} player={Player.GetXY()}")
            return
        if result == BehaviorTree.NodeState.SUCCESS:
            self.route_active = False
            self.route_complete = True
        parent.message = "Following your recorded approach to the skeleton."

    def fallback_target_valid(self, agent_id: int, slot: int, goal) -> bool:
        if (agent_id == Player.GetAgentID() or not Agent.IsValid(agent_id)
                or not Agent.IsLiving(agent_id) or Agent.IsDead(agent_id)):
            return False
        # Current GameData_enums.Allegiance: Ally=1, Enemy=3. Never neutrals.
        if Agent.GetAllegiance(agent_id)[0] != (3 if slot == 3 else 1):
            return False
        if slot == 3 and Agent.GetEncNameStrByID(agent_id, literal=True) == SKELETON_IDENTITY:
            return False
        xy = Agent.GetXY(agent_id)
        return (math.dist(Player.GetXY(), xy) <= SHADOWSTEP_RANGE
                and math.dist(xy, goal) <= SKELETON_SEARCH_RADIUS
                and math.dist(Player.GetXY(), goal) - math.dist(xy, goal) >= FALLBACK_MIN_GAIN)

    def approach_fallback(self, parent) -> bool:
        """Bounded task-specific composition of the existing skill and route owners."""
        now = time.monotonic()
        player_id = Player.GetAgentID()
        goal = (Agent.GetXY(self.target_id) if self.target_id
                and Agent.IsValid(self.target_id) and Agent.IsDead(self.target_id)
                else SKELETON_ORIGIN)
        if self.fallback_tree is not None:
            slot, target = self.fallback_slot, self.fallback_target
            # Check only identity/type/life/range here: becoming closer is success,
            # so do not reapply the pre-dispatch minimum-gain selection test.
            valid = (Agent.IsValid(target) and Agent.IsLiving(target)
                     and not Agent.IsDead(target)
                     and Agent.GetAllegiance(target)[0] == (3 if slot == 3 else 1))
            result = self.fallback_tree.tick() if valid and not self.fallback_cast_done else None
            if result == BehaviorTree.NodeState.SUCCESS:
                self.fallback_cast_done = True
            skill_id = GLOBAL_CACHE.SkillBar.GetSkillIDBySlot(slot)
            receipt = (GLOBAL_CACHE.SkillBar.GetSkillData(slot).recharge > 0
                       or GLOBAL_CACHE.Effects.HasEffect(player_id, skill_id))
            if receipt and self.fallback_receipt_at is None:
                self.fallback_receipt_at = now
            arrived = (valid and math.dist(Player.GetXY(), Agent.GetXY(target)) <= 322.0
                       and self.fallback_before - math.dist(Player.GetXY(), self.fallback_goal)
                       >= FALLBACK_MIN_GAIN)
            aftercast = max(0.0, float(GLOBAL_CACHE.Skill.Data.GetAftercast(skill_id)))
            settled = (self.fallback_receipt_at is not None
                       and now - self.fallback_receipt_at >= aftercast
                       and not Agent.IsCasting(player_id) and not GLOBAL_CACHE.SkillBar.GetCasting())
            if self.fallback_cast_done and settled and arrived:
                self.fallback_tree.reset()
                self.fallback_tree = None
                self.fallback_done = True
                if self.route_failed:
                    # A verified jump changed the starting position. Re-enter the
                    # same route owner from there; never retry a failed position.
                    if self.route is not None:
                        self.route.reset()
                    self.route_failed = False
                    self.route_complete = False
                self.shadowstep_failed = False
                if self.target_id and not Agent.IsDead(self.target_id):
                    remaining = [(1,"whirling"),(4,"light"),(5,"dwarf"),(6,"finish")]
                    self.phase = next((phase for slot,phase in remaining
                                       if slot not in self.attempted), "observe")
                parent.journal.emit('fallback_arrived', slot=slot, target=target,
                    player_xy=Player.GetXY(), distance_to_goal=math.dist(Player.GetXY(), self.fallback_goal))
                parent.tracking_status = "Shadowstep brought you closer; continuing to the skeleton."
                # No attacks or shouts are ever directed at the fallback target.
                return (self.approach_corpse(parent) if self.target_id
                    and Agent.IsValid(self.target_id) and Agent.IsDead(self.target_id)
                    else self.walk(parent))
            if (not valid or result == BehaviorTree.NodeState.FAILURE
                    or now - self.fallback_started >= FALLBACK_TIMEOUT):
                parent.journal.failure('fallback_arrival_not_confirmed', slot=slot,
                    target=target, valid=valid, receipt=receipt, arrived=arrived,
                    elapsed=now-self.fallback_started, player_xy=Player.GetXY())
                self.fallback_tree.reset()
                self.fallback_tree = None
                if slot == 7:
                    self.fallback_done = True
                parent.tracking_status = "Shadowstep did not confirm arrival; continuing the approach."
            else:
                parent.tracking_status = ("Death's Charge to a nearby enemy; checking arrival."
                                          if slot == 3 else
                                          "Death's Retreat to a nearby ally; checking arrival.")
                return False

        if self.fallback_done:
            if self.target_id and Agent.IsValid(self.target_id) and Agent.IsDead(self.target_id):
                return self.approach_corpse(parent)
            self.shadowstep_failed = False
            if self.target_id and Agent.IsValid(self.target_id) and not Agent.IsDead(self.target_id):
                remaining = [(1,"whirling"),(4,"light"),(5,"dwarf"),(6,"finish")]
                self.phase = next((phase for slot,phase in remaining
                                   if slot not in self.attempted), "observe")
            return self.walk(parent)
        if Agent.IsCasting(player_id) or GLOBAL_CACHE.SkillBar.GetCasting():
            return False
        # Only fallback discovery uses these arrays, at the existing 500ms rate.
        if now >= self.fallback_scan_at:
            self.fallback_scan_at = now + POLL_INTERVAL
            self.fallback_candidates = {3: AgentArray.GetEnemyArray(),
                                        7: AgentArray.GetAllyArray()}
        for slot, name in ((3, "Deaths_Charge"), (7, "Deaths_Retreat")):
            if slot in self.fallback_attempted:
                continue
            expected = GLOBAL_CACHE.Skill.GetID(name)
            if expected <= 0 or GLOBAL_CACHE.SkillBar.GetSkillIDBySlot(slot) != expected:
                continue
            if (not Routines.Checks.Skills.IsSkillSlotReady(slot)
                    or not Routines.Checks.Skills.HasEnoughEnergy(player_id, expected)):
                continue
            candidates = [aid for aid in self.fallback_candidates[slot]
                          if self.fallback_target_valid(aid, slot, goal)]
            if not candidates:
                continue
            target = min(candidates, key=lambda aid: (math.dist(Agent.GetXY(aid), goal), aid))
            # Recheck on dispatch, then stop the route so walking cannot interrupt
            # the spell. Resume this same owner and its forward progress afterward.
            if not self.fallback_target_valid(target, slot, goal):
                continue
            self.cancel()
            self.fallback_attempted.add(slot)
            self.attempted.add(slot)
            self.fallback_slot = slot
            self.fallback_target = target
            self.fallback_started = now
            self.fallback_before = math.dist(Player.GetXY(), goal)
            self.fallback_goal = goal
            self.fallback_receipt_at = None
            self.fallback_cast_done = False
            self.fallback_tree = BT.Skills.CastSkillSlot(slot=slot,
                target_agent_id=target, aftercast_delay=0, log=True)
            parent.journal.emit('fallback_requested', slot=slot, target=target,
                target_xy=Agent.GetXY(target), player_xy=Player.GetXY(), goal=goal)
            self.fallback_tree.tick()
            parent.tracking_status = ("Trying Death's Charge to get closer."
                                      if slot == 3 else "Trying Death's Retreat to get closer.")
            return False
        parent.tracking_status = "Searching for the skeleton; no useful shadowstep target, continuing on foot."
        return self.walk(parent)

    def tick(self, parent) -> bool:
        now = time.monotonic()
        player_id = Player.GetAgentID()
        if Agent.IsDead(player_id):
            if self.dead_since is None:
                self.dead_since = now
                self.cancel()
            parent.message = "Dead: waiting for resurrection; resign timer remains independent."
            return False
        if self.dead_since is not None:
            self.dead_since = None
            # Resume only skills not already requested, after reacquiring the
            # current skeleton. A pending request must never replay on revival.
            remaining = [(2,"dash"),(3,"approach"),(1,"whirling"),(4,"light"),
                         (5,"dwarf"),(6,"finish")]
            self.phase = next((phase for slot,phase in remaining if slot not in self.attempted),"observe")

        # Discovery is expensive; service action trees each frame using the
        # last identity-checked actor set, refreshed no more than twice/second.
        if now >= self.next_scan_at:
            self.next_scan_at = now + POLL_INTERVAL
            self.matches = []
            for agent_id in AgentArray.GetAgentArray():
                if (Agent.IsValid(agent_id) and Agent.IsLiving(agent_id)
                        and Agent.GetEncNameStrByID(agent_id, literal=True) == SKELETON_IDENTITY
                        and math.dist(Agent.GetXY(agent_id), SKELETON_ORIGIN) <= SKELETON_SEARCH_RADIUS):
                    self.matches.append(agent_id)
        matches = self.matches
        if len(matches) > 1:
            return self.fail(parent, "Multiple matching skeletons in the search area. Take over manually.")
        target_id = matches[0] if matches else 0
        if target_id and (not Agent.IsValid(target_id) or not Agent.IsLiving(target_id)):
            target_id = 0
        if self.target_id and target_id != self.target_id:
            # Loss is not death. Drop the old target and pending offensive work,
            # retain route progress, and reacquire only a fresh unique match.
            if self.cast is not None and self.slot != 2:
                self.cast.reset()
                self.cast = None
            parent.journal.emit('skeleton_tracking_changed', previous=self.target_id,
                current=target_id, phase=self.phase, player_xy=Player.GetXY())
            self.phase = "search"
        self.target_id = target_id
        if target_id:
            self.last_target_id = target_id
        if not target_id:
            parent.tracking_status = "Searching for the skeleton; heading to its usual location."
            if 2 in self.attempted:
                self.phase = "search"
                return self.approach_fallback(parent)
        else:
            parent.tracking_status = "Skeleton found."
            if self.phase == "search":
                remaining = [(3,"approach"),(1,"whirling"),(4,"light"),
                             (5,"dwarf"),(6,"finish")]
                self.phase = next((phase for slot,phase in remaining
                                   if slot not in self.attempted), "observe")
        distance = math.dist(Player.GetXY(), Agent.GetXY(target_id)) if target_id else float("inf")

        if target_id and capturable(target_id) and distance <= parent.radius:
            self.cancel()
            return True

        # Capture immediately when close. Outside capture range, the opening
        # instant Dash still helps reach a corpse; no offensive skill is sent.
        dead_target = bool(target_id and Agent.IsDead(target_id))
        if dead_target:
            if distance <= parent.radius:
                self.cancel()
                return True
            if self.phase != "dash" or 2 in self.attempted:
                if self.phase != "corpse" and self.fallback_tree is None:
                    if self.slot == 2 and self.cast is not None:
                        # Dash is a stance, so keep its concurrent walking route.
                        self.cast.reset()
                        self.cast = None
                    else:
                        self.cancel()
                self.phase = "corpse"
                return self.approach_fallback(parent)

        if self.fallback_tree is not None:
            return self.approach_fallback(parent)
        if self.route_failed or (self.shadowstep_failed and distance > parent.radius):
            return self.approach_fallback(parent)

        if not self.validated:
            for slot, name in enumerate(EXPECTED_SKILLS, 1):
                expected = GLOBAL_CACHE.Skill.GetID(name)
                if expected <= 0 or GLOBAL_CACHE.SkillBar.GetSkillIDBySlot(slot) != expected:
                    return self.fail(parent, f"Skill bar mismatch in slot {slot}: expected {name}.")
            self.validated = True

        # Tick an already-started real cast owner, then require a live receipt.
        if self.cast is not None:
            if self.slot == 2:
                self.advance_route(parent)
                if not parent.enabled:
                    return False
            skill_id = GLOBAL_CACHE.SkillBar.GetSkillIDBySlot(self.slot)
            if not self.cast_done:
                result = self.cast.tick()
                if result == BehaviorTree.NodeState.FAILURE:
                    if self.slot == 3:
                        self.cancel()
                        self.shadowstep_failed = True
                        return self.approach_fallback(parent)
                    return self.fail(parent, f"Skill slot {self.slot} could not be used. Take over manually.")
                self.cast_done = result == BehaviorTree.NodeState.SUCCESS
            receipt = (GLOBAL_CACHE.SkillBar.GetSkillData(self.slot).recharge > 0
                       or GLOBAL_CACHE.Effects.HasEffect(player_id, skill_id))
            if receipt and self.receipt_at is None:
                self.receipt_at = now
            if self.cast_done and self.receipt_at is not None:
                aftercast = max(0.0, float(GLOBAL_CACHE.Skill.Data.GetAftercast(skill_id)))
                if not Agent.IsCasting(player_id) and now - self.receipt_at >= aftercast:
                    if self.slot == 3 and distance > 322.0:
                        if now - self.cast_started <= 3.0:
                            return False
                        self.cancel()
                        self.phase = "observe"
                        self.shadowstep_failed = True
                        return self.approach_fallback(parent)
                    self.cast = None
                    self.wait_started = None
                    self.phase = {2: "approach", 3: "whirling", 1: "light",
                                  4: "dwarf", 5: "finish", 6: "observe"}[self.slot]
            if self.cast is not None and now - self.cast_started > 4.0:
                if self.slot == 3:
                    self.shadowstep_failed = True
                self.cancel()
                self.phase = "observe"
                parent.message = "Skill activation not confirmed; waiting for skeleton death."
            if self.cast is not None:
                return False

        if self.phase == "dash":
            slot = 2
        elif self.phase == "approach":
            if not target_id or distance > 1248.0:
                return self.walk(parent)
            self.cancel()
            self.phase = "charge"
            slot = 3
        elif self.phase == "charge":
            slot = 3
        elif self.phase == "whirling":
            slot = 1
        elif self.phase == "light":
            slot = 4
        elif self.phase == "dwarf":
            slot = 5
        elif self.phase == "finish":
            if not target_id or Agent.GetHealth(target_id) >= 0.5:
                parent.message = 'Waiting for skeleton below 50% health or death.'
                return False
            slot = 6
        else:
            if distance > parent.radius:
                return self.walk(parent)
            parent.message = "Waiting for the skeleton to die; no other enemies will be attacked."
            return False

        if slot != 2:
            if (not target_id or not Agent.IsValid(target_id) or Agent.IsDead(target_id)
                    or Agent.GetEncNameStrByID(target_id, literal=True) != SKELETON_IDENTITY):
                return False
            if distance > (1248.0 if slot == 3 else 322.0):
                return self.walk(parent)
        if Agent.IsCasting(player_id) or GLOBAL_CACHE.SkillBar.GetCasting():
            return False
        skill_id = GLOBAL_CACHE.SkillBar.GetSkillIDBySlot(slot)
        if (not Routines.Checks.Skills.IsSkillSlotReady(slot)
                or not Routines.Checks.Skills.HasEnoughEnergy(player_id, skill_id)):
            if slot == 3:
                self.shadowstep_failed = True
                return self.approach_fallback(parent)
            if self.wait_started is None:
                self.wait_started = now
            elif now - self.wait_started > 3.0:
                self.phase = "observe"
                parent.message = "Skill unavailable; preserving the capture-only fallback."
                return False
            parent.message = f"Waiting for energy or recharge: slot {slot}."
            return False
        self.wait_started = None
        if slot == 6 and Agent.GetHealth(target_id) >= 0.5:
            return False
        self.slot = slot
        self.cast_done = False
        self.receipt_at = None
        self.cast_started = now
        self.attempted.add(slot)
        self.cast = BT.Skills.CastSkillSlot(slot=slot,
            target_agent_id=target_id if slot in (3, 5, 6) else player_id,
            aftercast_delay=0, log=True)
        parent.message = f"Using {EXPECTED_SKILLS[slot - 1].replace('_', ' ')}."
        parent.journal.emit('skill_requested', slot=slot,
            skill=EXPECTED_SKILLS[slot-1], target=target_id if slot in (3,5,6) else player_id,
            player_xy=Player.GetXY(), phase=self.phase)
        self.cast.tick()
        if slot == 2 and (not target_id or distance > 1248.0 or dead_target):
            # Dash is instant and does not prevent walking. Queue the stance
            # first, then let the existing movement owner prepare immediately.
            return self.walk(parent)
        return False


class MonkApproach(ApproachAndSkills):
    """Monk mechanic sequence using the unchanged cast and movement owners."""
    def __init__(self):
        super().__init__()
        self.phase = "protect"
        self.landed = False
        self.last_short = 6
        self.effect_until = {}
        self.effect_probe_at = 0.0
        self.enemies = []
        self.allies = []
        self.retry_after = {}
        self.charge_failed_targets: set[int] = set()
        self.charge_log_state = None

    def actual_slot(self, role: int) -> int:
        return role if 1<=role<=8 else 0

    def skill_id(self, role: int) -> int:
        slot = self.actual_slot(role)
        return GLOBAL_CACHE.SkillBar.GetSkillIDBySlot(slot) if slot else 0

    def ready(self, role: int) -> bool:
        slot = self.actual_slot(role)
        return bool(slot and Routines.Checks.Skills.IsSkillSlotReady(slot))

    def recharge(self, role: int):
        slot = self.actual_slot(role)
        return GLOBAL_CACHE.SkillBar.GetSkillData(slot).recharge if slot else 0

    def skill_label(self, role: int) -> str:
        return MONK_SKILLS[role-1]

    def cast_step(self, parent, slot: int, target: int) -> bool:
        now = time.monotonic()
        player = Player.GetAgentID()
        if self.cast is None:
            skill = self.skill_id(slot)
            if not skill:
                self.attempted.add(slot)
                return True
            if (now < self.retry_after.get(slot,0) or Agent.IsCasting(player)
                    or GLOBAL_CACHE.SkillBar.GetCasting()
                    or not self.ready(slot)
                    or not Routines.Checks.Skills.HasEnoughEnergy(player,skill)):
                return False
            if self.route_active and slot != 1:
                self.route.reset()
                self.route_active = False
            if self.final_tree is not None and slot != 1:
                self.final_tree.reset()
                self.final_tree = None
                self.final_attempted = False
            self.slot = slot
            self.cast_done = False
            self.receipt_at = None
            self.cast_started = now
            self.cast = BT.Skills.CastSkillSlot(slot=self.actual_slot(slot), target_agent_id=target,
                aftercast_delay=0, log=True)
            parent.journal.emit('skill_requested', slot=self.actual_slot(slot), skill=self.skill_label(slot),
                target=target, player_xy=Player.GetXY(), phase=self.phase, profile=parent.bar_profile,
                effects_remaining_ms={s:round(max(0,self.effect_until.get(s,now)-now)*1000)
                                      for s in (5,6,7)})
        if self.slot != slot:
            return False
        if not self.cast_done:
            result = self.cast.tick()
            self.cast_done = result == BehaviorTree.NodeState.SUCCESS
            if result == BehaviorTree.NodeState.FAILURE:
                self.cast.reset()
                self.cast = None
                self.retry_after[slot] = now + 1.0
                parent.journal.emit('monk_skill_failed', slot=slot, reason='owner_failure')
                return False
        skill = self.skill_id(slot)
        receipt = (self.recharge(slot) > 0
                   or GLOBAL_CACHE.Effects.HasEffect(player,skill))
        if receipt and self.receipt_at is None:
            self.receipt_at = now
        if (self.cast_done and self.receipt_at is not None
                and now-self.receipt_at >= max(0,float(GLOBAL_CACHE.Skill.Data.GetAftercast(skill)))
                and not Agent.IsCasting(player) and not GLOBAL_CACHE.SkillBar.GetCasting()):
            self.cast = None
            self.attempted.add(slot)
            if slot in (6,7): self.last_short = slot
            return True
        if now-self.cast_started > 4.0:
            self.cast.reset()
            self.cast = None
            self.retry_after[slot] = now + 1.0
            parent.journal.emit('monk_skill_failed', slot=slot, reason='receipt_timeout')
        return False

    def protect(self, parent) -> bool:
        player = Player.GetAgentID()
        if Agent.IsDead(player):
            if self.cast is not None:
                self.cast.reset()
                self.cast = None
            self.effect_probe_at = 0
            self.last_short = 6
            return False
        if self.cast is not None:
            if self.slot in (5,6,7,8,11):
                self.cast_step(parent,self.slot,player)
                return True
            return False
        now = time.monotonic()
        if now >= self.effect_probe_at:
            self.effect_probe_at = now + POLL_INTERVAL
            self.effect_until = {slot:now + max(0,GLOBAL_CACHE.Effects.GetEffectTimeRemaining(
                player,self.skill_id(slot)))/1000
                for slot in (5,6,7) if self.skill_id(slot)}
            self.enemies = list(AgentArray.GetEnemyArray())
            self.allies = list(AgentArray.GetAllyArray()) if self.actual_slot(10) else []
        remaining = {slot:max(0,end-now) for slot,end in self.effect_until.items()}
        choices = []
        if self.skill_id(5) and remaining.get(5,0) <= 0:
            choices.append(5)
        if self.landed:
            if max(remaining.get(6,0),remaining.get(7,0)) <= 0:
                choices.extend((7,6))
            adjacent = any(Agent.IsValid(aid) and Agent.IsLiving(aid) and not Agent.IsDead(aid)
                and math.dist(Player.GetXY(),Agent.GetXY(aid)) <= 166.0 for aid in self.enemies)
            if adjacent and self.ready(8):
                choices.append(8)
            elif not self.skill_id(8) and 11 not in self.attempted and self.ready(11):
                choices.append(11)
        for slot in choices:
            skill = self.skill_id(slot)
            if (now < self.retry_after.get(slot,0)
                    or not self.ready(slot)
                    or not Routines.Checks.Skills.HasEnoughEnergy(player,skill)):
                continue
            self.cast_step(parent,slot,player)
            return True
        return False

    def tick(self, parent) -> bool:
        now = time.monotonic()
        player = Player.GetAgentID()
        if Agent.IsDead(player):
            self.cancel()
            self.protect(parent)
            parent.message = "Dead: waiting for resurrection; capture and resign remain active."
            return False
        if now >= self.next_scan_at:
            self.next_scan_at = now + POLL_INTERVAL
            self.matches = [aid for aid in AgentArray.GetAgentArray()
                if Agent.IsValid(aid) and Agent.IsLiving(aid)
                and Agent.GetEncNameStrByID(aid,literal=True)==SKELETON_IDENTITY
                and math.dist(Agent.GetXY(aid),SKELETON_ORIGIN)<=SKELETON_SEARCH_RADIUS]
        targets = [aid for aid in self.matches if Agent.IsValid(aid) and Agent.IsLiving(aid)]
        if len(targets)>1:
            return self.fail(parent,"Multiple skeletons in the search area; take over manually.")
        self.target_id = targets[0] if targets else 0
        target = self.target_id
        if target: self.last_target_id = target
        distance = math.dist(Player.GetXY(),Agent.GetXY(target)) if target else float('inf')
        parent.tracking_status = "Skeleton found." if target else "Searching; running to the skeleton's location."
        if target and capturable(target) and distance<=parent.radius:
            self.landed = True
            self.cancel()
            return True
        # Complete an offensive cast before starting another owner.
        if self.cast is not None and self.slot in (1,2,3,4,9,10):
            slot = self.slot
            if slot == 1: self.advance_route(parent)
            cast_target = getattr(self,'cast_target',player)
            if slot in (2,4,9,10) and (not Agent.IsValid(cast_target) or Agent.IsDead(cast_target)):
                self.cast.reset()
                self.cast = None
                if slot in (2,10):
                    recharge = self.recharge(slot)
                    self.charge_failed_targets.add(cast_target)
                    if slot==2 and recharge>0: self.attempted.add(2)
                    parent.journal.emit('monk_charge_target_lost', target=cast_target,
                        recharge=recharge, charge_spent=recharge>0)
                else:
                    self.attempted.add(slot)
            elif not self.cast_step(parent,slot,cast_target):
                if self.cast is None and slot in (2,10):
                    self.charge_failed_targets.add(cast_target)
                    if slot==2 and self.recharge(2)>0:
                        self.attempted.add(2)
                    return self.walk(parent)
                return False
            if slot in (2,10):
                if slot==10 and 10 in self.attempted:
                    self.attempted.add(2)
                self.landed = bool(target and distance<=parent.radius)
        if self.protect(parent):
            return False
        # Spirit must be observed before beginning the approach, not just queued.
        if self.skill_id(5) and self.effect_until.get(5,0) <= now:
            parent.message = "Waiting for Protective Spirit before the approach."
            return False
        if 1 not in self.attempted:
            self.phase = 'dash'
            self.cast_target = player
            self.cast_step(parent,1,player)
            return self.walk(parent)
        if 2 not in self.attempted or (self.actual_slot(10) and 10 not in self.attempted
                and not self.landed and distance>parent.radius):
            charge_target = (target if self.ready(2) and target and not Agent.IsDead(target)
                             and target not in self.charge_failed_targets else 0)
            charge_role = 2
            if not charge_target:
                goal = Agent.GetXY(target) if target else SKELETON_ORIGIN
                candidates = [aid for aid in self.enemies if aid not in self.charge_failed_targets
                              and self.fallback_target_valid(aid,3,goal)]
                charge_target = min(candidates,key=lambda aid:math.dist(Agent.GetXY(aid),goal)) if candidates else 0
                state = (tuple(candidates),charge_target,
                         self.ready(2))
                if state != self.charge_log_state:
                    self.charge_log_state = state
                    parent.journal.emit('monk_charge_fallback_checked', candidates=candidates,
                        selected=charge_target, ready=state[2],
                        failed_targets=sorted(self.charge_failed_targets), player_xy=Player.GetXY())
            if self.actual_slot(10) and (not charge_target or not self.ready(2)) and self.ready(10):
                goal = Agent.GetXY(target) if target else SKELETON_ORIGIN
                allies = [aid for aid in self.allies
                    if aid not in self.charge_failed_targets and self.fallback_target_valid(aid,7,goal)]
                if allies:
                    charge_role = 10
                    charge_target = min(allies,key=lambda aid:math.dist(Agent.GetXY(aid),goal))
            if charge_target and math.dist(Player.GetXY(),Agent.GetXY(charge_target))<=SHADOWSTEP_RANGE:
                if self.ready(charge_role):
                    self.phase = 'charge'
                    self.cast_target = charge_target
                    self.cast_step(parent,charge_role,charge_target)
                    return False if self.cast is not None else self.walk(parent)
                self.attempted.add(2)
            return self.walk(parent)
        if not target or distance>parent.radius:
            self.phase = 'approach'
            return self.walk(parent)
        self.landed = True
        if self.protect(parent): return False
        for slot,phase in ((3,'light'),(4,'dwarf'),(9,'finish')):
            if self.skill_id(slot) and slot not in self.attempted and not Agent.IsDead(target):
                if slot==9 and Agent.GetHealth(target)>=0.5:
                    continue
                self.phase = phase
                self.cast_target = target if slot in (4,9) else player
                self.cast_step(parent,slot,self.cast_target)
                return False
        self.phase = 'observe'
        return False


class GenericApproach(MonkApproach):
    """Same sequence and movement owners, with immutable observed slot bindings."""
    def __init__(self, bindings, names):
        super().__init__()
        self.bindings = tuple(sorted(bindings.items()))
        self.names = tuple(sorted(names.items()))

    def actual_slot(self, role: int) -> int:
        return dict(self.bindings).get(role,0)

    def skill_label(self, role: int) -> str:
        return dict(self.names).get(role,'Unknown')


class CaptureAssistant:
    def __init__(self) -> None:
        self.enabled = False
        self.radius = 322
        self.state = "watching"
        self.message = "Stopped. Start before entering the Underworld."
        self.tracking_status = "Waiting for the Underworld."
        self.visit_limit_reached = False
        self.cutoff_summary = ""
        self.in_underworld = False
        self.instance_uptime: int | None = None
        self.sent = False
        self.before = 0
        self.items_before = 0
        self.deadline = 0.0
        self.capture_attempts = 0
        self.corpse_id = 0
        self.distance: float | None = None
        self.confirmed_this_visit = False
        self.confirmed_total = 0
        self.failure_total = 0
        self.session_started_at = None
        self.session_elapsed = 0.0
        self.run_started_at = None
        self.last_run_seconds = None
        self.previous_resign_at = None
        self.resign_interval_total = 0.0
        self.resign_interval_count = 0
        self.visit_failure_recorded = False
        self.resign_tree: BehaviorTree | None = None
        self.resign_started = False
        self.resign_sent = False
        self.resign_error = ""
        self.next_poll_at = 0.0
        self.use_movement = True
        self.bar_profile = ""
        self.bar_probe_at = 0.0
        self.bar_last_seen = None
        self.bar_required = None
        self.bar_missing = []
        self.bar_bindings = {}
        self.bar_names = {}
        self.bar_signature = None
        self.bar_candidate_profile = ''
        self.skill_lookup = {}
        self.approach = ApproachAndSkills()
        self.journal = RunJournal(_log_directory())
        self.visit_log_started = False
        self.last_action_state = None
        self.readiness_valid: bool | None = None
        self.readiness_status = "Waiting for game readiness."
        self.readiness_history: list[dict] = []
        self.last_readiness_sample = None
        self.next_readiness_probe = 0.0
        self.last_callback_at: float | None = None
        self.next_status_log = 0.0
        self.last_slow_log = 0.0
        self.defense_tree = None
        self.defense_done = False
        self.defense_deadline = 0.0
        self.defense_dispatched = False
        self.loot_tree = None
        self.loot_next_scan = 0.0
        self.loot_attempted: set[int] = set()
        self.loot_before: dict[int, int] = {}
        self.loot_candidates: list[dict] = []
        self.loot_last_scan = None

    def observe_readiness(self, valid: bool) -> None:
        now = time.monotonic()
        if self.last_callback_at is not None and now - self.last_callback_at >= 0.5:
            gap = dict(event='callback_gap', gap_seconds=round(now-self.last_callback_at,3),
                       previous_readiness=self.readiness_valid, now=now)
            self.readiness_history.append(gap)
            self.journal.readiness('callback_gap', **{k:v for k,v in gap.items() if k!='event'})
        self.last_callback_at = now
        changed = valid != self.readiness_valid
        self.readiness_valid = valid
        if not changed and now < self.next_readiness_probe:
            return
        self.next_readiness_probe = now + POLL_INTERVAL
        map_ready = Map.IsMapReady()
        sample = dict(readiness_policy="local_player", map_ready=map_ready,
            player_ready=Player.IsPlayerLoaded() if map_ready else False,
            party_ready=Party.IsPartyLoaded() if map_ready else False,
            cinematic=Map.IsInCinematic() if map_ready else False,
            map_id=Map.GetMapID() if map_ready else 0, valid=valid)
        if map_ready and sample['player_ready']:
            upkeep_reader = getattr(Routines.Checks.Map, 'LocalPlayerUpkeepRequested', None)
            sample['local_upkeep_requested'] = bool(upkeep_reader and upkeep_reader())
            bar = getattr(GLOBAL_CACHE, 'SkillBar', None)
            owner_reader = getattr(bar, 'GetAgentID', None)
            slot_reader = getattr(bar, 'GetSkillIDBySlot', None)
            sample['local_agent_id'] = Player.GetAgentID()
            sample['skillbar_agent_id'] = owner_reader() if owner_reader else None
            sample['skillbar_slots'] = [slot_reader(slot) for slot in range(1,9)] if slot_reader else None
        if not map_ready:
            self.readiness_status = "Loading map; waiting for the game to become ready."
        elif not sample['player_ready']:
            self.readiness_status = "Map loaded; waiting for your character."
        elif sample['cinematic']:
            self.readiness_status = "Waiting for the cinematic to finish."
        elif not valid:
            self.readiness_status = "Character loaded; waiting for your skillbar to become ready."
        else:
            self.readiness_status = "Your character is ready; other party members do not delay this run."
        if sample != self.last_readiness_sample:
            self.last_readiness_sample = sample
            event = dict(sample, instance_uptime_ms=Map.GetInstanceUptime() if map_ready else None,
                         now=now)
            self.readiness_history.append(dict(event='readiness_changed', **event))
            self.journal.readiness('readiness_changed', **event)
        self.readiness_history = self.readiness_history[-16:]

    def reset_statistics(self) -> None:
        """Reset display history only; preserve every per-visit action latch."""
        self.confirmed_total = 0
        self.failure_total = 0
        self.session_elapsed = 0.0
        self.session_started_at = time.monotonic() if self.enabled else None
        self.last_run_seconds = None
        self.previous_resign_at = None
        self.resign_interval_total = 0.0
        self.resign_interval_count = 0
        self.run_started_at = (time.monotonic() if self.run_started_at is not None else None)
        self.journal.readiness('statistics_reset', enabled=self.enabled, state=self.state)

    def elapsed_session(self) -> float:
        return self.session_elapsed + (time.monotonic()-self.session_started_at
            if self.session_started_at is not None else 0.0)

    def finish_run_timer(self) -> None:
        if self.run_started_at is not None:
            self.last_run_seconds = max(0.0,time.monotonic()-self.run_started_at)
            self.run_started_at = None

    def record_resign_timing(self) -> None:
        now = time.monotonic()
        self.finish_run_timer()
        interval = None
        if self.previous_resign_at is not None:
            interval = max(0.0,now-self.previous_resign_at)
            self.resign_interval_total += interval
            self.resign_interval_count += 1
        self.previous_resign_at = now
        self.journal.emit('run_timing', run_seconds=self.last_run_seconds,
            resign_interval_seconds=interval, interval_count=self.resign_interval_count,
            average_seconds=(self.resign_interval_total/self.resign_interval_count
                if self.resign_interval_count else None))

    def start(self) -> None:
        if not self.enabled:
            self.session_started_at = time.monotonic()
        self.enabled = True
        # Stop/Start preserves the confirmation baseline and retry pacing.
        self.message = "Running. Watching for a weakened or dead Skeleton of Dhuum."
        if self.sent:
            self.message = "Checking the pending capture before any paced retry."
        print(f"[{MODULE_NAME}] {BUILD_ID}: Start; state={self.state}, sent={self.sent}")

    def record_failure(self) -> None:
        if self.in_underworld and not self.confirmed_this_visit and not self.visit_failure_recorded:
            self.visit_failure_recorded = True
            self.failure_total += 1
            self.journal.failure('visit_unconfirmed', state=self.state,
                phase=self.approach.phase, uptime_ms=self.instance_uptime)

    def inspect_bar(self) -> None:
        now = time.monotonic()
        if now < self.bar_probe_at:
            return
        self.bar_probe_at = now + POLL_INTERVAL
        actual = tuple(GLOBAL_CACHE.SkillBar.GetSkillIDBySlot(slot) for slot in range(1,9))
        if not any(actual):
            self.bar_required = None
            self.bar_missing = []
            self.bar_candidate_profile = ''
            return
        by_id = {sid:slot for slot,sid in enumerate(actual,1) if sid}
        if not self.skill_lookup:
            self.skill_lookup = {name:GLOBAL_CACHE.Skill.GetID(name)
                for alternatives in SKILL_ROLES.values() for name in alternatives}
        bindings,names = {},{}
        for role,alternatives in SKILL_ROLES.items():
            for name in alternatives:
                sid = self.skill_lookup[name]
                if sid>0 and sid in by_id:
                    bindings[role],names[role] = by_id[sid],name
                    break
        self.bar_bindings,self.bar_names = bindings,names
        self.bar_missing = (["Dash"] if 1 not in bindings else []) + (
            ["Death's Charge or Dark Prison"] if 2 not in bindings else [])
        self.bar_required = not self.bar_missing
        monk = tuple(self.skill_lookup[name] for name in MONK_SKILLS)
        ranger = tuple(self.skill_lookup[name] for name in EXPECTED_SKILLS)
        profile = ('monk' if all(monk) and actual==monk else
                   'ranger' if all(ranger) and actual[:6]==ranger else
                   'generic' if self.bar_required else '')
        self.bar_candidate_profile = profile
        if actual != self.bar_last_seen:
            self.journal.emit('skill_bar_detected', profile=profile or 'unrecognized', slots=actual,
                required=self.bar_required, missing=self.bar_missing, bindings=bindings, skills=names)
            self.bar_last_seen = actual

    def detect_bar(self) -> bool:
        self.inspect_bar()
        profile = self.bar_candidate_profile
        if not profile:
            self.message = ("Missing required skills: " + ', '.join(self.bar_missing)
                            if self.bar_required is False else "Waiting for the skill bar to load.")
            return False
        signature = (profile,tuple(sorted(self.bar_bindings.items())))
        if profile != self.bar_profile or (profile=='generic' and signature!=self.bar_signature):
            if profile in ('monk','generic') or isinstance(self.approach,MonkApproach):
                self.approach.cancel()
                self.approach = (GenericApproach(self.bar_bindings,self.bar_names) if profile=='generic'
                    else MonkApproach() if profile=='monk' else ApproachAndSkills())
            self.bar_profile = profile
            self.bar_signature = signature
        return True

    def cancel_defense(self) -> None:
        if isinstance(self.approach,MonkApproach) and self.approach.cast is not None:
            self.approach.cast.reset()
            self.approach.cast = None
        if self.defense_tree is not None:
            self.defense_tree.reset()
            self.defense_tree = None
        if self.defense_deadline:
            self.defense_done = True

    def defensive_tick(self) -> None:
        """One bounded self-stance attempt; no corpse or resign dependency."""
        if self.bar_profile in ('monk','generic'):
            self.approach.protect(self)
            return
        if not self.use_movement:
            self.defense_done = True
        if self.defense_done:
            return
        now = time.monotonic()
        if not self.defense_deadline:
            self.defense_deadline = now + 2.0
        player = Player.GetAgentID()
        skill = GLOBAL_CACHE.Skill.GetID('Whirling_Defense')
        reason = None
        if Agent.IsDead(player):
            reason = 'player_dead'
        elif GLOBAL_CACHE.SkillBar.GetSkillIDBySlot(1) != skill:
            reason = 'slot_1_not_whirling_defense'
        elif GLOBAL_CACHE.Effects.HasEffect(player, skill):
            reason = 'effect_observed'
        elif self.defense_dispatched and not Routines.Checks.Skills.IsSkillSlotReady(1):
            reason = 'recharge_observed'
        elif now >= self.defense_deadline:
            reason = 'attempt_window_expired'
        if reason:
            self.journal.emit('defense_finished', reason=reason,
                dispatched=self.defense_dispatched, state=self.state)
            self.cancel_defense()
            self.defense_done = True
            return
        if self.defense_dispatched:
            return
        if self.defense_tree is None:
            if (not Routines.Checks.Skills.IsSkillSlotReady(1)
                    or not Routines.Checks.Skills.HasEnoughEnergy(player,skill)):
                return
            self.defense_tree = BT.Skills.CastSkillSlot(slot=1,
                target_agent_id=player, aftercast_delay=0, log=True)
            self.journal.emit('defense_requested', slot=1, state=self.state)
        result = self.defense_tree.tick()
        if result == BehaviorTree.NodeState.SUCCESS:
            self.defense_dispatched = True
            self.defense_tree = None
            self.journal.emit('defense_dispatched', state=self.state)
        elif result == BehaviorTree.NodeState.FAILURE:
            self.journal.emit('defense_finished', reason='owner_failed', dispatched=False)
            self.cancel_defense()
            self.defense_done = True

    def cancel_loot(self) -> None:
        if self.loot_tree is not None:
            self.loot_tree.reset()
            self.loot_tree = None

    def owned_loot(self) -> list[dict]:
        result = []
        for aid in AgentArray.GetItemArray():
            if (not Agent.IsValid(aid) or not Agent.IsItem(aid)
                    or Agent.GetItemAgentOwnerID(aid) != Player.GetAgentID()):
                continue
            distance = math.dist(Player.GetXY(), Agent.GetXY(aid))
            if distance > LOOT_RANGE:
                continue
            item_id = Agent.GetItemAgentItemID(aid)
            model = int(Item.GetModelID(item_id) or 0) if item_id else 0
            if model:
                result.append(dict(agent=aid, model=model, item=item_id,
                    owner=Player.GetAgentID(), distance=round(distance, 2)))
        return result

    def loot_tick(self) -> None:
        """Post-capture successor; resign never cancels this pickup owner."""
        if Agent.IsDead(Player.GetAgentID()):
            self.cancel_loot()
            return
        if self.loot_tree is not None:
            result = self.loot_tree.tick()
            if result == BehaviorTree.NodeState.RUNNING:
                return
            self.journal.emit('loot_pickup_result', result=str(result),
                candidates=self.loot_candidates, counts_before=self.loot_before,
                counts_after={model:GLOBAL_CACHE.Inventory.GetModelCount(model)
                              for model in self.loot_before})
            if result == BehaviorTree.NodeState.FAILURE:
                self.journal.failure('loot_pickup_failed', candidates=self.loot_candidates)
            self.loot_attempted.update(entry['agent'] for entry in self.loot_candidates)
            self.cancel_loot()
        now = time.monotonic()
        if now < self.loot_next_scan:
            return
        self.loot_next_scan = now + POLL_INTERVAL
        candidates = self.owned_loot()
        signature = tuple(sorted((entry['agent'],entry['model']) for entry in candidates))
        if signature != self.loot_last_scan:
            self.loot_last_scan = signature
            self.journal.emit('loot_checked', candidates=candidates, resigned=self.resign_sent)
        candidates = [entry for entry in candidates if entry['agent'] not in self.loot_attempted]
        if not candidates:
            return
        if GLOBAL_CACHE.Inventory.GetFreeSlotCount() <= 0:
            self.journal.emit('loot_inventory_full', candidates=candidates)
            self.loot_attempted.update(entry['agent'] for entry in candidates)
            return
        # One model transaction at a time; owner retains selection/approach/retry.
        selected = min(candidates, key=lambda entry:entry['distance'])
        self.loot_candidates = [selected]
        self.loot_before = {selected['model']:GLOBAL_CACHE.Inventory.GetModelCount(selected['model'])}
        self.loot_tree = BTItems.PickupGroundItemByModelID(model_ids=(selected['model'],),
            max_distance=LOOT_RANGE, timeout_ms=LOOT_TIMEOUT_MS,
            allow_unassigned=False, interaction_interval_ms=500, aftercast_ms=0, log=True)
        self.journal.emit('loot_pickup_started', candidates=self.loot_candidates,
            timeout_ms=LOOT_TIMEOUT_MS, resigned=self.resign_sent)
        self.loot_tree.tick()

    def request_resign(self, reason: str) -> None:
        """Start the shared resign owner once, without changing capture state."""
        if self.resign_started:
            return
        self.resign_started = True
        self.resign_tree = BT.Player.Resign(log=True)
        self.journal.emit('resign_timer_triggered', reason=reason,
            captured=self.confirmed_this_visit, state=self.state)

    def service_resign(self) -> None:
        if self.resign_tree is None:
            return
        try:
            result = self.resign_tree.tick()
        except Exception as exc:
            self.resign_tree = None
            self.resign_error = f"{type(exc).__name__}: {exc}"
            self.journal.failure('resign_failed', error=self.resign_error)
            return
        if result == BehaviorTree.NodeState.SUCCESS:
            self.resign_tree = None
            self.resign_sent = True
            self.record_resign_timing()
            self.journal.emit('resign_requested', confirmed=self.confirmed_this_visit,
                timeout=self.visit_limit_reached, capture_continues=not self.confirmed_this_visit)
        elif result == BehaviorTree.NodeState.FAILURE:
            self.resign_tree = None
            self.resign_error = "Shared resign owner reported failure; resign manually."
            self.journal.failure('resign_failed', state=self.state)

    def halt(self, reason: str) -> None:
        # Halt gameplay actions, retaining the supervisor until explicit Stop.
        self.state = "failed"
        self.record_failure()
        self.approach.cancel()
        self.message = reason + " Waiting for the ten-second resign guard."
        self.journal.failure('actions_halted', message=reason, uptime_ms=self.instance_uptime)
        print(f"[{MODULE_NAME}] {self.message}")

    def stop(self, reason: str = "Stopped by you.") -> None:
        self.cancel_loot()
        if self.state == "failed":
            self.record_failure()
        if self.session_started_at is not None:
            self.session_elapsed += time.monotonic()-self.session_started_at
            self.session_started_at = None
        self.finish_run_timer()
        self.previous_resign_at = None
        self.enabled = False
        self.cancel_defense()
        self.approach.cancel()
        self.journal.emit('user_stopped', reason=reason)
        self.journal.finish('manual_stop')
        self.message = reason
        if self.sent and self.state == "confirming":
            self.message += " Already queued item use may finish."
        elif self.state == "resigning":
            self.message += " A resign command already queued may finish."
        print(f"[{MODULE_NAME}] {self.message}")

    def new_visit(self) -> None:
        self.cancel_loot()
        self.loot_attempted.clear()
        self.loot_next_scan = 0.0
        self.loot_last_scan = None
        self.cancel_defense()
        self.defense_done = False
        self.defense_deadline = 0.0
        self.defense_dispatched = False
        if self.in_underworld and self.enabled:
            self.record_failure()
        self.journal.finish('confirmed' if self.confirmed_this_visit else 'visit_replaced')
        self.visit_log_started = False
        self.finish_run_timer()
        self.last_action_state = None
        self.visit_failure_recorded = False
        self.approach.cancel()
        self.approach = ApproachAndSkills()
        self.bar_profile = ""
        self.bar_probe_at = 0.0
        self.bar_last_seen = None
        if self.resign_tree is not None:
            self.resign_tree.reset()
            self.resign_tree = None
        self.resign_started = False
        self.resign_sent = False
        self.resign_error = ""
        self.state = "watching"
        self.sent = False
        self.capture_attempts = 0
        self.confirmed_this_visit = False
        self.corpse_id = 0
        self.distance = None
        self.next_poll_at = 0.0
        self.visit_limit_reached = False
        self.cutoff_summary = ""
        self.tracking_status = "Searching for the skeleton."
        self.message = "Underworld: watching for a weakened or dead Skeleton of Dhuum."

    def log_capture_cutoff(self, uptime: int) -> None:
        """One observation at timeout; never dispatches or changes capture gates."""
        snapshot = dict(uptime_ms=uptime, state=self.state,
            phase=self.approach.phase, player_xy=Player.GetXY(),
            tracked_id=self.approach.target_id,
            last_tracked_id=self.approach.last_target_id,
            item_sent=self.sent, captured_before=self.before if self.sent else None,
            actors=[])
        try:
            snapshot['player_dead'] = Agent.IsDead(Player.GetAgentID())
            snapshot['captured_now'] = GLOBAL_CACHE.Inventory.GetModelCount(CAPTURED_SKELETON)
            snapshot['mobstoppers_now'] = GLOBAL_CACHE.Inventory.GetModelCount(MOBSTOPPER)
        except Exception as exc:
            snapshot['inventory_or_player_error'] = f"{type(exc).__name__}: {exc}"
        try:
            visible = set(AgentArray.GetAgentArray())
            known = {aid for aid in (self.approach.target_id,
                     self.approach.last_target_id, self.corpse_id) if aid}
            for aid in sorted(visible | known):
                actor = dict(agent_id=aid, in_array=aid in visible)
                try:
                    valid = Agent.IsValid(aid)
                    living = valid and Agent.IsLiving(aid)
                    identity = Agent.GetEncNameStrByID(aid, literal=True) if living else ''
                    match = identity == SKELETON_IDENTITY
                    if aid not in known and not match:
                        continue
                    actor.update(valid=valid, living=living, identity_match=match,
                                 encoded=identity)
                    if living:
                        xy = Agent.GetXY(aid)
                        distance = math.dist(snapshot['player_xy'], xy)
                        actor.update(dead=Agent.IsDead(aid), health=Agent.GetHealth(aid),
                            xy=xy, distance=round(distance, 2),
                            in_capture_range=distance <= self.radius,
                            in_search_area=math.dist(xy, SKELETON_ORIGIN) <= SKELETON_SEARCH_RADIUS)
                except Exception as exc:
                    if aid not in known:
                        continue
                    actor['read_error'] = f"{type(exc).__name__}: {exc}"
                snapshot['actors'].append(actor)
        except Exception as exc:
            snapshot['scan_error'] = f"{type(exc).__name__}: {exc}"
        eligible = any(a.get('valid') and a.get('living') and a.get('identity_match')
                       and (a.get('dead') or 0 < a.get('health',0) <= 0.25)
                       and a.get('in_capture_range')
                       for a in snapshot['actors'])
        self.cutoff_summary = ("Resign checkpoint: a capturable skeleton was within capture range."
                               if eligible else
                               "Resign checkpoint: no capturable skeleton was read within capture range.")
        self.journal.emit('capture_cutoff', **snapshot)
        print(f"[{MODULE_NAME}] {BUILD_ID}: CAPTURE_CUTOFF {snapshot!r}")

    def tick(self) -> None:
        # Keep map observation alive while stopped, without performing actions.
        # Transient unready frames do not rearm a previously used attempt.
        ready = Routines.Checks.Map.MapValid()
        self.observe_readiness(ready)
        if not ready:
            self.bar_required = None
            self.cancel_loot()
            self.cancel_defense()
            self.approach.cancel()
            return
        if not self.enabled or Map.GetMapID()!=72:
            self.inspect_bar()
        if Map.GetMapID() != 72:
            self.cancel_loot()
            self.finish_run_timer()
            self.cancel_defense()
            if self.enabled:
                self.record_failure()
            self.journal.finish('confirmed' if self.confirmed_this_visit else 'left_instance')
            self.approach.cancel()
            self.in_underworld = False
            self.instance_uptime = None
            if self.enabled:
                self.message = "Waiting for the next Underworld entry."
            return
        uptime = Map.GetInstanceUptime()
        if not self.in_underworld or (
            self.instance_uptime is not None and uptime < self.instance_uptime
        ):
            self.new_visit()
        self.in_underworld = True
        self.instance_uptime = uptime
        if not self.enabled:
            return

        if not self.visit_log_started:
            self.run_started_at = time.monotonic()
            self.visit_log_started = True
            self.journal.begin(map_id=72, uptime_ms=uptime, mode_movement=self.use_movement,
                route=HALLOWEEN_ROUTE, skeleton_origin=SKELETON_ORIGIN,
                readiness_history=list(self.readiness_history))
        now = time.monotonic()
        if now >= self.next_status_log:
            self.next_status_log = now + 1.0
            target = self.approach.target_id
            self.journal.emit('status_checkpoint', monotonic=now, uptime_ms=uptime,
                state=self.state, phase=self.approach.phase, player_xy=Player.GetXY(),
                player_dead=Agent.IsDead(Player.GetAgentID()), target_id=target,
                item_sent=self.sent, confirmed=self.confirmed_this_visit,
                message=self.message, tracking=self.tracking_status,
                readiness=self.last_readiness_sample)
        inv = GLOBAL_CACHE.Inventory
        if uptime >= VISIT_LIMIT_MS and not self.visit_limit_reached:
            self.visit_limit_reached = True
            try:
                self.log_capture_cutoff(uptime)
            except Exception as exc:
                self.journal.emit('resign_snapshot_error', message=str(exc))
            self.request_resign("Ten-second instance timer")
        # Independent supervisor: do not cancel or overwrite the action state.
        self.service_resign()
        bar_ready = bool(not self.use_movement or self.detect_bar())
        if self.bar_profile in ('monk','generic') and self.state=='confirming':
            self.defensive_tick()
        if self.state == "complete":
            self.defensive_tick()
            if not (self.bar_profile in ('monk','generic') and self.approach.cast is not None):
                CaptureAssistant.loot_tick(self)
            self.message = "Capture confirmed; collecting your nearby drops, including after resign."
            return
        # Limit agent/name scans and inventory confirmation reads, not map
        # readiness, the Stop button, or the existing shared resign owner.
        if self.state not in ("watching", "confirming"):
            return
        capture_ready = True
        if self.state=='watching' and self.use_movement and not bar_ready:
            nearby = any(capturable(aid) and math.dist(Player.GetXY(),Agent.GetXY(aid))<=self.radius
                         for aid in AgentArray.GetAgentArray())
            if not nearby:
                self.halt(self.message)
                return
        if self.state == "watching" and self.use_movement and bar_ready:
            capture_ready = (MonkApproach.tick(self.approach,self) if self.bar_profile in ('monk','generic')
                             else ApproachAndSkills.tick(self.approach, self))
            action_state = (self.approach.phase, self.approach.target_id,
                            self.approach.slot, self.approach.fallback_slot,
                            self.approach.fallback_tree is not None)
            if action_state != self.last_action_state:
                self.last_action_state = action_state
                self.journal.emit('action_state', phase=action_state[0], target=action_state[1],
                    skill_slot=action_state[2], fallback_slot=action_state[3],
                    fallback_pending=action_state[4], player_xy=Player.GetXY())
            if not self.enabled or self.state != "watching":
                return
        now = time.monotonic()
        if now < self.next_poll_at:
            return
        self.next_poll_at = now + POLL_INTERVAL
        if self.sent:
            count = inv.GetModelCount(CAPTURED_SKELETON)
            delta = count - self.before
            if delta == 1:
                self.confirmed_this_visit = True
                self.confirmed_total += 1
                self.journal.emit('capture_confirmed', corpse=self.corpse_id,
                    before=self.before, after=count, distance=self.distance)
                self.state = "complete"
                self.approach.cancel()
                self.message = "Capture confirmed; defense and owned loot. Resign timer remains independent."
                print(f"[{MODULE_NAME}] {BUILD_ID}: CONFIRMED corpse={self.corpse_id} "
                      f"distance={self.distance:.1f}, captured={self.before}->{count}")
                self.defensive_tick()
                if not (self.bar_profile in ('monk','generic') and self.approach.cast is not None):
                    CaptureAssistant.loot_tick(self)
                return
            elif delta != 0:
                self.halt(f"Unexpected Captured Skeleton count change ({delta:+d}); no retry.")
                return
            if Agent.IsDead(Player.GetAgentID()):
                self.message = "Waiting for resurrection; capture confirmation remains active."
                return
            if time.monotonic() < self.deadline:
                return
            if inv.GetModelCount(MOBSTOPPER) < self.items_before:
                self.message = "Mobstopper consumed; waiting for capture confirmation."
                return
            if self.state == "confirming":
                self.state = "watching"
                self.journal.emit('capture_retry_ready', attempts=self.capture_attempts,
                    player_dead=False, captured_now=count, captured_before=self.before)
        if not capture_ready:
            return
        if self.state != "watching":
            return
        if Agent.IsDead(Player.GetAgentID()):
            self.message = "You are dead; waiting. No item will be used."
            return

        player_xy = Player.GetXY()
        candidates: list[tuple[float, int]] = []
        for agent_id in AgentArray.GetAgentArray():
            if not Agent.IsValid(agent_id) or not Agent.IsLiving(agent_id):
                continue
            if Agent.GetEncNameStrByID(agent_id, literal=True) != SKELETON_IDENTITY:
                continue
            if not capturable(agent_id):
                continue
            distance = math.dist(player_xy, Agent.GetXY(agent_id))
            if distance <= self.radius:
                candidates.append((distance, agent_id))
        if not candidates:
            self.message = f"Watching: no weakened or dead skeleton within {self.radius} units."
            return

        distance, agent_id = min(candidates)
        item_id = inv.GetFirstModelID(MOBSTOPPER)
        if not item_id:
            self.halt("No Everlasting Mobstopper in your inventory.")
            return
        # Re-read the exact actor and distance on the dispatching tick. A missing
        # actor is never treated as proof of death. Item capture is area-based;
        # no target, attack, movement or interaction command is necessary.
        if (not Agent.IsValid(agent_id) or not Agent.IsLiving(agent_id)
                or Agent.GetEncNameStrByID(agent_id, literal=True) != SKELETON_IDENTITY
                or not capturable(agent_id)):
            return
        distance = math.dist(Player.GetXY(), Agent.GetXY(agent_id))
        if distance > self.radius:
            return
        if not self.sent:
            self.before = inv.GetModelCount(CAPTURED_SKELETON)
            self.items_before = inv.GetModelCount(MOBSTOPPER)
        self.corpse_id = agent_id
        self.distance = distance
        # Mark before enqueue so an exception cannot cause a duplicate request.
        self.sent = True
        self.capture_attempts += 1
        self.state = "confirming"
        self.deadline = time.monotonic() + CONFIRM_TIMEOUT
        self.message = "Mobstopper requested once; waiting for Captured Skeleton +1."
        print(f"[{MODULE_NAME}] {BUILD_ID}: REQUEST corpse={agent_id}, distance={distance:.1f}, "
              f"limit={self.radius}, captured_before={self.before}, mobstoppers={self.items_before}")
        self.journal.emit('capture_requested', corpse=agent_id, distance=distance,
            captured_before=self.before, mobstoppers_before=self.items_before,
            attempt=self.capture_attempts, player_dead=False,
            next_attempt_after_seconds=CONFIRM_TIMEOUT,
            target_dead=Agent.IsDead(agent_id), target_health=Agent.GetHealth(agent_id))
        inv.UseItem(item_id)


assistant = CaptureAssistant()
ini_key = ""


def update() -> None:
    started = time.monotonic()
    try:
        Routines.Checks.Map.RegisterLocalPlayerUpkeep(assistant, 72)
        with Routines.Checks.Map.LocalPlayerReadiness():
            CaptureAssistant.tick(assistant)
    except Exception as exc:
        assistant.journal.readiness('update_exception', traceback=traceback.format_exc(),
            state=assistant.state, phase=assistant.approach.phase)
        assistant.halt(f"Error: {type(exc).__name__}: {exc}. No automatic action retry.")
    finally:
        ended = time.monotonic()
        if ended - started >= 0.1 and ended - assistant.last_slow_log >= 1.0:
            assistant.last_slow_log = ended
            assistant.journal.readiness('slow_update', duration_seconds=round(ended-started,4),
                state=assistant.state, phase=assistant.approach.phase)


def draw() -> None:
    global ini_key
    if not ini_key:
        # The existing ImGui facade owns window persistence and ignores ini_key.
        ini_key = MODULE_NAME
    try:
        if ImGui.Begin(ini_key, MODULE_NAME, flags=PyImGui.WindowFlags.AlwaysAutoResize):
            if assistant.enabled:
                if PyImGui.button("STOP FARMING", 250, 44):
                    assistant.stop()
            elif PyImGui.button("START FARMING", 250, 44):
                assistant.start()
            if assistant.state == "failed":
                PyImGui.text_colored("NEEDS ATTENTION", (1.0, 0.3, 0.2, 1.0))
            else:
                PyImGui.text("Farm active" if assistant.enabled else "Farm stopped")
            if not assistant.readiness_valid:
                PyImGui.text_wrapped(assistant.readiness_status)
            PyImGui.text_wrapped(assistant.message)
            if assistant.resign_error:
                PyImGui.text_wrapped("Resign needs attention: " + assistant.resign_error)
            if assistant.cutoff_summary:
                PyImGui.text_wrapped(assistant.cutoff_summary)
            PyImGui.separator()
            PyImGui.text("THIS SESSION")
            PyImGui.text(f"Confirmed this session: {assistant.confirmed_total} | Failures: {assistant.failure_total}")
            if PyImGui.button("Reset statistics"):
                assistant.reset_statistics()
            PyImGui.text(f"Session elapsed: {assistant.elapsed_session():.1f}s")
            run_seconds = (time.monotonic()-assistant.run_started_at
                if assistant.run_started_at is not None else assistant.last_run_seconds)
            PyImGui.text("Run start to resign: " +
                (f"{run_seconds:.1f}s" if run_seconds is not None else "--"))
            average = (assistant.resign_interval_total/assistant.resign_interval_count
                if assistant.resign_interval_count else None)
            PyImGui.text("Average resign to resign: " +
                (f"{average:.1f}s ({assistant.resign_interval_count} intervals)"
                    if average is not None else "-- (needs two resigns)"))
            if not assistant.enabled:
                assistant.use_movement = PyImGui.checkbox("Use movement and skills", assistant.use_movement)
            PyImGui.separator()
            PyImGui.text("BUILD REQUIREMENTS")
            if not assistant.use_movement:
                PyImGui.text("No skill requirements in capture-only mode.")
            elif assistant.bar_required is True:
                PyImGui.text_colored("Required skills found", (0.3,1.0,0.4,1.0))
                dash = assistant.bar_bindings.get(1)
                jump = assistant.bar_bindings.get(2)
                name = assistant.bar_names.get(2,'Foe shadowstep').replace('_',' ')
                PyImGui.text(f"Dash: slot {dash} | {name}: slot {jump}")
            elif assistant.bar_required is False:
                PyImGui.text_colored("Missing required skills", (1.0,0.4,0.2,1.0))
                PyImGui.text_wrapped("Missing: " + ', '.join(assistant.bar_missing))
            else:
                PyImGui.text("Waiting for your skill bar to load.")
            PyImGui.text_wrapped("Required for automatic movement: Dash + Death's Charge OR Dark Prison. Any slots; any profession.")
            PyImGui.text_wrapped("Ally shadowsteps, defensive skills and damage skills are optional. Other slots can hold anything.")
            PyImGui.separator()
            PyImGui.text("HOW IT WORKS")
            if assistant.use_movement:
                PyImGui.text_wrapped("Automatic movement and skills; captures at 25% health or lower, or after death, within 322 units.")
                PyImGui.text_wrapped(assistant.tracking_status)
                PyImGui.text_wrapped("Moves toward the known skeleton; tries another foe, then an optional ally shadowstep if needed. Keeps walking to close the distance.")
            else:
                PyImGui.text_wrapped("Capture only: you handle movement and combat. Captures within 322 units.")
            PyImGui.text("After capture: defense and your nearby loot, including after resign.")
            PyImGui.text("Resigns once at 10 seconds; capture work continues until confirmed.")
            if assistant.journal.error:
                PyImGui.text_wrapped("Persistent logging unavailable: " + assistant.journal.error)
            if PyImGui.collapsing_header("Diagnostics"):
                PyImGui.text("Profile: " + (assistant.bar_profile or assistant.bar_candidate_profile or "Waiting"))
                PyImGui.text("Logs: Logs/HalloweenSkeleton")
                PyImGui.text(BUILD_ID)
    finally:
        ImGui.End(ini_key)


def main() -> None:
    pass


def on_disable() -> None:
    assistant.stop("Widget disabled.")


def draw_contents():
    global ini_key
    if assistant.enabled:
        if PyImGui.button('STOP FARMING', 250, 44):
            assistant.stop()
    elif PyImGui.button('START FARMING', 250, 44):
        assistant.start()
    if assistant.state == 'failed':
        PyImGui.text_colored('NEEDS ATTENTION', (1.0, 0.3, 0.2, 1.0))
    else:
        PyImGui.text('Farm active' if assistant.enabled else 'Farm stopped')
    if not assistant.readiness_valid:
        PyImGui.text_wrapped(assistant.readiness_status)
    PyImGui.text_wrapped(assistant.message)
    if assistant.resign_error:
        PyImGui.text_wrapped('Resign needs attention: ' + assistant.resign_error)
    if assistant.cutoff_summary:
        PyImGui.text_wrapped(assistant.cutoff_summary)
    PyImGui.separator()
    PyImGui.text('THIS SESSION')
    PyImGui.text(f'Confirmed this session: {assistant.confirmed_total} | Failures: {assistant.failure_total}')
    if PyImGui.button('Reset statistics'):
        assistant.reset_statistics()
    PyImGui.text(f'Session elapsed: {assistant.elapsed_session():.1f}s')
    run_seconds = time.monotonic() - assistant.run_started_at if assistant.run_started_at is not None else assistant.last_run_seconds
    PyImGui.text('Run start to resign: ' + (f'{run_seconds:.1f}s' if run_seconds is not None else '--'))
    average = assistant.resign_interval_total / assistant.resign_interval_count if assistant.resign_interval_count else None
    PyImGui.text('Average resign to resign: ' + (f'{average:.1f}s ({assistant.resign_interval_count} intervals)' if average is not None else '-- (needs two resigns)'))
    if not assistant.enabled:
        assistant.use_movement = PyImGui.checkbox('Use movement and skills', assistant.use_movement)
    PyImGui.separator()
    PyImGui.text('BUILD REQUIREMENTS')
    if not assistant.use_movement:
        PyImGui.text('No skill requirements in capture-only mode.')
    elif assistant.bar_required is True:
        PyImGui.text_colored('Required skills found', (0.3, 1.0, 0.4, 1.0))
        dash = assistant.bar_bindings.get(1)
        jump = assistant.bar_bindings.get(2)
        name = assistant.bar_names.get(2, 'Foe shadowstep').replace('_', ' ')
        PyImGui.text(f'Dash: slot {dash} | {name}: slot {jump}')
    elif assistant.bar_required is False:
        PyImGui.text_colored('Missing required skills', (1.0, 0.4, 0.2, 1.0))
        PyImGui.text_wrapped('Missing: ' + ', '.join(assistant.bar_missing))
    else:
        PyImGui.text('Waiting for your skill bar to load.')
    PyImGui.text_wrapped("Required for automatic movement: Dash + Death's Charge OR Dark Prison. Any slots; any profession.")
    PyImGui.text_wrapped('Ally shadowsteps, defensive skills and damage skills are optional. Other slots can hold anything.')
    PyImGui.separator()
    PyImGui.text('HOW IT WORKS')
    if assistant.use_movement:
        PyImGui.text_wrapped('Automatic movement and skills; captures at 25% health or lower, or after death, within 322 units.')
        PyImGui.text_wrapped(assistant.tracking_status)
        PyImGui.text_wrapped('Moves toward the known skeleton; tries another foe, then an optional ally shadowstep if needed. Keeps walking to close the distance.')
    else:
        PyImGui.text_wrapped('Capture only: you handle movement and combat. Captures within 322 units.')
    PyImGui.text('After capture: defense and your nearby loot, including after resign.')
    PyImGui.text('Resigns once at 10 seconds; capture work continues until confirmed.')
    if assistant.journal.error:
        PyImGui.text_wrapped('Persistent logging unavailable: ' + assistant.journal.error)
    if PyImGui.collapsing_header('Diagnostics'):
        PyImGui.text('Profile: ' + (assistant.bar_profile or assistant.bar_candidate_profile or 'Waiting'))
        PyImGui.text('Logs: Logs/HalloweenSkeleton')
        PyImGui.text(BUILD_ID)
