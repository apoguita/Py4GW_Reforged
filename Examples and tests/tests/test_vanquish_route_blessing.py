from __future__ import annotations
import ast
import builtins
from enum import IntEnum
from pathlib import Path
from types import SimpleNamespace as NS
from typing import Any
import unittest

ROOT = Path(__file__).resolve().parents[2]
BOTS = ('Drazach Thicket.py',)
FOLDER = ROOT / "Widgets/Automation/Bots/Vanquish/Factions/Echovald Forest"

class State(IntEnum):
    RUNNING = 1
    SUCCESS = 2
    FAILURE = 3

class Props:
    def __init__(self): self.paused = False
    def Get(self, *_): return self.paused
    def ApplyNow(self, *args): self.paused = args[-1]

class Tree:
    def __init__(self, result=State.SUCCESS): self.result = result; self.resets = 0
    def tick(self): return self.result
    def reset(self): self.resets += 1

class Recorder:
    def __init__(self, events, name="bot"): self.events = events; self.name = name
    def __getattr__(self, name): return Recorder(self.events, self.name + "." + name)
    def __call__(self, *args, **kwargs): self.events.append((self.name, args, kwargs))

def wait(_): yield

def finish(generator):
    while True:
        try: next(generator)
        except StopIteration as result: return result.value

def fixture(filename, result=State.SUCCESS):
    path = FOLDER / filename; source = path.read_text(encoding="utf-8-sig"); module = ast.parse(source)
    calls=[]; tree=Tree(result); bot=NS(Properties=Props(), Stop=lambda: calls.append("stop"))
    owner=NS(TakeBlessing=lambda **kw: calls.append(kw) or tree)
    original_import=builtins.__import__
    def importer(name, *args, **kwargs):
        if name == "Py4GWCoreLib.py4gwcorelib_src.BehaviorTree": return NS(BehaviorTree=NS(NodeState=State))
        if name == "Sources.ApoSource.ApoBottingLib": return NS(wrappers=owner)
        return original_import(name, *args, **kwargs)
    ns: dict[str, Any] = {"Botting": object, "Routines": NS(**{"Yield": NS(wait=wait)}), "__builtins__": dict(vars(builtins), __import__=importer)}
    for n in module.body:
        if isinstance(n, ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0], ast.Name):
            try: ns[n.targets[0].id] = ast.literal_eval(n.value)
            except (ValueError, TypeError): pass
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) and n.value is not None:
            try: ns[n.target.id] = ast.literal_eval(n.value)
            except (ValueError, TypeError): pass
    functions: list[ast.stmt] = [n for n in module.body if isinstance(n, ast.FunctionDef) and n.name in {"_take_kurzick_blessing", "bot_routine"}]
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(path), "exec"), ns)
    return ns, bot, tree, calls

class RouteBlessingTests(unittest.TestCase):
    def test_route_registers_blessing_before_existing_path_owner(self):
        for filename in BOTS:
            with self.subTest(bot=filename):
                ns, _, _, _ = fixture(filename); events=[]; ns["bot_routine"](Recorder(events))
                blessing = next(i for i,e in enumerate(events) if e[0]=="bot.States.AddCustomState" and e[1][1]=="Take the Kurzick blessing")
                path = next(i for i,e in enumerate(events) if e[0]=="bot.Move.FollowPath")
                self.assertLess(blessing, path)
                self.assertEqual(events[path][1][0], ns["Vanquish_Path"])

    def test_blessing_delegates_to_upstream_faction_owner_and_preserves_multibox(self):
        for filename in BOTS:
            with self.subTest(bot=filename):
                ns, bot, tree, calls = fixture(filename)
                self.assertTrue(finish(ns["_take_kurzick_blessing"](bot)))
                self.assertEqual(calls, [{"pos":ns["COORDS_FOR_PRIEST"], "faction":"kurzick", "multi_account":True, "log":True}])
                self.assertFalse(bot.Properties.paused); self.assertEqual(tree.resets, 1)

    def test_failure_stops_route_and_restores_blessing_upkeep(self):
        for filename in BOTS:
            with self.subTest(bot=filename):
                ns, bot, tree, calls = fixture(filename, State.FAILURE)
                with self.assertRaisesRegex(RuntimeError, "blessing owner failed"): finish(ns["_take_kurzick_blessing"](bot))
                self.assertIn("stop", calls); self.assertFalse(bot.Properties.paused); self.assertEqual(tree.resets, 1)

    def test_cancellation_resets_owner_and_restores_upkeep(self):
        for filename in BOTS:
            with self.subTest(bot=filename):
                ns, bot, tree, _ = fixture(filename, State.RUNNING); gen=ns["_take_kurzick_blessing"](bot); next(gen)
                self.assertTrue(bot.Properties.paused); gen.close()
                self.assertFalse(bot.Properties.paused); self.assertEqual(tree.resets, 1)

    def test_preexisting_pause_is_preserved(self):
        for filename in BOTS:
            with self.subTest(bot=filename):
                ns, bot, _, _ = fixture(filename); bot.Properties.paused=True
                self.assertTrue(finish(ns["_take_kurzick_blessing"](bot))); self.assertTrue(bot.Properties.paused)

if __name__ == "__main__": unittest.main()
