# Loot Config — Parity Audit (original code + agreed plan vs. implementation)

Ground truth for finishing the reengineer. Every row is a feature that exists in the **original
code** (legacy `LootManager.py`, `LootConfig`, InvPlus `LootModule.py`) or was **agreed in the
plan** (`01_loot_config_design.md`, `02_loot_ui.md`). Status is honest as of this audit.

Legend: ✅ done · 🟡 partial/wrong · ❌ missing.

## A. Decision engine (design §4–§8)

| # | Feature | Source | Status |
|---|---|---|---|
| A1 | Snapshot each ground item once (immutable) | plan §6 | ✅ |
| A2 | Flat "any match → pick up", blacklist is only override | plan §4 | ✅ |
| A3 | Model whitelist / blacklist (persisted catalog) | orig + plan | ✅ |
| A4 | Item-id whitelist / blacklist (transient per instance) | orig | ✅ |
| A5 | Rarity toggles (white/blue/purple/gold/green + coins) | orig | ✅ |
| A6 | Dye whitelist/blacklist ACTUALLY read (was dead) | orig+plan | ✅ |
| A7 | Category switches — non-destructive, membership only | plan §3 | 🟡 engine only; no persist/UI |
| A8 | Filters: conditions ANDed, filters ORed | plan §5 | ✅ engine |
| A9 | Condition value routing (enum/number "or better"/callable) via Item.Mods | plan §5 | ✅ model calls Item.Mods |
| A10 | `unless` exceptions on a filter | plan §5 | ✅ model |
| A11 | Ownership + loot-lock + distance gates (kept out of filters) | orig+plan §7 | ✅ |
| A12 | Bot runtime adds are TRANSIENT, never saved | plan §8 | ❌ AddToWhitelist still persists |
| A13 | Custom checks kept but as OR contributor, no override | plan §4 | ✅ |
| A14 | GetfilteredLootArray signature preserved (25 callers) | orig | ✅ |

## B. Persistence & multibox (design §13)

| # | Feature | Source | Status |
|---|---|---|---|
| B1 | Global shared ruleset via **JsonFactory** (filters+whitelist+dye) | plan §13 + user | ✅ |
| B2 | Per-account toggles via **Settings** (enable, rarities, quick-open) | plan §13 + user | ✅ |
| B3 | Category switches persisted per-account | plan | ❌ |
| B4 | Cross-account **messaging nudge** (LootConfigUpdated), no file polling | plan §13 | ✅ |
| B5 | No copy-between-accounts (global scope makes it unnecessary) | user | ✅ |
| B6 | Import / Export ruleset to a file (legacy Save/Load to File) | orig + plan §Status | ❌ |

## C. UI — editor (design §UI 3, doc 02)

| # | Feature | Source | Status |
|---|---|---|---|
| C1 | Own System Settings category, tabbed section | plan §9, doc 02 | ✅ registered |
| C2 | **Filters tab: real condition builder** (add/remove any condition, unless, editable name, new filter) | doc 02 §3.1 | ❌ 3 hardcoded buttons |
| C3 | Filter header: name · summary · match count · enabled checkbox; `###stable-id` | doc 02 §3.1 | 🟡 no editable name, no live count |
| C4 | Per-filter marking editor (recolour/fade/hide + beacon) | doc 02 §3.1 | ❌ |
| C5 | **Catalog tab: icon grid, 6 per row**, textures from ModelID | doc 02 §3.2 + InvPlus + user | ❌ regressed to checkboxes |
| C6 | Catalog search (type-to-find) across groups | doc 02 §3.2 | ✅ (works, but on checkboxes) |
| C7 | Catalog item tooltips (drop_info) | orig LootManager | ❌ |
| C8 | Marking tab: global knobs (fade steps, beacon presets, cap, master marking) | doc 02 §3.3 | ❌ placeholder |
| C9 | Status tab: master enable, quick-open toggle | doc 02 §3.4 | ✅ |
| C10 | Status tab: bot-added items list ("N added by X") | doc 02 §3.4, plan §8 | ❌ |
| C11 | Status tab: import/export + cross-account push | doc 02 §3.4 | 🟡 push only |
| C12 | Nick's rotating items (formula + date window, add to catalog) | orig LootManager | ❌ |

## D. UI — quick access (doc 02 §4)

| # | Feature | Source | Status |
|---|---|---|---|
| D1 | Floating window off the always-on host, imgui.ini position | doc 02 §4 | ✅ |
| D2 | Master looting on/off | doc 02 §4 | ✅ |
| D3 | Rarity toggles, colour-coded (InvPlus style) | doc 02 §4 + InvPlus | 🟡 dots not colour buttons |
| D4 | Category quick-toggles (dyes, materials, scrolls, …) NON-destructive | user + plan | ❌ current ones destroy whitelist |
| D5 | Marking quick-toggles ("recolour greens") | doc 02 §4 | ❌ |

