"""
Agent Recolor section - in-client tester for the native ``PyAgentRecolor`` module.

ONE module now recolors THREE categories via three native detours:
  * Living agents (players/NPCs/enemies) - the GetConsiderColor resolver.
  * Gadgets (signposts/chests/shrines/collectors) - CGadgetAgent::GetTextData.
  * Ground items - CItemAgent::GetTextData, with a rich filter store:
        agent_id > item_id > model_id > name(substring) > item_type > rarity.

Usability points (kept from the agent harness, extended to all three):
  * LIVE status + diagnostics per category inline (hook_installed / enabled / calls / hits).
  * A real COLOR PICKER (color_edit4), shared across categories.
  * Live PICKERS (agents / gadgets / items) so you never guess ids; item picker also shows
    item_id / model_id / rarity / name so you can drive every filter from real data.
  * The refresh note: item/gadget/agent tags only recolor once the game RE-DRAWS the tag
    (move the item into/out of view, or hold Ctrl / "always show names").

Colors are ARGB 0xAARRGGBB. Allegiance ids: 1=Ally 2=Neutral 3=Enemy 4=SpiritPet 5=Minion 6=NpcMinipet.
Item rarity ints: 0=White 1=Blue 2=Purple 3=Gold 4=Green.
"""

import PyImGui

import PyAgentRecolor

from Py4GWCoreLib import Agent
from Py4GWCoreLib import AgentArray
from Py4GWCoreLib.Item import Item

from . import casts
from . import diagnostics
from . import ui

_SECTION = "AgentRecolor"

# Allegiance taxonomy (native binding, 1..6).
_ALLEGIANCE_NAMES = {1: "Ally", 2: "Neutral", 3: "Enemy", 4: "SpiritPet", 5: "Minion", 6: "NpcMinipet"}
_ALLEG_IDS = [1, 2, 3, 4, 5, 6]
_ALLEG_LABELS = [f"{i} {_ALLEGIANCE_NAMES[i]}" for i in _ALLEG_IDS]

# Rarity taxonomy (native item binding, 0..4).
_RARITY_NAMES = {0: "White", 1: "Blue", 2: "Purple", 3: "Gold", 4: "Green"}
_RARITY_IDS = [0, 1, 2, 3, 4]
_RARITY_LABELS = [f"{i} {_RARITY_NAMES[i]}" for i in _RARITY_IDS]

# A few common GW::Constants::ItemType ids, for the item-type quick dropdown.
_ITEM_TYPE_COMMON = [
    (2, "Axe"), (5, "Bag"), (3, "Boots"), (6, "Bow"), (24, "Bundle"), (10, "Chestpiece"),
    (15, "Gloves"), (18, "Hammer"), (11, "Offhand"), (26, "Consumable"), (35, "Costume"),
    (12, "Leggings"), (29, "Material"), (13, "Wand"), (22, "Staff"), (27, "Sword"),
    (2, "Trophy_dup"), (0, "Salvage"), (19, "Headpiece"), (33, "Kit"), (44, "Scroll"),
]

_COLOR_ENEMY = 0xFFFF0000
_COLOR_NPC_MINIPET = 0xFFA0FF00
_COLOR_ALLY = 0xFF00FF00
_PLAYER_FAMILY = (0xFF40FF40, 0xFF6060FF, 0xFF9BBEFF, 0xFFA0A0A0)

_agent_list: "list[tuple[int, str]]" = []
_gadget_list: "list[tuple[int, str]]" = []
_item_list: "list[tuple]" = []  # (agent_id, item_id, model_id, rarity_val, rarity_name, name)
_val_rows: "list[dict]" = []
_val_summary = {"pass": 0, "fail": 0, "unknown": 0}


class _State:
    test_rgba: tuple = (1.0, 0.0, 1.0, 1.0)  # magenta
    # agents
    agent_id: int = 0
    alleg_index: int = 2
    agent_picker_index: int = 0
    # gadgets
    gadget_id: int = 0
    gadget_picker_index: int = 0
    # items
    item_picker_index: int = 0
    rarity_index: int = 3  # Gold
    item_type: int = 2
    item_type_combo: int = 0
    model_id: int = 0
    item_id: int = 0
    item_agent_id: int = 0
    name_substr: str = "ecto"


