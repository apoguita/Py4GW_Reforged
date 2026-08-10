"""Widget discovery adapter for the Py4GW bridge client.

The bridge implementation lives in ``py4gw_bridge.injected_client``. This
file remains under ``Widgets/`` because the Py4GW widget manager discovers
widgets from that tree.
"""

from py4gw_bridge.injected_client import MODULE_ICON
from py4gw_bridge.injected_client import MODULE_NAME
from py4gw_bridge.injected_client import OPTIONAL
from py4gw_bridge.injected_client import __widget__
from py4gw_bridge.injected_client import draw
from py4gw_bridge.injected_client import main
