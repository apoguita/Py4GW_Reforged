from __future__ import annotations

import os
import time
from typing import Callable

import Py4GW
import PySystem
import PyImGui
from Py4GWCoreLib import (
    Agent,
    ConsoleLog,
    GLOBAL_CACHE,
    Map,
    Player,
    Range,
    Routines,
)
from Py4GWCoreLib.BottingTree import BottingTree
from Py4GWCoreLib.Context import GWContext
from Py4GWCoreLib.Item import has_active_party_summon
from Py4GWCoreLib.Listeners import Listeners
from Py4GWCoreLib.native_src.internals.types import Vec2f
from Py4GWCoreLib.py4gwcorelib_src.BehaviorTree import BehaviorTree
from Py4GWCoreLib.py4gwcorelib_src.Settings import Settings
from Py4GWCoreLib.routines_src.BehaviourTrees import BT as RoutinesBT
from Py4GWCoreLib.routines_src.behaviourtrees_src.shared import BTShared
from Sources.ApoSource.ApoBottingLib import wrappers as BT
from Sources.Sky.Support import attach_botting_tree_support
from Widgets.System.Messaging import get_inventory_count, reset_inventory_count

from Py4GWCoreLib.enums_src.Multiboxing_enums import SharedCommandType
from Py4GWCoreLib.enums_src.Player_enums import PlayerStatus

TEXTURE = os.path.join(PySystem.Console.get_projects_path(), "Assets", "Textures", "Module_Icons", "doa.png")
MODULE_ICON = "Assets\\Textures\\Module_Icons\\doa.png"

MODULE_NAME = "Farm Gemstones Redux"
GATE_OF_ANGUISH_OUTPOST = 474
MISSION_MAP = 445

ENTRY_PRIEST_COORDS = Vec2f(6010, -13344)
ENTRY_DIALOG_ID = 0x84

FIGHT_POSITION = (-3379.43, -4959.41)
DEFENSE_LEASH_MAX_DISTANCE = 1200.0
DEFENSE_LEASH_RELEASE_DISTANCE = 650.0
DEFENSE_LEASH_REISSUE_MS = 400
GEMSTONE_HERO_IDS = (21, 25, 14,4)

GEMSTONE_MODEL_IDS = (
    21128,  # Margonite Gemstone
    21129,  # Stygian Gemstone
    21130,  # Titan Gemstone
    21131,  # Torment Gemstone
)

GEMSTONE_NAMES = {
    21128: "Margonite",
    21129: "Stygian",
    21130: "Titan",
    21131: "Torment",
}

STATISTICS_FILE = (
    "Widgets/Automation/Bots/Farmers/Trophies/"
    "Farm_Gemstones_Redux_BT.ini"
)
_STATS_SECTION = "Statistics"
_CHAR_NAMES_SECTION = "Character Names"
_GEMSTONE_DROP_SECTIONS = {
    model_id: f"Gemstone Drops {model_id}"
    for model_id in GEMSTONE_MODEL_IDS
}

_INVENTORY_QUERY_TIMEOUT_MS = 10_000
_INVENTORY_QUERY_POLL_MS = 200

_settings = Settings(STATISTICS_FILE, "global")
_statistics_loaded = False

# Persistent statistics.
# Invariant: total_runs = total_wins + total_fails.
_total_runs = 0
_total_wins = 0
_total_fails = 0

# Timing statistics intentionally describe successful runs only.
_total_run_time = 0.0
_fastest_run = float("inf")
_slowest_run = 0.0

_gemstone_drops: dict[str, dict[int, int]] = {}
_char_names: dict[str, str] = {}

# Session-only statistics.
# Invariant: session_runs = session_wins + session_fails.
_session_runs = 0
_session_wins = 0
_session_fails = 0

_session_gemstone_drops: dict[str, dict[int, int]] = {}
_statistics_reset_pending = False
_scramble_accounts = False

# Active run.
_t_run_start = 0.0
_current_run_time = 0.0
_run_gemstone_snapshot: dict[str, dict[int, int]] = {}

SUMMON_SETTLE_MS = 3_000

# Simple fixed-area defense.
# The run is only validated after the mission objective changes.
# Once that happens, the defended area must remain clean for a short,
# stable window before statistics are recorded and the party resigns.
DEFENSE_INITIAL_WAIT_MS = 10_000
DEFENSE_RADIUS = Range.Spirit.value
POST_OBJECTIVE_STABLE_CLEAR_MS = 10_000

MISSION_OBJECTIVE_BASELINE_TIMEOUT_MS = 15_000
MISSION_OBJECTIVE_CHANGE_TIMEOUT_MS = 15 * 60_000
MISSION_OBJECTIVE_BASELINE_STABLE_MS = 1_000

initialized = False
botting_tree: BottingTree | None = None

_mission_objective_baseline: tuple[tuple[int, int, str], ...] = ()
_run_completion_validated = False
_defense_leash_enabled = False


def ensure_botting_tree() -> BottingTree:
    global botting_tree

    _load_statistics()

    if botting_tree is None:
        Listeners.AutoReturnOnDefeat.Enable()
        botting_tree = BottingTree.Create(
            MODULE_NAME,
            main_routine=get_execution_steps(),
            routine_name="MultiAccountSequence",
            repeat=True,
            multi_account=True,
            isolation_enabled=False,
            configure_fn=_configure_botting_tree,
        )

    return botting_tree


def _make_action_node(
    name: str,
    action_fn: Callable[[BehaviorTree.Node], BehaviorTree.NodeState],
    aftercast_ms: int = 0,
) -> BehaviorTree:
    return BehaviorTree(
        BehaviorTree.ActionNode(
            name=name,
            action_fn=action_fn,
            aftercast_ms=aftercast_ms,
        )
    )


# ============================================================
# Statistics
# ============================================================

def _account_key(email: str) -> str:
    return str(email).replace("@", "_at_").replace(".", "_")


def _display_email(key: str) -> str:
    return str(key).replace("_at_", "@").replace("_", ".")


def _statistics_accounts() -> list[object]:
    try:
        accounts = GLOBAL_CACHE.ShMem.GetAllAccountData(sort_results=False)
    except TypeError:
        accounts = GLOBAL_CACHE.ShMem.GetAllAccountData()
    except Exception:
        accounts = []

    unique: list[object] = []
    seen: set[str] = set()

    for account in accounts or []:
        email = str(getattr(account, "AccountEmail", "") or "").strip()
        if not email or email in seen:
            continue
        seen.add(email)
        unique.append(account)

    return unique


def _refresh_character_names() -> bool:
    changed = False

    local_email = str(Player.GetAccountEmail() or "").strip()
    local_name = str(Player.GetName() or "").strip()

    if local_email and local_name:
        key = _account_key(local_email)
        if _char_names.get(key) != local_name:
            _char_names[key] = local_name
            changed = True

    for account in _statistics_accounts():
        email = str(getattr(account, "AccountEmail", "") or "").strip()
        agent_data = getattr(account, "AgentData", None)
        character_name = str(
            getattr(agent_data, "CharacterName", "") or ""
        ).strip()

        if not email or not character_name:
            continue

        key = _account_key(email)
        if _char_names.get(key) != character_name:
            _char_names[key] = character_name
            changed = True

    return changed


def _known_account_keys() -> list[str]:
    keys = (
        set(_gemstone_drops)
        | set(_session_gemstone_drops)
        | set(_run_gemstone_snapshot)
        | set(_char_names)
    )
    return sorted(key for key in keys if key and key != "local")


