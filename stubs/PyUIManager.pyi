"""Type stubs for the embedded PyUIManager module.

Exact counterpart of PYBIND11_EMBEDDED_MODULE(PyUIManager, ...) in
Py4GW_Reforged_Native/src/GW/ui/ui_bindings.cpp.

The binding covers the portion of the legacy UIManager surface that maps onto
the migrated GW::ui native module (frame tree, geometry, preferences, UI
messages, typed widget families, enc-string helpers). Legacy subsystems that
carried their own scanner-resolved procs/hooks/globals (window clones, devtext
hosting, window/dialog title hooks, frame logs, safe-destroy input scrubbing,
frame-list control swarm, key mappings) are NOT ported and are therefore NOT
declared here.
"""

from typing import Any, Dict, List, Optional, Tuple

class UIInteractionCallback:
    # No constructor is exposed by the binding (not constructible from Python);
    # instances only arrive via UIFrame.frame_callbacks.
    callback_address: int
    uictl_context: int
    h0008: int

    def get_address(self) -> int:
        """Retrieve the function pointer address."""
        ...

class FramePosition:
    def __init__(self) -> None: ...

    top: int
    left: int
    bottom: int
    right: int
    content_top: int
    content_left: int
    content_bottom: int
    content_right: int
    unknown: float
    scale_factor: float
    viewport_width: float
    viewport_height: float
    screen_top: float
    screen_left: float
    screen_bottom: float
    screen_right: float
    top_on_screen: int
    left_on_screen: int
    bottom_on_screen: int
    right_on_screen: int
    width_on_screen: int
    height_on_screen: int
    viewport_scale_x: float
    viewport_scale_y: float

class FrameRelation:
    def __init__(self) -> None: ...

    parent_id: int
    field67_0x124: int
    field68_0x128: int
    frame_hash_id: int
    siblings: List[int]

class UIFrame:
    def __init__(self, frame_id: int) -> None: ...

    frame_id: int
    parent_id: int
    frame_hash: int
    frame_layout: int
    visibility_flags: int
    type: int
    template_type: int
    position: FramePosition
    relation: FrameRelation
    frame_callbacks: List[UIInteractionCallback]
    child_offset_id: int
    is_visible: bool
    is_created: bool

    # All extra fields
    field1_0x0: int
    field2_0x4: int

    field3_0xc: int
    field4_0x10: int
    field5_0x14: int

    field7_0x1c: int

    field10_0x28: int
    field11_0x2c: int
    field12_0x30: int
    field13_0x34: int
    field14_0x38: int
    field15_0x3c: int
    field16_0x40: int
    field17_0x44: int
    field18_0x48: int
    field19_0x4c: int
    field20_0x50: int
    field21_0x54: int
    field22_0x58: int
    field23_0x5c: int
    field24_0x60: int
    field24a_0x64: int
    field24b_0x68: int
    field25_0x6c: int
    field26_0x70: int
    field27_0x74: int
    field28_0x78: int
    field29_0x7c: int
    field30_0x80: int
    field31_0x84: List[int]
    field32_0x94: int
    field33_0x98: int
    field34_0x9c: int
    field35_0xa0: int
    field36_0xa4: int

    field40_0xc0: int
    field41_0xc4: int
    field42_0xc8: int
    field43_0xcc: int
    field44_0xd0: int
    field45_0xd4: int

    field63_0x11c: int
    field64_0x120: int
    field65_0x124: int

    field73_0x144: int
    field74_0x148: int
    field75_0x14c: int
    field76_0x150: int
    field77_0x154: int
    field78_0x158: int
    field79_0x15c: int
    field80_0x160: int
    field81_0x164: int
    field82_0x168: int
    field83_0x16c: int
    field84_0x170: int
    field85_0x174: int
    field86_0x178: int
    field87_0x17c: int
    field88_0x180: int
    field89_0x184: int
    field90_0x188: int

    frame_state: int
    field92_0x190: int
    field93_0x194: int
    field94_0x198: int
    field95_0x19c: int
    field96_0x1a0: int
    field97_0x1a4: int
    field98_0x1a8: int

    field100_0x1b0: int
    field101_0x1b4: int
    field102_0x1b8: int
    field103_0x1bc: int
    field104_0x1c0: int
    field105_0x1c4: int

    def get_context(self) -> None:
        """Refresh the cached field snapshot from the live native frame."""
        ...

