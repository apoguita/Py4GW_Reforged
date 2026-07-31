# FrameTree - design spec

Status: agreed requirements, not yet implemented.
Date: 2026-07-29
Background RE: `../Py4GW_Reforged_Native/docs/RE/ui_frame_identity_reverse_engineering.md`

## 1. Problem

A frame currently has four identities in this codebase - `frame_id`, name hash, `FrameInfo`
entry, alias string - and no single place converts between them. Five parallel addressing
schemes exist:

| # | mechanism | where |
|---|---|---|
| 1 | 192 free statics, `frame_id` in / `frame_id` out | `UIManager.py` (2497 lines) |
| 2 | `FrameInfo` / `WindowFrame` dataclass registry, 58 entries | `UIManager.py:1335+` |
| 3 | `frame_aliases` string table | `frame_aliases.py` |
| 4 | snapshot + query engine, unused | `UI_RE/RuntimeFrameTreeEngine.py` |
| 5 | raw calls - 61 hardcoded hash literals across 39 files | everywhere |

Each consumer reimplemented resolution, so each rotted independently. The salvage prompt
was simultaneously encoded as `[6,98]`, `[6,109]` and `[6,113]` in different files; the
live value is 113 and `[6,109]` was clicking a child of Mission Goals.

## 2. What FrameTree is

**A frame handle.** One object represents one frame. Callers never pass child offsets -
they name a registry entry and the class does the walking. It is the *only* supported way
to touch a frame.

## 3. Agreed decisions

| topic | decision |
|---|---|
| shape | frame handle; offsets are internal, never a caller argument |
| addressing | breadcrumb identifier resolved through a registry, anchored on a frame name |
| registry format | nested, child paths relative to parent |
| key style | identifier style (`SalvageMaterials.YesButton`) |
| caller reference | generated constants module, Pylance-checkable |
| failure | raise |
| freshness | snapshot rebuilt from a registered `PyCallback` PreUpdate callback |
| surface | existence/state, interaction, text, geometry, navigation - everything |
| runtime-code entries | kept, marked dynamic |
| verification | deferred; resolver must allow adding it without reshaping the registry |
| location | `Py4GWCoreLib/FrameTree/` |
| scope | becomes the only path; `UIManager` frame statics, `FrameInfo` and the 39 raw call sites migrate to it |

## 4. Registry format

Nested, so a parent moving costs one edit instead of one per descendant.

```python
REGISTRY = {
    "SalvageMaterials": ("Game", [6, 113], {
        "YesButton":     [6],
        "NoButton":      [4],
        "Label":         [1],
        "QuestionFrame": [0],
    }),
}
```

- element 0 - anchor **frame name** (resolved to a hash via `frame_names.py`)
- element 1 - code tail from the anchor
- element 2 - children, paths relative to the parent entry

Reachable as `SalvageMaterials`, `SalvageMaterials.YesButton`, ...

### Source data

`frame_aliases.py` inverts into this almost cleanly: 1205 entries, **1108 distinct labels,
only 4 collisions**, 856 already dotted. Conversion is mechanical apart from:

- 93 `NPC Nameplate Frame` entries - runtime codes, collapse to one dynamic entry
- 3 genuine duplicate labels needing disambiguation
- 2 empty labels
- prose -> identifier-style key normalisation (one-time pass over 1108)

### Dynamic entries

Codes >= `0x03000001` and `0x04000018` are allocated per session per agent. Entries whose
tail contains them are marked dynamic so the resolver can refuse or special-case them
rather than failing opaquely.

## 5. Caller API

```python
from Py4GWCoreLib.FrameTree import Frame, FrameId

f = Frame(FrameId.SalvageMaterials.YesButton)
if f.exists:
    f.click()

Frame(FrameId.Skillbar).children()            # navigation
Frame(FrameId.Chat.TextArea).text()           # decoded text
Frame(FrameId.Compass).position.width         # geometry
```

Surface (all of it - the class is the only frame API):

