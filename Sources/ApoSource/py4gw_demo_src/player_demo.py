"""
Player section — the canonical template for every reengineered section.

Shape (see SPEC_reengineer.md §1.2):
  * ``build_player()`` calls the base ``Player`` wrapper getters, CASTS each value via ``casts``,
    and returns a list of display Blocks. No struct ever reaches a renderer un-dereferenced.
  * ``draw_player_view()`` renders those blocks, exposes every action binding as an explicit
    trigger button (never auto-fired), and offers the per-section Dump-to-file button.

Data path: ``Player.*`` (reads char/world context + PyPlayer bindings). Base wrapper, not
GlobalCache (no PlayerCache exists; enrichment lives in the base wrapper — R3 §15).

R2 coverage — PyPlayer getters wired: GetAgentID, GetName, GetXY, GetTargetID, GetObservingID,
GetPlayerNumber, GetLoginNumber, GetPartyNumber, GetLevel, IsPlayerLoaded, GetAccountName,
GetAccountEmail, GetPlayerUUID, GetInstanceUptime, GetAgent, GetRankData, GetTournamentRewardPoints,
GetMorale, GetExperience, GetSkillPointData, GetKurzickData, GetLuxonData, GetImperialData,
GetBalthazarData, GetAccountFlags, IsDhuumsCovenant, IsMelandrusAccord, IsReforged, GetActiveTitleID,
GetTitleArray, GetTitle, GetPlayerStatus, GetPlayerStatusName, GetMissionsCompleted,
GetMissionsBonusCompleted, GetMissionsCompletedHM, GetMissionsBonusCompletedHM,
GetLearnableCharacterSkills, GetUnlockedCharacterSkills, GetControlledMinions, RequestChatHistory,
IsChatHistoryReady, GetChatHistory, IsTyping.
Actions wired: ChangeTarget, CallTarget, Interact, Move, SendChat, SendChatCommand, SendWhisper,
SendDialog, SendRawDialog, SendAutomaticDialog, SendFakeChat, DepositFaction, SetActiveTitle,
RemoveActiveTitle, SetPlayerStatus, RequestChatHistory.
"""

import PyImGui

from Py4GWCoreLib import Agent
from Py4GWCoreLib.Player import Player

from . import casts
from . import diagnostics
from . import ui

_SECTION = "Player"


class _State:
    target_id: int = 0
    move_x: float = 0.0
    move_y: float = 0.0
    faction_id: int = 0
    dialog_hex: str = "0x84"
    auto_dialog: int = 1
    chat_channel: str = "#"
    chat_message: str = "hello"
    whisper_target: str = ""
    title_id: int = 0
    status_id: int = 0


state = _State()


# ---------------------------------------------------------------------------
# build_* — call getters, cast, return blocks (shared by render AND dump)
# ---------------------------------------------------------------------------
def _identity_block():
    px, py = casts.safe(Player.GetXY, default=(0.0, 0.0)) or (0.0, 0.0)
    uuid = casts.safe(Player.GetPlayerUUID, default=())
    rows = [
        ("Agent ID", casts.safe(Player.GetAgentID)),
        ("Name", casts.safe(Player.GetName)),
        ("XY", casts.vec(px, py)),
        ("Target ID", casts.safe(Player.GetTargetID)),
        ("Observing ID", casts.safe(Player.GetObservingID)),
        ("Player Number", casts.safe(Player.GetPlayerNumber)),
        ("Login Number", casts.safe(Player.GetLoginNumber)),
        ("Party Number", casts.safe(Player.GetPartyNumber)),
        ("Level", casts.safe(Player.GetLevel)),
        ("Is Player Loaded", casts.yesno(casts.safe(Player.IsPlayerLoaded))),
        ("Is Typing", casts.yesno(casts.safe(Player.IsTyping))),
        ("Account Name", casts.safe(Player.GetAccountName)),
        ("Account Email", casts.safe(Player.GetAccountEmail)),
        ("Player UUID", str(uuid)),
        ("Instance Uptime (ms)", casts.safe(Player.GetInstanceUptime)),
        ("Player Status", casts.safe(Player.GetPlayerStatus)),
        ("Player Status Name", casts.safe(Player.GetPlayerStatusName)),
    ]
    return ui.kv_block("Identity", rows)


