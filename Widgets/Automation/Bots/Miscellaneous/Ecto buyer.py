"""Ecto Buyer - buys Glob of Ectoplasm from the Rare Material Trader.

The purchase itself is not reimplemented here. `Routines.Yield.Merchant.BuyEctoplasm`
owns the whole flow: it walks to the trader, withdraws gold from storage while the
storage balance stays above the threshold, quotes every unit and buys it, and stops
when the storage gold reaches the threshold, the character gold runs out, or the
trader stops answering. This widget only decides *when* to call it, keeps the
threshold, and reports what happened.

Threshold semantics: the storage balance is the gate. A run starts only when
`storage_gold > threshold` and keeps buying until the storage balance sits at the
threshold, so the gold spent is the character's own gold first and then whatever
has to be pulled out of storage. The default is 500.000 gold, as requested.

Deliberately manual: there is no timer and no auto-buy. `Buy on main` buys on this
account only. `Buy on alts` never buys here: it asks the other accounts of the party
to buy, so the coordinating account spends nothing on that path. The click and the
order share the same routine and the same safeguards:

  - the request is the framework's own SharedCommandType.EnableWidget message,
    which makes each receiving client switch this widget on (the Messaging widget
    of that client handles the message);
  - the terms travel in `Widgets/EctoBuyer/order.ini` (global scope), so every
    client reads the same session, threshold and cap, and writes its own
    `Widgets/EctoBuyer/status_<email>.ini` back;
  - an account only obeys an order that is fresh, uncancelled, lists its email and
    comes from an account of the same party; the account that issued the order is
    never one of its executors, which keeps the purchase of the main behind its
    own button;
  - the account that started the run heartbeats the order; when it stops the order
    goes stale, and accounts that never started stand down. With the close option
    on, an account switches this widget off when its part is over.

A click or an order that cannot run (not in an outpost, no trader nearby, storage
at or below the threshold) reports the reason instead of spending anything, and a
run already in flight is never started twice.

Safety: the transaction uses the game trader UI, so the character must be in an
outpost with the trader reachable. This file never moves gold itself; it only calls
the routine that does.
"""

import re
import time

import PyImGui
import PySystem

from Py4GWCoreLib import Agent
from Py4GWCoreLib import AgentArray
from Py4GWCoreLib import Color
from Py4GWCoreLib import GLOBAL_CACHE
from Py4GWCoreLib import ImGui
from Py4GWCoreLib import Map
from Py4GWCoreLib import Player
from Py4GWCoreLib import Routines
from Py4GWCoreLib import ThrottledTimer
from Py4GWCoreLib.enums_src.Multiboxing_enums import SharedCommandType
from Py4GWCoreLib.GlobalCache.shared_memory_src.AccountStruct import AccountStruct
from Py4GWCoreLib.py4gwcorelib_src.Settings import Settings
from Py4GWCoreLib.py4gwcorelib_src.WidgetManager import get_widget_handler

MODULE_NAME = "Ecto Buyer"
MODULE_ICON = "Assets/Textures/Item Models/00930-Glob_of_Ectoplasm.png"
OPTIONAL = True

# The widget manager resolves remote enable/disable by the file stem, exact match
# (WidgetHandler._get_widget_by_plain_name), so this string has to keep the
# lowercase "b" of "Ecto buyer.py". Renaming the file would change this value.
WIDGET_NAME = "Ecto buyer"

# Name the trader carries in the client. Several outposts have one, so the widget
# resolves the nearest instead of hardcoding a position.
TRADER_NAME = "Rare Material Trader"

INI_PATH = "Widgets/Automation/Bots/Miscellaneous/EctoBuyer"
INI_FILENAME = "EctoBuyer.ini"

# Party coordination: global-scope documents, the same mechanism Party Trade
# Collector uses. The account that starts the run writes the order; every
# participating account writes its own status file.
ORDER_PATH = "Widgets/EctoBuyer/order.ini"
STATUS_PATH = "Widgets/EctoBuyer/status_{email}.ini"
ORDER_SECTION = "Order"
STATUS_SECTION = "Status"