- **state** - `exists`, `is_visible`, `is_created`, `frame_id`, `name`, `hash`
- **interaction** - `click`, `double_click`, `hover`, `send_message`
- **text** - `text()`, `encoded()`, `set_text()`
- **geometry** - `position` (screen rect, size, scale)
- **navigation** - `parent()`, `children()`, `child(...)` for unregistered descendants

## 6. Resolution and lifetime

Snapshot rebuilt once per tick from a registered callback, mirroring `FrameCache`:

```python
PyCallback.PyCallback.Register(name, PyCallback.Phase.PreUpdate, rebuild, priority=...)
```

Resolution: registry entry -> anchor name -> `StrHashI` -> anchor `frame_id` -> walk the
code tail. Handles read the snapshot; a raise carries the entry, the anchor, the tail, and
where the walk stopped.

## 7. Data modules

Already built, at repo root:

- `frame_names.py` - 506 `hash -> name`, four evidence tiers (427 confirmed / 19 observed /
  54 harvested / 6 reconstructed) plus `NAME_TO_HASH`
- `frame_aliases.py` - 1205 label-keyed paths, verified round-trip against the original

Both are plain dict literals - no json, no `open()`, per `AGENTS.md`.

## 8. Ownership boundary

The first pass made `Frame` a **locator**: it resolves a name to a `frame_id` and forwards
every call to `UIManager`, which forwards to `PyUIManager`. That is a third hop, not
ownership. Measured on the current tree: 41 members, 12 pure one-line proxies, 13 guarded
proxies (`if not exists: return default` -> `import UIManager` -> forward). Nothing is
owned except the address.

Ownership means the package is the **only** code that touches `PyUIManager` for frame data.
Three tiers, derived from the 88 bindings `UIManager` currently wraps:

### Tier 1 - `Frame` handle (38 bindings)

Everything whose first argument is a frame identity. These move off `UIManager` entirely:

| group | bindings |
| --- | --- |
| state | `get_frame_label_by_frame_id`, `get_frame_code_by_frame_id`, `get_frame_state_bit_by_frame_id`, `get_frame_user_param_by_frame_id`, `get_frame_context` |
| geometry | `get_frame_position_ex_by_frame_id`, `get_frame_client_border_by_frame_id`, `get_frame_clip_rect_by_frame_id`, `get_frame_min_size_by_frame_id`, `get_frame_native_size_by_frame_id` |
| text | `get_text_label_decoded_by_frame_id`, `get_text_label_encoded_by_frame_id`, `get_frame_title_by_frame_id` |
| interaction | `button_click`, `test_mouse_action`, `test_mouse_click_action`, `SendFrameUIMessage`, `SendFrameUIMessageWString` |
| presentation | `set_frame_visible_by_frame_id`, `set_frame_disabled_by_frame_id`, `set_frame_layer_by_frame_id`, `get_frame_layer_by_frame_id`, `set_frame_opacity_by_frame_id`, `get_frame_opacity_by_frame_id`, `show_frame_by_frame_id` |
| navigation | `get_parent_frame_id`, `get_parent_frame_id_direct`, `get_first_child_frame_id`, `get_last_child_frame_id`, `get_next_child_frame_id`, `get_prev_child_frame_id`, `get_child_frame_by_frame_id`, `get_child_frame_id_from_name_hash`, `get_child_frame_path_by_frame_id`, `get_related_frame_id`, `get_tab_frame_id`, `get_item_frame_id`, `is_ancestor_of_by_frame_id` |

### Tier 2 - `FrameTree` (10 bindings)

Tree-wide enumeration and identity resolution - not per-handle, still frame-owned:
`get_frame_array`, `get_frame_hierarchy`, `get_root_frame_id`, `get_overlay_frame_ids`,
`get_popup_frame_ids`, `get_child_frame_id` (by parent hash), `get_frame_id_by_hash`,
`get_frame_id_by_label`, `get_hash_by_label`, `get_frame_coords_by_hash`.

### Tier 3 - stays in `UIManager` (40 bindings)

