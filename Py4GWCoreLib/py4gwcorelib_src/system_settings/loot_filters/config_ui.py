"""Loot Filters settings -- the deep configuration.

**All configuration lives here.** The quick access configures nothing; it follows what is set here.
That includes which surfaces the quick access shows and which layout each one uses.

The live-state label appears **here as well as in the quick access** -- both surfaces must say when
what you are looking at is not what is running.

Authoring filters and profiles is **not** here: that is the Loot Filter Factory's own surface. This
feature only *selects* a profile.
"""

import PyImGui

from ....ImGui import ImGui
from . import renderer
from . import store
from . import surfaces
from .controller import LootFilters

GRAY = renderer.GRAY
WARN = (0.79, 0.63, 0.29, 1.0)
GOOD = (0.55, 0.80, 0.58, 1.0)

_state: dict = {"nick_year": 0, "nick_month": 0, "nick_day": 0, "dbg_range": 2500}


def _live_banner(loot: LootFilters) -> None:
    """The label. Shown wherever the user might be looking at settings that are not what runs."""
    if loot.is_stock():
        return
    PyImGui.text_colored("A script is changing these settings", (0.88, 0.77, 0.55, 1.0))
    PyImGui.same_line(0, 8)
    if PyImGui.small_button("Reset to saved##lf_reset"):
        loot.reset_live()
    ImGui.show_tooltip("Discards every change a script made and restores what you saved.")
    PyImGui.separator()


def _edit(loot: LootFilters, surface: str, entry_id: int, on: bool) -> None:
    """A user edit: PERSISTED is what is saved, and live is kept in step so it applies now."""
    surfaces.apply_to(surface, loot.persisted, entry_id, on)
    surfaces.apply_to(surface, loot.live, entry_id, on)
    loot.save()


def _draw_surface(loot: LootFilters, surface: str, default_open: bool = False) -> None:
    layout = store.load_layout_for(surface, surfaces.default_layout(surface))
    renderer.layout_selector(surface, layout, lambda value: store.save_layout_for(surface, value))
    PyImGui.separator()
    renderer.draw_section(
        surface.replace(" ", "_"), surface,
        surfaces.groups_for(surface, loot.persisted),
        surfaces.selected_set(surface, loot.persisted),
        lambda entry_id, on: _edit(loot, surface, entry_id, on),
        layout, surfaces.tooltip_for(surface), default_open,
    )


def draw_general(loot: LootFilters) -> None:
    _live_banner(loot)

    enabled = loot.persisted.enabled
    if PyImGui.checkbox("Looting enabled##lf_master", enabled) != enabled:
        loot.persisted.enabled = not enabled
        loot.live.enabled = not enabled
        loot.save()
    ImGui.show_tooltip("The master switch for this feature. Recolor & Beacons has its own.")

    lock = loot.persisted.respect_loot_lock
    if PyImGui.checkbox("Respect the cross-account loot lock##lf_lock", lock) != lock:
        loot.persisted.respect_loot_lock = not lock
        loot.live.respect_loot_lock = not lock
        loot.save()
    ImGui.show_tooltip("On: skip unassigned drops another of your accounts has claimed. Off: offer "
                       "them anyway. It used to be hard-coded on and invisible.")

    PyImGui.separator()
    PyImGui.text("Profile")
    PyImGui.text_colored("Profiles are made in the Loot Filter Factory. One runs at a time.", GRAY)
    names = ["(none)"] + [p.name for p in loot.profiles()]
    current = names.index(loot.persisted.profile) if loot.persisted.profile in names else 0
    picked = PyImGui.combo("##lf_profile", current, names)
    if picked != current:
        chosen = "" if picked == 0 else names[picked]
        loot.persisted.profile = chosen
        loot.live.profile = chosen
        loot.save()

    active = loot.active_filters()
    PyImGui.text_colored("%d filter(s) active" % len(active), GRAY)
    for rule in active:
        PyImGui.text_colored("  - %s" % rule.name, GRAY)


