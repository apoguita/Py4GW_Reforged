"""
Guild section — full guild state from BOTH data paths: the ``PyGuild`` free functions AND the
rich ``GWContext.Guild`` context struct (the roster / guild list / history / town alliances that
the free-function surface does not expose).

Shape (see player_demo.py, the canonical template):
  * ``build_guild()`` calls the native ``PyGuild`` free functions (CAST via ``casts``) for the
    scalar getters, then dereferences the ``GWContext.Guild`` context struct FIELD-BY-FIELD
    (never repr'd) via the ctypes reader in ``native_src/context/GuildContext.py``. Every nested
    struct (Guild / GuildPlayer / GuildHistoryEvent / TownAlliance / GHKey / CapeDesign) is
    unpacked field-by-field; encoded wide-strings are shown via the wrapper's ``*_str`` decoders.
  * ``draw_guild_view()`` builds once, offers the per-section Dump-to-file button, then a tab bar:
    ``Data`` (ui.draw_blocks) + ``Actions`` (explicit trigger buttons, never auto-fired).

Data paths:
  * native ``PyGuild`` module (free functions only) — index/announcement/announcer + GH travel.
  * ``GWContext.Guild`` (M1 context path) — the ``GuildContext`` pointer IS published in the
    shared-memory pointer table (``PointersSSM.GuildContext``), so the whole struct is readable.

R2 coverage — PyGuild (5 methods, ALL wired):
  Data getters (Data tab): get_player_guild_index(1), get_player_guild_announcement(2),
  get_player_guild_announcer(3).
  Action/mutators (Actions tab, queue-backed): travel_gh(4), leave_gh(5).

Context coverage — GWContext.Guild -> GuildContextStruct (native_src/context/GuildContext.py,
mirroring include/GW/context/guild.h): player_name_str, player_guild_index, player_guild_rank,
player_gh_key(GHKey.as_string), kurzick_town_count, luxon_town_count, announcement_str,
announcement_author_str, guild_array(List[Guild]), player_roster(List[GuildPlayer]),
player_guild_history(List[GuildHistoryEvent]), factions_outpost_guilds(List[TownAlliance]).
"""

import PyImGui

from . import casts
from . import diagnostics
from . import ui

_SECTION = "Guild"

# Native module handle, guarded so the section survives an offline / no-binding interpreter.
try:  # pragma: no cover - runtime specific
    import PyGuild as _PyGuild
except Exception:  # noqa: BLE001 - offline: no embedded binding
    _PyGuild = None

# Context facade, guarded the same way (registers a context callback on import).
try:  # pragma: no cover - runtime specific
    from Py4GWCoreLib.Context import GWContext as _GWContext
except Exception:  # noqa: BLE001 - offline: no context path
    _GWContext = None

# Guild.faction / TownAlliance.faction — confirmed inline in include/GW/context/guild.h
# ("faction; // 0=kurzick, 1=luxon"). GW::Constants enums are not bound to Python.
_FACTION_NAMES = {0: "Kurzick", 1: "Luxon"}


# ---------------------------------------------------------------------------
# Helpers (explicit, hand-wired — no reflection/dir())
# ---------------------------------------------------------------------------
def _guild_call(fn_name: str, default, *args):
    """Call one explicitly-named ``PyGuild`` free function, guarded.

    The caller always passes a constant function name (no discovery); any binding gap (offline,
    absent function, or a raising getter) degrades to ``default``.
    """
    if _PyGuild is None:
        return default
    fn = getattr(_PyGuild, fn_name, None)
    if not callable(fn):
        return default
    return casts.safe(fn, *args, default=default)


def _guild_context():
    """Return the dereferenced GuildContextStruct, or None (offline / not in a guild-aware state)."""
    if _GWContext is None:
        return None
    return casts.safe(_GWContext.Guild.GetContext, default=None)


def _prop(obj, name, default="<n/a>"):
    """Read one named struct property/field, guarded (a bad read never blanks the block)."""
    return casts.safe(getattr, obj, name, default=default)


def _s(value) -> str:
    """Decoded-string display: show the text, or ``(none)`` for empty/None."""
    return str(value) if value else "(none)"


def _faction(value) -> str:
    try:
        return casts.id_name(int(value), _FACTION_NAMES.get(int(value), "Unknown"))
    except (TypeError, ValueError):
        return str(value)


# ---------------------------------------------------------------------------
# build_* — call getters, cast, return blocks (shared by render AND dump)
# ---------------------------------------------------------------------------
def _free_function_block():
    if _PyGuild is None:
        return ui.text_block("Guild (PyGuild)", "PyGuild binding unavailable (offline / not injected).")
    index = _guild_call("get_player_guild_index", 0)
    announcement = _guild_call("get_player_guild_announcement", "")
    announcer = _guild_call("get_player_guild_announcer", "")
    rows = [
        ("Player Guild Index", index),
        ("Guild Announcer", _s(announcer)),
        ("Guild Announcement", _s(announcement)),
    ]
    return ui.kv_block("Player Guild (PyGuild free functions)", rows)


def _context_player_block(ctx):
    key = _prop(ctx, "player_gh_key", None)
    rows = [
        ("Context Ptr", casts.ptr(casts.safe(_GWContext.Guild.GetPtr, default=0) if _GWContext else 0)),
        ("Player Name", _s(_prop(ctx, "player_name_str", None))),
        ("Player Guild Index", _prop(ctx, "player_guild_index")),
        ("Player Guild Rank", _prop(ctx, "player_guild_rank")),
        ("Player GH Key", _s(_prop(key, "as_string", None)) if key is not None else "(none)"),
        ("Kurzick Town Count", _prop(ctx, "kurzick_town_count")),
        ("Luxon Town Count", _prop(ctx, "luxon_town_count")),
        ("Announcement", _s(_prop(ctx, "announcement_str", None))),
        ("Announcement Author", _s(_prop(ctx, "announcement_author_str", None))),
    ]
    return ui.kv_block("Player Guild (GWContext.Guild context)", rows)


