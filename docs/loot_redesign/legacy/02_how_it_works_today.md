# How looting works today — verified ground truth

**Every statement here was checked against the code.** Line numbers are current as of this pass. Where
an earlier version of this doc was wrong, the correction is marked **[was wrong]**. Nothing here is
inferred; if something could not be confirmed it says so.

---

## 1. THE CATALOGS — read this first

There are **two different catalogs**, and they are not interchangeable. Getting this wrong is what
broke the previous implementation attempt.

| | catalog A | catalog B |
|---|---|---|
| file | `json/Defaults/Widgets/LootManager/modelid_drop_data.json` | `Py4GWCoreLib/py4gwcorelib_src/Lootconfig_src.py:9-531` (`LootGroups`) |
| shape | JSON **array**, 403 entries | `Dict[str, Dict[str, List[ModelID]]]`, 395 entries |
| per item | `name`, `model_id`, `group`, `subgroup`, `drop_info` — **all 5 on all 403** | a bare `ModelID` member (name derived from `.name`) |
| `model_id` type | **string** `"ModelID.Foo"` (403/403, zero ints) | `ModelID` enum member |
| read by | **the Loot Manager widget** (`LootManager.py:44`) | `AutoInventoryHandler.py:458`, `InvPlus/LootModule.py:102` |

**[was wrong]** The old doc said "`LootGroups` … is just a model list the menu reads." That is true of
the **InvPlus** panel only. **The Loot Manager never imports or touches `LootGroups`** — it reads
catalog A (`LootManager.py:44,57-59,254`). The previous build started from `LootGroups` and therefore
silently dropped 15 items the widget's users can actually see.

**Structure (both catalogs):** 11 groups, 49 subgroups. Identical group/subgroup **placement** for
every shared item (0 differences). Trophies is 23 alphabet buckets A–W (no X/Y/Z).
Counts (A / B): Alcohol 15/15 · Sweets 13/13 · Party 7/7 · Death Penalty Removal 1/1 · Scrolls 10/10 ·
Tomes 20/20 · Keys 24/24 · Materials 36/36 · Trophies **244/237** · Reward Trophies 15/15 ·
Quest Items **18/17**.

**Reconciliation:** 388 shared · **7 only in `LootGroups`** (`Curved_Minotaur_Horn`, `Dredge_Charm`,
`Dredge_Manifesto`, `Keen_Oni_Claw`, `Oni_Talon`, `Plague_Idol`, `Sandblasted_Lodestone`) ·
**15 only in the JSON**, of which **5 are misspellings** of the `LootGroups`-only names and 10 are
genuinely new (`Elemental_Crystal_Shard`, `Elemental_Keystone`, `Luminous_Stone`,
`Maguuma_Spider_Web`, `Saurian_Bone`, `Sentient_Lodestone/Seed/Spore/Vine`, `Spider_Web`).

**The 5 dead entries** (JSON `model_id` names that do not exist in `ModelID` — these toggles do
nothing today): `Curved_Mintaur_Horn`→`Curved_Minotaur_Horn` · `Dregde_Charm`→`Dredge_Charm` ·
`Dregde_Manifesto`→`Dredge_Manifesto` · `Oni_Taloon`→`Oni_Talon` · `Plauge_Idol`→`Plague_Idol`. Four
also have a misspelled `name` field, so Nick's name-matching can never hit them.

**Placeholder ids — 25–27 items can never match a drop.** `Model_enums.py:858-903` marks 28 members
`# Dummy modelid's to insure no LootManager Crash - will be changed to correct value` (8–13-digit
values, e.g. `Animal_Hide = 1236547896911`). 25 are in `LootGroups`, 23 in the JSON. **Plus 5 more
implausible ids (>65535) carrying no comment**: `Charr_Hide`, `Herring`, `Roaring_Ether_Heart`,
`Umbral_Shell`, `Vampiric_Fang` — the last two are in both catalogs. Real ids for several are
recoverable from `Sources/frenkeyLib/LootEx/data/nick_cycle.json`.

**Two live bugs in the Loot Manager's resolve path:** `LootManager.py:616-617` `ModelID[member_name]`
is **unguarded** — hovering a dead entry with "Display ModelID In Hovered Text" on raises `KeyError`;
and `:149` inserts **`None`** into the whitelist when `_normalize_model_id` fails (`:322-341`).

**`Widgets/Data/` no longer exists.** `MerchantRules.py:56-58` still builds `DROP_DATA_PATH` under it,
so `_load_drop_data_catalog()` (`:6804-6826`) is now a **silent no-op** (`:6805` returns 0).

---

