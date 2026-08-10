# Assets

Status: current

This directory owns shared, shipped assets used by the injected Py4GW runtime.

| Path | Owner and contents |
|---|---|
| `Textures/` | Shared runtime UI, item, skill, profession, and module textures. Python consumers pass these paths to the native texture loader. |
| `Fonts/` | Fonts loaded by the native ImGui runtime. The sibling `Py4GW_Reforged_Native` project resolves them from `Assets/Fonts/` beside the DLL. |
| `Styles/` | Bundled read-only `*.default.json` style definitions. User-edited styles remain in `json/Global/Styles/` through `JsonFactory`. |
| `Branding/` | Shared project icons used by runtime widgets and legacy examples. |

Project-local images remain with their project owner, for example
`Widgets/Config/textures/`, `Bots/*/textures/`, and the launcher web assets.
