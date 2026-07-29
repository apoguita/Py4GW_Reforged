# Pending fixes — a pool of known issues, deliberately not fixed yet

Issues found while working on something else. **Nothing here is in scope for the task that found it.**
Each entry is fixed only when it is explicitly scoped as its own task.

Recording an issue here is the correct action on finding one. Fixing it opportunistically is not —
unscoped "while I'm here" work is what produced two full reverts of the loot rework.

Format: what is wrong, the evidence, the blast radius, and what makes it non-trivial.

---

## PF-1 · `ItemType` weapon/armour classification contradicts itself

**Found:** 2026-07-26, while settling how the loot filter's item-type picker should group types.
**File:** `Py4GWCoreLib/enums_src/Item_enums.py`
**Status:** open — **do not fix as part of the loot work.**

### What is wrong

Three overlapping sets under two names, two of which disagree:

| name | count | members |
|---|---|---|
| `ItemType.Weapon` (meta-type) | 9 | Axe, Bow, Daggers, Hammer, Scythe, Spear, Staff, Sword, Wand |
| `WEAPON_TYPES` (from the `WeaponType` literal) | 11 | the same 9 **plus Offhand and Shield** |
| `EquippableItem` (meta-type) | 11 | **byte-identical to `WEAPON_TYPES`** |

So:

- `WEAPON_TYPES` duplicates `EquippableItem` exactly, while carrying a name that means something
  narrower elsewhere in the same file;
- `ItemType(Shield).is_weapon_type()` returns **True**, but `ItemType.Weapon.item_types()` does **not**
  contain Shield. The file gives two answers to "is a shield a weapon".

Secondary: `ARMOR_TYPES` (from the `ArmorType` literal) includes **`ItemType.Salvage`**, so
`is_armor_type()` is True for a salvage item. This may be deliberate — salvage-type armour drops
exist — but it is undocumented, and undocumented intent is indistinguishable from a bug.

*Not* wrong: the weapon subdivision is internally consistent —
`MartialWeapon` (7) + `SpellcastingWeapon` (2) = `Weapon` (9), with `OffhandOrShield` (2) outside it.

### The ambiguity has already leaked

`Py4GWCoreLib/Item.py` works around it in three places, inconsistently:

```python
:454  if not item_type.is_weapon_type() and not item_type in [Offhand, Shield]:   # redundant - is_weapon_type() already includes both
:466  if not item_type.is_armor_type()  and not item_type == Shield:              # Shield treated as ARMOUR here
:478  if not item_type.is_armor_type()  and not item_type in [Offhand, Staff]:
```

Shield is a weapon at `:454` and armour at `:466`.

And `Sources/marks_sources/mods_parser.py:57,73` declares its **own** `WEAPON_TYPES` / `ARMOR_TYPES` —
a fourth and fifth definition of the same idea.

### Blast radius

Roughly 25 consumers across `Py4GWCoreLib/Item.py`, `Sources/frenkeyLib/`, and
`Sources/marks_sources/`. `is_weapon_type` and `is_armor_type` each have 6 call sites;
`WEAPON_TYPES` has 13.

### What makes it non-trivial

The redundancy at `Item.py:454` is load-bearing to check, not obviously deletable: removing it changes
behaviour for anyone relying on the broader reading. Deciding *which* definition is correct is a
semantic call about the game, not a refactor — and every consumer has to be re-read against whichever
answer is chosen.

### Why it was not fixed on discovery

The loot work does not need it. The loot filter can choose which definition its Weapons group uses
without touching the enum. Fixing a shared enum with 25 consumers, from inside an unrelated feature,
is precisely the unscoped drift that caused the previous reverts.

---

## PF-2 · Merchant Rules is a monolith that has absorbed other systems' responsibilities

**Found:** 2026-07-26, while surveying item-handling ownership.
**File:** `Widgets/Guild Wars/Items & Loot/MerchantRules.py` — **30,119 lines**, one `MerchantRulesWidget`
class spanning `:4712`–`:30088`.
**Status:** open — candidate for **replace / split**, not for an in-place fix.

### What is wrong

