from __future__ import annotations

from collections.abc import Generator
import importlib
import inspect
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, cast

from .build_src.combat_services import CombatServices

if TYPE_CHECKING:
    from HeroAI.custom_skill import CustomSkillClass
    from HeroAI.custom_skill_src.skill_types import CustomSkill
    from Py4GWCoreLib import Profession

BuildCoroutine = Generator[None, None, Any]
BuildHandler = Callable[[], Any]
TargetPredicate = Callable[[int], bool]
CustomSkillMutator = Callable[["CustomSkill"], None]

#region BuildMgr
class BuildMgr(CombatServices):
    from Py4GWCoreLib import Profession

    def __init__(
        self,
        name: str = "Generic Build",
        required_primary: Profession | None = None,
        required_secondary: Profession | None = None,
        template_code: str = "AAAAAAAAAAAAAAAA",
        required_skills: list[int] | None = None,
        optional_skills: list[int] | None = None,
        skills: list[int] | None = None,
        fallback_name: str | None = None,
        fallback_handler: "BuildMgr | None" = None,
        is_fallback_candidate: bool = False,
        IsFixedBuild: bool = False,
        is_combat_automator_compatible: bool = True,
        is_template_only: bool = False,
    ):
        from Py4GWCoreLib import Profession
        from Py4GWCoreLib import ThrottledTimer
        self.build_name = name
        self.required_primary: Profession = required_primary if required_primary is not None else Profession(0)
        self.required_secondary: Profession = required_secondary if required_secondary is not None else Profession(0)
        self.template_code = template_code
        legacy_skills = list(skills or [])
        self.required_skills = list(required_skills if required_skills is not None else legacy_skills)
        self.optional_skills = list(optional_skills or [])
        self.skills = list(self.required_skills)
        self.default_fallback_name = fallback_name
        self.current_fallback_name = fallback_name
        self.default_fallback_handler = fallback_handler
        self.current_fallback_handler = fallback_handler
        self.is_fallback_candidate = is_fallback_candidate
        self.IsFixedBuild = IsFixedBuild
        self.is_combat_automator_compatible = is_combat_automator_compatible
        self.is_template_only = is_template_only
        self.blocked_skills: list[int] = []
        self.priority_target = 0
        self._local_skill_casting_handler: BuildHandler | None = None
        self._local_ooc_handler: BuildHandler | None = None
        self._local_combat_handler: BuildHandler | None = None
        self._custom_skill_data_handler: CustomSkillClass | None = None
        self._cached_data: Any = None

        self.minimum_required_match = len(self.required_skills)
        self.tick_state = None
        self.current_target_id = 0
        self._was_in_aggro = False
        self._local_cast_timer = ThrottledTimer(0)
        self._local_cast_timer.Stop()
        self._auto_attack_timer = ThrottledTimer(0)
        self._auto_attack_timer.Stop()
        self._auto_attack_time = 0
        self._party_health_monitor: dict[int, dict[str, float]] = {}
        self._party_health_monitor_timer = ThrottledTimer(150)
        self._party_health_monitor_timer.Stop()
        self._party_health_monitor_window_ms = 1000

    def set_cached_data(self, cached_data: Any) -> None:
        """
        Optional hook for builds that need external cached runtime state.

        The base implementation stores the shared runtime cache so concrete
        builds can access HeroAI-backed helpers without reimplementing the hook.
        """
        self._cached_data = cached_data

        
    def ValidatePrimary(self, profession: Profession) -> bool:
        return self.required_primary == profession

    def ValidateSecondary(self, profession: Profession) -> bool:
        return self.required_secondary == profession

    def _get_current_skills(self) -> list[int]:
        from Py4GWCoreLib.Skillbar import SkillBar

        skills: list[int] = []
        for i in range(8):
            skill = SkillBar.GetSkillIDBySlot(i + 1)
            if skill:
                skills.append(skill)
        return skills

    def ScoreMatch(
        self,
        current_primary=None,
        current_secondary=None,
        current_skills: list[int] | None = None,
    ) -> int:
        from Py4GWCoreLib import Player, Agent, Profession

        if current_primary is None or current_secondary is None:
            player_id = Player.GetAgentID()
            primary_value, secondary_value = Agent.GetProfessions(player_id)
            current_primary = current_primary if current_primary is not None else Profession(primary_value)
            current_secondary = current_secondary if current_secondary is not None else Profession(secondary_value)

        if current_skills is None:
            current_skills = self._get_current_skills()

        required_skills = [skill for skill in self.required_skills if skill]
        optional_skills = [skill for skill in self.optional_skills if skill and skill not in required_skills]
        current_skill_set = set(skill for skill in current_skills if skill)

        any_profession = Profession(0)
        primary_matches = self.required_primary in (any_profession, current_primary)
        secondary_matches = self.required_secondary in (any_profession, current_secondary)
        if not self.is_combat_automator_compatible or not primary_matches or not secondary_matches:
            return -1

        required_hits = sum(1 for skill in required_skills if skill in current_skill_set)
        minimum_required_hits = min(self.minimum_required_match, len(required_skills))
        if required_hits < minimum_required_hits:
            return -1

        optional_hits = sum(1 for skill in optional_skills if skill in current_skill_set)
        return required_hits + optional_hits

    def ValidateSkills(self) -> Generator[None, None, bool]:
        from Py4GWCoreLib import Routines
        skills = self._get_current_skills()

        all_valid = sorted(self.skills) == sorted(skills)

        if not all_valid:
            wait_interval = 1000
        else:
            wait_interval = 0
        yield from Routines.Yield.wait(wait_interval)
        return all_valid

    def SetFallback(self, fallback_name: str | None = None, fallback_handler: "BuildMgr | None" = None) -> None:
        self.current_fallback_name = fallback_name
        self.current_fallback_handler = fallback_handler

    def SetBlockedSkills(self, skill_ids: list[int] | None = None) -> None:
        self.blocked_skills = [int(skill_id) for skill_id in (skill_ids or []) if int(skill_id) != 0]

    def GetSupportedSkills(self) -> list[int]:
        supported_skills: list[int] = []
        for skill_id in self.required_skills + self.optional_skills:
            skill_id = int(skill_id)
            if skill_id == 0 or skill_id in supported_skills:
                continue
            supported_skills.append(skill_id)
        return supported_skills

    def GetBlockedSkills(self) -> list[int]:
        blocked_skills: list[int] = []
        for skill_id in self.GetSupportedSkills() + self.blocked_skills:
            skill_id = int(skill_id)
            if skill_id == 0 or skill_id in blocked_skills:
                continue
            blocked_skills.append(skill_id)
        return blocked_skills

    def ApplyBlockedSkillIDs(self, blocked_skill_ids: list[int] | None = None) -> None:
        pass

    def SetOOCFn(self, handler: BuildHandler | None) -> None:
        self._local_ooc_handler = handler

    def SetCombatFn(self, handler: BuildHandler | None) -> None:
        self._local_combat_handler = handler

    def SetSkillCastingFn(self, handler: BuildHandler | None) -> None:
        self._local_skill_casting_handler = handler

    def CanProcess(self) -> bool:
        from Py4GWCoreLib import Agent, Player, Routines

        return (
            Routines.Checks.Map.MapValid()
            and Routines.Checks.Map.IsExplorable()
            and Routines.Checks.Player.CanAct()
            and not Agent.IsDead(Player.GetAgentID())
        )










    
    






















    







    










    def _yield_from_handler(self, handler: BuildHandler | None) -> BuildCoroutine:
        if handler is None:
            yield
            return None

        result = handler()
        if inspect.isgenerator(result):
            return (yield from result)
        return result

    def _process_phase(self, handler: BuildHandler | None, is_in_combat: bool) -> BuildCoroutine:
        # Whiteboard owner self-clear — release my (skill, target) slots on
        # the cast-finish transition so sibling accounts can reuse them
        # immediately. Lives here (not in Tick) because HeroAI's BT path
        # calls ProcessCombat/ProcessOOC directly and bypasses Tick.
        self._whiteboard_owner_self_clear()
        if not self.CanProcess():
            reasons: list[str] = []
            from Py4GWCoreLib import Agent, Player, Routines

            if not Routines.Checks.Map.MapValid():
                reasons.append("map invalid")
            if not Routines.Checks.Map.IsExplorable():
                reasons.append("not explorable")
            if not Routines.Checks.Player.CanAct():
                reasons.append("player cannot act")
            if Agent.IsDead(Player.GetAgentID()):
                reasons.append("player dead")
            if not reasons:
                reasons.append("unknown")
            yield
            return

        self.ResetTickState()
        self._refresh_target_tracking()
        yield from self._yield_from_handler(handler)

        if self.DidTickSucceed():
            return

        fallback = self.ResolveFallback()
        if fallback is not None:
            if is_in_combat:
                yield from fallback.ProcessCombat()
            else:
                yield from fallback.ProcessOOC()
            return

        yield

    def _process_skill_casting_phase(
        self,
        handler: BuildHandler | None,
        is_in_combat: bool | None = None,
    ) -> BuildCoroutine:
        self._whiteboard_owner_self_clear()
        if not self.CanProcess():
            yield
            return

        self.ResetTickState()
        self._refresh_target_tracking()
        handler_result = yield from self._yield_from_handler(handler)

        if self.DidTickSucceed():
            return

        if handler_result is True:
            self.SetTickSuccess()
            return

        fallback = self.ResolveFallback()
        if fallback is not None:
            if is_in_combat is True:
                yield from fallback.ProcessCombat()
            elif is_in_combat is False:
                yield from fallback.ProcessOOC()
            else:
                yield from fallback.ProcessSkillCasting()
            return

        yield

    def _apply_fallback_skill_mask(self, fallback_handler: "BuildMgr | None") -> None:
        if fallback_handler is None:
            return
        fallback_handler.ApplyBlockedSkillIDs(self.GetBlockedSkills())

    def ResetFallback(self) -> None:
        self.current_fallback_name = self.default_fallback_name
        self.current_fallback_handler = self.default_fallback_handler

    def ResolveFallback(self) -> "BuildMgr | None":
        if self.current_fallback_handler is not None:
            self._apply_fallback_skill_mask(self.current_fallback_handler)
            return self.current_fallback_handler
        return None

    def set_fsm(self, fsm) -> None:
        pass

    def set_bot(self, bot) -> None:
        pass

    def set_debug_fn(self, fn: Callable[[], bool]) -> None:
        pass

    def ResetTickState(self) -> None:
        self.tick_state = None

    def SetTickSuccess(self) -> None:
        from Py4GWCoreLib.py4gwcorelib_src.BehaviorTree import BehaviorTree

        self.tick_state = BehaviorTree.NodeState.SUCCESS

    def SetTickFailure(self) -> None:
        from Py4GWCoreLib.py4gwcorelib_src.BehaviorTree import BehaviorTree

        self.tick_state = BehaviorTree.NodeState.FAILURE

    def DidTickSucceed(self) -> bool:
        return getattr(self.tick_state, "name", None) == "SUCCESS"


    #region Whiteboard (cross-hero cast-intent coordination)











    def ProcessSkillCasting(self) -> BuildCoroutine:
        if self._local_skill_casting_handler is not None:
            yield from self._process_skill_casting_phase(self._local_skill_casting_handler)
            return

        if self._local_ooc_handler is None and self._local_combat_handler is None:
            raise NotImplementedError

        from Py4GWCoreLib.botting_src.helpers_src.HeroAICombatRange import hero_ai_combat_detected

        if hero_ai_combat_detected():
            yield from self.ProcessCombat()
        else:
            yield from self.ProcessOOC()

    def ProcessOOC(self) -> BuildCoroutine:
        if self._local_ooc_handler is None:
            yield from self.ProcessSkillCasting()
            return
        yield from self._process_phase(self._local_ooc_handler, is_in_combat=False)

    def ProcessCombat(self) -> BuildCoroutine:
        if self._local_combat_handler is None:
            yield from self.ProcessSkillCasting()
            return
        yield from self._process_phase(self._local_combat_handler, is_in_combat=True)

    def Tick(self, is_in_combat: bool):
        # Clear whiteboard intent slots on the cast-finish transition so
        # sibling accounts can reuse the (skill, target) as soon as my
        # local cast window has closed.
        self._whiteboard_owner_self_clear()
        if is_in_combat:
            yield from self.ProcessCombat()
        else:
            yield from self.ProcessOOC()
    
    def LoadSkillBar(self) -> Generator[Any, Any, None]:
        from Py4GWCoreLib import Routines
        """
        Load the skill bar with the build's template code.
        This method can be overridden in child classes if needed.
        """
        yield from Routines.Yield.Skills.LoadSkillbar(self.template_code, log=False)
        