Genuinely not frame-scoped: 9 preferences, 5 keyboard, 7 client settings, 5 string
encoding, 4 UI messages, 4 window state, 2 frame logs, plus `is_ui_drawn`,
`is_world_map_showing`, `draw_on_compass`, `get_current_tooltip_address`.

`UIManager` keeps no frame accessors. Where it needs one it holds a `Frame`.

## 9. Live model

A handle must not re-read the game every time a property is touched. Today `Frame._ui()`
constructs a **new** `PyUIManager.UIFrame` per property access, so one `if f.exists and
f.is_visible` is two constructions and two context reads.

`FrameTree` keeps one live record per frame it has been asked about:

```python
class FrameState:            # populated from a single UIFrame read
    __slots__ = ('frame_id', 'hash', 'code', 'parent_id', 'type',
                 'is_created', 'is_visible', 'position', 'tick')
```

Refresh policy is **lazy per tick**, not an eager sweep. An eager sweep is not affordable:
the registry has 1223 entries and the live tree runs to several thousand frames, while a
typical tick touches under twenty. So:

- the `PreUpdate` callback bumps a tick counter and nothing else,
- first touch of a frame within a tick does one `UIFrame` read and fills its `FrameState`,
- every later read in that same tick is a dict hit,
- a tick bump invalidates; the id cache keeps its existing `version` invalidation for tree
  rebuilds.

One `UIFrame` instance per frame per tick, owned by the model, never handed out.

## 10. Services, not proxies

Scripts currently do their own state evaluation. Counted across the tree: **76**
`exists`-then-act guards, 41 one-shot state flags, 153 throttle timers and 335 wait loops
sitting around frame checks, plus 62 direct `PyUIManager.UIFrame(...)` constructions in 15
files. Each is a place where a caller decided for itself what "usable" means - which is how
four NPC windows could report `IsOpen() == False` forever without anyone noticing.

The class owns those evaluations:

- **readiness** - one `is_usable` (created, visible, non-zero geometry) instead of each
  caller composing its own conjunction
- **identity check** - a named frame carries its hash; `StrHashI(name)` must match, so the
  handle can verify it landed on the intended frame rather than a same-path impostor. This
  is exactly the check the Merchant/Crafter collision needed (both at `[0,0,0]`,
  discriminated only by hash).
- **waiting** - the wait/latch idiom belongs here once, not 335 times
- **interaction** - `click()` asserts usability before dispatching, rather than firing a
  mouse action at a frame that is not there

No caller constructs `PyUIManager.UIFrame`. No caller reads `frame_id` to hand it to
something else - the remaining escapes (`FramePosition`, `settings.FrameCoords`,
`frame_id_io_events`, `frame_id_callbacks`) become services on the handle.

## 11. Identity, and the end of the alias JSON

A live frame carries only a hash and a chain of child codes. Naming one used to mean
building a `"<hash>,<code>,<code>"` string and looking it up in `Py4GWCoreLib/frame_aliases.json`
- read with a bare `open()` + `json.load`, which the library forbids, and duplicated inside
each debug tool.

The class owns identity now, from dict literals only:

| member | source | example |
| --- | --- | --- |
| `name` | `frame_names.py`, hash -> engine name | `SkillBar`, `BtnCraft` |
| `registry_key` | `frame_registry.py`, inverted | `Skillbar.Skill7.Frame.Number` |
| `alias` | `frame_aliases.py`, inverted | `Skillbar.Skill7.Frame.Number` |
| `describe()` | all three, best-first | `SkillBar  Skillbar.Skill1  (Skill 1)` |

`alias_by_path()` and `key_by_path()` invert the alias and registry tables onto the same
path form `path()` produces. Both build once, on first use: 1205 and 1253 entries, and
every one of the 1253 registry entries resolves to a non-empty identity string.

`frame_aliases.json` is **deleted**. It was verified redundant first: same 1205 values in
the same order, same 1017 code-bearing keys, differing only in that the anchor moved from a
hash (`641635682,6,2`) to a name (`SkillBar,6,2`). `UIManager.SaveEntryToJSON`,
`GetEntryFromJSON` and `GetFrameIDByCustomLabel` are gone with it, and `UIManager` no longer
imports `JsonFactory` at all.

