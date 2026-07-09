# ImGui_Legacy Functionality Categorization

## Purpose

This document classifies `ImGui_Legacy` by **what it actually does**, not by how it is currently organized.

The goal is deprecation planning:

- identify which parts are only wrappers or themed reskins
- identify which parts are genuine higher-level functionality
- identify which parts are infrastructure rather than widgets
- identify which parts should be preserved separately before `ImGui_Legacy` is retired

This is a classification document, not a migration implementation plan.


## High-Level Conclusion

`ImGui_Legacy` is **not** one coherent class.

It is a facade over at least five different concerns:

1. raw or near-raw `PyImGui` wrappers
2. themed widget reskins
3. higher-level composite controls
4. textured rendering infrastructure
5. managed-window / persistence behavior

Because of that, deprecating `ImGui_Legacy` does **not** mean all of its functionality is redundant.

The important distinction is:

- much of it is only a styled alternative to ordinary ImGui calls
- some of it is genuinely project-specific behavior that does not exist in plain `PyImGui`


## Source Modules Involved

Legacy behavior is spread across:

- [Py4GWCoreLib/ImGui_Legacy.py](Py4GWCoreLib/ImGui_Legacy.py:1)
- [Py4GWCoreLib/ImGui_Legacy_src/ImGuisrc.py](Py4GWCoreLib/ImGui_Legacy_src/ImGuisrc.py:1)
- [Py4GWCoreLib/ImGui_Legacy_src/Style.py](Py4GWCoreLib/ImGui_Legacy_src/Style.py:1)
- [Py4GWCoreLib/ImGui_Legacy_src/Textures.py](Py4GWCoreLib/ImGui_Legacy_src/Textures.py:1)
- [Py4GWCoreLib/ImGui_Legacy_src/WindowModule.py](Py4GWCoreLib/ImGui_Legacy_src/WindowModule.py:1)
- [Py4GWCoreLib/ImGui_Legacy_src/types.py](Py4GWCoreLib/ImGui_Legacy_src/types.py:1)


## Category A: Thin Wrappers Around PyImGui

These are the easiest pieces to deprecate.

They mostly forward to `PyImGui` with light argument normalization or naming convenience.

### Examples

- `new_line`
- `get_text_line_height`
- `get_text_line_height_with_spacing`
- `calc_text_size`
- `invisible_button`
- `set_cursor_pos`
- `set_cursor_screen_pos`
- `selectable`
- `color_edit3`
- `color_edit4`
- `dummy`
- `begin_child`
- `end_child`
- `begin_table`
- `end_table`
- `begin_popup`
- `end_popup`
- `begin_tooltip`
- `end_tooltip`
- `begin_combo`
- `end_combo`
- `begin_menu_bar`
- `end_menu_bar`
- `begin_main_menu_bar`
- `end_main_menu_bar`
- `begin_menu`
- `end_menu`
- `menu_item`
- `begin_popup_modal`
- `end_popup_modal`
- `tree_pop`

### Assessment

These are **not unique**.

At most they provide:

- naming consistency
- width/height tuple normalization
- some convenience defaults

### Deprecation value

High confidence deprecation candidates.

They do not justify preserving `ImGui_Legacy` as a system.


## Category B: Styled Reskins Of Standard Controls

These still map to standard ImGui control semantics, but they add custom theme colors, textures, icon grouping, or manual drawing.

They are more than one-line wrappers, but they are still fundamentally alternate presentations of standard UI controls.

### Examples

- `button`
- `small_button`
- `icon_button`
- `toggle_button`
- `toggle_icon_button`
- `image_button`
- `image_toggle_button`
- `combo`
- `checkbox`
- `radio_button`
- `input_int`
- `input_text`
- `input_float`
- `slider_int`
- `slider_float`
- `collapsing_header`
- `tree_node`
- `begin_tab_bar`
- `begin_tab_item`
- `progress_bar`
- `colored_button`

### Assessment

These are usually **not functionally unique**.

They are mostly:

- standard controls
- with project theme colors
- with project texture rendering
- with custom sizing/padding
- with custom icon/text composition

### Important nuance

Some of these are visually elaborate, especially under textured themes, but that still does not make them conceptually unique.

For deprecation purposes, these should be treated as:

- **theme-dependent presentation logic**
- not as core irreplaceable UI behavior

### Deprecation value

These should usually be replaced by either:

- direct new `ImGui` facade usage
- or a future small themed-controls package

They do **not** need the entire `ImGui_Legacy` class to survive.


## Category C: Text Formatting And Decorative Text Helpers

These functions are mostly about presentation and authoring ergonomics for text.

### Examples

- `text`
- `text_aligned`
- `text_centered`
- `text_disabled`
- `text_wrapped`
- `text_colored`
- `text_decorated`
- `text_unformatted`
- `text_scaled`
- `bullet_text`
- `objective_text`
- `hyperlink`
- `strip_markdown`
- `get_markdown_color`
- `_draw_decorator`
- `_with_font`

### Assessment

This category is mixed.

#### Not unique

Most of the basic helpers are still just:

