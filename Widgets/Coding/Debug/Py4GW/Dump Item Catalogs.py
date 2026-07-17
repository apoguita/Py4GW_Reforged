"""
Dump Item Catalogs (in-game)
===========================

ONE in-client script that turns the structural catalog dump (from Ghidra) into the
finished, human-readable catalogs — resolving every ETextStr id to its word via the
game's string table, and composing the 390 mod names via the native binding.

Inputs (produced offline by the Ghidra dumps):
  docs/item_mods/catalogs/raw_item_catalogs.json   (ids / numbers / struct fields)
  docs/item_mods/catalogs/formulas_recipes.json    (crafting recipes)
  docs/item_mods/tools/game_mod_table.py           (mod codes / upgrade_id)

Outputs (final, string-filled CSVs):
  docs/item_mods/catalogs/*.csv   (colors, attributes, descriptions, elements,
                                    formulas, pvp_items, pvp_unlocks, books)

String decoding is async, so a press captures + warms the string-table cache for a few
seconds, then writes. Run this in-game (map loaded) so gw.dat text is available.
"""

import csv
import json
import os
import struct
import traceback

import PyImGui
import PyItem
import PySystem

from Py4GWCoreLib.native_src.internals import string_table
from Py4GWCoreLib.native_src.internals.encoded_strings import GWEncoded

MODULE_NAME = "Dump Item Catalogs"
CATDIR = r"C:\Users\Apo\Py4GW_Reforged\docs\item_mods\catalogs"
TOOLS = r"C:\Users\Apo\Py4GW_Reforged\docs\item_mods\tools"

STATE_IDLE, STATE_WARMING, STATE_WRITING, STATE_DONE = 0, 1, 2, 3
_WARM_FRAMES = 500

_state = STATE_IDLE
_warm_left = 0
_raw = {}
_recipes = {}
_mod_codes = {}
_mod_enc = {}          # idx -> (name_enc bytes, desc_enc bytes)
_text_ids = []         # all ETextStr ids to warm
_status = "Idle. Press to dump the complete item catalogs."
_last = ""
initialized = False

HAS_MOD_BINDING = hasattr(PyItem, "get_pvp_unlock_name_enc")


# ── decode helpers ───────────────────────────────────────────────────────────
def _resolve(text_id):
    if not text_id:
        return ""
    try:
        return string_table.decode(bytes(GWEncoded._encode_string_table_number(int(text_id))) + b"\x00\x00")
    except Exception:
        return ""


def _decode_enc(byte_list):
    if not byte_list:
        return ""
    try:
        return string_table.decode(bytes(byte_list))
    except Exception:
        return ""


def _f32(hexstr):
    return struct.unpack("<f", struct.pack("<I", int(hexstr, 16)))[0]


def _clean(s):
    return (s or "").replace("\n", " / ").strip()


# ── load structural inputs ───────────────────────────────────────────────────
def _load():
    global _raw, _recipes, _mod_codes, _mod_enc, _text_ids
    with open(os.path.join(CATDIR, "raw_item_catalogs.json"), "r", encoding="utf-8") as f:
        _raw = json.load(f)
    rp = os.path.join(CATDIR, "formulas_recipes.json")
    _recipes = json.load(open(rp, encoding="utf-8"))["formulas"] if os.path.exists(rp) else {}
    ns = {}
    mp = os.path.join(TOOLS, "game_mod_table.py")
    if os.path.exists(mp):
        exec(open(mp, encoding="utf-8").read(), ns)
    _mod_codes = {u["i"]: u for u in ns.get("MOD_UNLOCKS", []) or []}

    # collect every text id used by the catalogs
    ids = set()
    for name, cat in _raw.items():
        if name == "_meta":
            continue
        if cat.get("kind") == "textid":
            for row in cat["entries"].values():
                v = int(row[0], 16)
                if v:
                    ids.add(v)
        elif name in ("elements", "pvp_items"):
            # name id is field 0 (elements) / field 1 (pvp_items)
            fi = 1 if name == "pvp_items" else 0
            for row in cat["entries"].values():
                v = int(row[fi], 16)
                if v:
                    ids.add(v)
    _text_ids = sorted(ids)

    # capture mod name/desc encoded bytes from the native binding (sync)
    _mod_enc = {}
    if HAS_MOD_BINDING:
        cnt = PyItem.get_pvp_unlock_count()
        for i in range(cnt):
            try:
                n, d = PyItem.get_pvp_unlock_name_enc(i)
                _mod_enc[i] = (list(n or []), list(d or []))
            except Exception:
                _mod_enc[i] = ([], [])