state = _State()


# --------------------------------------------------------------------------- color helpers
def _rgba_to_argb(rgba) -> int:
    r, g, b, a = rgba
    return ((int(a * 255) & 0xFF) << 24) | ((int(r * 255) & 0xFF) << 16) | ((int(g * 255) & 0xFF) << 8) | (int(b * 255) & 0xFF)


def _test_argb() -> int:
    return _rgba_to_argb(state.test_rgba)


# --------------------------------------------------------------------------- pickers
def _refresh_agent_list() -> None:
    global _agent_list
    ids = casts.safe(AgentArray.GetAgentArray, default=[]) or []
    _agent_list = [(int(a), f"[{a}] {casts.safe(Agent.GetNameByID, a, default='?')}") for a in list(ids)[:120]]


def _refresh_gadget_list() -> None:
    global _gadget_list
    ids = casts.safe(AgentArray.GetGadgetArray, default=[]) or []
    _gadget_list = [(int(a), f"[{a}] {casts.safe(Agent.GetNameByID, a, default='gadget')}") for a in list(ids)[:120]]


def _rarity_of(item_id: int) -> "tuple[int, str]":
    r = casts.safe(Item.Rarity.GetRarity, item_id, default=(0, "?"))
    if isinstance(r, (tuple, list)) and len(r) >= 2:
        return int(r[0]), str(r[1])
    return 0, "?"


def _refresh_item_list() -> None:
    global _item_list
    ids = casts.safe(AgentArray.GetItemArray, default=[]) or []
    out = []
    for aid in list(ids)[:150]:
        item_id = int(casts.safe(Agent.GetItemAgentItemID, aid, default=0) or 0)
        name = casts.safe(Item.Item.GetName, item_id, default="?") if item_id else "?"
        model = int(casts.safe(Item.Item.GetModelID, item_id, default=0) or 0) if item_id else 0
        rar_v, rar_n = _rarity_of(item_id) if item_id else (0, "?")
        out.append((int(aid), item_id, model, rar_v, rar_n, name))
    _item_list = out


# --------------------------------------------------------------------------- validate (agents)
def _expected_color(agent_id: int):
    alleg, alleg_name = casts.safe(Agent.GetAllegiance, agent_id, default=(0, "?")) or (0, "?")
    is_player = bool(casts.safe(Agent.IsPlayer, agent_id))
    if alleg == 3:
        return _COLOR_ENEMY, f"{alleg_name} (enemy)", is_player
    if alleg == 6:
        return _COLOR_NPC_MINIPET, f"{alleg_name} (npc/minipet)", is_player
    if is_player:
        return None, f"{alleg_name} (player: blue/green family)", True
    return _COLOR_ALLY, f"{alleg_name} (ally/friendly)", False


def _verdict(expected, actual, is_player) -> str:
    if actual is None:
        return "UNKNOWN"
    a = actual & 0xFFFFFFFF
    if is_player:
        return "PASS" if a in _PLAYER_FAMILY else "FAIL"
    if expected is None:
        return "UNKNOWN"
    return "PASS" if a == (expected & 0xFFFFFFFF) else "FAIL"


def validate_visible(limit: int = 60) -> None:
    global _val_rows
    seen, agents = set(), []
    for getter in (AgentArray.GetAllyArray, AgentArray.GetNeutralArray, AgentArray.GetEnemyArray):
        for aid in casts.safe(getter, default=[]) or []:
            if aid and aid not in seen:
                seen.add(aid)
                agents.append(aid)
    rows, summ = [], {"pass": 0, "fail": 0, "unknown": 0}
    for aid in agents[:limit]:
        expected, label, is_player = _expected_color(aid)
        actual = casts.safe(PyAgentRecolor.read_consider_color, int(aid))
        actual = int(actual) & 0xFFFFFFFF if actual is not None else None
        v = _verdict(expected, actual, is_player)
        summ[v.lower()] = summ.get(v.lower(), 0) + 1
        rows.append({
            "id": aid, "name": casts.safe(Agent.GetNameByID, aid, default="?"), "class": label,
            "expected": casts.hex_of(expected, 8) if expected is not None else "<player>",
            "actual": casts.hex_of(actual, 8) if actual is not None else "<none>", "verdict": v,
        })
    _val_rows = rows
    _val_summary.update(summ)


