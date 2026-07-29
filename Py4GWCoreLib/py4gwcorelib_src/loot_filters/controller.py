"""The Loot Filters feature -- the single authority on what loot is wanted.

It answers **what is wanted** and nothing else. It never walks to an item, targets it, picks it up, or
decides *when* looting is appropriate; consumers own all of that.

**Resolution.** The blacklist is an absolute veto, evaluated first, because its whole job is to
inhibit every other rule. Everything else is a **HAS-ANY** -- the positive rules are not ranked
against each other::

    blacklisted           -> never
    otherwise, any of     -> wanted
        hand list | dye colour | salvage target | direct addition | Nicholas | rarity | filter

**Two instances of one config class.** ``persisted`` is the user's; ``live`` is what runs. A script
writes only live, and **never persists** -- there is no path from live to a writer.

**Consumers, never evaluators.** A script hands over *values* -- a model id, an item id. It may not
hand over anything that decides, and it may not create structure (profiles, sets of filters). That is
what stops the library being used as a proxy for a script's own ruling.
"""

from datetime import date

from ..FrameCache import frame_cache
from ..item_catalog import dyes as dye_data
from ..item_catalog import materials as material_data
from ..item_catalog.nicholas import NicholasCache
from ..loot_filter_factory import matcher
from ..loot_filter_factory import store as factory_store
from .model import LootConfig
from . import store

_CB_NAME = "loot_filters"


def _log(message: str) -> None:
    try:
        from Py4GWCoreLib.Py4GWcorelib import ConsoleLog

        ConsoleLog("Loot Filters", message)
    except Exception:
        pass


