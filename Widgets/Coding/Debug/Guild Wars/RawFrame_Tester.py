#from Py4GWCoreLib import *
import PyImGui
import PyUIManager
import PyImGui
import PyOverlay
from typing import Dict, List, Tuple
from Py4GWCoreLib.FrameTree import Frame
# aliased: this module defines its own `FrameTree` class below
from Py4GWCoreLib.FrameTree import FrameTree as LiveTree

MODULE_NAME = "Frame Tester (Basic)"
MODULE_ICON = "Assets/Textures/Module_Icons/Frame Tester.png"
# Frame identity comes from the FrameTree name / registry / alias tables
# (Py4GWCoreLib/FrameTree/*.py dict literals), not from a file.

def RGBToNormal(r, g, b, a):
        """return a normalized RGBA tuple from 0-255 values"""
        return r / 255.0, g / 255.0, b / 255.0, a / 255.0
    
def RGBToColor(r, g, b, a) -> int:
        return (a << 24) | (b << 16) | (g << 8) | r
    
def ColorToTuple(color: int) -> Tuple[float, float, float, float]:
        """Convert a 32-bit integer color (ABGR) to a normalized (0.0 - 1.0) RGBA tuple."""
        a = (color >> 24) & 0xFF  # Extract Alpha (highest 8 bits)
        b = (color >> 16) & 0xFF  # Extract Blue  (next 8 bits)
        g = (color >> 8) & 0xFF   # Extract Green (next 8 bits)
        r = color & 0xFF          # Extract Red   (lowest 8 bits)
        return r / 255.0, g / 255.0, b / 255.0, a / 255.0  # Convert to RGBA float

def TupleToColor(color_tuple: Tuple[float, float, float, float]) -> int:
    """Convert a normalized (0.0 - 1.0) RGBA tuple back to a 32-bit integer color (ABGR)."""
    r = int(color_tuple[0] * 255)  # Convert R back to 0-255
    g = int(color_tuple[1] * 255)  # Convert G back to 0-255
    b = int(color_tuple[2] * 255)  # Convert B back to 0-255
    a = int(color_tuple[3] * 255)  # Convert A back to 0-255
    return RGBToColor(r, g, b, a)  # Encode back as ABGR
    
    
def toggle_button(label: str, v: bool, width:float =0.0, height:float =0.0, disabled:bool =False) -> bool:
        """
        Purpose: Create a toggle button that changes its state and color based on the current state.
        Args:
            label (str): The label of the button.
            v (bool): The current toggle state (True for on, False for off).
        Returns: bool: The new state of the button after being clicked.
        """
        clicked = False

        clicked = PyImGui.button(label, width, height)

        if clicked:
            v = not v
            
        return v
    
def table(title:str, headers, data):
    """
    Purpose: Display a table using PyImGui.
    Args:
        title (str): The title of the table.
        headers (list of str): The header names for the table columns.
        data (list of values or tuples): The data to display in the table. 
            - If it's a list of single values, display them in one column.
            - If it's a list of tuples, display them across multiple columns.
        row_callback (function): Optional callback function for each row.
    Returns: None
    """
    if len(data) == 0:
        return  # No data to display

    first_row = data[0]
    if isinstance(first_row, tuple):
        num_columns = len(first_row)
    else:
        num_columns = 1  # Single values will be displayed in one column

    # Start the table with dynamic number of columns
    if PyImGui.begin_table(title, num_columns, PyImGui.TableFlags.Borders | PyImGui.TableFlags.SizingStretchSame | PyImGui.TableFlags.Resizable):
        for i, header in enumerate(headers):
            PyImGui.table_setup_column(header)
        PyImGui.table_headers_row()

        for row in data:
            PyImGui.table_next_row()
            if isinstance(row, tuple):
                for i, cell in enumerate(row):
                    PyImGui.table_set_column_index(i)
                    PyImGui.text(str(cell))
            else:
                PyImGui.table_set_column_index(0)
                PyImGui.text(str(row))

        PyImGui.end_table()
        


def ConstructFramePath(frame_id: int) -> str:
    """Frame path, from the owning handle."""
    return Frame.from_id(frame_id).path() if frame_id else ""


def DescribeFrame(frame_id: int) -> str:
    """Best-known identity: engine name, registry key, then prose alias."""
    return Frame.from_id(frame_id).describe()


#region config options

