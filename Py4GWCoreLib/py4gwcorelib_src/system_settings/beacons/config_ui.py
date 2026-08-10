"""The Beacons editor -- a standalone authoring surface, embedded in no feature's UI.

Recolor & Beacons *consumes* what is authored here; it does not host this editor and does not own
these presets. The same arrangement as the Loot Filter Factory, and it has a useful consequence: a
beacon can be authored and previewed with the marking feature switched off entirely.

**Not a parameter dump.** Every control the reference has is here, plus the affordances that make
tweaking bearable: solo and mute, reset one parameter, copy a colour between the stops, the rarity
swatches, randomise, freeze, and a live cost figure.

*Why the preview owns a private renderer:* the shared pool is frame-driven -- whatever is not shown in
a frame is released at ``end_frame``. If the editor drove the shared pool, its frame boundary and the
marking feature's would collide and each would free the other's beacons. One preview, one pool.
"""

import random

import PyImGui

from ....ImGui import ImGui
from ...FileDialog import FileDialog
from . import store
from .effect import BeaconRenderer
from .model import BEACON_DEFAULTS
from .model import BEACON_GROUPS
from .model import BOOL
from .model import COLOR
from .model import COLOR_KEYS
from .model import COMBO
from .model import EMITTER_DEFAULTS
from .model import EMITTER_GROUPS
from .model import INT
from .model import RARITY_SWATCHES
from .model import BeaconPreset
from .model import Param
from .model import base_preset
from .model import make_emitter

#: `text_disabled` renders too dim to read; a mid gray keeps secondary text legible.
GRAY = (0.66, 0.67, 0.70, 1.0)
WARN = (0.79, 0.63, 0.29, 1.0)
GOOD = (0.55, 0.80, 0.58, 1.0)

_PREVIEW_KEY = "beacon_editor_preview"

_state: dict = {
    "presets": None,        # list[BeaconPreset], loaded once
    "selected": 0,
    "rename": "",
    "new_name": "",
    "solo": None,           # index of the soloed emitter, or None. Not persisted.
    "preview": False,
    "on_target": False,
    "message": "",
    "renderer": None,
    "dialog": None,
    "copy_from": 0,
}


# ---------------------------------------------------------------- state


def _presets() -> list[BeaconPreset]:
    if _state["presets"] is None:
        _state["presets"] = store.load()
    return _state["presets"]


def _save() -> None:
    store.save(_presets())


def _current() -> BeaconPreset | None:
    presets = _presets()
    if not presets:
        return None
    _state["selected"] = max(0, min(len(presets) - 1, int(_state["selected"])))
    return presets[_state["selected"]]


def _renderer() -> BeaconRenderer:
    if _state["renderer"] is None:
        _state["renderer"] = BeaconRenderer()
    return _state["renderer"]


def _dialog() -> FileDialog:
    if _state["dialog"] is None:
        _state["dialog"] = FileDialog()
    return _state["dialog"]


def _effective(preset: BeaconPreset) -> BeaconPreset:
    """The preset as it should currently be *heard*: explicit mutes, plus solo silencing the rest."""
    view = preset.copy()
    solo = _state["solo"]
    for index, emitter in enumerate(view.emitters):
        if solo is not None and index != solo:
            emitter.muted = True
    return view


# ---------------------------------------------------------------- generic parameter controls


def _reset_button(preset: BeaconPreset, key: str) -> None:
    """Put one parameter back to the base value, without touching the rest of the preset."""
    PyImGui.same_line(0, 4)
    if PyImGui.small_button("r##rst_%s" % key):
        preset.reset_param(key)
        _save()
    ImGui.show_tooltip("Reset just this one to the base value.")


