"""
Quest section — active quest, quest-log inspection, async text triads, actions.

Shape (mirrors ``player_demo.py``, the canonical template):
  * ``build_quest()`` calls the ``GLOBAL_CACHE.Quest`` getters, CASTS each value via ``casts``
    (never repr a ``QuestData`` struct — every field is dereferenced explicitly), and returns a
    list of display Blocks.
  * ``draw_quest_view()`` builds once, offers the per-section Dump-to-file button, exposes the
    ``state.quest_id`` subject input (+ a Load-Active-Quest helper), then a Data / Actions tab bar.

Data path: ``GLOBAL_CACHE.Quest`` (``QuestCache``, mirrors the ``PyQuest.PyQuest()`` static
surface). Routed through GlobalCache — not the base ``Quest`` wrapper — for crash-safety parity
with the legacy demo (the base wrapper rebuilds a native handle per call and can crash where the
throttled/cached GlobalCache path does not).

The async-id trap (R3 §12): quest text is NOT synchronous. Every string field is a 3-call triad —
``RequestQuest*`` (fire, an Action button) → ``IsQuest*Ready`` (poll) → ``GetQuest*`` (read). The
Data tab shows the ready flags + values and reports "<not requested / not ready>" until a request
in the Actions tab has completed, so an un-requested quest reads as textless (not nameless-forever).
``GetQuestData(quest_id)`` returns a ``QuestData`` struct whose string fields stay empty until the
async path fills them — only its ids / ``marker_x/y`` floats / flags are populated synchronously.

R2 coverage (PyQuest, 51 rows = 27 static methods + 24 free fns; ~24 free fns absent from the stub).
Wired via ``GLOBAL_CACHE.Quest`` (== PyQuest static surface):
  GetActiveQuest, SetActiveQuest, AbandonQuest, IsQuestCompleted, IsQuestPrimary,
  IsMissionMapQuestAvailable, GetQuestData, GetQuestLog, GetQuestLogIds, RequestQuestInfo,
  RequestQuestName/IsQuestNameReady/GetQuestName, RequestQuestDescription/IsQuestDescriptionReady/
  GetQuestDescription, RequestQuestObjectives/IsQuestObjectivesReady/GetQuestObjectives,
  RequestQuestLocation/IsQuestLocationReady/GetQuestLocation, RequestQuestNPC/IsQuestNPCReady/
  GetQuestNPC.
Wired directly from the native free-function surface (no wrapper / stub entry):
  get_quest_entry_group_name (PyQuest module-level fn, R2 row 32 — the only free fn with no static
  equivalent, absent from QuestCache), guarded so its absence never blanks the panel.
Skipped: QuestData.__init__ / PyQuest.__init__ (R2 rows 1-2, ctors — used internally by the
  cache), and the 23 remaining module-level free functions (R2 rows 28-51 minus row 32) — each is
  a byte-for-byte alias of a PyQuest static method already wired through the cache.
"""

import PyImGui
import PyQuest

from Py4GWCoreLib import GLOBAL_CACHE

from . import casts
from . import diagnostics
from . import ui

_SECTION = "Quest"


class _State:
    quest_id: int = 0
    update_marker: bool = False


state = _State()


# ---------------------------------------------------------------------------
# build_* — call getters, cast, return blocks (shared by render AND dump)
# ---------------------------------------------------------------------------
def _entry_group_name(quest_id):
    """Native free fn ``PyQuest.get_quest_entry_group_name`` — guarded (stub-absent, may be gone).

    base free fn: not on GLOBAL_CACHE (QuestCache has no quest-entry-group-name getter).
    """
    try:
        return PyQuest.get_quest_entry_group_name(quest_id)
    except Exception:  # noqa: BLE001 - free fn is not in the stub; tolerate its absence
        return "<unavailable>"


def _resolve_quest_name(quest_id):
    """Drive the async name triad and return the resolved string (R3 §12).

    Fires ``RequestQuestName`` every build so resolution actually progresses — the cache
    call is a pure native request/poll (``request_quest_name``), not a game-moving mutator, so
    it is safe to fire each frame (mirrors legacy firing ``Item.RequestName`` each frame). Once
    ``IsQuestNameReady`` flips true, ``GetQuestName`` returns the real name.
    """
    casts.safe(GLOBAL_CACHE.Quest.RequestQuestName, quest_id)
    if bool(casts.safe(GLOBAL_CACHE.Quest.IsQuestNameReady, quest_id)):
        name = casts.safe(GLOBAL_CACHE.Quest.GetQuestName, quest_id, default="")
        return str(name) if name else "(empty)"
    return "(resolving...)"


