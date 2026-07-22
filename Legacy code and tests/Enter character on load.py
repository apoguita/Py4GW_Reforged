from Py4GWCoreLib import Timer
from Py4GWCoreLib import UIManager
from Py4GWCoreLib import Keystroke
from Py4GWCoreLib import Key
from Py4GWCoreLib import ConsoleLog, Color, ImGui
from Py4GWCoreLib.py4gwcorelib_src.Settings import Settings
from Py4GWCoreLib.Context import GWContext
import PyImGui

module_name = "Enter character on load"
MODULE_NAME = "Enter on loading"
MODULE_ICON = "Textures/Module_Icons/Enter on Load.png"

play_button_hash = 184818986
loading_in_character_screen = True

start_timer = Timer()
start_timer.Start()

INI_KEY = ""
INI_INIT = False


def _ensure_ini() -> bool:
    global INI_KEY, INI_INIT
    if INI_INIT:
        return True

    cfg = Settings(f"{"Widgets/EnterCharacterOnLoad"}/{"EnterCharacterOnLoad.ini"}", "global")
    INI_KEY = cfg.name

    if not INI_KEY:
        ConsoleLog(module_name, "INI global key creation FAILED (INI_KEY empty).")
        return False

    # FORCE: ensure the document has at least 1 var so the file is created.
    cfg.set("Window config", "init", True)

    #ConsoleLog(module_name, f"INI global key OK: {INI_KEY}")
    INI_INIT = True
    return True


def main():
    global loading_in_character_screen, start_timer, play_button_hash

    _ensure_ini()

    if start_timer.IsStopped():
        return

    if (pregame_ctx := GWContext.PreGame.GetContext()) is None:
        return

    if start_timer.HasElapsed(1000) and loading_in_character_screen:
        frame_id = UIManager.GetFrameIDByHash(play_button_hash)
        if UIManager.FrameExists(frame_id):
            ConsoleLog(module_name, "Entering Game.")
            Keystroke.PressAndRelease(Key.Enter.value)

        loading_in_character_screen = False
        start_timer.Stop()

    if start_timer.HasElapsed(1500):
        loading_in_character_screen = False
        start_timer.Stop()


def tooltip():
    PyImGui.begin_tooltip()

    # Title
    title_color = Color(255, 200, 100, 255)
    ImGui.push_font("Regular", 20)
    PyImGui.text_colored("Enter character on load", title_color.to_tuple_normalized())
    ImGui.pop_font()
    
    PyImGui.spacing()
    PyImGui.separator()
    PyImGui.spacing()
    
    # Description
    PyImGui.text("Automatically presses Enter to enter")
    PyImGui.text("your character upon loading the")
    PyImGui.text("character selection screen.")
    
    PyImGui.spacing()
    PyImGui.separator()
    PyImGui.spacing()
    
    # Features
    PyImGui.text_colored("Features:", title_color.to_tuple_normalized())
    PyImGui.bullet_text("Automatically enters character on load.")
    
    PyImGui.spacing()
    PyImGui.separator()
    PyImGui.spacing()
    
    # Credits
    PyImGui.text_colored("Credits:", title_color.to_tuple_normalized())
    PyImGui.bullet_text("Developed by Apo")
    
    PyImGui.end_tooltip()


if __name__ == "__main__":
    main()
