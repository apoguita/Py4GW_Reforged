# ImGui Layer-2 Ergonomics Proposal (PARKED — resume later)

> **Status:** Exploratory. No code written. Parked mid-discussion to switch focus.
> **Owner context:** builds on the *completed* new-facade migration
> (`docs/ImGui_Facade_Migration_Plan.md` + `docs/ImGui_Implementation_Correction_Instructions.md`).
> This is a proposed **additive** layer, NOT a rewrite.

## Goal

Make the new `Py4GWCoreLib.ImGui` facade nicer to write against, while keeping:

- the single `ImGui = ImGuiRuntime()` singleton
- zero bridging to `ImGui_Legacy`
- the existing `with` + `.entered`/`.open` API fully working (nothing breaks)
- the immediate-mode / "re-describe the UI every frame" nature

The idea is a **Layer 2** on top of the current runtime. `with` stays. We *add*
shorter forms alongside it.

## The two annoyances we're targeting

Reference example — a Party window with a checkbox, a search box, and a table,
written the way it works **today**:

```python
with ImGui.window('Party', open=self.show_party) as win:
    if not win.entered:
        self.show_party = win.open
        return
    self.show_party = win.open

    self.only_alive = ImGui.checkbox('Only alive', self.only_alive)
    self.search     = ImGui.input.text('Search', self.search)

    with ImGui.table('members', 3) as table:
        if not table.entered:
            return
        # draw rows...
```

### Annoyance #1 — the "is it open?" guard on every block

```python
    if not win.entered:
        self.show_party = win.open
        return
    self.show_party = win.open
```

Repeats for every window/table/popup/etc. Root cause: a `with` block's body
**always runs**, even when the window is closed/collapsed, so the caller must
manually check `.entered` and bail. Also the early `return` from inside a
collapsed *table* over-aborts — it abandons the rest of the window.

### Annoyance #2 — manual value write-back

```python
    self.only_alive = ImGui.checkbox('Only alive', self.only_alive)
    self.search     = ImGui.input.text('Search', self.search)
```

Every stateful widget returns a new value the caller must store back. Forget the
`self.x =` and the widget silently becomes read-only. Classic footgun.

(There is also a related Annoyance #3 — the window `.open` value must be copied
in both branches of the guard. It gets fixed automatically by the same mechanism
as #2.)

## The two proposed fixes

Both are **independent** — we can build one, the other, or both.

### Fix A — blocks that skip themselves when not open ("iterable scopes")

Add a form of each scope that simply **does not run its body** when the window /
table / popup didn't actually open. Implemented via Python's iterator protocol
(the scope yields its result 0 times if not entered, 1 time if entered, and
always cleans up after).

```python
for win in ImGui.window('Party', open=self.show_party):
    ImGui.checkbox('Only alive', ...)
    for _ in ImGui.table('members', 3):
        # draw rows...
```

- No `if not entered: return`. No manual bail.
- A collapsed table skips only its own body; the window keeps rendering
  (fixes the over-abort).
- `for win in ...` when you need the result object; `for _ in ...` when you don't.

**Plain-language framing for non-experts:** read `for ... in ImGui.window(...)`
as "run this block **when** the window is open." The `for` keyword is just the
mechanism; it reads odd once, then disappears.

**Honest trade-off:** today's `with` guarantees deterministic cleanup even if the
body raises mid-block. The `for` form relies on CPython's prompt garbage
collection to run cleanup — reliable here because we're locked to **embedded
CPython 3.13** (not PyPy), but slightly weaker in the rare crash-mid-block case.
Therefore: **keep both.** `with` = bulletproof/explicit; `for` = short/everyday.
The existing `ImGui.frame()` stack tracker already logs any imbalance.

**Rejected alternatives for #1:**
- `sys.settrace`-based "conditional with" body-skipping — trace hook fires per
  line every frame; catastrophic in a 60fps render loop.
- Callbacks as the primary style (`window(body=fn)`) — the original plan already
  rejected this; closures hurt readability.

### Fix B — bind a widget to the value it edits ("Refs / bindings")

Let a widget read AND write its value on its own, instead of returning a value
the caller re-stores.

```python
    ImGui.checkbox('Only alive', bind=(self, 'only_alive'))
    ImGui.input.text('Search',   bind=(self, 'search'))
```

`self.only_alive` / `self.search` update by themselves. Nothing to re-save,
nothing to forget.

Design shape (a "Ref" = a small mutable value cell that stands in for C++'s
`bool*`/pointer, which Python doesn't have):

- `ImGui.ref(value)` — anonymous cell the caller holds
- `ImGui.state.ref(key, default)` — persistent, store-backed, stable identity per
  key (builds on the existing `_StateStore`)
- `ImGui.bind(obj, 'attr')` / `ImGui.bind(dct, 'key')` — two-way bind to an
  existing object attribute or dict key (lets current widget classes adopt this
  with near-zero edits)

**Backward compatible:** a widget given a raw value behaves exactly as today
(returns the new value); given a Ref/binding it mutates in place and returns
`changed: bool`. Old call sites keep working.

Fix B also removes Annoyance #3: `ImGui.window('Party', open=some_ref)` writes the
open/closed state back into the ref automatically — no more copying `win.open` in
two branches.

## The whole example with both fixes

```python
for win in ImGui.window('Party', open=self.show_party):
    ImGui.checkbox('Only alive', bind=(self, 'only_alive'))
    ImGui.input.text('Search',   bind=(self, 'search'))

    for _ in ImGui.table('members', 3):
        # draw rows...
```

Same window, same behavior — minus the guards and the re-saving.

## Optional / later (not core)

- **Decorator-registered top-level panels** — `@ImGui.panel('Party', open_key=...)`
  where the runtime owns the draw + persistence; good WidgetManager fit.
- **Row/column sugar** for tables.
- Explicitly **NOT** doing a retained/declarative widget *tree* (data → UI): it
  fights immediate-mode and loses inline reaction to `button()` returns.

## Open decisions (what to settle on resume)

1. **Which fix first** — A (skip-guard), B (bindings), or both. They're independent.
2. **Adoption stance** — additive layer (keep `with` as-is, recommended) vs. make
   the new forms the documented-primary style and mark the old guard pattern as
   legacy-compat.
3. Confirm the CPython-only cleanup trade-off for Fix A is acceptable.

## Where things stand

- New facade migration: **done** (per the two migration/correction docs).
- This Layer-2 proposal: **discussed only, nothing built.**
- User feedback during discussion: keep explanations concrete and jargon-free —
  lead with before/after use cases, not protocol names.
- Next step when resuming: pick from "Open decisions" above, then spec the chosen
  fix(es).
