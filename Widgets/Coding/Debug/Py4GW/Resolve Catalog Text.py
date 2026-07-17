"""
Resolve Catalog Text
===================

In-client pass that resolves every ETextStr id used by the item catalogs
(docs/item_mods/catalogs/raw_item_catalogs.json) to its game text, and writes a flat
map catalogs/textid_resolved.json = {"0x<id>": "text"}. The offline formatter
(format_catalogs.py) joins this to add a readable "text" column to the text-id catalogs
(colors / attributes / descriptions / elements-name).

Text ids collected: the single field of every 'textid' catalog, plus field 0 (name_id)
of the 'elements' and 'pvp_*' catalogs. Decoding is async, so a press captures + warms
the string-table cache for a few seconds, then writes.
"""

import os
import traceback

import PyImGui
import PySystem

from Py4GWCoreLib.native_src.internals import string_table
from Py4GWCoreLib.native_src.internals.encoded_strings import GWEncoded

MODULE_NAME = "Resolve Catalog Text"
RAW_PATH = r"C:\Users\Apo\Py4GW_Reforged\docs\item_mods\catalogs\raw_item_catalogs.json"
OUT_PATH = r"C:\Users\Apo\Py4GW_Reforged\docs\item_mods\catalogs\textid_resolved.json"

STATE_IDLE, STATE_WARMING, STATE_WRITING, STATE_DONE = 0, 1, 2, 3
_WARM_FRAMES = 300

_state = STATE_IDLE
_warm_left = 0
_ids = []
_status = "Idle. Press to resolve all catalog text ids."
_last_path = ""
initialized = False

# catalogs whose first field is a text id (name), for id collection
NAME_FIELD0 = ("elements", "pvp_items", "pvp_unlocks")


def _resolve(text_id):
    if not text_id:
        return ""
    try:
        return string_table.decode(bytes(GWEncoded._encode_string_table_number(int(text_id))) + b"\x00\x00")
    except Exception:
        return ""


def _collect_ids():
    import json
    with open(RAW_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    ids = set()
    for name, cat in data.items():
        if name == "_meta":
            continue
        if cat.get("kind") == "textid":
            for row in cat["entries"].values():
                v = int(row[0], 16)
                if v:
                    ids.add(v)
        elif name in NAME_FIELD0:
            for row in cat["entries"].values():
                v = int(row[1], 16) if name.startswith("pvp") else int(row[0], 16)
                if v:
                    ids.add(v)
    return sorted(ids)


def _write():
    global _last_path
    parts = []
    pending = 0
    for tid in _ids:
        t = _resolve(tid)
        if not t:
            pending += 1
        parts.append('  "0x%X": %s' % (tid, _json_str(t)))
    data = "{\n" + ",\n".join(parts) + "\n}\n"
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(data)
    _last_path = OUT_PATH
    try:
        PySystem.Console.Log(MODULE_NAME, "wrote %s (%d ids, %d pending)" % (OUT_PATH, len(_ids), pending),
                             PySystem.Console.MessageType.Success)
    except Exception:
        pass


def _json_str(s):
    s = (s or "").replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t")
    return '"%s"' % s


def draw_widget():
    global _state, _warm_left, _ids, _status
    try:
        if PyImGui.begin(MODULE_NAME):
            PyImGui.text("Resolves every ETextStr id in the item catalogs -> text.")
            PyImGui.separator()
            if _state in (STATE_IDLE, STATE_DONE):
                if PyImGui.button("Resolve catalog text ids"):
                    try:
                        _ids = _collect_ids()
                        if _ids:
                            _state = STATE_WARMING
                            _warm_left = _WARM_FRAMES
                            _status = "Collected %d unique ids. Warming..." % len(_ids)
                        else:
                            _status = "No ids (is raw_item_catalogs.json present?)."
                    except Exception as e:
                        _status = "Load failed: %s" % e
            else:
                PyImGui.text("Working...")
            PyImGui.separator()
            PyImGui.text(_status)
            if _last_path:
                PyImGui.text_wrapped(_last_path)
        PyImGui.end()
    except Exception:
        try:
            PySystem.Console.Log(MODULE_NAME, traceback.format_exc(), PySystem.Console.MessageType.Error)
        except Exception:
            pass

    if _state == STATE_WARMING:
        for tid in _ids:
            _resolve(tid)
        _warm_left -= 1
        _status = "Warming... %d frames left." % _warm_left
        if _warm_left <= 0:
            _state = STATE_WRITING
    elif _state == STATE_WRITING:
        try:
            _write()
            _status = "Done. Wrote textid_resolved.json."
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
