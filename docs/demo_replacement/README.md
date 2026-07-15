# Demo Replacement — Context & Analysis

Context gathering for replacing the Py4GW demo/test widgets. These scripts exist to **exercise and validate the whole CPP Native backend** — the `Py*` bindings, the Python wrappers, and the datasource/context paths — from inside the live game client. Before designing a replacement we captured what the two existing demos are, what they cover, and where the gaps are.

**Related backend project:** `C:\Users\Apo\Py4GW_Reforged_Native` (the C++ DLL that publishes the `Py*` modules).

> Status: **analysis / context only.** No replacement has been designed or built yet. See `05_gaps_and_considerations.md` §5 for the open design questions to settle first.

## The two subjects

| Demo | Location | Shape | Coverage |
|---|---|---|---|
| **v1 (legacy)** | `Widgets/Coding/Py4GW_DEMO.py` (~2,780 lines, one file) | many floating windows, `GLOBAL_CACHE` + `ImGui_Legacy` | broad: 13 domains, shallow vs new backend |
| **v2 (modular)** | `Py4GW DEMO 2.0.py` + `Sources/ApoSource/py4gw_demo_src/` | one window + sidebar nav, native `PyImGui`, context structs | narrow: Map/Agents/Pathing, deep + new surface |

## Documents

**Context & analysis (start here):**
1. [`01_demo_v1_legacy.md`](01_demo_v1_legacy.md) — v1 architecture and full per-section coverage inventory.
2. [`02_demo_v2_modular.md`](02_demo_v2_modular.md) — v2 file layout, sidebar/router architecture, per-view coverage, and what it's missing vs v1.
3. [`03_coverage_matrix.md`](03_coverage_matrix.md) — side-by-side domain matrix (v1 vs v2 vs backend); the work backlog.
4. [`04_backend_surface.md`](04_backend_surface.md) — high-level backend inventory (wrappers, contexts, GLOBAL_CACHE, C++ `Py*` bindings, `GW/` managers).
5. [`05_gaps_and_considerations.md`](05_gaps_and_considerations.md) — divergences, gaps, deprecation pressures, known defects, design questions.

**Full inventories (the completeness checklists):**
6. [`06_cpp_bindings_gameplay.md`](06_cpp_bindings_gameplay.md) — every GW gameplay `Py*` binding, per-method, getters vs actions (~430 methods, 23 modules).
7. [`07_cpp_bindings_infra_io.md`](07_cpp_bindings_infra_io.md) — infra/IO/render bindings (17 modules); PyImGui high-level only (**deferred pass**).
8. [`08_contexts.md`](08_contexts.md) — native context structs ↔ `native_src/context` ctypes readers, field inventories (18 contexts).
9. [`09_python_reusable_scripts.md`](09_python_reusable_scripts.md) — existing frame/agent/event/config scripts to **harvest** code from, with a ranked shortlist.
10. [`10_python_wrapper_api.md`](10_python_wrapper_api.md) — per-domain wrapper getter/action surface (~620 getters / 240 actions, 25 wrappers).

**Plan:**
11. [`11_build_plan.md`](11_build_plan.md) — **every module → a DEMO 2.0 section**, with data path, harvest source, and phased execution order.

> Note: **PyImGui + its addons are a deferred, dedicated pass** (doc 07 has the high-level map only) — not part of the main build order.

## One-paragraph summary

DEMO v1 is a complete-but-legacy, monolithic "show every method and all data" widget built on `GLOBAL_CACHE` + `ImGui_Legacy`, covering all 13 gameplay domains but only shallowly against the new Reforged backend. DEMO v2 is an in-progress modular rewrite (proper `Sources/` package, single dockable sidebar window, native `PyImGui`, dataclass state) that exercises the *new* Reforged surface v1 never touched — `Map.MissionMap/MiniMap/WorldMap/Pregame/Pathing`, `MapProjection`, `native_src` ctypes context structs — but has only ported Map, Agents and Pathing, dropping ~10 domains. A replacement should adopt v2's shell and native-surface depth while restoring v1's breadth, and additionally cover the large set of `Py*` bindings **neither** demo touches (`PyTrade`, `PyCamera`, `PyDXOverlay`, `PyDialog`, `PyUIManager`, `PyTexture`, `PyGuild`, `PyFriendList`, `PyPacketSniffer`, `PyAgentEvents`, `PySettings`, and more).
