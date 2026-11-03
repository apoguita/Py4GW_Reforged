from Py4GWCoreLib import Profession, Routines, BuildMgr
from Py4GWCoreLib.Agent import Agent
from Py4GWCoreLib.Player import Player
from Py4GWCoreLib.Skill import Skill
from Py4GWCoreLib.Builds.Any.HeroAI import HeroAI_Build
from Py4GWCoreLib.Builds.Skills import HexRemovalPriority, SkillsTemplate


Unyielding_Aura_ID = Skill.GetID("Unyielding_Aura")
Dwaynas_Kiss_ID = Skill.GetID("Dwaynas_Kiss")
Orison_of_Healing_ID = Skill.GetID("Orison_of_Healing")
Patient_Spirit_ID = Skill.GetID("Patient_Spirit")
Seed_of_Life_ID = Skill.GetID("Seed_of_Life")
Spirit_Bond_ID = Skill.GetID("Spirit_Bond")
Protective_Spirit_ID = Skill.GetID("Protective_Spirit")
Draw_Conditions_ID = Skill.GetID("Draw_Conditions")
Remove_Hex_ID = Skill.GetID("Remove_Hex")
Cure_Hex_ID = Skill.GetID("Cure_Hex")
Leech_Signet_ID = Skill.GetID("Leech_Signet")
Great_Dwarf_Weapon_ID = Skill.GetID("Great_Dwarf_Weapon")
Vigorous_Spirit_ID = Skill.GetID("Vigorous_Spirit")


class Unyielding_Aura(BuildMgr):
    """UA-based healer. Recommended bar (slots are interchangeable):

    UA | Dwayna's Kiss | Orison of Healing | Patient Spirit |
    Seed of Life | Protective Spirit | Spirit Bond | Draw Conditions.

    The actual UA in-game template was not supplied, so the template_code
    below is only the project's usual BuildMgr placeholder; load your own
    bar manually. Elite UA is the sole required skill for recognition.
    """

    def __init__(self, match_only: bool = False):
        super().__init__(
            name="Unyielding Aura",
            required_primary=Profession.Monk,
            template_code="",
            required_skills=[Unyielding_Aura_ID],
            optional_skills=[
                Dwaynas_Kiss_ID,
                Orison_of_Healing_ID,
                Patient_Spirit_ID,
                Seed_of_Life_ID,
                Spirit_Bond_ID,
                Protective_Spirit_ID,
                Draw_Conditions_ID,
                Remove_Hex_ID,
                Cure_Hex_ID,
                Leech_Signet_ID,
                Great_Dwarf_Weapon_ID,
                Vigorous_Spirit_ID,
            ],
        )
        if match_only:
            return

        self.SetFallback("HeroAI", HeroAI_Build(standalone_fallback=True))
        self.SetSkillCastingFn(self._run_local_skill_logic)
        self.skills: SkillsTemplate = SkillsTemplate(self)

    def _maintain_ua(self):
        player_id = Player.GetAgentID()
        if not self.IsSkillEquipped(Unyielding_Aura_ID):
            return False
        if Routines.Checks.Effects.HasBuff(player_id, Unyielding_Aura_ID):
            return False
        return (yield from self.CastSkillID(
            Unyielding_Aura_ID,
            target_agent_id=player_id,
            aftercast_delay=250,
        ))

    def _run_local_skill_logic(self):
        # Seed must collect 1s HP history even while another skill is casting.
        if self.IsSkillEquipped(Seed_of_Life_ID):
            self.UpdatePartyHealthMonitor(sample_interval_ms=150, window_ms=1000)

        if not Routines.Checks.Skills.CanCast():
            return False

        # Maintain the elite before engagement. Never toggle it off deliberately.
        if not self.IsInAggro() and (yield from self._maintain_ua()):
            return True

        # React to spikes before direct heals can erase the 8% HP delta.
        if self.IsSkillEquipped(Seed_of_Life_ID) and (yield from self.skills.Monk.NoAttribute.Seed_of_Life()):
            return True
        if self.IsSkillEquipped(Spirit_Bond_ID) and (yield from self.skills.Monk.ProtectionPrayers.Spirit_Bond()):
            return True
        if self.IsSkillEquipped(Protective_Spirit_ID) and (yield from self.skills.Monk.ProtectionPrayers.Protective_Spirit(prebuff_melee_precombat=True)):
            return True

        # Restore UA after emergency spike protection, before normal heals.
        # UA amplifies all subsequent Monk healing spells.
        if (yield from self._maintain_ua()):
            return True

        # Direct heals, including self-healing via Orison.
        if self.IsSkillEquipped(Dwaynas_Kiss_ID) and (yield from self.skills.Monk.HealingPrayers.Dwaynas_Kiss()):
            return True
        if self.IsSkillEquipped(Orison_of_Healing_ID) and (yield from self.skills.Monk.HealingPrayers.Orison_of_Healing()):
            return True
        if self.IsSkillEquipped(Patient_Spirit_ID) and (yield from self.skills.Monk.HealingPrayers.Patient_Spirit()):
            return True

        if (yield from self.skills.Monk.NoAttribute.Remove_Hex(min_priority=HexRemovalPriority.HIGH)):
            return True
        if (yield from self.skills.Monk.HealingPrayers.Cure_Hex(min_priority=HexRemovalPriority.HIGH)):
            return True
        if self.IsSkillEquipped(Draw_Conditions_ID) and (yield from self.skills.Monk.ProtectionPrayers.Draw_Conditions()):
            return True

        player_energy_pct = float(Agent.GetEnergy(Player.GetAgentID()))
        if player_energy_pct >= 0.50:
            if (yield from self.skills.Monk.NoAttribute.Remove_Hex(min_priority=HexRemovalPriority.MEDIUM)):
                return True
            if (yield from self.skills.Monk.HealingPrayers.Cure_Hex(min_priority=HexRemovalPriority.MEDIUM)):
                return True

        if not self.IsInAggro():
            return False

        if self.IsSkillEquipped(Leech_Signet_ID) and (yield from self.skills.Mesmer.InspirationMagic.Leech_Signet()):
            return True
        if self.IsSkillEquipped(Vigorous_Spirit_ID) and (yield from self.skills.Monk.HealingPrayers.Vigorous_Spirit()):
            return True
        if player_energy_pct >= 0.50 and self.IsSkillEquipped(Great_Dwarf_Weapon_ID):
            if (yield from self.skills.Any.NoAttribute.Great_Dwarf_Weapon()):
                return True

        return False