## 2. The list-maker — `LootConfig` (`Py4GWCoreLib/py4gwcorelib_src/Lootconfig_src.py`)

Singleton: `_instance` `:535`, `__new__` `:538-541`, `_initialized` guard `:536/:545`. **[was wrong]**
the old cite `:534` is the class statement, not the singleton.

`GetfilteredLootArray(distance=Range.SafeCompass.value, multibox_loot=False, allow_unasigned_loot=False)`
`:714`. Default distance **4800.0** (`GameData_enums.py:14`). The parameter really is spelled
**`allow_unasigned_loot`** (one `s`).

**Order of operations:** `MapValid` `:771` → `AgentArray.GetItemArray()` `:774` → distance filter `:775`
→ **eligibility** `:789-792` → per-item selectors `:796-848` → `Sort.ByDistance` `:850`.
**[was wrong]** the eligibility gate runs *after* the distance filter, not first.

**Eligibility** (`IsValidItem` `:724-731`): valid agent; owner is us **or** 0; and **only when
`owner_id == 0`** it also requires `not is_loot_lock_blocked(item_id)` `:729`. Items owned by us are
never lock-checked.

**Selectors** (first *decision* wins): item-id blacklist `:804` (skip) → model blacklist `:807` (skip)
→ item-id whitelist `:811` (take) → model whitelist `:815` (take) → five rarity switches `:820-843`
(take) → custom checks `:846` (take). **[was wrong]** "first match wins" is false: the `continue` sits
*inside* each rarity's nested `if self.loot_x:`, so an item whose rarity switch is **off** falls
through and still reaches `CustomItemChecks` `:846`.

**Purely pull-based:** no timer, thread, tick or per-frame hook anywhere in the file; it computes only
when a caller invokes it. (It does hold user-supplied predicates, `custom_item_checks` `:566`, invoked
at `:706`.)

**Dead / broken, confirmed:**
- **Dye lists are never read** — zero occurrences in `:714-852`; only the accessors touch them.
- **`loot_gold_coins` is never read by the engine** (`:554`, `:569` are the only writes). The Loot
  Manager compensates by whitelisting the model (`LootManager.py:138,154,169,441`); **InvPlus does not**
  (`LootModule.py:97`), so gold coins silently fail from that panel.
- `multibox_loot` appears only in the signature. The leader/follower block `:777-787` is a
  **triple-quoted string**, not `#` comments; `IsValidLeaderItem` `:733-758` and `IsValidFollowerItem`
  `:760-768` are defined but never called.
- **Id-space asymmetry:** the blacklist is checked against `agent_id` `:804`, the whitelist against
  `item_id` `:811`. **[was wrong]** this is *not* an end-to-end break — Messaging stores an agent id
  (`:1692` etc. from `loot_array`), which matches `:804`. The **whitelist** is the broken half.
- No `GetItemIDWhitelist` exists (the blacklist has one, `:634`). No persistence method of any kind.
- Its public **attributes** are mutated directly by callers (e.g. `Items.py:95`
  `loot_singleton.item_id_whitelist.add(...)`), bypassing the methods.

**Exactly 20 callers** (excluding `Legacy code and tests/` and the 3 frenkey re-definitions). 18 pass
`multibox_loot` and **8 pass `allow_unasigned_loot` by keyword** — so deleting those parameters is a
`TypeError` in 18 places, not a free cleanup. Only `botting_src/helpers_src/Items.py:38` passes
`allow_unasigned_loot=True`.

---

## 3. The "is it a good time?" check — three schedulers, NOT duplicates

**[was wrong]** The old doc said these "each re-do the same checks". They all end in the same two lines
(query the filter → send `PickUpLoot` to self) but their **guards differ materially**:

| | `Widgets/Automation/Multiboxing/HeroAI.py:43-87` | `HeroAI/headless_tree.py:83-140` | `botting_src/helpers_src/Upkeepers.py:137-192` |
|---|---|---|---|
| enable | `options.Looting` `:45` | `_headless_looting_enabled` `:84` (message-driven `:47-66`) | `auto_loot.is_active()` `:156` |
| combat | `in_aggro` `:51` | `IsHeadlessCombatPauseActive()` `:92` | danger block `:162-172` **only if the HeroAI widget is on**, else `pause_on_danger_fn()` `:174` |
| map | **none** | `MapValid()` + `IsExplorable()` `:98,109` | **none** |
| slots | `<= 1` `:63` | `<= 1` `:113` | **none** |
| pacing | `ThrottledTimer(250)` `:36` | own `ThrottledTimer(250)` `:35` | **no timer** — fixed `wait(500)` + blocks on the message `:190-192` |

