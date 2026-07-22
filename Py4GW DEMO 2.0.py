import PyImGui
from Sources.ApoSource.py4gw_demo_src import registry

MODULE_NAME = "Py4GW DEMO 2.0"
MODULE_ICON = "Textures/Module_Icons/Py4GW.png"


#region Main Window
def draw_window():
    # Layout, grouped nav, selection, per-panel error isolation and markdown help
    # are all handled by ImGui.SidebarWindow (built in registry from the GROUPS
    # registry). The whole sidebar+content window is one call.
    registry.get_window().draw()


def tooltip():
    PyImGui.begin_tooltip()
    PyImGui.text_colored("Py4GW Demo 2.0", (1.0, 0.78, 0.39, 1.0))
    PyImGui.separator()
    PyImGui.text("Live API reference AND access/debug test tool for the Py4GW backend.")
    PyImGui.text("Each panel shows data and probes every binding/getter for access.")
    PyImGui.spacing()
    PyImGui.text_colored("Coverage grows per docs/demo_replacement/11_build_plan.md", (0.6, 0.6, 0.65, 1.0))
    PyImGui.bullet_text("Green OK = binding resolved; Red ERR = raised")
    PyImGui.bullet_text("Action buttons test mutate/send bindings live")
    PyImGui.spacing()
    PyImGui.text_colored("Developed by Apo", (1.0, 0.78, 0.39, 1.0))
    PyImGui.end_tooltip()


def main():
    draw_window()


if __name__ == "__main__":
    main()
