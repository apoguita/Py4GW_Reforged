"""Recolor & Beacons settings -- selects a profile, and sets each filter's outcome.

**It authors no filters.** Filters and profiles are the Loot Filter Factory's; beacon presets are the
Beacons module's. This surface selects which profile runs and says, for each filter in it, what
highlighting it performs.

**There is no live quick access here** -- that window is for looting options only. So the live-state
label lives *only* in this surface, which makes it the single place a script's changes are visible.
"""

import PyImGui

from ...ImGui import ImGui
from ..loot_filter_factory import store as factory_store
from .controller import RecolorBeacons

#: `text_disabled` renders too dim to read; a mid gray keeps secondary text legible.
GRAY = (0.66, 0.67, 0.70, 1.0)
WARN = (0.79, 0.63, 0.29, 1.0)
GOOD = (0.55, 0.80, 0.58, 1.0)

_state: dict = {"live_open": False}


def _live_banner(mark: RecolorBeacons) -> None:
    if mark.is_stock():
        return
    PyImGui.text_colored("A script is changing these settings", (0.88, 0.77, 0.55, 1.0))
    PyImGui.same_line(0, 8)
    if PyImGui.small_button("details##rb_live"):
        _state["live_open"] = not _state["live_open"]
    PyImGui.same_line(0, 4)
    if PyImGui.small_button("Reset to saved##rb_reset"):
        mark.reset_live()
    ImGui.show_tooltip("Discards every change a script made and restores what you saved.")
    if _state["live_open"]:
        for line in mark.live_diff():
            PyImGui.bullet_text(line)
    PyImGui.separator()


def _save_rule(mark: RecolorBeacons, rule, **changes):
    """Rewrite one filter in the Factory's store. The outcome lives ON the filter."""
    from dataclasses import replace

    updated = replace(rule, **changes)
    rules = [updated if r.id == rule.id else r for r in factory_store.load_rules()]
    factory_store.save_rules(rules)
    mark.reload_factory()
    return updated


def draw_general() -> None:
    mark = RecolorBeacons()
    _live_banner(mark)

    enabled = mark.persisted.enabled
    if PyImGui.checkbox("Recolor & Beacons enabled##rb_master", enabled) != enabled:
        mark.persisted.enabled = not enabled
        mark.live.enabled = not enabled
        mark.save()
        if enabled:
            mark._clear_output()
    ImGui.show_tooltip("This feature's own switch. Loot Filters has a separate one -- neither "
                       "depends on the other.")

    PyImGui.separator()
    PyImGui.text("Profile")
    PyImGui.text_colored("Profiles are made in the Loot Filter Factory. This feature runs its own, "
                         "independently of the one Loot Filters runs.", GRAY)
    names = ["(none)"] + [p.name for p in mark.profiles()]
    current = names.index(mark.persisted.profile) if mark.persisted.profile in names else 0
    picked = PyImGui.combo("##rb_profile", current, names)
    if picked != current:
        chosen = "" if picked == 0 else names[picked]
        mark.persisted.profile = chosen
        mark.live.profile = chosen
        mark.save()

    PyImGui.separator()
    blank = mark.persisted.blank_unassigned
    if PyImGui.checkbox("Blank loot assigned to someone else##rb_blank_un", blank) != blank:
        mark.persisted.blank_unassigned = not blank
        mark.live.blank_unassigned = not blank
        mark.save()
    ImGui.show_tooltip("It is not yours to take, so it need not be on screen. Visual only -- it "
                       "changes nothing about what is wanted.")

    PyImGui.separator()
    status = mark.status()
    PyImGui.text_colored("%d marking filter(s)  -  %d item(s) recoloured  -  %d beacon(s), "
                         "%d particle(s)" % (status["filters"], status["recoloured"],
                                             status["beacons"], status["particles"]), GRAY)
    if not mark.persisted.profile:
        PyImGui.text_colored("No profile selected -- nothing is being marked.", WARN)


