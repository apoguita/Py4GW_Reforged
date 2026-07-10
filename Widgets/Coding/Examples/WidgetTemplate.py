import PyImGui
from Py4GWCoreLib import Routines, ImGui_Legacy, Color
from Py4GWCoreLib.py4gwcorelib_src.Settings import Settings

MODULE_NAME = "Widget Template" # Change this to your widget name
MODULE_ICON = "Textures/Module_Icons/Template.png" # Change this to your widget icon (optional)
WIDGET_KEY = 'Widgets/Coding/Examples/WidgetTemplate'

# ---------------------------------------
# Settings Handling
# Values persist through Settings under the widget's ini key.
# ---------------------------------------

INI_KEY = ""
INI_PATH = "Widgets/WidgetTemplate" #path to save ini key
INI_FILENAME = "WidgetTemplate.ini" #ini file name
def draw_widget():
    """Draws the widget interface."""
    global INI_KEY
    cfg = Settings.find(INI_KEY)
    if ImGui_Legacy.Begin(INI_KEY,MODULE_NAME, flags=PyImGui.WindowFlags.AlwaysAutoResize):

        PyImGui.text("Add your stuff here")

        if cfg:
            val = cfg.get_bool("TestBoolVar", "value", False)
            new_val = PyImGui.checkbox("Test Bool Variable", val)
            if new_val != val:
                cfg.set("TestBoolVar", "value", new_val)

    ImGui_Legacy.End(INI_KEY)
    
# ---------------------------------------
# Widget lifecycle functions
# ---------------------------------------

#def configure():
#    """
#        Optional
#        If this code is present, it runs when the widget congiguration is active
#    """
#    pass

def tooltip():
    """Optional
        If this code is present, will be used to draw the widget tooltip in the widget manager
    """
    PyImGui.begin_tooltip()

    # Title
    title_color = Color(255, 200, 100, 255)
    ImGui_Legacy.push_font("Regular", 20)
    PyImGui.text_colored(MODULE_NAME, title_color.to_tuple_normalized())
    ImGui_Legacy.pop_font()
    PyImGui.spacing()
    PyImGui.separator()

    # Description
    #ellaborate a better description 
    PyImGui.text("This is a template for creating new widgets.")
    
    PyImGui.spacing()

    # Features
    PyImGui.text_colored("Features:", title_color.to_tuple_normalized())
    PyImGui.bullet_text("Template structure for widget development.")
    PyImGui.bullet_text("Includes configuration variable handling.")
    PyImGui.bullet_text("Basic widget lifecycle functions.")

    PyImGui.spacing()
    PyImGui.separator()
    PyImGui.spacing()

    # Credits
    PyImGui.text_colored("Credits:", title_color.to_tuple_normalized())
    PyImGui.bullet_text("Developed by Mark")
    PyImGui.bullet_text("Contributors: Apo")

    PyImGui.end_tooltip()

       
def draw():
    """this code runs every frame to draw the widget"""
    global initialized
    if initialized:
        draw_widget()

initialized = False
def main():
    """this code runs once to initialize the widget"""
    global INI_KEY, initialized
    if initialized:
        return
    
    #one time initialization
    if not Routines.Checks.Map.MapValid():
        return
    if not INI_KEY:
        INI_KEY = Settings(f"{"Widgets/WidgetTemplate"}/{"WidgetTemplate.ini"}", "account").name
        if not INI_KEY:
            return

        initialized = True
        

if __name__ == "__main__":
    main()
