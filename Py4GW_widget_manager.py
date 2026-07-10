from typing import Optional
import PyImGui
from Py4GWCoreLib._legacy_facade import ImGui_Legacy
from Py4GWCoreLib.py4gwcorelib_src.Settings import Settings
from Py4GWCoreLib.enums_src.IO_enums import Key
import Widgets.WidgetCatalog.Py4GW_widget_catalog as widget_catalog

from Py4GWCoreLib.py4gwcorelib_src.WidgetManager import LayoutMode, Py4GWLibrary, WidgetHandler, get_widget_handler
import os

MODULE_NAME = "Widget Manager"
          
#region Main
# ------------------------------------------------------------
# Config
# ------------------------------------------------------------
widget_manager : WidgetHandler = get_widget_handler()
py4_gw_library : Optional[Py4GWLibrary] = None

INI_KEY = ""
INI_PATH = "Widgets/WidgetManager"
INI_FILENAME = "WidgetManager.ini"

def update():
    return 
    # #deprecated in place of callbacks
    if widget_manager.enable_all:
        widget_manager.execute_enabled_widgets_update()
    
def draw():
    return #deprecated in place of callbacks
    if widget_manager.enable_all:
        widget_manager.execute_enabled_widgets_draw()     
        
widget_manager_initialized = False
widget_manager_initializing = False

def main():
    global INI_KEY, widget_manager_initialized, widget_manager_initializing, py4_gw_library

    if not INI_KEY:
        if not os.path.exists(INI_PATH):
            os.makedirs(INI_PATH, exist_ok=True)

        INI_KEY = Settings(f"{INI_PATH}/{INI_FILENAME}", "account").name

        if not INI_KEY: return

        cfg = Settings.find(INI_KEY)
        if cfg is None: return

        widget_manager.MANAGER_INI_KEY = INI_KEY

        widget_manager.discover()

        # FIX 1: Explicitly load the global manager state into the handler
        widget_manager.enable_all = bool(cfg.get_bool("Configuration", "enable_all", True))
        widget_manager._apply_ini_configuration()


    if INI_KEY:
        cfg = Settings.find(INI_KEY)
        if cfg is None:
            return

        widget_catalog.main()
        show_adavanced = widget_catalog.show_adavanced_enabled()

        if show_adavanced:
            use_library = bool(cfg.get_bool("Configuration", "use_library", True))
            if use_library:
                if py4_gw_library is None:
                    py4_gw_library = Py4GWLibrary(INI_KEY, MODULE_NAME, widget_manager)
            
                py4_gw_library.draw_window()
            else:
                if ImGui_Legacy.Begin(ini_key=INI_KEY, name="Widget Manager", flags=PyImGui.WindowFlags.AlwaysAutoResize):
                    widget_manager.draw_ui(INI_KEY)
                ImGui_Legacy.End(INI_KEY)
        else:
            widget_catalog.draw()
            
        widget_manager._draw_pending_disable_confirmation()
    
    if widget_manager.enable_all:
        #deprecated in place of callbacks
        #widget_manager.execute_enabled_widgets_main()
        widget_manager.execute_configuring_widgets()


if __name__ == "__main__":
    main()