class ConfigOptions:
    def __init__(self):
        self.keep_data_updated = False
        self.show_frame_data = False
        self.recolor_frame_tree = True
        self.not_created_color = RGBToNormal(150, 150, 150, 255)
        self.not_visible_color = RGBToNormal(180, 0, 0, 255)
        self.no_hash_color = RGBToNormal(150, 0, 150, 255)
        self.identified_color = RGBToNormal(200, 180, 0, 255)
        self.base_color = RGBToNormal(255, 255, 255, 255)
        
config_options = ConfigOptions()

#endregion


#region FrameTree

class FrameNode:
    global config_options
    def __init__(self, frame_id: int, parent_id: int):
        self.frame_id = frame_id
        self.parent_id = parent_id
        self.frame_obj = Frame.from_id(self.frame_id)
        self.info_window = InfoWindow(self.frame_obj)
        self.frame_hash = self.frame_obj.hash
        self.child_offset_id = self.frame_obj.code
        self.label = DescribeFrame(self.frame_id)
        self.parent = None  # Will be set when building the tree
        self.children = []  # Stores child nodes
        self.show_frame_data = False
        
    def update(self):
        self.frame_obj.refresh()
        self.frame_hash = self.frame_obj.hash
        self.label = DescribeFrame(self.frame_id)

    def get_parent(self):
        """Returns the parent node of this frame."""
        return self.parent

    def get_children(self):
        """Returns a list of all child nodes."""
        return self.children

    def draw(self):
        """Recursively renders the tree hierarchy using PyImGui."""
        def choose_frame_color():
            if not self.frame_obj.is_created:
                return config_options.not_created_color
            elif not self.frame_obj.is_visible:
                return config_options.not_visible_color
            elif self.label:
                return config_options.identified_color
            elif not self.frame_hash or self.frame_hash == 0:
                return config_options.no_hash_color
            else:
                return config_options.base_color
            
        if self.children:
            PyImGui.push_style_color(PyImGui.ImGuiCol.Text, choose_frame_color())
            if PyImGui.tree_node(f"Frame:[{self}] <{self.frame_hash}> ({self.label}) ##{self.widget_id}"):
                PyImGui.pop_style_color(1)
                PyImGui.same_line(0,-1)
                self.show_frame_data = toggle_button(f"Show Data##{self.widget_id}", self.show_frame_data, width=70,height=17)
                if self.frame_id != 0:
                    if config_options.show_frame_data:
                        if PyImGui.collapsing_header(f"Frame#{self}Data##{self.widget_id}"):
                            headers = ["Value", "Data"]
                            data = [
                                ("Parent:", self.parent_id),
                                ("Is Visible:", self.frame_obj.is_visible),
                                ("Is Created:", self.frame_obj.is_created),
                            ]
                            table("frametester info##{self.frame_id}", headers, data)
                PyImGui.separator()
                
                for child in self.children:
                    child.draw()  # Recursively draw children
                PyImGui.tree_pop()  # Close tree node
            else:
                PyImGui.pop_style_color(1)
        else:
            PyImGui.text_colored(f"Frame:[{self}] <{self.frame_hash}> ({self.label})",choose_frame_color())  # Leaf node
            PyImGui.same_line(0,-1)
            self.show_frame_data = toggle_button(f"Show Data##{self.widget_id}", self.show_frame_data, width=70,height=17)
            if config_options.show_frame_data:
                if PyImGui.collapsing_header(f"Frame#{self}Data##{self.widget_id}"):
                    headers = ["Value", "Data"]
                    data = [
                        ("Parent:", self.parent_id),
                        ("Is Visible:", self.frame_obj.is_visible),
                        ("Is Created:", self.frame_obj.is_created),
                    ]
                    table("frametester info##{self.frame_id}", headers, data)
            PyImGui.separator()
                    
        if self.show_frame_data:
            self.info_window.Draw()


