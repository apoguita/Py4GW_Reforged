"""Launch Bar model — pure data, grid geometry, and collision.

No ImGui and no Py4GW imports: this module must stay importable and unit-testable from a
plain interpreter. The host layer (added later) consumes this model to render; all
selection / editing / animation state lives in the host, never here.

Coordinate model
----------------
A bar owns a logical grid of ``columns`` (x) by ``rows`` (y) square slots. Tiles occupy an
axis-aligned ``w`` x ``h`` block at ``(col, row)`` with zero-based logical coordinates. The
grid is orientation-agnostic: the drag strip's *side* (left/right/top/bottom) and any
transposition are the host's concern, not the model's.

Pixel geometry derives entirely from ``base_* * scale`` — nothing is hard-coded downstream.
``tile_rect``/``content_size`` return **content-local** pixels (i.e. relative to the grid's
top-left, padding included); the host offsets them by the window/strip position.
"""

from dataclasses import asdict
from dataclasses import dataclass
from dataclasses import field
from enum import Enum
from typing import Optional


class BarSide(str, Enum):
    """Which edge the drag strip ("title bar") sits on."""

    LEFT = "left"
    RIGHT = "right"
    TOP = "top"
    BOTTOM = "bottom"


@dataclass
class BarColors:
    """The only three per-bar color overrides pushed on top of the system theme.

    RGB is stored as ``#rrggbb`` hex; each surface also carries its own alpha (0..1) so the
    background, drag bar, and button face can be independently transparent. Derived shades
    (collapsed-strip, tile border) are computed by the host, not stored here.
    """

    bg: str = "#0f1013"
    bg_a: float = 0.92
    drag: str = "#0a0a0a"
    drag_a: float = 1.0
    face: str = "#2b2b31"
    face_a: float = 1.0


@dataclass
class Tile:
    """One occupant of the grid.

    A tile may bind a widget via ``widget_id`` (its full ``folder_script_name``); such a tile
    renders the widget's icon and launches/toggles it. An unbound tile is a placeholder.
    """

    id: str
    col: int
    row: int
    w: int = 1
    h: int = 1
    name: str = ""                     # display name (widget/action name, or user label)
    widget_id: Optional[str] = None
    action: Optional[str] = None       # built-in system action (e.g. "browser")
    deletable: bool = True             # False for fixed system buttons; everything else True

    def cells(self):
        """Yield every ``(col, row)`` cell this tile covers."""

        for dc in range(self.w):
            for dr in range(self.h):
                yield (self.col + dc, self.row + dr)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Tile":
        wid = data.get("widget_id")
        action = data.get("action")
        return cls(
            id=str(data["id"]),
            col=int(data["col"]),
            row=int(data["row"]),
            w=max(1, int(data.get("w", 1))),
            h=max(1, int(data.get("h", 1))),
            name=str(data.get("name", "")),
            widget_id=str(wid) if wid else None,
            action=str(action) if action else None,
            deletable=bool(data.get("deletable", True)),
        )


