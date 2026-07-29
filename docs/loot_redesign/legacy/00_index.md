# Loot Config redesign — index

Replacing the Loot Manager with one class that decides **what to pick up** and **what to mark**
(recolour / beacon). It never picks anything up and never decides *when* to loot — that is other
code's job and stays there.

| doc | what it is |
|---|---|
| **`01_loot_redesign.md`** | **The design.** What the class does, the four pickup surfaces (rarity / List / Materials / Filters), the filter syntax (mirrors `Item.Mods`), marking, persistence, the menu, the data tables, and what's still open. |
| **`02_how_it_works_today.md`** | **The audit.** How looting actually works right now, derived from the code: the list-maker, the three duplicated "is it a good time?" checks, the two grabbers, the two menus, and what's broken/dead. Also how the native item recolour really works. |
| **`03_structure_and_build.md`** | **The plan + what was built.** Module layout (mirrors `agent_recolor`), the 10-step build order, and an **As built** section listing every file that landed, what it was wired into, and the three deliberate deviations. |
| `salvage_mapping.json` | The extracted salvage table (`model_id → {common, rare}`). **Seeded** to `json/Defaults/Widgets/System/LootSalvage.json`; this copy is the review source. |
| `salvage_mapping_review.json` | The same data with item/material names, for reading during review. |
| `grouping.json` | The extracted grouping table (11 categories, 395 items). **Seeded** to `json/Defaults/Widgets/System/LootGrouping.json`. |
| `grouping_review.json` | The same with `{id, name}` per entry, for reading during review. |

**Status: implemented.** The engine, catalog, persistence, the System Settings editor, the
quick-access window, marking and the cross-account reload are all in; the old Loot Manager widget has
been retired to `Legacy code and tests/`. The two data tables are seeded and awaiting your cleanup
pass (they work as-is).

**Read order:** `02` (what exists) → `01` (what we're building) → `03` (how/what order).

**Ground rules carried through all three:**
- The class **decides**; it never walks, interacts, or picks up.
- The **List** (hand-picked items) and the **Filters** (property rules) are two separate systems — in
  the code and on screen — never merged.
- Filters reuse the **item-mod** query shape (`HasAllMods`: a list of conditions, all must match).
- **Transitional/runtime values are never saved.**
- Config is **global** (rules/lists) + **per-account** (toggles, quick-access choices), like the other
  settings modules; edits notify other accounts to reload.
- Persistence only through the sanctioned jailed store (`JsonFactory` / `Settings`).
