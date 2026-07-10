import Py4GW
from Py4GWCoreLib import *

MODULE_NAME = "tester for windows"


selected_skill = 0
def main():
    global selected_skill
    try:
        PyImGui.set_next_window_size((150, 150), PyImGui.ImGuiCond.FirstUseEver)
        PyImGui.set_next_window_pos((100, 100), PyImGui.ImGuiCond.FirstUseEver)
        if PyImGui.begin("MainFakeGWWindow"):
            PyImGui.text("hello_world")
            if PyImGui.button("print hello world"):
                print("Hello, World!")
        PyImGui.end()
        


    except Exception as e:
        PySystem.Console.Log(MODULE_NAME, f"Error: {str(e)}", PySystem.Console.MessageType.Error)
        raise


    
if __name__ == "__main__":
    main()
