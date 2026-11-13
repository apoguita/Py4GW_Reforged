"""Account-copy declarations for existing private System Settings values.

This catalog deliberately mirrors the current files, sections, keys, and JSON paths. It is not a
schema and performs no migration; it only identifies the smallest existing persistence surface
owned by each copyable UI item.
"""

from .account_copy import AccountCopySpec
from .account_copy import JsonPathOperation
from .account_copy import SettingsSectionOperation
from .account_copy import register_spec


def _register_native_listeners() -> None:
    from . import model
    from .controller import get_controller

    document = "Widgets/System/System Settings.ini"
    controller = get_controller()
    for category in model.CATALOG:
        for listener in category.listeners:
            setting_id = "listener.%s" % listener.name

            def _build(cat=category, lsn=listener):
                values: dict[str, object] = {lsn.name: controller.is_enabled(lsn)}
                for option in lsn.options:
                    values["%s.%s" % (lsn.name, option.key)] = controller.option_value(lsn, option)
                return (SettingsSectionOperation(document, cat.key, values),)

            register_spec(AccountCopySpec(
                setting_id=setting_id,
                label=listener.label,
                build_operations=_build,
                apply_runtime=controller.reload_account_settings,
                settings_documents=(document,),
            ))


def _register_travel() -> None:
    from .travel_on_character_load.controller import get_controller

    document = "Widgets/System/Travel On Character Load.ini"
    controller = get_controller()

    def _build():
        config = controller.config
        return (SettingsSectionOperation(document, "Travel On Character Load", {
            "travel_on_first_load": config.travel_on_first_load,
            "travel_on_character_switch": config.travel_on_character_switch,
            "destination": config.destination,
            "outpost_id": config.outpost_id,
        }),)

    register_spec(AccountCopySpec(
        setting_id="map.travel_character_load",
        label="Travel On Character Load",
        build_operations=_build,
        apply_runtime=controller.reload_account_settings,
        settings_documents=(document,),
    ))


def _register_title() -> None:
    from .title_on_map_load.controller import get_controller

    document = "Widgets/System/Title On Map Load.ini"
    controller = get_controller()
    register_spec(AccountCopySpec(
        setting_id="map.title_on_load",
        label="Title On Map Load",
        build_operations=lambda: (SettingsSectionOperation(
            document,
            "Title On Map Load",
            {"enabled": controller.config.enabled},
        ),),
        apply_runtime=controller.reload_account_settings,
        settings_documents=(document,),
    ))


def _register_camera() -> None:
    from .camera_smoothing.controller import get_controller

    document = "Widgets/System/Camera Smoothing.ini"
    controller = get_controller()
    register_spec(AccountCopySpec(
        setting_id="camera.disable_smoothing",
        label="Disable Camera Smoothing",
        build_operations=lambda: (SettingsSectionOperation(
            document,
            "Camera",
            {"disable_smoothing": controller.config.disable_smoothing},
        ),),
        apply_runtime=controller.reload_account_settings,
        settings_documents=(document,),
    ))


def _register_window_renamer() -> None:
    from .window_renamer.controller import get_controller

    document = "Widgets/System/Window Renamer.ini"
    controller = get_controller()

    def _build():
        config = controller.config
        return (SettingsSectionOperation(document, "window_renamer", {
            "enabled": config.enabled,
            "display_mode": config.display_mode,
            "fallback_to_character": config.fallback_to_character,
            "append_game_name": config.append_game_name,
            "prefix": config.prefix,
            "suffix": config.suffix,
        }),)

    register_spec(AccountCopySpec(
        setting_id="system.window_renamer",
        label="Window Renamer",
        build_operations=_build,
        apply_runtime=controller.reload_account_settings,
        settings_documents=(document,),
    ))


