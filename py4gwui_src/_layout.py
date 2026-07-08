import PyImGui


class _LayoutMethods:
    """Layout, cursor, and scroll accessors."""

    def separator(self):
        PyImGui.separator()

    def separator_text(self, label: str):
        PyImGui.separator_text(label)

    def same_line(self, offset: float = 0.0, spacing: float = -1.0):
        PyImGui.same_line(offset, spacing)

    def spacing(self):
        PyImGui.spacing()

    def new_line(self):
        PyImGui.new_line()

    def dummy(self, width: float, height: float):
        PyImGui.dummy((int(width), int(height)))

    def indent(self, indent_w: float = 0.0):
        PyImGui.indent(indent_w)

    def unindent(self, indent_w: float = 0.0):
        PyImGui.unindent(indent_w)

    def align_text_to_frame_padding(self):
        PyImGui.align_text_to_frame_padding()

    def get_frame_height(self) -> float:
        return PyImGui.get_frame_height()

    def get_frame_height_with_spacing(self) -> float:
        return PyImGui.get_frame_height_with_spacing()

    def get_font_size(self) -> float:
        return PyImGui.get_font_size()

    def set_cursor_pos(self, x, y=None):
        if y is None:
            PyImGui.set_cursor_pos(x)
        else:
            PyImGui.set_cursor_pos((float(x), float(y)))

    def set_cursor_pos_x(self, x: float):
        PyImGui.set_cursor_pos_x(x)

    def set_cursor_pos_y(self, y: float):
        PyImGui.set_cursor_pos_y(y)

    def set_cursor_screen_pos(self, x, y=None):
        if y is None:
            PyImGui.set_cursor_screen_pos(x)
        else:
            PyImGui.set_cursor_screen_pos((float(x), float(y)))

    def set_scroll_x(self, scroll_x: float):
        PyImGui.set_scroll_x(scroll_x)

    def set_scroll_y(self, scroll_y: float):
        PyImGui.set_scroll_y(scroll_y)

    def set_scroll_here_x(self, center_x_ratio: float = 0.5):
        PyImGui.set_scroll_here_x(center_x_ratio)

    def set_scroll_here_y(self, center_y_ratio: float = 0.5):
        PyImGui.set_scroll_here_y(center_y_ratio)

    def set_scroll_from_pos_x(self, local_x: float, center_x_ratio: float = 0.5):
        PyImGui.set_scroll_from_pos_x(local_x, center_x_ratio)

    def set_scroll_from_pos_y(self, local_y: float, center_y_ratio: float = 0.5):
        PyImGui.set_scroll_from_pos_y(local_y, center_y_ratio)
