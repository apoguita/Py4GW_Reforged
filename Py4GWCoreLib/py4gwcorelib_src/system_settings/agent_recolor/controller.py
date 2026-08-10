"""Agent Recolor controller — the process-wide singleton + the data-phase engine.

Owns the (global, shareable) rule list and the (per-account) master/category toggles, and
drives the native ``PyAgentRecolor`` module. When the account master toggle is on it registers
a profiled callback on ``PyCallback.Phase.Data`` (after the agent-array snapshot is refreshed in
PreUpdate, before draw): each pass it filters the ``AgentArray`` class by the enabled rules,
builds the full ``[(agent_id, argb)]`` set, and hands it to the native bulk setter in one call.
The native detours then recolor the tags reactively on every redraw — no polling of our own.

Rules are read live from ``self._rules`` each pass, so edits take effect on the next frame with
no re-registration. ``Agent`` / ``AgentArray`` / ``PyCallback`` are imported lazily so this module
stays import-safe offline.
"""

import uuid

from typing import Dict
from typing import List
from typing import Optional

from Py4GWCoreLib.AgentRecolor import AgentRecolor

from . import model
from . import store

_CB_NAME = "AgentRecolor"


def _log(msg: str) -> None:
    try:
        import PySystem

        PySystem.Console.Log(_CB_NAME, msg, PySystem.Console.MessageType.Warning)
    except Exception:
        pass


