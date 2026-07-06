# Migration to Reforged — Session Log

## Session 1 — 2026-07-06: Intake + Stub Audit

### Architecture Discovery

The Python library accesses game state through **two parallel data paths**:

1. **Bindings path** (`Py*` embedded modules): Callable methods like `PyAgent.get_agent_enc_name()`, `PyPlayer.PyPlayer().ChangeTarget()`, `PyParty.PyParty().AddHero()`
2. **Context path** (ctypes structs from shared memory): Data fields like agent position, health, level — read from `AgentStruct`, `AgentLivingStruct`, etc. via `SystemShaMemMgr`

The stubs at `stubs/*.pyi` define the binding module surface that the wrapper classes (`Agent.py`, `Player.py`, `Party.py`, etc.) consume.

### Stub Gap Analysis

Compared legacy stubs against Reforged Native C++ bindings:

| Stub | Status | Gap |
|---|---|---|
| `PyAgent.pyi` | **NEEDS UPDATE** | Legacy: `PyAgent` has data fields (`.x`, `.y`, `.z`, `.rotation_angle`, `.is_living`, `.living_agent`, etc.) + static `GetAgentEncName`. Reforged: `PyAgent` has getter methods (`.GetAgentID()`, `.GetPos()`, `.GetHP()`, etc.) + module-level `get_agent_enc_name()`. **However** `Agent.py` wrapper reads data from ctypes context structs, not PyAgent — so the data-field gap may not affect it. Only `PyAgent.PyAgent.GetAgentEncName()` (static) is used by Agent.py. |
| `PyPlayer.pyi` | **NEEDS UPDATE** | `agent: PyAgent` field type may differ. Otherwise methods match. |
| `PyParty.pyi` | **NEEDS UPDATE** | `HeroPartyMember.hero_id` is `Hero` in legacy (confirmed in `py_party.h:128`) but `int` in Reforged (confirmed in `party_bindings.cpp:68`). Python code at `Party.py:171` does `hero.hero_id.GetID()` — will break. `HeroPartyMember.primary`/`secondary` are `Profession` in legacy but `int` in Reforged. |
| `PyCamera.pyi` | MATCH | Reforged has data attributes + methods matching the stub. |
| `PyEffects.pyi` | MATCH | EffectType, BuffType, PyEffects all preserved. |
| `PyMerchant.pyi` | MATCH | PyMerchant class preserved. |
| `PyQuest.pyi` | MATCH | QuestData, PyQuest preserved. |
| `PyItem.pyi` | **NEEDS UPDATE** | Legacy `PyItem` has many data fields (`.rarity`, `.item_type`, `.modifiers`, etc.). Reforged `PyItem` has `.item_id`, `.GetName()`, `.RequestName()`, `.IsItemNameReady()`, static methods. |
| `PyInventory.pyi` | **NEEDS UPDATE** | Legacy `Bag` has `GetItemByIndex()`, `FindItemById()`. Reforged `Bag` has `.GetItems()`, `.GetSize()`, `.id`, `.name`. Legacy `PyInventory` has `.IsSalvaging()`, `.IsSalvageTransactionDone()`, `.FinishSalvage()`. Reforged may not have these. |
| `Py4GW/Console.pyi` | **RELOCATED** | Functions moved to `PySystem.Console` |
| `Py4GW/Game.pyi` | **RELOCATED** | Functions split between `PySystem` and `PyGameThread` |
| `PyPointers.pyi` | **DEAD** | Module retired; pointers in shared memory |
| `Py2DRenderer.pyi` | **DEAD** | Renamed to `PyDXOverlay` |
| `PyCombatEvents.pyi` | **DEAD** | Renamed to `PyAgentEvents` |

### Attack Plan

1. Update stubs to match Reforged surface (this session)
2. Migrate wrapper classes against updated stubs
3. Console/game repoints
4. Shared memory fixes (Camera field)
