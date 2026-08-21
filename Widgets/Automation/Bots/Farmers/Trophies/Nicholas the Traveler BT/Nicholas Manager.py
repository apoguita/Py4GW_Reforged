from __future__ import annotations

import importlib.util
import os
import sys

import PyImGui
import PySystem

from Py4GWCoreLib import ImGui, Map, get_texture_for_model
from Py4GWCoreLib.BottingTree import BottingTree
from Py4GWCoreLib.ImGui_src.types import Alignment
from Py4GWCoreLib.py4gwcorelib_src.Color import Color
from Py4GWCoreLib.py4gwcorelib_src.Settings import Settings


def _find_manager_modules_directory() -> str:
    """
    Locate the directory containing the two Nicholas Manager support modules.

    Py4GW compiles launched scripts as <string>, so the folder containing the
    script is not automatically available through __file__ / sys.path.
    """
    projects_root = os.path.abspath(PySystem.Console.get_projects_path())

    required = {
        "NicholasFarmBase.py",
        "NicholasFarms.py",
    }

    # Fast path for the recommended install locations.
    #
    # Support files live in "_modules", which intentionally has NO .widget
    # marker. WidgetManager therefore does not expose NicholasFarmBase.py or
    # NicholasFarms.py as standalone widgets.
    preferred_directories = (
        os.path.join(
            projects_root,
            "Widgets",
            "Automation",
            "Bots",
            "Farmers",
            "Trophies",
            "Nicholas the Traveler",
            "_modules",
        ),
        os.path.join(
            projects_root,
            "Widgets",
            "Automation",
            "Bots",
            "Farmers",
            "Nicholas the Traveler",
            "_modules",
        ),
        os.path.join(
            projects_root,
            "Widgets",
            "Automation",
            "Bots",
            "Farmers",
            "Nicholas",
            "_modules",
        ),

        # Backward-compatible fallbacks for older installations.
        os.path.join(
            projects_root,
            "Widgets",
            "Automation",
            "Bots",
            "Farmers",
            "Trophies",
            "Nicholas the Traveler",
        ),
        os.path.join(
            projects_root,
            "Widgets",
            "Automation",
            "Bots",
            "Farmers",
            "Nicholas the Traveler",
        ),
        os.path.join(
            projects_root,
            "Widgets",
            "Automation",
            "Bots",
            "Farmers",
            "Nicholas",
        ),
    )

    for directory in preferred_directories:
        if os.path.isdir(directory) and required.issubset(set(os.listdir(directory))):
            return directory

    # Fallback: search the project once. Directories that cannot contain Python
    # support modules are pruned to keep startup quick.
    skip_dirs = {
        ".git",
        "__pycache__",
        "Assets",
        "Textures",
        "settings",
    }

    for root, dirs, files in os.walk(projects_root):
        dirs[:] = [
            name
            for name in dirs
            if name not in skip_dirs
        ]

        file_set = set(files)
        if required.issubset(file_set):
            return root

    raise ModuleNotFoundError(
        "Nicholas Manager could not find NicholasFarmBase.py and "
        "NicholasFarms.py. Recommended layout: Nicholas the Traveler/_modules/."
    )


# Resolve the private support package.
_MANAGER_MODULE_DIR = _find_manager_modules_directory()
_MANAGER_WIDGET_DIR = os.path.dirname(_MANAGER_MODULE_DIR)

# Py4GW launches widgets from <string>, so the widget directory is not
# guaranteed to be on sys.path. Add it once, then use ordinary package imports.
if _MANAGER_WIDGET_DIR not in sys.path:
    sys.path.insert(0, _MANAGER_WIDGET_DIR)

from _modules.NicholasFarmBase import (
    build_exchange_steps,
    build_execution_steps,
    check_target_item_count,
    configure_tree,
    reset_prepare_session,
)
from _modules.NicholasFarms import FARMS, FarmDefinition


