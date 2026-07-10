"""Project-owned launch-surface framework.

This module contains the model and orchestration layer for configurable launch
surfaces. A launch surface is a user-owned canvas containing widget toggles,
project actions, external-window launchers, and explicitly registered embedded
components.

The module deliberately does not import ``PyImGui`` and does not participate in
``WidgetHandler`` discovery. It is therefore safe to validate outside the
injected game runtime. An ImGui host can consume :meth:`LaunchSurface.renderables`
and use the returned tile rectangles and definitions to draw the visual layer.

The framework uses ``Settings`` by composition through
:class:`LaunchSurfaceSettings`; it never subclasses or modifies ``Settings``.
"""

import json
from dataclasses import dataclass, field, replace
from enum import Enum, IntFlag
from typing import Any, Callable, Iterable, Mapping, Protocol, Sequence


class LaunchSurfaceError(Exception):
    """Base exception for invalid launch-surface definitions or operations."""


class LaunchRegistrationError(LaunchSurfaceError):
    """Raised when a provider attempts an invalid registry operation."""


class LaunchLayoutError(LaunchSurfaceError):
    """Raised when a tile cannot be placed within a page."""


class LaunchCapability(IntFlag):
    """Capabilities that a launch item may expose to a surface tile.

    Capabilities are intentionally composable. One item may be both a widget
    toggle and an embedded component, or an action and a status provider.
    """

    NONE = 0
    INVOKE = 1
    TOGGLE = 2
    RENDER = 4
    STATUS = 8
    CONFIGURE = 16
    PORTAL = 32


class LaunchPresentationMode(str, Enum):
    """Presentation modes understood by the model and ImGui host."""

    LAUNCHER = 'launcher'
    FLOATING = 'floating'
    DOCKED = 'docked'


class LaunchDockEdge(str, Enum):
    """Display edge used by an edge-docked surface."""

    TOP = 'top'
    BOTTOM = 'bottom'
    LEFT = 'left'
    RIGHT = 'right'


