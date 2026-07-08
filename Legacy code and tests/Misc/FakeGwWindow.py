import Py4GW
from Py4GWCoreLib import *

MODULE_NAME = "tester for windows"


selected_skill = 0
def main():
    global selected_skill
    try:
        if ImGui_Legacy.gw_window.begin(name= "MainFakeGWWindow",
                                 pos=(100, 100),
                                 size=(150, 150),
                                 collapsed=False,  
                                 cond=PyImGui.ImGuiCond.FirstUseEver):  
            PyImGui.text(f"hello_world")
            if PyImGui.button("print hello world"):
                print("Hello, World!")
   
        ImGui_Legacy.gw_window.end("MainFakeGWWindow")
        


    except Exception as e:
        PySystem.Console.Log(MODULE_NAME, f"Error: {str(e)}", PySystem.Console.MessageType.Error)
        raise


    
if __name__ == "__main__":
    main()
