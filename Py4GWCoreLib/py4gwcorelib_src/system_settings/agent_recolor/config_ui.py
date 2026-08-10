"""Agent Recolor UI — one tabbed 'Agent Recolor' section for the Agents group.

Tabs: Agents (rule list + editor for living-agent rules), Gadgets (gadget rules), and
Status (per-account master/category toggles, native diagnostics, share import/export). Each
rule renders as a collapsing header (name · swatch · live match count) whose body is the full
criteria editor. All state lives in the controller; only transient text-input buffers are kept
here (immediate-mode has no memory of its own).
"""

import PyImGui

from Py4GWCoreLib.AgentRecolor import AgentRecolor

from .controller import AgentRecolorController
from .controller import get_controller
from . import model

_MUTED = (0.60, 0.60, 0.65, 1.0)
_ACCENT = (1.00, 0.78, 0.39, 1.0)
_OK = (0.45, 0.85, 0.45, 1.0)
_MODE_LABELS = ["Solid", "Fade", "Hide"]


class _UI:
    """Transient per-frame input state (raw text buffers keyed by rule id + field)."""

    buffers: "dict[str, str]" = {}
    import_text: str = ""
    status_note: str = ""


_ui = _UI()


# ── buffer helpers (keep raw text stable across frames so typing isn't fought) ─────────────
def _buf(rule_id: str, field: str, seed: str) -> str:
    key = "%s:%s" % (rule_id, field)
    if key not in _ui.buffers:
        _ui.buffers[key] = seed
    return key


def _reseed(rule_id: str, field: str, seed: str) -> None:
    _ui.buffers["%s:%s" % (rule_id, field)] = seed


def _parse_int_list(s: str) -> "list[int]":
    out: "list[int]" = []
    for tok in s.replace(";", ",").split(","):
        tok = tok.strip()
        if tok:
            try:
                out.append(int(tok, 0))
            except Exception:
                pass
    return out


def _parse_opt_int(s: str) -> "int | None":
    s = s.strip()
    if not s:
        return None
    try:
        return int(s, 0)
    except Exception:
        return None


def _parse_opt_float(s: str) -> "float | None":
    s = s.strip()
    if not s:
        return None
    try:
        return float(s)
    except Exception:
        return None


def _ints_to_text(v: "list[int]") -> str:
    return ", ".join(str(x) for x in v)


def _opt_to_text(v) -> str:
    return "" if v is None else str(v)


