"""Recolor & Beacons persistence -- flat, per account, and only the PERSISTED instance is written.

Everything here is a handful of flat values, so ``Settings`` is the whole story: there is no
structured collection to keep. The filters and their outcomes belong to the Loot Filter Factory's
global store, and beacon presets to the Beacons module's -- neither is duplicated here.

**The live instance is never written.** There is no code path from it to a writer.
"""

from .model import MarkConfig

_INI = "Widgets/System/RecolorBeacons.ini"


def _settings():
    try:
        from Py4GWCoreLib.py4gwcorelib_src.Settings import Settings

        return Settings(_INI, "account")
    except Exception:
        return None


def load() -> MarkConfig:
    """The persisted configuration. Live is seeded from a copy of this."""
    config = MarkConfig()
    settings = _settings()
    if settings is None:
        return config
    config.enabled = settings.get_bool("general", "enabled", False)
    config.profile = settings.get_str("general", "profile", "")
    config.blank_unassigned = settings.get_bool("general", "blank_unassigned", False)
    config.max_beacons = settings.get_int("beacons", "max_beacons", 8)
    config.beacon_distance = float(settings.get_int("beacons", "beacon_distance", 2500))
    config.cheap_distant = settings.get_bool("beacons", "cheap_distant", True)
    config.cheap_distance = float(settings.get_int("beacons", "cheap_distance", 1200))
    return config


def save(config: MarkConfig) -> None:
    """Persist. Only ever called with the PERSISTED instance -- never with live."""
    settings = _settings()
    if settings is None:
        return
    settings.set("general", "enabled", bool(config.enabled))
    settings.set("general", "profile", str(config.profile))
    settings.set("general", "blank_unassigned", bool(config.blank_unassigned))
    settings.set("beacons", "max_beacons", int(config.max_beacons))
    settings.set("beacons", "beacon_distance", int(config.beacon_distance))
    settings.set("beacons", "cheap_distant", bool(config.cheap_distant))
    settings.set("beacons", "cheap_distance", int(config.cheap_distance))
