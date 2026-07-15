"""
Party section — reengineered to the DEMO 2.0 contract (mirrors ``player_demo`` exactly).

Data path: ``GLOBAL_CACHE.Party.*`` (the throttled/cached ``PartyCache``), aligned with the legacy
demo (``Widgets\\Coding\\Py4GW_DEMO.py``) exactly. The cache mirrors the base ``Party`` wrapper API —
same getters (``GetPlayers``/``GetHeroes``/``GetHenchmen``/``GetOthers``) and the same sub-namespaces
(``Players``/``Heroes``/``Henchmen``/``Pets``) — so this is a pure access-layer swap. Two members used
here are NOT on ``PartyCache`` and stay on the base ``Party`` wrapper (marked inline with a
``# base wrapper: not on GLOBAL_CACHE`` comment): ``GetPartyTarget`` (Summary) and ``GetHeroIndex``
(Actions). Every struct return is dereferenced field-by-field and cast via ``casts``.

IMPORTANT (Reforged surface): ``HeroPartyMember.hero_id`` / ``.primary`` / ``.secondary`` are now
``int`` (were ``Hero``/``Profession`` objects in legacy). We resolve them explicitly — hero name via
``GLOBAL_CACHE.Party.Heroes.GetHeroNameById(int)`` and professions via ``Profession``/``Profession_Names``.

R2 coverage — wired (every base ``Party`` wrapper member; each drives one or more of the 92 PyParty
methods/fields underneath):
  Scalars/bools (Data tab): GetPartyID, GetPartyLeaderID, GetOwnPartyNumber, GetPartyTarget,
    GetPartySize, GetPlayerCount, GetHeroCount, GetHenchmanCount, IsHardMode, IsNormalMode,
    IsHardModeUnlocked, IsPartyLoaded, IsPartyLeader, IsPartyDefeated, IsAllTicked,
    Heroes.IsAllFlagged, Heroes.GetAllFlag.
  Local-player chain (Data tab): Players.GetLoginNumberByAgentID, Players.GetPartyNumberFromLoginNumber,
    IsPlayerTicked.
  Rosters w/ per-member field deref (Data tab):
    Players  -> PlayerPartyMember.{login_number, called_target_id, is_connected, is_ticked} +
                Players.GetPartyNumberFromLoginNumber, Players.GetAgentIDByLoginNumber,
                Players.GetPlayerNameByLoginNumber.
    Heroes   -> HeroPartyMember.{hero_id, agent_id, owner_player_id, level, primary, secondary} +
                Heroes.GetHeroNameById, Heroes.GetHeroPartyPositionByAgentID, Heroes.IsHeroFlagged,
                Heroes.GetTargetIDByAgentID.
    Henchmen -> HenchmanPartyMember.{agent_id, level, profession} + Agent.GetNameByID.
    Others   -> bare ids + Agent.GetNameByID.
    Morale   -> GetPartyMorale() -> (agent_id, morale) + Agent.GetNameByID.
    Pet      -> Pets.GetPetInfo(struct).{agent_id, owner_agent_id, pet_name, model_file_id1,
                model_file_id2, behavior, locked_target_id} + Pets.GetPetID, Pets.GetPetBehavior.
  Query actions (Actions tab, fired on click): GetHeroIndex, Heroes.GetHeroAgentIDByPartyPosition,
    Heroes.GetHeroIDByPartyPosition, Heroes.GetHeroIDByAgentID, Heroes.GetHeroIdByName,
    Heroes.GetNameByAgentID, Heroes.IsHeroFlagged, IsPlayerTicked.
  Mutators (Actions tab, fired on click): SetTickasToggle, SetTicked, ToggleTicked, SetHardMode,
    SetNormalMode, ReturnToOutpost, LeaveParty, SearchParty, SearchPartyCancel, SearchPartyReply,
    RespondToPartyRequest, Players.InvitePlayer, Players.KickPlayer, Heroes.AddHero,
    Heroes.AddHeroByName, Heroes.KickHero, Heroes.KickHeroByName, Heroes.KickAllHeroes,
    Heroes.UseSkill, Heroes.SetSkillAIEnabled, Heroes.FlagHero, Heroes.FlagAllHeroes,
    Heroes.UnflagHero, Heroes.UnflagAllHeroes, Heroes.SetHeroBehavior, Henchmen.AddHenchman,
    Henchmen.KickHenchman, Pets.SetPetBehavior.

Intentionally skipped:
  * ``Party.party_instance()`` — plumbing accessor that returns the raw ``PyParty`` handle; not display
    data (rendering it would print the very raw-address defect this reengineer kills). Every other
    member calls through it.
  * ``Party.IsPlayerLoaded()`` — wrapper body is ``pass`` (returns None; unimplemented stub). Player
    load state is already surfaced by the Player section.
"""

