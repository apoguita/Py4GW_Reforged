
from enum import Enum

import PyImGui
import PyUIManager
import time
from typing import Dict, List, Optional
import PyOverlay
from collections import deque, defaultdict

from Py4GWCoreLib.py4gwcorelib_src.FrameCache import frame_cache
from .Py4GWcorelib import ConsoleLog, Console
from .enums_src.Item_enums import INVENTORY_BAGS, INVENTORY_WITH_EQUIPMENT_BAGS, STORAGE_BAGS, Bags, SalvageMode
from .enums_src.UI_enums import WindowID
from dataclasses import dataclass, field
from .native_src.internals.types import Vec2f
from typing import Any, TypedDict
from .Scanner import Scanner
from .FrameTree import Frame, FrameId, FrameTree

# —— Constants ——————————————————
NPC_DIALOG_HASH    = 3856160816
DEFAULT_OFFSET     = [2, 0, 0, 1]
DIALOG_CHILD_OFFSET = list(DEFAULT_OFFSET)

# —— Globals —————————————————


class UIManager:  
    _overlay = PyOverlay.Overlay()
    _devtext_dialog_proc_cache: int = 0
    
    class IOEvent(TypedDict):
        timestamp: int
        event_type: str
        mouse_pos: tuple[float, float]
        details: Dict[str, Any]
     
    frame_callbacks: list[int] = []
    frame_io_events: Dict[int, List[IOEvent]] = defaultdict(list)
    
    @staticmethod
    def RegisterFrameIOEventCallback(frame):
        """
        Register a frame ID to track IO events.

        :param frame: The frame handle to register.
        """
        if frame not in UIManager.frame_callbacks:
            UIManager.frame_callbacks.append(frame)
            
    @staticmethod
    def UnregisterFrameIOEventCallback(frame):
        """
        Unregister a frame ID from tracking IO events.

        :param frame: The frame handle to unregister.
        """
        if frame in UIManager.frame_callbacks:
            UIManager.frame_callbacks.remove(frame)
            if frame in UIManager.frame_io_events:
                del UIManager.frame_io_events[frame]
                
    
    @staticmethod
    def _UpdateFrameIOEvents():
        """
        Update IO events for registered frame IDs.
        """
        import PyImGui
        import PySystem
        from .enums_src.IO_enums import MouseButton

        io = PyImGui.get_io()
        mouse_pos = (io.mouse_pos_x, io.mouse_pos_y)
        timestamp = PySystem.get_tick_count64()
        
        for frame in UIManager.frame_callbacks:
            if not frame.is_usable:
                continue

            if not frame.is_mouse_over():
                continue

            is_left_mouse_clicked = PyImGui.is_mouse_clicked(MouseButton.Left.value)
            is_right_mouse_clicked = PyImGui.is_mouse_clicked(MouseButton.Right.value)
            is_middle_mouse_clicked = PyImGui.is_mouse_clicked(MouseButton.Middle.value)
            is_double_clicked = PyImGui.is_mouse_double_clicked(MouseButton.Left.value)
            scroll_y_delta = io.mouse_wheel
            scroll_x_delta = io.mouse_wheel_h
            
            def _add_event(event_type: str, details: Dict[str, Any] = {}):
                event: UIManager.IOEvent = {
                    "timestamp": timestamp,
                    "event_type": event_type,
                    "mouse_pos": mouse_pos,
                    "details": details
                }

                # ensure list exists for this frame
                if frame not in UIManager.frame_io_events:
                    UIManager.frame_io_events[frame] = []

                # search for existing event and update instead of adding a duplicate
                for i, existing in enumerate(UIManager.frame_io_events[frame]):
                    if existing.get("event_type") == event_type:
                        UIManager.frame_io_events[frame][i] = event
                        break
                else:
                    # not found -> append new
                    UIManager.frame_io_events[frame].append(event)
                
            if is_left_mouse_clicked:
                _add_event("left_mouse_clicked")
            
            if is_right_mouse_clicked:
                _add_event("right_mouse_clicked")
                
            if is_middle_mouse_clicked:
                _add_event("middle_mouse_clicked")
                
            if is_double_clicked:
                _add_event("double_clicked")
                
            if scroll_y_delta != 0.0:
                _add_event("mouse_wheel_scrolled", {"scroll_y_delta": scroll_y_delta})
                
            if scroll_x_delta != 0.0:
                _add_event("mouse_wheel_scrolled_horizontal", {"scroll_x_delta": scroll_x_delta})
                
    @staticmethod
    def GetIOEventsForFrame(frame) -> List[IOEvent]:
        """
        Get the list of IO events for a specific frame ID.

        :param frame: The frame handle to retrieve events for.
        :return: List[IOEvent]: List of IO events for the frame.
        """
        #lazy load the list if it doesn't exist
        if frame not in UIManager.frame_callbacks:
            UIManager.frame_callbacks.append(frame)
        
        return UIManager.frame_io_events.get(frame, [])
    
    @staticmethod
    def RegisterFrameIOCallbacks():
        """
        Register the frame IO event update callback.
        """
        import PyCallback
        PyCallback.PyCallback.Register(
            "UIManager.UpdateFrameIOEvents",
            PyCallback.Phase.Data,
            UIManager._UpdateFrameIOEvents,
            priority=2,
            context=PyCallback.Context.Draw
        )


    @staticmethod
    def GetFrameLogs() -> List[tuple[int, int, str]]:
        """
        Get the frame logs.

        :return: list of tuples: Each tuple contains (timestamp, frame_id, frame_label).
        """
        return PyUIManager.UIManager.get_frame_logs()
    
    @staticmethod
    def ClearFrameLogs() -> None:
        """
        Clear the frame logs.
        """
        PyUIManager.UIManager.clear_frame_logs()
    
    @staticmethod
    def GetUIMessageLogs() -> List[tuple[int, int, bool, bool, int, list[int], list[int]]]:
        """
        Get the UI message logs.

        :return: list of tuples: Each tuple contains (timestamp, msgid, incoming, is_frame_message, frame_id, wparam_bytes, lparam_bytes).
        """
        return PyUIManager.UIManager.get_ui_message_logs()
    
    @staticmethod
    def ClearUIMessageLogs() -> None:
        """
        Clear the UI message logs.
        """
        PyUIManager.UIManager.clear_ui_message_logs()


    @staticmethod
    def GetTextLanguage() -> int:
        return PyUIManager.UIManager.get_text_language()


    @staticmethod
    def SendUIMessage(msgid: int, values: list[int],skip_hooks: bool = False ) -> bool:
        return PyUIManager.UIManager.SendUIMessage(msgid, values, skip_hooks)
    
    @staticmethod
    def SendUIMessageRaw(msgid: int, wparam: int, lparam: int, skip_hooks: bool = False ) -> bool:
        return PyUIManager.UIManager.SendUIMessageRaw(msgid, wparam, lparam, skip_hooks)


    @staticmethod
    def DrawOnCompass(session_id: int, points: list[tuple[int, int]]) -> bool:
        return PyUIManager.UIManager.draw_on_compass(session_id, points)

    @staticmethod
    def LoadSettings(data: list[int]) -> None:
        PyUIManager.UIManager.load_settings(data)

    @staticmethod
    def GetSettings() -> list[int]:
        return PyUIManager.UIManager.get_settings()

    @staticmethod
    def GetCurrentTooltipAddress() -> int:
        return PyUIManager.UIManager.get_current_tooltip_address()

    # CreateUIComponent callback binding is intentionally disabled for now.
    # The runtime path was destabilizing validation runs and should only be
    # restored when callback-specific work is resumed.
    #
    # @staticmethod
    # def RegisterCreateUIComponentCallback(callback, altitude: int = -0x8000) -> int:
    #     return int(PyUIManager.UIManager.register_create_ui_component_callback(callback, altitude) or 0)
    #
    # @staticmethod
    # def RemoveCreateUIComponentCallback(handle: int) -> bool:
    #     return bool(PyUIManager.UIManager.remove_create_ui_component_callback(handle))


    @staticmethod
    def IsWorldMapShowing():
        """
        Check if the world map is showing.

        :return: bool: True if the world map is showing, False otherwise.
        """
        return PyUIManager.UIManager.is_world_map_showing()

    @staticmethod
    def IsUIDrawn() -> bool:
        return PyUIManager.UIManager.is_ui_drawn()

    @staticmethod
    def AsyncDecodeStr(enc_str: str) -> str:
        return PyUIManager.UIManager.async_decode_str(enc_str)

    @staticmethod
    def IsValidEncStr(enc_str: str) -> bool:
        return PyUIManager.UIManager.is_valid_enc_str(enc_str)

    @staticmethod
    def IsValidEncBytes(enc_bytes: bytes) -> bool:
        return bool(PyUIManager.UIManager.is_valid_enc_bytes(bytes(enc_bytes or b"")))

    @staticmethod
    def UInt32ToEncStr(value: int) -> str:
        return PyUIManager.UIManager.uint32_to_enc_str(value)

    @staticmethod
    def EncStrToUInt32(enc_str: str) -> int:
        return PyUIManager.UIManager.enc_str_to_uint32(enc_str)

    @staticmethod
    def SetOpenLinks(toggle: bool) -> None:
        PyUIManager.UIManager.set_open_links(toggle)
    
    @staticmethod
    def IsShiftScreenshot():
        """
        Check if the shift screenshot is enabled.

        :return: bool: True if shift screenshot is enabled, False otherwise.
        """
        return PyUIManager.UIManager.is_shift_screenshot()
            
    @staticmethod
    def GetFPSLimit():
        """
        Get the frame limit.

        :return: int: The frame limit.
        """
        return PyUIManager.UIManager.get_frame_limit()
    
    @staticmethod
    def SetFPSLimit(limit):
        """
        Set the frame limit.

        :param limit: The frame limit.
        """
        PyUIManager.UIManager.set_frame_limit(limit)


    @staticmethod
    def GetPreferenceOptions(pref:int) -> List[int]:
        return PyUIManager.UIManager.get_preference_options(pref)
    
    @staticmethod
    def GetEnumPreference(pref:int) -> int:
        return PyUIManager.UIManager.get_enum_preference(pref)
    
    @staticmethod
    def GetIntPreference(pref:int) -> int:
        return PyUIManager.UIManager.get_int_preference(pref)
    
    @staticmethod
    def GetStringPreference(pref:int) -> str:
        return PyUIManager.UIManager.get_string_preference(pref)
    
    @staticmethod
    def GetBoolPreference(pref:int) -> bool:
        return PyUIManager.UIManager.get_bool_preference(pref)
    
    @staticmethod
    def SetEnumPreference(pref:int, value:int) -> None:
        PyUIManager.UIManager.set_enum_preference(pref, value)
    
    @staticmethod
    def SetIntPreference(pref:int, value:int) -> None:
        PyUIManager.UIManager.set_int_preference(pref, value)
        
    @staticmethod
    def SetStringPreference(pref:int, value:str) -> None:
        PyUIManager.UIManager.set_string_preference(pref, value)
        
    @staticmethod
    def SetBoolPreference(pref:int, value:bool) -> None:
        PyUIManager.UIManager.set_bool_preference(pref, value)
        
    @staticmethod
    def GetKeyMappings() -> List[int]:
        return PyUIManager.UIManager.get_key_mappings()
    
    @staticmethod
    def SetKeyMappings(mappings: List[int]) -> None:
        PyUIManager.UIManager.set_key_mappings(mappings)
        
    @staticmethod
    def Keydown(key:int, frame_id:int) -> None:
        PyUIManager.UIManager.key_down(key,frame_id)
        
    @staticmethod
    def Keyup(key:int, frame_id:int) -> None:
        PyUIManager.UIManager.key_up(key,frame_id)
        
    @staticmethod
    def Keypress(key:int, frame_id:int) -> None:
        PyUIManager.UIManager.key_press(key,frame_id)
        
    @staticmethod
    def GetWindoPosition(window_id: int) -> list[int]:
        """
        Get the window position.

        :return: x,y,x1,y1 coordinates of the window.
        """
        return PyUIManager.UIManager.get_window_position(window_id)
    
    @staticmethod
    def IsWindowVisible(window_id: int) -> bool:
        """
        Check if a window is visible.

        :return: True if the window is visible, False otherwise.
        """
        return PyUIManager.UIManager.is_window_visible(window_id)
    
    @staticmethod
    def SetWindowVisible(window_id: int, visible: bool) -> None:
        """
        Set the visibility of a window.

        :param window_id: The ID of the window.
        :param visible: True to show the window, False to hide it.
        """
        PyUIManager.UIManager.set_window_visible(window_id, visible)
        
    @staticmethod
    def SetWindowPosition(window_id: int, position: list[int]) -> None:
        """
        Set the position of a window.

        :param window_id: The ID of the window.
        :param x: The x-coordinate.
        :param y: The y-coordinate.
        """
        PyUIManager.UIManager.set_window_position(window_id, position)
    
    @staticmethod
    def IsLockedChestWindowVisible() -> bool:
        """
        Check if the chest window is visible.

        :return: True if the chest window is visible, False otherwise.
        """
        
        return Frame(FrameId.NpcDialog.UseLockpickButton).is_usable
    
    @staticmethod
    def IsNPCDialogVisible() -> bool:
        """
        Check if the NPC dialog is visible.

        :return: True if the NPC dialog is visible, False otherwise.
        """
        return Frame(FrameId.NpcDialog).is_usable

    @staticmethod
    def FindDialogOffset() -> None:
        """Auto-detects DIALOG_CHILD_OFFSET for the option-container."""
        global DIALOG_CHILD_OFFSET
        root = Frame(FrameId.NpcDialog)
        if not root.exists or not root.is_visible:
            return

        children_map = FrameTree.children_map()

        # BFS: pick the container with the most template_type==1 children
        queue = deque([root])
        best = None
        best_count = 0
        while queue:
            cur = queue.popleft()
            kids = [Frame.from_id(c) for c in children_map.get(cur.frame_id, [])]
            count = sum(1 for c in kids if c.is_visible and c.template_type == 1)
            if count > best_count and count >= 2:
                best_count, best = count, cur
            queue.extend(kids)

        if best is None:
            return

        # Build the path from root -> best.  NOTE: this records sibling *indices*,
        # while the matcher below compares child key codes, so the offset fast
        # path can never hit and GetDialogButtons always falls back to BFS.
        # Pre-existing behaviour, preserved deliberately - see FrameTree notes.
        path = []
        cur = best
        while cur != root:
            parent = cur.parent()
            siblings = children_map.get(parent.frame_id, [])
            if cur.frame_id not in siblings:
                return
            path.insert(0, siblings.index(cur.frame_id))
            cur = parent

        DIALOG_CHILD_OFFSET = path
    
    @staticmethod
    def GetDialogButtons(debug: bool = False) -> list:
        """
        Returns the visible, template_type==1 option buttons as handles,
        sorted top→bottom. Pass debug=True to log offset detection.
        """
        # detect offset once
        if DIALOG_CHILD_OFFSET == DEFAULT_OFFSET:
            UIManager.FindDialogOffset()

        def _is_button(frame: Frame) -> bool:
            return frame.is_visible and frame.template_type == 1

        # try the offset first
        valid = [f for f in FrameTree.frames_at_path(NPC_DIALOG_HASH, DIALOG_CHILD_OFFSET)
                 if _is_button(f)]
        if valid:
            ordered = FrameTree.sort_by_vertical(valid)
            if debug:
                ConsoleLog("DialogHelper", f"Offset IDs -> {ordered}", Console.MessageType.Info)
            return ordered

        # fallback BFS over the whole dialog subtree
        if debug:
            ConsoleLog("DialogHelper", "Falling back to BFS for dialog buttons", Console.MessageType.Info)

        root = Frame(FrameId.NpcDialog)
        if not root.exists:
            return []

        valid = [f for f in FrameTree.descendants(root)
                 if _is_button(f)]
        ordered = FrameTree.sort_by_vertical(valid)
        if debug:
            ConsoleLog("DialogHelper", f"BFS IDs -> {ordered}", Console.MessageType.Info)
        return ordered
    
    @staticmethod
    def ClickDialogButton(choice: int, debug: bool = False) -> bool:
        """
        Click the Nth dialog option (1-based). Returns True if dispatched.
        """
        buttons = UIManager.GetDialogButtons(debug)
        idx = choice - 1
        if idx < 0 or idx >= len(buttons):
            if debug:
                ConsoleLog("DialogHelper", f"Choice #{choice} out of range", Console.MessageType.Warning)
            return False

        target = buttons[idx]
        if debug:
            ConsoleLog(
                "DialogHelper",
                f"Clicking dialog choice #{choice} -> frame {target}",
                Console.MessageType.Info
            )
        target.click()
        return True
    
    @staticmethod
    def GetDialogButtonCount(debug: bool = False) -> int:
        """
        Return the number of visible dialog‐button frames (template_type == 1),
        and log the count if debug=True.
        Log Example: [DialogHelper|Info] Dialog button count 3
        """
        buttons = UIManager.GetDialogButtons(debug)
        count = len(buttons)

        if debug:
            # Log the count to the console as an info message
            ConsoleLog(
                "DialogHelper",
                f"Dialog button count {count}",
                Console.MessageType.Info
            )

        return count
        
    @staticmethod
    def GetDialogButtonFrames(debug: bool = False) -> list[tuple[int, tuple[int, int, int, int]]]:
        '''
        Returns a list of tuples containing the frame ID and its coordinates
        for all visible dialog button frames (template_type == 1), sorted by their vertical position.
        Each tuple is in the format: (frame_id, (left, top, right, bottom))
        '''
        
        if DIALOG_CHILD_OFFSET == DEFAULT_OFFSET:
            UIManager.FindDialogOffset()

        # --- Attempt offset lookup first ---
        valid_frames = [
            (f, f.rect)
            for f in FrameTree.frames_at_path(NPC_DIALOG_HASH, DIALOG_CHILD_OFFSET)
            if f.is_visible and f.template_type == 1
        ]

        if debug:
            ConsoleLog(
                "DialogHelper",
                f"Dialog button frames with offset {DIALOG_CHILD_OFFSET}: {[fid for fid, _ in valid_frames]}",
                Console.MessageType.Info
            )

        # --- Sort by top_on_screen using cached tuples ---
        valid_frames.sort(key=lambda x: x[1][0])

        if debug:
            ConsoleLog(
                "DialogHelper",
                f"Detected dialog button frames: {valid_frames}",
                Console.MessageType.Info
            )

        # If we found frames, return immediately (no fallback needed)
        if valid_frames:
            return valid_frames

        # --- BFS fallback ---
        # The old version hand-rolled a whole-tree UIFrame cache here; the live
        # model already holds one, so this is now a walk over the snapshot.
        if debug:
            ConsoleLog("DialogHelper", "Falling back to BFS for dialog buttons", Console.MessageType.Info)

        root = Frame(FrameId.NpcDialog)
        if not root.exists:
            return []

        result = [
            (f, f.rect)
            for f in FrameTree.descendants(root)
            if f.is_visible and f.template_type == 1
        ]

        # NOTE: sorts by `left`, not `top`, despite the docstring.  Pre-existing
        # behaviour, preserved deliberately - changing the order would change
        # which button a given choice index maps to.
        result.sort(key=lambda x: x[1][0])

        return result
    
    @staticmethod
    def ConfirmMaxAmountDialog():
        '''
        Confirm the max amount dialog such as those from Trading and Dropping items by clicking the relevant buttons.
        '''
        max_amount = Frame(FrameId.MaxButton)
        drop_offer_confirm = Frame(FrameId.OkButton)
        
        if max_amount.exists:
            max_amount.click()
            
        if drop_offer_confirm.exists:
            drop_offer_confirm.click()
    
