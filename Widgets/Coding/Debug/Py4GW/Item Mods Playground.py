"""
Item Mods Playground
====================

A hands-on tester for the Item.Mods / Item.Properties / Item.Dye API. Hover any item in your
inventory (it latches onto the last one you hovered) and this widget shows:

  * INSPECT  — the game's own name + stats + tooltip (decoded from the item's encoded strings),
               side by side with what Item.Mods.GetDescriptions() produces for the same item.
  * FILTER   — build the kind of filter a player actually wants ("max req 9 sword, Sundering
               prefix, of Fortitude suffix") from item type + requirement + damage + the named
               prefixes / suffixes / runes / insignias / inscriptions, and see PASS/FAIL live.
  * HELPERS  — exercise HasMod / HasAllMods / HasAnyMods against the latched item so you can see
               exactly how the matching (exact-or-better) behaves.

Named upgrade lists come straight from the mod engine (mods_upgrades.UPGRADE_SLOT), so they stay
in sync with what Item.Mods can decode. See the wiki for what each name does:
  https://wiki.guildwars.com/wiki/List_of_weapon_upgrades   (prefixes / suffixes)
  https://wiki.guildwars.com/wiki/Rune                      (armor runes)
  https://wiki.guildwars.com/wiki/Insignia                  (armor insignias)

Run in-game with items to hover.
"""

import re
import traceback

import PyImGui
import PyItem
import PySystem

from Py4GWCoreLib import mods_core
from Py4GWCoreLib import mods_upgrades
from Py4GWCoreLib.Item import Item
from Py4GWCoreLib.Inventory import Inventory
from Py4GWCoreLib.enums_src.Item_enums import ItemType
from Py4GWCoreLib.native_src.internals import string_table

MODULE_NAME = "Item Mods Playground"

GREEN = (0.45, 1.00, 0.45, 1.0)
RED = (1.00, 0.50, 0.50, 1.0)
GREY = (0.70, 0.70, 0.70, 1.0)
GOLD = (1.00, 0.85, 0.40, 1.0)
CYAN = (0.55, 0.85, 1.00, 1.0)

_TAG = re.compile(r"<[^>]+>")


# ── user-facing name lists (built once from the engine's slot table) ─────────────
def _pretty(internal: str) -> str:
    s = mods_core._pretty(internal)
    s = s.replace(" Of ", " of ").replace(" The ", " the ").replace(" And ", " and ")
    if s.startswith("Of "):
        s = "of " + s[3:]
    return s


def _build_lists():
    prefixes, suffixes, runes, insignias, inscriptions = [], [], [], [], []
    for name, slot in mods_upgrades.UPGRADE_SLOT.items():
        entry = (_pretty(name), name)
        if slot == int(mods_core.Slot.Prefix):
            (insignias if "Insignia" in name else prefixes).append(entry)
        elif slot == int(mods_core.Slot.Suffix):
            (runes if "Rune" in name else suffixes).append(entry)
        elif slot == int(mods_core.Slot.Inscription):
            inscriptions.append(entry)
    for lst in (prefixes, suffixes, runes, insignias, inscriptions):
        lst.sort(key=lambda e: e[0].lower())
    return prefixes, suffixes, runes, insignias, inscriptions


PREFIXES, SUFFIXES, RUNES, INSIGNIAS, INSCRIPTIONS = _build_lists()
ITEM_TYPES = sorted(
    ((t.name.replace("_", " "), t) for t in ItemType if t.is_weapon_type() or t.is_armor_type()),
    key=lambda e: e[0].lower(),
)


# ── widget state ─────────────────────────────────────────────────────────────────
_latched_id = 0
_show_ours = True

# filter selections (index 0 in every combo = "(any)")
_f_type = 0
_f_req_on = False
_f_req_max = 9
_f_maxdmg = False
_f_prefix = 0
_f_suffix = 0
_f_rune = 0
_f_insignia = 0
_f_inscription = 0
_f_mode_all = True   # True = ALL (AND), False = ANY (OR)

# helper-tester selection
_h_mod = 0
_h_thresh = 0

initialized = False


def _dec(enc) -> str:
    if not enc:
        return ""
    try:
        return string_table.decode(bytes(enc))
    except Exception:
        return ""


def _combo(label: str, current: int, entries, any_label: str = "(any)") -> int:
    items = [any_label] + [e[0] for e in entries]
    return PyImGui.combo(label, current, items)


def _selected_internal(current: int, entries):
    """The internal upgrade name for a combo selection, or None for '(any)'."""
    if current <= 0 or current - 1 >= len(entries):
        return None
    return entries[current - 1][1]


def _verdict(label: str, ok: bool):
    PyImGui.text_colored(GREEN if ok else RED, ("PASS  " if ok else "FAIL  ") + label)


