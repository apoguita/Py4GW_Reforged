# DEMO v1 — Legacy `Py4GW_DEMO.py`

**File:** `Widgets/Coding/Py4GW_DEMO.py` (single file, ~2,780 lines)
**Status:** Complete but legacy-shaped. This is the historical "showcase every method and all data accessible from Py4GW" widget.
**Self-description in code (line 6):** *"This script is intended to be a showcase of every Method and all the data that can be accessed from Py4GW — current status, not complete."*

---

## 1. Architecture

Monolithic, procedural, "many floating windows" design:

- `from Py4GWCoreLib import *` wildcard import (pulls the whole convenience facade) plus `import PyPing`.
- A `WindowState` helper class holds per-section state (window name, open flags, button list, description list, arbitrary `values` list). One global `*_window_state` instance is declared per section (~15 of them).
- **Entry point:** `main()` → guards on `Map.IsMapReady()` → `DrawWindow()` (the main hub) or `CloseAllWindows()`.
- **Main hub `DrawWindow()`:** draws a single window "Py4GW Lib DEMO" with a **dynamically-gridded tileset of toggle buttons** (`calculate_grid_layout` computes a near-square grid). Each toggle opens a **separate top-level `PyImGui.begin()` floating window** via `ShowXWindow()`.
- Some sections nest further sub-windows (e.g. `ShowPyMapWindow` → `ShowPyImGuiTravelWindow` / `ShowPyImGuiExtraMaplWindow`; `ShowPyAgentWindow` → `draw_agent_window` → `ShowLivingAgentData`/`ShowItemAgentData`/`ShowGadgetAgentData`).
- **Error strategy:** every `Show*` function body is wrapped in `try/except` that logs via `PySystem.Console.Log(..., MessageType.Error)` and re-raises.

### UI idioms used
- `ImGui_Legacy.table(id, headers, data)` is the dominant data-display primitive (dozens of call sites).
- `ImGui_Legacy.DrawTextWithTitle(title, text, wrap)` for section descriptions.
- `ImGui_Legacy.toggle_button(...)`, `ImGui_Legacy.push_font/pop_font`.
- Raw `PyImGui.*` for tables, combos, inputs, buttons.
- Fixed pixel window sizes via `PyImGui.set_next_window_size(w, h)`.

## 2. Coverage — sections and what each exercises

Main button list (`main_window_state.button_list`, line ~2569):
`PyImGui, PyMap, PyAgent, PyPlayer, PyParty, PyItem, PyInventory, PySkill, PySkillbar, PyEffects, PyMerchant, PyQuest, Py4GW`