class FrameTree:
    def __init__(self):
        self.nodes = {}  # Stores frame_id -> FrameNode
        self.root = None  # Root of the tree
        
    def update(self):
        """Updates all nodes in the tree."""
        for node in self.nodes.values():
            node.update()

    def build_tree(self, frame_list: List[int]):
        """
        Builds the tree from a list of frame IDs.
        Uses PyUIManager.UIFrame to retrieve parent information.
        """
        # Step 1: Create nodes
        for frame_id in frame_list:
            frame_obj = Frame.from_id(frame_id)
            parent_id = frame_obj.parent_id  # Extract parent ID
            self.nodes[frame_id] = FrameNode(frame_id, parent_id)

        # Step 2: Assign parents and children
        for frame_id, node in self.nodes.items():
            if node.parent_id == 0:
                self.root = node  # Root node
            elif node.parent_id in self.nodes:
                node.parent = self.nodes[node.parent_id]  # Set parent reference
                self.nodes[node.parent_id].children.append(node)  # Add as child

    def get_node(self, frame_id: int):
        """Retrieves a node by its ID."""
        return self.nodes.get(frame_id, None)

    def draw(self):
        """Draws the entire hierarchy using PyImGui."""
        if self.root:
            self.root.draw()



#end region

_overlay = PyOverlay.Overlay()

def GetFrameArray():
    """
    Get the frame array.

    :return: list: The frame array.
    """
    return LiveTree.all_ids()

def IsFrameCreated(frame_id):
    """
    Check if a frame is created.

    :param frame_id: The ID of the frame.
    :return: bool: True if the frame is created, False otherwise.
    """
    return Frame.from_id(frame_id).is_created

def IsVisible(frame_id):
    """
    Check if a frame is visible.

    :param frame_id: The ID of the frame.
    :return: bool: True if the frame is visible, False otherwise.
    """
    return Frame.from_id(frame_id).is_visible

def FrameExists(frame_id):
    """
    Check if a frame exists.

    :param frame_id: The ID of the frame.
    :return: bool: True if the frame exists, False otherwise.
    """
    frame_aray = GetFrameArray()
    if frame_id not in frame_aray:
        return False
    return IsFrameCreated(frame_id) and IsVisible(frame_id)

def GetFrameCoords(frame_id):
    """
    Get the coordinates of a frame.

    :param frame_id: The ID of the frame.
    :return: top, left, bottom, right coordinates of the frame.
    """
    frame = Frame.from_id(frame_id)
    top = frame.position.top_on_screen
    left = frame.position.left_on_screen
    bottom = frame.position.bottom_on_screen
    right = frame.position.right_on_screen
    return left,top, right, bottom

def DrawFrame(frame_id:int, draw_color:int):
    global _overlay
    """
    Draw a frame on the UI.

    :param frame_id: The ID of the frame.
    """
    if not FrameExists(frame_id):
        return
    
    left, top, right, bottom = GetFrameCoords(frame_id)
    p1 = PyOverlay.Vec2f(left, top)
    p2 = PyOverlay.Vec2f(right, top)
    p3 = PyOverlay.Vec2f(right, bottom)
    p4 = PyOverlay.Vec2f(left, bottom)
    _overlay.BeginDraw()
    _overlay.DrawQuadFilled(p1,p2,p3,p4, draw_color)
    _overlay.EndDraw()
    
def FrameClick(frame_id):
    """
    Click a frame on the UI.

    :param frame_id: The ID of the frame.
    """
    if not FrameExists(frame_id):
        return
    (lambda fid: Frame.from_id(fid).click())(frame_id)
    
def TestMouseAction(frame_id, current_state, wparam_value, lparam_value=0):
    """
    Test mouse action on a frame.

    :param frame_id: The ID of the frame.
    :param current_state: The current state of the mouse.
    :param wparam_value: The wparam value.
    """
    if not FrameExists(frame_id):
        return
    (lambda fid, s, w=0, l=0: Frame.from_id(fid).mouse_action(s, w, l))(frame_id, current_state, wparam_value, lparam_value)
    
def TestMouseClickAction(frame_id, current_state, wparam_value, lparam_value=0):
    """
    Test mouse click action on a frame.

    :param frame_id: The ID of the frame.
    :param current_state: The current state of the mouse.
    :param wparam_value: The wparam value.
    """
    if not FrameExists(frame_id):
        return
    (lambda fid, s, w=0, l=0: Frame.from_id(fid).mouse_click_action(s, w, l))(frame_id, current_state, wparam_value, lparam_value)

#region InfoWindow
double_action = False