def _register_map_utilities() -> None:
    from .map_utilities.controller import get_controller

    document = "Widgets/System/Map Utilities.ini"
    controller = get_controller()

    register_spec(AccountCopySpec(
        setting_id="map.vanquish_tracker",
        label="Vanquish Tracker",
        build_operations=lambda: (SettingsSectionOperation(
            document,
            "Map Utilities",
            {"vanquish_enabled": controller.config.vanquish_enabled},
        ),),
        apply_runtime=controller.reload_account_settings,
        settings_documents=(document,),
    ))
    register_spec(AccountCopySpec(
        setting_id="map.instance_timer",
        label="Instance Timer",
        build_operations=lambda: (SettingsSectionOperation(
            document,
            "Map Utilities",
            {
                "instance_timer_enabled": controller.config.instance_timer_enabled,
                "true_instance_timer": controller.config.true_instance_timer,
            },
        ),),
        apply_runtime=controller.reload_account_settings,
        settings_documents=(document,),
    ))
    register_spec(AccountCopySpec(
        setting_id="map.disable_alcohol",
        label="Disable Alcohol Effect",
        build_operations=lambda: (SettingsSectionOperation(
            document,
            "Map Utilities",
            {"disable_alcohol_effect": controller.config.disable_alcohol_effect},
        ),),
        apply_runtime=controller.reload_account_settings,
        settings_documents=(document,),
    ))


def _register_skillbar_plus() -> None:
    from .skillbar_plus.controller import get_controller

    document = "Widgets/System/Skillbar Plus.ini"
    controller = get_controller()

    def _build():
        config = controller.config
        return (
            SettingsSectionOperation(document, "Skillbar", {
                "skillbar_enabled": config.skillbar_enabled,
                "skill_font_size": config.skill_font_size,
                "draw_background": config.draw_background,
                "background_color": config.background_color,
                "near_expiry_color": config.near_expiry_color,
                "near_expiry_threshold": config.near_expiry_threshold,
                "draw_durations": config.draw_durations,
                "duration_font_size": config.duration_font_size,
                "duration_background": config.duration_background,
                "duration_foreground": config.duration_foreground,
                "duration_offset": config.duration_offset,
            }),
            SettingsSectionOperation(document, "Effects", {
                "effects_enabled": config.effects_enabled,
                "font_size": config.effects_font_size,
                "background": config.effects_background,
            }),
            SettingsSectionOperation(document, "Auto Cast", {
                "alt_right_click": config.auto_cast_alt_right_click,
            }),
        )

    register_spec(AccountCopySpec(
        setting_id="skills.skillbar_plus",
        label="Skillbar +",
        build_operations=_build,
        apply_runtime=controller.reload_account_settings,
        settings_documents=(document,),
    ))


def _register_agent_recolor() -> None:
    from .agent_recolor.controller import get_controller

    document = "Widgets/System/Agent Recolor.ini"
    controller = get_controller()
    register_spec(AccountCopySpec(
        setting_id="agents.agent_recolor",
        label="Agent Recolor",
        build_operations=lambda: (SettingsSectionOperation(document, "general", {
            "enabled": controller.master_enabled,
            "agents_on": controller.agents_on,
            "gadgets_on": controller.gadgets_on,
        }),),
        apply_runtime=controller.reload_account_settings,
        settings_documents=(document,),
    ))


def _register_recolor_beacons() -> None:
    from .recolor_beacons import RecolorBeacons
    from .recolor_beacons import store

    ini_document = "Widgets/System/RecolorBeacons.ini"
    outcomes_document = "Widgets/System/RecolorOutcomes.json"
    controller = RecolorBeacons()

    def _build():
        config = controller.persisted
        outcomes = store.load_outcomes()
        return (
            SettingsSectionOperation(ini_document, "general", {
                "enabled": config.enabled,
                "profile": config.filter_set_id,
                "blank_unassigned": config.blank_unassigned,
            }),
            SettingsSectionOperation(ini_document, "beacons", {
                "max_beacons": config.max_beacons,
                "beacon_distance": int(config.beacon_distance),
                "cheap_distant": config.cheap_distant,
                "cheap_distance": int(config.cheap_distance),
            }),
            JsonPathOperation(
                outcomes_document,
                "outcomes",
                {filter_id: outcome.to_dict() for filter_id, outcome in outcomes.items()},
                replace=True,
            ),
        )

    register_spec(AccountCopySpec(
        setting_id="loot.recolor_beacons",
        label="Recolor & Beacons",
        build_operations=_build,
        apply_runtime=controller.reload_account_settings,
        settings_documents=(ini_document,),
        json_documents=(outcomes_document,),
    ))