BOT_NAME = "Nicholas Farm Manager"
MODULE_NAME = BOT_NAME
MODULE_ICON = "Assets\\Textures\\Module_Icons\\Nicholas.png"

MODULE_CATEGORY = "Automation"
MODULE_TAGS = [
    "Nicholas",
    "Nicholas the Traveler",
    "Farm",
]
MODULE_ALIASES = [
    "Nicholas Manager",
    "Nicholas Traveler",
]

MODULE_DESCRIPTION = """Multibox BottingTree manager for Nicholas the Traveler.

Features:
• Selectable Nicholas farm registry with shared BottingTree runtime
• Combined target-item counting across the active multibox party
• Direct, two-map, portal-loop, multi-map route-loop, challenge, dialog and Fissure of Woe farm flows
• Displays the required starting outpost and Map ID for the selected farm
• Uses a random district when travelling to the selected farm outpost on initial setup
• Automatic farming target calculated from the number of accounts that should receive all 5 Gifts
• Optional travel and exchange route to Nicholas when legacy route data is available
• Automatic multibox collector conversion for supported indirect Nicholas items
• MerchantRules is disabled on all active accounts during the current crash-isolation workflow
• One planner step per route waypoint for precise movement-failure recovery
• Map-aware zone transitions prevent old-map waypoints from replaying after zoning
• Shared setup, resign/reset safety and inventory-query logic instead of duplicated code in every farm

Credits:
• Farm paths and Nicholas exchange paths: BubbleTea — migrated/adapted from his original AutoIt Nicholas the Traveler scripts
• Py4GW BottingTree manager architecture and multibox integration: Nicholas Farm Manager project
"""

_SETTINGS_FILE = "Widgets/Automation/Bots/Farmers/Nicholas/Nicholas Farm Manager.ini"
_settings = Settings(_SETTINGS_FILE, "global")

_initialized = False
_selected_index = 0
_loaded_selection = False

botting_tree: BottingTree | None = None
_tree_farm_key = ""

exchange_tree: BottingTree | None = None
_exchange_farm_key = ""

_last_total_count = 0
_last_account_counts: dict[str, int] = {}
_last_account_labels: dict[str, str] = {}


def _get_gift_account_count() -> int:
    """
    Number of accounts for which the user wants the full weekly allocation
    of 5 Gifts of the Traveler.
    """
    return max(
        1,
        int(
            _settings.get_int(
                "Config",
                "GiftAccounts",
                4,
            )
        ),
    )


def _set_gift_account_count(value: int) -> None:
    _settings.set(
        "Config",
        "GiftAccounts",
        max(1, int(value)),
    )


def _target_for_farm(farm: FarmDefinition) -> int:
    """
    Combined farming target for the selected Nicholas trophy.

    items_for_5_gifts is the amount required for ONE account to obtain all
    5 weekly Gifts. The manager multiplies it by the configured account count.
    """
    return max(
        1,
        int(farm.items_for_5_gifts)
        * _get_gift_account_count(),
    )


def _load_selection() -> None:
    global _loaded_selection, _selected_index

    if _loaded_selection:
        return

    saved_key = str(
        _settings.get("Config", "SelectedFarm", "forgotten_seal")
        or "forgotten_seal"
    )

    for index, farm in enumerate(FARMS):
        if farm.key == saved_key:
            _selected_index = index
            break
    else:
        # Prefer Forgotten Seal as the initial migration/default farm.
        for index, farm in enumerate(FARMS):
            if farm.model_id == 459:
                _selected_index = index
                break

    _loaded_selection = True


def selected_farm() -> FarmDefinition:
    _load_selection()
    if not FARMS:
        raise RuntimeError("Nicholas farm registry is empty.")
    return FARMS[max(0, min(int(_selected_index), len(FARMS) - 1))]