- alternative text rendering
- alignment convenience
- color convenience
- font convenience

#### Potentially worth preserving

The following have some project-specific meaning:

- `objective_text`
- `hyperlink`
- markdown-aware text behavior

But even these are still mostly **composite text presentation helpers**, not a major subsystem.

### Deprecation value

These should not block deprecation of `ImGui_Legacy`.

If they are still valuable, they should become:

- a dedicated text helpers module
- or a small formatting surface separate from the old legacy facade


## Category D: Theme / Style System

This is real infrastructure, not just wrappers.

### Source

- [Py4GWCoreLib/ImGui_Legacy_src/Style.py](Py4GWCoreLib/ImGui_Legacy_src/Style.py:1)

### Core pieces

- `Style`
- `Style.StyleVar`
- `Style.StyleColor`
- `push_theme`
- `pop_theme`
- `set_theme`
- `reload_theme`
- `push_theme_window_style`
- `pop_theme_window_style`

### What it does

- stores theme definitions
- pushes/pops colors and style vars
- defines custom semantic colors
- loads theme data
- distinguishes default colors, custom colors, and texture colors

### Assessment

This is **real unique infrastructure**.

It is not plain `PyImGui`.

It is not just a reskin of one control.

It is an actual project theming system layered over ImGui.

### Deprecation value

Do **not** think of this as “just another widget wrapper”.

If you deprecate `ImGui_Legacy`, this theming system needs one of three outcomes:

1. retire it intentionally
2. extract it as a standalone theme subsystem
3. selectively preserve only the semantic style concepts needed by textured widgets


## Category E: Texture Rendering Infrastructure

This is another genuinely unique subsystem.

### Source

- [Py4GWCoreLib/ImGui_Legacy_src/Textures.py](Py4GWCoreLib/ImGui_Legacy_src/Textures.py:1)

### Core pieces

- `GameTexture`
- `ThemeTexture`
- `ThemeTextures`
- `TextureState`
- `TextureSliceMode`
- `RegionFlags`
- `UVRegion`

### What it does

- atlas-based texture state selection
- nine-slice / three-slice scalable rendering
- theme-dependent texture selection
- UV-region management
- draw-list rendering support for game UI style assets

### Assessment

This is **definitely unique**.

This is not a restyled button.

This is the rendering machinery that makes the textured legacy look possible.

### Deprecation value

If the project still wants textured Guild Wars-style controls, this subsystem is the part worth preserving.

If the project no longer wants textured controls, then this entire subsystem becomes optional.

But it should be evaluated as infrastructure, not as a mere wrapper.


## Category F: Managed Window Behavior

This is one of the most important unique categories.

### Sources

- [Py4GWCoreLib/ImGui_Legacy_src/WindowModule.py](Py4GWCoreLib/ImGui_Legacy_src/WindowModule.py:1)
- [Py4GWCoreLib/ImGui_Legacy_src/ImGuisrc.py](Py4GWCoreLib/ImGui_Legacy_src/ImGuisrc.py:286)

### Core pieces

- `Begin`
- `BeginWithClose`
- `End`
- `begin`
- `begin_with_close`
- `WindowModule`

### What it does

This is more than raw `PyImGui.begin/end`.

It adds:

- `IniManager` integration
- persisted window configuration
- tracked begin/end lifecycle
- managed collapsed-state behavior
- textured custom title-bar / close-button / drag behavior for textured themes
- theme-aware window decoration

### Assessment

This is **unique behavior**.

This is not just a restyled `begin`.

The raw `PyImGui` equivalent does not provide:

- project window persistence policy
- `IniManager` lifecycle integration
- custom Guild Wars-style decorated windows
- `WindowModule`-managed per-window state

### Deprecation value

This is a subsystem that must be treated carefully.

If `ImGui_Legacy` is deprecated, this behavior needs a decision:

1. reimplement it in a new managed-window module
2. keep `WindowModule` as a separate legacy-support subsystem
3. intentionally drop textured decorated windows and keep only persistence logic

This category should **not** be dismissed as a simple wrapper.


## Category G: Composite Interaction Helpers

These are not infrastructure, but they are more than simple wrappers.

They combine multiple low-level ImGui operations into reusable higher-level controls.

### Examples

- `begin_selectable`
- `end_selectable`
- `custom_selectable`
- `search_field`
- `keybinding`
- `show_tooltip`
- `format_hotkey`

### Assessment

These are **moderately unique**.

They are not fundamentally new UI primitives, but they do encode reusable interaction patterns:

- selectable container behavior
- search box with extra affordances
- modal hotkey capture
- tooltip conventions

### Deprecation value

These are good candidates for extraction into:

- `interaction_helpers`
- `input_helpers`
- `editor_helpers`

They do not justify preserving the entire legacy facade, but some of them are worth keeping.


## Category H: Floating / Overlay-Style Helpers

These are more specialized and clearly project-facing.

### Examples

- `floating_button`
- `floating_toggle_button`
- `floating_checkbox`
- `PushTransparentWindow`
- `PopTransparentWindow`
- `FloatingIcon`

### Assessment

This category is mixed.

#### Simple overlay helpers