def _draw_verdict(loot: LootFilters, agent_id: int, item_id: int, source: str) -> None:
    """One item's verdict plus every reason. `agent_id` may be 0 for a bag item."""
    from Py4GWCoreLib.Item import Item

    try:
        model_id = Item.GetModelID(item_id)
        name = Item.GetName(item_id) if Item.IsNameReady(item_id) else "(name decoding)"
        _v, rarity = Item.Rarity.GetRarity(item_id)
    except Exception as exc:
        PyImGui.text_colored("cannot read item %d: %s" % (item_id, exc), WARN)
        return
    PyImGui.text_colored(source, GRAY)
    PyImGui.text("%s   [%s]   item %d   model %d" % (name, rarity, item_id, model_id))
    # What the CATALOG thinks that model is -- the only way to see a mis-catalogued model id.
    PyImGui.text_colored("catalog says: %s" % loot.describe_model(model_id), GRAY)
    wanted = loot.wants(agent_id, item_id, model_id)
    PyImGui.text_colored("WANTED" if wanted else "NOT WANTED", GOOD if wanted else WARN)
    PyImGui.same_line(0, 10)
    if PyImGui.small_button("Print diagnostics##diag_%d_%d" % (agent_id, item_id)):
        loot.print_diagnostics(agent_id, item_id, model_id)
    ImGui.show_tooltip("Writes the full report to the Py4GW console: everything the game reports "
                       "about the item, what the catalog believes it is, the whole live "
                       "configuration, and every reason with its verdict.")
    PyImGui.separator()
    for reason, holds in loot.explain(agent_id, item_id, model_id):
        PyImGui.text_colored(("[x] " if holds else "[ ] ") + reason, GOOD if holds else GRAY)


def _hovered_item_id() -> int:
    """The item under the mouse in the inventory UI, if any."""
    try:
        from Py4GWCoreLib.Inventory import Inventory

        return int(Inventory.GetHoveredItemID() or 0)
    except Exception:
        return 0


def draw_debug(loot: LootFilters) -> None:
    """Live diagnostics: what the class is actually offering, and what the config really holds.

    This exists because a wrong answer and a wrong *questioner* look identical from the outside.
    `GetLootArray` is the only thing this feature offers a consumer, so if a drop is being taken
    while it is not on this list, the taker is something else -- another widget or a bot with its
    own looting -- and no amount of changing settings here will stop it.
    """
    from Py4GWCoreLib.Agent import Agent
    from Py4GWCoreLib.Item import Item

    _live_banner(loot)

    PyImGui.text_colored("What this feature offers consumers, right now.", GRAY)
    if PyImGui.small_button("Reload from disk##dbg_reload"):
        loot.reload()
    PyImGui.same_line(0, 6)
    if PyImGui.small_button("Reset live to saved##dbg_resetlive"):
        loot.reset_live()
    PyImGui.separator()

    # -- the live configuration, as the class actually holds it --
    config = loot.live
    if PyImGui.collapsing_header("Live configuration###dbg_cfg"):
        PyImGui.text_colored("master switch: %s" % ("ON" if config.enabled else "OFF"),
                             GOOD if config.enabled else WARN)
        PyImGui.text("profile: %s" % (config.profile or "(none)"))
        PyImGui.text("rarities: " + "  ".join(
            "%s=%s" % (label, "on" if config.rarity_enabled(key) else "off")
            for key, label in surfaces.RARITY_KEYS))
        for label, values in (("hand list (models)", config.enabled_model_ids),
                              ("salvage targets", config.salvage_target_ids),
                              ("dye colours", config.enabled_dye_colors),
                              ("script-added models", config.added_model_ids),
                              ("script-added drops", config.added_item_ids),
                              ("blacklisted models", config.blacklist_model_ids),
                              ("suppressed drops", config.blacklist_item_ids)):
            PyImGui.text_colored("%-22s %d" % (label, len(values)),
                                 WARN if values and "script" in label else GRAY)
        PyImGui.text_colored("%-22s %d" % ("nicholas weeks", len(config.nicholas)), GRAY)
        PyImGui.text_colored("%-22s %d" % ("active filters", len(loot.active_filters())), GRAY)

    hovered = _hovered_item_id()
    if hovered:
        if PyImGui.collapsing_header("Hovered item###dbg_hover"):
            _draw_verdict(loot, 0, hovered, "hovered in your inventory")
        PyImGui.separator()

    # -- everything nearby, and the verdict on each --
    distance = float(_state.get("dbg_range", 2500))
    _state["dbg_range"] = PyImGui.slider_int("Range##dbg_range", int(distance), 100, 5000)

    accepted = loot.GetLootArray(float(_state["dbg_range"]))
    PyImGui.text_colored("ACCEPTED LOOT ARRAY: %d" % len(accepted),
                         GOOD if accepted else GRAY)
    ImGui.show_tooltip("Exactly what GetLootArray returns. A drop being taken while NOT on this "
                       "list is being taken by something other than this feature.")

    try:
        from Py4GWCoreLib.AgentArray import AgentArray
        from Py4GWCoreLib.Player import Player

        nearby = AgentArray.Filter.ByDistance(AgentArray.GetItemArray(), Player.GetXY(),
                                              float(_state["dbg_range"]))
        mine = Player.GetAgentID()
    except Exception:
        nearby, mine = [], 0

    PyImGui.text_colored("ground items in range: %d" % len(nearby), GRAY)
    PyImGui.same_line(0, 10)
    if PyImGui.small_button("Print ALL to console##dbg_printall"):
        for candidate in nearby:
            try:
                agent_item = Agent.GetItemAgentByID(candidate)
                if agent_item is None:
                    continue
                loot.print_diagnostics(candidate, agent_item.item_id,
                                       Item.GetModelID(agent_item.item_id))
            except Exception:
                continue
    ImGui.show_tooltip("Dumps the full report for every ground item in range. If a drop vanishes "
                       "while it is NOT in the accepted array above, whatever took it is not this "
                       "feature.")
    PyImGui.separator()

    for agent_id in nearby:
        try:
            item_agent = Agent.GetItemAgentByID(agent_id)
            if item_agent is None:
                continue
            item_id = item_agent.item_id
            model_id = Item.GetModelID(item_id)
            name = Item.GetName(item_id) if Item.IsNameReady(item_id) else "(decoding)"
            owner = Agent.GetItemAgentOwnerID(agent_id)
            _value, rarity = Item.Rarity.GetRarity(item_id)
        except Exception as exc:
            PyImGui.text_colored("agent %d: unreadable (%s)" % (agent_id, exc), WARN)
            continue

        taken = agent_id in accepted
        owner_label = "mine" if owner == mine else ("unassigned" if owner == 0 else "someone else")
        header = "%s %s  [%s, %s]  agent %d###dbg_%d" % (
            "TAKE" if taken else "  --", name, rarity, owner_label, agent_id, agent_id)
        opened = PyImGui.collapsing_header(header)
        # Hovering the row is enough -- no need to expand it.
        breakdown = "\n".join(("[x] " if holds else "[ ] ") + reason
                              for reason, holds in loot.explain(agent_id, item_id, model_id))
        ImGui.show_tooltip("%s  [%s]\n%s" % (name, rarity, breakdown))
        if not opened:
            continue
        PyImGui.text_colored("item %d   model %d   owner %d" % (item_id, model_id, owner), GRAY)
        for reason, holds in loot.explain(agent_id, item_id, model_id):
            PyImGui.text_colored(("[x] " if holds else "[ ] ") + reason, GOOD if holds else GRAY)

    if not nearby:
        PyImGui.text_colored("Nothing on the ground in range.", GRAY)