# An order is only obeyed while the issuer keeps refreshing it, so a client that
# closes mid-run does not leave the party buying forever.
ORDER_POLL_S = 0.5
ORDER_HEARTBEAT_S = 2.0
ORDER_STALE_S = 20.0
STATUS_REFRESH_S = 1.0
PARTY_RUN_TIMEOUT_S = 900.0

_MSG = PySystem.Console.MessageType

_SETTINGS_SECTION = "Settings"
_KEY_THRESHOLD = "StorageGoldThreshold"
_KEY_MAX_ECTO = "MaxEctoPerRun"
_KEY_CLOSE_ALTS = "CloseAltsWhenDone"

DEFAULT_THRESHOLD = 500_000

_settings = Settings(f"{INI_PATH}/{INI_FILENAME}", "account")
_settings_loaded = False

_ini_key = ""
_threshold = DEFAULT_THRESHOLD
_max_ecto = 0  # 0 means "no cap": buy until the storage balance hits the threshold
_close_alts = True  # switch this widget off on the accounts that already finished
_running = False
_status = "idle"
_last_metrics: dict | None = None
# Structured outcome of the last sequence; the party order publishes it verbatim.
_last_outcome: dict | None = None
# The trader lookup walks every agent in the map, so the window caches it.
_trader_display: tuple[float, float] | None = None
# Same reason: the party scan walks every account of the shared memory.
_peer_count = 0
_party_id_display = 0
_display_timer = ThrottledTimer(1_000)


def _log(message: str, message_type: PySystem.Console.MessageType = PySystem.Console.MessageType.Info) -> None:
    """Console line that names the widget, so every message is attributable."""
    PySystem.Console.Log(MODULE_NAME, message, message_type)


def _safe(email: str) -> str:
    """Filesystem-safe file stem for the per-account status document."""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", email.strip().lower()) or "unknown"


def _party_doc(path: str) -> Settings:
    return Settings(path, "global")


def _order_doc() -> Settings:
    return _party_doc(ORDER_PATH)


def _status_doc(email: str) -> Settings:
    return _party_doc(STATUS_PATH.format(email=_safe(email)))


def _publish(doc: Settings, values: dict[str, object], section: str) -> None:
    """Write a shared document and flush it so the other clients see it now."""
    for key, value in values.items():
        doc.set(section, key, value)
    doc.save()


def _fresh(doc: Settings) -> Settings:
    """Re-read a shared document before trusting it: another client wrote it."""
    try:
        doc.reload()
    except Exception:
        pass
    return doc


def _my_email() -> str:
    try:
        return str(Player.GetAccountEmail() or "").strip().lower()
    except Exception:
        return ""


def _account(email: str) -> AccountStruct | None:
    if not email:
        return None
    try:
        return GLOBAL_CACHE.ShMem.GetAccountDataFromEmail(email)
    except Exception:
        return None


def _my_party_id() -> int:
    """Party id of this client, read live. Zero when there is no party."""
    try:
        live = int(GLOBAL_CACHE.Party.GetPartyID() or 0)
    except Exception:
        live = 0
    if live:
        return live
    # Fallback: the id this client publishes to the shared memory, for the window in
    # which the local party context is not ready yet.
    return _account_party_id(_account(_my_email()))


def _account_party_id(acc: AccountStruct | None) -> int:
    if acc is None:
        return 0
    try:
        return int(acc.AgentPartyData.PartyID or 0)
    except Exception:
        return 0


def _is_player_account(acc: AccountStruct) -> bool:
    """False for heroes, pets and inactive slots: only players are real peers."""
    try:
        if bool(getattr(acc, "IsHero", False)) or bool(getattr(acc, "IsPet", False)):
            return False
        return bool(getattr(acc, "IsSlotActive", True))
    except Exception:
        return False


