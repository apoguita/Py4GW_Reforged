"""
Dump Named Mod Table
====================

Uses the NEW native binding PyItem.get_pvp_unlock_name_enc(idx) — which runs the game's
own name-composer over each static PvP-unlock (item-mod) definition — to produce the
authoritative, fully-named mod table. Requires a rebuilt Py4GW.dll (the binding is added
in Py4GW_Reforged_Native/src/GW/item). If the binding isn't present yet, this widget says
so and does nothing.

Per unlock index it calls the binding to get the ENCODED (name, description) byte arrays,
decodes them with the native string_table (async → warmed over a few seconds), and cross-
references upgrade_id/codes from the dumped game_mod_table.py.

Output: docs/item_mods/tools/game_mod_table_named.txt
"""

import os
import traceback

import PyImGui
import PyItem
import PySystem

from Py4GWCoreLib.native_src.internals import string_table

MODULE_NAME = "Dump Named Mod Table"
MODTABLE_PATH = r"C:\Users\Apo\Py4GW_Reforged\docs\item_mods\tools\game_mod_table.py"
OUT_PATH = r"C:\Users\Apo\Py4GW_Reforged\docs\item_mods\tools\game_mod_table_named.txt"

HAS_BINDING = hasattr(PyItem, "get_pvp_unlock_name_enc") and hasattr(PyItem, "get_pvp_unlock_count")

STATE_IDLE, STATE_WARMING, STATE_WRITING, STATE_DONE = 0, 1, 2, 3
_WARM_FRAMES = 250

_state = STATE_IDLE
_warm_left = 0
_rows = []          # list of {idx, name_enc, desc_enc}
_meta = {}          # idx -> {upgrade_id, codes} from the dumped table
_status = "Idle." if HAS_BINDING else "Native binding not found — rebuild Py4GW.dll first."
_last_path = ""

initialized = False


def _load_meta():
    meta = {}
    try:
        ns = {}
        with open(MODTABLE_PATH, "r", encoding="utf-8") as f:
            exec(f.read(), ns)
        for u in ns.get("MOD_UNLOCKS", []) or []:
            meta[u.get("i")] = u
    except Exception:
        pass
    return meta


def _capture():
    rows = []
    count = PyItem.get_pvp_unlock_count()
    for idx in range(count):
        try:
            name_enc, desc_enc = PyItem.get_pvp_unlock_name_enc(idx)
        except Exception:
            name_enc, desc_enc = [], []
        rows.append({"idx": idx, "name_enc": list(name_enc or []), "desc_enc": list(desc_enc or [])})
    return rows


def _decode(byte_list):
    if not byte_list:
        return ""
    try:
        return string_table.decode(bytes(byte_list))
    except Exception:
        return ""


def _clean(s):
    return s.replace("\n", " \\n ").strip() if s else ""


def _write():
    global _last_path
    lines = ["GAME MOD TABLE — names composed by the game (native get_pvp_unlock_name_enc)",
             "=" * 96,
             "%-4s %-9s %-36s %-44s %s" % ("idx", "upg_id", "name", "description", "codes"),
             "-" * 96]
    pending = 0
    full = []   # untruncated, tab-delimited: idx \t upgrade_id \t name \t desc
    for r in _rows:
        idx = r["idx"]
        name = _decode(r["name_enc"])
        desc = _decode(r["desc_enc"])
        if r["name_enc"] and not name:
            pending += 1
            name = "<pending>"
        m = _meta.get(idx, {})
        codes = ", ".join("0x%08X" % c for c in m.get("codes", []))
        lines.append("%-4d 0x%-7X %-36s %-44s [%s]" % (
            idx, m.get("upgrade_id", 0), _clean(name)[:36], _clean(desc)[:44], codes))
        full.append("%d\t0x%X\t%s\t%s" % (idx, m.get("upgrade_id", 0), _clean(name), _clean(desc)))
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    with open(OUT_PATH.replace(".txt", "_full.tsv"), "w", encoding="utf-8") as f:
        f.write("\n".join(full))
    _last_path = OUT_PATH
    try:
        PySystem.Console.Log(MODULE_NAME, "wrote %s (%d pending)" % (OUT_PATH, pending),
                             PySystem.Console.MessageType.Success)
    except Exception:
        pass


def draw_widget():
    global _state, _warm_left, _rows, _meta, _status
    try:
        if PyImGui.begin(MODULE_NAME):
            if not HAS_BINDING:
                PyImGui.text("Native binding get_pvp_unlock_name_enc not found.")
                PyImGui.text("Rebuild Py4GW.dll (Py4GW_Reforged_Native), then reload.")
            else:
                PyImGui.text("Names the full 390-entry mod table via the game's composer.")
                PyImGui.separator()
                if _state in (STATE_IDLE, STATE_DONE):
                    if PyImGui.button("Dump named mod table"):
                        _meta = _load_meta()
                        _rows = _capture()
                        if _rows:
                            _state = STATE_WARMING
                            _warm_left = _WARM_FRAMES
                            _status = "Captured %d unlocks. Warming decoder..." % len(_rows)
                        else:
                            _status = "Binding returned nothing (in-game?)."
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
        for r in _rows:
            _decode(r["name_enc"])
            _decode(r["desc_enc"])
        _warm_left -= 1
        _status = "Warming decoder... %d frames left." % _warm_left
        if _warm_left <= 0:
            _state = STATE_WRITING
    elif _state == STATE_WRITING:
        try:
            _write()
            _status = "Done. Wrote named mod table."
        except Exception as e:
            _status = "Write failed: %s" % e
        _state = STATE_DONE


def draw():
    if initialized:
        draw_widget()


def main():
    global initialized
    if initialized:
        return
    initialized = True


if __name__ == "__main__":
    main()