import PyImGui

from Py4GWCoreLib import GLOBAL_CACHE
from Py4GWCoreLib.Agent import Agent
from Py4GWCoreLib.Player import Player
from Py4GWCoreLib.Party import Party
from Py4GWCoreLib.enums_src.GameData_enums import Profession
from Py4GWCoreLib.enums_src.GameData_enums import Profession_Names

from . import casts
from . import diagnostics
from . import ui

_SECTION = "Party"

_BEHAVIOR_NAMES = {0: "Fight", 1: "Guard", 2: "Avoid"}


class _State:
    agent_id: int = 0
    login_number: int = 0
    hero_id: int = 0
    hero_name: str = "Koss"
    hero_position: int = 0
    henchman_id: int = 0
    flag_x: float = 0.0
    flag_y: float = 0.0
    behavior: int = 0
    skill_slot: int = 1
    target_id: int = 0
    skill_ai_enabled: bool = True
    pet_behavior: int = 0
    pet_lock_target: int = 0
    search_type: int = 0
    advertisement: str = ""
    accept: bool = True
    respond_party_id: int = 0
    set_ticked: bool = True


state = _State()


# ---------------------------------------------------------------------------
# small local casts
# ---------------------------------------------------------------------------
def _prof(value):
    """int profession -> ``[id] - Name`` (Reforged HeroPartyMember.primary is an int)."""
    return casts.enum_name(Profession, value, Profession_Names)


def _behavior(value):
    try:
        i = int(value)
    except (TypeError, ValueError):
        return str(value)
    return casts.id_name(i, _BEHAVIOR_NAMES.get(i, "Unknown"))


# ---------------------------------------------------------------------------
# build_* — call getters, cast, return blocks (shared by render AND dump)
# ---------------------------------------------------------------------------
def _summary_block():
    flag_x, flag_y = casts.safe(GLOBAL_CACHE.Party.Heroes.GetAllFlag, default=(0.0, 0.0)) or (0.0, 0.0)
    rows = [
        ("Party ID", casts.safe(GLOBAL_CACHE.Party.GetPartyID)),
        ("Leader Agent ID", casts.safe(GLOBAL_CACHE.Party.GetPartyLeaderID)),
        ("Own Party Number", casts.safe(GLOBAL_CACHE.Party.GetOwnPartyNumber)),
        ("Party Target", casts.safe(Party.GetPartyTarget)),  # base wrapper: not on GLOBAL_CACHE
        ("Party Size", casts.safe(GLOBAL_CACHE.Party.GetPartySize)),
        ("Player Count", casts.safe(GLOBAL_CACHE.Party.GetPlayerCount)),
        ("Hero Count", casts.safe(GLOBAL_CACHE.Party.GetHeroCount)),
        ("Henchman Count", casts.safe(GLOBAL_CACHE.Party.GetHenchmanCount)),
        ("All-Heroes Flag", casts.vec(flag_x, flag_y)),
    ]
    return ui.kv_block("Summary", rows)