@dataclass
class LaunchBar:
    """A single launchpad: grid config, per-bar look, placement, and its tiles.

    All mutating tile operations are collision-checked and return ``None``/``False`` on an
    invalid request rather than corrupting the layout.
    """

    id: str
    name: str
    system: bool = False               # a non-deletable "main" bar carrying system buttons
    source: str = "manual"             # tile source: "manual" | "active" | "favorites" (auto-populated presets)
    side: BarSide = BarSide.LEFT
    columns: int = 8
    rows: int = 2
    base_cell: float = 35.0 #CELL SIZE = ICON SIZE
    base_gap: float = 2.0
    base_pad: float = 3.0
    base_strip: float = 14.0
    scale: float = 1.0
    idle_opacity: float = 0.6
    colors: BarColors = field(default_factory=BarColors)
    active_color: str = "#4caf50"          # active-widget indicator color
    ind_outline: bool = True               # indicator style: colored border + glow
    ind_mask: bool = False                 # indicator style: translucent color overlay
    x: float = 0.0
    y: float = 0.0
    collapsed: bool = False
    tiles: list[Tile] = field(default_factory=list)
    _tile_seq: int = 0

    # ---- scaled metrics -------------------------------------------------------------
    @property
    def cell(self) -> float:
        return self.base_cell * self.scale

    @property
    def gap(self) -> float:
        return self.base_gap * self.scale

    @property
    def pad(self) -> float:
        return self.base_pad * self.scale

    @property
    def strip(self) -> float:
        return self.base_strip * self.scale

    @property
    def is_horizontal(self) -> bool:
        """A left/right strip stacks the content horizontally; top/bottom vertically."""

        return self.side in (BarSide.LEFT, BarSide.RIGHT)

    def content_size(self) -> tuple[float, float]:
        """Grid content size in px (padding included), excluding the strip."""

        w = self.pad * 2 + self.columns * self.cell + (self.columns - 1) * self.gap
        h = self.pad * 2 + self.rows * self.cell + (self.rows - 1) * self.gap
        return (w, h)

    def cell_origin(self, col: int, row: int) -> tuple[float, float]:
        """Content-local top-left px of the cell at ``(col, row)``."""

        return (self.pad + col * (self.cell + self.gap), self.pad + row * (self.cell + self.gap))

    def tile_rect(self, tile: Tile) -> tuple[float, float, float, float]:
        """Content-local ``(x, y, w, h)`` px for a tile, spanning its slots and inner gaps."""

        x, y = self.cell_origin(tile.col, tile.row)
        w = tile.w * self.cell + (tile.w - 1) * self.gap
        h = tile.h * self.cell + (tile.h - 1) * self.gap
        return (x, y, w, h)

    # ---- occupancy / collision ------------------------------------------------------
    def occupied_cells(self, except_id: Optional[str] = None) -> set[tuple[int, int]]:
        """Set of covered cells, optionally ignoring one tile (for move/resize checks)."""

        cells: set[tuple[int, int]] = set()
        for tile in self.tiles:
            if tile.id == except_id:
                continue
            cells.update(tile.cells())
        return cells

    def can_place(self, w: int, h: int, col: int, row: int, except_id: Optional[str] = None) -> bool:
        """True if a ``w`` x ``h`` block fits at ``(col, row)`` in-bounds and unoccupied."""

        if w < 1 or h < 1 or col < 0 or row < 0:
            return False
        if col + w > self.columns or row + h > self.rows:
            return False
        occupied = self.occupied_cells(except_id)
        for dc in range(w):
            for dr in range(h):
                if (col + dc, row + dr) in occupied:
                    return False
        return True

    def first_free_block(self, w: int, h: int) -> Optional[tuple[int, int]]:
        """Row-major scan for the first ``(col, row)`` where a ``w`` x ``h`` block fits."""

        if w > self.columns or h > self.rows:
            return None
        for row in range(self.rows - h + 1):
            for col in range(self.columns - w + 1):
                if self.can_place(w, h, col, row):
                    return (col, row)
        return None

    # ---- tile CRUD (collision-checked) ----------------------------------------------
    def get_tile(self, tile_id: str) -> Optional[Tile]:
        return next((t for t in self.tiles if t.id == tile_id), None)

    def add_tile(self, w: int = 1, h: int = 1, col: Optional[int] = None, row: Optional[int] = None) -> Optional[Tile]:
        """Add a ``w`` x ``h`` tile. Auto-places in the first free block when col/row omitted.

        Returns the new tile, or ``None`` if it does not fit (no room / invalid target).
        """

        w = max(1, int(w))
        h = max(1, int(h))
        if col is None or row is None:
            pos = self.first_free_block(w, h)
            if pos is None:
                return None
            col, row = pos
        elif not self.can_place(w, h, col, row):
            return None
        self._tile_seq += 1
        tile = Tile(id=f"t{self._tile_seq}", col=int(col), row=int(row), w=w, h=h)
        self.tiles.append(tile)
        return tile

    def remove_tile(self, tile_id: str) -> bool:
        tile = self.get_tile(tile_id)
        if tile is None or not tile.deletable:
            return False
        self.tiles = [t for t in self.tiles if t.id != tile_id]
        return True

    def move_tile(self, tile_id: str, col: int, row: int) -> bool:
        """Move a tile to ``(col, row)`` if it fits there; no-op + ``False`` otherwise."""

        tile = self.get_tile(tile_id)
        if tile is None or not self.can_place(tile.w, tile.h, col, row, except_id=tile_id):
            return False
        tile.col, tile.row = int(col), int(row)
        return True

    def resize_tile(self, tile_id: str, w: int, h: int) -> bool:
        """Resize a tile in place if the new span fits; no-op + ``False`` otherwise."""

        tile = self.get_tile(tile_id)
        if tile is None:
            return False
        w = max(1, int(w))
        h = max(1, int(h))
        if not self.can_place(w, h, tile.col, tile.row, except_id=tile_id):
            return False
        tile.w, tile.h = w, h
        return True

    def clamp_tiles(self) -> list[str]:
        """Drop tiles that no longer fit after a grid shrink. Returns removed tile ids."""

        removed: list[str] = []
        kept: list[Tile] = []
        for tile in self.tiles:
            if tile.col + tile.w <= self.columns and tile.row + tile.h <= self.rows:
                kept.append(tile)
            else:
                removed.append(tile.id)
        self.tiles = kept
        return removed

    # ---- serialization --------------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "system": self.system,
            "source": self.source,
            "side": self.side.value,
            "columns": self.columns,
            "rows": self.rows,
            "base_cell": self.base_cell,
            "base_gap": self.base_gap,
            "base_pad": self.base_pad,
            "base_strip": self.base_strip,
            "scale": self.scale,
            "idle_opacity": self.idle_opacity,
            "colors": asdict(self.colors),
            "active_color": self.active_color,
            "ind_outline": self.ind_outline,
            "ind_mask": self.ind_mask,
            "x": self.x,
            "y": self.y,
            "collapsed": self.collapsed,
            "tiles": [t.to_dict() for t in self.tiles],
            "tile_seq": self._tile_seq,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LaunchBar":
        colors_data = data.get("colors", {}) or {}
        tiles = [Tile.from_dict(t) for t in data.get("tiles", [])]
        tile_seq = int(data.get("tile_seq", 0))
        # keep the sequence ahead of any restored numeric id so new ids never collide
        for tile in tiles:
            if tile.id.startswith("t") and tile.id[1:].isdigit():
                tile_seq = max(tile_seq, int(tile.id[1:]))
        bar = cls(
            id=str(data["id"]),
            name=str(data.get("name", data["id"])),
            system=bool(data.get("system", False)),
            source=str(data.get("source", "manual") or "manual"),
            side=BarSide(data.get("side", BarSide.LEFT.value)),
            columns=max(1, int(data.get("columns", 8))),
            rows=max(1, int(data.get("rows", 2))),
            base_cell=float(data.get("base_cell", 25.0)),
            base_gap=float(data.get("base_gap", 2.0)),
            base_pad=float(data.get("base_pad", 3.0)),
            base_strip=float(data.get("base_strip", 14.0)),
            scale=float(data.get("scale", 1.0)),
            idle_opacity=float(data.get("idle_opacity", 0.6)),
            active_color=str(data.get("active_color", "#4caf50")),
            ind_outline=bool(data.get("ind_outline", True)),
            ind_mask=bool(data.get("ind_mask", False)),
            colors=BarColors(
                bg=str(colors_data.get("bg", "#0f1013")),
                bg_a=float(colors_data.get("bg_a", 0.92)),
                drag=str(colors_data.get("drag", "#0a0a0a")),
                drag_a=float(colors_data.get("drag_a", 1.0)),
                face=str(colors_data.get("face", "#2b2b31")),
                face_a=float(colors_data.get("face_a", 1.0)),
            ),
            x=float(data.get("x", 0.0)),
            y=float(data.get("y", 0.0)),
            collapsed=bool(data.get("collapsed", False)),
            tiles=tiles,
        )
        bar._tile_seq = tile_seq
        return bar


