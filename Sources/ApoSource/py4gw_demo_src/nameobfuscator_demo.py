"""
Name Obfuscator section — native ``PyNameObfuscator`` (R2 module #19, batch b5).

Shape mirrors ``player_demo.py`` (the canonical template):
  * ``build_nameobfuscator()`` calls the no-arg getters, CASTS each value via ``casts``, and
    returns display Blocks. The alias dict, surface list, ``ObservedPlayer`` structs, and the
    30-key diagnostics dict are all dereferenced explicitly (an ``ObservedPlayer`` handle is
    never repr'd — its fields are read one by one).
  * ``draw_nameobfuscator_view()`` renders those blocks and exposes every mutator/query as an
    explicit trigger button.

Hooks are owned by DLL initialization; Python controls enable/disable, aliases, surfaces, and
caches. There is no stub (native-only). ``clear`` is a bound duplicate alias of ``clear_aliases``.

R2 coverage (PyNameObfuscator, 23/23 wired, 0 skipped):
  Getters wired (Data): is_enabled, is_map_ready, alias_count, get_aliases, list_surfaces,
    is_surface_enabled, observed_count, get_observed_players, get_diagnostics.
  Queries wired (Data + Actions): get_real_name, get_display_name, require_real_name.
  Actions wired: enable, disable, set_alias, remove_alias, clear_aliases, clear,
    set_surface_enabled, scrub_guild_roster, scrub_guild_identity, clear_observed_cache,
    reset_diagnostics.
"""

import PyImGui

import PyNameObfuscator

from . import casts
from . import diagnostics
from . import ui

_SECTION = "NameObfuscator"

# Read-only ObservedPlayer fields (explicit deref list — no reflection).
_OBSERVED_FIELDS = ("player_number", "agent_id", "real_name", "display_name", "aliased")


class _State:
    real_name: str = ""
    fake_name: str = ""
    query_display: str = ""
    query_real: str = ""
    query_name: str = ""


state = _State()


# ---------------------------------------------------------------------------
# build_* — call getters, cast, return blocks
# ---------------------------------------------------------------------------
def _state_block():
    rows = [
        ("Is Enabled", casts.yesno(casts.safe(PyNameObfuscator.is_enabled))),
        ("Is Map Ready", casts.yesno(casts.safe(PyNameObfuscator.is_map_ready))),
        ("Alias Count", casts.safe(PyNameObfuscator.alias_count)),
        ("Observed Count", casts.safe(PyNameObfuscator.observed_count)),
    ]
    return ui.kv_block("State", rows)


def _aliases_block():
    aliases = casts.safe(PyNameObfuscator.get_aliases, default={}) or {}
    rows = [(real, fake) for real, fake in aliases.items()]
    return ui.multi_block(f"Aliases ({len(rows)})", ["Real Name", "Fake Name"], rows)


def _surfaces_block():
    surfaces = casts.safe(PyNameObfuscator.list_surfaces, default=[]) or []
    rows = []
    for surf in surfaces:
        on = casts.safe(PyNameObfuscator.is_surface_enabled, surf)
        rows.append((surf, casts.yesno(on) if on is not None else "<n/a>"))
    return ui.multi_block(f"Surfaces ({len(rows)})", ["Surface", "Enabled"], rows)


def _observed_block():
    players = casts.safe(PyNameObfuscator.get_observed_players, default=[]) or []
    rows = []
    for p in players:
        rows.append(tuple(casts.safe(getattr, p, field, default="<n/a>") for field in _OBSERVED_FIELDS))
    headers = ["Player #", "Agent ID", "Real Name", "Display Name", "Aliased"]
    return ui.multi_block(f"Observed Players ({len(rows)})", headers, rows)


def _diagnostics_block():
    diag = casts.safe(PyNameObfuscator.get_diagnostics, default={}) or {}
    # First five keys are bools; the rest are counters. Keep source order explicit.
    bool_keys = (
        "initialized",
        "player_join_hook_registered",
        "class_observer_hook_registered",
        "enabled",
        "current_map_ready",
    )
    counter_keys = (
        "player_packets_seen",
        "player_packets_empty_name",
        "player_packets_disabled",
        "player_packets_map_not_ready",
        "observed_captures",
        "observed_trylock_skips",
        "alias_hits",
        "class_observer_hits",
        "message_global_hits",
        "item_custom_hits",
        "mercenary_hits",
        "mercenary_self_skips",
        "guild_info_hits",
        "party_search_hits",
        "acct_name_hits",
        "acct_name_self_skips",
        "score_summary_hits",
        "score_summary_mode_skips",
        "score_summary_self_skips",
        "guild_charname_hits",
        "guild_identity_hits",
        "guild_invite_hits",
        "guild_motd_hits",
        "own_name_hits",
        "reverse_alias_collisions",
    )
    rows = [(k, casts.yesno(diag.get(k))) for k in bool_keys]
    rows.extend((k, diag.get(k)) for k in counter_keys)
    return ui.kv_block("Diagnostics", rows)