def _account_label(key: str) -> str:
    if not _scramble_accounts:
        return _char_names.get(key) or _display_email(key)

    keys = _known_account_keys()
    index = keys.index(key) + 1 if key in keys else 0
    return f"Player {index}" if index > 0 else "Player"


def _ensure_drop_account(
    container: dict[str, dict[int, int]],
    account_key: str,
) -> dict[int, int]:
    account = container.setdefault(account_key, {})
    for model_id in GEMSTONE_MODEL_IDS:
        account.setdefault(int(model_id), 0)
    return account


def _load_statistics() -> None:
    global _statistics_loaded
    global _total_runs, _total_wins, _total_fails
    global _total_run_time, _fastest_run, _slowest_run

    if _statistics_loaded:
        return

    legacy_total_runs = _settings.get_int(_STATS_SECTION, "total_runs", 0)

    # Backward compatibility:
    # before win/fail tracking existed, total_runs contained successful runs.
    _total_wins = _settings.get_int(
        _STATS_SECTION,
        "total_wins",
        legacy_total_runs,
    )
    _total_fails = _settings.get_int(
        _STATS_SECTION,
        "total_fails",
        0,
    )
    _total_runs = max(
        legacy_total_runs,
        _total_wins + _total_fails,
    )

    _total_run_time = _settings.get_float(
        _STATS_SECTION,
        "total_run_time",
        0.0,
    )

    fastest = _settings.get_float(_STATS_SECTION, "fastest_run", 0.0)
    _fastest_run = float("inf") if fastest <= 0.0 else fastest
    _slowest_run = _settings.get_float(
        _STATS_SECTION,
        "slowest_run",
        0.0,
    )

    for model_id in GEMSTONE_MODEL_IDS:
        section = _GEMSTONE_DROP_SECTIONS[int(model_id)]
        for key in _settings.items(section).keys():
            if not key or key == "local":
                continue
            account = _ensure_drop_account(_gemstone_drops, key)
            account[int(model_id)] = _settings.get_int(section, key, 0)

    for key in _settings.items(_CHAR_NAMES_SECTION).keys():
        if not key or key == "local":
            continue
        name = str(
            _settings.get_str(_CHAR_NAMES_SECTION, key, "") or ""
        ).strip()
        if name:
            _char_names[key] = name

    _statistics_loaded = True


def _save_statistics() -> None:
    _settings.set(_STATS_SECTION, "total_runs", _total_runs)
    _settings.set(_STATS_SECTION, "total_wins", _total_wins)
    _settings.set(_STATS_SECTION, "total_fails", _total_fails)
    _settings.set(_STATS_SECTION, "total_run_time", _total_run_time)
    _settings.set(
        _STATS_SECTION,
        "fastest_run",
        0.0 if _fastest_run == float("inf") else _fastest_run,
    )
    _settings.set(_STATS_SECTION, "slowest_run", _slowest_run)

    for account_key, counts in _gemstone_drops.items():
        if not account_key or account_key == "local":
            continue
        for model_id in GEMSTONE_MODEL_IDS:
            section = _GEMSTONE_DROP_SECTIONS[int(model_id)]
            _settings.set(
                section,
                account_key,
                int(counts.get(int(model_id), 0)),
            )

    for key, name in _char_names.items():
        if key and key != "local":
            _settings.set(_CHAR_NAMES_SECTION, key, name)


def _statistics_action_node(
    name: str,
    action: Callable[[], None],
) -> BehaviorTree:
    def _run(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        try:
            action()
        except Exception as exc:
            PySystem.Console.Log(
                MODULE_NAME,
                f"[Statistics] {name} failed: {exc}",
                PySystem.Console.MessageType.Warning,
            )
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name=name,
            action_fn=_run,
            aftercast_ms=0,
        )
    )


def StartRunStatistics() -> BehaviorTree:
    def _start() -> None:
        global _t_run_start, _current_run_time, _run_gemstone_snapshot
        global _mission_objective_baseline, _run_completion_validated

        _load_statistics()
        _refresh_character_names()

        _t_run_start = time.monotonic()
        _current_run_time = 0.0
        _run_gemstone_snapshot = {}
        _mission_objective_baseline = ()
        _run_completion_validated = False

        PySystem.Console.Log(
            MODULE_NAME,
            "[Statistics] Gemstone run timer started.",
            PySystem.Console.MessageType.Info,
        )

    return _statistics_action_node("Start Gemstone Run Statistics", _start)


def _shared_model_count(account: object, model_id: int) -> int | None:
    inventory_bags = getattr(account, "InventoryBags", None)
    if inventory_bags is None:
        return None

    try:
        bags = list(inventory_bags.iter_bags())
    except Exception:
        return None

    if not bags:
        return None

    total = 0
    saw_slots_container = False

    try:
        for bag in bags:
            slots = getattr(bag, "Slots", None)
            if slots is None:
                continue

            saw_slots_container = True

            for slot in slots:
                if int(getattr(slot, "ModelID", 0) or 0) != int(model_id):
                    continue
                total += max(
                    0,
                    int(getattr(slot, "Quantity", 0) or 0),
                )
    except Exception:
        return None

    return total if saw_slots_container else None


def _apply_inventory_capture(
    counts: dict[str, dict[int, int]],
    *,
    after_run: bool,
) -> None:
    global _run_gemstone_snapshot

    if not after_run:
        _run_gemstone_snapshot = {
            account_key: dict(model_counts)
            for account_key, model_counts in counts.items()
        }
        PySystem.Console.Log(
            MODULE_NAME,
            (
                "[Statistics] Gemstone inventory snapshot stored for "
                f"{len(_run_gemstone_snapshot)} account(s)."
            ),
            PySystem.Console.MessageType.Info,
        )
        return

    total_run_drops = 0
    per_model_run = {int(model_id): 0 for model_id in GEMSTONE_MODEL_IDS}

    for account_key, after_counts in counts.items():
        before_counts = _run_gemstone_snapshot.get(account_key)
        if before_counts is None:
            continue

        all_time = _ensure_drop_account(_gemstone_drops, account_key)
        session = _ensure_drop_account(
            _session_gemstone_drops,
            account_key,
        )

        for model_id in GEMSTONE_MODEL_IDS:
            model_id = int(model_id)

            if model_id not in after_counts or model_id not in before_counts:
                continue

            delta = max(
                0,
                int(after_counts[model_id])
                - int(before_counts[model_id]),
            )

            if delta <= 0:
                continue

            all_time[model_id] += delta
            session[model_id] += delta
            per_model_run[model_id] += delta
            total_run_drops += delta

    _save_statistics()

    detail = ", ".join(
        f"{GEMSTONE_NAMES[model_id]}={count}"
        for model_id, count in per_model_run.items()
        if count > 0
    ) or "no gemstones"

    PySystem.Console.Log(
        MODULE_NAME,
        f"[Statistics] Run drops: {total_run_drops} ({detail}).",
        PySystem.Console.MessageType.Success,
    )


