"""Recolor & Beacons -- the single authority on what is **highlighted**.

It answers *"should this be highlighted, and how"* and nothing else. It never decides what is wanted;
that is Loot Filters, and the two are independent -- neither can be switched off from the other's
section and neither needs the other to be on.

**One feature, two expressions.** Recolour and beacon are the same act of highlighting. A filter may
do either, both, or neither; the two are independent checkboxes on the filter, not a variant of one
setting.

**Delivery is ONE bulk call.** The class resolves everything itself -- all matching, all conflict
resolution -- and hands over one already-decided colour per agent
(``AgentRecolor.SetItemColors``). The backend only paints the answer; it never chooses between rules.
That is why the per-kind item setters stay unexposed: a second matching path would be a competing
authority.

**Resolution.** Filters resolve independently, and the profile's order settles only what cannot hold
two values at once::

    is it wanted?            -> not this feature's question
    should it be blanked?    -> HAS-ANY, and it beats a colour: hiding is the stronger intent
    should it beacon?        -> HAS-ANY -- a boolean, so order is irrelevant
    which colour?            -> the topmost matching filter, because an agent carries only one
    which beacon preset?     -> the topmost matching filter, same reason

**We do not solve collisions.** Contradicting filters are the user's own choice: no conflict
detection, no warnings, no precedence system to configure. Determinism is still required -- a label
must not flicker between frames -- but that is an implementation consequence, not a feature.

**BLANK is a named feature.** A fully transparent colour removes an item from the on-screen labels.
It is visual only: blanking a label never changes whether the item is wanted.
"""

from ..FrameCache import frame_cache
from ..beacons import effect as beacon_effect
from ..loot_filter_factory import matcher
from ..loot_filter_factory import store as factory_store
from . import store
from .model import MarkConfig

_CB_DATA = "recolor_beacons"
_CB_DRAW = "recolor_beacons_draw"

#: Fully transparent -- the item leaves the on-screen labels entirely.
BLANK_ARGB = 0x00000000


def _log(message: str) -> None:
    try:
        from Py4GWCoreLib.Py4GWcorelib import ConsoleLog

        ConsoleLog("Recolor & Beacons", message)
    except Exception:
        pass


def _argb(rgba) -> int:
    r = max(0, min(255, int(rgba[0] * 255)))
    g = max(0, min(255, int(rgba[1] * 255)))
    b = max(0, min(255, int(rgba[2] * 255)))
    a = max(0, min(255, int(rgba[3] * 255)))
    return (a << 24) | (r << 16) | (g << 8) | b


