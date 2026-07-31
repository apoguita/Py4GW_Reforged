from typing import Optional
from Py4GWCoreLib import GLOBAL_CACHE, Allegiance, Overlay, Map, Agent, Range
from Py4GWCoreLib.GlobalCache.SharedMemory import AccountStruct
from .constants import MAX_NUM_PLAYERS
from .targeting import *
from .cache_data import CacheData
from Py4GWCoreLib.py4gwcorelib_src.FrameCache import frame_cache

def _account_key(account: AccountStruct):
    return (account.AccountEmail, int(account.AgentData.AgentID))


def _agent_key(agent_id, *_, **__):
    return int(agent_id)


def _agent_skill_key(agent_id, skill_id, *_, **__):
    return (int(agent_id), int(skill_id))


def IsValidEnergyValue(energy: float) -> bool:
    return 0.0 <= float(energy) <= 1.0


@frame_cache(category="utils", source_lib="SameMapAsAccount", key=_account_key)
def SameMapAsAccount(account : AccountStruct):
    if not Map.IsMapReady():
        return False
    
    own_map_id = Map.GetMapID()
    own_region = Map.GetRegion()[0]
    own_district = Map.GetDistrict()
    own_language = Map.GetLanguage()[0]
    return own_map_id == account.AgentData.Map.MapID and own_region == account.AgentData.Map.Region and own_district == account.AgentData.Map.District and own_language == account.AgentData.Map.Language

@frame_cache(category="utils", source_lib="SameMapOrPartyAsAccount", key=_account_key)
def SameMapOrPartyAsAccount(account : AccountStruct):
    if not Map.IsMapReady():
        return False
    
    own_map_id = Map.GetMapID()
    own_region = Map.GetRegion()[0]
    own_district = Map.GetDistrict()
    own_language = Map.GetLanguage()[0]
    party_members = [GLOBAL_CACHE.Party.Players.GetAgentIDByLoginNumber(party_member.login_number) for party_member in GLOBAL_CACHE.Party.GetPlayers()]
    
    same_map = own_map_id == account.AgentData.Map.MapID and own_district == account.AgentData.Map.District and own_language == account.AgentData.Map.Language
    
    if same_map and account.AgentData.AgentID in party_members and account.AgentPartyData.PartyID == GLOBAL_CACHE.Party.GetPartyID():
        return True
    
    return same_map and own_region == account.AgentData.Map.Region

@frame_cache(category="utils", source_lib="DistanceFromLeader")
def DistanceFromLeader():
    return Utils.Distance(Agent.GetXY(GLOBAL_CACHE.Party.GetPartyLeaderID()),Agent.GetXY(Player.GetAgentID()))

@frame_cache(category="utils", source_lib="DistanceFromWaypoint")
def DistanceFromWaypoint(posX, posY):
    distance = Utils.Distance((posX, posY), Player.GetXY())
    return distance if distance > 200 else 0


""" main configuration helpers """
@frame_cache(category="utils", source_lib="IsPartyMember", key=_agent_key)
def IsPartyMember(agent_id, live_cached_data : Optional[CacheData] = None) -> bool:
    cached_data: CacheData = live_cached_data if live_cached_data is not None else CacheData()
                
    for acc in cached_data.party:
        if acc.IsSlotActive and acc.AgentData.AgentID == agent_id and SameMapOrPartyAsAccount(acc) and acc.AgentPartyData.PartyID == cached_data.party.party_id:
            return True
        
    allegiance , _ = Agent.GetAllegiance(agent_id)
    if (allegiance == Allegiance.SpiritPet.value and 
        not Agent.IsSpawned(agent_id)):
        return True
    
    return False

@frame_cache(category="utils", source_lib="GetEnergyValues", key=_agent_key)
def GetEnergyValues(agent_id, live_cached_data : Optional[CacheData] = None):
    if live_cached_data is not None:
        cached_data = live_cached_data
    else:
        cached_data: CacheData = CacheData()
        
    if cached_data is not None:
        acc = cached_data.party.get_by_player_id(agent_id)
        if (
            acc is not None
            and acc.IsSlotActive
            and acc.AgentPartyData.PartyID == cached_data.party.party_id
        ):
            energy = float(acc.AgentData.Energy.Current)
            if IsValidEnergyValue(energy):
                return energy

    return -1.0

