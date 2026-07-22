"""System Settings model — the catalog of persistable library options.

Pure data + taxonomy: NO PyImGui, NO PyListeners, NO Settings. It only *describes* the options —
their native listener names, sub-option getter/setter names, defaults and grouping — so the runtime
layer can apply them to the native ``PyListeners`` module and the UI can render them. This mirrors
the layering used by ``map_overlay.model`` / ``launch_bar.model``.

The first surface covered is the native game-event **listeners** (see ``Py4GWCoreLib.Listeners`` and
``include/listeners/listeners.h``): each is a named on/off unit, some exposing extra options as
module-level ``PyListeners`` getters/setters. Adding a new options surface later = add a Category
here (and, if it isn't listener-backed, teach the runtime how to apply it).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class BoolOption:
    """A boolean sub-option of a listener, backed by a ``PyListeners`` get/set pair (by name)."""

    key: str            # persistence sub-key (unique within its listener)
    label: str
    getter: str         # PyListeners module-level function name returning bool
    setter: str         # PyListeners module-level function name taking a bool
    default: bool = False


@dataclass(frozen=True)
class IntOption:
    """An integer sub-option of a listener (rendered as a slider), backed by a get/set pair."""

    key: str
    label: str
    getter: str
    setter: str
    default: int = 0
    min: int = 0
    max: int = 100


@dataclass(frozen=True)
class Listener:
    """One toggleable native listener plus any sub-options it exposes."""

    name: str                    # native listener name (PyListeners enable/disable/is_enabled/set_enabled)
    label: str
    help: str = ""
    default_enabled: bool = False
    options: tuple = ()          # tuple[BoolOption | IntOption, ...]
    infra: bool = False          # True = a data feed other widgets may depend on (toggle with care)


@dataclass(frozen=True)
class Category:
    """A UI group of related listeners (renders as one SidebarWindow group)."""

    key: str                     # stable id (also the persisted section name)
    title: str
    icon: str = ""               # Font Awesome constant NAME (resolved to a glyph by the UI)
    listeners: tuple = ()        # tuple[Listener, ...]


# The whole catalog, grouped for the settings sidebar. Order here is the display order.
CATALOG: "tuple[Category, ...]" = (
    Category(
        key="skills", title="Skills & Casting", icon="ICON_HAT_WIZARD",
        listeners=(
            Listener(
                name="skill_list_filter", label="Skill list filter",
                help="Hide skills in the tome / skill-trainer / skill-capture windows.",
                options=(
                    BoolOption("hide_known_skills", "Hide known skills",
                               "get_hide_known_skills", "set_hide_known_skills"),
                    BoolOption("hide_nonelites_on_capture", "Hide non-elites on capture",
                               "get_hide_nonelites_on_capture", "set_hide_nonelites_on_capture"),
                ),
            ),
            Listener(name="signet_of_capture_limit", label="Signet of Capture cap",
                     help="Clamp the displayed Signet of Capture count to 10 in the skills window."),
            Listener(name="remove_cast_bar_minimum", label="Cast bar for short casts",
                     help="Remove the 1.5s minimum warmup so very short casts still show the cast bar."),
            Listener(name="auto_cancel_ua", label="Auto-cancel Unyielding Aura",
                     help="Drop Unyielding Aura before recasting it."),
        ),
    ),
    Category(
        key="map", title="Map & Missions", icon="ICON_MAP",
        listeners=(
            Listener(name="cinematic_skip", label="Skip cinematics",
                     help="Automatically skip in-game cinematics."),
            Listener(name="auto_return_on_defeat", label="Return to outpost on wipe",
                     help="Return the party to the outpost on a wipe (only when you are the party leader)."),
            Listener(name="keep_current_quest", label="Keep current quest",
                     help="Keep your manually-chosen quest active when the game auto-adds a new one."),
        ),
    ),
    Category(
        key="faction", title="Faction", icon="ICON_HAND_HOLDING",
        listeners=(
            Listener(
                name="faction_warning", label="Faction cap warning",
                help="Warn in the console when earned faction reaches a percentage of the cap in a "
                     "Luxon/Kurzick challenge or elite-area outpost.",
                options=(
                    IntOption("warn_percent", "Warn at %", "get_faction_warn_percent",
                              "set_faction_warn_percent", default=80, min=0, max=100),
                ),
            ),
            Listener(name="faction_donate_skip_name", label="One-click faction donation",
                     help="Prefill the character-name field when donating faction."),
        ),
    ),
    Category(
        key="items", title="Items & Merchants", icon="ICON_COINS",
        listeners=(
            Listener(name="disable_gold_confirmation", label="Skip gold/green sell confirmation",
                     help="Remove the confirmation prompt when selling gold/green items to merchants."),
            Listener(
                name="auto_open_locked_chest", label="Auto-open locked chests",
                help="Auto-send the use-key and/or use-lockpick response at a locked chest.",
                options=(
                    BoolOption("use_key", "Send 'use key'",
                               "get_auto_open_use_key", "set_auto_open_use_key"),
                    BoolOption("use_lockpick", "Send 'use lockpick'",
                               "get_auto_open_use_lockpick", "set_auto_open_use_lockpick"),
                ),
            ),
        ),
    ),
)


def all_listeners() -> "list[Listener]":
    """Flat list of every listener across all categories (display order preserved)."""
    out: "list[Listener]" = []
    for cat in CATALOG:
        out.extend(cat.listeners)
    return out