class RecolorBeacons:
    """Singleton. Holds the persisted and live configurations and decides what is highlighted."""

    _instance: "RecolorBeacons | None" = None

    def __new__(cls) -> "RecolorBeacons":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialise()
        return cls._instance

    def _initialise(self) -> None:
        self.persisted: MarkConfig = store.load()
        self.live: MarkConfig = self.persisted.copy()
        self._rules = factory_store.load_rules()
        self._profiles = factory_store.load_profiles()
        self._presets: list = []
        self._presets_loaded = False
        self._map_id: int | None = None
        self._pushed: list[tuple[int, int]] = []
        self._beacon_count = 0
        self._registered = False

    # ------------------------------------------------------------------ configuration

    def reload(self) -> None:
        self.persisted = store.load()
        self.live = self.persisted.copy()
        self.reload_factory()

    def reload_factory(self) -> None:
        """The Factory's filters or profiles changed, or a beacon preset did."""
        self._rules = factory_store.load_rules()
        self._profiles = factory_store.load_profiles()
        self._presets_loaded = False

    def save(self) -> None:
        """Persist the user's configuration. NEVER called with live."""
        store.save(self.persisted)

    def profiles(self):
        return list(self._profiles)

    def active_filters(self):
        """The filters the running profile names, **in its order** -- which is what resolves colour."""
        profile = factory_store.profile_by_name(self._profiles, self.live.profile)
        return [rule for rule in factory_store.rules_in_profile(self._rules, profile) if rule.enabled]

    def marking_filters(self):
        """Only those that actually mark. A filter that marks nothing is not worth evaluating."""
        return [rule for rule in self.active_filters() if rule.marks()]

    def presets(self):
        if not self._presets_loaded:
            from ..beacons import store as beacon_store

            self._presets = beacon_store.load()
            self._presets_loaded = True
        return self._presets

    def _preset(self, name: str):
        from ..beacons.model import BASE_NAME

        presets = self.presets()
        for preset in presets:
            if preset.name == name:
                return preset
        for preset in presets:
            if preset.name == BASE_NAME:
                return preset
        return presets[0] if presets else None

    # ------------------------------------------------------------------ live state

    def is_stock(self) -> bool:
        return not self.live.differs_from(self.persisted)

    def live_diff(self) -> list[str]:
        return self.live.diff(self.persisted)

    def reset_live(self) -> None:
        """Discard everything a script changed. The only recovery, and always available."""
        self.live = self.persisted.copy()

    # ------------------------------------------------------------------ what a script may do
    #
    # Consumers only, and live-only. A script may switch the feature off or change which profile
    # runs; it may never author a filter, a profile or a preset, and nothing it does reaches disk.

    def set_enabled(self, value: bool) -> None:
        self.live.enabled = bool(value)
        if not self.live.enabled:
            self._clear_output()

    def use_profile(self, name: str) -> bool:
        if not factory_store.profile_by_name(self._profiles, name):
            return False
        self.live.profile = name
        return True

    # ------------------------------------------------------------------ resolution

    def resolve(self, agent_id: int, item_id: int, model_id: int):
        """One item's whole verdict: ``(argb_or_None, preset_name_or_None)``.

        Blank wins over a colour -- a filter asking for the item to be gone is a stronger statement
        than one asking for it to be tinted. Otherwise the topmost matching filter supplies the
        colour, which is what keeps a label from flickering when several match.
        """
        colour: int | None = None
        preset: str | None = None
        blank = False
        for rule in self.marking_filters():
            if not matcher.matches(rule, item_id, model_id):
                continue
            if rule.mark_blank:
                blank = True
            if rule.mark_recolor and colour is None:
                colour = _argb(rule.mark_color)
            if rule.mark_beacon and preset is None:
                preset = rule.mark_preset or ""
        if blank:
            return BLANK_ARGB, preset
        return colour, preset

    # ------------------------------------------------------------------ the pass

    def _candidates(self, distance: float):
        """Nearby ground items and who owns them. Marking looks at ALL of them, not only ours --
        blanking loot assigned to somebody else is one of the stated uses."""
        from Py4GWCoreLib.Agent import Agent
        from Py4GWCoreLib.AgentArray import AgentArray
        from Py4GWCoreLib.Player import Player
        from Py4GWCoreLib.Routines import Routines

        if not Routines.Checks.Map.MapValid():
            return []
        array = AgentArray.Filter.ByDistance(AgentArray.GetItemArray(), Player.GetXY(), distance)
        mine = Player.GetAgentID()
        out = []
        for agent_id in array:
            if not Agent.IsValid(agent_id):
                continue
            owner = Agent.GetItemAgentOwnerID(agent_id)
            out.append((agent_id, owner == mine or owner == 0))
        return out

    @frame_cache(category="RecolorBeacons", source_lib="GetMarkedItems")
    def GetMarkedItems(self) -> list[tuple[int, int, str | None]]:
        """``[(agent_id, argb, preset), ...]`` for everything marked. Cached per frame.

        ``argb`` is ``-1`` for "no colour"; ``preset`` is ``None`` for "no beacon", and ``""`` for
        "a beacon on the default preset" -- the two are different answers and must not collapse.

        One walk of the agent array serves both the recolour push and the beacon pass.
        """
        if not self.live.enabled:
            return []

        from Py4GWCoreLib.Agent import Agent
        from Py4GWCoreLib.Item import Item

        self._check_map()
        # The recolour reaches as far as labels are drawn; the beacon limit is applied separately,
        # so a distant item can still be blanked without paying for a beacon.
        reach = max(float(self.live.beacon_distance), 5000.0)
        out: list[tuple[int, int, str | None]] = []
        for agent_id, is_ours in self._candidates(reach):
            item_agent = Agent.GetItemAgentByID(agent_id)
            if item_agent is None:
                continue
            item_id = item_agent.item_id
            colour, preset = self.resolve(agent_id, item_id, Item.GetModelID(item_id))
            if colour is None and self.live.blank_unassigned and not is_ours:
                colour = BLANK_ARGB     # not ours to take, so it need not be on screen
            if colour is None and preset is None:
                continue
            out.append((agent_id, colour if colour is not None else -1, preset))
        return out

    def _clear_output(self) -> None:
        """Stop marking: drop the colour rules and let every beacon go."""
        if self._pushed:
            try:
                from Py4GWCoreLib.AgentRecolor import AgentRecolor

                AgentRecolor.SetItemColors([])
            except Exception:
                pass
            self._pushed = []
        beacon_effect.renderer().clear()
        self._beacon_count = 0

    def _check_map(self) -> None:
        try:
            from Py4GWCoreLib.Map import Map

            map_id = Map.GetMapID()
        except Exception:
            return
        if map_id != self._map_id:
            self._map_id = map_id
            beacon_effect.renderer().invalidate_ground()

    # ------------------------------------------------------------------ output

    def _push_colours(self) -> None:
        """The whole delivery surface: one bulk call carrying the full resolved set."""
        rules = [(agent_id, argb) for agent_id, argb, _preset in self.GetMarkedItems() if argb >= 0]
        if rules == self._pushed:
            return                      # the backend already holds exactly this
        try:
            from Py4GWCoreLib.AgentRecolor import AgentRecolor

            AgentRecolor.EnableItems(True)
            AgentRecolor.SetItemColors(rules)
            self._pushed = rules
        except Exception as exc:
            _log("could not push item colours: %s" % exc)

    def _beacon_targets(self):
        """Which beacons to draw, inside the user's budget: nearest first, up to the maximum."""
        from Py4GWCoreLib.Agent import Agent
        from Py4GWCoreLib.Player import Player

        limit = float(self.live.beacon_distance)
        px, py = Player.GetXY()
        rows = []
        for agent_id, _argb, preset in self.GetMarkedItems():
            if preset is None:
                continue                # marked, but not with a beacon
            try:
                x, y = Agent.GetXY(agent_id)
            except Exception:
                continue
            distance = ((x - px) ** 2 + (y - py) ** 2) ** 0.5
            if distance > limit:
                continue
            rows.append((distance, agent_id, x, y, preset))
        rows.sort(key=lambda row: row[0])
        return rows[:max(0, int(self.live.max_beacons))]

    def _cheap(self, preset):
        """A stand-in for a distant beacon: the beam only.

        Emitters and rings are what a beacon costs; the beam is what makes it visible from far away.
        Dropping the first and keeping the second is the trade the user asked to be able to make.
        """
        stripped = preset.copy()
        stripped.params["rings"] = 0
        stripped.params["beam_glow"] = 0.0
        for emitter in stripped.emitters:
            emitter.enabled = False
        return stripped

    def _draw_beacons(self) -> None:
        from Py4GWCoreLib.Player import Player

        renderer = beacon_effect.renderer()
        if not self.live.enabled:
            self._beacon_count = 0
            renderer.end_frame()
            return
        try:
            px, py = Player.GetXY()
        except Exception:
            renderer.end_frame()
            return

        cheap_from = float(self.live.cheap_distance) if self.live.cheap_distant else float("inf")
        drawn = 0
        for distance, agent_id, x, y, preset_name in self._beacon_targets():
            preset = self._preset(preset_name)
            if preset is None:
                continue
            renderer.show(agent_id, x, y, self._cheap(preset) if distance > cheap_from else preset)
            drawn += 1
        self._beacon_count = drawn
        # Anything not shown this frame is released -- a picked-up drop takes its beacon with it.
        renderer.end_frame()

    # ------------------------------------------------------------------ diagnostics

    def status(self) -> dict:
        return {"enabled": self.live.enabled, "profile": self.live.profile,
                "filters": len(self.marking_filters()), "recoloured": len(self._pushed),
                "beacons": self._beacon_count,
                "particles": beacon_effect.renderer().live_particles()}

    # ------------------------------------------------------------------ driving

    def register(self) -> None:
        """Two passes: the colour push in the data phase, the beacons in the draw phase."""
        try:
            import PyCallback

            from Py4GWCoreLib.py4gwcorelib_src.Profiling import ProfilingRegistry

            PyCallback.PyCallback.RemoveByName(_CB_DATA)   # idempotent across reloads
            PyCallback.PyCallback.RemoveByName(_CB_DRAW)
            PyCallback.PyCallback.Register(_CB_DATA, PyCallback.Phase.Data, self._data_pass,
                                           priority=99, context=PyCallback.Context.Update)
            PyCallback.PyCallback.Register(_CB_DRAW, PyCallback.Phase.Update, self._draw_pass,
                                           priority=99, context=PyCallback.Context.Draw)
            registry = ProfilingRegistry()
            registry.register(_CB_DATA)
            registry.register(_CB_DRAW)
            self._registered = True
        except Exception as exc:
            _log("callback registration error: %s" % exc)

    def unregister(self) -> None:
        try:
            import PyCallback

            PyCallback.PyCallback.RemoveByName(_CB_DATA)
            PyCallback.PyCallback.RemoveByName(_CB_DRAW)
        except Exception:
            pass
        self._clear_output()
        self._registered = False

    def _profiled(self, name: str, scope: str, fn) -> None:
        try:
            from Py4GWCoreLib.py4gwcorelib_src.Profiling import ProfilingRegistry

            registry = ProfilingRegistry()
            if registry.enabled:
                registry.runcall_scope("widgets", "%s:%s" % (name, scope), fn)
                return
        except Exception:
            pass
        fn()

    def _data_pass(self) -> None:
        self._profiled(_CB_DATA, "data", self._do_data)

    def _do_data(self) -> None:
        if not self.live.enabled:
            if self._pushed:
                self._clear_output()
            return
        self._check_map()
        self._push_colours()

    def _draw_pass(self) -> None:
        self._profiled(_CB_DRAW, "draw", self._draw_beacons)
