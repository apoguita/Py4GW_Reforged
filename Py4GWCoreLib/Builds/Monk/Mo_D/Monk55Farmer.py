from __future__ import annotations

import time

import PySystem
from typing import TYPE_CHECKING

from Py4GWCoreLib import Agent, ConsoleLog, GLOBAL_CACHE, Profession, Range, Routines, Utils
from Py4GWCoreLib.AgentArray import AgentArray
from Py4GWCoreLib.Player import Player
from Py4GWCoreLib import BuildMgr, SkillBar

MODULE_NAME = "Monk55Farmer"
from Py4GWCoreLib.Player import Player

if TYPE_CHECKING:
    from Py4GWCoreLib.BuildMgr import BuildCoroutine

# Skill IDs for the 55 Monk farmer. Hardcoded rather than Skill.GetID("..."),
# which returns 0 on a name miss - silently, and 0 never casts.
PROT_SPIRIT_ID = 245  # Protective Spirit
HEALING_BREEZE_ID = 288  # Healing Breeze
# NOTE on the two regen options. This build accepts either, and the choice is
# the player's, but they are not equivalent and that matters per-area:
#
# - Mystic Regeneration (1516): 15s duration on a 10s recharge, 15 energy, and
#   it scales - +4 regen per maintained enchantment, up to 8 enchants. On a
#   kit this enchantment-heavy (PS, MR, shields, Blessed Aura) it is worth far
#   more than HB, and it is the sustain that carries hard fights.
#
# - Healing Breeze (288): flat +9 at rank 20, 15s on a 5s recharge, 10 energy.
#   Cheap and reliable, and better where incoming damage is light enough that
#   flat regen keeps pace.
#
# In Gates of Kryta NM, MR is the better pick: the ball-spot proximity pack is
# the largest fight in the run and flat 9 does not hold against it. HB is left
# in place because it can be the stronger choice in other areas - it is not
# being tuned for here, and swapping it is a bar change, not a code change.
MYSTIC_REGEN_ID = 1516  # Mystic Regeneration
SHIELDING_HANDS_ID = 299  # Shielding Hands
SHIELD_OF_ABSORPTION_ID = 1399  # Shield of Absorption
CASTIGATION_SIGNET_ID = 2006  # Castigation Signet
SYMBOL_OF_WRATH_ID = 247  # Symbol of Wrath
SHIELD_OF_JUDGMENT_ID = 262  # Shield of Judgment
LIGHT_OF_DELDRIMOR_ID = 2212  # Light of Deldrimor
BALTHAZARS_SPIRIT_ID = 242  # Balthazar's Spirit
ESSENCE_BOND_ID = 250  # Essence Bond
BLESSED_AURA_ID = 256  # Blessed Aura
BLESSED_SIGNET_ID = 297  # Blessed Signet
BALTHAZARS_AURA_ID = 272  # Balthazar's Aura
RADIATION_FIELD_ID = 2414  # Radiation Field
PAIN_INVERTER_ID = 2418  # Pain Inverter
RAY_OF_JUDGMENT_ID = 830  # Ray of Judgment (Elite Spell)
JUDGMENT_STRIKE_ID = 3425  # Judgment Strike (Elite Melee Attack)
MEND_AILMENT_ID = 277  # Mend Ailment
DISMISS_CONDITION_ID = 1691  # Dismiss Condition
SMITE_CONDITION_ID = 2004  # Smite Condition
JUDGES_INTERVENTION_ID = 1390  # Judge's Intervention (Smiting Prayers)


