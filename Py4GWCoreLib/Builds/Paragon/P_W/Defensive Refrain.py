from Py4GWCoreLib import Profession
from Py4GWCoreLib import Routines
from Py4GWCoreLib.Builds.Any.HeroAI import HeroAI_Build
from Py4GWCoreLib import BuildMgr
from Py4GWCoreLib.Player import Player
from Py4GWCoreLib.Skill import Skill
from Py4GWCoreLib.Builds.Skills import SkillsTemplate

Heroic_Refrain_ID = Skill.GetID("Heroic_Refrain")
Anthem_of_Flame_ID = Skill.GetID("Anthem_of_Flame")
Theyre_on_Fire_ID = Skill.GetID("Theyre_on_Fire")
Hasty_Refrain_ID = Skill.GetID("Hasty_Refrain")
Aggressive_Refrain_ID = Skill.GetID("Aggressive_Refrain")
Stand_Your_Ground_ID = Skill.GetID("Stand_Your_Ground")
For_Great_Justice_ID = Skill.GetID("For_Great_Justice")
Theres_Nothing_to_Fear_ID = Skill.GetID("Theres_Nothing_to_Fear")
Save_Yourselves_luxon_ID = Skill.GetID("Save_Yourselves_luxon")
Save_Yourselves_kurzick_ID = Skill.GetID("Save_Yourselves_kurzick")
Never_Surrender_ID = Skill.GetID("Never_Surrender")
Blazing_Finale_ID = Skill.GetID("Blazing_Finale")
Ebon_Vanguard_Assassin_Support_ID = Skill.GetID("Ebon_Vanguard_Assassin_Support")
Ebon_Battle_Standard_of_Wisdom_ID = Skill.GetID("Ebon_Battle_Standard_of_Wisdom")
Ebon_Battle_Standard_of_Honor_ID = Skill.GetID("Ebon_Battle_Standard_of_Honor")
Protectors_Defense_ID = Skill.GetID("Protectors_Defense")
Cant_Touch_This_ID = Skill.GetID("Cant_Touch_This")
Aria_of_Zeal_ID = Skill.GetID("Aria_of_Zeal")
Aria_of_Restoration_ID = Skill.GetID("Aria_of_Restoration")
Make_Your_Time_ID = Skill.GetID("Make_Your_Time")
Angelic_Protection_ID = Skill.GetID("Angelic_Protection")

# Added for the PvX "P/any Heroic Refrain Spear" variants.
Mighty_Throw_ID = Skill.GetID("Mighty_Throw")
Vicious_Attack_ID = Skill.GetID("Vicious_Attack")
Spear_of_Redemption_ID = Skill.GetID("Spear_of_Redemption")
Go_for_the_Eyes_ID = Skill.GetID("Go_for_the_Eyes")
Find_Their_Weakness_ID = Skill.GetID("Find_Their_Weakness")
Fall_Back_ID = Skill.GetID("Fall_Back")
Bladeturn_Refrain_ID = Skill.GetID("Bladeturn_Refrain")
Lyric_of_Zeal_ID = Skill.GetID("Lyric_of_Zeal")
Mending_Refrain_ID = Skill.GetID("Mending_Refrain")
Energizing_Finale_ID = Skill.GetID("Energizing_Finale")
Burning_Refrain_ID = Skill.GetID("Burning_Refrain")
To_the_Limit_ID = Skill.GetID("To_the_Limit")
You_Move_Like_a_Dwarf_ID = Skill.GetID("You_Move_Like_a_Dwarf")
Finish_Him_ID = Skill.GetID("Finish_Him")
Great_Dwarf_Weapon_ID = Skill.GetID("Great_Dwarf_Weapon")
Breath_of_the_Great_Dwarf_ID = Skill.GetID("Breath_of_the_Great_Dwarf")
Blind_ID = Skill.GetID("Blind")


