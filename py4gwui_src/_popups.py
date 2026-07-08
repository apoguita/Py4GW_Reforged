import PyImGui


class _PopupMenuMethods:
    """Popups, tooltips, and menu accessors."""

    def menu_item(self, label: str, shortcut: str | None = None,
                  selected: bool = False, enabled: bool = True) -> bool:
        return PyImGui.menu_item(label, shortcut, selected, enabled)

    def open_popup(self, str_id: str, popup_flags: int = 0):
        PyImGui.open_popup(str_id, popup_flags)

    def open_popup_on_item_click(self, str_id: str | None = None, popup_flags: int = 0):
        PyImGui.open_popup_on_item_click(str_id, popup_flags)

    def close_current_popup(self):
        PyImGui.close_current_popup()

    def is_popup_open(self, str_id: str, flags: int = 0) -> bool:
        return PyImGui.is_popup_open(str_id, flags)

    def set_tooltip(self, text: str):
        PyImGui.set_tooltip(text)

    def show_tooltip(self, text: str):
        PyImGui.show_tooltip(text)

    def begin_item_tooltip(self):
        PyImGui.begin_item_tooltip()

    def set_item_tooltip(self, text: str):
        PyImGui.set_item_tooltip(text)