def _summary_block():
    qid = state.quest_id
    ids = casts.safe(GLOBAL_CACHE.Quest.GetQuestLogIds, default=[]) or []
    rows = [
        ("Subject Quest ID", qid),
        ("Active Quest ID", casts.safe(GLOBAL_CACHE.Quest.GetActiveQuest)),
        ("Quest Log Count", len(ids)),
        ("Quest Log IDs", str(list(ids))),
        ("Mission-Map Quest Available", casts.yesno(casts.safe(GLOBAL_CACHE.Quest.IsMissionMapQuestAvailable))),
        ("Entry Group Name (subject)", _entry_group_name(qid)),
    ]
    return ui.kv_block("Summary", rows)


def _log_block():
    """Quest-log table (R2 subject rule): id + resolved name, + per-entry flags.

    Rows come from GetQuestLog() structs (quest_id / log_state dereffed field-by-field). Each
    row drives its own name triad via ``_resolve_quest_name`` (RequestQuestName fired per build),
    so names resolve on their own; completed/primary read live per row.
    """
    entries = casts.safe(GLOBAL_CACHE.Quest.GetQuestLog, default=[]) or []
    active = casts.safe(GLOBAL_CACHE.Quest.GetActiveQuest)
    headers = ["Quest ID", "Name", "log_state", "Completed", "Primary", "Active"]
    rows = []
    for entry in entries:
        eid = casts.safe(getattr, entry, "quest_id")
        rows.append((
            eid,
            _resolve_quest_name(eid),
            casts.flags(casts.safe(getattr, entry, "log_state", default=0)),
            casts.yesno(casts.safe(GLOBAL_CACHE.Quest.IsQuestCompleted, eid)),
            casts.yesno(casts.safe(GLOBAL_CACHE.Quest.IsQuestPrimary, eid)),
            casts.yesno(eid == active),
        ))
    return ui.multi_block("Quest Log (GetQuestLog structs)", headers, rows)


def _async_text_block():
    """The async triad for the subject quest — Ready flag + value per string field (R3 §12).

    Name is driven from build (RequestQuestName fired here) so the subject name resolves and
    displays without a manual Actions-tab click; the heavier fields (Description/Objectives/
    Location/NPC) stay request-on-demand via the Actions tab.
    """
    qid = state.quest_id
    casts.safe(GLOBAL_CACHE.Quest.RequestQuestName, qid)
    fields = [
        ("Name", GLOBAL_CACHE.Quest.IsQuestNameReady, GLOBAL_CACHE.Quest.GetQuestName),
        ("Description", GLOBAL_CACHE.Quest.IsQuestDescriptionReady, GLOBAL_CACHE.Quest.GetQuestDescription),
        ("Objectives", GLOBAL_CACHE.Quest.IsQuestObjectivesReady, GLOBAL_CACHE.Quest.GetQuestObjectives),
        ("Location", GLOBAL_CACHE.Quest.IsQuestLocationReady, GLOBAL_CACHE.Quest.GetQuestLocation),
        ("NPC", GLOBAL_CACHE.Quest.IsQuestNPCReady, GLOBAL_CACHE.Quest.GetQuestNPC),
    ]
    rows = []
    for label, ready_fn, get_fn in fields:
        ready = bool(casts.safe(ready_fn, qid))
        rows.append((f"{label} Ready", casts.yesno(ready)))
        if ready:
            value = casts.safe(get_fn, qid, default="")
            rows.append((label, value if value != "" else "(empty)"))
        else:
            rows.append((label, "<not requested / not ready>"))
    return ui.kv_block("Async Text (request via Actions tab)", rows)


