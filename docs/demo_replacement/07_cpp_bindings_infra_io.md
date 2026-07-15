# C++ Bindings — Infra / IO / Rendering

Inventory of the **infrastructure / IO / rendering** pybind11 binding surface exposed by the Py4GW Reforged Native DLL (`Py4GW.dll`). Source root: `C:\Users\Apo\Py4GW_Reforged_Native\src\`. This covers every non-gameplay `Py*` module so a demo/test widget can exercise every binding and data getter. Gameplay modules (`PyAgent`, `PyMap`, `PyParty`, …) are covered by a separate document.

Module registration is confirmed in `src\base\python_runtime.cpp` (`kEmbeddedModules`, lines ~399-439). The 39 embedded modules are imported at startup; the infra/IO/render subset documented here is:

`Py4GW` (+`SharedMemory`), `PySystem`, `PySettings`, `PyProfiler`, `PyCallback`, `PyListeners`, `PyAgentEvents`, `PyGameThread`, `PyPing`, `PyRender`, `PyScanner`, `PyTexture`, `PyOverlay`, `PyDXOverlay`, `PyKeystroke`, `PyMouse`, `PyImGui`.

**Legend for the "kind" column:** `getter` = pure data read (no side effect), `action` = mutates state / performs an operation, `ctor` = constructor, `field` = readable/writable data member, `enum` = enum type, `static` = static class method.

---

## Py4GW (+ SharedMemory submodule)

Source: `src\base\python_runtime.cpp` (lines ~327-346). The `Py4GW` module is intentionally minimal (per migration: reduced to `version()` + `SharedMemory`).

### Module-level free functions

| member | kind | signature/return | purpose |
|---|---|---|---|
| `version` | getter | `() -> str` | Library version string (currently `"0.1.0"`). |

### `Py4GW.SharedMemory` submodule (free functions)

| member | kind | signature/return | purpose |
|---|---|---|---|
| `is_ready` | getter | `() -> bool` | Whether the per-process runtime shared-memory region is valid/mapped. |
| `get_name` | getter | `() -> str` | The runtime shared-memory region name. |
| `get_size` | getter | `() -> int` | Size of the shared-memory region in bytes. |
| `get_sequence` | getter | `() -> int` | Header sequence counter (0 if header not available). |

---

## PySystem

Source: `src\system\system_bindings.cpp`. Provides console, process environment, GW window control, script lifecycle, and widget-manager host control. Organized as the root module plus five submodules (`Console`, `environment`, `window`, `script_control`, `widget_manager`).

### Enums

| enum | values | purpose |
|---|---|---|
| `MessageType` | 8 (`Info`, `Warning`, `Error`, `Debug`, `Success`, `Performance`, `Notice`, `Hook`) | Console message severity/category. |

### Classes

**`ConsoleMessage`** (read-only data record for a buffered console line):

| member | kind | signature/return | purpose |
|---|---|---|---|
| `timestamp` | field (ro) | `int` | Raw tick timestamp. |
| `display_timestamp` | field (ro) | `str` | Formatted timestamp for display. |
| `module_name` | field (ro) | `str` | Originating module/sender name. |
| `level` | field (ro) | `str` | Level string. |
| `message_type` | field (ro) | `MessageType` | Structured severity. |
| `message` | field (ro) | `str` | Message body. |
| `__repr__` | method | `() -> str` | Formatted one-line representation. |

### Root module free functions

| member | kind | signature/return | purpose |
|---|---|---|---|
| `get_tick_count64` | getter | `() -> int` | Frame timestamp tick count (64-bit). |
| `get_shared_memory_name` | getter | `() -> str` (wstr) | Current per-process runtime shared-memory name. |
| `get_credits` | getter | `() -> str` | Library credits. |
| `get_license` | getter | `() -> str` | Library license. |
| `change_working_directory` | action | `(path) -> ...` | Change the process working directory. |
| `request_shutdown_prompt` | action | `() -> None` | Open the shutdown confirmation modal. |
| `cancel_shutdown_prompt` | action | `() -> None` | Dismiss a pending shutdown modal. |
| `is_shutdown_prompt_pending` | getter | `() -> bool` | Whether the shutdown modal is pending. |
| `in_character_select_screen` | getter | `() -> bool` | Whether the char-select screen is ready. |
| `has_account_email` | getter | `() -> bool` | Whether the account anchor email is resolved. |
| `get_account_email` | getter | `() -> str` | Account email (persistence anchor); empty until resolved. |
| `get_settings_directory` | getter | `() -> str` | Per-account settings directory; empty until anchored. |

### `PySystem.Console` submodule

| member | kind | signature/return | purpose |
|---|---|---|---|
| `MessageType` | attr | (alias of root enum) | Re-exported enum. |
| `Log` | action | `(sender, message, message_type=Info)` | Write a console message. |
| `get_projects_path` | getter | `() -> str` | Path where `Py4GW.dll` lives. |
| `get_gw_window_handle` | getter | `() -> int` | GW window handle as integer. |
| `write` | action | `(module_name, message, level="INFO")` | Write message (string-level overload). |
| `write` | action | `(module_name, message, message_type)` | Write message (enum overload). |
| `get_messages` | getter | `() -> list[ConsoleMessage]` | All buffered messages. |
| `get_messages` | getter | `(message_type) -> list[ConsoleMessage]` | Buffered messages of one type. |
| `filter_messages` | getter | `(module_name="", level="", contains="")` | Filter buffered messages. |
| `clear_messages` | action | `() -> None` | Clear the console buffer. |
| `set_output_to_file` | action | `(enabled)` | Mirror console to injection log file. |
| `get_output_to_file` | getter | `() -> bool` | Whether mirroring to file is on. |
| `set_draw_console` | action | `(enabled)` | Show/hide full console window. |
| `get_draw_console` | getter | `() -> bool` | Whether full console is shown. |
| `set_draw_compact_console` | action | `(enabled)` | Show/hide compact console window. |
| `get_draw_compact_console` | getter | `() -> bool` | Whether compact console is shown. |
| `toggle_console` | action | `() -> None` | Toggle full console window. |
| `toggle_compact_console` | action | `() -> None` | Toggle compact console window. |

### `PySystem.environment` submodule

| member | kind | signature/return | purpose |
|---|---|---|---|
| `get_gw_window_handle` | getter | `() -> int` | GW window handle. |
| `get_projects_path` | getter | `() -> str` | DLL directory path. |

### `PySystem.window` submodule (GW window control — all actions except queries)

| member | kind | signature/return | purpose |
|---|---|---|---|
| `resize_window` | action | `(width, height)` | Resize the GW window. |
| `move_window_to` | action | `(x, y)` | Move the GW window. |
| `set_window_geometry` | action | `(x, y, width, height)` | Set window geometry. |
| `get_window_rect` | getter | `() -> (l,t,r,b)` | Window rectangle. |
| `get_client_rect` | getter | `() -> (l,t,r,b)` | Client rectangle. |
| `set_window_active` | action | `()` | Focus the window. |
| `set_window_title` | action | `(title)` (wstr) | Set window title. |
| `is_window_active` | getter | `() -> bool` | Window focused? |
| `is_window_minimized` | getter | `() -> bool` | Window minimized? |
| `is_window_in_background` | getter | `() -> bool` | Window in background? |
| `set_borderless` | action | `(enable)` | Toggle borderless mode. |
| `set_always_on_top` | action | `(enable)` | Toggle always-on-top. |
| `flash_window` | action | `(repeat_count=1)` | Flash taskbar button. |
| `request_attention` | action | `()` | Flash until foregrounded. |
| `get_z_order` | getter | `() -> int` | Z-order index. |
| `set_z_order` | action | `(insert_after=0)` | Set Z-order relative to another window. |
| `send_window_to_back` | action | `()` | Send to bottom of Z-stack. |
| `bring_window_to_front` | action | `()` | Bring to front of Z-stack. |
| `transparent_click_through` | action | `(enable)` | Make window click-through. |
| `adjust_window_opacity` | action | `(alpha)` | Set opacity 0-255. |
| `hide_window` | action | `()` | Hide the window. |
| `show_window` | action | `()` | Show the window if hidden. |

### `PySystem.script_control` submodule

| member | kind | signature/return | purpose |
|---|---|---|---|
| `load` | action | `(path) -> ...` | Set + load a Python script. |
| `run` | action | `()` | Run the loaded script. |
| `stop` | action | `()` | Stop the running script. |
| `pause` | action | `()` | Pause the running script. |
| `resume` | action | `()` | Resume the paused script. |
| `status` | getter | `() -> status` | Current script status. |
| `defer_load_and_run` | action | `(path, delay_ms=1000)` | Stop-if-needed, then load+run after delay. |
| `defer_stop_load_and_run` | action | `(path, delay_ms=1000)` | Force stop, then load+run after delay. |
| `defer_stop_and_run` | action | `(delay_ms=1000)` | Stop current, then rerun it after delay. |

### `PySystem.widget_manager` submodule

| member | kind | signature/return | purpose |
|---|---|---|---|
| `start` | action | `()` | Load and run the widget-manager script. |
| `stop` | action | `()` | Stop the widget-manager script. |
| `status` | getter | `() -> status` | Widget-manager run status. |

---

## PySettings

Source: `src\settings\settings_bindings.cpp`. Per-account INI settings. The single class `settings` (bound as `PySettings.settings`) is a handle to a named settings document; the module also has account-copy free functions. Keys may be flat (land in default section `"settings"`) or `"section/key"`. Autosaves on a debounce — `save`/`reload` are escape hatches only.

### Class `settings` (ctor + methods)

| member | kind | signature/return | purpose |
|---|---|---|---|
| `__init__` | ctor | `(name, scope="account")` | Bind to a named document. scope ∈ `account`/`global`/`root`. |
| `write` | action | `(key, value: bool\|int\|float\|str)` | Write a value (type by overload); flat/`section/key`. |
| `read` | getter | `(key, default_or_type=str) -> value` | Read with default value **or** a type token (`bool`/`int`/`float`/`str`). |
| `save` | action | `()` | Force an immediate save (escape hatch). |
| `reload` | action | `()` | Re-read from disk, discard unsaved changes. |
| `is_dirty` | getter | `() -> bool` | Unsaved changes pending? |
| `is_bound` | getter | `() -> bool` | Attached to a disk file yet? |
| `path` | getter | `() -> str` | Absolute on-disk path (empty until bound). |
| `has_key` | getter | `(key) -> bool` | Key exists (flat/`section/key`)? |
| `keys` | getter | `(section="settings") -> list[str]` | Keys in a section. |
| `sections` | getter | `() -> list[str]` | All section names. |
| `delete` | action | `(key) -> bool` | Delete a key (flat/`section/key`). |
| `delete_section` | action | `(section) -> bool` | Delete a whole section. |
| `set` | action | `(section, key, value: bool\|int\|float\|str)` | Explicit (section,key) write; no delimiter parsing. |
| `get` | getter | `(section, key, default_or_type=str) -> value` | Explicit (section,key) read w/ default or type token. |
| `has` | getter | `(section, key) -> bool` | Explicit (section,key) existence. |
| `remove` | action | `(section, key) -> bool` | Explicit (section,key) delete. |
| `items` | getter | `(section) -> list[(str,str)]` | (key,value) string pairs for a section. |

### Module-level free functions

| member | kind | signature/return | purpose |
|---|---|---|---|
| `copy_document_to_account` | action | `(name, target_email) -> ...` | Copy entire document into another account's file on disk. |
| `copy_section_to_account` | action | `(name, section, target_email)` | Copy one section into another account's file. |
| `copy_keys_to_account` | action | `(name, section, keys, target_email)` | Copy a named subset of keys into another account's file. |
| `apply_section_to_account` | action | `(name, section, values, target_email)` | Overlay a key/value mapping into another account's section. |
| `is_anchored` | getter | `() -> bool` | Account-scoped docs bound to disk yet? |
| `get_settings_directory` | getter | `() -> str` | Per-account settings directory (empty until anchored). |

---

## PyProfiler

Source: `src\profiler\profiler_bindings.cpp`. Performance counters. All free functions (no classes/enums).

| member | kind | signature/return | purpose |
|---|---|---|---|
| `get_metric_names` | getter | `() -> list[str]` | All profiler metric names. |
| `get_reports` | getter | `() -> list[(name,min,avg,p50,p95,p99,max)]` | Per-metric statistical reports. |
| `get_history` | getter | `(metric_name) -> list` | Sample history for a metric. |
| `reset` | action | `()` | Clear all profiler history. |
| `start` | action | `(name)` | Begin timing a named metric. |
| `end` | action | `(name)` | End timing a named metric (uses current frame stamp). |

---

## PyCallback

Source: `src\callback\callback_bindings.cpp`. Frame callback scheduler with phased execution and priorities. One class (all static methods) + two enums.

### Enums

| enum | values | purpose |
|---|---|---|
| `Phase` | 3 (`PreUpdate`, `Data`, `Update`) — `export_values()` | Execution phase within a frame. |
| `Context` | 3 (`Update`, `Draw`, `Main`) — `export_values()` | Execution context/thread. |

### Class `PyCallback` (all static)

| member | kind | signature/return | purpose |
|---|---|---|---|
| `Register` | static/action | `(name, fn, phase, priority=99, context=Draw) -> id` | Register a frame callback. |
| `RemoveById` | static/action | `(id)` | Remove a callback by id. |
| `RemoveByName` | static/action | `(name)` | Remove a callback by name. |
| `PauseById` | static/action | `(id)` | Pause a callback. |
| `ResumeById` | static/action | `(id)` | Resume a callback. |
| `IsPaused` | static/getter | `(id) -> bool` | Is the callback paused? |
| `IsRegistered` | static/getter | `(id) -> bool` | Is the callback registered? |
| `Clear` | static/action | `()` | Remove all callbacks. |
| `GetCallbackInfo` | static/getter | `() -> list[tuple]` | Info tuples for all callbacks. |

---

## PyListeners

Source: `src\listeners\listeners_bindings.cpp`. Runtime toggles for native game-event listeners (by name). All free functions.

| member | kind | signature/return | purpose |
|---|---|---|---|
| `list` | getter | `() -> list[str]` | Names of all toggleable listeners. |
| `enable` | action | `(name)` | Enable a listener. |
| `disable` | action | `(name)` | Disable a listener. |
| `toggle` | action | `(name)` | Toggle a listener. |
| `set_enabled` | action | `(name, enabled)` | Set a listener's enabled state. |
| `is_enabled` | getter | `(name) -> bool` | Is a listener enabled? |

---

## PyAgentEvents

Source: `src\listeners\agent_events_bindings.cpp`. Per-agent event capture (a named listener, enabled by default). One class + one constant submodule + free functions. All interpretation stays in Python.

### `PyAgentEvents.PyEventType` submodule

Event-type integer constants, generated from the `GW_AGENT_EVENT_TYPES` X-macro (each entry becomes a `uint32` attribute on the submodule). Count matches that X-macro; treat as a name→int lookup table (e.g. damage, cast, buff events). Enumerate at runtime via `dir(PyAgentEvents.PyEventType)`.

### Class `PyRawAgentEvent`

| member | kind | signature/return | purpose |
|---|---|---|---|
| `__init__` | ctor | `()` | Default constructor. |
| `timestamp` | field (ro) | `int` | Event timestamp. |
| `event_type` | field (ro) | `int` | Event type (matches `PyEventType`). |
| `agent_id` | field (ro) | `int` | Source agent id. |
| `value` | field (ro) | `int` | Integer payload. |
| `target_id` | field (ro) | `int` | Target agent id. |
| `float_value` | field (ro) | `float` | Float payload. |
| `agent_max_hp` | field (ro) | `int` | Source agent max HP. |
| `agent_max_energy` | field (ro) | `int` | Source agent max energy. |
| `target_max_hp` | field (ro) | `int` | Target max HP. |
| `target_max_energy` | field (ro) | `int` | Target max energy. |
| `__repr__` | method | `() -> str` | Debug representation. |
| `as_tuple` | getter | `() -> (ts,type,agent,value,target,float)` | Compact tuple form. |

### Module-level free functions

| member | kind | signature/return | purpose |
|---|---|---|---|
| `enable` | action | `()` | Install capture hooks, start recording. |
| `disable` | action | `()` | Remove hooks, clear buffer. |
| `is_enabled` | getter | `() -> bool` | Capture active? |
| `get_and_clear_events` | getter+action | `() -> list[PyRawAgentEvent]` | Drain captured events (call each frame). |
| `peek_events` | getter | `() -> list[PyRawAgentEvent]` | Read without clearing (debug). |
| `get_event_count` | getter | `() -> int` | Number of buffered events. |
| `get_capacity` | getter | `() -> int` | Buffer capacity. |

---

## PyGameThread

Source: `src\GW\game_thread\game_thread_bindings.cpp`. Enqueue Python callables to run on the GW game thread. All free functions.

| member | kind | signature/return | purpose |
|---|---|---|---|
| `clear_calls` | action | `()` | Clear queued game-thread calls. |
| `is_in_game_thread` | getter | `() -> bool` | Currently executing on the game thread? |
| `enqueue` | action | `(fn)` | Enqueue a Python callable to run on the GW game thread (GIL-safe; guarded by a map-ready check; errors reported to console). |

---

## PyPing

Source: `src\GW\ping\ping_bindings.cpp`. Ping tracker. One class (`PingHandler`); construct then poll.

| member | kind | signature/return | purpose |
|---|---|---|---|
| `__init__` | ctor | `()` | Create a ping tracker. |
| `Terminate` | action | `()` | Tear down the tracker. |
| `GetCurrentPing` | getter | `() -> int` | Current ping. |
| `GetAveragePing` | getter | `() -> int` | Average ping. |
| `GetMinPing` | getter | `() -> int` | Minimum observed ping. |
| `GetMaxPing` | getter | `() -> int` | Maximum observed ping. |

---

## PyRender

Source: `src\GW\render\render_bindings.cpp`. Render-loop / viewport queries. All free functions, all getters.

| member | kind | signature/return | purpose |
|---|---|---|---|
| `get_is_in_render_loop` | getter | `() -> bool` | Inside the render loop right now? |
| `get_is_fullscreen` | getter | `() -> int` | Fullscreen flag. |
| `get_viewport_width` | getter | `() -> int` | Viewport width in pixels. |
| `get_viewport_height` | getter | `() -> int` | Viewport height in pixels. |
| `get_field_of_view` | getter | `() -> float` | Camera field of view. |

---

## PyScanner

Source: `src\base\scanner_bindings.cpp`. Memory pattern scanner (RE parity surface). One class `PyScanner`, all static methods. Sections are raw `uint8` indices: `0=.text`, `1=.rdata`, `2=.data`.

| member | kind | signature/return | purpose |
|---|---|---|---|
| `Initialize` | static/action | `(module_name="")` | Initialize scanner over a module (default: main). |
| `Find` | static/getter | `(pattern: bytes, mask, offset, section) -> addr` | Pattern scan within a section. |
| `FindInRange` | static/getter | `(pattern, mask, offset, start, end) -> addr` | Pattern scan within an address range. |
| `FunctionFromNearCall` | static/getter | `(call_addr, check_valid_ptr=true) -> addr` | Resolve target of a near-call instruction. |
| `ToFunctionStart` | static/getter | `(addr, scan_range=0xFF) -> addr` | Walk back to function prologue. |
| `IsValidPtr` | static/getter | `(addr, section) -> bool` | Is the pointer valid within a section? |
| `FindUseOfAddress` | static/getter | `(address, offset, section) -> addr` | First code use of an address. |
| `FindNthUseOfAddress` | static/getter | `(address, nth, offset, section) -> addr` | Nth code use of an address. |
| `FindUseOfStringA` | static/getter | `(str, offset, section) -> addr` | First use of an ANSI string. |
| `FindUseOfStringW` | static/getter | `(wstr, offset, section) -> addr` | First use of a wide string. |
| `FindNthUseOfStringA` | static/getter | `(str, nth, offset, section) -> addr` | Nth use of an ANSI string. |
| `FindNthUseOfStringW` | static/getter | `(wstr, nth, offset, section) -> addr` | Nth use of a wide string. |
| `FindAssertion` | static/getter | `(assertion_file, assertion_msg, line_number=0, offset=0) -> addr` | Locate a GW assertion callsite. |
| `GetSectionAddressRange` | static/getter | `(section) -> (start, end)` | Address range of a PE section. |
| `GetScanStatus` | static/getter | `() -> {"scans":{...}, "hooks":{...}}` | Scan + hook resolution status dict. |

---

## PyTexture

Source: `src\GW\textures\texture_bindings.cpp`. Texture access. Returns an ImGui texture handle (the D3D9 texture pointer as an int; `0` when not ready), usable directly with `PyImGui.image()`. All free functions.

| member | kind | signature/return | purpose |
|---|---|---|---|
| `get_file_texture` | getter/action | `(path) -> int` | Load texture from file (PNG/JPG/BMP via WIC). Cached. |
| `get_dat_texture` | getter/action | `(key) -> int` | Load texture by cache key (`gwdat://<file_id>` routes to GW.dat). |
| `get_texture_by_file_id` | getter/action | `(file_id) -> int` | Load from GW.dat by file id (async; 0 until upload done). |
| `get_colored_model_texture` | getter/action | `(model_file_id, dye_tint=0, dye1=0, dye2=0, dye3=0, dye4=0) -> int` | Load a dyed model texture from GW.dat (async). |
| `cleanup_old_textures` | action | `(timeout_seconds=30)` | Release textures unused past the timeout. |

