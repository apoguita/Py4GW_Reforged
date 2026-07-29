# frenkeyLib — Severance Audit

**Date:** 2026-07-26
**Scope:** `Sources/frenkeyLib/` (30,991 lines, 9 subsystems) against the current Reforged Native
binding surface and the current `Py4GWCoreLib`.
**Purpose:** `frenkeyLib` was never carried through the GWCA → Reforged migration. It still compiles
and imports, but it calls APIs that no longer exist and reads data shapes that changed. This is the
list of what is severed, so a migration can be scoped.

**Related:** `docs/pending_fixes.md` PF-2 (Merchant Rules) and PF-3 (frenkeyLib reachability).
`docs/item_mods/04_frenkeylib_reference.md` documents the mod-model side.

---

## 0. How this was measured

```
npx pyright --outputjson Sources/frenkeyLib
```

**223 diagnostics, all severity `error`.** 55 of them (`PySystem` ×54, `PyGameThread` ×1) are the
known builtins-injection false positive — those names are injected into `builtins` by
`Py4GWCoreLib/__init__.py` and are valid at runtime. **168 are real.**

| rule | count | note |
|---|---|---|
| `reportUndefinedVariable` | 109 | 55 are the builtins false positive; **54 are a real missing `Console` import** |
| `reportAttributeAccessIssue` | 58 | removed bindings + changed data shapes |
| `reportArgumentType` | 21 | mostly `list` passed where `tuple[float × 4]` is required |
| `reportCallIssue` | 20 | |
| `reportMissingImports` | 5 | modules deleted from `Py4GWCoreLib` |
| `reportOptionalMemberAccess` / `reportGeneralTypeIssues` / `reportIncompatibleMethodOverride` | 8 | |

By file (errors, excluding the builtins false positive):

| file | errors | live? |
|---|---|---|
| `LootEx/gui.py` | 49 | no |
| `Py4GWLibrary/library.py` | 28 | no |
| `LootEx/trading.py` | 20 | no |
| **`ItemHandling/BTNodes.py`** | **18** | **yes — called by `Py4GWCoreLib`** |
| `LootEx/salvaging.py` | 17 | no |
| `LootEx/crafting.py` | 16 | no |
| `Drafts/*` (3 files) | 32 | no |
| `LootEx/inventory_handling.py` | 7 | no |
| **`ItemHandling/Handlers/InventoryHandler.py`** | **6** | **yes** |
| **`ItemHandling/Items/item_snapshot.py`** | **4** | **yes** |
| `SulfurousRunner/ui.py` | 4 | yes |
| **`ItemHandling/Items/item_collecting.py`**, **`ItemHandling/utility.py`** | 3 each | **yes** |
| `MultiBoxing/gui.py`, `MultiBoxing/window_handling.py` | 2 each | yes |
| `LootEx/models.py`, `LootEx/texture_scraping.py`, `LootEx/utility.py` | 2–3 each | no |

---

## 1. The severance that matters: core salvage runs on removed bindings

`Py4GWCoreLib/py4gwcorelib_src/AutoInventoryHandler.py` — **core library** — drives identify and
salvage through `frenkeyLib`:

```python
:346  node = BTNodes.Items.IdentifyItems([item_id], ...)
:411  node = BTNodes.Items.SalvageItem(...)
```

`ItemHandling/BTNodes.py:913-932` calls three bindings that **Reforged does not have.**
`stubs/PyInventory.pyi:3` says so outright:

```
# NOTE: IsSalvaging(), IsSalvageTransactionDone(), FinishSalvage() NOT in Reforged.
#       GetItemByIndex(), FindItemById() NOT in Reforged Bag.
```

And `BTNodes.py` swallows the failure rather than reporting it:

```python
:914  try:    is_salvaging = bool(inventory_instance.IsSalvaging())
:916  except Exception: is_salvaging = False          # <- always taken now
:919  try:    transaction_done = bool(inventory_instance.IsSalvageTransactionDone())
:921  except Exception: transaction_done = False      # <- always taken now
:924  if transaction_done:                            # <- now unreachable
:927      inventory_instance.FinishSalvage()          # <- never called
```

**Consequence:** the transaction-completion branch is dead. Salvage completion now falls through to
the heuristic at `:940-960` — `qty_changed or item_gone or windows_closed_after_confirm or
mod_salvaged` — and `windows_closed_after_confirm` itself depends on `not is_salvaging`, which is
now permanently `True`. So the detector is both less precise *and* biased toward declaring success
early, on every account, silently. The `except Exception` means nothing is logged.

This is the single highest-priority item: it is a live, silent behaviour change in the core library's
salvage path, caused by the migration, hidden by a bare except.

## 2. `Bag.GetItems()` changed shape — objects became dicts

Reforged `Bag.GetItems()` returns `List[Dict[str, Any]]` with keys
`{"item_id", "slot", "model_id", "quantity"}` (`stubs/PyInventory.pyi:21-22`). `frenkeyLib` still
treats the entries as objects with attributes:

| site | code | result at runtime |
|---|---|---|
| `ItemHandling/Items/item_snapshot.py:411-413` | `entry.slot`, `entry.item_id` | `AttributeError` |
| `ItemHandling/Items/item_collecting.py:97-98` | `entry.slot`, `entry.item_id` | `AttributeError` |
| `ItemHandling/utility.py:39-40` | `entry.slot`, `entry.item_id` | `AttributeError` |