def CaptureGemstoneInventory(*, after_run: bool) -> BehaviorTree:
    node_name = (
        "Capture Gemstones After Run"
        if after_run
        else "Snapshot Gemstones Before Run"
    )

    state: dict[str, object] = {
        "started": False,
        "counts": {},
        "pending": {},
        "request_started_at": 0.0,
    }

    def _reset() -> None:
        state["started"] = False
        state["counts"] = {}
        state["pending"] = {}
        state["request_started_at"] = 0.0

    def _store(
        account_key: str,
        model_id: int,
        count: int,
    ) -> None:
        counts: dict[str, dict[int, int]] = state["counts"]
        account = counts.setdefault(account_key, {})
        account[int(model_id)] = max(0, int(count))

    def _start() -> bool:
        _load_statistics()
        _refresh_character_names()

        local_email = str(Player.GetAccountEmail() or "").strip()
        if not local_email:
            return False

        local_key = _account_key(local_email)

        for model_id in GEMSTONE_MODEL_IDS:
            _store(
                local_key,
                int(model_id),
                int(GLOBAL_CACHE.Inventory.GetModelCount(int(model_id))),
            )

        pending: dict[tuple[str, int], tuple[str, int]] = {}
        mirror_reads = 0

        for account in _statistics_accounts():
            email = str(
                getattr(account, "AccountEmail", "") or ""
            ).strip()

            if not email or email == local_email:
                continue

            account_key = _account_key(email)

            for model_id in GEMSTONE_MODEL_IDS:
                model_id = int(model_id)
                mirrored = _shared_model_count(account, model_id)

                if mirrored is not None:
                    _store(account_key, model_id, mirrored)
                    mirror_reads += 1
                    continue

                reset_inventory_count(email, model_id, model_id)

                try:
                    GLOBAL_CACHE.ShMem.SendMessage(
                        local_email,
                        email,
                        SharedCommandType.InventoryQuery,
                        (
                            float(model_id),
                            float(model_id),
                            0.0,
                            0.0,
                        ),
                        ("report_inventory_count",),
                    )
                    pending[(email, model_id)] = (
                        account_key,
                        model_id,
                    )
                except Exception:
                    continue

        state["pending"] = pending
        state["started"] = True
        state["request_started_at"] = (
            time.monotonic() if pending else 0.0
        )

        if pending:
            PySystem.Console.Log(
                MODULE_NAME,
                (
                    "[Statistics] Inventory snapshot: "
                    f"{mirror_reads} mirrored gemstone count(s), "
                    f"{len(pending)} IPC fallback request(s)."
                ),
                PySystem.Console.MessageType.Info,
            )

        return True

    def _tick(node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        try:
            if bool(node.blackboard.get("USER_INTERRUPT_ACTIVE", False)):
                _reset()
                return BehaviorTree.NodeState.FAILURE

            if not bool(state["started"]):
                if not _start():
                    return BehaviorTree.NodeState.RUNNING

            pending: dict[
                tuple[str, int],
                tuple[str, int],
            ] = state["pending"]

            for request_key in list(pending):
                email, model_id = request_key
                account_key, _ = pending[request_key]

                count = int(
                    get_inventory_count(
                        email,
                        int(model_id),
                        int(model_id),
                    )
                )

                if count < 0:
                    continue

                _store(account_key, int(model_id), count)
                pending.pop(request_key, None)

            if pending:
                elapsed_ms = (
                    time.monotonic()
                    - float(state["request_started_at"] or 0.0)
                ) * 1000.0

                if elapsed_ms < _INVENTORY_QUERY_TIMEOUT_MS:
                    return BehaviorTree.NodeState.RUNNING

                for email, model_id in list(pending):
                    PySystem.Console.Log(
                        MODULE_NAME,
                        (
                            "[Statistics] Inventory query timeout: "
                            f"{email}, model={model_id}."
                        ),
                        PySystem.Console.MessageType.Warning,
                    )
                    pending.pop((email, model_id), None)

            counts: dict[str, dict[int, int]] = state["counts"]
            _apply_inventory_capture(counts, after_run=after_run)

            _reset()
            return BehaviorTree.NodeState.SUCCESS

        except Exception as exc:
            PySystem.Console.Log(
                MODULE_NAME,
                f"[Statistics] {node_name} failed: {exc}",
                PySystem.Console.MessageType.Warning,
            )
            _reset()
            return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name=node_name,
            action_fn=_tick,
            aftercast_ms=_INVENTORY_QUERY_POLL_MS,
        )
    )


def RecordFailedRun(reason: str) -> BehaviorTree:
    """Record one failed attempt (wipe) without adding it to successful timings."""

    def _record_fail() -> None:
        global _total_runs, _total_fails
        global _session_runs, _session_fails
        global _t_run_start, _current_run_time, _run_gemstone_snapshot
        global _mission_objective_baseline, _run_completion_validated

        elapsed = (
            max(0.0, time.monotonic() - _t_run_start)
            if _t_run_start > 0.0
            else 0.0
        )

        _total_runs += 1
        _total_fails += 1
        _session_runs += 1
        _session_fails += 1

        _t_run_start = 0.0
        _current_run_time = 0.0
        _run_gemstone_snapshot = {}
        _mission_objective_baseline = ()
        _run_completion_validated = False

        _save_statistics()

        PySystem.Console.Log(
            MODULE_NAME,
            (
                f"[Statistics] Failed run recorded ({reason}); "
                f"elapsed={elapsed:.0f}s, "
                f"session={_session_runs} "
                f"(win={_session_wins}, fail={_session_fails})."
            ),
            PySystem.Console.MessageType.Warning,
        )

    return _statistics_action_node(
        "Record Failed Gemstone Run",
        _record_fail,
    )



def RecordSuccessfulRun() -> BehaviorTree:
    def _record() -> None:
        global _total_runs, _total_wins
        global _session_runs, _session_wins
        global _total_run_time, _fastest_run, _slowest_run
        global _current_run_time, _t_run_start

        now = time.monotonic()

        if _t_run_start > 0.0:
            elapsed = max(0.0, now - _t_run_start)
            _current_run_time = elapsed
            _total_run_time += elapsed
            _fastest_run = min(_fastest_run, elapsed)
            _slowest_run = max(_slowest_run, elapsed)
        else:
            elapsed = 0.0

        _total_runs += 1
        _total_wins += 1
        _session_runs += 1
        _session_wins += 1
        _t_run_start = 0.0

        _save_statistics()

        PySystem.Console.Log(
            MODULE_NAME,
            (
                f"[Statistics] Successful run recorded in {elapsed:.0f}s; "
                f"session={_session_runs} "
                f"(win={_session_wins}, fail={_session_fails})."
            ),
            PySystem.Console.MessageType.Success,
        )

    return _statistics_action_node("Record Successful Run", _record)


def _reset_statistics() -> None:
    global _total_runs, _total_wins, _total_fails
    global _total_run_time
    global _fastest_run, _slowest_run
    global _current_run_time
    global _gemstone_drops

    _total_runs = 0
    _total_wins = 0
    _total_fails = 0
    _total_run_time = 0.0
    _fastest_run = float("inf")
    _slowest_run = 0.0
    _current_run_time = 0.0

    for account_key in list(_gemstone_drops):
        account = _ensure_drop_account(
            _gemstone_drops,
            account_key,
        )
        for model_id in GEMSTONE_MODEL_IDS:
            account[int(model_id)] = 0

    _save_statistics()

    PySystem.Console.Log(
        MODULE_NAME,
        "[Statistics] All-time statistics reset.",
        PySystem.Console.MessageType.Success,
    )


def _sum_drop_container(
    container: dict[str, dict[int, int]],
) -> int:
    return sum(
        int(count)
        for account in container.values()
        for count in account.values()
    )


def _model_total(
    container: dict[str, dict[int, int]],
    model_id: int,
) -> int:
    return sum(
        int(account.get(int(model_id), 0))
        for account in container.values()
    )


def _account_total(
    container: dict[str, dict[int, int]],
    account_key: str,
) -> int:
    return sum(
        int(container.get(account_key, {}).get(int(model_id), 0))
        for model_id in GEMSTONE_MODEL_IDS
    )