def _warm():
    for tid in _text_ids:
        _resolve(tid)
    for n, d in _mod_enc.values():
        _decode_enc(n)
        _decode_enc(d)


# ── write final catalogs ─────────────────────────────────────────────────────
def _wcsv(name, header, rows):
    with open(os.path.join(CATDIR, name), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def _write_all():
    global _last
    ent = lambda k: _raw[k]["entries"]

    # text-id catalogs: index, text_id, text
    for name in ("colors", "attributes", "descriptions"):
        rows = [[i, ent(name)[i][0], _clean(_resolve(int(ent(name)[i][0], 16)))]
                for i in sorted(ent(name), key=int)]
        _wcsv(name + ".csv", ["index", "text_id", "text"], rows)

    # elements (materials): index, name_id, material, f04, f08
    elem_name = {}
    erows = []
    for i in sorted(ent("elements"), key=int):
        r = ent("elements")[i]
        nm = _clean(_resolve(int(r[0], 16)))
        elem_name[int(i)] = nm
        erows.append([i, r[0], nm, r[1], r[2]])
    _wcsv("elements.csv", ["index", "name_id", "material", "f04", "f08"], erows)

    # formulas (crafting recipes): index, price, ingredients (material:qty)
    frows = []
    for i in sorted(_recipes, key=int):
        r = _recipes[i]
        ing = "; ".join("%s:%d" % (elem_name.get(e, "elem#%d" % e), q) for e, q in r["ingredients"])
        frows.append([i, _f32(r["f00"]), r["count"], ing])
    _wcsv("formulas.csv", ["index", "price", "ingredient_count", "ingredients"], frows)

    # pvp_items: index, model_id, name_id, name, type_mask
    prows = []
    for i in sorted(ent("pvp_items"), key=int):
        r = ent("pvp_items")[i]
        prows.append([i, r[0], r[1], _clean(_resolve(int(r[1], 16))), r[6]])
    _wcsv("pvp_items.csv", ["index", "model_id", "name_id", "base_name", "type_mask"], prows)

    # pvp_unlocks (mods): index, upgrade_id, name, description, codes
    mrows = []
    for i in sorted(ent("pvp_unlocks"), key=int):
        idx = int(i)
        m = _mod_codes.get(idx, {})
        n, d = _mod_enc.get(idx, ([], []))
        codes = " ".join("0x%08X" % c for c in m.get("codes", []))
        mrows.append([idx, "0x%X" % m.get("upgrade_id", 0),
                      _clean(_decode_enc(n)), _clean(_decode_enc(d)), codes])
    _wcsv("pvp_unlocks.csv", ["index", "upgrade_id", "name", "description", "codes"], mrows)

    _last = CATDIR
    try:
        PySystem.Console.Log(MODULE_NAME, "wrote complete catalogs to " + CATDIR,
                             PySystem.Console.MessageType.Success)
    except Exception:
        pass


def draw_widget():
    global _state, _warm_left, _status
    try:
        if PyImGui.begin(MODULE_NAME):
            PyImGui.text("Resolves all catalog strings in-game + composes mod names,")
            PyImGui.text("then writes the finished CSVs. Run in-game (map loaded).")
            if not HAS_MOD_BINDING:
                PyImGui.text_colored("Mod-name binding missing - rebuild Py4GW.dll for named mods.", (1, 0.6, 0.2, 1))
            PyImGui.separator()
            if _state in (STATE_IDLE, STATE_DONE):
                if PyImGui.button("Dump complete item catalogs"):
                    try:
                        _load()
                        _state = STATE_WARMING
                        _warm_left = _WARM_FRAMES
                        _status = "Loaded (%d text ids, %d mods). Resolving in-game..." % (
                            len(_text_ids), len(_mod_enc))
                    except Exception as e:
                        _status = "Load failed: %s" % e
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
        _status = "Resolving strings... %d frames left." % _warm_left
        if _warm_left <= 0:
            _state = STATE_WRITING
    elif _state == STATE_WRITING:
        try:
            _write_all()
            _status = "Done. Complete catalogs written."
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
