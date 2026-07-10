# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# File: Dialog Sync.py   (no move_interact_blessing_npc fallback)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

import os
import tempfile
import time
import math
from types import SimpleNamespace

from Py4GW_widget_manager import get_widget_handler
from Py4GWCoreLib import *
from Py4GWCoreLib import (
    GLOBAL_CACHE,
    PyImGui,
    IconsFontAwesome5,
    ConsoleLog,
    Console,
    Routines,
    UIManager,
    SharedCommandType,
    Timer,
    ThrottledTimer,
Player
)
from Py4GWCoreLib.py4gwcorelib_src.Settings import Settings

from Sources.aC_Scripts.aC_api import (
    is_npc_dialog_visible,
    click_dialog_button,
    get_dialog_button_count,
)

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Constants & Paths
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
FLAG_DIR = os.path.join(tempfile.gettempdir(), "GuildWarsNPCSync")
os.makedirs(FLAG_DIR, exist_ok=True)
SECTION = "NPC_SYNC"

WINDOW_INI_PATH   = os.path.join(FLAG_DIR, "npc_sync_window.ini")
ini_window        = Settings("GuildWarsNPCSync/npc_sync_window.ini", "global")

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Throttles & Timers
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
_npc_sync_timer    = ThrottledTimer(1000)   # run FSM at most once per second
save_window_timer  = Timer()
save_window_timer.Start()

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Window State (persisted)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
win_x            = ini_window.get_int(SECTION, "window_x", 100)
win_y            = ini_window.get_int(SECTION, "window_y", 100)
win_collapsed    = ini_window.get_bool(SECTION, "window_collapsed", False)
first_run_window = True

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# FSM Constants (only used for â€œCome Hereâ€ and â€œChoiceâ€ on followers)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
IDLE, MOVING_LEADER, IN_DIALOG, CHOICE_DONE = range(4)
DIALOG_RESET_TIMEOUT = 2.0

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Sharedâ€memory â€œLeader Stateâ€ (on each follower)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
leader_target_agent = 0        # NPC agent ID last broadcast by leader
leader_choice       = -1       # Dialogâ€button index last broadcast
leader_position     = None     # (x, y, timestamp) last â€œCome Hereâ€ broadcast
leader_position_ts  = 0.0      # timestamp component of leader_position

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Perâ€follower runtime variables
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
last_choice_time    = None
state               = IDLE
last_leader_pos     = None    # (x, y, timestamp) follower is moving toward
last_processed_lts  = 0.0     # last processed timestamp for position


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Helpers
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def get_email_for_agent(agent_id: int) -> str | None:
    """
    SharedMemory does not expose GetAccountDataFromAgentID, so we iterate
    over GetAllAccountData and match PlayerID â†’ agent_id.
    """
    for account in GLOBAL_CACHE.ShMem.GetAllAccountData():
        if int(account.AgentData.AgentID) == agent_id:
            return account.AccountEmail
    return None


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Leaderâ€side â€œbroadcastâ€ functions
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def broadcast_target_to_party(agent_id: int):
    """
    Leader calls this to notify all followers: â€œNPC agent_id is our next target.â€
    We put agent_id into Params[0] so that InteractWithTarget can pick it up.
    """
    leader_email = Player.GetAccountEmail()
    if not leader_email:
        return

    for slot in GLOBAL_CACHE.Party.GetPlayers():
        a_id = GLOBAL_CACHE.Party.Players.GetAgentIDByLoginNumber(slot.login_number)
        member_email = get_email_for_agent(a_id)
        if not member_email or member_email == leader_email:
            continue

        GLOBAL_CACHE.ShMem.SendMessage(
            sender_email   = leader_email,
            receiver_email = member_email,
            command        = SharedCommandType.DialogSyncSetTarget,
            params         = (float(agent_id), 0.0, 0.0, 0.0),
        )

    ConsoleLog(
        "DialogSync",
        f"Leader broadcast target agent_id={agent_id}",
        Console.MessageType.Info
    )