#region frameInfo


#region Callbacks
#autiomatic IO events was deactivated due to instability over long sessions
#use this feature on demand
#UIManager.RegisterFrameIOCallbacks()
    
class InventoryBagWindow:
    @staticmethod
    def _get_bag_offset(bag: Bags) -> int:
        return bag.value - Bags.Backpack.value
    
    @staticmethod
    @frame_cache(category="InventoryBagWindow", source_lib="IsOpen")
    def IsOpen(bag : Bags) -> bool:
        bag_frame = InventoryBagWindow.GetBagFrame(bag)
        return bag_frame.exists if bag_frame else False
    
    @staticmethod
    @frame_cache(category="InventoryBagWindow", source_lib="GetBagFrame")
    def GetBagFrame(bag : Bags) -> Optional[Frame]:
        if not bag in INVENTORY_WITH_EQUIPMENT_BAGS:
            return None
        
        if InventoryBagWindow._get_bag_offset(bag) < 0:
            return None

        return Frame.inventory_bag(bag)
        
    @staticmethod
    @frame_cache(category="InventoryBagWindow", source_lib="GetBagSlotFrames")
    def GetBagSlotFrames(bag : Bags, bag_size: Optional[int] = None) -> list[Frame]:
        if not bag in INVENTORY_WITH_EQUIPMENT_BAGS:
            return []
        
        offset = InventoryBagWindow._get_bag_offset(bag)
        if offset < 0:
            return []
                
        if bag_size is None:
            from PyInventory import Bag
            bag_instance = Bag(bag.value, bag.name)
            bag_size = bag_instance.GetSize()
            
        frames = []
        for slot in range(bag_size):
            frames.append(Frame.inventory_bag_slot(bag, slot))
        
        return frames
    
