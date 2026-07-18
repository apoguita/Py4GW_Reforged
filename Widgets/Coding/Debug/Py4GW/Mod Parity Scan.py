"""
Mod Parity Scan  ->  log
========================

Scans every item you have (inventory / equipped / storage) and, per item, writes:
  - GAME: the game's own decoded name + info-string (the authoritative tooltip lines), and
  - OURS: what the new Item.Mods engine decodes for the same item — every modifier's name,
    subtype and value(s), plus the applied upgrades (name + slot + maxed).

Put side by side, this lets you assess PARITY: does every game line have a matching mod in
ours, with the right value? Divergences are the implementation bugs to fix.

Run in-game (map loaded). Output: docs/item_mods/catalogs/mod_parity_scan.txt
"""

import traceback

import PyImGui
import PyItem
import PySystem

from Py4GWCoreLib.Item import Item
from Py4GWCoreLib.ItemArray import ItemArray
from Py4GWCoreLib.native_src.internals import string_table

MODULE_NAME = "Mod Parity Scan"
OUT = r"C:\Users\Apo\Py4GW_Reforged\docs\item_mods\catalogs\mod_parity_scan.txt"
# inventory bags (1-4) + belt/equip packs (5) + equipped (22) + storage (8-18) + material (6)
SCAN_BAGS = [1, 2, 3, 4, 5, 22, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 6]

STATE_IDLE, STATE_WARMING, STATE_WRITING, STATE_DONE = 0, 1, 2, 3
_WARM_FRAMES = 200

_state = STATE_IDLE
_warm_left = 0
_items: list = []           # [{id, name_enc, info_enc}]
_status = "Idle. Press to scan items and compare game vs. Item.Mods -> log."
_last = ""
initialized = False


def _decode(enc) -> str:
    if not enc:
        return ""
    try:
        return string_table.decode(bytes(enc))
    except Exception:
        return ""


def _reload_core():
    """Widget reload does NOT reload Py4GWCoreLib submodules (they stay in sys.modules), so
    edits to mods_upgrades/mods_core wouldn't be seen. reload() mutates the module in place;
    Item holds the mods_core object and mods_core holds mods_upgrades, so both propagate."""
    import importlib
    from Py4GWCoreLib import mods_core, mods_upgrades
    importlib.reload(mods_upgrades)
    importlib.reload(mods_core)


def _capture():
    items = []
    seen = set()
    bags = ItemArray.CreateBagList(*SCAN_BAGS)
    for iid in ItemArray.GetItemArray(bags):
        if iid in seen:
            continue
        seen.add(iid)
        try:
            py = PyItem.PyItem(iid)
            items.append({
                "id": iid,
                "name_enc": list(py.GetCompleteNameEnc() or []),
                "info_enc": list(py.GetInfoString() or []),
            })
        except Exception:
            continue
    return items


def _warm():
    for it in _items:
        _decode(it["name_enc"])
        _decode(it["info_enc"])


def _ours_lines(item_id) -> list:
    """The game-style description lines our Item.Mods engine renders for the item."""
    try:
        descs = Item.Mods.GetDescriptions(item_id)
    except Exception as e:
        return ["    (error: %s)" % e]
    if not descs:
        return ["    (no mods)"]
    return ["    %s" % d for d in descs]


def _write():
    global _last
    import re
    lines = []
    lines.append("MOD PARITY SCAN  (GAME enc-strings vs. Item.Mods decode)")
    lines.append("=" * 78)
    lines.append("items scanned: %d" % len(_items))
    lines.append("")
    for it in _items:
        name = re.sub(r"<[^>]+>", "", _decode(it["name_enc"])).strip()
        info = _decode(it["info_enc"])
        info_lines = [re.sub(r"<[^>]+>", "", l).strip() for l in info.split("\n") if l.strip()]
        lines.append("-" * 78)
        lines.append("ITEM %d  %r" % (it["id"], name))
        lines.append("  GAME:")
        if info_lines:
            for l in info_lines:
                lines.append("    %s" % l)
        else:
            lines.append("    (no info-string)")
        lines.append("  OURS (Item.Mods):")
        lines.extend(_ours_lines(it["id"]))
        try:
            raw = Item.Mods.GetRawDump(it["id"])
        except Exception as e:
            raw = ["(raw error: %s)" % e]
        if raw:
            lines.append("  RAW mods (id / args / upgrade_id / status):")
            for r in raw:
                lines.append("    %s" % r)
    text = "\n".join(lines)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(text)
    _last = OUT
    try:
        PySystem.Console.Log(MODULE_NAME, "parity -> %s (%d items)" % (OUT, len(_items)),
                             PySystem.Console.MessageType.Success)
    except Exception:
        pass


def draw_widget():
    global _state, _warm_left, _items, _status
    try:
        if PyImGui.begin(MODULE_NAME):
            PyImGui.text("Scans your items: game tooltip vs. Item.Mods decode -> parity log.")
            PyImGui.separator()
            if _state in (STATE_IDLE, STATE_DONE):
                if PyImGui.button("Scan items -> parity log"):
                    try:
                        _reload_core()
                        _items = _capture()
                        if _items:
                            _state = STATE_WARMING
                            _warm_left = _WARM_FRAMES
                            _status = "Captured %d items. Warming string decode..." % len(_items)
                        else:
                            _status = "No items found (in-game with items?)."
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
        _warm()
        _warm_left -= 1
        _status = "Warming string decode... %d frames left." % _warm_left
        if _warm_left <= 0:
            _state = STATE_WRITING
    elif _state == STATE_WRITING:
        try:
            _write()
            _status = "Done. See mod_parity_scan.txt."
        except Exception as e:
            _status = "Write failed: %s" % e
            try:
                PySystem.Console.Log(MODULE_NAME, traceback.format_exc(), PySystem.Console.MessageType.Error)
            except Exception:
                pass
        _state = STATE_DONE


def draw():
    if initialized:
        draw_widget()


def main():
    global initialized
    initialized = True


if __name__ == "__main__":
    main()