class Monk55Farmer(BuildMgr):
    """
    55 HP Monk Farmer build with coordinated protection shields.

    This build coordinates Shielding Hands and Shield of Absorption to prevent
    overlap - only one protection shield is maintained at a time. Shielding Hands
    is preferred due to its longer duration, with Shield of Absorption used as
    a fallback when Shielding Hands is recharging.

    Supported skill variants:
    - Healing Breeze or Mystic Regeneration for regeneration
    - Mend Ailment, Dismiss Condition, or Smite Condition for condition removal

    Note: this is the D/Mo bar. The skills are all Monk-primary, so the bar is
    selected on Monk primary + Dervish secondary plus the template code above.
    The Mo/any variant is a separate build to be added once this one is working.
    """

    ENCHANT_REFRESH_MS = 5000  # floor for the refresh window
    ENCHANT_REFRESH_FRACTION = 0.45  # recast with this much of the duration left
    # Protective Spirit runs ~24s on a ~0.25s recharge, so the fraction rule
    # above would recast it with ~10.8s still up - wasting 11 of every 24
    # seconds, and evicting a shield or regeneration cast each time because PS
    # sits first in the ladder. At 10 energy a cast it also burns the pool the
    # The value below is SAFETY MARGIN, not a target. With a ~0.25s recharge
    # there is always time to react, but a PS lapse is what kills this monk: it
    # caps every single hit at 10% of max health, so "no PS" means full hits
    # landing. A 2s window is only safe while the ladder is idle - during a pack
    # the tick is shared with cover, regen and the energy engines, and 2s was
    # observed running close to dropping. 5s of headroom costs almost nothing in
    # recasts and covers several crowded ticks.
    #
    # Do not go much above this: past ~8000ms the recast creeps toward the point
    # where a busy tick cannot land it in time.
    PROT_SPIRIT_REFRESH_MS = 5000
    # Mystic Regeneration gets an override for a stronger reason than PS: at 15
    # energy it is the most expensive cast on the bar, and with a 15s duration on
    # a 10s recharge the shared fraction rule is not merely wasteful, it is
    # impossible. 15s x 0.45 = 6.75s, so the ladder would try to recast ~8.2s
    # into the enchant - while the recharge is still ~1.8s from ready. The cast
    # cannot land, so the tick is spent on a doomed attempt and the ladder has
    # learned nothing about when it will actually be able to cast.
    #
    # The only window where MR is both recharging-done and still up is t=10s to
    # t=15s. 2000ms remaining (t=13s) sits safely inside it, with room for the
    # per-skill throttle. Do NOT raise this above ~4000ms: at 4000ms remaining
    # the cast would land at t=11s, barely after the recharge, and anything
    # tighter than 2000ms starts firing before the window opens.
    # A lapse here is what kills the monk, so keep real headroom rather than
    # recasting the instant it looks due. The hard ceiling is the recharge
    # window above: the recast has to land between t=10s and t=15s.
    #
    # 3000, not 5000. At 5000 the cast was scheduled for exactly t=10s - the
    # instant the 10s recharge clears, with no margin - and the live log showed
    # the regen lapsing 3 times despite energy being available. 3000 puts the
    # recast at t=12s, two seconds inside the window. Do NOT go above 5000: that
    # tries to cast before the recharge is done, the exact bug this override
    # exists to prevent.
    MYSTIC_REGEN_REFRESH_MS = 3000
    ENCHANT_DURATION_FLOOR_MS = 8000  # assume at least this long before trusting data

    # ---- Timing dial ---------------------------------------------------------
    #
    # One knob for how fast the stack goes up. Set to 0.25 to run 75% faster than
    # the measured cast times; raise it toward 1.0 to slow back down. Every
    # per-skill delay below is multiplied by this, so tuning is one edit rather
    # than a hunt through the cast sites.
    #
    # Deliberately erring fast: Protective Spirit is the only thing keeping a 55
    # monk alive, and a stack that arrives late is the same as no stack at all.
    # A redundant early cast costs a global cooldown; a late one costs the run.
    TIMING_SCALE = 0.25

    # Base per-skill delays, in the same units as the measured cast times
    # (~0.25s for Protective Spirit, Mystic Regeneration and Shielding Hands;
    # ~1s for Shield of Absorption). These are pre-scale reference values.
    CAST_COOLDOWN_MS = 750  # per-skill throttle between cast attempts
    AFTERCAST_FAST_MS = 300
    AFTERCAST_ABSORPTION_MS = 1000

    # Casts allowed in a single tick. Three is what the pre-cast stack needs:
    # Protective Spirit, then regen, then the shield covering the spirit. With
    # fewer, the tick returns while the monk is still unprotected - which is the
    # exact failure Protective Spirit cannot cover for.
    MAX_CASTS_PER_TICK = 3
    # Replace cover once the current shield has this much life left. This is the
    # handoff window that keeps the monk covered through the swap: Shield of
    # Absorption is held until this much remains, then Protective Spirit and
    # Shielding Hands go on top of it before it actually drops.
    SHIELD_REFRESH_SECONDS = 1.5
    # Shielding Hands duration, used only for the local expiry clock. SH is a buff
    # with no readable duration, so this is measured, not read: 9s with the +20%
    # weapon. A stale clock is self-correcting - presence still gates on it.
    SHIELDING_HANDS_DURATION_MS = 9000.0
    # Aggro radius for bringing the protection stack up.
    #
    # This matches the MoveAndKill / VanquishNode clear-area bubble, which both
    # default to Range.Spirit.value (2500). Matching it matters: those nodes pull
    # mobs from anywhere inside that bubble, so waiting for a shorter radius means
    # the monk is already being pulled before the kit is up. Range.Spellcast
    # (1248) was half the bubble and therefore roughly a full cast too late.
    AGGRO_RADIUS = Range.Spirit.value  # 2500
    # PS pre-cast trigger. Wider than AGGRO_RADIUS, and uses _threat_count rather
    # than the aggroed-only predicate - AGGRO_RADIUS fires PS at the same instant
    # the pull bubble can grab, which is too late for a pre-cast.
    THREAT_RADIUS = Range.SafeCompass.value  # 4800
    # Kept separate from AGGRO_RADIUS: the bubble is deliberately generous, but
    # the damage skills still need a target we can actually hit.
    ENGAGE_RADIUS = Range.Spellcast.value  # 1248
    # REMOVED: CONDITION_TOLERANCE. It held Smite Condition until a second
    # degen stacked, so a single poison or bleed was left on the monk. That was
    # cost-management for a spell that also does 126 flat holy damage to GoK's
    # undead - more than the SoJ it was deferred behind. With the energy gate
    # doing the real cost control, a lone degen is now cleansed as soon as the
    # pool can afford it. Do not reintroduce a wait here: the cleanse gate is
    # the energy test, and nothing else.

    # How long PS stays wanted after the last hostile leaves AGGRO_RADIUS.
    # See _ps_wanted.
    PS_LINGER_S = 2.0

    def __init__(self, match_only: bool = False):
        super().__init__(
            name="55 Monk Farmer",
            required_primary=Profession.Monk,
            required_secondary=Profession.Dervish,
            template_code="Owoj4wP6KO1D27ddlY9vHGE5BA",
            required_skills=[
                PROT_SPIRIT_ID,
                SHIELDING_HANDS_ID,
                SHIELD_OF_ABSORPTION_ID,
                BALTHAZARS_SPIRIT_ID,
            ],
            optional_skills=[
                SYMBOL_OF_WRATH_ID,
                CASTIGATION_SIGNET_ID,
                HEALING_BREEZE_ID,
                MYSTIC_REGEN_ID,
                SHIELD_OF_JUDGMENT_ID,
                LIGHT_OF_DELDRIMOR_ID,
                MEND_AILMENT_ID,
                DISMISS_CONDITION_ID,
                SMITE_CONDITION_ID,
                ESSENCE_BOND_ID,
                JUDGES_INTERVENTION_ID,
                # Monk enchantments last longer, which directly stretches PS
                # (~24s), MR and the shields.
                #
                # Scales with DIVINE FAVOR, not Protection Prayers. At 5 DF that
                # is 18% - see the wiki progression table (rank 0=10 up to
                # rank 21=45). The 35% figure is the rank-15 value, not the cap;
                # the cap is 45% at rank 21. Do not assume a high number here -
                # the live log showed PS reaching 29.1s on a 24s enchant, which is
                # ~1.21x and consistent with 18% plus rounding, not with 27-35%.
                #
                # The refresh windows below are absolute milliseconds, so a longer
                # real duration means they are reached later in practice - this
                # buys time rather than needing a retune.
                BLESSED_AURA_ID,
                # ---- Candidate additions, all opt-in, none wired into the
                # ladder yet. Listed so the template can carry them; each still
                # needs an upkeep/cast site before it will ever be used.
                #
                # Energy engine, complements Balthazar's Spirit: 3 energy per
                # maintained enchantment, capped at 24 - which also rewards
                # keeping shields and PS up.
                BLESSED_SIGNET_ID,
                # 8s adjacent-foe holy damage; pairs with SoJ-style disruption.
                BALTHAZARS_AURA_ID,
                # 5s health degeneration on nearby foes. Ward, so it is
                # cancellation-dependent rather than a straight damage slot.
                RADIATION_FIELD_ID,
                # Hex: foe takes 100...140% of the damage it deals back. Pairs
                # with a tanking setup where the monk is the one drawing hits.
                PAIN_INVERTER_ID,
                # Elite alternative to Shield of Judgment. Same target, same
                # knockdown intent, different numbers - pick one, not both.
                RAY_OF_JUDGMENT_ID,
                # Elite melee attack; only meaningful on a hammer build, where
                # it would replace part of the damage tier rather than add to it.
                JUDGMENT_STRIKE_ID,
            ],
        )

        if match_only:
            return

        self.SetSkillCastingFn(self._run_local_skill_logic)
        # Out of combat is a separate tick, not a no-op. HeroAI routes to
        # ProcessOOC() whenever in_aggro is false, and ProcessOOC() falls
        # through to the local skill handler only when no OOC handler is
        # registered - so without this the engines were maintained only during
        # fights, and a monk standing in an explorable map with nothing aggroed
        # never picked Balthazar's Spirit up at all.
        self.SetOOCFn(self._run_ooc_upkeep)

        # Per-skill cast throttle and learned enchant durations. The original
        # single _last_shield_cast_ms could only ever describe one shield, and
        # the engine needed its own upkeep that no timed rule could express.
        self._last_cast_ms: dict[int, float] = {}
        self._observed_remaining_ms: dict[int, float] = {}
        # Local expiry clock for Shielding Hands. SH is a BUFF, and BuffType has no
        # duration field, so its remaining time is unreadable - but we still need
        # to know when it drops, or SoA never gets refilled during the overlap.
        # Seeded at cast time and counted down from the known ~8s duration.
        self._shield_expiry_ms: dict[int, float] = {}
        # When we first observed an SH buff we did not cast, so a re-based clock
        # measures from the observation rather than from the (later) moment the
        # stale clock was noticed.
        self._shield_seen_ms: dict[int, float] = {}
        # While travelling unengaged only the engine is cast; this escalates to
        # full upkeep the moment a foe is in spellcast range.
        self._engaged: bool = False
        # A fresh Protective Spirit must be covered by a shield cast after it,
        # otherwise the spirit is wasted on an already-shielded monk.
        self._protection_pair_pending: bool = False
        # Per-tick cast intent, so a skill issued once in a tick is not offered
        # again on the next pass of the same tick.
        self._pending_regen: bool = False
        self._pending_cover: int = 0
        # Latch for the PS threat gate: monotonic ms until which PS stays wanted
        # after the last hostile left AGGRO_RADIUS. 0.0 = disarmed.
        self._ps_latch_until_ms: float = 0.0

    def _ps_wanted(self, now_ms: float) -> bool:
        """True when Protective Spirit should be up - threat, or a live latch.

        Replaces the previous behaviour, which maintained PS continuously. That
        was deliberate (see the unengaged branch in _run_local_skill_logic: an
        unengaged stretch used to let PS expire entirely, and the next pull then
        started uncapped), but it meant every step between fights re-cast a
        ~24s cap against an empty map. On a long farming run that is constant
        energy for nothing, and it is the same loot-timeout pressure the Ritualist
        build was fixed for.

        The latch keeps the fix and drops the waste: a hostile inside
        THREAT_RADIUS arms it, and once armed PS stays wanted for PS_LINGER_S
        after the LAST hostile is seen. So a mob that dies just before the cap
        would lapse does not drop it, and the monk arrives at the next mob
        already capped - but walking a genuinely empty stretch finally costs
        nothing.

        AGGRO_RADIUS, NOT THREAT_RADIUS. This was THREAT_RADIUS (4800) in the
        first version and it never gated anything: _threat_count counts ALL
        hostiles including non-aggroed ones, and a farming zone almost always
        has something inside 4800, so the latch was permanently armed. The
        visible symptom was PS firing ahead of the permanent enchants on every
        tick, because ps_due was always true and the engine loop below it was
        skipped every time.

        THREAT_RADIUS is the right radius for a pre-cast on approach - that is
        what the in-combat ladder uses it for, and it should stay wide so PS
        lands before the pull bubble grabs. It is the wrong radius for "are we
        in a fight at all", which is a much stricter question and wants the
        same 2500 the pull bubble itself uses.

        AGGRO_RADIUS is also self-consistent: the bubble pulls from inside 2500,
        so "no hostile inside 2500" means we are not committed and there is
        nothing to cap.

        Fails CLOSED on an unreadable threat list - a false "safe" costs the
        monk. That asymmetry is only safe because the normal path is narrow;
        with a 4800 radius it masked the bug above.
        """
        try:
            threatened = self._threat_count(self.AGGRO_RADIUS) > 0
        except Exception:
            return True
        if threatened:
            self._ps_latch_until_ms = now_ms + (self.PS_LINGER_S * 1000.0)
            return True
        return now_ms < self._ps_latch_until_ms

    def _foe_count(self, max_distance: float) -> int:
        try:
            px, py = Player.GetXY()
            return len(Routines.Agents.GetFilteredEnemyArray(px, py, max_distance) or [])
        except Exception:
            return 0

    def _threat_count(self, max_distance: float) -> int:
        """Living hostile mobs within `max_distance`, including NOT-yet-aggroed.

        This is deliberately a different predicate from _foe_count, and the
        difference is the whole point.

        GetFilteredEnemyArray (via _foe_count) only returns foes already aggroed,
        which made PS fire at melee range. GetEnemyArray is the raw hostile list,
        so this sees mobs on approach. Range.Spirit would be too tight - the
        MoveAndKill pull bubble is already 2500, so PS would land after we're
        committed.
        """
        try:
            px, py = Player.GetXY()
            count = 0
            for agent_id in AgentArray.GetEnemyArray() or []:
                if not Agent.IsAlive(agent_id):
                    continue
                ax, ay = Agent.GetXY(agent_id)
                if Utils.Distance((px, py), (ax, ay)) <= max_distance:
                    count += 1
            return count
        except Exception:
            return 0

    def _symbol_of_wrath_active(self, max_distance: float) -> bool:
        """True when a foe in `max_distance` is already standing in a Symbol of Wrath.

        Symbol of Wrath is a ground-target AoE, so the effect is carried by the
        mobs caught in it, not by the caster. Testing the player would therefore
        always report False and the build would re-cast the symbol on every tick,
        burning the energy the rest of the bar needs.

        Reads the nearest foe we could actually target, so this is a real
        "is the symbol already doing work in this fight" test rather than a
        global one - a symbol dropped on a pack behind us does not suppress a
        fresh cast here.
        """
        try:
            target = self._nearest_foe_in_range(max_distance)
            return bool(target) and self._has_effect(target, SYMBOL_OF_WRATH_ID)
        except Exception:
            return False

    def _nearest_foe_in_range(self, max_distance: float) -> int:
        """Closest living foe within `max_distance`, or 0 when the area is clear."""
        try:
            px, py = Player.GetXY()
            foes = [
                agent_id
                for agent_id in (Routines.Agents.GetFilteredEnemyArray(px, py, max_distance) or [])
                if Agent.IsAlive(agent_id)
            ]
            if not foes:
                return 0
            return min(foes, key=lambda agent_id: Utils.Distance((px, py), Agent.GetXY(agent_id)))
        except Exception:
            return 0

    def _has_effect(self, agent_id: int, skill_id: int) -> bool:
        """Check if an agent has a specific effect."""
        try:
            return bool(GLOBAL_CACHE.Effects.HasEffect(agent_id, skill_id))
        except Exception:
            return False

    def _effect_remaining(self, agent_id: int, skill_id: int) -> float:
        """SECONDS left on a timed effect, 0.0 when not up.

        GetEffectTimeRemaining returns MILLISECONDS, not seconds. This was
        previously documented as returning seconds, and two call sites then
        multiplied by 1000 again - so every duration in the build was inflated
        1000x. The live log showed PS reporting 14127 for an enchant that is
        really 14.1 seconds old.

        The damage that followed was total rather than subtle. _observed_remaining_ms
        learned 24127 instead of ~24000 for a 24s enchant, which happened to
        still work; but for a 15s skill it learned ~15000 and compared that
        against a window of 2000 - fine. The break was in the shields, where a
        "5 second" shield measured 5000 "seconds" and never approached any
        refresh threshold, and in Mystic Regeneration, whose 15s duration read
        as 15000 and so was treated as permanently far from expiry. That is why
        the regen sat at 0 and was never recast, and the monk degened to death
        while a ready skill went unused.

        Seconds at the boundary, milliseconds everywhere inside. One conversion,
        one place.

        NOTE: this reads EFFECTS only. GetEffectTimeRemaining does not scan the
        buff bucket, and a BuffType has no timing field at all - so for a skill
        registered as a buff (Shielding Hands) this always returns 0.0. Use
        _has_effect for those; see _cover_remaining_ms.
        """
        try:
            if not GLOBAL_CACHE.Effects.HasEffect(agent_id, skill_id):
                return 0.0
            remaining_ms = GLOBAL_CACHE.Effects.GetEffectTimeRemaining(agent_id, skill_id)
            if not remaining_ms:
                return 0.0
            return float(remaining_ms) / 1000.0
        except Exception:
            return 0.0

    def _needs_recast(self, player_id: int, skill_id: int, now_ms: float) -> bool:
        """
        True when a timed enchant should be recast.

        Recasts on a learned window rather than a flat one, because a long
        enchant (Healing Breeze runs far longer than a shield) refreshed on a
        fixed schedule either wastes the cast or lapses mid-fight depending on
        which way the number happens to fall.
        """
        if not self._has_effect(player_id, skill_id):
            return True
        if not self._cooldown_ok(skill_id, now_ms):
            return False
        remaining_ms = self._effect_remaining(player_id, skill_id) * 1000.0
        if remaining_ms > self._observed_remaining_ms.get(skill_id, 0.0):
            # The first sighting after a cast is the full duration, so taking
            # the maximum converges on the real value within one enchant cycle.
            self._observed_remaining_ms[skill_id] = remaining_ms
        return remaining_ms < self._refresh_window_ms(skill_id)

    def _refresh_window_ms(self, skill_id: int) -> float:
        """How much life must be left on a timed enchant before we recast it.

        Most enchants use the shared learned-duration heuristic: recast once less
        than ENCHANT_REFRESH_FRACTION of the observed duration remains.

        That heuristic is wrong for any enchant whose duration is short relative
        to its recharge, because it can schedule the recast before the skill is
        even available. Protective Spirit and Mystic Regeneration both override
        it below.
        PS runs ~24s on a ~0.25s recharge, so the fraction rule recasts it with
        ~10.8s still up - over 11 wasted seconds in every 24s cycle. And since
        PS is first in the ladder, each of those early recasts evicts a shield,
        the regeneration, or a condition clear that would have been better spent.
        With a recharge this short relative to the duration there is no reason to
        refresh early at all: wait until PS is close to lapsing and spend the
        freed casts on the rest of the kit.

        The override is a remaining-time floor rather than a fraction, because
        the point is "PS is nearly gone", not "PS is at some proportion of a
        duration we would otherwise have to guess".
        """
        if skill_id == PROT_SPIRIT_ID:
            return float(self.PROT_SPIRIT_REFRESH_MS)
        if skill_id == MYSTIC_REGEN_ID:
            return float(self.MYSTIC_REGEN_REFRESH_MS)
        observed_ms = self._observed_remaining_ms.get(skill_id, 0.0)
        if observed_ms < self.ENCHANT_DURATION_FLOOR_MS:
            return float(self.ENCHANT_REFRESH_MS)
        return max(float(self.ENCHANT_REFRESH_MS), observed_ms * self.ENCHANT_REFRESH_FRACTION)

    def _aftercast(self, skill_id: int) -> int:
        """Scaled aftercast for `skill_id`, in milliseconds.

        Shield of Absorption is the one slow cast on the bar (~1s); everything
        else is ~0.25s. TIMING_SCALE compresses both, which is the dial to turn
        when the stack is arriving late in a pull.
        """
        base = (
            self.AFTERCAST_ABSORPTION_MS
            if skill_id == SHIELD_OF_ABSORPTION_ID
            else self.AFTERCAST_FAST_MS
        )
        return max(1, int(base * self.TIMING_SCALE))

    def _cooldown_ok(self, skill_id: int, now_ms: float) -> bool:
        """True when `skill_id` can actually be cast right now.

        Two separate conditions, and only the first used to be checked:

        1. The real game recharge. Routines.Checks.Skills.IsSkillIDReady reads
           skill.recharge == 0 from the live skillbar, so this reflects the true
           recharge timer. This was MISSING, which is the bug behind a live
           death: both shields dropped and neither was recastable, and the ladder
           had no idea. _preferred_cover saw both shields as "ready" because the
           only gate was our own throttle, offered one of them, and the cast
           could not land - every tick, for as long as the recharge ran. The monk
           spent the whole window believing it was covered while being hit with
           nothing up.

        2. A short per-skill throttle, so a single cast cannot be re-issued on
           consecutive ticks while its own aftercast is still resolving.

        Order matters: the recharge is checked first because it is the expensive
        failure. A throttle-only check reports "ready" for a skill that is
        genuinely on cooldown.
        """
        if not self._recharge_ready(skill_id):
            return False
        throttle_ms = self.CAST_COOLDOWN_MS * self.TIMING_SCALE
        return now_ms - self._last_cast_ms.get(skill_id, 0.0) >= throttle_ms

    def _recharge_ready(self, skill_id: int) -> bool:
        """True when the live skillbar reports no recharge on `skill_id`.

        Fails OPEN. If the skill is not on the bar, the lookup cannot resolve a
        slot, or the check raises, we assume it is castable and let the existing
        throttle and IsSkillEquipped checks decide. A false negative here would
        silently disable a skill the build is supposed to be using, which is
        worse than a wasted cast attempt.
        """
        try:
            if not self.IsSkillEquipped(skill_id):
                return True
            return bool(Routines.Checks.Skills.IsSkillIDReady(skill_id))
        except Exception:
            return True

    def _mark_cast(self, skill_id: int, now_ms: float) -> None:
        self._last_cast_ms[skill_id] = now_ms
        if skill_id == SHIELDING_HANDS_ID:
            self._shield_expiry_ms[skill_id] = now_ms + self.SHIELDING_HANDS_DURATION_MS
            self._shield_seen_ms.pop(skill_id, None)  # our cast is the anchor now

    def _soj_up_or_ready(self, player_id: int) -> bool:
        """True when Shield of Judgment is running or about to be."""
        if self._has_effect(player_id, SHIELD_OF_JUDGMENT_ID):
            return True
        try:
            slot = SkillBar.GetSlotBySkillID(SHIELD_OF_JUDGMENT_ID) or 0
        except Exception:
            return False
        return bool(slot) and Routines.Checks.Skills.IsSkillSlotReady(slot)

    def _core_survival_ok(self, player_id: int, now_ms: float) -> bool:
        """True when the survivability core is all up and safe.

        Protective Spirit, the bar's regeneration skill, and at least one
        protection shield. These are repaired first every tick, so a condition
        that refuses to clear can never starve the kit and quietly kill the monk.
        """
        if self.IsSkillEquipped(PROT_SPIRIT_ID) and self._needs_recast(player_id, PROT_SPIRIT_ID, now_ms):
            return False
        regen_skill_id = self._regen_skill_id()
        if regen_skill_id and self._needs_recast(player_id, regen_skill_id, now_ms):
            return False
        return not self._shield_handoff_due(player_id, now_ms)

    def _skill_cost_points(self, player_id: int, skill_id: int) -> float:
        """Effects-aware energy cost of `skill_id`, in energy points."""
        try:
            return float(Routines.Checks.Skills.GetEnergyCostWithEffects(skill_id, player_id) or 0)
        except Exception:
            return 0.0

    def _energy_points(self, player_id: int) -> float:
        """Current energy in points.

        Agent.GetEnergy reports a 0-1 fraction, so normalize defensively rather
        than assuming the unit: a silent mismatch here would make the damage
        energy gate always-true or always-false.
        """
        try:
            energy = float(Agent.GetEnergy(player_id) or 0.0)
            if 0.0 < energy <= 1.0:
                return energy * float(Agent.GetMaxEnergy(player_id) or 0)
            return energy
        except Exception:
            return 0.0

    def _core_reserve_points(self, player_id: int) -> float:
        """Energy the core set needs for a full refresh.

        Protective Spirit, the bar's regeneration skill, and the cheapest
        protection shield. This is what a damage cast has to leave behind.
        """
        cheapest_shield = min(
            (
                self._skill_cost_points(player_id, skill_id)
                for skill_id in (SHIELDING_HANDS_ID, SHIELD_OF_ABSORPTION_ID)
                if self.IsSkillEquipped(skill_id)
            ),
            default=0.0,
        )
        core = [PROT_SPIRIT_ID] if self.IsSkillEquipped(PROT_SPIRIT_ID) else []
        regen_skill_id = self._regen_skill_id()
        if regen_skill_id:
            core.append(regen_skill_id)
        return sum(self._skill_cost_points(player_id, skill_id) for skill_id in core) + cheapest_shield

    def _can_afford_damage(self, player_id: int, skill_id: int) -> bool:
        """True when a damage cast will not starve the survivability kit."""
        return (
            self._energy_points(player_id) - self._skill_cost_points(player_id, skill_id)
            >= self._core_reserve_points(player_id)
        )

    def _ooc_can_afford_cleanse(self, player_id: int, skill_id: int) -> bool:
        """True when a cleanse can be paid for out of combat.

        Deliberately LOOSER than _can_afford_damage, which holds back a damage
        cast until the pool can still cover PS + regen + a shield. That reserve
        exists to keep the survivability kit castable mid-fight. Out of combat
        nothing is attacking, so there is no kit to protect and no pull to walk
        into for the next several seconds - a monk that spends its last energy
        clearing a bleed with 400 health and no mobs around is strictly better
        off than one that keeps the energy and dies of the bleed.

        The floor here is just the cast itself. Deep wound is handled by the
        same test, and it is the condition that actually ends runs, so a monk
        that cannot afford to clear it has bigger problems than energy anyway.

        Fails CLOSED: an unreadable energy reading must not be read as
        affordable, or a cleanse could be issued that silently never fires.
        """
        try:
            return self._energy_points(player_id) >= self._skill_cost_points(player_id, skill_id)
        except Exception:
            return False

    def _cover_remaining_ms(self, player_id: int, skill_id: int, now_ms: float) -> float:
        """Milliseconds of cover left, for either shield.

        Shield of Absorption is an effect, so its remaining time is real.
        Shielding Hands is a buff with no duration field, so this uses a local
        clock seeded at cast time.

        The clock is resynced against presence rather than trusted blindly.
        Anything other than our own cast - HeroAI on the same bar, a manual
        cast, a reload - re-applies SH without touching the clock, so a stale
        expiry made the handoff fire early and put SoA on top of a healthy SH.
        Presence is the ground truth; the clock only measures from it, so a buff
        still up after the clock ran out is re-based rather than called expired.
        """
        if skill_id == SHIELDING_HANDS_ID:
            if not self._has_effect(player_id, skill_id):
                self._shield_expiry_ms.pop(skill_id, None)
                self._shield_seen_ms.pop(skill_id, None)
                return 0.0
            expiry = self._shield_expiry_ms.get(skill_id)
            if expiry is None or now_ms >= expiry:
                # No clock, or it ran out while the buff is still up - so either we
                # did not cast it or something else did. Re-base from when we FIRST
                # saw it, not from now: the buff was already partly through its
                # life when we noticed, and counting from now over-reports the
                # remaining time and steps SoA on early.
                first_seen = self._shield_seen_ms.setdefault(skill_id, now_ms)
                self._shield_expiry_ms[skill_id] = first_seen + self.SHIELDING_HANDS_DURATION_MS
                return max(0.0, self._shield_expiry_ms[skill_id] - now_ms)
            # Our own cast, so the clock is authoritative - and the observation
            # anchor is no longer needed.
            self._shield_seen_ms.pop(skill_id, None)
            return expiry - now_ms
        return max(0.0, self._effect_remaining(player_id, skill_id) * 1000.0)

    def _shield_handoff_due(self, player_id: int, now_ms: float) -> bool:
        """True when a shield is close enough to expiry to replace.

        Time-based, not presence-based, and deliberately covering BOTH shields.
        Testing SH by presence instead would mean nothing is ever replaced while
        it is up - but SH is the longer of the two, so SoA would expire underneath
        it and leave the monk bare until SH dropped.
        """
        for skill_id in (SHIELDING_HANDS_ID, SHIELD_OF_ABSORPTION_ID):
            if self._cover_remaining_ms(player_id, skill_id, now_ms) > self.SHIELD_REFRESH_SECONDS * 1000.0:
                return False
        return True

    def _opening_cover(self, now_ms: float) -> int:
        """Shield to raise when the monk has no cover at all.

        Shielding Hands first, Shield of Absorption as the backup. This is the
        reverse of the original order, which opened with SoA on the theory that
        the shorter shield hands off sooner.

        That reasoning was backwards for how this build is played. Damage
        competes with the core for casts and energy, so the big absorb is worth
        more than a tidy handoff: the extra mobs at the ball spot arrive faster
        than the ladder can re-stack anything, and what actually keeps the monk
        alive is the damage reduction being up continuously rather than a gapless
        SoA->SH transition. SH absorbs more and lasts longer, so it is the
        default; SoA covers SH's recharge so the monk is never bare.

        SoA is never preferred over an available SH, but it is always castable
        while SH is down - that is the whole point of keeping two.
        """
        if self.IsSkillEquipped(SHIELDING_HANDS_ID) and self._cooldown_ok(SHIELDING_HANDS_ID, now_ms):
            return SHIELDING_HANDS_ID
        if self.IsSkillEquipped(SHIELD_OF_ABSORPTION_ID) and self._cooldown_ok(SHIELD_OF_ABSORPTION_ID, now_ms):
            return SHIELD_OF_ABSORPTION_ID
        return 0

    def _preferred_cover(self, player_id: int, now_ms: float) -> int:
        """Shield to raise when *replacing* cover that is about to expire.

        The old version unconditionally returned Shielding Hands whenever it was
        throttled-clear, with SoA only as a fallback. That made the handoff
        impossible: the gate (see _shield_handoff_due) closes while a shield is
        healthy, so SoA was never offered a window, and every replacement was SH
        again. In practice the monk opened once with SoA and then ran SH-only,
        refreshing a buff that still had life while SoA sat ready - which is the
        overlap being chased.

        So the choice is now driven by what is already up:

        - A shield that is DOWN is preferred: it is the gap that needs filling.
        - If both are down, Shielding Hands opens, being the longer of the two,
          so it buys the most time on the ground.
        - If the other shield is up with life to spare, it is the handoff target
          and no second shield is cast over it - the replacement lands after it
          drops, never on top of it.

        _shield_handoff_due still gates the whole thing; this only decides
        WHICH shield, so the two never overlap.
        """
        soa_up = self._cover_remaining_ms(player_id, SHIELD_OF_ABSORPTION_ID, now_ms) > 0.0
        sh_up = self._cover_remaining_ms(player_id, SHIELDING_HANDS_ID, now_ms) > 0.0
        soa_ready = self.IsSkillEquipped(SHIELD_OF_ABSORPTION_ID) and self._cooldown_ok(
            SHIELD_OF_ABSORPTION_ID, now_ms
        )
        sh_ready = self.IsSkillEquipped(SHIELDING_HANDS_ID) and self._cooldown_ok(
            SHIELDING_HANDS_ID, now_ms
        )

        # Exactly one is up: hand off to the one that is missing, so the monk
        # transitions rather than stacking.
        if soa_up and not sh_up and sh_ready:
            return SHIELDING_HANDS_ID
        if sh_up and not soa_up and soa_ready:
            return SHIELD_OF_ABSORPTION_ID

        # Neither up: open on the longer shield.
        if not soa_up and not sh_up:
            if sh_ready:
                return SHIELDING_HANDS_ID
            if soa_ready:
                return SHIELD_OF_ABSORPTION_ID

        # Both up (or nothing castable): do not stack a third cover over either.
        return 0

    def _cover_candidates(self, preferred: int, now_ms: float) -> tuple[int, ...]:
        """Shields worth trying this tick, `preferred` first.

        The point of two shields is that one covers the other's recharge, so
        both are tried. A shield already up with life to spare is skipped.
        """
        player_id = Player.GetAgentID()
        candidates: list[int] = []
        for skill_id in (preferred, SHIELDING_HANDS_ID, SHIELD_OF_ABSORPTION_ID):
            if not skill_id or skill_id in candidates:
                continue
            if not self.IsSkillEquipped(skill_id):
                continue
            # Both shields carry a local expiry (see _cover_remaining_ms), so a
            # shield with room left is skipped.
            if self._cover_remaining_ms(player_id, skill_id, now_ms) > self.SHIELD_REFRESH_SECONDS * 1000.0:
                continue  # already covering
            candidates.append(skill_id)
        return tuple(candidates)

    def _regen_skill_id(self) -> int:
        """The regeneration skill this bar actually carries, or 0."""
        if self.IsSkillEquipped(HEALING_BREEZE_ID):
            return HEALING_BREEZE_ID
        if self.IsSkillEquipped(MYSTIC_REGEN_ID):
            return MYSTIC_REGEN_ID
        return 0

    def _condition_clear_skill_id(self) -> int:
        """First condition clear from the preference order that is slotted."""
        for skill_id in (MEND_AILMENT_ID, DISMISS_CONDITION_ID, SMITE_CONDITION_ID):
            if self.IsSkillEquipped(skill_id):
                return skill_id
        return 0

    def _active_condition_count(self, player_id: int) -> int:
        """How many conditions are stacked on the player right now.

        Agent.py has no "count conditions" call, only per-condition booleans, so
        this sums the flags the events we actually see in GoK can apply - plus
        an effect-based sweep for the ones the bitfield cannot expose.

        THE BITFIELD IS NOT COMPLETE. Agent exposes IsBleeding, IsCrippled,
        IsDeepWounded, IsPoisoned and IsConditioned, and there is no
        IsDisease or IsBurning - the underlying LivingAgent simply does not
        expose them that way. So a monk standing in diseased water or burning
        from a fire trail counted ZERO conditions, no cleanse was ever issued,
        and the degen killed it out of combat with nothing responding. This is
        not a GoK problem: environmental hazards apply degenerations across most
        of the game, so the gap is everywhere, not just here.

        The same limitation is documented and worked around in
        Builds/Necromancer/N_Any/Contagion.py, which counts every condition by
        skill id for exactly this reason. This is that approach, scoped to the
        conditions that matter for a cleanse decision rather than all ten.
        """
        bitfield_count = sum(
            (
                Agent.IsBleeding(player_id),
                Agent.IsCrippled(player_id),
                Agent.IsDeepWounded(player_id),
                Agent.IsPoisoned(player_id),
                Agent.IsConditioned(player_id),
            )
        )
        if bitfield_count:
            return bitfield_count
        # Only pay for the effect sweep when the cheap path found nothing.
        # A cleanse triggers on "> 0", so one hit is all this needs to return,
        # and the sweep is the expensive path - it is only worth it when the
        # bitfield has already said "nothing wrong", which is precisely the case
        # it gets wrong.
        return 1 if self._has_unreadable_condition(player_id) else 0

    def _has_unreadable_condition(self, agent_id: int) -> bool:
        """True when a condition the agent bitfield cannot see is present.

        Disease and Burning are the two that matter here: neither has an Is*
        helper on Agent, and both are applied by ordinary play rather than by
        an exotic skill. Disease comes from plagued areas and water - Kryta's
        pools are the common case - and Burning from fire, which is on the bar
        in a great many zones. Either one drains health every tick on its own,
        with no enemy required to keep applying it.

        Checked as effects, not flags, because the effect exists where the bit
        does not. Blind, Dazed, Weakness and Cracked Armor are deliberately NOT
        here: they impair rather than degenerate, so they do not drain a farmer
        to death and a cleanse is not the answer to them.
        """
        for condition_name in ("Disease", "Burning"):
            try:
                condition_id = GLOBAL_CACHE.Skill.GetID(condition_name)
                if not condition_id:
                    # GetID returns 0 on a name miss, silently. 0 never matches a
                    # real effect, so skipping is correct rather than a false
                    # positive - but it must not be treated as "checked".
                    continue
                if self._has_effect(agent_id, condition_id):
                    return True
            except Exception:
                continue
        return False

    def _self_engines(self) -> tuple[int, ...]:
        """Energy engines this build maintains, in cast order.

        Balthazar's Spirit first: it refunds on every hit the bonded ally
        takes, so it is the reliable baseline. Essence Bond refunds when the
        bonded agent takes physical or elemental damage - bonding self is
        deliberate here, because a 55 monk is the one being hit, so every
        incoming packet pays out.

        NOTE the skill name spelling: the enum key is "Balthazars_Spirit",
        with NO apostrophe. The wiki name is "Balthazar's Spirit", which is a
        natural thing to write and resolves to skill id 0 - silently, with no
        exception and no log. That is why this skill once failed to appear in
        the build manager at all. See the matching entry in
        HeroAI/custom_skill_src/monk.py, which uses the same spelling.

        Engines are permanent: no duration to count down, only stripped by a
        dispel. They must never be given a refresh window, which would recast a
        permanent buff on a timer and waste the whole point of pre-casting.

        Blessed Aura is a permanent self-enchantment too (it lasts while
        maintained and is ended only by a dispel), so it belongs here rather
        than in the timed ladder. It was previously listed in optional_skills
        with no cast site at all, which is why it never fired despite being
        equipped: optional_skills only tells the template what the bar may
        carry, and nothing in the ladder read it.
        """
        engines = []
        if self.IsSkillEquipped(BALTHAZARS_SPIRIT_ID):
            engines.append(BALTHAZARS_SPIRIT_ID)
        if self.IsSkillEquipped(ESSENCE_BOND_ID):
            engines.append(ESSENCE_BOND_ID)
        # Last: it is an amplifier for the rest of the kit rather than a source of
        # energy, so it only pays off once the engines above are up. Monk
        # enchantments last 18% longer at 5 Divine Favor (see the wiki
        # progression table), which stretches PS, MR and the shields.
        if self.IsSkillEquipped(BLESSED_AURA_ID):
            engines.append(BLESSED_AURA_ID)
        # Blessed Signet is an engine for the same reason: it pays 3 energy per
        # maintained enchantment, so it rewards keeping PS, MR and the shields
        # up rather than letting them lapse. Goes after the Aura because it only
        # pays on top of a fuller enchantment set.
        if self.IsSkillEquipped(BLESSED_SIGNET_ID):
            engines.append(BLESSED_SIGNET_ID)
        return tuple(engines)

    def _cast_engine(self, skill_id: int, now_ms: float) -> BuildCoroutine:
        """Cast an energy engine on ourselves. False if it did not go out.

        Self-cast engines must go through the targetless path, and this is why.

        BuildMgr._validate_target_for_skill_cast enforces a skill's registered
        allegiance by calling Agent.IsMelee(target) and returning False when it
        fails - silently, with no exception and no log. IsMelee accepts only
        Axe/Hammer/Daggers/Scythe/Sword, so a staff-wielding monk fails the
        check on itself and the engine never casts. That would make the build
        weapon-dependent, which is not acceptable: a 55 monk swaps to a staff
        after dying to avoid resurrecting at 1hp, and the behaviour must not
        change with the weapon.

        The registry is shared HeroAI data and is not this build's to change, so
        the fix belongs here. Two things make it work:

        1. target_agent_id=0, which makes _validate_target_for_skill_cast return
           True on its first line without inspecting the allegiance at all.
        2. CanCastSkillID still runs, so map readiness, energy, shared skill
           toggles, slot readiness, cooldown and the custom-skill conditions all
           still gate the cast. We are bypassing a *targeting* rule, not the
           cast legality checks.

        A zero target is the correct way to say "self" here, and is the
        established convention in this codebase - see frenkeyLib/Polymock/combat.py,
        which routes a self-target through UseSkillTargetless rather than
        UseSkill(slot, own_id).

        Returns True when the cast was issued and the tick should stop.
        """
        player_id = Player.GetAgentID()
        if not player_id or Agent.IsDead(player_id):
            return False
        if self._has_effect(player_id, skill_id):
            return False
        if not self._cooldown_ok(skill_id, now_ms):
            return False

        if (yield from self.CastSkillID(
            skill_id,
            target_agent_id=0,
            aftercast_delay=self._aftercast(skill_id),
        )):
            self._mark_cast(skill_id, now_ms)
            return True
        return False

    def _run_ooc_upkeep(self) -> BuildCoroutine:
        """
        Out-of-combat upkeep: keep the energy engines alive, nothing else.

        Standing in an explorable map with no foes aggroed is still a state
        worth preparing for - the monk should be engined before the first pull,
        not after it. The protection kit is deliberately left alone here: with
        nothing to tank there is no reason to spend a cast on it, and the
        refresh windows in _needs_recast would only churn it on a timer.

        Only the engines are permanent and cheap, so they are the only thing
        worth maintaining here. The moment something is in range, the in-combat
        tick takes over and maintains the full set.
        """
        # Towns and loading maps are not places to be casting anything. Being in
        # an explorable map is the precondition, not merely being alive.
        if not Routines.Checks.Map.IsExplorable():
            return False
        if not Routines.Checks.Skills.CanCast():
            return False

        player_id = Player.GetAgentID()
        if not player_id or Agent.IsDead(player_id):
            return False

        now_ms = time.monotonic() * 1000.0

        # 0. Condition clear, FIRST and unconditionally in this handler.
        #
        # This used to not exist here at all, and that is a straight death
        # sentence: this method is the only thing running while the monk walks,
        # so a degen picked up out of combat had no response whatsoever. Nothing
        # in the in-combat ladder runs, because the ladder is not being called -
        # HeroAI routes here instead. The monk bled or poisoned to death in an
        # empty corridor, and the cleanse sat several methods away, unreachable.
        #
        # It goes first because a condition is the only thing in this handler
        # that can kill outright. PS is a cap and the engines are income; both
        # matter, but neither is as urgent as removing the thing actively
        # draining health every tick with nothing shooting back.
        #
        # No SoJ exemption and no two-condition wait here, for the same reasons
        # as the in-combat site: there is no knockdown out of combat to be
        # polite to, and there is no combat to be polite in. The energy gate is
        # the only limit, and it is deliberately not the damage-tier gate's
        # core-reserve arithmetic - see below.
        condition_clear = self._condition_clear_skill_id()
        if (
            condition_clear
            and self._cooldown_ok(condition_clear, now_ms)
            and (
                self._active_condition_count(player_id) > 0
                or Agent.IsDeepWounded(player_id)
            )
            and self._ooc_can_afford_cleanse(player_id, condition_clear)
        ):
            if (
                yield from self.CastSkillID(
                    condition_clear,
                    target_agent_id=player_id,
                    aftercast_delay=self._aftercast(condition_clear),
                )
            ):
                self._mark_cast(condition_clear, now_ms)
                return True

        # Same trade as the in-combat tick: PS outranks the engines. The OOC
        # handler is the only thing running while the monk walks between
        # fights, so it is also the only place a PS that decayed during travel
        # can be put back before the next pull.
        #
        # _ps_wanted is the gate. A PS that decayed mid-walk is re-cast when a
        # hostile is already within AGGRO_RADIUS (or inside the linger), which
        # is the pre-cast this handler exists to provide - not a constant upkeep
        # against an empty map.
        ps_due = (
            self.IsSkillEquipped(PROT_SPIRIT_ID)
            and self._ps_wanted(now_ms)
            and self._needs_recast(player_id, PROT_SPIRIT_ID, now_ms)
        )
        if not ps_due:
            for engine_skill_id in self._self_engines():
                if (yield from self._cast_engine(engine_skill_id, now_ms)):
                    return True
        if ps_due:
            if (
                yield from self.CastSkillID(
                    PROT_SPIRIT_ID,
                    target_agent_id=player_id,
                    aftercast_delay=self._aftercast(PROT_SPIRIT_ID),
                )
            ):
                self._mark_cast(PROT_SPIRIT_ID, now_ms)
                return True
        return False

    # Off. The file-based survival log found a 1000x unit bug in
    # _effect_remaining that had been silently breaking every refresh window,
    # so it is worth keeping available - but it writes a line per tick, which is
    # far too noisy for normal farming. Set True to diagnose, and delete
    # DEBUG_SURVIVAL_PATH afterwards.
    DEBUG_SURVIVAL = False  # set True to log the survival state each tick
    # Absolute path for the debug dump. ConsoleLog only goes to the Py4GW console
    # window, which is fiddly to open and impossible to scroll back through, so
    # the diagnostic writes to a file you can just open in any editor.
    DEBUG_SURVIVAL_PATH = r"C:\Users\kjohn\Documents\GitHub\Py4GW_Reforged\monk_survival_debug.log"

    def _debug_survival(self, player_id: int, now_ms: float, note: str = "") -> None:
        """Log the live survival state. Diagnostic only, off by default.

        Every survivability problem in this build so far has been a SCHEDULING
        question - is the ladder getting a tick, is the skill actually castable,
        is something above it eating the tick - and none of those can be answered
        by reading the code. They need the runtime values: how much life each
        enchant actually has left, whether the recharge is ready, and how much
        energy is in the pool.

        Turn DEBUG_SURVIVAL on and paste the log. It answers directly whether PS
        is lapsing, whether the shields are leap-frogging, and whether a cast is
        being refused or merely not attempted.

        NOTE on reloading: the build class is imported into the running process
        once. Editing this file does NOT change the live class, so the flag only
        takes effect after the build is reloaded (or the client restarted). If
        the log file never appears, that is almost certainly why - not a write
        failure, since the path is verified writable.
        """
        if not self.DEBUG_SURVIVAL:
            return
        try:
            regen_id = self._regen_skill_id()
            parts = [
                f"ps={self._effect_remaining(player_id, PROT_SPIRIT_ID):.1f}"
                f"/{'R' if self._recharge_ready(PROT_SPIRIT_ID) else '-'}"
                f"{'(due)' if self._needs_recast(player_id, PROT_SPIRIT_ID, now_ms) else ''}",
                f"soa={self._effect_remaining(player_id, SHIELD_OF_ABSORPTION_ID):.1f}"
                f"/{'R' if self._recharge_ready(SHIELD_OF_ABSORPTION_ID) else '-'}",
                f"sh={self._cover_remaining_ms(player_id, SHIELDING_HANDS_ID, now_ms) / 1000.0:.1f}"
                f"/{'R' if self._recharge_ready(SHIELDING_HANDS_ID) else '-'}",
                f"ba={self._effect_remaining(player_id, BALTHAZARS_SPIRIT_ID):.1f}",
                f"n={self._foe_count(self.ENGAGE_RADIUS)}",
                f"e={self._energy_points(player_id):.0f}",
                f"res={self._core_reserve_points(player_id):.0f}",
            ]
            if regen_id:
                parts.insert(1, f"rg={self._effect_remaining(player_id, regen_id):.1f}")
            line = " | ".join(parts) + (f" | {note}" if note else "")
            # To the file first - that is the copy worth having, because the
            # console window cannot be scrolled back to the moment things went
            # wrong. The console copy is just so it is visible live.
            #
            # A failed write is reported rather than swallowed: a silent except
            # here is how you end up staring for a log that was never written.
            try:
                with open(self.DEBUG_SURVIVAL_PATH, "a", encoding="utf-8") as _fh:
                    _fh.write(line + "\n")
            except Exception as _write_exc:
                ConsoleLog(
                    MODULE_NAME,
                    f"survival debug could not write to {self.DEBUG_SURVIVAL_PATH}: {_write_exc}",
                    PySystem.Console.MessageType.Warning,
                )
            ConsoleLog(MODULE_NAME, line)
        except Exception as exc:  # never let diagnostics break the build
            ConsoleLog(
                MODULE_NAME,
                f"survival debug failed: {exc}",
                PySystem.Console.MessageType.Warning,
            )

    def _run_local_skill_logic(self) -> BuildCoroutine:
        """
        Custom skill logic for 55 Monk farming.

        Priority order:
        0. Energy engines (Balthazar's Spirit, Essence Bond) - pre-cast, see below
        1-3. Protective Spirit -> regen -> cover, in that fixed order. Opening a
             fight raises Shield of Absorption; holding cover waits until ~1.5s
             remain and then refreshes with Shielding Hands.
        4. Castigation Signet (when enemies in range)
        5. Condition removal
        6. Damage skills (Shield of Judgment, Light of Deldrimor)
        """
        if not Routines.Checks.Skills.CanCast():
            return False

        player_id = Player.GetAgentID()
        if not player_id or Agent.IsDead(player_id):
            return False

        now_ms = time.monotonic() * 1000.0

        # 0. Energy engines - cast FIRST, and treated as permanent.
        #
        # Neither engine is a timed enchant: they have no duration to count down
        # and end only when something strips them. So they are checked purely for
        # presence, and must never be given a refresh window - a window would
        # recast a permanent buff on a timer and throw away the whole point.
        #
        # They also cannot sit below the protection ladder. Every CastSkillID
        # carries an aftercast, so a tick lands at most one cast; parked at
        # priority 4 the engine could therefore only ever fire on a tick where
        # Protective Spirit, regen and a shield were all already healthy. That
        # is the one moment the engine needs no help, so it never pre-cast and
        # the monk entered every pull with no energy engine. Casting them first
        # also pre-stacks them before the protection casts spend their own energy.
        self._debug_survival(player_id, now_ms, "tick")
        # Engines are cast first in principle, but never at PS's expense. Each
        # engine cast carries an aftercast, so one cast consumes the whole tick -
        # and with four engines on the bar (Balthazar's Spirit, Essence Bond,
        # Blessed Aura, Blessed Signet) an engine being stripped can consume
        # several ticks in a row. When PS is due that is the wrong trade: PS caps
        # every single hit at 10% of max health, so the recast outranks topping
        # up an energy engine, and this is what made the recast look like it
        # "only happened once it had run out".
        ps_due = (
            self.IsSkillEquipped(PROT_SPIRIT_ID)
            and self._needs_recast(player_id, PROT_SPIRIT_ID, now_ms)
        )
        if not ps_due:
            for engine_skill_id in self._self_engines():
                if (yield from self._cast_engine(engine_skill_id, now_ms)):
                    return True

        # 0b. Protective Spirit PRE-CAST, on approach rather than on contact.
        #
        # Above the aggro gate on purpose - the gate only sees already-aggroed
        # foes, which made PS fire at melee, a full cast too late. Uses
        # _threat_count so it sees mobs still approaching. Cast alone: the
        # shield/regen ladder below handles the rest once we're engaged.
        if (
            self.IsSkillEquipped(PROT_SPIRIT_ID)
            and self._threat_count(self.THREAT_RADIUS) > 0
            and self._needs_recast(player_id, PROT_SPIRIT_ID, now_ms)
        ):
            if (
                yield from self.CastSkillID(
                    PROT_SPIRIT_ID,
                    target_agent_id=player_id,
                    aftercast_delay=self._aftercast(PROT_SPIRIT_ID),
                )
            ):
                self._mark_cast(PROT_SPIRIT_ID, now_ms)
                self._protection_pair_pending = True
                return True

        # While travelling unengaged, PS used to be maintained unconditionally.
        # That was a real fix for a real bug - PS counts down while walking, so
        # an unengaged stretch could expire it entirely and the next pull started
        # with no cap - but it also meant re-casting a ~24s cap against an empty
        # map on every step of a long run, which is the loot-timeout pressure the
        # Ritualist build was fixed for.
        #
        # _ps_wanted keeps the fix and drops the waste: the cap is held while a
        # hostile is inside AGGRO_RADIUS and for PS_LINGER_S after the last one
        # goes, so a mob dying just before the cap would lapse does not drop it.
        # A genuinely empty stretch now costs nothing.
        if self._foe_count(self.AGGRO_RADIUS) == 0:
            self._engaged = False
            if (
                self.IsSkillEquipped(PROT_SPIRIT_ID)
                and self._ps_wanted(now_ms)
                and self._needs_recast(player_id, PROT_SPIRIT_ID, now_ms)
            ):
                if (
                    yield from self.CastSkillID(
                        PROT_SPIRIT_ID,
                        target_agent_id=player_id,
                        aftercast_delay=self._aftercast(PROT_SPIRIT_ID),
                    )
                ):
                    self._mark_cast(PROT_SPIRIT_ID, now_ms)
                    return True
            return False
        self._engaged = True

        # 1-3. The protection stack, in a fixed order.
        #
        # Opening a fight:   Protective Spirit -> regen -> Shield of Absorption
        # Holding cover:     (wait for SoA to reach ~1.5s left)
        # Handing off:       Protective Spirit -> Shielding Hands -> regen
        #
        # The order is not negotiable in either direction. Protective Spirit caps
        # each hit at 10% of current health, and the damage reduction has to land
        # *after* it or the spirit does nothing - the wiki is blunt that the build
        # collapses in seconds if Protective Spirit is not maintained, and just as
        # fast if it is cast under a shield that was already up.
        #
        # Shield of Absorption opens and Shielding Hands refreshes because their
        # durations differ (~6s vs ~8s). SoA is the short shield we hand off from:
        # waiting until it is nearly gone leaves just enough room for the
        # Protective Spirit + Shielding Hands pair to land on top of it, so the
        # monk is never actually bare. Using the long shield to open would
        # invert that and leave the handoff too late to matter.
        #
        # Each cast is followed by another *pass* rather than an immediate return,
        # so the whole stack lands inside one tick. Casts are paced by
        # aftercast_delay rather than by an early return, and the delays are set
        # to the measured cast times - see AFTERCAST_FAST_MS.
        #
        # _pending_regen/_pending_cover carry the intent across passes: once a
        # cast is issued in this tick we stop re-offering it, so a skill whose
        # HasEffect reads stale for a frame does not get double-cast.
        regen_skill_id = self._regen_skill_id()
        # _has_effect, not _effect_remaining: a buff (SH) has no readable
        # duration, so testing remaining would call "SH is up" an opening.
        opening = not any(
            self._has_effect(player_id, skill_id)
            for skill_id in (SHIELDING_HANDS_ID, SHIELD_OF_ABSORPTION_ID)
        )
        cover_skill_id = self._opening_cover(now_ms) if opening else self._preferred_cover(player_id, now_ms)
        if not self._shield_handoff_due(player_id, now_ms):
            cover_skill_id = 0
            # A fresh Protective Spirit wants a shield over it, but that does NOT
            # mean "cast one now" - if cover is already up and healthy the pair is
            # already satisfied. Clearing the flag stops the ladder casting SH on
            # top of a full SoA, which is what it used to do.
            self._protection_pair_pending = False
        self._pending_regen = bool(regen_skill_id) and self._needs_recast(player_id, regen_skill_id, now_ms)
        self._pending_cover = cover_skill_id

        cast_this_tick = False
        for _pass in range(self.MAX_CASTS_PER_TICK):
            if self.IsSkillEquipped(PROT_SPIRIT_ID) and self._needs_recast(player_id, PROT_SPIRIT_ID, now_ms):
                if (
                    yield from self.CastSkillID(
                        PROT_SPIRIT_ID,
                        target_agent_id=player_id,
                        aftercast_delay=self._aftercast(PROT_SPIRIT_ID),
                    )
                ):
                    self._mark_cast(PROT_SPIRIT_ID, now_ms)
                    # A fresh Prot Spirit must be covered by a shield cast after
                    # it, otherwise it is spent on an already-shielded monk.
                    self._protection_pair_pending = True
                    cast_this_tick = True
                    continue

            if regen_skill_id and self._pending_regen and self._needs_recast(player_id, regen_skill_id, now_ms):
                if (
                    yield from self.CastSkillID(
                        regen_skill_id,
                        target_agent_id=player_id,
                        aftercast_delay=self._aftercast(regen_skill_id),
                    )
                ):
                    self._mark_cast(regen_skill_id, now_ms)
                    self._pending_regen = False
                    cast_this_tick = True
                    continue

            # Cover goes last in the ladder but is pulled forward whenever a
            # fresh Protective Spirit still needs covering.
            #
            # The cover chosen at the top of the tick is a preference, not a
            # commitment. It used to be the only candidate, so when SoA was
            # recharging the ladder gave up and left the monk bare with
            # Shielding Hands unused.
            if self._pending_cover or self._protection_pair_pending:
                for cover in self._cover_candidates(self._pending_cover, now_ms):
                    if not cover or not self._cooldown_ok(cover, now_ms):
                        continue
                    if (
                        yield from self.CastSkillID(
                            cover,
                            target_agent_id=player_id,
                            aftercast_delay=self._aftercast(cover),
                        )
                    ):
                        self._mark_cast(cover, now_ms)
                        self._protection_pair_pending = False
                        self._pending_cover = 0
                        cast_this_tick = True
                        break
                else:
                    break
                continue

            break

        # Having just spent the tick on the survivability stack, stop here for the
        # SIGNET and the damage tier - they are all optional, and queueing one on
        # top of a fresh Protective Spirit is how the stack stops landing in
        # order.
        #
        # Condition removal is deliberately NOT gated by this. It used to be, and
        # that starved it completely: Smite Condition sits below this return, and
        # PS / regen / cover are essentially never all up on the same tick, so
        # cast_this_tick was almost always true and the one skill that can clear
        # conditions was never even tested. With three conditions stacked and the
        # monk unable to clear any of them, that is fatal - and the gate was
        # justified in a comment as "spend the tick on survival", which is a
        # reason to not ALSO cast a signet, not a reason to skip a cleanse.
        #
        # Deep wound, or ANY single condition, is a trigger. The energy test is
        # the only cost gate: if the pool covers the cast and still leaves the
        # core reserve intact, there is no reason to defer a cleanse by a tick.
        #
        # Two deliberate changes from the previous version of this gate.
        #
        # 1. The Shield of Judgment stand-down is GONE. It used to hold the
        #    cleanse while a knockdown pinned the pack, on the reasoning that
        #    energy income stops while foes are down so the pool is thinnest.
        #    That reasoning ignored what the knock is FOR: the pack is pinned
        #    and not hitting, which is the cheapest possible moment to spend.
        #    SC is also a flat holy damage skill, and against GoK's undead that
        #    is 126 per cast, double for having hit a monk that SoJ covers at
        #    106. Deferring it through the free window throws away the best
        #    damage the rotation ever gets.
        #
        # 2. CONDITION_TOLERANCE no longer applies. It existed to avoid paying
        #    twice for a second degen, which is right when a cleanse is
        #    expensive relative to what is left. When the energy is free that
        #    argument inverts: there is no second payment to avoid, because
        #    there is no pressure on the pool.
        soj_active = self._soj_up_or_ready(player_id)
        condition_clear = self._condition_clear_skill_id()
        if (
            condition_clear
            and self._cooldown_ok(condition_clear, now_ms)
            and (
                self._active_condition_count(player_id) > 0
                or Agent.IsDeepWounded(player_id)
            )
            and (
                Agent.IsDeepWounded(player_id)
                or self._can_afford_damage(player_id, condition_clear)
            )
        ):
            if (
                yield from self.CastSkillID(
                    condition_clear,
                    target_agent_id=player_id,
                    aftercast_delay=self._aftercast(condition_clear),
                )
            ):
                self._mark_cast(condition_clear, now_ms)
                return True

        if cast_this_tick:
            return True

        # 4. Castigation Signet - when enemies in range. A signet is not an
        # enchantment: it has no duration, it simply ends when we attack, so
        # the only state worth testing is whether it is present at all.
        if (
            self.IsSkillEquipped(CASTIGATION_SIGNET_ID)
            and not self._has_effect(player_id, CASTIGATION_SIGNET_ID)
            and self._cooldown_ok(CASTIGATION_SIGNET_ID, now_ms)
        ):
            signet_target = self._nearest_foe_in_range(Range.Earshot.value)
            if signet_target:
                if (
                    yield from self.CastSkillID(
                        CASTIGATION_SIGNET_ID,
                        target_agent_id=signet_target,
                        aftercast_delay=self._aftercast(CASTIGATION_SIGNET_ID),
                    )
                ):
                    self._mark_cast(CASTIGATION_SIGNET_ID, now_ms)
                    return True

        # 5. Condition removal. Smite Condition removes one per cast and is
        # expensive to spam, so spending it on a lone degen means paying again
        # for the next one. The regen layer covers a single condition, so hold
        # until a second stacks. Deep wound is exempt: that is the condition
        # that ends a run, so it is worth the spend on its own.
        #
        # The energy gate is the important part. This check used to run with no
        # affordability test at all, so a condition cast could take the pool
        # below the core reserve - which is exactly what left the monk with no
        # shield at n=15 in the live log. Now it defers to the same
        # _can_afford_damage test the damage tier uses.
        #
        # It ALSO stands down while the knockdown is holding foes down. That is
        # a deliberate trade, not just a throttle: a knocked-down foe is not
        # hitting us, so Balthazar's Spirit is not paying out, so energy income
        # has stopped at the exact moment the pool is thinnest. Spending 15 on
        # Smite Condition during that window buys the least for the most. A
        # condition that stacks during a knockdown is not costing anything while
        # the pack stays down, so it can wait for the window to close.
        #
        # Deep wound still overrides both: it is the condition that ends a run.
        # 5. Condition removal now lives ABOVE the cast_this_tick return, so that
        # a tick which spent itself on the survivability stack can still cleanse.
        # The cast site is the one there; it is not repeated here.
        #
        # What it still enforces there: the energy gate, so a cleanse cannot
        # take the pool below the core reserve - which is what left the monk with
        # no shield at n=15 in the live log. Deep wound still overrides it.
        #
        # What it NO LONGER enforces: the two-or-more tolerance and the
        # knockdown stand-down. Both were cost-management for a spell that is
        # also this build's second-biggest holy damage source. See the cast site
        # for the reasoning.
        #
        # soj_active is defined above, next to the cast site; the damage tier
        # below still uses it.

        # 5b. Optional support skills, only when they are actually slotted. The
        # rule for this whole block: anything in the build's skill list works if
        # the bar carries it. These used to be declared in optional_skills with
        # no cast site, so they were inert - the template could load them and
        # nothing would ever fire them.
        #
        # Each is timed, so _needs_recast applies rather than presence. They sit
        # after the survivability stack and before the damage tier: they relieve
        # pressure without spending the core reserve, which is what the damage
        # tier is gated on.
        support_targets = (
            (BALTHAZARS_AURA_ID, self.ENGAGE_RADIUS),
            (PAIN_INVERTER_ID, self.ENGAGE_RADIUS),
            (RADIATION_FIELD_ID, self.ENGAGE_RADIUS),
        )
        for support_skill_id, support_radius in support_targets:
            if not self.IsSkillEquipped(support_skill_id):
                continue
            if not self._needs_recast(player_id, support_skill_id, now_ms):
                continue
            if not self._cooldown_ok(support_skill_id, now_ms):
                continue
            support_target = self._nearest_foe_in_range(support_radius)
            if not support_target:
                continue
            if (
                yield from self.CastSkillID(
                    support_skill_id,
                    target_agent_id=support_target,
                    aftercast_delay=self._aftercast(support_skill_id),
                )
            ):
                self._mark_cast(support_skill_id, now_ms)
                return True

        # 5c. Elite melee. Judgment Strike only makes sense with a hammer, so it
        # is gated on being equipped and simply takes a normal cast when slotted.
        # It is an attack, so it costs the Castigation Signet - which is the
        # correct trade on a hammer build where the strike is the damage.
        if self.IsSkillEquipped(JUDGMENT_STRIKE_ID) and self._cooldown_ok(JUDGMENT_STRIKE_ID, now_ms):
            strike_target = self._nearest_foe_in_range(self.ENGAGE_RADIUS)
            if strike_target:
                if (
                    yield from self.CastSkillID(
                        JUDGMENT_STRIKE_ID,
                        target_agent_id=strike_target,
                        aftercast_delay=self._aftercast(JUDGMENT_STRIKE_ID),
                    )
                ):
                    self._mark_cast(JUDGMENT_STRIKE_ID, now_ms)
                    return True

        # 6. Damage skills. Lowest priority by design: damage is optional, the
        # core set is survival, so this only fires when its cost still leaves
        # enough energy to re-stack the core.
        if self._core_survival_ok(player_id, now_ms) and self._foe_count(self.ENGAGE_RADIUS) > 0:
            # SoJ is the priority and the rest of the damage tier stands down
            # while it is up. SoJ knocks foes down, a downed foe is not hitting
            # us, and the energy engines only pay out when the bonded ally takes
            # damage - so spending on damage during that window pays twice for a
            # fight already held. soj_active is computed above, for the
            # condition gate.
            # SoJ and Ray of Judgment do the same job - knock a target down and
            # damage it and its neighbours - so they are alternatives, not a
            # pair. Whichever is slotted takes the slot; slotting both would just
            # spend two casts on the same intent.
            knockdown_id = 0
            if self.IsSkillEquipped(SHIELD_OF_JUDGMENT_ID):
                knockdown_id = SHIELD_OF_JUDGMENT_ID
            elif self.IsSkillEquipped(RAY_OF_JUDGMENT_ID):
                knockdown_id = RAY_OF_JUDGMENT_ID
            if knockdown_id:
                # A signet ends the moment we attack, so while Castigation Signet
                # is up it is worth more than one knockdown hit: re-raising the
                # signet costs a cast plus the energy we just spent.
                if not self._has_effect(player_id, CASTIGATION_SIGNET_ID):
                    soj_target = self._nearest_foe_in_range(self.ENGAGE_RADIUS)
                    if soj_target and self._cooldown_ok(knockdown_id, now_ms):
                        if (
                            yield from self.CastSkillID(
                                knockdown_id,
                                target_agent_id=soj_target,
                                aftercast_delay=self._aftercast(knockdown_id),
                            )
                        ):
                            self._mark_cast(knockdown_id, now_ms)
                            return True

            # This is a SEPARATE `if`, not an `elif` chained to the knockdown
            # block above. It used to be an elif, which meant the whole damage
            # tier only ran when NO knockdown skill was slotted - so on any bar
            # carrying SoJ or Ray of Judgment, SoW, Judge's Intervention and
            # Light of Deldrimor were unreachable on every tick. Swapping SoJ
            # for the elite made that the normal case rather than the exception.
            if not soj_active:
                # ---- Damage tier: only when the engine is actually earning ----
                # SoW is an AoE on the pack and lasts 5s, so it is worth most per
                # cast and goes first. Judge's Intervention is a self-enchantment
                # that negates one fatal hit AND damages a nearby foe, so it
                # doubles as the monk's own safety net. Light of Deldrimor is the
                # most expensive single hit, so it is last.
                #
                # Symbol of Wrath. A ground AoE, so the effect sits on the foes
                # in it, not the caster - test the target, or it re-casts every tick.
                if self.IsSkillEquipped(SYMBOL_OF_WRATH_ID) and not self._symbol_of_wrath_active(
                    self.ENGAGE_RADIUS
                ) and self._cooldown_ok(SYMBOL_OF_WRATH_ID, now_ms):
                    sow_target = self._nearest_foe_in_range(self.ENGAGE_RADIUS)
                    if sow_target:
                        if (
                            yield from self.CastSkillID(
                                SYMBOL_OF_WRATH_ID,
                                target_agent_id=sow_target,
                                aftercast_delay=self._aftercast(SYMBOL_OF_WRATH_ID),
                            )
                        ):
                            self._mark_cast(SYMBOL_OF_WRATH_ID, now_ms)
                            return True

                # Judge's Intervention. Self-enchantment, so test presence on
                # self (unlike Symbol of Wrath). It also hits a nearby foe.
                if (
                    self.IsSkillEquipped(JUDGES_INTERVENTION_ID)
                    and not self._has_effect(player_id, JUDGES_INTERVENTION_ID)
                    and self._cooldown_ok(JUDGES_INTERVENTION_ID, now_ms)
                ):
                    if (
                        yield from self.CastSkillID(
                            JUDGES_INTERVENTION_ID,
                            target_agent_id=player_id,
                            aftercast_delay=self._aftercast(JUDGES_INTERVENTION_ID),
                        )
                    ):
                        self._mark_cast(JUDGES_INTERVENTION_ID, now_ms)
                        return True

                # Light of Deldrimor. A spell, not an attack, so it leaves the
                # signet standing. The most expensive option, hence last.
                if (
                    self.IsSkillEquipped(LIGHT_OF_DELDRIMOR_ID)
                    and self._can_afford_damage(player_id, LIGHT_OF_DELDRIMOR_ID)
                    and self._cooldown_ok(LIGHT_OF_DELDRIMOR_ID, now_ms)
                ):
                    lod_target = self._nearest_foe_in_range(self.ENGAGE_RADIUS)
                    if lod_target and (
                        yield from self.CastSkillID(
                            LIGHT_OF_DELDRIMOR_ID,
                            target_agent_id=lod_target,
                            aftercast_delay=self._aftercast(LIGHT_OF_DELDRIMOR_ID),
                        )
                    ):
                        self._mark_cast(LIGHT_OF_DELDRIMOR_ID, now_ms)
                        return True

        return False