def _party_peers() -> list[AccountStruct]:
    """Other player accounts of this party.

    Co-location is not required: every account buys at its own Rare Material Trader,
    so an alt in another outpost (or another district) is a perfectly good target.
    The party is the only scope.
    """
    me = _my_email()
    party_id = _my_party_id()
    if not me or not party_id:
        return []
    try:
        accounts = GLOBAL_CACHE.ShMem.GetAllAccountData()
    except Exception:
        return []
    peers: list[AccountStruct] = []
    for acc in accounts:
        email = str(acc.AccountEmail or "").strip().lower()
        if not email or email == me or not _is_player_account(acc):
            continue
        if _account_party_id(acc) != party_id:
            continue
        peers.append(acc)
    return peers


def _emails(raw: str) -> list[str]:
    return [part.strip().lower() for part in str(raw or "").split("|") if part.strip()]


def _close_self(reason: str) -> None:
    """Switch this widget off so its window does not linger on an idle account."""
    _log(f"Closing {MODULE_NAME} on this account: {reason}.")
    try:
        get_widget_handler().disable_widget(WIDGET_NAME)
    except Exception as exc:
        _log(f"Could not close the widget: {exc}", _MSG.Warning)


def _load_settings() -> None:
    """Read the stored configuration once per session."""
    global _settings_loaded, _threshold, _max_ecto, _close_alts
    if _settings_loaded:
        return
    _threshold = max(0, int(_settings.get_int(_SETTINGS_SECTION, _KEY_THRESHOLD, DEFAULT_THRESHOLD)))
    _max_ecto = max(0, int(_settings.get_int(_SETTINGS_SECTION, _KEY_MAX_ECTO, 0)))
    _close_alts = bool(_settings.get_bool(_SETTINGS_SECTION, _KEY_CLOSE_ALTS, True))
    _settings_loaded = True


def _save_settings() -> None:
    _settings.set(_SETTINGS_SECTION, _KEY_THRESHOLD, int(_threshold))
    _settings.set(_SETTINGS_SECTION, _KEY_MAX_ECTO, int(_max_ecto))
    _settings.set(_SETTINGS_SECTION, _KEY_CLOSE_ALTS, bool(_close_alts))


def _character_gold() -> int:
    try:
        return int(GLOBAL_CACHE.Inventory.GetGoldOnCharacter())
    except Exception:
        return 0


def _storage_gold() -> int:
    try:
        return int(GLOBAL_CACHE.Inventory.GetGoldInStorage())
    except Exception:
        return 0


# The client prints gold with "." between thousands, so the widget's numbers read
# the same way the game reads them. One constant keeps it a one-line change for a
# client that groups with commas instead.
_GROUP_SEPARATOR = "."


def _format_gold(value: int | float) -> str:
    """Group a gold amount for display: 1234567 -> 1.234.567.

    Display only. Gold that travels to another account or to the buy routine stays
    an int; formatting is never parsed back.
    """
    return f"{int(value):,}".replace(",", _GROUP_SEPARATOR)


def _trader_position() -> tuple[float, float] | None:
    """Nearest Rare Material Trader to the player, or None when there is none.

    The buy routine walks to the point it is handed and interacts there, so the
    point has to be the trader itself: handing it the player's position would make
    it interact with whatever happens to stand next to the party.
    """
    if not Routines.Checks.Map.MapValid():
        return None
    player_x, player_y = Player.GetXY()
    best: tuple[float, float] | None = None
    best_distance = 0.0
    for agent_id in AgentArray.GetAgentArray() or []:
        if Agent.GetNameByID(agent_id) != TRADER_NAME:
            continue
        agent_x, agent_y = Agent.GetXY(agent_id)
        dx = float(agent_x) - float(player_x)
        dy = float(agent_y) - float(player_y)
        distance = dx * dx + dy * dy
        if best is None or distance < best_distance:
            best = (float(agent_x), float(agent_y))
            best_distance = distance
    return best