class LaunchBarSet:
    """An ordered collection of :class:`LaunchBar` instances with stable id assignment.

    Selection / edit-mode state is UI concern and lives in the host, not here.
    """

    def __init__(self, bars: Optional[list[LaunchBar]] = None) -> None:
        self.bars: list[LaunchBar] = list(bars) if bars else []
        self._bar_seq: int = 0
        for bar in self.bars:
            if bar.id.startswith("bar") and bar.id[3:].isdigit():
                self._bar_seq = max(self._bar_seq, int(bar.id[3:]))

    def get(self, bar_id: str) -> Optional[LaunchBar]:
        return next((b for b in self.bars if b.id == bar_id), None)

    def add(self, **overrides) -> LaunchBar:
        """Create a bar with defaults (plus any overrides) and a fresh stable id."""

        self._bar_seq += 1
        bar_id = f"bar{self._bar_seq}"
        name = overrides.pop("name", f"Bar {self._bar_seq}")
        bar = LaunchBar(id=bar_id, name=name, **overrides)
        self.bars.append(bar)
        return bar

    def remove(self, bar_id: str) -> bool:
        bar = self.get(bar_id)
        if bar is None or bar.system:   # system bars are non-deletable
            return False
        self.bars = [b for b in self.bars if b.id != bar_id]
        return True

    def to_dict(self) -> dict:
        return {"bars": [b.to_dict() for b in self.bars], "bar_seq": self._bar_seq}

    @classmethod
    def from_dict(cls, data: dict) -> "LaunchBarSet":
        bars = [LaunchBar.from_dict(b) for b in data.get("bars", [])]
        inst = cls(bars)
        inst._bar_seq = max(inst._bar_seq, int(data.get("bar_seq", 0)))
        return inst
