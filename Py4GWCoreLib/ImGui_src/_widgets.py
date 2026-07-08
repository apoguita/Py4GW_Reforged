import PyImGui


class _WidgetMethods:
    def button(self, label: str, width: float = 0.0, height: float = 0.0) -> bool:
        return PyImGui.button(label, width, height)
    def small_button(self, label: str) -> bool:
        return PyImGui.small_button(label)
    def invisible_button(self, str_id: str, width: float, height: float, flags: int = 0) -> bool:
        return PyImGui.invisible_button(str_id, (int(width), int(height)), flags)
    def arrow_button(self, str_id: str, direction: int) -> bool:
        return PyImGui.arrow_button(str_id, direction)
    def checkbox(self, label: str, value: bool) -> bool:
        return PyImGui.checkbox(label, value)
    def checkbox_flags(self, label: str, flags: int, flags_value: int) -> int:
        return PyImGui.checkbox_flags(label, flags, flags_value)
    def radio_button(self, label: str, value: int, button_index: int) -> int:
        return PyImGui.radio_button(label, value, button_index)
    def progress_bar(self, fraction: float, width: float = -1.0, height: float = 0.0, overlay: str | None = None):
        PyImGui.progress_bar(fraction, width, height, overlay)
    def bullet(self):
        PyImGui.bullet()
    def slider_float(self, label: str, value: float, v_min: float, v_max: float,
                     fmt: str = "%.3f", flags: int = 0) -> float:
        return PyImGui.slider_float(label, value, v_min, v_max, fmt, flags)
    def slider_int(self, label: str, value: int, v_min: int, v_max: int,
                   fmt: str = "%d", flags: int = 0) -> int:
        return PyImGui.slider_int(label, value, v_min, v_max, fmt, flags)
    def slider_angle(self, label: str, v_rad: float, v_deg_min: float = -360.0,
                     v_deg_max: float = 360.0, fmt: str = "%.0f deg", flags: int = 0) -> float:
        return PyImGui.slider_angle(label, v_rad, v_deg_min, v_deg_max, fmt, flags)
    def v_slider_float(self, label: str, size, value: float, v_min: float, v_max: float,
                       fmt: str = "%.3f", flags: int = 0) -> float:
        return PyImGui.v_slider_float(label, size, value, v_min, v_max, fmt, flags)
    def v_slider_int(self, label: str, size, value: int, v_min: int, v_max: int,
                     fmt: str = "%d", flags: int = 0) -> int:
        return PyImGui.v_slider_int(label, size, value, v_min, v_max, fmt, flags)
    def slider_float2(self, label: str, v, v_min: float, v_max: float,
                      fmt: str = "%.3f", flags: int = 0):
        return PyImGui.slider_float2(label, v, v_min, v_max, fmt, flags)
    def slider_float3(self, label: str, v, v_min: float, v_max: float,
                      fmt: str = "%.3f", flags: int = 0):
        return PyImGui.slider_float3(label, v, v_min, v_max, fmt, flags)
    def slider_float4(self, label: str, v, v_min: float, v_max: float,
                      fmt: str = "%.3f", flags: int = 0):
        return PyImGui.slider_float4(label, v, v_min, v_max, fmt, flags)
    def slider_int2(self, label: str, v, v_min: int, v_max: int,
                    fmt: str = "%d", flags: int = 0):
        return PyImGui.slider_int2(label, v, v_min, v_max, fmt, flags)
    def slider_int3(self, label: str, v, v_min: int, v_max: int,
                    fmt: str = "%d", flags: int = 0):
        return PyImGui.slider_int3(label, v, v_min, v_max, fmt, flags)
    def slider_int4(self, label: str, v, v_min: int, v_max: int,
                    fmt: str = "%d", flags: int = 0):
        return PyImGui.slider_int4(label, v, v_min, v_max, fmt, flags)
    def drag_float(self, label: str, value: float, v_speed: float = 1.0, v_min: float = 0.0,
                   v_max: float = 0.0, fmt: str = "%.3f", flags: int = 0) -> float:
        return PyImGui.drag_float(label, value, v_speed, v_min, v_max, fmt, flags)
    def drag_float_range2(self, label: str, v_min_cur: float, v_max_cur: float,
                          v_speed: float = 1.0, v_min: float = 0.0, v_max: float = 0.0,
                          fmt: str = "%.3f", fmt_max: str | None = None, flags: int = 0):
        return PyImGui.drag_float_range2(label, v_min_cur, v_max_cur, v_speed, v_min, v_max, fmt, fmt_max, flags)
    def drag_int(self, label: str, value: int, v_speed: float = 1.0, v_min: int = 0,
                 v_max: int = 0, fmt: str = "%d", flags: int = 0) -> int:
        return PyImGui.drag_int(label, value, v_speed, v_min, v_max, fmt, flags)
    def drag_int_range2(self, label: str, v_min_cur: int, v_max_cur: int,
                        v_speed: float = 1.0, v_min: int = 0, v_max: int = 0,
                        fmt: str = "%d", fmt_max: str | None = None, flags: int = 0):
        return PyImGui.drag_int_range2(label, v_min_cur, v_max_cur, v_speed, v_min, v_max, fmt, fmt_max, flags)
    def drag_float2(self, label: str, v, v_speed: float = 1.0, v_min: float = 0.0,
                    v_max: float = 0.0, fmt: str = "%.3f", flags: int = 0):
        return PyImGui.drag_float2(label, v, v_speed, v_min, v_max, fmt, flags)
    def drag_float3(self, label: str, v, v_speed: float = 1.0, v_min: float = 0.0,
                    v_max: float = 0.0, fmt: str = "%.3f", flags: int = 0):
        return PyImGui.drag_float3(label, v, v_speed, v_min, v_max, fmt, flags)
    def drag_float4(self, label: str, v, v_speed: float = 1.0, v_min: float = 0.0,
                    v_max: float = 0.0, fmt: str = "%.3f", flags: int = 0):
        return PyImGui.drag_float4(label, v, v_speed, v_min, v_max, fmt, flags)
    def drag_int2(self, label: str, v, v_speed: float = 1.0, v_min: int = 0,
                  v_max: int = 0, fmt: str = "%d", flags: int = 0):
        return PyImGui.drag_int2(label, v, v_speed, v_min, v_max, fmt, flags)
    def drag_int3(self, label: str, v, v_speed: float = 1.0, v_min: int = 0,
                  v_max: int = 0, fmt: str = "%d", flags: int = 0):
        return PyImGui.drag_int3(label, v, v_speed, v_min, v_max, fmt, flags)
    def drag_int4(self, label: str, v, v_speed: float = 1.0, v_min: int = 0,
                  v_max: int = 0, fmt: str = "%d", flags: int = 0):
        return PyImGui.drag_int4(label, v, v_speed, v_min, v_max, fmt, flags)
    def input_float(self, label: str, value: float, step: float = 0.0, step_fast: float = 0.0,
                    fmt: str = "%.3f", flags: int = 0) -> float:
        return PyImGui.input_float(label, value, step, step_fast, fmt, flags)
    def input_float2(self, label: str, v, fmt: str = "%.3f", flags: int = 0):
        return PyImGui.input_float2(label, v, fmt, flags)
    def input_float3(self, label: str, v, fmt: str = "%.3f", flags: int = 0):
        return PyImGui.input_float3(label, v, fmt, flags)
    def input_float4(self, label: str, v, fmt: str = "%.3f", flags: int = 0):
        return PyImGui.input_float4(label, v, fmt, flags)
    def input_int(self, label: str, value: int, step: int = 1, step_fast: int = 100,
                  flags: int = 0) -> int:
        return PyImGui.input_int(label, value, step, step_fast, flags)
    def input_int2(self, label: str, v, flags: int = 0):
        return PyImGui.input_int2(label, v, flags)
    def input_int3(self, label: str, v, flags: int = 0):
        return PyImGui.input_int3(label, v, flags)
    def input_int4(self, label: str, v, flags: int = 0):
        return PyImGui.input_int4(label, v, flags)
    def input_double(self, label: str, value: float, step: float = 0.0, step_fast: float = 0.0,
                     fmt: str = "%.6f", flags: int = 0) -> float:
        return PyImGui.input_double(label, value, step, step_fast, fmt, flags)
    def input_text(self, label: str, text: str = "", flags: int = 0) -> str:
        return PyImGui.input_text(label, text, flags)
    def input_text_with_hint(self, label: str, hint: str, text: str = "", flags: int = 0) -> str:
        return PyImGui.input_text_with_hint(label, hint, text, flags)
    def input_text_multiline(self, label: str, text: str = "", size=(0, 0), flags: int = 0) -> str:
        return PyImGui.input_text_multiline(label, text, size, flags)
    def combo(self, label: str, current_item: int, items: list[str]) -> int:
        return PyImGui.combo(label, current_item, items)
    def list_box(self, label: str, current_item: int, items: list[str],
                 height_in_items: int = -1) -> int:
        return PyImGui.list_box(label, current_item, items, height_in_items)
    def selectable(self, label: str, selected: bool = False, flags: int = 0,
                   size=(0, 0)) -> bool:
        return PyImGui.selectable(label, selected, flags, (int(size[0]), int(size[1])))
