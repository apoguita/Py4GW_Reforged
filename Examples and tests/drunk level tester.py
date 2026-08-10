import Py4GW
from Py4GWCoreLib import *

MODULE_NAME = "tester for everything"

drunk_level = 0
tint = 0

def main():
    global drunk_level, tint
    try:
        window_flags=PyImGui.WindowFlags.AlwaysAutoResize #| PyImGui.WindowFlags.MenuBar
        if PyImGui.begin("drunk test", window_flags):
            PyImGui.text(f"Drunk Level: {Effects.GetAlcoholLevel()}")
            drunk_level = PyImGui.input_int("Drunk Level", drunk_level)
            tint = PyImGui.input_int("Tint", tint)
            if PyImGui.button("set drunk effect"):
                Effects.ApplyDrunkEffect(drunk_level, tint)
            
        PyImGui.end()
        


    except Exception as e:
        PySystem.Console.Log(MODULE_NAME, f"Error: {str(e)}", PySystem.Console.MessageType.Error)
        raise


    
if __name__ == "__main__":
    main()
