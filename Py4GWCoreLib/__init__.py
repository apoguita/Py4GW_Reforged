import traceback
import math
from enum import Enum
import time
from time import sleep
import inspect
import sys
from dataclasses import dataclass, field
import os
import subprocess

#*******************************************************************************
#********* Start of manual import of external libraries  ***********************
#*******************************************************************************
def find_system_python():
    try:
        python_path = subprocess.check_output("where python", shell=True).decode().split("\n")[0].strip()
        if python_path and os.path.exists(python_path):
            return os.path.dirname(python_path)
    except Exception:
        pass
    return sys.prefix if sys.prefix and os.path.exists(sys.prefix) else None

system_python_path = find_system_python()
if system_python_path:
    site_packages_path = os.path.join(system_python_path, "Lib", "site-packages")
    if site_packages_path not in sys.path:
        sys.path.append(site_packages_path)
    os.environ["PATH"] = site_packages_path + os.pathsep + os.environ["PATH"]


#*******************************************************************************
#********* End of manual import of external libraries  ***********************
#*******************************************************************************


import Py4GW
import PySystem
import PyGameThread
import PyPing
import PyScanner
import PyImGui
import PyCallback

# ── Legacy Console: inject into builtins so all legacy code (100+ bare
#    `Console.xxx()` and `ConsoleLog()` calls) works without per-file migration. ──
import builtins
from .py4gwcorelib_src.Console import ConsoleLog
builtins.Console = PySystem.Console
builtins.ConsoleLog = ConsoleLog

# ── Vec2 compatibility: PyImGui set_cursor_pos / set_cursor_screen_pos accept a single
#    Vec2 tuple in Reforged (not two scalar floats). Monkey-patch to accept both forms.
_PyImGui_set_cursor_pos = PyImGui.set_cursor_pos
_PyImGui_set_cursor_screen_pos = PyImGui.set_cursor_screen_pos
def _vec2_set_cursor_pos(*args):
    if len(args) == 1: return _PyImGui_set_cursor_pos(args[0])
    return _PyImGui_set_cursor_pos(args)
def _vec2_set_cursor_screen_pos(*args):
    if len(args) == 1: return _PyImGui_set_cursor_screen_pos(args[0])
    return _PyImGui_set_cursor_screen_pos(args)
PyImGui.set_cursor_pos = _vec2_set_cursor_pos
PyImGui.set_cursor_screen_pos = _vec2_set_cursor_screen_pos

# ── Vec2 slicing: Reforged PyImGui.Vec2 doesn't support [:2] slicing used
#    pervasively in legacy code. Monkey-patch __getitem__ to handle slices. ──
_Vec2 = PyImGui.Vec2
_Vec2_orig_getitem = _Vec2.__getitem__
def _vec2_getitem(self, key):
    if isinstance(key, slice):
        return tuple(self[i] for i in range(*key.indices(2)))
    return _Vec2_orig_getitem(self, key)
_Vec2.__getitem__ = _vec2_getitem

# ── is_rect_visible compatibility: Reforged takes (Vec2), legacy passes (w, h). ──
_PyImGui_is_rect_visible = PyImGui.is_rect_visible
def _vec2_is_rect_visible(*args):
    if len(args) == 1: return _PyImGui_is_rect_visible(args[0])
    return _PyImGui_is_rect_visible(args)   # (w, h) tuple works as Vec2
PyImGui.is_rect_visible = _vec2_is_rect_visible

# ── push_style_var2 compatibility: legacy code calls push_style_var2(var, x, y);
#    Reforged exposes push_style_var_vec2(var, (x, y)). ──
_PyImGui_push_style_var_vec2 = PyImGui.push_style_var_vec2
def _push_style_var2(var, x, y):
    _PyImGui_push_style_var_vec2(var, (x, y))
PyImGui.push_style_var2 = _push_style_var2

# ── dummy compatibility: Reforged takes (Vec2), legacy passes (w, h). ──
_PyImGui_dummy = PyImGui.dummy
def _vec2_dummy(*args):
    if len(args) == 1: return _PyImGui_dummy(args[0])
    return _PyImGui_dummy(args)
PyImGui.dummy = _vec2_dummy

# ── invisible_button compatibility: Reforged takes (Vec2), legacy passes (w, h). ──
_PyImGui_invisible_button = PyImGui.invisible_button
def _vec2_invisible_button(str_id, *args):
    if len(args) >= 2 and isinstance(args[0], (int, float)) and isinstance(args[1], (int, float)):
        return _PyImGui_invisible_button(str_id, (args[0], args[1]), *args[2:])
    return _PyImGui_invisible_button(str_id, *args)
PyImGui.invisible_button = _vec2_invisible_button

# ── begin_tab_item: Reforged binding requires explicit p_open=True;
#    legacy code calls begin_tab_item(label) with no p_open → defaults nullptr → returns False. ──
_PyImGui_begin_tab_item = PyImGui.begin_tab_item
def _tab_item(label, p_open=True, flags=0):
    return _PyImGui_begin_tab_item(label, p_open, flags)
PyImGui.begin_tab_item = _tab_item

