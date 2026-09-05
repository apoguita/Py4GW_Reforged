from itertools import chain
from typing import List, Tuple, Generator, Any, Optional, Dict, Callable
from dataclasses import dataclass
from enum import Enum
import time
import os
from Py4GWCoreLib import (GLOBAL_CACHE, Routines, Range, Py4GW, ConsoleLog, ModelID, Botting,
                          AutoPathing, PyImGui, ActionQueueManager, Map, Agent, Player, Item,
                          IconsFontAwesome5, SkillBar, Quest, AgentArray, UIManager, Color)
from Py4GWCoreLib.py4gwcorelib_src.Utils import Utils
from Py4GWCoreLib.ImGui_src.ImGuisrc import ImGui
from Py4GWCoreLib.enums_src.Hero_enums import HeroType
from Py4GWCoreLib.py4gwcorelib_src.BehaviorTree import BehaviorTree
from Py4GWCoreLib.BottingTree import BottingTree
from Py4GWCoreLib.routines_src.BehaviourTrees import BT as CoreBT
import PyGameThread

from Widgets.Automation.Helpers.Pycons import TEAM_SETTINGS_CACHE_MS
from Py4GWCoreLib.FrameTree import Frame, FrameId
from Sources.ApoSource.ApoBottingLib import wrappers as BT

BOT_NAME = "Elite Skills Capture BT"
MODULE_NAME = BOT_NAME
MODULE_ICON = "Assets\\Textures\\Module_Icons\\elite_skills_capture.png"
MODULE_CATEGORY = "Helpers"
MODULE_TAGS = ["automation", "skills", "elite", "capture", "botting", "bt"]
MODULE_DESCRIPTION = "Behavior Tree-based automation bot for capturing elite skills from bosses throughout Guild Wars.\n\nFeatures:\n• BT-based automation using CoreBT framework\n• Automated pathing to elite skill bosses across all campaigns\n• Intelligent boss detection and engagement system\n• Automatic Signet of Capture usage for skill learning\n• Support for all 10 professions with 151+ elite skills\n• Color-coded skill availability (Blue/Available, Green/Captured, Red/Map Locked)\n• Smart map access checking and unlock requirements\n• Progress tracking and capture status monitoring\n• Built-in safety features and stuck detection\n\nCredits:\n• Originally developed by Kendor with help from Wick Divinus and Simfoniya\n• BT refactoring for Py4GW widget system by Kendor"
ROUTINE_NAME = "EliteSkillsCaptureSequence"

# ============================================================================
# LOCAL ENUMS (from source file for consistency)
# ============================================================================

class LocalEliteSkillType(Enum):
    ELITE_SKILL = "elite_skill"

class LocalProfession(Enum):
    WARRIOR = "Warrior"
    RANGER = "Ranger"
    MONK = "Monk"
    NECROMANCER = "Necromancer"
    MESMER = "Mesmer"
    ELEMENTALIST = "Elementalist"
    ASSASSIN = "Assassin"
    RITUALIST = "Ritualist"
    PARAGON = "Paragon"
    DERVISH = "Dervish"

_saved_build_template: Optional[str] = None
_build_saved_once = False
_starting_map_id: Optional[int] = None

# ============================================================================
# SKILL CHECKING FUNCTIONS
# ============================================================================

def is_skill_unlocked(skill_id: int) -> bool:
    """Check if a skill is already unlocked for the current character."""
    unlocked_skills = Player.GetUnlockedCharacterSkills()
    
    bits_per_entry = 32
    entry_index = skill_id // bits_per_entry
    bit_position = skill_id % bits_per_entry
    
    if entry_index < len(unlocked_skills):
        skill_mask = unlocked_skills[entry_index]
        return (skill_mask >> bit_position) & 1 == 1
    
    return False

def can_learn_skill(skill_id: int) -> bool:
    """Check if a skill is learnable for the current character across all secondary professions."""
    return True

def can_access_skill_map(skill: "EliteSkill") -> bool:
    """Check if the required map for skill capture is unlocked."""
    if skill.start_map <= 0:
        return True  # No map requirement

    try:
        return Map.IsMapUnlocked(skill.start_map)
    except:
        return True  # Assume unlocked if check fails

def should_skip_skill(skill_id: int) -> Tuple[bool, str]:
    """
    Check if a skill should be skipped during capture.
    Returns (should_skip, reason)
    """
    if is_skill_unlocked(skill_id):
        return True, f"Skill {skill_id} ({GLOBAL_CACHE.Skill.GetName(skill_id)}) already unlocked"

    if not can_learn_skill(skill_id):
        return True, f"Skill {skill_id} ({GLOBAL_CACHE.Skill.GetName(skill_id)}) not learnable for this character"

    # Check map access
    skill = next((s for s in ELITE_SKILLS if s.skill_id == skill_id), None)
    if skill and not can_access_skill_map(skill):
        return True, f"Skill {skill_id} ({GLOBAL_CACHE.Skill.GetName(skill_id)}) map not accessible: {Map.GetMapName(skill.start_map)}"

    return False, ""

# ============================================================================
# DATA CLASSES
# ============================================================================

class EliteSkillType(Enum):
    ELITE_SKILL = "elite_skill"
    SIGNET = "signet"

@dataclass
class EliteSkill:
    """Represents a single elite skill"""
    id: str
    display_name: str
    skill_id: int
    profession: LocalProfession
    type: LocalEliteSkillType
    step_name: str
    capture_function: str
    start_map: int = 0
    description: str = ""
    icon_filename: Optional[str] = None

@dataclass
class CaptureRoute:
    """Configuration data for elite skill capture route"""
    skill_id: int
    profession: LocalProfession
    start_map: int
    
    # Entry type: "walk_exit", "mission", "npc_dialog", "gadget_dialog"
    entry_type: str = "walk_exit"
    
    # Walk exit data
    exit_map: Optional[int] = None
    exit_coords: Optional[Tuple[float, float]] = None
    
    # Mission entry data
    mission_map_id: Optional[int] = None
    mission_delay_ms: int = 1000
    
    # Dialog entry data
    dialog_id: Optional[int] = None
    dialog_coords: Optional[Tuple[float, float]] = None
    dialog_target_map: Optional[int] = None
    
    # Route data (after entry)
    route_coords: Optional[List[Tuple[float, float]]] = None
    
    # Wait times (skill-specific)
    wait_after_entry_ms: int = 0
    wait_before_boss_ms: int = 0
    
    # Retry configuration (for bosses with spawn variability)
    max_retries: int = 0
    retry_delay_ms: int = 5000
    
    hero_team_type: str = "AdvancedHeroTeam"
    use_combat_wait: bool = True

# ============================================================================
# CAPTURE ROUTE DATA
# ============================================================================
# NOTE: CAPTURE_ROUTES removed - using individual BUILDERS pattern instead
# Each skill now has its own explicit builder function in BUILDERS dictionary

# ============================================================================
# INDIVIDUAL SKILL BT BUILDERS
# ============================================================================

def _action(name: str, fn: Callable[[], object], aftercast_ms: int = 250) -> BehaviorTree:
    """Helper to create an action node from a simple function."""
    def _run() -> BehaviorTree.NodeState:
        try:
            fn()
            return BehaviorTree.NodeState.SUCCESS
        except Exception as exc:
            ConsoleLog(MODULE_NAME, f'{name} failed: {exc}', log=True)
            return BehaviorTree.NodeState.FAILURE
    return BehaviorTree(BehaviorTree.ActionNode(name=name, action_fn=_run, aftercast_ms=aftercast_ms))

def BuildEnergySurge(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Energy Surge elite skill capture."""
    nodes = [
        BT.LogMessage(message='Starting Energy Surge capture', module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=414),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.MESMER),
        BT.Wait(duration_ms=2000),  # Wait for build to fully load before checking for signet
        BuySignetOfCapture(LocalProfession.MESMER),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.Move(pos=(-833, 4980)),
        BT.MoveAndExitMap(pos=(-833, 4980), target_map_id=419),
        ConfigureAggressiveEnv(),
        BT.Move(pos=(-20867.55, -9056.55)),
        BT.Move(pos=(-19999.87, -4514.18)),
        BT.Move(pos=(-22300.36, -7250.76)),
        BT.Move(pos=(-22435, -6718)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 414),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name='Energy Surge Capture'))

def BuildIneptitude(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Ineptitude elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Ineptitude capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.MESMER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.MESMER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=641),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(19072, -10584), target_map_id=572),
        ConfigureAggressiveEnv(),
        BT.VanquishNode(steps=[(18975.00, -7661.00), (13678.05, -7953.19), (7806.59, -8390.89), (2419.74, -10806.55)]),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 641),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Ineptitude Capture"))

def BuildMigraine(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Migraine elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Migraine capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.MESMER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.MESMER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=638),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.Move(pos=(-9738.66, -21663.27)),
        BT.MoveAndExitMap(pos=(-9605, -19938), target_map_id=558),
        ConfigureAggressiveEnv(),
        BT.VanquishNode(steps=[(-11074.98, -14619.83), (-11022.09, -10608.68), (-10086.13, -6514.95), (-11156, -2359)]),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 638),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Migraine Capture"))

def BuildIllusionaryWeaponry(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Illusionary Weaponry elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Illusionary Weaponry capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.MESMER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.MESMER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=155),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(7565, -45115), target_map_id=26),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-18688, 12186)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 155),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Illusionary Weaponry Capture"))

def BuildPanic(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Panic elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Panic capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.MESMER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.MESMER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=35),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=2000),
        # Hell's Precipice special entrance
        BT.EnterChallenge(target_map_id=124),
        BT.Wait(duration_ms=2000),
        ConfigureAggressiveEnv(),
        BT.VanquishNode(steps=[(2573, 134), (3009, -4916)]),
        BT.Wait(duration_ms=7000),
        BT.VanquishNode(steps=[(5043.89, -7425.06), (9299, -9728), (7827.06, -13540.96)]),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 35),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Panic Capture"))

def BuildEcho(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Echo elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Echo capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.MESMER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.MESMER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=130),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(18021, 1913), target_map_id=128),
        ConfigureAggressiveEnv(),
        BT.VanquishNode(steps=[(9675, -2176), (4240, -2340)]),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 130),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Echo Capture"))

def BuildMantraOfRecall(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Mantra of Recall elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Mantra of Recall capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.MESMER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.MESMER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=155),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(6038, -41402), target_map_id=91),
        ConfigureAggressiveEnv(),
        BT.VanquishNode(steps=[(1526.63, -39178.76), (592.26, -43048.45), (-2607.90, -44448.80), (-5678.81, -43418.43)]),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 155),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Mantra of Recall Capture"))

def BuildEnergyDrain(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Energy Drain elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Energy Drain capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.MESMER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.MESMER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=193),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(6756, -7638), target_map_id=198),
        ConfigureAggressiveEnv(),
        BT.VanquishNode(steps=[(3079, 4784), (3966, -1263)]),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 193),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Energy Drain Capture"))

def BuildKeystoneSignet(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Keystone Signet elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Keystone Signet capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.MESMER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.MESMER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=156),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-11740, 14510), target_map_id=93),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-5079, -998)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 156),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Keystone Signet Capture"))

def BuildMantraOfRecovery(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Mantra of Recovery elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Mantra of Recovery capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.MESMER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.MESMER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=349),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-8796, -21562), target_map_id=210),
        ConfigureAggressiveEnv(),
        BT.VanquishNode(steps=[(3019, -12299), (-377, -10935)]),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 349),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Mantra of Recovery Capture"))

def BuildEnchantersConundrum(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Enchanter's Conundrum elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Enchanter's Conundrum capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.MESMER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.MESMER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=426),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-4431, 5107), target_map_id=380),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(12304, -2881)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 426),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Enchanter's Conundrum Capture"))

def BuildHexEaterVortex(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Hex Eater Vortex elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Hex Eater Vortex capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.MESMER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.MESMER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=480),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.Move(pos=(-3039, 13579)),
        BT.MoveAndExitMap(pos=(-3076, 11494), target_map_id=446),
        ConfigureAggressiveEnv(),
        BT.VanquishNode(steps=[(-6449, 4707), (-7007, 2674), (-9644, -10835)]),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 480),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Hex Eater Vortex Capture"))

def BuildPowerBlock(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Power Block elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Power Block capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.MESMER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.MESMER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=650),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-21630, 12565), target_map_id=649),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-4163, -203)),
        BT.MoveAndKill(pos=(11385, 2228)),
        BT.MoveAndKill(pos=(19190, -12141)),
        BT.MoveAndExitMap(pos=(23054, -13225), target_map_id=651),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-16333, 16622)),
        BT.MoveAndKill(pos=(-9609, 11059)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 650),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Power Block Capture"))

def BuildPowerFlux(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Power Flux elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Power Flux capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.MESMER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.MESMER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=469),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(15365, 20110), target_map_id=470),
        ConfigureAggressiveEnv(),
        BT.VanquishNode(steps=[(-11703, 1000), (-16661, 6337), (-8634, 10748)]),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 469),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Power Flux Capture"))

def BuildPsychicDistraction(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Psychic Distraction elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Psychic Distraction capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.MESMER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.MESMER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=284),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.Move(pos=(11750, -18667)),
        BT.MoveAndExitMap(pos=(11745, -21128), target_map_id=256),
        ConfigureAggressiveEnv(),
        BT.VanquishNode(steps=[(4219, 7155), (267, 6433), (123, 2310)]),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 284),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Psychic Distraction Capture"))

def BuildArcaneLanguor(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Arcane Languor elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Arcane Languor capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.MESMER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.MESMER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=226),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-9692, 3974), target_map_id=233),
        ConfigureAggressiveEnv(),
        BT.VanquishNode(steps=[(24348, 1495), (17308, 5582), (9049, 3750), (10315, -1258)]),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 226),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Arcane Languor Capture"))

def BuildStolenSpeed(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Stolen Speed elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Stolen Speed capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.MESMER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.MESMER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=283),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-18666, 16718), target_map_id=197),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(2563, -14091)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 283),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Stolen Speed Capture"))

def BuildSymbolsOfInspiration(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Symbols of Inspiration elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Symbols of Inspiration capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.MESMER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.MESMER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=473),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(11560, -1337), target_map_id=472),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(14496, 1656)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 473),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Symbols of Inspiration Capture"))

def BuildAirOfDisenchantment(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Air of Disenchantment elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Air of Disenchantment capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.MESMER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.MESMER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=428),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-2220, 14596), target_map_id=399),
        ConfigureAggressiveEnv(),
        BT.MoveAndDialog(pos=(-4552.00, 15863.00), dialog_id=0x84),
        BT.Wait(duration_ms=2000), # Wait for map load
        BT.VanquishNode(steps=[(21037, -6504), (21933, -1662), (21988, 4865), (18622, 13967)]),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 428),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Air of Disenchantment Capture"))

def BuildRecurringInsecurity(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Recurring Insecurity elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Recurring Insecurity capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.MESMER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.MESMER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=287),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(27082, 5310), target_map_id=209),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(20840, 2153)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 287),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Recurring Insecurity Capture"))

def BuildSharedBurden(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Shared Burden elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Shared Burden capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.MESMER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.MESMER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=287),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(27082, 5310), target_map_id=209),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(22343, -6025)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 287),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Shared Burden Capture"))

def BuildSignetOfIllusions(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Signet of Illusions elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Signet of Illusions capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.MESMER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.MESMER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=494),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-17156, 5363), target_map_id=465),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(10335, 14284)),
        BT.MoveAndKill(pos=(19876, 2352)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 494),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Signet of Illusions Capture"))

def BuildExtendConditions(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Extend Conditions elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Extend Conditions capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.MESMER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.MESMER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=381),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-6340, 5354), target_map_id=371),
        ConfigureAggressiveEnv(),
        BT.VanquishNode(steps=[(17746, -12948), (10002, -10969), (6450, -13753), (5055, -12183)]),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 381),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Extend Conditions Capture"))

def BuildLyssasAura(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Lyssa's Aura elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Lyssa's Aura capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.MESMER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.MESMER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=643),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(13563, 19055), target_map_id=513),
        ConfigureAggressiveEnv(),
        BT.VanquishNode([(13774, 1991), (11330, -4626), (11757, -9994), (12602, -18525), (14034, -22760)]),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 643),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Lyssa's Aura Capture"))

def BuildExpelHexes(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Expel Hexes elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Expel Hexes capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.MESMER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.MESMER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=292),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-14677, 5182), target_map_id=240),
        ConfigureAggressiveEnv(),
        BT.VanquishNode([(5352, -2622), (4441, 1667)]),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 292),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Expel Hexes Capture"))

def BuildPiousRenewal(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Pious Renewal elite skill capture."""
    nodes = [
        BT.LogMessage(message='Starting Pious Renewal capture', module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=493),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.DERVISH),
        BT.Wait(duration_ms=2000),  # Wait for build to fully load before checking for signet
        BuySignetOfCapture(LocalProfession.DERVISH),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        ConfigureAggressiveEnv(),
        BT.MoveAndDialog(pos=(-1508.00, 16739.00), dialog_id=0x81),
        BT.MoveAndDialog(pos=(-1508.00, 16739.00), dialog_id=0x84),
        BT.Wait(duration_ms=10000),
        BT.MoveAndKill(pos=(-15271.60, -11910.33)),
        BT.MoveAndKill(pos=(-14876.34, -11912.82)),
        BT.MoveAndKill(pos=(-14816, -11739)),
        BT.MoveAndKill(pos=(-14924, -9280)),
        BT.MoveAndKill(pos=(-14605, -8548)),
        BT.MoveAndKill(pos=(-14501, -7181)),
        BT.MoveAndKill(pos=(-14219, -5434)),
        BT.MoveAndKill(pos=(-12416, -5421)),
        BT.MoveAndKill(pos=(-12077, -5155)),
        BT.MoveAndKill(pos=(-8853, -4123)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 493),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name='Pious Renewal Capture'))

def BuildBloodIsPower(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Blood is Power elite skill capture."""
    nodes = [
        BT.LogMessage(message='Starting Blood is Power capture', module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.NECROMANCER),
        BT.Wait(duration_ms=2000),  # Wait for build to fully load before checking for signet
        BuySignetOfCapture(LocalProfession.NECROMANCER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=393),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndKill(pos=(-6066, -1583)),
        BT.MoveAndKill(pos=(-1695, -374)),
        BT.MoveAndKill(pos=(1297, 2931)),
        BT.MoveAndKill(pos=(5981, 4148)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 393),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name='Blood is Power Capture'))

def BuildCauterySignet(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Cautery Signet elite skill capture."""
    nodes = [
        BT.LogMessage(message='Starting Cautery Signet capture', module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.PARAGON),
        BT.Wait(duration_ms=2000),  # Wait for build to fully load before checking for signet
        BuySignetOfCapture(LocalProfession.PARAGON),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=424),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(3274, -4412), target_map_id=379),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-6308, 13198)),
        BT.MoveAndKill(pos=(-7341, 5275)),
        BT.MoveAndKill(pos=(-7027, -428)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 424),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name='Cautery Signet Capture'))

def BuildTogetherAsOne(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Together as One elite skill capture."""
    nodes = [
        BT.LogMessage(message='Starting Together as One capture', module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.RANGER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.RANGER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=650),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.RestockItems(model_id=38031, desired_quantity=1, allow_missing=False),
        BT.MoveAndExitMap(pos=(-21630, 12565), target_map_id=649),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-3924.91, -572.00)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        BT.MoveAndKill(pos=(11385, 2228)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        BT.MoveAndKill(pos=(19190, -12141)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        BT.MoveAndExitMap(pos=(23054, -13225), target_map_id=651),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-16333, 16622)),
        BT.MoveAndKill(pos=(-16605, 12608)),
        BT.MoveAndKill(pos=(-17653, 8825)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        BT.MoveAndKill(pos=(-17085, 5034)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        BT.MoveAndKill(pos=(-13308, 4215)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        BT.MoveAndKill(pos=(-13020, 270)),
        BT.MoveAndKill(pos=(-9647, -12780)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.DepositModelToStorage(model_id=38031, aftercast_ms=150),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 650),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name='Together as One Capture'))

def BuildHeroicRefrain(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Heroic Refrain elite skill capture."""
    nodes = [
        BT.LogMessage(message='Starting Heroic Refrain capture', module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.PARAGON),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.PARAGON),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=440),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.RestockItems(model_id=38031, desired_quantity=1, allow_missing=False),
        BT.MoveAndExitMap(pos=(-5108, -6684), target_map_id=439),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-7311.32, -4854.25)),
        BT.MoveAndKill(pos=(-14444, 3610)),
        BT.MoveAndKill(pos=(-13457.71, 9154.56)),
        BT.MoveAndKill(pos=(-14566, 9921)),
        BT.MoveAndKill(pos=(-15264.96, 10763.86)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.DepositModelToStorage(model_id=38031, aftercast_ms=150),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 440),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name='Heroic Refrain Capture'))

def BuildSoulTaker(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Soul Taker elite skill capture."""
    nodes = [
        BT.LogMessage(message='Starting Soul Taker capture', module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.NECROMANCER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.NECROMANCER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=35),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.RestockItems(model_id=38031, desired_quantity=1, allow_missing=False),
        BT.MoveAndExitMap(pos=(3807, -8332), target_map_id=121),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(8100, -4094)),
        BT.MoveAndKill(pos=(15507, -2022)),
        BT.MoveAndKill(pos=(20600, 2121)),
        BT.MoveAndKill(pos=(23425, 7266)),
        BT.MoveAndKill(pos=(23994, 13745)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.DepositModelToStorage(model_id=38031, aftercast_ms=150),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 35),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name='Soul Taker Capture'))

def BuildOverTheLimit(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Over The Limit elite skill capture."""
    nodes = [
        BT.LogMessage(message='Starting Over The Limit capture', module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.ELEMENTALIST),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.ELEMENTALIST),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=35),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.RestockItems(model_id=38031, desired_quantity=1, allow_missing=False),
        BT.MoveAndExitMap(pos=(3807, -8332), target_map_id=121),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(8100, -4094)),
        BT.MoveAndKill(pos=(15507, -2022)),
        BT.MoveAndKill(pos=(20600, 2121)),
        BT.MoveAndKill(pos=(23425, 7266)),
        BT.MoveAndKill(pos=(23994, 13745)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.DepositModelToStorage(model_id=38031, aftercast_ms=150),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 35),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name='Over The Limit Capture'))

def BuildJudgmentStrike(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Judgment Strike elite skill capture."""
    nodes = [
        BT.LogMessage(message='Starting Judgment Strike capture', module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.MONK),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.MONK),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=440),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.RestockItems(model_id=38031, desired_quantity=1, allow_missing=False),
        BT.MoveAndExitMap(pos=(-5108, -6684), target_map_id=439),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-7311.32, -4854.25)),
        BT.MoveAndKill(pos=(-14444, 3610)),
        BT.MoveAndKill(pos=(-13457.71, 9154.56)),
        BT.MoveAndKill(pos=(-14566, 9921)),
        BT.MoveAndKill(pos=(-15264.96, 10763.86)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.DepositModelToStorage(model_id=38031, aftercast_ms=150),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 440),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name='Judgment Strike Capture'))

def BuildTimeWard(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Time Ward elite skill capture."""
    nodes = [
        BT.LogMessage(message='Starting Time Ward capture', module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.MESMER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.MESMER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=650),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.RestockItems(model_id=38031, desired_quantity=1, allow_missing=False),
        BT.MoveAndExitMap(pos=(-21630, 12565), target_map_id=649),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-4163, -203)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        BT.MoveAndKill(pos=(11385, 2228)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        BT.MoveAndKill(pos=(19190, -12141)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        BT.MoveAndExitMap(pos=(23054, -13225), target_map_id=651),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-16333, 16622)),
        BT.MoveAndKill(pos=(-16605, 12608)),
        BT.MoveAndKill(pos=(-17653, 8825)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        BT.MoveAndKill(pos=(-17085, 5034)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        BT.MoveAndKill(pos=(-13308, 4215)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        BT.MoveAndKill(pos=(-13020, 270)),
        BT.MoveAndKill(pos=(-9647, -12780)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.DepositModelToStorage(model_id=38031, aftercast_ms=150),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 650),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name='Time Ward Capture'))

def BuildVowOfRevolution(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Vow of Revolution elite skill capture."""
    nodes = [
        BT.LogMessage(message='Starting Vow of Revolution capture', module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.DERVISH),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.DERVISH),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=440),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.RestockItems(model_id=38031, desired_quantity=1, allow_missing=False),
        BT.MoveAndExitMap(pos=(-5108, -6684), target_map_id=439),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-7311.32, -4854.25)),
        BT.MoveAndKill(pos=(-14444, 3610)),
        BT.MoveAndKill(pos=(-13457.71, 9154.56)),
        BT.MoveAndKill(pos=(-14566, 9921)),
        BT.MoveAndKill(pos=(-15264.96, 10763.86)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.DepositModelToStorage(model_id=38031, aftercast_ms=150),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 440),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name='Vow of Revolution Capture'))

def BuildSevenWeaponStance(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Seven Weapon Stance elite skill capture."""
    nodes = [
        BT.LogMessage(message='Starting Seven Weapon Stance capture', module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.WARRIOR),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.WARRIOR),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=226),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.RestockItems(model_id=38031, desired_quantity=1, allow_missing=False),
        BT.MoveAndExitMap(pos=(-9662, 3084), target_map_id=233),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(16446, 261)),
        BT.MoveAndKill(pos=(15194, 299)),
        BT.MoveAndKill(pos=(14830, -2177)),
        BT.MoveAndKill(pos=(14690, -4412)),
        BT.MoveAndKill(pos=(12365, -5527)),
        BT.MoveAndKill(pos=(10957, -4475)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.DepositModelToStorage(model_id=38031, aftercast_ms=150),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 226),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name='Seven Weapon Stance Capture'))

def BuildWeaponsOfThreeForges(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Weapons of Three Forges elite skill capture."""
    nodes = [
        BT.LogMessage(message='Starting Weapons of Three Forges capture', module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.RITUALIST),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.RITUALIST),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=226),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.RestockItems(model_id=38031, desired_quantity=1, allow_missing=False),
        BT.MoveAndExitMap(pos=(-9662, 3084), target_map_id=233),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(16446, 261)),
        BT.MoveAndKill(pos=(15194, 299)),
        BT.MoveAndKill(pos=(14830, -2177)),
        BT.MoveAndKill(pos=(14690, -4412)),
        BT.MoveAndKill(pos=(12365, -5527)),
        BT.MoveAndKill(pos=(10957, -4475)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.DepositModelToStorage(model_id=38031, aftercast_ms=150),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 226),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name='Weapons of Three Forges Capture'))

def BuildShadowTheft(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Shadow Theft elite skill capture."""
    nodes = [
        BT.LogMessage(message='Starting Shadow Theft capture', module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.ASSASSIN),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.ASSASSIN),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=226),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.RestockItems(model_id=38031, desired_quantity=1, allow_missing=False),
        BT.MoveAndExitMap(pos=(-9662, 3084), target_map_id=233),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(16446, 261)),
        BT.MoveAndKill(pos=(15194, 299)),
        BT.MoveAndKill(pos=(14830, -2177)),
        BT.MoveAndKill(pos=(14690, -4412)),
        BT.MoveAndKill(pos=(12365, -5527)),
        BT.MoveAndKill(pos=(10957, -4475)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.DepositModelToStorage(model_id=38031, aftercast_ms=150),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 226),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name='Shadow Theft Capture'))

def BuildShatteringAssault(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Shattering Assault elite skill capture."""
    nodes = [
        BT.LogMessage(message='Starting Shattering Assault capture', module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.ASSASSIN),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.ASSASSIN),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=480),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.Move(pos=(-3006.40, 13672.54)),
        BT.MoveAndExitMap(pos=(-3042, 11398), target_map_id=446),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-2385.10, 5693.95)),
        BT.MoveAndKill(pos=(-5785.96, 4816.62)),
        BT.MoveAndKill(pos=(-9790.39, -6153.40)),
        BT.MoveAndKill(pos=(-14231.77, -5938.61)),
        BT.MoveAndKill(pos=(-18997.60, -1960.05)),
        BT.MoveAndExitMap(pos=(-19988, -3069), target_map_id=448),
        BT.MoveAndKill(pos=(8516.31, -21069.59)),
        BT.MoveAndKill(pos=(5215.24, -21435.55)),
        BT.MoveAndKill(pos=(-7342.22, -18174.64)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 480),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name='Shattering Assault Capture'))

def BuildAnthemOfGuidance(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Anthem of Guidance elite skill capture."""
    nodes = [
        BT.LogMessage(message='Starting Anthem of Guidance capture', module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.PARAGON),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.PARAGON),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=403),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-19999, 20176), target_map_id=419),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(21678, -15544)),
        BT.MoveAndKill(pos=(10490, -14547)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 403),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name='Anthem of Guidance Capture'))

def BuildCripplingAnthem(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Crippling Anthem elite skill capture."""
    nodes = [
        BT.LogMessage(message='Starting Crippling Anthem capture', module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.PARAGON),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.PARAGON),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=376),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-13955, 18251), target_map_id=375),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-11625, 16880)),
        BT.MoveAndKill(pos=(-6742, 14805)),
        BT.MoveAndKill(pos=(-4287, 13281)),
        BT.MoveAndKill(pos=(99, 11211)),
        BT.MoveAndKill(pos=(1009, 9585)),
        BT.MoveAndKill(pos=(182, 7959)),
        BT.MoveAndKill(pos=(2359, 4706)),
        BT.MoveAndKill(pos=(2855, 819)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 376),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name='Crippling Anthem Capture'))

def BuildAngelicBond(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Angelic Bond elite skill capture."""
    nodes = [
        BT.LogMessage(message='Starting Angelic Bond capture', module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.PARAGON),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.PARAGON),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=434),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndDialog(pos=(1341.00, -20346.00), dialog_id=0x81),
        BT.MoveAndDialog(pos=(1341.00, -20346.00), dialog_id=0x84),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(1205, -14695)),
        BT.MoveAndKill(pos=(2156, -9851)),
        BT.MoveAndKill(pos=(3357, -8887)),
        BT.MoveAndKill(pos=(1530, -5931)),
        BT.MoveAndKill(pos=(1530, -4479)),
        BT.MoveAndKill(pos=(2296, -3650)),
        BT.MoveAndKill(pos=(2253, -2209)),
        BT.MoveAndKill(pos=(1371, -1043)),
        BT.MoveAndKill(pos=(1377, 289)),
        BT.MoveAndKill(pos=(2538, 1246)),
        BT.MoveAndKill(pos=(1344, 2875)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 434),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name='Angelic Bond Capture'))