**Manual senders skip all gating.** `HeroAI/ui_base.py:549-553` fans out to **every** account in shared
memory; `HeroAI/commands.py:173-177` fans out to a **caller-resolved** party/same-map set
(`command_api.py:56-70`) — **[was wrong]** "all accounts" is true only of the `ui_base` button.
**Six senders total** — the old doc missed `Bots/marks_coding_corner/VoltaicSpearTeamFarm.py:239`.

---

## 4. The grabber

**Message path.** Dispatch `Messaging.py:2726-2727`; `PickUpLoot` coroutine `:1633`. It is in
`_HERO_AI_SUSPENDING_COMMANDS` `:340`, which suppresses the stale-snapshot healer while it runs.
Sequence: mark running `:1658` → pre-check filter `:1660` → **snapshot + force-disable all HeroAI
options** `:1668,1671` (never mentioned in the old doc) → per item: `post_loot_lock` **before walking
and only for unassigned** `:1682` → `FollowPath(timeout=10000)` `:1711` → `InteractAgent` `:1733` →
poll every 100 ms up to **3000 ms** `:1736,1775-1782`.

**Success is not "the item disappeared"** — it is "no longer in the freshly recomputed **filtered**
array" `:1775-1776`, which is also true if another account locks it, the filter changes, or it drifts
out of Earshot. (The direct walker instead checks the live agent array,
`routines_src/yield_src/items.py:312-314`.)

**Cost:** `GetfilteredLootArray` — a full ground scan plus per-item filtering — runs **~10×/second**
for the whole duration of every pickup (`:1775` inside the 100 ms loop).

**Failure paths:** 4 of 5 blacklist the item (`:1692` map-invalid/bag-full, `:1713` FollowPath fail,
`:1742` timeout, `:1756` in-loop map/bag) — **map-invalid blacklists too**, which the old doc omitted.
Two paths do **not**: invalid agent `:1703-1708` and the post-walk exit check `:1726-1732`.

**Defect:** `_get_loot_exit_reason` `:1634-1652` already calls `RestoreHeroAISnapshot` +
`MarkMessageAsFinished` + `ResetAllQueues` before returning a reason, and the `finally` `:1786-1789`
does both again → **double restore (pops two snapshots) and double finish** on every map-invalid /
bag-full exit.

**Threshold mismatch:** senders stop at `<= 1` free slot; the coroutine only at `< 1` (`:1641`).

**Direct path.** `bot.Items.LootItems()` (`ITEMS_src.py:46`) → `helpers_src/Items.py:22-39` →
`routines_src/yield_src/items.py:242` (`LootItems`; retrying variant `:325`), and
`Sequential.LootItems` (`Sequential.py:582-628`). **[was wrong]** the behaviour-tree node
(`behaviourtrees_src/items.py:958-1041`) is **not** a hand-off to that walker — it is a third,
self-contained implementation that re-queries the filter each tick `:984,:1025` and calls
`Player.Interact` `:1020`. **[was wrong]** "no message involved" — the *yield* walkers do read and
mutate messaging (`items.py:19-29` `_finish_active_pick_up_loot_message`, called at `:247,254,275,…`).
Only the BT node and the Sequential walker are genuinely messaging-free.

**Contention.** `WhiteboardLocks.py`: `is_loot_lock_blocked` `:576`, `post_loot_lock` `:616`,
`clear_loot_lock` `:658`, all via `GLOBAL_CACHE.ShMem` — **zero file I/O**; all fail-open on exception.
TTL floor **4000 ms** (`:22,641`), EXCLUSIVE/OWNER_REENTRANT/HARD. **[was wrong]** the old doc said
contention is handled "**not** in the list-maker" — the *posting* lives with the grabbers, but the
**check is inside `GetfilteredLootArray`** (`Lootconfig_src.py:717,729`). A rewrite that drops that
line silently removes cross-account contention from the filter.

---

## 5. The two menus

**Loot Manager** (`Widgets/Guild Wars/Items & Loot/LootManager.py`) — 5 sections: Debug Settings tree
(5 checkboxes) `:374`; Save/Load via `FileDialog` `:390-409`; `Common` tree with **6** rarity
checkboxes `:411-424`; Nick's Items (formula checkbox, 0–12 weeks slider, Add button) `:451-515`;
Single-items tree with Select/Deselect All `:519-570`. Plus 4 sub-windows: whitelist `:629`, blacklist
`:678`, filtered-loot `:693`, manual editor `:728`.
Catalog rendered as a **two-level `tree_node` group → subgroup → checkbox** `:572-622`.
**No search box** (zero `search` hits in the file). Tooltips come from the catalog's **`drop_info`**
string `:613-619`, optionally suffixed with the numeric ModelID.
Persistence: 2 writable **account** docs (`loot_config.json` `:41`, `rarity_filter_data.json` `:42`),
2 read-only **global** tables (`modelid_drop_data.json` `:44`, `Nick_cycles.json` `:45`), exports under
`Widgets/LootManager/Exports/` `:176`, plus a **dead** `Settings("Widgets/Config/loot_window.ini",
"global")` `:29` that is read `:34-36` but never written.