def _draw_param(preset: BeaconPreset, param: Param) -> None:
    """One control, drawn from its metadata -- so the widget and range are never invented here."""
    if param.only_when is not None:
        gate_key, gate_value = param.only_when
        if preset.choice(gate_key) != gate_value:
            return

    key, label = param.key, param.label

    if param.kind == COMBO:
        current = preset.choice(key)
        picked = PyImGui.combo("%s##bp_%s" % (label, key), current, list(param.options))
        if picked != current:
            preset.set(key, picked)
            _save()
    elif param.kind == BOOL:
        on = preset.flag(key)
        if PyImGui.checkbox("%s##bp_%s" % (label, key), on) != on:
            preset.set(key, not on)
            _save()
    elif param.kind == INT:
        current = preset.choice(key)
        picked = PyImGui.slider_int("%s##bp_%s" % (label, key), current, int(param.lo), int(param.hi))
        if picked != current:
            preset.set(key, picked)
            _save()
    elif param.kind == COLOR:
        current = preset.color(key)
        picked = list(PyImGui.color_edit4("%s##bp_%s" % (label, key), current))
        if picked != current:
            preset.set(key, picked)
            _save()
    else:
        current = preset.number(key)
        picked = PyImGui.slider_float("%s##bp_%s" % (label, key), current, param.lo, param.hi)
        if abs(picked - current) > 1e-9:
            preset.set(key, picked)
            _save()

    _reset_button(preset, key)


# ---------------------------------------------------------------- presets


def _draw_preset_bar(preset: BeaconPreset) -> None:
    """Create, rename, duplicate, delete, reset, and file sharing -- the whole preset lifecycle."""
    presets = _presets()
    names = [p.name for p in presets]
    picked = PyImGui.combo("Preset##bp_pick", int(_state["selected"]), names)
    if picked != _state["selected"]:
        _state["selected"] = picked
        _state["solo"] = None
        _state["rename"] = ""

    protected = store.is_protected(preset.name)
    if protected:
        PyImGui.text_colored("The base beacon. It cannot be deleted -- there is always something to "
                             "fall back to.", GRAY)

    # -- new / duplicate --
    _state["new_name"] = PyImGui.input_text("##bp_new", str(_state["new_name"]))
    PyImGui.same_line(0, 4)
    if PyImGui.button("New##bp_new_btn"):
        name = store.unique_name(presets, (_state["new_name"] or "Beacon").strip())
        presets.append(base_preset().copy(name))
        _state["selected"] = len(presets) - 1
        _state["new_name"] = ""
        _save()
        return
    ImGui.show_tooltip("A new preset, starting from the base beacon.")
    PyImGui.same_line(0, 4)
    if PyImGui.button("Duplicate##bp_dup"):
        copy = preset.copy(store.unique_name(presets, preset.name))
        presets.append(copy)
        _state["selected"] = len(presets) - 1
        _save()
        return

    # -- rename --
    if not protected:
        if not _state["rename"]:
            _state["rename"] = preset.name
        _state["rename"] = PyImGui.input_text("##bp_rename", str(_state["rename"]))
        PyImGui.same_line(0, 4)
        if PyImGui.button("Rename##bp_rename_btn"):
            wanted = (_state["rename"] or "").strip()
            if wanted and wanted != preset.name:
                others = [p for p in presets if p is not preset]
                preset.name = store.unique_name(others, wanted)
                _save()
        PyImGui.same_line(0, 4)
        if PyImGui.button("Delete##bp_del"):
            presets.remove(preset)
            _state["selected"] = 0
            _state["rename"] = ""
            _save()
            return

    # -- reset to base --
    if PyImGui.button("Reset to base##bp_reset"):
        fresh = base_preset().copy(preset.name)
        preset.params, preset.colors, preset.emitters = fresh.params, fresh.colors, fresh.emitters
        _state["solo"] = None
        _save()
    ImGui.show_tooltip("Undo a session of fiddling: every parameter back to the base beacon.")
    PyImGui.same_line(0, 4)
    if PyImGui.button("Randomise##bp_rand"):
        _randomise(preset)
        _save()
    ImGui.show_tooltip("A starting point rather than a blank slate. Colours and shape only; "
                       "the emitters are left alone.")

    # -- sharing, by file --
    PyImGui.same_line(0, 12)
    if PyImGui.button("Export##bp_export"):
        _dialog().open_save("Export beacon preset", valid_types=".json",
                            start_path="%s.json" % preset.name, tag="export")
    ImGui.show_tooltip("Write this preset to a file you choose. Sharing is by file, never the "
                       "clipboard.")
    PyImGui.same_line(0, 4)
    if PyImGui.button("Import##bp_import"):
        _dialog().open_open("Import beacon preset", valid_types=".json", tag="import")

    path = _dialog().draw()
    if path:
        if _dialog().tag == "export":
            _ok, message = store.export_to_file(preset, path)
            _state["message"] = message
        else:
            imported, message = store.import_from_file(path)
            _state["message"] = message
            if imported is not None:
                imported.name = store.unique_name(presets, imported.name)
                presets.append(imported)
                _state["selected"] = len(presets) - 1
                _save()

    if _state["message"]:
        PyImGui.text_colored(_state["message"], GRAY)