---

## PyOverlay

Source: `src\overlay\overlay_bindings.cpp`. In-game ImGui-backed drawing overlay + coordinate transforms, plus a separate desktop `ScreenOverlay` and the `Vec2f`/`Vec3f` value types (legacy `Point2D`/`Point3D` were replaced — see migration notes). Bound via `bind_Vec2f`, `bind_Vec3f`, `bind_overlay`, `bind_ScreenOverlay`.

### Value types

**`Vec2f`**: ctor `()` / `(x, y)`; read-write fields `x`, `y`.
**`Vec3f`**: ctor `()` / `(x, y, z=0.0)`; read-write fields `x`, `y`, `z`.

### Class `Overlay`

| member | kind | signature/return | purpose |
|---|---|---|---|
| `__init__` | ctor | `()` | Create an overlay. |
| `RefreshDrawList` | action | `()` | Refresh the underlying draw list. |
| `GetMouseCoords` | getter | `() -> coords` | Current mouse coordinates. |
| `FindZ` | getter | `(x, y, pz=0) -> z` | Resolve terrain Z at a point. |
| `FindZPlane` | getter | `(x, y, z=0)` | Resolve Z plane. |
| `WorldToScreen` | getter | `(x, y, z)` | World → screen projection. |
| `GetMouseWorldPos` | getter | `() -> pos` | Mouse position in world coords. |
| `GamePosToWorldMap` | getter | `(x, y)` | Game → world-map coords. |
| `WorldMapToGamePos` | getter | `(x, y)` | World-map → game coords. |
| `WorldMapToScreen` | getter | `(x, y)` | World-map → screen. |
| `ScreenToWorldMap` | getter | `(x, y)` | Screen → world-map. |
| `GameMapToScreen` | getter | `(x, y)` | Game-map → screen. |
| `ScreenToGameMapPos` | getter | `(x, y)` | Screen → game-map. |
| `NormalizedScreenToScreen` | getter | `(norm_x, norm_y)` | Normalized → screen. |
| `ScreenToNormalizedScreen` | getter | `(screen_x, screen_y)` | Screen → normalized. |
| `NormalizedScreenToWorldMap` | getter | `(norm_x, norm_y)` | Normalized → world-map. |
| `NormalizedScreenToGameMap` | getter | `(norm_x, norm_y)` | Normalized → game-map. |
| `GamePosToNormalizedScreen` | getter | `(x, y)` | Game pos → normalized screen. |
| `BeginDraw` | action | `()` / `(name)` / `(name, x, y, w, h)` | Begin a draw block (3 overloads). |
| `EndDraw` | action | `()` | End the draw block. |
| `DrawLine` | action | `(from, to, color=0xFFFFFFFF, thickness=1.0)` | 2D line. |
| `DrawLine3D` | action | `(from, to, color, thickness)` | 3D line. |
| `DrawTriangle` / `DrawTriangle3D` | action | `(p1,p2,p3,color,thickness)` | Outlined triangle (2D/3D). |
| `DrawTriangleFilled` / `DrawTriangleFilled3D` | action | `(p1,p2,p3,color)` | Filled triangle (2D/3D). |
| `DrawQuad` / `DrawQuad3D` | action | `(p1..p4,color,thickness)` | Outlined quad (2D/3D). |
| `DrawQuadFilled` / `DrawQuadFilled3D` | action | `(p1..p4,color)` | Filled quad (2D/3D). |
| `DrawPoly` / `DrawPoly3D` | action | `(center, radius, color, numSegments=12, thickness, [autoZ])` | Outlined polygon/circle (2D/3D). |
| `DrawPolyFilled` / `DrawPolyFilled3D` | action | `(center, radius, color, numSegments, [autoZ])` | Filled polygon (2D/3D). |
| `DrawCubeOutline` | action | `(center, size, color, thickness)` | Wireframe cube. |
| `DrawCubeFilled` | action | `(center, size, color)` | Filled cube. |
| `DrawText` | action | `(position, text, color, centered=true, scale=1.0)` | 2D text. |
| `DrawText3D` | action | `(position3D, text, color, autoZ, centered, scale)` | 3D text. |
| `GetDisplaySize` | getter | `() -> size` | Display size. |
| `IsMouseClicked` | getter | `(button=0) -> bool` | Mouse-click query. |
| `PushClipRect` / `PopClipRect` | action | `(x,y,x2,y2)` / `()` | Clip-rect stack. |
| `DrawTexture` | action | 2 overloads `(path, w, h)` / `(path, size, uv0, uv1, tint, border_col)` | Draw a texture. |
| `DrawTexturedRect` | action | 2 overloads `(x,y,w,h,path)` / `(pos, size, path, uv0, uv1, tint)` | Draw a textured rect. |
| `UpkeepTextures` | action | `(timeout=30)` | Keep textures resident. |
| `ImageButton` | action | 2 overloads `(caption, file_path, w, h, frame_padding=0)` / `(…, size, uv0, uv1, bg_color, tint_color, frame_padding)` | Image button. |
| `DrawTextureInForegound` | action | `(pos, size, texture_path, uv0, uv1, tint)` | Draw texture in the foreground draw list. |
| `DrawTextureInDrawlist` | action | `(pos, size, texture_path, uv0, uv1, tint)` | Draw texture into the current draw list. |

