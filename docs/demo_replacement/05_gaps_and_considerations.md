# Gaps & Considerations for the Replacement

This is **context for planning**, not the plan itself. It records the divergences, gaps and open questions surfaced while analyzing DEMO v1 and v2, so the replacement design can start from facts.

---

## 1. The two demos disagree on almost everything structural

| Dimension | DEMO v1 (`Py4GW_DEMO.py`) | DEMO v2 (`Py4GW DEMO 2.0.py`) |
|---|---|---|
| File shape | one 2,780-line file | entry file + `py4gw_demo_src/` package |
| Window model | many independent floating `begin()` windows | one window, sidebar nav + content child |
| Data path | `GLOBAL_CACHE.*` getters | direct wrappers + `native_src` context structs |
| Tables/UI | `ImGui_Legacy.table` / `DrawTextWithTitle` | native `PyImGui` `draw_kv_table` |
| State | positional `WindowState.values[]` lists | dataclasses (`DisplayNode`, `MapVars`) |
| Coverage | broad (13 domains), shallow vs new backend | narrow (Map/Agents/Pathing), deep + new surface |

A replacement has to pick one coherent model. v2's shell is the better base; v1 is the coverage checklist.

## 2. Coverage gaps to close (from the matrix)

- **Ported in v1, missing in v2:** Player, Party, Item, Inventory, Skill, Skillbar, Effects, Merchant, Quest, Keystroke, Ping, PyImGui widget gallery. These must come back.
- **Missing in BOTH (real backend, never demoed):** `PyTrade`, `PyCamera`, `PyDXOverlay`, `PyDialog` (direct), `PyUIManager`/`GWUI`, `PyTexture`, `PyGuild`, `PyFriendList`, `PyPacketSniffer`, `PyAgentEvents`/`PyListeners`, `PyChat` (direct), `PySettings`, `PyProfiler`, `PyRender`, `PyNameObfuscator`, `PyAgentRecolor`, `PyScanner`. If the goal is "test all CPP functionality," these are net-new demo work.
- **Context path barely tested:** only `AgentContext` and `PreGameContext` are exercised (v2). The other ~15 `native_src/context/*` readers have no demo.

## 3. Deprecation pressures that must be resolved before/while porting

- **`ImGui_Legacy` is being retired** (see `docs/ImGui_Facade_Migration_Plan.md`). v1 is built entirely on it; v2 still leaks it (`agent_demo.py`, `tooltip()`). The replacement should target the new `Py4GWCoreLib.ImGui` facade with **no bridging** to legacy (project hard rule).
- **Binding renames already applied** (per CLAUDE.md): `Py2DRenderer→PyDXOverlay`, `PyCombatEvents→PyAgentEvents`, `PyPointers` retired, `Py4GW.Console.*→PySystem.Console.*`, `Py4GW.Game.*→PySystem`/`PyGameThread`, `PyOverlay` `Point2D/3D→Vec2f/Vec3f`, `PyKeystroke` `PyScanCodeKeystroke→PyKeyHandler`. v1 uses several old spellings indirectly; anything ported forward must use the Reforged names.
- **Getter-method style:** Reforged `Py*` favor `PyAgent().GetPos()` / module-level `PyAgent.get_agent_enc_name(id)` over legacy data-field access. v2 already follows this; v1 does not everywhere.

## 4. Known defects / dead spots in the current demos (don't copy forward)

- v1: `Item.GetName` hard-disabled → shows `"Feature Disabled"`; `IsRareMaterial` wired to `IsMaterial`; agent `zplane` row prints `IsLiving`; duplicated table boilerplate everywhere.
- v2: `WIP Observing Matches Data` listed in nav but has no router branch; `tooltip()` advertises domains that aren't implemented; several Mini/Mission Map option blocks share the same `map_vars.MissionMap.*` state (mini-map reuses mission-map vars).

## 5. Design questions to settle before building the replacement

1. **Purpose framing:** is this primarily a *developer API reference* (show data), or a *backend test harness* (assert bindings return sane values / don't throw)? v1/v2 are the former. "Debug and test all CPP functionality" leans toward the latter — which implies per-binding pass/fail status, not just data dumps.
2. **Scope target:** demo the *wrappers* (what scripts use) or the *raw `Py*` bindings* (what the DLL exposes), or both in layers? The matrix shows they diverge.
3. **Structure:** keep it a single Widget, or a package under `Sources/` with a thin `Widgets/` wrapper (the ModularBot pattern)? v2 already splits into `Sources/ApoSource/py4gw_demo_src/`.
4. **Data path per domain:** standardize on one (wrapper vs `GLOBAL_CACHE` vs context struct), or intentionally show all three side-by-side to validate they agree?
5. **Live-state dependence:** many sections only work in specific states (outpost vs explorable, map-ready, merchant-open, hard-mode). The replacement needs a consistent "not available in this context" affordance (v1 does this ad hoc; v2 partially).
6. **Naming/placement:** where does the replacement live and what is it called, and do v1/v2 get retired or kept as reference?

## 6. Suggested next step

Decide items in §5 (especially #1 and #2) before any code. Once framing is chosen, the coverage matrix (`03_coverage_matrix.md`) becomes the work backlog and the backend inventory (`04_backend_surface.md`) becomes the completeness checklist.