def BuildDefensiveAnthem(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Defensive Anthem elite skill capture."""
    nodes = [
        BT.LogMessage(message='Starting Defensive Anthem capture', module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.PARAGON),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.PARAGON),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=387),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-420, 3921), target_map_id=436),
        BT.MoveAndExitMap(pos=(5233, 7646), target_map_id=369),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-4337, 4183)),
        BT.MoveAndKill(pos=(-7636, 516)),
        BT.MoveAndKill(pos=(-8233, -1156)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 387),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name='Defensive Anthem Capture'))

def BuildItsJustaFleshWound(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for It's Just a Flesh Wound elite skill capture."""
    nodes = [
        BT.LogMessage(message='Starting It\'s Just a Flesh Wound capture', module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.PARAGON),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.PARAGON),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=480),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-3265, 11584), target_map_id=446),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-2498, 5680)),
        BT.MoveAndKill(pos=(-4497, 5079)),
        BT.MoveAndKill(pos=(-8191, 3361)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 480),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name='It\'s Just a Flesh Wound Capture'))

def BuildThePowerIsYours(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for The Power Is Yours elite skill capture."""
    nodes = [
        BT.LogMessage(message='Starting The Power Is Yours capture', module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.PARAGON),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.PARAGON),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=440),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(1814, -1774), target_map_id=439),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-23, 7080)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 440),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name='The Power Is Yours Capture'))

def BuildSongofPurification(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Song of Purification elite skill capture."""
    nodes = [
        BT.LogMessage(message='Starting Song of Purification capture', module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.PARAGON),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.PARAGON),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=403),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-18733, 13488), target_map_id=402),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-16092, 7570)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 403),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name='Song of Purification Capture'))

def BuildSongofRestoration(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Song of Restoration elite skill capture."""
    nodes = [
        BT.LogMessage(message='Starting Song of Restoration capture', module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.PARAGON),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.PARAGON),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=428),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-2081, 14485), target_map_id=399),
        BT.MoveAndDialog(pos=(-4552.00, 15863.00), dialog_id=0x81),
        BT.MoveAndDialog(pos=(-4552.00, 15863.00), dialog_id=0x84),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-10332, -11807)),
        BT.MoveAndKill(pos=(-16846, -5635)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 428),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name='Song of Restoration Capture'))

def BuildCruelSpear(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Cruel Spear elite skill capture."""
    nodes = [
        BT.LogMessage(message='Starting Cruel Spear capture', module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.PARAGON),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.PARAGON),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=427),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndDialog(pos=(-13955.00, -12776.00), dialog_id=0x81),
        BT.MoveAndDialog(pos=(-13955.00, -12776.00), dialog_id=0x84),
        BT.Wait(duration_ms=10000),
        BT.Wait(duration_ms=10000),  # Wait for map load
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-9584, -7325)),
        BT.Wait(duration_ms=30000),
        BT.MoveAndDialog(pos=(-9803.00, -7381.00), dialog_id=0x85),
        BT.MoveAndKill(pos=(-4765, -77)),
        BT.MoveAndKill(pos=(-3095, -1338)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 427),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name='Cruel Spear Capture'))

def BuildStunningStrike(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Stunning Strike elite skill capture."""
    nodes = [
        BT.LogMessage(message='Starting Stunning Strike capture', module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.PARAGON),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.PARAGON),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=469),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(8150, 18933), target_map_id=468),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(4636, 14852)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 469),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name='Stunning Strike Capture'))

def BuildSoldiersFury(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Soldier's Fury elite skill capture."""
    nodes = [
        BT.LogMessage(message='Starting Soldier\'s Fury capture', module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.PARAGON),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.PARAGON),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=438),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-14638, 2927), target_map_id=437),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-10841.79, 4156.87)),
        BT.Wait(duration_ms=8000),
        BT.Move(pos=(-10867.00, 4322.00)),
        BT.InteractTarget(),
        BT.Wait(duration_ms=2000),
        BT.MoveAndKill(pos=(-2487, 8247)),
        BT.MoveAndKill(pos=(-1621, 12022)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 438),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name='Soldier\'s Fury Capture'))

def BuildIncoming(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Incoming! elite skill capture."""
    nodes = [
        BT.LogMessage(message='Starting Incoming! capture', module_name=MODULE_NAME, print_to_console=True),
        BT.LogMessage(message='NOTE: Quest "Desperate Measures" must be completed for boss to appear: https://wiki.guildwars.com/wiki/Desperate_Measures', module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.PARAGON),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.PARAGON),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=414),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-5134, -5006), target_map_id=399),
        ConfigureAggressiveEnv(),
        BT.MoveAndDialog(pos=(6243.00, 10755.00), dialog_id=0x81EB01),
        BT.MoveAndKill(pos=(-8550, 10603)),
        BT.MoveAndKill(pos=(-10444, 5282)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 414),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name='Incoming! Capture'))

def BuildFocusedAnger(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Focused Anger elite skill capture."""
    nodes = [
        BT.LogMessage(message='Starting Focused Anger capture', module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.PARAGON),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.PARAGON),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=427),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndKill(pos=(-13625.08, -11257.90)),
        BT.MoveAndDialog(pos=(-13641.00, -10375.00), dialog_id=0x84),
        BT.Wait(duration_ms=5000),  # Wait for map change to 377
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-7615, -5029)),
        BT.MoveAndKill(pos=(-8597, -2378)),
        BT.MoveAndKill(pos=(-7171, 1228)),
        BT.MoveAndKill(pos=(-13321, 2245)),
        BT.MoveAndKill(pos=(-16798, 1529)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 427),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name='Focused Anger Capture'))

def BuildAnthemofFury(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Anthem of Fury elite skill capture."""
    nodes = [
        BT.LogMessage(message='Starting Anthem of Fury capture', module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.PARAGON),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.PARAGON),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=450),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-7826, 13976), target_map_id=465),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-2677, -10998)),
        BT.MoveAndKill(pos=(-1780, -7409)),
        BT.MoveAndKill(pos=(1456, -7825)),
        BT.MoveAndKill(pos=(5413, -13296)),
        BT.MoveAndKill(pos=(4591, -14059)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 450),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name='Anthem of Fury Capture'))

def BuildShadowForm(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Shadow Form elite skill capture."""
    nodes = [
        BT.LogMessage(message='Starting Shadow Form capture', module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.ASSASSIN),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.ASSASSIN),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=284),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.Move(pos=(11664.37, -18732.13)),
        BT.MoveAndExitMap(pos=(11637, -20480), target_map_id=256),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(12054, 10092)),
        BT.MoveAndKill(pos=(11784, 6581)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 284),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name='Shadow Form Capture'))

def BuildShadowPrison(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Shadow Prison elite skill capture."""
    nodes = [
        BT.LogMessage(message='Starting Shadow Prison capture', module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.ASSASSIN),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.ASSASSIN),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=398),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-4284, -615), target_map_id=437),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(18745.25, 10039.62)),
        BT.MoveAndKill(pos=(16146.25, 5758.00)),
        BT.MoveAndKill(pos=(15450, 1269)),
        BT.MoveAndKill(pos=(12274, -1577)),
        BT.MoveAndKill(pos=(11634.43, 3894.38)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 398),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name='Shadow Prison Capture'))

def BuildShadowShroud(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Shadow Shroud elite skill capture."""
    nodes = [
        BT.LogMessage(message='Starting Shadow Shroud capture', module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.ASSASSIN),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.ASSASSIN),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=277),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(3200, 2499), target_map_id=227),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(4599.85, 3940.26)),
        BT.MoveAndKill(pos=(3039.05, 5503.06)),
        BT.MoveAndKill(pos=(3187.73, -956.72)),
        BT.MoveAndKill(pos=(7629.23, 3.76)),
        BT.MoveAndKill(pos=(7716.02, 5614.70)),
        BT.MoveAndKill(pos=(4753.20, 7895.67)),
        BT.MoveAndKill(pos=(2412.87, 8214.28)),
        BT.MoveAndKill(pos=(-3362.41, 5083.70)),
        BT.MoveAndKill(pos=(-3286.67, 1236.43)),
        BT.MoveAndKill(pos=(-3234.05, -827.53)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 277),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name='Shadow Shroud Capture'))

def BuildWayOfTheAssassin(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Way of the Assassin elite skill capture."""
    nodes = [
        BT.LogMessage(message='Starting Way of the Assassin capture', module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.ASSASSIN),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.ASSASSIN),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=424),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.Move(pos=(441, 861)),
        BT.MoveAndExitMap(pos=(3676, -4703), target_map_id=379),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(11129, 7553)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 424),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name='Way of the Assassin Capture'))

def BuildDarkApostasy(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Dark Apostasy elite skill capture."""
    nodes = [
        BT.LogMessage(message='Starting Dark Apostasy capture', module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.ASSASSIN),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.ASSASSIN),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=230),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-4459, 5455), target_map_id=209),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-20168, -3708)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 230),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name='Dark Apostasy Capture'))

