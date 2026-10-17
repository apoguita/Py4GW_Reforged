from Py4GWCoreLib import BuildMgr, Profession
from Py4GWCoreLib.Builds.Any.HeroAI import HeroAI_Build
from Py4GWCoreLib.Skill import Skill


Signet_of_Lost_Souls_ID = Skill.GetID("Signet_of_Lost_Souls")
Icy_Veins_ID = Skill.GetID("Icy_Veins")
Animate_Bone_Fiend_ID = Skill.GetID("Animate_Bone_Fiend")
Animate_Bone_Minions_ID = Skill.GetID("Animate_Bone_Minions")
Masochism_ID = Skill.GetID("Masochism")
Death_Nova_ID = Skill.GetID("Death_Nova")
Putrid_Bile_ID = Skill.GetID("Putrid_Bile")
Resurrection_Signet_ID = Skill.GetID("Resurrection_Signet")


class Icy_Veins_MM(BuildMgr):
    """PvE Icy Veins Minion Master (N/any).

    Initial library version: identify the current Icy MM bar and delegate
    casting to the standard HeroAI.  Dedicated follower/minion priorities can
    be layered on this class later without changing the build registration.
    """

    def __init__(self, match_only: bool = False):
        super().__init__(
            name="Icy Veins MM",
            required_primary=Profession.Necromancer,
            template_code="OABSUYDTVV1MUBVBbhoBKgCA",
            required_skills=[
                Icy_Veins_ID,
                Animate_Bone_Fiend_ID,
                Animate_Bone_Minions_ID,
                Masochism_ID,
            ],
            optional_skills=[
                Signet_of_Lost_Souls_ID,
                Death_Nova_ID,
                Putrid_Bile_ID,
                Resurrection_Signet_ID,
            ],
        )

        if match_only:
            return

        self.SetFallback("HeroAI", HeroAI_Build(standalone_fallback=True))
