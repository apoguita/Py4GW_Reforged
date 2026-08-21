from Py4GWCoreLib import *
from Py4GWCoreLib.FrameTree import Frame

MODULE_NAME = "SkillTome Frame Primitives Test"

# Set this to an account-unlocked skill visible in the currently opened tome.
SKILL_ID = 0


def main():
    root = Frame.skill_tome()
    Py4GW.Console.Log(
        MODULE_NAME,
        f"root: exists={root.exists}, usable={root.is_usable}, path={root.path() if root.exists else ''}",
        Py4GW.Console.MessageType.Info,
    )

    learn = Frame.skill_tome_learn_button()
    Py4GW.Console.Log(
        MODULE_NAME,
        f"learn: exists={learn.exists}, usable={learn.is_usable}, path={learn.path() if learn.exists else ''}",
        Py4GW.Console.MessageType.Info,
    )

    if SKILL_ID <= 0:
        return

    row = Frame.skill_tome_skill(SKILL_ID)
    marker = Frame.skill_tome_selection_marker(SKILL_ID)

    Py4GW.Console.Log(
        MODULE_NAME,
        f"row[{SKILL_ID}]: {row.path() if row is not None else 'not found'}",
        Py4GW.Console.MessageType.Info,
    )
    Py4GW.Console.Log(
        MODULE_NAME,
        f"selection[{SKILL_ID}]: {marker.path() if marker is not None else 'not selected'}",
        Py4GW.Console.MessageType.Info,
    )


if __name__ == "__main__":
    main()