def draw_why(loot: LootFilters) -> None:
    """Why is this item wanted -- or not.

    **Hover any item in your bags** and it is evaluated live; with nothing hovered it falls back to
    the ground drop you have targeted. Resolution is HAS-ANY and only the blacklist vetoes, so a
    rarity being off never stops something another rule already wants -- which is exactly the thing
    that is impossible to see without this.
    """
    _live_banner(loot)
    PyImGui.text_wrapped("Hover an item in your inventory, or target a drop on the ground. "
                         "Any one reason is enough to take it; only the blacklist can veto.")
    PyImGui.separator()

    hovered = _hovered_item_id()
    if hovered:
        _draw_verdict(loot, 0, hovered, "hovered in your inventory")
        return

    try:
        from Py4GWCoreLib.Agent import Agent
        from Py4GWCoreLib.Player import Player

        agent_id = Player.GetTargetID()
        item_agent = Agent.GetItemAgentByID(agent_id) if agent_id else None
    except Exception:
        agent_id, item_agent = 0, None
    if not agent_id or item_agent is None:
        PyImGui.text_colored("Nothing hovered, and no ground item targeted.", GRAY)
        return
    _draw_verdict(loot, agent_id, item_agent.item_id, "targeted on the ground")


def draw_rarities(loot: LootFilters) -> None:
    _live_banner(loot)
    PyImGui.text("Take drops by rarity.")
    PyImGui.separator()
    for index, (key, label) in enumerate(surfaces.RARITY_KEYS):
        on = loot.persisted.rarity_enabled(key)
        if PyImGui.checkbox("%s##lf_rar_%s" % (label, key), on) != on:
            _edit(loot, surfaces.RARITIES, index, not on)
        if key == "gold_coins":
            ImGui.show_tooltip("An independent switch, not an alternative to the rarities - "
                               "combine it with any of them.")


