"""Live frame-tree capture as a plain dictionary.

No file I/O and no json - see AGENTS.md: json.load/json.dump/open() for data are
forbidden in project code. The capture is held in memory and exposed as
FRAME_TREE / FRAME_TREE_META for anything that wants to consume it.

Name tables come from Py4GWCoreLib.FrameTree.frame_names (dict literals).
"""

import PyImGui

from Py4GWCoreLib.FrameTree import FrameTree
from Py4GWCoreLib.FrameTree.frame_names import (
    FRAME_NAMES_CONFIRMED,
    FRAME_NAMES_OBSERVED,
)

MODULE_NAME = "Frame Tree Dump"

# ---- capture, as dictionaries ------------------------------------------
FRAME_TREE: dict[int, dict] = {}      # frame_id -> node
FRAME_TREE_META: dict[str, int] = {}  # counts
FRAME_ROOTS: list[int] = []
UNKNOWN_HASHES: list[dict] = []       # hashed frames with no name

status_text = "Ready - press Dump Frame Tree"
FILTERS = ("All", "Named", "Unknown hashed")
filter_mode = 0
_keep: set[int] = set()


def classify(h: int) -> tuple[str, str]:
    """-> (name, src) with src in 'confirmed' | 'observed' | 'unknown' | ''."""
    if not h:
        return "", ""
    name = FRAME_NAMES_CONFIRMED.get(h)
    if name:
        return name, "confirmed"
    name = FRAME_NAMES_OBSERVED.get(h)
    if name:
        return name, "observed"
    return "", "unknown"


def build_frame_tree() -> dict[int, dict]:
    """Walk the live tree and return {frame_id: node}. Also refreshes globals."""
    global FRAME_TREE, FRAME_TREE_META, FRAME_ROOTS, UNKNOWN_HASHES

    frames = {f.frame_id: f for f in FrameTree.all_frames()}

    children: dict[int, list[int]] = {}
    roots: list[int] = []
    for fid, fr in frames.items():
        pid = fr.parent_id
        children.setdefault(pid, []).append(fid)
        if pid == 0 or pid not in frames:
            roots.append(fid)
    for pid in children:
        children[pid].sort()
    roots.sort()

    tree: dict[int, dict] = {}
    for fid, fr in frames.items():
        h = fr.hash
        name, src = classify(h)
        tree[fid] = {
            "id": fid,
            "parent": fr.parent_id,
            "code": fr.code,
            "hash": h,
            "name": name,
            "src": src,
            "children": [k for k in children.get(fid, []) if k in frames],
        }

    FRAME_TREE = tree
    FRAME_ROOTS = roots
    FRAME_TREE_META = {
        "frames": len(tree),
        "leaves": sum(1 for n in tree.values() if not n["children"]),
        "hashed": sum(1 for n in tree.values() if n["hash"]),
        "confirmed": sum(1 for n in tree.values() if n["src"] == "confirmed"),
        "observed": sum(1 for n in tree.values() if n["src"] == "observed"),
        "unknown": sum(1 for n in tree.values() if n["src"] == "unknown"),
    }
    UNKNOWN_HASHES = [
        {"hash": n["hash"], "id": n["id"], "code": n["code"], "path": ancestry(n["id"])}
        for n in tree.values() if n["src"] == "unknown"
    ]
    _rebuild_keep()
    return tree


def ancestry(fid: int) -> str:
    """Readable chain from the nearest named ancestor down to this frame."""
    chain, cur, seen = [], fid, set()
    while cur and cur not in seen:
        seen.add(cur)
        n = FRAME_TREE.get(cur)
        if n is None:
            break
        chain.append(n)
        if cur != fid and n["name"]:
            break
        cur = n["parent"]
    chain.reverse()
    return " -> ".join(
        (n["name"] if (i == 0 and n["name"]) else str(n["code"]))
        for i, n in enumerate(chain)
    )


# ---- drawing -----------------------------------------------------------
def _match(n: dict) -> bool:
    if filter_mode == 1:
        return bool(n["name"])
    if filter_mode == 2:
        return n["src"] == "unknown"
    return True


def _rebuild_keep() -> None:
    global _keep
    _keep = set()

    def visit(fid, seen):
        if fid in seen:
            return False
        seen.add(fid)
        n = FRAME_TREE.get(fid)
        if n is None:
            return False
        hit = _match(n)
        for k in n["children"]:
            if visit(k, seen):
                hit = True
        if hit:
            _keep.add(fid)
        return hit

    seen: set[int] = set()
    for r in FRAME_ROOTS:
        visit(r, seen)


def _label(n: dict) -> str:
    s = "#%d  code=%d" % (n["id"], n["code"])
    if n["hash"]:
        if n["src"] == "confirmed":
            s += "   %s" % n["name"]
        elif n["src"] == "observed":
            s += "   ~%s" % n["name"]
        else:
            s += "   ? UNKNOWN hash=%d" % n["hash"]
    return s


def _color(n: dict) -> tuple[float, float, float, float]:
    if n["src"] == "confirmed":
        return (0.50, 0.92, 0.50, 1.0)
    if n["src"] == "observed":
        return (0.92, 0.86, 0.42, 1.0)
    if n["src"] == "unknown":
        return (0.95, 0.45, 0.45, 1.0)
    return (0.62, 0.62, 0.62, 1.0)


def draw_node(fid: int, seen: set) -> None:
    if fid in seen:
        return
    seen.add(fid)
    n = FRAME_TREE.get(fid)
    if n is None or (filter_mode and fid not in _keep):
        return

    kids = n["children"]
    if filter_mode:
        kids = [k for k in kids if k in _keep]

    if not kids:
        r, g, b, a = _color(n)
        PyImGui.text_colored(r, g, b, a, _label(n))
        return

    if PyImGui.tree_node("%s##%d" % (_label(n), fid)):
        for k in kids:
            draw_node(k, seen)
        PyImGui.tree_pop()


def configure() -> None:
    pass


def main() -> None:
    global status_text, filter_mode

    if PyImGui.begin(MODULE_NAME):
        if PyImGui.button("Dump Frame Tree"):
            try:
                build_frame_tree()
                status_text = "Captured %d frames" % FRAME_TREE_META["frames"]
            except Exception as exc:
                status_text = "Dump failed: %s" % exc
        PyImGui.same_line(0, -1)
        if PyImGui.button("Filter: %s" % FILTERS[filter_mode]):
            filter_mode = (filter_mode + 1) % len(FILTERS)
            _rebuild_keep()

        PyImGui.text(status_text)
        PyImGui.text("names: confirmed=%d  observed=%d"
                     % (len(FRAME_NAMES_CONFIRMED), len(FRAME_NAMES_OBSERVED)))
        if FRAME_TREE_META:
            PyImGui.text("frames=%(frames)d  hashed=%(hashed)d  |  confirmed=%(confirmed)d  "
                         "observed=%(observed)d  UNKNOWN=%(unknown)d" % FRAME_TREE_META)
        if UNKNOWN_HASHES:
            PyImGui.text_colored(0.95, 0.45, 0.45, 1.0,
                                 "%d hashed frames have no name" % len(UNKNOWN_HASHES))
        PyImGui.separator()

        if FRAME_TREE:
            seen: set[int] = set()
            for r in FRAME_ROOTS:
                draw_node(r, seen)
        else:
            PyImGui.text("No tree captured.")

    PyImGui.end()


if __name__ == "__main__":
    main()