class InventoryBagsWindow:
    @staticmethod
    def _get_bag_offset(bag: Bags) -> int:
        return bag.value - Bags.Backpack.value
    
    @staticmethod
    @frame_cache(category="InventoryBagsWindow", source_lib="IsOpen")
    def IsOpen() -> bool:
        return Frame(FrameId.InventoryBagsWindow).exists
    
    @staticmethod
    @frame_cache(category="InventoryBagsWindow", source_lib="GetBagFrame")
    def GetBagSlotFrames(bag : Bags, bag_size: Optional[int] = None) -> list[Frame]:
        if not bag in INVENTORY_BAGS:
            return []
                        
        if bag_size is None:
            from PyInventory import Bag
            bag_instance = Bag(bag.value, bag.name)
            bag_size = bag_instance.GetSize()
            
        frames = []
        for slot in range(bag_size):
            frames.append(Frame.bag_slot(bag, slot))
                
        return frames
    
    @staticmethod
    @frame_cache(category="InventoryBagsWindow", source_lib="GetAllInventorySlotFrames")
    def GetInventorySlotFrames() -> list[Frame]:
        frames = []
        
        for bag in INVENTORY_BAGS:
            frames.extend(InventoryBagsWindow.GetBagSlotFrames(bag))
            
        return frames