def BuildAssassinsPromise(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Assassins Promise elite skill capture."""
    nodes = [
        BT.LogMessage(message='Starting Assassins Promise capture', module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.ASSASSIN),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.ASSASSIN),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=640),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.Move(pos=(18003.32, 16753.06), pause_on_combat=True),
        BT.MoveAndExitMap(pos=(20243, 16910), target_map_id=501),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-21519, -7404)),
        BT.MoveAndKill(pos=(-19032.91, -10978.03)),
        BT.MoveAndKill(pos=(-20351.51, -11994.78)),
        BT.MoveAndKill(pos=(-21815.37, -12821.15)),
        BT.MoveAndKill(pos=(-22919.58, -12014.80)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 640),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name='Assassins Promise Capture'))

def BuildLocustsFury(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Locust's Fury elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Locusts Fury capture",module_name=MODULE_NAME,print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.ASSASSIN),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.ASSASSIN),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=129),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-7585, 1955), target_map_id=201),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-3771, 10839)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 129),
        RestoreSavedBuild(),
    ]

    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Locusts Fury Capture"))

def BuildPalmStrike(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Palm Strike elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Palm Strike capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.ASSASSIN),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.ASSASSIN),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=303),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(16512, 20762), target_map_id=240),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-5661.56, -8976.21)),
        BT.MoveAndKill(pos=(-2649.35, -11041.71)),
        BT.MoveAndKill(pos=(1566.75, -11356.73)),
        BT.MoveAndKill(pos=(3910.05, -11147.77)),
        BT.MoveAndKill(pos=(7522.26, -7489.61)),
        BT.MoveAndKill(pos=(11203.97, -4819.40)),
        BT.MoveAndKill(pos=(6323.50, -5214.16)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 303),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name='Palm Strike Capture'))

def BuildSeepingWound(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Seeping Wound elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Seeping Wound capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.ASSASSIN),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.ASSASSIN),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=51),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(5490, -12398), target_map_id=31),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-10625, -2757)),
        BT.MoveAndKill(pos=(-11491.36, -3626.96)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 51),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Seeping Wound Capture"))

def BuildFlashingBlades(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Flashing Blades elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Flashing Blades capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.ASSASSIN),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.ASSASSIN),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=220),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-14594, -3987), target_map_id=197),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(8270, -635)),
        BT.MoveAndKill(pos=(9518.52, 2496.50)),
        BT.MoveAndKill(pos=(9658.32, 895.20)),
        BT.MoveAndKill(pos=(9293.15, -141.34)),
        BT.MoveAndKill(pos=(9427.46, 795.07)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 220),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Flashing Blades Capture"))

def BuildFoxsPromise(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Fox's Promise elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Fox's Promise capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.ASSASSIN),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.ASSASSIN),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=396),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-1367, 5938), target_map_id=395),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(6784.16, -14382.22)),
        BT.MoveAndKill(pos=(-2183.42, -5759.83)),
        BT.MoveAndKill(pos=(-7934.60, -2841.50)),
        BT.MoveAndKill(pos=(-9840.09, -2618.33)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 396),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Fox's Promise Capture"))

def BuildAuraOfDisplacement(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Aura of Displacement elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Aura of Displacement capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.ASSASSIN),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.ASSASSIN),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=77),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.Move(pos=(8196.40, -1113.54)),
        BT.MoveAndExitMap(pos=(10660, -1027), target_map_id=210),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-9358.26, 12733.01)),
        BT.MoveAndKill(pos=(-1456.50, 19115.00)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 77),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Aura of Displacement Capture"))

def BuildMarkOfInsecurity(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Mark of Insecurity elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Mark of Insecurity capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.ASSASSIN),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.ASSASSIN),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=559),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-16693, 19103), target_map_id=465),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-5746, 3318)),
        BT.MoveAndKill(pos=(-7538, 825)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 559),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Mark of Insecurity Capture"))

def BuildHiddenCaltrops(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Hidden Caltrops elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Hidden Caltrops capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.ASSASSIN),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.ASSASSIN),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=424),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(5018, 5107), target_map_id=384),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-13221, -11714)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 424),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Hidden Caltrops Capture"))

def BuildAssaultEnchantments(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Assault Enchantments elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Assault Enchantments capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.ASSASSIN),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.ASSASSIN),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=450),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-7820, 14363), target_map_id=465),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-2950, -7871)),
        BT.MoveAndKill(pos=(4153, -9215)),
        BT.MoveAndKill(pos=(17913, -5760)),
        BT.MoveAndKill(pos=(20215.48, -6927.39)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 450),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Assault Enchantments Capture"))

def BuildShadowMeld(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Shadow Meld elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Shadow Meld capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.ASSASSIN),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.ASSASSIN),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=477),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-15570, -3834), target_map_id=371),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-13815, 3355)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 477),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Shadow Meld Capture"))

def BuildWastrelsCollapse(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Wastrel's Collapse elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Wastrel's Collapse capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.ASSASSIN),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.ASSASSIN),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=407),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-5262, 635), target_map_id=406),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-6604, -11438)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 407),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Wastrel's Collapse Capture"))

def BuildGoldenSkullStrike(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Golden Skull Strike elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Golden Skull Strike capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.ASSASSIN),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.ASSASSIN),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=496),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.Move(pos=(18267, -6197)),
        BT.MoveAndExitMap(pos=(19693, -7411), target_map_id=466),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-8329, -10361)),
        BT.MoveAndKill(pos=(-6013, -5332)),
        BT.MoveAndKill(pos=(-2935, -6277)),
        BT.MoveAndKill(pos=(142, -9721)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 496),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Golden Skull Strike Capture"))

def BuildTempleStrike(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Temple Strike elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Temple Strike capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.ASSASSIN),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.ASSASSIN),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=289),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-14020, -19884), target_map_id=203),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(9787, 5444)),
        BT.MoveAndKill(pos=(7366.23, 4905.62)),
        BT.MoveAndKill(pos=(6585.46, 4768.86)),
        BT.MoveAndKill(pos=(3505.03, 4318.40)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 289),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Temple Strike Capture"))

def BuildMoebiusStrike(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Moebius Strike elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Moebius Strike capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.ASSASSIN),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.ASSASSIN),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=130),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(18474, 1840), target_map_id=128),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(9, 10587)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 130),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Moebius Strike Capture"))

def BuildShroudOfSilence(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Shroud of Silence elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Shroud of Silence capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.ASSASSIN),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.ASSASSIN),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=226),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-9625, 3076), target_map_id=233),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(24307.18, 1386.19)),
        BT.MoveAndKill(pos=(10995.01, 4251.18)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 226),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Shroud of Silence Capture"))

def BuildSiphonStrength(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Siphon Strength elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Siphon Strength capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.ASSASSIN),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.ASSASSIN),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=288),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-16320, 13637), target_map_id=199),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-19877.70, 3994.01)),
        BT.MoveAndKill(pos=(-19831, 2587)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 288),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Siphon Strength Capture"))

def BuildWayOfTheEmptyPalm(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Way of the Empty Palm elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Way of the Empty Palm capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.ASSASSIN),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.ASSASSIN),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=273),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(3473, 7390), target_map_id=247),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(15726, -6563)),
        BT.MoveAndKill(pos=(17996, 2023)),
        BT.MoveAndKill(pos=(24723, 8890)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 273),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Way of the Empty Palm Capture"))

def BuildBeguilingHaze(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Beguiling Haze elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Beguiling Haze capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.ASSASSIN),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.ASSASSIN),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=287),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(32538, 10966), target_map_id=205),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(10599, -7793)),
        BT.MoveAndKill(pos=(11896, -819)),
        BT.MoveAndKill(pos=(14938, -266)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 287),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Beguiling Haze Capture"))

def BuildVowOfSilence(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Vow of Silence elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Vow of Silence capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.DERVISH),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.DERVISH),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=478),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-4817, 5097), target_map_id=444),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(22749, -5468)),
        BT.MoveAndKill(pos=(17736, -5503)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 478),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Vow of Silence Capture"))

def BuildOnslaught(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Onslaught elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Onslaught capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.DERVISH),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.DERVISH),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=643),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(13591, 19148), target_map_id=513),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(13883, 2057)),
        BT.MoveAndKill(pos=(8414, -1814)),
        BT.MoveAndKill(pos=(6336, -2122)),
        BT.MoveAndKill(pos=(4268, -4559)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        BT.MoveAndKill(pos=(2214, -6510)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 643),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Onslaught Capture"))

def BuildEbonDustAura(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Ebon Dust Aura elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Ebon Dust Aura capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.DERVISH),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.DERVISH),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=414),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-820, 5147), target_map_id=419),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(1457, -14317)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 414),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Ebon Dust Aura Capture"))

def BuildAvatarOfBalthazar(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Avatar of Balthazar elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Avatar of Balthazar capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.DERVISH),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.DERVISH),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=387),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-225, 4336), target_map_id=436),
        BT.MoveAndExitMap(pos=(5342, 7723), target_map_id=369),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-6895, 9930)),
        BT.MoveAndKill(pos=(-3407, 6775)),
        BT.MoveAndKill(pos=(-5368, 1542)),
        BT.MoveAndKill(pos=(-4033, -1548)),
        BT.MoveAndKill(pos=(-5894.94, -3791.20)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 387),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Avatar of Balthazar Capture"))

def BuildAvatarOfMelandru(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Avatar of Melandru elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Avatar of Melandru capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.DERVISH),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.DERVISH),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=477),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-15535, -3754), target_map_id=371),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-10797, -1490)),
        BT.MoveAndKill(pos=(-7581, -255)),
        BT.MoveAndKill(pos=(-4450, 1156)),
        BT.MoveAndKill(pos=(-2573, 1103)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 477),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Avatar of Melandru Capture"))

def BuildAvatarOfDwayna(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Avatar of Dwayna elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Avatar of Dwayna capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.DERVISH),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.DERVISH),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=424),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(3805, -4766), target_map_id=379),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-4402, 17178)),
        BT.MoveAndKill(pos=(-4890, 7205)),
        BT.MoveAndKill(pos=(-4795, -656)),
        BT.MoveAndKill(pos=(-6963, -254)),
        BT.MoveAndKill(pos=(-6190, -3157)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 424),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Avatar of Dwayna Capture"))

def BuildAvatarOfLyssa(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Avatar of Lyssa elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Avatar of Lyssa capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.DERVISH),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.DERVISH),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=554),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-4094, 5856), target_map_id=373),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-16524, -8868)),
        BT.MoveAndKill(pos=(-9692, -7130)),
        BT.MoveAndKill(pos=(-3158, -2143)),
        BT.MoveAndKill(pos=(-1276, -632)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 554),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Avatar of Lyssa Capture"))

def BuildAvatarOfGrenth(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Avatar of Grenth elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Avatar of Grenth capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.DERVISH),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.DERVISH),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=426),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-4431, 5107), target_map_id=380),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(16110, -13455)),
        BT.MoveAndKill(pos=(11764, -10069)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 426),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Avatar of Grenth Capture"))

def BuildArcaneZeal(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Arcane Zeal elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Arcane Zeal capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.DERVISH),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.DERVISH),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=450),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndDialog(pos=(-1052.00, 10003.00), dialog_id=0x82B801),
        BT.Travel(target_map_id=559),
        BT.MoveAndExitMap(pos=(-16114, 18564), target_map_id=465),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-3338, -3747)),
        BT.MoveAndKill(pos=(-4238, 5991)),
        BT.MoveAndKill(pos=(-6163, 11149)),
        BT.MoveAndKill(pos=(-10069, 10900)),
        BT.MoveAndKill(pos=(-12999, 13858)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 450),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Arcane Zeal Capture"))

def BuildGrenthsGrasp(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Grenth's Grasp elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Grenth's Grasp capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.DERVISH),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.DERVISH),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=477),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-15545, -4092), target_map_id=371),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-4241, -6589)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 477),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Grenth's Grasp Capture"))

def BuildReapersSweep(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Reaper's Sweep elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Reaper's Sweep capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.DERVISH),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.DERVISH),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=421),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(22989, 14206), target_map_id=373),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(18459, 421)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 421),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Reaper's Sweep Capture"))

def BuildVowOfStrength(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Vow of Strength elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Vow of Strength capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.DERVISH),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.DERVISH),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=376),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-13963, 18264), target_map_id=375),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-14487, 14623)),
        BT.MoveAndKill(pos=(-16605, 1454)),
        BT.MoveAndKill(pos=(-10991, -11117)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 376),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Vow of Strength Capture"))

def BuildWoundingStrike(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Wounding Strike elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Wounding Strike capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.DERVISH),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.DERVISH),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=476),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-4654, -2531), target_map_id=397),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(17786, 844)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 476),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Wounding Strike Capture"))

def BuildZealousVow(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Zealous Vow elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Zealous Vow capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.DERVISH),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.DERVISH),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=378),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(4856, 3125), target_map_id=377),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(15259, 14877)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 378),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Zealous Vow Capture"))

def BuildSignetOfSpirits(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Signet of Spirits elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Signet of Spirits capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.RITUALIST),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.RITUALIST),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=388),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-8152, -8703), target_map_id=210),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(10536, 17699)),
        BT.MoveAndKill(pos=(3726, 7910)),
        BT.MoveAndKill(pos=(5956, 4177)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 388),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Signet of Spirits Capture"))

def BuildAttunedWasSongkai(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Attuned Was Songkai elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Attuned Was Songkai capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.RITUALIST),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.RITUALIST),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=222),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-6866, 14696), target_map_id=195),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(2686, -9323)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 222),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Attuned Was Songkai Capture"))

def BuildClamorOfSouls(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Clamor of Souls elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Clamor of Souls capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.RITUALIST),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.RITUALIST),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=222),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-6866, 14696), target_map_id=195),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(2686, -9323)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 222),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Clamor of Souls Capture"))

def BuildCaretakersCharge(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Caretaker's Charge elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Caretaker's Charge capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.RITUALIST),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.RITUALIST),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=473),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(11591, -1382), target_map_id=472),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(1670, 10780)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 473),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Caretaker's Charge Capture"))

def BuildConsumeSoul(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Consume Soul elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Consume Soul capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.RITUALIST),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.RITUALIST),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=389),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-5411, 13654), target_map_id=200),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-14256, -2242)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 389),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Consume Soul Capture"))

def BuildSoulTwisting(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Soul Twisting elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Soul Twisting capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.RITUALIST),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.RITUALIST),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=298),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.Move(pos=(-11511, -4836)),
        BT.MoveAndExitMap(pos=(-14412, -8139), target_map_id=205),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(18907.74, 13014.72)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 298),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Soul Twisting Capture"))

def BuildXinraesWeapon(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Xinrae's Weapon elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Xinrae's Weapon capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.RITUALIST),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.RITUALIST),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=496),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.Move(pos=(18267, -6197)),
        BT.MoveAndExitMap(pos=(19693, -7411), target_map_id=466),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-8329, -10361)),
        BT.MoveAndKill(pos=(-6013, -5332)),
        BT.MoveAndKill(pos=(-2935, -6277)),
        BT.MoveAndKill(pos=(142, -9721)),
        BT.MoveAndKill(pos=(2824, -10910)),
        BT.MoveAndKill(pos=(14222, -3991)),
        BT.MoveAndKill(pos=(7129, 169)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 496),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Xinrae's Weapon Capture"))

def BuildWieldersZeal(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Wielder's Zeal elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Wielder's Zeal capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.RITUALIST),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.RITUALIST),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=376),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-13963, 18264), target_map_id=375),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-14487, 14623)),
        BT.MoveAndKill(pos=(-16605, 1454)),
        BT.MoveAndKill(pos=(-8890, -12943)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 376),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Wielder's Zeal Capture"))

def BuildDestructiveWasGlaive(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Destructive Was Glaive elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Destructive Was Glaive capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.RITUALIST),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.RITUALIST),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=387),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-411, 3939), target_map_id=436),
        BT.MoveAndExitMap(pos=(5096, 3792), target_map_id=380),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(1295, 8044)),
        BT.MoveAndKill(pos=(12185, 8546)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 387),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Destructive Was Glaive Capture"))

def BuildGraspingWasKuurong(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Grasping Was Kuurong elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Grasping Was Kuurong capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.RITUALIST),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.RITUALIST),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=391),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(6193, 17595), target_map_id=198),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(5647, -6283)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 391),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Grasping Was Kuurong Capture"))

def BuildOfferingOfSpirit(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Offering of Spirit elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Offering of Spirit capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.RITUALIST),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.RITUALIST),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=495),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-16837, -13647), target_map_id=472),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(12048, -18141)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 495),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Offering of Spirit Capture"))

def BuildPreservation(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Preservation elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Preservation capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.RITUALIST),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.RITUALIST),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=279),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(8538, -19837), target_map_id=144),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-5850, -17503)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 279),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Preservation Capture"))

def BuildReclaimEssence(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Reclaim Essence elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Reclaim Essence capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.RITUALIST),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.RITUALIST),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=442),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(3078, 5274), target_map_id=443),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(7213, -5869)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 442),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Reclaim Essence Capture"))

def BuildRitualLord(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Ritual Lord elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Ritual Lord capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.RITUALIST),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.RITUALIST),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=289),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-13995, -20044), target_map_id=203),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(9018, -11643)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 289),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Ritual Lord Capture"))

def BuildSignetOfGhostlyMight(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Signet of Ghostly Might elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Signet of Ghostly Might capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.RITUALIST),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.RITUALIST),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=480),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.Move(pos=(-3006.40, 13672.54)),
        BT.MoveAndExitMap(pos=(-3042, 11398), target_map_id=446),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-2385.10, 5693.95)),
        BT.MoveAndKill(pos=(-5785.96, 4816.62)),
        BT.MoveAndKill(pos=(-9790.39, -6153.40)),
        BT.MoveAndKill(pos=(-14231.77, -5938.61)),
        BT.MoveAndKill(pos=(-18997.60, -1960.05)),
        BT.MoveAndExitMap(pos=(-19988, -3069), target_map_id=448),
        BT.MoveAndKill(pos=(2100, -19557)),
        BT.MoveAndKill(pos=(-3528, -19879)),
        BT.MoveAndKill(pos=(-7089, -16108)),
        BT.MoveAndKill(pos=(-9079, -14954)),
        BT.MoveAndKill(pos=(-11733, -4433)),
        BT.MoveAndKill(pos=(-11537, -1719)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 480),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Signet of Ghostly Might Capture"))

def BuildSpiritChanneling(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Spirit Channeling elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Spirit Channeling capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.RITUALIST),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.RITUALIST),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=283),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-17865, 16700), target_map_id=197),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(4786, -14399)),
        BT.MoveAndKill(pos=(-6533, -16982)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 283),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Spirit Channeling Capture"))

def BuildSpiritLightWeapon(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Spirit Light Weapon elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Spirit Light Weapon capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.RITUALIST),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.RITUALIST),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=390),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-7023, -10645), target_map_id=201),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(12634, 20424)),
        BT.MoveAndKill(pos=(3329, 20174)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 390),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Spirit Light Weapon Capture"))

def BuildSpiritsStrength(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Spirit's Strength elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Spirit's Strength capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.RITUALIST),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.RITUALIST),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=428),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-139, 12822), target_map_id=399),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-6174, 5134)),
        BT.MoveAndKill(pos=(257, 2542)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 428),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Spirit's Strength Capture"))

def BuildTranquilWasTanasen(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Tranquil Was Tanasen elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Tranquil Was Tanasen capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.RITUALIST),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.RITUALIST),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=51),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(5939, -12643), target_map_id=31),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(8321, -7866)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 51),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Tranquil Was Tanasen Capture"))

def BuildVengefulWasKhanhei(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Vengeful Was Khanhei elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Vengeful Was Khanhei capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.RITUALIST),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.RITUALIST),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=287),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(27438, 5576), target_map_id=209),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(24420, -2651)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 287),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Vengeful Was Khanhei Capture"))

def BuildWanderlust(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Wanderlust elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Wanderlust capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.RITUALIST),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.RITUALIST),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=284),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(2770, -15781), target_map_id=269),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(2916, -12704)),
        BT.MoveAndKill(pos=(189, -7370)),
        BT.MoveAndKill(pos=(5309, 3700)),
        BT.MoveAndKill(pos=(1018, 11378)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 284),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Wanderlust Capture"))

def BuildWeaponOfFury(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Weapon of Fury elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Weapon of Fury capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.RITUALIST),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.RITUALIST),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=424),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(3481, -4573), target_map_id=379),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(2849, 13066)),
        BT.MoveAndKill(pos=(15425, 15994)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 424),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Weapon of Fury Capture"))

def BuildWeaponOfQuickening(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Weapon of Quickening elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Weapon of Quickening capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.RITUALIST),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.RITUALIST),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=219),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-26272, 2836), target_map_id=211),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(22084, 1779)),
        BT.MoveAndKill(pos=(13527, 9125)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 219),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Weapon of Quickening Capture"))

def BuildPrimalRage(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Primal Rage elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Primal Rage capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.WARRIOR),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.WARRIOR),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=298),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.Move(pos=(-11511, -4836)),
        BT.MoveAndExitMap(pos=(-14412, -8139), target_map_id=205),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(18907.74, 13014.72)),
        BT.MoveAndKill(pos=(16910.72, 11775.83)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 298),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Primal Rage Capture"))

def BuildEviscerate(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Eviscerate elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Eviscerate capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.WARRIOR),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.WARRIOR),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=650),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-27552, 16937), target_map_id=482),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(12886.46, -15018.20)),
        BT.MoveAndKill(pos=(9134.72, -13706.59)),
        BT.MoveAndKill(pos=(4565.56, -13479.55)),
        BT.MoveAndKill(pos=(2733.14, -15091.32)),
        BT.MoveAndKill(pos=(10.51, -15436.22)),
        BT.MoveAndKill(pos=(9.80, -17555.21)),
        BT.MoveAndKill(pos=(2167.66, -18356.87)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 650),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Eviscerate Capture"))

def BuildVictoryIsMine(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Victory is Mine elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Victory is Mine capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.WARRIOR),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.WARRIOR),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=158),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-7392, -2618), target_map_id=95),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-3347.47, 2503.66)),
        BT.MoveAndKill(pos=(-5052.62, 2948.76)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 158),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Victory is Mine Capture"))

def BuildCharge(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Charge! elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Charge! capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.WARRIOR),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.WARRIOR),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=277),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(3290, 2443), target_map_id=227),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(11281, 8015)),
        BT.MoveAndKill(pos=(10870, 7251)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 277),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Charge! Capture"))

def BuildCoward(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Coward! elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Coward! capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.WARRIOR),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.WARRIOR),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=278),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(19116, 10013), target_map_id=226),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(16359, 7541)),
        BT.MoveAndKill(pos=(15248, 5324)),
        BT.MoveAndKill(pos=(10957, -4475)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 278),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Coward! Capture"))

def BuildYoureAllAlone(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for You're All Alone! elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting You're All Alone! capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.WARRIOR),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.WARRIOR),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=376),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(3481, -4573), target_map_id=379),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(2849, 13066)),
        BT.MoveAndKill(pos=(15425, 15994)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 376),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="You're All Alone! Capture"))

def BuildAuspiciousParry(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Auspicious Parry elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Auspicious Parry capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.WARRIOR),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.WARRIOR),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=225),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-10496, 11387), target_map_id=206),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-11267, 7475)),
        BT.MoveAndKill(pos=(-12357, 5402)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 225),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Auspicious Parry Capture"))

def BuildBackbreaker(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Backbreaker elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Backbreaker capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.WARRIOR),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.WARRIOR),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=638),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-3174, 1420), target_map_id=498),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(8785, 12354)),
        BT.MoveAndKill(pos=(10056, 13688)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 638),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Backbreaker Capture"))

def BuildBattleRage(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Battle Rage elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Battle Rage capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.WARRIOR),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.WARRIOR),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=219),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-26272, 2836), target_map_id=211),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(22084, 1779)),
        BT.MoveAndKill(pos=(13527, 9125)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 219),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Battle Rage Capture"))

def BuildBullsCharge(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Bull's Charge elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Bull's Charge capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.WARRIOR),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.WARRIOR),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=35),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(22333, -1219), target_map_id=125),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(19989, -1656)),
        BT.MoveAndKill(pos=(18063, -1794)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 35),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Bull's Charge Capture"))

def BuildChargingStrike(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Charging Strike elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Charging Strike capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.WARRIOR),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.WARRIOR),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=435),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(53, 8080), target_map_id=419),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-7215, 14308)),
        BT.MoveAndKill(pos=(-9600.94, 14110.81)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 435),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Charging Strike Capture"))

def BuildCleave(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Cleave elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Cleave capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.WARRIOR),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.WARRIOR),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=289),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-13995, -20044), target_map_id=203),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(9018, -11643)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 289),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Cleave Capture"))

def BuildCripplingSlash(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Crippling Slash elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Crippling Slash capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.WARRIOR),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.WARRIOR),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=644),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-3174, 1420), target_map_id=498),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(8785, 12354)),
        BT.MoveAndKill(pos=(10056, 13688)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 644),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Crippling Slash Capture"))

def BuildDecapitate(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Decapitate elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Decapitate capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.WARRIOR),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.WARRIOR),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=424),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(3481, -4573), target_map_id=379),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(2849, 13066)),
        BT.MoveAndKill(pos=(15425, 15994)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 424),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Decapitate Capture"))

def BuildDefyPain(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Defy Pain elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Defy Pain capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.WARRIOR),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.WARRIOR),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=24),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(22333, -1219), target_map_id=125),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(19989, -1656)),
        BT.MoveAndKill(pos=(18063, -1794)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 24),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Defy Pain Capture"))

def BuildDevastatingHammer(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Devastating Hammer elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Devastating Hammer capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.WARRIOR),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.WARRIOR),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=279),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-11511, -4836), target_map_id=205),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(18907.74, 13014.72)),
        BT.MoveAndKill(pos=(16910.72, 11775.83)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 279),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Devastating Hammer Capture"))

def BuildDragonSlash(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Dragon Slash elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Dragon Slash capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.WARRIOR),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.WARRIOR),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=273),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(2770, -15781), target_map_id=269),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(2916, -12704)),
        BT.MoveAndKill(pos=(189, -7370)),
        BT.MoveAndKill(pos=(5309, 3700)),
        BT.MoveAndKill(pos=(1018, 11378)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 273),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Dragon Slash Capture"))

def BuildDwarvenBattleStance(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Dwarven Battle Stance elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Dwarven Battle Stance capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.WARRIOR),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.WARRIOR),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=639),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-3174, 1420), target_map_id=498),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(8785, 12354)),
        BT.MoveAndKill(pos=(10056, 13688)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 639),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Dwarven Battle Stance Capture"))

def BuildEnragedSmash(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Enraged Smash elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Enraged Smash capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.WARRIOR),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.WARRIOR),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=274),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(22333, -1219), target_map_id=125),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(19989, -1656)),
        BT.MoveAndKill(pos=(18063, -1794)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 274),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Enraged Smash Capture"))

def BuildForcefulBlow(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Forceful Blow elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Forceful Blow capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.WARRIOR),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.WARRIOR),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=272),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(3290, 2443), target_map_id=227),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(11281, 8015)),
        BT.MoveAndKill(pos=(10870, 7251)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 272),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Forceful Blow Capture"))

def BuildHeadbutt(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Headbutt elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Headbutt capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.WARRIOR),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.WARRIOR),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=381),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(3814, -8534), target_map_id=121),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(8603, 1382)),
        BT.MoveAndKill(pos=(6755, 3414)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 381),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Headbutt Capture"))

def BuildHundredBlades(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Hundred Blades elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Hundred Blades capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.WARRIOR),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.WARRIOR),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=284),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(2770, -15781), target_map_id=269),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(2916, -12704)),
        BT.MoveAndKill(pos=(189, -7370)),
        BT.MoveAndKill(pos=(5309, 3700)),
        BT.MoveAndKill(pos=(1018, 11378)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 284),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Hundred Blades Capture"))

def BuildMagehunterStrike(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Magehunter Strike elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Magehunter Strike capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.WARRIOR),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.WARRIOR),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=424),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(3481, -4573), target_map_id=379),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(2849, 13066)),
        BT.MoveAndKill(pos=(15425, 15994)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 424),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Magehunter Strike Capture"))

def BuildMagehuntersSmash(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Magehunter's Smash elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Magehunter's Smash capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.WARRIOR),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.WARRIOR),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=476),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(12327, 11160), target_map_id=477),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(13814, 7961)),
        BT.MoveAndKill(pos=(10586, 8052)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 476),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Magehunter's Smash Capture"))

def BuildQuiveringBlade(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Quivering Blade elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Quivering Blade capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.WARRIOR),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.WARRIOR),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=303),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(22333, -1219), target_map_id=125),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(19989, -1656)),
        BT.MoveAndKill(pos=(18063, -1794)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 303),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Quivering Blade Capture"))

def BuildRageoftheNtouka(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Rage of the Ntouka elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Rage of the Ntouka capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.WARRIOR),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.WARRIOR),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=387),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(22333, -1219), target_map_id=125),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(19989, -1656)),
        BT.MoveAndKill(pos=(18063, -1794)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 387),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Rage of the Ntouka Capture"))

def BuildShove(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Shove elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Shove capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.WARRIOR),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.WARRIOR),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=77),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(10623, 5344), target_map_id=148),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(11594, 5170)),
        BT.MoveAndKill(pos=(13191, 5344)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 77),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Shove Capture"))

def BuildSkullCrack(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Skull Crack elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Skull Crack capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.WARRIOR),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.WARRIOR),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=643),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-3174, 1420), target_map_id=498),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(8785, 12354)),
        BT.MoveAndKill(pos=(10056, 13688)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 643),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Skull Crack Capture"))

def BuildSoldiersStance(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Soldier's Stance elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Soldier's Stance capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.WARRIOR),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.WARRIOR),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=545),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(12327, 11160), target_map_id=477),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(13814, 7961)),
        BT.MoveAndKill(pos=(10586, 8052)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 545),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Soldier's Stance Capture"))

def BuildSteadyStance(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Steady Stance elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Steady Stance capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.WARRIOR),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.WARRIOR),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=407),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(22333, -1219), target_map_id=125),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(19989, -1656)),
        BT.MoveAndKill(pos=(18063, -1794)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 407),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Steady Stance Capture"))

def BuildTripleChop(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Triple Chop elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Triple Chop capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.WARRIOR),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.WARRIOR),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=303),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(22333, -1219), target_map_id=125),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(19989, -1656)),
        BT.MoveAndKill(pos=(18063, -1794)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 303),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Triple Chop Capture"))

def BuildWarriorsEndurance(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Warrior's Endurance elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Warrior's Endurance capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.WARRIOR),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.WARRIOR),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=117),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(10623, 5344), target_map_id=148),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(11594, 5170)),
        BT.MoveAndKill(pos=(13191, 5344)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 117),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Warrior's Endurance Capture"))

def BuildWhirlingAxe(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Whirling Axe elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Whirling Axe capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.WARRIOR),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.WARRIOR),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=273),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(2770, -15781), target_map_id=269),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(2916, -12704)),
        BT.MoveAndKill(pos=(189, -7370)),
        BT.MoveAndKill(pos=(5309, 3700)),
        BT.MoveAndKill(pos=(1018, 11378)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 273),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Whirling Axe Capture"))
def BuildInfuriatingHeat(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(
            message="Starting Infuriating Heat capture routine",
            module_name=MODULE_NAME,
            print_to_console=True,
        ),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.RANGER),
        BT.Wait(duration_ms=500),
        BuySignetOfCapture(LocalProfession.RANGER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=1500),
        BT.Travel(target_map_id=424),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=1000),
        BT.MoveAndExitMap(pos=(3481, -4573), target_map_id=379),
        BT.Wait(duration_ms=500),
        ConfigureAggressiveEnv(),
        BT.Move(pos=(-4903, -328)),
        BT.WaitUntilOutOfCombat(),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 424),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(
        BehaviorTree.SequenceNode(children=nodes, name="Infuriating Heat Capture")
    )

def BuildBroadheadArrow(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(
            message="Starting Broadhead Arrow capture routine",
            module_name=MODULE_NAME,
            print_to_console=True,
        ),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.RANGER),
        BT.Wait(duration_ms=500),
        BuySignetOfCapture(LocalProfession.RANGER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=1500),
        BT.Travel(target_map_id=284),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=1000),
        BT.Move(pos=(11664.37, -18732.13)),
        BT.MoveAndExitMap(pos=(11637, -20480), target_map_id=256),
        BT.Wait(duration_ms=500),
        ConfigureAggressiveEnv(),
        BT.VanquishNode(steps=[(12054, 10092),(12438.57, -2243.74),(12385.90, -5115.57),(9502.17, -7110.23),]),
        BT.WaitUntilOutOfCombat(),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 284),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(
        BehaviorTree.SequenceNode(children=nodes, name="Broadhead Arrow Capture")
    )

def BuildGreaterConflagration(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(
            message="Starting Greater Conflagration capture routine",
            module_name=MODULE_NAME,
            print_to_console=True,
        ),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.RANGER),
        BT.Wait(duration_ms=500),
        BuySignetOfCapture(LocalProfession.RANGER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=1500),
        BT.Travel(target_map_id=124),
        BT.Wait(duration_ms=2000),
        AdvancedHeroTeam(),
        BT.EnterChallenge(target_map_id=124),
        ConfigureAggressiveEnv(),
        BT.VanquishNode(steps=[(2573, 134),(3009, -4916),(5043.89, -7425.06),(9299, -9728),(7827.06, -13540.96),]),
        BT.WaitUntilOutOfCombat(),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 35),
        BT.Wait(duration_ms=2000),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(
        BehaviorTree.SequenceNode(children=nodes, name="Greater Conflagration Capture")
    )

def BuildPoisonArrow(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(
            message="Starting Poison Arrow capture routine",
            module_name=MODULE_NAME,
            print_to_console=True,
        ),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.RANGER),
        BT.Wait(duration_ms=500),
        BuySignetOfCapture(LocalProfession.RANGER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=1500),
        BT.Travel(target_map_id=158),
        AdvancedHeroTeam(),
        BT.MoveAndExitMap(pos=(-7392, -2618), target_map_id=95),
        BT.Wait(duration_ms=500),
        ConfigureAggressiveEnv(),
        BT.VanquishNode(steps=[(-3347.47, 2503.66),(-5052.62, 2948.76),]),
        BT.WaitUntilOutOfCombat(),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 158),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(
        BehaviorTree.SequenceNode(children=nodes, name="Poison Arrow Capture")
    )

def BuildPreparedShot(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(
            message="Starting Prepared Shot capture routine",
            module_name=MODULE_NAME,
            print_to_console=True,
        ),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.RANGER),
        BT.Wait(duration_ms=500),
        BuySignetOfCapture(LocalProfession.RANGER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=1500),
        BT.Travel(target_map_id=642),
        AdvancedHeroTeam(),
        BT.MoveAndExitMap(pos=(1250, 800), target_map_id=499),
        BT.Wait(duration_ms=500),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(6931.01, 5348.25)),
        BT.WaitUntilOutOfCombat(),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 642),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(
        BehaviorTree.SequenceNode(children=nodes, name="Prepared Shot Capture")
    )


def BuildArchersSignet(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(
            message="Starting Archer's Signet capture routine",
            module_name=MODULE_NAME,
            print_to_console=True,
        ),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.RANGER),
        BT.Wait(duration_ms=500),
        BuySignetOfCapture(LocalProfession.RANGER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=1500),
        BT.Travel(target_map_id=129),
        AdvancedHeroTeam(),
        BT.MoveAndExitMap(pos=(-7622, 1811), target_map_id=201),
        BT.Wait(duration_ms=500),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(7851, -7812)),
        BT.Wait(duration_ms=25000),
        BT.WaitUntilOutOfCombat(),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 129),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(
        BehaviorTree.SequenceNode(children=nodes, name="Archer's Signet Capture")
    )


def BuildGlassArrows(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(
            message="Starting Glass Arrows capture routine",
            module_name=MODULE_NAME,
            print_to_console=True,
        ),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.RANGER),
        BT.Wait(duration_ms=500),
        BuySignetOfCapture(LocalProfession.RANGER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=1500),
        BT.Travel(target_map_id=130),
        AdvancedHeroTeam(),
        BT.MoveAndExitMap(pos=(24085, 7289), target_map_id=205),
        BT.Wait(duration_ms=500),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-15388, 268)),
        BT.WaitUntilOutOfCombat(),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 130),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(
        BehaviorTree.SequenceNode(children=nodes, name="Glass Arrows Capture")
    )

def BuildBarrage(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(
            message="Starting Barrage capture routine",
            module_name=MODULE_NAME,
            print_to_console=True,
        ),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.RANGER),
        BT.Wait(duration_ms=500),
        BuySignetOfCapture(LocalProfession.RANGER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=1500),
        BT.Travel(target_map_id=349),
        AdvancedHeroTeam(),
        BT.MoveAndExitMap(pos=(-11143, -23655), target_map_id=195),
        BT.Wait(duration_ms=500),
        ConfigureAggressiveEnv(),
        BT.VanquishNode(steps=[(-8262, 18124),(-4299, 12125),]),
        BT.WaitUntilOutOfCombat(),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 349),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(
        BehaviorTree.SequenceNode(children=nodes, name="Barrage Capture")
    )


def BuildBurningArrow(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(
            message="Starting Burning Arrow capture routine",
            module_name=MODULE_NAME,
            print_to_console=True,
        ),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.RANGER),
        BT.Wait(duration_ms=500),
        BuySignetOfCapture(LocalProfession.RANGER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=1500),
        BT.Travel(target_map_id=381),
        AdvancedHeroTeam(),
        BT.MoveAndExitMap(pos=(-5984, 5358), target_map_id=371),
        BT.Wait(duration_ms=500),
        ConfigureAggressiveEnv(),
        BT.VanquishNode(steps=[(17803, -13310),(11578, -14143),(7770.03, -16148.65),]),
        BT.WaitUntilOutOfCombat(),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 381),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(
        BehaviorTree.SequenceNode(children=nodes, name="Burning Arrow Capture")
    )


def BuildCripplingShot(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(
            message="Starting Crippling Shot capture routine",
            module_name=MODULE_NAME,
            print_to_console=True,
        ),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.RANGER),
        BT.Wait(duration_ms=500),
        BuySignetOfCapture(LocalProfession.RANGER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=1500),
        BT.Travel(target_map_id=640),
        AdvancedHeroTeam(),
        BT.Move(pos=(18003.32, 16753.06)),
        BT.MoveAndExitMap(pos=(20243, 16910), target_map_id=501),
        BT.Wait(duration_ms=500),
        ConfigureAggressiveEnv(),
        BT.VanquishNode(steps=[(-5781, -9354),(1762, -8654),(19306, 6218),]),
        BT.WaitUntilOutOfCombat(),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 640),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(
        BehaviorTree.SequenceNode(children=nodes, name="Crippling Shot Capture")
    )
def BuildEnragedLunge(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(
            message="Starting Enraged Lunge capture routine",
            module_name=MODULE_NAME,
            print_to_console=True,
        ),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.RANGER),
        BT.Wait(duration_ms=500),
        BuySignetOfCapture(LocalProfession.RANGER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=1500),
        BT.Travel(target_map_id=51),
        AdvancedHeroTeam(),
        BT.MoveAndExitMap(pos=(7316, -17027), target_map_id=265),
        BT.Wait(duration_ms=500),
        ConfigureAggressiveEnv(),
        BT.VanquishNode(steps=[(18687, 7650),(14559, 2226),(7167, -1901),(4725, -142),]),
        BT.WaitUntilOutOfCombat(),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 51),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(
        BehaviorTree.SequenceNode(children=nodes, name="Enraged Lunge Capture")
    )


def BuildEquinox(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(
            message="Starting Equinox capture routine",
            module_name=MODULE_NAME,
            print_to_console=True,
        ),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.RANGER),
        BT.Wait(duration_ms=500),
        BuySignetOfCapture(LocalProfession.RANGER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=1500),
        BT.Travel(target_map_id=284),
        AdvancedHeroTeam(),
        BT.Move(pos=(11722, -18582)),
        BT.MoveAndExitMap(pos=(11699, -20253), target_map_id=256),
        BT.Wait(duration_ms=500),
        ConfigureAggressiveEnv(),
        BT.VanquishNode(steps=[(11908, 8425),(11332, -6134),(-1646, -6959),]),
        BT.WaitUntilOutOfCombat(),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 284),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(
        BehaviorTree.SequenceNode(children=nodes, name="Equinox Capture")
    )


def BuildEscape(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(
            message="Starting Escape capture routine",
            module_name=MODULE_NAME,
            print_to_console=True,
        ),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.RANGER),
        BT.Wait(duration_ms=500),
        BuySignetOfCapture(LocalProfession.RANGER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=1500),
        BT.Travel(target_map_id=224),
        AdvancedHeroTeam(),
        BT.MoveAndExitMap(pos=(4392, 26052), target_map_id=199),
        BT.Wait(duration_ms=500),
        ConfigureAggressiveEnv(),
        BT.VanquishNode(steps=[(8539, -7857),(1276, -8157),]),
        BT.WaitUntilOutOfCombat(),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 224),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(
        BehaviorTree.SequenceNode(children=nodes, name="Escape Capture")
    )
def BuildExpertsDexterity(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(
            message="Starting Expert's Dexterity capture routine",
            module_name=MODULE_NAME,
            print_to_console=True,
        ),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.RANGER),
        BT.Wait(duration_ms=500),
        BuySignetOfCapture(LocalProfession.RANGER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=1500),
        BT.Travel(target_map_id=407),
        AdvancedHeroTeam(),
        BT.MoveAndExitMap(pos=(5023, 4589), target_map_id=402),
        BT.Wait(duration_ms=500),
        ConfigureAggressiveEnv(),
        BT.VanquishNode(steps=[(3202, -15474),(4546, -17479),(14600, -13203),]),
        BT.WaitUntilOutOfCombat(),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 407),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(
        BehaviorTree.SequenceNode(children=nodes, name="Expert's Dexterity Capture")
    )


def BuildFamine(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(
            message="Starting Famine capture routine",
            module_name=MODULE_NAME,
            print_to_console=True,
        ),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.RANGER),
        BT.Wait(duration_ms=500),
        BuySignetOfCapture(LocalProfession.RANGER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=1500),
        BT.Travel(target_map_id=226),
        AdvancedHeroTeam(),
        BT.MoveAndExitMap(pos=(-9662, 3084), target_map_id=233),
        BT.Wait(duration_ms=500),
        ConfigureAggressiveEnv(),
        BT.VanquishNode(steps=[(16446, 261),(15194, 299),(14830, -2177),(14690, -4412),(12365, -5527),(10957, -4475),(6532, -6607),(6339, -4584),(3023, -6434),(2837, -4469),]),
        BT.WaitUntilOutOfCombat(),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 226),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(
        BehaviorTree.SequenceNode(children=nodes, name="Famine Capture")
    )


def BuildFerociousStrike(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(
            message="Starting Ferocious Strike capture routine",
            module_name=MODULE_NAME,
            print_to_console=True,
        ),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.RANGER),
        BT.Wait(duration_ms=500),
        BuySignetOfCapture(LocalProfession.RANGER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=1500),
        BT.Travel(target_map_id=273),
        AdvancedHeroTeam(),
        BT.MoveAndExitMap(pos=(3473, 7682), target_map_id=247),
        BT.Wait(duration_ms=500),
        ConfigureAggressiveEnv(),
        BT.VanquishNode(steps=[(13205, -8400),(13860, -7537),(19037, -9594),(21925, -4834),]),
        BT.WaitUntilOutOfCombat(),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 273),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(
        BehaviorTree.SequenceNode(children=nodes, name="Ferocious Strike Capture")
    )
def BuildHealAsOne(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(
            message="Starting Heal as One capture routine",
            module_name=MODULE_NAME,
            print_to_console=True,
        ),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.RANGER),
        BT.Wait(duration_ms=500),
        BuySignetOfCapture(LocalProfession.RANGER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=1500),
        BT.Travel(target_map_id=390),
        AdvancedHeroTeam(),
        BT.MoveAndExitMap(pos=(-7023, -10645), target_map_id=201),
        BT.Wait(duration_ms=500),
        ConfigureAggressiveEnv(),
        BT.VanquishNode(steps=[(12634, 20424),(8857, 16480),]),
        BT.WaitUntilOutOfCombat(),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 390),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(
        BehaviorTree.SequenceNode(children=nodes, name="Heal as One Capture")
    )


def BuildLacerate(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(
            message="Starting Lacerate capture routine",
            module_name=MODULE_NAME,
            print_to_console=True,
        ),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.RANGER),
        BT.Wait(duration_ms=500),
        BuySignetOfCapture(LocalProfession.RANGER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=1500),
        BT.Travel(target_map_id=272),
        AdvancedHeroTeam(),
        BT.Move(pos=(5487, 6623)),
        BT.MoveAndExitMap(pos=(6566, 8093), target_map_id=244),
        BT.Wait(duration_ms=500),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(2950, -8661)),
        BT.WaitUntilOutOfCombat(),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 272),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(
        BehaviorTree.SequenceNode(children=nodes, name="Lacerate Capture")
    )


def BuildMagebaneShot(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(
            message="Starting Magebane Shot capture routine",
            module_name=MODULE_NAME,
            print_to_console=True,
        ),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.RANGER),
        BT.Wait(duration_ms=500),
        BuySignetOfCapture(LocalProfession.RANGER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=1500),
        BT.Travel(target_map_id=442),
        AdvancedHeroTeam(),
        BT.MoveAndExitMap(pos=(-2395, -4922), target_map_id=441),
        BT.Wait(duration_ms=500),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(12200, 5685)),
        BT.Wait(duration_ms=10000),
        BT.Move(pos=(12294.00, 5674.00)),
        BT.InteractTarget(),
        BT.MoveAndKill(pos=(24286, 10004)),
        BT.WaitUntilOutOfCombat(),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 442),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(
        BehaviorTree.SequenceNode(children=nodes, name="Magebane Shot Capture")
    )

def BuildMarksmansWager(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Marksman's Wager elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Marksman's Wager capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.RANGER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.RANGER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=117),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.EnterChallenge(target_map_id=117),
        BT.Wait(duration_ms=5000),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-857, 8546)),
        BT.MoveAndKill(pos=(-2320, 5881)),
        BT.MoveAndKill(pos=(-125.10, 3166.91)),
        BT.MoveAndKill(pos=(-50.19, 103.76)),
        BT.MoveAndKill(pos=(1417.27, -2503.34)),
        BT.MoveAndKill(pos=(4508.23, -3895.00)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 117),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Marksman's Wager Capture"))

def BuildMelandrusArrows(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Melandru's Arrows elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Melandru's Arrows capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.RANGER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.RANGER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=159),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(3290, 2443), target_map_id=227),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(11281, 8015)),
        BT.MoveAndKill(pos=(10870, 7251)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 159),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Melandru's Arrows Capture"))

def BuildMelandrusShot(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Melandru's Shot elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Melandru's Shot capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.RANGER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.RANGER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=193),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(22333, -1219), target_map_id=125),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(19989, -1656)),
        BT.MoveAndKill(pos=(18063, -1794)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 193),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Melandru's Shot Capture"))

def BuildOathShot(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Oath Shot elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Oath Shot capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.RANGER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.RANGER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=23),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(22333, -1219), target_map_id=125),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(19989, -1656)),
        BT.MoveAndKill(pos=(18063, -1794)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 23),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Oath Shot Capture"))

def BuildQuickShot(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Quick Shot elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Quick Shot capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.RANGER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.RANGER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=425),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(3481, -4573), target_map_id=379),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(2849, 13066)),
        BT.MoveAndKill(pos=(15425, 15994)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 425),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Quick Shot Capture"))

def BuildQuicksand(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Quicksand elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Quicksand capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.RANGER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.RANGER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=442),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-13995, -20044), target_map_id=203),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(9018, -11643)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 442),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Quicksand Capture"))

def BuildRampageAsOne(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Rampage as One elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Rampage as One capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.RANGER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.RANGER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=387),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(22333, -1219), target_map_id=125),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(19989, -1656)),
        BT.MoveAndKill(pos=(18063, -1794)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 387),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Rampage as One Capture"))

def BuildScavengersFocus(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Scavenger's Focus elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Scavenger's Focus capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.RANGER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.RANGER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=440),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-10496, 11387), target_map_id=206),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-11267, 7475)),
        BT.MoveAndKill(pos=(-12357, 5402)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 440),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Scavenger's Focus Capture"))

def BuildSmokeTrap(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Smoke Trap elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Smoke Trap capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.RANGER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.RANGER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=442),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-13995, -20044), target_map_id=203),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(9018, -11643)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 442),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Smoke Trap Capture"))

def BuildSpikeTrap(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Spike Trap elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Spike Trap capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.RANGER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.RANGER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=219),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-26272, 2836), target_map_id=211),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(22084, 1779)),
        BT.MoveAndKill(pos=(13527, 9125)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 219),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Spike Trap Capture"))

def BuildStrikeAsOne(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Strike as One elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Strike as One capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.RANGER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.RANGER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=421),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(22333, -1219), target_map_id=125),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(19989, -1656)),
        BT.MoveAndKill(pos=(18063, -1794)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 421),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Strike as One Capture"))

def BuildTrappersFocus(skill: EliteSkill) -> BehaviorTree:
    """Build BT sequence for Trapper's Focus elite skill capture."""
    nodes = [
        BT.LogMessage(message="Starting Trapper's Focus capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.RANGER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.RANGER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=389),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(22333, -1219), target_map_id=125),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(19989, -1656)),
        BT.MoveAndKill(pos=(18063, -1794)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 389),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Trapper's Focus Capture"))
def BuildSignetOfJudgement(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Signet of Judgement capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.MONK),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.MONK),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=155),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(7565, -45115), target_map_id=26),
        ConfigureAggressiveEnv(),
        BT.Move(pos=(-18688, 12186)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 155),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Signet of Judgement Capture"))
def BuildUnyieldingAura(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Unyielding Aura capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.MONK),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.MONK),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=158),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-7392, -2618), target_map_id=95),
        ConfigureAggressiveEnv(),
        BT.Move(pos=(-3347.47, 2503.66)),
        BT.Move(pos=(-5052.62, 2948.76)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 158),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Unyielding Aura Capture"))
def BuildSpellBreaker(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Spell Breaker capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.MONK),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.MONK),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=155),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(6038, -41402), target_map_id=91),
        ConfigureAggressiveEnv(),
        BT.Move(pos=(1526.63, -39178.76)),
        BT.Move(pos=(592.26, -43048.45)),
        BT.Move(pos=(-2607.90, -44448.80)),
        BT.Move(pos=(-5678.81, -43418.43)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 155),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Spell Breaker Capture"))
def BuildGlimmerOfLight(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Glimmer of Light capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.MONK),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.MONK),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=421),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(26133, 17180), target_map_id=386),
        ConfigureAggressiveEnv(),
        BT.Move(pos=(3337, -12769)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 421),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Glimmer of Light Capture"))

def BuildBlessedLight(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Blessed Light capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.MONK),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.MONK),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=193),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.Move(pos=(5672, -4404)),
        BT.MoveAndExitMap(pos=(6809, -7548), target_map_id=198),
        ConfigureAggressiveEnv(),
        BT.Move(pos=(6044.61, 10084.75)),
        BT.Move(pos=(10710, 3833)),
        BT.Move(pos=(14782.42, 77.85)),
        BT.Move(pos=(11879.36, -3854.92)),
        BT.Move(pos=(16852.28, -8500.27)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 193),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Blessed Light Capture"))

def BuildHealingLight(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Healing Light capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.MONK),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.MONK),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=193),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.Move(pos=(5672, -4404)),
        BT.MoveAndExitMap(pos=(6809, -7548), target_map_id=198),
        ConfigureAggressiveEnv(),
        BT.Move(pos=(6044.61, 10084.75)),
        BT.Move(pos=(10271, 4880)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 193),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Healing Light Capture"))

