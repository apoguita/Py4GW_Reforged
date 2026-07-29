"""The Loot Filters configuration -- one class, instantiated twice.

**A script NEVER persists.** Whatever a script does lives in memory and never reaches disk. That is
the invariant everything here rests on, and the doubling is how it is enforced structurally rather
than by discipline: the feature holds a **persisted** instance and a **live** instance of this same
class. The user writes persisted; a script writes live; they are different objects, so a live change
physically cannot reach the user's configuration.

Everything else follows mechanically:

* live starts as a copy of persisted;
* reset is replacing live with a fresh copy;
* "is a script changing things?" is comparing the two;
* "what is it changing?" is diffing them;
* a restart is a reset, because live never existed on disk.

**Id-keyed entries are session-only.** Agent and item ids are per-instance: they mean nothing after a
map change, and reusing one would want or suppress an unrelated drop. They are never persisted and are
cleared on map change. Model ids are stable and persist normally.
"""

from dataclasses import dataclass
from dataclasses import field

from ..item_catalog.nicholas import NicholasSelection


@dataclass
class LootConfig:
    """One complete configuration. Used for both the persisted and the live instance."""

    enabled: bool = True

    # -- rarity toggles. Gold coins is independent and combinable with any rarity. --
    loot_whites: bool = False
    loot_blues: bool = False
    loot_purples: bool = False
    loot_golds: bool = False
    loot_greens: bool = False
    loot_gold_coins: bool = False

    # -- hand-crafted lists: which shipped catalog entries are on --
    enabled_model_ids: set[int] = field(default_factory=set)
    #: Dyes share one model id, so a dye is named by colour and matched on item type + colour.
    enabled_dye_colors: set[int] = field(default_factory=set)
    #: Materials wanted for what an item BREAKS DOWN INTO, as opposed to the material itself dropping.
    salvage_target_ids: set[int] = field(default_factory=set)

    #: Nicholas: the current week by default, plus any dates the user entered.
    #: Nicholas weeks being watched. EMPTY by default -- opt in.
    #:
    #: This used to default to the rolling current week, which meant a config nobody had touched
    #: was already selecting an item for pickup. Nothing may be selected without you activating it.
    nicholas: tuple[NicholasSelection, ...] = ()

    # -- direct additions. A script may add these; it may not create structure. --
    added_model_ids: set[int] = field(default_factory=set)
    added_item_ids: set[int] = field(default_factory=set)      # session-only

    # -- the blacklist: an absolute veto, and where failed pickups are recorded --
    blacklist_model_ids: set[int] = field(default_factory=set)
    #: Item TYPES never to take -- "never an offhand", whatever else wants it.
    #:
    #: A veto, not a preference. The positive rules are HAS-ANY and cannot express "not this":
    #: turning a rarity off only removes rarity as a REASON, it never stops a hand list, a salvage
    #: target or a filter from taking the thing anyway. This is the only shape that can.
    blacklist_item_types: set[int] = field(default_factory=set)

    #: Skip unassigned drops another account has claimed. Cross-account coordination, and YOURS to
    #: turn off -- it silently removed drops before anything else got a look, which is exactly the
    #: kind of hidden gate this tool should not have.
    respect_loot_lock: bool = True
    blacklist_item_ids: set[int] = field(default_factory=set)  # session-only

    #: The profile in use. One at a time; the filters come from the Loot Filter Factory.
    profile: str = ""

    def copy(self) -> "LootConfig":
        """A fully independent copy -- seeds live from persisted, and resets it back."""
        return LootConfig(
            enabled=self.enabled,
            loot_whites=self.loot_whites, loot_blues=self.loot_blues,
            loot_purples=self.loot_purples, loot_golds=self.loot_golds,
            loot_greens=self.loot_greens, loot_gold_coins=self.loot_gold_coins,
            enabled_model_ids=set(self.enabled_model_ids),
            enabled_dye_colors=set(self.enabled_dye_colors),
            salvage_target_ids=set(self.salvage_target_ids),
            nicholas=tuple(self.nicholas),
            added_model_ids=set(self.added_model_ids),
            added_item_ids=set(self.added_item_ids),
            blacklist_model_ids=set(self.blacklist_model_ids),
            blacklist_item_types=set(self.blacklist_item_types),
            respect_loot_lock=self.respect_loot_lock,
            blacklist_item_ids=set(self.blacklist_item_ids),
            profile=self.profile,
        )

    def clear_session_ids(self) -> bool:
        """Drop every agent/item-id entry. Correctness, not policy: those ids do not survive a map."""
        had = bool(self.added_item_ids or self.blacklist_item_ids)
        self.added_item_ids.clear()
        self.blacklist_item_ids.clear()
        return had

    _RARITY = {"white": "loot_whites", "blue": "loot_blues", "purple": "loot_purples",
               "gold": "loot_golds", "green": "loot_greens", "gold_coins": "loot_gold_coins"}

    def rarity_enabled(self, name: str) -> bool:
        attribute = self._RARITY.get(name)
        return bool(getattr(self, attribute)) if attribute else False

    def set_rarity(self, name: str, value: bool) -> None:
        attribute = self._RARITY.get(name)
        if attribute:
            setattr(self, attribute, bool(value))

    # ------------------------------------------------------------------ diffing

    def differs_from(self, other: "LootConfig") -> bool:
        return bool(self.diff(other))

    def diff(self, other: "LootConfig") -> list[str]:
        """What differs, for the live-state label and its detail window.

        ``self`` is live and ``other`` is persisted, so the wording reads as what changed.
        """
        out: list[str] = []
        if self.enabled != other.enabled:
            out.append("looting: %s (saved: %s)" % ("on" if self.enabled else "off",
                                                    "on" if other.enabled else "off"))
        for label, name in (("whites", "white"), ("blues", "blue"), ("purples", "purple"),
                            ("golds", "gold"), ("greens", "green"), ("gold coins", "gold_coins")):
            mine, theirs = self.rarity_enabled(name), other.rarity_enabled(name)
            if mine != theirs:
                out.append("%s: %s (saved: %s)" % (label, "on" if mine else "off",
                                                   "on" if theirs else "off"))
        for label, mine, theirs in (
            ("catalog entries", self.enabled_model_ids, other.enabled_model_ids),
            ("dye colours", self.enabled_dye_colors, other.enabled_dye_colors),
            ("salvage targets", self.salvage_target_ids, other.salvage_target_ids),
            ("added models", self.added_model_ids, other.added_model_ids),
            ("blacklisted models", self.blacklist_model_ids, other.blacklist_model_ids),
        ):
            added, removed = len(mine - theirs), len(theirs - mine)
            if added or removed:
                parts = ([("+%d" % added)] if added else []) + ([("-%d" % removed)] if removed else [])
                out.append("%s: %s" % (label, " ".join(parts)))
        if self.added_item_ids:
            out.append("specific drops wanted: %d" % len(self.added_item_ids))
        if self.blacklist_item_ids:
            out.append("drops suppressed this session: %d" % len(self.blacklist_item_ids))
        if self.nicholas != other.nicholas:
            out.append("Nicholas weeks: %d (saved: %d)" % (len(self.nicholas), len(other.nicholas)))
        if self.profile != other.profile:
            out.append("profile: %s (saved: %s)" % (self.profile or "(none)", other.profile or "(none)"))
        return out