class XunlaiStorageWindow:
    from .enums_src.Model_enums import ModelID
    MATERIAL_FRAME_OFFSETS : dict[ModelID, int] = {
        ModelID.Bone: 8,
        ModelID.Iron_Ingot: 1,
        ModelID.Tanned_Hide_Square: 3,
        
        ModelID.Scale: 6,
        ModelID.Chitin_Fragment: 7,
        ModelID.Bolt_Of_Cloth: 2,
        
        ModelID.Wood_Plank: 4,
        ModelID.Granite_Slab: 9,
        ModelID.Pile_Of_Glittering_Dust: 5,
        
        ModelID.Plant_Fiber: 10,
        ModelID.Feather: 11,
        ModelID.Fur_Square: 12,
        
        ModelID.Bolt_Of_Linen: 13,
        ModelID.Bolt_Of_Damask: 14,
        ModelID.Bolt_Of_Silk: 15,  
        
        ModelID.Glob_Of_Ectoplasm: 16,
        ModelID.Steel_Ingot: 17,
        ModelID.Deldrimor_Steel_Ingot: 18,
        
        ModelID.Monstrous_Claw: 19,
        ModelID.Monstrous_Eye: 20,
        ModelID.Monstrous_Fang: 21,
        
        ModelID.Ruby: 23,
        ModelID.Sapphire: 24,
        ModelID.Diamond: 22,
        
        ModelID.Onyx_Gemstone: 36,
        ModelID.Lump_Of_Charcoal: 28,
        ModelID.Obsidian_Shard: 25,
        
        ModelID.Tempered_Glass_Vial: 29,
        ModelID.Leather_Square: 30,
        ModelID.Elonian_Leather_Square: 31,
        
        ModelID.Vial_Of_Ink: 32,
        ModelID.Roll_Of_Parchment: 33,
        ModelID.Roll_Of_Vellum: 34,
        
        ModelID.Spiritwood_Plank: 35,
        ModelID.Amber_Chunk: 26,
        ModelID.Jadeite_Shard: 27,
    }
    
    MAX_TABS = 14
    @staticmethod
    def _get_bag_offset(bag: Bags) -> int:
        if bag == Bags.MaterialStorage:
            return XunlaiStorageWindow.MAX_TABS
        
        return bag.value - Bags.Storage1.value
    
    @staticmethod
    @frame_cache(category="XunlaiStorageWindow", source_lib="IsOpen")
    def IsOpen() -> bool:
        return Frame(FrameId.XunlaiWindow).exists
        
    @staticmethod
    @frame_cache(category="XunlaiStorageWindow", source_lib="GetTabContentFrame")
    def GetTabFrame(bag: Bags) -> Optional[Frame]:
        if not bag in STORAGE_BAGS and bag != Bags.MaterialStorage:
            return None
        
        return Frame.storage_tab(bag, reversed_order=True)
        
    @staticmethod
    @frame_cache(category="XunlaiStorageWindow", source_lib="GetTabContentFrame")
    def GetTabContentFrame(bag: Bags) -> Optional[Frame]:
        if not bag in STORAGE_BAGS and bag != Bags.MaterialStorage:
            return None
        
        return Frame.storage_tab(bag)
    
    @staticmethod
    @frame_cache(category="XunlaiStorageWindow", source_lib="GetActiveTabFrame")
    def GetActiveTabFrame() -> Optional[Frame]:
        for bag in STORAGE_BAGS:
            tab_frame = XunlaiStorageWindow.GetTabContentFrame(bag)
            if tab_frame and tab_frame.exists:
                return tab_frame
        
        material_tab_frame = XunlaiStorageWindow.GetTabContentFrame(Bags.MaterialStorage)
        if material_tab_frame and material_tab_frame.exists:
            return material_tab_frame
        
        return None
    
    @staticmethod
    @frame_cache(category="XunlaiStorageWindow", source_lib="GetActiveTabBag")
    def GetActiveTabBag() -> Optional[Bags]:
        for bag in [*STORAGE_BAGS, Bags.MaterialStorage]:
            tab_frame = XunlaiStorageWindow.GetTabContentFrame(bag)
            if tab_frame and tab_frame.exists:
                return bag
        
        return None
    
    @staticmethod
    @frame_cache(category="XunlaiStorageWindow", source_lib="GetActiveTabSlotFrames")
    def GetActiveTabSlotFrames() -> list[Frame]:
        active_tab = XunlaiStorageWindow.GetActiveTabBag()
        if not active_tab:
            return []
        
        if active_tab == Bags.MaterialStorage:
            return XunlaiStorageWindow.GetMaterialSlotFrames()
        
        return XunlaiStorageWindow.GetTabSlotFrames(active_tab)
    
    @staticmethod
    @frame_cache(category="XunlaiStorageWindow", source_lib="GetTabSlotFrames")
    def GetTabSlotFrames(bag : Bags, bag_size: Optional[int] = 25) -> list[Frame]:
        if not bag in STORAGE_BAGS:
            return []
                
        if bag_size is None:
            from PyInventory import Bag
            bag_instance = Bag(bag.value, bag.name)
            bag_size = bag_instance.GetSize()
        
        frames = []
        for slot in range(bag_size):
            frames.append(Frame.storage_slot(bag, slot))
                
        return frames
    
    @staticmethod
    def GetMaterialFrame(material: ModelID) -> Optional[Frame]:
        slot = XunlaiStorageWindow.MATERIAL_FRAME_OFFSETS.get(material)
        if slot is None:
            return None
        
        return Frame.material_slot(slot, max_tabs=XunlaiStorageWindow.MAX_TABS)

    @staticmethod
    @frame_cache(category="XunlaiStorageWindow", source_lib="GetMaterialSlotFrames")
    def GetMaterialSlotFrames() -> list[Frame]:       
        
        frames = []
        for material, slot in XunlaiStorageWindow.MATERIAL_FRAME_OFFSETS.items():
            frames.append(Frame.material_slot(slot, max_tabs=XunlaiStorageWindow.MAX_TABS,
                                             raw_slot=True))
                
        return frames
    
    @staticmethod
    @frame_cache(category="XunlaiStorageWindow", source_lib="GetAllStorageSlotFrames")
    def GetStorageSlotFrames() -> list[Frame]:
        frames = []
        
        for bag in STORAGE_BAGS:
            frames.extend(XunlaiStorageWindow.GetTabSlotFrames(bag))
            
        frames.extend(XunlaiStorageWindow.GetMaterialSlotFrames())
        return frames

    @staticmethod
    def ClickDepositAllMaterials() -> bool:
        if not XunlaiStorageWindow.IsOpen():
            return False
        
        frame = Frame(FrameId.XunlaiWindow.DepositAllMaterials)
        if not frame.exists:
            return False
                
        frame.click()
        frame.mouse_action(7)
        return True

