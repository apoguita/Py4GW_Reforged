"""Icy Prism targeting and priority, owned by its Elementalist skill definition."""
from Py4GWCoreLib import Agent, AgentArray, GLOBAL_CACHE, Player, Range, Routines, Utils
from Py4GWCoreLib.EnemyBlacklist import EnemyBlacklist
from Py4GWCoreLib.enums_src.GameData_enums import Attribute
from ..types import SkillNature, SkillType

def HasWaterMagicHex(agent_id: int) -> bool:
    """Return whether the agent currently carries a Water Magic hex."""
    if not agent_id or not Agent.IsValid(agent_id) or not Agent.IsHexed(agent_id):
        return False

    effects = GLOBAL_CACHE.Effects.GetBuffs(agent_id) + GLOBAL_CACHE.Effects.GetEffects(agent_id)
    for effect in effects:
        skill_id = int(getattr(effect, "skill_id", 0) or 0)
        if not skill_id:
            continue
        skill_type, _ = GLOBAL_CACHE.Skill.GetType(skill_id)
        if skill_type != SkillType.Hex.value:
            continue
        attribute = GLOBAL_CACHE.Skill.Attribute.GetAttribute(skill_id)
        if int(getattr(attribute, "attribute_id", -1)) == Attribute.WaterMagic.value:
            return True
    return False

def TargetWaterHexedClusteredEnemy(
    area=Range.Spellcast.value,
    cluster_radius=Range.Nearby.value,
    min_nearby_others=0,
):
    """Choose a Water-hexed foe that maximizes Icy Prism's additional hits."""
    player_xy = Player.GetXY()
    enemy_ids = Routines.Agents.GetFilteredEnemyArray(player_xy[0], player_xy[1], area)
    blacklist = EnemyBlacklist()
    enemy_ids = [
        enemy_id
        for enemy_id in enemy_ids or []
        if Agent.IsValid(enemy_id)
        and Agent.IsAlive(enemy_id)
        and not blacklist.is_blacklisted(enemy_id)
    ]
    water_hexed = [enemy_id for enemy_id in enemy_ids if HasWaterMagicHex(enemy_id)]

    scored: list[tuple[int, float, int]] = []
    for target_id in water_hexed:
        target_xy = Agent.GetXY(target_id)
        nearby_others = sum(
            1
            for enemy_id in enemy_ids
            if enemy_id != target_id
            and Utils.Distance(target_xy, Agent.GetXY(enemy_id)) <= cluster_radius
        )
        if nearby_others < min_nearby_others:
            continue
        scored.append(
            (
                -nearby_others,
                Utils.Distance(player_xy, target_xy),
                target_id,
            )
        )

    if not scored:
        return 0
    scored.sort()
    return scored[0][2]

def select_target(distance=Range.Spellcast.value):
    return TargetWaterHexedClusteredEnemy(area=distance)


def select_priority(distance=Range.Spellcast.value):
    if TargetWaterHexedClusteredEnemy(area=distance, min_nearby_others=1):
        return SkillNature.OffensiveA.value
    return SkillNature.CustomN.value