class UIManager:
    # ---- Global state / language ----
    @staticmethod
    def get_text_language() -> int: ...
    @staticmethod
    def is_world_map_showing() -> bool: ...
    @staticmethod
    def is_ui_drawn() -> bool: ...
    @staticmethod
    def is_shift_screenshot() -> bool: ...

    # ---- Built-in window (WindowID) position/visibility ----
    @staticmethod
    def is_window_visible(window_id: int) -> bool: ...
    @staticmethod
    def get_window_position(window_id: int) -> Optional[Tuple[float, float, float, float]]:
        """Get a built-in window rect as (left, top, right, bottom), or None."""
        ...
    @staticmethod
    def set_window_visible(window_id: int, is_visible: bool) -> bool: ...
    @staticmethod
    def set_open_links(toggle: bool) -> bool: ...
    @staticmethod
    def get_frame_limit() -> int: ...
    @staticmethod
    def set_frame_limit(value: int) -> bool: ...

    # ---- Frame tree traversal / discovery ----
    @staticmethod
    def get_root_frame_id() -> int: ...
    @staticmethod
    def get_frame_array() -> List[int]: ...
    @staticmethod
    def get_frame_id_by_label(label: str) -> int: ...
    @staticmethod
    def get_frame_id_by_hash(hash: int) -> int: ...
    @staticmethod
    def get_hash_by_label(label: str) -> int: ...
    @staticmethod
    def get_child_frame_by_frame_id(parent_frame_id: int, child_offset: int) -> int: ...
    @staticmethod
    def get_child_frame_path_by_frame_id(parent_frame_id: int, child_offsets: List[int]) -> int: ...
    @staticmethod
    def get_child_frame_id(parent_hash: int, child_offsets: List[int]) -> int: ...
    @staticmethod
    def get_child_frame_id_from_name_hash(parent_frame_id: int, name_hash: int) -> int: ...
    @staticmethod
    def get_parent_frame_id(frame_id: int) -> int: ...
    @staticmethod
    def get_parent_frame_id_direct(frame_id: int) -> int: ...
    @staticmethod
    def get_related_frame_id(frame_id: int, relation_kind: int, start_after: int = 0) -> int:
        """Traverses the frame tree by relation kind:
        0=first child, 1=last child, 2=next sibling, 3=prev sibling."""
        ...
    @staticmethod
    def get_first_child_frame_id(parent_frame_id: int) -> int: ...
    @staticmethod
    def get_last_child_frame_id(parent_frame_id: int) -> int: ...
    @staticmethod
    def get_next_child_frame_id(frame_id: int) -> int: ...
    @staticmethod
    def get_prev_child_frame_id(frame_id: int) -> int: ...
    @staticmethod
    def get_item_frame_id(parent_frame_id: int, index: int) -> int: ...
    @staticmethod
    def get_overlay_frame_ids() -> List[int]: ...
    @staticmethod
    def get_popup_frame_ids() -> List[int]: ...
    @staticmethod
    def get_frame_hierarchy() -> List[Tuple[int, int, int, int]]: ...
    @staticmethod
    def get_frame_coords_by_hash(frame_hash: int) -> List[Tuple[int, int]]: ...
    @staticmethod
    def is_ancestor_of_by_frame_id(frame_id: int, ancestor_id: int) -> bool: ...
    @staticmethod
    def frame_exists_by_frame_id(frame_id: int) -> bool: ...
    @staticmethod
    def get_frame_snapshot(frame_id: int) -> Dict[str, Any]:
        """Snapshot of a live frame (replaces the legacy UIFrame class): dict
        with named fields, position (incl. on-screen coords) and relation."""
        ...

    # ---- Frame metadata / geometry ----
    @staticmethod
    def get_frame_context(frame_id: int) -> int: ...
    @staticmethod
    def get_frame_layer_by_frame_id(frame_id: int) -> int: ...
    @staticmethod
    def set_frame_layer_by_frame_id(frame_id: int, layer: int) -> bool: ...
    @staticmethod
    def get_frame_code_by_frame_id(frame_id: int) -> int: ...
    @staticmethod
    def get_frame_min_size_by_frame_id(frame_id: int) -> Tuple[float, float]: ...
    @staticmethod
    def get_frame_client_border_by_frame_id(frame_id: int) -> Tuple[float, float, float, float]: ...
    @staticmethod
    def get_frame_clip_rect_by_frame_id(frame_id: int) -> Tuple[float, float, float, float]: ...
    @staticmethod
    def get_frame_position_ex_by_frame_id(frame_id: int) -> Tuple[float, float, float, float, int]: ...
    @staticmethod
    def get_frame_native_size_by_frame_id(frame_id: int) -> Tuple[float, float]: ...
    @staticmethod
    def get_frame_title_by_frame_id(frame_id: int) -> str: ...
    @staticmethod
    def get_frame_label_by_frame_id(frame_id: int) -> str: ...
    @staticmethod
    def get_frame_user_param_by_frame_id(frame_id: int) -> int: ...
    @staticmethod
    def get_frame_state_bit_by_frame_id(frame_id: int, bit: int) -> bool: ...
    @staticmethod
    def get_frame_opacity_by_frame_id(frame_id: int) -> float: ...

    # ---- Frame state setters ----
    @staticmethod
    def set_frame_visible_by_frame_id(frame_id: int, is_visible: bool) -> bool: ...
    @staticmethod
    def set_frame_disabled_by_frame_id(frame_id: int, is_disabled: bool) -> bool: ...
    @staticmethod
    def set_frame_opacity_by_frame_id(frame_id: int, opacity: float, fade_time: float = 0.0) -> bool: ...
    @staticmethod
    def show_frame_by_frame_id(frame_id: int, show: bool) -> bool: ...
    @staticmethod
    def trigger_frame_redraw_by_frame_id(frame_id: int) -> bool: ...
    @staticmethod
    def add_frame_ui_interaction_callback_by_frame_id(
        frame_id: int,
        callback_address: int,
        wparam: int = 0,
    ) -> bool: ...
    @staticmethod
    def destroy_ui_component_by_frame_id(frame_id: int) -> bool: ...

    # ---- Preferences ----
    @staticmethod
    def get_preference_options(pref: int) -> List[int]: ...
    @staticmethod
    def get_enum_preference(pref: int) -> int: ...
    @staticmethod
    def get_int_preference(pref: int) -> int: ...
    @staticmethod
    def get_bool_preference(pref: int) -> bool: ...
    @staticmethod
    def get_string_preference(pref: int) -> str: ...
    @staticmethod
    def set_enum_preference(pref: int, value: int) -> bool: ...
    @staticmethod
    def set_int_preference(pref: int, value: int) -> bool: ...
    @staticmethod
    def set_bool_preference(pref: int, value: bool) -> bool: ...
    @staticmethod
    def set_string_preference(pref: int, value: str) -> bool: ...

    # ---- UI messages / input ----
    @staticmethod
    def SendUIMessage(msgid: int, values: List[int], skip_hooks: bool = False) -> bool: ...
    @staticmethod
    def SendUIMessageRaw(msgid: int, wparam: int, lparam: int = 0, skip_hooks: bool = False) -> bool: ...
    @staticmethod
    def SendFrameUIMessage(frame_id: int, message_id: int, wparam: int, lparam: int = 0) -> bool: ...
    @staticmethod
    def SendFrameUIMessageWString(frame_id: int, message_id: int, text: str) -> bool: ...
    @staticmethod
    def button_click(frame_id: int) -> bool: ...
    @staticmethod
    def button_double_click(frame_id: int) -> bool: ...
    @staticmethod
    def test_mouse_action(frame_id: int, current_state: int, wparam: int = 0, lparam: int = 0) -> bool: ...
    @staticmethod
    def test_mouse_click_action(frame_id: int, current_state: int, wparam: int = 0, lparam: int = 0) -> bool: ...
    @staticmethod
    def key_down(key: int, frame_id: int = 0) -> bool: ...
    @staticmethod
    def key_up(key: int, frame_id: int = 0) -> bool: ...
    @staticmethod
    def key_press(key: int, frame_id: int = 0) -> bool: ...

    # ---- Enc-string helpers ----
    @staticmethod
    def is_valid_enc_str(enc_str: str) -> bool: ...
    @staticmethod
    def uint32_to_enc_str(value: int) -> str: ...
    @staticmethod
    def enc_str_to_uint32(enc_str: str) -> int: ...

    # ---- Widget creation (native component factories) ----
    @staticmethod
    def create_ui_component_by_frame_id(
        parent_frame_id: int,
        component_flags: int,
        child_index: int,
        event_callback: int,
        name_enc: str = "",
        component_label: str = "",
    ) -> int: ...
    @staticmethod
    def create_ui_component_raw_by_frame_id(
        parent_frame_id: int,
        component_flags: int,
        child_index: int,
        event_callback: int,
        wparam: int = 0,
        component_label: str = "",
    ) -> int: ...
    @staticmethod
    def create_button_frame_by_frame_id(
        parent_frame_id: int,
        component_flags: int,
        child_index: int = 0,
        name_enc: str = "",
        component_label: str = "",
    ) -> int: ...
    @staticmethod
    def create_ctl_button_frame_by_frame_id(
        parent_frame_id: int,
        component_flags: int,
        child_index: int = 0,
        name_enc: str = "",
        component_label: str = "",
    ) -> int: ...
    @staticmethod
    def create_text_button_frame_by_frame_id(
        parent_frame_id: int,
        component_flags: int,
        child_index: int = 0,
        caption: str = "",
        component_label: str = "",
    ) -> int: ...
    @staticmethod
    def create_flat_button_with_click_by_frame_id(
        parent_frame_id: int,
        component_flags: int,
        child_index: int = 0,
        label_text: str = "",
        enable_click: bool = False,
    ) -> int: ...
    @staticmethod
    def create_checkbox_frame_by_frame_id(
        parent_frame_id: int,
        component_flags: int,
        child_index: int = 0,
        name_enc: str = "",
        component_label: str = "",
    ) -> int: ...
    @staticmethod
    def create_scrollable_frame_by_frame_id(
        parent_frame_id: int,
        component_flags: int,
        child_index: int = 0,
        component_label: str = "",
    ) -> int: ...
    @staticmethod
    def create_text_label_frame_by_frame_id(
        parent_frame_id: int,
        component_flags: int,
        child_index: int = 0,
        name_enc: str = "",
        component_label: str = "",
    ) -> int: ...
    @staticmethod
    def create_dropdown_frame_by_frame_id(
        parent_frame_id: int,
        component_flags: int,
        child_index: int = 0,
        component_label: str = "",
    ) -> int: ...
    @staticmethod
    def create_slider_frame_by_frame_id(
        parent_frame_id: int,
        component_flags: int,
        child_index: int = 0,
        component_label: str = "",
    ) -> int: ...
    @staticmethod
    def create_editable_text_frame_by_frame_id(
        parent_frame_id: int,
        component_flags: int,
        child_index: int = 0,
        component_label: str = "",
    ) -> int: ...
    @staticmethod
    def create_progress_bar_by_frame_id(
        parent_frame_id: int,
        component_flags: int,
        child_index: int = 0,
        component_label: str = "",
    ) -> int: ...
    @staticmethod
    def create_tabs_frame_by_frame_id(
        parent_frame_id: int,
        component_flags: int,
        child_index: int = 0,
        component_label: str = "",
    ) -> int: ...

    # ---- Button ----
    @staticmethod
    def get_button_label_by_frame_id(frame_id: int) -> str: ...
    @staticmethod
    def set_button_label_by_frame_id(frame_id: int, enc_label: str) -> bool: ...
    @staticmethod
    def button_mouse_action_by_frame_id(frame_id: int, action_state: int) -> bool: ...

    # ---- Checkbox ----
    @staticmethod
    def is_checkbox_checked_by_frame_id(frame_id: int) -> bool: ...
    @staticmethod
    def set_checkbox_checked_by_frame_id(frame_id: int, checked: bool) -> bool: ...
    @staticmethod
    def get_checkbox_value_by_frame_id(frame_id: int) -> int: ...
    @staticmethod
    def set_checkbox_value_by_frame_id(frame_id: int, value: int) -> bool: ...

    # ---- Dropdown ----
    @staticmethod
    def get_dropdown_options_by_frame_id(frame_id: int) -> List[int]: ...
    @staticmethod
    def select_dropdown_option_by_frame_id(frame_id: int, value: int) -> bool: ...
    @staticmethod
    def select_dropdown_index_by_frame_id(frame_id: int, index: int) -> bool: ...
    @staticmethod
    def add_dropdown_option_by_frame_id(frame_id: int, label_enc: str, value: int) -> bool: ...
    @staticmethod
    def get_dropdown_count_by_frame_id(frame_id: int) -> int: ...
    @staticmethod
    def get_dropdown_option_value_by_frame_id(frame_id: int, index: int) -> int: ...
    @staticmethod
    def get_dropdown_option_index_by_frame_id(frame_id: int, value: int) -> int: ...
    @staticmethod
    def get_dropdown_selected_index_by_frame_id(frame_id: int) -> int: ...
    @staticmethod
    def dropdown_has_value_mapping_by_frame_id(frame_id: int) -> bool: ...
    @staticmethod
    def get_dropdown_value_by_frame_id(frame_id: int) -> int: ...
    @staticmethod
    def set_dropdown_value_by_frame_id(frame_id: int, value: int) -> bool: ...

    # ---- Slider ----
    @staticmethod
    def get_slider_value_by_frame_id(frame_id: int) -> int: ...
    @staticmethod
    def set_slider_value_by_frame_id(frame_id: int, value: int) -> bool: ...

    # ---- Editable text ----
    @staticmethod
    def get_editable_text_value_by_frame_id(frame_id: int) -> str: ...
    @staticmethod
    def set_editable_text_value_by_frame_id(frame_id: int, value: str) -> bool: ...
    @staticmethod
    def set_editable_text_max_length_by_frame_id(frame_id: int, max_length: int) -> bool: ...
    @staticmethod
    def is_editable_text_read_only_by_frame_id(frame_id: int) -> bool: ...
    @staticmethod
    def set_editable_text_read_only_by_frame_id(frame_id: int, read_only: bool) -> bool: ...
    @staticmethod
    def set_read_only_by_frame_id(frame_id: int, is_read_only: bool) -> bool: ...
    @staticmethod
    def is_read_only_by_frame_id(frame_id: int) -> bool: ...

    # ---- Progress bar ----
    @staticmethod
    def get_progress_bar_value_by_frame_id(frame_id: int) -> int: ...
    @staticmethod
    def set_progress_bar_value_by_frame_id(frame_id: int, value: int) -> bool: ...
    @staticmethod
    def set_progress_bar_max_by_frame_id(frame_id: int, value: int) -> bool: ...
    @staticmethod
    def set_progress_bar_color_id_by_frame_id(frame_id: int, color_id: int) -> bool: ...
    @staticmethod
    def set_progress_bar_style_by_frame_id(frame_id: int, style: int) -> bool: ...

    # ---- Text labels ----
    @staticmethod
    def get_text_label_encoded_by_frame_id(frame_id: int) -> str: ...
    @staticmethod
    def get_text_label_decoded_by_frame_id(frame_id: int) -> str: ...
    @staticmethod
    def set_text_label_by_frame_id(frame_id: int, label: str) -> bool: ...
    @staticmethod
    def set_label_by_frame_id(frame_id: int, label: str) -> bool: ...
    @staticmethod
    def set_multiline_label_by_frame_id(frame_id: int, label: str) -> bool: ...
    @staticmethod
    def set_text_label_font_by_frame_id(frame_id: int, font_id: int) -> bool: ...

    # ---- Tabs ----
    @staticmethod
    def add_tab_by_frame_id(
        frame_id: int,
        tab_name_enc: str,
        flags: int,
        child_offset_id: int,
        callback_address: int = 0,
        wparam: int = 0,
    ) -> int: ...
    @staticmethod
    def disable_tab_by_frame_id(frame_id: int, tab_id: int) -> bool: ...
    @staticmethod
    def enable_tab_by_frame_id(frame_id: int, tab_id: int) -> bool: ...
    @staticmethod
    def remove_tab_by_frame_id(frame_id: int, tab_id: int) -> bool: ...
    @staticmethod
    def get_current_tab_index_by_frame_id(frame_id: int) -> int: ...
    @staticmethod
    def get_tab_frame_id_by_frame_id(frame_id: int, tab_id: int) -> int: ...
    @staticmethod
    def get_tab_frame_id(parent_frame_id: int, index: int) -> int: ...
    @staticmethod
    def get_is_tab_enabled_by_frame_id(frame_id: int, tab_id: int) -> bool: ...
    @staticmethod
    def get_tab_by_label_by_frame_id(frame_id: int, label: str) -> int: ...
    @staticmethod
    def get_current_tab_by_frame_id(frame_id: int) -> int: ...
    @staticmethod
    def choose_tab_by_tab_frame_id(frame_id: int, tab_frame_id: int) -> bool: ...
    @staticmethod
    def choose_tab_by_index_by_frame_id(frame_id: int, tab_index: int) -> bool: ...
    @staticmethod
    def get_tab_button_by_frame_id(frame_id: int, tab_frame_id: int) -> int: ...

    # ---- Scrollable ----
    @staticmethod
    def clear_scrollable_items_by_frame_id(frame_id: int) -> bool: ...
    @staticmethod
    def remove_scrollable_item_by_frame_id(frame_id: int, child_offset_id: int) -> bool: ...
    @staticmethod
    def add_scrollable_item_by_frame_id(
        frame_id: int,
        flags: int,
        child_offset_id: int,
        callback_address: int = 0,
    ) -> bool: ...
    @staticmethod
    def get_scrollable_item_frame_id_by_frame_id(frame_id: int, child_offset_id: int) -> int: ...
    @staticmethod
    def get_scrollable_selected_value_by_frame_id(frame_id: int) -> int: ...
    @staticmethod
    def get_scrollable_first_child_frame_id_by_frame_id(frame_id: int) -> int: ...
    @staticmethod
    def get_scrollable_next_child_frame_id_by_frame_id(frame_id: int, child_frame_id: int) -> int: ...
    @staticmethod
    def get_scrollable_last_child_frame_id_by_frame_id(frame_id: int) -> int: ...
    @staticmethod
    def get_scrollable_prev_child_frame_id_by_frame_id(frame_id: int, child_frame_id: int) -> int: ...
    @staticmethod
    def get_scrollable_item_rect_by_frame_id(
        frame_id: int, child_offset_id: int
    ) -> Tuple[float, float, float, float]: ...
    @staticmethod
    def get_scrollable_count_by_frame_id(frame_id: int) -> int: ...
    @staticmethod
    def get_scrollable_items_by_frame_id(frame_id: int) -> List[int]: ...
    @staticmethod
    def get_scrollable_page_by_frame_id(frame_id: int) -> int: ...
