"""
Inventory "Identify All Items" helper.

The Identify All button is a named native frame, so it resolves straight from
the FrameTree registry - the legacy ``frame_aliases.json`` lookup and the
child-offset walk under the inventory window are both gone.
"""

from typing import Optional

from Py4GWCoreLib import Routines
from Py4GWCoreLib import UIManager
from Py4GWCoreLib.FrameTree import Frame, FrameId
from Py4GWCoreLib.enums_src.UI_enums import WindowID
from Py4GWCoreLib.py4gwcorelib_src.Console import Console, ConsoleLog

MODULE_NAME = "IdentifyAll"


class IdentifyAllItems:

    def IsWindowOpen(self) -> bool:
        """Whether the inventory bags window (the button's container) is visible."""
        return UIManager.IsWindowVisible(WindowID.WindowID_InventoryBags)

    def OpenWindow(self) -> None:
        """Open the inventory window when it is not already visible."""
        if self.IsWindowOpen():
            return
        UIManager.SetWindowVisible(WindowID.WindowID_Inventory, True)

    def find_identify_all_frame_id(self) -> Optional[int]:
        """The live frame id of the Identify All button, or None when absent."""
        frame = Frame(FrameId.IdentifyAll)
        return frame.frame_id if frame.exists else None

    def IdentifyAll(self):
        """Open the inventory window, then click the Identify All button."""
        if not self.IsWindowOpen():
            self.OpenWindow()
            yield from Routines.Yield.wait(150)
        else:
            ConsoleLog(MODULE_NAME, "Inventory already open", Console.MessageType.Info)

        yield from Routines.Yield.wait(350)
        if not self.IsWindowOpen():
            return

        yield from Routines.Yield.wait(150)

        frame = Frame(FrameId.IdentifyAll)
        if frame.exists:
            ConsoleLog(
                MODULE_NAME,
                f"Clicked frame {frame.frame_id} to IdentifyAll",
                Console.MessageType.Info,
            )
            frame.click()
        else:
            ConsoleLog(
                MODULE_NAME,
                "Identify All button not found",
                Console.MessageType.Warning,
            )