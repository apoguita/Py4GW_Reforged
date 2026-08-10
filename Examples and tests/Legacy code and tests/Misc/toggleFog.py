from Py4GWCoreLib import *
import time
import sys
import os



MODULE_NAME = "tester for everything"

fog = False

def DrawWindow():
    """ImGui draw function that runs every frame."""
    global fog
    try:
        flags = PyImGui.WindowFlags.NoScrollbar | PyImGui.WindowFlags.NoScrollWithMouse | PyImGui.WindowFlags.AlwaysAutoResize
        if PyImGui.begin("Py4GW", flags):

            if PyImGui.button("Toggle Fog"):
                PyCamera.PyCamera().SetFog(fog)
        PyImGui.end()

    except Exception as e:
        PySystem.Console.Log("tester", f"Unexpected Error: {str(e)}", PySystem.Console.MessageType.Error)

def main():
    """Runs every frame."""
    DrawWindow()

if __name__ == "__main__":
    main()
