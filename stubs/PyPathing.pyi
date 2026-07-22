# PyPathing stub — Reforged Native surface
# Matches src/GW/pathing/pathing_bindings.cpp (GW::pathing::PathPlanner).

from enum import IntEnum
from typing import List, Tuple

class PathStatus(IntEnum):
    Idle = 0
    Pending = 1
    Ready = 2
    Failed = 3

# py::enum_ .export_values() also injects the members at module level.
Idle: PathStatus
Pending: PathStatus
Ready: PathStatus
Failed: PathStatus

class PathPlanner:
    def __init__(self) -> None: ...

    def plan(
        self,
        start_x: float,
        start_y: float,
        start_z: float,
        goal_x: float,
        goal_y: float,
        goal_z: float,
    ) -> None:
        """Submit a path planning task to the game thread."""
        ...

    def compute_immediate(
        self,
        start_x: float,
        start_y: float,
        start_z: float,
        goal_x: float,
        goal_y: float,
        goal_z: float,
    ) -> List[Tuple[float, float, float]]:
        """Compute the path immediately and return it as a list of (x, y, z) tuples."""
        ...

    def get_status(self) -> PathStatus:
        """Get current planning status (Idle, Pending, Ready, Failed)."""
        ...

    def is_ready(self) -> bool:
        """Check if the planned path is ready."""
        ...

    def was_successful(self) -> bool:
        """Check if the path planning was successful."""
        ...

    def get_path(self) -> List[Tuple[float, float, float]]:
        """Retrieve the calculated path as a list of (x, y, z) tuples."""
        ...

    def reset(self) -> None:
        """Reset the planner to Idle state and clear the last result."""
        ...