def _buy_coroutine(position: tuple[float, float]):
    """Drive the owner routine and keep the widget state in sync."""
    global _running, _status, _last_metrics, _last_outcome
    try:
        metrics = yield from Routines.Yield.Merchant.BuyEctoplasm(
            x=float(position[0]),
            y=float(position[1]),
            use_storage_gold=True,
            # Spending down to the threshold is the whole point, so both bounds are it.
            start_threshold=int(_threshold),
            stop_threshold=int(_threshold),
            max_ecto_to_buy=int(_max_ecto) if _max_ecto > 0 else None,
        )
        _last_metrics = metrics or {}
        bought = int(_last_metrics.get("bought_items", 0) or 0)
        _status = f"done: {bought} ecto bought"
        _last_outcome = {"state": "done", "bought": bought, "msg": _status}
        _log(
            f"Bought {bought} ecto. Storage gold {_format_gold(_storage_gold())}"
            f" (threshold {_format_gold(_threshold)})."
            f" Metrics: {_last_metrics}",
            PySystem.Console.MessageType.Success if bought else PySystem.Console.MessageType.Info,
        )
    except Exception as error:
        _status = f"error: {error}"
        _last_outcome = {"state": "error", "bought": 0, "msg": str(error)}
        _log(f"Buy routine failed: {error}", PySystem.Console.MessageType.Error)
    finally:
        _running = False


def _start_buy() -> bool:
    """Start one buy sequence. Returns whether it actually started."""
    global _running, _status, _last_outcome
    if _running:
        return False
    if not Routines.Checks.Map.MapValid():
        _status = "waiting: no map loaded"
        return False
    if not Map.IsOutpost():
        _status = "waiting: the trader only exists in an outpost"
        return False
    storage_gold = _storage_gold()
    if storage_gold <= _threshold:
        _status = (
            f"waiting: storage {_format_gold(storage_gold)}"
            f" <= threshold {_format_gold(_threshold)}"
        )
        return False
    position = _trader_position()
    if position is None:
        _status = f"waiting: no '{TRADER_NAME}' nearby"
        return False
    _running = True
    _status = "buying"
    _last_outcome = None
    _log(
        f"Starting: character {_format_gold(_character_gold())},"
        f" storage {_format_gold(storage_gold)}, threshold {_format_gold(_threshold)},"
        f" trader at ({position[0]:.0f}, {position[1]:.0f})."
    )
    GLOBAL_CACHE.Coroutines.append(_buy_coroutine(position))
    return True