class SkillTrainerWindow:
    @staticmethod
    @frame_cache(category="SkillTrainerWindow", source_lib="IsOpen")
    def IsOpen() -> bool:
        return Frame(FrameId.SkillTrainerWindow).exists

    @staticmethod
    def Close() -> bool:
        if not SkillTrainerWindow.IsOpen():
            return False
        
        frame = Frame(FrameId.Merchant.C0.C0.CloseButton)  
        if not frame.exists:
            return False
              
        frame.click()
        return True

class TraderWindow:
    @staticmethod
    @frame_cache(category="TraderWindow", source_lib="IsOpen")
    def IsOpen() -> bool:          
        button = Frame(FrameId.Merchant.C0.C0.RequestQuoteButton)
        return Frame(FrameId.Merchant).exists and button.exists and button.name == "BtnRequestQuote"
            
    @staticmethod
    def Close() -> bool:
        if not TraderWindow.IsOpen():
            return False
        
        frame = Frame(FrameId.Merchant.C0.C0.TraderCloseButton)
        if not frame.exists:
            return False
                
        frame.click()
        return True
    
class MerchantWindow:
    @staticmethod
    @frame_cache(category="MerchantWindow", source_lib="IsOpen")
    def IsOpen() -> bool:        
        button = Frame(FrameId.Merchant.C0.C0.BuyButton)
        return Frame(FrameId.Merchant).exists and button.exists and button.name == "BtnBuy"
    
            
    @staticmethod
    def Close() -> bool:
        if not MerchantWindow.IsOpen():
            return False
        
        frame = Frame(FrameId.Merchant.C0.C0.CloseButton)
        if not frame.exists:
            return False
                
        frame.click()
        return True
    