def _struct_block():
    """GetQuestData(quest_id) — explicit field deref (R3 §12); never repr the QuestData struct."""
    qid = state.quest_id
    data = casts.safe(GLOBAL_CACHE.Quest.GetQuestData, qid)
    if data is None:
        return ui.kv_block("GetQuestData(quest_id)", [("GetQuestData", "None")])
    marker_x = casts.safe(getattr, data, "marker_x", default=0.0)
    marker_y = casts.safe(getattr, data, "marker_y", default=0.0)
    rows = [
        ("quest_id", casts.safe(getattr, data, "quest_id")),
        ("log_state", casts.flags(casts.safe(getattr, data, "log_state", default=0))),
        ("map_from", casts.safe(getattr, data, "map_from")),
        ("map_to", casts.safe(getattr, data, "map_to")),
        ("marker (x, y)", casts.vec(marker_x, marker_y)),
        ("h0024", casts.safe(getattr, data, "h0024")),
        # String fields are populated only by the async path, not by GetQuestData — expect empties.
        ("location", casts.safe(getattr, data, "location")),
        ("name", casts.safe(getattr, data, "name")),
        ("npc", casts.safe(getattr, data, "npc")),
        ("description", casts.safe(getattr, data, "description")),
        ("objectives", casts.safe(getattr, data, "objectives")),
        ("is_completed", casts.yesno(casts.safe(getattr, data, "is_completed"))),
        ("is_current_mission_quest", casts.yesno(casts.safe(getattr, data, "is_current_mission_quest"))),
        ("is_area_primary", casts.yesno(casts.safe(getattr, data, "is_area_primary"))),
        ("is_primary", casts.yesno(casts.safe(getattr, data, "is_primary"))),
    ]
    return ui.kv_block("GetQuestData(quest_id) — struct fields (strings empty until requested)", rows)


def _flags_block():
    bools = [
        ("Is Completed", bool(casts.safe(GLOBAL_CACHE.Quest.IsQuestCompleted, state.quest_id))),
        ("Is Primary", bool(casts.safe(GLOBAL_CACHE.Quest.IsQuestPrimary, state.quest_id))),
    ]
    return ui.bool_block("Subject Quest Flags", bools)


def build_quest():
    return [
        _summary_block(),
        _log_block(),
        _async_text_block(),
        _struct_block(),
        _flags_block(),
    ]


# ---------------------------------------------------------------------------
# Actions — explicit trigger buttons, fired only on click
# ---------------------------------------------------------------------------
def _draw_actions():
    ui.section_header("Active Quest")
    ui.action_button("Set Active Quest", GLOBAL_CACHE.Quest.SetActiveQuest, state.quest_id, key="set_active")
    PyImGui.same_line(0, 8)
    ui.action_button("Abandon Quest", GLOBAL_CACHE.Quest.AbandonQuest, state.quest_id, key="abandon")

    PyImGui.spacing()
    ui.section_header("Prefetch Quest Text (async triad step 1 — Request)")
    state.update_marker = PyImGui.checkbox("Update Marker", state.update_marker)
    ui.action_button(
        "Request Quest Info (umbrella)",
        GLOBAL_CACHE.Quest.RequestQuestInfo,
        state.quest_id,
        state.update_marker,
        key="req_info",
    )
    ui.action_button("Request Name", GLOBAL_CACHE.Quest.RequestQuestName, state.quest_id, key="req_name")
    PyImGui.same_line(0, 8)
    ui.action_button("Request Description", GLOBAL_CACHE.Quest.RequestQuestDescription, state.quest_id, key="req_desc")
    PyImGui.same_line(0, 8)
    ui.action_button("Request Objectives", GLOBAL_CACHE.Quest.RequestQuestObjectives, state.quest_id, key="req_obj")
    ui.action_button("Request Location", GLOBAL_CACHE.Quest.RequestQuestLocation, state.quest_id, key="req_loc")
    PyImGui.same_line(0, 8)
    ui.action_button("Request NPC", GLOBAL_CACHE.Quest.RequestQuestNPC, state.quest_id, key="req_npc")


# ---------------------------------------------------------------------------
# draw_*_view — uniform section entry point
# ---------------------------------------------------------------------------
def draw_quest_view() -> None:
    blocks = build_quest()
    diagnostics.dump_button(_SECTION, blocks)
    PyImGui.separator()
    state.quest_id = PyImGui.input_int("Quest ID", state.quest_id)
    PyImGui.same_line(0, 8)
    if PyImGui.button("Load Active Quest"):
        active = casts.safe(GLOBAL_CACHE.Quest.GetActiveQuest)
        if active is not None:
            state.quest_id = int(active)
    if PyImGui.begin_tab_bar("QuestTabs"):
        if PyImGui.begin_tab_item("Data"):
            ui.draw_blocks(_SECTION, blocks)
            PyImGui.end_tab_item()
        if PyImGui.begin_tab_item("Actions"):
            _draw_actions()
            PyImGui.end_tab_item()
        PyImGui.end_tab_bar()