def _draw_statistics() -> None:
    from Py4GWCoreLib import Color

    global _statistics_reset_pending, _scramble_accounts

    _load_statistics()

    if _refresh_character_names():
        _save_statistics()

    gold = Color(255, 210, 80, 255).to_tuple_normalized()
    cyan = Color(80, 210, 255, 255).to_tuple_normalized()
    live = Color(100, 180, 255, 255).to_tuple_normalized()

    def _fmt_time(seconds: float) -> str:
        if seconds <= 0.0 or seconds == float("inf"):
            return "--:--"
        minutes, remaining = divmod(int(seconds), 60)
        return f"{minutes:02d}:{remaining:02d}"

    def _avg_time() -> str:
        # Timing statistics are based on successful runs only.
        if _total_wins <= 0:
            return "--:--"
        return _fmt_time(_total_run_time / _total_wins)

    def _gems_per_run(count: int, runs: int) -> str:
        if runs <= 0:
            return "-"
        return f"{float(count) / float(runs):.2f}"

    def _drop_rate(count: int, runs: int) -> str:
        """Gemstone count divided by total attempts."""
        if runs <= 0:
            return "-"
        return f"{float(count) / float(runs) * 100.0:.1f}%"

    def _win_rate(wins: int, runs: int) -> str:
        if runs <= 0:
            return "-"
        return f"{float(wins) / float(runs) * 100.0:.1f}%"

    table_flags = (
        PyImGui.TableFlags.Borders
        | PyImGui.TableFlags.RowBg
        | PyImGui.TableFlags.SizingFixedFit
        | PyImGui.TableFlags.NoHostExtendX
    )

    header_color = 26 | (38 << 8) | (51 << 16) | (255 << 24)
    row_height = 22.0

    def _header_row(labels: tuple[str, ...]) -> None:
        PyImGui.table_next_row(0, row_height)
        PyImGui.table_set_bg_color(2, header_color, -1)

        for index, label in enumerate(labels):
            PyImGui.table_set_column_index(index)
            PyImGui.text(label)

    session_gems = _sum_drop_container(_session_gemstone_drops)
    total_gems = _sum_drop_container(_gemstone_drops)

    PyImGui.text_colored("Farm Gemstones Redux Statistics", gold)
    PyImGui.separator()
    PyImGui.spacing()

    _scramble_accounts = PyImGui.checkbox(
        "Hide Account Names",
        _scramble_accounts,
    )

    PyImGui.text_colored("Session Overview", cyan)

    if PyImGui.begin_table(
        "##gemstones_session_overview",
        5,
        table_flags,
    ):
        for label, width in (
            ("Total", 72.0),
            ("Win", 72.0),
            ("Fail", 72.0),
            ("Win Rate", 82.0),
            ("Gemstones", 90.0),
        ):
            PyImGui.table_setup_column(
                label,
                PyImGui.TableColumnFlags.WidthFixed,
                width,
            )

        _header_row(("Total", "Win", "Fail", "Win Rate", "Gemstones"))

        values = (
            _session_runs,
            _session_wins,
            _session_fails,
            _win_rate(_session_wins, _session_runs),
            session_gems,
        )

        PyImGui.table_next_row(0, row_height)

        for index, value in enumerate(values):
            PyImGui.table_set_column_index(index)
            PyImGui.text(str(value))

        PyImGui.end_table()

    PyImGui.spacing()
    PyImGui.text_colored("Total Overview", cyan)

    if PyImGui.begin_table(
        "##gemstones_total_overview",
        5,
        table_flags,
    ):
        for label, width in (
            ("Total", 72.0),
            ("Win", 72.0),
            ("Fail", 72.0),
            ("Win Rate", 82.0),
            ("Gemstones", 90.0),
        ):
            PyImGui.table_setup_column(
                label,
                PyImGui.TableColumnFlags.WidthFixed,
                width,
            )

        _header_row(("Total", "Win", "Fail", "Win Rate", "Gemstones"))

        values = (
            _total_runs,
            _total_wins,
            _total_fails,
            _win_rate(_total_wins, _total_runs),
            total_gems,
        )

        PyImGui.table_next_row(0, row_height)

        for index, value in enumerate(values):
            PyImGui.table_set_column_index(index)
            PyImGui.text(str(value))

        PyImGui.end_table()

    PyImGui.spacing()
    PyImGui.text_colored("Run Timing", cyan)

    if PyImGui.begin_table(
        "##gemstones_run_timing",
        4,
        table_flags,
    ):
        for label in ("Current", "Average", "Best", "Worst"):
            PyImGui.table_setup_column(
                label,
                PyImGui.TableColumnFlags.WidthFixed,
                92.0,
            )

        _header_row(("Current", "Avg Win", "Best Win", "Worst Win"))

        live_time = (
            time.monotonic() - _t_run_start
            if _t_run_start > 0.0
            else _current_run_time
        )

        PyImGui.table_next_row(0, row_height)

        PyImGui.table_set_column_index(0)
        if _t_run_start > 0.0:
            PyImGui.text_colored(_fmt_time(live_time), live)
        else:
            PyImGui.text(_fmt_time(live_time))

        PyImGui.table_set_column_index(1)
        PyImGui.text(_avg_time())

        PyImGui.table_set_column_index(2)
        PyImGui.text(_fmt_time(_fastest_run))

        PyImGui.table_set_column_index(3)
        PyImGui.text(_fmt_time(_slowest_run))

        PyImGui.end_table()

    PyImGui.spacing()
    PyImGui.text_colored("Gemstones By Type", cyan)

    if PyImGui.begin_table(
        "##gemstones_by_type",
        4,
        table_flags,
    ):
        PyImGui.table_setup_column(
            "Gemstone",
            PyImGui.TableColumnFlags.WidthStretch,
        )

        for label in ("Session", "All Time", "Drop Rate"):
            PyImGui.table_setup_column(
                label,
                PyImGui.TableColumnFlags.WidthFixed,
                90.0,
            )

        _header_row(("Gemstone", "Session", "All Time", "Drop Rate"))

        for model_id in GEMSTONE_MODEL_IDS:
            model_id = int(model_id)
            session_count = _model_total(
                _session_gemstone_drops,
                model_id,
            )
            all_time_count = _model_total(
                _gemstone_drops,
                model_id,
            )

            PyImGui.table_next_row(0, row_height)
            PyImGui.table_set_column_index(0)
            PyImGui.text(GEMSTONE_NAMES[model_id])
            PyImGui.table_set_column_index(1)
            PyImGui.text(str(session_count))
            PyImGui.table_set_column_index(2)
            PyImGui.text(str(all_time_count))
            PyImGui.table_set_column_index(3)
            PyImGui.text(
                _drop_rate(all_time_count, _total_runs)
            )

        PyImGui.end_table()

    PyImGui.spacing()
    PyImGui.text_colored("Drop Rate By Account", cyan)
    PyImGui.text(
        "Rate = gemstone count / total runs "
        f"({_total_runs})"
    )

    if PyImGui.begin_table(
        "##gemstones_drop_rate_by_account",
        6,
        table_flags,
    ):
        PyImGui.table_setup_column(
            "Account",
            PyImGui.TableColumnFlags.WidthStretch,
        )

        for label in (
            "Margonite",
            "Stygian",
            "Titan",
            "Torment",
        ):
            PyImGui.table_setup_column(
                label,
                PyImGui.TableColumnFlags.WidthFixed,
                105.0,
            )

        PyImGui.table_setup_column(
            "Total",
            PyImGui.TableColumnFlags.WidthFixed,
            95.0,
        )

        _header_row(
            (
                "Account",
                "Margonite",
                "Stygian",
                "Titan",
                "Torment",
                "Total",
            )
        )

        for key in _known_account_keys():
            account_counts = _gemstone_drops.get(key, {})

            PyImGui.table_next_row(0, row_height)

            PyImGui.table_set_column_index(0)
            PyImGui.text(_account_label(key))

            for column_index, model_id in enumerate(
                GEMSTONE_MODEL_IDS,
                start=1,
            ):
                count = int(account_counts.get(int(model_id), 0))

                PyImGui.table_set_column_index(column_index)
                PyImGui.text(
                    f"{count} ({_drop_rate(count, _total_runs)})"
                )

            total_count = _account_total(_gemstone_drops, key)

            PyImGui.table_set_column_index(5)
            PyImGui.text(
                f"{total_count} "
                f"({_gems_per_run(total_count, _total_runs)}/run)"
            )

        PyImGui.end_table()

    PyImGui.spacing()

    if not _statistics_reset_pending:
        if PyImGui.button("Reset All-Time Statistics"):
            _statistics_reset_pending = True
    else:
        PyImGui.text_colored(
            "Reset all-time runs (win/fail), timings and gemstone drops?",
            gold,
        )

        if PyImGui.button("Confirm Reset"):
            _reset_statistics()
            _statistics_reset_pending = False

        PyImGui.same_line(0.0, 8.0)

        if PyImGui.button("Cancel"):
            _statistics_reset_pending = False