# --------------------------------------------------------------------------- Data tab
def _rules_blocks():
    ar = [(a, casts.hex_of(c, 8)) for a, c in (casts.safe(PyAgentRecolor.get_agent_rules, default={}) or {}).items()]
    lr = [(a, _ALLEGIANCE_NAMES.get(a, "?"), casts.hex_of(c, 8)) for a, c in (casts.safe(PyAgentRecolor.get_allegiance_rules, default={}) or {}).items()]
    gr = [(a, casts.hex_of(c, 8)) for a, c in (casts.safe(PyAgentRecolor.get_gadget_rules, default={}) or {}).items()]
    i_ag = [(a, casts.hex_of(c, 8)) for a, c in (casts.safe(PyAgentRecolor.get_item_agent_rules, default={}) or {}).items()]
    i_id = [(a, casts.hex_of(c, 8)) for a, c in (casts.safe(PyAgentRecolor.get_item_id_rules, default={}) or {}).items()]
    i_mo = [(a, casts.hex_of(c, 8)) for a, c in (casts.safe(PyAgentRecolor.get_item_model_rules, default={}) or {}).items()]
    i_ty = [(a, casts.hex_of(c, 8)) for a, c in (casts.safe(PyAgentRecolor.get_item_type_rules, default={}) or {}).items()]
    i_ra = [(a, _RARITY_NAMES.get(a, "?"), casts.hex_of(c, 8)) for a, c in (casts.safe(PyAgentRecolor.get_item_rarity_rules, default={}) or {}).items()]
    i_nm = [(s, casts.hex_of(c, 8)) for s, c in (casts.safe(PyAgentRecolor.get_item_name_rules, default=[]) or [])]
    gall = casts.safe(PyAgentRecolor.has_all_gadget_color)
    return [
        ui.multi_block(f"Agent Rules ({len(ar)})", ["Agent ID", "ARGB"], ar),
        ui.multi_block(f"Allegiance Rules ({len(lr)})", ["Allegiance", "Name", "ARGB"], lr),
        ui.multi_block(f"Gadget Rules ({len(gr)})  all={casts.yesno(gall)}", ["Agent ID", "ARGB"], gr),
        ui.multi_block(f"Item Rarity Rules ({len(i_ra)})", ["Rarity", "Name", "ARGB"], i_ra),
        ui.multi_block(f"Item Type Rules ({len(i_ty)})", ["Type", "ARGB"], i_ty),
        ui.multi_block(f"Item Model Rules ({len(i_mo)})", ["Model ID", "ARGB"], i_mo),
        ui.multi_block(f"Item Name Rules ({len(i_nm)})", ["Substring", "ARGB"], i_nm),
        ui.multi_block(f"Item ID Rules ({len(i_id)})", ["Item ID", "ARGB"], i_id),
        ui.multi_block(f"Item Agent Rules ({len(i_ag)})", ["Agent ID", "ARGB"], i_ag),
    ]


def _diagnostics_block():
    d = casts.safe(PyAgentRecolor.get_diagnostics, default={}) or {}
    rows = [
        ("agent   hook/enabled", f"{casts.yesno(d.get('agent_hook_installed'))} / {casts.yesno(d.get('agent_enabled'))}"),
        ("gadget  hook/enabled", f"{casts.yesno(d.get('gadget_hook_installed'))} / {casts.yesno(d.get('gadget_enabled'))}"),
        ("item    hook/enabled", f"{casts.yesno(d.get('item_hook_installed'))} / {casts.yesno(d.get('item_enabled'))}"),
        ("agent  calls/hits", f"{d.get('resolver_calls_seen')} / {d.get('agent_rule_hits')} (+alleg {d.get('allegiance_rule_hits')})"),
        ("gadget calls/hits", f"{d.get('gadget_calls_seen')} / {d.get('gadget_rule_hits')} (+all {d.get('gadget_all_hits')})"),
        ("item   calls/hits", f"{d.get('item_calls_seen')} / {d.get('item_rule_hits')}"),
        ("item name_cache", d.get("item_name_cache_size")),
        ("last agent id/color", f"{d.get('last_agent_id')} / {casts.hex_of(d.get('last_agent_color', 0), 8)}"),
        ("last gadget id/color", f"{d.get('last_gadget_id')} / {casts.hex_of(d.get('last_gadget_color', 0), 8)}"),
        ("last item id/model/color", f"{d.get('last_item_id')} / {d.get('last_item_model')} / {casts.hex_of(d.get('last_item_color', 0), 8)}"),
    ]
    return ui.kv_block("Diagnostics (all categories)", rows)


