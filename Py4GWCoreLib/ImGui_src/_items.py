import PyImGui


class _ItemMethods:
    def is_item_hovered(self, flags: int = 0) -> bool:
        return PyImGui.is_item_hovered(flags)
    def is_item_active(self) -> bool:
        return PyImGui.is_item_active()
    def is_item_focused(self) -> bool:
        return PyImGui.is_item_focused()
    def is_item_clicked(self, mouse_button: int = 0) -> bool:
        return PyImGui.is_item_clicked(mouse_button)
    def is_item_visible(self) -> bool:
        return PyImGui.is_item_visible()
    def is_item_edited(self) -> bool:
        return PyImGui.is_item_edited()
    def is_item_activated(self) -> bool:
        return PyImGui.is_item_activated()
    def is_item_deactivated(self) -> bool:
        return PyImGui.is_item_deactivated()
    def is_item_deactivated_after_edit(self) -> bool:
        return PyImGui.is_item_deactivated_after_edit()
    def is_item_toggled_open(self) -> bool:
        return PyImGui.is_item_toggled_open()
    def is_any_item_hovered(self) -> bool:
        return PyImGui.is_any_item_hovered()
    def is_any_item_active(self) -> bool:
        return PyImGui.is_any_item_active()
    def is_any_item_focused(self) -> bool:
        return PyImGui.is_any_item_focused()
    def get_item_id(self) -> int:
        return PyImGui.get_item_id()
    def get_item_rect_min(self):
        return PyImGui.get_item_rect_min()
    def get_item_rect_max(self):
        return PyImGui.get_item_rect_max()
    def get_item_rect_size(self):
        return PyImGui.get_item_rect_size()
    def get_item_flags(self) -> int:
        return PyImGui.get_item_flags()
    def set_item_default_focus(self):
        PyImGui.set_item_default_focus()
    def set_nav_cursor_visible(self, visible: bool):
        PyImGui.set_nav_cursor_visible(visible)
    def set_next_item_width(self, item_width: float):
        PyImGui.set_next_item_width(item_width)
    def set_next_item_allow_overlap(self):
        PyImGui.set_next_item_allow_overlap()
    def push_id_str(self, str_id: str):
        PyImGui.push_id(str_id)
    def push_id_int(self, int_id: int):
        PyImGui.push_id_int(int_id)
    def pop_id(self):
        PyImGui.pop_id()
    def get_id(self, str_id: str) -> int:
        return PyImGui.get_id(str_id)
    def get_id_int(self, int_id: int) -> int:
        return PyImGui.get_id_int(int_id)
    def set_keyboard_focus_here(self, offset: int = 0):
        PyImGui.set_keyboard_focus_here(offset)
