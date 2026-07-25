import Py4GW
import PyImGui
from typing import Callable, Optional
from Py4GWCoreLib import ImGui, ColorPalette, GLOBAL_CACHE, Routines, Utils, Map
from typing import Dict, Tuple, List
#region QuestData


def _coerce_quest_id(raw) -> Optional[int]:
    """Return raw as a plain int, or None if it cannot be used as a quest id.

    set_active_quest_id() is a pybind11 binding over a c_uint32 field
    (WorldContext.active_quest_id), so negative values are rejected outright
    and None raises TypeError deep inside the ActionQueue, far from the call
    site that queued it. Everything that reaches the binding goes through
    here first.

    0 is the project-wide sentinel for "no active quest" (see QuestLogStruct,
    which maps None -> 0, and the Quest Auto-Runner's `== 0` check), so it is
    normalized to None rather than treated as a real id.
    """
    if raw is None:
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    return value


class QuestNode:
    def __init__(self, quest_id):
        self.quest_id: int = quest_id
        self.name: str = ""
        self.quest_location: str = ""
        self.npc_quest_giver: str = ""
        self.description: str = ""
        self.objectives: str = ""
        self.map_from: int = 0
        self.map_to: int = 0
        self.quest_marker: tuple[float, float] = (0.0, 0.0)
        self.is_completed: bool = False
        self.is_primary: bool = False
        self.is_area_primary: bool = False
        self.is_current_mission_quest: bool = False

        self.force_update: bool = True
        self.partial_data_fetched: bool = False
        self.complete_data_fetched: bool = False

    @property
    def is_sentinel(self) -> bool:
        """True for pseudo-nodes (mission map quest) that have no real id."""
        return self.quest_id is None or self.quest_id < 0

    def coro_initialize(self):
        def _wait_until_active(qid, timeout_ms: int = 3000):
            """Wait for qid to become the active quest.

            Returns True on success, False on timeout.  The original
            version looped forever, so a quest that never activated
            (notably the -1 sentinel) parked a coroutine permanently.
            """
            waited = 0
            while GLOBAL_CACHE.Quest.GetActiveQuest() != qid:
                if waited >= timeout_ms:
                    return False
                yield from Routines.Yield.wait(50)
                waited += 50
            return True

        def _fetch_with_retries(req_fn, is_ready_fn, get_fn, attr_name,
                                timeout_ms: int = 3000):
            for _ in range(5):
                req_fn(self.quest_id)
                setattr(self, attr_name, "Requesting...")
                yield from Routines.Yield.wait(50)

                waited = 0
                timed_out = False
                while not is_ready_fn(self.quest_id):
                    if waited >= timeout_ms:
                        timed_out = True
                        break
                    yield from Routines.Yield.wait(50)
                    waited += 50

                if timed_out:
                    continue

                value = get_fn(self.quest_id)
                setattr(self, attr_name, value)
                if value != "Timeout":
                    break

        # Snapshot whatever is active now so we can put it back afterwards.
        # None means "nothing sensible was active" - in that case we simply
        # do not restore, rather than feeding None to the binding.
        current = _coerce_quest_id(GLOBAL_CACHE.Quest.GetActiveQuest())

        activated = False
        if not self.is_sentinel and self.quest_id != current:
            GLOBAL_CACHE.Quest.SetActiveQuest(self.quest_id)
            yield from Routines.Yield.wait(50)
            if not (yield from _wait_until_active(self.quest_id)):
                # Could not activate; nothing was changed that needs undoing.
                return
            activated = True
            GLOBAL_CACHE.Quest.RequestQuestInfo(self.quest_id, update_marker=True)
            yield from Routines.Yield.wait(100)

        quest = GLOBAL_CACHE.Quest.GetQuestData(self.quest_id)
        if quest:
            self.map_from = quest.map_from
            self.map_to = quest.map_to
            self.quest_marker = (quest.marker_x, quest.marker_y)
            self.is_completed = quest.is_completed
            self.is_primary = quest.is_primary
            self.is_area_primary = quest.is_area_primary
            self.is_current_mission_quest = quest.is_current_mission_quest

        yield from _fetch_with_retries(
            GLOBAL_CACHE.Quest.RequestQuestName,
            GLOBAL_CACHE.Quest.IsQuestNameReady,
            GLOBAL_CACHE.Quest.GetQuestName,
            "name",
        )
        yield from _fetch_with_retries(
            GLOBAL_CACHE.Quest.RequestQuestLocation,
            GLOBAL_CACHE.Quest.IsQuestLocationReady,
            GLOBAL_CACHE.Quest.GetQuestLocation,
            "quest_location",
        )
        yield from _fetch_with_retries(
            GLOBAL_CACHE.Quest.RequestQuestDescription,
            GLOBAL_CACHE.Quest.IsQuestDescriptionReady,
            GLOBAL_CACHE.Quest.GetQuestDescription,
            "description",
        )
        yield from _fetch_with_retries(
            GLOBAL_CACHE.Quest.RequestQuestObjectives,
            GLOBAL_CACHE.Quest.IsQuestObjectivesReady,
            GLOBAL_CACHE.Quest.GetQuestObjectives,
            "objectives",
        )
        yield from _fetch_with_retries(
            GLOBAL_CACHE.Quest.RequestQuestNPC,
            GLOBAL_CACHE.Quest.IsQuestNPCReady,
            GLOBAL_CACHE.Quest.GetQuestNPC,
            "npc_quest_giver",
        )

        self.complete_data_fetched = True
        self.force_update = False

        # --- restore original active quest ---
        # Only if we actually changed it, and only with a usable int.
        if activated and current is not None and current != self.quest_id:
            GLOBAL_CACHE.Quest.SetActiveQuest(current)
            yield from Routines.Yield.wait(50)
            yield from _wait_until_active(current)