def _randomise(preset: BeaconPreset) -> None:
    """A random starting point. Shape and colour only -- randomising physics gives noise, not ideas."""
    for group_params in (BEACON_GROUPS[0][1], BEACON_GROUPS[1][1]):
        for param in group_params:
            if param.kind == COLOR:
                preset.set(param.key, [random.random(), random.random(), random.random(),
                                       preset.color(param.key)[3]])
            elif param.kind == INT:
                preset.set(param.key, random.randint(int(param.lo), int(param.hi)))
            elif param.kind == COMBO:
                preset.set(param.key, random.randrange(len(param.options)))
            elif param.kind != BOOL:
                preset.set(param.key, random.uniform(param.lo, param.hi))


# ---------------------------------------------------------------- colour helpers


def _draw_colour_tools(preset: BeaconPreset) -> None:
    """Most edits are colour, and re-picking the same colour four times is the main irritation."""
    if not PyImGui.collapsing_header("Colour tools###bp_colours"):
        return

    PyImGui.text_colored("Copy a colour between the beam stops and the ground.", GRAY)
    labels = [label for _key, label in COLOR_KEYS]
    _state["copy_from"] = PyImGui.combo("From##bp_cf", int(_state["copy_from"]), labels)
    source_key = COLOR_KEYS[int(_state["copy_from"])][0]
    for key, label in COLOR_KEYS:
        if key == source_key:
            continue
        if PyImGui.small_button("-> %s##bp_cp_%s" % (label, key)):
            source = preset.color(source_key)
            # RGB only: each stop's alpha IS its opacity, and copying it flattens the gradient.
            preset.set(key, source[:3] + [preset.color(key)[3]])
            _save()
        PyImGui.same_line(0, 4)
    PyImGui.new_line()
    if PyImGui.small_button("All four##bp_cp_all"):
        source = preset.color(source_key)
        for key, _label in COLOR_KEYS:
            preset.set(key, source[:3] + [preset.color(key)[3]])
        _save()

    PyImGui.separator()
    PyImGui.text_colored("Match a rarity in one click. Opacities are kept.", GRAY)
    for label, rgb in RARITY_SWATCHES:
        if PyImGui.small_button("%s##bp_sw_%s" % (label, label)):
            for key, _name in COLOR_KEYS:
                preset.set(key, [rgb[0], rgb[1], rgb[2], preset.color(key)[3]])
            _save()
        PyImGui.same_line(0, 4)
    PyImGui.new_line()


# ---------------------------------------------------------------- emitters


