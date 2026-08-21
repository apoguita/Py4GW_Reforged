"""Frame - the sole provider of Guild Wars native UI frames.

Nothing outside this module constructs a `PyUIManager.UIFrame` or calls a
frame-scoped `PyUIManager.UIManager` binding.  Callers name a registry entry and
ask the handle for a service:

    from Py4GWCoreLib.FrameTree import Frame, FrameId

    f = Frame(FrameId.SalvageWindow.Options.Option1)
    if f.is_usable:
        f.click()

Two layers:

  FrameTree  owns the live tree - structure snapshot, per-frame state cache, and
             the tree-wide bindings (enumeration, identity lookup).
  Frame      owns one frame - state, identity, text, geometry, interaction,
             navigation.  Every frame-scoped binding lives here.

Resolution is registry key -> anchor frame name -> hash -> anchor frame id ->
walk the relative child codes.

Reads are served from a live copy, not from the game.  A frame is read at most
once per tick no matter how many properties are touched; every later read that
tick is a dict hit.  See docs/ui/frame-tree/frame-tree-design.md sections 8-10.

Two kinds of member, and they fail differently:

  reads (name, hash, code, label, title, layer, opacity, geometry, text, raw,
  is_usable, exists, matches, describe)   ->  always answer.  An id that has
  gone stale yields an empty/zero result, exactly as constructing a UIFrame on
  a dead id used to.  This matters because a frame inspector renders dozens of
  properties per frame, and one raise inside an ImGui begin/end pair aborts the
  whole frame ("missing end_tab_bar").

  addressing and navigation (frame_id, parent, child, is_ancestor_of)  ->  raise
  FrameNotFound, because handing back a bogus id would corrupt whatever the
  caller does next.

Writes and interactions gate on `is_usable`, so they no-op on a dead frame
rather than firing input at nothing.
"""

import re
from typing import Any, Iterator, Optional

import PyOverlay  # type: ignore
import PyUIManager  # type: ignore

from .frame_aliases import FRAME_ALIASES
from .frame_ids import FrameId
from .frame_names import FRAME_NAMES, NAME_TO_HASH
from .frame_registry import DYNAMIC_KEYS, REGISTRY

__all__ = [
    "Frame",
    "FrameError",
    "FrameKeyError",
    "FrameNotFound",
    "FrameState",
    "FrameTree",
    "RELATION_FIRST_CHILD",
    "RELATION_LAST_CHILD",
    "RELATION_NEXT_SIBLING",
    "RELATION_PREV_SIBLING",
    "resolve_key",
]

_MOUSE_HOVER_STATE = 9

# native relation_kind values for get_related_frame_id
RELATION_FIRST_CHILD = 0
RELATION_LAST_CHILD = 1
RELATION_NEXT_SIBLING = 2
RELATION_PREV_SIBLING = 3


# --------------------------------------------------------------------------
class FrameError(Exception):
    """Base for every FrameTree failure."""


class FrameKeyError(FrameError):
    """The registry key does not exist, or names a per-session dynamic entry."""


class FrameNotFound(FrameError):
    """The key is valid but no live frame matches it."""


# --------------------------------------------------------------------------
def resolve_key(key: str) -> tuple[str, tuple[int, ...]]:
    """Registry key -> (anchor frame name, relative child codes)."""
    parts = key.split(".")
    entry = REGISTRY.get(parts[0])
    if entry is None:
        raise FrameKeyError("unknown registry key %r (no top-level %r)" % (key, parts[0]))

    if isinstance(entry, str):
        anchor, kids = entry, {}
    else:
        anchor, kids = entry[0], (entry[1] if len(entry) > 1 else {})

    tail: list[int] = []
    for i, seg in enumerate(parts[1:], 1):
        if seg not in kids:
            raise FrameKeyError(
                "unknown registry key %r: %r has no child %r"
                % (key, ".".join(parts[:i]), seg)
            )
        node = kids[seg]
        if isinstance(node, int):
            tail.append(node)
            kids = {}
        else:
            tail.append(node[0])
            kids = node[1]
    return anchor, tuple(tail)


# --------------------------------------------------------------------------
# Reverse identity tables.  A live frame knows only its hash and child codes, so
# to name an arbitrary frame we invert the registry and the alias map onto the
# same "<anchor_hash>,<code>,<code>" form that Frame.path() produces.  Both are
# built once, on first use.
_alias_by_path: Optional[dict[str, str]] = None
_key_by_path: Optional[dict[str, str]] = None


def _path_of(anchor_name: str, codes) -> Optional[str]:
    h = NAME_TO_HASH.get(anchor_name)
    if h is None:
        return None
    return ",".join([str(h)] + [str(c) for c in codes])


def alias_by_path() -> dict[str, str]:
    """"<hash>,<codes>" -> prose alias, inverted from FRAME_ALIASES."""
    global _alias_by_path
    if _alias_by_path is None:
        out: dict[str, str] = {}
        for key, label in FRAME_ALIASES.items():
            parts = key.split(",")
            p = _path_of(parts[0], parts[1:])
            if p is not None:
                out.setdefault(p, label)
        _alias_by_path = out
    return _alias_by_path


def key_by_path() -> dict[str, str]:
    """"<hash>,<codes>" -> dotted registry key, inverted from REGISTRY."""
    global _key_by_path
    if _key_by_path is None:
        out: dict[str, str] = {}

        def walk(prefix: str, anchor: str, tail: list, kids: dict) -> None:
            p = _path_of(anchor, tail)
            if p is not None:
                out.setdefault(p, prefix)
            for name, node in (kids or {}).items():
                if isinstance(node, int):
                    walk(prefix + "." + name, anchor, tail + [node], {})
                else:
                    walk(prefix + "." + name, anchor, tail + [node[0]],
                         node[1] if len(node) > 1 else {})

        for top, entry in REGISTRY.items():
            if isinstance(entry, str):
                walk(top, entry, [], {})
            else:
                walk(top, entry[0], [], entry[1] if len(entry) > 1 else {})
        _key_by_path = out
    return _key_by_path


# --------------------------------------------------------------------------
def _position_unusable(p: Any) -> bool:
    """True for the zeroed position struct the engine leaves on a missed lookup.

    A real frame always has a positive viewport scale; a zero scale, or a
    rectangle collapsed onto the origin, means the read did not land.
    """
    if p is None:
        return True
    try:
        if float(getattr(p, "viewport_scale_x", 0.0)) <= 0.0:
            return True
        if float(getattr(p, "viewport_scale_y", 0.0)) <= 0.0:
            return True
        return not any((
            float(getattr(p, "left_on_screen", 0.0)),
            float(getattr(p, "top_on_screen", 0.0)),
            float(getattr(p, "right_on_screen", 0.0)),
            float(getattr(p, "bottom_on_screen", 0.0)),
        ))
    except Exception:
        return True