### Class `ScreenOverlay` (desktop layered-window overlay, all monitors)

| member | kind | signature/return | purpose |
|---|---|---|---|
| `__init__` | ctor | `()` | Create a screen overlay object. |
| `create_overlay` | action | `(ms=0, destroy=false)` | Create a transparent, click-through, topmost desktop overlay. |
| `destroy` | action | `()` | Destroy the overlay, free resources. |
| `show` | action | `(show)` | Show/hide without activating. |
| `begin` | action | `()` | Begin a frame (clear to transparent). |
| `draw_rect` | action | `(x, y, w, h, argb, thickness=1.0)` | Outlined rect in desktop pixels (0xAARRGGBB). |
| `draw_rect_filled` | action | `(x, y, w, h, argb)` | Filled rect. |
| `draw_text_box` | action | `(x, y, w, h, text, argb, px_size, family="Segoe UI", hcenter=false, vcenter=false)` | Clipped/ellipsized text box. |
| `end` | action | `()` | Present via `UpdateLayeredWindow`. |
| `get_desktop_size` | getter | `() -> (width, height)` | Virtual desktop size (all monitors). |
| `set_auto_expire` | action | `(ms, destroy=false)` | Auto-expire timeout (0 = disabled). |

---

## PyDXOverlay

Source: `src\overlay\dx_overlay_bindings.cpp`. Direct-DirectX9 geometry overlay with world/screen transforms, masks, occlusion, and stencil control. One class `DXOverlay` (bound via `bind_dx_overlay`). Legacy `Py2DRenderer` → `PyDXOverlay` per migration.

