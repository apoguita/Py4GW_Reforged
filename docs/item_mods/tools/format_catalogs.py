"""
format_catalogs.py — turn the raw Ghidra dump (raw_item_catalogs.json) into clean per-catalog
CSVs. Offline (no game). Text-id catalogs keep the ETextStr id column (resolved to words in-client
by the resolver widget). Struct catalogs get named columns where the layout is known, raw hex
fields otherwise.

Run:  python docs/item_mods/tools/format_catalogs.py
"""
import csv
import json
import os
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
CATDIR = os.path.join(HERE, "..", "catalogs")
RAW = os.path.join(CATDIR, "raw_item_catalogs.json")

# Known struct field names (by index) for the catalogs we've reverse-engineered.
STRUCT_FIELDS = {
    "pvp_unlocks": ["model_id", "name_id", "f08", "f0c", "type_mask", "f14", "f18",
                    "f1c", "code_count", "codes_ptr"],
    "pvp_items":   ["model_id", "name_id", "f08", "f0c", "f10", "f14", "f18_mask",
                    "codes_ptr", "f20"],
    "elements":    ["name_id", "f04", "f08"],   # material/component; name_id is an ETextStr id
    # books: struct layout not yet reversed -> raw field columns.
    # formulas: emitted from formulas_recipes.json (crafting recipes) below.
}


def _f32(hexstr):
    return struct.unpack("<f", struct.pack("<I", int(hexstr, 16)))[0]


def _write_formulas(catdir):
    """Crafting recipes: price (float f00) + ingredients [(element_id, qty)]."""
    path = os.path.join(catdir, "formulas_recipes.json")
    if not os.path.exists(path):
        return False
    recipes = json.load(open(path, encoding="utf-8"))["formulas"]
    with open(os.path.join(catdir, "formulas.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["index", "price", "ingredient_count", "ingredients(element:qty)"])
        for i in sorted(recipes, key=int):
            r = recipes[i]
            ing = "; ".join("%d:%d" % (e, q) for e, q in r["ingredients"])
            w.writerow([i, _f32(r["f00"]), r["count"], ing])
    return True

TEXTID_KIND = "textid"


def _load_mod_names():
    """idx -> (name, description) from the already-generated game_mod_table_named.txt
    (fixed-width columns written by the Dump Named Mod Table widget)."""
    path = os.path.join(HERE, "game_mod_table_named.txt")
    out = {}
    if not os.path.exists(path):
        return out
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line[:4].strip().isdigit():
                continue
            idx = int(line[0:4].strip())
            name = line[15:51].strip()
            desc = line[52:96].strip()
            out[idx] = (name, desc)
    return out


def _load_mod_codes():
    """Pull the already-resolved mod codes/upgrade_id from game_mod_table.py (which
    followed the codes_ptr), keyed by unlock index."""
    path = os.path.join(HERE, "game_mod_table.py")
    if not os.path.exists(path):
        return {}
    ns = {}
    with open(path, "r", encoding="utf-8") as f:
        exec(f.read(), ns)
    out = {}
    for u in ns.get("MOD_UNLOCKS", []) or []:
        out[u.get("i")] = u
    return out


def main():
    with open(RAW, "r", encoding="utf-8") as f:
        data = json.load(f)

    mod_codes = _load_mod_codes()
    catdir = os.path.abspath(CATDIR)
    tpath = os.path.join(catdir, "textid_resolved.json")
    text_map = json.load(open(tpath, encoding="utf-8")) if os.path.exists(tpath) else {}

    def txt(hexid):
        return text_map.get(hexid, "") if text_map else ""

    formulas_ok = _write_formulas(catdir)
    summary = []
    for name, cat in data.items():
        if name == "_meta":
            continue
        if name == "formulas":
            summary.append((name, "recipes" if formulas_ok else "raw", cat["count"], "formulas.csv"))
            continue
        kind = cat["kind"]
        entries = cat["entries"]
        out_path = os.path.join(CATDIR, name + ".csv")
        with open(out_path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            if kind == TEXTID_KIND:
                w.writerow(["index", "text_id", "text"])
                for i in sorted(entries, key=int):
                    tid = entries[i][0]
                    w.writerow([i, tid, txt(tid)])
            elif name == "pvp_unlocks":
                # Self-contained mods CSV: real codes + upgrade_id merged in from game_mod_table.py.
                w.writerow(["index", "upgrade_id", "model_id", "name_id", "type_mask", "code_count", "codes"])
                for i in sorted(entries, key=int):
                    row = entries[i]
                    m = mod_codes.get(int(i), {})
                    codes = " ".join("0x%08X" % c for c in m.get("codes", []))
                    w.writerow([i, "0x%X" % m.get("upgrade_id", 0), row[0], row[1], row[4], row[8], codes])
            else:
                fields = cat["fields"]
                names = STRUCT_FIELDS.get(name, ["f%02x" % (n * 4) for n in range(fields)])
                w.writerow(["index"] + names)
                for i in sorted(entries, key=int):
                    row = entries[i]
                    w.writerow([i] + row)
        summary.append((name, kind, cat["count"], os.path.basename(out_path)))

    print("Formatted catalogs -> %s" % CATDIR)
    for name, kind, count, fn in summary:
        print("  %-14s %-8s %5d rows -> %s" % (name, kind, count, fn))


if __name__ == "__main__":
    main()