# ── the criteria editor for one rule ───────────────────────────────────────────────────────
def _draw_rule_editor(controller: "AgentRecolorController", rule: "model.Rule") -> None:
    before = rule.to_dict()
    is_agent = rule.scope == model.SCOPE_AGENT
    rid = rule.id

    rule.name = PyImGui.input_text("Name##nm_%s" % rid, rule.name)

    # ── action: color + mode ──────────────────────────────────────────────────────────────
    rgb_f = AgentRecolor.IntRGBToFloat(rule.color_rgb)
    new_rgb = PyImGui.color_edit3("Color##col_%s" % rid, rgb_f)
    if new_rgb is not None:
        rule.color_rgb = AgentRecolor.FloatRGBToInt((new_rgb[0], new_rgb[1], new_rgb[2]))
    mi = model.MODES.index(rule.mode) if rule.mode in model.MODES else 0
    mi = PyImGui.combo("Mode##mode_%s" % rid, mi, _MODE_LABELS)
    rule.mode = model.MODES[mi] if 0 <= mi < len(model.MODES) else model.MODE_SOLID
    if rule.mode == model.MODE_FADE:
        rule.alpha = PyImGui.slider_int("Alpha##a_%s" % rid, int(rule.alpha), 1, 254)
    PyImGui.text_colored("Solid = opaque · Fade = dim (alpha) · Hide = blank the tag", _MUTED)

    PyImGui.separator()
    PyImGui.text_colored("Criteria (unset = any; all set ones must match)", _MUTED)

    # ── allegiance (agent only) ───────────────────────────────────────────────────────────
    if is_agent:
        alleg_labels = ["(any)"] + [model.ALLEGIANCE_NAMES[i] for i in model.ALLEGIANCE_IDS]
        cur = 0 if rule.allegiance not in model.ALLEGIANCE_IDS else (model.ALLEGIANCE_IDS.index(rule.allegiance) + 1)
        cur = PyImGui.combo("Allegiance##al_%s" % rid, cur, alleg_labels)
        rule.allegiance = None if cur <= 0 else model.ALLEGIANCE_IDS[cur - 1]

        # kinds (any-of)
        PyImGui.text_colored("Kind (any of)", _MUTED)
        kinds = set(rule.kinds)
        for k in model.KIND_KEYS:
            on = PyImGui.checkbox("%s##k_%s_%s" % (k, k, rid), k in kinds)
            if on:
                kinds.add(k)
            else:
                kinds.discard(k)
            PyImGui.same_line(0, 6)
        PyImGui.new_line()
        rule.kinds = [k for k in model.KIND_KEYS if k in kinds]

        # model ids
        mk = _buf(rid, "models", _ints_to_text(rule.model_ids))
        _ui.buffers[mk] = PyImGui.input_text("Model IDs (csv)##%s" % mk, _ui.buffers[mk])
        rule.model_ids = _parse_int_list(_ui.buffers[mk])

        # professions
        pk = _buf(rid, "profs", _ints_to_text(rule.professions))
        _ui.buffers[pk] = PyImGui.input_text("Profession IDs (csv, prim/sec)##%s" % pk, _ui.buffers[pk])
        rule.professions = _parse_int_list(_ui.buffers[pk])

    # ── name / enc substring ──────────────────────────────────────────────────────────────
    rule.name_substr = PyImGui.input_text("Name contains##ns_%s" % rid, rule.name_substr or "") or None
    if is_agent:
        rule.enc_substr = PyImGui.input_text("Enc-name contains##es_%s" % rid, rule.enc_substr or "") or None

        # level range
        lmn = _buf(rid, "lmin", _opt_to_text(rule.level_min))
        _ui.buffers[lmn] = PyImGui.input_text("Level min##%s" % lmn, _ui.buffers[lmn])
        rule.level_min = _parse_opt_int(_ui.buffers[lmn])
        PyImGui.same_line(0, 8)
        lmx = _buf(rid, "lmax", _opt_to_text(rule.level_max))
        _ui.buffers[lmx] = PyImGui.input_text("Level max##%s" % lmx, _ui.buffers[lmx])
        rule.level_max = _parse_opt_int(_ui.buffers[lmx])

        # hp% range
        hmn = _buf(rid, "hmin", _opt_to_text(rule.hp_min))
        _ui.buffers[hmn] = PyImGui.input_text("HP%% min##%s" % hmn, _ui.buffers[hmn])
        rule.hp_min = _parse_opt_float(_ui.buffers[hmn])
        PyImGui.same_line(0, 8)
        hmx = _buf(rid, "hmax", _opt_to_text(rule.hp_max))
        _ui.buffers[hmx] = PyImGui.input_text("HP%% max##%s" % hmx, _ui.buffers[hmx])
        rule.hp_max = _parse_opt_float(_ui.buffers[hmx])

        # states (all-of)
        PyImGui.text_colored("State (all of)", _MUTED)
        states = set(rule.states)
        for si in model.STATE_KEYS:
            on = PyImGui.checkbox("%s##st_%s_%s" % (si, si, rid), si in states)
            if on:
                states.add(si)
            else:
                states.discard(si)
            PyImGui.same_line(0, 6)
        PyImGui.new_line()
        rule.states = [s for s in model.STATE_KEYS if s in states]

    # ── pin one id + grab-from-target ─────────────────────────────────────────────────────
    ak = _buf(rid, "aid", _opt_to_text(rule.agent_id))
    _ui.buffers[ak] = PyImGui.input_text("%s ID (pin one)##%s" % ("Agent" if is_agent else "Gadget", ak), _ui.buffers[ak])
    rule.agent_id = _parse_opt_int(_ui.buffers[ak])
    PyImGui.same_line(0, 8)
    if PyImGui.small_button("Grab target##gt_%s" % rid):
        _grab_target(rule)

    # match count + persist
    PyImGui.text_colored("Matches now: %d" % controller.count_matches(rule), _OK)
    if rule.to_dict() != before:
        controller.update_rule(rule)