# --------------------------------------------------------------------------
class FrameState:
    """One live read of a frame, valid only for the tick that produced it.

    Constructing this is the *only* place a PyUIManager.UIFrame comes into
    existence.  `is_created` / `is_visible` come from that single read; the
    position object is fetched on first use because most frames never need it.
    """

    __slots__ = ("frame_id", "frame", "is_created", "is_visible", "tick",
                 "_position", "_previous", "_landed", "served")

    def __init__(self, frame_id: int, tick: int = 0, previous: Any = None) -> None:
        self._previous = previous
        self._landed: Optional[bool] = None
        self.served = 0        # ticks this copy has stood in for a failed read
        self.frame_id = frame_id
        self.tick = tick
        try:
            self.frame = PyUIManager.UIFrame(frame_id)
        except Exception:
            self.frame = None
        f = self.frame
        self.is_created = bool(getattr(f, "is_created", False)) if f is not None else False
        self.is_visible = bool(getattr(f, "is_visible", False)) if f is not None else False
        self._position: Any = None

    @property
    def landed(self) -> bool:
        """Did this read produce usable data?

        The engine fills the whole frame struct in one pass, so when its lookup
        misses, everything zeroes together - state, geometry, viewport.  There is
        therefore one verdict for the whole snapshot rather than a test per
        field: either the read landed, or the copy is worthless and the previous
        one should be served instead.
        """
        if self._landed is None:
            if self.frame is None or not (self.is_created or self.is_visible):
                self._landed = False
            else:
                self._landed = not _position_unusable(
                    getattr(self.frame, "position", None))
        return self._landed

    @property
    def blank(self) -> bool:
        return not self.landed

    @property
    def position(self) -> Any:
        """Geometry for this frame, holding the last good read.

        Frame geometry barely changes tick to tick, so an unusable read is far
        more likely to be a missed lookup than a real move.  Rather than hand
        back zeros - which collapse every projection onto the origin - reuse the
        previous copy until a usable one arrives.
        """
        if self._position is None:
            fresh = self.frame.position if self.frame is not None else None
            if _position_unusable(fresh) and self._previous is not None:
                inherited = self._previous.position
                if not _position_unusable(inherited):
                    self._position = inherited
                    self._previous = None      # value carried; drop the chain
                    return inherited
            self._position = fresh
            self._previous = None
        return self._position