class AgentRecolorController:
    def __init__(self) -> None:
        self._rules: "List[model.Rule]" = store.load_rules()
        toggles = store.load_toggles()
        self._master: bool = bool(toggles.get("enabled", False))
        self._agents_on: bool = bool(toggles.get("agents_on", True))
        self._gadgets_on: bool = bool(toggles.get("gadgets_on", True))
        self._registered: bool = False
        # Last pushed sets (for change-detection so native only sees deltas).
        self._last_agents: "Dict[int, int]" = {}
        self._last_gadgets: "Dict[int, int]" = {}

    # ── queries ──────────────────────────────────────────────────────────────────────────
    @property
    def rules(self) -> "List[model.Rule]":
        return self._rules

    @property
    def master_enabled(self) -> bool:
        return self._master

    @property
    def agents_on(self) -> bool:
        return self._agents_on

    @property
    def gadgets_on(self) -> bool:
        return self._gadgets_on

    def rules_for_scope(self, scope: str) -> "List[model.Rule]":
        return [r for r in self._rules if r.scope == scope]

    # ── boot / native application ────────────────────────────────────────────────────────
    def boot(self) -> None:
        """Apply the persisted master state to the native side (idempotent). Called at startup."""
        self._apply_master()

    def _apply_master(self) -> None:
        if self._master:
            AgentRecolor.MasterEnable()
            AgentRecolor.EnableAgents(self._agents_on)
            AgentRecolor.EnableGadgets(self._gadgets_on)
            self._register_callback()
        else:
            self._unregister_callback()
            # Clear native stores and drop the hooks so colors revert.
            AgentRecolor.SetAgentColors([])
            AgentRecolor.SetGadgetColors([])
            AgentRecolor.MasterDisable()
            self._last_agents = {}
            self._last_gadgets = {}

    # ── master / category toggles (persist + apply) ──────────────────────────────────────
    def set_master_enabled(self, on: bool) -> None:
        self._master = bool(on)
        store.save_toggle("enabled", self._master)
        self._apply_master()

    def set_agents_on(self, on: bool) -> None:
        self._agents_on = bool(on)
        store.save_toggle("agents_on", self._agents_on)
        AgentRecolor.EnableAgents(self._agents_on)
        self._last_agents = {}   # force a repush next pass

    def set_gadgets_on(self, on: bool) -> None:
        self._gadgets_on = bool(on)
        store.save_toggle("gadgets_on", self._gadgets_on)
        AgentRecolor.EnableGadgets(self._gadgets_on)
        self._last_gadgets = {}

    # ── rule mutations (persist; the live pass picks them up next frame) ──────────────────
    def new_rule(self, scope: str) -> "model.Rule":
        rule = model.Rule(id=uuid.uuid4().hex, name="New rule", scope=scope)
        self._rules.append(rule)
        store.save_rules(self._rules)
        return rule

    def update_rule(self, rule: "model.Rule") -> None:
        for i, r in enumerate(self._rules):
            if r.id == rule.id:
                self._rules[i] = rule
                break
        store.save_rules(self._rules)

    def remove_rule(self, rule_id: str) -> None:
        self._rules = [r for r in self._rules if r.id != rule_id]
        store.save_rules(self._rules)

    def duplicate_rule(self, rule_id: str) -> None:
        for i, r in enumerate(self._rules):
            if r.id == rule_id:
                clone = model.Rule.from_dict(r.to_dict())
                clone.id = uuid.uuid4().hex
                clone.name = "%s (copy)" % r.name
                self._rules.insert(i + 1, clone)
                break
        store.save_rules(self._rules)

    def move_rule(self, rule_id: str, delta: int) -> None:
        """Shift a rule up (delta<0) or down (delta>0) in priority order."""
        idx = next((i for i, r in enumerate(self._rules) if r.id == rule_id), -1)
        if idx < 0:
            return
        new_idx = max(0, min(len(self._rules) - 1, idx + delta))
        if new_idx == idx:
            return
        self._rules.insert(new_idx, self._rules.pop(idx))
        store.save_rules(self._rules)

    def clear_rules(self) -> None:
        self._rules = []
        store.save_rules(self._rules)

    # ── import / export (shareable rule sets) ────────────────────────────────────────────
    def export_json(self) -> str:
        return store.rules_to_json(self._rules)

    def import_json(self, raw: str, replace: bool = True) -> int:
        """Load rules from a JSON string. Returns the number imported (0 on parse failure)."""
        imported = store.rules_from_json(raw)
        if not imported:
            return 0
        # Fresh ids to avoid collisions with existing rules.
        for r in imported:
            r.id = uuid.uuid4().hex
        self._rules = imported if replace else (self._rules + imported)
        store.save_rules(self._rules)
        return len(imported)

    # ── the data-phase callback ──────────────────────────────────────────────────────────
    def _register_callback(self) -> None:
        try:
            import PyCallback

            from Py4GWCoreLib.py4gwcorelib_src.Profiling import ProfilingRegistry

            PyCallback.PyCallback.RemoveByName(_CB_NAME)   # idempotent across reloads
            PyCallback.PyCallback.Register(
                _CB_NAME,
                PyCallback.Phase.Data,
                self._recolor_pass,
                priority=99,
                context=PyCallback.Context.Update,
            )
            ProfilingRegistry().register(_CB_NAME)          # declare profilable
            self._registered = True
        except Exception as exc:
            _log("callback registration error: %s" % exc)

    def _unregister_callback(self) -> None:
        try:
            import PyCallback

            PyCallback.PyCallback.RemoveByName(_CB_NAME)
        except Exception:
            pass
        self._registered = False

    def _recolor_pass(self) -> None:
        """Profiler-wrapped entry (routes through runcall_scope when a capture is active)."""
        try:
            from Py4GWCoreLib.py4gwcorelib_src.Profiling import ProfilingRegistry

            reg = ProfilingRegistry()
            if reg.enabled:
                reg.runcall_scope("widgets", "%s:data" % _CB_NAME, self._do_recolor_pass)
                return
        except Exception:
            pass
        self._do_recolor_pass()

    def _do_recolor_pass(self) -> None:
        if not self._master:
            return
        agent_map: "Dict[int, int]" = {}
        gadget_map: "Dict[int, int]" = {}
        try:
            from Py4GWCoreLib.Agent import Agent

            for rule in self._rules:
                if not rule.enabled:
                    continue
                argb = AgentRecolor.ARGB(rule.mode, rule.color_rgb, rule.alpha)
                if rule.scope == model.SCOPE_AGENT and self._agents_on:
                    for aid in self._agent_base_ids(rule):
                        if aid in agent_map:
                            continue
                        if self._agent_matches(rule, aid, Agent):
                            agent_map[aid] = argb
                elif rule.scope == model.SCOPE_GADGET and self._gadgets_on:
                    for gid in self._gadget_base_ids():
                        if gid in gadget_map:
                            continue
                        if self._gadget_matches(rule, gid, Agent):
                            gadget_map[gid] = argb
        except Exception as exc:
            _log("recolor pass error: %s" % exc)
            return
        self._push(agent_map, gadget_map)

    def _push(self, agent_map: "Dict[int, int]", gadget_map: "Dict[int, int]") -> None:
        changed = False
        if agent_map != self._last_agents:
            AgentRecolor.SetAgentColors(list(agent_map.items()))
            self._last_agents = agent_map
            changed = True
        if gadget_map != self._last_gadgets:
            AgentRecolor.SetGadgetColors(list(gadget_map.items()))
            self._last_gadgets = gadget_map
            changed = True
        # Only when the colored set actually changed: force the tags to re-render so the new
        # colors apply immediately (the game otherwise re-resolves a tag only on hover /
        # state-change). Bounded to real deltas, so no per-frame flashing on a static set.
        if changed:
            AgentRecolor.RefreshNameTags()

    # ── candidate arrays ─────────────────────────────────────────────────────────────────
    @staticmethod
    def _agent_base_ids(rule: "model.Rule") -> "List[int]":
        """The array to scan for a rule: the pre-bucketed allegiance array when the rule pins one
        (free allegiance match — the buckets are computed natively), else the full agent array."""
        from Py4GWCoreLib.AgentArray import AgentArray

        if rule.allegiance in model.ALLEGIANCE_ARRAY_GETTER:
            getter = getattr(AgentArray, model.ALLEGIANCE_ARRAY_GETTER[rule.allegiance], None)
            if getter is not None:
                return list(getter() or [])
            return []
        return list(AgentArray.GetAgentArray() or [])

    @staticmethod
    def _gadget_base_ids() -> "List[int]":
        from Py4GWCoreLib.AgentArray import AgentArray

        return list(AgentArray.GetGadgetArray() or [])

    # ── matching (allegiance already handled by base selection) ──────────────────────────
    @staticmethod
    def _agent_matches(rule: "model.Rule", aid: int, Agent) -> bool:
        try:
            if rule.agent_id is not None and aid != rule.agent_id:
                return False
            if rule.kinds:
                if not any(bool(getattr(Agent, model.KIND_PREDICATE[k])(aid)) for k in rule.kinds):
                    return False
            if rule.model_ids:
                if int(Agent.GetModelID(aid)) not in rule.model_ids:
                    return False
            if rule.professions:
                p1, p2 = Agent.GetProfessionIDs(aid)
                if int(p1) not in rule.professions and int(p2) not in rule.professions:
                    return False
            if rule.name_substr:
                if rule.name_substr.lower() not in (Agent.GetNameByID(aid) or "").lower():
                    return False
            if rule.enc_substr:
                if rule.enc_substr.lower() not in (Agent.GetEncNameStrByID(aid, True) or "").lower():
                    return False
            if rule.level_min is not None or rule.level_max is not None:
                lvl = int(Agent.GetLevel(aid))
                if rule.level_min is not None and lvl < rule.level_min:
                    return False
                if rule.level_max is not None and lvl > rule.level_max:
                    return False
            if rule.hp_min is not None or rule.hp_max is not None:
                hp = float(Agent.GetHealth(aid)) * 100.0
                if rule.hp_min is not None and hp < rule.hp_min:
                    return False
                if rule.hp_max is not None and hp > rule.hp_max:
                    return False
            if rule.states:
                if not all(bool(getattr(Agent, model.STATE_PREDICATE[s])(aid)) for s in rule.states):
                    return False
            return True
        except Exception:
            return False

    @staticmethod
    def _gadget_matches(rule: "model.Rule", gid: int, Agent) -> bool:
        try:
            if rule.agent_id is not None and gid != rule.agent_id:
                return False
            if rule.name_substr:
                if rule.name_substr.lower() not in (Agent.GetNameByID(gid) or "").lower():
                    return False
            return True
        except Exception:
            return False

    # ── live preview for the rule builder ────────────────────────────────────────────────
    def count_matches(self, rule: "model.Rule") -> int:
        try:
            from Py4GWCoreLib.Agent import Agent

            if rule.scope == model.SCOPE_AGENT:
                return sum(1 for aid in self._agent_base_ids(rule) if self._agent_matches(rule, aid, Agent))
            return sum(1 for gid in self._gadget_base_ids() if self._gadget_matches(rule, gid, Agent))
        except Exception:
            return 0


# ── process-wide singleton ───────────────────────────────────────────────────────────────────
_controller: Optional[AgentRecolorController] = None


def get_controller() -> AgentRecolorController:
    global _controller
    if _controller is None:
        _controller = AgentRecolorController()
    return _controller