def build_agentrecolor():
    d = casts.safe(PyAgentRecolor.get_diagnostics, default={}) or {}
    blocks = [ui.kv_block("Hooks Installed", [
        ("Agent resolver", casts.yesno(d.get("agent_hook_installed"))),
        ("Gadget GetTextData", casts.yesno(d.get("gadget_hook_installed"))),
        ("Item GetTextData", casts.yesno(d.get("item_hook_installed"))),
    ])]
    blocks.extend(_rules_blocks())
    blocks.append(_diagnostics_block())
    if _val_rows:
        vr = [(r["verdict"], r["id"], r["name"], r["class"], r["expected"], r["actual"]) for r in _val_rows]
        blocks.append(ui.multi_block(
            f"Validate (P{_val_summary['pass']}/F{_val_summary['fail']}/U{_val_summary['unknown']})",
            ["Verdict", "ID", "Name", "Class", "Expected", "Actual"], vr))
    return blocks


# --------------------------------------------------------------------------- shared header
def _draw_shared_header():
    d = casts.safe(PyAgentRecolor.get_diagnostics, default={}) or {}
    PyImGui.text_colored(
        f"agent[{casts.yesno(d.get('agent_hook_installed'))}] "
        f"gadget[{casts.yesno(d.get('gadget_hook_installed'))}] "
        f"item[{casts.yesno(d.get('item_hook_installed'))}] hooks",
        ui.OK_COLOR,
    )
    PyImGui.text_colored(
        "Tags only recolor once the game re-draws them (hold Ctrl / 'always show names'; for items, "
        "walk them in/out of view).", ui.ACCENT_COLOR,
    )
    ui.section_header("Shared Test Color (picker)")
    state.test_rgba = PyImGui.color_edit4("Test Color", state.test_rgba)
    ui.text_muted(f"ARGB = {casts.hex_of(_test_argb(), 8)}")
    if PyImGui.button("Clear ALL rules (agents+gadgets+items)"):
        casts.safe(PyAgentRecolor.clear_all_rules)
    PyImGui.same_line(0, 6)
    if PyImGui.button("Reset Diagnostics"):
        casts.safe(PyAgentRecolor.reset_diagnostics)


