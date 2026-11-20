"""Shards of Orr level-3 GID 8143 fire gate for per-client HeroAI.

Both leader and followers run HeroAI independently. A Shards botting-tree
node on the leader cannot stop follower AI from chasing its current target.
Keep the hard stop local, scoped to map 583 and gadget 8143 only.
"""
from __future__ import annotations
import math
import time

FENDI_LEVEL_3_MAP_ID = 583
FORCED_WAIT_GADGET_ID = 8143
ACTIVE_BIT = 0x8000
# Apply before reaching the dangerous flame radius (Shards uses 430u).
HOLD_APPROACH_RADIUS = 1400.0
STOP_REFRESH_S = 0.30

class ShardsFlameHold:
    def __init__(self):
        self._latched_agent_id = 0
        self._last_stop_s = 0.0
        self._last_log_state = False

    def reset(self):
        self._latched_agent_id = 0
        self._last_stop_s = 0.0
        self._last_log_state = False

    def _emit(self, message):
        try:
            from ..py4gwcorelib_src.Console import ConsoleLog, Console
            ConsoleLog('ShardsFlameHold', message, Console.MessageType.Info, log=True)
        except Exception:
            pass

    @staticmethod
    def _active(agent_id):
        from ..Agent import Agent
        a = Agent.GetAgentByID(int(agent_id))
        if a is None:
            return False
        return bool(int(getattr(a, 'name_properties', 0) or 0) & ACTIVE_BIT)

    @staticmethod
    def _nearest_active(current):
        from ..Agent import Agent
        from ..AgentArray import AgentArray
        nearest = (float('inf'), 0)
        for item in AgentArray.GetGadgetArray() or []:
            aid = int(item or 0)
            if aid <= 0:
                continue
            try:
                gadget = Agent.GetGadgetAgentByID(aid)
                if gadget is None or int(getattr(gadget, 'gadget_id', 0) or 0) != FORCED_WAIT_GADGET_ID:
                    continue
                if not ShardsFlameHold._active(aid):
                    continue
                xy = Agent.GetXY(aid)
                distance = math.dist(current, (float(xy[0]), float(xy[1])))
                if distance < nearest[0]:
                    nearest = distance, aid
            except Exception:
                continue
        return nearest

    def hold_if_needed(self):
        """Return True if HeroAI must not tick movement or attack this frame.

        Once held, target changes or moving outside the detection radius must
        NOT release the wait; only the trap going OFF / map exit may release it.
        """
        from ..Map import Map
        from ..Player import Player
        try:
            if not Map.IsMapReady() or int(Map.GetMapID() or 0) != FENDI_LEVEL_3_MAP_ID:
                self.reset()
                return False
            current = Player.GetXY()
            current = float(current[0]), float(current[1])
            if self._latched_agent_id:
                if not self._active(self._latched_agent_id):
                    self._emit(f'Trap 8143 OFF; follower movement resumed (agent={self._latched_agent_id}).')
                    self.reset()
                    return False
            else:
                distance, aid = self._nearest_active(current)
                if aid == 0 or distance > HOLD_APPROACH_RADIUS:
                    return False
                self._latched_agent_id = aid
                self._emit(f'Trap 8143 ON at {distance:.0f}u; holding local HeroAI until OFF (agent={aid}).')

            now = time.monotonic()
            if now - self._last_stop_s >= STOP_REFRESH_S:
                # Explicit raw stop also clears the independent ProactiveMove
                # intent so it cannot resume its last in-flight detour.
                Player.Move(current[0], current[1], avoid_obstacles=False)
                self._last_stop_s = now
            return True
        except Exception:
            # Never break HeroAI on a scanner error.
            return False

SHARDS_FLAME_HOLD = ShardsFlameHold()
