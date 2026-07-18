"""
Resolve Mod Tables
==================

Resolves the RE-dumped game tables (which hold raw ETextStr string-table IDs) to
their in-game text via the native string_table decoder. Two sources:

  - docs/item_mods/tools/game_mod_tables.py   -> the *_TEXT_IDS label tables
  - docs/item_mods/tools/game_mod_table.py    -> MOD_UNLOCKS (the 390-entry mod table)

For the mod table it resolves each unlock's name_id + desc_id, so we get the game's
own name/description for every mod alongside its upgrade_id and raw mod codes.

An ETextStr id N is decoded by building its codepoint reference (base-0x7F00, key 0)
and feeding it to string_table.decode(). Decoding is async, so a press captures +
warms the cache for a few seconds, then writes.

Outputs (next to the source files):
  - game_mod_tables_resolved.txt   (label tables)
  - game_mod_table_named.txt       (the 390 mods, named)
"""

import os
import traceback

import PyImGui
import PySystem

from Py4GWCoreLib.native_src.internals import string_table
from Py4GWCoreLib.native_src.internals.encoded_strings import GWEncoded

MODULE_NAME = "Resolve Mod Tables"

LABELS_PATH = r"C:\Users\Apo\Py4GW_Reforged\docs\item_mods\tools\game_mod_tables.py"
MODTABLE_PATH = r"C:\Users\Apo\Py4GW_Reforged\docs\item_mods\tools\game_mod_table.py"
OUT_LABELS = r"C:\Users\Apo\Py4GW_Reforged\docs\item_mods\tools\game_mod_tables_resolved.txt"
OUT_NAMED = r"C:\Users\Apo\Py4GW_Reforged\docs\item_mods\tools\game_mod_table_named.txt"

STATE_IDLE, STATE_WARMING, STATE_WRITING, STATE_DONE = 0, 1, 2, 3
_WARM_FRAMES = 250

_state = STATE_IDLE
_warm_left = 0
_label_tables = {}     # name -> {index: text_id}
_mod_unlocks = []      # list of unlock dicts
_all_ids = []          # every text_id to warm
_status = "Idle. Press to resolve the dumped tables + mod table."
_last_path = ""

initialized = False


def _encode_ref(text_id):
    if not text_id:
        return b""
    return bytes(GWEncoded._encode_string_table_number(int(text_id))) + b"\x00\x00"


def _resolve(text_id):
    enc = _encode_ref(text_id)
    if not enc:
        return ""
    try:
        return string_table.decode(enc)
    except Exception:
        return ""


def _load_all():
    label_tables, mod_unlocks = {}, []
    ids = set()

    # Label tables
    try:
        ns = {}
        with open(LABELS_PATH, "r", encoding="utf-8") as f:
            exec(f.read(), ns)
        for key, val in ns.items():
            if key.endswith("_TEXT_IDS") and isinstance(val, dict):
                label_tables[key] = val
                for tid in val.values():
                    if isinstance(tid, int) and tid:
                        ids.add(tid)
    except Exception:
        pass

    # Mod table
    try:
        ns2 = {}
        with open(MODTABLE_PATH, "r", encoding="utf-8") as f:
            exec(f.read(), ns2)
        mod_unlocks = ns2.get("MOD_UNLOCKS", []) or []
        for u in mod_unlocks:
            for k in ("name_id", "desc_id"):
                tid = u.get(k)
                if isinstance(tid, int) and tid:
                    ids.add(tid)
    except Exception:
        pass

    return label_tables, mod_unlocks, sorted(ids)


def _clean(text):
    return text.replace("\n", " \\n ").strip() if text else ""


def _write_labels():
    lines = ["RESOLVED LABEL TABLES (ETextStr id -> in-game text)", "=" * 70, ""]
    pending = 0
    for name in sorted(_label_tables.keys()):
        table = _label_tables[name]
        lines.append(name.replace("_TEXT_IDS", ""))
        lines.append("-" * 70)
        for idx in sorted(table.keys()):
            tid = table[idx]
            text = _resolve(tid) if tid else ""
            if tid and not text:
                pending += 1
                text = "<pending>"
            lines.append("  %3d : 0x%-6X  %s" % (idx, tid, _clean(text)))
        lines.append("")
    with open(OUT_LABELS, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return pending


def _write_named():
    lines = ["GAME MOD TABLE — resolved names (from the client string table)",
             "Source: game_mod_table.py (ConstItemPvp unlock defs @ 0x001b5990)",
             "=" * 90,
             "%-4s %-9s %-34s %-40s %s" % ("idx", "upg_id", "name", "description", "codes"),
             "-" * 90]
    pending = 0
    for u in _mod_unlocks:
        name = _resolve(u.get("name_id", 0))
        desc = _resolve(u.get("desc_id", 0))
        if u.get("name_id") and not name:
            pending += 1
            name = "<pending>"
        codes = ", ".join("0x%08X" % c for c in u.get("codes", []))
        lines.append("%-4d 0x%-7X %-34s %-40s [%s]" % (
            u.get("i", 0), u.get("upgrade_id", 0),
            _clean(name)[:34], _clean(desc)[:40], codes))
    with open(OUT_NAMED, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return pending


def _write_all():
    global _last_path
    p1 = _write_labels()
    p2 = _write_named()
    _last_path = OUT_NAMED
    try:
        PySystem.Console.Log(MODULE_NAME, "wrote resolved tables (%d+%d pending)" % (p1, p2),
                             PySystem.Console.MessageType.Success)
    except Exception:
        pass


def draw_widget():
    global _state, _warm_left, _label_tables, _mod_unlocks, _all_ids, _status
    try:
        if PyImGui.begin(MODULE_NAME):
            PyImGui.text("Resolves label tables + the 390-entry mod table")
            PyImGui.text("(ETextStr ids) -> in-game text.")
            PyImGui.separator()
            if _state in (STATE_IDLE, STATE_DONE):
                if PyImGui.button("Resolve tables + mod table -> text"):
                    try:
                        _label_tables, _mod_unlocks, _all_ids = _load_all()
                        if _all_ids:
                            _state = STATE_WARMING
                            _warm_left = _WARM_FRAMES
                            _status = "Loaded %d labels + %d mods (%d ids). Warming..." % (
                                len(_label_tables), len(_mod_unlocks), len(_all_ids))
                        else:
                            _status = "No ids found (are the dump files present?)."
                    except Exception as e:
                        _status = "Load failed: %s" % e
            else:
                PyImGui.text("Working...")
            PyImGui.separator()
            PyImGui.text(_status)
            if _last_path:
                PyImGui.text("Output:")
                PyImGui.text_wrapped(_last_path)
        PyImGui.end()
    except Exception:
        try:
            PySystem.Console.Log(MODULE_NAME, traceback.format_exc(), PySystem.Console.MessageType.Error)
        except Exception:
            pass

    if _state == STATE_WARMING:
        for tid in _all_ids:
            _resolve(tid)
        _warm_left -= 1
        _status = "Warming decoder... %d frames left." % _warm_left
        if _warm_left <= 0:
            _state = STATE_WRITING
    elif _state == STATE_WRITING:
        try:
            _write_all()
            _status = "Done. Wrote resolved label tables + named mod table."
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
    if initialized:
        return
    initialized = True


if __name__ == "__main__":
    main()