def broadcast_choice_to_party(choice_idx: int):
    """
    Leader calls this to notify all followers: â€œClick dialog button = choice_idx.â€
    """
    leader_email = Player.GetAccountEmail()
    if not leader_email:
        return

    for slot in GLOBAL_CACHE.Party.GetPlayers():
        a_id = GLOBAL_CACHE.Party.Players.GetAgentIDByLoginNumber(slot.login_number)
        member_email = get_email_for_agent(a_id)
        if not member_email or member_email == leader_email:
            continue

        GLOBAL_CACHE.ShMem.SendMessage(
            sender_email   = leader_email,
            receiver_email = member_email,
            command        = SharedCommandType.DialogSyncSetChoice,
            params         = (float(choice_idx), 0.0, 0.0, 0.0),
        )

    ConsoleLog(
        "DialogSync",
        f"Leader broadcast choice={choice_idx}",
        Console.MessageType.Info
    )


def broadcast_position_to_party(x: float, y: float):
    """
    Leader calls this to notify all followers: â€œMove to (x, y).â€
    We do not broadcast (0, 0); that is treated as a noâ€op.
    """
    if x == 0.0 and y == 0.0:
        return

    leader_email = Player.GetAccountEmail()
    if not leader_email:
        return

    for slot in GLOBAL_CACHE.Party.GetPlayers():
        a_id = GLOBAL_CACHE.Party.Players.GetAgentIDByLoginNumber(slot.login_number)
        member_email = get_email_for_agent(a_id)
        if not member_email or member_email == leader_email:
            continue

        GLOBAL_CACHE.ShMem.SendMessage(
            sender_email   = leader_email,
            receiver_email = member_email,
            command        = SharedCommandType.DialogSyncSetPosition,
            params         = (float(x), float(y), 0.0, 0.0),
        )

    ConsoleLog(
        "DialogSync",
        f"Leader broadcast position=({x:.1f},{y:.1f})",
        Console.MessageType.Info
    )


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Reset & Initialize
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def reset_sync():
    """
    Clear all local â€œleader_*â€ state on the follower and return the FSM to IDLE.
    Broadcast only â€œclear targetâ€ to followers. No zeroâ€choice or zeroâ€position.
    """
    global leader_target_agent, leader_choice, leader_position, leader_position_ts
    global last_choice_time, state, last_leader_pos, last_processed_lts

    leader_target_agent = 0
    leader_choice       = -1
    leader_position     = None
    leader_position_ts  = 0.0

    last_choice_time    = None
    state               = IDLE
    last_leader_pos     = None
    last_processed_lts  = 0.0

    ConsoleLog("NPCSync", "Sync reset to idle", Console.MessageType.Info)