# =============================================================================
# Nicholas item texture resolver
# =============================================================================
#
# Py4GWCoreLib.get_texture_for_model() builds one exact filename from the
# canonical ModelID enum member. That is insufficient for some Nicholas items:
#
#   - several item IDs are Enum aliases whose canonical member has another name
#     (e.g. Black Pearl 841 can resolve to MOSS_SPIDER);
#   - several Item Models PNGs intentionally use a dummy / legacy numeric prefix
#     (e.g. 987654321-Maguuma_Spider_Web.png).
#
# Nicholas Manager already knows BOTH the real farming model_id and the item
# name, so resolve UI textures independently without ever changing the model_id
# used for looting, inventory counting or farming logic.

_ITEM_TEXTURE_INDEX_READY = False
_ITEM_TEXTURES_BY_MODEL_ID: dict[int, tuple[str, ...]] = {}
_ITEM_TEXTURES_BY_NAME: dict[str, tuple[str, ...]] = {}


def _normalize_texture_name(value: str) -> str:
    return "".join(
        character.lower()
        for character in str(value or "")
        if character.isalnum()
    )


def _build_item_texture_index() -> None:
    """Index Assets/Textures/Item Models once for the lifetime of the widget."""
    global _ITEM_TEXTURE_INDEX_READY
    global _ITEM_TEXTURES_BY_MODEL_ID
    global _ITEM_TEXTURES_BY_NAME

    if _ITEM_TEXTURE_INDEX_READY:
        return

    by_model_id: dict[int, list[str]] = {}
    by_name: dict[str, list[str]] = {}

    texture_dir = os.path.join(
        os.path.abspath(PySystem.Console.get_projects_path()),
        "Assets",
        "Textures",
        "Item Models",
    )

    try:
        filenames = os.listdir(texture_dir)
    except Exception:
        filenames = []

    for filename in filenames:
        if not str(filename).lower().endswith(".png"):
            continue

        stem = os.path.splitext(str(filename))[0]
        prefix, separator, item_name = stem.partition("-")
        if not separator or not item_name:
            continue

        full_path = os.path.join(texture_dir, filename)

        try:
            numeric_prefix = int(prefix)
        except (TypeError, ValueError):
            numeric_prefix = None

        if numeric_prefix is not None:
            by_model_id.setdefault(numeric_prefix, []).append(full_path)

        normalized_name = _normalize_texture_name(item_name)
        if normalized_name:
            by_name.setdefault(normalized_name, []).append(full_path)

    _ITEM_TEXTURES_BY_MODEL_ID = {
        model_id: tuple(sorted(paths))
        for model_id, paths in by_model_id.items()
    }
    _ITEM_TEXTURES_BY_NAME = {
        name: tuple(sorted(paths))
        for name, paths in by_name.items()
    }
    _ITEM_TEXTURE_INDEX_READY = True


def _farm_texture_name_keys(farm: FarmDefinition) -> tuple[str, ...]:
    """Names that may identify the farmed trophy in Item Models."""
    keys: list[str] = []

    for raw_name in (
        farm.nicholas_item_name,
        farm.name,
    ):
        normalized = _normalize_texture_name(raw_name)
        if normalized and normalized not in keys:
            keys.append(normalized)

    return tuple(keys)


def _best_named_texture(
    candidates: tuple[str, ...],
    name_keys: tuple[str, ...],
) -> str:
    if not candidates:
        return ""

    if len(candidates) == 1:
        return candidates[0]

    # Prefer an exact normalized trophy-name match when several PNGs share
    # the same numeric prefix.
    for path in candidates:
        stem = os.path.splitext(os.path.basename(path))[0]
        _prefix, _separator, item_name = stem.partition("-")
        normalized = _normalize_texture_name(item_name)

        if normalized in name_keys:
            return path

    # Then accept variants such as "..._(trophy)".
    for path in candidates:
        stem = os.path.splitext(os.path.basename(path))[0]
        _prefix, _separator, item_name = stem.partition("-")
        normalized = _normalize_texture_name(item_name)

        if any(
            key and (key in normalized or normalized in key)
            for key in name_keys
        ):
            return path

    # Deterministic final choice when the numeric prefix itself is reliable.
    return candidates[0]