The widget is named for merchant interaction, but it now owns salvaging, identifying, destroying,
storage deposits/withdrawals, loot classification, mod parsing, travel routing, profile management and
multibox fan-out. Each of those already has an owner elsewhere, so the same behaviour exists two or
three times with different rules and different bugs. Whichever system runs last wins.

Overlapping owners of the same behaviour:

| behaviour | Merchant Rules | the other owner(s) |
|---|---|---|
| salvage decisions + salvage-option choice | `_run_salvage_pass` `:20555`, `_MerchantRulesExactUpgradeSalvageBridge` `:1787` | `Sources/frenkeyLib/LootEx/inventory_handling.py:99` + `LootEx/salvaging.py`; `Routines.Yield.Items.SalvageItems` |
| identify pass | `_run_identify_pass` `:19818` | `Routines.Yield.Items.IdentifyItems` |
| destroy | `_run_destroy_pass` `:20683`, `_run_instant_destroy_pass` `:20785` | `Routines.Yield.Items.DestroyItem`; `SuperItemEater.py` / `item_eater.py` |
| storage deposit / withdraw | `_execute_storage_transfers` `:16910`, `_plan_cleanup_actions` `:12801` | `Xunlaimanager.py` (3,349 lines); `Routines.Yield.Items.DepositItems` |
| buy / sell / restock | `_plan_buy_actions` `:13861`, `_execute_merchant_sell_phase` `:18237` | `Routines.Yield.Merchant.RestockKitsToTarget` / `SellItems` / `BuyMaterial` / `SellMaterialsAtTrader` |
| item rules & mod matching | ~90 module-level normalizers, `Sources/marks_sources/mods_parser` | `Sources/frenkeyLib/ItemHandling/{Rules,Mods,Handlers}`; `LootEx/filter.py`, `item_configuration.py` |
| loot policy | rarity flags, whitelists, protections | `LootManager.py`, `InventoryPlus.py`, and the in-flight redesign in `docs/loot_redesign/` |

### Evidence it bypasses, rather than uses, the shared layer

- It reaches into **private** `Routines.Yield.Merchant` internals in 10 places, each with a
  `# pylint: disable=protected-access` — `:16354, :16441, :16618, :16663, :16701, :16731, :16792,
  :16813, :16824, :16862` (`_wait_for_transaction`, `_interact_with_trader_xy`, `_wait_for_quote`,
  `_wait_for_stack_quantity_drop`). The public generators exist; it uses the guts instead.
- It queues raw `Inventory.SalvageItem` `:20141` and `Inventory.IdentifyItem` `:19796` onto
  `ActionQueueManager` directly, re-implementing kit selection, throttling and dialog handling that
  `Routines.Yield.Items` already implements.
- It defines its **own** salvage-option taxonomy (`SALVAGE_OPTION_DEFAULT / MATERIALS / AUTO_UPGRADE /
  PREFIX / SUFFIX / INSCRIPTION`, `:293`+) alongside LootEx's `SalvageOption` enum
  (`CraftingMaterials / LesserCraftingMaterials / RareCraftingMaterials / Prefix / Suffix / Inherent`).
  Two names for one game dialog.
- `PROFILE_VERSION = 32` — thirty-two migrations of a config schema that keeps growing because every
  new responsibility lands in the same document.

### Blast radius

Self-contained as a file (nothing imports it), so the *code* has no downstream consumers. The
**runtime** blast radius is the problem: it acts on the whole inventory, it can auto-run
(`auto_cleanup_on_outpost_entry`, identify-before-execute, auto-travel), and it broadcasts execute
and cleanup commands to other accounts over `ShMem` `:22145`+. Any script that also salvages, deposits
or destroys is racing it, and the loot redesign cannot define "who decides what happens to an item"
while this widget answers that question independently.

### What makes it non-trivial

There is no seam to cut on. Planning, execution, UI and persistence are interleaved inside one class —
`_build_plan` `:14732` alone takes 11 keyword flags and returns a `PlanResult` with 30 fields that the
UI, the executor and the preview all read. Extracting salvage means extracting the protection system
(`_get_protected_hit_reason` `:10843`, `_get_equippable_hard_protection_reason` `:11165`, the whole
Protections workspace), which is shared by sell, destroy and cleanup. And the rule schema is the user's
saved data: any split has to carry 32 profile versions forward or explicitly break existing configs.