#region BuildRegistry
class BuildRegistry:
    _cached_build_types: list[type[BuildMgr]] | None = None

    def __init__(self, default_fallback_name: str | None = None, build_init_kwargs: dict[str, Any] | None = None):
        self.default_fallback_name = default_fallback_name
        self.build_init_kwargs = dict(build_init_kwargs or {})
        self._runtime_build_instances: dict[type[BuildMgr], BuildMgr | None] = {}
        self._match_only_build_instances: dict[type[BuildMgr], BuildMgr | None] = {}
        self._cached_runtime_builds: list[BuildMgr] | None = None
        self._cached_match_only_builds: list[BuildMgr] | None = None
        self._cached_runtime_matchable_builds: list[BuildMgr] | None = None
        self._cached_match_only_matchable_builds: list[BuildMgr] | None = None
        self._cached_runtime_fallback_builds: list[BuildMgr] | None = None
        self._cached_match_only_fallback_builds: list[BuildMgr] | None = None

    @classmethod
    def _scan_build_types(cls) -> list[type[BuildMgr]]:
        builds_pkg = importlib.import_module("Py4GWCoreLib.Builds")
        build_types: list[type[BuildMgr]] = []

        seen_module_names: set[str] = set()
        for module_path in Path(builds_pkg.__path__[0]).rglob("*.py"):
            if module_path.name == "__init__.py":
                continue

            relative_path = module_path.relative_to(builds_pkg.__path__[0]).with_suffix("")
            module_name = ".".join((builds_pkg.__name__, *relative_path.parts))
            if module_name in seen_module_names:
                continue
            seen_module_names.add(module_name)

            module = importlib.import_module(module_name)
            for _, value in inspect.getmembers(module, inspect.isclass):
                if value is BuildMgr:
                    continue
                if value.__module__ != module.__name__:
                    continue
                if not issubclass(value, BuildMgr):
                    continue
                build_types.append(value)

        return build_types

    @classmethod
    def GetBuildTypes(cls) -> list[type[BuildMgr]]:
        if cls._cached_build_types is None:
            cls._cached_build_types = cls._scan_build_types()
        return list(cls._cached_build_types)

    @classmethod
    def ClearCache(cls) -> None:
        cls._cached_build_types = None

    def _call_build_ctor(self, build_type: type[BuildMgr], *args: Any, **kwargs: Any) -> BuildMgr | None:
        try:
            ctor = cast(Any, build_type)
            build = ctor(*args, **kwargs)
        except TypeError:
            return None
        return cast(BuildMgr | None, build)

    def _instantiate_build(self, build_type: type[BuildMgr], match_only: bool = False) -> BuildMgr | None:
        cache = self._match_only_build_instances if match_only else self._runtime_build_instances

        if build_type in cache:
            build = cache[build_type]
            if build is not None and "cached_data" in self.build_init_kwargs and hasattr(build, "set_cached_data"):
                build.set_cached_data(self.build_init_kwargs["cached_data"])
            return build

        if match_only:
            build = self._call_build_ctor(build_type, match_only=True, **self.build_init_kwargs)
            if build is None:
                build = self._call_build_ctor(build_type, match_only=True)
            if build is None:
                build = self._call_build_ctor(build_type, **self.build_init_kwargs)
            if build is None:
                build = self._call_build_ctor(build_type)
        else:
            build = self._call_build_ctor(build_type, **self.build_init_kwargs)
            if build is None:
                build = self._call_build_ctor(build_type)

        if build is not None and "cached_data" in self.build_init_kwargs and hasattr(build, "set_cached_data"):
            build.set_cached_data(self.build_init_kwargs["cached_data"])

        cache[build_type] = build
        return build

    def _iter_builds(self, match_only: bool = False) -> list[BuildMgr]:
        cached_builds = self._cached_match_only_builds if match_only else self._cached_runtime_builds
        if cached_builds is not None:
            return list(cached_builds)

        builds: list[BuildMgr] = []
        for build_type in self.GetBuildTypes():
            build = self._instantiate_build(build_type, match_only=match_only)
            if build is not None:
                builds.append(build)

        if match_only:
            self._cached_match_only_builds = builds
            return list(self._cached_match_only_builds)

        self._cached_runtime_builds = builds
        return list(self._cached_runtime_builds)

    def _iter_matchable_builds(self, match_only: bool = False) -> list[BuildMgr]:
        cached_builds = self._cached_match_only_matchable_builds if match_only else self._cached_runtime_matchable_builds
        if cached_builds is not None:
            return list(cached_builds)

        matchable_builds: list[BuildMgr] = []
        for build in self._iter_builds(match_only=match_only):
            if build.is_template_only:
                continue
            if build.is_fallback_candidate:
                continue
            if build.IsFixedBuild:
                continue
            if not build.is_combat_automator_compatible:
                continue
            matchable_builds.append(build)

        if match_only:
            self._cached_match_only_matchable_builds = matchable_builds
            return list(self._cached_match_only_matchable_builds)

        self._cached_runtime_matchable_builds = matchable_builds
        return list(self._cached_runtime_matchable_builds)

    def _iter_fallback_builds(self, match_only: bool = False) -> list[BuildMgr]:
        cached_builds = self._cached_match_only_fallback_builds if match_only else self._cached_runtime_fallback_builds
        if cached_builds is not None:
            return list(cached_builds)

        fallback_builds: list[BuildMgr] = []
        for build in self._iter_builds(match_only=match_only):
            if build.is_fallback_candidate:
                fallback_builds.append(build)

        if match_only:
            self._cached_match_only_fallback_builds = fallback_builds
            return list(self._cached_match_only_fallback_builds)

        self._cached_runtime_fallback_builds = fallback_builds
        return list(self._cached_runtime_fallback_builds)

    def ResolveFallback(self, fallback_name: str | None = None) -> BuildMgr | None:
        requested_name = (fallback_name or self.default_fallback_name or "").strip().casefold()
        fallback_builds = self._iter_fallback_builds(match_only=True)

        if requested_name:
            for build in fallback_builds:
                if build.build_name.casefold() == requested_name or build.__class__.__name__.casefold() == requested_name:
                    return self._instantiate_build(build.__class__)

        if fallback_builds:
            return self._instantiate_build(fallback_builds[0].__class__)

        return None

    def GetBestBuild(
        self,
        current_primary=None,
        current_secondary=None,
        current_skills: list[int] | None = None,
        fallback_name: str | None = None,
    ) -> BuildMgr | None:
        best_build_type: type[BuildMgr] | None = None
        best_score = -1

        for build in self._iter_matchable_builds(match_only=True):
            if build.is_template_only:
                continue
            score = build.ScoreMatch(
                current_primary=current_primary,
                current_secondary=current_secondary,
                current_skills=current_skills,
            )
            if score > best_score:
                best_score = score
                best_build_type = build.__class__

        if best_build_type is not None:
            return self._instantiate_build(best_build_type)

        return self.ResolveFallback(fallback_name=fallback_name)

    def ResolveBuild(
        self,
        current_primary=None,
        current_secondary=None,
        current_skills: list[int] | None = None,
        fallback_name: str | None = None,
    ) -> BuildMgr | None:
        return self.GetBestBuild(
            current_primary=current_primary,
            current_secondary=current_secondary,
            current_skills=current_skills,
            fallback_name=fallback_name,
        )