class _PartyOrder:
    """Obeys the order published by the account that started the party run.

    This is the only path that buys without a click, and it only obeys an order
    that is fresh, uncancelled, lists this account by email, and comes from an
    account of the same party. The issuer never obeys its own order: on the
    coordinating account the purchase stays behind the Buy on main button.
    """

    def __init__(self) -> None:
        self.session = ""
        self.done: set[str] = set()      # sessions this account already answered
        self.closed: set[str] = set()    # sessions this account already closed itself for
        self.active = False              # this account is executing an order right now
        self.close_after = False
        self._last_poll = 0.0
        self._last_status = 0.0

    def tick(self) -> None:
        now = time.monotonic()
        if now - self._last_poll < ORDER_POLL_S:
            return
        self._last_poll = now

        doc = _fresh(_order_doc())
        session = str(doc.get_str(ORDER_SECTION, "session", "")).strip()
        me = _my_email()
        if not session or not me:
            return

        cancelled = bool(doc.get_bool(ORDER_SECTION, "cancel", False))
        close_after = bool(doc.get_bool(ORDER_SECTION, "close_after", False))
        stale = time.time() - float(doc.get_float(ORDER_SECTION, "ts", 0.0)) > ORDER_STALE_S

        if self.active:
            self._watch(close_after)
            return

        if me not in _emails(doc.get_str(ORDER_SECTION, "accounts", "")) or session in self.done:
            return

        main_email = str(doc.get_str(ORDER_SECTION, "main_email", "")).strip().lower()

        if main_email == me:
            # The issuer never executes its own order: on the coordinating account the
            # only purchase path is the "Buy on main" button. Orders published by an
            # older version listed the issuer among the accounts, so this also covers
            # a document still lying around from a previous run.
            self.done.add(session)
            return

        if cancelled or stale:
            # The issuer gave up before this account started.
            self.done.add(session)
            if close_after and session not in self.closed and not _running:
                self.closed.add(session)
                _close_self("the party run ended before this account started")
            return

        main_acc = _account(main_email)
        my_party = _my_party_id()
        issuer_party = _account_party_id(main_acc)
        if not my_party or issuer_party != my_party:
            self.done.add(session)
            _log(
                f"Party run ignored: issuer {main_email or '?'} is in party {issuer_party},"
                f" this account is in party {my_party}.",
                _MSG.Warning,
            )
            return

        self._start(session, doc, close_after)

    def _start(self, session: str, doc: Settings, close_after: bool) -> None:
        global _threshold, _max_ecto, _last_outcome
        if _running:
            # A manual run is in flight. Leave the session unclaimed so the order is
            # retried on the next poll instead of being reported as skipped.
            return
        # Reload safety: an account that already answered this session (its own status
        # document says so) does not buy twice if the widget is reopened while the
        # order is still being refreshed.
        mine = _fresh(_status_doc(_my_email()))
        if str(mine.get_str(STATUS_SECTION, "session", "")).strip() == session:
            self.done.add(session)
            _log(f"Party run {session}: already answered by this account.", _MSG.Info)
            return
        # The issuer's terms win: this run uses its threshold and cap.
        _threshold = max(0, int(doc.get_int(ORDER_SECTION, "threshold", _threshold)))
        _max_ecto = max(0, int(doc.get_int(ORDER_SECTION, "max_ecto", _max_ecto)))
        _save_settings()

        self.session = session
        self.close_after = close_after
        self.done.add(session)
        self.active = True
        self._last_status = 0.0

        if not _start_buy():
            # _start_buy explains the refusal in the window status, and the outcome
            # records it so the issuer's panel stops waiting for this account.
            reason = str(_status).replace("waiting: ", "", 1)
            self._report("skipped", reason, 0)
            _last_outcome = {"state": "skipped", "bought": 0, "msg": reason}
            self.active = False
            _log(f"Party run {session} skipped: {_status}", _MSG.Warning)
            if close_after:
                self.closed.add(session)
                _close_self("nothing to do for this account")
            return

        self._report("running", "buying", 0)
        _log(f"Party run {session}: buying (threshold {_threshold}).", _MSG.Success)

    def _watch(self, close_after: bool) -> None:
        """Follow the local run. A purchase in flight is never aborted."""
        now = time.monotonic()
        if _running:
            if now - self._last_status >= STATUS_REFRESH_S:
                self._last_status = now
                self._report("running", _status, 0)
            return

        outcome = _last_outcome or {}
        state = str(outcome.get("state", "done"))
        msg = str(outcome.get("msg", _status))
        bought = int(outcome.get("bought", 0) or 0)
        self._report(state, msg, bought)
        self.active = False
        _log(f"Party run {self.session}: {state} ({msg}).")
        if close_after or self.close_after:
            self.closed.add(self.session)
            _close_self("party run finished")

    def _report(self, state: str, msg: str, bought: int) -> None:
        _publish(_status_doc(_my_email()), {
            "session": self.session,
            "state": state,
            "msg": msg,
            "bought": int(bought),
            "storage_gold": _storage_gold(),
            "ts": time.time(),
        }, STATUS_SECTION)