def _resolve_farm_texture(farm: FarmDefinition) -> str:
    """
    Resolve the selected farm icon from Assets/Textures/Item Models.

    Resolution order:
      1. PNG numeric prefix == farm.model_id;
         if several exist, prefer the trophy name.
      2. Exact normalized trophy-name match regardless of PNG numeric prefix.
      3. Existing Py4GWCoreLib.get_texture_for_model() fallback.

    This keeps the REAL farming model_id untouched. For example:
        Maguuma Spider Web farm model_id = 234
        displayed PNG = 987654321-Maguuma_Spider_Web.png
    """
    _build_item_texture_index()

    model_id = int(farm.model_id)
    name_keys = _farm_texture_name_keys(farm)

    by_id = _ITEM_TEXTURES_BY_MODEL_ID.get(model_id, ())
    if by_id:
        return _best_named_texture(by_id, name_keys)

    for key in name_keys:
        by_name = _ITEM_TEXTURES_BY_NAME.get(key, ())
        if by_name:
            return _best_named_texture(by_name, name_keys)

    return get_texture_for_model(model_id)


def _record_count_result(
    total: int,
    counts: dict[str, int],
    labels: dict[str, str],
) -> None:
    global _last_total_count
    global _last_account_counts
    global _last_account_labels

    _last_total_count = int(total)
    _last_account_counts = dict(counts)
    _last_account_labels = dict(labels)


def _clear_count_result() -> None:
    global _last_total_count
    global _last_account_counts
    global _last_account_labels

    _last_total_count = 0
    _last_account_counts = {}
    _last_account_labels = {}


def _stop_active_tree() -> None:
    if botting_tree is not None:
        botting_tree.Stop()


def _count_factory(farm: FarmDefinition):
    return lambda: check_target_item_count(
        farm=farm,
        target_getter=lambda: _target_for_farm(farm),
        result_callback=_record_count_result,
        stop_callback=_stop_active_tree,
    )


def _create_tree_for_farm(farm: FarmDefinition) -> BottingTree:
    holder: dict[str, BottingTree] = {}

    def _get_tree() -> BottingTree:
        return holder["tree"]

    tree = BottingTree.Create(
        BOT_NAME,
        main_routine=build_execution_steps(
            tree_getter=_get_tree,
            farm=farm,
            count_node_factory=_count_factory(farm),
        ),
        routine_name=f"Nicholas_{farm.key}",
        repeat=True,
        multi_account=True,
        auto_loot=True,
        auto_resurrection_scroll=False,
        isolation_enabled=False,
        pause_on_combat=True,
        configure_fn=configure_tree,
    )

    holder["tree"] = tree
    return tree



def _create_exchange_tree_for_farm(farm: FarmDefinition) -> BottingTree:
    return BottingTree.Create(
        f"{BOT_NAME} - Exchange",
        main_routine=build_exchange_steps(farm),
        routine_name=f"NicholasExchange_{farm.key}",
        repeat=False,
        multi_account=True,
        auto_loot=False,
        auto_resurrection_scroll=False,
        isolation_enabled=False,
        pause_on_combat=True,
        configure_fn=configure_tree,
    )


def ensure_exchange_tree() -> BottingTree:
    global exchange_tree, _exchange_farm_key

    farm = selected_farm()

    if (
        exchange_tree is None
        or _exchange_farm_key != farm.key
    ):
        if exchange_tree is not None and exchange_tree.IsStarted():
            return exchange_tree

        exchange_tree = _create_exchange_tree_for_farm(farm)
        _exchange_farm_key = farm.key

    return exchange_tree

