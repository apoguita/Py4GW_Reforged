"""
Preferences section — GW engine preferences via the UIManager typed preference API.

R4 flagged the legacy file as a GOOD template (hand-written, typed Get/Set*Preference wiring)
and this reengineer preserves that intent while moving it onto the DEMO 2.0 contract (build_*
returns cast Blocks; explicit action buttons; per-section dump). NO reflection: the preference
id -> type mapping is the hand-written enum tables below, not discovery.

Data path: ``UIManager.Get*Preference`` / ``Set*Preference`` (PyUIManager preference bindings)
plus ``GetPreferenceOptions`` and ``GetKeyMappings`` / ``SetKeyMappings``.

Coverage — one row per known preference id, grouped by native type:
  * Enum  (UIManager.GetEnumPreference,  EnumPreference):   CharSortOrder, AntiAliasing, Reflections,
    ShaderQuality, ShadowQuality, TerrainQuality, InterfaceSize, FrameLimiter.
  * Int   (UIManager.GetIntPreference,   NumberPreference):  AutoTournPartySort, ChatState, ChatTab,
    DistrictLastVisitedLanguage(2), DistrictLastVisitedNonInternationalLanguage(2), DamageTextSize,
    FullscreenGamma, InventoryBag, TextLanguage, AudioLanguage, ChatFilterLevel, RefreshRate,
    ScreenSizeX/Y, SkillListFilterRarity/SortMethod/ViewMode, SoundQuality, StorageBagPage,
    Territory, TextureQuality, UseBestTextureFiltering, BackgroundVolume, DialogVolume,
    EffectsVolume, MusicVolume, UIVolume, Vote, WindowPosX/Y, WindowSizeX/Y, SealedSeed,
    SealedCount, FieldOfView, CameraRotationSpeed, ScreenBorderless, MasterVolume, ClockMode.
  * Bool  (UIManager.GetBoolPreference,  FlagPreference):    channel flags, ShowTextInSkillFloaters,
    ShowKRGBRatingsInGame, AutoHideUIOnLoginScreen, DoubleClickToInteract, InvertMouseControlOfCamera,
    DisableMouseWalking, AutoCameraInObserveMode, AutoHideUIInObserveMode, RememberAccountName,
    IsWindowed, ShowSpendAttributesButton, ConciseSkillDescriptions, skill-tip toggles,
    MuteWhenGuildWarsIsInBackground, AutoTargetFoes/NPCs, AlwaysShowNearbyNamesPvP,
    FadeDistantNameTags, WaitForVSync, DoubleTapForwardToRunBackwardsToFlip,
    DoNotCloseWindowsOnEscape, ShowMinimapOnWorldMap, OptimizeForStereo,
    UseHighResolutionTexturesInOutposts, EnhancedDrawDistance, WhispersFromFriendsEtcOnly,
    ShowChatTimestamps.
  * String (UIManager.GetStringPreference, StringPreference): Unk1(0), Unk2(1), LastCharacterName(2).
    Ids are driven straight off the StringPreference enum members (verified against the Reforged
    Native GW::Constants::StringPreference and legacy GWCA UIMgr.h) so each label maps to its slot.
  * Key mappings (UIManager.GetKeyMappings) shown as a flat index/value/hex table when the binding
    is available. NOTE: the key-mapping accessor is not yet ported to the Reforged Native backend
    (see Py4GW_Reforged_Native ui_bindings.cpp), so this degrades to an explicit status note there
    instead of a misleading empty table.
Actions: set-preference (Enum/Int/Bool/String) and set-key-mapping (index + value).
"""

import PyImGui

from Py4GWCoreLib.UIManager import UIManager
from Py4GWCoreLib.enums_src.UI_enums import AntiAliasing
from Py4GWCoreLib.enums_src.UI_enums import EnumPreference
from Py4GWCoreLib.enums_src.UI_enums import FlagPreference
from Py4GWCoreLib.enums_src.UI_enums import FrameLimiter
from Py4GWCoreLib.enums_src.UI_enums import InterfaceSize
from Py4GWCoreLib.enums_src.UI_enums import NumberPreference
from Py4GWCoreLib.enums_src.UI_enums import Reflections
from Py4GWCoreLib.enums_src.UI_enums import ShaderQuality
from Py4GWCoreLib.enums_src.UI_enums import ShadowQuality
from Py4GWCoreLib.enums_src.UI_enums import StringPreference
from Py4GWCoreLib.enums_src.UI_enums import TerrainQuality