# ============================================================
# Native BT custom leaves
# ============================================================

def MarkRunStart() -> BehaviorTree:
    def _tick(node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        node.blackboard["gemstones_last_result"] = "starting"
        ConsoleLog(MODULE_NAME, "[Gemstone] Run started")
        return BehaviorTree.NodeState.SUCCESS

    return _make_action_node("Mark Run Start", _tick)


def ConfigureGemstoneLootAllAccounts() -> BehaviorTree:
    """Whitelist all four DoA gemstones on every active multibox account."""
    children: list[BehaviorTree | BehaviorTree.Node] = []

    for model_id in GEMSTONE_MODEL_IDS:
        children.append(
            RoutinesBT.Shared.SendAndWait(
                command=SharedCommandType.AddModelToLootWhitelist,
                params=(float(model_id), 0.0, 0.0, 0.0),
                include_self=True,
                refs_blackboard_key=f"gemstones_loot_{model_id}_refs",
                timeout_ms=5_000,
                log=True,
            )
        )

    return BT.Sequence(
        name="Whitelist Gemstones On All Accounts",
        children=children,
    )


def _shared_accounts() -> list[object]:
    """Forsaken-style shared-memory account discovery."""
    try:
        accounts = GLOBAL_CACHE.ShMem.GetAllAccountData(sort_results=False)
    except TypeError:
        accounts = GLOBAL_CACHE.ShMem.GetAllAccountData()
    except Exception:
        accounts = []

    unique: list[object] = []
    seen: set[str] = set()

    for account in accounts or []:
        email = str(getattr(account, "AccountEmail", "") or "").strip()
        if not email or email in seen:
            continue
        seen.add(email)
        unique.append(account)

    return unique


def _shared_account_label(account: object) -> str:
    agent_data = getattr(account, "AgentData", None)
    character_name = str(getattr(agent_data, "CharacterName", "") or "").strip()
    return character_name or str(
        getattr(account, "AccountEmail", "") or "Unknown account"
    )


def _summoning_target_accounts() -> list[tuple[str, str]]:
    """Return the same account set used by the proven Forsaken multibox flow."""
    targets: list[tuple[str, str]] = []
    seen: set[str] = set()

    for account in _shared_accounts():
        email = str(getattr(account, "AccountEmail", "") or "").strip()
        if email and email not in seen:
            seen.add(email)
            targets.append((email, _shared_account_label(account)))

    local_email = str(Player.GetAccountEmail() or "").strip()
    if local_email and local_email not in seen:
        targets.append((local_email, str(Player.GetName() or local_email)))

    return targets


def _summoning_recipient_emails() -> list[str]:
    return [email for email, _label in _summoning_target_accounts()]


def UseAvailableSummoningStone() -> BehaviorTree:
    """Broadcast the native UseSummoningStone command like Forsaken BT."""

    def _dispatch(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        sender_email = str(Player.GetAccountEmail() or "").strip()
        recipients = _summoning_recipient_emails()

        if not sender_email or not recipients:
            return BehaviorTree.NodeState.SUCCESS

        for receiver_email in recipients:
            try:
                GLOBAL_CACHE.ShMem.SendMessage(
                    sender_email,
                    receiver_email,
                    SharedCommandType.UseSummoningStone,
                    (0.0, 0.0, 0.0, 0.0),
                    ("", "", "", ""),
                )
            except Exception:
                continue

        ConsoleLog(
            MODULE_NAME,
            f"[Summoning] Request sent to {len(recipients)} account(s).",
        )
        return BehaviorTree.NodeState.SUCCESS

    return BT.Sequence(
        name="Use Available Summoning Stone",
        children=[
            _make_action_node(
                "Use Summoning Stone (Multibox Non Blocking)",
                _dispatch,
            ),
            BT.Wait(SUMMON_SETTLE_MS),
        ],
    )


def SummoningStoneRecoveryService() -> BehaviorTree:
    """Replace a lost summon during the defense using the Forsaken pattern."""

    ATTEMPT_INTERVAL_MS = 3_000.0
    RETRY_CYCLE_DELAY_MS = 15_000.0

    state: dict[str, object] = {
        "map_id": 0,
        "saw_active_summon": False,
        "recovering": False,
        "targets": [],
        "target_index": 0,
        "next_attempt_ms": 0.0,
    }

    def _reset_for_map(map_id: int) -> None:
        state["map_id"] = int(map_id)
        state["saw_active_summon"] = False
        state["recovering"] = False
        state["targets"] = []
        state["target_index"] = 0
        state["next_attempt_ms"] = 0.0

    def _refresh_targets() -> list[tuple[str, str]]:
        targets: list[tuple[str, str]] = []
        seen: set[str] = set()

        for email, label in _summoning_target_accounts():
            email = str(email or "").strip()
            if not email or email in seen:
                continue
            seen.add(email)
            targets.append((email, str(label or email)))

        state["targets"] = targets
        return targets

    def _tick(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        if not Map.IsMapReady() or Map.IsMapLoading() or not Map.IsExplorable():
            return BehaviorTree.NodeState.RUNNING

        map_id = int(Map.GetMapID() or 0)
        if map_id != MISSION_MAP:
            if map_id != int(state["map_id"] or 0):
                _reset_for_map(map_id)
            return BehaviorTree.NodeState.RUNNING

        if map_id != int(state["map_id"] or 0):
            _reset_for_map(map_id)
            return BehaviorTree.NodeState.RUNNING

        player_id = int(Player.GetAgentID() or 0)
        if player_id <= 0 or not Agent.IsValid(player_id) or Agent.IsDead(player_id):
            return BehaviorTree.NodeState.RUNNING

        if Routines.Checks.Party.IsPartyWiped():
            return BehaviorTree.NodeState.RUNNING

        try:
            summon_alive = bool(
                has_active_party_summon(GLOBAL_CACHE.Party.GetOthers())
            )
        except Exception:
            summon_alive = False

        if summon_alive:
            if bool(state["recovering"]):
                ConsoleLog(
                    MODULE_NAME,
                    "[Summoning] Replacement summon detected; recovery stopped.",
                )

            state["saw_active_summon"] = True
            state["recovering"] = False
            state["targets"] = []
            state["target_index"] = 0
            state["next_attempt_ms"] = 0.0
            return BehaviorTree.NodeState.RUNNING

        # Do not invent a replacement if no successful summon has ever
        # been observed on this mission instance.
        if not bool(state["saw_active_summon"]):
            return BehaviorTree.NodeState.RUNNING

        now_ms = time.monotonic() * 1000.0

        if not bool(state["recovering"]):
            state["recovering"] = True
            state["target_index"] = 0
            state["next_attempt_ms"] = now_ms
            _refresh_targets()
            ConsoleLog(
                MODULE_NAME,
                "[Summoning] Active summon lost; trying replacement stones.",
            )

        if now_ms < float(state["next_attempt_ms"] or 0.0):
            return BehaviorTree.NodeState.RUNNING

        targets: list[tuple[str, str]] = list(state["targets"] or [])
        if not targets:
            targets = _refresh_targets()
            if not targets:
                state["next_attempt_ms"] = now_ms + RETRY_CYCLE_DELAY_MS
                return BehaviorTree.NodeState.RUNNING

        target_index = int(state["target_index"] or 0)

        if target_index >= len(targets):
            state["target_index"] = 0
            state["targets"] = _refresh_targets()
            state["next_attempt_ms"] = now_ms + RETRY_CYCLE_DELAY_MS
            return BehaviorTree.NodeState.RUNNING

        sender_email = str(Player.GetAccountEmail() or "").strip()
        if not sender_email:
            state["next_attempt_ms"] = now_ms + ATTEMPT_INTERVAL_MS
            return BehaviorTree.NodeState.RUNNING

        receiver_email, label = targets[target_index]
        state["target_index"] = target_index + 1
        state["next_attempt_ms"] = now_ms + ATTEMPT_INTERVAL_MS

        try:
            GLOBAL_CACHE.ShMem.SendMessage(
                sender_email,
                receiver_email,
                SharedCommandType.UseSummoningStone,
                (0.0, 0.0, 0.0, 0.0),
            )
            ConsoleLog(
                MODULE_NAME,
                f"[Summoning] Asking {label} to try a replacement stone.",
            )
        except Exception as exc:
            ConsoleLog(
                MODULE_NAME,
                f"[Summoning] Replacement request failed for {label}: {exc}",
                PySystem.Console.MessageType.Warning,
            )

        return BehaviorTree.NodeState.RUNNING

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name="Summoning Stone Recovery Service",
            action_fn=_tick,
            aftercast_ms=500,
        )
    )


def SetDefenseLeashEnabled(enabled: bool) -> BehaviorTree:
    """Enable/disable the defense leash used only during Defend Zhellix."""
    def _set(node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        global _defense_leash_enabled
        _defense_leash_enabled = bool(enabled)

        # Never leave local headless combat disabled when the leash is turned off.
        if not enabled:
            node.blackboard["DEFENSE_LEASH_RETURNING"] = False
            node.blackboard["combat_enabled_request"] = True

        return BehaviorTree.NodeState.SUCCESS

    return _make_action_node(
        "Enable Defense Leash" if enabled else "Disable Defense Leash",
        _set,
    )


def DefenseLeashService() -> BehaviorTree:
    """
    Keep the leader around FIGHT_POSITION while Defend Zhellix is active.

    Priority rule:
      - inside DEFENSE_LEASH_MAX_DISTANCE: combat owns movement;
      - outside it: the leash temporarily disables LOCAL headless combat,
        clears the current target and owns movement back to FIGHT_POSITION;
      - once inside DEFENSE_LEASH_RELEASE_DISTANCE: combat is re-enabled.

    Only the local leader's BottingTree combat engine is paused. Followers/heroes
    continue fighting normally on their own clients / HeroAI.
    """
    state: dict[str, float | bool] = {
        "returning": False,
        "last_move_at": 0.0,
    }

    def _reset(node: BehaviorTree.Node, *, restore_combat: bool) -> None:
        if restore_combat and bool(state["returning"]):
            node.blackboard["combat_enabled_request"] = True
        node.blackboard["DEFENSE_LEASH_RETURNING"] = False
        state["returning"] = False
        state["last_move_at"] = 0.0

    def _tick(node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        if not _defense_leash_enabled:
            _reset(node, restore_combat=True)
            return BehaviorTree.NodeState.RUNNING

        if (
            not Map.IsMapReady()
            or Map.IsMapLoading()
            or int(Map.GetMapID() or 0) != MISSION_MAP
        ):
            _reset(node, restore_combat=True)
            return BehaviorTree.NodeState.RUNNING

        if bool(node.blackboard.get("USER_INTERRUPT_ACTIVE", False)):
            return BehaviorTree.NodeState.RUNNING

        player_id = int(Player.GetAgentID() or 0)
        if player_id <= 0 or not Agent.IsValid(player_id) or Agent.IsDead(player_id):
            return BehaviorTree.NodeState.RUNNING

        if Routines.Checks.Party.IsPartyWiped():
            return BehaviorTree.NodeState.RUNNING

        try:
            player_x, player_y = Player.GetXY()
        except Exception:
            return BehaviorTree.NodeState.RUNNING

        dx = float(player_x) - float(FIGHT_POSITION[0])
        dy = float(player_y) - float(FIGHT_POSITION[1])
        distance_sq = dx * dx + dy * dy

        max_sq = DEFENSE_LEASH_MAX_DISTANCE * DEFENSE_LEASH_MAX_DISTANCE
        release_sq = DEFENSE_LEASH_RELEASE_DISTANCE * DEFENSE_LEASH_RELEASE_DISTANCE

        if not bool(state["returning"]):
            if distance_sq <= max_sq:
                node.blackboard["DEFENSE_LEASH_RETURNING"] = False
                return BehaviorTree.NodeState.RUNNING

            state["returning"] = True
            state["last_move_at"] = 0.0
            node.blackboard["DEFENSE_LEASH_RETURNING"] = True

            # Critical part: stop the local combat engine before returning.
            # This is consumed by BottingTree's HeroAI service on the next tick.
            node.blackboard["combat_enabled_request"] = False

            # Break any existing Interact/auto-attack chase immediately.
            Player.ChangeTarget(0)

            ConsoleLog(
                MODULE_NAME,
                (
                    "[Gemstone] Defense leash triggered "
                    f"(>{DEFENSE_LEASH_MAX_DISTANCE:.0f}); local combat paused."
                ),
            )

        if distance_sq <= release_sq:
            state["returning"] = False
            state["last_move_at"] = 0.0
            node.blackboard["DEFENSE_LEASH_RETURNING"] = False
            node.blackboard["combat_enabled_request"] = True

            ConsoleLog(
                MODULE_NAME,
                "[Gemstone] Defense position restored; local combat resumed.",
            )
            return BehaviorTree.NodeState.RUNNING

        # Keep combat disabled for the whole return transaction.
        node.blackboard["DEFENSE_LEASH_RETURNING"] = True
        node.blackboard["combat_enabled_request"] = False

        # Let the current cast finish, then take movement ownership.
        if Routines.Checks.Player.IsCasting():
            return BehaviorTree.NodeState.RUNNING

        now_ms = time.monotonic() * 1000.0
        if now_ms - float(state["last_move_at"] or 0.0) < DEFENSE_LEASH_REISSUE_MS:
            return BehaviorTree.NodeState.RUNNING

        # Clear any target that another routine may have assigned this frame,
        # then issue the last movement command of the tick toward the center.
        Player.ChangeTarget(0)
        Player.Move(
            float(FIGHT_POSITION[0]),
            float(FIGHT_POSITION[1]),
        )
        state["last_move_at"] = now_ms

        return BehaviorTree.NodeState.RUNNING

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name="Defense Leash Service",
            action_fn=_tick,
            aftercast_ms=100,
        )
    )


def WaitForClearEnemiesInAreaLeashAware() -> BehaviorTree:
    """Run the final active cleanup, but never issue enemy-chase orders while the leash owns movement."""
    clear_tree = BT.WaitForClearEnemiesInArea(
        *FIGHT_POSITION,
        stable_clear_ms=POST_OBJECTIVE_STABLE_CLEAR_MS,
        radius=DEFENSE_RADIUS,
        log=True,
        keep_player_near_center=False,
    )

    def _tick(node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        if bool(node.blackboard.get("DEFENSE_LEASH_RETURNING", False)):
            return BehaviorTree.NodeState.RUNNING

        clear_tree.blackboard = node.blackboard
        result = BehaviorTree.Node._normalize_state(clear_tree.tick())
        if result is None:
            raise TypeError("Leash-aware clear-area tree returned a non-NodeState result.")
        return result

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name="Leash Aware Final Area Cleanup",
            action_fn=_tick,
            aftercast_ms=100,
        )
    )