def BuildBoonSignet(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Boon Signet capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.MONK),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.MONK),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=388),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.Move(pos=(-7243.40, -8111.62)),
        BT.MoveAndExitMap(pos=(-8040, -8675), target_map_id=210),
        ConfigureAggressiveEnv(),
        BT.Move(pos=(12619.55, 21320.75)),
        BT.Move(pos=(8350.78, 13316.25)),
        BT.Move(pos=(7732.76, 11883.11)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 388),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Boon Signet Capture"))

def BuildHealersBoon(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Healer's Boon capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.MONK),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.MONK),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=403),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-18733, 13488), target_map_id=402),
        ConfigureAggressiveEnv(),
        BT.Move(pos=(-16092, 7570)),
        BT.Move(pos=(-18859.48, -543.13)),
        BT.Move(pos=(-18043.42, -3146.39)),
        BT.Move(pos=(-14355.99, -4735.46)),
        BT.Move(pos=(976.84, -7402.01)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 403),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Healer's Boon Capture"))

def BuildPeaceandHarmony(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Peace and Harmony capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.MONK),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.MONK),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=155),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(5797, -41362), target_map_id=91),
        ConfigureAggressiveEnv(),
        BT.Move(pos=(6758, -32813)),
        BT.Move(pos=(5448, -29156)),
        BT.Move(pos=(1608, -29247)),
        BT.Move(pos=(4823.32, -22619.05)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 155),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Peace and Harmony Capture"))


def BuildWithdrawHexes(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Withdraw Hexes capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.MONK),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.MONK),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=389),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-5840, 14320), target_map_id=200),
        ConfigureAggressiveEnv(),
        BT.Move(pos=(-7252, -2700)),
        BT.Move(pos=(-8604, 8056)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 389),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Withdraw Hexes Capture"))


def BuildHealingBurst(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Healing Burst capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.MONK),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.MONK),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=130),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(18153, 1880), target_map_id=128),
        ConfigureAggressiveEnv(),
        BT.Move(pos=(16632, -2766)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 130),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Healing Burst Capture"))


def BuildHealingHands(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Healing Hands capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.MONK),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.MONK),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=35),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.Move(pos=(3695, -9914)),
        BT.MoveAndExitMap(pos=(3772, -8096), target_map_id=121),
        ConfigureAggressiveEnv(),
        BT.Move(pos=(4435.06, 2104.76)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 35),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Healing Hands Capture"))


def BuildLightofDeliverance(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Light of Deliverance capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.MONK),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.MONK),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=554),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(5721, -5353), target_map_id=371),
        ConfigureAggressiveEnv(),
        BT.Move(pos=(-3106, 9981)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 554),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Light of Deliverance Capture"))

def BuildWordofHealing(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Word of Healing capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.MONK),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.MONK),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=303),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(16596, 20549), target_map_id=240),
        ConfigureAggressiveEnv(),
        BT.Move(pos=(-5836, -8676)),
        BT.Move(pos=(-4659, -17086)),
        BT.Move(pos=(-5177, -19524)),
        BT.MoveAndExitMap(pos=(-5167, -21282), target_map_id=31),
        BT.Move(pos=(-3172.72, 9102.06)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 303),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Word of Healing Capture"))


def BuildAirofEnchantment(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Air of Enchantment capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.MONK),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.MONK),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=297),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(17214, 10919), target_map_id=203),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(436, -14129)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 297),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Air of Enchantment Capture"))


def BuildAuraofFaith(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Aura of Faith capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.MONK),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.MONK),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=23),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-12507, -23517), target_map_id=94),
        ConfigureAggressiveEnv(),
        BT.Move(pos=(7408, 15741)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 23),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Aura of Faith Capture"))


def BuildDivertHexes(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Divert Hexes capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.MONK),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.MONK),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=480),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-3104, 11454), target_map_id=446),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(590.94, 8003.54)),
        BT.MoveAndKill(pos=(1281.14, 7621.92)),
        BT.Wait(duration_ms=6000),
        BT.MoveAndKill(pos=(1144.00, 7795.00)),
        BT.InteractTarget(),
        BT.MoveAndKill(pos=(8356, 6260)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 480),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Divert Hexes Capture"))


def BuildLifeSheath(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Life Sheath capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.MONK),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.MONK),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=284),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.Move(pos=(11581, -18462)),
        BT.MoveAndExitMap(pos=(11729, -20248), target_map_id=256),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(1667, 8179)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 284),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Life Sheath Capture"))

def BuildShieldOfRegeneration(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Shield of Regeneration capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.MONK),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.MONK),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=648),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.Move(pos=(11581, -18462)),
        BT.MoveAndExitMap(pos=(-15205, 13205), target_map_id=647),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-5878, 4262)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 648),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Shield of Regeneration Capture"))


def BuildZealousBenediction(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Zealous Benediction capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.MONK),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.MONK),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=428),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-3, 12656), target_map_id=399),
        ConfigureAggressiveEnv(),
        BT.VanquishNode(steps=[(-6079,4930),(-7671,-3974),(-8311,-8169),(3971,-12376)]),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 428),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Zealous Benediction Capture"))


def BuildDefendersZeal(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Defender's Zeal capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.MONK),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.MONK),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=469),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(7784, 18756), target_map_id=468),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(8744, -3500)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 469),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Defender's Zeal Capture"))


def BuildRayofJudgment(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Ray of Judgment capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.MONK),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.MONK),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=303),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(16596, 20549), target_map_id=240),
        ConfigureAggressiveEnv(),
        BT.VanquishNode(steps=[(-5836,-8676),(1451.48,-11371.12),(3837.11,-11483.70),(6579.26,-15095.15)]),
        BT.MoveAndExitMap(pos=(4201, -17019), target_map_id=241),
        #BT.ItemsUseAllConsumables(),
        BT.Move(pos=(8936, 11691)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 303),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Ray of Judgment Capture"))


def BuildWordOfCensure(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Word of Censure capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.MONK),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.MONK),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=303),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(10898, 14691), target_map_id=239),
        ConfigureAggressiveEnv(),
        BT.VanquishNode(steps=[(6662,14738),(3888,12848),(-5294,12210),(-7574,11998),(-7848,14735),(-7357,19672)]),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 303),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Word of Censure Capture"))


def BuildEmpathicRemoval(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Empathic Removal capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.MONK),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.MONK),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=129),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-7622, 1811), target_map_id=201),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-10570, 9687)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 129),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Empathic Removal Capture"))
def BuildMartyr(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Martyr capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.MONK),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.MONK),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=442),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-2263, -4568), target_map_id=441),
        ConfigureAggressiveEnv(),
        BT.VanquishNode(steps=[(1187.66,7907.58),(-2401.63,7256.86),(-3468.55,7226.10)]),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 442),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Martyr Capture"))


def BuildSignetOfRemoval(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Signet of Removal capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.MONK),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.MONK),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=427),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-16327, -16374), target_map_id=384),
        ConfigureAggressiveEnv(),
        BT.VanquishNode(steps=[(2931,4745),(-1370,647),(3193.36,-5025.75)]),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 427),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Signet of Removal Capture"))


def BuildBalthazarsPendulum(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Balthazar's Pendulum capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.MONK),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.MONK),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=378),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(5833, 4322), target_map_id=377),
        ConfigureAggressiveEnv(),
        BT.VanquishNode(steps=[(-13138.58,15124.79),(-10693,13246),(-9128,6575),(-10995,4335),(-12734,3613)]),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 378),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Balthazar's Pendulum Capture"))
def BuildLifeBarrier(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Life Barrier capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.MONK),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.MONK),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=24),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-7469, -31762), target_map_id=98),
        ConfigureAggressiveEnv(),
        BT.VanquishNode(steps=[(13171, 13137),(8538, 10771),(8703, 3675),(3643, 2558)]),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 24),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Life Barrier Capture"))

def BuildMarkOfProtection(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Mark of Protection capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.MONK),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.MONK),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=38),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-20530, -300), target_map_id=113),
        ConfigureAggressiveEnv(),
        BT.Move(pos=(11978, -12945)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 38),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Mark of Protection Capture"))


def BuildAnimateFleshGolem(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Animate Flesh Golem capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.NECROMANCER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.NECROMANCER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=51),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(5363, -12211), target_map_id=31),
        ConfigureAggressiveEnv(),
        BT.VanquishNode(steps=[(5179, 2952),(3615, 7450),(9049, 3750),(3807, 14506)]),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 51),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Animate Flesh Golem Capture"))

def BuildContagion(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Contagion capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.NECROMANCER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.NECROMANCER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=425),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-15149, 8672), target_map_id=384),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-17954, 4393)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 425),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Contagion Capture"))

def BuildCorruptEnchantment(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Corrupt Enchantment capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.NECROMANCER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.NECROMANCER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=393),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-6041, -1493), target_map_id=392),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-11689, -11432)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 393),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Corrupt Enchantment Capture"))

def BuildCultistsFervor(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Cultist's Fervor capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.NECROMANCER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.NECROMANCER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=234),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-6654, 7301), target_map_id=202),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(10855, -978)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 234),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Cultist's Fervor Capture"))

def BuildTaintedFlesh(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Tainted Flesh capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.NECROMANCER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.NECROMANCER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=287),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(32765, 10871), target_map_id=205),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-3359, -4976)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 287),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Tainted Flesh Capture"))

def BuildDepravity(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Depravity capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.NECROMANCER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.NECROMANCER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=381),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.Move(pos=(-1401, 1675)),
        BT.MoveAndExitMap(pos=(4805, 943), target_map_id=380),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(1550, -11990)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 381),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Depravity Capture"))

def BuildDiscord(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Discord capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.NECROMANCER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.NECROMANCER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=350),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(18483, 11343), target_map_id=199),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(18504, 332)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 350),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Discord Capture"))

def BuildIcyVeins(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Icy Veins capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.NECROMANCER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.NECROMANCER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=222),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-6840, 14641), target_map_id=195),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-11535, -8301)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 222),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Icy Veins Capture"))

def BuildCripplingAnguish(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Crippling Anguish capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.MESMER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.MESMER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=222),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-6840, 14641), target_map_id=195),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-6719, -8760)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 222),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Crippling Anguish Capture"))

def BuildRavenousGaze(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Ravenous Gaze capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.NECROMANCER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.NECROMANCER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=424),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-5400, 5435), target_map_id=369),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(16919, -7990)),
        BT.MoveAndKill(pos=(9744, -6408)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 424),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Ravenous Gaze Capture"))

def BuildSignetOfSuffering(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Signet of Suffering capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.NECROMANCER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.NECROMANCER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=442),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(3146, 5326), target_map_id=443),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(26837, -9576)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 442),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Signet of Suffering Capture"))

def BuildLingeringCurse(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Lingering Curse capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.NECROMANCER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.NECROMANCER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=272),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(6741, 8137), target_map_id=244),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(1670, -16662)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 272),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Lingering Curse Capture"))

def BuildSoulBind(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Soul Bind capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.NECROMANCER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.NECROMANCER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=284),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.Move(pos=(11722, -18582)),
        BT.MoveAndExitMap(pos=(11699, -20253), target_map_id=256),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-268, -3164)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 284),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Soul Bind Capture"))

def BuildVampiricSpirit(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Vampiric Spirit capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.NECROMANCER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.NECROMANCER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=272),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(6741, 8137), target_map_id=244),
        ConfigureAggressiveEnv(),
        BT.VanquishNode(steps=[(1670, -16662),(-504.80, -16517.78),(-2798.65, -14165.61),(-3806.34, -11823.33),(-3814.97, -9261.53),(-5226.15, -7235.82),(-4634.54, -4265.22),(-5148.32, -561.04),(-8040.69, 1808.49),(-10270.11, 1419.24),(-10349.71, -1068.52),(-12137.71, -3830.18),(-12871.10, -7120.67),(-11126.82, -8543.61),(-12697.35, -10302.01)]),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 272),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Vampiric Spirit Capture"))

def BuildGrenthsBalance(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Grenth's Balance capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.NECROMANCER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.NECROMANCER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=378),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(5113,3280), target_map_id=377),
        ConfigureAggressiveEnv(),
        BT.VanquishNode(steps=[(-13774,15792),(-10455,13159),(-7383,13899),(-5354,6658),(-2508,12905),(5144,12110),(9696,1088),(7632,-1551),(6514,-4133)]),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 378),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Grenth's Balance Capture"))
def BuildJaggedBones(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Jagged Bones capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.NECROMANCER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.NECROMANCER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=643),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.Move(pos=(14682,22900)),
        BT.MoveAndExitMap(pos=(17000,22872), target_map_id=546),
        ConfigureAggressiveEnv(),
        BT.VanquishNode(steps=[(-9431,-20124),(-8441,-13685),(-9743,-6744),(-10672,4815),(-8464,17239),(-11761,24520)]),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 643),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Jagged Bones Capture"))

def BuildOfferingOfBlood(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Offering of Blood capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.NECROMANCER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.NECROMANCER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=22),
        AdvancedHeroTeam(),
        BT.EnterChallenge(target_map_id=22),
        ConfigureAggressiveEnv(),
        BT.VanquishNode(steps=[(-11206.22,-8611.91),(-9682.32,-7021.72),(-8752.07,-4005.16),(-7490.79,-2338.30),(-8756.21,-1456.15),(-12159,-893)]),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 22),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Offering of Blood Capture"))

def BuildOrderOfTheVampire(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Order of the Vampire capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.NECROMANCER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.NECROMANCER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=117),
        AdvancedHeroTeam(),
        BT.EnterChallenge(target_map_id=117),
        BT.WaitForMapToChange(map_id=117),
        ConfigureAggressiveEnv(),
        BT.VanquishNode(steps=[(-857,8546),(-2320,5881),(-125.10,3166.91),(-50.19,103.76),(1417.27,-2503.34),(4508.23,-3895.00),(5735.68,-3615.36),(6548.60,-2597.65),(6904.65,-1450.62),(8282.06,-1424.29)]),
        BT.MoveAndInteract(pos=(8945,-2457)),
        BT.WaitForMapToChange(map_id=117),
        BT.Wait(duration_ms=1000),
        BT.VanquishNode(steps=[(13091,-5283),(10711.53,-4565.11),(8666.88,-6085.35),(9782.77,-9098.71),(5899,-6912)]),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 117),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Order of the Vampire Capture"))
def BuildToxicChill(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Toxic Chill capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.NECROMANCER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.NECROMANCER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=433),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(5067,1018), target_map_id=404),
        ConfigureAggressiveEnv(),
        BT.Move(pos=(659,1838)),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 433),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Toxic Chill Capture"))

def BuildWailOfDoom(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Wail of Doom capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.NECROMANCER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.NECROMANCER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=226),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-9625,3076), target_map_id=233),
        ConfigureAggressiveEnv(),
        BT.VanquishNode(steps=[(8310,-7070),(10629,-7757)]),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 226),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Wail of Doom Capture"))

def BuildWeakenKnees(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Weaken Knees capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.NECROMANCER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.NECROMANCER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=129),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-7622,1811), target_map_id=201),
        ConfigureAggressiveEnv(),
        BT.Move(pos=(7851,-7812)),
        BT.Wait(duration_ms=25000),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 129),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Weaken Knees Capture"))
def BuildSpoilVictor(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Spoil Victor capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.NECROMANCER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.NECROMANCER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=230),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.Move(pos=(-4247.07, 3886.89)),
        BT.MoveAndExitMap(pos=(-4663, 4805), target_map_id=209),
        ConfigureAggressiveEnv(),
        BT.VanquishNode(steps=[(-19692, -6351), (-23447, -4835), (-26800.49, -3882.72)]),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 230),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Spoil Victor Capture"))

def BuildLifeTransfer(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Life Transfer capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.NECROMANCER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.NECROMANCER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=650),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-21630,12565), target_map_id=649),
        ConfigureAggressiveEnv(),
        BT.VanquishNode(steps=[(-4163,-203),(11385,2228),(19190,-12141)]),
        BT.MoveAndExitMap(pos=(23054,-13225), target_map_id=651),
        ConfigureAggressiveEnv(),
        BT.VanquishNode(steps=[(-16333,16622),(-9609,11059)]),
        BT.WaitUntilOutOfCombat(timeout_ms=120000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 650),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Life Transfer Capture"))

def BuildSpitefulSpirit(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Spiteful Spirit capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.NECROMANCER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.NECROMANCER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=155),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(7565,-45115), target_map_id=26),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-18688,12186)),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 155),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Spiteful Spirit Capture"))

def BuildReapersMark(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Reaper's Mark capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.NECROMANCER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.NECROMANCER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=378),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(5833,4322), target_map_id=377),
        ConfigureAggressiveEnv(),
        BT.VanquishNode(steps=[(-13138.58,15124.79),(-10693,13246),(-9128,6575),(-10995,4335),(-12734,3613)]),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 378),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Reaper's Mark Capture"))

def BuildPlagueSignet(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Plague Signet capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.NECROMANCER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.NECROMANCER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=640),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(16363,13124), target_map_id=569),
        ConfigureAggressiveEnv(),
        BT.VanquishNode(steps=[(12400,9817),(8632,6437),(8268,-1725)]),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 640),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Plague Signet Capture"))

def BuildAuraOfTheLich(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Aura of the Lich capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.NECROMANCER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.NECROMANCER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=124),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.EnterChallenge(target_map_id=6000),
        ConfigureAggressiveEnv(),
        BT.VanquishNode(steps=[(2573,134),(3009,-4916)]),
        BT.Wait(duration_ms=7000),
        BT.VanquishNode(steps=[(5043.89,-7425.06),(9299,-9728),(7827.06,-13540.96)]),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 35),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Aura of the Lich Capture"))
def BuildMistForm(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Mist Form capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.ELEMENTALIST),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.ELEMENTALIST),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=155),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(7565,-45115), target_map_id=26),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-18688,12186)),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 155),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Mist Form Capture"))


def BuildObsidianFlesh(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Obsidian Flesh capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.ELEMENTALIST),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.ELEMENTALIST),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=438),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-14638,2927), target_map_id=437),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-10867,4322)),
        BT.Wait(duration_ms=5000),
        BT.MoveAndInteract(pos=(-10867,4322)),
        BT.Wait(duration_ms=2000),
        BT.VanquishNode(steps=[(-2675.33,6765.78),(-300,2474),(5329.65,5429.12)]),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 438),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Obsidian Flesh Capture"))


def BuildMindBurn(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Mind Burn capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.ELEMENTALIST),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.ELEMENTALIST),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=217),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-11644,-15830), target_map_id=197),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-1976,10596)),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 217),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Mind Burn Capture"))


def BuildGlimmeringMark(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Glimmering Mark capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.ELEMENTALIST),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.ELEMENTALIST),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=158),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-7392,-2618), target_map_id=95),
        ConfigureAggressiveEnv(),
        BT.VanquishNode(steps=[(-3347.47,2503.66),(-5052.62,2948.76)]),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 158),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Glimmering Mark Capture"))

def BuildMindShock(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Mind Shock capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.ELEMENTALIST),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.ELEMENTALIST),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=155),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(6038,-41402), target_map_id=91),
        ConfigureAggressiveEnv(),
        BT.VanquishNode(steps=[(1526.63,-39178.76),(592.26,-43048.45),(-2607.90,-44448.80),(-5678.81,-43418.43)]),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 155),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Mind Shock Capture"))


def BuildThunderclap(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Thunderclap capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.ELEMENTALIST),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.ELEMENTALIST),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=23),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-12507,-23517), target_map_id=94),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(7408,15741)),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 23),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Thunderclap Capture"))


def BuildMasterOfMagic(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Master of Magic capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.ELEMENTALIST),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.ELEMENTALIST),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=393),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-6041,-1493), target_map_id=392),
        ConfigureAggressiveEnv(),
        BT.VanquishNode(steps=[(-6279,-8739),(-7868,-9560)]),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 393),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Master of Magic Capture"))


def BuildInvokeLightning(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Invoke Lightning capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.ELEMENTALIST),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.ELEMENTALIST),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=393),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-6041,-1493), target_map_id=392),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-13509,-17579)),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 393),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Invoke Lightning Capture"))
def BuildShockwave(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Shockwave capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.ELEMENTALIST),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.ELEMENTALIST),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=272),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(6741,8137), target_map_id=244),
        ConfigureAggressiveEnv(),
        BT.VanquishNode(steps=[(1670,-16662),(-261,-16661),(-1637,-15269)]),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 272),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Shockwave Capture"))


def BuildDoubleDragon(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Double Dragon capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.ELEMENTALIST),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.ELEMENTALIST),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=303),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(10814,14589), target_map_id=239),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(4035,10701)),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 303),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Double Dragon Capture"))


def BuildBlindingSurge(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Blinding Surge capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.ELEMENTALIST),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.ELEMENTALIST),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=433),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(5045,1052), target_map_id=404),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-7018,-8461)),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 433),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Blinding Surge Capture"))


def BuildElementalAttunement(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Elemental Attunement capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.ELEMENTALIST),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.ELEMENTALIST),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=477),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-15629,-3751), target_map_id=371),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-4598,-10651)),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 477),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Elemental Attunement Capture"))


def BuildGust(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Gust capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.ELEMENTALIST),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.ELEMENTALIST),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=287),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(27258,5426), target_map_id=209),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(24360,5664)),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 287),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Gust Capture"))

def BuildLightningSurge(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Lightning Surge capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.ELEMENTALIST),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.ELEMENTALIST),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=288),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-16308,13732), target_map_id=199),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-721,7622)),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 288),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Lightning Surge Capture"))


def BuildRideTheLightning(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Ride the Lightning capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.ELEMENTALIST),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.ELEMENTALIST),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=650),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-21602,12394), target_map_id=649),
        ConfigureAggressiveEnv(),
        BT.VanquishNode(steps=[(-9425,9534),(-5124,9715),(3866,3904)]),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 650),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Ride the Lightning Capture"))


def BuildSandstorm(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Sandstorm capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.ELEMENTALIST),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.ELEMENTALIST),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=440),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(2275,-1056), target_map_id=439),
        ConfigureAggressiveEnv(),
        BT.VanquishNode(steps=[(-5235,11047),(-4874,12918)]),
        BT.MoveAndExitMap(pos=(21006,18196), target_map_id=443),
        BT.MoveAndKill(pos=(-24310,2150)),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 440),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Sandstorm Capture"))


def BuildStoneSheath(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Stone Sheath capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.ELEMENTALIST),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.ELEMENTALIST),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=427),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.Move(pos=(-13625.08,-11257.90)),
        BT.MoveAndDialog(pos=(-13641,-10375), dialog_id=0x84),
        BT.WaitForMapLoad(map_id=377),
        ConfigureAggressiveEnv(),
        BT.VanquishNode(steps=[(-7615,-5029),(-2763,-4443),(-3663,-6080),(-3711,-6683),(-3769,-7410),(-1642,-10908),(3416,-8155),(9321,1942),(13134,11247)]),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 427),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Stone Sheath Capture"))

def BuildUnsteadyGround(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Unsteady Ground capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.ELEMENTALIST),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.ELEMENTALIST),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=288),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-16308,13732), target_map_id=199),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-18285,5935)),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 288),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Unsteady Ground Capture"))


def BuildEnergyBoon(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Energy Boon capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.ELEMENTALIST),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.ELEMENTALIST),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=388),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.Move(pos=(-7243.40,-8111.62)),
        BT.MoveAndExitMap(pos=(-8040,-8675), target_map_id=210),
        ConfigureAggressiveEnv(),
        BT.VanquishNode(steps=[(15436,19966),(11474,9869)]),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 388),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Energy Boon Capture"))


def BuildEtherPrism(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Ether Prism capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.ELEMENTALIST),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.ELEMENTALIST),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=442),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(3025,5267), target_map_id=443),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-5210,465)),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 442),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Ether Prism Capture"))


def BuildEtherRenewal(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Ether Renewal capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.ELEMENTALIST),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.ELEMENTALIST),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=117),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.EnterChallenge(target_map_id=117),
        BT.WaitForMapLoad(map_id=117),
        ConfigureAggressiveEnv(),
        BT.VanquishNode(steps=[
            (-857,8546),(-2320,5881),(-125.10,3166.91),(-50.19,103.76),(1417.27,-2503.34),
            (4508.23,-3895.00),(5735.68,-3615.36),(6548.60,-2597.65),(6904.65,-1450.62),
            (8282.06,-1424.29)
        ]),
        BT.MoveAndInteract(pos=(8945,-2457)),
        BT.WaitForMapLoad(map_id=117),
        BT.Wait(duration_ms=1000),
        BT.VanquishNode(steps=[
            (13091,-5283),(10711.53,-4565.11),(8666.88,-6085.35),(9782.77,-9098.71),(6407,-11845)
        ]),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 117),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Ether Renewal Capture"))

def BuildMindBlast(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Mind Blast capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.ELEMENTALIST),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.ELEMENTALIST),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=495),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-16837,-13647), target_map_id=472),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-7832,-18723)),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 495),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Mind Blast Capture"))


def BuildSavannahHeat(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Savannah Heat capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.ELEMENTALIST),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.ELEMENTALIST),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=545),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(2918,-4281), target_map_id=444),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-643,13446)),
        BT.Wait(duration_ms=7000),
        BT.MoveAndInteract(pos=(-579,13354)),
        BT.MoveAndKill(pos=(9436,14585)),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 545),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Savannah Heat Capture"))


def BuildSearingFlames(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Searing Flames capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.ELEMENTALIST),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.ELEMENTALIST),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=478),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(5042,-4839), target_map_id=386),
        ConfigureAggressiveEnv(),
        BT.VanquishNode(steps=[(-7298,15105),(-1703,12884),(-1078,20148)]),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 478),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Searing Flames Capture"))


def BuildStarBurst(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Star Burst capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.ELEMENTALIST),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.ELEMENTALIST),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=226),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-9600,3803), target_map_id=233),
        ConfigureAggressiveEnv(),
        BT.VanquishNode(steps=[(16795,8477),(-973,2190),(-3992.75,-6002.14)]),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 226),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Star Burst Capture"))

def BuildIcyShackles(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Icy Shackles capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.ELEMENTALIST),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.ELEMENTALIST),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=424),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(5109,5319), target_map_id=384),
        ConfigureAggressiveEnv(),
        BT.VanquishNode(steps=[(-11476,-11870),(1573,-12592)]),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 424),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Icy Shackles Capture"))


def BuildMindFreeze(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Mind Freeze capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.ELEMENTALIST),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.ELEMENTALIST),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=469),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(7611,18645), target_map_id=468),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(9441,11297)),
        BT.Wait(duration_ms=30000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 469),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Mind Freeze Capture"))


def BuildMirrorOfIce(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Mirror of Ice capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.ELEMENTALIST),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.ELEMENTALIST),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=284),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.Move(pos=(11750,-18667)),
        BT.MoveAndExitMap(pos=(11745,-21128), target_map_id=256),
        ConfigureAggressiveEnv(),
        BT.VanquishNode(steps=[(6939,10824),(2009.15,5432.86),(3684.09,3832.11),(6207.97,26.18)]),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 284),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Mirror of Ice Capture"))


def BuildShatterstone(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Shatterstone capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.ELEMENTALIST),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.ELEMENTALIST),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=130),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(18072,1905), target_map_id=128),
        ConfigureAggressiveEnv(),
        BT.VanquishNode(steps=[(14466,-24),(20340.17,-5591.57)]),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 130),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Shatterstone Capture"))

def BuildWaterTrident(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Water Trident capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.ELEMENTALIST),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.ELEMENTALIST),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=642),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(1250,800), target_map_id=499),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(5721.17,21335.62)),
        BT.Wait(duration_ms=45000),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 642),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Water Trident Capture"))

def BuildSimpleThievery(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Simple Thievery capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.MESMER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.MESMER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=376),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-13963,18264), target_map_id=375),
        ConfigureAggressiveEnv(),
        BT.VanquishNode(steps=[(-14487,14623), (-16605,1454), (-10991,-11117), (-9148,-9792)]),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 376),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Simple Thievery Capture"))


def BuildPsychicInstability(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Psychic Instability capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.MESMER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.MESMER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=277),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(3200,2499), target_map_id=227),
        ConfigureAggressiveEnv(),
        BT.VanquishNode(steps=[(4599.85,3940.26), (3039.05,5503.06), (3187.73,-956.72), (7629.23,3.76), (7716.02,5614.70), (4753.20,7895.67), (2412.87,8214.28), (-3362.41,5083.70), (-3286.67,1236.43)]),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 277),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Psychic Instability Capture"))


def BuildTease(skill: EliteSkill) -> BehaviorTree:
    nodes = [
        BT.LogMessage(message="Starting Tease capture", module_name=MODULE_NAME, print_to_console=True),
        RecordStartingMap(),
        SaveCurrentBuild(),
        LoadSecondaryBuild(LocalProfession.MESMER),
        BT.Wait(duration_ms=2000),
        BuySignetOfCapture(LocalProfession.MESMER),
        BT.SendChatCommand(command="/leave", log=False),
        BT.Wait(duration_ms=2000),
        BT.Travel(target_map_id=393),
        AdvancedHeroTeam(),
        BT.Wait(duration_ms=3000),
        BT.MoveAndExitMap(pos=(-6041,-1493), target_map_id=392),
        ConfigureAggressiveEnv(),
        BT.MoveAndKill(pos=(-10388,-7828)),
        ConfigurePacifistEnv(),
        UseSignetOfCapture(),
        BT.Wait(duration_ms=5000),
        CaptureSkillWithRetry(skill.skill_id),
        BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 393),
        RestoreSavedBuild(),
    ]
    return BehaviorTree(BehaviorTree.SequenceNode(children=nodes, name="Tease Capture"))

# ============================================================================
# BUILDERS DICTIONARY
# ============================================================================

