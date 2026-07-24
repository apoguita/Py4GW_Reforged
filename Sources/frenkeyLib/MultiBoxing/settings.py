import ctypes

import PySystem

from Py4GWCoreLib.GlobalCache.SharedMemory import AccountStruct
from Py4GWCoreLib.Player import Player
from Py4GWCoreLib.py4gwcorelib_src.Console import ConsoleLog
from Py4GWCoreLib.py4gwcorelib_src.JsonFactory import JsonFactory
from Py4GWCoreLib.py4gwcorelib_src.Settings import Settings as NativeSettings
from Sources.frenkeyLib.MultiBoxing.enum import RenameClientType
from Sources.frenkeyLib.MultiBoxing.messaging import position_clients
from Sources.frenkeyLib.MultiBoxing.region import Region

MODULE_NAME = __file__.split("\\")[-2]

# Multiboxing config is shared across every client on the machine (the reload
# broadcast in messaging.py assumes a single shared file), so both the flat
# settings and the layouts live in the machine-wide "global" scope.
_SETTINGS_DOC = "MultiBoxing/MultiBoxing.ini"
_SETTINGS_SECTION = "MultiBoxing"
_LAYOUT_INDEX_DOC = "MultiBoxing/Layouts.json"


def _settings_store() -> NativeSettings:
    return NativeSettings(_SETTINGS_DOC, "global")


def _layout_index() -> JsonFactory:
    return JsonFactory(_LAYOUT_INDEX_DOC, "global")


def _layout_store(name: str) -> JsonFactory:
    return JsonFactory(f"MultiBoxing/Layouts/{name}.json", "global")


