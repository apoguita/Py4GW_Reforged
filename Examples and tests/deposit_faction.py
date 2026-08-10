import Py4GW
from Py4GWCoreLib import *

MODULE_NAME = "tester for fonts"


def main():
    global npc_name
    try:
        window_flags=PyImGui.WindowFlags.AlwaysAutoResize #| PyImGui.WindowFlags.MenuBar
        if PyImGui.begin("move", window_flags):
            if PyImGui.button("donate"):
                Player.DepositFaction(0)
            
            
        PyImGui.end()
        


    except Exception as e:
        PySystem.Console.Log(MODULE_NAME, f"Error: {str(e)}", PySystem.Console.MessageType.Error)
        raise


    
if __name__ == "__main__":
    main()