def _status_block():
    bools = [
        ("Is Hard Mode", bool(casts.safe(GLOBAL_CACHE.Party.IsHardMode))),
        ("Is Normal Mode", bool(casts.safe(GLOBAL_CACHE.Party.IsNormalMode))),
        ("Hard Mode Unlocked", bool(casts.safe(GLOBAL_CACHE.Party.IsHardModeUnlocked))),
        ("Is Party Loaded", bool(casts.safe(GLOBAL_CACHE.Party.IsPartyLoaded))),
        ("Is Party Leader", bool(casts.safe(GLOBAL_CACHE.Party.IsPartyLeader))),
        ("Is Party Defeated", bool(casts.safe(GLOBAL_CACHE.Party.IsPartyDefeated))),
        ("Is All Ticked", bool(casts.safe(GLOBAL_CACHE.Party.IsAllTicked))),
        ("All Heroes Flagged", bool(casts.safe(GLOBAL_CACHE.Party.Heroes.IsAllFlagged))),
    ]
    return ui.bool_block("Status Flags", bools)


def _local_player_block():
    agent_id = casts.safe(Player.GetAgentID, default=0) or 0
    login_number = casts.safe(GLOBAL_CACHE.Party.Players.GetLoginNumberByAgentID, agent_id, default=0)
    party_number = casts.safe(GLOBAL_CACHE.Party.Players.GetPartyNumberFromLoginNumber, login_number, default=-1)
    rows = [
        ("Player Agent ID", agent_id),
        ("Login Number", login_number),
        ("Party Number", party_number),
        ("Is Player Ticked (party#)", casts.yesno(casts.safe(GLOBAL_CACHE.Party.IsPlayerTicked, party_number))),
    ]
    return ui.kv_block("Local Player", rows)


def _players_block():
    players = casts.safe(GLOBAL_CACHE.Party.GetPlayers, default=[]) or []
    headers = ["Login#", "Party#", "Agent ID", "Name", "Called Target", "Connected", "Ticked"]
    rows = []
    for p in players:
        login = casts.safe(getattr, p, "login_number", default=0)
        rows.append((
            login,
            casts.safe(GLOBAL_CACHE.Party.Players.GetPartyNumberFromLoginNumber, login, default=-1),
            casts.safe(GLOBAL_CACHE.Party.Players.GetAgentIDByLoginNumber, login, default=0),
            casts.safe(GLOBAL_CACHE.Party.Players.GetPlayerNameByLoginNumber, login, default="?"),
            casts.safe(getattr, p, "called_target_id", default=0),
            casts.yesno(casts.safe(getattr, p, "is_connected", default=False)),
            casts.yesno(casts.safe(getattr, p, "is_ticked", default=False)),
        ))
    return ui.multi_block(f"Players ({len(rows)})", headers, rows)


def _heroes_block():
    heroes = casts.safe(GLOBAL_CACHE.Party.GetHeroes, default=[]) or []
    headers = [
        "Hero ID", "Name", "Agent ID", "Owner Player", "Level",
        "Primary", "Secondary", "Party Pos", "Flagged", "Locked Target",
    ]
    rows = []
    for h in heroes:
        hero_id = casts.safe(getattr, h, "hero_id", default=0)
        agent_id = casts.safe(getattr, h, "agent_id", default=0)
        pos = casts.safe(GLOBAL_CACHE.Party.Heroes.GetHeroPartyPositionByAgentID, agent_id, default=-1)
        rows.append((
            hero_id,
            casts.safe(GLOBAL_CACHE.Party.Heroes.GetHeroNameById, hero_id, default="?"),
            agent_id,
            casts.safe(getattr, h, "owner_player_id", default=0),
            casts.safe(getattr, h, "level", default=0),
            _prof(casts.safe(getattr, h, "primary", default=0)),
            _prof(casts.safe(getattr, h, "secondary", default=0)),
            pos,
            casts.yesno(casts.safe(GLOBAL_CACHE.Party.Heroes.IsHeroFlagged, pos)),
            casts.safe(GLOBAL_CACHE.Party.Heroes.GetTargetIDByAgentID, agent_id, default=0),
        ))
    return ui.multi_block(f"Heroes ({len(rows)})", headers, rows)