def draw_catalog(loot: LootFilters) -> None:
    _live_banner(loot)
    PyImGui.text_colored("A category contains groups. Trophies is banded alphabetically as it draws.",
                         GRAY)
    PyImGui.separator()
    from . import catalog as catalog_data

    for category in catalog_data.categories():
        _draw_surface(loot, category)


def draw_materials(loot: LootFilters) -> None:
    _live_banner(loot)
    PyImGui.text_wrapped("Wanting a material when it drops. Separate from 'Salvages to', which wants "
                         "any item that breaks down into a material.")
    PyImGui.separator()
    _draw_surface(loot, surfaces.MATERIALS, default_open=True)


def draw_salvages_to(loot: LootFilters) -> None:
    _live_banner(loot)
    PyImGui.text_wrapped("Take anything that salvages into these. This is what makes the large "
                         "un-listed salvageable population reachable without enumerating it.")
    PyImGui.text_colored("Every material is offered; the bundled salvage data informs the tooltip and "
                         "never limits the choice.", GRAY)
    PyImGui.separator()
    _draw_surface(loot, surfaces.SALVAGES_TO, default_open=True)


def draw_dyes(loot: LootFilters) -> None:
    _live_banner(loot)
    PyImGui.text_wrapped("Every dye shares one model id, so a dye is chosen by colour and matched on "
                         "item type plus colour.")
    PyImGui.separator()
    _draw_surface(loot, surfaces.DYES, default_open=True)


def draw_nicholas(loot: LootFilters) -> None:
    import datetime

    from .nicholas import NicholasSelection

    _live_banner(loot)
    PyImGui.text_wrapped("Nicholas is opt in -- nothing here is watched until you switch it on. "
                         "Several weeks may be active at once.")
    PyImGui.separator()

    today = datetime.date.today()

    def _set(selections) -> None:
        loot.persisted.nicholas = tuple(selections)
        loot.live.nicholas = tuple(selections)
        loot.save()

    # The rolling current week is the common case, so it gets its own switch -- and it can be
    # switched OFF, which is the whole point of opt in.
    rolling = NicholasSelection(None)
    following = rolling in loot.persisted.nicholas
    if PyImGui.checkbox("Follow the current week##nick_rolling", following) != following:
        _set([s for s in loot.persisted.nicholas if s != rolling] if following
             else list(loot.persisted.nicholas) + [rolling])
        return
    ImGui.show_tooltip("Rolls over on its own as the week changes. Untick it and no week is "
                       "watched unless you pinned one below.")

    if not loot.persisted.nicholas:
        PyImGui.text_colored("Nothing watched.", GRAY)
    PyImGui.separator()

    for selection, label, is_current in surfaces.nicholas_rows(loot.persisted, today):
        PyImGui.text(label)
        if not is_current:
            PyImGui.same_line(0, 8)
            if PyImGui.small_button("remove##nick_%s" % selection.week):
                _set([s for s in loot.persisted.nicholas if s != selection])
                return

    PyImGui.separator()
    PyImGui.text_colored("Add a date", GRAY)
    if not _state["nick_year"]:
        _state.update({"nick_year": today.year, "nick_month": today.month, "nick_day": today.day})
    PyImGui.push_item_width(70)
    _state["nick_year"] = PyImGui.input_int("Year##nk_y", int(_state["nick_year"]))
    PyImGui.same_line(0, 6)
    _state["nick_month"] = PyImGui.input_int("Month##nk_m", int(_state["nick_month"]))
    PyImGui.same_line(0, 6)
    _state["nick_day"] = PyImGui.input_int("Day##nk_d", int(_state["nick_day"]))
    PyImGui.pop_item_width()

    try:
        picked = datetime.date(int(_state["nick_year"]), max(1, min(12, int(_state["nick_month"]))),
                               max(1, min(31, int(_state["nick_day"]))))
    except ValueError:
        PyImGui.text_colored("Not a valid date.", WARN)
        return
    preview = surfaces.nicholas_preview(picked)
    if preview:
        PyImGui.text_colored("That week: %s" % preview, GRAY)
    if PyImGui.button("Add this week##nk_add"):
        selection = NicholasSelection.on(picked)
        if selection not in loot.persisted.nicholas:
            _set(list(loot.persisted.nicholas) + [selection])


def draw_item_types(loot: LootFilters) -> None:
    """Item types never to take. A VETO, and the only way to say "not this"."""
    _live_banner(loot)
    PyImGui.text_wrapped("Tick a type to NEVER take it. This is a veto: it beats every other rule, "
                         "exactly like the model blacklist.")
    PyImGui.text_colored("Turning a rarity off is not the same thing -- that only removes rarity as "
                         "a reason, and a hand list, a salvage target or a filter can still take the "
                         "item. This is the only control that stops it outright.", GRAY)
    PyImGui.separator()
    _draw_surface(loot, surfaces.ITEM_TYPES, default_open=True)


