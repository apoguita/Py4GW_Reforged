import Py4GW
import PyImGui

from .settings import Settings
from Py4GWCoreLib import Agent
from Py4GWCoreLib import GLOBAL_CACHE
from Py4GWCoreLib import ImGui
from Py4GWCoreLib import Map
from Py4GWCoreLib import Party
from Py4GWCoreLib import ModelID
from Py4GWCoreLib import Player
from Py4GWCoreLib import Range
from Py4GWCoreLib import Routines
from Py4GWCoreLib import SharedCommandType
from Py4GWCoreLib import Skill
from Py4GWCoreLib import SkillBar
from Py4GWCoreLib import ThrottledTimer
from Py4GWCoreLib import Timer
from Py4GWCoreLib.GlobalCache.SharedMemory import AccountStruct
from Py4GWCoreLib.GlobalCache.WhiteboardLocks import claim_resurrection_target
from Py4GWCoreLib.GlobalCache.WhiteboardLocks import publish_resurrection_scroll_state
from Py4GWCoreLib.GlobalCache.WhiteboardLocks import read_resurrection_scroll_states
from Py4GWCoreLib.ImGui_src.IconsFontAwesome5 import IconsFontAwesome5
from Py4GWCoreLib.py4gwcorelib_src.Console import Console
from Py4GWCoreLib.py4gwcorelib_src.Console import ConsoleLog

MODULE_NAME = "HeroAI Resurrection Scroll"

_SCROLL_MODEL_ID = ModelID.Scroll_Of_Resurrection.value
_CHECK_INTERVAL_MS = 1500
_USE_COOLDOWN_MS = 8000
_AFTERCAST_MS = 500
_CACHE_DELAY_MS = 8000

_RES_SKILLS = {
    2: "resurrection signet",
    52: "rebirth",
    58: "restore life",
    247: "resurrection chant",
    509: "we shall return!",
    878: "flesh of my flesh",
    894: "death pact signet",
    1180: "lively was naomei",
    1264: "sunspear rebirth signet",
    1778: "signet of return",
}
_RES_SKILL_IDS = set(_RES_SKILLS.keys())
_RES_SKILL_NAMES = set(_RES_SKILLS.values())

_BROADCAST_INTERVAL_MS = 1000

# SetResurrectionScroll message payload (leader -> account command):
#   Params = (enabled, skip_if_res_available, field_mask, 0)
#   field_mask selects which fields to apply; 0 = legacy payload (enabled only, from Params[0]).
_MSG_FIELD_ENABLED = 1
_MSG_FIELD_SKIP = 2

_settings = Settings()
_check_timer = ThrottledTimer(_CHECK_INTERVAL_MS)
_broadcast_timer = ThrottledTimer(_BROADCAST_INTERVAL_MS)
_cooldown_timer = Timer()
_cooldown_timer.Start()
_aftercast_timer = Timer()
_aftercast_timer.Start()
_explorable_entry_timer = Timer()

_status_text = ""
_res_cache: list[tuple[int, str, str]] = []
_cache_built = False
_last_was_explorable = False
_on_cooldown = False


