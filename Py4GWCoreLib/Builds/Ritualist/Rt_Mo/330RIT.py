"""360 HP Vengeful Ritualist/Monk farmer.

The core mechanic: Protective Spirit caps every incoming hit at 10% of max
Health. Vengeful Was Khanhei steals a flat 47 back per strike (Restoration 16,
more with AL). So long as the 10% cap stays below 47, every hit is more than
fully healed and the build is effectively invulnerable against normal damage.
The heal exceeds the cap; the point is that the two are close enough that
nothing gets through, and that is the pairing to preserve if either number is
ever retuned.

HP: 360, not the 330 this file was written around. The extra 30 is a staff;
the 20/20 wand is gone. This is a deliberate move UP, and the reason is the
cap is proportional - the build was running at 330 with a 33 cap and no buffer
at all, so any tick where the cap was down took a third of total health. More
HP widens the buffer without touching the heal, and it costs the pairing
almost nothing: the cap goes 33 -> 36 while VwK stays at 47.

That margin is worth watching, though. 47 over a 36 cap is 11 spare, where it
was 14 at 330. The build still fully heals, but the slack is shrinking, and
pushing much past ~400 would start to put the 10% cap close enough to 47 that
VwK alone stops covering every hit. If the cap is ever retuned, or AL is
removed and VwK drops below 47, check this ratio first - it is the one number
in the file that decides whether the build works at all.

This is NOT a build for dangerous areas. It has no answer to health
degeneration (nothing regenerates health through damage-over-time) and no answer
to enchantment stripping (the whole kit is enchants). Those are avoided by
choosing the farm, not mitigated here. Use it where mobs die to ordinary hits.

Retribution used to be cast only in the damage step, which is gated on a
target being in ENGAGE_RADIUS, so it never went up until a mob was already
close. It is a self buff like Essence Bond and Balthazar's Spirit, so it is
maintained in _core_upkeep instead and fires on entering the explorable area.

Shared skill implementations live under Builds/Skills/ritualist and the Monk
folders. This file owns only the rotation.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from Py4GWCoreLib import Agent, GLOBAL_CACHE, Profession, Range, Routines, Utils
from Py4GWCoreLib.Player import Player
from Py4GWCoreLib import BuildMgr

if TYPE_CHECKING:
    # Runtime-only annotation: BuildCoroutine is a generator type, and the build
    # is imported by BuildRegistry at scan time. Importing it eagerly is
    # unnecessary and risks a cycle through Py4GWCoreLib.BuildMgr.
    from Py4GWCoreLib.BuildMgr import BuildCoroutine

MODULE_NAME = "330RIT"

# Skill IDs, verified against skill_descriptions.json rather than looked up by
# name. Skill.GetID returns 0 on a name miss, silently, and 0 never casts - that
# has bitten this repo three times already (Balthazars_Spirit, Ray_of_Judgement,
# and "I Am Unstoppable!", whose stored name carries literal quote characters).
# Every one of these is spelled correctly and hardcoded.
VENGEFUL_WAS_KHANHEI_ID = 790  # Restoration
VENGEFUL_WEAPON_ID = 964  # Restoration
PROT_SPIRIT_ID = 245  # Protection Prayers
SPIRIT_BOND_ID = 1114  # Protection Prayers
REVERSAL_OF_DAMAGE_ID = 1400  # Smiting Prayers
RETRIBUTION_ID = 248  # Smiting Prayers
ESSENCE_BOND_ID = 250  # Spirit Spawning
BALTHAZARS_SPIRIT_ID = 242  # Smiting Prayers

# Variants. These are MUTUALLY EXCLUSIVE with Reversal of Damage - the bar has
# eight slots and the core bar fills all eight, so a variant replaces RoD rather
# than joining it. All six are declared optional so the template can carry any
# of them; only the one actually slotted will ever cast.
SMITE_CONDITION_ID = 2004
LIGHT_OF_DELDRIMOR_ID = 2212
RADIATION_FIELD_ID = 2414
PAIN_INVERTER_ID = 2418
I_AM_UNSTOPPABLE_ID = 2356  # stored as '"I Am Unstoppable!"' - quotes included
EBON_BATTLE_STANDARD_WISDOM_ID = 2232


class Ritualist330(BuildMgr):
    """Ritualist/Monk. Vengeful Was Khanhei + Protective Spirit, 360 HP.

    Named 330 after the HP the bar was originally built around, and the name is
    kept because the file name, the module name and the build registry all key
    off it - renaming is a cross-file change, not a docstring fix. The class
    docstring used to say 470 HP, which was never true; 360 is current (330
    base plus 30 from the staff, the 20/20 wand being gone). See the module
    header for why more HP is a deliberate move UP rather than a regression.
    """

    # ---- Timing dial ---------------------------------------------------------
    #
    # One knob for how fast the stack goes up, multiplying every per-skill
    # aftercast. 0.25 runs ~75% faster than measured cast times. Erring fast is
    # correct here: PS + VwK are the invulnerability pair, and a stack that
    # arrives a tick late is the same as no stack.
    TIMING_SCALE = 0.25
    AFTERCAST_FAST_MS = 300
    AFTERCAST_ELITE_MS = 750  # VwK is the slow one at ~0.75s
    CAST_COOLDOWN_MS = 750  # per-skill throttle between cast attempts

    # ---- Refresh windows (milliseconds of remaining life) --------------------
    #
    # Absolute per-skill, not a fraction of a learned duration. Most enchants
    # here are 8s (Spirit Bond, Vengeful Weapon, Reversal of Damage), so a
    # fraction rule would recast them with seconds left. VwK is 11s. PS is
    # ~17s as a Ritualist, NOT the ~23s a monk gets - see PS_REFRESH_MS below.
    ENCHANT_REFRESH_MS = 2500
    VWK_REFRESH_MS = 3000
    # PS_REFRESH_MS is measured against the RITUALIST's real duration, not the
    # monk's. Ritualist/maintenance gives ~17s here, not the ~23s a monk gets.
    # The old value of 5000 was ~22% of the monk's duration but ~31% of ours.
    # 3000ms is ~18% of 17s, so the recast goes out with four fifths of the cap
    # still standing and the recharge (~5s) is long clear by then.
    #
    # PS is REFRESHED by re-casting, and re-casting works while it is already
    # up: a skill in GW can be used whenever it is off cooldown, whether or not
    # its effect is currently running. So this window is live and honoured. An
    # earlier comment here claimed the game refuses an early reapplication -
    # that was wrong, and was inferred from IsSkillSlotReady returning
    # `skill.recharge == 0` without ever reading PS's real recharge. Recharge is
    # a few seconds, the duration is 17s; they are not the same number.
    PS_REFRESH_MS = 3000
    # Spirit Bond is emergency-only: 8s duration, cast on demand when health
    # dips OR when VwK is wearing off, so it must NOT be maintained on a timer
    # or it would be up permanently and provide nothing when it is actually
    # needed.
    SPIRIT_BOND_HEALTH_FRACTION = 0.85
    # How long is left on VwK before Spirit Bond is layered on for the gap. VwK
    # is the heal this build trades on, and Spirit Bond is the regen that covers
    # the handover - so the two must overlap, not sit in sequence with a dead
    # tick between them.
    SPIRIT_BOND_VWK_GAP_S = 3.0
    # Energy headroom before Vengeful Weapon (VW) is worth its cast. VW is
    # damage, and damage is the one thing here that can be skipped: PS and VwK
    # are not.
    #
    # REMOVED: VWEAPON_SURPLUS_POINTS = 6.0. It demanded 6 of 10 points AFTER PS
    # and VwK were already funded, so it never passed and VW never cast. The
    # energy discipline it was trying to express is now carried by rotation
    # ORDER - survival is earlier in the loop and each step returns on first
    # success - which achieves the same thing without a threshold that
    # excluded itself. See _vengeful_weapon_if_surplus.

    # ---- Ranges --------------------------------------------------------------
    # Three radii, and the distinction between them is load-bearing. This file
    # originally declared all three and then used only ENGAGE_RADIUS for
    # everything, which made the other two dead constants and the build blind
    # past 1248 - precisely where casters sit.
    #   AGGRO_RADIUS  - the buffer zone. Gates PS upkeep, so the cap is only
    #                   paid for when a mob is already on the way. This is what
    #                   keeps a loot cycle from timing out on an idle cap.
    #   THREAT_RADIUS - "is anything hitting me". Used for VwK upkeep and
    #                   _engaged. Includes ranged attackers on purpose.
    #   ENGAGE_RADIUS - "can I reach it". Used only to pick a damage target.
    # A kite caster at 1500 is a THREAT and not an ENGAGE. Gating the heal on
    # the engage radius meant taking projectile damage with the heal switched
    # off, so the split is the fix, not a tuning value.
    AGGRO_RADIUS = Range.Spirit.value  # 2500
    THREAT_RADIUS = Range.SafeCompass.value  # 4800
    ENGAGE_RADIUS = Range.Spellcast.value  # 1248

    # ---- Energy reserve ------------------------------------------------------
    #
    # The single most important number in this build. The wiki is explicit:
    # "wait for energy to fill before casting each one". Every optional cast
    # (Retribution, Vengeful Weapon, a variant) is gated on leaving this much
    # behind, which is what keeps PS and VwK castable.
    #
    # In ENERGY POINTS, against a 10-point max bar, so it must stay under 10 or
    # nothing ever casts. This previously read 15.0, which is unreachable: the
    # gate could never pass and the whole stack silently never came up. 3.0 is
    # the minimum that still leaves PS and one VwK cast available - enough to
    # keep the invulnerability pair, and no more.
    CORE_RESERVE_POINTS = 3.0

    # ---- Variant slot --------------------------------------------------------
    #
    # Slot 5 is the variable one. The seven required skills above fill the rest,
    # and the wiki's template ships Reversal of Damage there; the six skills in
    # optional_skills are the documented replacements for it. This build file
    # only owns the rotation, so the default is asserted here and can be
    # overridden per-instance by a farmer that wants a different variant.
    DEFAULT_VARIANT_SKILL_ID = REVERSAL_OF_DAMAGE_ID

    # ---- Protective Spirit: threat gate plus combat latch -------------------
    #
    # PS is gated on threat so idle looting costs nothing, but a plain gate was
    # not enough: once a pull started, PS still fell for a beat every time the
    # 17s enchant expired, because the rotation was busy and the cap came back
    # late. That gap is the thing that kills this build, because the cap is the
    # only thing standing between a hit and a third of total health.
    #
    # So the gate has a LATCH. Once a mob crosses AGGRO_RADIUS, PS is treated as
    # wanted for PS_LINGER_S seconds AFTER the last threat is seen, and it is
    # refreshed on the same 3s window as any other enchant. Linger covers the
    # ordinary case of a mob dying or walking out of range a moment before the
    # cap would have lapsed - without it, the enchant drops between two mobs and
    # the next pull starts with no cap.
    #
    # Linger is what makes the aggro gate and the refresh work together rather
    # than fight: the gate alone left PS fully down whenever a mob stepped
    # outside 2500, which is what caused the long unprotected stretches. With it,
    # the cap survives the tail of a fight and is already up for the next one.
    PS_LINGER_S = 2.0

    DEBUG_SURVIVAL = False
    DEBUG_SURVIVAL_PATH = r"C:\Users\kjohn\Documents\GitHub\Py4GW_Reforged\rit330_survival_debug.log"

    def __init__(self, match_only: bool = False):
        super().__init__(
            name="330 Ritualist Vengeful Farmer",
            required_primary=Profession.Ritualist,
            required_secondary=Profession.Monk,
            template_code="OAOK4gPaITKjFj4VP0i4V8h+QeA",
            required_skills=[
                VENGEFUL_WAS_KHANHEI_ID,
                VENGEFUL_WEAPON_ID,
                PROT_SPIRIT_ID,
                SPIRIT_BOND_ID,
                RETRIBUTION_ID,
                ESSENCE_BOND_ID,
                BALTHAZARS_SPIRIT_ID,
            ],
            optional_skills=[
                REVERSAL_OF_DAMAGE_ID,
                SMITE_CONDITION_ID,
                LIGHT_OF_DELDRIMOR_ID,
                RADIATION_FIELD_ID,
                PAIN_INVERTER_ID,
                I_AM_UNSTOPPABLE_ID,
                EBON_BATTLE_STANDARD_WISDOM_ID,
            ],
        )

        # BuildMgr.__init__ sets self.skills to the required list alone, and the
        # inherited ValidateSkills compares that list to the live bar for an
        # EXACT match. On this build that could never succeed: the bar has eight
        # slots, the required list has seven, so the two sets always differed by
        # the variant and validation sat in its 1000ms wait loop instead of
        # loading. Overriding the attribute here fixes it for this build only.
        #
        # Scoped deliberately: ValidateSkills and ScoreMatch live in the shared
        # BuildMgr and are not ours to change - they gate every other build for
        # every other user. The correct full fix is a required/optional-aware
        # comparison in BuildMgr, but that is a separate, reviewed change, not
        # something to smuggle in while debugging one build.
        #
        # Set before the match_only return so the match-only instances the
        # registry builds for the skill-bar picker describe the same bar.
        self.skills = self.required_skills + [self.DEFAULT_VARIANT_SKILL_ID]
        # minimum_required_match stays at 7, which is what ScoreMatch already
        # uses, so an 8-slot bar scores 7 required + 1 optional = 8.

        if match_only:
            return

        self.SetSkillCastingFn(self._run_local_skill_logic)
        self.SetOOCFn(self._run_ooc_upkeep)

        self._last_cast_ms: dict[int, float] = {}
        self._engaged = False
        # Latch for the PS threat gate: the monotonic time (ms) until which PS
        # stays wanted after the last mob left AGGRO_RADIUS. 0.0 = disarmed.
        # See PS_LINGER_S and _ps_wanted.
        self._ps_latch_until_ms: float = 0.0

    # ---- Shared helpers ------------------------------------------------------
    #
    # Duplicated from Monk55Farmer rather than imported. A shared base class
    # would be the better structure, but extracting one now would touch a build
    # that is currently working and verified, and the alternative - editing
    # BuildMgr - would change behaviour for every other build in the repo. This
    # file is the owner; it carries its own copy until that refactor is done
    # deliberately rather than as a side effect of debugging.

    def _has_effect(self, agent_id: int, skill_id: int) -> bool:
        """True when the agent carries the effect."""
        try:
            return bool(GLOBAL_CACHE.Effects.HasEffect(agent_id, skill_id))
        except Exception:
            return False

    def _effect_remaining(self, agent_id: int, skill_id: int) -> float:
        """SECONDS left on a timed effect, 0.0 when it is not up.

        GLOBAL_CACHE.Effects.GetEffectTimeRemaining returns MILLISECONDS. This
        divides once, here, so every caller in this file works in seconds. The
        1000x inflation this avoids is not hypothetical - it is what made the
        55 Monk's shields never approach their refresh window, so its regen
        sat at zero and the monk degened while a ready skill went unused.

        Reads EFFECTS only. A skill registered as a buff has no timing field
        here and will always report 0.0; use _has_effect for those.
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

    def _cooldown_ok(self, skill_id: int, now_ms: float) -> bool:
        last = self._last_cast_ms.get(skill_id)
        return last is None or (now_ms - last) >= self.CAST_COOLDOWN_MS

    def _energy_points(self) -> float:
        """Current energy as POINTS, not the 0..1 fraction most helpers report.

        CORE_RESERVE_POINTS is compared against this, so a fraction would make
        every energy gate trivially pass and the reserve would do nothing. The
        max is read from the agent rather than
        assumed, so a max-energy change (gear, an effect) cannot silently
        rescale the gates.
        """
        player_id = Player.GetAgentID()
        if not player_id:
            return 0.0
        fraction = float(Agent.GetEnergy(player_id) or 0.0)
        return fraction * float(Agent.GetMaxEnergy(player_id) or 0.0)

    def _can_afford(self, cost: float) -> bool:
        """True when there is at least `cost` energy points available."""
        return self._energy_points() >= cost

    def _aftercast(self, skill_id: int) -> int:
        """Scaled aftercast for `skill_id`, in milliseconds.

        CastSkillID declares aftercast_delay as int ms, so this scales in ms and
        truncates rather than returning seconds as a float. VwK is the slow
        cast on the bar; everything else is fast. TIMING_SCALE compresses both.
        """
        base_ms = self.AFTERCAST_ELITE_MS if skill_id == VENGEFUL_WAS_KHANHEI_ID else self.AFTERCAST_FAST_MS
        return max(1, int(base_ms * self.TIMING_SCALE))

    def _foes_in_range(self, radius: float | None = None) -> list[int]:
        """Living foes within `radius` of the player, ENGAGE_RADIUS if omitted.

        The Monk's version of this is a plain list comprehension over
        Routines.Agents.GetFilteredEnemyArray plus an IsAlive filter, and that
        is the shape used here: Utils has no GetLivingEnemyList, and inventing
        one here would be a second owner for a job the shared helper already
        does.

        `radius` is a parameter because "can I hit it" and "is it shooting me"
        are different questions and must not share one number. Hardcoding
        ENGAGE_RADIUS here - which this file did - made every threat test blind
        past 1248, i.e. exactly the range a caster sits at. VwK upkeep was
        gated on it, so a kite caster at 1500 turned the heal off entirely
        while its projectiles were landing. See AGGRO_RADIUS/THREAT_RADIUS.
        """
        if radius is None:
            radius = self.ENGAGE_RADIUS
        try:
            px, py = Player.GetXY()
            return [
                agent_id
                for agent_id in (Routines.Agents.GetFilteredEnemyArray(px, py, radius) or [])
                if Agent.IsAlive(agent_id)
            ]
        except Exception:
            return []

    def _foe_count(self, radius: float | None = None) -> int:
        return len(self._foes_in_range(radius))

    def _nearest_foe_in_range(self) -> int:
        """Closest living foe within ENGAGE_RADIUS, or 0 when the area is clear."""
        try:
            foes = self._foes_in_range()
            if not foes:
                return 0
            px, py = Player.GetXY()
            return min(foes, key=lambda agent_id: Utils.Distance((px, py), Agent.GetXY(agent_id)))
        except Exception:
            return 0

    def _refresh_window_ms(self, skill_id: int) -> int:
        """How much remaining life counts as 'needs a recast', in ms."""
        if skill_id == VENGEFUL_WAS_KHANHEI_ID:
            return self.VWK_REFRESH_MS
        if skill_id == PROT_SPIRIT_ID:
            return self.PS_REFRESH_MS
        return self.ENCHANT_REFRESH_MS

    def _needs_recast(self, agent_id: int, skill_id: int, now_ms: float) -> bool:
        """True when this enchant should go back up.

        Three cases, and the third is the reason this is not a plain timer:
        never cast, let it expire within the refresh window, or it is simply not
        up. Spirit Bond is deliberately excluded by the caller - it is
        emergency-only, cast on demand rather than maintained.
        """
        if not self._has_effect(agent_id, skill_id):
            return True
        if not self._cooldown_ok(skill_id, now_ms):
            return False
        remaining_ms = self._effect_remaining(agent_id, skill_id) * 1000.0
        return remaining_ms <= self._refresh_window_ms(skill_id)

    def _cast_self(self, skill_id: int, now_ms: float) -> BuildCoroutine:
        """Cast an energy engine on ourselves. False if it did not go out.

        Self-cast engines must go through the targetless path, and this is why.

        BuildMgr._validate_target_for_skill_cast enforces a skill's registered
        allegiance by calling Agent.IsMelee(target) and returning False when it
        fails - silently, with no exception and no log. IsMelee accepts only
        Axe/Hammer/Daggers/Scythe/Sword, so a non-melee caster fails the check
        on itself and the engine never casts. That would make the build
        weapon-dependent, which is not acceptable: behaviour must not change
        with the weapon equipped.

        The registry is shared HeroAI data and is not this build's to change, so
        the fix belongs here. Two things make it work:

        1. target_agent_id=0, which makes _validate_target_for_skill_cast return
           True on its first line without inspecting the allegiance at all.
        2. CanCastSkillID still runs, so map readiness, energy, shared skill
           toggles, slot readiness, cooldown and the custom-skill conditions all
           still gate the cast. We are bypassing a *targeting* rule, not the
           cast legality checks.

        A zero target is the correct way to say "self" here, and is the
        established convention in this codebase - see frenkeyLib/Polymock/
        combat.py, which routes a self-target through UseSkillTargetless rather
        than UseSkill(slot, own_id).
        """
        player_id = Player.GetAgentID()
        if not player_id or Agent.IsDead(player_id):
            return False
        # NOTE: there is deliberately no `if self._has_effect(...): return False`
        # guard here. One used to sit on these lines, and it silently made every
        # refresh window in this file dead code: _needs_recast would correctly
        # report "PS is inside its window, recast it", and this guard would then
        # veto the cast because the effect was still up - which it always is
        # until it lapses. The visible symptom was PS refreshing only AFTER it
        # had expired, leaving the cap down for the whole recast window on a
        # 17s skill. The guard is redundant rather than protective: every caller
        # gates on _needs_recast first, and that already returns True for both
        # "not up" and "up but expiring". _cooldown_ok below is the throttle
        # that stops a recast going out every tick while it is in flight.
        if not self._cooldown_ok(skill_id, now_ms):
            return False

        if (yield from self.CastSkillID(
            skill_id,
            target_agent_id=0,
            aftercast_delay=self._aftercast(skill_id),
        )):
            self._last_cast_ms[skill_id] = now_ms
            return True
        return False

    def _ps_wanted(self, now_ms: float) -> bool:
        """True when Protective Spirit should be up, threat or latch.

        One predicate, called by BOTH _core_upkeep and the step-0 gate. That
        sharing is deliberate: the two used to disagree, and when one thought PS
        was wanted and the other did not, the rotation stalled.

        A mob inside AGGRO_RADIUS arms the latch. Once armed, PS stays wanted for
        PS_LINGER_S after the LAST threat is seen, so a mob that dies or walks
        off just before the cap lapses does not drop it. The latch is disarmed
        only when the linger has run out with nothing threatening, which is what
        lets the cap expire during looting.

        Fails CLOSED on an exception. A foecount that raises must not be read as
        "no threat", or a single bad frame silently disarms the latch and the
        build goes back to being capless.
        """
        try:
            threatened = self._foe_count(self.AGGRO_RADIUS) > 0
        except Exception:
            # Cannot tell whether something is coming, so assume it is. The cost
            # of being wrong is one wasted cast; the cost of guessing "safe" is
            # a dead monk.
            return True

        if threatened:
            self._ps_latch_until_ms = now_ms + (self.PS_LINGER_S * 1000.0)
            return True
        return now_ms < self._ps_latch_until_ms

    def _core_upkeep(self, now_ms: float) -> BuildCoroutine:
        """Enchants that must be up even with nothing in range.

        Protective Spirit is the caps the build survives on and Balthazar's
        Spirit is the damage reduction underneath it; both are worth their
        energy even out of combat. Essence Bond and Spirit Bond are maintained
        here too - EB because it is a flat damage engine, Spirit Bond because
        having it up before a fight is better than casting it during one.

        Retribution lives here rather than in the damage step. It is a self
        buff like Essence Bond and Balthazar's Spirit, and it is the build's
        primary attack, so a rotation that only reaches it once a target is in
        ENGAGE_RADIUS leaves the whole bar down for the walk in and for the
        approach. It is cast ONCE and left to run, which is what the user asked
        for and also what the skill wants - Retribution is a long timer, not a
        refresh-every-fight cooldown. _needs_recast already reports True when
        the effect is simply absent, so "is it up" is the whole test here.

        Vengeful Was Khanhei is deliberately NOT here. It is the heal this build
        trades on, and it only fires when something is hitting, so it belongs in
        _battle_upkeep where a target exists to trigger it.

        Order matters: PS first, because it is the cheapest way to make the rest
        of the stack safe to assemble. Retribution is second, ahead of the two
        damage enchants, because it is the attack everything else is amplifying.

        PS is THREAT-GATED at AGGRO_RADIUS and the other three are not. That is
        the deliberate asymmetry, and it is the whole point of this method: PS
        is a 17s cap that costs real energy, and maintaining it through a loot
        cycle spends the pool on a mob that may never come - which is how you
        get a loot timeout, because the energy the bot is supposed to be
        banking for loot is going into re-casting a cap against empty space.

        So PS is an early-warning cast, not a permanent fixture. 2500 is the
        buffer zone: a mob has to be inside spirit range before the cap goes
        up, which is early enough to be assembled before anything is in
        ENGAGE_RADIUS, and late enough that idle looting costs nothing. The
        other three stay unconditional - Retribution, Balthazar's and Essence
        Bond are long timers whose value is in being up when the pull happens,
        and dropping them to save energy would cost more than it keeps.

        One consequence worth stating: while genuinely idle PS is DOWN, so the
        gate at the top of _run_local_skill_logic cannot be "PS is up". It has
        to be "PS is up, or nothing is a threat yet" - see that method.
        """
        player_id = Player.GetAgentID()
        if not player_id or Agent.IsDead(player_id):
            return False

        # The buffer zone, with the combat latch folded in - see _ps_wanted.
        # Computed once per call, and read before the loop so a mob walking
        # into range mid-loop is picked up on the next tick rather than costing
        # a wasted pass.
        ps_wanted = self._ps_wanted(now_ms)

        for skill_id in (
            PROT_SPIRIT_ID,
            RETRIBUTION_ID,
            BALTHAZARS_SPIRIT_ID,
            ESSENCE_BOND_ID,
        ):
            if skill_id == PROT_SPIRIT_ID and not ps_wanted:
                # No mob inside the buffer zone, so the cap has nothing to cap.
                # Skipped rather than cast: this is the loot-timeout fix.
                continue
            if not self._needs_recast(player_id, skill_id, now_ms):
                continue
            if not self._can_afford(self.CORE_RESERVE_POINTS):
                return False
            if (yield from self._cast_self(skill_id, now_ms)):
                return True
        return False
    def _battle_upkeep(self, now_ms: float) -> BuildCoroutine:
        """Vengeful Was Khanhei only. The build's actual survival engine.

        VwK is the heal everything else is bought around, so it is maintained
        and it is the ONLY thing in this method. Vengeful Weapon used to sit
        here beside it in the same loop, which made it fire on the same
        refresh cadence as the heal - it is damage, not survival, and spending
        the energy on it starved the very heal that was keeping the build
        alive. It now lives in _vengeful_weapon_if_surplus below, which only
        casts when there is energy genuinely to spare.

        Held back entirely with nothing in range: VwK is the slowest cast in
        the kit and there is no reason to spend it on empty space.

        The range test is THREAT_RADIUS, not ENGAGE_RADIUS, and that is the
        whole point of this method being range-aware. A caster does not walk
        into spellcast range before it opens up - it parks at 1500+ and shoots,
        which is comfortably outside 1248. Gating the heal on ENGAGE_RADIUS
        meant a kite caster switched VwK OFF while its projectiles were landing,
        which is the worst possible time to discover the build is blind past
        its own engage range. VwK is a reaction heal: it only ever fires when
        something is already hitting, so there is nothing to waste it on out
        here. The damage step below still uses ENGAGE_RADIUS, because there we
        genuinely need something we can reach.
        """
        player_id = Player.GetAgentID()
        if not player_id or Agent.IsDead(player_id):
            return False
        if self._foe_count(self.THREAT_RADIUS) == 0:
            return False

        if not self._needs_recast(player_id, VENGEFUL_WAS_KHANHEI_ID, now_ms):
            return False
        if not self._can_afford(self.CORE_RESERVE_POINTS):
            return False
        if (yield from self._cast_self(VENGEFUL_WAS_KHANHEI_ID, now_ms)):
            return True
        return False

    def _vengeful_weapon_if_surplus(self, now_ms: float) -> BuildCoroutine:
        """Vengeful Weapon (VW), maintained like any other damage enchant.

        VW used to be gated behind VWEAPON_SURPLUS_POINTS - 6.0 energy points on
        a 10-point bar, demanded AFTER PS and VwK were already funded, and cast
        last in the rotation. That combination meant it effectively never fired:
        the pool was already committed to survival by the time the check ran, so
        the surplus test failed every tick and VW sat unused through entire
        fights. Reversal of Damage, which is maintained the ordinary way, worked
        fine alongside it - the difference was never the skill, it was the
        gating.

        So VW is now a normal maintained damage enchant, on the same
        _needs_recast logic as everything else in _core_upkeep. The energy
        discipline is preserved, but expressed as ORDER rather than as a
        threshold: survival skills are earlier in the loop, and because each
        step returns on the first successful cast, the damage enchants only get
        what is left over. That is the same guarantee the surplus number was
        reaching for, without the number being set so high that it excluded
        itself.

        VwK must be up first. VW is damage, and this build does not trade the
        heal for it.
        """
        player_id = Player.GetAgentID()
        if not player_id or Agent.IsDead(player_id):
            return False
        if not self.IsSkillEquipped(VENGEFUL_WEAPON_ID):
            return False
        if self._foe_count() == 0:
            return False
        if not self._needs_recast(player_id, VENGEFUL_WEAPON_ID, now_ms):
            return False

        if not self._has_effect(player_id, VENGEFUL_WAS_KHANHEI_ID):
            return False

        if (yield from self._cast_self(VENGEFUL_WEAPON_ID, now_ms)):
            return True
        return False

    def _spirit_bond_for_gap(self, now_ms: float) -> BuildCoroutine:
        """Spirit Bond layered on as VwK wears off, before the heal drops.

        VwK is a timed heal and Spirit Bond is the regen that covers its
        expiry. Waiting until health actually dipped meant the build ran the
        last stretch of every VwK cycle unprotected, because the health gate
        only fired once damage had already landed.

        So this is a second trigger, ahead of the health one: when VwK is within
        SPIRIT_BOND_VWK_GAP_S of lapsing, Spirit Bond goes up. The two overlap
        deliberately - the point is to never have neither up.
        """
        player_id = Player.GetAgentID()
        if not player_id or Agent.IsDead(player_id):
            return False
        if self._has_effect(player_id, SPIRIT_BOND_ID):
            return False
        if not self._has_effect(player_id, VENGEFUL_WAS_KHANHEI_ID):
            return False

        vwk_remaining = self._effect_remaining(player_id, VENGEFUL_WAS_KHANHEI_ID)
        if vwk_remaining > self.SPIRIT_BOND_VWK_GAP_S:
            return False

        if not self._can_afford(self.CORE_RESERVE_POINTS):
            return False
        if (yield from self._cast_self(SPIRIT_BOND_ID, now_ms)):
            return True
        return False

    def _run_ooc_upkeep(self) -> BuildCoroutine:
        """Out of combat: the long-timer buffs, and PS only if something is near.

        Only _core_upkeep runs here. _battle_upkeep is skipped so the slow
        Vengeful casts are not burned on empty space, and no damage skill fires
        because there is nothing to fire it at.

        This is the method that runs for most of a farming run, and it is where
        the loot-timeout fix actually pays off. _core_upkeep threat-gates PS at
        AGGRO_RADIUS, so walking between mobs costs nothing on the cap - only
        on Retribution, Balthazar's and Essence Bond, which are long timers
        worth having ready. The moment something enters the buffer zone, PS
        starts assembling.

        The wait is short and unconditional on purpose: out of combat there is
        no reason to sit idle for a long tick, and this state lasts for most of
        a farming run.
        """
        now_ms = time.monotonic() * 1000.0
        if (yield from self._core_upkeep(now_ms)):
            return True
        yield from Routines.Yield.wait(250)
        return False

    def _damage_skill_ids(self) -> list[int]:
        """Every equipped VARIANT skill that contributes damage, in cast order.

        Read off the live bar rather than hardcoded, so a swapped variant is
        picked up without a code change - this is the whole reason the variant
        lives in optional_skills.

        Retribution is deliberately NOT here. It used to lead this list as the
        "primary attack", which is why it never went up until something was
        already in ENGAGE_RADIUS. It is a self buff on a long timer, so it is
        now owned entirely by _core_upkeep and cast once. Listing it in both
        places would have this loop re-requesting it at a target every
        CAST_COOLDOWN_MS, spending energy on a skill that is already up and
        re-activating nothing. One owner per skill.
        """
        ids: list[int] = []
        for variant_id in (
            REVERSAL_OF_DAMAGE_ID,
            SMITE_CONDITION_ID,
            LIGHT_OF_DELDRIMOR_ID,
            RADIATION_FIELD_ID,
            PAIN_INVERTER_ID,
            I_AM_UNSTOPPABLE_ID,
            EBON_BATTLE_STANDARD_WISDOM_ID,
        ):
            if self.IsSkillEquipped(variant_id):
                ids.append(variant_id)
                break
        return ids

    def _run_local_skill_logic(self) -> BuildCoroutine:
        """The rotation. One action per call, then return.

        Order is the build's whole thesis and should not be reordered casually.
        The organising principle is survival first, damage last, and no damage
        of any kind - enchants included - before the cap is up:

        0. Protective Spirit, as a GATE when threatened. If PS is down AND a
           mob is inside AGGRO_RADIUS, the build has no answer to damage, so
           nothing else fires until it is back. With no mob in range the gate
           steps aside entirely - PS is not maintained while idle, and treating
           "down" as a failure here would deadlock the rotation.
        1. Spirit Bond for the VwK gap. Placed above the health check because
           it prevents damage rather than answering it - the handover between
           two timed heals must never leave a dead tick.
        2. Spirit Bond on health. The degen counter and the backstop.
        3. Core upkeep: PS (threat-gated), Retribution, Balthazar's, Essence
           Bond.
        4. Battle upkeep: Vengeful Was Khanhei, maintained. The heal.
        5. Damage VARIANT against a real target. Retribution is not here - it
           is cast once from step 3, before any target exists.
        6. Vengeful Weapon, out of surplus energy only.

        Steps 1-6 each return immediately on a successful cast, so the tick
        performs exactly one action and re-evaluates. That is deliberate: this
        build's survival depends on the order the stack goes up, and a rotation
        that fired several skills per tick would break the ordering guarantee.
        """
        player_id = Player.GetAgentID()
        if not player_id or Agent.IsDead(player_id):
            yield from Routines.Yield.wait(500)
            return False

        now_ms = time.monotonic() * 1000.0

        # 0. Protective Spirit, as a GATE - but only when something is coming.
        # PS is not first in a list here, it is a gate: if the cap is down while
        # a mob is inside the buffer zone, the build has no answer to damage at
        # all, so no heal, no damage and no damage-enchant may go out before it.
        #
        # The AGGRO_RADIUS + latch condition is load-bearing and was added with
        # the threat gate in _core_upkeep. PS is deliberately NOT maintained
        # while idle - it costs energy the bot is trying to bank for loot - so
        # "PS is down" is the normal, correct state while walking to the next
        # mob. Testing only `not has_effect(PS)` here therefore deadlocked the
        # whole rotation: it would call _core_upkeep (which now correctly
        # refuses to cast PS with no threat), get nothing, wait, and repeat
        # forever without ever reaching step 1.
        #
        # _ps_wanted is the shared predicate, so this gate and _core_upkeep can
        # never disagree about whether the cap is wanted - which is what turns
        # "PS down mid-fight" into an immediate re-cast rather than a stall.
        if (
            not self._has_effect(player_id, PROT_SPIRIT_ID)
            and self._ps_wanted(now_ms)
        ):
            if (yield from self._core_upkeep(now_ms)):
                return True
            yield from Routines.Yield.wait(200)
            return False

        # 1. Spirit Bond for the VwK gap. Ahead of the health check, because
        # this one prevents damage rather than answering it.
        if (yield from self._spirit_bond_for_gap(now_ms)):
            return True

        # 2. Spirit Bond on health. The degen counter, and the backstop when
        # VwK is fully down and there is no timed gap left to anticipate.
        if not self._has_effect(player_id, SPIRIT_BOND_ID):
            if Agent.GetHealth(player_id) <= self.SPIRIT_BOND_HEALTH_FRACTION * Agent.GetMaxHealth(player_id):
                if self._can_afford(self.CORE_RESERVE_POINTS):
                    if (yield from self._cast_self(SPIRIT_BOND_ID, now_ms)):
                        return True

        # 3. Core upkeep: the rest of the permanent stack.
        if (yield from self._core_upkeep(now_ms)):
            return True

        # 4. Battle upkeep: VwK, the heal.
        if (yield from self._battle_upkeep(now_ms)):
            return True

        # 5. Damage, only against a real target and only from a safe position.
        target_id = self._nearest_foe_in_range()
        if target_id:
            for skill_id in self._damage_skill_ids():
                if not self._cooldown_ok(skill_id, now_ms):
                    continue
                if (yield from self.CastSkillID(
                    skill_id,
                    target_agent_id=target_id,
                    aftercast_delay=self._aftercast(skill_id),
                )):
                    self._last_cast_ms[skill_id] = now_ms
                    return True

        # 6. Vengeful Weapon, last of all and only out of surplus. Everything
        # above is survival; this is not. If the rotation is out of energy by
        # the time it gets here, that is the intended trade.
        if (yield from self._vengeful_weapon_if_surplus(now_ms)):
            return True

        # THREAT_RADIUS, not ENGAGE_RADIUS: _engaged answers "is anything
        # shooting me", and a caster at 1500 is shooting us while reporting
        # zero foes in engage range. Diagnostic only - nothing gates on it yet.
        self._engaged = bool(self._foe_count(self.THREAT_RADIUS))
        yield from Routines.Yield.wait(200)
        return False