def _grab_target(rule: "model.Rule") -> None:
    """Fill this rule's fields from the current target so users don't hand-type ids."""
    try:
        from Py4GWCoreLib.Player import Player
        from Py4GWCoreLib.Agent import Agent

        tid = int(Player.GetTargetID() or 0)
        if not tid:
            return
        rule.agent_id = tid
        _reseed(rule.id, "aid", str(tid))
        if rule.scope == model.SCOPE_AGENT:
            model_id = int(Agent.GetModelID(tid) or 0)
            if model_id:
                rule.model_ids = [model_id]
                _reseed(rule.id, "models", str(model_id))
        name = Agent.GetNameByID(tid) or ""
        if name:
            rule.name_substr = name
    except Exception:
        pass


# ── rule list for a scope ───────────────────────────────────────────────────────────────────
def _swatch_prefix(rule: "model.Rule") -> str:
    tag = {model.MODE_SOLID: "#", model.MODE_FADE: "~", model.MODE_HIDE: "x"}.get(rule.mode, "#")
    return "[%s%06X]" % (tag, rule.color_rgb & 0xFFFFFF)


def _draw_rule_list(controller: "AgentRecolorController", scope: str) -> None:
    scope_name = "agent" if scope == model.SCOPE_AGENT else "gadget"
    if PyImGui.button("+ New %s rule" % scope_name):
        controller.new_rule(scope)
    PyImGui.same_line(0, 8)
    PyImGui.text_colored("First enabled rule that matches wins (top = highest priority).", _MUTED)

    if scope == model.SCOPE_AGENT:
        _draw_presets(controller)

    PyImGui.separator()
    rules = controller.rules_for_scope(scope)
    if not rules:
        PyImGui.text_colored("No rules yet — add one above.", _MUTED)
        return

    remove_id = ""
    dup_id = ""
    move: "tuple[str, int] | None" = None
    for rule in rules:
        on = "on" if rule.enabled else "off"
        # NOTE: ### (not ##) so the header ID depends ONLY on the rule id — the visible label
        # includes the mutable name/swatch/on-state, and ## would re-hash the ID every keystroke
        # (collapsing the header on each character). ### fixes the ID to the trailing token.
        header = "%s %s  ·  %s  (%s)###hdr_%s" % (_swatch_prefix(rule), rule.name, scope_name, on, rule.id)
        if PyImGui.collapsing_header(header):
            if PyImGui.small_button("Up##up_%s" % rule.id):
                move = (rule.id, -1)
            PyImGui.same_line(0, 4)
            if PyImGui.small_button("Down##dn_%s" % rule.id):
                move = (rule.id, 1)
            PyImGui.same_line(0, 4)
            if PyImGui.small_button("Duplicate##du_%s" % rule.id):
                dup_id = rule.id
            PyImGui.same_line(0, 4)
            if PyImGui.small_button("Remove##rm_%s" % rule.id):
                remove_id = rule.id
            rule.enabled = PyImGui.checkbox("Enabled##en_%s" % rule.id, rule.enabled)
            _draw_rule_editor(controller, rule)
            PyImGui.separator()

    # apply structural changes after the loop (never mutate the list mid-iteration)
    if move is not None:
        controller.move_rule(move[0], move[1])
    if dup_id:
        controller.duplicate_rule(dup_id)
    if remove_id:
        controller.remove_rule(remove_id)


def _draw_presets(controller: "AgentRecolorController") -> None:
    PyImGui.text_colored("Quick presets:", _MUTED)
    PyImGui.same_line(0, 6)
    if PyImGui.small_button("Enemies red"):
        r = controller.new_rule(model.SCOPE_AGENT)
        r.name, r.allegiance, r.color_rgb = "Enemies red", 3, 0xFF0000
        controller.update_rule(r)
    PyImGui.same_line(0, 6)
    if PyImGui.small_button("Bosses gold"):
        r = controller.new_rule(model.SCOPE_AGENT)
        r.name, r.kinds, r.color_rgb = "Bosses gold", ["boss"], 0xFFD24F
        controller.update_rule(r)
    PyImGui.same_line(0, 6)
    if PyImGui.small_button("Fade allies"):
        r = controller.new_rule(model.SCOPE_AGENT)
        r.name, r.allegiance, r.mode, r.color_rgb, r.alpha = "Fade allies", 1, model.MODE_FADE, 0xFFFFFF, 0x40
        controller.update_rule(r)


