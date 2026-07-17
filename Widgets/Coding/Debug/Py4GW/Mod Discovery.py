"""
Mod Discovery / Validation
=========================

Compares the game's PvP mod table (the 390 upgrade_ids in game_mod_table.py) against the
mods actually present on your REAL items — the PvE ground truth. For every item in
inventory / equipped / storage it reads each modifier; any "Upgrade" modifier (identifier
0x2408, whose low 16 bits = upgrade_id) is checked against the known 390.

  - Validates our data: known upgrade_ids should all resolve.
  - Discovers gaps: any upgrade_id NOT in the 390 is a mod the PvP list is missing
    (the ~19 PvE-only ones — of Slaying / of the Profession — and possibly more),
    logged with the item's decoded name for identification.

Output: docs/item_mods/catalogs/mod_discovery.txt  (+ unknown upgrade_ids as CSV).
Run in-game; scan more characters/storage over time to widen coverage.
"""

import os
import traceback

import PyImGui
import PyItem
import PySystem

from Py4GWCoreLib.ItemArray import ItemArray
from Py4GWCoreLib.Item import Item
from Py4GWCoreLib.native_src.internals import string_table

MODULE_NAME = "Mod Discovery"
TOOLS = r"C:\Users\Apo\Py4GW_Reforged\docs\item_mods\tools"
OUT = r"C:\Users\Apo\Py4GW_Reforged\docs\item_mods\catalogs\mod_discovery.txt"

UPGRADE_IDENTIFIER = 0x2408   # mod >> 16 for the "Upgrade" modifier; GetArg() = upgrade_id

# inventory 1-4, equipped 22, xunlai storage 8-18, equipment pack 5, belt pouches handled by 1-4
SCAN_BAGS = [1, 2, 3, 4, 5, 22, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18]

STATE_IDLE, STATE_WARMING, STATE_WRITING, STATE_DONE = 0, 1, 2, 3
_WARM_FRAMES = 150

_state = STATE_IDLE
_warm_left = 0
_known = set()
_found = []          # list of dict(upgrade_id, item_id, model_id, type, known)
_status = "Idle. Press to scan your items and validate against the 390."
_last = ""
initialized = False


def _load_known():
    ns = {}
    p = os.path.join(TOOLS, "game_mod_table.py")
    if os.path.exists(p):
        exec(open(p, encoding="utf-8").read(), ns)
    return {u.get("upgrade_id") for u in ns.get("MOD_UNLOCKS", []) or [] if u.get("upgrade_id")}


def _scan():
    known = _load_known()
    found = []
    bags = ItemArray.CreateBagList(*SCAN_BAGS)
    item_ids = ItemArray.GetItemArray(bags)
    seen_items = set()
    for iid in item_ids:
        if iid in seen_items:
            continue
        seen_items.add(iid)
        try:
            it = PyItem.PyItem(iid)
            mods = it.modifiers or []
            try:
                itype = it.item_type.ToInt()
            except Exception:
                itype = -1
            model = getattr(it, "model_id", 0)
        except Exception:
            continue
        for m in mods:
            try:
                if m.GetIdentifier() == UPGRADE_IDENTIFIER:
                    uid = m.GetArg()
                    found.append({"upgrade_id": uid, "item_id": iid, "model_id": model,
                                  "type": itype, "known": uid in known})
                    Item.RequestName(iid)
            except Exception:
                pass
    return known, found


def _name(item_id):
    try:
        return string_table.decode(bytes(PyItem.PyItem(item_id).GetCompleteNameEnc()))
    except Exception:
        return ""


def _write():
    global _last
    unknown = [f for f in _found if not f["known"]]
    known_ids = sorted({f["upgrade_id"] for f in _found if f["known"]})
    unk_ids = sorted({f["upgrade_id"] for f in _found})
    unk_only = sorted({f["upgrade_id"] for f in unknown})

    lines = []
    lines.append("MOD DISCOVERY / VALIDATION  (your items vs the game's 390 PvP mods)")
    lines.append("=" * 78)
    lines.append("items scanned with upgrades: %d   distinct upgrade_ids on items: %d" % (
        len({f["item_id"] for f in _found}), len(unk_ids)))
    lines.append("known (in the 390): %d   UNKNOWN (missing from the 390): %d" % (
        len(known_ids), len(unk_only)))
    lines.append("")
    lines.append("=== UNKNOWN upgrade_ids (mods NOT in the PvP table) ===")
    if not unknown:
        lines.append("  (none found on the items scanned)")
    seen = set()
    for f in sorted(unknown, key=lambda x: x["upgrade_id"]):
        uid = f["upgrade_id"]
        if uid in seen:
            continue
        seen.add(uid)
        nm = string_table.decode_plain(bytes(PyItem.PyItem(f["item_id"]).GetCompleteNameEnc())) if True else ""
        lines.append("  upgrade_id 0x%X  (type %d, model %d)  on item: %r" % (
            uid, f["type"], f["model_id"], nm))
    lines.append("")
    lines.append("=== all distinct upgrade_ids seen on your items ===")
    lines.append("  known:   " + ", ".join("0x%X" % u for u in known_ids))
    lines.append("  UNKNOWN: " + ", ".join("0x%X" % u for u in unk_only))
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    _last = OUT
    try:
        PySystem.Console.Log(MODULE_NAME, "scanned; %d unknown mods -> %s" % (len(unk_only), OUT),
                             PySystem.Console.MessageType.Success)
    except Exception:
        pass


def draw_widget():
    global _state, _warm_left, _known, _found, _status
    try:
        if PyImGui.begin(MODULE_NAME):
            PyImGui.text("Scans your items, diffs their mods vs the 390 PvP mods.")
            PyImGui.text("Unknown upgrade_ids = mods missing from the table.")
            PyImGui.separator()
            if _state in (STATE_IDLE, STATE_DONE):
                if PyImGui.button("Scan items + validate"):
                    try:
                        _known, _found = _scan()
                        _state = STATE_WARMING
                        _warm_left = _WARM_FRAMES
                        u = len({f["upgrade_id"] for f in _found if not f["known"]})
                        _status = "Scanned %d upgrades (%d unknown). Warming names..." % (len(_found), u)
                    except Exception as e:
                        _status = "Scan failed: %s" % e
            else:
                PyImGui.text("Working...")
            PyImGui.separator()
            PyImGui.text(_status)
            if _last:
                PyImGui.text_wrapped(_last)
        PyImGui.end()
    except Exception:
        try:
            PySystem.Console.Log(MODULE_NAME, traceback.format_exc(), PySystem.Console.MessageType.Error)
        except Exception:
            pass

    if _state == STATE_WARMING:
        for f in _found:
            _name(f["item_id"])
        _warm_left -= 1
        if _warm_left <= 0:
            _state = STATE_WRITING
    elif _state == STATE_WRITING:
        try:
            _write()
            _status = "Done. See mod_discovery.txt."
        except Exception as e:
            _status = "Write failed: %s" % e
        _state = STATE_DONE


def draw():
    if initialized:
        draw_widget()


def main():
    global initialized
    initialized = True


if __name__ == "__main__":
    main()