def _get_same_party_accounts() -> list[AccountStruct]:
    """Live player accounts in this *actual party*, never all clients in shared memory.

    A missing PartyID does not authorize broadcasting to unrelated instances:
    use the in-game party login roster when available, otherwise fall back to self.
    Both the local player and followers must be on the same map instance.
    """
    self_email = str(Player.GetAccountEmail() or "").strip()
    if not self_email:
        return []

    self_account = GLOBAL_CACHE.ShMem.GetAccountDataFromEmail(self_email)
    try:
        if not Map.IsMapReady() or not Party.IsPartyLoaded():
            return [self_account] if self_account is not None else []
        party_id = int(Party.GetPartyID() or 0)
        party_login_numbers = {
            int(getattr(player, "login_number", 0) or 0)
            for player in (Party.GetPlayers() or [])
        }
        party_login_numbers.discard(0)
        local_map = (
            int(Map.GetMapID() or 0),
            int(Map.GetRegion()[0] or 0),
            int(Map.GetDistrict() or 0),
            int(Map.GetLanguage()[0] or 0),
        )
    except Exception:
        return [self_account] if self_account is not None else []

    if local_map[0] <= 0 or (party_id <= 0 and not party_login_numbers):
        return [self_account] if self_account is not None else []

    try:
        active_accounts = GLOBAL_CACHE.ShMem.GetAllAccountData(
            sort_results=False, include_isolated=True,
        )
    except TypeError:
        active_accounts = GLOBAL_CACHE.ShMem.GetAllAccountData(sort_results=False)

    accounts: list[AccountStruct] = []
    seen: set[str] = set()
    for account in active_accounts or []:
        email = str(getattr(account, "AccountEmail", "") or "").strip()
        if not email or email in seen or not bool(getattr(account, "IsSlotActive", False)):
            continue
        account_party_id = int(getattr(getattr(account, "AgentPartyData", None), "PartyID", 0) or 0)
        if party_id > 0 and account_party_id != party_id:
            continue
        data = getattr(account, "AgentData", None)
        account_login = int(getattr(data, "LoginNumber", 0) or 0)
        if party_login_numbers and account_login not in party_login_numbers and email != self_email:
            continue
        amap = getattr(data, "Map", None)
        account_map = (
            int(getattr(amap, "MapID", 0) or 0),
            int(getattr(amap, "Region", 0) or 0),
            int(getattr(amap, "District", 0) or 0),
            int(getattr(amap, "Language", 0) or 0),
        )
        if account_map != local_map:
            continue
        accounts.append(account)
        seen.add(email)

    # A temporary ShMem slot mismatch must not prevent the local UI from working.
    if self_email not in seen and self_account is not None:
        accounts.append(self_account)

    return sorted(
        accounts,
        key=lambda account: (
            int(getattr(getattr(account, "AgentPartyData", None), "PartyPosition", 9999) or 9999),
            str(getattr(account, "AccountEmail", "") or ""),
        ),
    )


def _build_res_cache() -> None:
    global _res_cache, _cache_built
    _res_cache = []

    player_id = Player.GetAgentID()
    if player_id != 0:
        try:
            player_skills = SkillBar.GetSkillbar()
            player_name = Agent.GetNameByID(player_id) or "Player"
            if not player_skills:
                ConsoleLog(MODULE_NAME, f"[Cache] {player_name}: skillbar empty (not loaded yet?)", Console.MessageType.Warning, log=False)
                return

            for skill_id in player_skills:
                skill_name = Skill.GetNameFromWiki(skill_id)
                if skill_id in _RES_SKILL_IDS or skill_name.lower() in _RES_SKILL_NAMES:
                    _res_cache.append((player_id, player_name, skill_name))
                    break
        except Exception as exc:
            ConsoleLog(MODULE_NAME, f"[Cache] Error reading local skillbar: {exc}", Console.MessageType.Error)
            return

    try:
        for account in GLOBAL_CACHE.ShMem.GetAllAccountData():
            account_agent_data = getattr(account, "AgentData", None)
            account_agent_id = int(getattr(account_agent_data, "AgentID", 0) or 0)
            if account_agent_id == 0 or account_agent_id == player_id:
                continue

            char_name = getattr(account_agent_data, "CharacterName", "") or getattr(account, "AccountEmail", "") or "Account"
            skillbar = getattr(account_agent_data, "Skillbar", None)
            skills = getattr(skillbar, "Skills", []) if skillbar is not None else []
            account_skill_ids = [int(skill.Id) for skill in skills if int(skill.Id) != 0]
            if not account_skill_ids:
                ConsoleLog(MODULE_NAME, f"[Cache] {char_name}: shared memory skillbar empty (not synced yet?)", Console.MessageType.Warning, log=False)
                return

            for skill_id in account_skill_ids:
                skill_name = Skill.GetNameFromWiki(skill_id)
                if skill_id in _RES_SKILL_IDS or skill_name.lower() in _RES_SKILL_NAMES:
                    _res_cache.append((account_agent_id, char_name, skill_name))
                    break
    except Exception as exc:
        ConsoleLog(MODULE_NAME, f"[Cache] Error reading shared memory: {exc}", Console.MessageType.Error)
        return

    if not _res_cache:
        ConsoleLog(MODULE_NAME, "[Cache] No party members have a res skill equipped", Console.MessageType.Info)
    else:
        ConsoleLog(MODULE_NAME, f"[Cache] {len(_res_cache)} party member(s) with res skills cached", Console.MessageType.Info)

    _cache_built = True