@frame_cache(category="utils", source_lib="CheckForEffect", key=_agent_skill_key)
def CheckForEffect(agent_id, skill_id, cached_data : Optional[CacheData] = None) -> bool:
    """
    check if the given agent has the effect or buff with the given skill id
    """    
    cached_data = cached_data if cached_data is not None else CacheData()

    owned_pet_id = GLOBAL_CACHE.Party.Pets.GetPetID(Player.GetAgentID())
    if agent_id == Player.GetAgentID() or (owned_pet_id != 0 and agent_id == owned_pet_id):
        # Self-upkeep should use live local effects rather than shared-memory party
        # state, which can lag and suppress recasts of expired buffs.
        return GLOBAL_CACHE.Effects.HasEffect(agent_id, skill_id)
    
    for acc in cached_data.party:
        if acc.IsSlotActive and acc.AgentData.AgentID == agent_id and SameMapOrPartyAsAccount(acc) and acc.AgentPartyData.PartyID == cached_data.party.party_id:
            return any(buff.SkillId == skill_id for buff in acc.AgentData.Buffs.Buffs)        

    allegiance, allegiance_name = Agent.GetAllegiance(agent_id)
    if allegiance == Allegiance.SpiritPet.value:
        # Shared memory should be the source of truth for pets and spirits. If a
        # spirit/pet target is not represented there and it's not our own pet,
        # treat it as already buffed to avoid recast loops on inaccessible units.
        return True

    if allegiance_name in ("Ally", "NPC/Minipet"):
        return True

    return GLOBAL_CACHE.Effects.HasEffect(agent_id, skill_id)

@frame_cache(category="utils", source_lib="HasIllusionaryWeaponry", key=_agent_key)
def HasIllusionaryWeaponry(agent_id, cached_data : Optional[CacheData] = None) -> bool:
    cached_data = cached_data if cached_data is not None else CacheData()
    iw_skill_ids = (
        GLOBAL_CACHE.Skill.GetID("Illusionary_Weaponry"),
        GLOBAL_CACHE.Skill.GetID("Illusionary_Weaponry_(PVP)"),
    )
    for acc in cached_data.party:
        if (
            acc.IsSlotActive
            and acc.AgentData.AgentID == agent_id
            and SameMapOrPartyAsAccount(acc)
            and acc.AgentPartyData.PartyID == cached_data.party.party_id
        ):
            shared_skillbar_ids = {int(skill.Id) for skill in acc.AgentData.Skillbar.Skills if int(skill.Id) != 0}
            for skill_id in iw_skill_ids:
                if skill_id and (
                    CheckForEffect(agent_id, skill_id, cached_data=cached_data)
                    or skill_id in shared_skillbar_ids
                ):
                    return True
            return False

    return any(
        skill_id and CheckForEffect(agent_id, skill_id, cached_data=cached_data)
        for skill_id in iw_skill_ids
    )

@frame_cache(category="utils", source_lib="GetEffectAndBuffIds", key=_agent_key)
def GetEffectAndBuffIds(agent_id, cached_data : Optional[CacheData] = None) -> list[int]:
    """
    get all effect and buff skill ids for the given agent
    """
    cached_data = cached_data if cached_data is not None else CacheData()
    
    for acc in cached_data.party:
        if acc.IsSlotActive and acc.AgentData.AgentID == agent_id and SameMapOrPartyAsAccount(acc) and acc.AgentPartyData.PartyID == cached_data.party.party_id:
            return [buff.SkillId for buff in acc.AgentData.Buffs.Buffs]
    
    return [effect.skill_id for effect in GLOBAL_CACHE.Effects.GetBuffs(agent_id) + GLOBAL_CACHE.Effects.GetEffects(agent_id)]

@frame_cache(category="utils", source_lib="IsHeroFlagged")
def IsHeroFlagged(index):    
    if  index != 0 and index <= GLOBAL_CACHE.Party.GetHeroCount():
        return GLOBAL_CACHE.Party.Heroes.IsHeroFlagged(index)
    else:
        acc = GLOBAL_CACHE.ShMem.GetHeroAIOptionsByPartyNumber(index)
        return acc is not None and acc.IsFlagged 


FIGHT_ZONE_FLAG_COLOR = (255, 140, 30, 255)
MANUAL_FLAG_COLOR = (0, 255, 0, 255)


