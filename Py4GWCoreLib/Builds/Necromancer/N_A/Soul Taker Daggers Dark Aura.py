from __future__ import annotations

from Py4GWCoreLib import BuildMgr, Profession, Range, Routines
from Py4GWCoreLib.Agent import Agent
from Py4GWCoreLib.Builds.Any.HeroAI import HeroAI_Build
from Py4GWCoreLib.Builds.Skills import SkillsTemplate
from Py4GWCoreLib.Player import Player
from Py4GWCoreLib.Skill import Skill
from Py4GWCoreLib.py4gwcorelib_src.Utils import Utils


JAGGED_STRIKE_ID = Skill.GetID("Jagged_Strike")
FOX_FANGS_ID = Skill.GetID("Fox_Fangs")
DEATH_BLOSSOM_ID = Skill.GetID("Death_Blossom")
MASOCHISM_ID = Skill.GetID("Masochism")
DARK_AURA_ID = Skill.GetID("Dark_Aura")
SOUL_TAKER_ID = Skill.GetID("Soul_Taker")
I_AM_UNSTOPPABLE_ID = Skill.GetID("I_Am_Unstoppable")
DRUNKEN_MASTER_ID = Skill.GetID("Drunken_Master")

# dagger_status is read off the target: 0 = idle, 1 = lead landed,
# 2 = off-hand landed, 3 = dual landed (chain complete).
MID_COMBO_DAGGER_STATUS = (1, 2)


class Soul_Taker_Daggers_Dark_Aura(BuildMgr):
    """N/A Soul Taker dagger spammer, Dark Aura variant.

    Soul Taker makes every dagger swing sacrifice health, and Dark Aura turns
    each of those sacrifices into armor-ignoring shadow damage around this
    character. The aura therefore has to sit on *us*, and we have to stay in
    melee contact - the dagger chain is both the damage and the trigger.
    """

    def __init__(self, match_only: bool = False):
        super().__init__(
            name="Soul Taker Daggers Dark Aura",
            required_primary=Profession.Necromancer,
            required_secondary=Profession.Assassin,
            template_code="OAdTUYT2Tyhhh5gZLkO4rmmUVE",
            required_skills=[
                JAGGED_STRIKE_ID,
                FOX_FANGS_ID,
                DEATH_BLOSSOM_ID,
                MASOCHISM_ID,
                DARK_AURA_ID,
                SOUL_TAKER_ID,
            ],
            # The two PvE slots are what variants of this bar swap out, so they
            # score the match without being required to make it.
            optional_skills=[
                I_AM_UNSTOPPABLE_ID,
                DRUNKEN_MASTER_ID,
            ],
        )
        if match_only:
            return

        self.SetFallback("HeroAI", HeroAI_Build(standalone_fallback=True))
        self.SetSkillCastingFn(self._run_local_skill_logic)
        self.skillbook: SkillsTemplate = SkillsTemplate(self)
        # Dark Aura hits foes adjacent to us and Death Blossom hits foes
        # adjacent to the target, so a clustered pick pays out twice.
        self.dagger_target_type = "EnemyClustered"

    def _is_in_melee_contact(self, target_agent_id: int) -> bool:
        if not target_agent_id or not Agent.IsValid(target_agent_id) or Agent.IsDead(target_agent_id):
            return False
        return Utils.Distance(Player.GetXY(), Agent.GetXY(target_agent_id)) <= Range.Adjacent.value

    def _auto_attack_cluster(self):
        return (yield from self.AutoAttack(target_type=self.dagger_target_type))

    def _should_upkeep(self, skill_id: int, mid_chain: bool) -> bool:
        """Allow upkeep casts freely, but mid-combo only when the buff is gone.

        A routine refresh can wait a swing or two rather than clip a pending
        chain step. A buff that has actually dropped cannot: without Soul Taker
        or Dark Aura the bar does almost no damage at all, so that is worth
        interrupting the combo for.
        """
        if not self.IsSkillEquipped(skill_id):
            return False
        if not mid_chain:
            return True
        return not Routines.Checks.Agents.HasEffect(Player.GetAgentID(), skill_id)

    def _run_local_skill_logic(self):
        if not (self.IsInAggro() or self.IsCloseToAggro()):
            return False

        # Never chain-gated, and evaluated before anything that could return
        # early: while it is off cooldown the helper records that we were
        # knocked down, which is what lets it fire again just after a
        # knockdown rather than only during one.
        # contact_count is left to the helper: it runs the same adjacency scan
        # itself, but only once its cheap gates have passed. Computing it here
        # would pay for a full enemy-array scan on every tick of the skill's
        # uptime and on every tick we are only close to aggro.
        if self.IsSkillEquipped(I_AM_UNSTOPPABLE_ID) and (
            yield from self.skillbook.Any.NoAttribute.I_Am_Unstoppable(
                min_adjacent_enemies=2,
                refresh_window_ms=1000,
                aftercast_delay=150,
            )
        ):
            return True

        target_agent_id = self.current_target_id
        in_melee_contact = self._is_in_melee_contact(target_agent_id)
        mid_chain = in_melee_contact and Agent.GetDaggerStatus(target_agent_id) in MID_COMBO_DAGGER_STATUS

        # Enchantments snapshot attributes on cast, so Masochism's +2 Death
        # Magic / Soul Reaping has to be up before Soul Taker and Dark Aura are
        # applied - that is what makes the aura hit harder and last longer.
        if self._should_upkeep(MASOCHISM_ID, mid_chain) and (
            yield from self.skillbook.Necromancer.SoulReaping.Masochism()
        ):
            return True

        # Soul Taker is the sacrifice engine that detonates the aura on every
        # swing, so it goes up before the aura it feeds.
        if self._should_upkeep(SOUL_TAKER_ID, mid_chain) and (
            yield from self.skillbook.Necromancer.SoulReaping.Soul_Taker(refresh_window_ms=2000)
        ):
            return True

        # self_only: the aura bills its caster for every sacrifice the enchanted
        # ally makes, so on this bar it belongs on us and nowhere else. Left to
        # normal party targeting it would drift to another Necromancer as soon
        # as our own copy was up, and we would pay for their attacks.
        if self._should_upkeep(DARK_AURA_ID, mid_chain) and (
            yield from self.skillbook.Necromancer.DeathMagic.Dark_Aura(
                required_skill_id=SOUL_TAKER_ID,
                other_ally=False,
                self_only=True,
            )
        ):
            return True

        # Chain-gated mostly because the helper can insert a drink wait.
        if self._should_upkeep(DRUNKEN_MASTER_ID, mid_chain) and (
            yield from self.skillbook.Any.PvE.Drunken_Master(refresh_window_ms=2000)
        ):
            return True

        # Closing to contact is part of the damage rotation here, not filler:
        # the aura only burns foes adjacent to us.
        if not in_melee_contact and (yield from self._auto_attack_cluster()):
            return True

        # Finisher first. Each helper self-gates on a mutually exclusive dagger
        # status, so at most one can fire per tick and the combo sequences
        # itself - Jagged Strike -> Fox Fangs -> Death Blossom.
        if (yield from self.skillbook.Assassin.DaggerMastery.Death_Blossom()):
            return True

        if (yield from self.skillbook.Assassin.DaggerMastery.Fox_Fangs()):
            return True

        if (yield from self.skillbook.Assassin.DaggerMastery.Jagged_Strike()):
            return True

        if (yield from self._auto_attack_cluster()):
            return True

        return False
