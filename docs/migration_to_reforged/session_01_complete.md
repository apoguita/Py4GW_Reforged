# Migration to Reforged â€” Session Log

## Session 1 â€” 2026-07-06: Full Binding Migration

### Architecture Discovery

Two parallel data paths in the Python library:
1. **Bindings** (`Py*` embedded modules) â†’ consumed by wrapper classes (`Agent.py`, `Player.py`, `Party.py`, etc.)
2. **Context** (ctypes structs from shared memory) â†’ consumed by `native_src/context/*.py`

### Stale Docs Fixed (in Py4GW_Reforged_Native/docs/)

- `python-migration-layers-analysis.md`: Reconciliation table corrected (API-SHAPE â†’ MATCH for 8 modules), attack order simplified
- `python-migration-progress.md`: Binding-ledger corrected (all major modules MATCH), next-action replaced with Python-only tasks

### Stubs Updated

**New (created):**
- `PySystem.pyi` â€” Console, window, environment, script_control, widget_manager
- `PyGameThread.pyi` â€” enqueue, clear_calls, is_in_game_thread
- `PyCallback.pyi` â€” Register, RemoveByName, Phase, Context
- `PyDXOverlay.pyi` â€” DXOverlay class (2D/3D drawing)
- `PyAgentEvents.pyi` â€” PyRawAgentEvent, enable/disable, get_and_clear_events

**Updated to match Reforged:**
- `PyAgent.pyi` â€” PyAgent class (getter methods), Profession, module-level functions
- `PyPlayer.pyi` â€” PyPlayer class (data + methods), PlayerStatus enum
- `PyParty.pyi` â€” PyParty/Hero/PartyTick/HeroPartyMember classes. **hero_id: int** (was Hero in legacy)
- `PyItem.pyi` â€” PyItem class (comprehensive data), ItemModifier, ItemTypeClass, DyeInfo
- `PyInventory.pyi` â€” Bag + PyInventory classes. Missing: IsSalvaging/FinishSalvage/GetItemByIndex/FindItemById
- `PyCamera.pyi` â€” PyCamera (data attrs + methods), Point3D
- `Py4GW/__init__.pyi` â€” Reduced to version() + SharedMemory only
- `PyKeystroke.pyi` â€” PyKeyHandler (renamed from PyScanCodeKeystroke)
- `PyOverlay.pyi` â€” Vec2f/Vec3f (renamed from Point2D/Point3D)
- `PyImGui.pyi` â€” Full 1.92.x surface: Window, Layout, Text, Widgets, Input, Combo, Selectable, Color, Image, Tree, Tabs, Tables, Legacy Columns, Menus, Popups, Tooltips, Cursor, Scroll, Item Query, ID/Focus, Keyboard, Mouse, Style, Clip Rect, Font, Clipboard, INI, Drag & Drop, Viewport, Plotting, Debug, Docking, DrawList (class + flat functions), IO

### Wrapper Fixes

| File | Change | Reason |
|---|---|---|
| `Agent.py:144,158,172` | `PyAgent.PyAgent.GetAgentEncName(id)` â†’ `PyAgent.get_agent_enc_name(id)` | Module-level function in Reforged |
| `Party.py:171` | `h.hero_id.GetID()` â†’ `h.hero_id` | hero_id is int in Reforged |
| `Party.py:502,517` | `hero.hero_id.GetID()` â†’ `hero.hero_id` | Same |
| `Party.py:555` | `hero.hero_id.GetName()` â†’ `PyParty.Hero(hero.hero_id).GetName()` | Must construct Hero from int |
| `Skillbar.py:1` | Removed `from PyAgent import AttributeClass` | Dead import |
| `modular/selectors.py:100` | `PyAgent.PyAgent.GetAgentEncName(id)` â†’ `PyAgent.get_agent_enc_name(id)` | Same as Agent.py |
| `GlobalCache/shared_memory_src/AllAccounts.py` | 5x `hero_data.hero_id.GetID()` â†’ `hero_data.hero_id` | Same |
| `GlobalCache/shared_memory_src/AccountStruct.py` | 2x hero_id.GetID()â†’hero_id, 1x GetName()â†’PyParty.Hero().GetName() | Same |
| `GlobalCache/PartyCache.py` | 2x GetID()â†’hero_id, 1x GetName()â†’PyParty.Hero().GetName() | Same |
| `GlobalCache/ItemCache.py:116` | `item.item_id` â†’ `item["item_id"]` | Bag.GetItems() returns dicts in Reforged |
| `GlobalCache/ItemCache.py:172` | `bag.FindItemById(id)` â†’ iterate `bag.GetItems()` dicts | Method removed |

### Import + Console/Game Repoints

- `Py4GWCoreLib/__init__.py`: Added PySystem, PyGameThread, PyCallback, PyDXOverlay, PyAgentEvents. Removed Py2DRenderer, PyCombatEvents. Logger â†’ PySystem.Console.
- **~25 files**: `Py4GW.Console.*` â†’ `PySystem.Console.*`, `Py4GW.Game.get_tick_count64()` â†’ `PySystem.get_tick_count64()`, `Py4GW.Game.enqueue()` â†’ `PyGameThread.enqueue()`
- `SkillManager.py`: `Py4GW.PingHandler()` â†’ `PyPing.PingHandler()`
- `Map.py`: `from Py4GW import Game; Game.InCharacterSelectScreen()` â†’ `import PySystem; PySystem.in_character_select_screen()`

### Dead Module Cleanup

- Removed `import PyPointers` from 11 context files (AccAgent, Char, Cinematic, Gameplay, Guild, Map, MissionMap, PreGame, Text, World, WorldMap)
- Removed `from Py4GW import Game` from context files
- Removed dead `import Py4GW` from KeyStruct.py, UI.py

### Shared Memory

- `PointersSSM.py`: Added `("Camera", c_void_p)` as 16th field
- `SysShaMem.py`: `Py4GW.Game.get_shared_memory_name()` â†’ `PySystem.get_shared_memory_name()`

### PyImGui

- Full stub written matching 682-line C++ binding
- `ImGui_Legacy.py` wrapper is a thin re-export â€” no changes needed
- `ImGuisrc.py` already had Py4GWâ†’PySystem fix applied