| member | kind | signature/return | purpose |
|---|---|---|---|
| `__init__` | ctor | `()` | Create the DX overlay. |
| `set_primitives` | action | `(primitives, draw_color=0xFFFFFFFF)` | Set the primitive batch to render. |
| `build_pathing_trapezoid_geometry` | action | `(color=0xFF00FF00)` | Build geometry from pathing trapezoids. |
| `inverse_rendering` | action | `(enabled)` | Toggle inverse rendering. |
| `set_world_zoom_x` / `set_world_zoom_y` | action | `(zoom)` | World zoom per axis. |
| `set_world_pan` | action | `(x, y)` | World pan. |
| `set_world_rotation` | action | `(r)` | World rotation. |
| `set_world_space` | action | `(enabled)` | Toggle world-space mode. |
| `set_world_scale` | action | `(scale)` | World scale. |
| `set_screen_offset` | action | `(x, y)` | Screen offset. |
| `set_screen_zoom_x` / `set_screen_zoom_y` | action | `(zoom)` | Screen zoom per axis. |
| `set_screen_rotation` | action | `(r)` | Screen rotation. |
| `set_circular_mask` | action | `(enabled)` | Toggle circular mask. |
| `set_circular_mask_radius` | action | `(radius)` | Circular mask radius. |
| `set_circular_mask_center` | action | `(x, y)` | Circular mask center. |
| `set_rectangle_mask` | action | `(enabled)` | Toggle rectangle mask. |
| `set_rectangle_mask_bounds` | action | `(x, y, width, height)` | Rectangle mask bounds. |
| `render` | action | `()` | Render the current batch. |
| `DrawLine` | action | `(from, to, color, thickness)` | 2D line. |
| `DrawTriangle` / `DrawTriangleFilled` | action | `(p1,p2,p3,color[,thickness])` | 2D triangle outline/fill. |
| `DrawQuad` / `DrawQuadFilled` | action | `(p1..p4,color[,thickness])` | 2D quad outline/fill. |
| `DrawPoly` / `DrawPolyFilled` | action | `(center, radius, color, segments=3[, thickness])` | 2D polygon outline/fill. |
| `DrawCubeOutline` / `DrawCubeFilled` | action | `(center, size, color, use_occlusion=true)` | Cube outline/fill. |
| `DrawLine3D` | action | `(from, to, color, use_occlusion, segments=16, floor_offset=0)` | Occlusion-aware 3D line. |
| `DrawTriangle3D` / `DrawTriangleFilled3D` | action | `(p1,p2,p3,color, use_occlusion, edge_segments=16, floor_offset)` | 3D triangle outline/fill. |
| `DrawQuad3D` / `DrawQuadFilled3D` | action | `(p1..p4,color, use_occlusion, [edge_]segments, floor_offset)` | 3D quad outline/fill. |
| `DrawPoly3D` / `DrawPolyFilled3D` | action | `(center, radius, color, numSegments, autoZ, use_occlusion, segments, floor_offset)` | 3D polygon outline/fill. |
| `Setup3DView` | action | `()` | Configure the 3D view. |
| `ApplyStencilMask` / `ResetStencilMask` | action | `()` | Stencil-mask control. |
| `DrawTexture` | action | `(file_path, screen_pos_x, screen_pos_y, width=100, height=100, int_tint=0xFFFFFFFF)` | 2D screen texture. |
| `DrawTexture3D` | action | `(file_path, world_pos_x, world_pos_y, world_pos_z, width, height, use_occlusion, int_tint)` | 3D world texture. |
| `DrawQuadTextured3D` | action | `(file_path, p1..p4, use_occlusion, int_tint)` | Textured 3D quad. |
| `SaveGeometryToFile` | action | `(filename, min_x, min_y, max_x, max_y)` | Dump geometry to file. |