def rebuild_cache() -> None:
    global _cache_built
    _cache_built = False


def _alive_party_member_has_res_skill() -> bool:
    for agent_id, _, _ in _res_cache:
        if agent_id == 0:
            continue
        try:
            if Agent.IsValid(agent_id) and not Agent.IsDead(agent_id):
                return True
        except Exception:
            pass
    return False


def _broadcast_local_state() -> None:
    """Publish THIS account's resurrection-scroll state on the whiteboard so the party can read it."""
    publish_resurrection_scroll_state(
        _settings.get_account_resurrection_scroll_enabled(),
        _settings.get_account_resurrection_scroll_skip_if_res_available(),
    )


def _send_state_command(
    target_email: str,
    *,
    enabled: bool | None = None,
    skip: bool | None = None,
) -> None:
    """Command another account to change its resurrection-scroll state via Messaging (never by
    writing its file). The target applies it locally in _consume_toggle_messages and re-broadcasts."""
    sender_email = str(Player.GetAccountEmail() or "").strip()
    target = str(target_email or "").strip()
    if not sender_email or not target:
        return
    mask = 0
    if enabled is not None:
        mask |= _MSG_FIELD_ENABLED
    if skip is not None:
        mask |= _MSG_FIELD_SKIP
    if mask == 0:
        return
    GLOBAL_CACHE.ShMem.SendMessage(
        sender_email,
        target,
        SharedCommandType.SetResurrectionScroll,
        (1 if enabled else 0, 1 if skip else 0, mask, 0),
    )


def apply_state_command(message: object) -> bool:
    """Apply a SetResurrectionScroll message in its recipient's local settings.

    Used by both the HeroAI tick and the always-running Messaging widget: the
    first consumer to receive a command handles it instead of discarding it.
    The caller owns the MarkMessageAsFinished lifecycle.
    """
    account_email = str(Player.GetAccountEmail() or "").strip()
    if not account_email or str(getattr(message, "ReceiverEmail", "") or "").strip() != account_email:
        return False
    if int(getattr(message, "Command", SharedCommandType.NoCommand)) != int(SharedCommandType.SetResurrectionScroll):
        return False

    _settings.ensure_initialized()
    params = getattr(message, "Params", (0, 0, 0, 0)) or (0, 0, 0, 0)
    mask = int(params[2] or 0) if len(params) > 2 else 0
    changed = False
    if mask == 0 or (mask & _MSG_FIELD_ENABLED):
        # mask == 0 is the original enabled-only message format.
        _settings.set_account_resurrection_scroll_enabled(bool(int(params[0] or 0)))
        changed = True
    if mask & _MSG_FIELD_SKIP:
        _settings.set_account_resurrection_scroll_skip_if_res_available(bool(int(params[1] or 0)))
        changed = True

    if changed:
        _broadcast_local_state()
        ConsoleLog(
            "HeroAI",
            f"Resurrection Scroll {'enabled' if is_enabled() else 'disabled'} for local account",
            Console.MessageType.Info,
        )
    return True


