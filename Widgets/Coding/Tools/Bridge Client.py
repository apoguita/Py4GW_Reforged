"""Widget discovery adapter for the Py4GW bridge client.

The bridge implementation lives in ``py4gw_bridge.injected_client``. This
file remains under ``Widgets/`` because the Py4GW widget manager discovers
widgets from that tree.

The package is dropped from ``sys.modules`` before the import on purpose. The
widget manager gives this file a fresh module name every time it loads, but a
plain package import resolves from ``sys.modules``, so without this a widget
reload keeps serving the code from the last client start: a change in
``py4gw_bridge/`` would only take effect after restarting the game client.
"""

from Py4GWCoreLib.py4gwcorelib_src.Utils import Utils

Utils.ClearSubModules("py4gw_bridge")

from py4gw_bridge.injected_client import MODULE_ICON
from py4gw_bridge.injected_client import MODULE_NAME
from py4gw_bridge.injected_client import OPTIONAL
from py4gw_bridge.injected_client import __widget__
from py4gw_bridge.injected_client import draw
from py4gw_bridge.injected_client import main