def _query_block():
    rows = [
        ("get_real_name(display)", casts.safe(PyNameObfuscator.get_real_name, state.query_display)),
        ("get_display_name(real)", casts.safe(PyNameObfuscator.get_display_name, state.query_real)),
        ("require_real_name(name)", casts.safe(PyNameObfuscator.require_real_name, state.query_name)),
    ]
    return ui.kv_block("Name Resolution Query (set inputs in Actions)", rows)


def build_nameobfuscator():
    return [
        _state_block(),
        _aliases_block(),
        _surfaces_block(),
        _observed_block(),
        _diagnostics_block(),
        _query_block(),
    ]


# ---------------------------------------------------------------------------
# Actions — explicit trigger buttons, fired only on click
# ---------------------------------------------------------------------------
def _draw_actions():
    # Live precondition hint: packet surfaces only rewrite while the master switch is on, and the
    # map-ready gate governs PlayerJoinInstance capture (native IsMapReady()).
    enabled = casts.safe(PyNameObfuscator.is_enabled)
    map_ready = casts.safe(PyNameObfuscator.is_map_ready)
    ui.text_muted(
        f"Obfuscator enabled: {casts.yesno(enabled)}   |   Map ready: {casts.yesno(map_ready)}   "
        "(surfaces/scrubs no-op while disabled)"
    )
    PyImGui.spacing()

    ui.section_header("Enable / Caches / Diagnostics")
    ui.action_button("Enable", PyNameObfuscator.enable, key="enable")
    PyImGui.same_line(0, 8)
    ui.action_button("Disable", PyNameObfuscator.disable, key="disable")
    PyImGui.same_line(0, 8)
    ui.action_button("Clear Observed Cache", PyNameObfuscator.clear_observed_cache, key="clear_observed")
    PyImGui.same_line(0, 8)
    ui.action_button("Reset Diagnostics", PyNameObfuscator.reset_diagnostics, key="reset_diag")

    PyImGui.spacing()
    ui.section_header("Aliases")
    state.real_name = PyImGui.input_text("Real Name", state.real_name)
    state.fake_name = PyImGui.input_text("Fake Name", state.fake_name)
    ui.action_button("Set Alias", PyNameObfuscator.set_alias, state.real_name, state.fake_name, key="set_alias")
    PyImGui.same_line(0, 8)
    ui.action_button("Remove Alias", PyNameObfuscator.remove_alias, state.real_name, key="remove_alias")
    ui.action_button("Clear Aliases", PyNameObfuscator.clear_aliases, key="clear_aliases")
    PyImGui.same_line(0, 8)
    ui.action_button("Clear (alias of Clear Aliases)", PyNameObfuscator.clear, key="clear")

    PyImGui.spacing()
    ui.section_header("Surfaces")
    # Per-surface toggles driven by the native list_surfaces() — guarantees the exact string key
    # SetSurfaceEnabled() expects (an unknown key silently returns False), so every surface works.
    surfaces = casts.safe(PyNameObfuscator.list_surfaces, default=[]) or []
    for surf in surfaces:
        on = casts.safe(PyNameObfuscator.is_surface_enabled, surf)
        PyImGui.text_unformatted(f"{surf}: {casts.yesno(on)}")
        PyImGui.same_line(0, 8)
        ui.action_button(
            f"Toggle##{surf}",
            PyNameObfuscator.set_surface_enabled,
            surf,
            not bool(on),
            key=f"surface::{surf}",
        )

    PyImGui.spacing()
    ui.section_header("Guild Scrub")
    ui.text_muted(
        "Scrub Guild Identity needs: enabled + 'guild_identity' surface on + an aliased guild "
        "currently loaded. Returns guilds changed (0 if any precondition is unmet)."
    )
    ui.action_button("Scrub Guild Identity", PyNameObfuscator.scrub_guild_identity, key="scrub_identity")
    ui.text_muted("Scrub Guild Roster is a native Phase 4 stub (not implemented): always returns 0.")
    ui.action_button("Scrub Guild Roster", PyNameObfuscator.scrub_guild_roster, key="scrub_roster")

    PyImGui.spacing()
    ui.section_header("Name Resolution Queries")
    state.query_display = PyImGui.input_text("Display Name", state.query_display)
    ui.action_button("Get Real Name", PyNameObfuscator.get_real_name, state.query_display, key="get_real")
    state.query_real = PyImGui.input_text("Real Name (query)", state.query_real)
    ui.action_button("Get Display Name", PyNameObfuscator.get_display_name, state.query_real, key="get_display")
    state.query_name = PyImGui.input_text("Name (require)", state.query_name)
    ui.action_button("Require Real Name", PyNameObfuscator.require_real_name, state.query_name, key="require_real")


# ---------------------------------------------------------------------------
# draw_*_view — uniform section entry point
# ---------------------------------------------------------------------------
def draw_nameobfuscator_view() -> None:
    blocks = build_nameobfuscator()
    diagnostics.dump_button(_SECTION, blocks)
    PyImGui.separator()
    if PyImGui.begin_tab_bar("NameObfuscatorTabs"):
        if PyImGui.begin_tab_item("Data"):
            ui.draw_blocks(_SECTION, blocks)
            PyImGui.end_tab_item()
        if PyImGui.begin_tab_item("Actions"):
            _draw_actions()
            PyImGui.end_tab_item()
        PyImGui.end_tab_bar()