BUILDERS: Dict[str, Callable[[EliteSkill], BehaviorTree]] = {
    "[H]Energy Surge": BuildEnergySurge,
    "[H]Ineptitude": BuildIneptitude,
    "[H]Migraine": BuildMigraine,
    "[H]Illusionary Weaponry": BuildIllusionaryWeaponry,
    "[H]Panic": BuildPanic,
    "[H]Echo": BuildEcho,
    "[H]Mantra of Recall": BuildMantraOfRecall,
    "[H]Energy Drain": BuildEnergyDrain,
    "[H]Keystone Signet": BuildKeystoneSignet,
    "[H]Mantra of Recovery": BuildMantraOfRecovery,
    "[H]Enchanter's Conundrum": BuildEnchantersConundrum,
    "[H]Hex Eater Vortex": BuildHexEaterVortex,
    "[H]Power Block": BuildPowerBlock,
    "[H]Power Flux": BuildPowerFlux,
    "[H]Psychic Distraction": BuildPsychicDistraction,
    "[H]Arcane Languor": BuildArcaneLanguor,
    "[H]Stolen Speed": BuildStolenSpeed,
    "[H]Symbols of Inspiration": BuildSymbolsOfInspiration,
    "[H]Air of Disenchantment": BuildAirOfDisenchantment,
    "[H]Recurring Insecurity": BuildRecurringInsecurity,
    "[H]Shared Burden": BuildSharedBurden,
    "[H]Signet of Illusions": BuildSignetOfIllusions,
    "[H]Extend Conditions": BuildExtendConditions,
    "[H]Lyssa's Aura": BuildLyssasAura,
    "[H]Expel Hexes": BuildExpelHexes,
    "[H]Pious Renewal": BuildPiousRenewal,
    "[H]Blood is Power": BuildBloodIsPower,
    "[H]Cautery Signet": BuildCauterySignet,
    "[H]Together as One": BuildTogetherAsOne,
    "[H]Heroic Refrain": BuildHeroicRefrain,
    "[H]Soul Taker": BuildSoulTaker,
    "[H]Over The Limit": BuildOverTheLimit,
    "[H]Judgment Strike": BuildJudgmentStrike,
    "[H]Time Ward": BuildTimeWard,
    "[H]Vow of Revolution": BuildVowOfRevolution,
    "[H]Seven Weapon Stance": BuildSevenWeaponStance,
    "[H]Weapons of Three Forges": BuildWeaponsOfThreeForges,
    "[H]Shadow Theft": BuildShadowTheft,
    "[H]Shattering Assault": BuildShatteringAssault,
    "[H]Anthem of Guidance": BuildAnthemOfGuidance,
    "[H]Crippling Anthem": BuildCripplingAnthem,
    "[H]Angelic Bond": BuildAngelicBond,
    "[H]Defensive Anthem": BuildDefensiveAnthem,
    "[H]It's Just a Flesh Wound.": BuildItsJustaFleshWound,
    "[H]The Power Is Yours!": BuildThePowerIsYours,
    "[H]Song of Purification": BuildSongofPurification,
    "[H]Song of Restoration": BuildSongofRestoration,
    "[H]Cruel Spear": BuildCruelSpear,
    "[H]Stunning Strike": BuildStunningStrike,
    "[H]Soldier's Fury": BuildSoldiersFury,
    "[H]Incoming!": BuildIncoming,
    "[H]Focused Anger": BuildFocusedAnger,
    "[H]Anthem of Fury": BuildAnthemofFury,
    "[H]Shadow Form": BuildShadowForm,
    "[H]Shadow Prison": BuildShadowPrison,
    "[H]Shadow Shroud": BuildShadowShroud,
    "[H]Way of the Assassin": BuildWayOfTheAssassin,
    "[H]Dark Apostasy": BuildDarkApostasy,
    "[H]Assassins Promise": BuildAssassinsPromise,
    "[H]Locust's Fury": BuildLocustsFury,
    "[H]Palm Strike": BuildPalmStrike,
    "[H]Seeping Wound": BuildSeepingWound,
    "[H]Flashing Blades": BuildFlashingBlades,
    "[H]Fox's Promise": BuildFoxsPromise,
    "[H]Aura of Displacement": BuildAuraOfDisplacement,
    "[H]Mark of Insecurity": BuildMarkOfInsecurity,
    "[H]Hidden Caltrops": BuildHiddenCaltrops,
    "[H]Assault Enchantments": BuildAssaultEnchantments,
    "[H]Shadow Meld": BuildShadowMeld,
    "[H]Wastrel's Collapse": BuildWastrelsCollapse,
    "[H]Golden Skull Strike": BuildGoldenSkullStrike,
    "[H]Temple Strike": BuildTempleStrike,
    "[H]Moebius Strike": BuildMoebiusStrike,
    "[H]Shroud of Silence": BuildShroudOfSilence,
    "[H]Siphon Strength": BuildSiphonStrength,
    "[H]Way of the Empty Palm": BuildWayOfTheEmptyPalm,
    "[H]Beguiling Haze": BuildBeguilingHaze,
    "[H]Vow of Silence": BuildVowOfSilence,
    "[H]Onslaught": BuildOnslaught,
    "[H]Ebon Dust Aura": BuildEbonDustAura,
    "[H]Avatar of Balthazar": BuildAvatarOfBalthazar,
    "[H]Avatar of Melandru": BuildAvatarOfMelandru,
    "[H]Avatar of Dwayna": BuildAvatarOfDwayna,
    "[H]Avatar of Lyssa": BuildAvatarOfLyssa,
    "[H]Avatar of Grenth": BuildAvatarOfGrenth,
    "[H]Arcane Zeal": BuildArcaneZeal,
    "[H]Grenth's Grasp": BuildGrenthsGrasp,
    "[H]Reaper's Sweep": BuildReapersSweep,
    "[H]Vow of Strength": BuildVowOfStrength,
    "[H]Wounding Strike": BuildWoundingStrike,
    "[H]Zealous Vow": BuildZealousVow,
    "[H]Signet of Spirits": BuildSignetOfSpirits,
    "[H]Attuned Was Songkai": BuildAttunedWasSongkai,
    "[H]Clamor of Souls": BuildClamorOfSouls,
    "[H]Caretaker's Charge": BuildCaretakersCharge,
    "[H]Consume Soul": BuildConsumeSoul,
    "[H]Soul Twisting": BuildSoulTwisting,
    "[H]Xinrae's Weapon": BuildXinraesWeapon,
    "[H]Wielder's Zeal": BuildWieldersZeal,
    "[H]Destructive Was Glaive": BuildDestructiveWasGlaive,
    "[H]Grasping Was Kuurong": BuildGraspingWasKuurong,
    "[H]Offering of Spirit": BuildOfferingOfSpirit,
    "[H]Preservation": BuildPreservation,
    "[H]Reclaim Essence": BuildReclaimEssence,
    "[H]Ritual Lord": BuildRitualLord,
    "[H]Signet of Ghostly Might": BuildSignetOfGhostlyMight,
    "[H]Spirit Channeling": BuildSpiritChanneling,
    "[H]Spirit Light Weapon": BuildSpiritLightWeapon,
    "[H]Spirit's Strength": BuildSpiritsStrength,
    "[H]Tranquil Was Tanasen": BuildTranquilWasTanasen,
    "[H]Vengeful Was Khanhei": BuildVengefulWasKhanhei,
    "[H]Wanderlust": BuildWanderlust,
    "[H]Weapon of Fury": BuildWeaponOfFury,
    "[H]Weapon of Quickening": BuildWeaponOfQuickening,
    "[H]Primal Rage": BuildPrimalRage,
    "[H]Eviscerate": BuildEviscerate,
    "[H]Victory is Mine": BuildVictoryIsMine,
    "[H]Charge!": BuildCharge,
    "[H]Coward!": BuildCoward,
    "[H]You're All Alone!": BuildYoureAllAlone,
    "[H]Auspicious Parry": BuildAuspiciousParry,
    "[H]Backbreaker": BuildBackbreaker,
    "[H]Battle Rage": BuildBattleRage,
    "[H]Bull's Charge": BuildBullsCharge,
    "[H]Charging Strike": BuildChargingStrike,
    "[H]Cleave": BuildCleave,
    "[H]Crippling Slash": BuildCripplingSlash,
    "[H]Decapitate": BuildDecapitate,
    "[H]Defy Pain": BuildDefyPain,
    "[H]Devastating Hammer": BuildDevastatingHammer,
    "[H]Dragon Slash": BuildDragonSlash,
    "[H]Dwarven Battle Stance": BuildDwarvenBattleStance,
    "[H]Enraged Smash": BuildEnragedSmash,
    "[H]Forceful Blow": BuildForcefulBlow,
    "[H]Headbutt": BuildHeadbutt,
    "[H]Hundred Blades": BuildHundredBlades,
    "[H]Magehunter Strike": BuildMagehunterStrike,
    "[H]Magehunter's Smash": BuildMagehuntersSmash,
    "[H]Quivering Blade": BuildQuiveringBlade,
    "[H]Rage of the Ntouka": BuildRageoftheNtouka,
    "[H]Shove": BuildShove,
    "[H]Skull Crack": BuildSkullCrack,
    "[H]Soldier's Stance": BuildSoldiersStance,
    "[H]Steady Stance": BuildSteadyStance,
    "[H]Triple Chop": BuildTripleChop,
    "[H]Warrior's Endurance": BuildWarriorsEndurance,
    "[H]Whirling Axe": BuildWhirlingAxe,
    "[H]Infuriating Heat": BuildInfuriatingHeat,
    "[H]Broadhead Arrow": BuildBroadheadArrow,
    "[H]Greater Conflagration": BuildGreaterConflagration,
    "[H]Poison Arrow": BuildPoisonArrow,
    "[H]Prepared Shot": BuildPreparedShot,
    "[H]Archer's Signet": BuildArchersSignet,
    "[H]Glass Arrows": BuildGlassArrows,
    "[H]Barrage": BuildBarrage,
    "[H]Burning Arrow": BuildBurningArrow,
    "[H]Crippling Shot": BuildCripplingShot,
    "[H]Enraged Lunge": BuildEnragedLunge,
    "[H]Equinox": BuildEquinox,
    "[H]Escape": BuildEscape,
    "[H]Expert's Dexterity": BuildExpertsDexterity,
    "[H]Famine": BuildFamine,
    "[H]Ferocious Strike": BuildFerociousStrike,
    "[H]Heal as One": BuildHealAsOne,
    "[H]Lacerate": BuildLacerate,
    "[H]Magebane Shot": BuildMagebaneShot,   
    "[H]Marksman's Wager": BuildMarksmansWager,
    "[H]Melandru's Arrows": BuildMelandrusArrows,
    "[H]Melandru's Shot": BuildMelandrusShot,
    "[H]Oath Shot": BuildOathShot,
    "[H]Quick Shot": BuildQuickShot,
    "[H]Quicksand": BuildQuicksand,
    "[H]Rampage as One": BuildRampageAsOne,
    "[H]Scavenger's Focus": BuildScavengersFocus,
    "[H]Smoke Trap": BuildSmokeTrap,
    "[H]Spike Trap": BuildSpikeTrap,
    "[H]Strike as One": BuildStrikeAsOne,
    "[H]Trapper's Focus": BuildTrappersFocus,
    "[H]Signet of Judgement": BuildSignetOfJudgement,
    "[H]Unyielding Aura": BuildUnyieldingAura,
    "[H]Spell Breaker": BuildSpellBreaker,
    "[H]Glimmer of Light": BuildGlimmerOfLight,
    "[H]Blessed Light": BuildBlessedLight,
    "[H]Healing Light": BuildHealingLight,
    "[H]Boon Signet": BuildBoonSignet,
    "[H]Healer's Boon": BuildHealersBoon,
    "[H]Peace and Harmony": BuildPeaceandHarmony,
    "[H]Withdraw Hexes": BuildWithdrawHexes,
    "[H]Healing Burst": BuildHealingBurst,
    "[H]Healing Hands": BuildHealingHands,
    "[H]Light of Deliverance": BuildLightofDeliverance,
    "[H]Word of Healing": BuildWordofHealing,
    "[H]Air of Enchantment": BuildAirofEnchantment,
    "[H]Aura of Faith": BuildAuraofFaith,
    "[H]Divert Hexes": BuildDivertHexes,
    "[H]Life Sheath": BuildLifeSheath,
    "[H]Shield of Regeneration": BuildShieldOfRegeneration,
    "[H]Zealous Benediction": BuildZealousBenediction,
    "[H]Defender's Zeal": BuildDefendersZeal,
    "[H]Ray of Judgment": BuildRayofJudgment,
    "[H]Word of Censure": BuildWordOfCensure,
    "[H]Empathic Removal": BuildEmpathicRemoval,
    "[H]Martyr": BuildMartyr,
    "[H]Signet of Removal": BuildSignetOfRemoval,
    "[H]Balthazar's Pendulum": BuildBalthazarsPendulum,
    "[H]Life Barrier": BuildLifeBarrier,
    "[H]Animate Flesh Golem": BuildAnimateFleshGolem,
    "[H]Contagion": BuildContagion,
    "[H]Corrupt Enchantment": BuildCorruptEnchantment,
    "[H]Cultist's Fervor": BuildCultistsFervor,
    "[H]Tainted Flesh": BuildTaintedFlesh,
    "[H]Depravity": BuildDepravity,
    "[H]Discord": BuildDiscord,
    "[H]Icy Veins": BuildIcyVeins,
    "[H]Grenth's Balance": BuildGrenthsBalance,
    "[H]Jagged Bones": BuildJaggedBones,
    "[H]Offering of Blood": BuildOfferingOfBlood,
    "[H]Order of the Vampire": BuildOrderOfTheVampire,
    "[H]Toxic Chill": BuildToxicChill,
    "[H]Wail of Doom": BuildWailOfDoom,
    "[H]Weaken Knees": BuildWeakenKnees,
    "[H]Spoil Victor": BuildSpoilVictor,
    "[H]Life Transfer": BuildLifeTransfer,
    "[H]Spiteful Spirit": BuildSpitefulSpirit,
    "[H]Reaper's Mark": BuildReapersMark,
    "[H]Plague Signet": BuildPlagueSignet,
    "[H]Aura of the Lich": BuildAuraOfTheLich,
    "[H]Mist Form": BuildMistForm,
    "[H]Obsidian Flesh": BuildObsidianFlesh,
    "[H]Mind Burn": BuildMindBurn,
    "[H]Glimmering Mark": BuildGlimmeringMark,
    "[H]Mind Shock": BuildMindShock,
    "[H]Thunderclap": BuildThunderclap,
    "[H]Master of Magic": BuildMasterOfMagic,
    "[H]Invoke Lightning": BuildInvokeLightning,
    "[H]Shockwave": BuildShockwave,
    "[H]Double Dragon": BuildDoubleDragon,
    "[H]Blinding Surge": BuildBlindingSurge,
    "[H]Elemental Attunement": BuildElementalAttunement,
    "[H]Gust": BuildGust,
    "[H]Lightning Surge": BuildLightningSurge,
    "[H]Ride the Lightning": BuildRideTheLightning,
    "[H]Sandstorm": BuildSandstorm,
    "[H]Stone Sheath": BuildStoneSheath,
    "[H]Unsteady Ground": BuildUnsteadyGround,
    "[H]Energy Boon": BuildEnergyBoon,
    "[H]Ether Prism": BuildEtherPrism,
    "[H]Ether Renewal": BuildEtherRenewal,
    "[H]Mind Blast": BuildMindBlast,
    "[H]Savannah Heat": BuildSavannahHeat,
    "[H]Searing Flames": BuildSearingFlames,
    "[H]Star Burst": BuildStarBurst,
    "[H]Icy Shackles": BuildIcyShackles,
    "[H]Mind Freeze": BuildMindFreeze,
    "[H]Mirror of Ice": BuildMirrorOfIce,
    "[H]Shatterstone": BuildShatterstone,
    "[H]Water Trident": BuildWaterTrident,
    "[H]Simple Thievery": BuildSimpleThievery,
    "[H]Psychic Instability": BuildPsychicInstability,
    "[H]Tease": BuildTease,
    "[H]Mark of Protection": BuildMarkOfProtection,

}

def ConfigureAggressiveEnv() -> BehaviorTree:
    """Configure aggressive combat environment."""
    tree = ensure_botting_tree()
    return tree.Config.Aggressive(
        multi_account=False,
        auto_loot=True,
        resurrection_scroll=False,
    )

def ConfigurePacifistEnv() -> BehaviorTree:
    """Configure pacifist combat environment."""
    tree = ensure_botting_tree()
    return tree.Config.Pacifist(
        multi_account=False,
        auto_loot=False,
        resurrection_scroll=False,
    )


def SaveCurrentBuild() -> BehaviorTree.ActionNode:
    """Save the character's original skill template once per session."""
    def _save_action():
        global _saved_build_template, _build_saved_once
        try:
            if _saved_build_template and _build_saved_once:
                ConsoleLog("Capture", "Build already saved, preserving original", log=True)
                return BehaviorTree.NodeState.SUCCESS

            template = Utils.GenerateSkillbarTemplate()
            if not template:
                ConsoleLog("Capture", "GenerateSkillbarTemplate returned no template", log=True)
                return BehaviorTree.NodeState.FAILURE

            _saved_build_template = template
            _build_saved_once = True
            ConsoleLog("Capture", f"Current build saved: {template[:30]}...", log=True)
            return BehaviorTree.NodeState.SUCCESS
        except Exception as e:
            ConsoleLog("Capture", f"Failed to save build: {e}", log=True)
            return BehaviorTree.NodeState.FAILURE

    return BehaviorTree.ActionNode(
        name='Save Current Build',
        action_fn=_save_action,
    )


def RestoreSavedBuild() -> BehaviorTree.ActionNode:
    """Restore the original build after the capture sequence finishes."""
    def _restore_action():
        global _saved_build_template
        try:
            if not _saved_build_template:
                ConsoleLog("Capture", "No saved build to restore", log=True)
                return BehaviorTree.NodeState.SUCCESS

            SkillBar.LoadSkillTemplate(_saved_build_template)
            ConsoleLog("Capture", "Restored original build", log=True)
            return BehaviorTree.NodeState.SUCCESS
        except Exception as e:
            ConsoleLog("Capture", f"Failed to restore build: {e}", log=True)
            return BehaviorTree.NodeState.FAILURE

    return BehaviorTree.ActionNode(
        name='Restore Saved Build',
        action_fn=_restore_action,
    )


def RecordStartingMap() -> BehaviorTree.ActionNode:
    """Record the current map so the bot can return after capture."""
    def _record_action():
        global _starting_map_id
        try:
            current_map = Map.GetMapID()
            _starting_map_id = int(current_map) if current_map is not None else None
            if _starting_map_id is None:
                ConsoleLog("Capture", "No map ID available to record", log=True)
                return BehaviorTree.NodeState.FAILURE
            ConsoleLog("Capture", f"Starting map recorded: {_starting_map_id}", log=True)
            return BehaviorTree.NodeState.SUCCESS
        except Exception as e:
            ConsoleLog("Capture", f"Failed to record map: {e}", log=True)
            return BehaviorTree.NodeState.FAILURE

    return BehaviorTree.ActionNode(
        name='Record Starting Map',
        action_fn=_record_action,
    )


def UseSignetOfCapture() -> BehaviorTree.ActionNode:
    """Use Signet of Capture (skill ID 3) by finding its slot in the skillbar."""
    def _use_action():
        try:
            # Find the slot containing Signet of Capture (skill ID 3)
            signet_slot = None
            for slot in range(1, 9):
                skill_id = SkillBar.GetSkillIDBySlot(slot)
                if skill_id == 3:
                    signet_slot = slot
                    break
            
            if signet_slot is None:
                ConsoleLog("Capture", "Signet of Capture not found in skillbar", log=True)
                return BehaviorTree.NodeState.FAILURE
            
            SkillBar.UseSkill(signet_slot)
            ConsoleLog("Capture", f"Using Signet of Capture from slot {signet_slot}", log=True)
            return BehaviorTree.NodeState.SUCCESS
        except Exception as e:
            ConsoleLog("Capture", f"Failed to use Signet of Capture: {e}", log=True)
            return BehaviorTree.NodeState.FAILURE

    return BehaviorTree.ActionNode(
        name='Use Signet of Capture',
        action_fn=_use_action,
    )

def ClickSkillFrame(skill_id: int) -> BehaviorTree.ActionNode:
    """Click the capture dialog skill frame using the working original approach."""
    def _click_action():
        try:
            # Get attribute offset for the skill
            attribute = GLOBAL_CACHE.Skill.Attribute.GetAttribute(skill_id)
            attribute_offset = attribute if isinstance(attribute, int) else 1
            
            # Get the skill frame using the Frame API
            skill_frame = Frame.capture_skill(attribute_offset, skill_id)
            
            ConsoleLog("Capture", f"Looking for skill frame {skill_id} with attribute offset {attribute_offset}", log=True)
            
            if not skill_frame.exists:
                ConsoleLog("Capture", f"Skill frame {skill_id} not found; signet UI may not be open", log=True)
                return BehaviorTree.NodeState.FAILURE

            ConsoleLog("Capture", f"Found skill frame {skill_id}, clicking it", log=True)
            
            # Use mouse_click_action like the working original
            PyGameThread.enqueue(lambda f=skill_frame: f.mouse_click_action(0, 0))
            time.sleep(0.2)

            # Wait before clicking capture button (like original)
            time.sleep(1.0)
            
            # Try to find and click the capture button
            capture_frame = Frame(FrameId.SkillCaptureDialog.Content)
            
            if capture_frame.exists:
                ConsoleLog("Capture", f"Capture button found, clicking it", log=True)
                capture_frame.click()
                time.sleep(0.2)
                ConsoleLog("Capture", f"Successfully clicked capture button for skill {skill_id}", log=True)
                return BehaviorTree.NodeState.SUCCESS

            ConsoleLog("Capture", "Capture button not found in the dialog", log=True)
            return BehaviorTree.NodeState.FAILURE

        except Exception as e:
            ConsoleLog("Capture", f"Failed to click skill frame: {e}", log=True)
            return BehaviorTree.NodeState.FAILURE

    return BehaviorTree.ActionNode(
        name=f'Click Skill Frame {skill_id}',
        action_fn=_click_action,
    )

def CaptureSkillWithRetry(skill_id: int, max_retries: int = 3) -> BehaviorTree:
    """Capture a skill with retry logic if verification fails."""
    def _build_capture_sequence():
        retry_attempts = []

        # Build each retry attempt as a Sequence
        for i in range(max_retries):
            retry_attempts.append(
                BT.Sequence(
                    name=f'Capture Attempt {i+1}',
                    children=[
                        ClickSkillFrame(skill_id),
                        BT.Wait(duration_ms=5000),
                        VerifySkillCaptured(skill_id),
                    ]
                )
            )
        
        # Final fallback that always fails
        retry_attempts.append(BT.Failer(name='All Retries Exhausted'))
        
        return BehaviorTree(
            BehaviorTree.SelectorNode(
                name=f'Capture Skill {skill_id} With Retry',
                children=retry_attempts
            )
        )
    
    return _build_capture_sequence()

def VerifySkillCaptured(skill_id: int) -> BehaviorTree.ActionNode:
    """Verify that the skill was successfully captured by checking both skillbar and unlocked skills."""
    def _verify_action():
        try:
            # First check if skill is on the skillbar (immediate capture)
            skill_on_bar = False
            for slot in range(1, 9):
                bar_skill_id = SkillBar.GetSkillIDBySlot(slot)
                if bar_skill_id == skill_id:
                    skill_on_bar = True
                    ConsoleLog("Capture", f"Skill {skill_id} found on skillbar slot {slot}", log=True)
                    break

            # Also check if skill is unlocked (persistent)
            skill_unlocked = is_skill_unlocked(skill_id)

            if skill_on_bar or skill_unlocked:
                ConsoleLog("Capture", f"Skill {skill_id} ({GLOBAL_CACHE.Skill.GetName(skill_id)}) successfully captured!", log=True)
                return BehaviorTree.NodeState.SUCCESS

            ConsoleLog("Capture", f"Skill {skill_id} ({GLOBAL_CACHE.Skill.GetName(skill_id)}) not yet captured, will retry", log=True)
            return BehaviorTree.NodeState.FAILURE

        except Exception as e:
            ConsoleLog("Capture", f"Failed to verify skill capture: {e}", log=True)
            return BehaviorTree.NodeState.FAILURE

    return BehaviorTree.ActionNode(
        name=f'Verify Skill {skill_id} Captured',
        action_fn=_verify_action,
    )


def ClickSkillFrameOLD(skill_id: int) -> BehaviorTree.ActionNode:
    """Click the capture dialog skill frame using the working original approach."""
    def _click_action():
        try:
            # Get attribute offset for the skill
            attribute = GLOBAL_CACHE.Skill.Attribute.GetAttribute(skill_id)
            attribute_offset = attribute if isinstance(attribute, int) else 1
            
            # Get the skill frame using the Frame API
            skill_frame = Frame.capture_skill(attribute_offset, skill_id)
            
            ConsoleLog("Capture", f"Looking for skill frame {skill_id} with attribute offset {attribute_offset}", log=True)
            
            if not skill_frame.exists:
                ConsoleLog("Capture", f"Skill frame {skill_id} not found; signet UI may not be open", log=True)
                return BehaviorTree.NodeState.FAILURE

            ConsoleLog("Capture", f"Found skill frame {skill_id}, clicking it", log=True)
            
            # Use mouse_click_action like the working original
            PyGameThread.enqueue(lambda f=skill_frame: f.mouse_click_action(0, 0))
            time.sleep(0.2)
            
            # Wait before clicking capture button (like original)
            time.sleep(1.0)
            
            # Try to find and click the capture button
            capture_frame = Frame(FrameId.SkillCaptureDialog.Content)
            
            if capture_frame.exists:
                ConsoleLog("Capture", f"Capture button found, clicking it", log=True)
                # Direct click without enqueue (like the working original)
                capture_frame.click()
                time.sleep(0.2)
                ConsoleLog("Capture", f"Successfully clicked capture button for skill {skill_id}", log=True)
                return BehaviorTree.NodeState.SUCCESS

            ConsoleLog("Capture", "Capture button not found in the dialog", log=True)
            return BehaviorTree.NodeState.FAILURE
        except Exception as e:
            ConsoleLog("Capture", f"Failed to click skill frame: {e}", log=True)
            return BehaviorTree.NodeState.FAILURE

    return BehaviorTree.ActionNode(
        name=f'Click Skill Frame {skill_id}',
        action_fn=_click_action,
    )




def CaptureSkillWithRetryOLD(skill_id: int, max_retries: int = 3) -> BehaviorTree:
    """Capture a skill with retry logic if verification fails."""
    def _build_capture_sequence():
        # Use Selector to stop on first success
        retry_attempts = []
        for i in range(max_retries):
            retry_attempts.append(
                BT.Sequence(
                    name=f'Capture Attempt {i+1}',
                    children=[
                        ClickSkillFrame(skill_id),
                        BT.Wait(duration_ms=5000),
                        VerifySkillCaptured(skill_id),
                    ]
                )
            )
        
        # Add a final fallback that always fails if all retries exhausted
        retry_attempts.append(BT.Failer(name='All Retries Exhausted'))
        
        return BehaviorTree(
            BehaviorTree.SelectorNode(
                name=f'Capture Skill {skill_id} With Retry',
                children=retry_attempts
            )
        )
    
    return _build_capture_sequence()

def VerifySkillCapturedOLD(skill_id: int) -> BehaviorTree.ActionNode:
    """Verify that the skill was successfully captured by checking both skillbar and unlocked skills."""
    def _verify_action():
        try:
            # First check if skill is on the skillbar (immediate capture)
            skill_on_bar = False
            for slot in range(1, 9):
                bar_skill_id = SkillBar.GetSkillIDBySlot(slot)
                if bar_skill_id == skill_id:
                    skill_on_bar = True
                    ConsoleLog("Capture", f"Skill {skill_id} found on skillbar slot {slot}", log=True)
                    break

            # Also check if skill is unlocked (persistent)
            skill_unlocked = is_skill_unlocked(skill_id)

            if skill_on_bar or skill_unlocked:
                ConsoleLog("Capture", f"Skill {skill_id} ({GLOBAL_CACHE.Skill.GetName(skill_id)}) successfully captured!", log=True)
                return BehaviorTree.NodeState.SUCCESS
            else:
                ConsoleLog("Capture", f"Skill {skill_id} ({GLOBAL_CACHE.Skill.GetName(skill_id)}) not yet captured, will retry", log=True)
                return BehaviorTree.NodeState.FAILURE
        except Exception as e:
            ConsoleLog("Capture", f"Failed to verify skill capture: {e}", log=True)
            return BehaviorTree.NodeState.FAILURE

    return BehaviorTree.ActionNode(
        name=f'Verify Skill {skill_id} Captured',
        action_fn=_verify_action,
    )

