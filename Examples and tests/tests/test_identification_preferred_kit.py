"""Offline regression for the Prefer Infinite Identification Kit option.

The option must select model 38620 from an allowed inventory slot and otherwise leave the legacy
kit selection untouched.

Run:  python "Examples and tests/tests/test_identification_preferred_kit.py"
Exit code 1 on any failure.
"""

from enum import IntEnum
import importlib.util
import pathlib
import sys
import types


ROOT = pathlib.Path(__file__).resolve().parents[2]
SETTINGS_DIR = ROOT / "Py4GWCoreLib" / "py4gwcorelib_src" / "system_settings"
INFINITE_KIT_ID = 102
NORMAL_KIT_ID = 100
INFINITE_MODEL_ID = 38620


class ModelID(IntEnum):
    Infinite_Identification_Kit = INFINITE_MODEL_ID


class FakeItem:
    models = {INFINITE_KIT_ID: INFINITE_MODEL_ID, NORMAL_KIT_ID: 2989}

    @classmethod
    def GetModelID(cls, item_id: int) -> int:
        return cls.models[item_id]


class FakeInventory:
    @staticmethod
    def GetFirstIDKit() -> int:
        return NORMAL_KIT_ID


def package(name: str) -> None:
    value = types.ModuleType(name)
    value.__path__ = []
    sys.modules[name] = value


def module(name: str, **values) -> None:
    value = types.ModuleType(name)
    for key, entry in values.items():
        setattr(value, key, entry)
    sys.modules[name] = value


for package_name in (
    "Py4GWCoreLib",
    "Py4GWCoreLib.enums_src",
    "Py4GWCoreLib.py4gwcorelib_src",
    "Py4GWCoreLib.py4gwcorelib_src.system_settings",
    "Py4GWCoreLib.py4gwcorelib_src.system_settings.inventory",
    "Py4GWCoreLib.py4gwcorelib_src.system_settings.loot_filter_factory",
    "Py4GWCoreLib.py4gwcorelib_src.system_settings.identification",
):
    package(package_name)

BASE = "Py4GWCoreLib.py4gwcorelib_src.system_settings"
setattr(sys.modules["Py4GWCoreLib"], "ThrottledTimer", object)
module("Py4GWCoreLib.Item", Item=FakeItem)
module("Py4GWCoreLib.Inventory", Inventory=FakeInventory)
module("Py4GWCoreLib.enums_src.Item_enums", INVENTORY_BAGS=())
module("Py4GWCoreLib.enums_src.Model_enums", ModelID=ModelID)
module(BASE + ".inventory.monitor", InventoryMonitor=object)
module(BASE + ".inventory.store", load_bags=lambda: None)
module(BASE + ".inventory.model", BAGS=())
module(BASE + ".item_runtime", StableMapGate=object, get_item_operation_lease=lambda: None)
module(BASE + ".loot_filter_factory.matcher", matches=lambda *_args: False)
module(BASE + ".loot_filter_factory.model", MATCH_ALL=0, Filter=object)
module(BASE + ".identification.store")
module(BASE + ".identification.model", IdentificationSettings=object)

spec = importlib.util.spec_from_file_location(
    BASE + ".identification.controller", str(SETTINGS_DIR / "identification" / "controller.py")
)
assert spec is not None and spec.loader is not None
controller = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = controller
spec.loader.exec_module(controller)

failures = 0


def check(label: str, expected, observed) -> None:
    global failures
    ok = expected == observed
    if not ok:
        failures += 1
    print("[%s] %s" % ("PASS" if ok else "FAIL", label))
    if not ok:
        print("      expected: %r" % (expected,))
        print("      observed: %r" % (observed,))


def entry(item_id: int, allowed: bool = True, is_id_kit: bool = False):
    return types.SimpleNamespace(item_id=item_id, bag=None, slot=int(allowed), is_id_kit=is_id_kit)


def build(prefer: bool, entries: list, map_ready: bool = True):
    instance = controller.IdentificationController.__new__(controller.IdentificationController)
    instance._settings = types.SimpleNamespace(prefer_infinite_id_kit=prefer)
    instance._map_context = lambda: object() if map_ready else None
    instance._monitor = types.SimpleNamespace(scan=lambda *_args, **_kwargs: entries)
    controller.inventory_store = types.SimpleNamespace(
        load_bags=lambda: types.SimpleNamespace(allows=lambda _bag, slot: bool(slot))
    )
    return instance


normal = entry(NORMAL_KIT_ID, is_id_kit=True)
infinite = entry(INFINITE_KIT_ID)
blocked_infinite = entry(INFINITE_KIT_ID, allowed=False)

check("enabled option selects the infinite kit", INFINITE_KIT_ID, build(True, [normal, infinite]).preferred_kit_id())
check("disabled option selects no preferred kit", 0, build(False, [normal, infinite]).preferred_kit_id())
check("a blocked Bags slot is not selected", 0, build(True, [normal, blocked_infinite]).preferred_kit_id())
check("a missing infinite kit is not selected", 0, build(True, [normal]).preferred_kit_id())
check("an unstable map selects no kit", 0, build(True, [infinite], map_ready=False).preferred_kit_id())
check("the infinite kit alone is usable when enabled", True, build(True, [infinite])._has_usable_id_kit())
check("the legacy kit stays usable when the option is off", True, build(False, [normal])._has_usable_id_kit())
check("a kit without the native flag stays unusable when off", False, build(False, [entry(NORMAL_KIT_ID)])._has_usable_id_kit())

print("=" * 68)
print("%d case(s) failed" % failures)
sys.exit(1 if failures else 0)