def ensure_botting_tree() -> BottingTree:
    global botting_tree, _tree_farm_key

    farm = selected_farm()

    if (
        botting_tree is None
        or _tree_farm_key != farm.key
    ):
        if botting_tree is not None and botting_tree.IsStarted():
            return botting_tree

        botting_tree = _create_tree_for_farm(farm)
        _tree_farm_key = farm.key

    return botting_tree


def _starting_outpost_name(farm: FarmDefinition) -> str:
    """Resolve the required starting outpost name from its MapID."""
    try:
        name = str(Map.GetMapName(int(farm.outpost_map_id)) or "").strip()
    except Exception:
        name = ""

    if not name or name == "Unknown Map ID":
        return f"Unknown outpost (Map ID {farm.outpost_map_id})"

    return name



def _flow_label(farm: FarmDefinition) -> str:
    labels = {
        "direct": "Direct farm + Resign",
        "two_map": "Transit map + farm map + Resign",
        "portal_loop": "Portal reset loop (no Resign each run)",
        "challenge": "Mission / challenge entry",
        "dialog": "NPC dialog entry",
        "fow": "Fissure of Woe entry",
    }
    return labels.get(farm.flow, farm.flow)


def _draw_manager_main_summary() -> None:
    farm = selected_farm()
    gift_accounts = _get_gift_account_count()
    target = _target_for_farm(farm)

    PyImGui.text(f"Farm: {farm.name}")
    PyImGui.text(
        f"Starting outpost: {_starting_outpost_name(farm)} "
        f"(Map ID {farm.outpost_map_id})"
    )
    PyImGui.text(f"Gift accounts: {gift_accounts}")
    PyImGui.text(f"Combined count: {_last_total_count} / {target}")
    PyImGui.text("MerchantRules: OFF on all accounts after Start")