def is_fight_zone_flag(leader_options, own_options) -> bool:
    """Tell an auto-dropped fight pin from a hand-placed party flag.

    On the client running the fight publisher this is a fact, not a guess: the
    zone's own anchor is in the debug snapshot, so a flag standing on it is ours.

    Everywhere else it stays an inference, because HeroAIOptionStruct cannot grow
    a field without a matching change to the C++-owned shared memory region. The
    inference leans on a manual all-flag publishing flagged_follow_threshold (0.0
    by default) while a fight slot publishes its line tolerance, floored at
    Adjacent. That is weaker than it looks and the fact is always preferred:
    _resolve_anchor hands out flagged_follow_threshold to every member the zone
    did NOT give a slot to, so those viewers read their own fight pin as manual
    and drew it green.
    """
    if leader_options is None:
        return False
    if not bool(getattr(leader_options, "IsFlagged", False)):
        return False

    import HeroAI.globals as hero_globals

    snapshot = hero_globals.fight_zone_debug_snapshot
    anchor = snapshot.get("anchor") if snapshot is not None else None
    if anchor is not None:
        all_flag = getattr(leader_options, "AllFlag", None)
        if all_flag is not None:
            on_anchor = abs(float(anchor[0]) - float(getattr(all_flag, "x", 0.0))) <= 1.0 and abs(
                float(anchor[1]) - float(getattr(all_flag, "y", 0.0))
            ) <= 1.0
            if on_anchor:
                return True

    if own_options is None:
        return False
    return float(getattr(own_options, "FollowMoveThresholdCombat", -1.0)) >= float(Range.Adjacent.value)


def DrawFlagAll(pos_x, pos_y, color=None):
    overlay = Overlay()
    pos_z = overlay.FindZ(pos_x, pos_y)
    flag_color = Utils.RGBToColor(*(color or MANUAL_FLAG_COLOR))

    overlay.BeginDraw()
    overlay.DrawLine3D(pos_x, pos_y, pos_z, pos_x, pos_y, pos_z - 150, flag_color, 3)
    overlay.DrawTriangleFilled3D(
        pos_x, pos_y, pos_z - 150,               # Base point
        pos_x, pos_y, pos_z - 120,               # 30 units up
        pos_x - 50, pos_y, pos_z - 135,          # 50 units left, 15 units up
        flag_color
    )
    if color == FIGHT_ZONE_FLAG_COLOR:
        # A ring on the ground so the fight pin reads as a zone centre rather
        # than a waypoint, even with the debug overlay switched off.
        overlay.DrawPoly3D(pos_x, pos_y, pos_z, radius=90.0, color=flag_color, numsegments=16, thickness=2.0)

    overlay.EndDraw()

def DrawHeroFlag(pos_x, pos_y):
    overlay = Overlay()
    
    pos_z = overlay.FindZ(pos_x, pos_y)

    overlay.BeginDraw()
    overlay.DrawLine3D(pos_x, pos_y, pos_z, pos_x, pos_y, pos_z - 150, Utils.RGBToColor(0, 255, 0, 255), 3)
    overlay.DrawTriangleFilled3D(
        pos_x + 25, pos_y, pos_z - 150,          # Right base
        pos_x - 25, pos_y, pos_z - 150,          # Left base
        pos_x, pos_y, pos_z - 100,               # 50 units up
        Utils.RGBToColor(0, 255, 0, 255)
    )
        
    overlay.EndDraw()


def DrawSharedMemoryFlags() -> None:
    if not Map.IsMapReady():
        return

    leader_options = GLOBAL_CACHE.ShMem.GetHeroAIOptionsByPartyNumber(0)
    if (
        leader_options is not None
        and bool(getattr(leader_options, "IsFlagged", False))
        and (
            abs(float(getattr(leader_options.AllFlag, "x", 0.0))) > 0.001
            or abs(float(getattr(leader_options.AllFlag, "y", 0.0))) > 0.001
        )
    ):
        own_options = GLOBAL_CACHE.ShMem.GetHeroAIOptionsFromEmail(Player.GetAccountEmail())
        DrawFlagAll(
            float(leader_options.AllFlag.x),
            float(leader_options.AllFlag.y),
            FIGHT_ZONE_FLAG_COLOR if is_fight_zone_flag(leader_options, own_options) else None,
        )

    for i in range(1, MAX_NUM_PLAYERS):
        account = GLOBAL_CACHE.ShMem.GetAccountDataFromPartyNumber(i)
        options = GLOBAL_CACHE.ShMem.GetHeroAIOptionsByPartyNumber(i)
        if (
            account is None
            or options is None
            or not bool(getattr(account, "IsSlotActive", False))
            or not bool(getattr(options, "IsFlagged", False))
        ):
            continue
        if (
            abs(float(getattr(options.FlagPos, "x", 0.0))) <= 0.001
            and abs(float(getattr(options.FlagPos, "y", 0.0))) <= 0.001
        ):
            continue
        DrawHeroFlag(float(options.FlagPos.x), float(options.FlagPos.y))
