from __future__ import annotations
import ast
from enum import IntEnum
from pathlib import Path
from types import SimpleNamespace as NS
from typing import Any
import unittest

ROOT = Path(__file__).resolve().parents[2]
SOURCE_PATH = 'Widgets/Automation/Bots/Vanquish/Factions/Echovald Forest/Drazach Thicket.py'

class State(IntEnum):
    RUNNING = 1
    SUCCESS = 2
    FAILURE = 3

class Properties:
    def __init__(self): self.values = {"hero_ai_paused": False}
    def Get(self, name, field): return self.values[name]
    def ApplyNow(self, name, field, value): self.values[name] = value

class Tree:
    def __init__(self, states, *, reset_error=False):
        self.states = iter(states)
        self.resets = 0
        self.reset_error = reset_error
    def tick(self): return next(self.states)
    def reset(self):
        self.resets += 1
        if self.reset_error: raise RuntimeError("reset failed")

def wait(_): yield

def load(name, ns: dict[str, Any]) -> Any:
    tree = ast.parse((ROOT / SOURCE_PATH).read_text(encoding="utf-8-sig"))
    node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)
    node.decorator_list = []
    exec(compile(ast.Module(body=[node], type_ignores=[]), SOURCE_PATH, "exec"), ns)
    return ns[name]

def fixture():
    bot = NS(Properties=Properties())
    ns: dict[str, Any] = {"Botting": object, "BehaviorTree": NS(NodeState=State), "Routines": NS(**{"Yield": NS(wait=wait)})}
    fn = load("_run_owner_tree", ns)
    return bot, fn, ns

def finish(generator):
    while True:
        try: next(generator)
        except StopIteration as result: return result.value

class OwnerSchedulingTests(unittest.TestCase):
    def test_success_and_failure_restore_upkeep_and_reset_owner(self):
        for terminal, expected in [(State.SUCCESS, True), (State.FAILURE, False)]:
            bot, run, _ = fixture(); tree = Tree([State.RUNNING, terminal])
            self.assertIs(finish(run(bot, tree)), expected)
            self.assertFalse(bot.Properties.values["hero_ai_paused"])
            self.assertEqual(tree.resets, 1)

    def test_cancel_releases_the_actual_generator_finally_boundary(self):
        bot, run, _ = fixture(); tree = Tree([State.RUNNING])
        generator = run(bot, tree); next(generator)
        self.assertTrue(bot.Properties.values["hero_ai_paused"])
        generator.close()
        self.assertFalse(bot.Properties.values["hero_ai_paused"])
        self.assertEqual(tree.resets, 1)

    def test_reset_error_still_restores_upkeep(self):
        bot, run, _ = fixture(); tree = Tree([State.SUCCESS], reset_error=True)
        with self.assertRaisesRegex(RuntimeError, "reset failed"): finish(run(bot, tree))
        self.assertFalse(bot.Properties.values["hero_ai_paused"])

    def test_preexisting_pause_is_retained(self):
        bot, run, _ = fixture(); bot.Properties.values["hero_ai_paused"] = True
        self.assertTrue(finish(run(bot, Tree([State.SUCCESS]))))
        self.assertTrue(bot.Properties.values["hero_ai_paused"])

    def test_blessing_uses_existing_upstream_faction_owner(self):
        bot, _, ns = fixture(); calls = []
        ns.update(BT=NS(TakeBlessing=lambda **kw: calls.append(kw) or Tree([State.SUCCESS])), COORDS_FOR_PRIEST=(10, 20), _kurzick_blessing_active=lambda: True)
        self.assertTrue(finish(load("_take_kurzick_blessing", ns)(bot)))
        self.assertEqual(calls, [{"pos": (10, 20), "faction": "kurzick", "multi_account": False, "log": True}])

    def test_default_farm_setup_preserves_party_actions_and_single_account_skips_them(self):
        path = ROOT / "Py4GWCoreLib/botting_src/subclases_src/TEMPLATES_src.py"
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "PrepareForFarm")
        ns: dict[str, Any] = {}; exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), ns)
        for single in [False, True]:
            events = []
            bot = NS(States=NS(AddHeader=lambda _: None), Events=NS(OnPartyMemberBehindCallback=lambda _: None, OnPartyMemberInDangerCallback=lambda _: None, OnPartyMemberDeadBehindCallback=lambda _: None), Multibox=NS(KickAllAccounts=lambda: events.append("kick"), LeavePartyOnAllAccounts=lambda: events.append("leave"), SummonAllAccounts=lambda: events.append("summon"), InviteAllAccounts=lambda: events.append("invite")), Wait=NS(ForTime=lambda _: events.append("wait")), Travel_To_Random_District=lambda **_: events.append("travel"))
            self_obj = NS(parent=bot)
            ns["PrepareForFarm"](self_obj, 77, single_account=single)
            self.assertEqual(events, ["travel"] if single else ["kick", "travel", "summon", "wait", "invite"])

    def test_amber_conversion_preserves_capture_positions_and_requires_inventory_effect(self):
        bot, _, ns = fixture(); calls = []; observed = {"faction": 10000, "amber": 3}
        class Exchange(Tree):
            def tick(self):
                observed.update(faction=0, amber=5)
                return State.SUCCESS
        ns.update(Player=NS(GetKurzickData=lambda: (observed["faction"], 0, 10000)), GLOBAL_CACHE=NS(Inventory=NS(GetModelCount=lambda _: observed["amber"])), ModelID=NS(Amber_Chunk=42), DONATION_CHUNK=5000, _HOUSE_DONATION_NPC_TARGET_XY=(10, 20), _AMBER_REDEMPTION_MAX_VISIBLE_BUTTONS=(1, 2), BT=NS(MoveAndAutoDialog=lambda **kw: calls.append(kw) or Exchange([State.SUCCESS])), ConsoleLog=lambda *_: None, BOT_NAME="test")
        success, reason = finish(load("_redeem_kurzick_faction_for_amber", ns)(bot))
        self.assertTrue(success, reason)
        self.assertEqual(calls[0]["buttons"], [0, 1])
        self.assertEqual(calls[0]["pos"], (10, 20))

    def test_terminal_jump_cancels_only_the_displaced_state_when_requested(self):
        path = ROOT / "Py4GWCoreLib/py4gwcorelib_src/FSM.py"
        tree = ast.parse(path.read_text(encoding="utf-8-sig"));node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "jump_to_state_by_name")
        ns: dict[str, Any] = {};exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), ns)
        for cancel in [False, True]:
            scheduled = ["old-route"]
            old = NS(reset=lambda: scheduled.remove("old-route"))
            new = NS(name="Return to outpost", reset=lambda: None, enter=lambda: None)
            fsm = NS(current_state=old, states=[new], log_actions=False)
            ns["jump_to_state_by_name"](fsm, "Return to outpost", cancel_current_state=cancel)
            self.assertIs(fsm.current_state, new)
            self.assertEqual(scheduled, [] if cancel else ["old-route"])

if __name__ == "__main__": unittest.main()