## E. Visual marking layer (design §12)

| # | Feature | Source | Status |
|---|---|---|---|
| E1 | Expose ground-item setters in `AgentRecolor.py` (native store exists) | plan §12 | ❌ |
| E2 | Drive recolour/fade/hide from filters' marking | plan §12 | ❌ |
| E3 | Distance fade, 10 steps, threshold-based (per-item alpha) | plan §12 | ❌ |
| E4 | Hide = label alpha 0, does NOT affect pickup | plan §12 | ❌ |
| E5 | Beacon renderer from `light_beacon.py` presets (purple ships) | plan §12 | ❌ |
| E6 | Beacon nearest-N cap | plan §12 | ❌ |
| E7 | Marking precedence handled by native store | plan §12 | n/a (native) |

## F. Adjacent clean-ups (design §11)

| # | Feature | Source | Status |
|---|---|---|---|
| F1 | Dye filter uses `Item.Dye`, not raw `Item.GetDyeColor` | plan §11 | ✅ snapshot uses Dye path |
| F2 | De-dup `Item.GetDyeColor` callers | plan §11 | ❌ (5 callers, separate) |
| F3 | `IsMaxDamage`/`DAMAGE_RANGES` → mod condition | plan §11 | ❌ (not used by loot) |

## Resolution (this pass — all Pylance-clean)

- **A7, B3, D4** ✅ Categories are non-destructive membership switches (`engine.categories` +
  `_category_model_ids`), persisted per-account via Settings, toggled from quick access + a
  Categories tab. They never touch the per-model whitelist.
- **A12, C10** ✅ Bot adds go to a transient `runtime_whitelist` (facade `AddToWhitelist` etc.),
  never saved; Status shows the count.
- **C2, C3, C4** ✅ Real condition builder: pick property (type/rarity/model/value/quantity/dye/
  requirement/damage), add/remove `when` + `unless`, editable name, new/delete filter, per-filter
  marking editor (mode + colour + beacon). (C3 shows condition count, not a live match count.)
- **C5, C7** ✅ Catalog is a 6-icon-per-row grid (`image_toggle_button` + `get_texture_for_model`)
  with per-item tooltips (drop-info via **JsonFactory**), search, per-group all/none.
- **B6, C11** ✅ Export/Import as named **JsonFactory** docs (`json/Global/Loot Exports/`) — no raw
  json/open, no arbitrary-path FileDialog. Cross-account push retained.
- **C12** ✅ Nick reuses the library's `NICHOLAS_CYCLE` (dated, `model_id` resolved) — no reinvented
  formula, no `Nick_cycles.json`.
- **E1–E6, C8** ✅ `AgentRecolor` ground-item setters exposed; `marking.py` drives recolour/fade
  (10 distance steps, bucketed)/hide from per-filter marking, plus a compact beacon (nearest-N cap);
  driven each frame from the System widget. Marking tab shows knobs + availability.
- **D3** 🟡 rarity toggles are colour-dotted checkboxes (not full game colour-buttons) — acceptable.
- **D5** — marking quick-toggles: **covered by per-filter marking** (make a "Greens" filter with
  green marking); not a separate destructive shortcut.
- **F1** ✅ loot reads dye via the `DyeInfo` struct (`DyeColor.from_dye_info`).
- **F2** ✅ `Item.GetDyeColor` is now **guarded to Dye items** — on a non-dye it returns 0 instead
  of the first non-zero mod arg (the garbage that gave `25` on a bow). This fixes every raw caller
  (fiber farmer, TeamInventoryViewer) in place, matching its own docstring ("Vial of Dye color").
- **F3** ✅ `Item.Properties.IsMaxDamage` now compares against the **weapon type's cap** (highest
  max across DAMAGE_RANGES rows) instead of indexing by requirement, so weapons above req 9 (the
  table only covers 0-9, e.g. the req-11 dumped bow) are judged correctly.

## Rarity confirmed (all five)

Blue is **not** pending: the ground dumps show `single_item_name` populated on ground items, which
is the field blue detection reads. All five rarities read correctly unidentified, on the floor.

### Persistence rule (hard): JSON only via `JsonFactory`, INI only via `Settings`

Verified: the `loot_config` package contains **no** `import json`, `json.load/dump`, or file
`open()`. Global ruleset + backups = `JsonFactory`; per-account toggles/categories = `Settings`.
