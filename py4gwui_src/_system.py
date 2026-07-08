import PyImGui


class _SystemMethods:
    """Clipboard, log, ini, drag-drop, plotting, debug, and misc accessors."""

    def get_clipboard_text(self) -> str:
        return PyImGui.get_clipboard_text()

    def set_clipboard_text(self, text: str):
        PyImGui.set_clipboard_text(text)

    def log_to_tty(self, auto_open_depth: int = -1):
        PyImGui.log_to_tty(auto_open_depth)

    def log_to_file(self, auto_open_depth: int = -1, filename: str | None = None):
        PyImGui.log_to_file(auto_open_depth, filename)

    def log_to_clipboard(self, auto_open_depth: int = -1):
        PyImGui.log_to_clipboard(auto_open_depth)

    def log_buttons(self):
        PyImGui.log_buttons()

    def log_finish(self):
        PyImGui.log_finish()

    def get_time(self) -> float:
        return PyImGui.get_time()

    def get_frame_count(self) -> int:
        return PyImGui.get_frame_count()

    def load_ini_settings_from_disk(self, ini_filename: str):
        PyImGui.load_ini_settings_from_disk(ini_filename)

    def load_ini_settings_from_memory(self, ini_data: str, ini_size: int = 0):
        PyImGui.load_ini_settings_from_memory(ini_data, ini_size)

    def save_ini_settings_to_disk(self, ini_filename: str):
        PyImGui.save_ini_settings_to_disk(ini_filename)

    def save_ini_settings_to_memory(self) -> str:
        return PyImGui.save_ini_settings_to_memory()

    def set_drag_drop_payload(self, payload_type: str, data, size: int,
                              cond: int = 0) -> bool:
        return PyImGui.set_drag_drop_payload(payload_type, data, size, cond)

    def accept_drag_drop_payload(self, payload_type: str, flags: int = 0):
        return PyImGui.accept_drag_drop_payload(payload_type, flags)

    def get_drag_drop_payload(self):
        return PyImGui.get_drag_drop_payload()

    def plot_lines(self, label: str, values: list[float], values_offset: int = 0,
                   overlay_text: str | None = None, scale_min: float | None = None,
                   scale_max: float | None = None, graph_size=(0, 0)):
        PyImGui.plot_lines(label, values, values_offset, overlay_text,
                           scale_min or 3.4028235e38, scale_max or 3.4028235e38, graph_size)

    def plot_histogram(self, label: str, values: list[float], values_offset: int = 0,
                       overlay_text: str | None = None, scale_min: float | None = None,
                       scale_max: float | None = None, graph_size=(0, 0)):
        PyImGui.plot_histogram(label, values, values_offset, overlay_text,
                               scale_min or 3.4028235e38, scale_max or 3.4028235e38, graph_size)

    def value_bool(self, prefix: str, value: bool):
        PyImGui.value_bool(prefix, value)

    def value_int(self, prefix: str, value: int):
        PyImGui.value_int(prefix, value)

    def value_uint(self, prefix: str, value: int):
        PyImGui.value_uint(prefix, value)

    def value_float(self, prefix: str, value: float, fmt: str | None = None):
        PyImGui.value_float(prefix, value, fmt)

    def show_demo_window(self):
        PyImGui.show_demo_window()

    def show_metrics_window(self):
        PyImGui.show_metrics_window()

    def show_debug_log_window(self):
        PyImGui.show_debug_log_window()

    def show_id_stack_tool_window(self):
        PyImGui.show_id_stack_tool_window()

    def show_about_window(self):
        PyImGui.show_about_window()

    def show_style_editor(self):
        PyImGui.show_style_editor()

    def show_style_selector(self, label: str):
        PyImGui.show_style_selector(label)

    def show_font_selector(self, label: str):
        PyImGui.show_font_selector(label)

    def show_user_guide(self):
        PyImGui.show_user_guide()

    def get_version(self) -> str:
        return PyImGui.get_version()

    def debug_flash_style_color(self, idx: int):
        PyImGui.debug_flash_style_color(idx)

    def debug_start_item_picker(self):
        PyImGui.debug_start_item_picker()

    def debug_text_encoding(self, text: str):
        PyImGui.debug_text_encoding(text)
