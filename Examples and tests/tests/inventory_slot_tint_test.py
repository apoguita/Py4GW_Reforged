"""Small in-client test for the guarded border-material brightness path."""

import PyImGui
import PyInventory
import PyUIManager


WINDOW = "Inventory border brightness"

_item_id = 0
_hovered_item_id = 0
_color = (1.0, 0.0, 1.0, 1.0)
_brightness = 2.0
_material_enabled = False
_diagnostics: dict = {}
_prepared_state: tuple[bool, float] | None = None


def _native(name: str):
    return getattr(PyUIManager.UIManager, name, None)


def _argb() -> int:
    r, g, b, a = (max(0.0, min(1.0, value)) for value in _color)
    return (round(a * 255) << 24) | (round(r * 255) << 16) | (round(g * 255) << 8) | round(b * 255)


def _set_bool(name: str, value: bool) -> None:
    setter = _native(name)
    if setter is not None:
        setter(value)


def _apply_item_tint() -> None:
    if _item_id <= 0:
        print(f"[{WINDOW}] enter an item id or capture the hovered item first")
        return
    setter = _native("set_item_tint_by_item_id")
    if setter is None:
        print(f"[{WINDOW}] item tint binding unavailable; reinject the current DLL")
        return
    argb = _argb()
    setter(_item_id, argb)
    print(f"[{WINDOW}] queued item={_item_id} argb=0x{argb:08X}")


def _print_diagnostics() -> None:
    probe = _native("get_item_frame_tint_diagnostics")
    if probe is None:
        print(f"[{WINDOW}] diagnostics unavailable; reinject the current DLL")
        return
    try:
        print(f"[{WINDOW}] diagnostics={probe()}")
    except Exception as exc:  # noqa: BLE001
        print(f"[{WINDOW}] diagnostics failed: {exc!r}")


def _prepare_native() -> None:
    """Leave the old alpha/icon/probe experiments off for an unambiguous test."""
    global _prepared_state
    state = (_material_enabled, round(_brightness, 3))
    if _prepared_state == state:
        return
    _prepared_state = state
    _set_bool("set_item_frame_tint_enabled", True)
    _set_bool("set_item_frame_pop_enabled", False)
    _set_bool("set_item_frame_shader_pop_enabled", False)
    _set_bool("set_item_frame_border_probe_enabled", False)
    _set_bool("set_item_frame_material_pop_enabled", _material_enabled)
    setter = _native("set_item_frame_pop_brightness")
    if setter is not None:
        setter(float(_brightness))


def main() -> None:
    global _item_id, _hovered_item_id, _color, _brightness, _material_enabled, _diagnostics

    try:
        hovered = int(PyInventory.get_hovered_item_id() or 0)
        if hovered > 0:
            _hovered_item_id = hovered
    except Exception:
        pass

    if not PyImGui.begin(WINDOW, PyImGui.WindowFlags.AlwaysAutoResize):
        PyImGui.end()
        return

    hook_probe = _native("is_item_frame_tint_hook_installed")
    hook_ok = bool(hook_probe()) if hook_probe else False
    PyImGui.text_colored(
        "Hook active" if hook_ok else "Hook unavailable",
        (0.3, 1.0, 0.4, 1.0) if hook_ok else (1.0, 0.3, 0.3, 1.0),
    )
    PyImGui.text("This test targets only the selected item's +0x2c border material.")

    _material_enabled = bool(PyImGui.checkbox("Enable border material brightness", _material_enabled))
    _brightness = float(PyImGui.slider_float("Brightness", _brightness, 1.0, 8.0))
    _prepare_native()

    _color = tuple(PyImGui.color_edit4("Tint color", _color))
    _item_id = int(PyImGui.input_int("Item id", _item_id))
    PyImGui.text(f"Hovered item: {_hovered_item_id or '(none)'}")
    if PyImGui.button("Use hovered item"):
        _item_id = _hovered_item_id
    PyImGui.same_line(0, -1)
    if PyImGui.button("Apply tint"):
        _apply_item_tint()

    if PyImGui.button("Clear selected"):
        clearer = _native("clear_item_tint_by_item_id")
        if clearer and _item_id > 0:
            clearer(_item_id)
            print(f"[{WINDOW}] cleared item={_item_id}")
    PyImGui.same_line(0, -1)
    if PyImGui.button("Clear all"):
        clearer = _native("clear_item_frame_tints")
        if clearer:
            clearer()
            print(f"[{WINDOW}] cleared all item tint rules")

    probe = _native("get_item_frame_tint_diagnostics")
    if probe:
        try:
            _diagnostics = probe()
            PyImGui.separator()
            PyImGui.text(
                "material={material_pop_enabled} setter={material_setter_resolved} "
                "id={constant_id_resolved} map={border_material_map_valid} "
                "constants={border_material_constant_count} writes={material_constant_calls}".format(**_diagnostics)
            )
            PyImGui.text(
                "tint_matches={tint_matches} border_color_calls={color_calls} "
                "last_item={last_item_id}".format(**_diagnostics)
            )
        except Exception as exc:  # noqa: BLE001
            PyImGui.text_colored(f"Diagnostics failed: {exc!r}", (1.0, 0.3, 0.3, 1.0))
    if PyImGui.button("Print diagnostics"):
        _print_diagnostics()

    PyImGui.end()


if __name__ == "__main__":
    main()