**InvPlus** (`Sources/ApoSource/InvPlus/LootModule.py`) — rarity row of 5 × `game_toggle_button` 20×20
coloured from `ColorPalette` `:74-95`, plus a 6th gold-coins toggle using a *different* helper `:97`;
all five write the attribute **directly**, bypassing `SetProperties`. Catalog = a 3-column
`begin_table` of `ImGui.image_toggle_button` **48×48** with `text_wrapped` labels `:106-136`, iterating
**`LootGroups`** `:102`. **No tooltips on the icons**, no search. **Save/Export/Import are all literal
`pass`** `:53-68`; the module contains zero persistence code.

Both hold the **same singleton** (`LootManager.py:17`, `LootModule.py:20`).

**[was wrong]** "InvPlus edits persist because the Loot Manager autosaves" — **there is no autosave**.
The Loot Manager writes only from its own event handlers, and `load_loot_config()` `:84` rebuilds the
whitelist from its own `loot_items[*]["enabled"]` `:141-149`, so InvPlus edits are **actively
overwritten** on the next Loot Manager load.

---

## 6. Marking — native-capable, zero production use

`Py4GWCoreLib/AgentRecolor.py` exposes 16 methods and **no item functions**. Nuance: `MasterEnable`
`:79` / `MasterDisable` `:87` / `ClearAllRules` `:172` **do** affect items (shared), so the wrapper can
already gate and wipe item rules — it just cannot set or read one.

Native has the full item surface (`stubs/PyAgentRecolor.pyi:120-179`): `item_enable/disable/
is_enabled`, six `set_item_{agent,id,model,name,type,rarity}_color`, six removers, `item_clear_rules`,
six getters. **[correction]** the marking vocabulary is **six keys**, not four — it includes item_id
and agent_id.

**Mechanism:** a detour on the game's own item-label function — `Detour_ItemGetTextData`
(`agent_recolor.cpp:99`) → `AgentRecolor::OnItemGetTextData` (**`:640`**, not :641). Rules are
re-snapshotted **only on mutation** (`RebuildItemSnapshotLocked` at `:542,547,553,…`), never on a
timer. **So Python pushes rules once on change; there is no per-frame item pass.** Precedence
`agent_id > item_id > model_id > name > type > rarity`, first match wins, `:661-700`. Alpha is
fade/hide; `0x00` blanks the label, `:703-707`. Matching is lock-free but acquiring the snapshot
pointer takes one brief mutex `:644-648`.

**Preconditions the design must honour (were missing):**
- Item recolour is **double-gated** — it needs **both** `master_enable()` (`:801-802`) and
  `item_enable()` (checked first thing, `:641`). Rules alone do nothing.