# ============================================================
# Mission objective completion / wipe handling
# ============================================================

def _mission_objective_signature() -> tuple[tuple[int, int, str], ...]:
    """Return a stable snapshot of the currently exposed mission objectives."""
    try:
        world = GWContext.World.GetContext()
        objectives = (
            list(world.mission_objectives or [])
            if world is not None
            else []
        )
    except Exception:
        return ()

    signature: list[tuple[int, int, str]] = []

    for objective in objectives:
        try:
            signature.append(
                (
                    int(getattr(objective, "objective_id", 0) or 0),
                    int(getattr(objective, "type", 0) or 0),
                    str(getattr(objective, "enc_str", "") or ""),
                )
            )
        except Exception:
            continue

    # Avoid treating a harmless list-order change as objective progression.
    return tuple(sorted(signature))


def CaptureMissionObjectiveBaseline() -> BehaviorTree:
    """Capture a non-empty objective snapshot once it has been stable for 1s."""
    state: dict[str, object] = {
        "started_at": 0.0,
        "last_signature": (),
        "stable_since": 0.0,
    }

    def _reset() -> None:
        state["started_at"] = 0.0
        state["last_signature"] = ()
        state["stable_since"] = 0.0

    def _tick(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        global _mission_objective_baseline

        now = time.monotonic()

        if int(Map.GetMapID() or 0) != MISSION_MAP:
            _reset()
            return BehaviorTree.NodeState.FAILURE

        if float(state["started_at"] or 0.0) <= 0.0:
            state["started_at"] = now

        signature = _mission_objective_signature()

        if signature:
            if signature != state["last_signature"]:
                state["last_signature"] = signature
                state["stable_since"] = now
            elif (
                float(state["stable_since"] or 0.0) > 0.0
                and (now - float(state["stable_since"])) * 1000.0
                >= MISSION_OBJECTIVE_BASELINE_STABLE_MS
            ):
                _mission_objective_baseline = signature

                ConsoleLog(
                    MODULE_NAME,
                    (
                        "[Gemstone] Mission objective baseline captured "
                        f"({len(signature)} objective(s))."
                    ),
                )

                _reset()
                return BehaviorTree.NodeState.SUCCESS

        elapsed_ms = (
            now - float(state["started_at"] or now)
        ) * 1000.0

        if elapsed_ms >= MISSION_OBJECTIVE_BASELINE_TIMEOUT_MS:
            ConsoleLog(
                MODULE_NAME,
                (
                    "[Gemstone] Unable to capture a stable mission objective "
                    "baseline; run validation aborted."
                ),
                PySystem.Console.MessageType.Warning,
            )
            _reset()
            return BehaviorTree.NodeState.FAILURE

        return BehaviorTree.NodeState.RUNNING

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name="Capture Mission Objective Baseline",
            action_fn=_tick,
            aftercast_ms=100,
        )
    )