def _register_bags() -> None:
    from .inventory import get_controller

    document = "Widgets/System/Bags.json"
    controller = get_controller()
    register_spec(AccountCopySpec(
        setting_id="items.bags",
        label="Bags",
        build_operations=lambda: (JsonPathOperation(
            document,
            "settings",
            controller.bag_settings().to_dict(),
            replace=True,
        ),),
        apply_runtime=controller.reload_account_settings,
        json_documents=(document,),
    ))


def _register_identification() -> None:
    from .identification import get_controller
    from .identification import store as identification_store

    document = "Widgets/System/Identification.ini"
    controller = get_controller()

    def _build():
        config = controller.settings()
        filters = identification_store.load_filters()
        filter_sets = identification_store.load_filter_sets()
        return (
            SettingsSectionOperation(document, "general", {
                "enabled": config.enabled,
                "filter_set": config.filter_set_id,
            }),
            SettingsSectionOperation(document, "rarity", {
                "white": config.id_whites,
                "blue": config.id_blues,
                "purple": config.id_purples,
                "gold": config.id_golds,
            }),
            JsonPathOperation(
                identification_store.FILTERS_DOCUMENT,
                "filters",
                [filter_definition.to_dict() for filter_definition in filters],
                replace=True,
            ),
            JsonPathOperation(
                identification_store.FILTERS_DOCUMENT,
                "filter_sets",
                [filter_set.to_dict() for filter_set in filter_sets],
                replace=True,
            ),
        )

    register_spec(AccountCopySpec(
        setting_id="items.identification",
        label="Identification",
        build_operations=_build,
        apply_runtime=controller.reload_account_settings,
        settings_documents=(document,),
        json_documents=(identification_store.FILTERS_DOCUMENT,),
    ))


def _register_salvage() -> None:
    from .salvage import get_controller
    from .salvage import store as salvage_store

    document = "Widgets/System/Salvage.ini"
    controller = get_controller()

    def _build():
        config = controller.settings()
        filters = salvage_store.load_filters()
        filter_sets = salvage_store.load_filter_sets()
        return (
            SettingsSectionOperation(document, "general", {
                "enabled": config.enabled,
                "filter_set": config.filter_set_id,
            }),
            SettingsSectionOperation(document, "rarity", {
                "white": config.salvage_whites,
                "blue": config.salvage_blues,
                "purple": config.salvage_purples,
                "gold": config.salvage_golds,
            }),
            SettingsSectionOperation(document, "actions", {
                "common_materials": config.salvage_common_materials,
                "rare_materials": config.salvage_rare_materials,
                "matching_upgrades": config.salvage_matching_upgrades,
                "auto_confirm_warning": config.auto_confirm_materials_warning,
            }),
            JsonPathOperation(
                salvage_store.FILTERS_DOCUMENT,
                "filters",
                [filter_definition.to_dict() for filter_definition in filters],
                replace=True,
            ),
            JsonPathOperation(
                salvage_store.FILTERS_DOCUMENT,
                "filter_sets",
                [filter_set.to_dict() for filter_set in filter_sets],
                replace=True,
            ),
        )

    register_spec(AccountCopySpec(
        setting_id="items.salvage",
        label="Salvage",
        build_operations=_build,
        apply_runtime=controller.reload_account_settings,
        settings_documents=(document,),
        json_documents=(salvage_store.FILTERS_DOCUMENT,),
    ))


def register_default_specs() -> None:
    _register_native_listeners()
    _register_travel()
    _register_title()
    _register_camera()
    _register_window_renamer()
    _register_map_utilities()
    _register_skillbar_plus()
    _register_agent_recolor()
    _register_recolor_beacons()
    _register_bags()
    _register_identification()
    _register_salvage()