def _consume_toggle_messages() -> None:
    account_email = str(Player.GetAccountEmail() or "").strip()
    if not account_email:
        return

    for message_index, message in GLOBAL_CACHE.ShMem.GetAllMessages():
        if message is None or not getattr(message, "Active", False):
            continue
        if apply_state_command(message):
            GLOBAL_CACHE.ShMem.MarkMessageAsFinished(account_email, message_index)


def is_enabled() -> bool:
    """LOCAL account's resurrection-scroll enabled state (the only one it can read from Settings)."""
    return _settings.get_account_resurrection_scroll_enabled()


def _account_state(account_email: str, states: dict[str, tuple[bool, bool]]) -> tuple[bool, bool]:
    """(enabled, skip) for an account: own Settings for the local account, whiteboard for the rest."""
    self_email = str(Player.GetAccountEmail() or "").strip()
    if account_email == self_email:
        return (
            _settings.get_account_resurrection_scroll_enabled(),
            _settings.get_account_resurrection_scroll_skip_if_res_available(),
        )
    return states.get(account_email, (False, False))


def are_all_party_accounts_enabled() -> bool:
    accounts = _get_same_party_accounts()
    if not accounts:
        return is_enabled()
    states = read_resurrection_scroll_states()
    return all(_account_state(str(account.AccountEmail or ""), states)[0] for account in accounts)


def toggle_all_accounts() -> bool:
    """Toggle the scroll option for the active party, including the local client."""
    sender_email = str(Player.GetAccountEmail() or "").strip()
    if not sender_email:
        return False

    accounts = _get_same_party_accounts()
    if not accounts:
        return False

    new_enabled = not are_all_party_accounts_enabled()
    # Local changes are immediate; never rely on a message addressed to self.
    _settings.set_account_resurrection_scroll_enabled(new_enabled)
    _broadcast_local_state()

    remote_count = 0
    for account in accounts:
        target_email = str(getattr(account, "AccountEmail", "") or "").strip()
        if not target_email or target_email == sender_email:
            continue
        _send_state_command(target_email, enabled=new_enabled)
        remote_count += 1

    ConsoleLog(
        "HeroAI",
        f"Resurrection Scroll {'enabled' if new_enabled else 'disabled'} for active party: "
        f"local + {remote_count} other account(s)",
        Console.MessageType.Info,
    )
    return new_enabled