class InfoWindow:
    from PyUIManager import UIFrame
    def __init__(self, frame_obj:UIFrame):
        self.frame = frame_obj 
        self.auto_update = True
        self.draw_frame = True
        self.draw_color :int = RGBToColor(0, 255, 0, 125)
        self.monitor_callbacks = False
        self.frame_alias = DescribeFrame(self.frame.frame_id)
        self.window_name = ""
        self.setWindowName()
        self.current_state = 0
        self.wparam = 0
        self.lparam = 0
        
    def setWindowName(self):
        if self.frame_alias:
            self.window_name = f"Frame[{self.frame}] Hash:<{self.frame.hash}> Alias:\"{self.frame_alias}\"##{self.frame.widget_id}"
        else:
            self.window_name = f"Frame[{self.frame}] Hash:<{self.frame.hash}>##{self.frame.widget_id}"

          
      
    def DrawFrame(self):
        DrawFrame(self.frame.frame_id, self.draw_color)
        
    def MonitorCallbacks(self):
        pass
    
    def to_hex(self,value: int) -> str:
        return f"0x{value:X}"
    
    def to_bin(self,value: int) -> str:
        return bin(value)
    
    def to_char(self,value: int) -> str:
        byte_values = value.to_bytes(4, byteorder="little", signed=False)
        return "".join(chr(b) if 32 <= b <= 126 else "." for b in byte_values)


    
    def Draw(self):
        global config_options
        global full_tree
        global double_action
        if PyImGui.begin(f"{self.window_name}##{self.frame.widget_id}", True, PyImGui.WindowFlags.AlwaysAutoResize):
            if not config_options.keep_data_updated:
                self.auto_update = PyImGui.checkbox(f"Auto Update##{self.frame.widget_id}", self.auto_update)
            self.draw_frame = PyImGui.checkbox(f"Draw Frame##{self.frame.widget_id}", self.draw_frame)
            if self.draw_frame:
                PyImGui.same_line(0,-1)
                self.draw_color = TupleToColor(PyImGui.color_edit4("Color", ColorToTuple(self.draw_color)))
            
            self.monitor_callbacks = PyImGui.checkbox("Monitor Callbacks", self.monitor_callbacks)
            
            if self.auto_update:
                self.frame.refresh()
            if self.draw_frame:
                self.DrawFrame()   
            if self.monitor_callbacks:
                self.MonitorCallbacks()
                
            PyImGui.separator()
            if PyImGui.begin_child("FrameTreeChild",size=(1000,800),border=True,flags=PyImGui.WindowFlags.HorizontalScrollbar):
                if PyImGui.begin_tab_bar(f"FrameDebuggerIndividualTabBar##{self.frame.widget_id}"):
                    if PyImGui.begin_tab_item(f"Frame Tree##{self.frame.widget_id}"):
                        PyImGui.text(f"Frame ID: {self.frame}")
                        PyImGui.text(f"Frame Hash: {self.frame.hash}")
                        _handle = self.frame
                        PyImGui.text(f"Engine Name: {_handle.name or '(unnamed)'}")
                        PyImGui.text(f"Registry Key: {_handle.registry_key or '(unregistered)'}")
                        PyImGui.text(f"Alias: {_handle.alias or '(none)'}")
                        PyImGui.text(f"Path: {_handle.path() or '(unresolved)'}")
                        if PyImGui.button(f"Copy Registry Key##{self.frame.widget_id}"):
                            PyImGui.set_clipboard_text(_handle.registry_key or _handle.path())

                        if PyImGui.button(f"Click on frame{self.frame}##click{self.frame}"):
                            FrameClick(self.frame.frame_id)
                            print (f"Clicked on frame {self.frame}")
                            
                        PyImGui.separator()
                        self.current_state = PyImGui.input_int(f"Current State##{self.frame.widget_id}", self.current_state)
                        self.wparam = PyImGui.input_int(f"wParam##{self.frame.widget_id}", self.wparam)
                        self.lparam = PyImGui.input_int(f"lParam##{self.frame.widget_id}", self.lparam)
                        if PyImGui.button((f"test mouse action##{self.frame.widget_id}")):
                            TestMouseAction(self.frame.frame_id, self.current_state, self.wparam, self.lparam)
                            self.current_state += 1
                            if self.current_state in (6, 10, 8):
                                self.current_state += 1
                            if self.current_state > 10:
                                self.current_state = 0
                                self.wparam += 1
                                if self.wparam > 10:
                                    self.wparam = 0
                                    self.lparam += 1
                                    
                            print (f"Tested on frame {self.frame}")
                            
                        if PyImGui.button((f"test mouse click action##{self.frame.widget_id}")):
                            TestMouseClickAction(self.frame.frame_id, self.current_state, self.wparam, self.lparam)
                            self.current_state += 1
                            #if self.current_state in (6, 10, 8):
                            #    self.current_state += 1
                            if self.current_state > 10:
                                self.current_state = 0
                                self.wparam += 1
                                if self.wparam > 10:
                                    self.wparam = 0
                                    self.lparam += 1
                                    
                            print (f"Tested on frame {self.frame}")


                        PyImGui.text(f"Parent ID: {self.frame.parent_id}")
                        PyImGui.text(f"Visibility Flags: {self.frame.visibility_flags}")
                        PyImGui.text(f"Is Visible: {self.frame.is_visible}")
                        PyImGui.text(f"Is Created: {self.frame.is_created}")
                        PyImGui.text(f"Type: {self.frame.type}")
                        PyImGui.text(f"Template Type: {self.frame.template_type}")
                        PyImGui.text(f"Frame Layout: {self.frame.frame_layout}")
                        PyImGui.text(f"Child Offset ID: {self.frame.code}")
                        PyImGui.end_tab_item()
                    if PyImGui.begin_tab_item(f"Position##{self.frame.widget_id}"):
                        PyImGui.text(f"Top: {self.frame.position.top}")
                        PyImGui.text(f"Left: {self.frame.position.left}")
                        PyImGui.text(f"Bottom: {self.frame.position.bottom}")
                        PyImGui.text(f"Right: {self.frame.position.right}")
                        PyImGui.text(f"Content Top: {self.frame.position.content_top}")
                        PyImGui.text(f"Content Left: {self.frame.position.content_left}")
                        PyImGui.text(f"Content Bottom: {self.frame.position.content_bottom}")
                        PyImGui.text(f"Content Right: {self.frame.position.content_right}")
                        PyImGui.text(f"Unknown: {self.frame.position.unknown}")
                        PyImGui.text(f"Scale Factor: {self.frame.position.scale_factor}")
                        PyImGui.text(f"Viewport Width: {self.frame.position.viewport_width}")
                        PyImGui.text(f"Viewport Height: {self.frame.position.viewport_height}")
                        PyImGui.text(f"Screen Top: {self.frame.position.screen_top}")
                        PyImGui.text(f"Screen Left: {self.frame.position.screen_left}")
                        PyImGui.text(f"Screen Bottom: {self.frame.position.screen_bottom}")
                        PyImGui.text(f"Screen Right: {self.frame.position.screen_right}")
                        PyImGui.text(f"Top on Screen: {self.frame.position.top_on_screen}")
                        PyImGui.text(f"Left on Screen: {self.frame.position.left_on_screen}")
                        PyImGui.text(f"Bottom on Screen: {self.frame.position.bottom_on_screen}")
                        PyImGui.text(f"Right on Screen: {self.frame.position.right_on_screen}")
                        PyImGui.text(f"Width on Screen: {self.frame.position.width_on_screen}")
                        PyImGui.text(f"Height on Screen: {self.frame.position.height_on_screen}")
                        PyImGui.text(f"Viewport Scale X: {self.frame.position.viewport_scale_x}")
                        PyImGui.text(f"Viewport Scale Y: {self.frame.position.viewport_scale_y}")
                        PyImGui.end_tab_item()
                    if PyImGui.begin_tab_item(f"Relation##{self.frame.widget_id}"):
                        PyImGui.text(f"Parent ID: {self.frame.parent_id}")
                        PyImGui.text("Field67_0x124: " + str(self.frame.fields().get('relation.field67_0x124', 0)))
                        PyImGui.text("Field68_0x128: " + str(self.frame.fields().get('relation.field68_0x128', 0)))
                        PyImGui.text(f"Frame Hash ID: {self.frame.hash}")
                        if PyImGui.collapsing_header("Siblings"):
                            for i, sibling in enumerate(self.frame.siblings()):
                                PyImGui.text(f"Siblings[{i}]: {sibling.describe() or sibling}")
                        PyImGui.end_tab_item()
                    if PyImGui.begin_tab_item(f"Callbacks##{self.frame.widget_id}"):
                        for i, callback in enumerate(self.frame.frame_callbacks):
                            PyImGui.text(f"{i}: {callback.get_address()} - Hex({self.to_hex(callback.get_address())})")


                        PyImGui.end_tab_item()

                    if PyImGui.begin_tab_item(f"Extra Fields##{self.frame.widget_id}"):
                        # Prepare data list
                        data = []
                        
                        # Define headers
                        headers = ["Field", "Dec", "Hex", "Bin", "Char"]
                        
                        data = [
                            *[
                                (name, str(value), self.to_hex(value), self.to_bin(value), self.to_char(value))
                                for name, value in self.frame.fields().items()
                            ],
                        ]

                        parameter_list = self.frame.parameters
                        for i, parameter in enumerate(parameter_list):
                            data.append((f"Field31_0x84[{i}]",
                                        str(parameter),
                                        self.to_hex(parameter),
                                        self.to_bin(parameter),
                                        self.to_char(parameter)))

                        data.extend([
                            *[
                                (name, str(value), self.to_hex(value), self.to_bin(value), self.to_char(value))
                                for name, value in self.frame.fields().items()
                            ],
                        ])

                        
                        
    
                        table(f"Frame Data##{self.frame.widget_id}", headers, data)

                        PyImGui.end_tab_item()
                    PyImGui.end_tab_bar()
                PyImGui.end_child()               
        PyImGui.end()
   