def _progression_block():
    rank, rating, qualifier, wins, losses = casts.safe(Player.GetRankData, default=(0, 0, 0, 0, 0)) or (0, 0, 0, 0, 0)
    skill_cur, skill_total = casts.safe(Player.GetSkillPointData, default=(0, 0)) or (0, 0)
    rows = [
        ("Rank / Rating", f"{rank} / {rating}"),
        ("Qualifier Points", qualifier),
        ("Wins / Losses", f"{wins} / {losses}"),
        ("Tournament Reward Points", casts.safe(Player.GetTournamentRewardPoints)),
        ("Morale", casts.safe(Player.GetMorale)),
        ("Experience", casts.safe(Player.GetExperience)),
        ("Skill Points (cur / total)", f"{skill_cur} / {skill_total}"),
        ("Kurzick", str(casts.safe(Player.GetKurzickData))),
        ("Luxon", str(casts.safe(Player.GetLuxonData))),
        ("Imperial", str(casts.safe(Player.GetImperialData))),
        ("Balthazar", str(casts.safe(Player.GetBalthazarData))),
    ]
    return ui.kv_block("Progression", rows)


def _account_block():
    rows = [
        ("Account Flags", casts.flags(casts.safe(Player.GetAccountFlags, default=0))),
    ]
    bools = [
        ("Dhuum's Covenant", bool(casts.safe(Player.IsDhuumsCovenant))),
        ("Melandru's Accord", bool(casts.safe(Player.IsMelandrusAccord))),
        ("Reforged", bool(casts.safe(Player.IsReforged))),
    ]
    return [ui.kv_block("Account", rows), ui.bool_block("Account Flags (decoded)", bools)]


def _title_block():
    active = casts.safe(Player.GetActiveTitleID, default=-1)
    indices = casts.safe(Player.GetTitleArray, default=[]) or []
    rows = [
        ("Active Title Index", active),
        ("Active Title Name", _title_name(active)),
        ("Title Array (len)", len(indices)),
        ("Title Indices", str(list(indices))),
    ]
    # Title struct cast — explicit field deref (R1 §4), guarded field-by-field.
    title = casts.safe(Player.GetTitle, active)
    if title is None:
        rows.append(("GetTitle(active)", "None"))
    else:
        for field in (
            "current_points", "current_title_tier_index", "points_needed_current_rank",
            "next_title_tier_index", "max_title_rank", "is_percentage_based", "has_tiers",
        ):
            rows.append((f"title.{field}", casts.safe(getattr, title, field, default="<n/a>")))
    return ui.kv_block("Titles", rows)


def _title_name(index):
    try:
        from Py4GWCoreLib import TitleID
        from Py4GWCoreLib import TITLE_NAME

        return TITLE_NAME.get(TitleID(index), "Unknown")
    except Exception:  # noqa: BLE001 - enum/table may be absent
        return "<unresolved>"


def _missions_block():
    def _fmt(fn):
        lst = casts.safe(fn, default=[]) or []
        return f"[{len(lst)}] {list(lst)}"

    rows = [
        ("Missions Completed", _fmt(Player.GetMissionsCompleted)),
        ("Missions Bonus Completed", _fmt(Player.GetMissionsBonusCompleted)),
        ("Missions Completed (HM)", _fmt(Player.GetMissionsCompletedHM)),
        ("Missions Bonus Completed (HM)", _fmt(Player.GetMissionsBonusCompletedHM)),
        ("Learnable Skills", _fmt(Player.GetLearnableCharacterSkills)),
        ("Unlocked Skills", _fmt(Player.GetUnlockedCharacterSkills)),
    ]
    return ui.kv_block("Missions & Skills", rows)


def _minions_block():
    minions = casts.safe(Player.GetControlledMinions, default=[]) or []
    rows = []
    for agent_id, count in minions:
        rows.append((agent_id, casts.safe(Agent.GetNameByID, agent_id, default="?"), count))
    return ui.multi_block("Controlled Minions", ["Agent ID", "Name", "Count"], rows)


def _chat_block():
    ready = bool(casts.safe(Player.IsChatHistoryReady))
    history = casts.safe(Player.GetChatHistory, default=[]) or [] if ready else []
    rows = [
        ("Chat History Ready", casts.yesno(ready)),
        ("Chat History (len)", len(history)),
    ]
    return ui.kv_block("Chat History (request via Actions tab)", rows)


