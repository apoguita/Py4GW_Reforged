"""
Friend List section — friend/ignore/partner/trader counts, self status, and add/set actions.

Shape (see player_demo.py, the canonical template):
  * ``build_friendlist()`` calls the native ``PyFriendList`` free functions, CASTS each value via
    ``casts`` (self-status int -> ``[value] - Name`` via a local FriendStatus map; counts per
    FriendType), and returns display Blocks. Every displayed value is a scalar. Counts are queried
    per FriendType so the "list" is represented as a per-type tally.
  * ``draw_friendlist_view()`` builds once, offers the per-section Dump-to-file button, then a tab
    bar: ``Data`` (ui.draw_blocks) + ``Actions`` (explicit trigger buttons, never auto-fired).

Why no per-friend roster here (verified, not an omission): the per-entry list lives in the C++
``GW::Context::FriendList`` (include/GW/context/friend_list.h) as ``FriendsListArray friends`` of
``Friend{type, status, uuid[16], alias[20], charname[20], friend_id, zone_id}``, reached only via
the unbound ``GW::Context::GetFriendList()`` accessor. That struct has NO shared-memory pointer
(see PointersSSM — no FriendList entry), NO ctypes reader (no native_src/context/FriendList.py),
and NO ``GWContext`` facade, so there is no handle to deref from Python. The bindings expose only
free functions (friend_list_bindings.cpp): counts + self status. ``PyFriendList`` binds no
``py::class_``/``py::enum_`` and the ``GetFriend`` overloads are NOT bound. Hence counts + status
ARE the maximum reachable surface — surfaced below, with the gap documented in ``_unavailable_block``.

Data path: native ``PyFriendList`` module (free functions only). No wrapper/GlobalCache layer.

R2 coverage — PyFriendList (8 methods, ALL wired):
  Data getters (Data tab): get_number_of_friends(1) [called per FriendType], get_number_of_ignores(2),
  get_number_of_partners(3), get_number_of_traders(4), get_my_status(5).
  Action/mutators (Actions tab, queue-backed): set_friend_list_status(6), add_friend(7),
  add_ignore(8).
  Skipped: none — the whole bound surface is wired.
"""

import PyImGui

from . import casts
from . import diagnostics
from . import ui

_SECTION = "FriendList"

# Native module handle, guarded so the section survives an offline / no-binding interpreter.
try:  # pragma: no cover - runtime specific
    import PyFriendList as _PyFriendList
except Exception:  # noqa: BLE001 - offline: no embedded binding
    _PyFriendList = None

# GW::Constants enums are NOT bound to Python; mirror them locally for readable casts.
# (include/GW/common/constants/friend_list.h)
_FRIEND_TYPE_NAMES = {
    0: "Unknown",
    1: "Friend",
    2: "Ignore",
    3: "Player",
    4: "Trade",
}
_FRIEND_STATUS_NAMES = {
    0: "Offline",
    1: "Online",
    2: "DND",
    3: "Away",
    4: "Unknown",
}


# ---------------------------------------------------------------------------
# Helpers (explicit, hand-wired — no reflection/dir())
# ---------------------------------------------------------------------------
def _fl_call(fn_name: str, default, *args):
    """Call one explicitly-named ``PyFriendList`` free function, guarded."""
    if _PyFriendList is None:
        return default
    fn = getattr(_PyFriendList, fn_name, None)
    if not callable(fn):
        return default
    return casts.safe(fn, *args, default=default)


def _named(value, names: dict) -> str:
    try:
        return casts.id_name(int(value), names.get(int(value), "Unknown"))
    except (TypeError, ValueError):
        return str(value)