def WaitForMissionObjectiveChangeOrWipe() -> BehaviorTree:
    """
    Validate wave completion from the mission objective.

    If AutoReturnOnDefeat has already returned the party to Gate of Anguish,
    return SUCCESS as an aborted path; FinishRun will detect that the objective
    was not validated and will not record statistics.
    """
    state: dict[str, float] = {"started_at": 0.0}

    def _reset() -> None:
        state["started_at"] = 0.0

    def _tick(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        global _mission_objective_baseline, _run_completion_validated

        now = time.monotonic()
        current_map = int(Map.GetMapID() or 0)

        if current_map == GATE_OF_ANGUISH_OUTPOST:
            _run_completion_validated = False
            ConsoleLog(
                MODULE_NAME,
                (
                    "[Gemstone] Party returned to Gate of Anguish before "
                    "objective completion; treating run as a wipe/abort."
                ),
                PySystem.Console.MessageType.Warning,
            )
            _reset()
            return BehaviorTree.NodeState.SUCCESS

        if current_map != MISSION_MAP:
            return BehaviorTree.NodeState.RUNNING

        if not _mission_objective_baseline:
            ConsoleLog(
                MODULE_NAME,
                "[Gemstone] Missing mission objective baseline.",
                PySystem.Console.MessageType.Warning,
            )
            _reset()
            return BehaviorTree.NodeState.FAILURE

        if float(state["started_at"] or 0.0) <= 0.0:
            state["started_at"] = now

        current_signature = _mission_objective_signature()

        if (
            current_signature
            and current_signature != _mission_objective_baseline
        ):
            _run_completion_validated = True

            ConsoleLog(
                MODULE_NAME,
                (
                    "[Gemstone] Mission objective changed: "
                    "19-wave defense completion validated."
                ),
            )

            _reset()
            return BehaviorTree.NodeState.SUCCESS

        elapsed_ms = (
            now - float(state["started_at"] or now)
        ) * 1000.0

        if elapsed_ms >= MISSION_OBJECTIVE_CHANGE_TIMEOUT_MS:
            ConsoleLog(
                MODULE_NAME,
                (
                    "[Gemstone] Mission objective did not change before timeout; "
                    "run will not be counted as successful."
                ),
                PySystem.Console.MessageType.Warning,
            )
            _reset()
            return BehaviorTree.NodeState.FAILURE

        return BehaviorTree.NodeState.RUNNING

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name="Wait For Mission Objective Change",
            action_fn=_tick,
            aftercast_ms=100,
        )
    )


def WipeReturnDetected() -> BehaviorTree:
    """Succeed only after an aborted run has returned to the outpost."""

    def _check(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        global _run_completion_validated

        if int(Map.GetMapID() or 0) != GATE_OF_ANGUISH_OUTPOST:
            return BehaviorTree.NodeState.FAILURE

        _run_completion_validated = False
        ConsoleLog(
            MODULE_NAME,
            "[Gemstone] Wipe return detected: leaving Defend Zhellix.",
            PySystem.Console.MessageType.Warning,
        )
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ConditionNode(
            name="Wipe Return Detected",
            condition_fn=_check,
        )
    )


# ============================================================
# Simple fixed-area defense
# ============================================================

