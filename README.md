# Py4GW Reforged

Py4GW Reforged is a Python automation and scripting library for the Guild Wars
client. It gives you tools for automation, scripting, and in-game interactions,
from single-character helpers to full multi-account bots.

This is the current, actively developed version of Py4GW. It replaces the
original project at https://github.com/apoguita/Py4GW, which is now retired.

## How it works

Python does not run standalone here. It runs embedded inside the Guild Wars
process through `Py4GW.dll`, which is injected into the game by the launcher.
Most of this library is meant to execute in-client against a live game, not from
a plain interpreter.

The library reaches the game through two parallel paths:

- Bindings - `Py*` modules (`PyAgent`, `PyPlayer`, `PyImGui`, `PySystem`, and
  more) provided by the DLL. The `stubs/` folder holds the type stubs for them,
  and the wrapper classes in `Py4GWCoreLib/` build on top.
- Shared memory - live game state (agent positions, health, map and world
  context, and so on) read directly from the game process.

`Py4GW.dll` itself is built by the companion C++ project:
https://github.com/apoguita/Py4GW_Reforged_Native

## Features

- Agent handling - manage NPCs, enemies, and allies.
- Inventory management - automate item handling and categorization.
- Pathfinding and navigation - built-in movement tools.
- Widgets - extensible in-game UI for travel, titles, and more.
- Event hooks - react to game events with your own logic.
- Hero AI and combat automation - rule-driven combat and party control.
- Multi-account support - run and coordinate multiple accounts at once, with a
  shared-memory layer for cross-account coordination.
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

3. Get the injected DLL and launcher from the Releases page, and follow the
   setup instructions there:
   https://github.com/apoguita/Py4GW_Reforged/releases

## Project layout

    Py4GW_Reforged/
    |-- Py4GWCoreLib/        Core library: the single source-of-truth layer
    |                        (Agent, Player, Map, Inventory, Skill, Party, ImGui,
    |                        Pathing, GlobalCache, shared memory, and more)
    |-- HeroAI/              Hero AI automation and combat logic
    |-- Widgets/             In-game widgets (folder-based discovery)
    |-- Sources/             Larger script projects (ModularBot, tools, libraries)
    |-- Bots/ , bot_factory/ Bot implementations and scaffolding
    |-- BridgeRuntime/       Bridge stack for external tools and MCP integration
    |-- stubs/               Type stubs for the Py* binding modules
    |-- Textures/ , fonts/ , Styles/   UI assets
    |-- Examples/            Example scripts demonstrating library usage
    |-- docs/                Architecture notes and subsystem guides
    |-- Py4GW_Launcher.py            External launcher and injector
    |-- Py4GW_widget_manager.py      In-client widget bootstrap
    |-- bridge_daemon.py , bridge_cli.py , py4gw_mcp_server.py
    |                                Bridge daemon, operator CLI, and MCP adapter

## Entry points

- Py4GW_Launcher.py - the external launcher and injector UI.
- Py4GW_widget_manager.py - the in-client widget host. Widgets are discovered by
  folder: any folder under `Widgets/` containing a `.widget` marker is loaded.
- Bridge stack - lets external tools talk to injected clients: the in-client
  Bridge Client widget, the `bridge_daemon.py` daemon, the `bridge_cli.py`
  operator CLI, and the `py4gw_mcp_server.py` MCP adapter.

## Documentation

See the `docs/` folder for architecture notes and per-subsystem guides. `AGENTS.md`
is a good starting point for how the repository is organized.

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
