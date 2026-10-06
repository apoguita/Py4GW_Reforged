import time

from Py4GWCoreLib import BuildMgr, Profession, Routines, GLOBAL_CACHE, AgentArray
from Py4GWCoreLib.Player import Player
from Py4GWCoreLib.Agent import Agent
from Py4GWCoreLib.Builds.Any.HeroAI import HeroAI_Build
from Py4GWCoreLib.Skill import Skill
from Py4GWCoreLib.Builds.Skills import SkillsTemplate


# Required: signature skills used to match the Aura of the Lich MM archetype.
AURA_OF_THE_LICH_ID = Skill.GetID("Aura_of_the_Lich")
ANIMATE_BONE_FIEND_ID = Skill.GetID("Animate_Bone_Fiend")
MASOCHISM_ID = Skill.GetID("Masochism")

# Optional skills owned by this controller. Other bar slots are deliberately not
# listed here so the HeroAI fallback remains free to use them.
PUTRID_BILE_ID = Skill.GetID("Putrid_Bile")
BLOOD_OF_THE_MASTER_ID = Skill.GetID("Blood_of_the_Master")


# Refresh Aura only near the end of its duration.
AURA_REFRESH_WINDOW_MS = 2000

# Blood of the Master safety policy.
# The live skill sacrifices 5% max HP + 2% per undead ally healed, so we keep a
# large post-cast safety reserve and never let the generic HeroAI spam it.
BLOOD_MASTER_INJURED_HP_PCT = 0.50
BLOOD_MASTER_MIN_INJURED_OWN_MINIONS = 2
BLOOD_MASTER_MIN_INTERVAL_MS = 4500.0
BLOOD_MASTER_POST_CAST_HP_RESERVE = 0.35


class Aura_of_the_Lich_MM(BuildMgr):
    """PvE Aura of the Lich Minion Master.

    Matching requires Necromancer primary + Aura of the Lich + Animate Bone
    Fiend + Masochism. No secondary profession is required.

    The structure intentionally mirrors the existing Necro_Prot build:
    - register a HeroAI fallback;
    - register one local skill-casting handler;
    - expose SkillsTemplate helpers;
    - own only the skills for which this build has dedicated logic.
    """

    def __init__(self, match_only: bool = False):
        super().__init__(
            name="Aura of the Lich MM",
            required_primary=Profession.Necromancer,
            template_code="OAljUwGpZSyBUBKg4Bbh1Y7Y1bA",
            required_skills=[
                AURA_OF_THE_LICH_ID,
                ANIMATE_BONE_FIEND_ID,
                MASOCHISM_ID,
            ],
            optional_skills=[
                PUTRID_BILE_ID,
                BLOOD_OF_THE_MASTER_ID,
            ],
        )
        if match_only:
            return

        self.SetFallback("HeroAI", HeroAI_Build(standalone_fallback=True))
        self.SetSkillCastingFn(self._run_local_skill_logic)
        self.skills: SkillsTemplate = SkillsTemplate(self)
        self._last_blood_master_cast_ms = -1_000_000.0

    def _run_local_skill_logic(self):
        if not Routines.Checks.Skills.CanCast():
            return False

        # Priority 1: keep Masochism active before using Death Magic skills.
        if (yield from self.skills.Necromancer.SoulReaping.Masochism()):
            return True

        # Priority 2: maintain Aura of the Lich with a conservative refresh.
        if (yield from self._aura_of_the_lich()):
            return True

        # Priority 3: Blood of the Master is locally controlled because the
        # generic HeroAI tends to overuse it while minions are degenerating.
        if self.IsSkillEquipped(BLOOD_OF_THE_MASTER_ID) and (
            yield from self._blood_of_the_master()
        ):
            return True

        # Priority 4: use available corpses for Bone Fiends.
        if (yield from self.skills.Necromancer.DeathMagic.Animate_Bone_Fiend()):
            return True

        # Priority 5: optional Putrid Bile logic already present in DeathMagic.
        if self.IsSkillEquipped(PUTRID_BILE_ID) and (
            yield from self.skills.Necromancer.DeathMagic.Putrid_Bile()
        ):
            return True

        # Returning False lets the registered HeroAI fallback handle every
        # remaining skill on the actual bar that is not owned above.
        return False

    def _aura_of_the_lich(self):
        """Maintain Aura of the Lich without depending on a custom DeathMagic helper."""
        if not self.IsSkillEquipped(AURA_OF_THE_LICH_ID):
            return False

        # Do not waste the enchantment while travelling through a clear area.
        if not (self.IsInAggro() or self.IsCloseToAggro()):
            return False

        player_agent_id = Player.GetAgentID()

        if Routines.Checks.Agents.HasEffect(player_agent_id, AURA_OF_THE_LICH_ID):
            remaining_ms = int(
                GLOBAL_CACHE.Effects.GetEffectTimeRemaining(
                    player_agent_id,
                    AURA_OF_THE_LICH_ID,
                ) or 0
            )
            if remaining_ms > AURA_REFRESH_WINDOW_MS:
                return False

        return (yield from self.CastSkillID(
            skill_id=AURA_OF_THE_LICH_ID,
            log=False,
            aftercast_delay=250,
        ))

    def _blood_of_the_master(self):
        """Heal our minions conservatively without draining the Necromancer.

        Policy:
        - at least two allied living minions must be below 50% HP, matching the
          native hero usage rule;
        - at least 4.5 seconds between casts;
        - estimate the current sacrifice cost (5% + 2% per living allied
          minion) and preserve at least 35% HP after the cast.
        """
        if not self.IsSkillEquipped(BLOOD_OF_THE_MASTER_ID):
            return False

        now_ms = time.monotonic() * 1000.0
        if now_ms - self._last_blood_master_cast_ms < BLOOD_MASTER_MIN_INTERVAL_MS:
            return False

        self_agent_id = self._resolve_self_agent_id()
        all_minions = [
            agent_id
            for agent_id in (AgentArray.GetMinionArray() or [])
            if Agent.IsAlive(agent_id)
        ]

        # Blood of the Master heals ALL allied minions, including minions owned
        # by another minion master. Mirror the native hero usage rule: cast once
        # at least two allied minions are below 50% HP. Do not filter by owner_id.
        injured_minions = [
            agent_id
            for agent_id in all_minions
            if Agent.GetHealth(agent_id) < BLOOD_MASTER_INJURED_HP_PCT
        ]

        if len(injured_minions) < BLOOD_MASTER_MIN_INJURED_OWN_MINIONS:
            return False

        player_hp_pct = Agent.GetHealth(self_agent_id)

        # The skill sacrifices +2% max HP per minion actually healed. Counting
        # all allied living minions is deliberately conservative and prevents
        # an unsafe cast when another MM is present.
        projected_sacrifice = 0.05 + (0.02 * len(all_minions))
        if player_hp_pct - projected_sacrifice < BLOOD_MASTER_POST_CAST_HP_RESERVE:
            return False

        casted = yield from self.CastSkillID(
            skill_id=BLOOD_OF_THE_MASTER_ID,
            log=False,
            aftercast_delay=250,
        )
        if casted:
            self._last_blood_master_cast_ms = time.monotonic() * 1000.0
            return True

        return False
