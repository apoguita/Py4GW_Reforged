from enum import IntEnum
from typing import Callable
from types import ModuleType
import re
import traceback
import PySystem
import PyPing
import PyGameThread
import PyDXOverlay
import PyAgentEvents
import PyImGui
from Py4GWCoreLib.HotkeyManager import HOTKEY_MANAGER, HotKey
from Py4GWCoreLib.ImGui_Legacy_src.Style import Style
from Py4GWCoreLib.ImGui_Legacy_src.types import Alignment, StyleTheme
from Py4GWCoreLib.py4gwcorelib_src.Settings import Settings
from Py4GWCoreLib._legacy_facade import ImGui_Legacy
from Py4GWCoreLib.GlobalCache import GLOBAL_CACHE
from Py4GWCoreLib.enums_src.IO_enums import Key, ModifierKey
from Py4GWCoreLib.enums_src.Multiboxing_enums import SharedCommandType
from Py4GWCoreLib.Player import Player
from Py4GWCoreLib.ImGui_Legacy_src.IconsFontAwesome5 import IconsFontAwesome5
import importlib.util
import os
import sys
import PyImGui
import PyCallback
from dataclasses import dataclass, field
from types import ModuleType
from typing import Callable, Iterable, Literal, Optional

from Py4GWCoreLib.py4gwcorelib_src.Color import Color

_profiling_registry = None
base_path = PySystem.Console.get_projects_path()

def _get_profiling():
    global _profiling_registry
    if _profiling_registry is None:
        from Py4GWCoreLib.py4gwcorelib_src.Profiling import ProfilingRegistry
        _profiling_registry = ProfilingRegistry()
    return _profiling_registry

#region Py4GW Library
class LayoutMode(IntEnum):
    Library = 0
    Compact = 1
    Minimalistic = 2
    SingleButton = 3
    
    LastView = 100
    
class SortMode(IntEnum):
    ByName = 0
    ByCategory = 1
    ByStatus = 2
    
class ViewMode(IntEnum):
    All = 0
    Favorites = 1
    Actives = 2
    Inactives = 3
    
class WidgetTreeNode:
    def __init__(
        self,
        name: str = "",
        depth: int = 0,
        parent: "WidgetTreeNode | None" = None,
    ):
        self.name: str = name
        self.depth: int = depth
        self.parent: WidgetTreeNode | None = parent

        # full path (stable, precomputed)
        if parent and parent.path:
            self.path: str = f"{parent.path}/{name}"
        elif parent:
            self.path: str = name
        else:
            self.path: str = ""

        # hierarchy
        self.children: dict[str, WidgetTreeNode] = {}
        self.widgets: list[str] = []

    def get_child(self, name: str) -> "WidgetTreeNode":
        if name not in self.children:
            self.children[name] = WidgetTreeNode(
                name=name,
                depth=self.depth + 1,
                parent=self
            )
        return self.children[name]


CatalogScope = Literal["all", "favorites", "active", "inactive"]
CatalogSort = Literal["name", "category", "status"]


@dataclass
class WidgetCatalogNode:
    name: str = ""
    depth: int = 0
    parent: "WidgetCatalogNode | None" = None
    path: str = ""
    is_widget_container: bool = False
    children: dict[str, "WidgetCatalogNode"] = field(default_factory=dict)
    widget_ids: list[str] = field(default_factory=list)

    def get_child(self, name: str) -> "WidgetCatalogNode":
        child = self.children.get(name)
        if child is None:
            child_path = f"{self.path}/{name}" if self.path else name
            child = WidgetCatalogNode(
                name=name,
                depth=self.depth + 1,
                parent=self,
                path=child_path,
            )
            self.children[name] = child
        return child


@dataclass(frozen=True)
class WidgetCatalogSnapshot:
    widgets_by_id: dict[str, "Widget"]
    tree: WidgetCatalogNode
    categories: list[str]
    tags: list[str]
    paths: list[str]
    widget_container_paths: list[str]


@dataclass
class WidgetCatalogQuery:
    text: str = ""
    category: str = ""
    path: str = ""
    tag: str = ""
    scope: CatalogScope = "all"
    sort_by: CatalogSort = "name"
    favorite_ids: set[str] = field(default_factory=set)