# ---------------------------------------------------------------------------
# build_* — call getters, cast, return blocks (shared by render AND dump)
# ---------------------------------------------------------------------------
def _status_block():
    if _PyFriendList is None:
        return ui.text_block("Friend List", "PyFriendList binding unavailable (offline / not injected).")
    status = _fl_call("get_my_status", 0)
    rows = [
        ("My Status", _named(status, _FRIEND_STATUS_NAMES)),
        ("Ignores", _fl_call("get_number_of_ignores", 0)),
        ("Partners", _fl_call("get_number_of_partners", 0)),
        ("Traders", _fl_call("get_number_of_traders", 0)),
    ]
    return ui.kv_block("My Status & Totals", rows)


def _counts_block():
    # get_number_of_friends(friend_type) — tally per FriendType (the per-entry list is not bound).
    headers = ["Friend Type", "Count"]
    rows = []
    for type_id, name in sorted(_FRIEND_TYPE_NAMES.items()):
        count = _fl_call("get_number_of_friends", 0, type_id)
        rows.append((casts.id_name(type_id, name), count))
    return ui.multi_block("Friends by Type (get_number_of_friends)", headers, rows)


def _unavailable_block():
    return ui.text_block(
        "Per-friend roster — not exposed to Python",
        "The friend entries (Friend struct: type, status, uuid, alias, charname, friend_id, "
        "zone_id) live in GW::Context::FriendList, reached only via the unbound GetFriendList() "
        "accessor. It has no shared-memory pointer and no ctypes reader, so per-friend rows "
        "cannot be read here; the counts + self status above are the full reachable surface.",
    )


def build_friendlist():
    blocks = [_status_block()]
    if _PyFriendList is not None:
        blocks.append(_counts_block())
        blocks.append(_unavailable_block())
    return blocks


# ---------------------------------------------------------------------------
# Actions — explicit trigger buttons, fired only on click
# ---------------------------------------------------------------------------
class _State:
    status_id: int = 1              # set_friend_list_status (FriendStatus; 1 = Online)
    friend_name: str = ""           # add_friend / add_ignore charname
    friend_alias: str = ""          # add_friend / add_ignore display alias (optional)


state = _State()


def _draw_actions():
    ui.section_header("Self Status")
    ui.text_muted("Status: 0 Offline / 1 Online / 2 DND / 3 Away")
    state.status_id = PyImGui.input_int("Status ID", state.status_id)
    ui.action_button(
        "Set Friend List Status", _fl_action, "set_friend_list_status", state.status_id, key="set_status"
    )

    PyImGui.spacing()
    ui.section_header("Add Friend / Ignore")
    state.friend_name = PyImGui.input_text("Character Name", state.friend_name)
    state.friend_alias = PyImGui.input_text("Alias (optional)", state.friend_alias)
    ui.action_button(
        "Add Friend", _fl_action, "add_friend", state.friend_name, state.friend_alias, key="add_friend"
    )
    PyImGui.same_line(0, 8)
    ui.action_button(
        "Add Ignore", _fl_action, "add_ignore", state.friend_name, state.friend_alias, key="add_ignore"
    )


def _fl_action(fn_name: str, *args):
    """Fire one explicitly-named PyFriendList action; raise if the binding is missing."""
    if _PyFriendList is None:
        raise RuntimeError("PyFriendList binding unavailable")
    fn = getattr(_PyFriendList, fn_name, None)
    if not callable(fn):
        raise RuntimeError(f"PyFriendList.{fn_name} unavailable")
    return fn(*args)


# ---------------------------------------------------------------------------
# draw_*_view — uniform section entry point
# ---------------------------------------------------------------------------
def draw_friendlist_view() -> None:
    blocks = build_friendlist()
    diagnostics.dump_button(_SECTION, blocks)
    PyImGui.separator()
    if PyImGui.begin_tab_bar("FriendListTabs"):
        if PyImGui.begin_tab_item("Data"):
            ui.draw_blocks(_SECTION, blocks)
            PyImGui.end_tab_item()
        if PyImGui.begin_tab_item("Actions"):
            _draw_actions()
            PyImGui.end_tab_item()
        PyImGui.end_tab_bar()