def _draw_emitter(preset: BeaconPreset, index: int) -> str:
    """One emitter. Returns an action for the caller to apply after the loop, never during it."""
    emitter = preset.emitters[index]
    action = ""
    solo = _state["solo"]
    silenced = emitter.muted or (solo is not None and solo != index)
    title = "%s%s###bp_em_%d" % (emitter.name, "  (silent)" if silenced else "", index)
    if not PyImGui.collapsing_header(title):
        return action

    # -- mixer row: solo and mute answer "what does this one actually contribute?" --
    is_solo = solo == index
    if ImGui.toggle_button("solo##bp_solo_%d" % index, is_solo, 46, 20) != is_solo:
        _state["solo"] = None if is_solo else index
    ImGui.show_tooltip("Hear only this one. Nothing is saved -- solo is an inspection aid.")
    PyImGui.same_line(0, 4)
    if ImGui.toggle_button("mute##bp_mute_%d" % index, emitter.muted, 46, 20) != emitter.muted:
        emitter.muted = not emitter.muted
    PyImGui.same_line(0, 12)
    on = emitter.enabled
    if PyImGui.checkbox("enabled##bp_en_%d" % index, on) != on:
        emitter.enabled = not on
        _save()
    PyImGui.same_line(0, 8)
    additive = emitter.additive
    if PyImGui.checkbox("additive##bp_add_%d" % index, additive) != additive:
        emitter.additive = not additive
        _save()

    # -- identity and order --
    new_name = PyImGui.input_text("name##bp_nm_%d" % index, emitter.name)
    if new_name != emitter.name:
        emitter.name = new_name
        _save()
    for label, verb in (("up", "up"), ("down", "down"), ("duplicate", "dup"), ("remove", "del")):
        if PyImGui.small_button("%s##bp_%s_%d" % (label, verb, index)):
            action = verb
        PyImGui.same_line(0, 4)
    PyImGui.new_line()

    mode = int(emitter.mode)
    picked = PyImGui.combo("mode##bp_mode_%d" % index, mode, ["ballistic", "orbital"])
    if picked != mode:
        emitter.mode = picked
        _save()
    colour = list(emitter.color)
    new_colour = list(PyImGui.color_edit4("color##bp_col_%d" % index, colour))
    if new_colour != colour:
        emitter.color = new_colour
        _save()

    if PyImGui.small_button("randomise##bp_emrand_%d" % index):
        for group_label, fields in EMITTER_GROUPS:
            for key, lo, hi in fields:
                emitter.params[key] = random.uniform(lo, hi)
        _save()
    PyImGui.same_line(0, 4)
    if PyImGui.small_button("reset##bp_emreset_%d" % index):
        emitter.params = dict(EMITTER_DEFAULTS)
        _save()

    for group_label, fields in EMITTER_GROUPS:
        PyImGui.text_colored("- " + group_label, GRAY)
        for key, lo, hi in fields:
            current = float(emitter.params.get(key, EMITTER_DEFAULTS[key]))
            value = PyImGui.slider_float("%s##bp_em%d_%s" % (key, index, key), current, lo, hi)
            if abs(value - current) > 1e-9:
                emitter.params[key] = value
                _save()
            PyImGui.same_line(0, 4)
            if PyImGui.small_button("r##bp_emr%d_%s" % (index, key)):
                emitter.params[key] = EMITTER_DEFAULTS[key]
                _save()
    return action


def _apply_emitter_action(preset: BeaconPreset, index: int, action: str) -> None:
    emitters = preset.emitters
    if action == "del":
        emitters.pop(index)
        _state["solo"] = None
    elif action == "dup":
        emitters.insert(index + 1, emitters[index].copy())
        _state["solo"] = None
    elif action == "up" and index > 0:
        emitters[index - 1], emitters[index] = emitters[index], emitters[index - 1]
        _state["solo"] = None
    elif action == "down" and index < len(emitters) - 1:
        emitters[index + 1], emitters[index] = emitters[index], emitters[index + 1]
        _state["solo"] = None
    else:
        return
    _save()


def _draw_emitters(preset: BeaconPreset) -> None:
    PyImGui.text("Particle emitters (%d)" % len(preset.emitters))
    if PyImGui.button("+ add emitter##bp_em_add") and len(preset.emitters) < 12:
        preset.emitters.append(make_emitter("Emitter %d" % (len(preset.emitters) + 1)))
        _save()
    if _state["solo"] is not None:
        PyImGui.same_line(0, 8)
        PyImGui.text_colored("soloing one emitter", WARN)
        PyImGui.same_line(0, 6)
        if PyImGui.small_button("clear solo##bp_unsolo"):
            _state["solo"] = None

    pending = (-1, "")
    for index in range(len(preset.emitters)):
        action = _draw_emitter(preset, index)
        if action:
            pending = (index, action)
    if pending[0] >= 0:
        _apply_emitter_action(preset, pending[0], pending[1])


# ---------------------------------------------------------------- preview and cost


