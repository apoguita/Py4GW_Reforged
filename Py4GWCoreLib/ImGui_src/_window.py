import PyImGui


class _WindowMethods:
    def set_next_window_pos(self, x: float, y: float, cond: int = 0):
        PyImGui.set_next_window_pos(x, y, cond)
    def set_next_window_size(self, width: float, height: float, cond: int = 0):
        PyImGui.set_next_window_size(width, height, cond)
    def set_next_window_size_constraints(self, min_size, max_size):
        PyImGui.set_next_window_size_constraints(min_size, max_size)
    def set_next_window_content_size(self, size):
        PyImGui.set_next_window_content_size(size)
    def set_next_window_collapsed(self, collapsed: bool, cond: int = 0):
        PyImGui.set_next_window_collapsed(collapsed, cond)
    def set_next_window_focus(self):
        PyImGui.set_next_window_focus()
    def set_next_window_bg_alpha(self, alpha: float):
        PyImGui.set_next_window_bg_alpha(alpha)
    def set_next_window_scroll(self, scroll):
        PyImGui.set_next_window_scroll(scroll)
    def set_next_window_viewport(self, viewport_id: int):
        PyImGui.set_next_window_viewport(viewport_id)
    def set_window_pos(self, x: float, y: float, cond: int = 0):
        PyImGui.set_window_pos(x, y, cond)
    def set_window_size(self, width: float, height: float, cond: int = 0):
        PyImGui.set_window_size(width, height, cond)
    def set_window_collapsed(self, collapsed: bool, cond: int = 0):
        PyImGui.set_window_collapsed(collapsed, cond)
    def set_window_focus(self, name: str):
        PyImGui.set_window_focus(name)
    def is_rect_visible(self, size) -> bool:
        return PyImGui.is_rect_visible(size)
    def get_text_line_height(self) -> float:
        return PyImGui.get_text_line_height()
    def get_text_line_height_with_spacing(self) -> float:
        return PyImGui.get_text_line_height_with_spacing()
    def calc_text_size(self, text: str, hide_after_hash: bool = False,
                       wrap_width: float = -1.0):
        return PyImGui.calc_text_size(text, None, hide_after_hash, wrap_width)
    def get_font_tex_uv_white_pixel(self):
        return PyImGui.get_font_tex_uv_white_pixel()
    def set_window_font_scale(self, scale: float):
        PyImGui.set_window_font_scale(scale)