# ── section 1: inspect the latched item ──────────────────────────────────────────
def _draw_inspect(item_id: int):
    global _show_ours
    try:
        name = _TAG.sub("", _dec(PyItem.PyItem(item_id).GetCompleteNameEnc())).strip()
        type_name = Item.GetItemType(item_id)[1]
    except Exception:
        name, type_name = "", "?"
    PyImGui.text_colored(GOLD, name or "(name decoding...)")
    PyImGui.text_colored(GREY, "type: %s   id: %d" % (type_name, item_id))
    PyImGui.separator()

    # key stats a player cares about
    try:
        attr, req = Item.Properties.GetRequirement(item_id)
        if req:
            PyImGui.text("Requirement: %d %s" % (req, getattr(attr, "name", str(attr))))
        dmin, dmax = Item.Properties.GetDamage(item_id)
        if dmax:
            maxed = Item.Properties.IsMaxDamage(item_id)
            PyImGui.text("Damage: %d-%d" % (dmin, dmax))
            PyImGui.same_line()
            PyImGui.text_colored(GREEN if maxed else GREY, "(max)" if maxed else "(not max)")
        armor = Item.Properties.GetArmor(item_id)
        if armor:
            PyImGui.text("Armor: %d" % armor)
        energy = Item.Properties.GetEnergy(item_id)
        if energy:
            PyImGui.text("Energy: +%d" % energy)
    except Exception:
        PyImGui.text_colored(RED, "stat read error")

    # applied upgrades (prefix / suffix / rune / insignia / inscription)
    try:
        upgrades = Item.Mods.GetUpgrades(item_id)
    except Exception:
        upgrades = []
    if upgrades:
        PyImGui.separator()
        PyImGui.text_colored(CYAN, "Upgrades:")
        for uname, slot in upgrades:
            maxed = ""
            try:
                if Item.Mods.IsMaxed(item_id, uname):
                    maxed = "  (max)"
            except Exception:
                pass
            PyImGui.bullet_text("%s: %s%s" % (slot.name, _pretty(uname), maxed))

    # GAME (from encoded info-string) vs OURS (Item.Mods)
    PyImGui.separator()
    _show_ours = PyImGui.checkbox("show OURS (Item.Mods) alongside GAME", _show_ours)
    try:
        info = _dec(PyItem.PyItem(item_id).GetInfoString())
        game_lines = [_TAG.sub("", l).strip() for l in info.split("\n") if l.strip()]
    except Exception:
        game_lines = []
    PyImGui.text_colored(GOLD, "GAME (tooltip):")
    if game_lines:
        for l in game_lines:
            PyImGui.text("  " + l)
    else:
        PyImGui.text_colored(GREY, "  (decoding... hover a moment)")
    if _show_ours:
        PyImGui.text_colored(CYAN, "OURS (Item.Mods.GetDescriptions):")
        try:
            ours = Item.Mods.GetDescriptions(item_id)
        except Exception as e:
            ours = ["(error: %s)" % e]
        if ours:
            for l in ours:
                PyImGui.text("  " + l)
        else:
            PyImGui.text_colored(GREY, "  (no mods)")


# ── section 2: build a player-style filter and test it ───────────────────────────
def _draw_filter(item_id: int):
    global _f_type, _f_req_on, _f_req_max, _f_maxdmg
    global _f_prefix, _f_suffix, _f_rune, _f_insignia, _f_inscription, _f_mode_all

    _f_type = _combo("Item type", _f_type, ITEM_TYPES)
    _f_req_on = PyImGui.checkbox("Requirement at most", _f_req_on)
    if _f_req_on:
        PyImGui.same_line()
        PyImGui.push_item_width(120)
        _f_req_max = PyImGui.slider_int("req", _f_req_max, 0, 13)
        PyImGui.pop_item_width()
    _f_maxdmg = PyImGui.checkbox("Require max damage (for its req)", _f_maxdmg)
    _f_prefix = _combo("Prefix", _f_prefix, PREFIXES)
    _f_suffix = _combo("Suffix", _f_suffix, SUFFIXES)
    _f_rune = _combo("Rune", _f_rune, RUNES)
    _f_insignia = _combo("Insignia", _f_insignia, INSIGNIAS)
    _f_inscription = _combo("Inscription", _f_inscription, INSCRIPTIONS)

    PyImGui.separator()
    mode = 0 if _f_mode_all else 1
    mode = PyImGui.radio_button("Match ALL (AND)", mode, 0)
    PyImGui.same_line()
    mode = PyImGui.radio_button("Match ANY (OR)", mode, 1)
    _f_mode_all = (mode == 0)

    # build the enabled criteria and evaluate each against the latched item
    try:
        upg_names = {n for n, _ in Item.Mods.GetUpgrades(item_id)}
    except Exception:
        upg_names = set()
    results = []   # (label, passed)

    if _f_type > 0:
        want = ITEM_TYPES[_f_type - 1][1]
        try:
            got = Item.GetItemType(item_id)[0]
        except Exception:
            got = -1
        results.append(("type is %s" % want.name.replace("_", " "), got == int(want)))
    if _f_req_on:
        try:
            _, req = Item.Properties.GetRequirement(item_id)
        except Exception:
            req = 0
        results.append(("requirement %d <= %d" % (req, _f_req_max), 0 < req <= _f_req_max))
    if _f_maxdmg:
        try:
            ok = Item.Properties.IsMaxDamage(item_id)
        except Exception:
            ok = False
        results.append(("max damage", ok))
    for label, sel, entries in (
        ("prefix", _f_prefix, PREFIXES),
        ("suffix", _f_suffix, SUFFIXES),
        ("rune", _f_rune, RUNES),
        ("insignia", _f_insignia, INSIGNIAS),
        ("inscription", _f_inscription, INSCRIPTIONS),
    ):
        internal = _selected_internal(sel, entries)
        if internal is not None:
            results.append(("%s %s" % (label, _pretty(internal)), internal in upg_names))

    PyImGui.separator()
    if not results:
        PyImGui.text_colored(GREY, "Pick at least one criterion above.")
        return
    passed = [ok for _, ok in results]
    overall = all(passed) if _f_mode_all else any(passed)
    PyImGui.text_colored(GREEN if overall else RED,
                         "ITEM MATCHES" if overall else "ITEM DOES NOT MATCH")
    PyImGui.text_colored(GREY, "(%s of %d criteria)" %
                         ("all" if _f_mode_all else "any", len(results)))
    for label, ok in results:
        _verdict(label, ok)