def setup():
    """
    Called once at startup on each client.
    """
    reset_sync()

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Main Logic Loop (called once per frame/tick)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def run_logic_if_needed():
    global last_choice_time, state, last_leader_pos, last_processed_lts
    global leader_target_agent, leader_choice, leader_position

    me        = Player.GetAgentID()
    is_leader = (GLOBAL_CACHE.Party.GetPartyLeaderID() == me)

    # â”€â”€ 1) If I am the leader, skip the follower FSM entirely â”€â”€
    if is_leader:
        return

    # â”€â”€ 2) Followers only: throttle to once per second â”€â”€
    if not _npc_sync_timer.IsExpired():
        return

    # â”€â”€ 3) Validate map for followers â”€â”€
    if not Routines.Checks.Map.MapValid():
        return

    # â”€â”€ 4) Followers: React to â€œleader_positionâ€ (Come Here) â”€â”€
    if leader_position is not None:
        lx, ly, lts = leader_position
        if not (lx == 0.0 and ly == 0.0):
            if state == IDLE and lts > last_processed_lts:
                last_leader_pos   = (lx, ly, lts)
                Player.Move(lx, ly)
                time.sleep(0.125)   # let the movement begin
                ConsoleLog("NPCSync", f"Follower moving to leader at ({lx:.1f},{ly:.1f})", Console.MessageType.Info)
                state = MOVING_LEADER
                last_processed_lts = lts

            elif state == MOVING_LEADER and last_leader_pos is not None:
                cx, cy    = Player.GetXY()
                tx, ty, _ = last_leader_pos
                if math.dist((cx, cy), (tx, ty)) < 50.0:
                    ConsoleLog("NPCSync", "Arrived at leaderâ€™s spot", Console.MessageType.Info)
                    last_leader_pos = None
                    state           = IDLE

    # â”€â”€ 5) Followers: Cancel/Reset if leader cleared target and position â”€â”€
    if state != IDLE and leader_target_agent == 0 and (leader_position is None or (leader_position[0] == 0.0 and leader_position[1] == 0.0)):
        reset_sync()
        return

    # â”€â”€ 6) Followers: Inâ€dialog â€œwait for leaderâ€™s choiceâ€ â”€â”€
    if state == IN_DIALOG:
        if leader_choice and leader_choice != last_choice:
            click_dialog_button(leader_choice)
            last_choice      = leader_choice
            last_choice_time = time.time()
            state            = CHOICE_DONE

    # â”€â”€ 7) Followers: After pressing choice, wait for dialog to close â”€â”€
    elif state == CHOICE_DONE:
        if is_npc_dialog_visible():
            leader_choice = -1
            last_choice   = None
            state         = IN_DIALOG
        elif last_choice_time and (time.time() - last_choice_time) > DIALOG_RESET_TIMEOUT:
            reset_sync()


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# UI Rendering (ImGui_Legacy) â€“ only draw when you are the leader
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def render_ui():
    global win_x, win_y, win_collapsed, first_run_window
    global leader_target_agent, leader_choice, leader_position

    me        = Player.GetAgentID()
    is_leader = (GLOBAL_CACHE.Party.GetPartyLeaderID() == me)
    if not is_leader:
        return

    # Window geometry delegated to ImGui native persistence

    PyImGui.begin("Dialog Sync", PyImGui.WindowFlags.AlwaysAutoResize)

    # â”€â”€ Leader UI: â€œCome Hereâ€ (Running Man) â”€â”€
    if PyImGui.button(IconsFontAwesome5.ICON_RUNNING):
        if Routines.Checks.Map.MapValid():
            x, y = Player.GetXY()
            if not (x == 0.0 and y == 0.0):
                leader_position    = (x, y, time.time())
                leader_position_ts = leader_position[2]
                broadcast_position_to_party(x, y)
            else:
                ConsoleLog("NPCSync", "Cannot broadcast position (0,0).", Console.MessageType.Warning)

    PyImGui.same_line(0.0, -1.0)

    # â”€â”€ Leader UI: â€œGo Interactâ€ (Phone) â”€â”€
    if PyImGui.button(IconsFontAwesome5.ICON_PHONE):
        tid = Player.GetTargetID()
        if tid:
            # 1) Update moduleâ€level variable
            leader_target_agent = tid

            # 2) Broadcast to followers
            broadcast_target_to_party(tid)

            # 3) Also have leader walk+interact via InteractWithTarget coroutine
            fake_msg = SimpleNamespace(
                SenderEmail   = Player.GetAccountEmail(),
                ReceiverEmail = Player.GetAccountEmail(),
                Params        = (str(tid), "0", "0", "0")
            )
            GLOBAL_CACHE.Coroutines.append(InteractWithTarget(-1, fake_msg))

        else:
            ConsoleLog("NPCSync", "No target selected, cannot broadcast NPC.", Console.MessageType.Warning)

    PyImGui.same_line(0.0, -1.0)

    # â”€â”€ Leader UI: â€œReset Syncâ€ (â†») â”€â”€
    if PyImGui.button(IconsFontAwesome5.ICON_SYNC):
        reset_sync()
        broadcast_target_to_party(0)   # clear agentâ€ID for followers

    # â”€â”€ Leader UI: â€œAll Click Button iâ€ when in dialog â”€â”€
    if is_npc_dialog_visible():
        count = get_dialog_button_count()
        for i in range(1, count + 1):
            if PyImGui.button(f"All Click Button {i}"):
                # Leader clicks locally
                UIManager.ClickDialogButton(i)

                # Record & broadcast to followers
                leader_choice = i
                broadcast_choice_to_party(i)

    PyImGui.end()

    # Window geometry delegated to ImGui native persistence


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Entry Points
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def main():
    # 1) Process incoming messages (e.g. follower: target broadcast â†’ InteractWithTarget)
    ProcessMessages()

    # 2) Run the follower FSM for â€œCome Hereâ€ and â€œChoiceâ€ (leader skips this entirely)
    run_logic_if_needed()

    # 3) Draw leaderâ€™s UI (followers see nothing)
    render_ui()


def configure():
    pass


__all__ = ["main", "configure"]
