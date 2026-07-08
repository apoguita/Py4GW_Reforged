import PyImGui


class _InputStateMethods:
    def is_key_down(self, key: int) -> bool:
        return PyImGui.is_key_down(key)
    def is_key_pressed(self, key: int, repeat: bool = True) -> bool:
        return PyImGui.is_key_pressed(key, repeat)
    def is_key_released(self, key: int) -> bool:
        return PyImGui.is_key_released(key)
    def is_key_chord_pressed(self, key_chord: int) -> bool:
        return PyImGui.is_key_chord_pressed(key_chord)
    def get_key_name(self, key: int) -> str:
        return PyImGui.get_key_name(key)
    def get_key_pressed_amount(self, key: int, repeat_delay: float, rate: float) -> int:
        return PyImGui.get_key_pressed_amount(key, repeat_delay, rate)
    def set_next_frame_want_capture_keyboard(self, want_capture: bool):
        PyImGui.set_next_frame_want_capture_keyboard(want_capture)
    def shortcut(self, key_chord: int, flags: int = 0) -> bool:
        return PyImGui.shortcut(key_chord, flags)
    def set_next_item_shortcut(self, key_chord: int, flags: int = 0):
        PyImGui.set_next_item_shortcut(key_chord, flags)
    def set_item_key_owner(self, key: int):
        PyImGui.set_item_key_owner(key)
    def set_mouse_cursor(self, cursor_type: int):
        PyImGui.set_mouse_cursor(cursor_type)
    def get_mouse_cursor(self) -> int:
        return PyImGui.get_mouse_cursor()
    def get_mouse_pos(self):
        return PyImGui.get_mouse_pos()
    def get_mouse_pos_on_opening_current_popup(self):
        return PyImGui.get_mouse_pos_on_opening_current_popup()
    def is_mouse_down(self, button: int) -> bool:
        return PyImGui.is_mouse_down(button)
    def is_mouse_clicked(self, button: int, repeat: bool = False) -> bool:
        return PyImGui.is_mouse_clicked(button, repeat)
    def is_mouse_released(self, button: int) -> bool:
        return PyImGui.is_mouse_released(button)
    def is_mouse_double_clicked(self, button: int) -> bool:
        return PyImGui.is_mouse_double_clicked(button)
    def is_mouse_released_with_delay(self, button: int, delay: float) -> bool:
        return PyImGui.is_mouse_released_with_delay(button, delay)
    def is_mouse_dragging(self, button: int, lock_threshold: float = -1.0) -> bool:
        return PyImGui.is_mouse_dragging(button, lock_threshold)
    def is_mouse_hovering_rect(self, r_min, r_max, clip: bool = True) -> bool:
        return PyImGui.is_mouse_hovering_rect(r_min, r_max, clip)
    def is_any_mouse_down(self) -> bool:
        return PyImGui.is_any_mouse_down()
    def is_mouse_pos_valid(self, mouse_pos=None) -> bool:
        return PyImGui.is_mouse_pos_valid(mouse_pos)
    def get_mouse_clicked_count(self, button: int) -> int:
        return PyImGui.get_mouse_clicked_count(button)
    def get_mouse_drag_delta(self, button: int = 0, lock_threshold: float = -1.0):
        return PyImGui.get_mouse_drag_delta(button, lock_threshold)
    def reset_mouse_drag_delta(self, button: int = 0):
        PyImGui.reset_mouse_drag_delta(button)
    def set_next_frame_want_capture_mouse(self, want_capture: bool):
        PyImGui.set_next_frame_want_capture_mouse(want_capture)
