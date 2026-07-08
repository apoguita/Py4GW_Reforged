import PyImGui


class _ColorImageMethods:
    def color_edit3(self, label: str, color, flags: int = 0):
        return PyImGui.color_edit3(label, color, flags)
    def color_edit4(self, label: str, color, flags: int = 0):
        return PyImGui.color_edit4(label, color, flags)
    def color_picker3(self, label: str, color, flags: int = 0):
        return PyImGui.color_picker3(label, color, flags)
    def color_picker4(self, label: str, color, flags: int = 0):
        return PyImGui.color_picker4(label, color, flags)
    def color_button(self, desc_id: str, color, flags: int = 0, size=(0, 0)) -> bool:
        return PyImGui.color_button(desc_id, color, flags, size)
    def set_color_edit_options(self, flags: int):
        PyImGui.set_color_edit_options(flags)
    def color_convert_u32_to_float4(self, value: int):
        return PyImGui.color_convert_u32_to_float4(value)
    def color_convert_float4_to_u32(self, value) -> int:
        return PyImGui.color_convert_float4_to_u32(value)
    def color_convert_rgb_to_hsv(self, r: float, g: float, b: float):
        return PyImGui.color_convert_rgb_to_hsv(r, g, b)
    def color_convert_hsv_to_rgb(self, h: float, s: float, v: float):
        return PyImGui.color_convert_hsv_to_rgb(h, s, v)
    def get_color_u32(self, idx: int, alpha_mul: float = 1.0) -> int:
        return PyImGui.get_color_u32(idx, alpha_mul)
    def get_color_u32_vec4(self, color) -> int:
        return PyImGui.get_color_u32_vec4(color)
    def get_style_color_vec4(self, idx: int):
        return PyImGui.get_style_color_vec4(idx)
    def image(self, tex_id: int, size, uv0=(0, 0), uv1=(1, 1)):
        PyImGui.image(tex_id, size, uv0, uv1)
    def image_with_bg(self, tex_id: int, size, uv0=(0, 0), uv1=(1, 1),
                      bg_color=(0, 0, 0, 0), tint=(1, 1, 1, 1)):
        PyImGui.image_with_bg(tex_id, size, uv0, uv1, bg_color, tint)
    def image_button(self, str_id: str, tex_id: int, size, uv0=(0, 0), uv1=(1, 1),
                     bg_color=(0, 0, 0, 0), tint=(1, 1, 1, 1)) -> bool:
        return PyImGui.image_button(str_id, tex_id, size, uv0, uv1, bg_color, tint)