All three are in the **live** path — `item_snapshot.ItemSnapshot.get_bags_snapshot` is what
`AutoInventoryHandler:138-139` calls to enumerate inventory.

Additionally `item_snapshot.py:41` calls `PyInventory.Bag(...).FindItemById(item_id)`, also removed
per the stub note above.

## 3. Deleted `Py4GWCoreLib` modules still imported

| import | site | status |
|---|---|---|
| `Py4GWCoreLib.py4gwcorelib_src.MerchantHandler` | `LootEx/instance_manager.py:27`, `LootEx/inventory_handling.py:11` | **module deleted** |
| `Py4GWCoreLib.Builds.SF_Ass_vaettir` | `LootEx/inventory_handling.py:5` | **module deleted** |
| `Sources.frenkeyLib.Py4GWLibrary.enum` | `Drafts/Py4GW Library.py:20` | never existed |
| `Sources.frenkeyLib.Py4GWLibrary.module_cards` | `Drafts/Py4GW Library.py:22` | never existed |

`LootEx/inventory_handling.py:175` also subclasses the deleted `MerchantHandler`
(`class LootEx_Merchant_Handler(MerchantHandler)`) and at `:2207` / `:2226` reassigns
`MerchantHandler._instance` to hijack the singleton — a pattern with no counterpart in the current
core. These files fail at import time today.

## 4. Retired core APIs still called

| call | site(s) | Reforged replacement |
|---|---|---|
| `Console.is_window_active()` | `MultiBoxing/window_handling.py:42`, `LootEx/data_collection.py:590` | `PySystem.Console.*` |
| `Console.set_window_title()` | `MultiBoxing/window_handling.py:50` | `PySystem.Console.*` |
| `Settings.find(...)` | `Drafts/*` ×6 | removed — `Settings.py:66` states there is no separate ensure/find step |
| `WidgetHandler.pause_widgets()` / `.resume_widgets()` | `Drafts/*` ×4 | removed by the launchpad migration; per-widget `Widget.pause()` / `.resume()` exist |

Note `MultiBoxing/window_handling.py` is **live** (backs `Widgets/Guild Wars/Customization/MultiBoxing.py`).

## 5. Missing `Console` import — 54 sites

`LootEx/trading.py` (20), `LootEx/salvaging.py` (17), `LootEx/crafting.py` (16) and
`MultiBoxing/gui.py:816` (1) reference `Console.MessageType` without importing `Console`. These files
previously relied on `from Py4GWCoreLib import *` re-exporting it. `MultiBoxing/gui.py` is live, so
that one raises `NameError` on any logging path that reaches it.

## 6. Colour tuples

21 `reportArgumentType` errors, mostly `list[float]` passed where the ImGui wrapper now requires
`tuple[float, float, float, float]` — `SulfurousRunner/ui.py:133-139`, `MultiBoxing/gui.py:391`, and
others. Live subsystems. Mechanical fix.

---

## Migration scope

Ordered by risk, not by size.

**Tier 1 — live breakage in the core path (do first, independent of any other decision).**
1. `BTNodes.py` salvage completion: replace `IsSalvaging` / `IsSalvageTransactionDone` /
   `FinishSalvage` with the Reforged equivalent (`Salvage`, `AcceptSalvageWindow`, plus
   `UIManagerExtensions` window state), and **remove the bare `except Exception`** that hid the
   removal. Decide deliberately what the completion predicate is.
2. `Bag.GetItems()` dict shape: `item_snapshot.py`, `item_collecting.py`, `utility.py`.
3. `Bag.FindItemById` at `item_snapshot.py:41`.

**Tier 2 — live subsystems, cheap.**
4. `Console` → `PySystem.Console` in `MultiBoxing/window_handling.py`.
5. Missing `Console` import in `MultiBoxing/gui.py`.
6. Colour tuples in `SulfurousRunner/ui.py`, `MultiBoxing/gui.py`.

**Tier 3 — blocked on a scope decision (PF-3).**
7. `LootEx/` (12,336 lines) does not import-resolve today and has no entry point. Migrating it means
   restoring `MerchantHandler`, replacing the singleton hijack, and adding the 53 missing `Console`
   references — before any of its own logic is even reviewed. Whether that happens depends on whether
   LootEx is meant to come back.
8. `Py4GWLibrary/` (1,573 lines) is a widget-launcher UI superseded by the launchpad. Migrating it
   means re-targeting a UI that has a live replacement.
9. `Drafts/` — 3 unfinished files, 32 errors, imports that never existed. Nothing to migrate.

**Not in this audit:** the duplicated catalogs (~21 MB, three copies of `runes.json` /
`weapon_mods.json`) and the raw-`open()` persistence sites that write inside the repo tree. Those are
recorded in PF-3 and are a separate cleanup.

---

## Reference: legacy twin

`C:\Users\Apo\Py4GW_python_files\Sources\frenkeyLib\` holds the pre-migration tree with the same
9-subsystem layout. Every file differs from the current copy, so the current state is *partially*
migrated, not untouched — diff against the twin before assuming any given break is original.
`ItemHandling/ConfigExamples/ExampleGUIs/LootConfigView.py` exists only in the legacy tree.