- `floating_button`
- `floating_toggle_button`
- `floating_checkbox`
- transparent-window push/pop helpers

These are mainly convenience composites.

#### Truly unique component

- `FloatingIcon`

`FloatingIcon` is a genuine higher-level controller:

- persistent visibility state
- persisted icon config
- draggable icon window
- tooltip switching based on visibility state
- callback-based controlled UI toggling
- synchronization with normal begin-with-close behavior

### Deprecation value

`FloatingIcon` is a **real standalone component** and should be considered unique.

If it is still useful, it should be extracted as its own supported module rather than left buried inside `ImGui_Legacy`.


## Category I: Rich Text / Markup Rendering

This is one of the clearest unique higher-level behaviors.

### Examples

- `render_wrapped_bullet`
- `render_wrapped_objective`
- `render_tokenized_markup`
- `DrawTextWithTitle`

### Assessment

`render_tokenized_markup` is **genuinely unique**.

It is not plain ImGui at all.

It encodes:

- token-based Guild Wars-style markup rendering
- color stack handling
- bullet/objective semantics
- wrapped objective layout

This is domain-specific UI rendering logic.

### Deprecation value

This should be treated as a separate feature candidate, not as disposable theming glue.

If deprecating `ImGui_Legacy`, decide whether this becomes:

- a dedicated markup renderer module
- a quest/objective rendering helper
- or a bot/overlay text utility package


## Category J: Texture-Based Drawing Utilities

These are direct rendering helpers that sit between texture infrastructure and actual widgets.

### Examples

- `DrawTexture`
- `DrawTextureExtended`
- `DrawTexturedRect`
- `DrawTexturedRectExtended`
- `DrawTextureInForegound`
- `DrawTextureInDrawList`
- `GetModelIDTexture`
- `image`

### Assessment

These are not basic ImGui controls.

They are project-specific rendering helpers tied to:

- game textures
- atlas UVs
- draw lists
- model-id-to-texture mapping

### Deprecation value

This category is more infrastructure-adjacent than widget-adjacent.

If texture-based UI remains important, these should probably survive in some form outside `ImGui_Legacy`.


## Category K: Legacy / Experimental Window System

### Example

- nested class `gw_window`

### Assessment

This appears to be an older custom-textured window renderer separate from `WindowModule`.

It likely overlaps with `WindowModule` significantly.

Its main traits:

- manual atlas-region window drawing
- custom title bar / border rendering
- internal collapsed-state tracking

### Deprecation value

This is a likely **legacy-within-legacy** piece.

It should be reviewed skeptically:

- if unused, remove it
- if lightly used, migrate its few needed ideas into the surviving window system
- do not preserve it automatically just because it is custom


## Practical Classification Summary

### Category 1: Safe To Deprecate First

These are mostly wrappers or presentation sugar:

- raw PyImGui pass-throughs
- simple text helpers
- simple input helpers
- simple standard controls
- simple begin/end aliases

### Category 2: Likely Replaceable, But Not Trivial

These are reskins or composites:

- themed buttons / toggles / image buttons
- combo / checkbox / radio / sliders
- collapsing headers / tab bars with themed behavior
- floating button helpers
- searchable input convenience
- selectable container helpers

### Category 3: Genuinely Unique And Worth Separate Evaluation

These are the parts most likely worth preserving independently:

- `Style` theme system
- `Textures` subsystem
- `WindowModule`
- `Begin` / `End` persistence behavior
- `FloatingIcon`
- `render_tokenized_markup`
- wrapped objective / quest markup helpers
- keybinding capture control
- texture drawing helpers
- model-id texture lookup helpers

### Category 4: Likely Dead-End Legacy

These need explicit justification to survive:

- `gw_window`
- any duplicate custom window path overlapping `WindowModule`


## Recommended Deprecation Strategy

Do not deprecate `ImGui_Legacy` as if all methods are equal.

Instead treat it as four extraction decisions:

### 1. Drop the wrappers

Deprecate direct wrapper methods aggressively.

These should not drive architecture.

### 2. Decide whether textured UI still matters

If yes:

- preserve `Style`
- preserve `Textures`
- preserve whichever managed-window path actually matters

If no:

- a very large part of `ImGui_Legacy` can be retired

### 3. Extract the genuinely reusable high-level helpers

Best candidates:

- `FloatingIcon`
- `render_tokenized_markup`
- `keybinding`
- `begin_selectable` / `custom_selectable`
- `search_field`

### 4. Remove internal overlap

Before long-term preservation, determine whether both of these are needed:

- `WindowModule`
- `gw_window`

They should not both survive by default.


## Most Important Final Takeaway

If the question is:

> "What in `ImGui_Legacy` is actually unique, and what is just another reskin?"

The shortest accurate answer is:

### Mostly not unique

- standard controls
- text helpers
- input helpers
- begin/end aliases
- simple convenience wrappers

### Actually unique

- theme/style system
- texture atlas / sliced rendering system
- managed decorated window system
- persistent floating icon controller
- markup/objective rendering helpers
- modal hotkey capture helper

That is the boundary that should drive deprecation.