### Why it was not fixed on discovery

It is not a bug, it is a scope decision — whether Merchant Rules keeps owning salvage/identify/destroy
or hands them back to the shared routines and the loot system. That decision belongs to the loot
redesign, and making it opportunistically would be a rewrite of the single largest file in the repo.

---

## PF-3 · `Sources/frenkeyLib/` was severed by the Reforged migration and never carried across

**Found:** 2026-07-26, following PF-2 — the other half of the item-handling ownership problem.
**Path:** `Sources/frenkeyLib/` — 30,991 lines of Python + **~21 MB of bundled JSON**.
**Status:** open — **needs a migration**, plus a scope decision on the parts worth migrating.
**Severance audit:** `docs/migration_to_reforged/frenkeylib_severance_audit.md` — 168 real pyright
errors, the per-file breakdown, and a tiered migration scope. **Read that first; PF-3 is the summary.**
**See also:** `docs/item_mods/04_frenkeylib_reference.md` and `05_comparison_and_painpoints.md`
document the mod-model half.

### The headline

`frenkeyLib` was left behind when the library was repointed from the GWCA binding surface to Reforged
Native. It still imports, so nothing flagged it — but it calls bindings that were removed and reads a
data shape that changed, and **one of those breaks is in the core library's salvage path**:

`Py4GWCoreLib/py4gwcorelib_src/AutoInventoryHandler.py:411` drives salvage through
`ItemHandling/BTNodes.py`, which calls `IsSalvaging()`, `IsSalvageTransactionDone()` and
`FinishSalvage()` — all three removed in Reforged, as `stubs/PyInventory.pyi:3` states explicitly.
`BTNodes.py:913-932` wraps each in a bare `except Exception`, so the transaction-completion branch is
now permanently dead and salvage falls back to a heuristic that is biased toward declaring success
early. Silent, on every account, with nothing logged. Likewise `Bag.GetItems()` now returns dicts, not
objects, so `item_snapshot.py:411`, `item_collecting.py:97` and `utility.py:39` raise `AttributeError`
on attribute access that used to work.

### What is wrong

Nine subsystems under one folder with no shared contract, three different relationships to the core
library, and no statement of which are live:

| subsystem | lines | reached from outside `frenkeyLib`? |
|---|---|---|
| `LootEx/` | **12,336** | **no — zero importers anywhere in the repo** |
| `ItemHandling/` | 3,983 | yes, but only via 5 lazy imports inside `Py4GWCoreLib` (below) |
| `Py4GWLibrary/` | 1,573 | **no** — only by a file in `Drafts/` |
| `Core/` | 3,190 | **no** — used only by other `frenkeyLib` subsystems |
| `MultiBoxing/`, `PartyQuestLog/`, `Polymock/`, `SulfurousRunner/` | ~2,700 | yes — each backs one widget |
| `Drafts/` | ~1,900 | no — three unfinished files, one with a typo in its name (`SimlpeTree`) |

So the two biggest things in the folder — LootEx (12.3k lines, `gui.py` alone is 6,110 with a single
5,830-line `UI` class) and Py4GWLibrary (a second widget-launcher UI, superseded by the launchpad) —
ship and are maintained but cannot currently run. LootEx does not even import-resolve: two of its
`Py4GWCoreLib` imports point at deleted modules. That is the clearest sign this is severance rather
than deliberate retirement — nobody switched it off, it simply stopped being reachable and no one
noticed, because no entry point exercises it.

### Evidence

**LootEx is unreachable.** `grep -rn "LootEx" --include=*.py` outside its own folder returns six hits,
none of them an import: an enum member (`SharedCommandType.LootEx`), a comment in `mods_parser.py`, a
tooltip and a comment in two widgets, a `sys.path` string in `InventoryPlus.py`, and a message-router
`case` in `Widgets/System/Messaging.py:2823`. Nothing constructs it, nothing draws it. It is a complete
loot engine — rules, GUI, profiles, salvaging, trading, price checks, crafting, texture scraping — with
no entry point.

