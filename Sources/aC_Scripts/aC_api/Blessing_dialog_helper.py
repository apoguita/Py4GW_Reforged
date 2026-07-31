# Blessing_dialog_helper.py
import time
from Py4GWCoreLib import *
from collections import deque, defaultdict
from Py4GWCoreLib.FrameTree import Frame, FrameId
from Py4GWCoreLib.FrameTree import FrameTree

# —— Constants ——————————————————
NPC_DIALOG_HASH    = 3856160816
DEFAULT_OFFSET     = [2, 0, 0, 1]
DIALOG_CHILD_OFFSET = list(DEFAULT_OFFSET)

# —— Core Helpers —————————————————

def is_npc_dialog_visible() -> bool:
    """Return True if the NPC-dialog frame exists and is visible."""
    fid = Frame(FrameId.NpcDialog)
    return fid.exists and fid.is_visible


def find_dialog_offset() -> None:
    """Auto-detects DIALOG_CHILD_OFFSET for the option-container."""
    global DIALOG_CHILD_OFFSET
    root = Frame(FrameId.NpcDialog)
    if not root.is_usable:
        return

    children_map = FrameTree.children_map()

    # BFS: pick the container with the most template_type==1 children
    queue = deque([root])
    best = None
    best_count = 0
    while queue:
        cur = queue.popleft()
        kids = [Frame.from_id(c) for c in children_map.get(cur.frame_id, [])]
        count = sum(1 for c in kids if c.is_visible and c.template_type == 1)
        if count > best_count and count >= 2:
            best_count, best = count, cur
        queue.extend(kids)

    if best is None:
        return

    # index-path from root -> best
    path = []
    cur = best
    while cur != root:
        parent = cur.parent()
        siblings = children_map.get(parent.frame_id, [])
        if cur.frame_id not in siblings:
            return
        path.insert(0, siblings.index(cur.frame_id))
        cur = parent

    DIALOG_CHILD_OFFSET = path


def _dialog_buttons() -> list:
    """Visible option buttons, top to bottom, as handles."""
    def is_button(frame) -> bool:
        return frame.is_visible and frame.template_type == 1

    found = [f for f in FrameTree.frames_at_path(NPC_DIALOG_HASH, DIALOG_CHILD_OFFSET)
             if is_button(f)]
    if found:
        return FrameTree.sort_by_vertical(found)

    root = Frame(FrameId.NpcDialog)
    if not root.exists:
        return []
    return FrameTree.sort_by_vertical(
        [f for f in FrameTree.descendants(root) if is_button(f)])


def get_dialog_buttons(debug: bool = False) -> list:
    """The dialog's option buttons as handles, top to bottom."""
    if DIALOG_CHILD_OFFSET == DEFAULT_OFFSET:
        find_dialog_offset()

    buttons = _dialog_buttons()
    if debug:
        ConsoleLog("DialogHelper",
                   "Dialog buttons -> %s" % [str(b) for b in buttons],
                   Console.MessageType.Info)
    return buttons


def click_dialog_button(choice: int, debug: bool = False) -> bool:
    """Click the Nth dialog option (1-based). Returns True if dispatched."""
    buttons = get_dialog_buttons(debug)
    idx = choice - 1
    if idx < 0 or idx >= len(buttons):
        if debug:
            ConsoleLog("DialogHelper", f"Choice #{choice} out of range",
                       Console.MessageType.Warning)
        return False

    target = buttons[idx]
    if debug:
        ConsoleLog(
            "DialogHelper",
            f"[{time.time():.2f}] Clicking dialog choice #{choice} -> {target}",
            Console.MessageType.Info
        )
    target.click()
    return True


def get_dialog_button_count(debug: bool = False) -> int:
    """
    Return the number of visible dialog‐button frames (template_type == 1),
    and log the count if debug=True.
    Log Example: [DialogHelper|Info] Dialog button count 3
    """
    count = len(get_dialog_buttons(debug))

    if debug:
        # Log the count to the console as an info message
        ConsoleLog(
            "DialogHelper",
            f"Dialog button count {count}",
            Console.MessageType.Info
        )

    return count

__all__ = ["is_npc_dialog_visible", "click_dialog_button", "get_dialog_button_count"]
