from typing import TYPE_CHECKING
from typing import Callable
from typing import Sequence

from ..py4gwcorelib_src.BehaviorTree import BehaviorTree

if TYPE_CHECKING:
    from ..BTBuildMgr import BTBuildMgr


class BottingTreeUpkeepMixin:
    def SetServiceTrees(
        self,
        steps: Sequence[tuple[str, Callable[[], object] | object]],
    ):
        self._service_steps = list(steps)
        self._service_trees = [
            (step_name, self._coerce_runtime_tree(subtree_or_builder))
            for step_name, subtree_or_builder in self._service_steps
        ]
        self._rebuild_root_tree()

    def AddServiceTree(self, name: str, subtree_or_builder: Callable[[], object] | object):
        self._service_steps.append((name, subtree_or_builder))
        self._service_trees.append((name, self._coerce_runtime_tree(subtree_or_builder)))
        self._rebuild_root_tree()

    def ClearServiceTrees(self):
        self._service_steps = []
        self._service_trees = []
        self._rebuild_root_tree()

    def GetServiceTreeNames(self) -> list[str]:
        return [step_name for step_name, _ in self._service_steps]

    def SetUpkeepTrees(
        self,
        steps: Sequence[tuple[str, Callable[[], object] | object]],
    ):
        self.SetServiceTrees(steps)

    def AddUpkeepTree(self, name: str, subtree_or_builder: Callable[[], object] | object):
        self.AddServiceTree(name, subtree_or_builder)

    def ClearUpkeepTrees(self):
        self.ClearServiceTrees()

    def GetUpkeepTreeNames(self) -> list[str]:
        return self.GetServiceTreeNames()

    def AddBuild(self, build: "BTBuildMgr") -> None:
        self.AddServiceTree(f"Build:{build.build_name}", build.get_rotation_tree)

    def AddSummoningStonePartyService(
        self,
        *,
        enabled: bool | Callable[[], bool] = True,
        map_ids: Sequence[int] | None = None,
        initial_grace_ms: float = 3000.0,
        attempt_interval_ms: float = 5000.0,
        retry_cycle_delay_ms: float = 15000.0,
        log: bool = True,
    ) -> None:
        self.AddServiceTree(
            'SummoningStonePartyService',
            lambda: self.SummoningStonePartyServiceTree(
                enabled=enabled,
                map_ids=map_ids,
                initial_grace_ms=initial_grace_ms,
                attempt_interval_ms=attempt_interval_ms,
                retry_cycle_delay_ms=retry_cycle_delay_ms,
                log=log,
            ),
        )

    def EnsureSummoningStonePartyService(
        self,
        *,
        enabled: bool | Callable[[], bool] = True,
        map_ids: Sequence[int] | None = None,
        initial_grace_ms: float = 3000.0,
        attempt_interval_ms: float = 5000.0,
        retry_cycle_delay_ms: float = 15000.0,
        log: bool = True,
    ) -> None:
        subtree_or_builder = lambda: self.SummoningStonePartyServiceTree(
            enabled=enabled,
            map_ids=map_ids,
            initial_grace_ms=initial_grace_ms,
            attempt_interval_ms=attempt_interval_ms,
            retry_cycle_delay_ms=retry_cycle_delay_ms,
            log=log,
        )
        for index, (service_name, _existing) in enumerate(self._service_steps):
            if service_name != 'SummoningStonePartyService':
                continue
            self._service_steps[index] = (service_name, subtree_or_builder)
            self._service_trees[index] = (service_name, self._coerce_runtime_tree(subtree_or_builder))
            self._rebuild_root_tree()
            return
        self.AddServiceTree('SummoningStonePartyService', subtree_or_builder)

    def AddPartyMemberRecoveryService(
        self,
        *,
        enabled: bool | Callable[[], bool] = True,
        regroup_distance: float = 500.0,
        move_tolerance: float = 100.0,
        retry_interval_ms: float = 2000.0,
        wait_log_interval_ms: float = 15000.0,
        log: bool = True,
    ) -> None:
        self.AddServiceTree(
            'PartyMemberRecoveryService',
            lambda: self.PartyMemberRecoveryServiceTree(
                enabled=enabled,
                regroup_distance=regroup_distance,
                move_tolerance=move_tolerance,
                retry_interval_ms=retry_interval_ms,
                wait_log_interval_ms=wait_log_interval_ms,
                log=log,
            ),
        )

    def EnsurePartyMemberRecoveryService(
        self,
        *,
        enabled: bool | Callable[[], bool] = True,
        regroup_distance: float = 500.0,
        move_tolerance: float = 100.0,
        retry_interval_ms: float = 2000.0,
        wait_log_interval_ms: float = 15000.0,
        log: bool = True,
    ) -> None:
        subtree_or_builder = lambda: self.PartyMemberRecoveryServiceTree(
            enabled=enabled,
            regroup_distance=regroup_distance,
            move_tolerance=move_tolerance,
            retry_interval_ms=retry_interval_ms,
            wait_log_interval_ms=wait_log_interval_ms,
            log=log,
        )
        for index, (service_name, _existing) in enumerate(self._service_steps):
            if service_name != 'PartyMemberRecoveryService':
                continue
            self._service_steps[index] = (service_name, subtree_or_builder)
            self._service_trees[index] = (service_name, self._coerce_runtime_tree(subtree_or_builder))
            self._rebuild_root_tree()
            return
        self.AddServiceTree('PartyMemberRecoveryService', subtree_or_builder)

    def AddPartyWipeRecoveryService(
        self,
        default_step_name: str | Callable[[], str | None] | None = None,
        return_interval_ms: float = 1000.0,
        shrine_step_resolver: Callable[[int, tuple[float, float], str], tuple[str, float] | str | None] | None = None,
    ) -> None:
        self.AddServiceTree(
            'PartyWipeRecoveryService',
            lambda: self.PartyWipeRecoveryServiceTree(
                default_step_name=default_step_name,
                return_interval_ms=return_interval_ms,
                shrine_step_resolver=shrine_step_resolver,
            ),
        )

    def EnsurePartyWipeRecoveryService(
        self,
        default_step_name: str | Callable[[], str | None] | None = None,
        return_interval_ms: float = 1000.0,
        shrine_step_resolver: Callable[[int, tuple[float, float], str], tuple[str, float] | str | None] | None = None,
    ) -> None:
        subtree_or_builder = lambda: self.PartyWipeRecoveryServiceTree(
            default_step_name=default_step_name,
            return_interval_ms=return_interval_ms,
            shrine_step_resolver=shrine_step_resolver,
        )
        for index, (service_name, _existing) in enumerate(self._service_steps):
            if service_name != 'PartyWipeRecoveryService':
                continue
            self._service_steps[index] = (service_name, subtree_or_builder)
            self._service_trees[index] = (service_name, self._coerce_runtime_tree(subtree_or_builder))
            self._rebuild_root_tree()
            return
        self.AddServiceTree('PartyWipeRecoveryService', subtree_or_builder)