# --------------------------------------------------------------------------- Agents tab
def _draw_agents():
    enabled = bool(casts.safe(PyAgentRecolor.is_enabled))
    ui.action_button("Enable" if not enabled else "Enabled *", PyAgentRecolor.enable, key="a_enable")
    PyImGui.same_line(0, 6)
    ui.action_button("Disable", PyAgentRecolor.disable, key="a_disable")
    PyImGui.same_line(0, 6)
    ui.action_button("Clear Agent Rules", PyAgentRecolor.clear_rules, key="a_clear")
    d = casts.safe(PyAgentRecolor.get_diagnostics, default={}) or {}
    ui.text_muted(f"calls={d.get('resolver_calls_seen')} hits={d.get('agent_rule_hits')} alleg={d.get('allegiance_rule_hits')}")

    ui.section_header("Recolor by allegiance")
    for aid in _ALLEG_IDS:
        ui.action_button(f"{_ALLEGIANCE_NAMES[aid]}", lambda a=aid: casts.safe(PyAgentRecolor.set_allegiance_color, a, _test_argb()), key=f"a_rc_{aid}")
        if aid != _ALLEG_IDS[-1]:
            PyImGui.same_line(0, 6)
    state.alleg_index = PyImGui.combo("Allegiance", state.alleg_index, _ALLEG_LABELS)
    _al = _ALLEG_IDS[state.alleg_index] if 0 <= state.alleg_index < len(_ALLEG_IDS) else 1
    ui.action_button("Remove Allegiance Color", PyAgentRecolor.remove_allegiance_color, _al, key="a_rm_alleg")
    _rgb_a = _test_argb() & 0x00FFFFFF
    ui.action_button("Hide allegiance", lambda: casts.safe(PyAgentRecolor.set_allegiance_color, _al, 0x00000000), key="a_hide")
    PyImGui.same_line(0, 6)
    ui.action_button("Fade allegiance", lambda: casts.safe(PyAgentRecolor.set_allegiance_color, _al, 0x40000000 | _rgb_a), key="a_fade")
    ui.text_muted("Alpha: 0xFF solid / 0x01-0xFE fade / 0x00 hide (name tag). Ring stays colored via the resolver.")

    ui.section_header("Single agent (live picker)")
    if PyImGui.button("Refresh Agents"):
        _refresh_agent_list()
    PyImGui.same_line(0, 8)
    ui.text_muted(f"{len(_agent_list)} cached")
    if _agent_list:
        state.agent_picker_index = PyImGui.combo("Agent", min(state.agent_picker_index, len(_agent_list) - 1), [l for _i, l in _agent_list])
        if PyImGui.button("Use Selected##agent"):
            state.agent_id = _agent_list[state.agent_picker_index][0]
    state.agent_id = PyImGui.input_int("Agent ID", state.agent_id)
    ui.action_button("Recolor Agent", lambda: casts.safe(PyAgentRecolor.set_agent_color, int(state.agent_id), _test_argb()), key="a_rc_one")
    PyImGui.same_line(0, 6)
    ui.action_button("Remove Agent Color", PyAgentRecolor.remove_agent_color, state.agent_id, key="a_rm_one")
    PyImGui.same_line(0, 6)
    ui.action_button("Read Consider Color", PyAgentRecolor.read_consider_color, state.agent_id, key="a_read")

    ui.section_header("Validate (expected vs actual)")
    if PyImGui.button("Validate Visible Agents"):
        validate_visible()
    PyImGui.same_line(0, 8)
    ui.text_muted(f"PASS={_val_summary['pass']} FAIL={_val_summary['fail']} UNKNOWN={_val_summary['unknown']} (table in Data tab)")


# --------------------------------------------------------------------------- Gadgets tab
def _draw_gadgets():
    enabled = bool(casts.safe(PyAgentRecolor.gadget_is_enabled))
    ui.action_button("Enable" if not enabled else "Enabled *", PyAgentRecolor.gadget_enable, key="g_enable")
    PyImGui.same_line(0, 6)
    ui.action_button("Disable", PyAgentRecolor.gadget_disable, key="g_disable")
    PyImGui.same_line(0, 6)
    ui.action_button("Clear Gadget Rules", PyAgentRecolor.gadget_clear_rules, key="g_clear")
    d = casts.safe(PyAgentRecolor.get_diagnostics, default={}) or {}
    ui.text_muted(f"calls={d.get('gadget_calls_seen')} hits={d.get('gadget_rule_hits')} all={d.get('gadget_all_hits')}")

    ui.section_header("All gadgets")
    ui.action_button("Recolor ALL Gadgets", lambda: casts.safe(PyAgentRecolor.set_all_gadget_color, _test_argb()), key="g_all")
    PyImGui.same_line(0, 6)
    ui.action_button("Clear 'all gadgets'", PyAgentRecolor.clear_all_gadget_color, key="g_all_clr")

    ui.section_header("Single gadget (live picker)")
    if PyImGui.button("Refresh Gadgets"):
        _refresh_gadget_list()
    PyImGui.same_line(0, 8)
    ui.text_muted(f"{len(_gadget_list)} cached")
    if _gadget_list:
        state.gadget_picker_index = PyImGui.combo("Gadget", min(state.gadget_picker_index, len(_gadget_list) - 1), [l for _i, l in _gadget_list])
        if PyImGui.button("Use Selected##gadget"):
            state.gadget_id = _gadget_list[state.gadget_picker_index][0]
    state.gadget_id = PyImGui.input_int("Gadget Agent ID", state.gadget_id)
    ui.action_button("Recolor Gadget", lambda: casts.safe(PyAgentRecolor.set_gadget_color, int(state.gadget_id), _test_argb()), key="g_rc_one")
    PyImGui.same_line(0, 6)
    ui.action_button("Remove Gadget Color", PyAgentRecolor.remove_gadget_color, state.gadget_id, key="g_rm_one")