class CollectorWindow:
    @staticmethod
    @frame_cache(category="CollectorWindow", source_lib="IsOpen")
    def IsOpen() -> bool:
        button = Frame(FrameId.Merchant.C0.C0.Exchange)
        return Frame(FrameId.Merchant).exists \
            and button.exists and button.hash == 0 \
            and SkillTrainerWindow.IsOpen() == False \
            and TraderWindow.IsOpen() == False \
            and CrafterWindow.IsOpen() == False
    
    @staticmethod
    def Confirm() -> bool:
        if not CollectorWindow.IsOpen():
            return False
        
        frame = Frame(FrameId.Merchant.C0.C0.Exchange)
        if not frame.exists:
            return False
                
        frame.click()
        return True
    
    @staticmethod
    def Close() -> bool:
        if not CollectorWindow.IsOpen():
            return False
        
        frame = Frame(FrameId.Merchant.C0.C0.Goodbye)
        if not frame.exists:
            return False
                
        frame.click()
        return True
    
class CrafterWindow:
    @staticmethod
    @frame_cache(category="CrafterWindow", source_lib="IsOpen")
    def IsOpen() -> bool:        
        button = Frame(FrameId.Merchant.C0.C0.BuyButton)
        return button.exists and button.name == "BtnCraft"

    @staticmethod
    def Close() -> bool:
        if not CrafterWindow.IsOpen():
            return False
        
        frame = Frame(FrameId.Merchant.C0.C0.CloseButton)
        if not frame.exists:
            return False
                
        frame.click()
        return True

    @staticmethod
    @frame_cache(category="CrafterWindow", source_lib="IsCustomizeTabOpen")
    def IsCustomizeTabOpen() -> bool:
        if not CrafterWindow.IsOpen():
            return False
        
        frame = Frame(FrameId.Merchant.C0.C1.CustomizeButton)
        return frame.exists and frame.name == "BtnCustomize"

    @staticmethod
    def CustomizeWeapon() -> bool:
        if not CrafterWindow.IsCustomizeTabOpen():
            return False
                
        frame = Frame(FrameId.Merchant.C0.C1.CustomizeButton)
        frame.click()
        return True
    
