from Py4GWCoreLib import *
from collections import deque, defaultdict
from Py4GWCoreLib.FrameTree import Frame, FrameId
from Py4GWCoreLib.FrameTree import FrameTree

# â€”â€” Constants â€”â€”
NPC_DIALOG_HASH    = 3856160816
DEFAULT_OFFSET     = [2, 0, 0, 1]
# will be updated at runtime if detection succeeds
DIALOG_CHILD_OFFSET = list(DEFAULT_OFFSET)

# â€”â€” Helpers â€”â€”
def is_npc_dialog_visible() -> bool:
    """Return True if the NPC-dialog frame exists and is visible."""
    fid = Frame(FrameId.NpcDialog)
    return fid.exists and fid.is_visible


def find_dialog_offset(debug: bool = False) -> None:
    """Auto-detects DIALOG_CHILD_OFFSET for the option-container."""
    global DIALOG_CHILD_OFFSET
    root = Frame(FrameId.NpcDialog)
    if not root.is_usable:
        return

    children_map = FrameTree.children_map()

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

    path = []
    curr = best
    while curr != root:
        parent = curr.parent()
        siblings = children_map.get(parent.frame_id, [])
        if curr.frame_id not in siblings:
            return
        path.insert(0, siblings.index(curr.frame_id))
        curr = parent

    DIALOG_CHILD_OFFSET = path
    if debug:
        ConsoleLog("DialogTester", f"Detected offset {path}", Console.MessageType.Info)


def get_dialog_buttons(debug: bool = False) -> list:
    """Visible option buttons, top to bottom, as handles."""
    if DIALOG_CHILD_OFFSET == DEFAULT_OFFSET:
        find_dialog_offset(debug)

    def is_button(frame) -> bool:
        return frame.is_visible and frame.template_type == 1

    primary = [f for f in FrameTree.frames_at_path(NPC_DIALOG_HASH, DIALOG_CHILD_OFFSET)
               if is_button(f)]
    if primary:
        ordered = FrameTree.sort_by_vertical(primary)
        if debug:
            ConsoleLog("DialogTester",
                       "Offset buttons -> %s" % [str(b) for b in ordered],
                       Console.MessageType.Info)
        return ordered

    if debug:
        ConsoleLog("DialogTester", "Falling back to BFS", Console.MessageType.Info)

    root = Frame(FrameId.NpcDialog)
    if not root.exists:
        return []
    ordered = FrameTree.sort_by_vertical(
        [f for f in FrameTree.descendants(root) if is_button(f)])
    if debug:
        ConsoleLog("DialogTester",
                   "BFS buttons -> %s" % [str(b) for b in ordered],
                   Console.MessageType.Info)
    return ordered


def click_dialog_button(choice: int, debug: bool = False) -> bool:
    """
    Clicks the given dialog choice by index (1-based).
    Performs an immediate FrameClick plus queuing it on the ACTION queue.
    Returns True if dispatched.
    """
    if not is_npc_dialog_visible():
        if debug:
            ConsoleLog("DialogTester", "Dialog not visible; cannot click.", Console.MessageType.Warning)
        return False

    buttons = get_dialog_buttons(debug)
    idx = choice - 1
    if idx < 0 or idx >= len(buttons):
        if debug:
            ConsoleLog("DialogTester", f"Choice #{choice} out of range (found {len(buttons)}).", Console.MessageType.Warning)
        return False

    target = buttons[idx]
    # immediate plus queued click
    ActionQueueManager().AddAction("ACTION", target.click)

    if debug:
        ConsoleLog("DialogTester", f"Clicked & queued frame {target} (choice #{choice})", Console.MessageType.Info)
    return True

# â€”â€” ImGui window â€”â€”
window = ImGui.WindowModule(
    "Dialog Tester",
    window_name="Dialog Tester",
    window_size=(360, 240),
    window_flags=PyImGui.WindowFlags.AlwaysAutoResize
)

def on_ui():
    window.begin()
    PyImGui.text("NPC Dialog Tester")
    PyImGui.separator()

    # Debug info
    vis = is_npc_dialog_visible()
    buttons = get_dialog_buttons(debug=True)
    # gather template types for each choice
    types = []
    for button in buttons:
        try:
            types.append(button.template_type)
        except Exception:
            types.append(None)

    PyImGui.text(f"Dialog Visible : {vis}")
    PyImGui.text(f"Choices Found  : {len(buttons)} â†’ {buttons}")
    PyImGui.text(f"Template Types: {types}")
    PyImGui.separator()

    # Dynamic choice buttons
    for i, fid in enumerate(buttons, start=1):
        label = f"Click Choice {i}"
        if PyImGui.button(label):
            if not click_dialog_button(i, debug=True):
                ConsoleLog("DialogTester", f"Failed to click choice {i}", Console.MessageType.Error)
        if (i % 3) != 0:
            PyImGui.separator()

    window.end()

def main():
    on_ui()