def _henchmen_block():
    henchmen = casts.safe(GLOBAL_CACHE.Party.GetHenchmen, default=[]) or []
    headers = ["Agent ID", "Name", "Level", "Profession"]
    rows = []
    for hm in henchmen:
        agent_id = casts.safe(getattr, hm, "agent_id", default=0)
        rows.append((
            agent_id,
            casts.safe(Agent.GetNameByID, agent_id, default="?"),
            casts.safe(getattr, hm, "level", default=0),
            _prof(casts.safe(getattr, hm, "profession", default=0)),
        ))
    return ui.multi_block(f"Henchmen ({len(rows)})", headers, rows)


def _others_block():
    others = casts.safe(GLOBAL_CACHE.Party.GetOthers, default=[]) or []
    headers = ["Agent ID", "Name"]
    rows = [(oid, casts.safe(Agent.GetNameByID, oid, default="?")) for oid in others]
    return ui.multi_block(f"Others ({len(rows)})", headers, rows)


def _morale_block():
    morale = casts.safe(GLOBAL_CACHE.Party.GetPartyMorale, default=[]) or []
    headers = ["Agent ID", "Name", "Morale"]
    rows = [(aid, casts.safe(Agent.GetNameByID, aid, default="?"), val) for aid, val in morale]
    return ui.multi_block(f"Party Morale ({len(rows)})", headers, rows)


def _pet_block():
    owner = casts.safe(Player.GetAgentID, default=0) or 0
    info = casts.safe(GLOBAL_CACHE.Party.Pets.GetPetInfo, owner)
    if not info:
        return ui.kv_block("Pet", [("GetPetInfo(player)", "None / no pet")])
    rows = [
        ("Owner Agent ID", owner),
        ("Pet Agent ID", casts.safe(getattr, info, "agent_id", default=0)),
        ("Pet ID (via GetPetID)", casts.safe(GLOBAL_CACHE.Party.Pets.GetPetID, owner, default=0)),
        ("Owner Agent (struct)", casts.safe(getattr, info, "owner_agent_id", default=0)),
        ("Pet Name", casts.safe(getattr, info, "pet_name", default="?")),
        ("Model File ID 1", casts.safe(getattr, info, "model_file_id1", default=0)),
        ("Model File ID 2", casts.safe(getattr, info, "model_file_id2", default=0)),
        ("Behavior", _behavior(casts.safe(getattr, info, "behavior", default=0))),
        ("Behavior (via GetPetBehavior)", _behavior(casts.safe(GLOBAL_CACHE.Party.Pets.GetPetBehavior, owner))),
        ("Locked Target ID", casts.safe(getattr, info, "locked_target_id", default=0)),
    ]
    return ui.kv_block("Pet", rows)


def build_party():
    return [
        _summary_block(),
        _status_block(),
        _local_player_block(),
        _players_block(),
        _heroes_block(),
        _henchmen_block(),
        _others_block(),
        _morale_block(),
        _pet_block(),
    ]