class Paragon_Refrain(BuildMgr):
    """P/any Heroic Refrain support Paragon.

    Ports PvX "Build:P/any Heroic Refrain Spear" and its variants on top of the
    original Defensive Refrain bar. The engine is Heroic Refrain: it is stacked
    on ourselves first so every copy we hand out is cast at the highest
    Leadership we can reach, then spread across the party. The echoes are
    renewed either when "They're on Fire!" expires normally or through the
    documented special case where reapplying "Can't Touch This!" ends its
    existing copy on affected allies.

    The spear attacks are clamped to spear range - which is the same
    1012 units as earshot, so staying in range to attack is the same thing as
    staying in range to renew.
    """

    def __init__(self, match_only: bool = False):
        super().__init__(
            name="Defensive Refrain",
            required_primary=Profession.Paragon,
            # BuildMgr uses enum value zero as the wildcard profession.
            # Warrior-only helpers below remain guarded by IsSkillEquipped.
            required_secondary=Profession(0),
            template_code="OQGkUNlnpiy0ZNQYPWNm72G4VhoH",
            # The elite is the complete archetype fingerprint. Other bar slots
            # determine available behavior, not whether this controller owns
            # the build.
            required_skills=[
                Heroic_Refrain_ID,
            ],
            # Everything here is driven below. That is not optional: declaring a
            # skill masks it out of the HeroAI fallback, so a declared skill the
            # build never casts is a skill nobody casts.
            optional_skills=[
                Save_Yourselves_luxon_ID,
                Save_Yourselves_kurzick_ID,
                Theres_Nothing_to_Fear_ID,
                Theyre_on_Fire_ID,
                Anthem_of_Flame_ID,
                Hasty_Refrain_ID,
                Never_Surrender_ID,
                Aggressive_Refrain_ID,
                Stand_Your_Ground_ID,
                For_Great_Justice_ID,
                Blazing_Finale_ID,
                Ebon_Vanguard_Assassin_Support_ID,
                Ebon_Battle_Standard_of_Wisdom_ID,
                Ebon_Battle_Standard_of_Honor_ID,
                Protectors_Defense_ID,
                Cant_Touch_This_ID,
                Aria_of_Zeal_ID,
                Aria_of_Restoration_ID,
                Make_Your_Time_ID,
                Angelic_Protection_ID,
                Mighty_Throw_ID,
                Vicious_Attack_ID,
                Spear_of_Redemption_ID,
                Go_for_the_Eyes_ID,
                Find_Their_Weakness_ID,
                Fall_Back_ID,
                Bladeturn_Refrain_ID,
                Lyric_of_Zeal_ID,
                Mending_Refrain_ID,
                Energizing_Finale_ID,
                Burning_Refrain_ID,
                To_the_Limit_ID,
                You_Move_Like_a_Dwarf_ID,
                Finish_Him_ID,
                Great_Dwarf_Weapon_ID,
                Breath_of_the_Great_Dwarf_ID,
            ],
        )
        if match_only:
            return

        self.SetFallback("HeroAI", HeroAI_Build(standalone_fallback=True))
        self.SetOOCFn(self._run_ooc)
        self.SetCombatFn(self._run_combat_phase)
        # Named skillbook, not skills: BuildMgr.skills is the list[int] of
        # equipped skill ids that ValidateSkills sorts, and shadowing it with
        # the helper namespace makes that call raise TypeError.
        self.skillbook: SkillsTemplate = SkillsTemplate(self)
        # Spear attacks are ranged, so there is no reason to prefer whatever is
        # closest - pick the target that dies soonest.
        self.spear_target_type = "EnemyInjured"

    def _run_upkeep(self):
        """Refrain maintenance. Runs in and out of combat.

        Everything here has to be reachable while travelling: the refrains are
        maintained continuously, not re-established at every pull.
        """
        # The elite, and the reason for the bar, must be first. Its helper casts
        # on self until the Leadership bootstrap reaches 20, then walks the
        # party. Refrains cast before that bootstrap would use the lower rank.
        if self.IsSkillEquipped(Heroic_Refrain_ID):
            if (yield from self.skillbook.Paragon.Leadership.Heroic_Refrain()):
                return True

            # Heroic_Refrain returns False both when bootstrap is complete and
            # when the second self cast is merely recharging. Only the live
            # rank-20 postcondition permits lower-rank refrains to be spread.
            if not self.skillbook.Paragon.Leadership.IsHeroicRefrainSelfReady():
                return True

        # Spread every equipped party refrain immediately after Heroic Refrain,
        # in or out of combat. Entering combat must not postpone an incomplete
        # distribution behind the rest of the combat rotation.
        if (yield from self._run_refrain_spreading()):
            return True

        # Aggressive Refrain is self-only and is maintained by the same expiring
        # shouts as the party refrains.
        if self.IsSkillEquipped(Aggressive_Refrain_ID) and (yield from self.skillbook.Paragon.Leadership.Aggressive_Refrain()):
            return True

        # Reapplying CTT ends its existing party shout and renews Heroic
        # Refrain and the other maintainable echoes on each affected ally.
        if self.IsSkillEquipped(Cant_Touch_This_ID) and (
            yield from self.skillbook.Paragon.Command.Cant_Touch_This(maintain_refrains=True)
        ):
            return True

        if self.IsSkillEquipped(Anthem_of_Flame_ID) and (yield from self.skillbook.Paragon.Leadership.Anthem_of_Flame()):
            return True

        # The renewal engine. PvX: this shout alone is enough to keep Heroic
        # Refrain up on the whole party, and it is also what keeps Aggressive
        # Refrain alive above.
        if self.IsSkillEquipped(Theyre_on_Fire_ID) and (yield from self.skillbook.Paragon.Leadership.Theyre_on_Fire()):
            return True

        if self.IsInAggro():
            return False

        # Travel speed. Ends on the holder's next attack, so the helper keeps it
        # to genuine out-of-combat movement.
        if self.IsSkillEquipped(Fall_Back_ID) and (yield from self.skillbook.Paragon.Command.Fall_Back()):
            return True

        return False

    def _run_refrain_spreading(self):
        """Spread the maintainable echoes over the party.

        Each helper picks an ally in earshot who does not have the echo yet, so
        together they converge on full coverage and then go quiet - which is why
        they are cheap to retry every tick.
        """
        if self.IsSkillEquipped(Mending_Refrain_ID) and (yield from self.skillbook.Paragon.Motivation.Mending_Refrain()):
            return True

        if self.IsSkillEquipped(Bladeturn_Refrain_ID) and (yield from self.skillbook.Paragon.Command.Bladeturn_Refrain()):
            return True

        if self.IsSkillEquipped(Energizing_Finale_ID) and (yield from self.skillbook.Paragon.Motivation.Energizing_Finale()):
            return True

        # Burning Refrain and Blazing Finale pay off most on the traditional
        # "They're on Fire!" variant, but remain valid maintainable echoes.
        if self.IsSkillEquipped(Burning_Refrain_ID) and (yield from self.skillbook.Paragon.Motivation.Burning_Refrain()):
            return True

        if self.IsSkillEquipped(Blazing_Finale_ID) and (yield from self.skillbook.Paragon.Motivation.Blazing_Finale()):
            return True

        if self.IsSkillEquipped(Hasty_Refrain_ID) and (yield from self.skillbook.Paragon.Motivation.Hasty_Refrain()):
            return True

        return False

    def _run_combat(self):
        """Party defence, adrenaline, offensive support and spear damage."""
        if self.IsSkillEquipped(Angelic_Protection_ID) and (yield from self.skillbook.Paragon.Leadership.Angelic_Protection(health_threshold=0.30)):
            return True

        # Defensive shouts first - they are the reason the build is taken, and
        # they are also the bar's energy engine, since Leadership refunds energy
        # per ally a shout or chant affects.
        if self.IsSkillEquipped(Theres_Nothing_to_Fear_ID) and (yield from self.skillbook.Any.NoAttribute.Theres_Nothing_to_Fear()):
            return True

        if self.IsSkillEquipped(Aria_of_Zeal_ID) and (yield from self.skillbook.Paragon.Motivation.Aria_of_Zeal()):
            return True

        if self.IsSkillEquipped(Aria_of_Restoration_ID) and (yield from self.skillbook.Paragon.Motivation.Aria_of_Restoration()):
            return True

        # Save Yourselves outranks the skills that charge it: when it is already
        # charged, spending the tick on an enabler instead delays the single
        # biggest mitigation on the bar. When it is not charged its adrenaline
        # check fails for free, and the enablers below run on the same tick's
        # next pass.
        if self.IsSkillEquipped(Save_Yourselves_kurzick_ID) and (yield from self.skillbook.Any.NoAttribute.Save_Yourselves_kurzick()):
            return True

        if self.IsSkillEquipped(Save_Yourselves_luxon_ID) and (yield from self.skillbook.Any.NoAttribute.Save_Yourselves_luxon()):
            return True

        if self.IsSkillEquipped(Stand_Your_Ground_ID) and (yield from self.skillbook.Paragon.Command.Stand_Your_Ground()):
            return True

        if self.IsSkillEquipped(Never_Surrender_ID) and (yield from self.skillbook.Paragon.Motivation.Never_Surrender()):
            return True

        if self.IsSkillEquipped(Protectors_Defense_ID) and (yield from self.skillbook.Warrior.NoAttribute.Protectors_Defense()):
            return True

        # Adrenaline enablers, below the payload they exist to charge.
        if self.IsSkillEquipped(Make_Your_Time_ID) and (yield from self.skillbook.Paragon.Leadership.Make_Your_Time()):
            return True

        if self.IsSkillEquipped(For_Great_Justice_ID) and (yield from self.skillbook.Warrior.NoAttribute.For_Great_Justice()):
            return True

        if self.IsSkillEquipped(To_the_Limit_ID) and (yield from self.skillbook.Warrior.Tactics.To_the_Limit()):
            return True

        # Offensive party support. "Go for the Eyes!" comes first because
        # Vicious Attack below waits on it.
        if self.IsSkillEquipped(Go_for_the_Eyes_ID) and (yield from self.skillbook.Paragon.Command.Go_for_the_Eyes()):
            return True

        if self.IsSkillEquipped(Find_Their_Weakness_ID) and (yield from self.skillbook.Paragon.Command.Find_Their_Weakness()):
            return True

        if self.IsSkillEquipped(Lyric_of_Zeal_ID) and (yield from self.skillbook.Paragon.Motivation.Lyric_of_Zeal()):
            return True

        # PvE slot.
        if self.IsSkillEquipped(Ebon_Vanguard_Assassin_Support_ID) and (yield from self.skillbook.Any.PvE.Ebon_Vanguard_Assassin_Support()):
            return True

        if self.IsSkillEquipped(Ebon_Battle_Standard_of_Honor_ID) and (yield from self.skillbook.Any.NoAttribute.Ebon_Battle_Standard_of_Honor()):
            return True

        if self.IsSkillEquipped(Ebon_Battle_Standard_of_Wisdom_ID) and (yield from self.skillbook.Any.NoAttribute.Ebon_Battle_Standard_of_Wisdom()):
            return True

        if self.IsSkillEquipped(Great_Dwarf_Weapon_ID) and (yield from self.skillbook.Any.NoAttribute.Great_Dwarf_Weapon()):
            return True

        if self.IsSkillEquipped(Breath_of_the_Great_Dwarf_ID) and (yield from self.skillbook.Any.NoAttribute.Breath_of_the_Great_Dwarf()):
            return True

        if self.IsSkillEquipped(You_Move_Like_a_Dwarf_ID) and (yield from self.skillbook.Any.NoAttribute.You_Move_Like_a_Dwarf()):
            return True

        if self.IsSkillEquipped(Finish_Him_ID) and (yield from self.skillbook.Any.NoAttribute.Finish_Him()):
            return True

        # Mid-fight top-up: allies who died and were resurrected have lost their
        # echoes. Below everything urgent, above filler.
        if (yield from self._run_refrain_spreading()):
            return True

        if (yield from self._run_spear_attacks()):
            return True

        if (yield from self.AutoAttack()):
            return True

        return False

    def _run_spear_attacks(self):
        """Spear chain, ordered by what the current situation is worth.

        Spear of Redemption jumps the queue while we are blinded: a blinded
        attack misses, and the miss is what strips the Blindness - so the skill
        is worth more as a condition removal than as damage.

        Vicious Attack then outranks Mighty Throw, despite Mighty Throw hitting
        harder. Its gate only passes while "Go for the Eyes!" is up, and that
        shout buffs the next attack only - whichever spear skill goes first
        spends the charge. A near-guaranteed Deep Wound is worth more than the
        damage difference, so Vicious Attack should be the one that spends it.
        When "Go for the Eyes!" is not on the bar the gate is inert and this is
        simply the cheaper attack going first.
        """
        has_spear_of_redemption = self.IsSkillEquipped(Spear_of_Redemption_ID)
        # Kept separate from the equipment check: folding the two together makes
        # a blinded Paragon read as "not blinded" on every bar that does not
        # carry the answer to it, which is the one case a future caller reading
        # this flag would most need it to be right.
        is_blinded = Routines.Checks.Agents.HasEffect(Player.GetAgentID(), Blind_ID)

        if has_spear_of_redemption and is_blinded and (
            yield from self.skillbook.Paragon.SpearMastery.Spear_of_Redemption()
        ):
            return True

        # Spear of Redemption above is the only attack worth throwing blind,
        # because its miss is the point. Every other attack skill would be spent
        # and put on full recharge for a swing that almost certainly misses, so
        # once it has had its chance - unequipped, or recharging - stop here and
        # let the free auto-attack take the miss instead.
        if is_blinded:
            return False

        if self.IsSkillEquipped(Vicious_Attack_ID) and (
            yield from self.skillbook.Paragon.SpearMastery.Vicious_Attack(require_critical_buff=True)
        ):
            return True

        if self.IsSkillEquipped(Mighty_Throw_ID) and (yield from self.skillbook.Paragon.SpearMastery.Mighty_Throw()):
            return True

        if has_spear_of_redemption and (yield from self.skillbook.Paragon.SpearMastery.Spear_of_Redemption()):
            return True

        return False

    def _run_ooc(self):
        """Evaluate travelling upkeep from current state on every fresh tick."""
        if not Routines.Checks.Skills.CanCast():
            return False

        return (yield from self._run_upkeep())

    def _run_combat_phase(self):
        """Evaluate upkeep before combat work without a cross-phase continuation."""
        if not Routines.Checks.Skills.CanCast():
            return False

        if (yield from self._run_upkeep()):
            return True

        if not self.IsInAggro():
            return False

        if (yield from self._run_combat()):
            return True

        return False
