"""Runtime owner for the independent Xunlai and Colorize item features."""

from typing import Optional

from Py4GWCoreLib.py4gwcorelib_src.Color import Color

from . import store
from .model import ColorizeSettings, InventoryFeatureSettings
from .monitor import InventoryMonitor

_CONTEXT_POPUP_ID = "SystemItemsContextMenu"
_CONTEXT_CALLBACK = "SystemItemsContextMenuCallback"
_COLORIZE_CALLBACK = "SystemItemsColorize"


def _log(message: str, error: bool = False) -> None:
    try:
        import PySystem

        level = PySystem.Console.MessageType.Error if error else PySystem.Console.MessageType.Info
        PySystem.Console.Log("System Settings / Items", message, level)
    except Exception:
        pass


def _color(color: tuple[int, int, int, int], alpha: int | None = None) -> Color:
    value = Color(*color)
    if alpha is not None:
        value.set_a(alpha)
    return value


def _map_is_ready() -> bool:
    try:
        from Py4GWCoreLib.Map import Map

        return bool(Map.IsMapReady())
    except Exception:
        return False


class InventorySettingsController:
    def __init__(self) -> None:
        self._settings = store.load()
        self._monitor = InventoryMonitor()
        self._context_monitor = InventoryMonitor()
        self._booted = False
        self._native_tints: dict[int, int] = {}
        self._xunlai_status = ""
        self._native_outline_warned = False
        self._callbacks_registered = False

    def boot(self) -> None:
        if not self._booted:
            self._booted = True
            self._register_callbacks()

    def settings(self) -> InventoryFeatureSettings:
        return self._settings

    def save_settings(self) -> None:
        store.save(self._settings)

    def _register_callbacks(self) -> None:
        try:
            import PyCallback

            from Py4GWCoreLib.py4gwcorelib_src.Profiling import ProfilingRegistry

            PyCallback.PyCallback.RemoveByName(_CONTEXT_CALLBACK)
            PyCallback.PyCallback.RemoveByName(_COLORIZE_CALLBACK)
            PyCallback.PyCallback.Register(_CONTEXT_CALLBACK, PyCallback.Phase.Update, self._context_pass,
                                            priority=99, context=PyCallback.Context.Draw)
            PyCallback.PyCallback.Register(_COLORIZE_CALLBACK, PyCallback.Phase.Update, self._colorize_pass,
                                            priority=99, context=PyCallback.Context.Draw)
            registry = ProfilingRegistry()
            registry.register(_CONTEXT_CALLBACK)
            registry.register(_COLORIZE_CALLBACK)
            self._callbacks_registered = True
        except Exception as exc:
            self._callbacks_registered = False
            _log("item callback registration error: %s" % exc, error=True)

    def open_xunlai(self) -> None:
        if not _map_is_ready():
            self._xunlai_status = "Map is not ready."
            return
        try:
            from Py4GWCoreLib import GLOBAL_CACHE

            if GLOBAL_CACHE.Inventory.IsStorageOpen():
                self._xunlai_status = "Xunlai Vault is already open."
                return
            opened = bool(GLOBAL_CACHE.Inventory.OpenXunlaiWindow())
            self._xunlai_status = "Xunlai Vault is already open." if opened else "Xunlai Vault open requested."
        except Exception as exc:
            self._xunlai_status = "Open Xunlai failed: %s" % exc
            _log(self._xunlai_status, error=True)

    def xunlai_status(self) -> str:
        return self._xunlai_status

    def toggle_colorize(self) -> None:
        self._settings.colorize.enabled = not self._settings.colorize.enabled
        self.save_settings()
        _log("Colorize %s from the shared item context menu." %
             ("enabled" if self._settings.colorize.enabled else "disabled"))

    def draw_context_menu_items(self, prepend_separator: bool = True) -> bool:
        if not _map_is_ready():
            return False
        import PyImGui

        from Py4GWCoreLib import GLOBAL_CACHE

        settings = self._settings
        if not (settings.context_menu_xunlai or settings.colorize.context_menu_toggle):
            return False
        if prepend_separator:
            PyImGui.separator()
        if settings.context_menu_xunlai and not GLOBAL_CACHE.Inventory.IsStorageOpen():
            if PyImGui.menu_item("Open Xunlai Vault##system_items_xunlai"):
                self.open_xunlai()
                PyImGui.close_current_popup()
        if settings.colorize.context_menu_toggle:
            label = "Disable Colorize" if settings.colorize.enabled else "Enable Colorize"
            if PyImGui.menu_item(label + "##system_items_colorize"):
                self.toggle_colorize()
                PyImGui.close_current_popup()
        return True

    def update(self) -> None:
        self._context_pass()
        self._colorize_pass()

    def _context_pass(self) -> None:
        if not _map_is_ready():
            return
        self._draw_context_menu()

    def _colorize_pass(self) -> None:
        if not _map_is_ready():
            return
        colorize = self._settings.colorize
        slots = self._monitor.scan() if colorize.enabled else []
        self._draw_imgui(colorize, slots)
        self._reconcile_native(colorize, slots)

    def _draw_context_menu(self) -> None:
        import PyImGui

        from Py4GWCoreLib.FrameTree import Frame, FrameId
        from Py4GWCoreLib.enums_src.IO_enums import MouseButton

        settings = self._settings
        if not (settings.context_menu_xunlai or settings.colorize.context_menu_toggle):
            return
        if PyImGui.is_mouse_clicked(MouseButton.Right.value):
            hit = (Frame(FrameId.InventoryBagsWindow).is_mouse_over()
                   or Frame(FrameId.InventoryWindow).is_mouse_over())
            if hit:
                PyImGui.open_popup(_CONTEXT_POPUP_ID)
        if PyImGui.begin_popup(_CONTEXT_POPUP_ID):
            self.draw_context_menu_items(prepend_separator=False)
            PyImGui.end_popup()

    @staticmethod
    def _color_for(settings: ColorizeSettings, rarity: str) -> tuple[int, int, int, int] | None:
        return settings.colors.get(rarity) if settings.rarities.get(rarity, False) else None

    def _draw_imgui(self, settings: ColorizeSettings, slots) -> None:
        if not settings.enabled or not (settings.imgui_frame or settings.imgui_outline):
            return
        for entry in slots:
            color = self._color_for(settings, entry.rarity)
            if color is None:
                continue
            if settings.imgui_frame:
                for frame in (entry.bag_frame, entry.inventory_frame):
                    if frame is not None:
                        frame.draw(_color(color, 25).to_color())
            if settings.imgui_outline:
                for frame in (entry.bag_frame, entry.inventory_frame):
                    if frame is not None:
                        frame.draw_outline(_color(color, 125).to_color())

    def _reconcile_native(self, settings: ColorizeSettings, slots) -> None:
        desired: dict[int, int] = {}
        if settings.enabled and settings.native_frame:
            for entry in slots:
                color = self._color_for(settings, entry.rarity)
                if color is None:
                    continue
                for frame in (entry.bag_frame, entry.inventory_frame):
                    if frame is not None:
                        desired[int(frame.frame_id)] = _color(color).to_dx_color()
        try:
            import PyUIManager

            for frame_id in set(self._native_tints) - set(desired):
                PyUIManager.UIManager.clear_item_frame_tint_by_frame_id(frame_id)
            for frame_id, color in desired.items():
                if self._native_tints.get(frame_id) != color:
                    PyUIManager.UIManager.set_item_frame_tint_by_frame_id(frame_id, color)
            self._native_tints = desired
        except Exception as exc:
            if desired:
                _log("Native Colorize unavailable: %s" % exc, error=True)
        if settings.native_outline and not self._native_outline_warned:
            self._native_outline_warned = True
            _log("Native outline Colorize is not exposed by the current native UI owner; no native outline was applied.")


_controller: Optional[InventorySettingsController] = None


def get_controller() -> InventorySettingsController:
    global _controller
    if _controller is None:
        _controller = InventorySettingsController()
    return _controller
