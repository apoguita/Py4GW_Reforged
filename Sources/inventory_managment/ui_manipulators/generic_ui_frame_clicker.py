"""Frame-tree enumeration helpers for the inventory management scripts.

The live UI tree is served by the FrameTree snapshot, which rebuilds lazily
once per tick.  Prefer a registry handle (``Frame(FrameId.<...>)``) whenever
the target frame has a key; this helper exists for callers that must walk an
arbitrary container's descendants by relative child codes.
"""

from Py4GWCoreLib.FrameTree import FrameTree


class UIManagerHelpers:
    """Reusable helpers for locating native UI frames."""

    def GetAllChildFrameIDs(self, root_frame_id: int) -> list[int]:
        """
        Return every live frame id whose ancestry reaches ``root_frame_id``.

        Frames come back breadth-first in native frame-array order within each
        level, matching the order of the legacy ``GetFrameArray`` sweep.  The
        snapshot is at most one tick old, so this reflects the UI state on the
        next tick when called from ``update()`` / ``draw()``.

        :param root_frame_id: The container frame id to enumerate.
        :return: List of descendant frame ids (does not include the root).
        """
        return FrameTree.descendants_of(root_frame_id)