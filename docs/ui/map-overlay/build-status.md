# Map Overlay Merge — Build Status

> Status: **code-complete, pyright-clean, not yet verified in-client.** Both legacy widgets are
> merged into one widget and retired. In-client testing is the remaining step (needs the live
> game; cannot be done offline).

## What shipped

Package `Py4GWCoreLib/py4gwcorelib_src/map_overlay/` (launch_bar-style layering):

| Module | Contents |
|---|---|
| `model.py` | Pure data + taxonomy: `OverlayMode`, `MarkerStyle`/`Ring`/`CustomMarker`/`Terrain/Snap/PositionConfig`/`OverlayConfig`, `classify_spirit` (reuses `SPIRIT_BUFF_MAP`), classification consts, defaults |
| `shapes.py` | Rotation-capable registry (MM shapes + Star/Tear2), draw-list helpers, colour pack cache, `draw_marker`/`draw_aura` |
| `projection.py` | `AxisAlignedProjection` (mission, Raw* math + mega-zoom) / `RotatingProjection` (compass, native MiniMap projection + detached) |
| `agents.py` | One data-oriented pass (single struct read) → markers/auras; boss glow, item rarity, custom markers, cull; registers click-hit targets |
| `terrain.py` | DXOverlay pathing render: rectangular+mega-zoom (mission) / circular (compass) |
| `interaction.py` | Click-to-target, alt-click move, full NavMesh snap-move + waypoint queue + previews + danger-pause + arrival + stop |
| `persistence.py` | Own account ini load/save + opt-in `import_mission_map` / `import_compass` |
| `host.py` | Per-frame orchestrator, floating strips (move/mapid/coords/mega-zoom), tooltip |
| `config_ui.py` | Editor: mode, import, position, terrain, snap, grouped markers, custom markers, rings |

Widget host: `Widgets/Guild Wars/Screen Overlays/Map Overlay.py` (thin; `draw`/`configure`/`tooltip`).
Icon: `Assets/Textures/Module_Icons/Map Overlay.png` (placeholder copied from Mission Map+; replace with a bespoke map icon when convenient).

Retired (moved as-is, reversible): `Legacy code and tests/Deprecated but working/Mission Map +.py` and `Compass +.py`. Their legacy inis stay in place so opt-in import can find them.

## Design assumptions to verify in-client (highest → lowest risk)

1. **Compass glyph rotation.** Shapes rotate by `map_rotation = projection.rotation` applied
   rigidly via the same formula as position rotation; per-agent facing = `agent.rotation_angle`
   for both modes. Mission mode is pixel-identical to before (rotation 0). **Check compass:
   tears/triangles point the right way as the camera rotates.** If mirrored, flip the sign in
   `shapes._make_rot` (use `-angle`) or negate facing in `agents`.
2. **Spirit aura default on.** `show_spirit_range` defaults True (MM behaviour). Confirm not too
   busy on compass.
3. **NavMesh snap from compass.** Snap now works in either mode. Confirm right-click snap on the
   compass frame behaves (screen_to_game uses the rotating projection).
4. **Legacy import mapping.** `import_compass` maps a few renamed markers (Ally (Pet)→Pet,
   Signpost→Gadget, Item (White)→Item); `import_mission_map` matches by name. Spot-check.

## Player ranges vs range rings — two DIFFERENT features (do not conflate)

An early pass wrongly collapsed these into one; both are now restored and kept separate:

- **Player ranges — mission-map exclusive** (`PlayerRangeConfig`, `host._draw_player_ranges`):
  - *aggro bubble*: earshot, 4px stroke inset 2px **plus** a translucent fill.
  - *compass range*: a **black hairline at exactly the compass radius**, plus a soft band inset
    by `2.85·zoom` with thickness `5.7·zoom` — deliberately zoom-scaled so it stays readable.
    This is a bespoke Mission Map rendering, **not** a generic ring.
- **Range rings** (`cfg.rings`, `host._draw_rings`): the configurable Touch…Compass ring list
  with per-ring fill/outline/thickness. Originally a Compass feature; **renders in both modes**.

They **coexist — neither replaces the other**. In mission mode the tailored indicators draw
underneath and the rings draw on top. Both live in one **"Player ranges"** config section (the
mission-only indicators appear as a sub-block above the ring table).

> Two corrections were needed here: first the rings wrongly *replaced* the mission indicators;
> then the over-correction hid the rings from mission mode entirely. Current behaviour above is
> the intended one.

Also restored: **hostile spirits keep their own marker colour**; only the *aura* is blended 55%
toward enemy red (`shapes.shift_rgba`), so the spirit stays identifiable — an earlier pass had
overridden the marker colour too.

## Known deferred / minor

- Shapes that ignore facing (Square/SignPost/Lock/Scale/Penta) rotate rigidly with the compass;
  Penta/Circle segment orientation won't visibly rotate — acceptable.
- Widget uses `draw()` phase only (no `main()`), matching Mission Map.
- Icon is a placeholder copy.
