"""
Xunlai storage "Deposit All Materials" helper.

Deposit uses the canonical XunlaiStorageWindow helper, which clicks the
registered ``XunlaiWindow.DepositAllMaterials`` frame - the legacy
``frame_aliases.json`` lookup and the child-offset walk are gone.
"""

from typing import Optional

from Py4GWCoreLib import Map
from Py4GWCoreLib import Routines
from Py4GWCoreLib.FrameTree import Frame, FrameId
from Py4GWCoreLib.Inventory import Inventory
from Py4GWCoreLib.UIManager import XunlaiStorageWindow
from Py4GWCoreLib.py4gwcorelib_src.Console import Console, ConsoleLog

MODULE_NAME = "DepositMaterials"


class DepositMaterials:

    def find_deposit_all_frame_id(self) -> Optional[int]:
        """The live frame id of the Deposit All Materials button, or None."""
        frame = Frame(FrameId.XunlaiWindow.DepositAllMaterials)
        return frame.frame_id if frame.exists else None

    def DepositMaterials(self):
        """Open the storage window in an outpost, then deposit all materials."""
        if not Map.IsOutpost():
            ConsoleLog(
                MODULE_NAME,
                "Wrong location type - requires an outpost",
                Console.MessageType.Warning,
            )
            return

        if not Inventory.IsStorageOpen():
            Inventory.OpenXunlaiWindow()
            yield from Routines.Yield.wait(150)
        else:
            ConsoleLog(MODULE_NAME, "Chest already open", Console.MessageType.Info)

        yield from Routines.Yield.wait(350)
        if not Inventory.IsStorageOpen():
            return

        yield from Routines.Yield.wait(150)

        frame_id = self.find_deposit_all_frame_id()
        if frame_id is not None:
            ConsoleLog(
                MODULE_NAME,
                f"Clicked frame {frame_id} to DepositAllMaterials",
                Console.MessageType.Info,
            )
            XunlaiStorageWindow.ClickDepositAllMaterials()
        else:
            ConsoleLog(
                MODULE_NAME,
                "Deposit All Materials button not found",
                Console.MessageType.Warning,
            )