from . import casts
from . import diagnostics
from . import ui

_SECTION = "Preferences"

# Hand-written type map — the set-preference actions dispatch on this (no reflection).
_TYPES = ["Enum", "Int", "Bool", "String"]
_GETTERS = {
    "Enum": UIManager.GetEnumPreference,
    "Int": UIManager.GetIntPreference,
    "Bool": UIManager.GetBoolPreference,
    "String": UIManager.GetStringPreference,
}
_SETTERS = {
    "Enum": UIManager.SetEnumPreference,
    "Int": UIManager.SetIntPreference,
    "Bool": UIManager.SetBoolPreference,
    "String": UIManager.SetStringPreference,
}

# Value-name tables for enum preferences (typed cast of the raw int -> readable name).
_ENUM_VALUE_TABLES = {
    EnumPreference.AntiAliasing: AntiAliasing,
    EnumPreference.Reflections: Reflections,
    EnumPreference.ShaderQuality: ShaderQuality,
    EnumPreference.ShadowQuality: ShadowQuality,
    EnumPreference.TerrainQuality: TerrainQuality,
    EnumPreference.InterfaceSize: InterfaceSize,
    EnumPreference.FrameLimiter: FrameLimiter,
}


class _State:
    pref_id: int = 0
    type_index: int = 0
    int_value: int = 0
    str_value: str = ""
    keymap_index: int = 0
    keymap_value: int = 0


state = _State()


# ---------------------------------------------------------------------------
# build_* — call typed getters, cast, return blocks (shared by render AND dump)
# ---------------------------------------------------------------------------
def _members(enum_type):
    """Ordered (value, name) pairs for an IntEnum, dropping the internal ``Count`` sentinel."""
    seen = set()
    out = []
    for member in enum_type:
        if member.name == "Count" or member.value in seen:
            continue
        seen.add(member.value)
        out.append((int(member.value), member.name))
    return out


def _enum_block():
    headers = ["ID", "Preference", "Current", "Options"]
    rows = []
    for pref_id, name in _members(EnumPreference):
        current = casts.safe(UIManager.GetEnumPreference, pref_id)
        value_table = _ENUM_VALUE_TABLES.get(EnumPreference(pref_id))
        if value_table is not None and current is not None:
            typed = casts.enum_name(value_table, current)
        else:
            typed = str(current)
        options = casts.safe(UIManager.GetPreferenceOptions, pref_id, default=[]) or []
        rows.append((pref_id, name, typed, str(list(options))))
    return ui.multi_block("Enum Preferences", headers, rows)


def _int_block():
    headers = ["ID", "Preference", "Current"]
    rows = []
    for pref_id, name in _members(NumberPreference):
        current = casts.safe(UIManager.GetIntPreference, pref_id)
        rows.append((pref_id, name, str(current)))
    return ui.multi_block("Int (Number) Preferences", headers, rows)


def _bool_block():
    items = []
    for pref_id, name in _members(FlagPreference):
        value = bool(casts.safe(UIManager.GetBoolPreference, pref_id))
        items.append((f"[0x{pref_id:X}] {name}", value))
    return ui.bool_block("Bool (Flag) Preferences", items)


def _string_block():
    # Iterate the real StringPreference enum members by their actual values (Unk1=0, Unk2=1,
    # LastCharacterName=2). No hand-shifted list — pref_id IS the enum value passed to the getter,
    # so each row's label is bound to the exact slot its value came from.
    headers = ["ID", "Preference", "Value"]
    rows = []
    for pref_id, name in _members(StringPreference):
        current = casts.safe(UIManager.GetStringPreference, pref_id)
        if current is None:
            shown = "<none>"
        elif current == "":
            shown = "<empty>"
        else:
            shown = str(current)
        rows.append((pref_id, name, shown))
    return ui.multi_block("String Preferences", headers, rows)