class Settings:
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Settings, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        # guard: only initialize once
        if self.__class__._initialized:
            return

        self.__class__._initialized = True

        screen_size = self.get_screen_size()

        self.sub_regions : list[Region] = []  # Placeholder for sub-regions

        self.regions : list[Region] = []
        self.active_region : Region | None = None
        self.move_slave_to_main : bool = True
        self.move_on_focus : bool = False

        self.show_overview : bool = True

        self.screen_size : tuple[int, int] = screen_size
        self.screen_size_changed : bool = False

        self.custom_names : dict[str, str] = {}  # account email -> custom name
        self.rename_to : RenameClientType = RenameClientType.Character
        self.append_gw : bool = True

        self.hide_widgets_on_slave : bool = True

        self.snap_to_edges : bool = True
        self.edge_snap_distance : int = 15

        self.columns : int = 1
        self.rows : int = 1
        self.layout_import_rows : str = "1 1 1"
        self.layout_import_columns : str = "1 1 1"

        self.layout : str = "None"  # Current layout name
        self.layouts : list[str] = ["None"]  # List of layout names

        self.account : str = ""
        self.accounts : list[AccountStruct] = []  # List of account objects
        self.accounts_order : list[str] = []  # List of (account index, account email) tuples


    @property
    def main_region(self) -> Region | None:
        main = next((r for r in self.regions if r.main), None) if self.regions else None

        return main

    def set_accounts(self, accounts: list[AccountStruct]):
        self.accounts = accounts

        for acc in accounts:
            if not acc.AccountEmail:
                continue

            if acc.AccountEmail not in self.accounts_order:
                self.accounts_order.append(acc.AccountEmail)

    def move_account(self, from_index: int, to_index: int):
        if from_index < 0 or from_index >= len(self.accounts_order):
            return
        if to_index < 0 or to_index >= len(self.accounts_order):
            return

        # Move the account
        account = self.accounts_order.pop(from_index)
        self.accounts_order.insert(to_index, account)

        # Save new order
        self.save_settings()

    def get_account_mail(self) -> str:
        if not self.account:
            self.account = Player.GetAccountEmail()

        return self.account

    def get_screen_size(self) -> tuple[int, int]:
        user32 = ctypes.windll.user32
        user32.SetProcessDPIAware()
        screen_width = user32.GetSystemMetrics(0)
        screen_height = user32.GetSystemMetrics(1)
        return screen_width, screen_height

    def add_region(self, region: Region):
        self.regions.append(region)

    def remove_region(self, region: Region):
        if region in self.regions:
            self.regions.remove(region)

    def clear_regions(self):
        self.regions.clear()

    def save_settings(self):
        store = _settings_store()
        store.set(_SETTINGS_SECTION, "rename_to", self.rename_to.name)
        store.set(_SETTINGS_SECTION, "append_gw", self.append_gw)
        store.set(_SETTINGS_SECTION, "hide_widgets_on_slave", self.hide_widgets_on_slave)
        store.set(_SETTINGS_SECTION, "snap_to_edges", self.snap_to_edges)
        store.set(_SETTINGS_SECTION, "edge_snap_distance", self.edge_snap_distance)
        store.set(_SETTINGS_SECTION, "layout", self.layout)
        store.set(_SETTINGS_SECTION, "accounts_order", ",".join(self.accounts_order))
        store.set(_SETTINGS_SECTION, "show_overview", self.show_overview)

    def load_settings(self):
        store = _settings_store()
        # Pick up writes made by a peer client (shared global document).
        store.reload()

        rename_to_str = store.get_str(_SETTINGS_SECTION, "rename_to", "Character")
        self.rename_to = RenameClientType[rename_to_str] if rename_to_str in RenameClientType.__members__ else RenameClientType.Character
        self.append_gw = store.get_bool(_SETTINGS_SECTION, "append_gw", True)
        self.hide_widgets_on_slave = store.get_bool(_SETTINGS_SECTION, "hide_widgets_on_slave", True)
        self.snap_to_edges = store.get_bool(_SETTINGS_SECTION, "snap_to_edges", True)
        self.edge_snap_distance = store.get_int(_SETTINGS_SECTION, "edge_snap_distance", 15)
        self.layout = store.get_str(_SETTINGS_SECTION, "layout", "None")
        order_raw = store.get_str(_SETTINGS_SECTION, "accounts_order", "")
        self.accounts_order = [email for email in order_raw.split(",") if email]
        self.show_overview = store.get_bool(_SETTINGS_SECTION, "show_overview", True)

    def save_layout(self, name: str):
        if not name:
            ConsoleLog(MODULE_NAME, "Layout name is empty, cannot save layout.", PySystem.Console.MessageType.Warning)
            return

        _layout_store(name).set_json("regions", [region.to_dict() for region in self.regions])
        ConsoleLog(MODULE_NAME, f"Layout '{name}' saved successfully.")

        if name not in self.layouts:
            self.layouts.append(name)  # Add to layouts list if not already present

        index = _layout_index()
        names = index.get_json("names", [])
        if name not in names:
            names.append(name)
            index.set_json("names", names)

    def load_layout(self, name: str):
        if not name or name == "None":
            ConsoleLog(MODULE_NAME, "Layout name is empty or 'None', cannot load layout.", PySystem.Console.MessageType.Warning)
            return

        store = _layout_store(name)
        # Pick up a peer client's save of this layout (shared global document).
        store.reload()

        if not store.has("regions"):
            ConsoleLog(MODULE_NAME, f"Layout '{name}' does not exist.", PySystem.Console.MessageType.Warning)
            return

        self.clear_regions()

        for i, region_data in enumerate(store.get_json("regions", [])):
            region = Region.from_dict(region_data, number=i+1)
            self.add_region(region)

        if name != self.layout:
            self.layout = name
            self.save_settings()

        ConsoleLog(MODULE_NAME, f"Layout '{name}' loaded successfully with {len(self.regions)} regions.")
        position_clients(self.get_account_mail(), self.regions, self.accounts)

    def load_layouts(self):
        self.layouts = ["None"]  # Reset to default

        for name in _layout_index().get_json("names", []):
            if name and name not in self.layouts:
                self.layouts.append(name)
                ConsoleLog(MODULE_NAME, f"Adding layout: '{name}'")