The frame inspectors lose their "type an alias and save it" box. Hand-naming frames was a
workaround for not knowing what the game calls them; the name tables answer that now, so the
inspectors show engine name / registry key / alias and offer *Copy Registry Key* instead.

## 12. Redesign - the class handles, scripts ask

The first two attempts produced a **locator that hands out ids**, not a handler.
Measured across live code, outside the package:

| scripts doing the class's job | sites | files |
| --- | --- | --- |
| `frame_id` leaves the class | 335 | 42 |
| `from_hash` / `from_id` raw addressing | 333 | 45 |
| `parent()` / `parent_id` tree walking | 51 | 14 |
| bind a handle only to test it once | 26 | 15 |
| `.raw` snapshot pulled out | 11 | 6 |
| guard-then-act (`if exists: click`) | 8 | 4 |
| `try/except FrameKeyError` in a script | 4 | 4 |

The escape hatches *were* the failure. `from_hash` was documented as "use only
where the path is not knowable statically", which legitimised every indexed loop
building its own offset list. `frame_id` being public meant 335 places could step
around the class entirely.

### What the 335 id reads are actually for

Categorised, none of them needs an integer:

| real need | today | redesign |
| --- | --- | --- |
| unique ImGui widget suffix (~50) | `f"...##{f.frame_id}"` | `f.widget_id` - opaque stable token |
| key a dict / list (162) | `d[f.frame_id]` | `d[f]` - Frame is hashable |
| hold a reference (35) | `self.x = f.frame_id` | `self.x = f` |
| re-wrap into a handle (32) | `Frame.from_id(f.frame_id)` | `f` |
| return across an API (30) | `-> int` | `-> Frame` |
| identify in a log (108) | `f"{f.frame_id}"` | `str(f)` -> `describe()` |
| existence test (8) | `id != 0` | `f.exists` |

### Rules

1. **No ids escape.** `frame_id`, `from_id`, `from_hash`, `raw`, `parent_id`
   become package-internal. A script cannot obtain one, so it cannot route
   around the class.
2. **Every operation is total.** No read raises and no action needs a guard:
   `click()` already no-ops when unusable, `coords()` returns zeros, `text()`
   returns `""`. `if x.exists: x.click()` collapses to `x.click()`.
3. **One readiness question.** `is_usable`. Callers never compose
   `exists and is_visible` themselves.
4. **Lookup never throws at a script.** An unknown key yields an inert handle,
   not `FrameKeyError`. The 4 `try/except` sites disappear.
5. **Indexed access is named.** `Frame.skill(i)`, `Frame.bag_slot(bag, slot)`,
   `Frame.storage_slot(tab, slot)`, `Frame.party_member(i)`. The offset
   arithmetic - including the outpost/explorable party split - lives inside the
   package. Loops never build a code list.
6. **Frame is a value type.** `__eq__`, `__hash__`, `__str__`, `__bool__` so it
   can be stored, compared, keyed and printed without unwrapping.

### Consequence

`Frame` stops being a name resolver with a proxy layer and becomes the only
thing that can *do* anything to a frame. The measure of success is that
`grep -r '\.frame_id' --include=*.py` outside the package returns nothing.

## 13. Migration progress

**Stage 1 - the class handles (done).**

- 11 named accessors take domain arguments only, so no caller builds a code
  list: `skill`, `hero_skill`, `bag_slot`, `inventory_bag`, `inventory_bag_slot`,
  `storage_tab`, `storage_slot`, `material_slot`, `party_member`, `effect`,
  `dialog_option`. Verified offline to reproduce the paths the scripts built by
  hand, including the outpost/explorable party split.
- `raw` deleted. `fields()` replaces it: every scalar the engine exposes, as
  data, with `relation.*` and `position.*` flattened in. Testers inspect
  everything without ever holding the object.
- `relation` deleted. `siblings()` returns handles, not the engine's id list.
- `parameters` surfaces the `0x84` slot as a plain list.
- Reads are total - a stale id yields empty/zero rather than raising, so a frame
  inspector can never abort an ImGui frame mid-render.