class _PartyLauncher:
    """Asks the alts of this party to buy, and follows what each one reports.

    The request is the framework's SharedCommandType.EnableWidget message, which
    the receiving client handles in its Messaging widget; the terms travel in the
    order document. This state only exists on the account that pressed the button.
    """

    def __init__(self) -> None:
        self.session = ""
        self.accounts: list[str] = []
        self.names: dict[str, str] = {}
        self.results: dict[str, str] = {}
        self.tracking = False
        self.started = 0.0
        self._last_read = 0.0
        self._last_beat = 0.0

    def start(self) -> None:
        """Ask every alt of this party to buy. This account never buys on this path."""
        if self.tracking:
            _log("A party run is already in flight.", _MSG.Warning)
            return

        me = _my_email()
        if not me or _account(me) is None:
            _log("This account is not in shared memory: cannot address the party.", _MSG.Error)
            return

        peers = _party_peers()
        if not peers:
            _log(
                f"No other account of this party is visible (party {_my_party_id()})."
                " Accept the invites first, or check that the alts run this widget.",
                _MSG.Warning,
            )
            return

        self.accounts = []
        self.names = {}
        self.results = {}
        asked = 0
        for acc in peers:
            email = str(acc.AccountEmail or "").strip().lower()
            if not email:
                continue
            self.accounts.append(email)
            self.names[email] = str(acc.AgentData.CharacterName or "unnamed")
            self.results[email] = "waiting"
            try:
                GLOBAL_CACHE.ShMem.SendMessage(
                    me, email, SharedCommandType.EnableWidget, (0, 0, 0, 0), (WIDGET_NAME, "", "", "")
                )
                asked += 1
            except Exception as exc:
                self.results[email] = f"error: {exc}"
                _log(f"Could not ask {email} to open the widget: {exc}", _MSG.Warning)

        if not self.accounts:
            _log("None of the party peers could be addressed: nothing to start.", _MSG.Warning)
            self.results = {}
            self.names = {}
            return

        self.session = f"e{int(time.time() * 1000)}"
        self.started = time.time()
        self.tracking = True
        self._last_read = 0.0
        self._publish_order(False)
        _log(
            f"Party run {self.session}: {len(self.accounts)} alt(s), {asked} asked to buy."
            " This account does not buy on this path.",
            _MSG.Info,
        )

    def _publish_order(self, cancelled: bool) -> None:
        _publish(_order_doc(), {
            "session": self.session,
            "main_email": _my_email(),
            "accounts": "|".join(self.accounts),
            "threshold": int(_threshold),
            "max_ecto": int(_max_ecto),
            "close_after": bool(_close_alts),
            "cancel": bool(cancelled),
            "ts": time.time(),
        }, ORDER_SECTION)
        self._last_beat = time.monotonic()

    def tick(self) -> None:
        """Heartbeat the order and keep the per-account results fresh."""
        if not self.tracking:
            return
        now = time.monotonic()
        if time.time() - self.started > PARTY_RUN_TIMEOUT_S:
            self.stop("timed out")
            return
        if now - self._last_beat >= ORDER_HEARTBEAT_S:
            self._publish_order(False)
        if now - self._last_read < STATUS_REFRESH_S:
            return
        self._last_read = now
        self._read_results()
        if self._finished():
            self.tracking = False
            _log(f"Party run {self.session} finished.", _MSG.Success)

    def _read_results(self) -> None:
        """Collect what each alt reported for this session."""
        for email in self.accounts:
            doc = _fresh(_status_doc(email))
            if str(doc.get_str(STATUS_SECTION, "session", "")) != self.session:
                continue
            state = str(doc.get_str(STATUS_SECTION, "state", "")).strip()
            if state:
                self.results[email] = _compose(state, str(doc.get_str(STATUS_SECTION, "msg", "")))

    def _finished(self) -> bool:
        if _running:
            return False
        for result in self.results.values():
            if str(result).lower().startswith(("waiting", "running", "buying", "starting")):
                return False
        return True

    def stop(self, reason: str = "stopped") -> None:
        """Tell the party to stand down. A purchase already in flight finishes."""
        if not self.session:
            return
        for email, result in list(self.results.items()):
            if str(result).lower().startswith("waiting"):
                self.results[email] = f"cancelled ({reason})"
        self._publish_order(True)
        _log(f"Party run {self.session} stopped: {reason}.", _MSG.Warning)
        self.tracking = False

    def clear(self) -> None:
        self.session = ""
        self.accounts = []
        self.names = {}
        self.results = {}
        self.tracking = False