# --------------------------------------------------------------------------
class _FrameTree:
    """The live tree.  Owns the structure snapshot and the per-frame state cache.

    Refresh is lazy per tick, not an eager sweep: the PreUpdate callback only
    bumps a counter.  The structure snapshot is rebuilt on the first resolution
    of a tick, and per-frame state is read on first touch of that frame.  A tick
    in which no frame is touched costs nothing.
    """

    _CALLBACK = "FrameTree.Tick"
    BUFFER_TICKS = 5      # passes a good copy may stand in for a failed read.
                          # Counted in polls, not time: the system reads every
                          # frame, so this is at most 5 frames behind, whatever
                          # the framerate.

    def __init__(self) -> None:
        self.version = 0          # bumps on every structure rebuild
        self.tick = 0             # bumps every PreUpdate
        self._built_tick = -1
        self._parent: dict[int, int] = {}
        self._code: dict[int, int] = {}
        self._hash: dict[int, int] = {}
        self._children: dict[int, dict[int, list[int]]] = {}
        self._order: list[int] = []
        self._by_hash: dict[int, list[int]] = {}
        self._state: dict[int, FrameState] = {}
        self._registered = False
        self.stale = False   # last rebuild came back empty; showing the previous tree
        self._root_id = 0    # last good UI root id
        self._viewport_height = 0.0
        self._overlay: Any = None

    # -- lifecycle --------------------------------------------------------
    def enable(self) -> None:
        if self._registered:
            return
        import PyCallback  # type: ignore

        PyCallback.PyCallback.Register(
            self._CALLBACK, PyCallback.Phase.PreUpdate, self._on_tick, priority=6
        )
        self._registered = True

    def disable(self) -> None:
        if not self._registered:
            return
        import PyCallback  # type: ignore

        PyCallback.PyCallback.RemoveByName(self._CALLBACK)
        self._registered = False

    def _on_tick(self) -> None:
        """Invalidate.  Deliberately does no work beyond the counter."""
        self.tick += 1

    # -- structure snapshot -----------------------------------------------
    def rebuild(self) -> None:
        parent: dict[int, int] = {}
        code: dict[int, int] = {}
        fhash: dict[int, int] = {}
        children: dict[int, dict[int, list[int]]] = {}
        order: list[int] = []
        by_hash: dict[int, list[int]] = {}

        for raw in PyUIManager.UIManager.get_frame_array():
            fid = int(raw)
            order.append(fid)
            try:
                fr = PyUIManager.UIFrame(fid)
            except Exception:
                continue
            pid = int(getattr(fr, "parent_id", 0) or 0)
            cod = int(getattr(fr, "child_offset_id", 0) or 0)
            h = int(getattr(fr, "frame_hash", 0) or 0)
            parent[fid] = pid
            code[fid] = cod
            fhash[fid] = h
            # a code is normally unique per parent, but siblings can collide -
            # keep every one so enumeration does not silently lose frames
            children.setdefault(pid, {}).setdefault(cod, []).append(fid)
            if h:
                by_hash.setdefault(h, []).append(fid)

        # The engine returns an EMPTY array whenever its frame array pointer is
        # null - during map load, UI teardown, or before the UI context exists.
        # That is not "the UI is gone", it is "we cannot see it this tick".
        # Swapping an empty snapshot in makes every handle stop resolving for a
        # frame or two, which is what made overlays flicker.  Keep the last good
        # tree instead and try again next tick.
        self._built_tick = self.tick
        if not order and self._order:
            self.stale = True
            return

        self.stale = False
        self._parent, self._code, self._hash = parent, code, fhash
        self._children, self._order, self._by_hash = children, order, by_hash
        self.version += 1

    def ensure(self) -> None:
        self.enable()
        if self._built_tick != self.tick:
            self.rebuild()

    # -- per-frame live copy ----------------------------------------------
    def state(self, frame_id: int) -> FrameState:
        """The live copy of one frame for this tick, read at most once.

        Entries are overwritten in place rather than cleared each tick.  A frame
        that is still in the tree but reads back blank - GetContext bailing on a
        transient null - keeps its previous copy, so a caller reading geometry
        never sees a one-frame hole.  A frame that has genuinely left the tree
        gets the blank read, because then it really is gone.
        """
        previous = self._state.get(frame_id)
        if previous is not None and previous.tick == self.tick:
            return previous

        fresh = FrameState(frame_id, self.tick, previous)
        if (not fresh.landed and previous is not None and previous.landed
                and previous.served < self.BUFFER_TICKS):
            # The read did not land but we have a good copy from a moment ago.
            # Geometry barely moves between ticks, so redrawing from the buffer
            # is far closer to the truth than a zeroed struct - and one bad tick
            # is enough to blank an overlay or flip it into a fallback mode.
            # Bounded, so a frame that stops reporting eventually tells the truth.
            previous.served += 1
            previous.tick = self.tick
            return previous

        self._state[frame_id] = fresh
        if len(self._state) > 4096:
            self._prune()
        return fresh

    def _prune(self) -> None:
        """Drop copies nothing has touched for a while."""
        cutoff = self.tick - 240
        for fid in [f for f, st in self._state.items() if st.tick < cutoff]:
            del self._state[fid]

    def invalidate(self, frame_id: Optional[int] = None) -> None:
        """Drop cached live copies so the next read hits the game again.

        Only needed when something is expected to change *within* a tick; the
        tick boundary invalidates everything on its own.
        """
        if frame_id is None:
            self._state.clear()
        else:
            self._state.pop(int(frame_id), None)

    # -- structure queries ------------------------------------------------
    def anchor_ids(self, anchor) -> list[int]:
        if isinstance(anchor, int):
            h = anchor
            label = ""
        else:
            label = str(anchor)
            h = NAME_TO_HASH.get(label)
            if h is None:
                raise FrameKeyError("no known frame named %r" % label)

        found = self._by_hash.get(h)
        if found:
            return found

        # A name-table hash comes from offline RE and can lag the client.  When
        # resolving a registry anchor, the client can hash the literal label
        # itself; prefer that authoritative fallback before treating the frame
        # as absent.  Dynamic callers that supply a raw hash still use the
        # hash lookup below.
        if label:
            try:
                fid = int(PyUIManager.UIManager.get_frame_id_by_label(label) or 0)
            except Exception:
                fid = 0
            if fid:
                return [fid]

        # The snapshot has not seen this hash - it may be a tick behind, or the
        # sweep may have missed it.  Ask the engine directly, the way the legacy
        # code always did, rather than reporting the frame as gone.
        try:
            fid = int(PyUIManager.UIManager.get_frame_id_by_hash(h) or 0)
        except Exception:
            fid = 0
        return [fid] if fid else []

    def child_of(self, frame_id: int, code: int) -> Optional[int]:
        got = self._children.get(frame_id, {}).get(code)
        return got[0] if got else None

    def children_at(self, frame_id: int, code: int) -> list[int]:
        """Every child under `code` - normally one, occasionally colliding siblings."""
        return list(self._children.get(frame_id, {}).get(code, ()))

    def children_of(self, frame_id: int) -> list[int]:
        out: list[int] = []
        for ids in self._children.get(frame_id, {}).values():
            out.extend(ids)
        return sorted(out)

    def child_codes_of(self, frame_id: int) -> list[int]:
        return sorted(self._children.get(frame_id, {}).keys())

    def parent_of(self, frame_id: int) -> int:
        return self._parent.get(frame_id, 0)

    def hash_of(self, frame_id: int) -> int:
        return self._hash.get(frame_id, 0)

    def code_of(self, frame_id: int) -> int:
        return self._code.get(frame_id, 0)

    def known(self, frame_id: int) -> bool:
        return frame_id in self._parent

    def live(self, frame_id: int) -> bool:
        """Ask the engine directly whether this frame is real.

        The structure snapshot is at best a tick old, and an id handed to us by
        another subsystem - a native context, say - can be valid before we have
        ever seen it in a frame-array sweep.  Treating "not in my snapshot" as
        "does not exist" is what made geometry collapse to the origin for a
        frame at a time; the legacy code asked the engine every call and never
        had that failure.  This is that check, served from the per-tick copy.
        """
        if not frame_id:
            return False
        # a RAW read - never the retained copy, or existence would feed on the
        # very cache it is meant to validate and a removed frame would never die
        try:
            f = PyUIManager.UIFrame(int(frame_id))
        except Exception:
            return False
        return bool(getattr(f, "is_created", False) or getattr(f, "is_visible", False))

    # -- tree-wide bindings (tier 2) --------------------------------------
    def all_ids(self) -> list[int]:
        """Every live frame id, in native frame-array order."""
        self.ensure()
        return list(self._order)

    def all_frames(self) -> list["Frame"]:
        return [Frame.from_id(f) for f in self.all_ids()]

    def children_map(self) -> dict[int, list[int]]:
        """parent id -> child ids, children in native frame-array order."""
        self.ensure()
        out: dict[int, list[int]] = {}
        for fid in self._order:
            out.setdefault(self._parent.get(fid, 0), []).append(fid)
        return out

    @staticmethod
    def _as_id(frame_or_id: Any) -> int:
        """Accept a Frame or a raw id, so callers never have to unwrap."""
        if isinstance(frame_or_id, Frame):
            return frame_or_id._target_id()
        return int(frame_or_id or 0)

    def descendants(self, frame: Any) -> list["Frame"]:
        """Breadth-first descendant handles."""
        return [Frame.from_id(i) for i in self.descendants_of(frame)]

    def descendants_of(self, frame_id: Any) -> list[int]:
        """Breadth-first descendants, native order within each level."""
        from collections import deque

        frame_id = self._as_id(frame_id)
        kids = self.children_map()
        out: list[int] = []
        queue = deque([frame_id])
        while queue:
            cur = queue.popleft()
            for c in kids.get(cur, []):
                out.append(c)
                queue.append(c)
        return out

    def root(self) -> "Frame":
        """The UI root.  Cached: it never changes, and a transient 0 from the
        engine would otherwise zero out every viewport-relative calculation."""
        fid = int(PyUIManager.UIManager.get_root_frame_id() or 0)
        if fid:
            self._root_id = fid
        return Frame.from_id(fid or self._root_id)

    def viewport_height(self) -> float:
        """Screen height of the UI root, held across transient misses."""
        _, height = self.root().viewport_dimensions()
        if height:
            self._viewport_height = height
        return self._viewport_height

    def hierarchy(self) -> list[tuple[int, int, int, int]]:
        """Native flat hierarchy dump: (frame_id, parent_id, code, hash) rows."""
        return PyUIManager.UIManager.get_frame_hierarchy()

    def overlay_frames(self) -> list["Frame"]:
        return [Frame.from_id(int(i)) for i in PyUIManager.UIManager.get_overlay_frame_ids()]

    def popup_frames(self) -> list["Frame"]:
        return [Frame.from_id(int(i)) for i in PyUIManager.UIManager.get_popup_frame_ids()]

    def by_hash(self, frame_hash: int) -> "Frame":
        """Handle on the frame carrying `frame_hash` (native lookup)."""
        return Frame.from_id(int(PyUIManager.UIManager.get_frame_id_by_hash(frame_hash) or 0))

    def by_label(self, label: str) -> "Frame":
        """Handle on the frame at a legacy alias label (native lookup)."""
        return Frame.from_id(int(PyUIManager.UIManager.get_frame_id_by_label(label) or 0))

    def hash_for_label(self, label: str) -> int:
        return int(PyUIManager.UIManager.get_hash_by_label(label) or 0)

    def coords_for_hash(self, frame_hash: int) -> list[tuple[int, int]]:
        return PyUIManager.UIManager.get_frame_coords_by_hash(frame_hash)

    def child_by_parent_hash(self, parent_hash: int, child_offsets: list[int]) -> "Frame":
        return Frame.from_id(
            int(PyUIManager.UIManager.get_child_frame_id(parent_hash, child_offsets) or 0)
        )

    def frames_at_path(self, anchor: Any, codes: list[int]) -> list["Frame"]:
        """Every frame whose code path from `anchor` is exactly `codes`.

        `Frame(key)` stops at the first match; this returns all of them, which is
        what dialog option enumeration needs.  Served from the snapshot, so it
        costs a dict walk per frame rather than a UIFrame construction.
        """
        self.ensure()
        return self._frames_at(set(self.anchor_ids(anchor)), codes)

    def frames_under(self, anchor_frame_id: Any, codes: list[int]) -> list["Frame"]:
        """`frames_at_path` anchored on one known frame instead of a hash."""
        self.ensure()
        anchor_frame_id = self._as_id(anchor_frame_id)
        if not anchor_frame_id:
            return []
        return self._frames_at({int(anchor_frame_id)}, codes)

    def _frames_at(self, anchor_ids: set, codes: list[int]) -> list["Frame"]:
        if not anchor_ids:
            return []
        depth = len(codes)
        out: list[int] = []
        for fid in self._order:
            trace = fid
            walked: list[int] = []
            for _ in range(depth):
                walked.insert(0, self.code_of(trace))
                pid = self.parent_of(trace)
                if not pid:
                    break
                trace = pid
            if trace in anchor_ids and walked == list(codes):
                out.append(fid)
        return [Frame.from_id(f) for f in out]

    def sort_by_vertical(self, frames: list["Frame"]) -> list["Frame"]:
        """Top of screen first."""
        return sorted(frames, key=lambda f: f.rect[1])

    def color_frames(self, anchor: Any, codes: list[int], debug: bool = False) -> None:
        """Tint every frame at a code path a distinct colour - a debug aid."""
        def rgb(r, g, b, a) -> int:
            return (a << 24) | (b << 16) | (g << 8) | r

        colors = [
            rgb(0, 255, 0, 200),      # green
            rgb(255, 0, 0, 200),      # red
            rgb(0, 128, 255, 200),    # blue
            rgb(255, 255, 0, 200),    # yellow
            rgb(128, 0, 255, 200),    # purple
            rgb(255, 128, 0, 200),    # orange
            rgb(0, 255, 255, 200),    # cyan
        ]
        ordered = self.sort_by_vertical(self.frames_at_path(anchor, codes))
        if debug:
            from ..Py4GWcorelib import Console, ConsoleLog

            for f in ordered:
                ConsoleLog(
                    "FrameTree",
                    "frame %d top %d" % (f.frame_id, f.rect[1]),
                    Console.MessageType.Debug,
                )
        for i, f in enumerate(ordered):
            if i >= len(colors):
                break
            f.draw(colors[i])

    # -- shared overlay for frame drawing ---------------------------------
    @property
    def overlay(self) -> Any:
        if self._overlay is None:
            self._overlay = PyOverlay.Overlay()
        return self._overlay