**Layering inversion.** `Py4GWCoreLib/py4gwcorelib_src/AutoInventoryHandler.py` — core library, layer 3 —
imports *upward* into a contributor source folder, five times, all as function-level lazy imports to hide
the dependency: `:138-139` (`ItemSnapshot`, `INVENTORY_BAGS`), `:231` (`SalvageMode`), `:339` and `:362`
(`BTNodes`). Core identify and salvage therefore run on `Sources/frenkeyLib/ItemHandling/BTNodes.py`
(1,566 lines: `BTNodes.Merchant`, `.Trader`, `.Items`, `.Bags`, `.Crafting`) — a full parallel action
layer to `Routines.Yield.*`. Deleting or moving `frenkeyLib` breaks `Py4GWCoreLib`.

**Three copies of the same catalogs, ~21 MB.**

```
Sources/frenkeyLib/LootEx/data/items.json            3.68 MB
Sources/frenkeyLib/LootEx/data/items copy.json       3.26 MB   <- committed working copy
Sources/frenkeyLib/LootEx/data/items copy 2.json     3.82 MB   <- committed working copy
Sources/frenkeyLib/LootEx/data/scraped_items.json    5.42 MB
Sources/frenkeyLib/ItemHandling/Items/items.json     3.94 MB   <- a different item catalog
Sources/frenkeyLib/LootEx/data/runes.json            339 KB    +  "runes copy.json"       321 KB
Sources/frenkeyLib/LootEx/data/weapon_mods.json      207 KB    +  "weapon_mods copy.json" 174 KB
Sources/marks_sources/mods_data/runes.json           339 KB    <- third copy of the same file
Sources/marks_sources/mods_data/weapon_mods.json     207 KB    <- third copy
```

`mods_parser.py:445` states outright that it parses "the exact format saved by LootEx
`Data.SaveRunes()` / `Data.SaveWeaponMods()`" — a live consumer coupled to a dead producer's file
format, fed from its own private copy of the output.

**Persistence rules only half-applied.** `LootEx/settings.py` and `ItemHandling/GlobalConfigs/RuleConfig.py`
were migrated to `JsonFactory`, but 62 raw `open()` / `json.load` / `json.dump` sites remain, including
writes to paths derived from `__file__` with `os.makedirs` (`LootEx/data.py:890-935`, and again at
`:947, :1010, :1030, :1062, :1084, :1181, :1189`). Those write *inside the repo tree*, outside the
`/json` jail, which is exactly what PF-adjacent path-jail work exists to prevent.

**Correctness smells in the dead code.** `LootEx/api.py` decorates module-level functions with
`@staticmethod` (`:11` `DepositMaterials`, and following) — a no-op outside a class body; the functions
are unusable as written on some paths. `LootEx/weaponmods.py` is a 5-entry stub that shadows the real
model in `models.py` (already flagged in `docs/item_mods/04`). Neither has been caught because nothing
runs this code.

**Duplicate decoders and mod models**, per `docs/item_mods/05` §8-9: `frenkeyLib/Core/encoded_names.py`
(1,308 lines) near-duplicates `native_src/internals/string_table.py`, and `LootEx/models.py` (1,815) is
one of three parallel "decode a mod" implementations alongside `Py4GWCoreLib/item_mods_src` and
`marks_sources/mods_parser.py`.

### Blast radius

Small in code, large in confusion. Only four widgets and one core file import anything here, and the
live subsystems (MultiBoxing, PartyQuestLog, Polymock, SulfurousRunner) are cleanly one-widget-each.
The cost is that ~16k lines and ~21 MB of dead assets sit next to live ones with no marker, so every
audit of "how does this repo handle items" has to read LootEx before discovering it never runs — and
new work keeps mining it for patterns (`mods_parser.py` did exactly that).

### What makes it non-trivial

The migration and the scope decision are entangled. `ItemHandling` must be migrated regardless — the
core library runs on it — but its replacement is not `Routines.Yield.*` as-is: `BTNodes.Items.SalvageItem`
(`:690`) carries salvage-dialog handling the yield routines do not have, so migrating it means first
deciding whether that handling moves into the core or stays vendored. `LootEx` cannot be migrated
cheaply (it does not import-resolve at all — `MerchantHandler` and `SF_Ass_vaettir` are gone, and it
hijacks a deleted singleton) and cannot be deleted cheaply either, because its *data format* is
load-bearing for `mods_parser.py`, which `MerchantRules` (PF-2) depends on.