def tick() -> None:
    global _on_cooldown, _status_text, _cache_built, _last_was_explorable

    _settings.ensure_initialized()
    _consume_toggle_messages()

    # Heartbeat this account's state onto the whiteboard so party members can read it (even while
    # disabled, so the leader UI can show a truthful "off").
    if _broadcast_timer.IsExpired():
        _broadcast_timer.Reset()
        _broadcast_local_state()

    if not is_enabled():
        _status_text = "Disabled"
        return

    if not _check_timer.IsExpired():
        return
    _check_timer.Reset()

    if not Routines.Checks.Map.MapValid():
        _status_text = "Map invalid"
        _cache_built = False
        _last_was_explorable = False
        return

    if not Map.IsExplorable():
        _status_text = "Not in explorable"
        _cache_built = False
        _last_was_explorable = False
        return

    skip_if_res_available = _settings.get_account_resurrection_scroll_skip_if_res_available()
    if skip_if_res_available and not _cache_built:
        if Routines.Checks.Map.IsMapReady() and Routines.Checks.Party.IsPartyLoaded():
            if not _last_was_explorable:
                _explorable_entry_timer.Reset()
                _last_was_explorable = True
                _status_text = "Waiting for skillbars to load..."
                return
            if not _explorable_entry_timer.HasElapsed(_CACHE_DELAY_MS):
                _status_text = "Waiting for skillbars to load..."
                return
            _build_res_cache()

    player_id = Player.GetAgentID()
    if player_id == 0:
        return

    if Agent.IsDead(player_id):
        _status_text = "Player is dead"
        return

    dead_ally_ids = Routines.Agents.GetDeadAllyArray(Range.Earshot.value)
    if not dead_ally_ids:
        _status_text = "All alive"
        _on_cooldown = False
        return

    # A client that cannot actually use a scroll must NOT reserve the dead
    # ally on the shared Whiteboard: that starves other accounts in multibox.
    if skip_if_res_available and _alive_party_member_has_res_skill():
        _status_text = "Dead party member - res skill available"
        return

    if not _aftercast_timer.HasElapsed(_AFTERCAST_MS):
        _status_text = "Dead party member - waiting aftercast"
        return

    if _on_cooldown and not _cooldown_timer.HasElapsed(_USE_COOLDOWN_MS):
        _status_text = "Dead party member - waiting cooldown"
        return

    item_id = GLOBAL_CACHE.Inventory.GetFirstModelID(_SCROLL_MODEL_ID)
    if item_id == 0:
        _status_text = "Dead party member - no scroll in inventory"
        return

    dead_ally_id = claim_resurrection_target(
        dead_ally_ids,
        skill_id=0,
        aftercast_delay=_USE_COOLDOWN_MS,
    )
    if dead_ally_id == 0:
        _status_text = "Dead party member locked by another account"
        return

    Player.ChangeTarget(dead_ally_id)
    ConsoleLog(MODULE_NAME, f"Party member dead, using Scroll of Resurrection on {dead_ally_id}", Console.MessageType.Info)
    GLOBAL_CACHE.Inventory.UseItem(item_id)
    _aftercast_timer.Reset()
    _on_cooldown = True
    _cooldown_timer.Reset()
    _status_text = "Used scroll!"


def draw_settings() -> None:
    _settings.ensure_initialized()

    if ImGui.begin_child("##ResurrectionScrollSettingsChild", (0, 0)):
        PyImGui.text("Party Members")
        PyImGui.separator()

        accounts = _get_same_party_accounts()
        if not accounts:
            PyImGui.text_disabled("No same-party accounts found.")
        else:
            self_email = str(Player.GetAccountEmail() or "").strip()
            states = read_resurrection_scroll_states()
            for account in accounts:
                account_email = str(account.AccountEmail or "")
                account_name = str(getattr(getattr(account, "AgentData", None), "CharacterName", "") or account_email)
                is_local = account_email == self_email

                enabled, skip = _account_state(account_email, states)

                new_enabled = PyImGui.checkbox(f"Enable##res_scroll_enabled_{account_email}", enabled)
                if new_enabled != enabled:
                    if is_local:
                        _settings.set_account_resurrection_scroll_enabled(new_enabled)
                        _broadcast_local_state()
                    else:
                        _send_state_command(account_email, enabled=new_enabled)

                PyImGui.same_line(0, 8)
                PyImGui.text(account_name)

                new_skip = PyImGui.checkbox(f"Skip if res skill available##res_scroll_skip_{account_email}", skip)
                if new_skip != skip:
                    if is_local:
                        _settings.set_account_resurrection_scroll_skip_if_res_available(new_skip)
                        _broadcast_local_state()
                    else:
                        _send_state_command(account_email, skip=new_skip)

        PyImGui.spacing()
        PyImGui.separator()
        PyImGui.text(f"Local status: {_status_text}")

        if _res_cache:
            PyImGui.spacing()
            PyImGui.text("Local cached res skill holders:")
            for agent_id, name, skill_name in _res_cache:
                alive = "?"
                try:
                    alive = "alive" if Agent.IsValid(agent_id) and not Agent.IsDead(agent_id) else "dead"
                except Exception:
                    pass
                PyImGui.bullet_text(f"{name}: {skill_name} ({alive})")

        PyImGui.spacing()
        if PyImGui.button(f"{IconsFontAwesome5.ICON_SCROLL} Rebuild local cache"):
            rebuild_cache()

    ImGui.end_child()