_order = _PartyOrder()
_launcher = _PartyLauncher()


def update() -> None:
    """Non-UI hook: never buys on its own, only obeys a party order."""
    _load_settings()
    _order.tick()
    _launcher.tick()


def _compose(state: str, msg: str) -> str:
    """One display line, without repeating the state word twice."""
    text = str(msg or "").strip()
    if not text:
        return state
    if state and text.lower().startswith(state.lower()):
        return text
    return f"{state}: {text}" if state else text


def _pending(result: str) -> bool:
    """True while an account has not answered the order yet."""
    return str(result).lower().startswith(("waiting", "running", "buying", "starting"))


def _result_color(result: str) -> tuple[int, int, int, int]:
    low = str(result).lower()
    if low.startswith("done"):
        return (150, 220, 150, 255)
    if low.startswith("skipped"):
        return (200, 200, 120, 255)
    if low.startswith(("error", "cancelled", "timed")):
        return (240, 150, 140, 255)
    if low.startswith("waiting"):
        return (170, 170, 170, 255)
    return (255, 200, 100, 255)


def tooltip() -> None:
    PyImGui.begin_tooltip()

    title_color = Color(255, 200, 100, 255)
    ImGui.push_font("Regular", 20)
    PyImGui.text_colored(MODULE_NAME, title_color.to_tuple_normalized())
    ImGui.pop_font()
    PyImGui.separator()

    PyImGui.text("Buys Glob of Ectoplasm from the Rare Material Trader.")
    PyImGui.spacing()
    PyImGui.text_colored("Rules:", title_color.to_tuple_normalized())
    PyImGui.bullet_text("Buys only when you press Buy on main, or when an alt obeys an order.")
    PyImGui.bullet_text("Never runs while the storage gold is at or below the threshold.")
    PyImGui.bullet_text("Spends the character's gold first, then pulls from storage.")
    PyImGui.bullet_text("Stops when the storage balance reaches the threshold.")
    PyImGui.spacing()
    PyImGui.text_colored("Buy on alts:", title_color.to_tuple_normalized())
    PyImGui.bullet_text("Asks the same widget to open on every alt of this party.")
    PyImGui.bullet_text("This account never buys on that path: Buy on main is its only purchase.")
    PyImGui.bullet_text("Each alt buys with the threshold and cap sent by the issuer.")
    PyImGui.bullet_text("An alt only obeys an order from its own party.")
    PyImGui.bullet_text("Each alt buys at its own trader: same outpost not required.")
    PyImGui.bullet_text("Closing the window with its X switches the widget off.")
    PyImGui.bullet_text("Closing it cancels the alts that have not started.")

    PyImGui.end_tooltip()