def _guilds_block(ctx):
    guilds = _prop(ctx, "guild_array", None)
    headers = [
        "#", "Name", "Tag", "Index", "Rank", "Features", "Rating",
        "Faction", "Faction Pts", "Qualifier Pts", "GH Key",
    ]
    rows = []
    for i, g in enumerate(guilds or []):
        key = _prop(g, "key", None)
        rows.append((
            i,
            _s(_prop(g, "name_str", None)),
            _s(_prop(g, "tag_str", None)),
            _prop(g, "index"),
            _prop(g, "rank"),
            _prop(g, "features"),
            _prop(g, "rating"),
            _faction(_prop(g, "faction", "?")),
            _prop(g, "faction_point"),
            _prop(g, "qualifier_point"),
            _s(_prop(key, "as_string", None)) if key is not None else "(none)",
        ))
    title = f"Guild Array (GuildContext.guild_array) [{len(rows)}]"
    return ui.multi_block(title, headers, rows)


def _roster_block(ctx):
    roster = _prop(ctx, "player_roster", None)
    headers = [
        "#", "Current Name", "Invited Name", "Inviter", "Promoter",
        "Invite Time", "Offline", "Member Type", "Status",
    ]
    rows = []
    for i, p in enumerate(roster or []):
        rows.append((
            i,
            _s(_prop(p, "current_name_str", None)),
            _s(_prop(p, "invited_name_str", None)),
            _s(_prop(p, "inviter_name_str", None)),
            _s(_prop(p, "promoter_name_str", None)),
            _prop(p, "invite_time"),
            _prop(p, "offline"),
            _prop(p, "member_type"),  # no confirmed enum in native headers -> raw int
            _prop(p, "status"),       # no confirmed enum in native headers -> raw int
        ))
    title = f"Guild Roster (GuildContext.player_roster) [{len(rows)}]"
    return ui.multi_block(title, headers, rows)


def _history_block(ctx):
    history = _prop(ctx, "player_guild_history", None)
    headers = ["#", "Time1", "Time2", "Name"]
    rows = []
    for i, e in enumerate(history or []):
        rows.append((
            i,
            _prop(e, "time1"),
            _prop(e, "time2"),
            _s(_prop(e, "name_str", None)),
        ))
    title = f"Guild History (GuildContext.player_guild_history) [{len(rows)}]"
    return ui.multi_block(title, headers, rows)


def _town_alliances_block(ctx):
    alliances = _prop(ctx, "factions_outpost_guilds", None)
    headers = ["#", "Name", "Tag", "Rank", "Allegiance", "Faction", "Map ID"]
    rows = []
    for i, a in enumerate(alliances or []):
        rows.append((
            i,
            _s(_prop(a, "name_str", None)),
            _s(_prop(a, "tag_str", None)),
            _prop(a, "rank"),
            _prop(a, "allegiance"),
            _faction(_prop(a, "faction", "?")),
            _prop(a, "map_id"),
        ))
    title = f"Town Alliances (GuildContext.factions_outpost_guilds) [{len(rows)}]"
    return ui.multi_block(title, headers, rows)


def build_guild():
    blocks = [_free_function_block()]
    ctx = _guild_context()
    if ctx is None:
        blocks.append(ui.text_block(
            "Guild Context (GWContext.Guild)",
            "Context not available in this state (offline, not injected, or GuildContext pointer "
            "not yet published this frame).",
        ))
        return blocks
    blocks.append(_context_player_block(ctx))
    blocks.append(_guilds_block(ctx))
    blocks.append(_roster_block(ctx))
    blocks.append(_history_block(ctx))
    blocks.append(_town_alliances_block(ctx))
    return blocks


# ---------------------------------------------------------------------------
# Actions — explicit trigger buttons, fired only on click
# ---------------------------------------------------------------------------
def _draw_actions():
    ui.section_header("Guild Hall")
    ui.action_button("Travel to GH", _guild_action, "travel_gh", key="travel_gh")
    PyImGui.same_line(0, 8)
    ui.action_button("Leave GH", _guild_action, "leave_gh", key="leave_gh")


def _guild_action(fn_name: str):
    """Fire one explicitly-named PyGuild action; raise if the binding is missing."""
    if _PyGuild is None:
        raise RuntimeError("PyGuild binding unavailable")
    fn = getattr(_PyGuild, fn_name, None)
    if not callable(fn):
        raise RuntimeError(f"PyGuild.{fn_name} unavailable")
    return fn()


# ---------------------------------------------------------------------------
# draw_*_view — uniform section entry point
# ---------------------------------------------------------------------------
def draw_guild_view() -> None:
    blocks = build_guild()
    diagnostics.dump_button(_SECTION, blocks)
    PyImGui.separator()
    if PyImGui.begin_tab_bar("GuildTabs"):
        if PyImGui.begin_tab_item("Data"):
            ui.draw_blocks(_SECTION, blocks)
            PyImGui.end_tab_item()
        if PyImGui.begin_tab_item("Actions"):
            _draw_actions()
            PyImGui.end_tab_item()
        PyImGui.end_tab_bar()