Verified across the tree, excluding the package and `UI_RE/`:

| check | result |
| --- | --- |
| `Frame(...).raw` | 0 |
| raw `relation.` traversal | 0 |
| `PyUIManager.UIFrame(` constructed | 0 |
| repo parses | 1442 files, 1 pre-existing failure (`LootEx/gui.py`) |
| `frame.py` under pyright | clean |

**Stage 2 - `Py4GWCoreLib` (done).** All 12 raw-addressing sites removed: the
NPC dialog hash, the inventory / storage / material builders, three bag-slot
helpers and one backpack path. Inventory's five `_get_*_frame_id() -> int`
helpers now return `Frame`, so callers stopped re-wrapping ids.

**Stage 3 - `Widgets` / `Sources` / `HeroAI` / `Examples` (raw addressing done).**
40 sites migrated onto named accessors. Two more accessors were added from real
call sites - `trainer_skill(skill_id)` and `capture_skill(attribute, skill_id)` -
plus `party_list()`.

Raw hash addressing across the tree:

| area | `from_hash` |
| --- | --- |
| `Py4GWCoreLib` | 0 |
| `Widgets` | 0 |
| `HeroAI` | 0 |
| `Examples` | 0 |
| `Sources` | 3 (blocked, below) |

Two sites are genuine *discovery* code - the InventoryPlus layout probe and the
LootEx salvage scan - and cannot name a path they are searching for. They now
anchor on a registered window and walk relative codes via `find_child`, so no
hash appears, but they remain the one legitimate exception to "address by name".

**Stage 4 - ids (done).** 320 -> 10, and all 10 are deliberate.

Classification, because the raw count conflated three different things:

| | count | a bypass? |
| --- | --- | --- |
| internal bookkeeping | 31 | no - dict/sort keys inside the module that built them |
| tester tier | ~150 | no - those tools take a frame id as user input |
| genuine escapes | **10** | see below |

The 10 that remain:

| what | count | why it stays |
| --- | --- | --- |
| salvage yes/no paths | 3 | **blocked** - needs a live dump |
| `Map.GetFrame()` conversions | 4 | the id arrives from a **native context struct**; this is the boundary and the right place to convert |
| `Inventory` entry graph | 2 | ids used as keys inside the module that built them from handles |
| `CHEST_FRAME_ID` fallback | 1 | a hardcoded last-resort frame id constant |

Nothing outside the package obtains a frame id in order to act on a frame.

Converted this stage: all three copies of the dialog pipeline; `FramePosition`,
`FrameCoords`, `GUI_Helpers.Frame` and the io-event registry now hold handles;
`DrawFramedContent`, `_click_frame`, `_frame_exists`, `IsElementVisible`,
`iter_frame_click`, `RegisterFrameIOEventCallback`, `GetIOEventsForFrame` take
handles; `Frame.widget_id` replaced ids in ImGui suffixes and `__str__` replaced
them in log text.

Bugs found and fixed while doing it: a hash passed to `from_id` (the Xunlai
overlay never resolved), infinite recursion in `GUI_Helpers.Frame._handle`, two
stale call sites left by earlier renames in `MerchantRules`, `mouse_action()`
called on an int, and several orphaned fields after signature changes.

## 14. Open items

1. **Verification deferred.** Named frames could self-verify for free (frame carries its
   hash; `StrHashI(name)` must match). Anonymous frames would need declared expected child
   codes. Not in the first pass, but the resolver must not preclude it.
2. **Key normalisation** - 1108 prose labels to identifier style; needs review, not blind
   transformation.
3. **3 colliding labels** need disambiguation before they can be registry keys.
4. **Migration order** for `UIManager` / `FrameInfo` / 39 raw call sites is not decided.
5. **`frame_state`** is referenced by the old engine; confirm it is still bound before use.
6. **405 of 2015** `FrameCreate` call sites remain undecoded; improving the offline scraper
   moves names from harvested to confirmed.