def draw_outcomes() -> None:
    """Each filter in the running profile, and what it does. The outcome is part of the filter."""
    mark = RecolorBeacons()
    _live_banner(mark)

    rules = mark.active_filters()
    if not rules:
        PyImGui.text_colored("No profile selected, or it holds no enabled filters.", GRAY)
        PyImGui.text_colored("Filters and profiles are authored in the Loot Filter Factory.", GRAY)
        return

    PyImGui.text_colored("A filter may recolour, beacon, both, or neither.", GRAY)
    PyImGui.text_colored("The profile's order settles only what cannot hold two values: when several "
                         "filters match one drop, the topmost supplies the colour and the preset. "
                         "Reorder them in the Factory.", GRAY)
    PyImGui.separator()

    preset_names = ["(base)"] + [p.name for p in mark.presets()]
    for position, rule in enumerate(rules):
        marks = "recolour" if rule.mark_recolor else ""
        if rule.mark_blank:
            marks = "BLANK"
        if rule.mark_beacon:
            marks = (marks + " + beacon") if marks else "beacon"
        header = "%d. %s  %s###rb_rule_%s" % (position + 1, rule.name,
                                              "(%s)" % marks if marks else "(no marking)", rule.id)
        if not PyImGui.collapsing_header(header):
            continue

        recolor = rule.mark_recolor
        if PyImGui.checkbox("Recolour this##rb_rc_%s" % rule.id, recolor) != recolor:
            rule = _save_rule(mark, rule, mark_recolor=not recolor)
        if rule.mark_recolor:
            colour = list(rule.mark_color)
            picked = list(PyImGui.color_edit4("Label colour##rb_col_%s" % rule.id, colour))
            if picked != colour:
                rule = _save_rule(mark, rule, mark_color=(picked[0], picked[1], picked[2], picked[3]))

        blank = rule.mark_blank
        if PyImGui.checkbox("BLANK - hide it from the labels##rb_bl_%s" % rule.id, blank) != blank:
            rule = _save_rule(mark, rule, mark_blank=not blank)
        ImGui.show_tooltip("A fully transparent label: the drop disappears from view. Visual only -- "
                           "it does not change whether the item is wanted. Beats a colour when both "
                           "are asked for.")

        beacon = rule.mark_beacon
        if PyImGui.checkbox("Beacon this##rb_bc_%s" % rule.id, beacon) != beacon:
            rule = _save_rule(mark, rule, mark_beacon=not beacon)
        if rule.mark_beacon:
            current = preset_names.index(rule.mark_preset) if rule.mark_preset in preset_names else 0
            chosen = PyImGui.combo("Preset##rb_ps_%s" % rule.id, current, preset_names)
            if chosen != current:
                _save_rule(mark, rule, mark_preset="" if chosen == 0 else preset_names[chosen])
            ImGui.show_tooltip("Presets are authored in the Beacons section.")


def draw_budget() -> None:
    """The beacon cost controls. The user sets the trade-off; the class imposes no hidden cap."""
    mark = RecolorBeacons()
    _live_banner(mark)

    PyImGui.text_wrapped("Beacons are the expensive part of this feature. These are your controls; "
                         "nothing is capped behind your back.")
    PyImGui.separator()

    config = mark.persisted
    value = PyImGui.slider_int("Max live beacons##rb_max", int(config.max_beacons), 0, 40)
    if value != config.max_beacons:
        config.max_beacons = value
        mark.live.max_beacons = value
        mark.save()
    ImGui.show_tooltip("When more items match, the nearest win.")

    distance = PyImGui.slider_float("Beacon distance##rb_dist", float(config.beacon_distance),
                                    100.0, 5000.0)
    if abs(distance - config.beacon_distance) > 1e-6:
        config.beacon_distance = distance
        mark.live.beacon_distance = distance
        mark.save()
    ImGui.show_tooltip("Beyond this, no beacon. Recolouring is unaffected -- a distant drop can "
                       "still be blanked.")

    cheap = config.cheap_distant
    if PyImGui.checkbox("Cheap shape for distant beacons##rb_cheap", cheap) != cheap:
        config.cheap_distant = not cheap
        mark.live.cheap_distant = not cheap
        mark.save()
    ImGui.show_tooltip("Past the distance below, draw the beam only -- no particles, no rings. The "
                       "beam is what carries at range; the rest is what it costs.")
    if config.cheap_distant:
        cheap_at = PyImGui.slider_float("Cheap beyond##rb_cheapd", float(config.cheap_distance),
                                        100.0, 5000.0)
        if abs(cheap_at - config.cheap_distance) > 1e-6:
            config.cheap_distance = cheap_at
            mark.live.cheap_distance = cheap_at
            mark.save()

    PyImGui.separator()
    status = mark.status()
    PyImGui.text_colored("Right now: %d beacon(s), %d live particle(s)"
                         % (status["beacons"], status["particles"]),
                         WARN if status["particles"] > 1500 else GOOD)
    worst = 0.0
    for preset in mark.presets():
        worst = max(worst, preset.estimated_live_particles())
    if worst:
        PyImGui.text_colored("Your heaviest preset is about %.0f particles per beacon, so %d of them "
                             "would be roughly %.0f." % (worst, config.max_beacons,
                                                         worst * config.max_beacons), GRAY)


def add_sections(win, group) -> None:
    """Add the Recolor & Beacons section. A consumer: it selects, it never authors."""
    win.add_section(group, "Recolor & Beacons")
    win.add_tab("Recolor & Beacons", "General", draw_general)
    win.add_tab("Recolor & Beacons", "Outcomes", draw_outcomes)
    win.add_tab("Recolor & Beacons", "Beacon budget", draw_budget)