def _preview_position() -> tuple[float, float, str] | None:
    """Where the preview draws: the player, or the picked target if the user asked for that."""
    try:
        from Py4GWCoreLib.Player import Player
    except Exception:
        return None

    if _state["on_target"]:
        try:
            from Py4GWCoreLib.Agent import Agent

            target = Player.GetTargetID()
            if target:
                x, y = Agent.GetXY(target)
                return float(x), float(y), "on your target"
        except Exception:
            pass
    try:
        x, y = Player.GetXY()
    except Exception:
        return None
    if x == 0 and y == 0:
        return None
    return float(x), float(y), "at your position"


def _draw_preview(preset: BeaconPreset) -> None:
    renderer = _renderer()

    on = bool(_state["preview"])
    if PyImGui.checkbox("Live preview##bp_prev", on) != on:
        _state["preview"] = not on
        if on:
            renderer.clear()          # turning it off takes the beacon away immediately
    ImGui.show_tooltip("Draws this preset in the world so you can judge it as you edit.")
    PyImGui.same_line(0, 8)
    frozen = renderer.frozen
    if PyImGui.checkbox("Freeze##bp_freeze", frozen) != frozen:
        renderer.frozen = not frozen
    ImGui.show_tooltip("Stop the animation to judge a static gradient.")
    PyImGui.same_line(0, 8)
    target = bool(_state["on_target"])
    if PyImGui.checkbox("On my target##bp_target", target) != target:
        _state["on_target"] = not target
        renderer.clear()
    ImGui.show_tooltip("Draw it on the picked target instead of on you -- to see it on a real item.")

    # -- cost, before twenty of them are running --
    per_second = preset.particles_per_second()
    estimated = preset.estimated_live_particles()
    PyImGui.text_colored("%.0f particles/sec  -  about %.0f alive per beacon" % (per_second, estimated),
                         WARN if estimated > 400 else GRAY)
    ImGui.show_tooltip("The cost of ONE beacon. Twenty of these run twenty times this.")

    if _state["preview"]:
        where = _preview_position()
        if where is None:
            PyImGui.text_colored("Not in game -- nothing to draw on.", GRAY)
            renderer.end_frame()
            return
        x, y, label = where
        renderer.show(_PREVIEW_KEY, x, y, _effective(preset))
        PyImGui.text_colored("drawing %s  -  %d live particle(s)"
                             % (label, renderer.live_particles()), GOOD)
        if renderer.status != "idle":
            PyImGui.text_colored(renderer.status, WARN)
    renderer.end_frame()


# ---------------------------------------------------------------- the tabs


def draw_editor() -> None:
    preset = _current()
    if preset is None:
        PyImGui.text_colored("No presets. This should not happen -- the base beacon is guaranteed.",
                             WARN)
        return

    _draw_preset_bar(preset)
    PyImGui.separator()
    _draw_preview(preset)
    PyImGui.separator()

    for title, params in BEACON_GROUPS:
        if PyImGui.collapsing_header("%s###bp_grp_%s" % (title, title)):
            for param in params:
                _draw_param(preset, param)
    _draw_colour_tools(preset)


def draw_emitters() -> None:
    preset = _current()
    if preset is None:
        return
    _draw_preview(preset)
    PyImGui.separator()
    _draw_emitters(preset)


def draw_presets() -> None:
    """The list, for managing many at once. No thumbnails."""
    presets = _presets()
    PyImGui.text_colored("Presets are global -- authored once, available on every account.", GRAY)
    PyImGui.separator()
    for index, preset in enumerate(presets):
        selected = index == _state["selected"]
        if ImGui.toggle_button("%s##bp_row_%d" % (preset.name, index), selected, 190, 22) != selected:
            _state["selected"] = index
            _state["solo"] = None
            _state["rename"] = ""
        PyImGui.same_line(0, 8)
        PyImGui.text_colored("%d emitter(s), %.0f particles/sec%s"
                             % (len(preset.emitters), preset.particles_per_second(),
                                "  -  protected" if store.is_protected(preset.name) else ""), GRAY)


def add_sections(win, group) -> None:
    """Add the Beacons section. Its own surface; embedded in no feature."""
    win.add_section(group, "Beacons")
    win.add_tab("Beacons", "Beacon", draw_editor)
    win.add_tab("Beacons", "Emitters", draw_emitters)
    win.add_tab("Beacons", "Presets", draw_presets)