def draw() -> None:
    """Render the widget window."""
    global _ini_key, _threshold, _max_ecto, _close_alts, _trader_display
    global _peer_count, _party_id_display

    _load_settings()
    if not _ini_key:
        _ini_key = _settings.name
        if not _ini_key:
            return

    if _display_timer.IsExpired():
        _display_timer.Reset()
        _trader_display = _trader_position()
        _peer_count = len(_party_peers())
        _party_id_display = _my_party_id()

    expanded, keep_open = ImGui.BeginWithClose(
        _ini_key, MODULE_NAME, p_open=True, flags=PyImGui.WindowFlags.AlwaysAutoResize
    )
    if expanded:
        character_gold = _character_gold()
        storage_gold = _storage_gold()

        PyImGui.text(f"Character gold: {_format_gold(character_gold)}")
        PyImGui.text(f"Storage gold:   {_format_gold(storage_gold)}")
        PyImGui.separator()

        new_threshold = PyImGui.input_int("Storage gold threshold", int(_threshold), 10_000, 100_000)
        PyImGui.same_line(0, 12)
        PyImGui.text_disabled(f"= {_format_gold(new_threshold)}")
        if new_threshold != _threshold:
            _threshold = max(0, int(new_threshold))
            _save_settings()

        new_max = PyImGui.input_int("Max ecto per run (0 = no cap)", int(_max_ecto), 1, 10)
        if new_max != _max_ecto:
            _max_ecto = max(0, int(new_max))
            _save_settings()

        PyImGui.separator()
        PyImGui.text_disabled(f"Party {_party_id_display} - {_peer_count} alt(s) visible")
        if _running:
            PyImGui.text_colored("Running...", (255, 200, 100, 255))
        else:
            if PyImGui.button("Buy on main"):
                _start_buy()
            PyImGui.same_line()
            if _launcher.tracking:
                PyImGui.text_disabled("party run in flight")
            elif PyImGui.button(f"Buy on alts ({_peer_count})##buy_alts"):
                _launcher.start()

        new_close = PyImGui.checkbox("Close the widget on the alts when done", _close_alts)
        if new_close != _close_alts:
            _close_alts = bool(new_close)
            _save_settings()

        PyImGui.text_wrapped(f"Status: {_status}")

        if _order.session:
            PyImGui.text(f"Party order: {_order.session}")

        if _launcher.results:
            answered = sum(1 for result in _launcher.results.values() if not _pending(result))
            PyImGui.separator()
            PyImGui.text(f"Party run {_launcher.session}: {answered} / {len(_launcher.results)} answered")
            for email, result in _launcher.results.items():
                name = _launcher.names.get(email, email)
                PyImGui.text_colored(f"{name}: {result}", _result_color(result))
            if _launcher.tracking:
                if PyImGui.button("Stop party run"):
                    _launcher.stop("stopped from this account")
            elif PyImGui.button("Clear party log"):
                _launcher.clear()

        if _trader_display is None:
            PyImGui.text_colored(f"No '{TRADER_NAME}' in this map.", (255, 190, 80, 255))
        else:
            PyImGui.text(f"Trader at ({_trader_display[0]:.0f}, {_trader_display[1]:.0f})")

        if storage_gold <= _threshold:
            PyImGui.text_colored(
                "Storage gold is at or below the threshold: nothing to buy.",
                (160, 160, 160, 255),
            )

        if _last_metrics:
            PyImGui.separator()
            PyImGui.text("Last run:")
            for key, value in _last_metrics.items():
                PyImGui.text(f"  {key}: {value}")

    ImGui.End(_ini_key)
    if not keep_open:
        # The window's X switches the widget off, like the catalog toggle: on_disable
        # then stands the party down instead of leaving an invisible widget obeying
        # orders. ImGui only owns the click; the widget's state belongs to the manager.
        _close_self("its window was closed")


def on_enable() -> None:
    """Put the transient state back when the manager switches the widget on.

    The module globals are already fresh after a reload, so this only matters when
    the same instance is re-enabled. `_running` is deliberately left alone: a
    purchase started before the widget was switched off keeps running inside the
    coroutine manager, and clearing the flag here would let a second sequence start
    on top of the first one.
    """
    global _status, _last_metrics, _last_outcome, _trader_display
    _status = "idle"
    _last_metrics = None
    _last_outcome = None
    _trader_display = None
    _display_timer.Reset()


def on_disable() -> None:
    """Switched off from the manager or from the window's X: stand the party down.

    Only the account that started the run has a launcher, so this is a no-op on an
    alt. A purchase already in flight is not aborted: the order only stops the
    accounts that have not started yet.
    """
    if _launcher.tracking:
        _launcher.stop("the widget was closed on the issuing account")


if __name__ == "__main__":
    update()
    draw()
