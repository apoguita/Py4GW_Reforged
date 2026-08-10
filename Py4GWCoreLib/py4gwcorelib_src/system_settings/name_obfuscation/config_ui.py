"""Name Obfuscation UI — one tabbed 'Name Obfuscation' section for the Agents group.

Adds a single :class:`ImGui.SidebarWindow` section whose content is a tab bar: Obfuscation (master
enable + live status + surface gates), Aliases (the real->fake table, add / edit / shuffle / remove),
Characters (obtain names from the current account + the accounts DB, then assign/shuffle), and
Buckets (edit the first-name / surname pools the shuffler draws from). All state lives in the
controller; these draw callables just read/write it.
"""

import PyImGui

from .controller import NameObfuscationController
from .controller import get_controller

_MUTED = (0.60, 0.60, 0.65, 1.0)
_ACCENT = (1.00, 0.78, 0.39, 1.0)
_NAME_COL = 170.0   # x where each row's controls start, so the name column lines up


class _UI:
    """Transient per-frame input state (immediate-mode has no memory of its own)."""

    add_real = ""
    add_fake = ""
    alias_search = ""
    char_search = ""
    first_text = ""
    surnames_text = ""
    buckets_loaded = False
    preview = ""


_ui = _UI()


def _yesno(value) -> str:
    if value is None:
        return "<n/a>"
    return "yes" if value else "no"


# ── tabs ─────────────────────────────────────────────────────────────────────────────────
def _draw_obfuscation(controller: "NameObfuscationController") -> None:
    enabled = controller.enabled
    new_enabled = PyImGui.checkbox("Enable name obfuscation", enabled)
    if new_enabled != enabled:
        controller.set_enabled(new_enabled)
    PyImGui.text_wrapped(
        "Masks player & character names across chat, party, guild and other game surfaces using the "
        "alias map below. Global: one identity set applies to every account on this machine."
    )
    PyImGui.separator()

    status = controller.native_status()
    if not status.get("available"):
        PyImGui.text_colored("PyNameObfuscator unavailable (offline).", _MUTED)
    else:
        PyImGui.text("Native enabled:      %s" % _yesno(status.get("enabled")))
        PyImGui.text("Map ready:           %s" % _yesno(status.get("map_ready")))
        PyImGui.text("Aliases registered:  %s" % status.get("alias_count"))
        PyImGui.text("Observed players:    %s" % status.get("observed_count"))

    surfaces = controller.list_surfaces()
    if surfaces:
        PyImGui.separator()
        PyImGui.text_colored("Surfaces", _MUTED)
        PyImGui.text_wrapped("Per-surface gates for which game surfaces get rewritten.")
        for surface in surfaces:
            on = controller.is_surface_enabled(surface)
            new_on = PyImGui.checkbox("%s##surf_%s" % (surface, surface), on)
            if new_on != on:
                controller.set_surface_enabled(surface, new_on)


def _draw_alias_row(controller: "NameObfuscationController", real: str) -> None:
    fake = controller.aliases.get(real, "")
    PyImGui.text_unformatted(real)
    PyImGui.same_line(_NAME_COL, -1)
    PyImGui.push_item_width(180.0)
    new_fake = PyImGui.input_text("##fake_%s" % real, fake)
    PyImGui.pop_item_width()
    if new_fake != fake:
        controller.set_alias(real, new_fake)
    PyImGui.same_line(0, 6)
    if PyImGui.small_button("Shuffle##ash_%s" % real):
        controller.assign_random(real)
    PyImGui.same_line(0, 6)
    if PyImGui.small_button("Remove##arm_%s" % real):
        controller.remove_alias(real)


def _draw_aliases(controller: "NameObfuscationController") -> None:
    PyImGui.text_colored("Add alias", _MUTED)
    _ui.add_real = PyImGui.input_text("Real name##add_real", _ui.add_real)
    _ui.add_fake = PyImGui.input_text("Fake name##add_fake", _ui.add_fake)
    if PyImGui.button("Add"):
        if _ui.add_real.strip():
            controller.set_alias(_ui.add_real, _ui.add_fake)
            _ui.add_real, _ui.add_fake = "", ""
    PyImGui.same_line(0, 8)
    if PyImGui.button("Add + shuffle a fake"):
        if _ui.add_real.strip():
            controller.set_alias(_ui.add_real, controller.shuffle_name())
            _ui.add_real, _ui.add_fake = "", ""

    PyImGui.separator()
    aliases = controller.aliases
    PyImGui.text_colored("Aliases (%d)" % len(aliases), _MUTED)
    _ui.alias_search = PyImGui.input_text("Search##alias_search", _ui.alias_search)
    if aliases:
        PyImGui.same_line(0, 8)
        if PyImGui.small_button("Clear all"):
            controller.clear_aliases()
            return
    query = _ui.alias_search.strip().lower()
    # Snapshot keys: rows may remove themselves mid-loop.
    for real in sorted(aliases.keys()):
        if query and query not in real.lower() and query not in aliases.get(real, "").lower():
            continue
        _draw_alias_row(controller, real)