# --------------------------------------------------------------------------- Items tab
def _draw_items():
    enabled = bool(casts.safe(PyAgentRecolor.item_is_enabled))
    ui.action_button("Enable" if not enabled else "Enabled *", PyAgentRecolor.item_enable, key="i_enable")
    PyImGui.same_line(0, 6)
    ui.action_button("Disable", PyAgentRecolor.item_disable, key="i_disable")
    PyImGui.same_line(0, 6)
    ui.action_button("Clear Item Rules", PyAgentRecolor.item_clear_rules, key="i_clear")
    d = casts.safe(PyAgentRecolor.get_diagnostics, default={}) or {}
    ui.text_muted(f"calls={d.get('item_calls_seen')} hits={d.get('item_rule_hits')} name_cache={d.get('item_name_cache_size')}")
    ui.text_muted("Precedence: agent_id > item_id > model_id > name > type > rarity")

    ui.section_header("Loot filter (alpha = solid / fade / hide)")
    ui.text_muted("Alpha 0xFF=solid, 0x01-0xFE=fade, 0x00=hide. Applies to the selected rarity below.")
    _r_lf = _RARITY_IDS[state.rarity_index] if 0 <= state.rarity_index < len(_RARITY_IDS) else 0
    _rgb = _test_argb() & 0x00FFFFFF
    ui.action_button("Hide rarity", lambda: casts.safe(PyAgentRecolor.set_item_rarity_color, _r_lf, 0x00000000), key="lf_hide")
    PyImGui.same_line(0, 6)
    ui.action_button("Fade rarity", lambda: casts.safe(PyAgentRecolor.set_item_rarity_color, _r_lf, 0x40000000 | _rgb), key="lf_fade")
    PyImGui.same_line(0, 6)
    ui.action_button("Solid rarity", lambda: casts.safe(PyAgentRecolor.set_item_rarity_color, _r_lf, 0xFF000000 | _rgb), key="lf_solid")
    ui.text_muted("(Tip: hide/fade also work on every other filter - pass alpha in the ARGB.)")

    ui.section_header("By rarity")
    for rid in _RARITY_IDS:
        ui.action_button(_RARITY_NAMES[rid], lambda r=rid: casts.safe(PyAgentRecolor.set_item_rarity_color, r, _test_argb()), key=f"i_ra_{rid}")
        if rid != _RARITY_IDS[-1]:
            PyImGui.same_line(0, 6)
    state.rarity_index = PyImGui.combo("Rarity", state.rarity_index, _RARITY_LABELS)
    _r = _RARITY_IDS[state.rarity_index] if 0 <= state.rarity_index < len(_RARITY_IDS) else 0
    ui.action_button("Remove Rarity Color", PyAgentRecolor.remove_item_rarity_color, _r, key="i_ra_rm")

    ui.section_header("By item type")
    _type_labels = [f"{t} {n}" for t, n in _ITEM_TYPE_COMMON]
    state.item_type_combo = PyImGui.combo("Common types", state.item_type_combo, _type_labels)
    if PyImGui.button("Use type from dropdown"):
        state.item_type = _ITEM_TYPE_COMMON[state.item_type_combo][0]
    state.item_type = PyImGui.input_int("Item Type (int)", state.item_type)
    ui.action_button("Set Type Color", lambda: casts.safe(PyAgentRecolor.set_item_type_color, int(state.item_type), _test_argb()), key="i_ty_set")
    PyImGui.same_line(0, 6)
    ui.action_button("Remove Type Color", PyAgentRecolor.remove_item_type_color, state.item_type, key="i_ty_rm")

    ui.section_header("By name (substring, case-insensitive)")
    state.name_substr = PyImGui.input_text("Name contains", state.name_substr)
    ui.action_button("Set Name Color", lambda: casts.safe(PyAgentRecolor.set_item_name_color, state.name_substr, _test_argb()), key="i_nm_set")
    PyImGui.same_line(0, 6)
    ui.action_button("Remove Name Color", PyAgentRecolor.remove_item_name_color, state.name_substr, key="i_nm_rm")
    ui.text_muted("Names decode asynchronously - a rule may take a frame or two to take effect per item kind.")

    ui.section_header("By model id")
    state.model_id = PyImGui.input_int("Model ID", state.model_id)
    ui.action_button("Set Model Color", lambda: casts.safe(PyAgentRecolor.set_item_model_color, int(state.model_id), _test_argb()), key="i_mo_set")
    PyImGui.same_line(0, 6)
    ui.action_button("Remove Model Color", PyAgentRecolor.remove_item_model_color, state.model_id, key="i_mo_rm")

    ui.section_header("By item id / agent id")
    state.item_id = PyImGui.input_int("Item ID", state.item_id)
    ui.action_button("Set Item-ID Color", lambda: casts.safe(PyAgentRecolor.set_item_id_color, int(state.item_id), _test_argb()), key="i_id_set")
    PyImGui.same_line(0, 6)
    ui.action_button("Remove Item-ID Color", PyAgentRecolor.remove_item_id_color, state.item_id, key="i_id_rm")
    state.item_agent_id = PyImGui.input_int("Item Agent ID", state.item_agent_id)
    ui.action_button("Set Agent-ID Color", lambda: casts.safe(PyAgentRecolor.set_item_agent_color, int(state.item_agent_id), _test_argb()), key="i_ag_set")
    PyImGui.same_line(0, 6)
    ui.action_button("Remove Agent-ID Color", PyAgentRecolor.remove_item_agent_color, state.item_agent_id, key="i_ag_rm")

    ui.section_header("Ground-item picker (drives every filter above)")
    if PyImGui.button("Refresh Ground Items"):
        _refresh_item_list()
    PyImGui.same_line(0, 8)
    ui.text_muted(f"{len(_item_list)} on ground")
    if _item_list:
        labels = [f"[{a}] {nm} ({rn}) model={mo} item={ii}" for (a, ii, mo, _rv, rn, nm) in _item_list]
        state.item_picker_index = PyImGui.combo("Ground item", min(state.item_picker_index, len(_item_list) - 1), labels)
        sel = _item_list[state.item_picker_index]
        if PyImGui.button("Load Selected -> fields"):
            state.item_agent_id, state.item_id, state.model_id = sel[0], sel[1], sel[2]
            state.rarity_index = sel[3] if 0 <= sel[3] < len(_RARITY_IDS) else state.rarity_index
            state.name_substr = str(sel[5])
        PyImGui.same_line(0, 6)
        if PyImGui.button("Recolor Selected (by agent id)"):
            casts.safe(PyAgentRecolor.set_item_agent_color, int(sel[0]), _test_argb())


# --------------------------------------------------------------------------- entry
def _draw_actions():
    _draw_shared_header()
    PyImGui.separator()
    if PyImGui.begin_tab_bar("RecolorCatTabs"):
        if PyImGui.begin_tab_item("Agents"):
            _draw_agents()
            PyImGui.end_tab_item()
        if PyImGui.begin_tab_item("Gadgets"):
            _draw_gadgets()
            PyImGui.end_tab_item()
        if PyImGui.begin_tab_item("Items"):
            _draw_items()
            PyImGui.end_tab_item()
        PyImGui.end_tab_bar()


def draw_agentrecolor_view() -> None:
    blocks = build_agentrecolor()
    diagnostics.dump_button(_SECTION, blocks)
    PyImGui.separator()
    if PyImGui.begin_tab_bar("AgentRecolorTabs"):
        if PyImGui.begin_tab_item("Tester"):
            _draw_actions()
            PyImGui.end_tab_item()
        if PyImGui.begin_tab_item("Data"):
            ui.draw_blocks(_SECTION, blocks)
            PyImGui.end_tab_item()
        PyImGui.end_tab_bar()
