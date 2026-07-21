# Py4GW Reforged

Py4GW Reforged is a Python automation and scripting library for the Guild Wars
client. Python runs embedded inside the game process through `Py4GW.dll`, giving
you tools for automation, scripting, and in-game interactions.

This is the current, actively developed version of Py4GW. It replaces the
original project at https://github.com/apoguita/Py4GW, which is now retired.

## The two projects

Py4GW Reforged is split into two repositories:

- Py4GW_Reforged (this repo) - the Python library you write scripts and widgets
  against.
- Py4GW_Reforged_Native - the C++ project that builds `Py4GW.dll`, the injected
  backend the Python library runs inside:
  https://github.com/apoguita/Py4GW_Reforged_Native

## Features

- Agent handling - manage NPCs, enemies, and allies.
- Inventory management - automate item handling and categorization.
- Pathfinding and navigation - built-in movement tools.
- Widgets - extensible in-game UI for travel, titles, and more.
- Event hooks - react to game events with your own logic.
- Multi-account support - run and coordinate multiple accounts at once.
- Lightweight and modular - fast, modular, and easy to extend.

## Requirements

- Python 3.13.0 32-bit (other versions can crash the Guild Wars client):
  https://www.python.org/downloads/release/python-3130/
- A Guild Wars client.

## Getting started

1. Clone this repository:

       git clone https://github.com/apoguita/Py4GW_Reforged.git

2. Enter the project directory:

       cd Py4GW_Reforged

3. Follow the instructions on the Releases page to get the injected DLL and
   launcher, and to set up your environment:
   https://github.com/apoguita/Py4GW_Reforged/releases

## Contributing

Contributions are welcome:

1. Fork the repository.
2. Create a branch for your feature or fix.
3. Commit your changes and push the branch.
4. Open a pull request for review.

### Stop tracking local log and config files

To stop tracking local changes to the log and configuration files, remove them
from the worktree:

    git update-index --skip-worktree Py4GW_injection_log.txt
    git update-index --skip-worktree Py4GW.ini
    git update-index --skip-worktree Py4GW_Launcher.ini

Verify they are skipped (each should be prefixed with S):

    git ls-files -v | grep "^S"

Re-enable tracking with:

    git update-index --no-skip-worktree Py4GW_injection_log.txt
    git update-index --no-skip-worktree Py4GW.ini
    git update-index --no-skip-worktree Py4GW_Launcher.ini

------------------------------------------------------------------------------