def DefendZhellix() -> BehaviorTree:
    """
    Fixed-area defense with mission-objective validation, wipe handling and a
    hard leash around FIGHT_POSITION.

    When the leader crosses the outer leash radius, local BottingTree combat is
    paused so it cannot keep issuing Interact/attack movement orders against the
    return movement. Combat is restored once the leader reaches the inner radius.
    """
    wipe_path = BT.Sequence(
        name="Wipe Return - Disable Defense Leash",
        children=[
            WipeReturnDetected(),
            SetDefenseLeashEnabled(False),
        ],
    )

    normal_defense = BT.Sequence(
        name="Normal Zhellix Defense",
        children=[
            SetDefenseLeashEnabled(True),
            BT.Wait(DEFENSE_INITIAL_WAIT_MS),
            CaptureMissionObjectiveBaseline(),
            WaitForMissionObjectiveChangeOrWipe(),
            BT.Sequence(
                name="Post Objective Area Cleanup",
                children=[
                    WaitForClearEnemiesInAreaLeashAware(),
                ],
            ),
            SetDefenseLeashEnabled(False),
        ],
    )

    return BehaviorTree(
        BehaviorTree.ChoiceNode(
            name="Defend Zhellix - Wipe Aware",
            children=[
                wipe_path,
                normal_defense,
            ],
        )
    )


def ResignIfStillInMission() -> BehaviorTree:
    def _choose(_node: BehaviorTree.Node) -> BehaviorTree:
        try:
            if int(Map.GetMapID()) == MISSION_MAP:
                return BT.Resign(
                    wait_for_map_load=True,
                    target_map_id=GATE_OF_ANGUISH_OUTPOST,
                    multi_account=True,
                    timeout_ms=30_000,
                    log=True,
                )
        except Exception:
            pass

        return BT.Succeeder(name="Skip Resign - Already Outpost")

    return BT.Subtree("Resign If Still In Mission", subtree_fn=_choose)


# ============================================================
# Planner
# ============================================================

def _aggressive_multibox_mode() -> BehaviorTree:
    """Match Oola's Lab BT multibox HeroAI/follow/combat initialization."""
    bot = ensure_botting_tree()
    return bot.Config.Aggressive(
        multi_account=True,
        auto_loot=True,
        resurrection_scroll=True,
        account_isolation=False,
    )


def InitializeBot() -> BehaviorTree:
    return BT.Sequence(
        name="Initialize Bot",
        children=[
            _aggressive_multibox_mode(),
            BT.SetPlayerStatus(PlayerStatus.Offline, log=True),
            BT.LogMessage(
                message=f"{MODULE_NAME} initialized in multibox aggressive mode.",
                module_name=MODULE_NAME,
            ),
        ],
    )


def PrepareRun() -> BehaviorTree:
    """Forsaken-style party preparation with resume support."""
    already_inside = BT.IsCurrentMap(map_id=MISSION_MAP, log=False)

    prepare = BT.Sequence(
        name="Prepare Gemstone Run",
        map_id_or_name=GATE_OF_ANGUISH_OUTPOST,
        children=[
            BT.CreateParty(
                hero_ids=list(GEMSTONE_HERO_IDS),
                multibox_invite=True,
                timeout_ms=30_000,
                log=True,
            ),
        ],
    )

    return BT.Selector(
        name="Prepare Gemstone Run Or Resume",
        children=[
            already_inside,
            prepare,
        ],
    )


def EnterMission() -> BehaviorTree:
    """Enter the mission once; restarting inside the mission safely skips entry."""
    return BT.Selector(
        name="Enter Gemstone Mission Or Resume",
        children=[
            BT.IsCurrentMap(map_id=MISSION_MAP, log=False),
            BT.Sequence(
                name="Enter Gemstone Mission",
                children=[
                    MarkRunStart(),
                    BT.MoveAndDialog(
                        ENTRY_PRIEST_COORDS,
                        ENTRY_DIALOG_ID,
                        multi_account=False,
                    ),
                    BT.WaitForMapLoad(
                        map_id=MISSION_MAP,
                        timeout_ms=30_000,
                    ),
                ],
            ),
        ],
    )


def SetupDefense() -> BehaviorTree:
    """Move to the defended island position, flag heroes and summon."""
    return BT.Sequence(
        name="Setup Zhellix Defense",
        children=[
            # Re-assert multibox HeroAI here as well so planner resume/start-at
            # on Setup Defense still wakes followers before the leader moves.
            _aggressive_multibox_mode(),
            StartRunStatistics(),
            CaptureGemstoneInventory(after_run=False),
            ConfigureGemstoneLootAllAccounts(),
            BT.Move(
                Vec2f(*FIGHT_POSITION),
            ),
            UseAvailableSummoningStone(),
        ],
    )


def FinishRun() -> BehaviorTree:
    """Record stats only when the mission objective validated the run."""

    def _build(_node: BehaviorTree.Node) -> BehaviorTree:
        current_map = int(Map.GetMapID() or 0)

        if _run_completion_validated and current_map == MISSION_MAP:
            return BT.Sequence(
                name="Finish Successful Gemstone Run",
                children=[
                    BT.Move([Vec2f(-5542, -6113), Vec2f(-1894, -6482), Vec2f(-3260, -4952)]),
                    BT.Wait(2_000),
                    CaptureGemstoneInventory(after_run=True),
                    RecordSuccessfulRun(),
                    ResignIfStillInMission(),
                ],
            )

        return BT.Sequence(
            name="Finish Failed Gemstone Run",
            children=[
                # Gemstones already looted before the wipe still belong to this
                # attempt and must contribute to drop rates based on total runs.
                CaptureGemstoneInventory(after_run=True),
                RecordFailedRun("party wipe / return to outpost"),
                RoutinesBT.Party.UnflagAllHeroes(log=True),
                BT.LogMessage(
                    message=(
                        "Gemstone run recorded as FAIL after party wipe; "
                        "any gemstones looted before the wipe were preserved "
                        "in drop statistics."
                    ),
                    module_name=MODULE_NAME,
                ),
            ],
        )

    return BT.Subtree(
        name="Finish Gemstone Run",
        subtree_fn=_build,
    )


def _configure_botting_tree(tree: BottingTree) -> None:
    """Forsaken-style centralized BottingTree upkeep configuration."""
    tree.Config.ConfigureUpkeep(
        # Loot stays OFF during the defense. FinishRun enables it only for the
        # final pickup sweep around the arena.
        looting_enabled=True,
        resurrection_scroll=True,
        auto_inventory_handler_enabled=False,
        enable_party_wipe_recovery=False,
        enable_nearest_shrine_recovery=False,
        heroai_state_logging=False,
    )
    tree.AddServiceTree(
        "SummoningStoneRecoveryService",
        SummoningStoneRecoveryService,
    )
    tree.AddServiceTree(
        "DefenseLeashService",
        DefenseLeashService,
    )


def get_execution_steps() -> list[tuple[str, Callable[[], BehaviorTree]]]:
    return [
        ("Initialize Bot", InitializeBot),
        ("Prepare Run", PrepareRun),
        ("Enter Mission", EnterMission),
        ("Setup Defense", SetupDefense),
        ("Defend Zhellix", DefendZhellix),
        ("Finish Run", FinishRun),
    ]

def main() -> None:
    global initialized

    if not initialized:
        ensure_botting_tree()
        initialized = True

    tree = ensure_botting_tree()
    tree.tick()
    attach_botting_tree_support(tree)
    tree.UI.draw_window(icon_path=TEXTURE,
        main_child_dimensions=(550, 390),
        extra_tabs=[("Statistics", _draw_statistics)],
    )


if __name__ == "__main__":
    main()