def _draw_config_tab() -> None:
    global _selected_index
    global botting_tree, _tree_farm_key
    global exchange_tree, _exchange_farm_key

    farm = selected_farm()
    tree = ensure_botting_tree()
    ex_tree = ensure_exchange_tree()

    farming = bool(tree.IsStarted())
    exchanging = bool(ex_tree.IsStarted())
    busy = farming or exchanging

    PyImGui.text("Nicholas Farm Selection")
    PyImGui.separator()

    farm_names = [entry.name for entry in FARMS]

    if busy:
        PyImGui.begin_disabled(True)

    new_index = int(
        PyImGui.combo(
            "Farm",
            int(_selected_index),
            farm_names,
        )
    )

    if busy:
        PyImGui.end_disabled()

    if not busy and new_index != _selected_index:
        _selected_index = max(0, min(new_index, len(FARMS) - 1))
        new_farm = selected_farm()

        _settings.set("Config", "SelectedFarm", new_farm.key)
        _clear_count_result()

        botting_tree = None
        _tree_farm_key = ""
        exchange_tree = None
        _exchange_farm_key = ""

        farm = new_farm
        tree = ensure_botting_tree()
        ex_tree = ensure_exchange_tree()

    PyImGui.spacing()
    PyImGui.text("Required starting outpost")
    PyImGui.text(_starting_outpost_name(farm))
    PyImGui.text(f"Map ID: {farm.outpost_map_id}")

    PyImGui.separator()

    gift_accounts = _get_gift_account_count()
    new_gift_accounts = max(
        1,
        int(
            PyImGui.input_int(
                "Accounts to receive 5 Gifts",
                int(gift_accounts),
            )
        ),
    )

    if new_gift_accounts != gift_accounts:
        _set_gift_account_count(new_gift_accounts)
        gift_accounts = new_gift_accounts

    target = _target_for_farm(farm)

    PyImGui.spacing()
    PyImGui.text("Calculated farming target")
    PyImGui.text(
        f"{farm.items_for_5_gifts} {farm.name}"
        f"{'' if farm.items_for_5_gifts == 1 else 's'} per account"
    )
    PyImGui.text(
        f"{gift_accounts} account"
        f"{'' if gift_accounts == 1 else 's'} x {farm.items_for_5_gifts} "
        f"= {target} {farm.name}"
        f"{'' if target == 1 else 's'}"
    )
    PyImGui.text(f"Current total: {_last_total_count} / {target}")

    PyImGui.separator()
    PyImGui.text("Nicholas information")
    PyImGui.text(
        f"{farm.items_for_5_gifts} {farm.name}"
        f"{'' if farm.items_for_5_gifts == 1 else 's'}"
        " required per account for all 5 Gifts of the Traveler."
    )

    if farm.requires_collector_conversion:
        PyImGui.text(
            f"Collector conversion: {farm.name} -> {farm.collector_item_name}"
        )

        if farm.collector_mode in ("town", "inline"):
            PyImGui.text(
                f"Automatic conversion: {farm.collector_exchange_rate} "
                f"{farm.name} -> 1 {farm.collector_item_name}"
            )
            PyImGui.text(
                "The conversion is performed independently on every active account."
            )
        else:
            PyImGui.text(
                "Manual collector conversion required before the Nicholas exchange."
            )
            PyImGui.text(
                "BubbleTea's AutoIt source does not provide a reliable Yajide route."
            )

        PyImGui.text(
            f"Nicholas requests: {farm.nicholas_item_name}"
        )
    else:
        PyImGui.text(
            f"Nicholas requests: {farm.nicholas_item_name}"
        )

    PyImGui.separator()
    PyImGui.text("Nicholas exchange")

    if farm.exchange_available:
        PyImGui.text(
            f"Legacy route: {farm.exchange_source_file}"
        )

        if farming:
            PyImGui.begin_disabled(True)

        if PyImGui.button("Exchange with Nicholas"):
            ex_tree = ensure_exchange_tree()
            if not ex_tree.IsStarted():
                ex_tree.Start()

        if farming:
            PyImGui.end_disabled()

        if exchanging:
            PyImGui.text("Exchange route running...")
    else:
        PyImGui.text(
            "Exchange route unavailable in the legacy AutoIt source."
        )

    PyImGui.separator()
    PyImGui.text(f"Model ID: {farm.model_id}")
    PyImGui.text(f"Flow: {_flow_label(farm)}")
    if busy:
        PyImGui.separator()
        PyImGui.text("Stop the active routine before changing farm.")

    if _last_account_counts:
        PyImGui.separator()
        PyImGui.text("Counts per Account:")

        for email, count in _last_account_counts.items():
            label = _last_account_labels.get(email, email)
            PyImGui.text(f"{label}: {count}")


def _draw_about_tab() -> None:
    PyImGui.text("Nicholas Farm Manager - clean architecture")
    PyImGui.separator()
    PyImGui.text(f"Registered farms: {len(FARMS)}")
    PyImGui.text(f"Nicholas exchange routes: {sum(1 for farm in FARMS if farm.exchange_available)}")
    PyImGui.text("One shared engine handles setup, counting, farming and resets.")
    PyImGui.text("Party setup runs once per manual Start and survives step recovery.")
    PyImGui.text("Farm target is calculated automatically from the configured gift-account count.")
    PyImGui.text("MerchantRules is disabled once on every active account.")
    PyImGui.text("No account isolation.")
    PyImGui.text("Auto inventory handler is disabled while the bot runs.")
    PyImGui.text("3 s safety wait before and after farm map resets.")
    PyImGui.separator()
    PyImGui.text("Special structural flows supported:")
    PyImGui.bullet_text("Two-map transit farms")
    PyImGui.bullet_text("Portal reset loops")
    PyImGui.bullet_text("Mission / challenge entry")
    PyImGui.bullet_text("NPC dialog entry")
    PyImGui.bullet_text("Fissure of Woe entry")



