# Loot Config — UI Design

How the loot config is presented. Companion to `01_loot_config_design.md` (the system) — this doc
is only the interface. Plain language on purpose.

---

## 1. Two surfaces, one config

There are two places you interact with loot, driving the same underlying config:

1. **The full editor** — lives inside **System Settings**, where you do the heavy work: writing
   filters, browsing the model catalog, setting up marking, sharing.
2. **The quick access** — a small **floating window** you pop open from the editor, for the handful
   of things you flip during play (rarity toggles, master on/off, "recolour greens"). It stays on
   screen while you play; the editor does not.

The quick-access window is **toggled on and off from within the System Settings loot section** — a
button in the editor shows/hides the floating bar.

---

## 2. Where it plugs in (same pattern as the other modules)

System Settings is an `ImGui.SidebarWindow` built in
`Py4GWCoreLib/py4gwcorelib_src/system_settings/config_ui.py` from a `CATALOG` of categories. Feature
modules attach by exposing an `add_sections(win, group)` function that adds their section and tabs —
exactly how `agent_recolor` and `name_obfuscation` do it:

```python
# agent_recolor/config_ui.py — the pattern we copy
def add_sections(win, group):
    win.add_section(group, "Agent Recolor")
    win.add_tab("Agent Recolor", "Agents",  lambda: _draw_agents(c))
    win.add_tab("Agent Recolor", "Gadgets", lambda: _draw_gadgets(c))
    win.add_tab("Agent Recolor", "Status",  lambda: _draw_status(c))
```

Loot does the same. It gets its **own category** in the System Settings catalog (loot is large
enough — filters + catalog + marking + sharing — to warrant its own group rather than being a
section under "Items & Merchants"), and registers a tabbed section into it. Registration is the same
lazy-import, error-surfaced branch the `agents` category uses, so a build failure shows a visible
placeholder instead of an empty panel.

---

## 3. The full editor — tabs

One section, four tabs (mirroring agent_recolor's tabbed section):

### Tab 1 — Filters
The list of filters. Restated at the top: **"an item is picked up if any filter matches."** Each
filter renders as a collapsing header showing *name · one-line summary · live match count · an
enabled checkbox* (the checkbox is the toggle — enabling/disabling never needs the editor open).
The header body is the condition editor:

- add/remove conditions — type, rarity, model, value, quantity, dye colour, and mod conditions
  (requirement, damage, …) written in the `Item.Mods` style;
- the `unless` exceptions for that filter;
- the filter's **marking**: recolour (colour, fade on/off, hide) and beacon (on/off, preset).

Use `###stable-id` on each filter header so open/edit state survives the summary text changing.

### Tab 2 — Catalog
The hundreds of specific-model toggles. **Search is the primary control** — a text box at the top
(type-to-find) filters the grid live. Below it, an icon grid grouped by category (derived from
`ModelID` + the texture folder; only grouping is hand-maintained). Click an icon to toggle that
model on/off. This is the surface that replaces the old 403-row checkbox tree.

### Tab 3 — Marking
Global marking knobs (per-filter marking lives on the filter in Tab 1): the distance-fade steps,
the beacon presets and the nearest-N beacon cap, and master marking on/off. Manage the saved beacon
presets here (the purple preset ships as the example).

### Tab 4 — Status / Share
Per-account state and distribution: the **master enable** and per-account gates, the list of items a
running **bot has added** (transient, "4 added by VaettirBot"), **import/export** of the shared
ruleset as a file, and the **cross-account controls** — push/notify other accounts. Mirrors
agent_recolor's Status tab.

---

## 4. The quick-access floating window

- **A button in the editor** (Status tab, or a header button) — "Open Quick Access" — toggles a
  boolean. The floating window renders while that boolean is true.
- It is a plain `PyImGui.begin` window, compact, that **persists its own position** through
  `imgui.ini` (leave `NoSavedSettings` off — per the window-handling migration, don't re-add private
  position saving).
- **Contents = the everyday toggles only**, no editing:
  - master **looting on/off**;
  - the **rarity toggles** (white / blue / purple / gold / green), colour-coded like Inventory+’s
    row of coloured toggles, plus gold coins;
  - a few **marking quick-toggles** (e.g. "recolour greens", "beacon golds").
- It is the in-play HUD; the editor is where things are built. Both read and write the same config —
  the quick toggles are the per-account local toggles (§13 of the design), the editor writes the
  shared ruleset.

**Rendering note:** the quick-access window must draw even when System Settings is closed, so its
draw call hangs off the **always-on System widget** (the host that also renders the settings
window), gated by the toggle boolean — not off the settings window, which only draws when open. The
toggle boolean is a per-account setting, so each account remembers whether its quick bar is showing.

---

## 5. Module layout (mirrors agent_recolor)

```
py4gwcorelib_src/loot_config/         (or wherever the class lands)
  model.py        — filters / catalog selections / marking / toggles (data)
  store.py        — global-scope ruleset + per-account toggles (design §13)
  controller.py   — owns state; apply, broadcast-on-save, quick-access open/close bool
  config_ui.py    — add_sections(win, group) for the editor tabs
                    + draw_quick_access() for the floating window
```

`config_ui.py` exposes both `add_sections(win, group)` (registered into System Settings) and a
`draw_quick_access()` the always-on host calls each frame when the toggle is on. All durable state
lives in the controller; only transient text-input buffers live in the UI module (immediate-mode has
no memory of its own — same as agent_recolor's `_UI.buffers`).