SECONDARY_CAPTURE_BUILDS: Dict[LocalProfession, Dict[LocalProfession, str]] = {
    LocalProfession.WARRIOR: {
        LocalProfession.WARRIOR: "OQcSE5OTOMMMHMwODAFFxgi1",
        LocalProfession.RANGER: "OQITEZJnDSpgqAqA2ZAooIGUsGA",
        LocalProfession.MONK: "OQMT4iILZSpgqAqA2ZAooIGUsGA",
        LocalProfession.NECROMANCER: "OQQTQiILZSpgqAqA2ZAooIGUsGA",
        LocalProfession.MESMER: "OQUTEiILZSpgqAqA2ZAooIGUsGA",
        LocalProfession.ELEMENTALIST: "OQYTsiILZSpgqAqA2ZAooIGUsGA",
        LocalProfession.ASSASSIN: "OQcSE5OTOMMMHMwODAFFxgi1",
        LocalProfession.RITUALIST: "OQgjExSsYQKFUFQFwODAFFxgi1A",
        LocalProfession.PARAGON: "OQkjExScZQKFUFQFwODAFFxgi1A",
        LocalProfession.DERVISH: "OQojExScaQKFUFQFwODAFFxgi1A",
    },
    LocalProfession.RANGER: {
        LocalProfession.WARRIOR: "OgEUUDLe1MTKGj1ghMGoSUNDA0GA",
        LocalProfession.RANGER: "OgEUUDLe1MTKGj1ghMGoSUNDA0GA",
        LocalProfession.MONK: "OgMU8CLe1MTKGj1ghMGoSUNDA0GA",
        LocalProfession.NECROMANCER: "OgQUcCLe1MTKGj1ghMGoSUNDA0GA",
        LocalProfession.MESMER: "OgUUMCLe1MTKGj1ghMGoSUNDA0GA",
        LocalProfession.ELEMENTALIST: "OgYUsCLe1MTKGj1ghMGoSUNDA0GA",
        LocalProfession.ASSASSIN: "OgcUYxrm5fQKGj1ghMGoSUNDA0GA",
        LocalProfession.RITUALIST: "OggkYhXaGDGkixYNYIjBqEVzAAtB",
        LocalProfession.PARAGON: "OgkkYhXaGXGkixYNYIjBqEVzAAtB",
        LocalProfession.DERVISH: "OgokYhXaGnGkixYNYIjBqEVzAAtB",
    },
    LocalProfession.MESMER: {
        LocalProfession.WARRIOR: "OQFUAWBPsaQoAaAXADBEB9A2gDAA",
        LocalProfession.RANGER: "OQJUAWBPMcQoAaAXADBEB9A2gDAA",
        LocalProfession.MONK: "OQNEArwj1BhCoBcBMEQE0DYDOAA",
        LocalProfession.NECROMANCER: "OQREArwjdBhCoBcBMEQE0DYDOAA",
        LocalProfession.MESMER: "OQREArwjdBhCoBcBMEQE0DYDOAA",
        LocalProfession.ELEMENTALIST: "OQZEArwjhBhCoBcBMEQE0DYDOAA",
        LocalProfession.ASSASSIN: "OQdUAWBPseQoAaAXADBEB9A2gDAA",
        LocalProfession.RITUALIST: "OQhkAsC8gJGEKgGwFwQARQPgN4AA",
        LocalProfession.PARAGON: "OQlkAsC8gVGEKgGwFwQARQPgN4AA",
        LocalProfession.DERVISH: "OQBDArwjRoAaAXADBEB9A2gDAA",
    },
    LocalProfession.MONK: {
        LocalProfession.WARRIOR: "OwEU04nA5aQNgbE3N3ETfQgdRDAA",
        LocalProfession.RANGER: "OwIU04nA5cQNgbE3N3ETfQgdRDAA",
        LocalProfession.MONK: "OwQUciG/EITNgbE3N3ETfQgdRDAA",
        LocalProfession.NECROMANCER: "OwQUciG/EITNgbE3N3ETfQgdRDAA",
        LocalProfession.MESMER: "OwUUMiG/EITNgbE3N3ETfQgdRDAA",
        LocalProfession.ELEMENTALIST: "OwYUsiG/EITNgbE3N3ETfQgdRDAA",
        LocalProfession.ASSASSIN: "OwcU04nA5fQNgbE3N3ETfQgdRDAA",
        LocalProfession.RITUALIST: "Owgk0wPCEDGUD4GxdzNx0HEYX0AA",
        LocalProfession.PARAGON: "Owkk0wPCEXGUD4GxdzNx0HEYX0AA",
        LocalProfession.DERVISH: "Owok0wPCEnGUD4GxdzNx0HEYX0AA",
    },
    LocalProfession.NECROMANCER: {
        LocalProfession.WARRIOR: "OAFTUYDLDqm5GUB8LYAImsqaLEA",
        LocalProfession.RANGER: "OAJTUYDjDqm5GUB8LYAImsqaLEA",
        LocalProfession.MONK: "OANDUsxfQ1M3gKgfBDAxkVVbhA",
        LocalProfession.NECROMANCER: "OANDUsxfQ1M3gKgfBDAxkVVbhA",
        LocalProfession.MESMER: "OAVDIRxGT1M3gKgfBDAxkVVbhA",
        LocalProfession.ELEMENTALIST: "OABCUsxUNzNoC4XwAQMZV1W",
        LocalProfession.ASSASSIN: "OAdTUYD/Dqm5GUB8LYAImsqaLEA",
        LocalProfession.RITUALIST: "OAhjUwGMYQ1M3gKgfBDAxkVVbhA",
        LocalProfession.PARAGON: "OAljUwGcZQ1M3gKgfBDAxkVVbhA",
        LocalProfession.DERVISH: "OApjUwGcaQ1M3gKgfBDAxkVVbhA",
    },
    LocalProfession.ELEMENTALIST: {
        LocalProfession.WARRIOR: "OgFToYGXHaX0msYQYgWAZIAYAAA",
        LocalProfession.RANGER: "OgJToYGjHaX0msYQYgWAZw3YAAA",
        LocalProfession.MONK: "OgNDoMz9Q7i2kFDCD0CIDZEDAA",
        LocalProfession.NECROMANCER: "OgRDcjyMT7i2kFDCD0CIDHCDAA",
        LocalProfession.MESMER: "OgVDIjyMT7i2kFDCD0CIDXADAA",
        LocalProfession.ELEMENTALIST: "OgVDIjyMT7i2kFDCD0CIDXADAA",
        LocalProfession.ASSASSIN: "OgdToYG/HaX0msYQYgWAZwlZAAA",
        LocalProfession.RITUALIST: "OghjowMM4Q7i2kFDCD0CIDfTDAA",
        LocalProfession.PARAGON: "OgljowM85Q7i2kFDCD0CIDxYDAA",
        LocalProfession.DERVISH: "OgpjowM86Q7i2kFDCD0CIDiXDAA",
    },
    LocalProfession.ASSASSIN: {
        LocalProfession.WARRIOR: "OwFTUnO/Zyhhh5g5AaX0mMAYAAA",
        LocalProfession.RANGER: "OwJTgnO/Zyhhh5g5AaX0m03YAAA",
        LocalProfession.MONK: "OwNT8mO/Zyhhh5g5AaX0m8uaAAA",
        LocalProfession.NECROMANCER: "OwRTcmO/Zyhhh5g5AaX0m8QYAAA",
        LocalProfession.MESMER: "OwVTImO/Zyhhh5g5AaX0m8CYAAA",
        LocalProfession.ELEMENTALIST: "OwZTomO/Zyhhh5g5AaX0msYYAAA",
        LocalProfession.ASSASSIN: "OwBT0Z/8Zyhhh5g5AaX0mkAaAAA",
        LocalProfession.RITUALIST: "Owhj0xfM4QOMMMHMHQ7i2kfTDAA",
        LocalProfession.PARAGON: "Owlj0xf85QOMMMHMHQ7i2kxYDAA",
        LocalProfession.DERVISH: "Owpj0xf86QOMMMHMHQ7i2kiXDAA",
    },
    LocalProfession.RITUALIST: {
        LocalProfession.WARRIOR: "OAGkUFgsITKT18a+NLnnNm5mbAA",
        LocalProfession.RANGER: "OAKkgFgsITKT18a+NLnnNm5mbAA",
        LocalProfession.MONK: "OAOk8EgsITKT18a+NLnnNm5mbAA",
        LocalProfession.NECROMANCER: "OASkcEgsITKT18a+NLnnNm5mbAA",
        LocalProfession.MESMER: "OAWkIEgsITKT18a+NLnnNm5mbAA",
        LocalProfession.ELEMENTALIST: "OAakoEgsITKT18a+NLnnNm5mbAA",
        LocalProfession.ASSASSIN: "OAek8FgsITKT18a+NLnnNm5mbAA",
        LocalProfession.RITUALIST: "OACjAyiM5MVzr53sce2YmbuBAA",
        LocalProfession.PARAGON: "OAmkAyiMpUGT18a+NLnnNm5mbAA",
        LocalProfession.DERVISH: "OAqkAyiMpoGT18a+NLnnNm5mbAA",
    },
    LocalProfession.PARAGON: {
        LocalProfession.WARRIOR: "OQGkUdlqpimUN2VR62CGXBQo72AA",
        LocalProfession.RANGER: "OQKkkFlrpiqUNGAQ62CGAAQo72AA",
        LocalProfession.MONK: "OQOk8ElrpiqUNGAQ62CGAAQo72AA",
        LocalProfession.NECROMANCER: "OQSkcElrpiqUNGAQ62CGAAQo72AA",
        LocalProfession.MESMER: "OQWkMElrpiqUNGAQ62CGAAQo72AA",
        LocalProfession.ELEMENTALIST: "OQaksElrpiqUNGAQ62CGAAQo72AA",
        LocalProfession.ASSASSIN: "OQek8FlrpiqUNGAQ62CGAAQo72AA",
        LocalProfession.RITUALIST: "OQikAGlrpiqUNGAQ62CGAAQo72AA",
        LocalProfession.PARAGON: "OQGkUdlqpimUN2VR62CGXBQo72AA",
        LocalProfession.DERVISH: "OQqkUumKqmGUNGAQ62CGAAQo72AA",
    },
    LocalProfession.DERVISH: {
        LocalProfession.WARRIOR: "OgGkUFp5Kzmk513m4VMJB2+F71AA",
        LocalProfession.RANGER: "OgKkgFp5Kzmk513m4VMJB2+F71AA",
        LocalProfession.MONK: "OgOk0Ep5Kzmk513m4VMJB2+F71AA",
        LocalProfession.NECROMANCER: "OgSkcEp5Kzmk513m4VMJB2+F71AA",
        LocalProfession.MESMER: "OgWkIEp5Kzmk513m4VMJB2+F71AA",
        LocalProfession.ELEMENTALIST: "OgakkEp5Kzmk513m4VMJB2+F71AA",
        LocalProfession.ASSASSIN: "Ogek8Fp5Kzmk513m4VMJB2+F71AA",
        LocalProfession.RITUALIST: "OgikIGp5Kzmk513m4VMJB2+F71AA",
        LocalProfession.PARAGON: "OgmkUGp5Kzmk513m4VMJB2+F71AA",
        LocalProfession.DERVISH: "OgCjkmrMbSmXfbiXxkEY7XsXDAA",
    },
}


def _resolve_active_profession() -> LocalProfession:
    """Resolve the current profession from the live character state."""
    try:
        primary_name, _ = Agent.GetProfessionNames(Player.GetAgentID())
    except Exception:
        return LocalProfession.MESMER

    name_map = {
        "Warrior": LocalProfession.WARRIOR,
        "Ranger": LocalProfession.RANGER,
        "Monk": LocalProfession.MONK,
        "Necromancer": LocalProfession.NECROMANCER,
        "Mesmer": LocalProfession.MESMER,
        "Elementalist": LocalProfession.ELEMENTALIST,
        "Assassin": LocalProfession.ASSASSIN,
        "Ritualist": LocalProfession.RITUALIST,
        "Paragon": LocalProfession.PARAGON,
        "Dervish": LocalProfession.DERVISH,
    }
    return name_map.get(primary_name, LocalProfession.MESMER)


def _load_capture_template_for_profession(profession: LocalProfession) -> bool:
    """Load the saved old-build template for the target secondary profession."""
    current_primary = _resolve_active_profession()
    primary_builds = SECONDARY_CAPTURE_BUILDS.get(current_primary)
    if primary_builds is None:
        ConsoleLog("Capture", f"No capture templates found for primary profession {current_primary.value}", log=True)
        return False

    template = primary_builds.get(profession, primary_builds.get(current_primary))
    if not template:
        ConsoleLog("Capture", f"No capture template found for {current_primary.value}/{profession.value}", log=True)
        return False

    SkillBar.LoadSkillTemplate(template)
    ConsoleLog("Capture", f"Loaded capture skillbar for {current_primary.value}/{profession.value}", log=True)
    return True


def HasSignetOfCapture() -> bool:
    """Check if Signet of Capture is in the current skill bar."""
    try:
        for slot in range(1, 9):
            skill_data = GLOBAL_CACHE.SkillBar.GetSkillData(slot)
            if skill_data and getattr(skill_data, "id", None) == 3:
                return True
        return False
    except Exception:
        return False

def BuySignetOfCaptureNode() -> BehaviorTree.ActionNode:
    """BT ActionNode that buys Signet of Capture using Player.BuySkill(3)."""
    def _buy():
        try:
            Player.BuySkill(3)
            ConsoleLog("Signet", "Purchased Signet of Capture (skill ID 3)", log=True)
            return BehaviorTree.NodeState.SUCCESS
        except Exception as e:
            ConsoleLog("Signet", f"Failed to purchase Signet of Capture: {e}", log=True)
            return BehaviorTree.NodeState.FAILURE

    return BehaviorTree.ActionNode(
        name="Buy Signet of Capture",
        action_fn=_buy
    )


def BuySignetOfCapture(profession: LocalProfession) -> BehaviorTree:
    """Travel to Eye of the North and buy Signet of Capture if not equipped."""

    def _has_signet() -> bool:
        try:
            return HasSignetOfCapture()
        except Exception as e:
            ConsoleLog("Capture", f"Error checking for Signet of Capture: {e}", log=True)
            return False

    skip_purchase = BT.Sequence(
        name="Skip Purchase",
        children=[
            BehaviorTree.ConditionNode(
                name="Has Signet of Capture",
                condition_fn=_has_signet
            ),
            BT.LogMessage(
                message="Signet of Capture already equipped - skipping purchase",
                module_name=MODULE_NAME,
                print_to_console=True
            )
        ]
    )

    purchase_sequence = BT.Sequence(
        name="Buy Signet of Capture",
        children=[
            BT.LogMessage(
                message="Traveling to Eye of the North to buy Signet of Capture...",
                module_name=MODULE_NAME,
                print_to_console=True
            ),

            # Travel to Eye of the North
            BT.EqualizeGold(target_gold=1000, deposit_all=True),
            BT.LeaveParty(),
            BT.Wait(duration_ms=500),
            BT.Travel(target_map_id=642),
            BT.Wait(duration_ms=2000),

            # Move to skill trainer NPC
            BT.MoveAndDialog(pos=(-3551.00, 2341.00), dialog_id=0x84),
            BT.Wait(duration_ms=500),

            # TEST: Buy without clicking the UI button
            BuySignetOfCaptureNode(),
            BT.Wait(duration_ms=500),

            BT.LeaveParty(),
            BT.Wait(duration_ms=500),

            # Return to starting map
            BT.Travel(target_map_id=_starting_map_id if _starting_map_id else 642),
            BT.Wait(duration_ms=2000),

            BT.LogMessage(
                message="Returned to starting map, reloading build to equip signet",
                module_name=MODULE_NAME,
                print_to_console=True
            ),

            LoadSecondaryBuild(profession),
            BT.Wait(duration_ms=2000),

            BT.LogMessage(
                message="Signet purchase sequence complete",
                module_name=MODULE_NAME,
                print_to_console=True
            ),
        ]
    )

    root = BehaviorTree.SelectorNode(
        name="Buy Signet of Capture Selector",
        children=[
            skip_purchase,
            purchase_sequence
        ]
    )

    return BehaviorTree(root)



def LoadSecondaryBuild(profession: LocalProfession) -> BehaviorTree.ActionNode:
    """Load the matching old-build skillbar for the requested profession."""
    def _load_action():
        try:
            if _load_capture_template_for_profession(profession):
                return BehaviorTree.NodeState.SUCCESS
            ConsoleLog("Capture", f"Failed to load capture build for {profession.value}", log=True)
            return BehaviorTree.NodeState.FAILURE
        except Exception as e:
            ConsoleLog("Capture", f"Failed to load build: {e}", log=True)
            return BehaviorTree.NodeState.FAILURE

    return BehaviorTree.ActionNode(
        name=f'Load {profession.value} Build',
        action_fn=_load_action,
    )


def SetupHeroTeam(hero_list: List[HeroType], skill_template_map: Dict[HeroType, str], behavior: int = 1) -> BehaviorTree:
    """Setup hero team with specific heroes and skill templates."""
    children = [BT.LeaveParty()]
    
    hero_ids = [int(hero.value) for hero in hero_list]
    children.append(BT.CreateParty(hero_ids=hero_ids, log=False))
    children.append(BT.Wait(duration_ms=1000))
    
    for position, hero in enumerate(hero_list, start=1):
        if hero in skill_template_map and skill_template_map[hero]:
            children.append(BT.LoadHeroSkillbar(hero_index=position, template=skill_template_map[hero], log=False))
    
    children.append(CoreBT.Party.ForceHeroState(behavior))
    
    return BT.Sequence(name='Setup Hero Team', children=children)


def AdvancedHeroTeam() -> BehaviorTree:
    """Setup Dunkoro-based hero team for Pious Renewal capture."""
    party_size = Map.GetMaxPartySize()

    skill_template_map = {
        HeroType.Gwen: "OQBDAqwDSnATP5AmOaAZAEBHgA",
        HeroType.Vekk: "OgVDI8gsO5gTw0z0hTFAZgiA",
        HeroType.ZhedShadowhoof: "OgVDI8gsO5gTw0z0hTFAZgiA",
        HeroType.AcolyteSousuke: "OgVDI8gsO5gTw0z0hTFAZgiA",
        HeroType.MasterOfWhispers: "OABDUshnSyBVBoBKgbhVVfCWCA",
        HeroType.Olias: "OAhjQoGYIP3hhWVVaO5EeDTqNA",
        HeroType.Dunkoro: "OwUUMsG/E4SNgbE3N3ETfQgZAMEA",
        HeroType.Ogden: "OwUUMsG/E4SNgbE3N3ETfQgZAMEA",
        HeroType.Livia: "OANDY7ZPPEEt4K5uWPCIVV7A",
    }

    hero_list = []

    if party_size <= 4:
        hero_list.extend([HeroType.Dunkoro, HeroType.Vekk, HeroType.Ogden])
    else:
        hero_list.extend([HeroType.Gwen, HeroType.Vekk, HeroType.AcolyteSousuke, HeroType.MasterOfWhispers, HeroType.Olias, HeroType.Dunkoro, HeroType.Ogden, HeroType.Livia])

    return SetupHeroTeam(hero_list, skill_template_map, behavior=1)


# ============================================================================
# NOTE: Generic builders removed - using individual BUILDERS pattern instead
# ============================================================================

# ============================================================================
# GUI STATE
# ============================================================================

class GUIState:
    """Simple GUI state management"""
    def __init__(self):
        self.selected_skill: Optional[EliteSkill] = None
        self.capture_running = False
        self.skill_chain: List[EliteSkill] = []
        self.chain_running = False
        self.current_profession = LocalProfession.MESMER

gui_state = GUIState()

# ============================================================================
# GUI DRAW FUNCTIONS
# ============================================================================

def draw_skills_tab() -> None:
    """Draw the skills selection tab"""
    global gui_state
    
    PyImGui.text("Elite Skills")
    PyImGui.separator()
    
    # Profession filter
    if PyImGui.begin_combo("Profession", gui_state.current_profession.value):
        for prof in LocalProfession:
            if PyImGui.selectable(prof.value, prof == gui_state.current_profession):
                gui_state.current_profession = prof
        PyImGui.end_combo()
    
    PyImGui.separator()

    # Skills list with scrollbar
    if PyImGui.begin_child("SkillsList", (0, 400), True):
        for skill in ELITE_SKILLS:
            if skill.profession != gui_state.current_profession:
                continue

            is_unlocked = is_skill_unlocked(skill.skill_id)
            should_skip, skip_reason = should_skip_skill(skill.skill_id)

            # Skill button
            if is_unlocked:
                PyImGui.push_style_color(PyImGui.ImGuiCol.Button, (0.2, 0.8, 0.2, 1.0))
                PyImGui.push_style_color(PyImGui.ImGuiCol.ButtonHovered, (0.3, 0.9, 0.3, 1.0))
            elif should_skip:
                PyImGui.push_style_color(PyImGui.ImGuiCol.Button, (0.8, 0.2, 0.2, 1.0))
                PyImGui.push_style_color(PyImGui.ImGuiCol.ButtonHovered, (0.9, 0.3, 0.3, 1.0))
            else:
                PyImGui.push_style_color(PyImGui.ImGuiCol.Button, (0.2, 0.6, 0.8, 1.0))
                PyImGui.push_style_color(PyImGui.ImGuiCol.ButtonHovered, (0.3, 0.7, 0.9, 1.0))

            # Disable button if already captured or map locked
            if is_unlocked or should_skip:
                PyImGui.begin_disabled(True)

            if PyImGui.button(f"{skill.display_name}##{skill.id}", 200, 30):
                if skill.step_name in BUILDERS:
                    gui_state.selected_skill = skill
                    start_capture_for_skill(skill)

            if is_unlocked or should_skip:
                PyImGui.end_disabled()

            PyImGui.pop_style_color(2)

            # Status text
            PyImGui.same_line(0, 10)
            if is_unlocked:
                PyImGui.text_colored("✓ Captured", (0.2, 0.8, 0.2, 1.0))
            elif should_skip:
                PyImGui.text_colored("✗ Locked", (0.8, 0.2, 0.2, 1.0))
                # Show tooltip with reason
                if PyImGui.is_item_hovered():
                    if PyImGui.begin_tooltip():
                        PyImGui.text(skip_reason)
                        PyImGui.end_tooltip()
            else:
                PyImGui.text_colored("○ Available", (0.2, 0.6, 0.8, 1.0))

    PyImGui.end_child()

def draw_main_tab() -> None:
    """Draw the main status tab"""
    global gui_state
    
    PyImGui.text("Elite Skills Capture BT")
    PyImGui.separator()
    
    PyImGui.text("Status:")
    if gui_state.capture_running:
        PyImGui.text_colored("Capturing...", (0.2, 0.8, 0.2, 1.0))
        if gui_state.selected_skill:
            PyImGui.text(f"Skill: {gui_state.selected_skill.display_name}")
    else:
        PyImGui.text("Ready")
    
    PyImGui.separator()
    
    # Progress
    captured_count = sum(1 for s in ELITE_SKILLS if is_skill_unlocked(s.skill_id))
    PyImGui.text(f"Progress: {captured_count}/{len(ELITE_SKILLS)} skills captured")

def start_capture_for_skill(skill: EliteSkill) -> None:
    """Start capture for a single skill using BUILDERS pattern."""
    global gui_state
    ConsoleLog("Capture", f"=== START CAPTURE CALLED for {skill.display_name} ===", log=True)
    tree = ensure_botting_tree()
    ConsoleLog("Capture", f"BottingTree instance: {tree}", log=True)
    
    builder = BUILDERS.get(skill.step_name)
    if builder is None:
        ConsoleLog("Capture", f"No builder found for {skill.step_name}", log=True)
        return

    # Check map access before starting capture
    if not can_access_skill_map(skill):
        ConsoleLog("Capture", f"Cannot capture {skill.display_name}: map {skill.start_map} ({Map.GetMapName(skill.start_map)}) is not unlocked", log=True)
        gui_state.capture_running = False
        gui_state.selected_skill = None
        return

    ConsoleLog("Capture", f"Building BT for {skill.display_name}", log=True)
    
    gui_state.capture_running = True
    gui_state.selected_skill = skill
    
    ConsoleLog("Capture", f"Starting capture for {skill.display_name}", log=True)
    
    # Set the planner steps and start the tree (matching PVE Skills Unlocker pattern)
    try:
        tree.SetNamedPlannerSteps([(skill.display_name, lambda skill=skill: builder(skill))], name=ROUTINE_NAME, repeat=False)
        ConsoleLog("Capture", "Planner steps set successfully", log=True)
    except Exception as e:
        ConsoleLog("Capture", f"Error setting planner steps: {e}", log=True)
        import traceback
        ConsoleLog("Capture", traceback.format_exc(), log=True)
        return
    
    try:
        if tree.GetNamedPlannerStepNames():
            tree.Start()
            ConsoleLog("Capture", "Tree started successfully", log=True)
        else:
            ConsoleLog("Capture", "No planner steps to execute", log=True)
    except Exception as e:
        ConsoleLog("Capture", f"Error starting tree: {e}", log=True)
        import traceback
        ConsoleLog("Capture", traceback.format_exc(), log=True)
        return
    
    ConsoleLog("Capture", "Bot started - BT sequence queued", log=True)

def stop_capture() -> None:
    """Stop current capture operation"""
    global gui_state
    tree = ensure_botting_tree()
    tree.Stop()
    gui_state.capture_running = False
    gui_state.selected_skill = None
    ConsoleLog("Capture", "Capture stopped", log=True)


def InitializeBot() -> BehaviorTree:
    """Initialize the bot with the standard aggressive runtime template."""
    tree = ensure_botting_tree()
    return BehaviorTree(
        BehaviorTree.SequenceNode(
            name='Initialize Bot',
            children=[
                tree.Config.Aggressive(
                    multi_account=False,
                    auto_loot=True,
                    resurrection_scroll=False,
                ),
            ],
        )
    )


def get_execution_steps() -> List[Tuple[str, Callable[[], BehaviorTree]]]:
    """Return the default startup sequence for the botting tree."""
    return [
        ('Initialize Bot', InitializeBot),
    ]


def ConfigureRuntimeUpkeep(tree: BottingTree) -> BottingTree:
    """Configure runtime upkeep settings for the BottingTree."""
    return tree.Config.ConfigureUpkeep(
        looting_enabled=False,
        restore_isolation_on_stop=True,
        enable_party_wipe_recovery=True,
        heroai_state_logging=False,
        consumable_upkeeps=[],
    )

_botting_tree: Optional[BottingTree] = None

def ensure_botting_tree() -> BottingTree:
    """Get or create the BottingTree instance using Create pattern."""
    global _botting_tree
    if _botting_tree is None:
        _botting_tree = BottingTree.Create(
            MODULE_NAME,
            routine_name=ROUTINE_NAME,
            repeat=False,
            reset=False,
            pause_on_combat=True,
            multi_account=False,
            auto_loot=False,
            configure_fn=ConfigureRuntimeUpkeep,
        )
    return _botting_tree

def main() -> None:
    """Main entry point for the Elite Skills Capture BT bot."""
    tree = ensure_botting_tree()
    
    # Tick the tree to execute any running BT
    tree.tick()
    
    # Set up extra tabs for the GUI
    extra_tabs = [
        ("Skills", draw_skills_tab),
        ("Status", draw_main_tab),
    ]
    
    # Draw the BottingTree window with our custom tabs
    tree.UI.draw_window(extra_tabs=extra_tabs)

if __name__ == "__main__":
    main()

# ============================================================================
# ELITE SKILLS LIST
# ============================================================================

