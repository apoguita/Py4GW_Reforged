"""Global persistence for the remaining independent item-feature settings."""

from .model import InventoryFeatureSettings

_DOC = "Widgets/System/InventoryFeatures.json"


def _json():
    try:
        from Py4GWCoreLib.py4gwcorelib_src.JsonFactory import JsonFactory

        return JsonFactory(_DOC, "global")
    except Exception:
        return None


def load() -> InventoryFeatureSettings:
    document = _json()
    raw = document.get_json("settings", {}) if document is not None else {}
    return InventoryFeatureSettings.from_dict(raw)


def save(settings: InventoryFeatureSettings) -> None:
    document = _json()
    if document is not None:
        document.set_json("settings", settings.to_dict())