| Section (fn) | Backend surface exercised |
|---|---|
| **PyImGui** `ShowPyImGuiDemoWindow` | Sub-demos: Selectables (checkbox/radio/combo), Input Fields (sliders/inputs/text), Tables, Miscellaneous (color_edit3/4, progress_bar, tooltip), plus `PyImGui.show_demo_window()` (official ImGui demo). |
| **PyMap** `ShowPyMapWindow` | `Map.GetMapID/GetMapName/GetInstanceUptime/GetMaxPartySize/GetMaxPlayerSize/GetMin*`, `IsOutpost/IsExplorable/IsMapLoading/IsMapReady`. Sub: **Travel** (`Map.Travel`, `Map.TravelToDistrict`, chat `tp eotn`); **Extra Info** (`GetCampaign/GetContinent/GetRegion/GetDistrict/GetLanguage`, `HasEnterChallengeButton`, `EnterChallenge/CancelEnterChallenge`, `IsVanquishable`, `GetFoesKilled/GetFoesToKill`). |
| **PyAgent** `ShowPyAgentWindow` | Nearest-entity discovery via `AgentArray.Get*Array` + `AgentArray.Sort.ByDistance` + `AgentArray.Manipulation.Subtract`; `Agent.GetAgentIDByName`. Agent inspector `draw_agent_window`: `Agent.IsLiving/IsItem/IsGadget`, `GetXYZ`, rotation/velocity, `GetAttributes`. Type-specific: **Living** (professions, energy/health/regen, name, dagger status, allegiance, weapon data, PvE state/combat flags/typemap bitmasks), **Item** (`GetItemAgentByID`), **Gadget** (`GetGadgetAgentByID`, h00C4/h00C8/h00D4 raw fields). |
| **PyPlayer** `ShowPlayerWindow` | `Player.GetAgentID/GetName/GetXY/GetTargetID/GetObservingID`; player data (`GetRankData`, `GetTournamentRewardPoints`, `GetMorale`, `GetExperience`, `GetSkillPointData`, Kurzick/Luxon/Imperial/Balthazar data, account name/email); `DepositFaction`; Titles (`GetActiveTitleID/GetTitle/SetActiveTitle/RemoveActiveTitle`); Methods (`SendDialog`, `SendChatCommand`, `SendChat`, `SendWhisper`, `ChangeTarget`, `Interact`, `Move`). |
| **PyParty** `ShowPartyWindow` | `GLOBAL_CACHE.Party.*` — party/leader IDs, login/party numbers, hard/normal mode, sizes/counts, tick state. Players (invite/kick, per-player data), Heroes (`PyParty.Hero`, add/kick by id/name, flag, `SetHeroBehavior`, `UseSkill`), Henchmen (add/kick), Others, Pets (`SetPetBehavior`, `GetPetInfo`). |
| **PyItem** `ShowItemWindow` / `ShowItemDataWindow` | `GLOBAL_CACHE.Item.*` — type, model id/file, slot, agent id; Rarity, Properties (customized/value/quantity/equipped/profession/interaction), Type (weapon/armor/material/…), Usage (kits, identified, uses), Customization (inscriptions, upgradable, formula, stackable, sparkly), Modifiers (`GetModifiers`), DyeInfo. `Item.RequestName`. |
| **PyInventory** `ShowInventoryWindow` | `GLOBAL_CACHE.Inventory.*` — hovered item, first ID/salvage kit, first unidentified/salvageable, gold on character/storage, `IdentifyFirst`, `SalvageItem`, `PyInventory.PyInventory().AcceptSalvageWindow`, `IsStorageOpen`, `OpenXunlaiWindow`. |
| **PySkill** `ShowSkillWindow` / `ShowSkillDataWindow` | `GLOBAL_CACHE.Skill.*` — GetName/GetType/GetCampaign/GetProfession; `.Data.*` (combo, reqs, costs, adrenaline, activation/aftercast/recharge, aoe); `.Attribute.*` (scale, bonus scale, duration); `.Flags.*` (~40 boolean predicates); `.Animations.*`; `.ExtraData.*`. Hovered skill via `SkillBar.GetHoveredSkillID`. |
| **PySkillbar** `ShowSkillbarWindow` | `GLOBAL_CACHE.SkillBar.*` — `GetSkillIDBySlot`, `GetSkillData`, `UseSkill`, `GetHeroSkillbar`, `HeroUseSkill`; iterates party heroes. |
| **PyEffects** `ShowEffectsWindow` | `GLOBAL_CACHE.Effects.GetBuffs/GetEffects/DropBuff`; `PySkill.Skill(id).id.GetName()`. |
| **PyMerchant** `ShowMerchantWindow` | `GLOBAL_CACHE.Trading.*` — `Trader` (GetOfferedItems, GetQuotedItemID/Value, RequestQuote/RequestSellQuote, BuyItem/SellItem), `Merchant`, `Crafter.CraftItem`, `Collector.ExchangeItem`, `IsTransactionComplete`; `Inventory.GetHoveredItemID`. |
| **PyQuest** `ShowQuestWindow` | `GLOBAL_CACHE.Quest.GetActiveQuest/SetActiveQuest/AbandonQuest`. |
| **Py4GW** `ShowPy4GW_Window_main` | `Keystroke.Press/Release/PressAndRelease` (with `Key` enum); `PyPing.PingHandler` (current/avg/min/max); `Timer` (start/stop/pause/resume/elapsed/has-elapsed); `Overlay()` (GetMouseCoords, DrawPoly3D area rings, GetMouseWorldPos, WorldToScreen, FindZ, DrawText3D, DrawLine, mark-target). |

## 3. Notable characteristics / weaknesses (for the replacement discussion)

- **Data-path style:** overwhelmingly `GLOBAL_CACHE.*` getters + a few direct wrappers (`Agent`, `Player`, `Map`, `AgentArray`, `Keystroke`, `Overlay`). It does **not** touch the new `native_src` ctypes context structs or the new `Map.MissionMap/MiniMap/WorldMap/Pregame/Pathing` sub-namespaces at all — those are DEMO v2 territory.
- **Legacy UI:** relies on `ImGui_Legacy` (the API being deprecated per the ImGui facade migration) and many independent floating windows instead of one dockable surface.
- **No structured pass/fail:** it "shows data"; there is no explicit indication of whether a binding returned a sane value, raised, or is stubbed (several fields are hard-disabled, e.g. `Item.GetName` commented out → `"Feature Disabled"`).
- **Duplication:** repeated table-building boilerplate; several copy-paste bugs (e.g. `IsRareMaterial` mapped to `IsMaterial`, `zplane` row shows `Agent.IsLiving`).
- **Broad but shallow** against the Reforged backend: covers every domain, but mostly the "does the getter return something" level.
