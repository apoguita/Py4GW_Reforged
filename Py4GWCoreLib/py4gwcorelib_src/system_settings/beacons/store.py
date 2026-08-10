"""Beacon preset storage -- global, and always containing the base beacon.

**Presets are global**, shared across accounts, exactly like filters and profiles: a beacon authored
once is available everywhere. Which preset a feature *uses* is a selection, and belongs to that
feature's per-account settings -- not here.

**The shipped beacons are hard-coded**, not seeded into this file: the base, one per rarity, and
Red. They are always present because the code defines them, so they cannot go missing on an install
whose document already existed. They are editable -- an edit is stored here as an override under the
same name -- but not deletable, since deleting something the code defines only makes it reappear.

**Sharing is by file, never the clipboard**
(`docs/architecture/records/pending-fixes.md` PF-4): export writes a file the
user puts wherever they like, import reads one back in.
"""

from .model import BASE_NAME
from .model import BeaconPreset
from .model import base_preset
from .model import rarity_presets

_DOC = "Widgets/System/Beacons.json"


def _doc():
    """The global document. Imported lazily so this module stays import-safe offline."""
    try:
        from Py4GWCoreLib.py4gwcorelib_src.JsonFactory import JsonFactory

        return JsonFactory(_DOC, "global")
    except Exception:
        return None


def shipped() -> list[BeaconPreset]:
    """The beacons that ship with the library: the base, plus one per rarity, plus Red.

    **Built in code, never seeded into a file.** They are package data in the same sense the item
    catalogs are -- present because the code says so, not because a document happened to be written
    correctly once. Seeding them into the store instead made them invisible on any install whose
    document already existed, which is exactly the failure a file-seeded default invites.
    """
    return [base_preset()] + rarity_presets()


SHIPPED_NAMES: tuple[str, ...] = tuple(p.name for p in shipped())


def load() -> list[BeaconPreset]:
    """The shipped beacons first, then the user's own.

    A stored preset whose name matches a shipped one **replaces** it -- that is how an edit to a
    shipped beacon survives, without the shipped list ever being able to go missing.
    """
    doc = _doc()
    raw = doc.get_json("presets", []) if doc is not None else []
    stored: dict[str, BeaconPreset] = {}
    order: list[str] = []
    if isinstance(raw, list):
        for entry in raw:
            if isinstance(entry, dict):
                try:
                    preset = BeaconPreset.from_dict(entry)
                except Exception:
                    continue
                stored[preset.name] = preset
                order.append(preset.name)

    out = [stored.get(preset.name, preset) for preset in shipped()]
    out += [stored[name] for name in order if name not in SHIPPED_NAMES]
    return out


def save(presets) -> None:
    doc = _doc()
    if doc is not None:
        doc.set_json("presets", [p.to_dict() for p in presets])


def by_name(presets, name: str) -> BeaconPreset | None:
    for preset in presets:
        if preset.name == name:
            return preset
    return None


def unique_name(presets, wanted: str) -> str:
    """``wanted``, or ``wanted (2)``, ``(3)``... Names identify a preset, so they cannot repeat."""
    taken = {p.name for p in presets}
    if wanted not in taken:
        return wanted
    index = 2
    while "%s (%d)" % (wanted, index) in taken:
        index += 1
    return "%s (%d)" % (wanted, index)


def is_protected(name: str) -> bool:
    """The shipped beacons cannot be deleted -- they are code, so they would simply reappear.

    They remain fully EDITABLE; an edit is stored as an override under the same name. Only the
    user's own presets can be removed.
    """
    return name in SHIPPED_NAMES


# ---------------------------------------------------------------- sharing, by file


def export_to_file(preset: BeaconPreset, path: str) -> tuple[bool, str]:
    """Write one preset to a file of the user's choosing. Returns ``(ok, message)``.

    Raw ``json`` is correct here and is not a breach of the persistence rule: this writes to a path
    the **user** picked, outside the managed store. ``JsonFactory`` owns the store and is jailed to
    it, which is exactly why it cannot be the thing that writes an export.
    """
    import json

    try:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"kind": "py4gw.beacon", "version": 1, "preset": preset.to_dict()},
                      handle, indent=2)
        return True, "Exported to %s" % path
    except OSError as exc:
        return False, "Could not write %s: %s" % (path, exc)


def import_from_file(path: str) -> tuple[BeaconPreset | None, str]:
    """Read a preset back. Returns ``(preset_or_None, message)``; the caller names and stores it."""
    import json

    try:
        with open(path, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except OSError as exc:
        return None, "Could not read %s: %s" % (path, exc)
    except ValueError as exc:
        return None, "Not valid JSON: %s" % exc

    if not isinstance(raw, dict):
        return None, "Not a beacon file."
    body = raw.get("preset") if raw.get("kind") == "py4gw.beacon" else raw
    if not isinstance(body, dict):
        return None, "Not a beacon file."
    # A file without a single recognisable section is not a beacon. Without this, `from_dict`
    # falls back to the defaults for everything and ANY JSON object silently imports as a
    # brand-new base beacon -- a rejection reported as a success.
    if not any(section in body for section in ("params", "colors", "emitters")):
        return None, "Not a beacon file - no beacon data in it."
    try:
        return BeaconPreset.from_dict(body), "Imported %s" % body.get("name", "preset")
    except Exception as exc:
        return None, "Could not read that preset: %s" % exc