FrameTree = _FrameTree()


# --------------------------------------------------------------------------
class Frame:
    """A handle on one native frame.  Owns every frame-scoped binding."""

    __slots__ = ("_key", "_anchor", "_tail", "_fid", "_version", "_blackboard")

    def __init__(self, key: Any, _frame_id: Optional[int] = None) -> None:
        if _frame_id is not None:          # internal: wrap a known frame id
            self._key = ""
            self._anchor: Any = ""
            self._tail: tuple[int, ...] = ()
            self._fid: Optional[int] = _frame_id
            self._version = -1
            self._blackboard: dict = {}
            return

        key = getattr(key, "KEY", key)
        if not isinstance(key, str):
            raise FrameKeyError("frame key must be a string or a FrameId node, got %r" % (key,))
        if key in DYNAMIC_KEYS:
            raise FrameKeyError(
                "%r has per-session runtime codes and cannot be resolved from the "
                "registry; locate it by walking the live tree instead" % key
            )
        self._key = key
        self._anchor, self._tail = resolve_key(key)
        self._fid = None
        self._version = -1
        self._blackboard = {}

    @classmethod
    def from_id(cls, frame_id: int) -> "Frame":
        """Wrap a frame id we already have."""
        return cls(None, _frame_id=int(frame_id))

    @classmethod
    def from_hash(cls, frame_hash: int, codes=(),
                  blackboard: Optional[dict] = None) -> "Frame":
        """Deferred handle for a runtime-computed path: anchor hash + child codes.

        Use only where the path is not knowable statically (per-bag / per-slot
        item frames).  Everything with a fixed path belongs in the registry.
        """
        f = cls.__new__(cls)
        f._key = ""
        f._anchor = int(frame_hash)
        f._tail = tuple(int(c) for c in codes)
        f._fid = None
        f._version = -1
        f._blackboard = dict(blackboard) if blackboard else {}
        return f

    @classmethod
    def from_label(cls, label: str) -> "Frame":
        """Resolve one of the legacy prose alias labels ("Xunlai Window").

        Kept for callers that select a frame by a runtime label string.  New
        code should use a FrameId constant.
        """
        for path, lab in FRAME_ALIASES.items():
            if lab == label:
                parts = path.split(",")
                h = NAME_TO_HASH.get(parts[0])
                if h is None:
                    break
                return cls.from_hash(h, [int(c) for c in parts[1:]])
        raise FrameKeyError("no frame alias labelled %r" % label)

    # -- named indexed addressing -----------------------------------------
    # The engine addresses a child by (parent, key_code).  Where those codes are
    # computed from game data - a bag number, a slot, a skill id - the
    # arithmetic belongs here, not in a script.  Each accessor takes DOMAIN
    # arguments and resolves a registered parent, so no caller ever names a code.
    @classmethod
    def _under(cls, parent_key: Any, *codes: int) -> "Frame":
        """A registered parent plus computed child codes.  Package-internal."""
        parent = cls(parent_key)
        anchor, tail = parent._anchor, parent._tail
        f = cls.__new__(cls)
        f._key = ""
        f._anchor = anchor
        f._tail = tuple(tail) + tuple(int(c) for c in codes)
        f._fid = None
        f._version = -1
        f._blackboard = {}
        return f

    @classmethod
    def skill(cls, index: int) -> "Frame":
        """Player skillbar slot, 1-based."""
        return cls("Skillbar.Skill%d" % int(index))

    @classmethod
    def hero_skill(cls, hero: int, index: int) -> "Frame":
        """Hero skillbar slot; hero and index both 1-based."""
        return cls("Hero%dWindow.SkillBar.Skill%d" % (int(hero), int(index)))

    @classmethod
    def bag_slot(cls, bag: Any, slot: int) -> "Frame":
        """Slot in the aggregate inventory bags panel.

        `bag` is a Bags enum (or its value) and `slot` is 0-based, matching how
        the game numbers them - the engine's own codes are `bag - Backpack` and
        `slot + 2`, and that arithmetic stays here.
        """
        return cls._under(FrameId.InventoryBagsWindow.Content.C0.C0,
                          cls._bag_offset(bag), 2 + int(slot))

    @staticmethod
    def _bag_offset(bag: Any) -> int:
        """Bag -> its child code.  Accepts a Bags enum or a raw bag value."""
        from ..enums_src.Item_enums import Bags

        value = getattr(bag, "value", bag)
        return int(value) - int(Bags.Backpack.value)

    @classmethod
    def inventory_bag(cls, bag: Any) -> "Frame":
        """The standalone window for one bag (not the aggregate bags panel)."""
        return cls._under(FrameId.InventoryWindow, cls._bag_offset(bag))

    @classmethod
    def inventory_bag_slot(cls, bag: Any, slot: int) -> "Frame":
        """Slot inside a standalone bag window; `slot` is 0-based."""
        return cls._under(FrameId.InventoryWindow,
                          cls._bag_offset(bag), 2 + int(slot))

    @classmethod
    def storage_tab(cls, bag: Any, reversed_order: bool = False) -> "Frame":
        """Xunlai storage tab for `bag`.

        `reversed_order` selects the engine's descending tab codes, which the
        tab strip uses while the content panes count up.
        """
        offset = cls._bag_offset(bag)
        code = (0xFFFFFFFF - offset) if reversed_order else offset
        return cls._under(FrameId.XunlaiWindow.StorageFrame, code)

    @classmethod
    def storage_slot(cls, bag: Any, slot: int) -> "Frame":
        """Xunlai storage slot; `slot` is 0-based."""
        return cls._under(FrameId.XunlaiWindow.StorageFrame,
                          cls._bag_offset(bag), 2 + int(slot))

    @classmethod
    def material_slot(cls, slot: int, max_tabs: int = 5, raw_slot: bool = False) -> "Frame":
        """Material storage slot; it sits one tab past the last storage tab."""
        code = int(slot) if raw_slot else 2 + int(slot)
        return cls._under(FrameId.XunlaiWindow.StorageFrame, int(max_tabs), code)

    @classmethod
    def party_list(cls) -> "Frame":
        """The container holding party entries, for whichever map type we are in."""
        from ..Map import Map

        return cls(
            FrameId.PartyFormation.Outpost.Members.Frame.C0.C0.Parent
            if Map.IsOutpost() else
            FrameId.PartyFormation.Explorable.C0.C0.MembersParentExplorable
        )

    @classmethod
    def party_member(cls, index: int) -> "Frame":
        """Party list entry, 1-based.

        The party window is laid out differently in an outpost than in an
        explorable area.  Deciding which is the class's job - a caller asking
        for "party member 3" should not have to know the map type.
        """
        from ..Map import Map

        parent = (
            FrameId.PartyFormation.Outpost.Members.Frame.C0.C0.Parent  # codes [1,8,0,0,0,0]
            if Map.IsOutpost() else
            FrameId.PartyFormation.Explorable.C0.C0.MembersParentExplorable  # codes [0,0,0,0]
        )
        # each entry sits at <parent>,<slot>,0
        return cls._under(parent, int(index) - 1, 0)

    @classmethod
    def effect(cls, skill_id: int) -> "Frame":
        """Effect icon in the effects monitor, addressed by skill id.

        Effect children are keyed by skill id at runtime, so they can never be
        enumerated in the registry - the mapping lives here instead.
        """
        return cls._under(FrameId.EffectsMonitor, int(skill_id) + 4)

    @classmethod
    def skill_tome(cls) -> "Frame":
        """Root frame of the native Skill Tome window."""
        return cls(FrameId.SkillTome)

    @classmethod
    def skill_tome_skill(cls, skill_id: int) -> Optional["Frame"]:
        """Usable Skill Tome row for ``skill_id``.

        Tome rows are keyed by skill id but sit below a runtime list/group code,
        so their complete child-code path is not static. Keep that structural
        lookup here rather than leaking FrameTree traversal into routines.
        """
        wanted = int(skill_id)
        root = cls.skill_tome()
        if not root.exists:
            return None

        try:
            for frame in FrameTree.descendants(root):
                try:
                    if int(frame.code) == wanted and frame.is_usable:
                        return frame
                except Exception:
                    continue
        except Exception:
            return None
        return None

    @classmethod
    def skill_tome_selection_marker(cls, skill_id: int) -> Optional["Frame"]:
        """Visible selection marker below the Skill Tome row for ``skill_id``.

        The marker's native child code is intentionally owned by Frame so
        callers only ask whether a tome skill is selected.
        """
        row = cls.skill_tome_skill(skill_id)
        if row is None:
            return None

        try:
            for frame in FrameTree.descendants(row):
                try:
                    if int(frame.code) == 14 and frame.is_visible and frame.is_usable:
                        return frame
                except Exception:
                    continue
        except Exception:
            return None
        return None

    @classmethod
    def skill_tome_learn_button(cls) -> "Frame":
        """Learn button in the native Skill Tome window."""
        return cls._under(FrameId.SkillTome, 0)

    @classmethod
    def trainer_skill(cls, skill_id: int) -> "Frame":
        """Skill entry in the skill-trainer list, keyed by skill id."""
        return cls._under(FrameId.SkillTrainerWindow, 0, 0, 0, 5, 1, int(skill_id), 0)

    @classmethod
    def capture_skill(cls, attribute: int, skill_id: int) -> "Frame":
        """Skill entry in the elite-capture dialog, keyed by attribute + skill id."""
        return cls._under(FrameId.SkillCaptureDialog, 3, 0, 0, 0,
                          int(attribute), 1, int(skill_id), 0)

    @classmethod
    def dialog_option(cls, index: int) -> "Frame":
        """NPC dialog option, 1-based."""
        return cls("Option%d" % int(index))

    # -- resolution -------------------------------------------------------
    def _resolve(self) -> Optional[int]:
        FrameTree.ensure()
        if self._version == FrameTree.version:
            return self._fid
        self._version = FrameTree.version

        if not self._key and not self._anchor:             # wrapped id
            fid = self._fid or 0
            # snapshot first (cheap), then the engine, so an id we have not
            # swept yet is not mistaken for a dead one
            self._fid = fid if fid and (FrameTree.known(fid) or FrameTree.live(fid)) else None
            return self._fid

        fid = None
        for anchor_id in FrameTree.anchor_ids(self._anchor):
            cur: Optional[int] = anchor_id
            for code in self._tail:
                cur = FrameTree.child_of(cur, code) if cur is not None else None
                if cur is None:
                    break
            if cur is not None:
                fid = cur
                break
        self._fid = fid
        return fid

    @property
    def exists(self) -> bool:
        """The frame is present in the live tree."""
        try:
            return self._resolve() is not None
        except FrameError:
            return False

    @property
    def frame_id(self) -> int:
        fid = self._resolve()
        if fid is None:
            raise FrameNotFound(
                "%r did not resolve (anchor %r + codes %s)"
                % (self._key or "<frame id>", self._anchor, list(self._tail))
            )
        return fid

    def _target_id(self) -> int:
        """The id to read, without demanding that it resolve.

        `frame_id` is the strict accessor and raises; reads that only *describe*
        a frame must not, because a frame inspector walks ids that go stale
        mid-frame.  An unresolved id yields a zeroed snapshot here, exactly as
        constructing a UIFrame on a dead id used to.
        """
        fid = self._resolve()
        if fid is not None:
            return fid
        return self._fid or 0

    def _state(self) -> FrameState:
        return FrameTree.state(self._target_id())

    @property
    def blackboard(self) -> dict:
        """Per-handle scratch space for caller context.

        Lives on this handle object, not on the frame, so it only persists
        while the caller keeps the handle (InventoryPlus stores a handle per
        item slot and hangs the item data here).
        """
        return self._blackboard

    def refresh(self) -> None:
        """Re-read this frame from the game now, mid-tick."""
        FrameTree.invalidate(self._target_id())

    # -- identity ---------------------------------------------------------
    @property
    def key(self) -> str:
        return self._key

    @property
    def hash(self) -> int:
        """Name hash, or 0 when the frame is unnamed or gone."""
        return FrameTree.hash_of(self._target_id())

    @property
    def name(self) -> str:
        """Engine frame name, when the hash is one we can name."""
        return FRAME_NAMES.get(self.hash, "")

    @property
    def code(self) -> int:
        """Child key code under its parent, or 0 when the frame is gone."""
        return FrameTree.code_of(self._target_id())

    @property
    def label(self) -> str:
        """Native frame label; empty when the frame is gone."""
        try:
            return str(
                PyUIManager.UIManager.get_frame_label_by_frame_id(self._target_id()) or ""
            )
        except Exception:
            return ""

    @property
    def alias(self) -> str:
        """Prose alias for this frame, from the migrated alias table."""
        if not self.exists:
            return ""
        return alias_by_path().get(self.path(), "")

    @property
    def registry_key(self) -> str:
        """Dotted registry key that addresses this frame, if it has one.

        `key` is what this handle was built from; this is what the live frame
        turns out to be - the two differ when the handle came from a raw id.
        """
        if self._key:
            return self._key
        if not self.exists:
            return ""
        return key_by_path().get(self.path(), "")

    def describe(self) -> str:
        """Best available identity for display: engine name, key, then alias.

        This is what a frame inspector should show.  Nothing here reads a file -
        it is all resolved from the migrated name / registry / alias tables.
        """
        parts: list[str] = []
        name = self.name
        if name:
            parts.append(name)
        key = self.registry_key
        if key and key != name:
            parts.append(key)
        alias = self.alias
        if alias and alias not in parts:
            parts.append("(%s)" % alias)
        return "  ".join(parts)

    @property
    def widget_id(self) -> str:
        """A stable, unique token for this frame, for ImGui widget suffixes.

        Scripts used the raw frame id to keep `##` suffixes unique.  This is a
        string label instead: unique per frame and stable within a session, but
        not something that can be passed back in to address a frame.
        """
        return "fr%x" % (self._target_id() & 0xFFFFFFFF)

    def matches(self, *names: str) -> bool:
        """The frame resolved and its engine name is one of `names`.

        This is the identity check for paths that host different frames
        depending on context - the Merchant / Crafter / Trader buttons all sit
        at the same path and are told apart only by name.
        """
        if not self.exists:
            return False
        return self.name in names

    @property
    def is_anonymous(self) -> bool:
        """Resolved, but the frame carries no name hash."""
        return self.exists and self.hash == 0

    def path(self) -> str:
        """"hash" if the frame is named, else "ancestor_hash,code,code,..."."""
        if not self.exists:
            return ""
        fid = self.frame_id
        own = FrameTree.hash_of(fid)
        if own:
            return str(own)
        codes: list[str] = []
        cur = fid
        anchor = 0
        while cur:
            codes.append(str(FrameTree.code_of(cur)))
            pid = FrameTree.parent_of(cur)
            if not pid:
                break
            ph = FrameTree.hash_of(pid)
            if ph:
                anchor = ph
                break
            cur = pid
        if not anchor:
            return ""
        return str(anchor) + "," + ",".join(reversed(codes))

    # -- state ------------------------------------------------------------
    @property
    def is_created(self) -> bool:
        return self.exists and self._state().is_created

    @property
    def is_visible(self) -> bool:
        return self.exists and self._state().is_visible

    @property
    def is_usable(self) -> bool:
        """Present, created and visible - safe to read or act on.

        This is the one readiness question.  Callers ask it instead of
        composing their own conjunction of exists / is_created / is_visible.
        """
        if not self.exists:
            return False
        st = self._state()
        return st.is_created and st.is_visible

    @property
    def template_type(self) -> int:
        """Widget template kind (1 == the interactive dialog button template)."""
        f = self._state().frame
        return int(getattr(f, "template_type", 0) or 0) if f is not None else 0

    @property
    def type(self) -> int:
        f = self._state().frame
        return int(getattr(f, "type", 0) or 0) if f is not None else 0

    @property
    def visibility_flags(self) -> int:
        f = self._state().frame
        return int(getattr(f, "visibility_flags", 0) or 0) if f is not None else 0

    @property
    def frame_layout(self) -> int:
        f = self._state().frame
        return int(getattr(f, "frame_layout", 0) or 0) if f is not None else 0

    def siblings(self) -> list["Frame"]:
        """Frames sharing this frame's parent, per the engine's relation block.

        Returns handles, never ids - `relation.siblings` is a raw id list and
        must not leave the class.  Its scalars are still visible via `fields()`
        under the `relation.` prefix.
        """
        f = self._state().frame
        rel = getattr(f, "relation", None) if f is not None else None
        if rel is None:
            return []
        try:
            return [Frame.from_id(int(i)) for i in (getattr(rel, "siblings", ()) or ())]
        except Exception:
            return []

    @property
    def frame_callbacks(self) -> Any:
        f = self._state().frame
        return getattr(f, "frame_callbacks", None) if f is not None else None

    @property
    def frame_state(self) -> int:
        f = self._state().frame
        return int(getattr(f, "frame_state", 0) or 0) if f is not None else 0

    def fields(self) -> dict:
        """Every scalar the engine exposes for this frame, as plain data.

        This is the inspection surface for frame testers: they get the values,
        never the underlying object, so there is still no way to address or
        act on a frame except through this class.  Named fields come first,
        then the undocumented `field*_0x..` slots ordered by struct offset.
        """
        f = self._state().frame
        if f is None:
            return {}

        def scalars(obj, prefix=""):
            named: dict = {}
            offsets: list = []
            for name in dir(obj):
                if name.startswith("_"):
                    continue
                try:
                    value = getattr(obj, name)
                except Exception:
                    continue
                if callable(value):
                    continue
                key = prefix + name
                if isinstance(value, (int, float, bool)):
                    m = re.match(r"field\w*?_0x([0-9a-fA-F]+)$", name)
                    if m:
                        offsets.append((int(m.group(1), 16), key, value))
                    else:
                        named[key] = value
                elif prefix == "" and name in ("relation", "position"):
                    # one level of nesting, so testers never need the object
                    sub_named, sub_offsets = scalars(value, name + ".")
                    named.update(sub_named)
                    offsets.extend(sub_offsets)
            return named, offsets

        named, offsets = scalars(f)
        out = dict(sorted(named.items()))
        for _, name, value in sorted(offsets):
            out[name] = value
        return out

    @property
    def parameters(self) -> list:
        """The frame's parameter list (struct slot 0x84), as plain data."""
        f = self._state().frame
        if f is None:
            return []
        try:
            return list(getattr(f, "field31_0x84", ()) or ())
        except Exception:
            return []

    @property
    def parent_id(self) -> int:
        """Parent frame id from the snapshot; 0 at the root or when gone."""
        return FrameTree.parent_of(self._target_id())

    def state_bit(self, bit: int) -> bool:
        return bool(PyUIManager.UIManager.get_frame_state_bit_by_frame_id(self._target_id(), bit))

    @property
    def user_param(self) -> int:
        return int(PyUIManager.UIManager.get_frame_user_param_by_frame_id(self._target_id()) or 0)

    @property
    def context(self) -> int:
        return int(PyUIManager.UIManager.get_frame_context(self._target_id()) or 0)

    # -- presentation -----------------------------------------------------
    def set_visible(self, visible: bool) -> bool:
        return bool(
            PyUIManager.UIManager.set_frame_visible_by_frame_id(self.frame_id, bool(visible))
        )

    def set_disabled(self, disabled: bool) -> bool:
        return bool(
            PyUIManager.UIManager.set_frame_disabled_by_frame_id(self.frame_id, bool(disabled))
        )

    def show(self, show: bool = True) -> bool:
        return bool(PyUIManager.UIManager.show_frame_by_frame_id(self.frame_id, bool(show)))

    @property
    def layer(self) -> int:
        return int(PyUIManager.UIManager.get_frame_layer_by_frame_id(self._target_id()) or 0)

    def set_layer(self, layer: int) -> bool:
        return bool(PyUIManager.UIManager.set_frame_layer_by_frame_id(self.frame_id, layer))

    @property
    def opacity(self) -> float:
        return float(PyUIManager.UIManager.get_frame_opacity_by_frame_id(self._target_id()))

    def set_opacity(self, opacity: float, fade_time: float = 0.0) -> bool:
        return bool(
            PyUIManager.UIManager.set_frame_opacity_by_frame_id(
                self.frame_id, opacity, fade_time
            )
        )

    # -- interaction ------------------------------------------------------
    # Each one refuses on an unusable frame rather than firing an action at a
    # frame that is not on screen - that check used to be the caller's job.
    def click(self) -> None:
        if not self.is_usable:
            return
        PyUIManager.UIManager.button_click(self.frame_id)

    def double_click(self) -> None:
        if not self.is_usable:
            return
        PyUIManager.UIManager.button_double_click(self.frame_id)

    def hover(self) -> None:
        self.mouse_action(_MOUSE_HOVER_STATE)

    def mouse_action(self, state: int, wparam: int = 0, lparam: int = 0) -> None:
        if not self.is_usable:
            return
        PyUIManager.UIManager.test_mouse_action(self.frame_id, state, wparam, lparam)

    def mouse_click_action(self, state: int, wparam: int = 0, lparam: int = 0) -> None:
        if not self.is_usable:
            return
        PyUIManager.UIManager.test_mouse_click_action(self.frame_id, state, wparam, lparam)

    def send_message(self, message_id: int, wparam: int = 0, lparam: int = 0) -> bool:
        return bool(
            PyUIManager.UIManager.SendFrameUIMessage(self.frame_id, message_id, wparam, lparam)
        )

    def send_message_text(self, message_id: int, text: str) -> bool:
        return bool(
            PyUIManager.UIManager.SendFrameUIMessageWString(self.frame_id, message_id, text)
        )

    # -- text -------------------------------------------------------------
    def text(self) -> str:
        try:
            return str(
                PyUIManager.UIManager.get_text_label_decoded_by_frame_id(self._target_id()) or ""
            )
        except Exception:
            return ""

    def encoded(self) -> str:
        try:
            return str(
                PyUIManager.UIManager.get_text_label_encoded_by_frame_id(self._target_id()) or ""
            )
        except Exception:
            return ""

    def set_text(self, encoded_text: str) -> None:
        """Set the frame's text.  The engine expects an *encoded* label."""
        PyUIManager.UIManager.set_text_label_by_frame_id(self.frame_id, encoded_text)

    def title(self) -> str:
        """Window title; empty when the frame is gone."""
        try:
            return str(
                PyUIManager.UIManager.get_frame_title_by_frame_id(self._target_id()) or ""
            )
        except Exception:
            return ""

    # -- geometry ---------------------------------------------------------
    @property
    def position(self) -> Any:
        """Raw FramePosition: screen rect, content rect, scale, viewport."""
        return self._state().position

    @property
    def rect(self) -> tuple[int, int, int, int]:
        """(left, top, right, bottom) on screen."""
        p = self.position
        if p is None:
            return (0, 0, 0, 0)
        return (
            int(p.left_on_screen),
            int(p.top_on_screen),
            int(p.right_on_screen),
            int(p.bottom_on_screen),
        )

    @property
    def size(self) -> tuple[int, int]:
        p = self.position
        if p is None:
            return (0, 0)
        return int(p.width_on_screen), int(p.height_on_screen)

    def coords(self) -> tuple[int, int, int, int]:
        """(left, top, right, bottom); zeros when the frame is absent."""
        if not self.exists:
            return (0, 0, 0, 0)
        return self.rect

    def content_coords(self) -> tuple[int, int, int, int]:
        """Content-area screen coords, Y flipped into screen space."""
        if not self.exists:
            return (0, 0, 0, 0)
        p = self.position
        if p is None:
            return (0, 0, 0, 0)
        scale_x, scale_y = self.viewport_scale()
        # The Y flip must use the ROOT's viewport height - that is the screen
        # height the content rectangle is measured against.  A frame's own
        # viewport_height is not the same value, and using it anchors every Y
        # coordinate at zero while leaving X correct.  The root's height is
        # cached, so a tick where the root cannot be read reuses the last good
        # one rather than collapsing the rectangle.
        height = FrameTree.viewport_height()
        if not height:
            # without a viewport height the Y flip below would invert the frame
            # onto negative screen space; better to report nothing this tick
            return (0, 0, 0, 0)
        return (
            int(p.content_left * scale_x),
            int((height - p.content_top) * scale_y),
            int(p.content_right * scale_x),
            int((height - p.content_bottom) * scale_y),
        )

    def viewport_scale(self) -> tuple[float, float]:
        """Viewport scale, never zero.

        A zeroed position struct - what the engine leaves behind when its frame
        lookup misses - would otherwise report a scale of 0, and any caller
        multiplying by it collapses every coordinate onto the origin.  There is
        no meaningful zero scale, so an unreadable one falls back to identity.
        """
        if not self.exists:
            return (1.0, 1.0)
        p = self.position
        if p is None:
            return (1.0, 1.0)
        sx = float(p.viewport_scale_x)
        sy = float(p.viewport_scale_y)
        if sx <= 0.0 or sy <= 0.0:
            return (1.0, 1.0)
        return sx, sy

    def viewport_dimensions(self) -> tuple[float, float]:
        """Viewport size for this frame.

        Deliberately NOT gated on `exists`.  This is normally asked of the UI
        root, which does not reliably appear in a frame-array sweep - gating it
        made the whole viewport read zero whenever the sweep missed it, which
        zeroed every content rectangle derived from it.  The legacy code read
        this straight off the frame with no checks at all, and never had that
        failure.
        """
        p = self._state().position
        if p is None:
            return (0.0, 0.0)
        return float(p.viewport_width), float(p.viewport_height)

    def min_size(self) -> tuple:
        return PyUIManager.UIManager.get_frame_min_size_by_frame_id(self._target_id())

    def native_size(self) -> tuple:
        return PyUIManager.UIManager.get_frame_native_size_by_frame_id(self._target_id())

    def client_border(self) -> tuple:
        return PyUIManager.UIManager.get_frame_client_border_by_frame_id(self._target_id())

    def clip_rect(self) -> tuple:
        return PyUIManager.UIManager.get_frame_clip_rect_by_frame_id(self._target_id())

    def position_ex(self) -> tuple:
        return PyUIManager.UIManager.get_frame_position_ex_by_frame_id(self._target_id())

    def is_mouse_over(self) -> bool:
        if not self.is_usable:
            return False
        import PyImGui  # type: ignore

        from ..ImGui import ImGui

        io = PyImGui.get_io()
        left, top, right, bottom = self.rect
        return ImGui.is_mouse_in_rect(
            (left, top, right - left, bottom - top), (io.mouse_pos_x, io.mouse_pos_y)
        )

    # -- drawing ----------------------------------------------------------
    def draw(self, color: int) -> None:
        if not self.is_usable:
            return
        left, top, right, bottom = self.rect
        overlay = FrameTree.overlay
        overlay.BeginDraw()
        overlay.DrawQuadFilled(
            PyOverlay.Vec2f(left, top),
            PyOverlay.Vec2f(right, top),
            PyOverlay.Vec2f(right, bottom),
            PyOverlay.Vec2f(left, bottom),
            color,
        )
        overlay.EndDraw()

    def draw_outline(self, color: int, thickness: float = 1.0) -> None:
        if not self.is_usable:
            return
        left, top, right, bottom = self.rect
        overlay = FrameTree.overlay
        overlay.BeginDraw()
        overlay.DrawQuad(
            PyOverlay.Vec2f(left, top),
            PyOverlay.Vec2f(right, top),
            PyOverlay.Vec2f(right, bottom),
            PyOverlay.Vec2f(left, bottom),
            color,
            thickness,
        )
        overlay.EndDraw()

    # -- navigation -------------------------------------------------------
    def parent(self) -> "Frame":
        pid = FrameTree.parent_of(self.frame_id)
        if not pid:
            raise FrameNotFound("%r has no parent" % (self._key or self.frame_id))
        return Frame.from_id(pid)

    def parent_id_native(self) -> int:
        """Parent from the native walker rather than the snapshot."""
        return int(PyUIManager.UIManager.get_parent_frame_id(self.frame_id) or 0)

    def parent_direct(self) -> "Frame":
        return Frame.from_id(
            int(PyUIManager.UIManager.get_parent_frame_id_direct(self.frame_id) or 0)
        )

    def children(self) -> list["Frame"]:
        return [Frame.from_id(c) for c in FrameTree.children_of(self.frame_id)]

    def child_codes(self) -> list[int]:
        return FrameTree.child_codes_of(self.frame_id)

    def child(self, *codes: int) -> "Frame":
        """Walk to an unregistered descendant by raw child codes."""
        cur = self.frame_id
        for code in codes:
            nxt = FrameTree.child_of(cur, code)
            if nxt is None:
                raise FrameNotFound(
                    "%r has no descendant at codes %s (stopped at frame %d, code %d)"
                    % (self._key or self.frame_id, list(codes), cur, code)
                )
            cur = nxt
        return Frame.from_id(cur)

    def find_child(self, *codes: int) -> Optional["Frame"]:
        """`child` that answers None instead of raising."""
        try:
            return self.child(*codes)
        except FrameError:
            return None

    def child_native(self, code: int) -> "Frame":
        """Child by code via the native lookup rather than the snapshot."""
        return Frame.from_id(
            int(PyUIManager.UIManager.get_child_frame_by_frame_id(self.frame_id, code) or 0)
        )

    def child_path_native(self, codes: list[int]) -> "Frame":
        return Frame.from_id(
            int(PyUIManager.UIManager.get_child_frame_path_by_frame_id(self.frame_id, codes) or 0)
        )

    def child_with_hash(self, name_hash: int) -> "Frame":
        """Child carrying `name_hash`."""
        return Frame.from_id(
            int(
                PyUIManager.UIManager.get_child_frame_id_from_name_hash(self.frame_id, name_hash)
                or 0
            )
        )

    def child_named(self, name: str) -> "Frame":
        """Child carrying the hash of `name`."""
        h = NAME_TO_HASH.get(name)
        if h is None:
            raise FrameKeyError("no known frame named %r" % name)
        return self.child_with_hash(h)

    def first_child(self) -> "Frame":
        return Frame.from_id(
            int(PyUIManager.UIManager.get_first_child_frame_id(self.frame_id) or 0)
        )

    def last_child(self) -> "Frame":
        return Frame.from_id(
            int(PyUIManager.UIManager.get_last_child_frame_id(self.frame_id) or 0)
        )

    def next_sibling(self) -> "Frame":
        return Frame.from_id(
            int(PyUIManager.UIManager.get_next_child_frame_id(self.frame_id) or 0)
        )

    def prev_sibling(self) -> "Frame":
        return Frame.from_id(
            int(PyUIManager.UIManager.get_prev_child_frame_id(self.frame_id) or 0)
        )

    def related(self, relation_kind: int, start_after: int = 0) -> "Frame":
        """Native relation walker.  See RELATION_* constants."""
        return Frame.from_id(
            int(
                PyUIManager.UIManager.get_related_frame_id(
                    self.frame_id, relation_kind, start_after
                )
                or 0
            )
        )

    def item(self, index: int) -> "Frame":
        return Frame.from_id(
            int(PyUIManager.UIManager.get_item_frame_id(self.frame_id, index) or 0)
        )

    def tab(self, index: int) -> "Frame":
        return Frame.from_id(
            int(PyUIManager.UIManager.get_tab_frame_id(self.frame_id, index) or 0)
        )

    def is_ancestor_of(self, other: "Frame") -> bool:
        return bool(
            PyUIManager.UIManager.is_ancestor_of_by_frame_id(self.frame_id, other.frame_id)
        )

    # -- io events --------------------------------------------------------
    def io_events(self) -> list:
        if not self.exists:
            return []
        from ..UIManager import UIManager

        return UIManager.GetIOEventsForFrame(self)

    def __iter__(self) -> Iterator["Frame"]:
        return iter(self.children())

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Frame):
            return NotImplemented
        return self._resolve() == other._resolve()

    def __hash__(self) -> int:
        return hash(self._resolve())

    def __bool__(self) -> bool:
        return self.exists

    def __str__(self) -> str:
        """Human-readable identity, for logs and labels."""
        return self.describe() or self.widget_id

    def __repr__(self) -> str:
        fid = self._resolve()
        if self._key:
            return "<Frame %s -> %s>" % (self._key, fid if fid else "unresolved")
        return "<Frame #%s>" % fid