ELITE_SKILLS = [
EliteSkill(id="skill_39", display_name="Energy Surge", skill_id=39, profession=LocalProfession.MESMER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Energy Surge", capture_function="skill_39", start_map=414, icon_filename="[39] - Energy Surge.jpg"),
EliteSkill(id="skill_47", display_name="Ineptitude", skill_id=47, profession=LocalProfession.MESMER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Ineptitude", capture_function="skill_47", start_map=641, icon_filename="[47] - Ineptitude.jpg"),
EliteSkill(id="skill_53", display_name="Migraine", skill_id=53, profession=LocalProfession.MESMER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Migraine", capture_function="skill_53", start_map=638, icon_filename="[53] - Migraine.jpg"),
EliteSkill(id="skill_33", display_name="Illusionary Weaponry", skill_id=33, profession=LocalProfession.MESMER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Illusionary Weaponry", capture_function="skill_33", start_map=155, icon_filename="[33] - Illusionary Weaponry.jpg"),
EliteSkill(id="skill_52", display_name="Panic", skill_id=52, profession=LocalProfession.MESMER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Panic", capture_function="skill_52", start_map=124, icon_filename="[52] - Panic.jpg"),
EliteSkill(id="skill_74", display_name="Echo", skill_id=74, profession=LocalProfession.MESMER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Echo", capture_function="skill_74", start_map=130, icon_filename="[74] - Echo.jpg"),
EliteSkill(id="skill_82", display_name="Mantra of Recall", skill_id=82, profession=LocalProfession.MESMER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Mantra of Recall", capture_function="skill_82", start_map=155, icon_filename="[82] - Mantra of Recall.jpg"),
EliteSkill(id="skill_79", display_name="Energy Drain", skill_id=79, profession=LocalProfession.MESMER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Energy Drain", capture_function="skill_79", start_map=193, icon_filename="[79] - Energy Drain.jpg"),
EliteSkill(id="skill_63", display_name="Keystone Signet", skill_id=63, profession=LocalProfession.MESMER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Keystone Signet", capture_function="skill_63", start_map=156, icon_filename="[63] - Keystone Signet.jpg"),
EliteSkill(id="skill_13", display_name="Mantra of Recovery", skill_id=13, profession=LocalProfession.MESMER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Mantra of Recovery", capture_function="skill_13", start_map=349, icon_filename="[13] - Mantra of Recovery.jpg"),
EliteSkill(id="skill_1345", display_name="Enchanter's Conundrum", skill_id=1345, profession=LocalProfession.MESMER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Enchanter's Conundrum", capture_function="skill_1345", start_map=426, icon_filename="[1345] - Enchanter's Conundrum.jpg"),
EliteSkill(id="skill_1348", display_name="Hex Eater Vortex", skill_id=1348, profession=LocalProfession.MESMER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Hex Eater Vortex", capture_function="skill_1348", start_map=480, icon_filename="[1348] - Hex Eater Vortex.jpg"),
EliteSkill(id="skill_5", display_name="Power Block", skill_id=5, profession=LocalProfession.MESMER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Power Block", capture_function="skill_5", start_map=650, icon_filename="[5] - Power Block.jpg"),
EliteSkill(id="skill_953", display_name="Power Flux", skill_id=953, profession=LocalProfession.MESMER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Power Flux", capture_function="skill_953", start_map=469, icon_filename="[953] - Power Flux.jpg"),
EliteSkill(id="skill_1053", display_name="Psychic Distraction", skill_id=1053, profession=LocalProfession.MESMER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Psychic Distraction", capture_function="skill_1053", start_map=284, icon_filename="[1053] - Psychic Distraction.jpg"),
EliteSkill(id="skill_804", display_name="Arcane Languor", skill_id=804, profession=LocalProfession.MESMER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Arcane Languor", capture_function="skill_804", start_map=226, icon_filename="[804] - Arcane Languor.jpg"),
EliteSkill(id="skill_880", display_name="Stolen Speed", skill_id=880, profession=LocalProfession.MESMER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Stolen Speed", capture_function="skill_880", start_map=283, icon_filename="[880] - Stolen Speed.jpg"),
EliteSkill(id="skill_1339", display_name="Symbols of Inspiration", skill_id=1339, profession=LocalProfession.MESMER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Symbols of Inspiration", capture_function="skill_1339", start_map=473, icon_filename="[1339] - Symbols of Inspiration.jpg"),
EliteSkill(id="skill_1656", display_name="Air of Disenchantment", skill_id=1656, profession=LocalProfession.MESMER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Air of Disenchantment", capture_function="skill_1656", start_map=428, icon_filename="[1656] - Air of Disenchantment.jpg"),
EliteSkill(id="skill_1055", display_name="Recurring Insecurity", skill_id=1055, profession=LocalProfession.MESMER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Recurring Insecurity", capture_function="skill_1055", start_map=287, icon_filename="[1055] - Recurring Insecurity.jpg"),
EliteSkill(id="skill_900", display_name="Shared Burden", skill_id=900, profession=LocalProfession.MESMER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Shared Burden", capture_function="skill_900", start_map=287, icon_filename="[900] - Shared Burden.jpg"),
EliteSkill(id="skill_1346", display_name="Signet of Illusions", skill_id=1346, profession=LocalProfession.MESMER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Signet of Illusions", capture_function="skill_1346", start_map=494, icon_filename="[1346] - Signet of Illusions.jpg"),
EliteSkill(id="skill_1333", display_name="Extend Conditions", skill_id=1333, profession=LocalProfession.MESMER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Extend Conditions", capture_function="skill_1333", start_map=381, icon_filename="[1333] - Extend Conditions.jpg"),
EliteSkill(id="skill_813", display_name="Lyssa's Aura", skill_id=813, profession=LocalProfession.MESMER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Lyssa's Aura", capture_function="skill_813", start_map=643, icon_filename="[813] - Lyssa's Aura.jpg"),
EliteSkill(id="skill_954", display_name="Expel Hexes", skill_id=954, profession=LocalProfession.MESMER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Expel Hexes", capture_function="skill_954", start_map=292, icon_filename="[954] - Expel Hexes.jpg"),
EliteSkill(id="skill_1499", display_name="Pious Renewal", skill_id=1499, profession=LocalProfession.DERVISH, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Pious Renewal", capture_function="skill_1499", start_map=493, icon_filename="[1499] - Pious Renewal.jpg"),
EliteSkill(id="skill_119", display_name="Blood is Power", skill_id=119, profession=LocalProfession.NECROMANCER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Blood is Power", capture_function="skill_119", start_map=393, icon_filename="[119] - Blood is Power.jpg"),
EliteSkill(id="skill_1588", display_name="Cautery Signet", skill_id=1588, profession=LocalProfession.PARAGON, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Cautery Signet", capture_function="skill_1588", start_map=424, icon_filename="[1588] - Cautery Signet.jpg"),
EliteSkill(id="skill_3427", display_name="Together as One!", skill_id=3427, profession=LocalProfession.RANGER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Together as One", capture_function="skill_3427", start_map=650, icon_filename="[3427] - Together as One!.jpg"),
EliteSkill(id="skill_3431", display_name="Heroic Refrain", skill_id=3431, profession=LocalProfession.PARAGON, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Heroic Refrain", capture_function="skill_3431", start_map=440, icon_filename="[3431] - Heroic Refrain.jpg"),
EliteSkill(id="skill_3423", display_name="Soul Taker", skill_id=3423, profession=LocalProfession.NECROMANCER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Soul Taker", capture_function="skill_3423", start_map=35, icon_filename="[3423] - Soul Taker.jpg"),
EliteSkill(id="skill_3424", display_name="Over The Limit", skill_id=3424, profession=LocalProfession.ELEMENTALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Over The Limit", capture_function="skill_3424", start_map=35, icon_filename="[3424] - Over the Limit.jpg"),
EliteSkill(id="skill_3425", display_name="Judgment Strike", skill_id=3425, profession=LocalProfession.MONK, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Judgment Strike", capture_function="skill_3425", start_map=440, icon_filename="[3425] - Judgment Strike.jpg"),
EliteSkill(id="skill_3422", display_name="Time Ward", skill_id=3422, profession=LocalProfession.MESMER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Time Ward", capture_function="skill_3422", start_map=650, icon_filename="[3422] - Time Ward.jpg"),
EliteSkill(id="skill_3430", display_name="Vow of Revolution", skill_id=3430, profession=LocalProfession.DERVISH, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Vow of Revolution", capture_function="skill_3430", start_map=440, icon_filename="[3430] - Vow of Revolution.jpg"),
EliteSkill(id="skill_3426", display_name="Seven Weapon Stance", skill_id=3426, profession=LocalProfession.WARRIOR, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Seven Weapon Stance", capture_function="skill_3426", start_map=226, icon_filename="[3426] - Seven Weapons Stance.jpg"),
EliteSkill(id="skill_831", display_name="Primal Rage", skill_id=831, profession=LocalProfession.WARRIOR, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Primal Rage", capture_function="skill_831", start_map=298, icon_filename="[831] - Primal Rage.jpg"),
EliteSkill(id="skill_338", display_name="Eviscerate", skill_id=338, profession=LocalProfession.WARRIOR, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Eviscerate", capture_function="skill_338", start_map=650, icon_filename="[338] - Eviscerate.jpg"),
EliteSkill(id="skill_365", display_name="Victory is Mine", skill_id=365, profession=LocalProfession.WARRIOR, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Victory is Mine", capture_function="skill_365", start_map=158, icon_filename="[365] - Victory is Mine!.jpg"),
EliteSkill(id="skill_364", display_name="Charge!", skill_id=364, profession=LocalProfession.WARRIOR, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Charge!", capture_function="skill_364", start_map=277, icon_filename="[364] - Charge!.jpg"),
EliteSkill(id="skill_869", display_name="Coward!", skill_id=869, profession=LocalProfession.WARRIOR, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Coward!", capture_function="skill_869", start_map=278, icon_filename="[869] - Coward!.jpg"),
EliteSkill(id="skill_1412", display_name="You're All Alone!", skill_id=1412, profession=LocalProfession.WARRIOR, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]You're All Alone!", capture_function="skill_1412", start_map=376, icon_filename="[1412] - You're All Alone!.jpg"),
EliteSkill(id="skill_1142", display_name="Auspicious Parry", skill_id=1142, profession=LocalProfession.WARRIOR, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Auspicious Parry", capture_function="skill_1142", start_map=225, icon_filename="[1142] - Auspicious Parry.jpg"),
EliteSkill(id="skill_358", display_name="Backbreaker", skill_id=358, profession=LocalProfession.WARRIOR, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Backbreaker", capture_function="skill_358", start_map=638, icon_filename="[358] - Backbreaker.jpg"),
EliteSkill(id="skill_317", display_name="Battle Rage", skill_id=317, profession=LocalProfession.WARRIOR, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Battle Rage", capture_function="skill_317", start_map=219, icon_filename="[317] - Battle Rage.jpg"),
EliteSkill(id="skill_379", display_name="Bull's Charge", skill_id=379, profession=LocalProfession.WARRIOR, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Bull's Charge", capture_function="skill_379", start_map=35, icon_filename="[379] - Bull's Charge.jpg"),
EliteSkill(id="skill_1405", display_name="Charging Strike", skill_id=1405, profession=LocalProfession.WARRIOR, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Charging Strike", capture_function="skill_1405", start_map=435, icon_filename="[1405] - Charging Strike.jpg"),
EliteSkill(id="skill_335", display_name="Cleave", skill_id=335, profession=LocalProfession.WARRIOR, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Cleave", capture_function="skill_335", start_map=289, icon_filename="[335] - Cleave.jpg"),
EliteSkill(id="skill_1415", display_name="Crippling Slash", skill_id=1415, profession=LocalProfession.WARRIOR, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Crippling Slash", capture_function="skill_1415", start_map=644, icon_filename="[1415] - Crippling Slash.jpg"),
EliteSkill(id="skill_1696", display_name="Decapitate", skill_id=1696, profession=LocalProfession.WARRIOR, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Decapitate", capture_function="skill_1696", start_map=424, icon_filename="[1696] - Decapitate.jpg"),
EliteSkill(id="skill_318", display_name="Defy Pain", skill_id=318, profession=LocalProfession.WARRIOR, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Defy Pain", capture_function="skill_318", start_map=24, icon_filename="[318] - Defy Pain.jpg"),
EliteSkill(id="skill_355", display_name="Devastating Hammer", skill_id=355, profession=LocalProfession.WARRIOR, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Devastating Hammer", capture_function="skill_355", start_map=279, icon_filename="[355] - Devastating Hammer.jpg"),
EliteSkill(id="skill_907", display_name="Dragon Slash", skill_id=907, profession=LocalProfession.WARRIOR, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Dragon Slash", capture_function="skill_907", start_map=273, icon_filename="[907] - Dragon Slash.jpg"),
EliteSkill(id="skill_375", display_name="Dwarven Battle Stance", skill_id=375, profession=LocalProfession.WARRIOR, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Dwarven Battle Stance", capture_function="skill_375", start_map=639, icon_filename="[375] - Dwarven Battle Stance.jpg"),
EliteSkill(id="skill_993", display_name="Enraged Smash", skill_id=993, profession=LocalProfession.WARRIOR, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Enraged Smash", capture_function="skill_993", start_map=274, icon_filename="[993] - Enraged Smash.jpg"),
EliteSkill(id="skill_889", display_name="Forceful Blow", skill_id=889, profession=LocalProfession.WARRIOR, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Forceful Blow", capture_function="skill_889", start_map=272, icon_filename="[889] - Forceful Blow.jpg"),
EliteSkill(id="skill_1406", display_name="Headbutt", skill_id=1406, profession=LocalProfession.WARRIOR, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Headbutt", capture_function="skill_1406", start_map=381, icon_filename="[1406] - Headbutt.jpg"),
EliteSkill(id="skill_381", display_name="Hundred Blades", skill_id=381, profession=LocalProfession.WARRIOR, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Hundred Blades", capture_function="skill_381", start_map=284, icon_filename="[381] - Hundred Blades.jpg"),
EliteSkill(id="skill_1694", display_name="Magehunter Strike", skill_id=1694, profession=LocalProfession.WARRIOR, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Magehunter Strike", capture_function="skill_1694", start_map=424, icon_filename="[1694] - Magehunter Strike.jpg"),
EliteSkill(id="skill_1697", display_name="Magehunter's Smash", skill_id=1697, profession=LocalProfession.WARRIOR, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Magehunter's Smash", capture_function="skill_1697", start_map=476, icon_filename="[1697] - Magehunter's Smash.jpg"),
EliteSkill(id="skill_892", display_name="Quivering Blade", skill_id=892, profession=LocalProfession.WARRIOR, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Quivering Blade", capture_function="skill_892", start_map=303, icon_filename="[892] - Quivering Blade.jpg"),
EliteSkill(id="skill_1408", display_name="Rage of the Ntouka", skill_id=1408, profession=LocalProfession.WARRIOR, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Rage of the Ntouka", capture_function="skill_1408", start_map=387, icon_filename="[1408] - Rage of the Ntouka.jpg"),
EliteSkill(id="skill_1146", display_name="Shove", skill_id=1146, profession=LocalProfession.WARRIOR, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Shove", capture_function="skill_1146", start_map=77, icon_filename="[1146] - Shove.jpg"),
EliteSkill(id="skill_329", display_name="Skull Crack", skill_id=329, profession=LocalProfession.WARRIOR, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Skull Crack", capture_function="skill_329", start_map=643, icon_filename="[329] - Skull Crack.jpg"),
EliteSkill(id="skill_1698", display_name="Soldier's Stance", skill_id=1698, profession=LocalProfession.WARRIOR, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Soldier's Stance", capture_function="skill_1698", start_map=545, icon_filename="[1698] - Soldier's Stance.jpg"),
EliteSkill(id="skill_1701", display_name="Steady Stance", skill_id=1701, profession=LocalProfession.WARRIOR, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Steady Stance", capture_function="skill_1701", start_map=407, icon_filename="[1701] - Steady Stance.jpg"),
EliteSkill(id="skill_992", display_name="Triple Chop", skill_id=992, profession=LocalProfession.WARRIOR, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Triple Chop", capture_function="skill_992", start_map=303, icon_filename="[992] - Triple Chop.jpg"),
EliteSkill(id="skill_374", display_name="Warrior's Endurance", skill_id=374, profession=LocalProfession.WARRIOR, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Warrior's Endurance", capture_function="skill_374", start_map=117, icon_filename="[374] - Warrior's Endurance.jpg"),
EliteSkill(id="skill_888", display_name="Whirling Axe", skill_id=888, profession=LocalProfession.WARRIOR, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Whirling Axe", capture_function="skill_888", start_map=273, icon_filename="[888] - Whirling Axe.jpg"),
EliteSkill(id="skill_3429", display_name="Weapons of Three Forges", skill_id=3429, profession=LocalProfession.RITUALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Weapons of Three Forges", capture_function="skill_3429", start_map=440, icon_filename="[3429] - Weapons of Three Forges.jpg"),
EliteSkill(id="skill_3428", display_name="Shadow Theft", skill_id=3428, profession=LocalProfession.ASSASSIN, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Shadow Theft", capture_function="skill_3428", start_map=226, icon_filename="[3428] - Shadow Theft.jpg"),
EliteSkill(id="skill_1634", display_name="Shattering Assault", skill_id=1634, profession=LocalProfession.ASSASSIN, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Shattering Assault", capture_function="skill_1634", start_map=480, icon_filename="[1634] - Shattering Assault.jpg"),
EliteSkill(id="skill_1568", display_name="Anthem of Guidance", skill_id=1568, profession=LocalProfession.PARAGON, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Anthem of Guidance", capture_function="skill_1568", start_map=403, icon_filename="[1568] - Anthem of Guidance.jpg"),
EliteSkill(id="skill_1554", display_name="Crippling Anthem", skill_id=1554, profession=LocalProfession.PARAGON, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Crippling Anthem", capture_function="skill_1554", start_map=376, icon_filename="[1554] - Crippling Anthem.jpg"),
EliteSkill(id="skill_1587", display_name="Angelic Bond", skill_id=1587, profession=LocalProfession.PARAGON, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Angelic Bond", capture_function="skill_1587", start_map=434, icon_filename="[1587] - Angelic Bond.jpg"),
EliteSkill(id="skill_1555", display_name="Defensive Anthem", skill_id=1555, profession=LocalProfession.PARAGON, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Defensive Anthem", capture_function="skill_1555", start_map=387, icon_filename="[1555] - Defensive Anthem.jpg"),
EliteSkill(id="skill_1599", display_name="It's Just a Flesh Wound.", skill_id=1599, profession=LocalProfession.PARAGON, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]It's Just a Flesh Wound.", capture_function="skill_1599", start_map=480, icon_filename="[1599] - It's Just a Flesh Wound..jpg"),
EliteSkill(id="skill_1782", display_name="The Power Is Yours!", skill_id=1782, profession=LocalProfession.PARAGON, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]The Power Is Yours!", capture_function="skill_1782", start_map=440, icon_filename="[1782] - The Power Is Yours!.jpg"),
EliteSkill(id="skill_1570", display_name="Song of Purification", skill_id=1570, profession=LocalProfession.PARAGON, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Song of Purification", capture_function="skill_1570", start_map=403, icon_filename="[1570] - Song of Purification.jpg"),
EliteSkill(id="skill_1771", display_name="Song of Restoration", skill_id=1771, profession=LocalProfession.PARAGON, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Song of Restoration", capture_function="skill_1771", start_map=428, icon_filename="[1771] - Song of Restoration.jpg"),
EliteSkill(id="skill_1548", display_name="Cruel Spear", skill_id=1548, profession=LocalProfession.PARAGON, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Cruel Spear", capture_function="skill_1548", start_map=427, icon_filename="[1548] - Cruel Spear.jpg"),
EliteSkill(id="skill_1602", display_name="Stunning Strike", skill_id=1602, profession=LocalProfession.PARAGON, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Stunning Strike", capture_function="skill_1602", start_map=469, icon_filename="[1602] - Stunning Strike.jpg"),
EliteSkill(id="skill_1773", display_name="Soldier's Fury", skill_id=1773, profession=LocalProfession.PARAGON, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Soldier's Fury", capture_function="skill_1773", start_map=438, icon_filename="[1773] - Soldier's Fury.jpg"),
EliteSkill(id="skill_1596", display_name="Incoming!", skill_id=1596, profession=LocalProfession.PARAGON, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Incoming!", capture_function="skill_1596", start_map=414, icon_filename="[1596] - Incoming!.jpg"),
EliteSkill(id="skill_1769", display_name="Focused Anger", skill_id=1769, profession=LocalProfession.PARAGON, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Focused Anger", capture_function="skill_1769", start_map=427, icon_filename="[1769] - Focused Anger.jpg"),
EliteSkill(id="skill_1553", display_name="Anthem of Fury", skill_id=1553, profession=LocalProfession.PARAGON, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Anthem of Fury", capture_function="skill_1553", start_map=450, icon_filename="[1553] - Anthem of Fury.jpg"),
EliteSkill(id="skill_826", display_name="Shadow Form", skill_id=826, profession=LocalProfession.ASSASSIN, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Shadow Form", capture_function="skill_826", start_map=284, icon_filename="[826] - Shadow Form.jpg"),
EliteSkill(id="skill_1652", display_name="Shadow Prison", skill_id=1652, profession=LocalProfession.ASSASSIN, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Shadow Prison", capture_function="skill_1652", start_map=398, icon_filename="[1652] - Shadow Prison.jpg"),
EliteSkill(id="skill_928", display_name="Shadow Shroud", skill_id=928, profession=LocalProfession.ASSASSIN, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Shadow Shroud", capture_function="skill_928", start_map=277, icon_filename="[928] - Shadow Shroud.jpg"),
EliteSkill(id="skill_1649", display_name="Way of the Assassin", skill_id=1649, profession=LocalProfession.ASSASSIN, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Way of the Assassin", capture_function="skill_1649", start_map=424, icon_filename="[1649] - Way of the Assassin.jpg"),
EliteSkill(id="skill_1029", display_name="Dark Apostasy", skill_id=1029, profession=LocalProfession.ASSASSIN, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Dark Apostasy", capture_function="skill_1029", start_map=230, icon_filename="[1029] - Dark Apostasy.jpg"),
EliteSkill(id="skill_1035", display_name="Assassin's Promise", skill_id=1035, profession=LocalProfession.ASSASSIN, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Assassins Promise", capture_function="skill_1035", start_map=640, icon_filename="[1035] - Assassin's Promise.jpg"),
EliteSkill(id="skill_1030", display_name="Locust's Fury", skill_id=1030, profession=LocalProfession.ASSASSIN, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Locust's Fury", capture_function="skill_1030", start_map=129, icon_filename="[1030] - Locust's Fury.jpg"),
EliteSkill(id="skill_1045", display_name="Palm Strike", skill_id=1045, profession=LocalProfession.ASSASSIN, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Palm Strike", capture_function="skill_1045", start_map=303, icon_filename="[1045] - Palm Strike.jpg"),
EliteSkill(id="skill_1034", display_name="Seeping Wound", skill_id=1034, profession=LocalProfession.ASSASSIN, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Seeping Wound", capture_function="skill_1034", start_map=51, icon_filename="[1034] - Seeping Wound.jpg"),
EliteSkill(id="skill_1042", display_name="Flashing Blades", skill_id=1042, profession=LocalProfession.ASSASSIN, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Flashing Blades", capture_function="skill_1042", start_map=220, icon_filename="[1042] - Flashing Blades.jpg"),
EliteSkill(id="skill_1640", display_name="Fox's Promise", skill_id=1640, profession=LocalProfession.ASSASSIN, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Fox's Promise", capture_function="skill_1640", start_map=396, icon_filename="[1640] - Fox's Promise.jpg"),
EliteSkill(id="skill_771", display_name="Aura of Displacement", skill_id=771, profession=LocalProfession.ASSASSIN, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Aura of Displacement", capture_function="skill_771", start_map=77, icon_filename="[771] - Aura of Displacement.jpg"),
EliteSkill(id="skill_570", display_name="Mark of Insecurity", skill_id=570, profession=LocalProfession.ASSASSIN, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Mark of Insecurity", capture_function="skill_570", start_map=559, icon_filename="[570] - Mark of Insecurity.jpg"),
EliteSkill(id="skill_1642", display_name="Hidden Caltrops", skill_id=1642, profession=LocalProfession.ASSASSIN, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Hidden Caltrops", capture_function="skill_1642", start_map=424, icon_filename="[1642] - Hidden Caltrops.jpg"),
EliteSkill(id="skill_1643", display_name="Assault Enchantments", skill_id=1643, profession=LocalProfession.ASSASSIN, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Assault Enchantments", capture_function="skill_1643", start_map=450, icon_filename="[1643] - Assault Enchantments.jpg"),
EliteSkill(id="skill_1654", display_name="Shadow Meld", skill_id=1654, profession=LocalProfession.ASSASSIN, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Shadow Meld", capture_function="skill_1654", start_map=477, icon_filename="[1654] - Shadow Meld.jpg"),
EliteSkill(id="skill_1644", display_name="Wastrel's Collapse", skill_id=1644, profession=LocalProfession.ASSASSIN, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Wastrel's Collapse", capture_function="skill_1644", start_map=407, icon_filename="[1644] - Wastrel's Collapse.jpg"),
EliteSkill(id="skill_1635", display_name="Golden Skull Strike", skill_id=1635, profession=LocalProfession.ASSASSIN, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Golden Skull Strike", capture_function="skill_1635", start_map=496, icon_filename="[1635] - Golden Skull Strike.jpg"),
EliteSkill(id="skill_988", display_name="Temple Strike", skill_id=988, profession=LocalProfession.ASSASSIN, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Temple Strike", capture_function="skill_988", start_map=289, icon_filename="[988] - Temple Strike.jpg"),
EliteSkill(id="skill_781", display_name="Moebius Strike", skill_id=781, profession=LocalProfession.ASSASSIN, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Moebius Strike", capture_function="skill_781", start_map=130, icon_filename="[781] - Moebius Strike.jpg"),
EliteSkill(id="skill_801", display_name="Shroud of Silence", skill_id=801, profession=LocalProfession.ASSASSIN, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Shroud of Silence", capture_function="skill_801", start_map=226, icon_filename="[801] - Shroud of Silence.jpg"),
EliteSkill(id="skill_827", display_name="Siphon Strength", skill_id=827, profession=LocalProfession.ASSASSIN, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Siphon Strength", capture_function="skill_827", start_map=288, icon_filename="[827] - Siphon Strength.jpg"),
EliteSkill(id="skill_987", display_name="Way of the Empty Palm", skill_id=987, profession=LocalProfession.ASSASSIN, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Way of the Empty Palm", capture_function="skill_987", start_map=273, icon_filename="[987] - Way of the Empty Palm.jpg"),
EliteSkill(id="skill_799", display_name="Beguiling Haze", skill_id=799, profession=LocalProfession.ASSASSIN, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Beguiling Haze", capture_function="skill_799", start_map=287, icon_filename="[799] - Beguiling Haze.jpg"),
EliteSkill(id="skill_1517", display_name="Vow of Silence", skill_id=1517, profession=LocalProfession.DERVISH, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Vow of Silence", capture_function="skill_1517", start_map=478, icon_filename="[1517] - Vow of Silence.jpg"),
EliteSkill(id="skill_1754", display_name="Onslaught", skill_id=1754, profession=LocalProfession.DERVISH, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Onslaught", capture_function="skill_1754", start_map=643, icon_filename="[1754] - Onslaught.jpg"),
EliteSkill(id="skill_1760", display_name="Ebon Dust Aura", skill_id=1760, profession=LocalProfession.DERVISH, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Ebon Dust Aura", capture_function="skill_1760", start_map=414, icon_filename="[1760] - Ebon Dust Aura.jpg"),
EliteSkill(id="skill_1518", display_name="Avatar of Balthazar", skill_id=1518, profession=LocalProfession.DERVISH, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Avatar of Balthazar", capture_function="skill_1518", start_map=387, icon_filename="[1518] - Avatar of Balthazar.jpg"),
EliteSkill(id="skill_1522", display_name="Avatar of Melandru", skill_id=1522, profession=LocalProfession.DERVISH, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Avatar of Melandru", capture_function="skill_1522", start_map=477, icon_filename="[1522] - Avatar of Melandru.jpg"),
EliteSkill(id="skill_1519", display_name="Avatar of Dwayna", skill_id=1519, profession=LocalProfession.DERVISH, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Avatar of Dwayna", capture_function="skill_1519", start_map=424, icon_filename="[1519] - Avatar of Dwayna.jpg"),
EliteSkill(id="skill_1521", display_name="Avatar of Lyssa", skill_id=1521, profession=LocalProfession.DERVISH, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Avatar of Lyssa", capture_function="skill_1521", start_map=554, icon_filename="[1521] - Avatar of Lyssa.jpg"),
EliteSkill(id="skill_1520", display_name="Avatar of Grenth", skill_id=1520, profession=LocalProfession.DERVISH, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Avatar of Grenth", capture_function="skill_1520", start_map=426, icon_filename="[1520] - Avatar of Grenth.jpg"),
EliteSkill(id="skill_1502", display_name="Arcane Zeal", skill_id=1502, profession=LocalProfession.DERVISH, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Arcane Zeal", capture_function="skill_1502", start_map=450, icon_filename="[1502] - Arcane Zeal.jpg"),
EliteSkill(id="skill_1756", display_name="Grenth's Grasp", skill_id=1756, profession=LocalProfession.DERVISH, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Grenth's Grasp", capture_function="skill_1756", start_map=477, icon_filename="[1756] - Grenth's Grasp.jpg"),
EliteSkill(id="skill_1767", display_name="Reaper's Sweep", skill_id=1767, profession=LocalProfession.DERVISH, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Reaper's Sweep", capture_function="skill_1767", start_map=421, icon_filename="[1767] - Reaper's Sweep.jpg"),
EliteSkill(id="skill_1759_1", display_name="Vow of Strength", skill_id=1759, profession=LocalProfession.DERVISH, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Vow of Strength", capture_function="skill_1759_1", start_map=376, icon_filename="[1759] - Vow of Strength.jpg"),
EliteSkill(id="skill_1536", display_name="Wounding Strike", skill_id=1536, profession=LocalProfession.DERVISH, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Wounding Strike", capture_function="skill_1536", start_map=476, icon_filename="[1536] - Wounding Strike.jpg"),
EliteSkill(id="skill_1761", display_name="Zealous Vow", skill_id=1761, profession=LocalProfession.DERVISH, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Zealous Vow", capture_function="skill_1761", start_map=378, icon_filename="[1761] - Zealous Vow.jpg"),
EliteSkill(id="skill_1239", display_name="Signet of Spirits", skill_id=1239, profession=LocalProfession.RITUALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Signet of Spirits", capture_function="skill_1239", start_map=388, icon_filename="[1239] - Signet of Spirits.jpg"),
EliteSkill(id="skill_1220", display_name="Attuned Was Songkai", skill_id=1220, profession=LocalProfession.RITUALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Attuned Was Songkai", capture_function="skill_1220", start_map=222, icon_filename="[1220] - Attuned Was Songkai.jpg"),
EliteSkill(id="skill_1215", display_name="Clamor of Souls", skill_id=1215, profession=LocalProfession.RITUALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Clamor of Souls", capture_function="skill_1215", start_map=222, icon_filename="[1215] - Clamor of Souls.jpg"),
EliteSkill(id="skill_1744", display_name="Caretaker's Charge", skill_id=1744, profession=LocalProfession.RITUALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Caretaker's Charge", capture_function="skill_1744", start_map=473, icon_filename="[1744] - Caretaker's Charge.jpg"),
EliteSkill(id="skill_914", display_name="Consume Soul", skill_id=914, profession=LocalProfession.RITUALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Consume Soul", capture_function="skill_914", start_map=389, icon_filename="[914] - Consume Soul.jpg"),
EliteSkill(id="skill_1240", display_name="Soul Twisting", skill_id=1240, profession=LocalProfession.RITUALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Soul Twisting", capture_function="skill_1240", start_map=298, icon_filename="[1240] - Soul Twisting.jpg"),
EliteSkill(id="skill_1750", display_name="Xinrae's Weapon", skill_id=1750, profession=LocalProfession.RITUALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Xinrae's Weapon", capture_function="skill_1750", start_map=496, icon_filename="[1750] - Xinrae's Weapon.jpg"),
EliteSkill(id="skill_1737", display_name="Wielder's Zeal", skill_id=1737, profession=LocalProfession.RITUALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Wielder's Zeal", capture_function="skill_1737", start_map=376, icon_filename="[1737] - Wielder's Zeal.jpg"),
EliteSkill(id="skill_1732", display_name="Destructive Was Glaive", skill_id=1732, profession=LocalProfession.RITUALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Destructive Was Glaive", capture_function="skill_1732", start_map=387, icon_filename="[1732] - Destructive Was Glaive.jpg"),
EliteSkill(id="skill_789", display_name="Grasping Was Kuurong", skill_id=789, profession=LocalProfession.RITUALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Grasping Was Kuurong", capture_function="skill_789", start_map=391, icon_filename="[789] - Grasping Was Kuurong.jpg"),
EliteSkill(id="skill_1479", display_name="Offering of Spirit", skill_id=1479, profession=LocalProfession.RITUALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Offering of Spirit", capture_function="skill_1479", start_map=495, icon_filename="[1479] - Offering of Spirit.jpg"),
EliteSkill(id="skill_1250", display_name="Preservation", skill_id=1250, profession=LocalProfession.RITUALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Preservation", capture_function="skill_1250", start_map=279, icon_filename="[1250] - Preservation.jpg"),
EliteSkill(id="skill_1482", display_name="Reclaim Essence", skill_id=1482, profession=LocalProfession.RITUALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Reclaim Essence", capture_function="skill_1482", start_map=442, icon_filename="[1482] - Reclaim Essence.jpg"),
EliteSkill(id="skill_1761", display_name="Zealous Vow", skill_id=1761, profession=LocalProfession.DERVISH, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Zealous Vow", capture_function="skill_1761", start_map=378, icon_filename="[1761] - Zealous Vow.jpg"),
EliteSkill(id="skill_1239", display_name="Signet of Spirits", skill_id=1239, profession=LocalProfession.RITUALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Signet of Spirits", capture_function="skill_1239", start_map=388, icon_filename="[1239] - Signet of Spirits.jpg"),
EliteSkill(id="skill_1220", display_name="Attuned Was Songkai", skill_id=1220, profession=LocalProfession.RITUALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Attuned Was Songkai", capture_function="skill_1220", start_map=222, icon_filename="[1220] - Attuned Was Songkai.jpg"),
EliteSkill(id="skill_1215", display_name="Clamor of Souls", skill_id=1215, profession=LocalProfession.RITUALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Clamor of Souls", capture_function="skill_1215", start_map=222, icon_filename="[1215] - Clamor of Souls.jpg"),
EliteSkill(id="skill_1744", display_name="Caretaker's Charge", skill_id=1744, profession=LocalProfession.RITUALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Caretaker's Charge", capture_function="skill_1744", start_map=473, icon_filename="[1744] - Caretaker's Charge.jpg"),
EliteSkill(id="skill_914", display_name="Consume Soul", skill_id=914, profession=LocalProfession.RITUALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Consume Soul", capture_function="skill_914", start_map=389, icon_filename="[914] - Consume Soul.jpg"),
EliteSkill(id="skill_1240", display_name="Soul Twisting", skill_id=1240, profession=LocalProfession.RITUALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Soul Twisting", capture_function="skill_1240", start_map=298, icon_filename="[1240] - Soul Twisting.jpg"),
EliteSkill(id="skill_1750", display_name="Xinrae's Weapon", skill_id=1750, profession=LocalProfession.RITUALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Xinrae's Weapon", capture_function="skill_1750", start_map=496, icon_filename="[1750] - Xinrae's Weapon.jpg"),
EliteSkill(id="skill_1737", display_name="Wielder's Zeal", skill_id=1737, profession=LocalProfession.RITUALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Wielder's Zeal", capture_function="skill_1737", start_map=376, icon_filename="[1737] - Wielder's Zeal.jpg"),
EliteSkill(id="skill_1732", display_name="Destructive Was Glaive", skill_id=1732, profession=LocalProfession.RITUALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Destructive Was Glaive", capture_function="skill_1732", start_map=387, icon_filename="[1732] - Destructive Was Glaive.jpg"),
EliteSkill(id="skill_789", display_name="Grasping Was Kuurong", skill_id=789, profession=LocalProfession.RITUALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Grasping Was Kuurong", capture_function="skill_789", start_map=391, icon_filename="[789] - Grasping Was Kuurong.jpg"),
EliteSkill(id="skill_1479", display_name="Offering of Spirit", skill_id=1479, profession=LocalProfession.RITUALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Offering of Spirit", capture_function="skill_1479", start_map=495, icon_filename="[1479] - Offering of Spirit.jpg"),
EliteSkill(id="skill_1250", display_name="Preservation", skill_id=1250, profession=LocalProfession.RITUALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Preservation", capture_function="skill_1250", start_map=279, icon_filename="[1250] - Preservation.jpg"),
EliteSkill(id="skill_1482", display_name="Reclaim Essence", skill_id=1482, profession=LocalProfession.RITUALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Reclaim Essence", capture_function="skill_1482", start_map=442, icon_filename="[1482] - Reclaim Essence.jpg"),
EliteSkill(id="skill_1217", display_name="Ritual Lord", skill_id=1217, profession=LocalProfession.RITUALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Ritual Lord", capture_function="skill_1217", start_map=289, icon_filename="[1217] - Ritual Lord.jpg"),
EliteSkill(id="skill_1742", display_name="Signet of Ghostly Might", skill_id=1742, profession=LocalProfession.RITUALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Signet of Ghostly Might", capture_function="skill_1742", start_map=480, icon_filename="[1742] - Signet of Ghostly Might.jpg"),
EliteSkill(id="skill_1231", display_name="Spirit Channeling", skill_id=1231, profession=LocalProfession.RITUALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Spirit Channeling", capture_function="skill_1231", start_map=283, icon_filename="[1231] - Spirit Channeling.jpg"),
EliteSkill(id="skill_1257", display_name="Spirit Light Weapon", skill_id=1257, profession=LocalProfession.RITUALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Spirit Light Weapon", capture_function="skill_1257", start_map=390, icon_filename="[1257] - Spirit Light Weapon.jpg"),
EliteSkill(id="skill_1736", display_name="Spirit's Strength", skill_id=1736, profession=LocalProfession.RITUALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Spirit's Strength", capture_function="skill_1736", start_map=428, icon_filename="[1736] - Spirit's Strength.jpg"),
EliteSkill(id="skill_913", display_name="Tranquil Was Tanasen", skill_id=913, profession=LocalProfession.RITUALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Tranquil Was Tanasen", capture_function="skill_913", start_map=51, icon_filename="[913] - Tranquil Was Tanasen.jpg"),
EliteSkill(id="skill_790", display_name="Vengeful Was Khanhei", skill_id=790, profession=LocalProfession.RITUALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Vengeful Was Khanhei", capture_function="skill_790", start_map=287, icon_filename="[790] - Vengeful Was Khanhei.jpg"),
EliteSkill(id="skill_1255", display_name="Wanderlust", skill_id=1255, profession=LocalProfession.RITUALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Wanderlust", capture_function="skill_1255", start_map=284, icon_filename="[1255] - Wanderlust.jpg"),
EliteSkill(id="skill_1749", display_name="Weapon of Fury", skill_id=1749, profession=LocalProfession.RITUALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Weapon of Fury", capture_function="skill_1749", start_map=424, icon_filename="[1749] - Weapon of Fury.jpg"),
EliteSkill(id="skill_1268", display_name="Weapon of Quickening", skill_id=1268, profession=LocalProfession.RITUALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Weapon of Quickening", capture_function="skill_1268", start_map=219, icon_filename="[1268] - Weapon of Quickening.jpg"),
EliteSkill(id="skill_1730", display_name="Infuriating Heat", skill_id=1730, profession=LocalProfession.RANGER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Infuriating Heat", capture_function="skill_1730", start_map=424, icon_filename="[1730] - Infuriating Heat.jpg"),
EliteSkill(id="skill_1198", display_name="Broadhead Arrow", skill_id=1198, profession=LocalProfession.RANGER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Broadhead Arrow", capture_function="skill_1198", start_map=284, icon_filename="[1198] - Broadhead Arrow.jpg"),
EliteSkill(id="skill_465", display_name="Greater Conflagration", skill_id=465, profession=LocalProfession.RANGER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Greater Conflagration", capture_function="skill_465", start_map=35, icon_filename="[465] - Greater Conflagration.jpg"),
EliteSkill(id="skill_404", display_name="Poison Arrow", skill_id=404, profession=LocalProfession.RANGER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Poison Arrow", capture_function="skill_404", start_map=158, icon_filename="[404] - Poison Arrow.jpg"),
EliteSkill(id="skill_1465", display_name="Prepared Shot", skill_id=1465, profession=LocalProfession.RANGER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Prepared Shot", capture_function="skill_1465", start_map=642, icon_filename="[1465] - Prepared Shot.jpg"),
EliteSkill(id="skill_1200", display_name="Archer's Signet", skill_id=1200, profession=LocalProfession.RANGER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Archer's Signet", capture_function="skill_1200", start_map=129, icon_filename="[1200] - Archer's Signet.jpg"),
EliteSkill(id="skill_1199", display_name="Glass Arrows", skill_id=1199, profession=LocalProfession.RANGER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Glass Arrows", capture_function="skill_1199", start_map=130, icon_filename="[1199] - Glass Arrows.jpg"),
EliteSkill(id="skill_395", display_name="Barrage", skill_id=395, profession=LocalProfession.RANGER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Barrage", capture_function="skill_395", start_map=349, icon_filename="[395] - Barrage.jpg"),
EliteSkill(id="skill_1466", display_name="Burning Arrow", skill_id=1466, profession=LocalProfession.RANGER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Burning Arrow", capture_function="skill_1466", start_map=381, icon_filename="[1466] - Burning Arrow.jpg"),
EliteSkill(id="skill_393", display_name="Crippling Shot", skill_id=393, profession=LocalProfession.RANGER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Crippling Shot", capture_function="skill_393", start_map=640, icon_filename="[393] - Crippling Shot.jpg"),
EliteSkill(id="skill_1202", display_name="Enraged Lunge", skill_id=1202, profession=LocalProfession.RANGER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Enraged Lunge", capture_function="skill_1202", start_map=51, icon_filename="[1202] - Enraged Lunge.jpg"),
EliteSkill(id="skill_1212", display_name="Equinox", skill_id=1212, profession=LocalProfession.RANGER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Equinox", capture_function="skill_1212", start_map=284, icon_filename="[1212] - Equinox.jpg"),
EliteSkill(id="skill_448", display_name="Escape", skill_id=448, profession=LocalProfession.RANGER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Escape", capture_function="skill_448", start_map=224, icon_filename="[448] - Escape.jpg"),
EliteSkill(id="skill_1724", display_name="Expert's Dexterity", skill_id=1724, profession=LocalProfession.RANGER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Expert's Dexterity", capture_function="skill_1724", start_map=407, icon_filename="[1724] - Expert's Dexterity.jpg"),
EliteSkill(id="skill_997", display_name="Famine", skill_id=997, profession=LocalProfession.RANGER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Famine", capture_function="skill_997", start_map=226, icon_filename="[997] - Famine.jpg"),
EliteSkill(id="skill_442", display_name="Ferocious Strike", skill_id=442, profession=LocalProfession.RANGER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Ferocious Strike", capture_function="skill_442", start_map=273, icon_filename="[442] - Ferocious Strike.jpg"),
EliteSkill(id="skill_1195", display_name="Heal as One", skill_id=1195, profession=LocalProfession.RANGER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Heal as One", capture_function="skill_1195", start_map=390, icon_filename="[1195] - Heal as One.jpg"),
EliteSkill(id="skill_961", display_name="Lacerate", skill_id=961, profession=LocalProfession.RANGER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Lacerate", capture_function="skill_961", start_map=272, icon_filename="[961] - Lacerate.jpg"),
EliteSkill(id="skill_1726", display_name="Magebane Shot", skill_id=1726, profession=LocalProfession.RANGER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Magebane Shot", capture_function="skill_1726", start_map=442, icon_filename="[1726] - Magebane Shot.jpg"),
EliteSkill(id="skill_430", display_name="Marksman's Wager", skill_id=430, profession=LocalProfession.RANGER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Marksman's Wager", capture_function="skill_430", start_map=117, icon_filename="[430] - Marksman's Wager.jpg"),
EliteSkill(id="skill_429", display_name="Melandru's Arrows", skill_id=429, profession=LocalProfession.RANGER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Melandru's Arrows", capture_function="skill_429", start_map=159, icon_filename="[429] - Melandru's Arrows.jpg"),
EliteSkill(id="skill_853", display_name="Melandru's Shot", skill_id=853, profession=LocalProfession.RANGER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Melandru's Shot", capture_function="skill_853", start_map=193, icon_filename="[853] - Melandru's Shot.jpg"),
EliteSkill(id="skill_405", display_name="Oath Shot", skill_id=405, profession=LocalProfession.RANGER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Oath Shot", capture_function="skill_405", start_map=23, icon_filename="[405] - Oath Shot.jpg"),
EliteSkill(id="skill_397", display_name="Quick Shot", skill_id=397, profession=LocalProfession.RANGER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Quick Shot", capture_function="skill_397", start_map=425, icon_filename="[397] - Quick Shot.jpg"),
EliteSkill(id="skill_1473", display_name="Quicksand", skill_id=1473, profession=LocalProfession.RANGER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Quicksand", capture_function="skill_1473", start_map=442, icon_filename="[1473] - Quicksand.jpg"),
EliteSkill(id="skill_1721", display_name="Rampage as One", skill_id=1721, profession=LocalProfession.RANGER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Rampage as One", capture_function="skill_1721", start_map=387, icon_filename="[1721] - Rampage as One.jpg"),
EliteSkill(id="skill_1471", display_name="Scavenger's Focus", skill_id=1471, profession=LocalProfession.RANGER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Scavenger's Focus", capture_function="skill_1471", start_map=440, icon_filename="[1471] - Scavenger's Focus.jpg"),
EliteSkill(id="skill_1729", display_name="Smoke Trap", skill_id=1729, profession=LocalProfession.RANGER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Smoke Trap", capture_function="skill_1729", start_map=442, icon_filename="[1729] - Smoke Trap.jpg"),
EliteSkill(id="skill_461", display_name="Spike Trap", skill_id=461, profession=LocalProfession.RANGER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Spike Trap", capture_function="skill_461", start_map=219, icon_filename="[461] - Spike Trap.jpg"),
EliteSkill(id="skill_1468", display_name="Strike as One", skill_id=1468, profession=LocalProfession.RANGER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Strike as One", capture_function="skill_1468", start_map=421, icon_filename="[1468] - Strike as One.jpg"),
EliteSkill(id="skill_946", display_name="Trapper's Focus", skill_id=946, profession=LocalProfession.RANGER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Trapper's Focus", capture_function="skill_946", start_map=389, icon_filename="[946] - Trapper's Focus.jpg"),
EliteSkill(id="skill_294", display_name="Signet of Judgement", skill_id=294, profession=LocalProfession.MONK, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Signet of Judgement", capture_function="skill_294", start_map=155, icon_filename="[294] - Signet of Judgement.jpg"),
EliteSkill(id="skill_268", display_name="Unyielding Aura", skill_id=268, profession=LocalProfession.MONK, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Unyielding Aura", capture_function="skill_268", start_map=158, icon_filename="[268] - Unyielding Aura.jpg"),
EliteSkill(id="skill_273", display_name="Spell Breaker", skill_id=273, profession=LocalProfession.MONK, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Spell Breaker", capture_function="skill_273", start_map=155, icon_filename="[273] - Spell Breaker.jpg"),
EliteSkill(id="skill_1686", display_name="Glimmer of Light", skill_id=1686, profession=LocalProfession.MONK, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Glimmer of Light", capture_function="skill_1686", start_map=421, icon_filename="[1686] - Glimmer of Light.jpg"),
EliteSkill(id="skill_941", display_name="Blessed Light", skill_id=941, profession=LocalProfession.MONK, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Blessed Light", capture_function="skill_941", start_map=193, icon_filename="[941] - Blessed Light.jpg"),
EliteSkill(id="skill_867", display_name="Healing Light", skill_id=867, profession=LocalProfession.MONK, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Healing Light", capture_function="skill_867", start_map=193, icon_filename="[867] - Healing Light.jpg"),
EliteSkill(id="skill_847", display_name="Boon Signet", skill_id=847, profession=LocalProfession.MONK, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Boon Signet", capture_function="skill_847", start_map=388, icon_filename="[847] - Boon Signet.jpg"),
EliteSkill(id="skill_1393", display_name="Healer's Boon", skill_id=1393, profession=LocalProfession.MONK, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Healer's Boon", capture_function="skill_1393", start_map=403, icon_filename="[1393] - Healer's Boon.jpg"),
EliteSkill(id="skill_266", display_name="Peace and Harmony", skill_id=266, profession=LocalProfession.MONK, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Peace and Harmony", capture_function="skill_266", start_map=155, icon_filename="[266] - Peace and Harmony.jpg"),
EliteSkill(id="skill_942", display_name="Withdraw Hexes", skill_id=942, profession=LocalProfession.MONK, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Withdraw Hexes", capture_function="skill_942", start_map=389, icon_filename="[942] - Withdraw Hexes.jpg"),
EliteSkill(id="skill_1118", display_name="Healing Burst", skill_id=1118, profession=LocalProfession.MONK, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Healing Burst", capture_function="skill_1118", start_map=130, icon_filename="[1118] - Healing Burst.jpg"),
EliteSkill(id="skill_285", display_name="Healing Hands", skill_id=285, profession=LocalProfession.MONK, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Healing Hands", capture_function="skill_285", start_map=35, icon_filename="[285] - Healing Hands.jpg"),
EliteSkill(id="skill_1397", display_name="Light of Deliverance", skill_id=1397, profession=LocalProfession.MONK, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Light of Deliverance", capture_function="skill_1397", start_map=554, icon_filename="[1397] - Light of Deliverance.jpg"),
EliteSkill(id="skill_282", display_name="Word of Healing", skill_id=282, profession=LocalProfession.MONK, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Word of Healing", capture_function="skill_282", start_map=303, icon_filename="[282] - Word of Healing.jpg"),
EliteSkill(id="skill_1115", display_name="Air of Enchantment", skill_id=1115, profession=LocalProfession.MONK, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Air of Enchantment", capture_function="skill_1115", start_map=297, icon_filename="[1115] - Air of Enchantment.jpg"),
EliteSkill(id="skill_260", display_name="Aura of Faith", skill_id=260, profession=LocalProfession.MONK, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Aura of Faith", capture_function="skill_260", start_map=23, icon_filename="[260] - Aura of Faith.jpg"),
EliteSkill(id="skill_1692", display_name="Divert Hexes", skill_id=1692, profession=LocalProfession.MONK, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Divert Hexes", capture_function="skill_1692", start_map=480, icon_filename="[1692] - Divert Hexes.jpg"),
EliteSkill(id="skill_1123", display_name="Life Sheath", skill_id=1123, profession=LocalProfession.MONK, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Life Sheath", capture_function="skill_1123", start_map=284, icon_filename="[1123] - Life Sheath.jpg"),
EliteSkill(id="skill_261", display_name="Shield of Regeneration", skill_id=261, profession=LocalProfession.MONK, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Shield of Regeneration", capture_function="skill_261", start_map=648, icon_filename="[261] - Shield of Regeneration.jpg"),
EliteSkill(id="skill_1687", display_name="Zealous Benediction", skill_id=1687, profession=LocalProfession.MONK, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Zealous Benediction", capture_function="skill_1687", start_map=428, icon_filename="[1687] - Zealous Benediction.jpg"),
EliteSkill(id="skill_1688", display_name="Defender's Zeal", skill_id=1688, profession=LocalProfession.MONK, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Defender's Zeal", capture_function="skill_1688", start_map=469, icon_filename="[1688] - Defender's Zeal.jpg"),
EliteSkill(id="skill_830", display_name="Ray of Judgment", skill_id=830, profession=LocalProfession.MONK, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Ray of Judgment", capture_function="skill_830", start_map=303, icon_filename="[830] - Ray of Judgment.jpg"),
EliteSkill(id="skill_1129", display_name="Word of Censure", skill_id=1129, profession=LocalProfession.MONK, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Word of Censure", capture_function="skill_1129", start_map=303, icon_filename="[1129] - Word of Censure.jpg"),
EliteSkill(id="skill_1126", display_name="Empathic Removal", skill_id=1126, profession=LocalProfession.MONK, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Empathic Removal", capture_function="skill_1126", start_map=129, icon_filename="[1126] - Empathic Removal.jpg"),
EliteSkill(id="skill_298", display_name="Martyr", skill_id=298, profession=LocalProfession.MONK, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Martyr", capture_function="skill_298", start_map=442, icon_filename="[298] - Martyr.jpg"),
EliteSkill(id="skill_1690", display_name="Signet of Removal", skill_id=1690, profession=LocalProfession.MONK, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Signet of Removal", capture_function="skill_1690", start_map=427, icon_filename="[1690] - Signet of Removal.jpg"),
EliteSkill(id="skill_1395", display_name="Balthazar's Pendulum", skill_id=1395, profession=LocalProfession.MONK, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Balthazar's Pendulum", capture_function="skill_1395", start_map=378, icon_filename="[1395] - Balthazar's Pendulum.jpg"),
EliteSkill(id="skill_270", display_name="Life Barrier", skill_id=270, profession=LocalProfession.MONK, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Life Barrier", capture_function="skill_270", start_map=24, icon_filename="[270] - Life Barrier.jpg"),
EliteSkill(id="skill_832", display_name="Animate Flesh Golem", skill_id=832, profession=LocalProfession.NECROMANCER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Animate Flesh Golem", capture_function="skill_832", start_map=51, icon_filename="[832] - Animate Flesh Golem.jpg"),
EliteSkill(id="skill_1356", display_name="Contagion", skill_id=1356, profession=LocalProfession.NECROMANCER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Contagion", capture_function="skill_1356", start_map=425, icon_filename="[1356] - Contagion.jpg"),
EliteSkill(id="skill_86", display_name="Grenth's Balance", skill_id=86, profession=LocalProfession.NECROMANCER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Grenth's Balance", capture_function="skill_86", start_map=378, icon_filename="[86] - Grenth's Balance.jpg"),
EliteSkill(id="skill_1355", display_name="Jagged Bones", skill_id=1355, profession=LocalProfession.NECROMANCER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Jagged Bones", capture_function="skill_1355", start_map=643, icon_filename="[1355] - Jagged Bones.jpg"),
EliteSkill(id="skill_146", display_name="Offering of Blood", skill_id=146, profession=LocalProfession.NECROMANCER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Offering of Blood", capture_function="skill_146", start_map=22, icon_filename="[146] - Offering of Blood.jpg"),
EliteSkill(id="skill_148", display_name="Order of the Vampire", skill_id=148, profession=LocalProfession.NECROMANCER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Order of the Vampire", capture_function="skill_148", start_map=117, icon_filename="[148] - Order of the Vampire.jpg"),
EliteSkill(id="skill_1659", display_name="Toxic Chill", skill_id=1659, profession=LocalProfession.NECROMANCER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Toxic Chill", capture_function="skill_1659", start_map=433, icon_filename="[1659] - Toxic Chill.jpg"),
EliteSkill(id="skill_764", display_name="Wail of Doom", skill_id=764, profession=LocalProfession.NECROMANCER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Wail of Doom", capture_function="skill_764", start_map=226, icon_filename="[764] - Wail of Doom.jpg"),
EliteSkill(id="skill_822", display_name="Weaken Knees", skill_id=822, profession=LocalProfession.NECROMANCER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Weaken Knees", capture_function="skill_822", start_map=129, icon_filename="[822] - Weaken Knees.jpg"),
EliteSkill(id="skill_1066", display_name="Spoil Victor", skill_id=1066, profession=LocalProfession.NECROMANCER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Spoil Victor", capture_function="skill_1066", start_map=230, icon_filename="[1066] - Spoil Victor.jpg"),
EliteSkill(id="skill_126", display_name="Life Transfer", skill_id=126, profession=LocalProfession.NECROMANCER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Life Transfer", capture_function="skill_126", start_map=650, icon_filename="[126] - Life Transfer.jpg"),
EliteSkill(id="skill_121", display_name="Spiteful Spirit", skill_id=121, profession=LocalProfession.NECROMANCER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Spiteful Spirit", capture_function="skill_121", start_map=155, icon_filename="[121] - Spiteful Spirit.jpg"),
EliteSkill(id="skill_808", display_name="Reaper's Mark", skill_id=808, profession=LocalProfession.NECROMANCER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Reaper's Mark", capture_function="skill_808", start_map=378, icon_filename="[808] - Reaper's Mark.jpg"),
EliteSkill(id="skill_132", display_name="Plague Signet", skill_id=132, profession=LocalProfession.NECROMANCER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Plague Signet", capture_function="skill_132", start_map=640, icon_filename="[132] - Plague Signet.jpg"),
EliteSkill(id="skill_114", display_name="Aura of the Lich", skill_id=114, profession=LocalProfession.NECROMANCER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Aura of the Lich", capture_function="skill_114", start_map=35, icon_filename="[114] - Aura of the Lich.jpg"),
EliteSkill(id="skill_236", display_name="Mist Form", skill_id=236, profession=LocalProfession.ELEMENTALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Mist Form", capture_function="skill_236", start_map=155, icon_filename="[236] - Mist Form.jpg"),
EliteSkill(id="skill_218", display_name="Obsidian Flesh", skill_id=218, profession=LocalProfession.ELEMENTALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Obsidian Flesh", capture_function="skill_218", start_map=438, icon_filename="[218] - Obsidian Flesh.jpg"),
EliteSkill(id="skill_185", display_name="Mind Burn", skill_id=185, profession=LocalProfession.ELEMENTALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Mind Burn", capture_function="skill_185", start_map=217, icon_filename="[185] - Mind Burn.jpg"),
EliteSkill(id="skill_227", display_name="Glimmering Mark", skill_id=227, profession=LocalProfession.ELEMENTALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Glimmering Mark", capture_function="skill_227", start_map=158, icon_filename="[227] - Glimmering Mark.jpg"),
EliteSkill(id="skill_226", display_name="Mind Shock", skill_id=226, profession=LocalProfession.ELEMENTALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Mind Shock", capture_function="skill_226", start_map=155, icon_filename="[226] - Mind Shock.jpg"),
EliteSkill(id="skill_228", display_name="Thunderclap", skill_id=228, profession=LocalProfession.ELEMENTALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Thunderclap", capture_function="skill_228", start_map=23, icon_filename="[228] - Thunderclap.jpg"),
EliteSkill(id="skill_1378", display_name="Master of Magic", skill_id=1378, profession=LocalProfession.ELEMENTALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Master of Magic", capture_function="skill_1378", start_map=393, icon_filename="[1378] - Master of Magic.jpg"),
EliteSkill(id="skill_1664", display_name="Invoke Lightning", skill_id=1664, profession=LocalProfession.ELEMENTALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Invoke Lightning", capture_function="skill_1664", start_map=393, icon_filename="[1664] - Invoke Lightning.jpg"),
EliteSkill(id="skill_937", display_name="Shockwave", skill_id=937, profession=LocalProfession.ELEMENTALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Shockwave", capture_function="skill_937", start_map=272, icon_filename="[937] - Shockwave.jpg"),
EliteSkill(id="skill_1091", display_name="Double Dragon", skill_id=1091, profession=LocalProfession.ELEMENTALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Double Dragon", capture_function="skill_1091", start_map=303, icon_filename="[1091] - Double Dragon.jpg"),
EliteSkill(id="skill_1367", display_name="Blinding Surge", skill_id=1367, profession=LocalProfession.ELEMENTALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Blinding Surge", capture_function="skill_1367", start_map=433, icon_filename="[1367] - Blinding Surge.jpg"),
EliteSkill(id="skill_164", display_name="Elemental Attunement", skill_id=164, profession=LocalProfession.ELEMENTALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Elemental Attunement", capture_function="skill_164", start_map=477, icon_filename="[164] - Elemental Attunement.jpg"),
EliteSkill(id="skill_843", display_name="Gust", skill_id=843, profession=LocalProfession.ELEMENTALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Gust", capture_function="skill_843", start_map=287, icon_filename="[843] - Gust.jpg"),
EliteSkill(id="skill_205", display_name="Lightning Surge", skill_id=205, profession=LocalProfession.ELEMENTALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Lightning Surge", capture_function="skill_205", start_map=288, icon_filename="[205] - Lightning Surge.jpg"),
EliteSkill(id="skill_836", display_name="Ride the Lightning", skill_id=836, profession=LocalProfession.ELEMENTALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Ride the Lightning", capture_function="skill_836", start_map=650, icon_filename="[836] - Ride the Lightning.jpg"),
EliteSkill(id="skill_1372", display_name="Sandstorm", skill_id=1372, profession=LocalProfession.ELEMENTALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Sandstorm", capture_function="skill_1372", start_map=440, icon_filename="[1372] - Sandstorm.jpg"),
EliteSkill(id="skill_1373", display_name="Stone Sheath", skill_id=1373, profession=LocalProfession.ELEMENTALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Stone Sheath", capture_function="skill_1373", start_map=427, icon_filename="[1373] - Stone Sheath.jpg"),
EliteSkill(id="skill_1083", display_name="Unsteady Ground", skill_id=1083, profession=LocalProfession.ELEMENTALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Unsteady Ground", capture_function="skill_1083", start_map=288, icon_filename="[1083] - Unsteady Ground.jpg"),
EliteSkill(id="skill_837", display_name="Energy Boon", skill_id=837, profession=LocalProfession.ELEMENTALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Energy Boon", capture_function="skill_837", start_map=388, icon_filename="[837] - Energy Boon.jpg"),
EliteSkill(id="skill_1377", display_name="Ether Prism", skill_id=1377, profession=LocalProfession.ELEMENTALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Ether Prism", capture_function="skill_1377", start_map=442, icon_filename="[1377] - Ether Prism.jpg"),
EliteSkill(id="skill_181", display_name="Ether Renewal", skill_id=181, profession=LocalProfession.ELEMENTALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Ether Renewal", capture_function="skill_181", start_map=117, icon_filename="[181] - Ether Renewal.jpg"),
EliteSkill(id="skill_1662", display_name="Mind Blast", skill_id=1662, profession=LocalProfession.ELEMENTALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Mind Blast", capture_function="skill_1662", start_map=495, icon_filename="[1662] - Mind Blast.jpg"),
EliteSkill(id="skill_1380", display_name="Savannah Heat", skill_id=1380, profession=LocalProfession.ELEMENTALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Savannah Heat", capture_function="skill_1380", start_map=545, icon_filename="[1380] - Savannah Heat.jpg"),
EliteSkill(id="skill_884", display_name="Searing Flames", skill_id=884, profession=LocalProfession.ELEMENTALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Searing Flames", capture_function="skill_884", start_map=478, icon_filename="[884] - Searing Flames.jpg"),
EliteSkill(id="skill_1095", display_name="Star Burst", skill_id=1095, profession=LocalProfession.ELEMENTALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Star Burst", capture_function="skill_1095", start_map=226, icon_filename="[1095] - Star Burst.jpg"),
EliteSkill(id="skill_939", display_name="Icy Shackles", skill_id=939, profession=LocalProfession.ELEMENTALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Icy Shackles", capture_function="skill_939", start_map=424, icon_filename="[939] - Icy Shackles.jpg"),
EliteSkill(id="skill_209", display_name="Mind Freeze", skill_id=209, profession=LocalProfession.ELEMENTALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Mind Freeze", capture_function="skill_209", start_map=469, icon_filename="[209] - Mind Freeze.jpg"),
EliteSkill(id="skill_1098", display_name="Mirror of Ice", skill_id=1098, profession=LocalProfession.ELEMENTALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Mirror of Ice", capture_function="skill_1098", start_map=284, icon_filename="[1098] - Mirror of Ice.jpg"),
EliteSkill(id="skill_809", display_name="Shatterstone", skill_id=809, profession=LocalProfession.ELEMENTALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Shatterstone", capture_function="skill_809", start_map=130, icon_filename="[809] - Shatterstone.jpg"),
EliteSkill(id="skill_237", display_name="Water Trident", skill_id=237, profession=LocalProfession.ELEMENTALIST, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Water Trident", capture_function="skill_237", start_map=642, icon_filename="[237] - Water Trident.jpg"),
EliteSkill(id="skill_1350", display_name="Simple Thievery", skill_id=1350, profession=LocalProfession.MESMER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Simple Thievery", capture_function="skill_1350", start_map=376, icon_filename="[1350] - Simple Thievery.jpg"),
EliteSkill(id="skill_1057", display_name="Psychic Instability", skill_id=1057, profession=LocalProfession.MESMER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Psychic Instability", capture_function="skill_1057", start_map=277, icon_filename="[1057] - Psychic Instability.jpg"),
EliteSkill(id="skill_1342", display_name="Tease", skill_id=1342, profession=LocalProfession.MESMER, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Tease", capture_function="skill_1342", start_map=393, icon_filename="[1342] - Tease.jpg"),
EliteSkill(id="skill_269", display_name="Mark of Protection", skill_id=269, profession=LocalProfession.MONK, type=LocalEliteSkillType.ELITE_SKILL, step_name="[H]Mark of Protection", capture_function="skill_269", start_map=38, icon_filename="[269] - Mark of Protection.jpg"),

]