def draw_blacklist(loot: LootFilters) -> None:
    from . import catalog as catalog_data

    _live_banner(loot)
    PyImGui.text_wrapped("The blacklist inhibits every other rule. A blacklisted item is never taken, "
                         "no matter what else wants it.")
    PyImGui.separator()
    for model_id in sorted(loot.persisted.blacklist_model_ids):
        entry = catalog_data.by_model_id(model_id)
        if PyImGui.small_button("remove##bl_%d" % model_id):
            loot.persisted.blacklist_model_ids.discard(model_id)
            loot.live.blacklist_model_ids.discard(model_id)
            loot.save()
            return
        PyImGui.same_line(0, 6)
        PyImGui.text(entry.name if entry else "model %d" % model_id)
    if not loot.persisted.blacklist_model_ids:
        PyImGui.text_colored("Nothing blacklisted.", GRAY)
    if loot.live.blacklist_item_ids:
        PyImGui.separator()
        PyImGui.text_colored("%d drop(s) suppressed this session (cleared on map change)"
                             % len(loot.live.blacklist_item_ids), GRAY)


def draw_quick_access(loot: LootFilters) -> None:
    """Where the user decides what their quick access contains. The window itself configures nothing."""
    from . import quick_access

    _live_banner(loot)

    # A persisted setting, so it reads as one: a checkbox that stays where the user left it,
    # not a button that has to be clicked again every session.
    shown = quick_access.is_open()
    if PyImGui.checkbox("Show the quick access window##qa_toggle", shown) != shown:
        quick_access.toggle(not shown)
    ImGui.show_tooltip("A separate window you keep open while playing. It holds only what you add "
                       "here, and it reopens by itself next session.")

    PyImGui.separator()
    PyImGui.text("Uniform layout")
    PyImGui.text_colored("Each surface keeps its own layout. These apply one to all of them.", GRAY)
    for value, label in renderer.LAYOUTS:
        if PyImGui.small_button("%s##uni_%s" % (label, value)):
            for name in surfaces.names():
                store.save_layout_for(name, value)
        PyImGui.same_line(0, 4)
    PyImGui.new_line()

    PyImGui.separator()
    PyImGui.text("Surfaces shown in the quick access")
    chosen = quick_access.surfaces()
    for name in surfaces.names():
        on = name in chosen
        if PyImGui.checkbox("%s##qa_pick_%s" % (name, name), on) != on:
            quick_access.set_surfaces([s for s in surfaces.names()
                                       if (s in chosen) != (s == name)])

    PyImGui.separator()
    PyImGui.text("Filters shown in the quick access")
    PyImGui.text_colored("Filters come from the Loot Filter Factory.", GRAY)
    for rule in loot.active_filters():
        PyImGui.text_colored("  - %s" % rule.name, GRAY)
    if not loot.active_filters():
        PyImGui.text_colored("  (no profile selected, or it has no filters)", GRAY)


def add_sections(win, group) -> None:
    """Add the Loot Filters section."""
    loot = LootFilters()
    win.add_section(group, "Loot Filters")
    # Quick Access leads: it is the tab reached most often, and last in a nine-tab row put it
    # out of reach.
    win.add_tab("Loot Filters", "Quick Access", lambda: draw_quick_access(loot))
    win.add_tab("Loot Filters", "General", lambda: draw_general(loot))
    win.add_tab("Loot Filters", "Why?", lambda: draw_why(loot))
    win.add_tab("Loot Filters", "Debug", lambda: draw_debug(loot))
    win.add_tab("Loot Filters", "Rarities", lambda: draw_rarities(loot))
    win.add_tab("Loot Filters", "Catalog", lambda: draw_catalog(loot))
    win.add_tab("Loot Filters", "Materials", lambda: draw_materials(loot))
    win.add_tab("Loot Filters", "Salvages to", lambda: draw_salvages_to(loot))
    win.add_tab("Loot Filters", "Dyes", lambda: draw_dyes(loot))
    win.add_tab("Loot Filters", "Nicholas", lambda: draw_nicholas(loot))
    win.add_tab("Loot Filters", "Never these types", lambda: draw_item_types(loot))
    win.add_tab("Loot Filters", "Blacklist", lambda: draw_blacklist(loot))