# ── section 3: exercise the HasMod / HasAllMods / HasAnyMods helpers ──────────────
def _draw_helpers(item_id: int):
    global _h_mod, _h_thresh
    try:
        mods = Item.Mods.GetMods(item_id)
    except Exception as e:
        PyImGui.text_colored(RED, "GetMods error: %s" % e)
        return
    if not mods:
        PyImGui.text_colored(GREY, "This item has no decodable effect mods.")
        return

    PyImGui.text_colored(GREY, "The item's effect mods (name / values):")
    names = []
    for m in mods:
        try:
            nm = Item.Mods.GetName(m)
            vals = Item.Mods.GetValues(item_id, m)
        except Exception:
            nm, vals = str(m), []
        names.append(nm)
        PyImGui.bullet_text("%s  ->  %s" % (nm, vals if vals else "(no value)"))

    PyImGui.separator()
    PyImGui.text_colored(CYAN, "Try HasMod(item, mod, threshold):")
    if _h_mod >= len(names):
        _h_mod = 0
    _h_mod = PyImGui.combo("mod", _h_mod, names)
    PyImGui.push_item_width(120)
    _h_thresh = PyImGui.input_int("threshold (0 = any)", _h_thresh)
    PyImGui.pop_item_width()
    chosen = mods[_h_mod]
    try:
        if _h_thresh:
            ok = Item.Mods.HasMod(item_id, chosen, _h_thresh)
            label = "HasMod(%s, %d or better)" % (names[_h_mod], _h_thresh)
        else:
            ok = Item.Mods.HasMod(item_id, chosen)
            label = "HasMod(%s)" % names[_h_mod]
    except Exception as e:
        ok, label = False, "HasMod error: %s" % e
    _verdict(label, ok)

    PyImGui.separator()
    PyImGui.text_colored(CYAN, "Round-trip sanity (against the item's own mods):")
    try:
        all_ok = Item.Mods.HasAllMods(item_id, list(mods))
        any_ok = Item.Mods.HasAnyMods(item_id, [mods[0]])
    except Exception as e:
        all_ok = any_ok = False
        PyImGui.text_colored(RED, "helper error: %s" % e)
    _verdict("HasAllMods(all %d of its mods)" % len(mods), all_ok)
    _verdict("HasAnyMods([%s])" % names[0], any_ok)


# ── frame ─────────────────────────────────────────────────────────────────────────
def draw_widget():
    global _latched_id
    try:
        hovered = Inventory.GetHoveredItemID()
    except Exception:
        hovered = 0
    if hovered:
        _latched_id = hovered

    try:
        if PyImGui.begin(MODULE_NAME):
            if not _latched_id:
                PyImGui.text_colored(GREY, "Hover an item in your inventory to inspect it.")
            else:
                if hovered and hovered == _latched_id:
                    PyImGui.text_colored(GREEN, "hovering")
                else:
                    PyImGui.text_colored(GREY, "latched (last hovered)")
                if PyImGui.collapsing_header("Inspect", int(PyImGui.TreeNodeFlags.DefaultOpen)):
                    _draw_inspect(_latched_id)
                if PyImGui.collapsing_header("Filter test"):
                    _draw_filter(_latched_id)
                if PyImGui.collapsing_header("Helpers (HasMod / HasAll / HasAny)"):
                    _draw_helpers(_latched_id)
        PyImGui.end()
    except Exception:
        try:
            PySystem.Console.Log(MODULE_NAME, traceback.format_exc(), PySystem.Console.MessageType.Error)
        except Exception:
            pass


def draw():
    if initialized:
        draw_widget()


def main():
    global initialized
    initialized = True


if __name__ == "__main__":
    main()