def _get_key_mappings():
    """Return ``(mappings, error)``.

    ``mappings`` is a ``list[int]`` when the binding is available, or ``None`` when it is not.
    ``GetKeyMappings`` is declared in the stub but is NOT yet ported to the Reforged Native
    backend, so at runtime the call may raise (missing binding) — we surface that explicitly
    rather than letting it collapse into a misleading empty table.
    """
    try:
        result = UIManager.GetKeyMappings()
    except Exception as e:  # noqa: BLE001 - binding is unported on the Reforged Native backend
        return None, f"{type(e).__name__}: {e}"
    if result is None:
        return None, "GetKeyMappings returned None"
    return list(result), None


def _keymap_block():
    mappings, err = _get_key_mappings()
    if mappings is None:
        return ui.text_block(
            "Key Mappings",
            f"Not available: {err} "
            "(GetKeyMappings is not yet ported to the Reforged Native backend).",
        )
    headers = ["Index", "Value", "Hex"]
    rows = [(idx, value, casts.hex_of(value)) for idx, value in enumerate(mappings)]
    return ui.multi_block(f"Key Mappings ({len(mappings)})", headers, rows)


def build_preferences():
    return [
        _enum_block(),
        _int_block(),
        _bool_block(),
        _string_block(),
        _keymap_block(),
    ]


# ---------------------------------------------------------------------------
# Actions — explicit trigger buttons, fired only on click
# ---------------------------------------------------------------------------
def _draw_actions():
    ui.section_header("Set Preference")
    state.pref_id = PyImGui.input_int("Preference ID", state.pref_id)
    PyImGui.push_item_width(160)
    state.type_index = PyImGui.combo("Type", state.type_index, _TYPES)
    PyImGui.pop_item_width()
    ptype = _TYPES[state.type_index] if 0 <= state.type_index < len(_TYPES) else "Enum"
    setter = _SETTERS[ptype]

    if ptype == "String":
        state.str_value = PyImGui.input_text("Value", state.str_value)
        ui.action_button("Set Preference", setter, state.pref_id, state.str_value, key="pref_set")
    elif ptype == "Bool":
        state.int_value = PyImGui.input_int("Value (0/1)", state.int_value)
        ui.action_button("Set Preference", setter, state.pref_id, bool(state.int_value), key="pref_set")
    else:
        state.int_value = PyImGui.input_int("Value", state.int_value)
        ui.action_button("Set Preference", setter, state.pref_id, state.int_value, key="pref_set")

    PyImGui.spacing()
    ui.section_header("Set Key Mapping")
    state.keymap_index = PyImGui.input_int("Key Index", state.keymap_index)
    state.keymap_value = PyImGui.input_int("Key Value", state.keymap_value)
    ui.action_button("Set Key Mapping", _set_key_mapping, state.keymap_index, state.keymap_value, key="keymap_set")


def _set_key_mapping(index, value):
    """Read the current mapping list, overwrite one slot, write it back (explicit action)."""
    mappings, err = _get_key_mappings()
    if mappings is None:
        return f"unavailable: {err}"
    if index < 0 or index >= len(mappings):
        return f"index {index} out of range (len {len(mappings)})"
    mappings[index] = int(value)
    UIManager.SetKeyMappings(mappings)
    return f"set [{index}] = {value}"


# ---------------------------------------------------------------------------
# draw_*_view — uniform section entry point
# ---------------------------------------------------------------------------
def draw_preferences_view() -> None:
    blocks = build_preferences()
    diagnostics.dump_button(_SECTION, blocks)
    PyImGui.separator()
    if PyImGui.begin_tab_bar("PreferencesTabs"):
        if PyImGui.begin_tab_item("Data"):
            ui.draw_blocks(_SECTION, blocks)
            PyImGui.end_tab_item()
        if PyImGui.begin_tab_item("Actions"):
            _draw_actions()
            PyImGui.end_tab_item()
        PyImGui.end_tab_bar()