def build_player():
    blocks = [_identity_block(), _progression_block()]
    blocks.extend(_account_block())
    blocks.append(_title_block())
    blocks.append(_missions_block())
    blocks.append(_minions_block())
    blocks.append(_chat_block())
    return blocks


# ---------------------------------------------------------------------------
# Actions — explicit trigger buttons, fired only on click
# ---------------------------------------------------------------------------
def _draw_actions():
    ui.section_header("Targeting / Movement")
    state.target_id = PyImGui.input_int("Agent ID", state.target_id)
    ui.action_button("Change Target", Player.ChangeTarget, state.target_id, key="chg_target")
    PyImGui.same_line(0, 8)
    ui.action_button("Call Target", Player.CallTarget, state.target_id, key="call_target")
    PyImGui.same_line(0, 8)
    ui.action_button("Interact", Player.Interact, state.target_id, key="interact")
    state.move_x = PyImGui.input_float("Move X", state.move_x)
    state.move_y = PyImGui.input_float("Move Y", state.move_y)
    ui.action_button("Move", Player.Move, state.move_x, state.move_y, key="move")

    PyImGui.spacing()
    ui.section_header("Chat / Dialog")
    state.chat_channel = PyImGui.input_text("Channel", state.chat_channel)
    state.chat_message = PyImGui.input_text("Message", state.chat_message)
    ui.action_button("Send Chat", Player.SendChat, state.chat_channel, state.chat_message, key="send_chat")
    PyImGui.same_line(0, 8)
    ui.action_button("Send Chat Command", Player.SendChatCommand, state.chat_message, key="chat_cmd")
    state.whisper_target = PyImGui.input_text("Whisper To", state.whisper_target)
    ui.action_button("Send Whisper", Player.SendWhisper, state.whisper_target, state.chat_message, key="whisper")
    state.dialog_hex = PyImGui.input_text("Dialog (hex, e.g. 0x84)", state.dialog_hex)
    ui.action_button("Send Dialog", Player.SendDialog, state.dialog_hex, key="send_dialog")
    PyImGui.same_line(0, 8)
    ui.action_button("Send Raw Dialog", Player.SendRawDialog, _try_int(state.dialog_hex), key="send_raw_dialog")
    state.auto_dialog = PyImGui.input_int("Auto Dialog Button #", state.auto_dialog)
    ui.action_button("Send Automatic Dialog", Player.SendAutomaticDialog, state.auto_dialog, key="auto_dialog")
    ui.action_button("Request Chat History", Player.RequestChatHistory, key="req_chat")

    PyImGui.spacing()
    ui.section_header("Faction / Titles / Status")
    state.faction_id = PyImGui.input_int("Faction ID", state.faction_id)
    ui.action_button("Deposit Faction", Player.DepositFaction, state.faction_id, key="deposit")
    state.title_id = PyImGui.input_int("Title ID", state.title_id)
    ui.action_button("Set Active Title", Player.SetActiveTitle, state.title_id, key="set_title")
    PyImGui.same_line(0, 8)
    ui.action_button("Remove Active Title", Player.RemoveActiveTitle, key="rm_title")
    state.status_id = PyImGui.input_int("Player Status", state.status_id)
    ui.action_button("Set Player Status", Player.SetPlayerStatus, state.status_id, key="set_status")


def _try_int(text):
    try:
        return int(text, 16) if isinstance(text, str) and text.lower().startswith("0x") else int(text)
    except (TypeError, ValueError):
        return 0


# ---------------------------------------------------------------------------
# draw_*_view — uniform section entry point
# ---------------------------------------------------------------------------
def draw_player_view() -> None:
    blocks = build_player()
    diagnostics.dump_button(_SECTION, blocks)
    PyImGui.separator()
    if PyImGui.begin_tab_bar("PlayerTabs"):
        if PyImGui.begin_tab_item("Data"):
            ui.draw_blocks(_SECTION, blocks)
            PyImGui.end_tab_item()
        if PyImGui.begin_tab_item("Actions"):
            _draw_actions()
            PyImGui.end_tab_item()
        PyImGui.end_tab_bar()