# endregion

#region MainWindow
module_name = "Frame Tester"

frame_array = []
full_tree = FrameTree()




def DrawMainWindow():
    global frame_array
    global full_tree
    global config_options
    
    if config_options.keep_data_updated:
        full_tree.update()
    
    

    if PyImGui.begin("frame tester window", True, PyImGui.WindowFlags.AlwaysAutoResize):
        if PyImGui.begin_tab_bar("FrameDebuggerTabBar"):
            if PyImGui.begin_tab_item("Frame Tree"):
                if PyImGui.collapsing_header("options"):
                    config_options.keep_data_updated = PyImGui.checkbox("Keep all frame Data Updated", config_options.keep_data_updated)
                    #ImGui.show_tooltip("This will lower fps!")
                    config_options.show_frame_data = PyImGui.checkbox("Show Frame Data", config_options.show_frame_data)
                    config_options.recolor_frame_tree = PyImGui.checkbox("Recolor Frame Tree", config_options.recolor_frame_tree)

                build_button_text = "Build Frame Tree"
                if frame_array:
                    build_button_text = "Rebuild Frame Tree"
                    
                if PyImGui.button(build_button_text):
                    frame_array = GetFrameArray()
                    full_tree.build_tree(frame_array)    
                    
                PyImGui.text_colored("Not Created", config_options.not_created_color)
                PyImGui.same_line(0,-1)
                PyImGui.text_colored("Not Visible", config_options.not_visible_color)
                PyImGui.same_line(0,-1)
                PyImGui.text_colored("No Hash", config_options.no_hash_color)
                PyImGui.same_line(0,-1)
                PyImGui.text_colored("Identified", config_options.identified_color)
                PyImGui.same_line(0,-1)
                PyImGui.text_colored("Base", config_options.base_color)
                
                PyImGui.separator()
                
                if PyImGui.begin_child("FrameTreeChild",size=(900,800),border=True,flags=PyImGui.WindowFlags.HorizontalScrollbar):                                        
                    if frame_array:
                        full_tree.draw()

                    PyImGui.end_child()

                PyImGui.end_tab_item()
            PyImGui.end_tab_bar()

    PyImGui.end()
    