def tooltip():
    # Keep the tooltip compact enough for the Widget Catalog while forcing
    # long bullets/credits to wrap inside the window instead of overflowing.
    PyImGui.set_next_window_size((580, 0))
    PyImGui.begin_tooltip()
    PyImGui.push_text_wrap_pos(550)

    # Title
    title_color = Color(255, 200, 100, 255)
    ImGui.image(MODULE_ICON, (32, 32))
    PyImGui.same_line(0, 10)
    ImGui.push_font("Regular", 20)
    ImGui.text_aligned(
        MODULE_NAME,
        alignment=Alignment.MidLeft,
        color=title_color.color_tuple,
        height=32,
    )
    ImGui.pop_font()

    PyImGui.spacing()
    PyImGui.separator()
    PyImGui.spacing()

    # Description
    PyImGui.text_wrapped(
        "Multibox BottingTree manager for Nicholas the Traveler. "
        "Select a trophy farm and the manager handles party setup, farming, "
        "combined item counting and supported Nicholas exchange routes."
    )
    PyImGui.spacing()

    # Features
    PyImGui.text_colored("Features:", title_color.to_tuple_normalized())
    PyImGui.bullet_text(
        f"{len(FARMS)} Nicholas trophy farms in one manager."
    )
    PyImGui.bullet_text(
        "Combined trophy count across the active multibox party."
    )
    PyImGui.bullet_text(
        "One setting defines how many accounts should receive all 5 weekly Gifts."
    )
    PyImGui.bullet_text(
        "Direct, multi-map, complex portal-loop, challenge, dialog and FoW farm flows."
    )
    PyImGui.bullet_text(
        "Shows the required starting outpost for the selected farm."
    )
    PyImGui.bullet_text(
        "Initial farm travel uses a random district, matching the Shards-style setup."
    )
    PyImGui.bullet_text(
        "Each route waypoint is its own recovery step, with map-aware zone transitions."
    )
    PyImGui.bullet_text(
        "Farm resets resign only when needed; portal loops keep a resign fallback."
    )
    PyImGui.bullet_text(
        "Calculates the farming target automatically from the number of gift accounts."
    )
    PyImGui.bullet_text(
        "Automatic multibox conversion for supported collector-backed trophies."
    )
    PyImGui.bullet_text(
        f"{sum(1 for farm in FARMS if farm.exchange_available)} Nicholas exchange routes available."
    )
    PyImGui.spacing()

    # Credits
    PyImGui.text_colored("Credits:", title_color.to_tuple_normalized())
    PyImGui.bullet_text(
        "Farm and Nicholas exchange paths: BubbleTea - migrated/adapted "
        "from his original AutoIt Nicholas the Traveler scripts."
    )
    PyImGui.bullet_text(
        "BottingTree manager and multibox integration: Sky."
    )

    PyImGui.pop_text_wrap_pos()
    PyImGui.end_tooltip()


def main() -> None:
    global _initialized

    if not _initialized:
        _load_selection()
        ensure_botting_tree()
        _initialized = True

    tree = ensure_botting_tree()

    # The one-time party setup must survive BottingTree named-step restarts,
    # but it must NOT survive a real user Stop -> Start cycle.
    #
    # While stopped, continuously clear the session marker. The Start button is
    # handled by the BottingTree UI later in this frame; on the next frame the
    # tree is already started, so the marker is left intact and Initial Farm
    # Setup runs exactly once for that manual Start.
    if not tree.IsStarted():
        reset_prepare_session(tree)

    tree.tick()

    ex_tree = ensure_exchange_tree()
    ex_tree.tick()

    farm = selected_farm()
    texture = _resolve_farm_texture(farm)

    tree.UI.draw_window(
        icon_path=texture,
        iconwidth=96,
        main_child_dimensions=(470, 380),
        additional_ui=_draw_manager_main_summary,
        extra_tabs=[
            ("Config", _draw_config_tab),
            ("About", _draw_about_tab),
        ],
    )


if __name__ == "__main__":
    main()