class UpgradeWindow:
    '''
    Utility class to check for and interact with the Upgrade Window that appears when using an upgrade extract on items with multiple upgrade options.
    '''
    
    @staticmethod
    @frame_cache(category="UpgradeWindow", source_lib="IsOpen")
    def IsOpen() -> bool:
        '''Return True if the Upgrade Window is open.'''
        return Frame(FrameId.UpgradeWindow).exists
    
    @staticmethod
    def Cancel() -> bool:
        '''Cancel the Upgrade Window by clicking the relevant button. Returns True if the button was found and clicked, False otherwise.'''
        if not UpgradeWindow.IsOpen():
            return False
        
        frame = Frame(FrameId.UpgradeWindow.Cancel)
        frame.click()
        return True
    
    @staticmethod
    def Confirm() -> bool:
        '''Confirm the currently selected Upgrade Option by clicking the relevant button. Returns True if the button was found and clicked, False otherwise.'''
        if not UpgradeWindow.IsOpen():
            return False
        
        frame = Frame(FrameId.UpgradeWindow.Confirm)
        frame.click()
        return True

class SalvageOptionsWindow:
    '''
    Utility class to check for and interact with the Salvage Options Window that appears when using an expert salvage kit on items with multiple salvage options.
    '''    
    @staticmethod
    @frame_cache(category="SalvageOptionsWindow", source_lib="IsOpen")
    def IsOpen() -> bool:
        '''Return True if the Salvage Options Window is open.'''
        
        return Frame(FrameId.SalvageWindow).exists
    
    @staticmethod
    def Cancel() -> bool:
        '''Cancel the Salvage Options Window by clicking the relevant button. Returns True if the button was found and clicked, False otherwise.'''
        if not SalvageOptionsWindow.IsOpen():
            return False

        frame = Frame(FrameId.SalvageWindow.CancelButton)
        frame.click()
        return True
    
    @staticmethod
    def Confirm() -> bool:
        '''Confirm the currently selected Salvage Option by clicking the relevant button. Returns True if the button was found and clicked, False otherwise.'''
        if not SalvageOptionsWindow.IsOpen():
            return False

        frame = Frame(FrameId.SalvageWindow.Button)
        frame.click()
        return True
    
    @staticmethod
    def GetSalvageOptionFrame(mode: SalvageMode) -> Optional[Frame]:
        '''Return the frame corresponding to the given salvage mode.'''
        if not SalvageOptionsWindow.IsOpen():
            return None
        
        match mode:
            case SalvageMode.Prefix:
                return Frame(FrameId.SalvageWindow.Options.Option1)
            
            case SalvageMode.Suffix:
                return Frame(FrameId.SalvageWindow.Options.Option2)
            
            case SalvageMode.Inscription:
                return Frame(FrameId.SalvageWindow.Options.Option3)
            
            case SalvageMode.RareCraftingMaterials | SalvageMode.LesserCraftingMaterials:
                return Frame(FrameId.SalvageWindow.Options.Option4)
            
            case _:
                return None
    
    @staticmethod
    @frame_cache(category="SalvageOptionsWindow", source_lib="IsOptionVisible")
    def IsOptionVisible(mode: SalvageMode) -> bool:
        '''Return True if the given salvage option is visible.'''
        option_frame = SalvageOptionsWindow.GetSalvageOptionFrame(mode)
        if option_frame is None:
            return False
        
        return option_frame.exists
    
    @staticmethod
    def SelectOption(mode: SalvageMode) -> bool:
        '''Select the given salvage option by clicking the relevant button. Returns True if the button was found and clicked, False otherwise.'''
        if not SalvageOptionsWindow.IsOptionVisible(mode):
            return False
        
        option_frame = SalvageOptionsWindow.GetSalvageOptionFrame(mode)
        if option_frame is None:
            return False
        
        option_frame.click()
        option_frame.mouse_action(8)
        return True
    
    @staticmethod
    def SelectAndConfirmOption(mode: SalvageMode) -> bool:
        '''Select and confirm the given salvage option by clicking the relevant buttons. Returns True if the buttons were found and clicked, False otherwise.'''
        if not SalvageOptionsWindow.SelectOption(mode):
            return False
        
        if not SalvageOptionsWindow.Confirm():
            return False
        
        return True

class SalvageConfirmationPopup:
    '''
    Utility class to check for and interact with the confirmation pop up for salvaging with a salvage kit.
    '''
    
    @staticmethod
    @frame_cache(category="SalvageConfirmationPopup", source_lib="IsOpen")
    def IsOpen() -> bool:
        '''
        Return True if the confirmation pop up for salvaging with a salvage kit is open.
        '''
        return Frame(FrameId.SalvageWindow.OptionsWindowConfirmMaterialsWindow).exists
    
    @staticmethod
    def Cancel() -> bool:
        '''
        Cancel the confirmation pop up for salvaging with a salvage kit by clicking the relevant button. Returns True if the button was found and clicked, False otherwise.
        '''
        if not SalvageConfirmationPopup.IsOpen():
            return False
        
        frame = Frame(FrameId.SalvageWindow.OptionsWindowConfirmMaterialsWindow.Cancel)
        frame.click()
        return True
    
    @staticmethod
    def Confirm() -> bool:
        '''
        Confirm the confirmation pop up for salvaging with a salvage kit by clicking the relevant button. Returns True if the button was found and clicked, False otherwise.
        '''
        if not SalvageConfirmationPopup.IsOpen():
            return False
        
        frame = Frame(FrameId.SalvageWindow.OptionsWindowConfirmMaterialsWindow.Confirm)
        frame.click()
        return True