# ---------------------------------------------------------------------------
# Actions — explicit trigger buttons, fired only on click
# ---------------------------------------------------------------------------
def _draw_actions():
    ui.section_header("Party Membership / Mode")
    ui.action_button("Toggle Ticked", GLOBAL_CACHE.Party.ToggleTicked, key="toggle_tick")
    PyImGui.same_line(0, 8)
    state.set_ticked = PyImGui.checkbox("Ticked value", state.set_ticked)
    ui.action_button("Set Ticked", GLOBAL_CACHE.Party.SetTicked, state.set_ticked, key="set_ticked")
    PyImGui.same_line(0, 8)
    ui.action_button("Set Tick As Toggle", GLOBAL_CACHE.Party.SetTickasToggle, state.set_ticked, key="set_tick_toggle")
    ui.action_button("Set Hard Mode", GLOBAL_CACHE.Party.SetHardMode, key="hard")
    PyImGui.same_line(0, 8)
    ui.action_button("Set Normal Mode", GLOBAL_CACHE.Party.SetNormalMode, key="normal")
    ui.action_button("Return To Outpost", GLOBAL_CACHE.Party.ReturnToOutpost, key="rto")
    PyImGui.same_line(0, 8)
    ui.action_button("Leave Party", GLOBAL_CACHE.Party.LeaveParty, key="leave")

    PyImGui.spacing()
    ui.section_header("Players")
    state.agent_id = PyImGui.input_int("Agent ID / Player ID", state.agent_id)
    state.login_number = PyImGui.input_int("Login Number", state.login_number)
    ui.action_button("Invite Player (by id)", GLOBAL_CACHE.Party.Players.InvitePlayer, state.agent_id, key="invite")
    PyImGui.same_line(0, 8)
    ui.action_button("Kick Player (by login#)", GLOBAL_CACHE.Party.Players.KickPlayer, state.login_number, key="kick_player")
    ui.action_button("Is Player Ticked?", GLOBAL_CACHE.Party.IsPlayerTicked, state.login_number, key="q_ticked")
    PyImGui.same_line(0, 8)
    ui.action_button("Agent ID by Login#", GLOBAL_CACHE.Party.Players.GetAgentIDByLoginNumber, state.login_number, key="q_agent_by_login")

    PyImGui.spacing()
    ui.section_header("Heroes")
    state.hero_id = PyImGui.input_int("Hero ID", state.hero_id)
    state.hero_name = PyImGui.input_text("Hero Name", state.hero_name)
    state.hero_position = PyImGui.input_int("Hero Position", state.hero_position)
    ui.action_button("Add Hero", GLOBAL_CACHE.Party.Heroes.AddHero, state.hero_id, key="add_hero")
    PyImGui.same_line(0, 8)
    ui.action_button("Add Hero (by name)", GLOBAL_CACHE.Party.Heroes.AddHeroByName, state.hero_name, key="add_hero_name")
    ui.action_button("Kick Hero", GLOBAL_CACHE.Party.Heroes.KickHero, state.hero_id, key="kick_hero")
    PyImGui.same_line(0, 8)
    ui.action_button("Kick Hero (by name)", GLOBAL_CACHE.Party.Heroes.KickHeroByName, state.hero_name, key="kick_hero_name")
    PyImGui.same_line(0, 8)
    ui.action_button("Kick All Heroes", GLOBAL_CACHE.Party.Heroes.KickAllHeroes, key="kick_all_heroes")
    ui.action_button("Hero Index (owned)", Party.GetHeroIndex, state.hero_id, key="q_hero_index")  # base wrapper: not on GLOBAL_CACHE
    PyImGui.same_line(0, 8)
    ui.action_button("Hero ID by Name", GLOBAL_CACHE.Party.Heroes.GetHeroIdByName, state.hero_name, key="q_hero_id_name")
    ui.action_button("Agent ID by Position", GLOBAL_CACHE.Party.Heroes.GetHeroAgentIDByPartyPosition, state.hero_position, key="q_hero_agent_pos")
    PyImGui.same_line(0, 8)
    ui.action_button("Hero ID by Position", GLOBAL_CACHE.Party.Heroes.GetHeroIDByPartyPosition, state.hero_position, key="q_hero_id_pos")
    ui.action_button("Hero ID by Agent", GLOBAL_CACHE.Party.Heroes.GetHeroIDByAgentID, state.agent_id, key="q_hero_id_agent")
    PyImGui.same_line(0, 8)
    ui.action_button("Hero Name by Agent", GLOBAL_CACHE.Party.Heroes.GetNameByAgentID, state.agent_id, key="q_hero_name_agent")
    PyImGui.same_line(0, 8)
    ui.action_button("Is Hero Flagged? (pos)", GLOBAL_CACHE.Party.Heroes.IsHeroFlagged, state.hero_position, key="q_hero_flagged")

    PyImGui.spacing()
    ui.section_header("Hero Flags / Behavior / Skills")
    state.flag_x = PyImGui.input_float("Flag X", state.flag_x)
    state.flag_y = PyImGui.input_float("Flag Y", state.flag_y)
    ui.action_button("Flag Hero (agent id)", GLOBAL_CACHE.Party.Heroes.FlagHero, state.agent_id, state.flag_x, state.flag_y, key="flag_hero")
    PyImGui.same_line(0, 8)
    ui.action_button("Flag All Heroes", GLOBAL_CACHE.Party.Heroes.FlagAllHeroes, state.flag_x, state.flag_y, key="flag_all")
    ui.action_button("Unflag Hero (agent id)", GLOBAL_CACHE.Party.Heroes.UnflagHero, state.agent_id, key="unflag_hero")
    PyImGui.same_line(0, 8)
    ui.action_button("Unflag All Heroes", GLOBAL_CACHE.Party.Heroes.UnflagAllHeroes, key="unflag_all")
    state.behavior = PyImGui.input_int("Behavior (0=Fight 1=Guard 2=Avoid)", state.behavior)
    ui.action_button("Set Hero Behavior (agent id)", GLOBAL_CACHE.Party.Heroes.SetHeroBehavior, state.agent_id, state.behavior, key="set_hero_behavior")
    state.skill_slot = PyImGui.input_int("Skill Slot (1-8)", state.skill_slot)
    state.target_id = PyImGui.input_int("Target ID", state.target_id)
    ui.action_button("Use Hero Skill", GLOBAL_CACHE.Party.Heroes.UseSkill, state.agent_id, state.skill_slot, state.target_id, key="hero_use_skill")
    state.skill_ai_enabled = PyImGui.checkbox("Skill AI Enabled", state.skill_ai_enabled)
    ui.action_button("Set Hero Skill AI", GLOBAL_CACHE.Party.Heroes.SetSkillAIEnabled, state.agent_id, state.skill_slot, state.skill_ai_enabled, key="hero_skill_ai")

    PyImGui.spacing()
    ui.section_header("Henchmen")
    state.henchman_id = PyImGui.input_int("Henchman ID", state.henchman_id)
    ui.action_button("Add Henchman", GLOBAL_CACHE.Party.Henchmen.AddHenchman, state.henchman_id, key="add_hench")
    PyImGui.same_line(0, 8)
    ui.action_button("Kick Henchman", GLOBAL_CACHE.Party.Henchmen.KickHenchman, state.henchman_id, key="kick_hench")

    PyImGui.spacing()
    ui.section_header("Pet")
    state.pet_behavior = PyImGui.input_int("Pet Behavior (0/1/2)", state.pet_behavior)
    state.pet_lock_target = PyImGui.input_int("Pet Lock Target ID", state.pet_lock_target)
    ui.action_button("Set Pet Behavior", GLOBAL_CACHE.Party.Pets.SetPetBehavior, state.pet_behavior, state.pet_lock_target, key="set_pet_behavior")

    PyImGui.spacing()
    ui.section_header("Party Search / Requests")
    state.search_type = PyImGui.input_int("Search Type", state.search_type)
    state.advertisement = PyImGui.input_text("Advertisement", state.advertisement)
    ui.action_button("Search Party", GLOBAL_CACHE.Party.SearchParty, state.search_type, state.advertisement, key="search_party")
    PyImGui.same_line(0, 8)
    ui.action_button("Search Party Cancel", GLOBAL_CACHE.Party.SearchPartyCancel, key="search_cancel")
    state.accept = PyImGui.checkbox("Accept", state.accept)
    ui.action_button("Search Party Reply", GLOBAL_CACHE.Party.SearchPartyReply, state.accept, key="search_reply")
    state.respond_party_id = PyImGui.input_int("Respond Party ID", state.respond_party_id)
    ui.action_button("Respond To Party Request", GLOBAL_CACHE.Party.RespondToPartyRequest, state.respond_party_id, state.accept, key="respond_request")


# ---------------------------------------------------------------------------
# draw_*_view — uniform section entry point
# ---------------------------------------------------------------------------
def draw_party_view() -> None:
    blocks = build_party()
    diagnostics.dump_button(_SECTION, blocks)
    PyImGui.separator()
    if PyImGui.begin_tab_bar("PartyTabs"):
        if PyImGui.begin_tab_item("Data"):
            ui.draw_blocks(_SECTION, blocks)
            PyImGui.end_tab_item()
        if PyImGui.begin_tab_item("Actions"):
            _draw_actions()
            PyImGui.end_tab_item()
        PyImGui.end_tab_bar()