# ── tabs ─────────────────────────────────────────────────────────────────────────────────────
def _draw_agents(controller: "AgentRecolorController") -> None:
    _draw_rule_list(controller, model.SCOPE_AGENT)


def _draw_gadgets(controller: "AgentRecolorController") -> None:
    _draw_rule_list(controller, model.SCOPE_GADGET)


def _draw_status(controller: "AgentRecolorController") -> None:
    master = controller.master_enabled
    new_master = PyImGui.checkbox("Enable Agent Recolor (this account)", master)
    if new_master != master:
        controller.set_master_enabled(new_master)
    PyImGui.text_wrapped(
        "Master switch toggles the native recolor hooks for THIS account. Rules are shared "
        "machine-wide; each account decides whether to run them."
    )
    PyImGui.separator()

    ag = controller.agents_on
    new_ag = PyImGui.checkbox("Agents category", ag)
    if new_ag != ag:
        controller.set_agents_on(new_ag)
    gg = controller.gadgets_on
    new_gg = PyImGui.checkbox("Gadgets category", gg)
    if new_gg != gg:
        controller.set_gadgets_on(new_gg)

    PyImGui.separator()
    PyImGui.text_colored("Native status", _MUTED)
    d = AgentRecolor.GetDiagnostics()
    if not d:
        PyImGui.text_colored("PyAgentRecolor unavailable (offline).", _MUTED)
    else:
        PyImGui.text("master enabled:   %s" % AgentRecolor.IsMasterEnabled())
        PyImGui.text("agent hook/gate:  %s / %s" % (d.get("agent_hook_installed"), d.get("agent_enabled")))
        PyImGui.text("gadget hook/gate: %s / %s" % (d.get("gadget_hook_installed"), d.get("gadget_enabled")))
        PyImGui.text("agent calls/hits: %s / %s (+alleg %s)" % (
            d.get("resolver_calls_seen"), d.get("agent_rule_hits"), d.get("allegiance_rule_hits")))
        PyImGui.text("gadget calls/hits:%s / %s" % (d.get("gadget_calls_seen"), d.get("gadget_rule_hits")))

    PyImGui.separator()
    PyImGui.text_colored("Share rules (global list)", _MUTED)
    if PyImGui.button("Export -> box"):
        _ui.import_text = controller.export_json()
        _ui.status_note = "Exported %d rules." % len(controller.rules)
    PyImGui.same_line(0, 6)
    if PyImGui.button("Import (replace)"):
        n = controller.import_json(_ui.import_text, replace=True)
        _ui.status_note = "Imported %d rules (replace)." % n if n else "Import failed (bad JSON)."
    PyImGui.same_line(0, 6)
    if PyImGui.button("Import (append)"):
        n = controller.import_json(_ui.import_text, replace=False)
        _ui.status_note = "Imported %d rules (append)." % n if n else "Import failed (bad JSON)."
    _ui.import_text = PyImGui.input_text_multiline("##ar_share", _ui.import_text, (0.0, 120.0))
    if _ui.status_note:
        PyImGui.text_colored(_ui.status_note, _ACCENT)


# ── section registration (called by System Settings' Agents group) ────────────────────────
def add_sections(win, group) -> None:
    """Add the single tabbed 'Agent Recolor' section to ``group`` on ``win`` (a SidebarWindow)."""
    controller = get_controller()
    win.add_section(group, "Agent Recolor")
    win.add_tab("Agent Recolor", "Agents", lambda c=controller: _draw_agents(c))
    win.add_tab("Agent Recolor", "Gadgets", lambda c=controller: _draw_gadgets(c))
    win.add_tab("Agent Recolor", "Status", lambda c=controller: _draw_status(c))