- Colours are **not always true-RGB**: until an item's name decodes (async, a frame or two per item
  kind) it falls back to GW's ~7 palette colours (`PyAgentRecolor.pyi:14-19`; `agent_recolor.cpp:120-139,
  732-748`).
- The model/name/type/rarity tiers **silently no-op** if `GW::item::GetItemById` fails (`:669,676`);
  only agent_id and item_id work without a resolved item.
- Name rules are lowercased substrings matched in **insertion order** (`:687-688`).

**It is purely the floating name label** — `name_tag[0]` string swap `:717`, base colours `:723-724`,
blank `:706`. No geometry. **[was wrong]** "the engine can recolour a label **and draw a beacon**" —
the engine draws no beacon; **the beacon is entirely ours**.

**Existing callers: none in production.** Only `tests/name_tag_color/name_tag_color_test.py` and
`Sources/ApoSource/py4gw_demo_src/agentrecolor_demo.py` (wired into the demo registry, and it calls
`import PyAgentRecolor` **directly**, bypassing the wrapper — which is why the wrapper gap went
unnoticed).

**For agents, by contrast,** Python *does* scan every data pass and push — `agent_recolor/controller.py:175-181`
registers on `PyCallback.Phase.Data`; `_do_recolor_pass` `:209` scans the agent array `:222,266` and
`_push` `:238` calls `SetAgentColors` — though the push is **delta-gated** `:240,244`.

**Beacons.** `light_beacon.py` and `loot_beam.py` are at the **repo root**, imported by nothing, and
**not widgets** (widget discovery needs a `.widget` marker; the root has none). **[was wrong]** "reuse
the existing beacon renderer" pointing at `light_beacon.py`: that file has **no class** — it is a
singleton tuning harness with module globals (`state` `:63`, `_emitters` `:27`, `_profile_cache` `:171`)
that draws **one** beacon at one position. The reusable one is **`loot_beam.py`** — `class LootBeam`
`:109` with per-instance emitters, `configure()` `:124`, `draw(x, y)` `:138`. **Both execute native
calls at import** (`light_beacon.py:22-23`, `loot_beam.py:21-22`), which violates the passive-import
rule and must be moved before either is lifted.

---

## 7. Data sources

**Materials.** `MaterialMap` `Item_enums.py:267-304` — **36 entries**, keys are `ModelID` members,
values are plain display strings (mechanically `name.replace("_"," ")`, hence `"Bolt Of Cloth"`).
Same set as the `Materials` group in both catalogs.

**Salvage output.** **The client does not expose it.** `stubs/PyItem.pyi` lists all 45 `PyItem` fields;
none names a material. The only salvage entry points are actions (`salvage_start`, `salvage_materials`,
`PyItem.pyi:131-137`). **[was wrong]** the readers are **`Item.Type.IsMaterial`** (`Item.py:564`) and
**`Item.Usage.IsMaterialSalvageable`** (`Item.py:600`) — **not** `Item.Properties.*`, which has no
salvage member (`Item.py:398-541`). A data table is therefore mandatory.
Sources: 3 same-shape copies of frenkey's `items.json` (`ItemHandling/Items/`, `LootEx/data/`, and a
runtime copy at `Settings/Global/Item & Inventory/`) — 3793 items, **2032 with salvage** — plus the raw
`scraped_items.json` (4040 keys) and `materials.json`. Entry shape:
`common_salvage`/`rare_salvage` = `{material name: {model_id, amount:-1, min_amount:-1, max_amount:-1}}`.
The extraction in this folder yields **2021 items / 34 materials**. **3 of those materials
(31202/31203/31204, Zaishen coins) are NOT in `MaterialMap`**, and 5 `MaterialMap` entries
(927/930/943/945/950) are never a salvage output. Armor is genuinely uncovered (Boots 92/0,
Leggings 90/0, Headpiece 221/0, Gloves 100/0, Chestpiece 92/1).

**Nicholas — three different datasets.**
| dataset | entries | fields | consumer |
|---|---|---|---|
| `NICHOLAS_CYCLE` (`Calendar_enums.py:394-1655`) | 140 | `week: date`, `item`, **`model_id: ModelID`**, `location`, `region`, `campaign`, `map_url` | **Calendar** |
| `Nick_cycles.json` | 141 | **only** `Week: str`, `Item: str` | **Loot Manager** |
| `LootEx/data/nick_cycle.json` | 137 | `Week`, `Item`, `ModelId: int`, `Index` | frenkey |

`NICHOLAS_CYCLE` is the good one: all 140 `model_id`s are valid members. The Loot Manager matches **by
display name** (`LootManager.py:492-515`) and **silently loses 20 of 137 items** (plurals + a typo
`Chrimson`). Calendar mutates `NICHOLAS_CYCLE` **in place** to roll the cycle (`Calendar.py:66-97`).

**Textures.** `get_texture_for_model(model_id) -> str` (`Texture_enums.py:12-30`) **never returns empty
and never raises** — it falls back to `0-File_Not_found.png` twice (`:18-22`, `:26-27`). Filename
convention is `zfill(5)`-id + `-` + enum name. **[was wrong]** "assume every item resolves a texture":
**41 of 403** catalog entries (37 of 395 in `LootGroups`) have **no** texture file. Whole subgroups are
blank — all 10 **Elite Tomes**, all 4 **Passage Scrolls**, all 4 **Map Pieces**, 7 of 8 **Quest-Item
Keys**, both `El_*_Tonic`. A texture-only grid shows 41 identical "not found" tiles; a name fallback is
required.

---

## 8. Fixed during this pass
`json/Global/Widgets/LootManager/{modelid_drop_data,Nick_cycles}.json` were **`{}` (2 bytes)** — the
persistence migration created the global docs empty, and `JsonFactory` only seeds from `json/Defaults`
when the document does **not** exist, so they could never self-heal. The Loot Manager was running on a
**zero-item catalog**. Both were restored from their Defaults (403 and 141 entries).
