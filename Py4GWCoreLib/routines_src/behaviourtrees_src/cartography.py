"""Hold a captured cartography edge using the Iron Mines boundary pattern."""
from __future__ import annotations

import math
import time

from Py4GWCoreLib.Map import Map
from Py4GWCoreLib.Player import Player
from Py4GWCoreLib.py4gwcorelib_src.BehaviorTree import BehaviorTree


class _CartographyHoldNode(BehaviorTree.Node):
    def __init__(self, point: tuple[float, float], direction: str,
                 hold_seconds: float, name: str) -> None:
        super().__init__(name=name)
        self._point = point
        self._direction = direction
        self._duration = hold_seconds
        self._started: float | None = None
        self._map_id: int | None = None
        self._moving = False

    def _stop(self) -> None:
        if self._moving:
            # Never cancel movement in a different instance.
            if Map.IsExplorable() and int(Map.GetMapID()) == self._map_id:
                Player.Move(*Player.GetXY())
            self._moving = False

    def _tick_impl(self) -> BehaviorTree.NodeState:
        if not Map.IsExplorable():
            self._stop()
            return BehaviorTree.NodeState.FAILURE
        if self._started is None:
            if math.dist(Player.GetXY(), self._point) > 200.0:
                return BehaviorTree.NodeState.FAILURE
            self._map_id = int(Map.GetMapID())
            self._started = time.monotonic()
            dx, dy = {'west': (-750.0, 0.0), 'south': (0.0, -750.0)}[self._direction]
            Player.Move(self._point[0] + dx, self._point[1] + dy)
            self._moving = True
        if int(Map.GetMapID()) != self._map_id:
            self._moving = False
            return BehaviorTree.NodeState.FAILURE
        if time.monotonic() - self._started < self._duration:
            return BehaviorTree.NodeState.RUNNING
        self._stop()
        return BehaviorTree.NodeState.SUCCESS

    def reset(self) -> None:
        self._stop()
        self._started = None
        self._map_id = None
        super().reset()


def HoldCartographyPoint(
    point: tuple[float, float],
    *,
    direction: str,
    hold_seconds: float = 3.0,
    name: str = 'Face the map edge and hold position',
) -> BehaviorTree:
    """Hold a captured map edge, releasing movement on finish or cancellation."""
    if (type(point) is not tuple or len(point) != 2
            or not all(type(v) in (int, float) and math.isfinite(v) for v in point)):
        raise ValueError('Cartography hold requires a finite captured XY tuple')
    if direction not in ('west', 'south'):
        raise ValueError('Supported captured edge directions are west and south')
    if not math.isfinite(hold_seconds) or hold_seconds <= 0:
        raise ValueError('Cartography hold duration must be positive and finite')
    return BehaviorTree(_CartographyHoldNode(point, direction, hold_seconds, name))