@dataclass(frozen=True)
class LaunchRuntimeContext:
    """Read-only context supplied to availability and status callbacks.

    ``values`` is intentionally generic. Providers can publish values such as
    map state, party state, combat state, or HeroAI availability without the
    launch framework importing those feature packages.
    """

    values: Mapping[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        """Return a context value or ``default`` when the value is absent."""

        return self.values.get(key, default)


@dataclass(frozen=True)
class LaunchInvocation:
    """Information passed to an action, toggle, or portal callback."""

    surface_id: str
    page_id: str
    tile_id: str
    item_id: str
    context: LaunchRuntimeContext


@dataclass(frozen=True)
class LaunchProfile:
    """Account/character projection metadata supplied to a surface context."""

    profile_id: str
    label: str
    values: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate profile identity and provide a stable display label."""

        object.__setattr__(self, 'profile_id', _require_identifier(self.profile_id, 'profile_id'))
        object.__setattr__(self, 'label', str(self.label).strip() or self.profile_id)


class LaunchProfileStore:
    """Small instance-owned profile selector for account/character projections."""

    def __init__(self, profiles: Iterable[LaunchProfile] = ()) -> None:
        """Create a store without importing account or character systems."""

        self._profiles: dict[str, LaunchProfile] = {profile.profile_id: profile for profile in profiles}
        self._active_profile_id = next(iter(self._profiles), '')

    def register(self, profile: LaunchProfile, replace: bool = False) -> LaunchProfile:
        """Register a profile with duplicate protection."""

        if profile.profile_id in self._profiles and not replace:
            raise LaunchSurfaceError(f"Profile '{profile.profile_id}' is already registered")
        self._profiles[profile.profile_id] = profile
        if not self._active_profile_id:
            self._active_profile_id = profile.profile_id
        return profile

    def select(self, profile_id: str) -> LaunchProfile:
        """Select and return an existing profile."""

        profile = self._profiles.get(profile_id)
        if profile is None:
            raise LaunchSurfaceError(f"Profile '{profile_id}' is not registered")
        self._active_profile_id = profile_id
        return profile

    def active(self) -> LaunchProfile | None:
        """Return the active profile, if one exists."""

        return self._profiles.get(self._active_profile_id)

    def list_profiles(self) -> list[LaunchProfile]:
        """Return profiles sorted by display label and stable ID."""

        return sorted(self._profiles.values(), key=lambda profile: (profile.label.casefold(), profile.profile_id))

    def context(self, base: LaunchRuntimeContext | None = None) -> LaunchRuntimeContext:
        """Merge the active profile values into a runtime context snapshot."""

        values = dict((base or LaunchRuntimeContext()).values)
        profile = self.active()
        if profile is not None:
            values.update(profile.values)
            values['profile_id'] = profile.profile_id
            values['profile_label'] = profile.label
        return LaunchRuntimeContext(values)


class LaunchFrameAnchor(Protocol):
    """Optional adapter that resolves an attached game-frame position."""

    def position(self, window_size: tuple[float, float]) -> tuple[float, float] | None:
        """Return a screen position for a surface window, or ``None`` to fall back."""


class WidgetRuntimePort(Protocol):
    """Narrow runtime contract used by widget-toggle launch items.

    The current ``WidgetHandler`` can be adapted to this protocol without
    making the project-owned launch framework depend on private handler
    methods. ``widget_id`` is always the full catalog ID.
    """

    def get(self, widget_id: str) -> Any:
        """Return the live widget adapter object, if available."""

    def is_enabled(self, widget_id: str) -> bool:
        """Return whether the full widget ID is currently enabled."""

    def enable(self, widget_id: str) -> None:
        """Enable the widget identified by its full catalog ID."""

    def request_disable(self, widget_id: str) -> None:
        """Request widget disablement, preserving system-widget safeguards."""

    def set_configuring(self, widget_id: str, value: bool = True) -> None:
        """Set the widget's configuration visibility state."""

    def reload_revision(self) -> int:
        """Return a value that changes whenever widget discovery is reloaded."""


class SettingsDocument(Protocol):
    """Minimal settings surface required by :class:`LaunchSurfaceSettings`."""

    def get_str(self, section: str, key: str, default: str = '') -> str:
        """Read a string value."""

    def get_bool(self, section: str, key: str, default: bool = False) -> bool:
        """Read a boolean value."""

    def get_float(self, section: str, key: str, default: float = 0.0) -> float:
        """Read a floating-point value."""

    def set_str(self, section: str, key: str, value: str) -> None:
        """Write a string value."""

    def set_bool(self, section: str, key: str, value: bool) -> None:
        """Write a boolean value."""

    def set_float(self, section: str, key: str, value: float) -> None:
        """Write a floating-point value."""


LaunchCallback = Callable[[LaunchInvocation], Any]
AvailabilityCallback = Callable[[LaunchRuntimeContext], bool]
StatusCallback = Callable[[LaunchRuntimeContext], Any]
ComponentFactory = Callable[['LaunchComponentContext'], Any]
RuntimeContextProvider = Callable[[], LaunchRuntimeContext]


class LaunchComponent(Protocol):
    """Optional lifecycle contract implemented by embedded components."""

    def draw(self, context: 'LaunchComponentContext') -> None:
        """Render the component for the current frame."""


@dataclass
class LaunchItemDefinition:
    """Registered functionality that can be placed on one or more surfaces.

    Definitions are shared by all surface instances. User-specific geometry,
    labels, visibility, and representation choices are stored by
    :class:`LaunchTile`, not here.
    """

    item_id: str
    label: str
    description: str = ''
    icon: str = ''
    category: str = ''
    tags: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()
    capabilities: LaunchCapability = LaunchCapability.NONE
    source_widget_id: str = ''
    invoke_callback: LaunchCallback | None = None
    availability_callback: AvailabilityCallback | None = None
    visibility_callback: AvailabilityCallback | None = None
    status_callback: StatusCallback | None = None
    component_factory: ComponentFactory | None = None
    configure_callback: LaunchCallback | None = None
    portal_callback: LaunchCallback | None = None
    provider_id: str = 'core'
    minimum_span: tuple[int, int] = (1, 1)
    preferred_span: tuple[int, int] = (1, 1)
    maximum_span: tuple[int, int] | None = None
    supported_representations: tuple[str, ...] = ('compact', 'expanded', 'status', 'portal', 'auto')
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate identity and normalize metadata collections."""

        self.item_id = _require_identifier(self.item_id, 'item_id')
        self.label = str(self.label).strip() or self.item_id
        self.tags = _normalize_strings(self.tags)
        self.aliases = _normalize_strings(self.aliases)
        _validate_span(self.minimum_span, 'minimum_span')
        _validate_span(self.preferred_span, 'preferred_span')
        if self.maximum_span is not None:
            _validate_span(self.maximum_span, 'maximum_span')
            if self.preferred_span[0] > self.maximum_span[0] or self.preferred_span[1] > self.maximum_span[1]:
                raise LaunchSurfaceError('preferred_span cannot exceed maximum_span')
        if self.minimum_span[0] > self.preferred_span[0] or self.minimum_span[1] > self.preferred_span[1]:
            raise LaunchSurfaceError('minimum_span cannot exceed preferred_span')

    def supports(self, capability: LaunchCapability) -> bool:
        """Return whether all requested capability flags are available."""

        return bool(self.capabilities & capability == capability)

    def is_available(self, context: LaunchRuntimeContext | None = None) -> bool:
        """Evaluate the optional availability predicate safely.

        A provider exception is treated as unavailable. The host can add
        logging around this method without allowing one feature to break the
        entire launch surface.
        """

        if self.availability_callback is None:
            return True
        try:
            return bool(self.availability_callback(context or LaunchRuntimeContext()))
        except Exception:
            return False

    def is_visible(self, context: LaunchRuntimeContext | None = None) -> bool:
        """Evaluate optional projection visibility without mutating layout."""

        if self.visibility_callback is None:
            return True
        try:
            return bool(self.visibility_callback(context or LaunchRuntimeContext()))
        except Exception:
            return False


@dataclass(frozen=True)
class CatalogWidgetMetadata:
    """Catalog-derived display metadata for one discovered widget."""

    widget_id: str
    label: str
    icon: str = ''
    category: str = ''
    tags: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()
    enabled: bool = False
    configurable: bool = False


class LaunchCatalogAdapter:
    """Read-only adapter over a ``WidgetCatalogSnapshot``-shaped object.

    The adapter intentionally relies on the snapshot contract rather than
    importing or instantiating ``WidgetCatalog``. The caller supplies the
    current snapshot from the existing catalog system.
    """

    def __init__(self, snapshot: Any | None = None) -> None:
        """Create an adapter and optionally attach an initial snapshot."""

        self._snapshot: Any | None = None
        self._revision = 0
        if snapshot is not None:
            self.set_snapshot(snapshot)

    @property
    def snapshot(self) -> Any | None:
        """Return the currently attached catalog snapshot."""

        return self._snapshot

    def set_snapshot(self, snapshot: Any | None) -> None:
        """Replace the snapshot and advance the adapter revision."""

        self._snapshot = snapshot
        self._revision += 1

    def get_catalog_revision(self) -> int:
        """Return a monotonic revision suitable for cache invalidation."""

        return self._revision

    def list_widgets(self) -> list[CatalogWidgetMetadata]:
        """Return catalog widgets sorted by display label and full ID."""

        if self._snapshot is None:
            return []
        widgets = getattr(self._snapshot, 'widgets_by_id', {}) or {}
        result = [self._metadata(widget_id, widget) for widget_id, widget in widgets.items()]
        return sorted(result, key=lambda item: (item.label.casefold(), item.widget_id.casefold()))

    def search(self, text: str = '') -> list[CatalogWidgetMetadata]:
        """Search widget names, IDs, categories, tags, and aliases."""

        query = str(text).strip().casefold()
        if not query:
            return self.list_widgets()
        return [
            metadata
            for metadata in self.list_widgets()
            if any(query in field.casefold() for field in self._search_fields(metadata))
        ]

    def filter(
        self,
        *,
        category: str = '',
        tag: str = '',
        scope: str = 'all',
    ) -> list[CatalogWidgetMetadata]:
        """Filter catalog metadata by category, tag, and enabled scope."""

        category_query = str(category).strip().casefold()
        tag_query = str(tag).strip().casefold()
        scope_query = str(scope).strip().casefold() or 'all'
        result: list[CatalogWidgetMetadata] = []
        for metadata in self.list_widgets():
            if category_query and metadata.category.casefold() != category_query:
                continue
            if tag_query and tag_query not in {value.casefold() for value in metadata.tags}:
                continue
            if scope_query == 'active' and not metadata.enabled:
                continue
            if scope_query == 'inactive' and metadata.enabled:
                continue
            result.append(metadata)
        return result

    def get_widget(self, widget_id: str) -> CatalogWidgetMetadata | None:
        """Return metadata for a full widget ID, or ``None`` if unresolved."""

        if self._snapshot is None:
            return None
        widget = (getattr(self._snapshot, 'widgets_by_id', {}) or {}).get(widget_id)
        return self._metadata(widget_id, widget) if widget is not None else None

    def definition_for(self, widget_id: str, provider_id: str = 'catalog') -> LaunchItemDefinition | None:
        """Create a generic widget-toggle definition from catalog metadata."""

        metadata = self.get_widget(widget_id)
        if metadata is None:
            return None
        capabilities = LaunchCapability.TOGGLE
        if metadata.configurable:
            capabilities |= LaunchCapability.CONFIGURE
        return LaunchItemDefinition(
            item_id=LaunchSurface.widget_item_id(widget_id),
            label=metadata.label,
            icon=metadata.icon,
            category=metadata.category,
            tags=metadata.tags,
            aliases=metadata.aliases,
            capabilities=capabilities,
            source_widget_id=metadata.widget_id,
            provider_id=provider_id,
            metadata={'catalog_enabled': metadata.enabled},
        )

    @staticmethod
    def _search_fields(metadata: CatalogWidgetMetadata) -> tuple[str, ...]:
        """Return normalized search fields for one metadata record."""

        return (
            metadata.widget_id,
            metadata.label,
            metadata.category,
            *metadata.tags,
            *metadata.aliases,
        )

    @staticmethod
    def _metadata(widget_id: str, widget: Any) -> CatalogWidgetMetadata:
        """Convert one catalog widget object into a stable metadata record."""

        return CatalogWidgetMetadata(
            widget_id=str(widget_id),
            label=str(getattr(widget, 'name', '') or getattr(widget, 'plain_name', '') or widget_id),
            icon=str(getattr(widget, 'image', '') or ''),
            category=str(getattr(widget, 'category', '') or ''),
            tags=_normalize_strings(getattr(widget, 'tags', ()) or ()),
            aliases=_normalize_strings(getattr(widget, 'aliases', ()) or ()),
            enabled=bool(getattr(widget, 'enabled', False)),
            configurable=bool(getattr(widget, 'has_configure_property', False)),
        )


@dataclass
class LaunchTile:
    """User-owned placement of one registered item on a page.

    Coordinates are zero-based logical slots. Empty cells are not represented
    by tiles and therefore remain invisible and non-interactive at runtime.
    """

    tile_id: str
    item_id: str
    x: int = 0
    y: int = 0
    column_span: int = 1
    row_span: int = 1
    visible: bool = True
    representation: str = 'auto'
    custom_label: str = ''
    custom_icon: str = ''
    z_index: int = 0
    cluster_id: str = ''

    def __post_init__(self) -> None:
        """Validate tile identity, coordinates, and dimensions."""

        self.tile_id = _require_identifier(self.tile_id, 'tile_id')
        self.item_id = _require_identifier(self.item_id, 'item_id')
        _validate_coordinate(self.x, 'x')
        _validate_coordinate(self.y, 'y')
        _validate_span((self.column_span, self.row_span), 'tile span')

    @property
    def span(self) -> tuple[int, int]:
        """Return the tile width and height in logical slots."""

        return self.column_span, self.row_span

    def to_dict(self) -> dict[str, Any]:
        """Serialize the tile to JSON-compatible data."""

        return {
            'tile_id': self.tile_id,
            'item_id': self.item_id,
            'x': self.x,
            'y': self.y,
            'column_span': self.column_span,
            'row_span': self.row_span,
            'visible': self.visible,
            'representation': self.representation,
            'custom_label': self.custom_label,
            'custom_icon': self.custom_icon,
            'z_index': self.z_index,
            'cluster_id': self.cluster_id,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> 'LaunchTile':
        """Deserialize a tile and apply safe defaults for optional fields."""

        return cls(
            tile_id=str(data.get('tile_id', '')),
            item_id=str(data.get('item_id', '')),
            x=int(data.get('x', 0)),
            y=int(data.get('y', 0)),
            column_span=int(data.get('column_span', 1)),
            row_span=int(data.get('row_span', 1)),
            visible=bool(data.get('visible', True)),
            representation=str(data.get('representation', 'auto')),
            custom_label=str(data.get('custom_label', '')),
            custom_icon=str(data.get('custom_icon', '')),
            z_index=int(data.get('z_index', 0)),
            cluster_id=str(data.get('cluster_id', '')),
        )


@dataclass
class LaunchPage:
    """A user-sized logical canvas containing explicitly positioned tiles."""

    page_id: str
    label: str
    columns: int = 8
    rows: int = 4
    cell_size: float = 40.0
    gap: float = 4.0
    tiles: list[LaunchTile] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate page identity and canvas dimensions."""

        self.page_id = _require_identifier(self.page_id, 'page_id')
        self.label = str(self.label).strip() or self.page_id
        _validate_positive_int(self.columns, 'columns')
        _validate_positive_int(self.rows, 'rows')
        if self.cell_size <= 0 or self.gap < 0:
            raise LaunchLayoutError('cell_size must be positive and gap cannot be negative')

    def get_tile(self, tile_id: str) -> LaunchTile | None:
        """Return a tile by ID."""

        return next((tile for tile in self.tiles if tile.tile_id == tile_id), None)

    def add_tile(self, tile: LaunchTile, allow_overlap: bool = False) -> None:
        """Add a tile after checking identity, bounds, and overlap."""

        if self.get_tile(tile.tile_id) is not None:
            raise LaunchLayoutError(f"Tile '{tile.tile_id}' already exists on page '{self.page_id}'")
        self.validate_tile(tile, ignore_tile_id=None, allow_overlap=allow_overlap)
        self.tiles.append(tile)

    def remove_tile(self, tile_id: str) -> bool:
        """Remove a tile and return whether it existed."""

        original_count = len(self.tiles)
        self.tiles[:] = [tile for tile in self.tiles if tile.tile_id != tile_id]
        return len(self.tiles) != original_count

    def validate_tile(
        self,
        tile: LaunchTile,
        ignore_tile_id: str | None = None,
        allow_overlap: bool = False,
    ) -> None:
        """Validate a tile without mutating the page.

        By default, placement outside the user-defined canvas and overlap with
        another visible tile are rejected. The editor may explicitly opt into
        overlap, but normal loading never moves tiles automatically.
        """

        if tile.x + tile.column_span > self.columns or tile.y + tile.row_span > self.rows:
            raise LaunchLayoutError(
                f"Tile '{tile.tile_id}' does not fit inside page '{self.page_id}' " f'({self.columns}x{self.rows})'
            )
        if allow_overlap:
            return
        for other in self.tiles:
            if other.tile_id == ignore_tile_id or not other.visible or not tile.visible:
                continue
            if _tiles_overlap(tile, other):
                raise LaunchLayoutError(f"Tile '{tile.tile_id}' overlaps tile '{other.tile_id}'")

    def update_tile(self, tile: LaunchTile, allow_overlap: bool = False) -> None:
        """Replace an existing tile after validating its new geometry."""

        if self.get_tile(tile.tile_id) is None:
            raise LaunchLayoutError(f"Tile '{tile.tile_id}' does not exist on page '{self.page_id}'")
        self.validate_tile(tile, ignore_tile_id=tile.tile_id, allow_overlap=allow_overlap)
        for index, current in enumerate(self.tiles):
            if current.tile_id == tile.tile_id:
                self.tiles[index] = tile
                return

    def resize_canvas(self, columns: int, rows: int) -> None:
        """Resize the canvas without silently moving or clipping tiles."""

        _validate_positive_int(columns, 'columns')
        _validate_positive_int(rows, 'rows')
        for tile in self.tiles:
            if tile.x + tile.column_span > columns or tile.y + tile.row_span > rows:
                raise LaunchLayoutError(f"Tile '{tile.tile_id}' would fall outside resized page '{self.page_id}'")
        self.columns = columns
        self.rows = rows

    def tile_rect(self, tile: LaunchTile) -> tuple[float, float, float, float]:
        """Return a tile rectangle in page-local pixels.

        The returned tuple is ``(x, y, width, height)``. Empty cells are never
        queried by the runtime renderer.
        """

        self.validate_tile(tile, ignore_tile_id=tile.tile_id, allow_overlap=True)
        x = tile.x * (self.cell_size + self.gap)
        y = tile.y * (self.cell_size + self.gap)
        width = tile.column_span * self.cell_size + max(0, tile.column_span - 1) * self.gap
        height = tile.row_span * self.cell_size + max(0, tile.row_span - 1) * self.gap
        return x, y, width, height

    def to_dict(self) -> dict[str, Any]:
        """Serialize page dimensions and explicit tile geometry."""

        return {
            'page_id': self.page_id,
            'label': self.label,
            'columns': self.columns,
            'rows': self.rows,
            'cell_size': self.cell_size,
            'gap': self.gap,
            'tiles': [tile.to_dict() for tile in self.tiles],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> 'LaunchPage':
        """Deserialize a page and its explicitly positioned tiles."""

        page = cls(
            page_id=str(data.get('page_id', '')),
            label=str(data.get('label', '')),
            columns=int(data.get('columns', 8)),
            rows=int(data.get('rows', 4)),
            cell_size=float(data.get('cell_size', 40.0)),
            gap=float(data.get('gap', 4.0)),
        )
        for tile_data in data.get('tiles', []) or []:
            tile = LaunchTile.from_dict(tile_data)
            page.add_tile(tile)
        return page


@dataclass
class LaunchCluster:
    """Optional group of tiles that can move or collapse as one unit."""

    cluster_id: str
    label: str
    tile_ids: list[str] = field(default_factory=list)
    collapsed: bool = False

    def __post_init__(self) -> None:
        """Normalize cluster identity and member IDs."""

        self.cluster_id = _require_identifier(self.cluster_id, 'cluster_id')
        self.label = str(self.label).strip() or self.cluster_id
        self.tile_ids = list(dict.fromkeys(str(tile_id) for tile_id in self.tile_ids if str(tile_id).strip()))

    def to_dict(self) -> dict[str, Any]:
        """Serialize this cluster to JSON-compatible data."""

        return {
            'cluster_id': self.cluster_id,
            'label': self.label,
            'tile_ids': list(self.tile_ids),
            'collapsed': self.collapsed,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> 'LaunchCluster':
        """Deserialize one cluster record."""

        return cls(
            cluster_id=str(data.get('cluster_id', '')),
            label=str(data.get('label', '')),
            tile_ids=[str(tile_id) for tile_id in data.get('tile_ids', []) or []],
            collapsed=bool(data.get('collapsed', False)),
        )


@dataclass
class LaunchSurfaceState:
    """Persistent and runtime state owned by one surface instance."""

    visible: bool = True
    presentation_mode: LaunchPresentationMode = LaunchPresentationMode.FLOATING
    dock_edge: LaunchDockEdge = LaunchDockEdge.TOP
    dock_offset: float = 0.5
    floating_x: float = 0.25
    floating_y: float = 0.25
    locked: bool = False
    profile_id: str = ''
    active_page: str = 'main'
    pages: list[LaunchPage] = field(default_factory=lambda: [LaunchPage('main', 'Main')])
    shortcuts: dict[str, dict[str, Any]] = field(default_factory=dict)
    component_state: dict[str, dict[str, Any]] = field(default_factory=dict)
    layout_presets: dict[str, Any] = field(default_factory=dict)
    clusters: dict[str, LaunchCluster] = field(default_factory=dict)

    def get_page(self, page_id: str) -> LaunchPage | None:
        """Return a page by ID."""

        return next((page for page in self.pages if page.page_id == page_id), None)

    def ensure_page(self, page_id: str, label: str | None = None) -> LaunchPage:
        """Return an existing page or create an empty page."""

        page = self.get_page(page_id)
        if page is None:
            page = LaunchPage(page_id, label or page_id)
            self.pages.append(page)
        return page


class LaunchSurfaceSettings:
    """Persistence adapter that composes an existing ``Settings`` document.

    The adapter owns launch-surface serialization and schema migration. It does
    not subclass, extend, or modify the project ``Settings`` class.
    """

    SCHEMA_VERSION = 1
    SURFACE_SECTION = 'Launch Surface'
    PAGES_SECTION = 'Pages'
    PRESETS_SECTION = 'Layout Presets'

    def __init__(self, document: SettingsDocument) -> None:
        """Bind the adapter to one independent settings document."""

        self.document = document
        self.last_save_ok = True
        self.last_save_error = ''

    def load(self) -> LaunchSurfaceState:
        """Load one surface state, falling back safely on malformed data."""

        state = LaunchSurfaceState(
            visible=self.document.get_bool(self.SURFACE_SECTION, 'visible', True),
            presentation_mode=_enum_or_default(
                LaunchPresentationMode,
                self.document.get_str(self.SURFACE_SECTION, 'presentation_mode', 'floating'),
                LaunchPresentationMode.FLOATING,
            ),
            dock_edge=_enum_or_default(
                LaunchDockEdge,
                self.document.get_str(self.SURFACE_SECTION, 'dock_edge', 'top'),
                LaunchDockEdge.TOP,
            ),
            dock_offset=_clamp(self.document.get_float(self.SURFACE_SECTION, 'dock_offset', 0.5), 0.0, 1.0),
            floating_x=_clamp(self.document.get_float(self.SURFACE_SECTION, 'floating_x', 0.25), 0.0, 1.0),
            floating_y=_clamp(self.document.get_float(self.SURFACE_SECTION, 'floating_y', 0.25), 0.0, 1.0),
            locked=self.document.get_bool(self.SURFACE_SECTION, 'locked', False),
            profile_id=self.document.get_str(self.SURFACE_SECTION, 'profile_id', ''),
            active_page=self.document.get_str(self.PAGES_SECTION, 'active_page', 'main') or 'main',
        )

        pages_data = self._load_json(self.PAGES_SECTION, 'pages_json', [])
        if pages_data:
            loaded_pages = self._load_pages(pages_data)
            if loaded_pages:
                state.pages = loaded_pages
                if state.get_page(state.active_page) is None:
                    state.active_page = state.pages[0].page_id

        shortcuts = self._load_json(self.SURFACE_SECTION, 'shortcuts_json', {})
        component_state = self._load_json(self.SURFACE_SECTION, 'component_state_json', {})
        presets = self._load_json(self.PRESETS_SECTION, 'presets_json', {})
        state.shortcuts = (
            {str(tile_id): dict(binding) for tile_id, binding in shortcuts.items() if isinstance(binding, Mapping)}
            if isinstance(shortcuts, dict)
            else {}
        )
        state.component_state = (
            {str(item_id): dict(values) for item_id, values in component_state.items() if isinstance(values, Mapping)}
            if isinstance(component_state, dict)
            else {}
        )
        state.layout_presets = presets if isinstance(presets, dict) else {}
        cluster_data = self._load_json(self.PAGES_SECTION, 'clusters_json', {}) or {}
        if isinstance(cluster_data, Mapping):
            for cluster_id, value in cluster_data.items():
                if not isinstance(value, Mapping):
                    continue
                try:
                    cluster = LaunchCluster.from_dict({**value, 'cluster_id': cluster_id})
                except (TypeError, ValueError, LaunchSurfaceError):
                    continue
                state.clusters[cluster.cluster_id] = cluster
        return state

    def save(self, state: LaunchSurfaceState) -> bool:
        """Persist one complete surface state and flush native settings when supported."""

        try:
            self.document.set_str(self.SURFACE_SECTION, 'schema_version', str(self.SCHEMA_VERSION))
            self.document.set_bool(self.SURFACE_SECTION, 'visible', state.visible)
            self.document.set_str(self.SURFACE_SECTION, 'presentation_mode', state.presentation_mode.value)
            self.document.set_str(self.SURFACE_SECTION, 'dock_edge', state.dock_edge.value)
            self.document.set_float(self.SURFACE_SECTION, 'dock_offset', _clamp(state.dock_offset, 0.0, 1.0))
            self.document.set_float(self.SURFACE_SECTION, 'floating_x', _clamp(state.floating_x, 0.0, 1.0))
            self.document.set_float(self.SURFACE_SECTION, 'floating_y', _clamp(state.floating_y, 0.0, 1.0))
            self.document.set_bool(self.SURFACE_SECTION, 'locked', state.locked)
            self.document.set_str(self.SURFACE_SECTION, 'profile_id', state.profile_id)
            self.document.set_str(self.PAGES_SECTION, 'active_page', state.active_page)
            self.document.set_str(
                self.PAGES_SECTION, 'pages_json', _json_dumps([page.to_dict() for page in state.pages])
            )
            self.document.set_str(self.SURFACE_SECTION, 'shortcuts_json', _json_dumps(state.shortcuts))
            self.document.set_str(self.SURFACE_SECTION, 'component_state_json', _json_dumps(state.component_state))
            self.document.set_str(self.PRESETS_SECTION, 'presets_json', _json_dumps(state.layout_presets))
            self.document.set_str(
                self.PAGES_SECTION,
                'clusters_json',
                _json_dumps({cluster_id: cluster.to_dict() for cluster_id, cluster in state.clusters.items()}),
            )
            flush = getattr(self.document, 'save', None)
            if callable(flush):
                result = flush()
                self.last_save_ok = bool(result) if result is not None else True
            else:
                self.last_save_ok = True
            self.last_save_error = ''
        except Exception as exc:
            self.last_save_ok = False
            self.last_save_error = f'{type(exc).__name__}: {exc}'
        return self.last_save_ok

    def _load_json(self, section: str, key: str, default: Any) -> Any:
        """Read one JSON setting and return ``default`` if it is invalid."""

        raw = self.document.get_str(section, key, '')
        if not raw:
            return default
        try:
            return json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            return default

    @staticmethod
    def _load_pages(data: Any) -> list[LaunchPage]:
        """Deserialize valid pages while skipping malformed page records."""

        pages: list[LaunchPage] = []
        if not isinstance(data, list):
            return pages
        for page_data in data:
            if not isinstance(page_data, Mapping):
                continue
            try:
                page = LaunchPage.from_dict(page_data)
            except (TypeError, ValueError, LaunchSurfaceError):
                continue
            if any(existing.page_id == page.page_id for existing in pages):
                continue
            pages.append(page)
        return pages


@dataclass
class LaunchComponentContext:
    """Context supplied to an embedded component factory or renderer.

    The context is intentionally narrower than the widget manager. Component
    state is mutable because it is the component's namespaced persistence
    boundary; all cross-item actions remain routed through explicit callbacks.
    """

    surface_id: str
    page_id: str
    tile_id: str
    item_id: str
    tile_rect: tuple[float, float, float, float]
    runtime_context: LaunchRuntimeContext
    state: dict[str, Any]
    hovered: bool = False
    focused: bool = False
    editing: bool = False
    invoke_callback: Callable[[str], Any] | None = None
    portal_callback: Callable[[str], Any] | None = None
    dirty: bool = False

    @property
    def available_size(self) -> tuple[float, float]:
        """Return the current component width and height in pixels."""

        return self.tile_rect[2], self.tile_rect[3]

    def get(self, key: str, default: Any = None) -> Any:
        """Read a namespaced component-state value."""

        return self.state.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Write a namespaced component-state value and mark the host dirty."""

        self.state[key] = value
        self.dirty = True

    def request_redraw(self) -> None:
        """Mark the component state as changed for the current host frame."""

        self.dirty = True

    def invoke(self, item_id: str) -> Any:
        """Invoke another registered item through the host's explicit router."""

        if self.invoke_callback is None:
            raise LaunchSurfaceError('This component has no invocation router')
        return self.invoke_callback(item_id)

    def open_portal(self, target_id: str) -> Any:
        """Request navigation to another page or surface through the host."""

        if self.portal_callback is None:
            raise LaunchSurfaceError('This component has no portal router')
        return self.portal_callback(target_id)


@dataclass(frozen=True)
class LaunchRenderable:
    """Resolved tile data consumed by the ImGui host boundary."""

    surface_id: str
    page_id: str
    tile: LaunchTile
    definition: LaunchItemDefinition | None
    tile_rect: tuple[float, float, float, float]
    available: bool
    enabled: bool | None
    status: Any = None


class LaunchSurfaceRegistry:
    """Shared registry for project-provided launch definitions.

    Registry state is shared intentionally; placement and display state are
    owned by each ``LaunchSurface`` instance.
    """

    def __init__(self) -> None:
        """Create an empty registry with no implicit providers."""

        self._items: dict[str, LaunchItemDefinition] = {}
        self._provider_items: dict[str, set[str]] = {}
        self._provider_errors: dict[str, str] = {}

    def register(self, definition: LaunchItemDefinition, replace: bool = False) -> LaunchItemDefinition:
        """Register a definition, rejecting accidental duplicate IDs."""

        active_provider = getattr(self, '_active_provider_id', None)
        if active_provider and definition.provider_id == 'core':
            definition.provider_id = active_provider
        existing = self._items.get(definition.item_id)
        if existing is not None and not replace:
            raise LaunchRegistrationError(f"Launch item '{definition.item_id}' is already registered")
        if existing is not None:
            self._provider_items.get(existing.provider_id, set()).discard(existing.item_id)
        self._items[definition.item_id] = definition
        self._provider_items.setdefault(definition.provider_id, set()).add(definition.item_id)
        return definition

    def register_provider(
        self,
        provider_id: str,
        provider: Callable[['LaunchSurfaceRegistry'], Any],
        *,
        replace: bool = False,
    ) -> Any:
        """Execute an explicit provider registration function.

        The provider is responsible for calling ``register`` or one of the
        convenience methods. The framework never scans project modules. A
        provider failure is recorded and isolated so unrelated providers and
        existing surface layouts remain usable.
        """

        provider_id = _require_identifier(provider_id, 'provider_id')
        if replace:
            self.unregister_provider(provider_id)
        previous_items = set(self._provider_items.get(provider_id, set()))
        previous_provider = getattr(self, '_active_provider_id', None)
        self._active_provider_id = provider_id
        try:
            result = provider(self)
            self._provider_errors.pop(provider_id, None)
            return result
        except Exception as exc:
            current_items = set(self._provider_items.get(provider_id, set()))
            for item_id in current_items - previous_items:
                self._items.pop(item_id, None)
            self._provider_items[provider_id] = previous_items
            self._provider_errors[provider_id] = f'{type(exc).__name__}: {exc}'
            return None
        finally:
            self._active_provider_id = previous_provider

    def provider_errors(self) -> dict[str, str]:
        """Return a copy of provider registration failures."""

        return dict(self._provider_errors)

    def provider_ids(self) -> list[str]:
        """Return provider IDs that currently own one or more definitions."""

        return sorted(provider_id for provider_id, items in self._provider_items.items() if items)

    def register_action(
        self,
        item_id: str,
        label: str,
        callback: LaunchCallback,
        *,
        provider_id: str | None = None,
        **metadata: Any,
    ) -> LaunchItemDefinition:
        """Register an invokable project action."""

        return self.register(
            LaunchItemDefinition(
                item_id=item_id,
                label=label,
                capabilities=LaunchCapability.INVOKE,
                invoke_callback=callback,
                provider_id=provider_id or getattr(self, '_active_provider_id', None) or 'core',
                **metadata,
            )
        )

    def register_window_launcher(
        self,
        item_id: str,
        label: str,
        callback: LaunchCallback,
        *,
        provider_id: str | None = None,
        **metadata: Any,
    ) -> LaunchItemDefinition:
        """Register an existing-window launcher as an invokable item."""

        return self.register_action(
            item_id,
            label,
            callback,
            provider_id=provider_id,
            **metadata,
        )

    def register_portal(
        self,
        item_id: str,
        label: str,
        callback: LaunchCallback,
        *,
        provider_id: str | None = None,
        **metadata: Any,
    ) -> LaunchItemDefinition:
        """Register a navigation item that opens another page or surface."""

        return self.register(
            LaunchItemDefinition(
                item_id=item_id,
                label=label,
                capabilities=LaunchCapability.PORTAL,
                portal_callback=callback,
                provider_id=provider_id or getattr(self, '_active_provider_id', None) or 'core',
                **metadata,
            )
        )

    def register_component(
        self,
        item_id: str,
        label: str,
        component_factory: ComponentFactory,
        *,
        provider_id: str | None = None,
        **metadata: Any,
    ) -> LaunchItemDefinition:
        """Register an explicitly embeddable component."""

        return self.register(
            LaunchItemDefinition(
                item_id=item_id,
                label=label,
                capabilities=LaunchCapability.RENDER,
                component_factory=component_factory,
                provider_id=provider_id or getattr(self, '_active_provider_id', None) or 'core',
                **metadata,
            )
        )

    def register_widget_toggle(
        self,
        widget_id: str,
        *,
        label: str = '',
        provider_id: str | None = None,
        **metadata: Any,
    ) -> LaunchItemDefinition:
        """Register a generic toggle definition for a full widget ID."""

        widget_id = _require_identifier(widget_id, 'widget_id')
        return self.register(
            LaunchItemDefinition(
                item_id=LaunchSurface.widget_item_id(widget_id),
                label=label or widget_id,
                capabilities=LaunchCapability.TOGGLE,
                source_widget_id=widget_id,
                provider_id=provider_id or getattr(self, '_active_provider_id', None) or 'catalog',
                **metadata,
            )
        )

    def unregister_provider(self, provider_id: str) -> list[str]:
        """Remove all definitions owned by a provider and return their IDs."""

        item_ids = sorted(self._provider_items.pop(provider_id, set()))
        for item_id in item_ids:
            self._items.pop(item_id, None)
        self._provider_errors.pop(provider_id, None)
        return item_ids

    def get(self, item_id: str) -> LaunchItemDefinition | None:
        """Return one registered definition."""

        return self._items.get(item_id)

    def list_items(self, category: str = '') -> list[LaunchItemDefinition]:
        """Return definitions sorted by category, label, and stable ID."""

        items = self._items.values()
        if category:
            items = (item for item in items if item.category == category)
        return sorted(
            items, key=lambda item: (item.category.casefold(), item.label.casefold(), item.item_id.casefold())
        )

    def search(self, text: str = '', category: str = '', tags: Iterable[str] = ()) -> list[LaunchItemDefinition]:
        """Query registered definitions by display metadata and category."""

        query = str(text).strip().casefold()
        requested_tags = {str(tag).strip().casefold() for tag in tags if str(tag).strip()}
        result: list[LaunchItemDefinition] = []
        for item in self.list_items(category):
            fields = (item.item_id, item.label, item.description, item.category, *item.tags, *item.aliases)
            if query and not any(query in str(field).casefold() for field in fields):
                continue
            if requested_tags and not requested_tags.issubset({tag.casefold() for tag in item.tags}):
                continue
            result.append(item)
        return result


class LaunchSurface:
    """One independent, user-configurable launch surface instance.

    A surface owns its pages, tiles, presentation state, and settings adapter.
    It shares item definitions through a registry and obtains widget display
    metadata through a catalog adapter. This class intentionally exposes model
    operations rather than drawing ImGui directly.
    """

    WIDGET_ITEM_PREFIX = 'widget:'

    def __init__(
        self,
        surface_id: str,
        registry: LaunchSurfaceRegistry,
        catalog: LaunchCatalogAdapter | None = None,
        settings: LaunchSurfaceSettings | None = None,
        widget_runtime: WidgetRuntimePort | None = None,
        load_settings: bool = True,
    ) -> None:
        """Create a surface with independent state and optional adapters."""

        self.surface_id = _require_identifier(surface_id, 'surface_id')
        self.registry = registry
        self.catalog = catalog or LaunchCatalogAdapter()
        self.settings = settings
        self.widget_runtime = widget_runtime
        self.state = settings.load() if settings is not None and load_settings else LaunchSurfaceState()
        self._last_catalog_revision = self.catalog.get_catalog_revision()

    @classmethod
    def widget_item_id(cls, widget_id: str) -> str:
        """Return the stable launch item ID for a full widget ID."""

        return f'{cls.WIDGET_ITEM_PREFIX}{_require_identifier(widget_id, "widget_id")}'

    def refresh_catalog(self, snapshot: Any | None = None) -> int:
        """Refresh catalog metadata without changing user tile geometry.

        Existing widget tiles remain in place. Missing widget IDs are retained
        as unresolved tiles so a later reload can resolve them again.
        """

        if snapshot is not None:
            self.catalog.set_snapshot(snapshot)
        for metadata in self.catalog.list_widgets():
            item_id = self.widget_item_id(metadata.widget_id)
            definition = self.registry.get(item_id)
            if definition is None:
                definition = self.catalog.definition_for(metadata.widget_id)
                if definition is not None:
                    self.registry.register(definition)
            elif definition.provider_id == 'catalog':
                definition.label = metadata.label
                definition.icon = metadata.icon
                definition.category = metadata.category
                definition.tags = metadata.tags
                definition.aliases = metadata.aliases
                definition.metadata['catalog_enabled'] = metadata.enabled
        self._last_catalog_revision = self.catalog.get_catalog_revision()
        return self._last_catalog_revision

    def add_widget(
        self,
        widget_id: str,
        *,
        page_id: str = 'main',
        tile_id: str | None = None,
        x: int = 0,
        y: int = 0,
        span: tuple[int, int] = (1, 1),
    ) -> LaunchTile:
        """Add a catalog-backed widget toggle to a page.

        The widget must exist in the current catalog or already have a generic
        registry definition. The tile is placed exactly at the requested
        coordinates; no automatic packing is performed.
        """

        widget_id = _require_identifier(widget_id, 'widget_id')
        item_id = self.widget_item_id(widget_id)
        if self.registry.get(item_id) is None:
            definition = self.catalog.definition_for(widget_id)
            if definition is None:
                raise LaunchSurfaceError(f"Widget '{widget_id}' is not available in the current catalog")
            self.registry.register(definition)
        return self.add_item(item_id, page_id=page_id, tile_id=tile_id, x=x, y=y, span=span)

    def add_item(
        self,
        item_id: str,
        *,
        page_id: str = 'main',
        tile_id: str | None = None,
        x: int = 0,
        y: int = 0,
        span: tuple[int, int] | None = None,
        representation: str = 'auto',
        allow_overlap: bool = False,
    ) -> LaunchTile:
        """Place a registered item at explicit coordinates on a page."""

        definition = self.registry.get(item_id)
        if definition is None:
            raise LaunchSurfaceError(f"Launch item '{item_id}' is not registered")
        page = self.state.ensure_page(page_id)
        selected_span = span or definition.preferred_span
        _validate_definition_span(definition, selected_span)
        tile = LaunchTile(
            tile_id=tile_id or self._new_tile_id(item_id, page),
            item_id=item_id,
            x=x,
            y=y,
            column_span=selected_span[0],
            row_span=selected_span[1],
            representation=representation,
        )
        page.add_tile(tile, allow_overlap=allow_overlap)
        return tile

    def remove_tile(self, tile_id: str, page_id: str | None = None) -> bool:
        """Remove a tile from one page or all pages."""

        pages = [self.state.get_page(page_id)] if page_id else self.state.pages
        removed = any(page is not None and page.remove_tile(tile_id) for page in pages)
        if removed:
            self.state.shortcuts.pop(tile_id, None)
            for cluster in self.state.clusters.values():
                cluster.tile_ids = [member_id for member_id in cluster.tile_ids if member_id != tile_id]
        return removed

    def update_tile(self, tile: LaunchTile, page_id: str | None = None, allow_overlap: bool = False) -> None:
        """Update a tile’s position, span, visibility, or representation."""

        page = self.state.get_page(page_id or self.state.active_page)
        if page is None:
            raise LaunchSurfaceError(f"Page '{page_id or self.state.active_page}' does not exist")
        page.update_tile(tile, allow_overlap=allow_overlap)

    def resize_page(self, page_id: str, columns: int, rows: int) -> None:
        """Resize a page without silently moving existing tiles."""

        page = self.state.get_page(page_id)
        if page is None:
            raise LaunchSurfaceError(f"Page '{page_id}' does not exist")
        page.resize_canvas(columns, rows)

    def set_active_page(self, page_id: str) -> None:
        """Select an existing page as the active page."""

        if self.state.get_page(page_id) is None:
            raise LaunchSurfaceError(f"Page '{page_id}' does not exist")
        self.state.active_page = page_id

    def set_profile(self, profile_id: str) -> None:
        """Persist the profile ID used by the host's context projection."""

        self.state.profile_id = str(profile_id).strip()

    def create_page(
        self,
        page_id: str,
        label: str,
        *,
        columns: int = 8,
        rows: int = 4,
        cell_size: float = 40.0,
        gap: float = 4.0,
    ) -> LaunchPage:
        """Create and return an independent page in this surface."""

        page_id = _require_identifier(page_id, 'page_id')
        if self.state.get_page(page_id) is not None:
            raise LaunchSurfaceError(f"Page '{page_id}' already exists")
        page = LaunchPage(page_id, label, columns, rows, cell_size, gap)
        self.state.pages.append(page)
        return page

    def duplicate_page(self, source_page_id: str, new_page_id: str, label: str | None = None) -> LaunchPage:
        """Clone a page's geometry into a new page without sharing tile objects."""

        source = self.state.get_page(source_page_id)
        if source is None:
            raise LaunchSurfaceError(f"Page '{source_page_id}' does not exist")
        if self.state.get_page(new_page_id) is not None:
            raise LaunchSurfaceError(f"Page '{new_page_id}' already exists")
        page = LaunchPage.from_dict({**source.to_dict(), 'page_id': new_page_id, 'label': label or new_page_id})
        self.state.pages.append(page)
        return page

    def remove_page(self, page_id: str, fallback_page_id: str | None = None) -> bool:
        """Remove a page while ensuring one valid active page remains."""

        if len(self.state.pages) <= 1:
            raise LaunchSurfaceError('A surface must retain at least one page')
        page = self.state.get_page(page_id)
        if page is None:
            return False
        remaining = [candidate for candidate in self.state.pages if candidate.page_id != page_id]
        fallback = fallback_page_id or remaining[0].page_id
        if not any(candidate.page_id == fallback for candidate in remaining):
            fallback = remaining[0].page_id
        self.state.pages = remaining
        if self.state.active_page == page_id:
            self.state.active_page = fallback
        return True

    def save_preset(self, preset_id: str, page_ids: Iterable[str] | None = None) -> None:
        """Persist selected page layouts as a named, portable preset."""

        preset_id = _require_identifier(preset_id, 'preset_id')
        selected_ids = set(page_ids) if page_ids is not None else {page.page_id for page in self.state.pages}
        pages = [page.to_dict() for page in self.state.pages if page.page_id in selected_ids]
        if not pages:
            raise LaunchSurfaceError('A layout preset must contain at least one page')
        clusters = {
            cluster_id: cluster.to_dict()
            for cluster_id, cluster in self.state.clusters.items()
            if any(
                tile_data.get('cluster_id') == cluster_id
                for page_data in pages
                for tile_data in page_data.get('tiles', [])
            )
        }
        self.state.layout_presets[preset_id] = {'pages': pages, 'clusters': clusters}

    def apply_preset(self, preset_id: str, *, replace_pages: bool = True) -> None:
        """Apply a saved preset without sharing mutable page or tile objects."""

        preset = self.state.layout_presets.get(preset_id)
        if not isinstance(preset, (list, Mapping)):
            raise LaunchSurfaceError(f"Layout preset '{preset_id}' does not exist")
        preset_pages = preset.get('pages', []) if isinstance(preset, Mapping) else preset
        pages = self._load_preset_pages(preset_pages)
        if not pages:
            raise LaunchSurfaceError(f"Layout preset '{preset_id}' is empty or invalid")
        if replace_pages:
            self.state.pages = pages
            if self.state.get_page(self.state.active_page) is None:
                self.state.active_page = pages[0].page_id
        else:
            for page in pages:
                existing = self.state.get_page(page.page_id)
                if existing is None:
                    self.state.pages.append(page)
                else:
                    self.state.pages[self.state.pages.index(existing)] = page
        if isinstance(preset, Mapping):
            self.state.clusters = self._load_clusters(preset.get('clusters', {}))

    def delete_preset(self, preset_id: str) -> bool:
        """Delete a named layout preset."""

        return self.state.layout_presets.pop(preset_id, None) is not None

    def export_layout(self, page_ids: Iterable[str] | None = None) -> dict[str, Any]:
        """Return a JSON-compatible layout package for explicit import/export."""

        selected_ids = set(page_ids) if page_ids is not None else {page.page_id for page in self.state.pages}
        pages = [page.to_dict() for page in self.state.pages if page.page_id in selected_ids]
        return {
            'schema_version': LaunchSurfaceSettings.SCHEMA_VERSION,
            'surface_id': self.surface_id,
            'active_page': self.state.active_page,
            'pages': pages,
            'shortcuts': json.loads(_json_dumps(self.state.shortcuts)),
            'clusters': json.loads(_json_dumps({key: value.to_dict() for key, value in self.state.clusters.items()})),
        }

    def import_layout(self, data: Mapping[str, Any], *, replace_pages: bool = True) -> None:
        """Import validated page geometry from an exported layout package."""

        pages = self._load_preset_pages(data.get('pages', []))
        if not pages:
            raise LaunchSurfaceError('Layout package contains no valid pages')
        if replace_pages:
            self.state.pages = pages
        else:
            by_id = {page.page_id: page for page in self.state.pages}
            by_id.update({page.page_id: page for page in pages})
            self.state.pages = list(by_id.values())
        active_page = str(data.get('active_page', self.state.active_page))
        if self.state.get_page(active_page) is not None:
            self.state.active_page = active_page
        imported_shortcuts = data.get('shortcuts')
        if isinstance(imported_shortcuts, Mapping):
            self.state.shortcuts.update(
                {str(key): dict(value) for key, value in imported_shortcuts.items() if isinstance(value, Mapping)}
            )
        imported_clusters = data.get('clusters')
        if isinstance(imported_clusters, Mapping):
            self.state.clusters = self._load_clusters(imported_clusters)

    def create_cluster(self, cluster_id: str, label: str, tile_ids: Iterable[str]) -> LaunchCluster:
        """Group existing tiles so they can move or collapse together."""

        cluster_id = _require_identifier(cluster_id, 'cluster_id')
        if cluster_id in self.state.clusters:
            raise LaunchSurfaceError(f"Cluster '{cluster_id}' already exists")
        member_ids = list(dict.fromkeys(str(tile_id) for tile_id in tile_ids))
        if not member_ids:
            raise LaunchSurfaceError('A cluster must contain at least one tile')
        known_tiles = {tile.tile_id for page in self.state.pages for tile in page.tiles}
        missing = [tile_id for tile_id in member_ids if tile_id not in known_tiles]
        if missing:
            raise LaunchSurfaceError(f"Cluster contains unknown tiles: {', '.join(missing)}")
        cluster = LaunchCluster(cluster_id, label, member_ids)
        self.state.clusters[cluster_id] = cluster
        for page in self.state.pages:
            for tile in list(page.tiles):
                if tile.tile_id in member_ids:
                    page.update_tile(replace(tile, cluster_id=cluster_id), allow_overlap=True)
        return cluster

    def remove_cluster(self, cluster_id: str) -> bool:
        """Remove grouping metadata while retaining member tile placement."""

        cluster = self.state.clusters.pop(cluster_id, None)
        if cluster is None:
            return False
        for page in self.state.pages:
            for tile in list(page.tiles):
                if tile.cluster_id == cluster_id:
                    page.update_tile(replace(tile, cluster_id=''), allow_overlap=True)
        return True

    def set_cluster_collapsed(self, cluster_id: str, collapsed: bool) -> None:
        """Set whether a cluster projects only its first member tile."""

        cluster = self.state.clusters.get(cluster_id)
        if cluster is None:
            raise LaunchSurfaceError(f"Cluster '{cluster_id}' does not exist")
        cluster.collapsed = bool(collapsed)

    def move_cluster(self, cluster_id: str, delta_x: int, delta_y: int, page_id: str | None = None) -> None:
        """Move all cluster members atomically by logical grid cells."""

        cluster = self.state.clusters.get(cluster_id)
        if cluster is None:
            raise LaunchSurfaceError(f"Cluster '{cluster_id}' does not exist")
        page = self.state.get_page(page_id or self.state.active_page)
        if page is None:
            raise LaunchSurfaceError(f"Page '{page_id or self.state.active_page}' does not exist")
        members = [tile for tile in page.tiles if tile.tile_id in cluster.tile_ids]
        if len(members) != len(cluster.tile_ids):
            raise LaunchSurfaceError('All cluster members must be on the same page to move as a unit')
        moved = [replace(tile, x=tile.x + int(delta_x), y=tile.y + int(delta_y)) for tile in members]
        probe = LaunchPage(page.page_id, page.label, page.columns, page.rows, page.cell_size, page.gap)
        for tile in page.tiles:
            if tile.tile_id not in cluster.tile_ids:
                probe.add_tile(tile)
        for tile in moved:
            probe.add_tile(tile)
        page.tiles = [
            next((candidate for candidate in moved if candidate.tile_id == tile.tile_id), tile) for tile in page.tiles
        ]

    @staticmethod
    def _load_preset_pages(data: Any) -> list[LaunchPage]:
        """Deserialize page records for presets and import/export operations."""

        return LaunchSurfaceSettings._load_pages(data)

    @staticmethod
    def _load_clusters(data: Any) -> dict[str, LaunchCluster]:
        """Deserialize valid cluster records while skipping malformed entries."""

        if not isinstance(data, Mapping):
            return {}
        clusters: dict[str, LaunchCluster] = {}
        for cluster_id, value in data.items():
            if not isinstance(value, Mapping):
                continue
            try:
                cluster = LaunchCluster.from_dict({**value, 'cluster_id': cluster_id})
            except (TypeError, ValueError, LaunchSurfaceError):
                continue
            clusters[cluster.cluster_id] = cluster
        return clusters

    def renderables(
        self,
        page_id: str | None = None,
        context: LaunchRuntimeContext | None = None,
    ) -> list[LaunchRenderable]:
        """Return only visible occupied tiles and their calculated rectangles.

        This is the boundary used by the visual host. Empty grid cells do
        not appear in the result and therefore cannot consume input.
        """

        page = self.state.get_page(page_id or self.state.active_page)
        if page is None:
            return []
        runtime_context = context or LaunchRuntimeContext()
        result: list[LaunchRenderable] = []
        for tile in sorted(page.tiles, key=lambda value: (value.z_index, value.y, value.x, value.tile_id)):
            if not tile.visible:
                continue
            definition = self.registry.get(tile.item_id)
            if definition is not None and not definition.is_visible(runtime_context):
                continue
            cluster = self.state.clusters.get(tile.cluster_id) if tile.cluster_id else None
            if (
                cluster is not None
                and cluster.collapsed
                and tile.tile_id != (cluster.tile_ids[0] if cluster.tile_ids else '')
            ):
                continue
            available = (
                definition is not None and definition.is_available(runtime_context) and self._item_available(definition)
            )
            enabled = self._tile_enabled(definition)
            status = self._tile_status(definition, runtime_context)
            result.append(
                LaunchRenderable(
                    surface_id=self.surface_id,
                    page_id=page.page_id,
                    tile=tile,
                    definition=definition,
                    tile_rect=page.tile_rect(tile),
                    available=available,
                    enabled=enabled,
                    status=status,
                )
            )
        return result

    def activate(
        self,
        tile_id: str,
        *,
        page_id: str | None = None,
        context: LaunchRuntimeContext | None = None,
    ) -> Any:
        """Activate an item using its declared capability.

        Widget-toggle items are routed through ``WidgetRuntimePort``. Other
        items invoke their registered callback. Embedded components are drawn
        by a host and are not invoked as ordinary actions.
        """

        page = self.state.get_page(page_id or self.state.active_page)
        if page is None:
            raise LaunchSurfaceError(f"Page '{page_id or self.state.active_page}' does not exist")
        tile = page.get_tile(tile_id)
        if tile is None:
            raise LaunchSurfaceError(f"Tile '{tile_id}' does not exist")
        definition = self.registry.get(tile.item_id)
        if definition is None:
            raise LaunchSurfaceError(f"Launch item '{tile.item_id}' is unresolved")
        invocation = LaunchInvocation(
            self.surface_id, page.page_id, tile.tile_id, definition.item_id, context or LaunchRuntimeContext()
        )
        if not definition.is_available(invocation.context) or not self._item_available(definition):
            raise LaunchSurfaceError(f"Launch item '{definition.item_id}' is unavailable in the current context")
        if definition.source_widget_id:
            return self.toggle_widget(definition.source_widget_id)
        if definition.portal_callback is not None:
            return definition.portal_callback(invocation)
        if definition.invoke_callback is not None:
            return definition.invoke_callback(invocation)
        raise LaunchSurfaceError(f"Launch item '{definition.item_id}' has no activation callback")

    def toggle_widget(self, widget_id: str) -> bool:
        """Toggle a widget through the injected runtime adapter.

        Returns the resulting enabled state. A missing runtime adapter is an
        explicit integration error rather than a silent no-op.
        """

        if self.widget_runtime is None:
            raise LaunchSurfaceError('A WidgetRuntimePort is required for widget toggles')
        if self.widget_runtime.is_enabled(widget_id):
            self.widget_runtime.request_disable(widget_id)
            return False
        self.widget_runtime.enable(widget_id)
        return True

    def configure_widget(self, widget_id: str, value: bool = True) -> None:
        """Forward a widget configuration request to the runtime adapter."""

        if self.widget_runtime is None:
            raise LaunchSurfaceError('A WidgetRuntimePort is required for widget configuration')
        self.widget_runtime.set_configuring(widget_id, value)

    def configure_item(
        self,
        tile_id: str,
        *,
        page_id: str | None = None,
        context: LaunchRuntimeContext | None = None,
    ) -> Any:
        """Invoke an item's explicit configure capability."""

        page = self.state.get_page(page_id or self.state.active_page)
        if page is None:
            raise LaunchSurfaceError(f"Page '{page_id or self.state.active_page}' does not exist")
        tile = page.get_tile(tile_id)
        if tile is None:
            raise LaunchSurfaceError(f"Tile '{tile_id}' does not exist")
        definition = self.registry.get(tile.item_id)
        if definition is None or not definition.supports(LaunchCapability.CONFIGURE):
            raise LaunchSurfaceError(f"Launch item '{tile.item_id}' is not configurable")
        runtime_context = context or LaunchRuntimeContext()
        invocation = LaunchInvocation(self.surface_id, page.page_id, tile.tile_id, definition.item_id, runtime_context)
        if definition.source_widget_id:
            self.configure_widget(definition.source_widget_id, True)
            return None
        if definition.configure_callback is None:
            raise LaunchSurfaceError(f"Launch item '{definition.item_id}' has no configure callback")
        return definition.configure_callback(invocation)

    def set_shortcut(self, tile_id: str, key_name: str, modifiers: int = 0) -> None:
        """Assign a persisted key name and modifier bitmask to a tile."""

        self.state.shortcuts[tile_id] = {
            'key': str(key_name),
            'modifiers': int(modifiers),
        }

    def clear_shortcut(self, tile_id: str) -> None:
        """Remove a tile shortcut without removing the tile itself."""

        self.state.shortcuts.pop(tile_id, None)

    def save(self) -> bool:
        """Persist this surface through its composed settings adapter."""

        if self.settings is not None:
            return bool(self.settings.save(self.state))
        return True

    def _tile_enabled(self, definition: LaunchItemDefinition | None) -> bool | None:
        """Resolve the enabled state for a widget-backed tile."""

        if definition is None or not definition.source_widget_id or self.widget_runtime is None:
            return None
        try:
            return bool(self.widget_runtime.is_enabled(definition.source_widget_id))
        except Exception:
            # A persisted tile may outlive a removed widget. Keep the tile
            # renderable as an unresolved/unknown state so the user can repair
            # or remove it from the editor.
            return None

    def _item_available(self, definition: LaunchItemDefinition) -> bool:
        """Return whether a runtime-backed definition still resolves."""

        if not definition.source_widget_id or self.widget_runtime is None:
            return True
        try:
            getter = getattr(self.widget_runtime, 'get', None)
            if callable(getter):
                getter(definition.source_widget_id)
            else:
                # Preserve compatibility with early adapters that only
                # implemented the original enable-state protocol.
                self.widget_runtime.is_enabled(definition.source_widget_id)
            return True
        except Exception:
            return False

    @staticmethod
    def _tile_status(definition: LaunchItemDefinition | None, context: LaunchRuntimeContext) -> Any:
        """Resolve an optional status callback without propagating provider errors."""

        if definition is None or definition.status_callback is None:
            return None
        try:
            return definition.status_callback(context)
        except Exception:
            return None

    def _new_tile_id(self, item_id: str, page: LaunchPage) -> str:
        """Create a stable-enough tile ID unique across this surface."""

        base = item_id.replace(':', '_').replace('/', '_').replace('\\', '_').replace(' ', '_')
        existing = {tile.tile_id for candidate_page in self.state.pages for tile in candidate_page.tiles}
        candidate = base
        index = 2
        while candidate in existing:
            candidate = f'{base}_{index}'
            index += 1
        return candidate


@dataclass(frozen=True)
class LaunchNavigationEntry:
    """One page/surface location in a navigation stack."""

    surface_id: str
    page_id: str


class LaunchSurfaceManager:
    """Optional lifecycle coordinator for multiple independent surfaces."""

    def __init__(self, registry: LaunchSurfaceRegistry) -> None:
        """Create a manager that shares one registry but no surface state."""

        self.registry = registry
        self._surfaces: dict[str, LaunchSurface] = {}
        self._navigation: list[LaunchNavigationEntry] = []

    def add(self, surface: LaunchSurface) -> LaunchSurface:
        """Add a surface, rejecting duplicate surface IDs."""

        if surface.surface_id in self._surfaces:
            raise LaunchSurfaceError(f"Surface '{surface.surface_id}' is already managed")
        self._surfaces[surface.surface_id] = surface
        return surface

    def get(self, surface_id: str) -> LaunchSurface | None:
        """Return a managed surface by ID."""

        return self._surfaces.get(surface_id)

    def remove(self, surface_id: str) -> LaunchSurface | None:
        """Remove and return a surface without touching its settings."""

        removed = self._surfaces.pop(surface_id, None)
        self._navigation = [entry for entry in self._navigation if entry.surface_id != surface_id]
        return removed

    def list_surfaces(self) -> list[LaunchSurface]:
        """Return managed surfaces in stable ID order."""

        return [self._surfaces[key] for key in sorted(self._surfaces)]

    def navigate(self, surface_id: str, page_id: str | None = None, *, replace: bool = False) -> LaunchSurface:
        """Push a surface/page location onto the independent navigation stack."""

        surface = self.get(surface_id)
        if surface is None:
            raise LaunchSurfaceError(f"Surface '{surface_id}' is not managed")
        target_page = page_id or surface.state.active_page
        if surface.state.get_page(target_page) is None:
            raise LaunchSurfaceError(f"Page '{target_page}' does not exist on surface '{surface_id}'")
        entry = LaunchNavigationEntry(surface_id, target_page)
        if replace and self._navigation:
            self._navigation[-1] = entry
        else:
            self._navigation.append(entry)
        surface.set_active_page(target_page)
        return surface

    def back(self) -> LaunchNavigationEntry | None:
        """Pop the current location and return the new location, if any."""

        if len(self._navigation) <= 1:
            return self._navigation[0] if self._navigation else None
        self._navigation.pop()
        entry = self._navigation[-1]
        surface = self.get(entry.surface_id)
        if surface is not None:
            surface.set_active_page(entry.page_id)
        return entry

    def current_location(self) -> LaunchNavigationEntry | None:
        """Return the current navigation location without mutating it."""

        return self._navigation[-1] if self._navigation else None

    def navigation_stack(self) -> tuple[LaunchNavigationEntry, ...]:
        """Return an immutable snapshot of the navigation stack."""

        return tuple(self._navigation)

    def shortcut_conflicts(self) -> list[tuple[tuple[str, int], list[tuple[str, str]]]]:
        """Find duplicate persisted key combinations across managed surfaces."""

        bindings: dict[tuple[str, int], list[tuple[str, str]]] = {}
        for surface in self._surfaces.values():
            for tile_id, binding in surface.state.shortcuts.items():
                key = (str(binding.get('key', 'Unmapped')), int(binding.get('modifiers', 0)))
                if key[0] in {'Unmapped', 'Unused', 'Unmappable', 'VK_0x00'}:
                    continue
                bindings.setdefault(key, []).append((surface.surface_id, str(tile_id)))
        return [(key, owners) for key, owners in sorted(bindings.items()) if len(owners) > 1]


class LaunchSurfaceHotkeys:
    """Synchronize per-tile shortcuts with the shared hotkey manager."""

    def __init__(self, surface: LaunchSurface) -> None:
        """Bind shortcut callbacks to one surface instance."""

        self.surface = surface
        self._registered: set[str] = set()
        self._signature: tuple[tuple[str, str, int], ...] = ()

    def sync(self) -> None:
        """Register changed shortcuts and unregister removed bindings."""

        signature = tuple(
            sorted(
                (
                    str(tile_id),
                    str(binding.get('key', 'Unmapped')),
                    int(binding.get('modifiers', 0)),
                )
                for tile_id, binding in self.surface.state.shortcuts.items()
            )
        )
        if signature == self._signature:
            return

        from Py4GWCoreLib.HotkeyManager import HOTKEY_MANAGER

        for identifier in self._registered:
            HOTKEY_MANAGER.unregister_hotkey(identifier)
        self._registered.clear()
        for tile_id, key_name, modifiers_value in signature:
            try:
                from Py4GWCoreLib.enums_src.IO_enums import Key, ModifierKey

                key = Key[key_name]
                modifiers = ModifierKey(modifiers_value)
            except (KeyError, TypeError, ValueError):
                continue
            if key.name in {'Unmapped', 'Unused', 'Unmappable', 'VK_0x00'}:
                continue
            identifier = self._identifier(tile_id)
            HOTKEY_MANAGER.register_hotkey(
                key=key,
                modifiers=modifiers,
                identifier=identifier,
                name=f'{self.surface.surface_id}:{tile_id}',
                callback=lambda tile_id=tile_id: self._activate_tile(tile_id),
            )
            self._registered.add(identifier)
        self._signature = signature

    def conflicts(self) -> list[tuple[str, str]]:
        """Return configured shortcuts that collide with another registration."""

        from Py4GWCoreLib.HotkeyManager import HOTKEY_MANAGER

        own_identifiers = {self._identifier(tile_id) for tile_id in self.surface.state.shortcuts}
        conflicts: list[tuple[str, str]] = []
        for tile_id, binding in self.surface.state.shortcuts.items():
            key_name = str(binding.get('key', 'Unmapped'))
            modifiers = int(binding.get('modifiers', 0))
            for identifier, hotkey in HOTKEY_MANAGER.hotkeys.items():
                if identifier in own_identifiers:
                    continue
                if hotkey.key.name == key_name and int(hotkey.modifiers) == modifiers:
                    conflicts.append((tile_id, identifier))
        return conflicts

    def dispose(self) -> None:
        """Unregister all bindings owned by this surface."""

        from Py4GWCoreLib.HotkeyManager import HOTKEY_MANAGER

        for identifier in self._registered:
            HOTKEY_MANAGER.unregister_hotkey(identifier)
        self._registered.clear()
        self._signature = ()

    def _activate_tile(self, tile_id: str) -> None:
        """Activate a tile while isolating callback errors from the hotkey loop."""

        try:
            import PyImGui

            if PyImGui.is_any_item_active() or PyImGui.is_any_item_focused():
                return
        except Exception:
            pass
        try:
            self.surface.activate(tile_id)
        except Exception as exc:
            print(f'LaunchSurface shortcut error for {tile_id}: {type(exc).__name__}: {exc}')

    def _identifier(self, tile_id: str) -> str:
        """Return the stable global hotkey registration identifier."""

        return f'LaunchSurface.{self.surface.surface_id}.{tile_id}'


class WidgetHandlerRuntimeAdapter:
    """Bridge the current ``WidgetHandler`` to :class:`WidgetRuntimePort`.

    This adapter is the only Phase 2 code that knows the current handler's
    method names. The launch model continues to use full widget IDs and does
    not import or depend on private handler behavior.
    """

    def __init__(self, handler: Any) -> None:
        """Bind the adapter to the already-created widget handler singleton."""

        self.handler = handler
        self._revision = self._signature()

    def _widget(self, widget_id: str) -> Any:
        """Resolve one full widget ID or raise an integration error."""

        widget = self.handler.get_widget_info(widget_id)
        if widget is None:
            raise LaunchSurfaceError(f"Widget '{widget_id}' is not available")
        return widget

    def get(self, widget_id: str) -> Any:
        """Return the live widget object for diagnostics or adapters."""

        return self._widget(widget_id)

    def is_enabled(self, widget_id: str) -> bool:
        """Return the current enabled state for a full widget ID."""

        return bool(self._widget(widget_id).enabled)

    def enable(self, widget_id: str) -> None:
        """Enable a widget through the handler's persistence-aware API."""

        widget = self._widget(widget_id)
        self.handler.enable_widget(widget.plain_name)

    def request_disable(self, widget_id: str) -> None:
        """Request disablement while preserving system-widget confirmation."""

        widget = self._widget(widget_id)
        request = getattr(self.handler, '_request_disable_widget', None)
        if callable(request):
            request(widget)
        else:
            self.handler.disable_widget(widget.plain_name)

    def set_configuring(self, widget_id: str, value: bool = True) -> None:
        """Set configuration state using the handler's public API."""

        widget = self._widget(widget_id)
        self.handler.set_widget_configuring(widget.plain_name, value)

    def reload_revision(self) -> int:
        """Return a revision that changes when the discovered widget set changes."""

        current = self._signature()
        if current != self._revision:
            self._revision = current
        return hash(self._revision)

    def _signature(self) -> tuple[str, ...]:
        """Build a cheap discovery signature from full widget IDs."""

        return tuple(sorted(str(widget_id) for widget_id in self.handler.widgets))


class LaunchSurfaceImGuiHost:
    """Minimal ImGui host for one :class:`LaunchSurface` instance.

    The host renders only occupied tiles and provides an editor for page size,
    tile coordinates, spans, visibility, and catalog selection. It is kept
    outside the model so the model remains testable without injected ImGui.
    """

    def __init__(
        self,
        surface: LaunchSurface,
        *,
        context_provider: RuntimeContextProvider | None = None,
        navigation_callback: Callable[[str], Any] | None = None,
        frame_anchor: LaunchFrameAnchor | None = None,
    ) -> None:
        """Create a host with editor state owned by this instance."""

        self.surface = surface
        self.editor_open = False
        self.edit_mode = False
        self.search_text = ''
        self.selected_tile_id = ''
        self._position_initialized = False
        self._last_runtime_revision = -1
        self._last_saved_position: tuple[float, float] | None = None
        self._controls_position_initialized = False
        self._component_instances: dict[str, Any] = {}
        self._component_contexts: dict[str, LaunchComponentContext] = {}
        self.hotkeys = LaunchSurfaceHotkeys(surface)
        self.context_provider = context_provider
        self.navigation_callback = navigation_callback
        self.frame_anchor = frame_anchor
        self._runtime_context = LaunchRuntimeContext()
        self._component_tile_ids: set[str] = set()
        self._new_page_id = ''
        self._preset_id = ''
        self._new_cluster_id = ''
        self._surface_dragged_this_frame = False
        self._page_drafts: dict[str, dict[str, float | int]] = {}
        self._editor_message = ''
        self._editor_message_color = (0.45, 0.9, 0.45, 1.0)

    def draw(self) -> None:
        """Draw the launch surface, launcher handle, and optional editor."""

        self._refresh_catalog_if_needed()
        self._runtime_context = self._read_runtime_context()
        self._surface_dragged_this_frame = False
        try:
            self.hotkeys.sync()
        except Exception:
            # Hotkeys are an optional integration. A missing or incomplete
            # runtime binding must not prevent the launch surface from drawing.
            pass
        if not self.surface.state.visible:
            self._draw_launcher_handle()
        else:
            self._draw_surface_window()
        if self.editor_open:
            self._draw_editor_window()

    def _refresh_catalog_if_needed(self) -> None:
        """Refresh catalog metadata after the runtime discovers new widgets."""

        runtime = self.surface.widget_runtime
        if runtime is None:
            return
        revision = runtime.reload_revision()
        if revision == self._last_runtime_revision:
            return
        self._last_runtime_revision = revision
        from Py4GWCoreLib.py4gwcorelib_src.WidgetManager import WidgetCatalog

        self.surface.refresh_catalog(WidgetCatalog.snapshot_from_widgets(runtime.handler.widgets))

    def _draw_launcher_handle(self) -> None:
        """Draw a small reopen button while the surface is hidden."""

        import PyImGui

        flags = (
            PyImGui.WindowFlags.NoTitleBar
            | PyImGui.WindowFlags.NoResize
            | PyImGui.WindowFlags.NoScrollbar
            | PyImGui.WindowFlags.NoScrollWithMouse
            | PyImGui.WindowFlags.NoSavedSettings
        )
        if PyImGui.begin(f'##LaunchSurfaceHandle_{self.surface.surface_id}', flags):
            if PyImGui.button('Launch##launch_surface_handle', 80.0, 28.0):
                self.surface.state.visible = True
                self._position_initialized = False
                self._controls_position_initialized = False
                self.surface.save()
        PyImGui.end()

    def _draw_surface_window(self) -> None:
        """Draw a non-interactive canvas plus independent occupied tile windows."""

        import PyImGui

        page = self.surface.state.get_page(self.surface.state.active_page)
        if page is None:
            return
        window_size = self._page_window_size(page)
        self._apply_window_position(window_size)
        flags = (
            PyImGui.WindowFlags.NoTitleBar
            | PyImGui.WindowFlags.NoBackground
            | PyImGui.WindowFlags.NoMouseInputs
            | PyImGui.WindowFlags.NoScrollbar
            | PyImGui.WindowFlags.NoScrollWithMouse
            | PyImGui.WindowFlags.NoCollapse
            | PyImGui.WindowFlags.NoSavedSettings
        )
        PyImGui.set_next_window_size(window_size, PyImGui.ImGuiCond.Always)
        expanded, open_ = PyImGui.begin_with_close(
            f'##LaunchSurfaceCanvas_{self.surface.surface_id}', self.surface.state.visible, flags
        )
        self.surface.state.visible = bool(open_)
        canvas_position = PyImGui.get_window_pos()
        renderables: list[LaunchRenderable] = []
        if expanded:
            renderables = self.surface.renderables(context=self._runtime_context)
            self._unmount_missing_components({item.tile.tile_id for item in renderables})
        PyImGui.end()
        if not self.surface.state.visible:
            self.surface.save()
            return

        self._draw_surface_controls(canvas_position, window_size)
        for renderable in renderables:
            self._draw_tile_window(renderable, canvas_position)

    def _draw_surface_controls(self, canvas_position: tuple[float, float], window_size: tuple[float, float]) -> None:
        """Draw the only interactive surface-wide region: the compact toolbar."""

        import PyImGui

        toolbar_flags = (
            PyImGui.WindowFlags.NoTitleBar
            | PyImGui.WindowFlags.NoResize
            | PyImGui.WindowFlags.NoScrollbar
            | PyImGui.WindowFlags.NoScrollWithMouse
            | PyImGui.WindowFlags.NoSavedSettings
        )
        if self.surface.state.presentation_mode == LaunchPresentationMode.DOCKED or self.surface.state.locked:
            toolbar_flags |= PyImGui.WindowFlags.NoMove
        position_condition = (
            PyImGui.ImGuiCond.Always if not self._controls_position_initialized else PyImGui.ImGuiCond.Once
        )
        if self.surface.state.presentation_mode == LaunchPresentationMode.DOCKED or self.surface.state.locked:
            position_condition = PyImGui.ImGuiCond.Always
        PyImGui.set_next_window_pos(canvas_position, position_condition)
        PyImGui.set_next_window_size((window_size[0], 36.0), PyImGui.ImGuiCond.Always)
        self._controls_position_initialized = True
        expanded = PyImGui.begin(f'##LaunchSurfaceControls_{self.surface.surface_id}', toolbar_flags)
        if expanded:
            movable = (
                self.surface.state.presentation_mode == LaunchPresentationMode.FLOATING
                and not self.surface.state.locked
            )
            if not movable:
                PyImGui.begin_disabled()
            PyImGui.button('Move##launch_surface_move', 44.0, 22.0)
            if movable and PyImGui.is_item_active() and PyImGui.is_mouse_dragging(0, 4.0):
                self._drag_surface()
            if not movable:
                PyImGui.end_disabled()
            PyImGui.same_line(0.0, 4.0)
            self._draw_surface_toolbar()
            if PyImGui.button('Hide##launch_surface_hide', 48.0, 22.0):
                self.surface.state.visible = False
                self.surface.save()
            if (
                self.surface.state.presentation_mode == LaunchPresentationMode.FLOATING
                and not self.surface.state.locked
                and not self._surface_dragged_this_frame
            ):
                self._capture_floating_position()
        PyImGui.end()

    def _drag_surface(self) -> None:
        """Move a floating surface by screen pixels through the toolbar handle."""

        import PyImGui

        io = PyImGui.get_io()
        window_x, window_y = PyImGui.get_window_pos()
        window_width, window_height = PyImGui.get_window_size()
        delta_x, delta_y = PyImGui.get_mouse_drag_delta(0, 4.0)
        available_x = max(1.0, float(io.display_size_x) - float(window_width))
        available_y = max(1.0, float(io.display_size_y) - float(window_height))
        self.surface.state.floating_x = _clamp((window_x + delta_x) / available_x, 0.0, 1.0)
        self.surface.state.floating_y = _clamp((window_y + delta_y) / available_y, 0.0, 1.0)
        self._last_saved_position = (self.surface.state.floating_x, self.surface.state.floating_y)
        self._surface_dragged_this_frame = True
        self.surface.save()
        PyImGui.reset_mouse_drag_delta(0)

    def _draw_tile_window(self, renderable: LaunchRenderable, canvas_position: tuple[float, float]) -> None:
        """Draw one interactive window exactly over one occupied tile rectangle."""

        import PyImGui

        x, y, width, height = renderable.tile_rect
        flags = (
            PyImGui.WindowFlags.NoTitleBar
            | PyImGui.WindowFlags.NoResize
            | PyImGui.WindowFlags.NoScrollbar
            | PyImGui.WindowFlags.NoScrollWithMouse
            | PyImGui.WindowFlags.NoSavedSettings
            | PyImGui.WindowFlags.NoBackground
        )
        PyImGui.set_next_window_pos((canvas_position[0] + x, canvas_position[1] + 40.0 + y), PyImGui.ImGuiCond.Always)
        PyImGui.set_next_window_size((width, height), PyImGui.ImGuiCond.Always)
        if PyImGui.begin(f'##LaunchSurfaceTile_{self.surface.surface_id}_{renderable.tile.tile_id}', flags):
            # _draw_renderable applies the layout offset to its cursor. Offset
            # it back here because this independent window is already placed
            # at the tile's screen rectangle.
            self._draw_renderable(renderable, -x, -y)
        PyImGui.end()

    def _draw_surface_toolbar(self) -> None:
        """Draw compact controls that do not occupy logical grid slots."""

        import PyImGui

        edit_label = 'Close edit' if self.editor_open else 'Edit'
        if PyImGui.button(f'{edit_label}##launch_surface_edit', 78.0, 22.0):
            self.editor_open = not self.editor_open
            self.edit_mode = self.editor_open
        PyImGui.same_line(0.0, 4.0)
        if PyImGui.button(('Unlock' if self.surface.state.locked else 'Lock') + '##launch_surface_lock', 64.0, 22.0):
            self.surface.state.locked = not self.surface.state.locked
            self._save_with_notice('Surface lock state saved.')
        PyImGui.separator()

    def _draw_renderable(self, renderable: LaunchRenderable, origin_x: float, origin_y: float) -> None:
        """Draw one occupied tile and route interaction to the model."""

        import PyImGui

        tile = renderable.tile
        x, y, width, height = renderable.tile_rect
        PyImGui.set_cursor_pos((origin_x + x, origin_y + y))
        definition = renderable.definition
        label = tile.custom_label or (definition.label if definition is not None else 'Missing item')
        item_id = definition.item_id if definition is not None else tile.item_id

        if self.edit_mode:
            clicked = PyImGui.button(f'{label}##edit_{tile.tile_id}', width, height)
            if clicked:
                self.selected_tile_id = tile.tile_id
                self.editor_open = True
            if PyImGui.is_item_active() and PyImGui.is_mouse_dragging(0, 6.0):
                self._drag_tile(renderable)
            if PyImGui.is_item_hovered():
                self._draw_tooltip(f'{label}\n{tile.column_span}x{tile.row_span} at ({tile.x},{tile.y})')
            return

        if (
            definition is not None
            and definition.supports(LaunchCapability.RENDER)
            and tile.representation not in {'compact', 'portal'}
        ):
            self._draw_component_tile(renderable, origin_x + x, origin_y + y, width, height)
        else:
            clicked = self._draw_action_tile(renderable, label, width, height)
            if clicked:
                try:
                    self.surface.activate(tile.tile_id, context=self._runtime_context)
                except Exception as exc:
                    self._draw_tooltip(f'Activation failed: {exc}')

        if PyImGui.is_item_clicked(1):
            self.selected_tile_id = tile.tile_id
            self.editor_open = True
        if PyImGui.is_item_hovered():
            state_label = 'Unavailable' if not renderable.available else self._state_label(renderable.enabled)
            status = f'\n{renderable.status}' if renderable.status not in (None, '') else ''
            self._draw_tooltip(f'{label}\n{state_label}\n{item_id}{status}')

    def _draw_action_tile(self, renderable: LaunchRenderable, label: str, width: float, height: float) -> bool:
        """Draw an icon-backed or text-backed action tile."""

        import os
        import PyImGui

        definition = renderable.definition
        icon = renderable.tile.custom_icon or (definition.icon if definition is not None else '')
        disabled = not renderable.available
        if icon and os.path.isfile(icon):
            from Py4GWCoreLib._legacy_facade import ImGui_Legacy

            return ImGui_Legacy.image_button(
                f'##launch_{renderable.tile.tile_id}',
                icon,
                width,
                height,
                disabled=disabled,
            )
        visible_label = icon if icon and not icon.startswith('ICON_') else label
        if renderable.status not in (None, '') and width >= 100.0:
            visible_label = f'{visible_label}\n{renderable.status}'
        if width >= 100.0 or height >= 60.0:
            visible_label = f'{visible_label}\n{label}' if visible_label != label else label
        if disabled:
            PyImGui.begin_disabled()
        clicked = PyImGui.button(f'{visible_label}##launch_{renderable.tile.tile_id}', width, height)
        if disabled:
            PyImGui.end_disabled()
        return clicked and not disabled

    def _draw_component_tile(
        self, renderable: LaunchRenderable, x: float, y: float, width: float, height: float
    ) -> None:
        """Draw a registered component or a safe placeholder panel."""

        import PyImGui

        PyImGui.set_cursor_pos((x, y))
        if not PyImGui.begin_child(
            f'##launch_component_{self.surface.surface_id}_{renderable.tile.tile_id}',
            (width, height),
            True,
            PyImGui.WindowFlags.NoScrollbar | PyImGui.WindowFlags.NoScrollWithMouse,
        ):
            PyImGui.end_child()
            return
        definition = renderable.definition
        PyImGui.text(definition.label if definition is not None else 'Missing component')
        if definition is not None and definition.component_factory is not None:
            try:
                context = LaunchComponentContext(
                    surface_id=self.surface.surface_id,
                    page_id=self.surface.state.active_page,
                    tile_id=renderable.tile.tile_id,
                    item_id=definition.item_id,
                    tile_rect=renderable.tile_rect,
                    runtime_context=self._runtime_context,
                    state=self._component_state(definition.item_id),
                    hovered=PyImGui.is_item_hovered(),
                    focused=PyImGui.is_item_focused(),
                    editing=self.edit_mode,
                    invoke_callback=self._invoke_component_item,
                    portal_callback=self._open_component_portal,
                )
                component = self._component_instances.get(renderable.tile.tile_id)
                if component is None:
                    component = definition.component_factory(context)
                    if component is not None:
                        self._component_instances[renderable.tile.tile_id] = component
                        mount = getattr(component, 'on_mount', None)
                        if callable(mount):
                            self._call_component_hook(mount, context)
                self._component_contexts[renderable.tile.tile_id] = context
                if component is not None and hasattr(component, 'draw'):
                    update = getattr(component, 'update', None)
                    if callable(update):
                        self._call_component_hook(update, context)
                    component.draw(context)
                    if context.dirty:
                        self.surface.save()
            except Exception as exc:
                PyImGui.text_wrapped(f'Component error: {exc}')
        else:
            PyImGui.text_disabled('Component registered without a renderer.')
        PyImGui.end_child()

    def _component_state(self, item_id: str) -> dict[str, Any]:
        """Return a mutable, validated state namespace for one component."""

        state = self.surface.state.component_state.get(item_id)
        if not isinstance(state, dict):
            state = {}
            self.surface.state.component_state[item_id] = state
        return state

    def _read_runtime_context(self) -> LaunchRuntimeContext:
        """Read a provider-defined context snapshot without breaking drawing."""

        if self.context_provider is None:
            return LaunchRuntimeContext()
        try:
            context = self.context_provider()
            return context if isinstance(context, LaunchRuntimeContext) else LaunchRuntimeContext(dict(context))
        except Exception:
            return LaunchRuntimeContext()

    def _unmount_missing_components(self, active_tile_ids: set[str]) -> None:
        """Unmount component instances whose visible tiles disappeared."""

        for tile_id in list(self._component_instances):
            if tile_id in active_tile_ids:
                continue
            component = self._component_instances.pop(tile_id)
            context = self._component_contexts.pop(tile_id, None)
            unmount = getattr(component, 'on_unmount', None)
            if callable(unmount):
                self._call_component_hook(unmount, context)

    @staticmethod
    def _call_component_hook(callback: Callable[..., Any], context: LaunchComponentContext | None) -> None:
        """Call lifecycle hooks supporting both context and legacy no-arg forms."""

        if context is not None:
            try:
                callback(context)
                return
            except TypeError:
                pass
        callback()

    def _invoke_component_item(self, item_id: str) -> Any:
        """Route a component's explicit item invocation through this surface."""

        page = self.surface.state.get_page(self.surface.state.active_page)
        if page is None or page.get_tile(item_id) is not None:
            return self.surface.activate(item_id, context=self._runtime_context)
        definition = self.surface.registry.get(item_id)
        if definition is None:
            raise LaunchSurfaceError(f"Launch item '{item_id}' is not registered")
        invocation = LaunchInvocation(
            self.surface.surface_id,
            self.surface.state.active_page,
            f'component:{item_id}',
            item_id,
            self._runtime_context,
        )
        if not definition.is_available(self._runtime_context) or not self.surface._item_available(definition):
            raise LaunchSurfaceError(f"Launch item '{item_id}' is unavailable")
        if definition.invoke_callback is not None:
            return definition.invoke_callback(invocation)
        raise LaunchSurfaceError(f"Launch item '{item_id}' has no invocation callback")

    def _open_component_portal(self, target_id: str) -> Any:
        """Route a component portal request to the host callback."""

        if self.navigation_callback is None:
            raise LaunchSurfaceError('This host has no navigation coordinator')
        return self.navigation_callback(target_id)

    def _draw_editor_window(self) -> None:
        """Draw the complete visual editor for one launch-surface instance."""

        import PyImGui

        page = self.surface.state.get_page(self.surface.state.active_page)
        if page is None:
            return
        PyImGui.set_next_window_size((1180.0, 760.0), PyImGui.ImGuiCond.Once)
        expanded, open_ = PyImGui.begin_with_close(
            f'LaunchSurface Editor##{self.surface.surface_id}',
            self.editor_open,
            PyImGui.WindowFlags.NoSavedSettings,
        )
        self.editor_open = bool(open_)
        self.edit_mode = self.editor_open
        if expanded:
            if self._editor_message:
                PyImGui.text_colored(self._editor_message_color, self._editor_message)
            self._draw_page_navigation(page)
            page = self.surface.state.get_page(self.surface.state.active_page)
            if page is None:
                PyImGui.end()
                return
            self._draw_editor_workspace(page)
        PyImGui.end()

    def _draw_editor_workspace(self, page: LaunchPage) -> None:
        """Draw the grid workspace beside the page and tile inspector panels."""

        import PyImGui

        PyImGui.separator_text('Layout workspace')
        PyImGui.text_disabled('Click a tile to select it. Click an empty slot to move the selected tile there.')
        PyImGui.text_disabled('Drag a tile to move it by grid cells. Empty slots are available placement space.')
        grid_width = min(760.0, max(360.0, page.columns * 48.0 + 24.0))
        workspace_height = 550.0
        PyImGui.text(f'Grid: {page.columns} columns x {page.rows} rows')
        if PyImGui.begin_child(
            f'##launch_editor_grid_{self.surface.surface_id}',
            (grid_width, workspace_height),
            True,
            PyImGui.WindowFlags.HorizontalScrollbar,
        ):
            self._draw_editor_grid(page)
        PyImGui.end_child()
        PyImGui.same_line(0.0, 12.0)
        if PyImGui.begin_child(
            f'##launch_editor_inspector_{self.surface.surface_id}',
            (0.0, workspace_height),
            True,
            0,
        ):
            self._draw_page_editor(page)
            PyImGui.separator()
            self._draw_item_selector(page)
            PyImGui.separator()
            self._draw_tile_editor(page)
        PyImGui.end_child()

    def _draw_editor_grid(self, page: LaunchPage) -> None:
        """Draw every logical slot and every occupied tile in the editor."""

        import PyImGui

        cell_size = 42.0
        gap = 5.0
        step = cell_size + gap
        occupied_cells: dict[tuple[int, int], LaunchTile] = {}
        for tile in page.tiles:
            for row in range(tile.y, tile.y + tile.row_span):
                for column in range(tile.x, tile.x + tile.column_span):
                    occupied_cells[(column, row)] = tile

        for row in range(page.rows):
            for column in range(page.columns):
                tile = occupied_cells.get((column, row))
                if tile is not None and (column, row) != (tile.x, tile.y):
                    continue
                PyImGui.set_cursor_pos((column * step, row * step))
                if tile is None:
                    label = f'+##{self.surface.surface_id}_empty_{column}_{row}'
                    if PyImGui.button(label, cell_size, cell_size):
                        self._place_selected_tile(page, column, row)
                    continue

                definition = self.surface.registry.get(tile.item_id)
                label = tile.custom_label or (definition.label if definition is not None else 'Missing item')
                if not tile.visible:
                    label = f'Hidden\n{label}'
                if tile.tile_id == self.selected_tile_id:
                    label = f'> {label}'
                width = tile.column_span * cell_size + max(0, tile.column_span - 1) * gap
                height = tile.row_span * cell_size + max(0, tile.row_span - 1) * gap
                if PyImGui.button(f'{label}##{self.surface.surface_id}_tile_{tile.tile_id}', width, height):
                    self.selected_tile_id = tile.tile_id
                if PyImGui.is_item_active() and PyImGui.is_mouse_dragging(0, 6.0):
                    self._drag_editor_tile(page, tile, step)
                if PyImGui.is_item_hovered():
                    self._draw_tooltip(f'{label}\n{tile.column_span}x{tile.row_span} at ({tile.x},{tile.y})')

        PyImGui.set_cursor_pos((0.0, page.rows * step + 12.0))
        selected = page.get_tile(self.selected_tile_id) if self.selected_tile_id else None
        if selected is None:
            PyImGui.text_disabled('No tile selected. Empty slots show where a tile can be placed.')
        else:
            PyImGui.text(f'Selected: {selected.tile_id} | {selected.column_span}x{selected.row_span}')

    def _place_selected_tile(self, page: LaunchPage, column: int, row: int) -> None:
        """Move the selected tile to an empty slot when the placement is valid."""

        if not self.selected_tile_id:
            self._set_editor_message('Select a tile before choosing an empty slot.', error=True)
            return
        tile = page.get_tile(self.selected_tile_id)
        if tile is None:
            self._set_editor_message('The selected tile no longer exists.', error=True)
            self.selected_tile_id = ''
            return
        self._move_editor_tile(page, tile, column, row)

    def _drag_editor_tile(self, page: LaunchPage, tile: LaunchTile, step: float) -> None:
        """Move a grid tile according to the active drag delta."""

        import PyImGui

        delta_x, delta_y = PyImGui.get_mouse_drag_delta(0, 6.0)
        target_x = round(tile.x + delta_x / max(1.0, step))
        target_y = round(tile.y + delta_y / max(1.0, step))
        if (target_x, target_y) == (tile.x, tile.y):
            return
        self._move_editor_tile(page, tile, max(0, target_x), max(0, target_y))
        PyImGui.reset_mouse_drag_delta(0)

    def _move_editor_tile(self, page: LaunchPage, tile: LaunchTile, column: int, row: int) -> None:
        """Validate, persist, and report one visual-editor tile move."""

        updated = replace(tile, x=int(column), y=int(row))
        try:
            self.surface.update_tile(updated, page.page_id)
            if self._save_with_notice('Tile position saved.'):
                self.selected_tile_id = tile.tile_id
            else:
                self.surface.update_tile(tile, page.page_id)
        except LaunchLayoutError as exc:
            self._set_editor_message(f'Tile move rejected: {exc}', error=True)

    def _draw_page_navigation(self, page: LaunchPage) -> None:
        """Draw page selection, creation, duplication, and preset controls."""

        import PyImGui

        page_ids = [candidate.page_id for candidate in self.surface.state.pages]
        current_index = page_ids.index(page.page_id)
        selected_index = PyImGui.combo('Active page', current_index, page_ids)
        if 0 <= selected_index < len(page_ids) and selected_index != current_index:
            self.surface.set_active_page(page_ids[selected_index])
            self.selected_tile_id = ''
            self._save_with_notice('Active page saved.')
        self._new_page_id = PyImGui.input_text('New page ID', self._new_page_id)
        if PyImGui.small_button('Create page##launch_create_page'):
            if not self._new_page_id.strip():
                self._set_editor_message('Enter a page ID before creating a page.', error=True)
            else:
                try:
                    created = self.surface.create_page(self._new_page_id.strip(), self._new_page_id.strip())
                    self.surface.set_active_page(created.page_id)
                    self._new_page_id = ''
                    self.selected_tile_id = ''
                    self._save_with_notice('Page created and saved.')
                except LaunchSurfaceError as exc:
                    self._set_editor_message(f'Page creation rejected: {exc}', error=True)
        PyImGui.same_line(0.0, 8.0)
        if PyImGui.small_button('Duplicate page##launch_duplicate_page'):
            try:
                duplicate_id = self._unique_page_id(f'{page.page_id}_copy')
                self.surface.duplicate_page(page.page_id, duplicate_id)
                self.surface.set_active_page(duplicate_id)
                self.selected_tile_id = ''
                self._save_with_notice('Page duplicated and saved.')
            except LaunchSurfaceError as exc:
                self._set_editor_message(f'Page duplication rejected: {exc}', error=True)
        PyImGui.same_line(0.0, 8.0)
        if PyImGui.small_button('Remove page##launch_remove_page'):
            try:
                self.surface.remove_page(page.page_id)
                self.selected_tile_id = ''
                self._save_with_notice('Page removed and saved.')
            except LaunchSurfaceError as exc:
                self._set_editor_message(f'Page removal rejected: {exc}', error=True)

        self._preset_id = PyImGui.input_text('Preset', self._preset_id)
        if PyImGui.small_button('Save preset##launch_save_preset'):
            if not self._preset_id.strip():
                self._set_editor_message('Enter a preset ID before saving a preset.', error=True)
            else:
                try:
                    self.surface.save_preset(self._preset_id.strip())
                    self._save_with_notice('Preset saved.')
                except LaunchSurfaceError as exc:
                    self._set_editor_message(f'Preset could not be saved: {exc}', error=True)
        preset_ids = sorted(self.surface.state.layout_presets)
        if preset_ids:
            selected_preset = min(
                max(0, preset_ids.index(self._preset_id)) if self._preset_id in preset_ids else 0, len(preset_ids) - 1
            )
            selected_preset = PyImGui.combo('Stored preset', selected_preset, preset_ids)
            self._preset_id = preset_ids[selected_preset]
            if PyImGui.small_button('Apply preset##launch_apply_preset'):
                try:
                    self.surface.apply_preset(self._preset_id)
                    self.selected_tile_id = ''
                    self._page_drafts.clear()
                    self._save_with_notice('Preset applied and saved.')
                except LaunchSurfaceError as exc:
                    self._set_editor_message(f'Preset could not be applied: {exc}', error=True)
            PyImGui.same_line(0.0, 8.0)
            if PyImGui.small_button('Delete preset##launch_delete_preset'):
                if self.surface.delete_preset(self._preset_id):
                    self._preset_id = ''
                    self._save_with_notice('Preset deleted.')
                else:
                    self._set_editor_message('Preset no longer exists.', error=True)
        PyImGui.text_disabled('Page edits are staged; use Apply page layout. Other changes auto-save.')
        if PyImGui.small_button('Save now##launch_surface_save_now'):
            self._save_with_notice('Launch Surface settings saved.')

    def _unique_page_id(self, base: str) -> str:
        """Return a page ID not currently used by this surface."""

        candidate = base
        index = 2
        while self.surface.state.get_page(candidate) is not None:
            candidate = f'{base}_{index}'
            index += 1
        return candidate

    def _draw_page_editor(self, page: LaunchPage) -> None:
        """Draw page dimensions and presentation controls."""

        import PyImGui

        PyImGui.text(f'Page: {page.label}')
        draft = self._page_drafts.setdefault(
            page.page_id,
            {
                'columns': page.columns,
                'rows': page.rows,
                'cell_size': page.cell_size,
                'gap': page.gap,
            },
        )
        draft['columns'] = PyImGui.input_int('Width in slots', int(draft['columns']))
        draft['rows'] = PyImGui.input_int('Height in slots', int(draft['rows']))
        draft['cell_size'] = max(16.0, PyImGui.slider_float('Cell size', float(draft['cell_size']), 16.0, 160.0))
        draft['gap'] = max(0.0, PyImGui.slider_float('Cell gap', float(draft['gap']), 0.0, 24.0))
        page_layout_changed = (
            int(draft['columns']) != page.columns
            or int(draft['rows']) != page.rows
            or float(draft['cell_size']) != page.cell_size
            or float(draft['gap']) != page.gap
        )
        if page_layout_changed:
            PyImGui.text_colored((1.0, 0.75, 0.25, 1.0), 'Unsaved page layout changes')
        if PyImGui.button('Apply page layout##launch_apply_page_layout', 180.0, 24.0):
            original_page = page.to_dict()
            try:
                self.surface.resize_page(page.page_id, max(1, int(draft['columns'])), max(1, int(draft['rows'])))
                page.cell_size = float(draft['cell_size'])
                page.gap = float(draft['gap'])
                if self.surface.save():
                    self._page_drafts.pop(page.page_id, None)
                    self._set_editor_message('Page layout applied and saved.')
                else:
                    restored = LaunchPage.from_dict(original_page)
                    self.surface.state.pages[self.surface.state.pages.index(page)] = restored
                    self._set_editor_message(
                        self._settings_error('Page layout changed but could not be saved.'), error=True
                    )
            except LaunchSurfaceError as exc:
                self._set_editor_message(f'Page layout rejected: {exc}', error=True)
        if page_layout_changed:
            PyImGui.same_line(0.0, 8.0)
            if PyImGui.small_button('Discard##launch_discard_page_layout'):
                self._page_drafts.pop(page.page_id, None)
                self._set_editor_message('Pending page layout discarded.')
        modes = [mode.value for mode in LaunchPresentationMode]
        current_mode = modes.index(self.surface.state.presentation_mode.value)
        new_mode = PyImGui.combo('Presentation', current_mode, modes)
        if new_mode != current_mode:
            self.surface.state.presentation_mode = LaunchPresentationMode(modes[new_mode])
            self._position_initialized = False
            self._controls_position_initialized = False
            self._save_with_notice('Presentation mode saved.')
        if self.surface.state.presentation_mode == LaunchPresentationMode.DOCKED:
            edges = [edge.value for edge in LaunchDockEdge]
            current_edge = edges.index(self.surface.state.dock_edge.value)
            new_edge = PyImGui.combo('Dock edge', current_edge, edges)
            if new_edge != current_edge:
                self.surface.state.dock_edge = LaunchDockEdge(edges[new_edge])
                self._position_initialized = False
                self._controls_position_initialized = False
                self._save_with_notice('Dock edge saved.')
            dock_offset = PyImGui.slider_float('Dock offset', self.surface.state.dock_offset, 0.0, 1.0)
            if abs(dock_offset - self.surface.state.dock_offset) > 0.0001:
                self.surface.state.dock_offset = _clamp(float(dock_offset), 0.0, 1.0)
                self._position_initialized = False
                self._controls_position_initialized = False
                self._save_with_notice('Dock offset saved.')

    def _save_with_notice(self, success_message: str = 'Launch Surface settings saved.') -> bool:
        """Flush settings and expose persistence failure in the editor."""

        if self.surface.save():
            self._set_editor_message(success_message)
            return True
        self._set_editor_message(self._settings_error('Launch Surface settings could not be saved.'), error=True)
        return False

    def _settings_error(self, fallback: str) -> str:
        """Return the adapter's concrete save error when available."""

        settings = self.surface.settings
        error = getattr(settings, 'last_save_error', '') if settings is not None else ''
        return error or fallback

    def _set_editor_message(self, message: str, *, error: bool = False) -> None:
        """Set a visible editor status message."""

        self._editor_message = str(message)
        self._editor_message_color = (1.0, 0.4, 0.35, 1.0) if error else (0.45, 0.9, 0.45, 1.0)

    def _draw_item_selector(self, page: LaunchPage) -> None:
        """Show catalog widgets and registered actions that can be added."""

        import PyImGui

        self.search_text = PyImGui.input_text('Search items', self.search_text)
        catalog_items = self.surface.catalog.search(self.search_text)
        definitions = [
            item
            for item in self.surface.registry.list_items()
            if not item.item_id.startswith(LaunchSurface.WIDGET_ITEM_PREFIX)
        ]
        PyImGui.text(f'Available widgets: {len(catalog_items)} | actions: {len(definitions)}')
        if PyImGui.begin_child(f'##launch_item_selector_{self.surface.surface_id}', (520.0, 180.0), True):
            for metadata in catalog_items:
                self._draw_add_row(page, self.surface.widget_item_id(metadata.widget_id), metadata.label)
            for definition in definitions:
                self._draw_add_row(page, definition.item_id, definition.label)
        PyImGui.end_child()

    def _draw_add_row(self, page: LaunchPage, item_id: str, label: str) -> None:
        """Draw one addable item row at the first free location."""

        import PyImGui

        PyImGui.text(label)
        PyImGui.same_line(0.0, 12.0)
        if PyImGui.small_button(f'Add##{item_id}'):
            definition = self.surface.registry.get(item_id)
            if definition is None:
                metadata_id = item_id.removeprefix(LaunchSurface.WIDGET_ITEM_PREFIX)
                definition = self.surface.catalog.definition_for(metadata_id)
                if definition is not None:
                    self.surface.registry.register(definition)
            if definition is not None:
                position = self._find_free_position(page, definition.preferred_span)
                if position is not None:
                    try:
                        tile = self.surface.add_item(
                            item_id,
                            page_id=page.page_id,
                            x=position[0],
                            y=position[1],
                            span=definition.preferred_span,
                        )
                        if self._save_with_notice(f'{label} added and saved.'):
                            self.selected_tile_id = tile.tile_id
                        else:
                            self.surface.remove_tile(tile.tile_id, page.page_id)
                    except LaunchSurfaceError as exc:
                        self._set_editor_message(f'Could not add {label}: {exc}', error=True)
                else:
                    self._set_editor_message(
                        f'No free space for {label} ({definition.preferred_span[0]}x{definition.preferred_span[1]}).',
                        error=True,
                    )

    def _draw_tile_editor(self, page: LaunchPage) -> None:
        """Draw controls for the selected tile's explicit geometry."""

        import PyImGui

        tile = page.get_tile(self.selected_tile_id) if self.selected_tile_id else None
        if tile is None:
            PyImGui.text_disabled('Select a tile from the surface edit mode or add an item.')
            return
        definition = self.surface.registry.get(tile.item_id)
        PyImGui.text(f'Selected: {definition.label if definition else tile.item_id}')
        x = PyImGui.input_int('Tile X', tile.x)
        y = PyImGui.input_int('Tile Y', tile.y)
        width = PyImGui.input_int('Tile width', tile.column_span)
        height = PyImGui.input_int('Tile height', tile.row_span)
        visible = PyImGui.checkbox('Visible', tile.visible)
        custom_label = PyImGui.input_text('Custom label', tile.custom_label)
        custom_icon = PyImGui.input_text('Custom icon path', tile.custom_icon)
        representations = ['auto', 'compact', 'expanded', 'status', 'portal']
        representation_index = (
            representations.index(tile.representation) if tile.representation in representations else 0
        )
        representation = representations[PyImGui.combo('Representation', representation_index, representations)]
        if (x, y, width, height, visible, custom_label, custom_icon, representation) != (
            tile.x,
            tile.y,
            tile.column_span,
            tile.row_span,
            tile.visible,
            tile.custom_label,
            tile.custom_icon,
            tile.representation,
        ):
            updated = replace(
                tile,
                x=max(0, x),
                y=max(0, y),
                column_span=max(1, width),
                row_span=max(1, height),
                visible=visible,
                custom_label=custom_label,
                custom_icon=custom_icon,
                representation=representation,
            )
            try:
                if definition is not None:
                    _validate_definition_span(definition, updated.span)
                self.surface.update_tile(updated, page.page_id)
                if not self._save_with_notice('Tile updated and saved.'):
                    self.surface.update_tile(tile, page.page_id)
            except LaunchSurfaceError as exc:
                self._set_editor_message(f'Tile update rejected: {exc}', error=True)
        if definition is not None and definition.supports(LaunchCapability.CONFIGURE):
            if PyImGui.small_button('Configure source##launch_configure_source'):
                try:
                    self.surface.configure_item(tile.tile_id, context=self._runtime_context)
                except LaunchSurfaceError:
                    self._set_editor_message('The source could not be configured.', error=True)
        self._draw_cluster_editor(tile)
        self._draw_shortcut_editor(tile)
        if PyImGui.button('Remove tile##launch_remove_tile', 120.0, 24.0):
            removed_tile = tile
            previous_binding = self.surface.state.shortcuts.get(tile.tile_id)
            component = self._component_instances.pop(tile.tile_id, None)
            context = self._component_contexts.pop(tile.tile_id, None)
            if component is not None:
                unmount = getattr(component, 'on_unmount', None)
                if callable(unmount):
                    self._call_component_hook(unmount, context)
            self.surface.remove_tile(tile.tile_id, page.page_id)
            self.surface.clear_shortcut(tile.tile_id)
            self.selected_tile_id = ''
            if not self._save_with_notice('Tile removed and settings saved.'):
                page.add_tile(removed_tile)
                self.selected_tile_id = removed_tile.tile_id
                if previous_binding is not None:
                    self.surface.state.shortcuts[removed_tile.tile_id] = previous_binding

    def _draw_cluster_editor(self, tile: LaunchTile) -> None:
        """Expose optional cluster creation, collapse, and group movement."""

        import PyImGui

        cluster = self.surface.state.clusters.get(tile.cluster_id) if tile.cluster_id else None
        if cluster is None:
            self._new_cluster_id = PyImGui.input_text('New cluster ID', self._new_cluster_id)
            if PyImGui.small_button('Create cluster from tile##launch_create_cluster'):
                if not self._new_cluster_id.strip():
                    self._set_editor_message('Enter a cluster ID before creating a cluster.', error=True)
                else:
                    try:
                        cluster_id = self._new_cluster_id.strip()
                        self.surface.create_cluster(cluster_id, cluster_id, [tile.tile_id])
                        self._new_cluster_id = ''
                        self._save_with_notice('Cluster created and saved.')
                    except LaunchSurfaceError as exc:
                        self._set_editor_message(f'Cluster creation rejected: {exc}', error=True)
            return
        PyImGui.text(f'Cluster: {cluster.label} ({len(cluster.tile_ids)} tiles)')
        if PyImGui.small_button(
            ('Expand cluster' if cluster.collapsed else 'Collapse cluster') + '##launch_toggle_cluster'
        ):
            self.surface.set_cluster_collapsed(cluster.cluster_id, not cluster.collapsed)
            self._save_with_notice('Cluster state saved.')
        PyImGui.same_line(0.0, 8.0)
        if PyImGui.small_button('Ungroup##launch_remove_cluster'):
            self.surface.remove_cluster(cluster.cluster_id)
            self._save_with_notice('Cluster removed and saved.')
        for label, delta_x, delta_y in (('←', -1, 0), ('→', 1, 0), ('↑', 0, -1), ('↓', 0, 1)):
            PyImGui.same_line(0.0, 4.0)
            if PyImGui.small_button(f'{label}##launch_move_cluster_{cluster.cluster_id}_{label}'):
                try:
                    self.surface.move_cluster(cluster.cluster_id, delta_x, delta_y)
                    self._save_with_notice('Cluster moved and saved.')
                except LaunchLayoutError as exc:
                    self._set_editor_message(f'Cluster move rejected: {exc}', error=True)

    def _draw_shortcut_editor(self, tile: LaunchTile) -> None:
        """Edit the optional global hotkey assigned to one tile."""

        import PyImGui

        from Py4GWCoreLib._legacy_facade import ImGui_Legacy
        from Py4GWCoreLib.enums_src.IO_enums import Key, ModifierKey

        binding = self.surface.state.shortcuts.get(tile.tile_id, {})
        key_name = str(binding.get('key', 'Unmapped'))
        try:
            key = Key[key_name]
        except KeyError:
            key = Key.Unmapped
        modifiers = ModifierKey(int(binding.get('modifiers', 0)))
        new_key, new_modifiers, changed = ImGui_Legacy.keybinding(
            f'Shortcut##{self.surface.surface_id}_{tile.tile_id}', key, modifiers
        )
        if changed:
            if new_key in (Key.Unmapped, Key.Unused, Key.Unmappable, Key.VK_0x00):
                self.surface.clear_shortcut(tile.tile_id)
            else:
                self.surface.set_shortcut(tile.tile_id, new_key.name, int(new_modifiers))
            if self._save_with_notice('Shortcut saved.'):
                self.hotkeys.sync()
        conflicts = [tile_id for tile_id, _ in self.hotkeys.conflicts() if tile_id == tile.tile_id]
        if conflicts:
            PyImGui.text_colored((1.0, 0.65, 0.2, 1.0), 'Shortcut conflicts with another hotkey.')

    @staticmethod
    def _find_free_position(page: LaunchPage, span: tuple[int, int]) -> tuple[int, int] | None:
        """Find a free editor placement without changing existing tiles."""

        probe = LaunchTile('##probe', '##probe', column_span=span[0], row_span=span[1])
        for y in range(max(0, page.rows - span[1] + 1)):
            for x in range(max(0, page.columns - span[0] + 1)):
                probe.x = x
                probe.y = y
                try:
                    page.validate_tile(probe)
                except LaunchLayoutError:
                    continue
                return x, y
        return None

    def _apply_window_position(self, window_size: tuple[float, float]) -> None:
        """Apply floating or edge-docked position before beginning the window."""

        import PyImGui

        io = PyImGui.get_io()
        display_width = max(1.0, float(io.display_size_x))
        display_height = max(1.0, float(io.display_size_y))
        width, height = window_size
        if self.frame_anchor is not None:
            try:
                anchored_position = self.frame_anchor.position(window_size)
                if anchored_position is not None:
                    PyImGui.set_next_window_pos(anchored_position, PyImGui.ImGuiCond.Always)
                    return
            except Exception:
                pass
        if self.surface.state.presentation_mode == LaunchPresentationMode.DOCKED:
            offset = _clamp(self.surface.state.dock_offset, 0.0, 1.0)
            if self.surface.state.dock_edge == LaunchDockEdge.TOP:
                position = ((display_width - width) * offset, 5.0)
            elif self.surface.state.dock_edge == LaunchDockEdge.BOTTOM:
                position = ((display_width - width) * offset, display_height - height - 5.0)
            elif self.surface.state.dock_edge == LaunchDockEdge.LEFT:
                position = (5.0, (display_height - height) * offset)
            else:
                position = (display_width - width - 5.0, (display_height - height) * offset)
            PyImGui.set_next_window_pos(position, PyImGui.ImGuiCond.Always)
            return
        position = (
            _clamp(self.surface.state.floating_x, 0.0, 1.0) * max(0.0, display_width - width),
            _clamp(self.surface.state.floating_y, 0.0, 1.0) * max(0.0, display_height - height),
        )
        PyImGui.set_next_window_pos(position, PyImGui.ImGuiCond.Always)
        self._position_initialized = True

    def _capture_floating_position(self) -> None:
        """Persist normalized position after a floating window is moved."""

        if self.surface.state.presentation_mode != LaunchPresentationMode.FLOATING or self.surface.state.locked:
            return
        import PyImGui

        io = PyImGui.get_io()
        window_x, window_y = PyImGui.get_window_pos()
        window_width, window_height = PyImGui.get_window_size()
        available_x = max(1.0, float(io.display_size_x) - float(window_width))
        available_y = max(1.0, float(io.display_size_y) - float(window_height))
        position = (_clamp(window_x / available_x, 0.0, 1.0), _clamp(window_y / available_y, 0.0, 1.0))
        if self._last_saved_position is None or any(
            abs(a - b) > 0.002 for a, b in zip(position, self._last_saved_position)
        ):
            self.surface.state.floating_x, self.surface.state.floating_y = position
            self._last_saved_position = position
            self.surface.save()

    def _drag_tile(self, renderable: LaunchRenderable) -> None:
        """Move an edited tile by whole logical cells while it is dragged."""

        import PyImGui

        page = self.surface.state.get_page(renderable.page_id)
        if page is None:
            return
        delta_x, delta_y = PyImGui.get_mouse_drag_delta(0, 6.0)
        step = max(1.0, page.cell_size + page.gap)
        target_x = round(renderable.tile.x + delta_x / step)
        target_y = round(renderable.tile.y + delta_y / step)
        if (target_x, target_y) == (renderable.tile.x, renderable.tile.y):
            return
        updated = replace(renderable.tile, x=max(0, target_x), y=max(0, target_y))
        try:
            self.surface.update_tile(updated, page.page_id)
            if not self.surface.save():
                self.surface.update_tile(renderable.tile, page.page_id)
                self._set_editor_message(self._settings_error('Tile move could not be saved.'), error=True)
            PyImGui.reset_mouse_drag_delta(0)
        except LaunchLayoutError as exc:
            # Keep the last valid position when the drag would leave the page
            # or overlap a neighboring occupied tile.
            self._set_editor_message(f'Tile move rejected: {exc}', error=True)
            PyImGui.reset_mouse_drag_delta(0)

    @staticmethod
    def _page_window_size(page: LaunchPage) -> tuple[float, float]:
        """Calculate the host window size from the logical page dimensions."""

        return (
            page.columns * page.cell_size + max(0, page.columns - 1) * page.gap + 16.0,
            page.rows * page.cell_size + max(0, page.rows - 1) * page.gap + 48.0,
        )

    @staticmethod
    def _state_label(enabled: bool | None) -> str:
        """Format an optional item enabled state for tooltips."""

        if enabled is None:
            return 'Ready'
        return 'Enabled' if enabled else 'Disabled'

    @staticmethod
    def _draw_tooltip(text: str) -> None:
        """Draw a compact tooltip for the last submitted item."""

        import PyImGui

        PyImGui.begin_tooltip()
        PyImGui.text_wrapped(text)
        PyImGui.end_tooltip()


_HOST: LaunchSurfaceImGuiHost | None = None
_HOST_ERROR_REPORTED = False
_HOST_WAIT_REPORTED = False


def _ensure_runtime_host() -> LaunchSurfaceImGuiHost | None:
    """Initialize the current widget runtime and create the testable host.

    This follows the existing ``Py4GW_widget_manager.py`` initialization
    contract: the current global manager settings document is opened first,
    then discovery and saved widget state are applied. The launch surface uses
    its own settings document and never becomes a widget-discovery root.
    """

    global _HOST, _HOST_WAIT_REPORTED
    if _HOST is not None:
        return _HOST

    from Py4GWCoreLib.py4gwcorelib_src.Settings import Settings
    from Py4GWCoreLib.py4gwcorelib_src.WidgetManager import WidgetCatalog, get_widget_handler

    handler = get_widget_handler()
    manager_key = handler.MANAGER_INI_KEY or Settings('Widgets/WidgetManager/WidgetManager.ini', 'global').name
    manager_cfg = Settings.find(manager_key)
    if manager_cfg is None:
        if not _HOST_WAIT_REPORTED:
            _HOST_WAIT_REPORTED = True
            print('LaunchSurface: waiting for Widget Manager settings initialization.')
        return None

    handler.MANAGER_INI_KEY = manager_key
    if not handler.discovered:
        handler.discover()
    if not handler.ini_applied:
        handler.enable_all = manager_cfg.get_bool('Configuration', 'enable_all', True)
        handler._apply_ini_configuration()

    registry = LaunchSurfaceRegistry()
    registry.register_provider('LaunchSurface', _register_core_items)
    registry.register_provider('HeroAI', _register_heroai_actions)
    registry.register_provider('Project', _register_project_items)
    catalog = LaunchCatalogAdapter(WidgetCatalog.snapshot_from_handler(handler))
    runtime = WidgetHandlerRuntimeAdapter(handler)
    surface_document = Settings('Projects/LaunchSurface/main.ini', 'global')
    surface = LaunchSurface(
        surface_id='main',
        registry=registry,
        catalog=catalog,
        settings=LaunchSurfaceSettings(surface_document),
        widget_runtime=runtime,
    )
    surface.refresh_catalog()
    _HOST = LaunchSurfaceImGuiHost(surface, context_provider=_runtime_context)
    return _HOST


class _RuntimeStatusComponent:
    """Small project-owned component demonstrating the embedded contract."""

    def draw(self, context: LaunchComponentContext) -> None:
        """Render current projection values inside its occupied tile."""

        import PyImGui

        PyImGui.text('Runtime status')
        PyImGui.text(f"Map: {context.runtime_context.get('map_type', 'Unknown')}")
        PyImGui.text(f"HeroAI: {'Available' if context.runtime_context.get('heroai_available') else 'Unavailable'}")


def _register_core_items(registry: LaunchSurfaceRegistry) -> None:
    """Register project-owned framework diagnostics and sample components."""

    registry.register_component(
        'launchsurface:runtime_status',
        'Runtime Status',
        lambda _context: _RuntimeStatusComponent(),
        description='Shows the current launch-surface runtime projection.',
        category='LaunchSurface',
        tags=('LaunchSurface', 'Status'),
        preferred_span=(2, 1),
        maximum_span=(8, 4),
    )


def _register_heroai_actions(registry: LaunchSurfaceRegistry) -> None:
    """Expose existing HeroAI commands as optional launch actions.

    The adapter preserves HeroAI's command implementation and only supplies
    launch metadata plus the account-list argument expected by its command
    objects. If HeroAI is unavailable, the launch surface remains usable with
    catalog-backed widget toggles.
    """

    try:
        from HeroAI.commands import HeroAICommands
    except Exception:
        return

    for command_name, command in HeroAICommands().Commands.items():
        if command.is_separator or command.command_function is None:
            continue
        item_id = f'heroai:command/{_slug(command_name)}'
        if registry.get(item_id) is not None:
            continue

        def invoke(_invocation: LaunchInvocation, command=command):
            from Py4GWCoreLib.GlobalCache import GLOBAL_CACHE

            accounts = list(GLOBAL_CACHE.ShMem.GetAllAccountData())
            command(accounts)

        def available(_context: LaunchRuntimeContext, command=command) -> bool:
            try:
                from Py4GWCoreLib.Map import Map

                map_type = 'Explorable' if Map.IsExplorable() else 'Outpost'
                return not command.map_types or map_type in command.map_types
            except Exception:
                return True

        registry.register_action(
            item_id,
            command.name,
            invoke,
            provider_id='HeroAI',
            description=command.description,
            icon=command.icon,
            category='HeroAI',
            tags=('HeroAI', 'Command'),
            availability_callback=available,
        )


def _register_project_items(registry: LaunchSurfaceRegistry) -> None:
    """Load user-owned actions from the root extension module."""

    from LaunchSurface_Providers import register_launch_surface_items

    register_launch_surface_items(registry)


def _runtime_context() -> LaunchRuntimeContext:
    """Build the small context projection used by the default host."""

    values: dict[str, Any] = {}
    try:
        from Py4GWCoreLib.Map import Map

        values['map_is_explorable'] = bool(Map.IsExplorable())
        values['map_type'] = 'Explorable' if values['map_is_explorable'] else 'Outpost'
    except Exception:
        values['map_type'] = 'Unknown'
    try:
        from HeroAI.commands import HeroAICommands

        values['heroai_available'] = bool(HeroAICommands().Commands)
    except Exception:
        values['heroai_available'] = False
    return LaunchRuntimeContext(values)


def _slug(value: str) -> str:
    """Convert a display name into a stable action ID fragment."""

    result = ''.join(character.lower() if character.isalnum() else '_' for character in str(value))
    return '_'.join(part for part in result.split('_') if part) or 'item'


def main() -> None:
    """Initialize and draw the launcher-compatible launch surface host."""

    global _HOST_ERROR_REPORTED
    try:
        host = _ensure_runtime_host()
        if host is not None:
            host.draw()
    except Exception as exc:
        if not _HOST_ERROR_REPORTED:
            _HOST_ERROR_REPORTED = True
            print(f'LaunchSurface host error: {type(exc).__name__}: {exc}')


def _require_identifier(value: str, field_name: str) -> str:
    """Normalize and validate a stable identifier."""

    value = str(value).strip()
    if not value:
        raise LaunchSurfaceError(f'{field_name} cannot be empty')
    return value


def _normalize_strings(values: Iterable[Any]) -> tuple[str, ...]:
    """Normalize and deduplicate string metadata while preserving order."""

    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        if text and text not in seen:
            result.append(text)
            seen.add(text)
    return tuple(result)


def _validate_positive_int(value: int, field_name: str) -> None:
    """Reject non-positive integer dimensions."""

    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise LaunchLayoutError(f'{field_name} must be a positive integer')


def _validate_coordinate(value: int, field_name: str) -> None:
    """Reject negative logical grid coordinates."""

    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise LaunchLayoutError(f'{field_name} must be a non-negative integer')


def _validate_span(span: Sequence[int], field_name: str) -> None:
    """Reject invalid width/height spans."""

    if len(span) != 2:
        raise LaunchLayoutError(f'{field_name} must contain width and height')
    _validate_positive_int(int(span[0]), f'{field_name}.width')
    _validate_positive_int(int(span[1]), f'{field_name}.height')


def _validate_definition_span(definition: LaunchItemDefinition, span: Sequence[int]) -> None:
    """Ensure a tile span is supported by its registered item definition."""

    _validate_span(span, 'tile span')
    if span[0] < definition.minimum_span[0] or span[1] < definition.minimum_span[1]:
        raise LaunchLayoutError(f"Tile span for '{definition.item_id}' is smaller than its minimum span")
    if definition.maximum_span is not None:
        if span[0] > definition.maximum_span[0] or span[1] > definition.maximum_span[1]:
            raise LaunchLayoutError(f"Tile span for '{definition.item_id}' exceeds its maximum span")


def _tiles_overlap(first: LaunchTile, second: LaunchTile) -> bool:
    """Return whether two visible tile rectangles overlap in slot space."""

    return not (
        first.x + first.column_span <= second.x
        or second.x + second.column_span <= first.x
        or first.y + first.row_span <= second.y
        or second.y + second.row_span <= first.y
    )


def _enum_or_default(enum_type: type[Enum], value: str, default: Enum) -> Enum:
    """Parse an enum value while safely falling back for old settings."""

    try:
        return enum_type(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, minimum: float, maximum: float) -> float:
    """Clamp a numeric value to an inclusive range."""

    return max(minimum, min(maximum, float(value)))


def _json_dumps(value: Any) -> str:
    """Serialize JSON deterministically for stable settings writes."""

    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


__all__ = [
    'CatalogWidgetMetadata',
    'LaunchCapability',
    'LaunchCatalogAdapter',
    'LaunchCluster',
    'LaunchComponent',
    'LaunchComponentContext',
    'LaunchDockEdge',
    'LaunchFrameAnchor',
    'LaunchInvocation',
    'LaunchItemDefinition',
    'LaunchLayoutError',
    'LaunchNavigationEntry',
    'LaunchPage',
    'LaunchProfile',
    'LaunchProfileStore',
    'LaunchPresentationMode',
    'LaunchRegistrationError',
    'LaunchRenderable',
    'LaunchRuntimeContext',
    'LaunchSurface',
    'LaunchSurfaceError',
    'LaunchSurfaceManager',
    'LaunchSurfaceRegistry',
    'LaunchSurfaceSettings',
    'LaunchSurfaceState',
    'LaunchTile',
    'LaunchSurfaceHotkeys',
    'LaunchSurfaceImGuiHost',
    'SettingsDocument',
    'WidgetHandlerRuntimeAdapter',
    'WidgetRuntimePort',
    'main',
]