---

## PyKeystroke / PyMouse

Source: `src\virtual_input\virtual_input_bindings.cpp`. Two separate modules. `PyKeystroke` exposes the class `PyKeyHandler` (scan-code key handler; legacy `PyScanCodeKeystroke` → `PyKeyHandler`). `PyMouse` exposes the class `PyMouse` (mouse handler).

### PyKeystroke → class `PyKeyHandler`

| member | kind | signature/return | purpose |
|---|---|---|---|
| `__init__` | ctor | `()` | Create a key handler. |
| `PressKey` | action | `(virtualKeyCode)` | Press a single key (scan code). |
| `ReleaseKey` | action | `(virtualKeyCode)` | Release a single key. |
| `PushKey` | action | `(virtualKeyCode)` | Press+release a single key. |
| `PressKeyCombo` | action | `(keys)` | Press a combination of keys. |
| `ReleaseKeyCombo` | action | `(keys)` | Release a combination of keys. |
| `PushKeyCombo` | action | `(keys)` | Press+release a combination. |

### PyMouse → class `PyMouse`

| member | kind | signature/return | purpose |
|---|---|---|---|
| `__init__` | ctor | `()` | Create a mouse handler. |
| `MoveMouse` | action | `(x, y)` | Move to client-relative (x, y). |
| `Click` | action | `(button=0, x=0, y=0)` | Click at (x, y). |
| `DoubleClick` | action | `(button=0, x=0, y=0)` | Double-click at (x, y). |
| `Scroll` | action | `(delta, x=0, y=0)` | Scroll wheel. |
| `PressButton` | action | `(button=0, x=0, y=0)` | Press a mouse button. |
| `ReleaseButton` | action | `(button=0, x=0, y=0)` | Release a mouse button. |