#endregion

def tooltip():
    PyImGui.begin_tooltip()

    # Title
    title_color = (1.0,0.78, 0.4,1.0)

    PyImGui.text_colored("UI Frame Tester", title_color)

    PyImGui.spacing()
    PyImGui.separator()

    # Description
    PyImGui.text("Frame Tester with no Unnecessary Imports")

    PyImGui.spacing()

    # Features
    PyImGui.text_colored("Features:", title_color)
    PyImGui.bullet_text("Frame Tree: Hierarchical visualization of all UI elements (AdvUI)")
    PyImGui.bullet_text("Visual Debugging: Real-time screen highlighting of selected UI Frames")
    PyImGui.bullet_text("State Tracking: Color-coded indicators for Visible, Hidden, and Uncreated frames")
    PyImGui.bullet_text("Alias Manager: Map frame hashes to human-readable names via JSON")
    PyImGui.bullet_text("Detail Inspector: View frame IDs, parentage, child counts, and internal hashes")

    PyImGui.spacing()
    PyImGui.separator()
    PyImGui.spacing()

    # Credits
    PyImGui.text_colored("Credits:", title_color)
    PyImGui.bullet_text("Developed by Apo")

    PyImGui.end_tooltip()



def main():
    DrawMainWindow()


if __name__ == "__main__":
    main()