class LesserSalvageWindow:
    '''
    Utility class to check for and interact with the confirmation pop up for salvaging with a normal salvage kit.
    '''
    @staticmethod
    @frame_cache(category="LesserSalvageWindow", source_lib="IsOpen")
    def IsOpen() -> bool:
        '''
        Return True if the confirmation pop up for salvaging with a normal salvage kit is open.
        '''
        return Frame(FrameId.ScreenFrame.C6.LesserSalvageWindow).exists
    
    @staticmethod
    def Cancel() -> bool:
        '''
        Cancel the confirmation pop up for salvaging with a normal salvage kit by clicking the relevant button. Returns True if the button was found and clicked, False otherwise.
        '''
        if not LesserSalvageWindow.IsOpen():
            return False
        
        frame = Frame(FrameId.ScreenFrame.C6.LesserSalvageWindow.SalvageWithLesserKitCancel)
        frame.click()
        return True
    
    @staticmethod
    def Confirm() -> bool:
        '''
        Confirm the confirmation pop up for salvaging with a normal salvage kit by clicking the relevant button. Returns True if the button was found and clicked, False otherwise.
        '''
        if not LesserSalvageWindow.IsOpen():
            return False
        
        frame = Frame(FrameId.ScreenFrame.C6.LesserSalvageWindow.SalvageWithLesserKitConfirm)
        frame.click()
        return True

class ExpertSalvageUnidentifiedWindow:
    '''
    Utility class to check for and interact with the Salvage Window from using Expert Salvage Kits on Unidentified Items.
    '''
    
    @staticmethod
    @frame_cache(category="ExpertSalvageUnidentifiedWindow", source_lib="IsOpen")
    def IsOpen() -> bool:
        '''
        Return True if the Expert Salvage Unidentified Window is open.
        '''
                
        return Frame(FrameId.ScreenFrame.C6.ExpertSalvageUnidentifiedItem).exists
    
    @staticmethod
    def Cancel() -> bool:
        '''
        Cancel the Expert Salvage Unidentified Window by clicking the relevant button. Returns True if the button was found and clicked, False otherwise.
        '''
        if not ExpertSalvageUnidentifiedWindow.IsOpen():
            return False
        
        frame = Frame(FrameId.ScreenFrame.C6.ExpertSalvageUnidentifiedItem.Cancel)
        frame.click()
        return True
    
    @staticmethod
    def Confirm() -> bool:
        '''
        Confirm the Expert Salvage Unidentified Window by clicking the relevant button. Returns True if the button was found and clicked, False otherwise.
        '''        
        if not ExpertSalvageUnidentifiedWindow.IsOpen():
            return False
        
        frame = Frame(FrameId.ScreenFrame.C6.ExpertSalvageUnidentifiedItem.Confirm)
        frame.click()
        return True

class AnySalvageWindow:
    '''
    Utility class to check for and interact with any salvage-related window, including SalvageOptionsWindow, SalvageConfirmationPopup, LesserSalvageWindow, and ExpertSalvageUnidentifiedWindow.
    '''
    
    @staticmethod
    @frame_cache(category="AnySalvageWindow", source_lib="AnySalvageWindowOpen")
    def IsOpen() -> bool:
        '''
        Return True if any salvage-related window is open, including SalvageOptionsWindow, SalvageConfirmationPopup, LesserSalvageWindow, or ExpertSalvageUnidentifiedWindow.
        '''
        
        return (
            SalvageConfirmationPopup.IsOpen()
            or SalvageOptionsWindow.IsOpen()
            or LesserSalvageWindow.IsOpen()
            or ExpertSalvageUnidentifiedWindow.IsOpen()
        )

    @staticmethod
    def Cancel() -> bool:
        '''
        Cancel any open salvage-related window, including SalvageOptionsWindow, SalvageConfirmationPopup, LesserSalvageWindow, or ExpertSalvageUnidentifiedWindow. Returns True if a salvage-related window was found and cancelled, False otherwise.
        '''
        
        if SalvageOptionsWindow.IsOpen():
            return SalvageOptionsWindow.Cancel()

        if LesserSalvageWindow.IsOpen():
            return LesserSalvageWindow.Cancel()

        if ExpertSalvageUnidentifiedWindow.IsOpen():
            return ExpertSalvageUnidentifiedWindow.Cancel()

        if SalvageConfirmationPopup.IsOpen():
            return SalvageConfirmationPopup.Cancel()

        return False


    @staticmethod
    def Confirm() -> bool:
        '''
        WARNING: This will irreversibly confirm salvage actions. Use the more specific Confirm methods if possible to avoid unintended consequences.\n
        Confirm any open salvage-related window, including SalvageOptionsWindow, SalvageConfirmationPopup, LesserSalvageWindow, or ExpertSalvageUnidentifiedWindow.
        Returns True if a salvage-related window was found and confirmed, False otherwise.
        '''
        if SalvageConfirmationPopup.IsOpen():
            return SalvageConfirmationPopup.Confirm()

        if SalvageOptionsWindow.IsOpen():
            return SalvageOptionsWindow.Confirm()

        if LesserSalvageWindow.IsOpen():
            return LesserSalvageWindow.Confirm()

        if ExpertSalvageUnidentifiedWindow.IsOpen():
            return ExpertSalvageUnidentifiedWindow.Confirm()

        return False