Order that works: fix the live core breakage first (Tier 1 of the audit — independent of everything
else), then decide item ownership (PF-2), then decide which frenkeyLib subsystems get migrated and
which are retired.

### Why it was not fixed on discovery

Tier 1 is a real bug and should be scoped as its own task — but it is a core-library salvage change,
not something to slip in from an unrelated survey. Everything past Tier 1 is a project decision about
16k lines of a contributor's code, which is not a cleanup call to make unilaterally.

---

## PF-4 · `agent_recolor` asks the user to type ids as CSV, and keys rules by uuid

**Found:** 2026-07-26, while using `agent_recolor` as the cohesion reference for the loot filter editor.
**Files:** `Py4GWCoreLib/py4gwcorelib_src/agent_recolor/config_ui.py`, `controller.py`
**Status:** open — **rework**, not a bug fix.

### What is wrong

**1 · Ids are entered as comma-separated text.**

```python
:132  _ui.buffers[mk] = PyImGui.input_text("Model IDs (csv)##%s" % mk, _ui.buffers[mk])
:137  _ui.buffers[pk] = PyImGui.input_text("Profession IDs (csv, prim/sec)##%s" % pk, ...)
:178  _ui.buffers[ak] = PyImGui.input_text("Agent ID (pin one)##%s" % ak, ...)
```

The user is asked to know and type numeric ids. Meanwhile the repository already contains a solved
interface for exactly this — Inventory+'s two-pane picker
(`Sources/ApoSource/InvPlus/AutoHandlerModule.py:119-190`): a search box, Contains / Starts With, a
left pane of every `ModelID` member sorted by name, a right pane of the chosen set, click to add, click
to remove. Nothing needs typing and no id needs memorising.

The CSV approach also costs a whole support mechanism: **17 uses of `_ui.buffers`** exist purely so
half-typed text survives a frame without being parsed and reformatted under the cursor. A picker needs
none of it.

**2 · Rules are keyed by `uuid4().hex`.**

```python
:110  rule = model.Rule(id=uuid.uuid4().hex, name="New rule", scope=scope)
:130  clone.id = uuid.uuid4().hex          # duplicate
:162  r.id = uuid.uuid4().hex              # on import
```

The rules live in **one document at one scope** — `Widgets/System/Agent Recolor.ini`, `[rules] list`,
a JSON string. Within a single list, a short sequential id is unique by construction. A 32-character
random hex per rule buys nothing there and makes the stored JSON unreadable and un-hand-editable.

The one place it has a defensible motive is the share box (`config_ui.py:333-343`,
`controller.export_json` / `import_json`): pasted foreign rules could collide with existing ids. But
that is solved by renumbering on import — which the code *already does* at `:162` — so the uuid is not
what makes import safe.

**3 · Sharing is raw JSON copy-pasted through a textarea.**

`config_ui.py:330-345`, in the Status tab:

```
Share rules (global list)
[Export -> box]  [Import (replace)]  [Import (append)]
+-- multiline text box, 120px ------------------+
```

**Export -> box** dumps the whole rule list as JSON into the box for the user to select and copy by
hand; importing means pasting JSON back in. That is a developer's debugging affordance presented as a
user feature, and it is the module's only sharing path.

**What it should be:** *export to a file, saved wherever the user chooses; import from a file into our
own store.* **Never through the clipboard.**

Note this also removes the last argument for uuid ids — the only collision the uuid guards against is
between two hand-pasted JSON blobs, and `import_json` renumbers on import anyway (`controller.py:162`).

### Blast radius

Self-contained. `agent_recolor` is one package plus its System Settings section; the rule list is its
own document. Changing the id scheme needs a migration for rules already saved, or acceptance that
existing ids stay as they are and only new ones are short.

### What makes it non-trivial

The CSV inputs and the `_ui.buffers` machinery are load-bearing together — removing one means removing
the other. And the ids are user data: whatever replaces uuid has to read the existing hex ids without
discarding rules the user already made.