---

## PyImGui (high-level map only)

Source: `src\imgui\imgui_bindings.cpp` (module entry, ~770 lines) plus `src\imgui\bindings\*.cpp` (registered via `register_types`, `register_enums`, `register_style`, `register_docking`, `register_drawlist`, `register_io`, `register_addons`). Full ImGui 1.92.x API parity — **hundreds of functions**; not enumerated here. Use `dir(PyImGui)` at runtime for the exact surface.

### Binding files / groups

| file | contents | rough counts |
|---|---|---|
| `imgui_bindings.cpp` | Main module: all core immediate-mode functions across the categories below. Plus 2 classes (`TableColumnSortSpecs`, `TableSortSpecs`). | ~359 `m.def` free functions |
| `bindings/types.cpp` | Value types `Vec2` (`ImVec2`) and `Vec4` (`ImVec4`) with fields/ops. | 2 classes, ~17 defs |
| `bindings/enums.cpp` | Enums + flag constants: `SortDirection`, `MouseButton`, `MouseCursor`, `ImGuiCol`, `ImGuiStyleVar` (5 `py::enum_`), plus ~23 attr-style flag groups (`WindowFlags`, `ChildFlags`, `InputTextFlags`, `TreeNodeFlags`, `SelectableFlags`, `ComboFlags`, `TabBarFlags`, `TabItemFlags`, `TableFlags`, `TableColumnFlags`, `TableRowFlags`, `DragDropFlags`, `SliderFlags`, `ColorEditFlags`, `HoveredFlags`, `FocusedFlags`, `PopupFlags`, `ButtonFlags`, `DrawFlags`, `ConfigFlags`, `BackendFlags`, `DockNodeFlags`, …). | ~204 `.value()` + flag attrs |
| `bindings/style.cpp` | `ImGuiStyle` + `StyleConfig` classes; style push/pop helpers. | 2 classes, ~8 defs |
| `bindings/io.cpp` | `ImGuiIO` (`IOHandle`) — input/output state (display size, delta time, key/mouse state, flags). | 1 class, ~6 defs |
| `bindings/drawlist.cpp` | `DrawList` (`ImDrawList`) low-level primitive drawing + ~13 free helpers. | 1 class, ~53 defs |
| `bindings/docking.cpp` | Docking API (dock-space, dock builder) + 1 enum. | 1 enum, ~14 defs |
| `bindings/addons.cpp` | Addon widgets, each in its own submodule: `filebrowser` (`FileBrowser` + `DialogMode` enum), `hotkey` (`HotKey`), `markdown`, `memory_editor` (`MemoryEditor`), `anim` (`Ease`/`Policy` enums), `text_editor` (`TextEditor`). | 4 classes, 3 enums, 6 submodules, ~61 defs |

### Core function categories (headers in `imgui_bindings.cpp`)

Window; Window Setup; Window Query; Layout; Text; Widgets (buttons/checkbox/radio/progress/sliders/drags); Input (float/int/double/text/multiline); Combo / List Box; Selectable; Color (edit/picker/button/convert); Image (image/image_with_bg/image_button); Tree / Collapsing; Tabs; Tables (+ legacy columns); Menus; Popups / Tooltips; Cursor; Item Query; ID / Focus; Keyboard; Mouse; Style; Clip Rect; Clipboard / Log; Drag & Drop; Multi-Select.

**Notable non-standard bindings:** `begin` (3 overloads incl. close-button tuple form), `begin_with_close`, `begin_child` (always returns true so paired `end_child` is safe), fabricated `WindowFlags.Docking` bit (stripped before reaching ImGui; injects `NoDocking` otherwise), dynamic-font entry points (`push_font`, `push_font_scaled`, `push_style_font`, `push_font_size`, `get/set_global_font_scale` via `style.FontScaleMain`), `set_next_window_detached` / `set_next_window_main_viewport`.