def _draw_characters(controller: "NameObfuscationController") -> None:
    if PyImGui.button("Obtain characters"):
        controller.refresh_known_characters()
    PyImGui.same_line(0, 8)
    if controller.known_characters:
        if PyImGui.button("Assign random to all unaliased"):
            controller.assign_random_to_unaliased()

    chars = controller.known_characters
    PyImGui.text_colored("Known characters (%d)" % len(chars), _MUTED)
    if not chars:
        PyImGui.text_wrapped(
            "Click 'Obtain characters' to pull your current account's characters (from the "
            "character-select list) plus every character stored in the accounts database."
        )
        return

    _ui.char_search = PyImGui.input_text("Search##char_search", _ui.char_search)
    query = _ui.char_search.strip().lower()
    for name in chars:
        if query and query not in name.lower():
            continue
        alias = controller.alias_for(name)
        PyImGui.text_unformatted(name)
        PyImGui.same_line(_NAME_COL, -1)
        if alias:
            PyImGui.text_colored("-> %s" % alias, _ACCENT)
        else:
            PyImGui.text_colored("(no alias)", _MUTED)
        PyImGui.same_line(0, 6)
        if PyImGui.small_button("Shuffle##csh_%s" % name):
            controller.assign_random(name)
        if alias:
            PyImGui.same_line(0, 6)
            if PyImGui.small_button("Remove##crm_%s" % name):
                controller.remove_alias(name)


def _draw_buckets(controller: "NameObfuscationController") -> None:
    if not _ui.buckets_loaded:
        _ui.first_text = "\n".join(controller.first_names)
        _ui.surnames_text = "\n".join(controller.surnames)
        _ui.buckets_loaded = True

    PyImGui.text_wrapped(
        "One name per line. Shuffle picks one first name + one surname from these pools to build a "
        "fake like 'Rowan Nightfall'."
    )
    PyImGui.text_colored("First names", _MUTED)
    _ui.first_text = PyImGui.input_text_multiline("##first_names", _ui.first_text, (0.0, 150.0))
    PyImGui.text_colored("Surnames", _MUTED)
    _ui.surnames_text = PyImGui.input_text_multiline("##surnames", _ui.surnames_text, (0.0, 150.0))

    if PyImGui.button("Apply"):
        controller.set_buckets(_ui.first_text.splitlines(), _ui.surnames_text.splitlines())
        _ui.buckets_loaded = False   # re-seed from the cleaned lists next frame
    PyImGui.same_line(0, 8)
    if PyImGui.button("Reset to defaults"):
        controller.reset_buckets()
        _ui.buckets_loaded = False
    PyImGui.same_line(0, 8)
    if PyImGui.button("Preview a name"):
        _ui.preview = controller.shuffle_name()
    if _ui.preview:
        PyImGui.same_line(0, 8)
        PyImGui.text_colored(_ui.preview, _ACCENT)


# ── section registration (called by System Settings' Agents group) ───────────────────────
def add_sections(win, group) -> None:
    """Add the single tabbed 'Name Obfuscation' section to ``group`` on ``win`` (a SidebarWindow)."""
    controller = get_controller()
    win.add_section(group, "Name Obfuscation")   # no context -> hosts the tabs below
    win.add_tab("Name Obfuscation", "Obfuscation", lambda c=controller: _draw_obfuscation(c))
    win.add_tab("Name Obfuscation", "Aliases", lambda c=controller: _draw_aliases(c))
    win.add_tab("Name Obfuscation", "Characters", lambda c=controller: _draw_characters(c))
    win.add_tab("Name Obfuscation", "Buckets", lambda c=controller: _draw_buckets(c))