### Why it was not fixed on discovery

It was being read as a *reference*, not worked on. Its patterns were about to be copied into the loot
filter editor — the CSV inputs were **not** copied (A1 settled on the Inventory+ picker instead), and
the uuid scheme was proposed and rejected for the same reason it is questionable here.

---

## PF-5 · DXOverlay 3D drawing costs ~6x what the same geometry costs on ImGui

**Found:** 2026-07-27, while fixing the aC library's 3D-draw freeze.
**Files:** `Py4GW_Reforged_Native/src/overlay/dx_overlay.cpp`, `src/GW/world_render/world_render.cpp`
**Status:** open — **unexplained; needs a measurement before any further change.**
**Full record:** `docs/overlay_3d_performance_issues.md` — what was fixed, what was reverted, and
the exact next diagnostic. **Read that first; PF-5 is the summary.**

### What is wrong

Drawing a BottingTree move path through `DXOverlay` runs at **9 fps**. The same path, same geometry,
on the ImGui surface runs at **60 fps**. Both go through the same Direct3D 9 device.

Three explanations were tested and each ruled out:

| suspected cause | how it was ruled out |
|---|---|
| the depth test / occlusion | the surface toggle and the occlusion toggle were split; DirectX is equally slow with occlusion **off** |
| fill / rasterisation | DXOverlay draws 1-pixel unantialiased lines, ImGui draws thick antialiased ones — less pixel work, still 6x slower |
| draw-call count | a batching change (one `DrawPrimitiveUP` per group instead of per primitive) was built and did **not** recover the framerate |

### Leading suspect — not yet measured

`GW::world_render` invokes its callbacks at DDI opcode **`0x1E`, not at present**
(`world_render.cpp:87`; 0x0F/present is too late, depth is already discarded there). `0x1E` fires
several times per frame. On each firing `DXOverlay::OccludedTick` deep-copies the entire command list
(`local = m_draw_list` — N `std::function` copies, each heap-allocating) and **re-executes every
queued command**, recomputing lerps, calling `findZ` and rebuilding vertices, before the batched
flush. Batching removed the submissions but left that per-pass work untouched.

60 -> 9 fps is ~94 ms added per frame, which is the right order for a few dozen full rebuilds of a
few hundred commands.

**The measurement that settles it** (the dispatcher already counts it):

```python
import PyWorldRender
print(PyWorldRender.get_diagnostics())
```

Sample twice, a second or two apart, while a path draws in DirectX mode. `drawn` is the present count
(frames), `cbs` is callback invocations (drains). **`Δcbs / Δdrawn` is the replay multiplier.** If it
is ~1 the suspect is wrong and the cost is elsewhere; if it is large, the fix is to build the vertex
batch once per frame and only *submit* it per pass.

### Blast radius

Every consumer of DXOverlay's 3D drawing: `Py4GWCoreLib/py4gwcorelib_src/map_overlay/terrain.py`,
`Sources/frenkeyLib/SulfurousRunner/ui.py`, `loot_beam.py`, `light_beacon.py`, the ApoSource demo,
and BottingTree's optional DirectX path mode. In practice it caps any 3D overlay feature at a few
dozen primitives — occlusion is only available through DXOverlay, so anything wanting *both*
occlusion and volume is currently blocked.

Not affected: everything drawing through `Overlay` (the ImGui draw list), which is most of the repo —
HeroAI range rings, BottingTree by default, the botting-tree waypoint UI, the pathing examples.

### What makes it non-trivial

It is a Native change in a hot path, and it cannot be diagnosed from the Python side. Five
reasoning-only attempts were already made and reverted (listed in the troubleshooting doc): shared
draw list, plane-list cache + coverage grid + context hoist, a two-table findZ cache, and a shared
world-render registration. All were argued convincingly and all measured neutral or worse.

The lesson that came out of it is the constraint on the next attempt: **measure first, ship one
change per build, and state exactly what else is already live in that build.**

### Why it was not fixed on discovery

The task that found it was the aC freeze, which is fixed. This is a separate, pre-existing property
of DXOverlay that only became visible once the freeze was gone. Continuing without the replay
measurement would be a sixth guess.
