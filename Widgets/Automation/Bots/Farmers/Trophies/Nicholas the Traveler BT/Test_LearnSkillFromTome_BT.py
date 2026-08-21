import PyImGui

from Py4GWCoreLib.Py4GWcorelib import ConsoleLog
from Py4GWCoreLib.Routines import Routines
from Py4GWCoreLib.py4gwcorelib_src.BehaviorTree import BehaviorTree

MODULE_NAME = "BT LearnSkillFromTome Test"

skill_id = 1750
_tree = None
_last_result = "Idle"


def main():
    global skill_id, _tree, _last_result

    if _tree is not None:
        result = _tree.tick()
        _last_result = result.name
        if result in (BehaviorTree.NodeState.SUCCESS, BehaviorTree.NodeState.FAILURE):
            ConsoleLog(MODULE_NAME, f"Finished with {result.name}.", log=True)
            _tree = None
        return

    if PyImGui.begin(MODULE_NAME):
        PyImGui.text("Integrated BT.Player.LearnSkillFromTome test")
        PyImGui.text("The window hides while the BT is running so PyMouse can reach GW UI.")
        PyImGui.separator()
        skill_id = int(PyImGui.input_int("Skill ID", int(skill_id)))
        if PyImGui.button("Run LearnSkillFromTome"):
            _tree = Routines.BT.Player.LearnSkillFromTome(skill_id, log=True)
            _last_result = "RUNNING"
        PyImGui.separator()
        PyImGui.text(f"Last state: {_last_result}")
    PyImGui.end()


if __name__ == "__main__":
    main()
