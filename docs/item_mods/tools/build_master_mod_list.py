"""
build_master_mod_list.py — merge the game-sourced mod table with the hand-crafted id list
into one authoritative master mod list, clearly marking the source of each entry.

  - GAME-VERIFIED: upgrade_id present in the game's 390 PvP unlock table (game_mod_table.py) —
    we have its real codes and the game composed its name. High trust.
  - HAND: upgrade_id only in the hand-crafted ItemUpgradeId enum (item_mods_src/types.py) —
    a PvE-only / non-PvP-unlockable mod we can't enumerate from the game. Trusted because the
    game *validated* the overlapping ids, but not independently confirmed.

Output: docs/item_mods/catalogs/mod_master_list.csv
Run:    python docs/item_mods/tools/build_master_mod_list.py
"""
import csv
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
OUT = os.path.join(HERE, "..", "catalogs", "mod_master_list.csv")


def _game_ids():
    ns = {}
    exec(open(os.path.join(HERE, "game_mod_table.py"), encoding="utf-8").read(), ns)
    out = {}
    for u in ns.get("MOD_UNLOCKS", []) or []:
        uid = u.get("upgrade_id")
        if uid:
            out.setdefault(uid, u.get("codes", []))
    return out


def _hand_ids():
    """{upgrade_id: enum_name} from item_mods_src/types.py ItemUpgradeId."""
    path = os.path.join(ROOT, "Py4GWCoreLib", "item_mods_src", "types.py")
    out = {}
    inblock = False
    for line in open(path, encoding="utf-8"):
        if "class ItemUpgradeId" in line:
            inblock = True
            continue
        if inblock:
            m = re.match(r"\s+([A-Za-z0-9_]+)\s*=\s*(0x[0-9A-Fa-f]+|-?\d+)", line)
            if m:
                try:
                    v = int(m.group(2), 0)
                except ValueError:
                    continue
                if v > 0:
                    out.setdefault(v, m.group(1))
            elif re.match(r"^class ", line):
                break
    return out


def main():
    game = _game_ids()
    hand = _hand_ids()

    # hand ids that are NOT standalone mods: rune-attribute descriptors + "applies to" ids.
    # (Runes appear on items as base-rune-id + AttributeRune arg, never as these ids.)
    def classify(uid, name, in_game):
        if in_game:
            return "GAME-VERIFIED"
        if name.startswith("AppliesTo"):
            return "descriptor"       # rune "applies to" id — not a standalone mod
        if name.startswith(("OfSlaying_", "OfTheProfession_", "OfAttribute_")) or \
           name in ("ShowMeTheMoney", "MeasureForMeasure"):
            return "HAND-PVE"         # genuine PvE-only mod the PvP table lacks
        # OfMinor/Major/Superior<Attribute> = rune-attribute descriptor
        if name.startswith(("OfMinor", "OfMajor", "OfSuperior")):
            return "descriptor"
        return "HAND-PVE"

    all_ids = sorted(set(game) | set(hand))
    rows = []
    for uid in all_ids:
        in_game = uid in game
        name = hand.get(uid, "")
        codes = " ".join("0x%08X" % c for c in game.get(uid, [])) if in_game else ""
        rows.append(["0x%X" % uid, name, classify(uid, name, in_game), codes])

    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["upgrade_id", "name", "source", "codes"])
        w.writerows(rows)

    from collections import Counter
    c = Counter(r[2] for r in rows)
    print("wrote %s" % os.path.abspath(OUT))
    print("  total rows: %d" % len(rows))
    print("  GAME-VERIFIED (real, game-sourced): %d" % c["GAME-VERIFIED"])
    print("  HAND-PVE (real PvE mods, hand-sourced gap): %d" % c["HAND-PVE"])
    print("  descriptor (rune-attribute ids, NOT standalone mods): %d" % c["descriptor"])
    print("  -> real mod count = GAME-VERIFIED + HAND-PVE = %d" % (c["GAME-VERIFIED"] + c["HAND-PVE"]))


if __name__ == "__main__":
    main()