class LootFilters:
    """Singleton. Holds the persisted and live configurations and answers what is wanted."""

    _instance: "LootFilters | None" = None

    def __new__(cls) -> "LootFilters":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialise()
        return cls._instance

    def _initialise(self) -> None:
        self.persisted: LootConfig = store.load()
        self.live: LootConfig = self.persisted.copy()
        self._rules = factory_store.load_rules()
        self._profiles = factory_store.load_profiles()
        self._nicholas = NicholasCache()
        self._map_id: int | None = None
        self._registered = False

    # ------------------------------------------------------------------ configuration

    def reload(self) -> None:
        """Re-read the user's configuration and reset live to it."""
        self.persisted = store.load()
        self.live = self.persisted.copy()
        self.reload_factory()
        self._nicholas.invalidate()

    def reload_factory(self) -> None:
        """The Factory's filters or profiles changed."""
        self._rules = factory_store.load_rules()
        self._profiles = factory_store.load_profiles()

    def save(self) -> None:
        """Persist the user's configuration. NEVER called with live."""
        store.save(self.persisted)

    def active_filters(self):
        """The filters the running profile names, in its order."""
        profile = factory_store.profile_by_name(self._profiles, self.live.profile)
        return factory_store.rules_in_profile(self._rules, profile)

    def profiles(self):
        return list(self._profiles)

    # ------------------------------------------------------------------ live state

    def is_stock(self) -> bool:
        """Whether what is running is exactly what the user saved."""
        return not self.live.differs_from(self.persisted)

    def live_diff(self) -> list[str]:
        return self.live.diff(self.persisted)

    def reset_live(self) -> None:
        """Discard everything a script changed. The only recovery, and always available."""
        self.live = self.persisted.copy()
        self._nicholas.invalidate()

    def on_map_change(self) -> None:
        if self.live.clear_session_ids():
            _log("map changed - cleared session id entries")

    def _check_map(self) -> None:
        try:
            from Py4GWCoreLib.Map import Map

            map_id = Map.GetMapID()
        except Exception:
            return
        if map_id != self._map_id:
            self._map_id = map_id
            self.on_map_change()

    # ------------------------------------------------------------------ what a script may do
    #
    # ENTRIES yes, STRUCTURE no. All of it lands in LIVE and none of it is ever written to disk.

    def add_model(self, model_id: int) -> None:
        """Also want this kind of item, for this run."""
        self.live.added_model_ids.add(int(model_id))

    def add_item(self, agent_id: int) -> None:
        """Also want this one specific drop. Cleared on map change -- the id means nothing after."""
        self.live.added_item_ids.add(int(agent_id))

    def blacklist_model(self, model_id: int) -> None:
        """Never offer this kind of item, for this run."""
        self.live.blacklist_model_ids.add(int(model_id))

    def report_failed(self, agent_id: int) -> None:
        """"I could not get this one." Suppression is simply a blacklist entry, live-only."""
        self.live.blacklist_item_ids.add(int(agent_id))

    def use_profile(self, name: str) -> bool:
        """Switch the running profile. Live-only: the user's saved choice is untouched."""
        if not factory_store.profile_by_name(self._profiles, name):
            return False
        self.live.profile = name
        return True

    def set_rarity(self, name: str, value: bool) -> None:
        """Flip a rarity switch for this run only."""
        self.live.set_rarity(name, value)

    # ------------------------------------------------------------------ evaluation

    def _nicholas_model_ids(self) -> set[int]:
        if not self.live.nicholas:
            return set()
        return self._nicholas.model_ids(self.live.nicholas, date.today())

    def _rarity_wants(self, item_id: int) -> bool:
        from Py4GWCoreLib.Item import Item

        config, rarity = self.live, Item.Rarity
        return bool(
            (config.loot_whites and rarity.IsWhite(item_id))
            or (config.loot_blues and rarity.IsBlue(item_id))
            or (config.loot_purples and rarity.IsPurple(item_id))
            or (config.loot_golds and rarity.IsGold(item_id))
            or (config.loot_greens and rarity.IsGreen(item_id))
        )

    def _is_gold_coin(self, item_id: int) -> bool:
        try:
            from Py4GWCoreLib.enums import ItemType
            from Py4GWCoreLib.Item import Item

            return int(Item.GetItemType(item_id)[0]) == int(ItemType.Gold_Coin)
        except Exception:
            return False

    def _type_vetoed(self, item_id: int) -> bool:
        """Whether this item's TYPE is vetoed. Checked with the blacklist, before any positive rule."""
        if not self.live.blacklist_item_types:
            return False
        from Py4GWCoreLib.Item import Item

        try:
            return int(Item.GetItemType(item_id)[0]) in self.live.blacklist_item_types
        except Exception:
            return False

    def type_name(self, item_id: int) -> str:
        try:
            from Py4GWCoreLib.Item import Item

            value, name = Item.GetItemType(item_id)
            return "%s (%d)" % (name or "?", int(value))
        except Exception:
            return "?"

    #: Categories the game can confirm directly, by its own boolean. Used when the item-type
    #: table cannot resolve an entry -- 10 of the 20 tomes, for instance, are named differently in
    #: the source data, and `is_tome` answers for all of them.
    _CATEGORY_FLAG = {
        "Materials": ("IsMaterial", "IsRareMaterial"),
        "Tomes": ("IsTome",),
    }

    def on_hand_list(self, item_id: int, model_id: int) -> bool:
        """Whether a hand-list entry matches this item -- id **and** kind.

        **A model id does not identify an item.** The game reuses the number across item types::

            model 949 -> Materials_Zcoins : Steel Ingot
            model 949 -> Shield           : Embossed Aegis

        so matching the number alone made "I want Steel Ingot" also mean "I want an Embossed
        Aegis". **40 catalogued entries** are ambiguous this way.

        A list therefore means what it says: an entry picked from **Materials** must be a material,
        one picked from **Tomes** must be a tome, and so on. Two sources answer that, both the
        game's own:

        1. ``expected_types`` -- the item type each catalogued id should be, derived from the
           game's item data. Covers 336 ids.
        2. the game's kind booleans (``is_material``, ``is_tome``) for the categories that have
           one, which cover entries the table could not resolve.

        When neither can answer, the id alone matches -- **nothing is silently excluded**.
        """
        model_id = int(model_id)
        if model_id not in self.live.enabled_model_ids:
            return False

        from Py4GWCoreLib.Item import Item

        from ..item_catalog import catalog as catalog_data
        from ..item_catalog.expected_types import expected_type

        entry = catalog_data.by_model_id(model_id)
        category = entry.category if entry is not None else (
            "Materials" if material_data.material(model_id) is not None else "")

        for flag in self._CATEGORY_FLAG.get(category, ()):
            try:
                if bool(getattr(Item.Type, flag)(item_id)):
                    return True
            except Exception:
                pass

        wanted_type = expected_type(model_id)
        if wanted_type is None:
            return not self._CATEGORY_FLAG.get(category)   # no evidence either way -> the id stands
        try:
            return int(Item.GetItemType(item_id)[0]) == int(wanted_type)
        except Exception:
            return True     # unreadable -- honour the id rather than silently dropping loot

    def hand_list_kind(self, model_id: int) -> str:
        """What kind the catalog says a hand-listed id is, for the diagnostics."""
        from ..item_catalog.expected_types import expected_type

        wanted = expected_type(int(model_id))
        return "expected item type %s" % wanted if wanted is not None else "no expected type known"

    def wants(self, agent_id: int, item_id: int, model_id: int) -> bool:
        """The whole decision for one drop: blacklist veto, then HAS-ANY."""
        config = self.live
        agent_id, model_id = int(agent_id), int(model_id)

        # -- absolute veto --
        if agent_id in config.blacklist_item_ids or model_id in config.blacklist_model_ids:
            return False
        if self._type_vetoed(item_id):
            return False

        # -- HAS-ANY: no rule outranks another --
        if agent_id in config.added_item_ids:
            return True
        # A script's addition is explicit, so it matches on the id as given. A HAND LIST entry is
        # not: model ids are shared across item types, so it must also be the right kind of thing.
        if model_id in config.added_model_ids:
            return True
        if self.on_hand_list(item_id, model_id):
            return True

        # Dyes: identified by ITEM TYPE plus colour, never by model id -- they all share one.
        if config.enabled_dye_colors and dye_data.is_dye(item_id):
            if dye_data.color_of(item_id) in config.enabled_dye_colors:
                return True

        # Wanted for what it breaks down into, rather than for being that item.
        if config.salvage_target_ids:
            common, rare = material_data.salvages_into(model_id)
            if any(m in config.salvage_target_ids for m in common + rare):
                return True

        if model_id in self._nicholas_model_ids():
            return True

        # Gold coins are honoured here, from the toggle -- never by writing into a list.
        if config.loot_gold_coins and self._is_gold_coin(item_id):
            return True

        if self._rarity_wants(item_id):
            return True

        return matcher.any_match(self.active_filters(), item_id, model_id)

    def describe_model(self, model_id: int) -> str:
        """What the CATALOG believes model ``model_id`` is. Names the entry, category and group."""
        from ..item_catalog import catalog as catalog_data

        entry = catalog_data.by_model_id(int(model_id))
        if entry is not None:
            where = "%s / %s" % (entry.category, entry.group) if entry.group else entry.category
            return "%s  (%s, model %d)" % (entry.name, where, model_id)
        material = material_data.material(int(model_id))
        if material is not None:
            return "%s  (material, model %d)" % (material.name, model_id)
        return "model %d -- NOT IN THE CATALOG" % model_id

    def diagnostics(self, agent_id: int, item_id: int, model_id: int) -> list[str]:
        """A full printable report for one item: what was read, and every reason with its verdict."""
        from Py4GWCoreLib.Item import Item

        lines: list[str] = []

        def read(label, getter):
            try:
                lines.append("  %-26s %s" % (label, getter()))
            except Exception as exc:
                lines.append("  %-26s !! %s: %s" % (label, type(exc).__name__, exc))

        lines.append("=" * 68)
        lines.append("LOOT DIAGNOSTICS  agent=%d item=%d model=%d" % (agent_id, item_id, model_id))
        lines.append("=" * 68)
        lines.append("-- what the game reports --")
        read("name ready", lambda: Item.IsNameReady(item_id))
        read("name", lambda: Item.GetName(item_id))
        read("model id", lambda: Item.GetModelID(item_id))
        read("item type", lambda: Item.GetItemType(item_id))
        read("rarity", lambda: Item.Rarity.GetRarity(item_id))
        read("value", lambda: Item.Properties.GetValue(item_id))
        read("quantity", lambda: Item.Properties.GetQuantity(item_id))
        read("is weapon / armor", lambda: (Item.IsWeapon(item_id), Item.IsArmorType(item_id)))
        read("is material / rare", lambda: (Item.Type.IsMaterial(item_id), Item.Type.IsRareMaterial(item_id)))
        read("owner", lambda: __import__("Py4GWCoreLib.Agent", fromlist=["Agent"])
             .Agent.GetItemAgentOwnerID(agent_id) if agent_id else "(bag item)")

        lines.append("-- what the CATALOG says that model is --")
        lines.append("  %s" % self.describe_model(model_id))

        config = self.live
        lines.append("-- the live configuration --")
        lines.append("  master enabled             %s" % config.enabled)
        lines.append("  profile                    %s" % (config.profile or "(none)"))
        lines.append("  rarities                   white=%s blue=%s purple=%s gold=%s green=%s coins=%s"
                     % (config.loot_whites, config.loot_blues, config.loot_purples,
                        config.loot_golds, config.loot_greens, config.loot_gold_coins))
        for label, values in (("hand list models", config.enabled_model_ids),
                              ("salvage targets", config.salvage_target_ids),
                              ("dye colours", config.enabled_dye_colors),
                              ("script-added models", config.added_model_ids),
                              ("script-added drops", config.added_item_ids),
                              ("blacklisted models", config.blacklist_model_ids),
                              ("vetoed item types", config.blacklist_item_types),
                              ("suppressed drops", config.blacklist_item_ids)):
            lines.append("  %-26s %d entries%s" % (label, len(values),
                                                   "  <-- CONTAINS THIS MODEL"
                                                   if model_id in values else ""))
        lines.append("  %-26s %d" % ("active filters", len(self.active_filters())))

        lines.append("-- resolution (HAS-ANY; only the blacklist vetoes) --")
        for reason, holds in self.explain(agent_id, item_id, model_id):
            lines.append("  [%s] %s" % ("x" if holds else " ", reason))
        lines.append("-- VERDICT: %s --" % ("WANTED" if self.wants(agent_id, item_id, model_id)
                                            else "NOT WANTED"))
        return lines

    def print_diagnostics(self, agent_id: int, item_id: int, model_id: int) -> None:
        """Print the report to the Py4GW console, one line at a time so nothing is truncated."""
        for line in self.diagnostics(agent_id, item_id, model_id):
            _log(line)

    def explain(self, agent_id: int, item_id: int, model_id: int) -> list[tuple[str, bool]]:
        """``[(reason, holds), ...]`` -- why this drop is, or is not, wanted.

        Resolution is HAS-ANY: **only the blacklist vetoes**, and any single positive reason is
        enough. That is by design, but it is opaque without this -- "I turned purples off and it
        still took a purple" is answered by seeing that *Salvages to* wanted it for what it breaks
        down into, which has nothing to do with its rarity.
        """
        from Py4GWCoreLib.Item import Item

        config = self.live
        agent_id, model_id = int(agent_id), int(model_id)
        out: list[tuple[str, bool]] = []

        # State the two exclusions that happen BEFORE any rule is consulted, so nothing is
        # silently removed from consideration.
        try:
            from Py4GWCoreLib.Agent import Agent
            from Py4GWCoreLib.GlobalCache.WhiteboardLocks import is_loot_lock_blocked
            from Py4GWCoreLib.Player import Player

            owner = Agent.GetItemAgentOwnerID(agent_id) if agent_id else 0
            mine = Player.GetAgentID()
            if owner not in (0, mine):
                out.append(("assigned to someone else -- not offered at all", True))
                return out
            if config.respect_loot_lock and owner == 0 and is_loot_lock_blocked(agent_id):
                out.append(("claimed by another account (loot lock) -- not offered at all", True))
                return out
        except Exception:
            pass

        blacklisted = agent_id in config.blacklist_item_ids or model_id in config.blacklist_model_ids
        out.append(("blacklisted (vetoes everything else)", blacklisted))
        if blacklisted:
            return out
        type_vetoed = self._type_vetoed(item_id)
        out.append(("item type %s is vetoed (vetoes everything else)" % self.type_name(item_id)
                    if type_vetoed else "item type is vetoed", type_vetoed))
        if type_vetoed:
            return out

        out.append(("added by a script, this drop", agent_id in config.added_item_ids))
        out.append(("added by a script, this model", model_id in config.added_model_ids))

        # Name the entry. "on a hand list" without saying WHICH is unactionable -- and when the
        # named entry is obviously not the item in front of you, that is the catalog being wrong
        # about a model id, which is the only way to see it.
        on_list = self.on_hand_list(item_id, model_id)
        if on_list:
            out.append(("on a hand list: %s" % self.describe_model(model_id), True))
        elif model_id in config.enabled_model_ids:
            # Same number, different item. Say which, or this looks like a broken list.
            out.append(("hand list has %s, but this item is not that kind (%s) -- the model id is "
                        "shared across item types"
                        % (self.describe_model(model_id), self.hand_list_kind(model_id)), False))
        else:
            out.append(("on a hand list", False))

        wanted_dye = False
        if config.enabled_dye_colors and dye_data.is_dye(item_id):
            wanted_dye = dye_data.color_of(item_id) in config.enabled_dye_colors
        out.append(("a dye colour you want", wanted_dye))

        salvage_hit = ""
        if config.salvage_target_ids:
            common, rare = material_data.salvages_into(model_id)
            for candidate in common + rare:
                if candidate in config.salvage_target_ids:
                    material = material_data.material(candidate)
                    salvage_hit = material.name if material else str(candidate)
                    break
        out.append(("salvages into %s" % salvage_hit if salvage_hit else "salvages into something you want",
                    bool(salvage_hit)))

        out.append(("this week's Nicholas item", model_id in self._nicholas_model_ids()))
        out.append(("gold coins", bool(config.loot_gold_coins and self._is_gold_coin(item_id))))

        rarity_names = (("loot_whites", "white", Item.Rarity.IsWhite),
                        ("loot_blues", "blue", Item.Rarity.IsBlue),
                        ("loot_purples", "purple", Item.Rarity.IsPurple),
                        ("loot_golds", "gold", Item.Rarity.IsGold),
                        ("loot_greens", "green", Item.Rarity.IsGreen))
        for attribute, label, check in rarity_names:
            try:
                is_that = bool(check(item_id))
            except Exception:
                is_that = False
            if is_that:
                out.append(("rarity: it is %s, and %s are on" % (label, label),
                            bool(getattr(config, attribute))))
                break

        for rule in self.active_filters():
            out.append(("filter '%s'" % rule.name, matcher.matches(rule, item_id, model_id)))
        return out

    # ------------------------------------------------------------------ the query surface

    def _candidates(self, distance: float) -> list[int]:
        """Nearby ground items this character may take, contention respected."""
        from Py4GWCoreLib.Agent import Agent
        from Py4GWCoreLib.AgentArray import AgentArray
        from Py4GWCoreLib.GlobalCache.WhiteboardLocks import is_loot_lock_blocked
        from Py4GWCoreLib.Player import Player
        from Py4GWCoreLib.Routines import Routines

        if not Routines.Checks.Map.MapValid():
            return []
        array = AgentArray.Filter.ByDistance(AgentArray.GetItemArray(), Player.GetXY(), distance)
        player_agent_id = Player.GetAgentID()
        out: list[int] = []
        for agent_id in array:
            if not Agent.IsValid(agent_id):
                continue
            owner_id = Agent.GetItemAgentOwnerID(agent_id)
            if owner_id != player_agent_id and owner_id != 0:
                continue
            # Unassigned drops are contended. The lock belongs to the pickup path; we only read
            # it -- and only when you have left that switched on.
            if self.live.respect_loot_lock and owner_id == 0 and is_loot_lock_blocked(agent_id):
                continue
            out.append(agent_id)
        return out

    @frame_cache(category="LootFilters", source_lib="GetLootArray")
    def GetLootArray(self, distance: float | None = None) -> list[int]:
        """Nearby drops worth picking up, nearest first. Cached per frame.

        The dead ``multibox_loot`` and ``allow_unasigned_loot`` parameters are gone: cross-account
        coordination is the loot lock, always consulted, and unassigned drops are always eligible.
        """
        # The master switch gates everything, before any work at all: a disabled feature costs nothing.
        if not self.live.enabled:
            return []

        from Py4GWCoreLib.Agent import Agent
        from Py4GWCoreLib.AgentArray import AgentArray
        from Py4GWCoreLib.enums import Range
        from Py4GWCoreLib.Item import Item
        from Py4GWCoreLib.Player import Player

        search = float(Range.SafeCompass.value if distance is None else distance)
        self._check_map()

        wanted: list[int] = []
        for agent_id in self._candidates(search):
            item_agent = Agent.GetItemAgentByID(agent_id)
            if item_agent is None:
                continue
            item_id = item_agent.item_id
            if self.wants(agent_id, item_id, Item.GetModelID(item_id)):
                wanted.append(agent_id)
        return AgentArray.Sort.ByDistance(wanted, Player.GetXY())

    def HasLoot(self, distance: float | None = None) -> bool:
        """Whether anything nearby is worth grabbing, without building a list to look at."""
        return bool(self.GetLootArray(distance))

    def IsWanted(self, agent_id: int) -> bool:
        """Whether one specific drop is still wanted."""
        from Py4GWCoreLib.Agent import Agent
        from Py4GWCoreLib.Item import Item

        item_agent = Agent.GetItemAgentByID(agent_id)
        if item_agent is None:
            return False
        item_id = item_agent.item_id
        return self.wants(agent_id, item_id, Item.GetModelID(item_id))

    # ------------------------------------------------------------------ driving

    def register(self) -> None:
        """Register the data-phase pass and declare it to the perf monitor."""
        try:
            import PyCallback

            from Py4GWCoreLib.py4gwcorelib_src.Profiling import ProfilingRegistry

            PyCallback.PyCallback.RemoveByName(_CB_NAME)  # idempotent across reloads
            PyCallback.PyCallback.Register(_CB_NAME, PyCallback.Phase.Data, self._pass,
                                           priority=99, context=PyCallback.Context.Update)
            ProfilingRegistry().register(_CB_NAME)
            self._registered = True
        except Exception as exc:
            _log("callback registration error: %s" % exc)

    def unregister(self) -> None:
        try:
            import PyCallback

            PyCallback.PyCallback.RemoveByName(_CB_NAME)
        except Exception:
            pass
        self._registered = False

    def _pass(self) -> None:
        """Profiler-wrapped, so the cost is attributable when a capture is active."""
        try:
            from Py4GWCoreLib.py4gwcorelib_src.Profiling import ProfilingRegistry

            registry = ProfilingRegistry()
            if registry.enabled:
                registry.runcall_scope("widgets", "%s:data" % _CB_NAME, self._do_pass)
                return
        except Exception:
            pass
        self._do_pass()

    def _do_pass(self) -> None:
        if self.live.enabled:
            self._check_map()