import PyAgent
import PyPlayer
import PyParty
import PyItem
import PyInventory

# ── Reforged: PyInventory.Bag.GetItems() returns dicts.
#    Convert each dict to a SimpleNamespace so all legacy attribute-access
#    callers (item.model_id, item.item_id, item.quantity, item.slot, …)
#    work retroactively. ──
import types as _types
_Bag = PyInventory.Bag
_orig_Bag_GetItems = _Bag.GetItems
def _wrapped_Bag_GetItems(self):
    items = _orig_Bag_GetItems(self)
    return [_types.SimpleNamespace(**item) if isinstance(item, dict) else item for item in (items or [])]
_Bag.GetItems = _wrapped_Bag_GetItems

import PySkill
import PySkillbar
import PyMerchant
import PyEffects
import PyKeystroke
import PyOverlay
import PyQuest
import PyPathing
import PyUIManager
import PyCamera
import PyDXOverlay
import PyAgentEvents

# Inject PySystem, PyPing, PyGameThread into builtins so all widget modules
# (loaded dynamically via importlib) can access them without explicit import.
import builtins
builtins.PySystem = PySystem
builtins.PyPing = PyPing
builtins.PyGameThread = PyGameThread
builtins.PyDXOverlay = PyDXOverlay
builtins.PyAgentEvents = PyAgentEvents

from .enums import *
from .ImGui_Legacy_src.IconsFontAwesome5 import IconsFontAwesome5
from .Map import *
from .ImGui_Legacy import *
from .model_data import *
from .Agent import *
from .Player import *
from .AgentArray import *
from .Party import *
from .Item import *
from .ItemArray import *
from .Inventory import *
from .Skill import *
from .Skillbar import *
from .Effect import *
from .Merchant import *
from .Quest import *
from .Camera import *
from .Scanner import *

from .Py4GWcorelib import *
from .Overlay import *
from .DXOverlay import *
from .UIManager import *
from .Routines import *
from .SkillManager import *
from .GlobalCache import GLOBAL_CACHE
from .Pathing import AutoPathing
from .BuildMgr import BuildMgr
from .Botting import BottingClass as Botting
from .Context import GWContext
#from .CombatEvents import CombatEventQueue, CombatEvents, COMBAT_EVENTS
from .Database import Database
from .GWUI import GWUI

from .py4gwcorelib_src.Profiling import ProfilingRegistry, SimpleProfiler
from .py4gwcorelib_src.FrameCache import FRAME_CACHE, frame_cache
from .py4gwcorelib_src.WidgetManager import WidgetHandler, Widget
from .py4gwcorelib_src.WindowFactory import WindowFactory, ManagedWindowSpec, WindowVarSpec

from .native_src.internals.types import Vec2f, Vec3f, GamePos

traceback = traceback
math = math
Enum = Enum
time = time
sleep = sleep
inspect = inspect
dataclass = dataclass
field = field

Vec2f = Vec2f
Vec3f = Vec3f
GamePos = GamePos

Py4Gw = Py4GW
Py4GW = Py4GW
PySystem = PySystem
PyGameThread = PyGameThread
PyPing = PyPing
PyScanner = PyScanner
PyImGui = PyImGui

PyAgent = PyAgent
PyPlayer = PyPlayer
PyParty = PyParty
PyItem = PyItem
PyInventory = PyInventory
PySkill = PySkill
PySkillbar = PySkillbar
PyMerchant = PyMerchant
PyEffects = PyEffects
PyPathing = PyPathing
PyOverlay = PyOverlay
PyQuest = PyQuest
PyUIManager = PyUIManager
PyCamera = PyCamera
PyDXOverlay = PyDXOverlay
PyAgentEvents = PyAgentEvents
GLOBAL_CACHE = GLOBAL_CACHE
AutoPathing = AutoPathing
IconsFontAwesome5 = IconsFontAwesome5
Database = Database
#CombatEvents = CombatEvents
#COMBAT_EVENTS = COMBAT_EVENTS
ProfilingRegistry = ProfilingRegistry
SimpleProfiler = SimpleProfiler
FRAME_CACHE = FRAME_CACHE
frame_cache = frame_cache
WidgetHandler = WidgetHandler
Widget = Widget
GWUI = GWUI
WindowFactory = WindowFactory
ManagedWindowSpec = ManagedWindowSpec
WindowVarSpec = WindowVarSpec


#redirect print output to Py4GW Console
class Py4GWLogger:
    def write(self, message):
        if message.strip():  # Avoid logging empty lines
            PySystem.Console.Log("print:", f"{message.strip()}", PySystem.Console.MessageType.Info)

    def flush(self):  
        pass  # Required for sys.stdout but does nothing
    
class Py4GWLoggerError:
    def write(self, message):
        if message.strip():  # Avoid logging empty lines
            PySystem.Console.Log("print:", f"{message.strip()}", PySystem.Console.MessageType.Error)

    def flush(self):  
        pass  # Required for sys.stdout but does nothing

# Redirect Python's print output to Py4GW Console
sys.stdout = Py4GWLogger()
sys.stderr = Py4GWLoggerError()