class WidgetCatalog:
    PRESET_WORDS: dict[str, list[str]] = {
        "no_image": ["#no_image", "#noimg", "#noicon"],
        "enabled": ["#enabled", "#active", "#on"],
        "disabled": ["#disabled", "#inactive", "#off"],
        "favorites": ["#favorites", "#favs", "#fav"],
        "system": ["#system", "#sys"],
    }

    @classmethod
    def snapshot_from_handler(cls, handler: "WidgetHandler") -> WidgetCatalogSnapshot:
        return cls.snapshot_from_widgets(handler.widgets)

    @classmethod
    def snapshot_from_widgets(cls, widgets: dict[str, "Widget"]) -> WidgetCatalogSnapshot:
        root = WidgetCatalogNode()
        categories: set[str] = set()
        tags: set[str] = set()
        paths: set[str] = set()
        widget_container_paths: set[str] = set()

        for widget_id, widget in widgets.items():
            node = root

            if widget.category:
                categories.add(widget.category)

            for tag in widget.tags:
                if tag:
                    tags.add(tag)

            if widget.widget_path:
                widget_container_paths.add(widget.widget_path)
                current_path = ""
                for part in widget.widget_path.split("/"):
                    current_path = f"{current_path}/{part}" if current_path else part
                    paths.add(current_path)
                    node = node.get_child(part)
                node.is_widget_container = True

            node.widget_ids.append(widget_id)

        cls._sort_tree(root)

        return WidgetCatalogSnapshot(
            widgets_by_id=widgets,
            tree=root,
            categories=sorted(categories),
            tags=sorted(tags),
            paths=sorted(paths),
            widget_container_paths=sorted(widget_container_paths),
        )

    @classmethod
    def query(cls, snapshot: WidgetCatalogSnapshot, query: WidgetCatalogQuery) -> list["Widget"]:
        widgets = list(snapshot.widgets_by_id.values())
        keywords = [kw.strip().lower() for kw in query.text.lower().strip().split(";") if kw.strip()]

        preset_checks = {key: False for key in cls.PRESET_WORDS}
        remaining_keywords: list[str] = []

        for kw in keywords:
            matched_preset = False
            for preset_name, preset_words in cls.PRESET_WORDS.items():
                if kw in preset_words:
                    preset_checks[preset_name] = True
                    matched_preset = True
            if not matched_preset:
                remaining_keywords.append(kw)

        favorite_ids = query.favorite_ids or set()

        match query.scope:
            case "favorites":
                widgets = [widget for widget in widgets if widget.folder_script_name in favorite_ids]
            case "active":
                widgets = [widget for widget in widgets if widget.enabled]
            case "inactive":
                widgets = [widget for widget in widgets if not widget.enabled]

        widgets = [
            widget for widget in widgets
            if (not preset_checks["enabled"] or widget.enabled)
            and (not preset_checks["disabled"] or not widget.enabled)
            and (not preset_checks["favorites"] or widget.folder_script_name in favorite_ids)
            and (not preset_checks["no_image"] or cls._has_missing_icon(widget))
            and (not preset_checks["system"] or widget.category == "System")
            and (widget.category == query.category or not query.category)
            and (query.tag in widget.tags or not query.tag)
            and cls._matches_path(widget, query.path)
            and cls._matches_keywords(widget, remaining_keywords)
        ]

        match query.sort_by:
            case "category":
                widgets.sort(key=lambda widget: ((widget.category or "").lower(), widget.name.lower()))
            case "status":
                widgets.sort(key=lambda widget: (not widget.enabled, widget.name.lower()))
            case _:
                widgets.sort(key=lambda widget: widget.name.lower())

        return widgets

    @classmethod
    def tree_children(cls, node: WidgetCatalogNode) -> list[WidgetCatalogNode]:
        return list(node.children.values())

    @staticmethod
    def _sort_tree(node: WidgetCatalogNode) -> None:
        node.widget_ids.sort()
        node.children = dict(sorted(node.children.items(), key=lambda item: item[0].lower()))
        for child in node.children.values():
            WidgetCatalog._sort_tree(child)

    @staticmethod
    def _normalize(text: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", (text or "").lower())

    @staticmethod
    def _matches_path(widget: "Widget", path: str) -> bool:
        if not path:
            return True
        if not widget.widget_path:
            return False
        return widget.widget_path == path or widget.widget_path.startswith(f"{path}/")

    @staticmethod
    def _has_missing_icon(widget: "Widget") -> bool:
        return (widget.image or "").replace("/", "\\").lower().endswith("textures\\missing_texture.png")

    @classmethod
    def _matches_keywords(cls, widget: "Widget", keywords: Iterable[str]) -> bool:
        search_fields = [
            widget.name,
            widget.plain_name,
            widget.folder,
            widget.category,
            *widget.tags,
            *widget.aliases,
        ]
        haystacks = [
            ((field or "").lower(), cls._normalize(field or ""))
            for field in search_fields
            if field
        ]

        for kw in keywords:
            normalized_kw = cls._normalize(kw)
            if not any(
                kw in haystack or (normalized_kw and normalized_kw in normalized_haystack)
                for haystack, normalized_haystack in haystacks
            ):
                return False

        return True
                    
#region widget
@dataclass
class Widget:
    """
    Widget data class with callback extraction in __post_init__
    """
    # Core identity (passed to __init__)
    folder_script_name: str       # "folder/script_name"
    plain_name: str = ""          # script without extension
    widget_path: str = ""         # folder relative path (no script)
    script_path: str = ""         # script full path
    
    #callback data
    update_callback_id: int = 0
    draw_callback_id: int = 0   
    main_callback_id: int = 0
    
    #Extra_execution data
    has_update_property: bool = False
    has_draw_property: bool = False
    has_main_property: bool = False
    has_configure_property: bool = False
    has_tooltip_property: bool = False
    
    # INI configuration (passed to __init__)
    ini_key: str = ""             # "" or valid key
    ini_path: str = ""            # "Widgets/folder"
    ini_filename: str = ""        # "script_name.ini"
        
    # Extracted callbacks (will be populated in __post_init__)
    main: Optional[Callable] = field(default=None, init=False)
    configure: Optional[Callable] = field(default=None, init=False)
    update: Optional[Callable] = field(default=None, init=False)
    draw: Optional[Callable] = field(default=None, init=False)
    tooltip: Optional[Callable] = field(default=None, init=False)
    minimal: Optional[Callable] = field(default=None, init=False)
    
    on_enable: Optional[Callable] = field(default=None, init=False)
    on_disable: Optional[Callable] = field(default=None, init=False)
    
    module: Optional[ModuleType] = field(default=None, init=False, repr=False)
    __enabled: bool = field(default=False, init=False,)
    __configuring: bool = field(default=False, init=False)
    __paused: bool = field(default=False, init=False)
    
    # Optional properties to be displayed in widget manager ui
    name : str = field(default="", init=False, repr=False)
    image : str = field(default="", init=False, repr=False)
    tags : list[str] = field(default_factory=list, init=False)
    aliases : list[str] = field(default_factory=list, init=False)
    category : str = field(default="", init=False)    
    
    @property
    def is_paused(self) -> bool:
        """Check if the widget is paused"""
        return self.__paused
    
    @property
    def enabled(self) -> bool:
        """Check if the widget is enabled"""
        return self.__enabled
    
    @property
    def configuring(self) -> bool:
        """Check if the widget is in configuring state"""
        return self.__configuring
    
    def load_module(self) -> bool:
        """Load the module if not already loaded"""
        if self.module is not None:
            return True  # Already loaded
        
        if not os.path.isfile(self.script_path):
            PySystem.Console.Log("WidgetManager", f"Widget script not found: {self.script_path}", PySystem.Console.MessageType.Error)
            return False
        
        unique_name = f"py4gw_widget_{self.folder_script_name.replace('/', '_').replace('.', '_')}"
        
        spec = importlib.util.spec_from_file_location(unique_name, self.script_path)
        if spec is None or spec.loader is None:
            raise ValueError(f"Invalid module spec: {self.script_path}")
        
        module = importlib.util.module_from_spec(spec)
        sys.modules[unique_name] = module
        
        # Inject migrated module aliases into the widget's namespace
        import PySystem
        import PyPing
        import PyGameThread
        import PyDXOverlay
        import PyAgentEvents
        module.PySystem = PySystem
        module.PyPing = PyPing
        module.PyGameThread = PyGameThread
        module.PyDXOverlay = PyDXOverlay
        module.PyAgentEvents = PyAgentEvents
        
        try:
            spec.loader.exec_module(module)
        except Exception as e:
            del sys.modules[unique_name]
            self.disable()
            PySystem.Console.Log("WidgetManager", f"Failed to load widget module '{self.folder_script_name}': {e}", PySystem.Console.MessageType.Error)
            return False
        
        self.module = module
        
        if self.module:                
            # --- capability flags (what exists in the widget module) ---
            self.has_main_property      = callable(getattr(self.module, "main", None))
            self.has_configure_property = callable(getattr(self.module, "configure", None))
            self.has_update_property    = callable(getattr(self.module, "update", None))
            self.has_draw_property      = callable(getattr(self.module, "draw", None))
            self.has_tooltip_property   = callable(getattr(self.module, "tooltip", None))
            
            # Extract main callback
            self.main = getattr(self.module, "main", None) if self.has_main_property else None
            self.configure = getattr(self.module, "configure", None) if self.has_configure_property else None
            self.update = getattr(self.module, "update", None) if self.has_update_property else None
            self.draw = getattr(self.module, "draw", None) if self.has_draw_property else None
            self.tooltip = getattr(self.module, "tooltip", None) if self.has_tooltip_property else None
            self.minimal = getattr(self.module, "minimal", None) if callable(getattr(self.module, "minimal", None)) else None
            self.on_enable = getattr(self.module, "on_enable", None) if callable(getattr(self.module, "on_enable", None)) else None
            self.on_disable = getattr(self.module, "on_disable", None) if callable(getattr(self.module, "on_disable", None)) else None
            
            self.name = getattr(self.module, 'MODULE_NAME', "") if hasattr(self.module, 'MODULE_NAME') else self.cleaned_name()
            self.category = getattr(self.module, 'MODULE_CATEGORY', "") if hasattr(self.module, 'MODULE_CATEGORY') else (self.widget_path.split('/')[0] if self.widget_path else "") #get first folder after Widgets 
            self.tags = getattr(self.module, 'MODULE_TAGS', []) if hasattr(self.module, 'MODULE_TAGS') else [folder for folder in self.widget_path.split('/') if folder]
            self.aliases = [str(alias).strip() for alias in getattr(self.module, 'MODULE_ALIASES', []) if str(alias).strip()]
            self.image = os.path.join(base_path, getattr(self.module, 'MODULE_ICON', "") if hasattr(self.module, 'MODULE_ICON') else "Textures\\missing_texture.png")
            
            self.optional = getattr(self.module, 'OPTIONAL', True) if hasattr(self.module, 'OPTIONAL') else self.category not in ["System", "Py4GW"] # System and Py4GW widgets are non-optional by default, all others are optional by default
              
        return True
    
    def set_configuring(self, state: bool):
        """Set configuring state"""
        self.__configuring = state
        
    def enable_configuring(self):
        """Enable configuring state"""
        self.set_configuring(True)
        
    def disable_configuring(self):  
        """Disable configuring state"""
        self.set_configuring(False)
        
    def pause(self):
        """Pause the widget"""
        self.__paused = True
        self.PauseCallbacks()
        
    def resume(self):
        """Resume the widget"""
        self.__paused = False
        self.ResumeCallbacks()
        
    def PauseCallbacks(self):
        """Pause callbacks by id if they exist"""
        if self.update_callback_id:
            PyCallback.PyCallback.PauseById(self.update_callback_id)
        if self.draw_callback_id:
            PyCallback.PyCallback.PauseById(self.draw_callback_id)
        if self.main_callback_id:
            PyCallback.PyCallback.PauseById(self.main_callback_id)
            
    def ResumeCallbacks(self):
        """Resume callbacks by id if they exist"""
        if self.update_callback_id:
            PyCallback.PyCallback.ResumeById(self.update_callback_id)
        if self.draw_callback_id:
            PyCallback.PyCallback.ResumeById(self.draw_callback_id)
        if self.main_callback_id:
            PyCallback.PyCallback.ResumeById(self.main_callback_id)
            
    def RegisterCallbacks(self):
        """Register callbacks if they exist in the module"""
        def wrap_profiler(key: str, fn: Callable):
            # We return a NEW function (lambda) that the C++ Callback system 
            # will store and execute every frame.
            def callback_wrapper():
                profiling = _get_profiling()
                if profiling.enabled:
                    # Executes fn() inside the profiling scope
                    return profiling.runcall_scope("widgets", f"{self.folder_script_name}:{key}", fn)
                else:
                    # Executes fn() normally
                    return fn()
            
            return callback_wrapper
       
        if self.module is None:
            return
        
        # 1. Update Callback (Logic Loop)
        if self.has_update_property and self.update is not None and self.update_callback_id == 0:
            self.update_callback_id = PyCallback.PyCallback.Register(
                self.folder_script_name,
                PyCallback.Phase.Update,
                wrap_profiler("update", self.update), # Pass the wrapper
                priority=99,
                context=PyCallback.Context.Update
            )
            
        # 2. Draw Callback (Visual Loop)
        if self.has_draw_property and self.draw is not None and self.draw_callback_id == 0:
            self.draw_callback_id = PyCallback.PyCallback.Register(
                self.folder_script_name,
                PyCallback.Phase.Update,
                wrap_profiler("draw", self.draw), # Pass the wrapper
                priority=99,
                context=PyCallback.Context.Draw
            )
            
        # 3. Main Callback (System Loop)
        if self.has_main_property and self.main is not None and self.main_callback_id == 0:
            self.main_callback_id = PyCallback.PyCallback.Register(
                self.folder_script_name,
                PyCallback.Phase.Update,
                wrap_profiler("main", self.main), # Pass the wrapper
                priority=99,
                context=PyCallback.Context.Main
            )
        
    def disable(self):
        """Disable the widget"""
        self.PauseCallbacks()
        if self.__enabled:
            if self.module is not None:
                try:
                    if self.on_disable:
                        self.on_disable()
                    
                except Exception as e:
                    PySystem.Console.Log("WidgetManager", f"Error during on_disable of widget {self.folder_script_name}: {str(e)}", PySystem.Console.MessageType.Error)
                    PySystem.Console.Log("WidgetManager", f"Stack trace: {traceback.format_exc()}", PySystem.Console.MessageType.Error)
                
            self.__enabled = False
        
    def enable(self):
        """Enable the widget"""
        if self.enabled and self.module is not None: 
            return  # Already enabled
        
        # enable widget only if module loads successfully
        self.__enabled = self.load_module()
        
        if self.enabled:
            self.__paused = False
            self.RegisterCallbacks()
            self.ResumeCallbacks()
            try:
                if self.on_enable:
                    self.on_enable()
                
            except Exception as e:
                PySystem.Console.Log("WidgetManager", f"Error during on_enable of widget {self.folder_script_name}: {str(e)}", PySystem.Console.MessageType.Error)
                PySystem.Console.Log("WidgetManager", f"Stack trace: {traceback.format_exc()}", PySystem.Console.MessageType.Error)
        
    def cleaned_name(self):
        """Cleanup the widget name for display"""
        ## if name starts with [0-9]-, remove that part for module cleanup and replace all _ with " "
        import re
        cleaned_name = re.sub(r'^\d+-', '', self.plain_name)
        cleaned_name = cleaned_name.replace("_", " ")
        return cleaned_name.strip()
                    
    def __post_init__(self):
        """Extract callbacks from module after initialization"""      
        
        # --- capability flags (what exists in the widget module) ---
        self.has_main_property      = False
        self.has_configure_property = False
        self.has_update_property    = False
        self.has_draw_property      = False
        self.has_tooltip_property   = False
        
        # Extract main callback
        self.main : Optional[Callable] = None
        self.configure : Optional[Callable] = None
        self.update : Optional[Callable] = None
        self.draw : Optional[Callable] = None
        self.tooltip : Optional[Callable] = None
        self.minimal : Optional[Callable] = None
        self.on_enable : Optional[Callable] = None
        self.on_disable : Optional[Callable] = None
        self.optional = True  
        self.__paused = True
        
        self.load_module()
        
            
    @property
    def folder(self) -> str:
        """Extract folder path from name"""
        if '/' in self.folder_script_name:
            return self.folder_script_name.rsplit('/', 1)[0]
        return ""
    
    @property  
    def script_name(self) -> str:
        """Extract script name from name"""
        if '/' in self.folder_script_name:
            return self.folder_script_name.rsplit('/', 1)[1]
        return self.folder_script_name
    
    @property
    def can_save(self) -> bool:
        """Check if widget can save (has INI key)"""
        return bool(self.ini_key)
    
    @property
    def needs_ini_key(self) -> bool:
        """Check if widget needs INI key resolved"""
        # FIXED: Your logic was inverted
        return not self.ini_key and bool(self.ini_path) and bool(self.ini_filename)
    
    @property
    def is_global(self) -> bool:
        """Check if widget is global (works without account)"""
        return bool(getattr(self.module, 'GLOBAL', False))
    
    def __getitem__(self, item):
        if item in self.__dict__:
            return self.__dict__[item]
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{item}'")
    
    def __setitem__(self, key, value):
        if key in self.__dict__:
            self.__dict__[key] = value
        else:
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{key}'")
#endregion

class WidgetConfigVars:
    def __init__(self, widget_id: str, section: str, var_name: str):
        self.widget_id = widget_id
        self.section = section
        self.var_name = var_name
            
         
#region widget handler
class WidgetHandler:
    _instance = None
    _widgets_folder = "Widgets"
    CONFIRMATION_MODAL_ID = "This is a critical widget!##ConfirmDisableSystemWidgetManager"
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, widgets_path=None):
        # Singleton guard
        if hasattr(self, "_initialized"):
            return
            
        # Path resolution
        if widgets_path:
            self.widgets_path = os.path.abspath(widgets_path)
        else:
            base_dir = PySystem.Console.get_projects_path()
            self.widgets_path = os.path.join(base_dir, self._widgets_folder)
            
        self.MANAGER_INI_KEY:str = ""
        self.MANAGER_INI_PATH = "Widgets/WidgetManager"
        self.MANAGER_INI_FILENAME = "WidgetManager.ini"
        self.MANAGER_VARS_ADDED = False
        
        # Core state
        self.widgets: dict[str, Widget] = {}
        self.show_ui = True
        self.__pause_optionals = False
        self.run_once = False
        self.enable_all = True
        
        self.paused = False
        
        self.discovered = False
        self.ini_applied = False
        self.widget_initialized = False
        self._initialized = True
        self.config_vars: list[WidgetConfigVars] = []
        self._pending_disable_widget: Widget | None = None
        
        
        
    # Properties
    @property
    def optional_widgets_paused(self):
        return self.__pause_optionals
    
    @property
    def show_widget_ui(self):
        return self.show_ui
    
    #region internal helpers
    def _log_error(self, message: str):
        PySystem.Console.Log("WidgetManager", message, PySystem.Console.MessageType.Error)
        
    def _log_success(self, message: str):
        PySystem.Console.Log("WidgetManager", message, PySystem.Console.MessageType.Info)
        
    def _get_config_var(self, widget_name: str, var_name: str) -> Optional[WidgetConfigVars]:
        for cv in self.config_vars:
            if cv.widget_id == widget_name and cv.var_name == var_name:
                return cv
        return None
    
    def _widget_var(self, widget_id: str, suffix: str) -> str:
        """Returns the unique variable name for Settings lookup"""
        return f"{widget_id}__{suffix}"
    
    def _get_widget_by_plain_name(self, plain_name: str) -> Optional[Widget]:
        for widget in self.widgets.values():
            if widget.plain_name == plain_name:
                return widget
        return None
        
    def _manager_cfg(self) -> Settings:
        # Process-wide singleton; constructing it here returns the same live
        # document any other consumer gets — no key to pass around or look up.
        return Settings(f"{self.MANAGER_INI_PATH}/{self.MANAGER_INI_FILENAME}", "account")

    def _set_widget_state(self, name: str, state: bool):
        widget = self._get_widget_by_plain_name(name)
        if not widget:
            PySystem.Console.Log("WidgetHandler", f"Widget '{name}' not found", PySystem.Console.MessageType.Warning)
            return

        if state:
            widget.enable()
        else:
            widget.disable()

        widget_id = widget.folder_script_name  # full id: "folder/file.py"
        v_enabled = self._widget_var(widget_id, "enabled")  # "folder/file.py__enabled"

        cv = self._get_config_var(widget_id, v_enabled)

        if cv:
            self._manager_cfg().set(cv.section, "enabled", state)

    def _request_disable_widget(self, widget: Widget, broadcast: bool = False):
        if widget.category == "System":
            self._pending_disable_widget = widget
            return

        self.disable_widget(widget.plain_name)
        if broadcast:
            for acc in GLOBAL_CACHE.ShMem.GetAllAccountData():
                if acc.AccountEmail == Player.GetAccountEmail():
                    continue
                
                GLOBAL_CACHE.ShMem.SendMessage(Player.GetAccountEmail(), acc.AccountEmail, SharedCommandType.DisableWidget, ExtraData=(widget.plain_name,))

    def _draw_pending_disable_confirmation(self):
        if self._pending_disable_widget:
            PyImGui.open_popup(self.CONFIRMATION_MODAL_ID)
            self._draw_confirmation_modal()

    def _draw_confirmation_modal(self):
        io = PyImGui.get_io()
        center_x = (io.display_size_x / 2) - 250
        center_y = (io.display_size_y / 2) - 100

        PyImGui.set_next_window_pos(
            (center_x, center_y),
            PyImGui.ImGuiCond.Always,
        )

        PyImGui.set_next_window_size(
            (500, 175),
            PyImGui.ImGuiCond.Always,
        )

        if PyImGui.begin_popup_modal(
            self.CONFIRMATION_MODAL_ID,
            True,
            PyImGui.WindowFlags.NoMove | PyImGui.WindowFlags.NoResize | PyImGui.WindowFlags.NoTitleBar
            | PyImGui.WindowFlags.NoSavedSettings
        ):
            widget = self._pending_disable_widget

            if widget:
                ImGui_Legacy.text_colored(
                    "Warning - This widget is required for core functionality!",
                    (1.0, 0.2, 0.2, 1.0),
                    font_size=16
                )
                PyImGui.separator()

                ImGui_Legacy.text_wrapped(
                    f"The widget '{widget.name}' is a SYSTEM widget.\n\n"
                    "Disabling it may break core functionality.\n\n"
                    "Are you sure you want to continue?"
                )

                PyImGui.spacing()
                PyImGui.separator()
                PyImGui.spacing()

                PyImGui.columns(2, "widget_manager_confirmation_buttons", False)
                if ImGui_Legacy.button("Cancel", -1, 0):
                    self._pending_disable_widget = None
                    PyImGui.close_current_popup()

                PyImGui.next_column()
                if ImGui_Legacy.button("Disable", -1, 0):
                    self.disable_widget(widget.plain_name)
                    self._pending_disable_widget = None
                    PyImGui.close_current_popup()
                PyImGui.end_columns()

            PyImGui.end_popup()
    #endregion        

        
    # --------------------------------------------
    # region discovery
           
    def discover(self):
        if self.discovered:
            return
        
        """Phase 0: Unload currently enabled widgets"""
        for widget in self.widgets.values():
            if widget.enabled:
                widget.disable()
                                
        """Phase 1: Discover widgets without INI configuration"""
        self.widgets.clear()
        
        try:
            self._scan_widget_folders()
            self.discovered = True
        except Exception as e:
            self._log_error(f"Discovery failed: {e}")
            raise
    
    
    def _scan_widget_folders(self):
        """Find .widget folders and load .py files throughout the entire tree"""
        if not os.path.isdir(self.widgets_path):
            raise FileNotFoundError(f"Widgets folder missing: {self.widgets_path}")
        
        for current_dir, dirs, files in os.walk(self.widgets_path):
            # Check if this specific folder is marked as a widget container
            if ".widget" in files:
                for py_file in [f for f in files if f.endswith(".py")]:
                    self._load_widget_module(current_dir, py_file)

    def _load_widget_module(self, folder: str, filename: str):
        """Load a widget module without INI configuration"""
        # Create widget ID
        rel_folder = os.path.relpath(folder, self.widgets_path)
        widget_id = f"{rel_folder}/{filename}" if rel_folder != "." else filename

        plain = os.path.splitext(filename)[0]
        widget_path = "" if rel_folder == "." else rel_folder.replace("\\", "/")

                
        if widget_id in self.widgets:
            return
        
        script_path = os.path.join(folder, filename)
        
        try:
            # 1. Create Widget with EMPTY INI data
            widget = Widget(
                folder_script_name=widget_id,
                plain_name=plain,
                widget_path=widget_path,
                script_path=script_path,
                ini_key="",           # Empty - will be set later
                ini_path="",          # Empty - will be set later  
                ini_filename="",      # Empty - will be set later                
            )
            
            # 3. Register
            self.widgets[widget_id] = widget
            
            #4. Ini handling (SECTION PER WIDGET)
            self.config_vars.append(WidgetConfigVars(
                widget_id=widget_id,
                section=f"Widget:{widget_id}",
                var_name=f"{widget_id}__enabled"
            ))
            self.config_vars.append(WidgetConfigVars(
                widget_id=widget_id,
                section=f"Widget:{widget_id}",
                var_name=f"{widget_id}__optional"
            ))                    

            cv = self._get_config_var(widget.folder_script_name, self._widget_var(widget.folder_script_name, "enabled"))

            _mgr_cfg = self._manager_cfg()
            enabled = bool(_mgr_cfg.get_bool(cv.section, "enabled", False)) if cv else False
            if enabled:
                widget.enable()
                
            #keep logging minimal
            #self._log_success(f"Discovered: {widget_id}")
            
        except Exception as e:
            self._log_error(f"Failed to discover {widget_id}: {e}")
                            
                
    def _apply_ini_configuration(self):
        """Apply saved enabled states and enforce System widget activation"""
        try:
            _mgr_cfg = self._manager_cfg()
            for wid, w in self.widgets.items():
                section = f"Widget:{wid}"

                # 1. Read the current state from Settings (which just loaded from disk)
                enabled = bool(_mgr_cfg.get_bool(section, "enabled", False))

                # 2. THE FORCE: Check if this is a System widget section
                is_system = "Widget:System" in section

                if is_system:
                    # If it's system but the disk/ini said False, we override it right now
                    if not enabled:
                        # PySystem.Console.Log("WidgetManager", f"Forcing System Widget: {wid}", PySystem.Console.MessageType.Info)
                        enabled = True
                        # Update Settings memory so it stays synced
                        if _mgr_cfg:
                            _mgr_cfg.set(section, "enabled", True)
                        # Note: No need to save_vars here unless you want to fix the file immediately; 
                        # the next global save will persist this.
                        self._log_success(f"Enforcing System Widget Enabled: {wid}")
                
                # 3. Final Activation
                if enabled:
                    w.enable()
        except Exception as e:
            self._log_error(f"Failed to apply INI configuration: {e}")
        
        finally:
            self.ini_applied = True
                
    #endregion
    
    #region UI       
    def PauseAllWidgets(self):
        for widget in self.widgets.values():
            if widget.enabled:
                widget.pause()
            
        self.paused = True
                
    def ResumeAllWidgets(self):
        for widget in self.widgets.values():
            if widget.is_paused:
                widget.resume()
                
        self.paused = False
            
    def prepare_discover(self):
        self.discovered = False
        self.ini_applied = False
        
    #endregion
        
    def execute_enabled_widgets_update(self):
        profiling = _get_profiling()
        profiling_enabled = profiling.enabled
        pause_optional = self.pause_optional_widgets

        for widget_name, widget_info in self.widgets.items():
            if not widget_info.enabled or widget_info.is_paused:
                continue

            if pause_optional and widget_info.optional:
                continue

            if widget_info.update is not None:
                try:
                    if profiling_enabled:
                        profiling.runcall_scope("widgets", f"{widget_name}:update", widget_info.update)
                    else:
                        widget_info.update()
                except Exception as e:
                    PySystem.Console.Log("WidgetHandler", f"Error executing widget {widget_name}: {str(e)}", PySystem.Console.MessageType.Error)
                    PySystem.Console.Log("WidgetHandler", f"Stack trace: {traceback.format_exc()}", PySystem.Console.MessageType.Error)

    def execute_enabled_widgets_draw(self):
        profiling = _get_profiling()
        profiling_enabled = profiling.enabled
        style = ImGui_Legacy.Selected_Style.pyimgui_style
        alpha = style.Alpha
        ui_enabled = self.show_widget_ui
        pause_optional = self.optional_widgets_paused

        if not ui_enabled:
            style.Alpha = 0.0
            style.Push()

        for widget_name, widget_info in self.widgets.items():
            if not widget_info.enabled or widget_info.is_paused:
                continue

            if widget_info.minimal is not None:
                try:
                    if profiling_enabled:
                        profiling.runcall_scope("widgets", f"{widget_name}:minimal", widget_info.minimal)
                    else:
                        widget_info.minimal()
                except Exception as e:
                    PySystem.Console.Log("WidgetHandler", f"Error executing minimal of widget {widget_name}: {str(e)}", PySystem.Console.MessageType.Error)
                    PySystem.Console.Log("WidgetHandler", f"Stack trace: {traceback.format_exc()}", PySystem.Console.MessageType.Error)

            if pause_optional and widget_info.optional:
                continue

            if widget_info.draw is not None:
                try:
                    if profiling_enabled:
                        profiling.runcall_scope("widgets", f"{widget_name}:draw", widget_info.draw)
                    else:
                        widget_info.draw()
                except Exception as e:
                    PySystem.Console.Log("WidgetHandler", f"Error executing widget {widget_name}: {str(e)}", PySystem.Console.MessageType.Error)
                    PySystem.Console.Log("WidgetHandler", f"Stack trace: {traceback.format_exc()}", PySystem.Console.MessageType.Error)

        if not ui_enabled:
            style.Alpha = alpha
            style.Push()

    def execute_enabled_widgets_main(self):
        profiling = _get_profiling()
        profiling_enabled = profiling.enabled
        style = ImGui_Legacy.Selected_Style.pyimgui_style
        alpha = style.Alpha
        ui_enabled = self.show_widget_ui
        pause_optional = self.optional_widgets_paused

        if not ui_enabled:
            style.Alpha = 0.0
            style.Push()

        for widget_name, widget_info in self.widgets.items():
            if not widget_info.enabled or widget_info.is_paused:
                continue

            if widget_info.minimal is not None:
                try:
                    if profiling_enabled:
                        profiling.runcall_scope("widgets", f"{widget_name}:minimal", widget_info.minimal)
                    else:
                        widget_info.minimal()
                except Exception as e:
                    PySystem.Console.Log("WidgetHandler", f"Error executing minimal of widget {widget_name}: {str(e)}", PySystem.Console.MessageType.Error)
                    PySystem.Console.Log("WidgetHandler", f"Stack trace: {traceback.format_exc()}", PySystem.Console.MessageType.Error)

            if pause_optional and widget_info.optional:
                continue

            if widget_info.main is not None:
                try:
                    if profiling_enabled:
                        profiling.runcall_scope("widgets", f"{widget_name}:main", widget_info.main)
                    else:
                        widget_info.main()
                except Exception as e:
                    PySystem.Console.Log("WidgetHandler", f"Error executing widget {widget_name}: {str(e)}", PySystem.Console.MessageType.Error)
                    PySystem.Console.Log("WidgetHandler", f"Stack trace: {traceback.format_exc()}", PySystem.Console.MessageType.Error)

        if not ui_enabled:
            style.Alpha = alpha
            style.Push()
        
    def execute_configuring_widgets(self):
        for widget_name, widget_info in self.widgets.items():
            if not widget_info.configuring:
                continue
            try:
                if widget_info.configure:
                    widget_info.configure()
                    
            except Exception as e:
                PySystem.Console.Log("WidgetHandler", f"Error executing widget {widget_name}: {str(e)}", PySystem.Console.MessageType.Error)
                PySystem.Console.Log("WidgetHandler", f"Stack trace: {traceback.format_exc()}", PySystem.Console.MessageType.Error)
      
      
    #region  Public API
    def set_widget_ui_visibility(self, visible: bool):            
        self.show_ui = visible

    def reload_widgets(self):
        self.widget_initialized = False
        self.prepare_discover()
        self.discover()
        self.widget_initialized = True

    def set_optional_widgets_paused(self, paused: bool, sync_shared: bool = True):
        if paused:
            self.pause_optional_widgets()
        else:
            self.resume_optional_widgets()

        if not sync_shared:
            return

        own_email = Player.GetAccountEmail()
        for acc in GLOBAL_CACHE.ShMem.GetAllAccountData():
            if acc.AccountEmail == own_email:
                continue

            GLOBAL_CACHE.ShMem.SendMessage(
                own_email,
                acc.AccountEmail,
                SharedCommandType.PauseWidgets if paused else SharedCommandType.ResumeWidgets,
            )

    def toggle_optional_widgets_paused(self, sync_shared: bool = True) -> bool:
        paused = not self.optional_widgets_paused
        self.set_optional_widgets_paused(paused, sync_shared=sync_shared)
        return self.optional_widgets_paused
        
    def pause_optional_widgets(self):
        for widget in self.widgets.values():
            if widget.enabled and widget.optional and not widget.is_paused:
                widget.pause()
                
        self.__pause_optionals = True
        
    def resume_optional_widgets(self):
        for widget in self.widgets.values():
            if widget.enabled and widget.optional and widget.is_paused:
                widget.resume()
                
        self.__pause_optionals = False
    
    def is_widget_enabled(self, name: str) -> bool:
        widget = self._get_widget_by_plain_name(name)
        return bool(widget and widget.enabled)

    def list_enabled_widgets(self) -> list[str]:
        return [name for name, info in self.widgets.items() if info.enabled]
    
    def enable_widget(self, name: str):
        self._set_widget_state(name, True)
        if name == "HeroAI" or str(name).replace("\\", "/").endswith("/HeroAI.py"):
            self._force_heroai_player_options(True)

    def disable_widget(self, name: str):
        self._set_widget_state(name, False)
        if name == "HeroAI" or str(name).replace("\\", "/").endswith("/HeroAI.py"):
            self._force_heroai_player_options(False)

    def _force_heroai_player_options(self, enabled: bool):
        try:
            from Py4GWCoreLib import GLOBAL_CACHE, Player
            from Py4GWCoreLib.GlobalCache.shared_memory_src.Globals import SHMEM_MAX_NUMBER_OF_SKILLS

            account_email = Player.GetAccountEmail()
            if not account_email:
                return

            options = GLOBAL_CACHE.ShMem.GetHeroAIOptionsFromEmail(account_email)
            if options is None:
                return

            options.Following = bool(enabled)
            options.Avoidance = bool(enabled)
            options.Looting = bool(enabled)
            options.Targeting = bool(enabled)
            options.Combat = bool(enabled)
            for skill_index in range(SHMEM_MAX_NUMBER_OF_SKILLS):
                options.Skills[skill_index] = bool(enabled)
            GLOBAL_CACHE.ShMem.SetHeroAIOptionsByEmail(account_email, options)
        except Exception as exc:
            PySystem.Console.Log("WidgetHandler", f"Failed to force HeroAI player options: {exc}", PySystem.Console.MessageType.Warning)
         
    def set_widget_configuring(self, name: str, value: bool = True):
        widget = self._get_widget_by_plain_name(name)
        if not widget:
            PySystem.Console.Log("WidgetHandler", f"Widget '{name}' not found", PySystem.Console.MessageType.Warning)
            return
        widget.set_configuring(value)
        
    def get_widget_info(self, name: str) -> Widget | None:
        # 1) direct full id lookup
        w = self.widgets.get(name, None)
        if w:
            return w

        # 2) fallback to plain_name lookup
        return self._get_widget_by_plain_name(name)
    #endregion
#endregion

_widget_handler = WidgetHandler()

def get_widget_handler() -> WidgetHandler:
    return _widget_handler