class QuestData:
    # ===============================
    # COLOR MAPS for quest markup tags
    # ===============================
    COLOR_MAP: Dict[str, Tuple[float, float, float, float]] = {
        "@warning": ColorPalette.GetColor("red").to_tuple_normalized(),
        "@Warning": ColorPalette.GetColor("red").to_tuple_normalized(),
        "@Quest":   ColorPalette.GetColor("bright_green").to_tuple_normalized(),
        "@quest":   ColorPalette.GetColor("bright_green").to_tuple_normalized(),
        "Header":  ColorPalette.GetColor("creme").to_tuple_normalized(),
    }

    def __init__(self):
        self.quest_log: Dict[int, 'QuestNode'] = {}
        self.active_quest_id = 0
        self.initialized = False
        self.initializing = False
        self.mission_map_quest = None
        self.mission_map_quest_initialized = False
        self.mission_map_quest_initializing = False
        self.mission_map_quest_force_update = False
        # Read by PartyQuestLog/ui.py draw_log(); must always exist.
        self.mission_map_quest_loaded = False

    # ------------------------------------------------------------------
    # lookup
    # ------------------------------------------------------------------
    def get_node(self, qid) -> Optional['QuestNode']:
        """Resolve a quest id to its node.

        The mission map quest is grouped and drawn alongside the regular
        quests but is NOT stored in self.quest_log, so indexing quest_log
        directly raised KeyError as soon as a mission map quest existed.
        """
        if (self.mission_map_quest is not None
                and qid == self.mission_map_quest.quest_id):
            return self.mission_map_quest
        return self.quest_log.get(qid)

    def get_name(self, qid) -> str:
        node = self.get_node(qid)
        return node.name if node is not None else ""

    # ------------------------------------------------------------------
    # mission map quest resolution
    # ------------------------------------------------------------------
    @staticmethod
    def resolve_mission_map_quest_id() -> Optional[int]:
        """Find the real quest id of the current mission map quest.

        PyQuest exposes is_mission_map_quest_available() but no accessor for
        the id itself. QuestData rows carry an is_current_mission_quest flag,
        so scan the log for it rather than inventing a -1 sentinel: -1 is
        rejected by the unsigned bindings and GetQuestData(-1) silently
        returns a zero-filled struct.
        """
        try:
            quest_log = GLOBAL_CACHE.Quest.GetQuestLog()
        except Exception:
            return None

        for row in quest_log or []:
            if getattr(row, "is_current_mission_quest", False):
                return _coerce_quest_id(getattr(row, "quest_id", None))
        return None

    # ------------------------------------------------------------------
    # coroutines
    # ------------------------------------------------------------------
    def coro_initialize(self):
        try:
            quest_log_ids = GLOBAL_CACHE.Quest.GetQuestLogIds()
            for qid in quest_log_ids:
                quest_node = QuestNode(qid)
                self.quest_log[qid] = quest_node
                yield from quest_node.coro_initialize()
            self.initialized = True
        finally:
            # Always clear the in-progress flag, otherwise a failure
            # wedges initialization permanently.
            self.initializing = False

    def coro_initialize_mission_map_quest(self, quest_id: int):
        try:
            if self.mission_map_quest is None or self.mission_map_quest.quest_id != quest_id:
                self.mission_map_quest = QuestNode(quest_id)
                yield from self.mission_map_quest.coro_initialize()
            self.mission_map_quest_initialized = True
            self.mission_map_quest_loaded = True
            self.mission_map_quest_force_update = False
            yield
        finally:
            self.mission_map_quest_initializing = False

    def update(self):
        self.active_quest_id = _coerce_quest_id(GLOBAL_CACHE.Quest.GetActiveQuest())

        if not GLOBAL_CACHE.Quest.IsMissionMapQuestAvailable():
            if self.mission_map_quest is not None:
                self.mission_map_quest = None
                self.mission_map_quest_initialized = False
                self.mission_map_quest_initializing = False
                self.mission_map_quest_loaded = False
                self.mission_map_quest_force_update = False
                print("Mission map quest data cleared.")
        else:
            mission_qid = self.resolve_mission_map_quest_id()

            if mission_qid is None:
                # Flagged available but the row is not in the log yet.
                # Do nothing this tick; update() runs again on the next one.
                pass
            else:
                changed = (self.mission_map_quest is not None
                           and self.mission_map_quest.quest_id != mission_qid)
                if changed:
                    self.mission_map_quest_initialized = False
                    self.mission_map_quest_loaded = False

                if self.mission_map_quest is None and not self.mission_map_quest_initializing:
                    print("Mission map quest now available.")

                needs_init = (not self.mission_map_quest_initialized
                              or self.mission_map_quest_force_update)
                if needs_init and not self.mission_map_quest_initializing:
                    # Mark "in progress", not "done" - the coroutine sets
                    # initialized only once it actually completes.
                    self.mission_map_quest_initializing = True
                    self.mission_map_quest_force_update = False
                    GLOBAL_CACHE.Coroutines.append(
                        self.coro_initialize_mission_map_quest(mission_qid))
                    print(f"Initializing mission map quest data (id {mission_qid})...")

        if not self.initialized:
            if not self.initializing:
                self.initializing = True
                GLOBAL_CACHE.Coroutines.append(self.coro_initialize())

    # ------------------------------------------------------------------
    # drawing
    # ------------------------------------------------------------------
    def draw_content(self, window_width: float, window_height: float):
        if not self.initialized:
            ImGui.text("Initializing quest data...")
            PyImGui.text(f"Active Quest ID: {self.active_quest_id}")
            return

        PyImGui.push_style_color(PyImGui.ImGuiCol.Text, self.COLOR_MAP["Header"])
        ImGui.text("Active Quests:", font_size=18)
        PyImGui.same_line(0, -1)
        PyImGui.text(f"Active Quest ID: {self.active_quest_id}")
        PyImGui.pop_style_color(1)
        PyImGui.same_line(0, -1)
        if PyImGui.button("Refresh Quest Info"):
            for quest in self.quest_log.values():
                GLOBAL_CACHE.Quest.RequestQuestInfo(quest.quest_id, update_marker=True)
                quest.force_update = True

        if PyImGui.begin_child("QuestTreeChild", (window_width - 20, 250), True, PyImGui.WindowFlags.NoFlag):
            grouped_quests: Dict[str, List[int]] = {}

            mission_location = None
            if self.mission_map_quest is not None:
                mission_location = self.mission_map_quest.quest_location
                grouped_quests.setdefault(mission_location, []).append(
                    self.mission_map_quest.quest_id)

            for quest in self.quest_log.values():
                # The mission map quest now carries a real id, so it is also a
                # row in quest_log - skip it here or it renders twice.
                if mission_location is not None and quest.quest_id == self.mission_map_quest.quest_id:
                    continue
                if quest.is_primary:
                    grouped_quests.setdefault("Primary", []).append(quest.quest_id)
                else:
                    grouped_quests.setdefault(quest.quest_location, []).append(quest.quest_id)

            ordered_groups: list[tuple[str, list[int]]] = []
            if mission_location is not None and mission_location in grouped_quests:
                ordered_groups.append((mission_location, grouped_quests.pop(mission_location)))

            if "Primary" in grouped_quests:
                ordered_groups.append(("Primary", grouped_quests.pop("Primary")))
            # Sort other groups alphabetically by location name
            for loc in sorted(grouped_quests.keys(), key=lambda s: s.lower()):
                ordered_groups.append((loc, grouped_quests[loc]))

            # --- Draw the tree ---
            for location, quest_ids in ordered_groups:
                # Sort quest IDs alphabetically by name
                sorted_qids = sorted(
                    quest_ids,
                    key=lambda qid: self.get_name(qid).lower()
                )

                ImGui.push_font("Regular", 18)
                PyImGui.push_style_color(PyImGui.ImGuiCol.Text, self.COLOR_MAP["Header"])
                opened = PyImGui.tree_node(f"{location} Quests ({len(sorted_qids)})")
                PyImGui.pop_style_color(1)
                ImGui.pop_font()

                if opened:
                    for qid in sorted_qids:
                        node = self.get_node(qid)
                        if node is None:
                            continue

                        is_active = (self.active_quest_id is not None
                                     and qid == self.active_quest_id)

                        if is_active:
                            PyImGui.push_style_color(PyImGui.ImGuiCol.Text, self.COLOR_MAP["Header"])

                        PyImGui.text(f"{node.name} (ID: {qid})")
                        text_size = PyImGui.calc_text_size(node.name)
                        text_pos = PyImGui.get_item_rect_min()
                        total_width = text_size[0]
                        max_height = text_size[1]
                        if node.is_completed:
                            PyImGui.same_line(0, 5)
                            PyImGui.push_style_color(PyImGui.ImGuiCol.Text, self.COLOR_MAP["Header"])
                            completed_text = "(Completed)"
                            PyImGui.text(completed_text)
                            PyImGui.pop_style_color(1)
                            total_width += 5 + PyImGui.calc_text_size(completed_text)[0]

                        if is_active:
                            PyImGui.pop_style_color(1)

                        # === highlight active quest ===
                        if is_active:
                            style = PyImGui.StyleConfig()
                            style.Pull()
                            padding_x = style.CellPadding[0] if style.CellPadding else 0.0
                            style.Push()

                            # get full child dimensions
                            child_pos = PyImGui.get_window_pos()
                            child_size = PyImGui.get_window_size()

                            # margin in pixels around the text (controls vertical overflow)
                            v_margin = 3.0  # expand highlight up/down by 3px each side

                            rect_min = (child_pos[0] + padding_x, text_pos[1] - v_margin)
                            rect_max = (
                                child_pos[0] + child_size[0] - padding_x,
                                text_pos[1] + max_height + v_margin
                            )

                            color = ColorPalette.GetColor("white").copy()
                            color.a = 50
                            PyImGui.draw_list_add_rect_filled(
                                rect_min[0], rect_min[1],
                                rect_max[0], rect_max[1],
                                color.to_color(),
                                0, 0
                            )

                        # overlay invisible button covering both texts
                        PyImGui.set_cursor_screen_pos(text_pos)
                        if PyImGui.invisible_button(f"quest_btn_{qid}", (total_width, max_height)):
                            # Sentinel nodes have no real id - do not try to
                            # activate them.
                            if not node.is_sentinel:
                                GLOBAL_CACHE.Quest.SetActiveQuest(qid)
                                # was: self.active_quest_id (stale by one frame)
                                GLOBAL_CACHE.Quest.RequestQuestInfo(qid, update_marker=True)
                                node.force_update = True

                    PyImGui.tree_pop()
            PyImGui.end_child()

        if PyImGui.begin_child("AccountInfoChild", (window_width - 20, 0), False, PyImGui.WindowFlags.NoFlag):
            child_width = PyImGui.get_content_region_avail()[0]
            active_node = self.get_node(self.active_quest_id)

            if active_node is None:
                # No active quest, or its node has not been built yet.
                PyImGui.push_style_color(PyImGui.ImGuiCol.Text, self.COLOR_MAP["Header"])
                ImGui.text("No active quest selected.", font_size=20)
                PyImGui.pop_style_color(1)
                PyImGui.end_child()
                return

            PyImGui.push_style_color(PyImGui.ImGuiCol.Text, self.COLOR_MAP["Header"])
            ImGui.text(f"ID: {self.active_quest_id} - {active_node.name}", font_size=20)
            ImGui.text("Quest Summary:", font_size=18)
            PyImGui.pop_style_color(1)

            tokens = Utils.TokenizeMarkupText(active_node.objectives, max_width=child_width)
            ImGui.render_tokenized_markup(tokens, max_width=child_width, COLOR_MAP=self.COLOR_MAP)

            PyImGui.push_style_color(PyImGui.ImGuiCol.Text, self.COLOR_MAP["Header"])
            PyImGui.text_wrapped(f"{active_node.npc_quest_giver}")
            PyImGui.pop_style_color(1)

            tokens = Utils.TokenizeMarkupText(active_node.description, max_width=child_width)
            ImGui.render_tokenized_markup(tokens, max_width=child_width, COLOR_MAP=self.COLOR_MAP)

            PyImGui.separator()
            PyImGui.text(f"From: {Map.GetMapName(active_node.map_from)}")
            PyImGui.text(f"To: {Map.GetMapName(active_node.map_to)}")
            PyImGui.text(f"Marker X,Y: ({active_node.quest_marker[0]}, {active_node.quest_marker[1]})")
            PyImGui.end_child()
