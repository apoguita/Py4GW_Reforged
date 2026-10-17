from Py4GWCoreLib import GLOBAL_CACHE, BuildMgr, Profession, Routines
from Py4GWCoreLib.Agent import Agent
from Py4GWCoreLib.Player import Player
from Py4GWCoreLib.Builds.Any.HeroAI import HeroAI_Build
from Py4GWCoreLib.Skill import Skill
from Py4GWCoreLib.Builds.Skills import SkillsTemplate


Spiteful_Spirit_ID = Skill.GetID("Spiteful_Spirit")
Arcane_Echo_ID = Skill.GetID("Arcane_Echo")
Signet_of_Lost_Souls_ID = Skill.GetID("Signet_of_Lost_Souls")
Enfeebling_Blood_ID = Skill.GetID("Enfeebling_Blood")
Weaken_Armor_ID = Skill.GetID("Weaken_Armor")
Mark_of_Pain_ID = Skill.GetID("Mark_of_Pain")
Foul_Feast_ID = Skill.GetID("Foul_Feast")


# Keep enough energy to seed Arcane Echo and immediately cast Spiteful Spirit.
ARCANE_ECHO_MIN_ENERGY = 30.0
SIGNET_ENERGY_CEILING = 0.60


class Spiteful_Spirit(BuildMgr):
    """Generic PvE Spiteful Spirit controller.

    Matching deliberately requires only Necromancer primary + Spiteful Spirit.
    Arcane Echo and the locally-supported utility skills are optional. Other
    bar slots remain available to the standard HeroAI fallback.
    """

    def __init__(self, match_only: bool = False):
        super().__init__(
            name="Spiteful Spirit",
            required_primary=Profession.Necromancer,
            template_code="AAAAAAAAAAAAAAAA",
            required_skills=[
                Spiteful_Spirit_ID,
            ],
            optional_skills=[
                Arcane_Echo_ID,
                Signet_of_Lost_Souls_ID,
                Enfeebling_Blood_ID,
                Weaken_Armor_ID,
                Mark_of_Pain_ID,
                Foul_Feast_ID,
            ],
        )

        if match_only:
            return

        self.SetFallback("HeroAI", HeroAI_Build(standalone_fallback=True))
        self.SetSkillCastingFn(self._run_local_skill_logic)
        self.skills: SkillsTemplate = SkillsTemplate(self)

    def _run_local_skill_logic(self):
        if not Routines.Checks.Skills.CanCast():
            return False

        player_id = Player.GetAgentID()
        arcane_echo_active = Routines.Checks.Agents.HasEffect(player_id, Arcane_Echo_ID)

        # Seed Arcane Echo only when the original SS is ready and we have enough
        # energy to cast Echo + the first SS immediately afterwards.
        ss_slot = GLOBAL_CACHE.SkillBar.GetSlotBySkillID(Spiteful_Spirit_ID)
        ss_is_ready = ss_slot != 0 and Routines.Checks.Skills.IsSkillSlotReady(ss_slot)
        player_energy_abs = Agent.GetEnergy(player_id) * Agent.GetMaxEnergy(player_id)

        if (
            self.IsSkillEquipped(Arcane_Echo_ID)
            and not arcane_echo_active
            and ss_is_ready
            and player_energy_abs >= ARCANE_ECHO_MIN_ENERGY
            and (self.IsInAggro() or self.IsCloseToAggro())
            and (yield from self.skills.Mesmer.NoAttribute.Arcane_Echo())
        ):
            return True

        # If Arcane Echo is waiting to copy SS, try SS first. Crucially, do
        # NOT hard-lock the whole build if SS was interrupted / is unavailable:
        # otherwise the controller can sit idle for the full Echo window.
        ss_attempted_while_echo_active = False
        if arcane_echo_active:
            ss_attempted_while_echo_active = True
            if (yield from self.skills.Necromancer.Curses.Spiteful_Spirit()):
                return True

        # Foul Feast is a reactive party cleanse and is useful even outside
        # active aggro. If Echo is still waiting because SS was interrupted,
        # this may consume Echo by copying Foul Feast; that is intentionally
        # preferable to freezing the build and doing nothing.
        if self.IsSkillEquipped(Foul_Feast_ID) and (
            yield from self.skills.Necromancer.SoulReaping.Foul_Feast()
        ):
            return True

        if not self.IsInAggro():
            return False

        # Main SS cast, or Arcane Echo's copied SS if the original slot is now
        # recharging. Skip this duplicate call when Echo already attempted SS
        # earlier in the same tick.
        if not ss_attempted_while_echo_active:
            last_ss_target_id = getattr(self, "_last_spiteful_spirit_target_id", 0)
            if (yield from self.skills.Necromancer.Curses.Spiteful_Spirit(
                exclude_target_id=last_ss_target_id if self.IsSkillEquipped(Arcane_Echo_ID) else 0,
            )):
                return True

        # Energy recovery. Same ceiling already used by the existing Necro Prot
        # controller in this library.
        if self.IsSkillEquipped(Signet_of_Lost_Souls_ID) and (
            yield from self.skills.Necromancer.SoulReaping.Signet_of_Lost_Souls(
                max_self_energy_pct=SIGNET_ENERGY_CEILING,
            )
        ):
            return True

        # Mark of Pain: use it only on a worthwhile pack target. The helper
        # avoids overwriting an existing Mark and skips nearly-dead enemies.
        if self.IsSkillEquipped(Mark_of_Pain_ID) and (
            yield from self.skills.Necromancer.Curses.Mark_of_Pain()
        ):
            return True

        # Optional local Curses already implemented in the skill library.
        if self.IsSkillEquipped(Enfeebling_Blood_ID) and (
            yield from self.skills.Necromancer.Curses.Enfeebling_Blood()
        ):
            return True

        if self.IsSkillEquipped(Weaken_Armor_ID) and (
            yield from self.skills.Necromancer.Curses.Weaken_Armor()
        ):
            return True

        return False
