from collections.abc import Sequence as RuntimeSequence
from typing import TYPE_CHECKING, Callable, Sequence, cast

from ..py4gwcorelib_src.BehaviorTree import BehaviorTree


class BottingTreePlannerMixin:
    _service_trees: list[tuple[str, BehaviorTree]]
    planner_tree: BehaviorTree
    tree: BehaviorTree
    _planner_steps: list[tuple[str, Callable[[], object] | object]]
    _planner_recovery_anchors: dict[str, tuple[int, float, float]]
    _planner_recovery_pass_id: int
    _planner_shrine_recovery_checkpoints: dict[str, str]
    _active_planner_shrine_recovery_checkpoint: tuple[int, str, str] | None
    _nearest_shrine_recovery_enabled: bool
    _planner_sequence_name: str
    planner_repeat: bool

    if TYPE_CHECKING:
        def Start(self) -> None: ...

        def Reset(self) -> None: ...

        def GetBlackboardValue(self, key: str, default=None): ...

        def SetBlackboardValue(self, key: str, value) -> None: ...

        def ClearBlackboardValue(self, key: str) -> None: ...

        def _tick_heroai(self, node: BehaviorTree.Node) -> BehaviorTree.NodeState: ...

        def _tick_planner(self, node: BehaviorTree.Node) -> BehaviorTree.NodeState: ...

        def _tick_service_tree(self, node: BehaviorTree.Node, service_tree: BehaviorTree, service_name: str) -> BehaviorTree.NodeState: ...

    def _build_default_planner_tree(self) -> BehaviorTree:
        return BehaviorTree(
            root=BehaviorTree.ActionNode(
                name='DefaultPlannerTick',
                action_fn=lambda node: BehaviorTree.NodeState.RUNNING,
            )
        )

    def _build_parallel_tree(self) -> BehaviorTree:
        heroai_branch = BehaviorTree.RepeaterForeverNode(
            BehaviorTree.ActionNode(
                name='HeroAIServiceTick',
                action_fn=lambda node: self._tick_heroai(node),
            ),
            name='HeroAIService',
        )

        planner_branch = BehaviorTree.RepeaterForeverNode(
            BehaviorTree.ActionNode(
                name='PlannerServiceTick',
                action_fn=lambda node: self._tick_planner(node),
            ),
            name='PlannerService',
        )

        service_branches = [
            BehaviorTree.RepeaterForeverNode(
                BehaviorTree.ActionNode(
                    name=f'{service_name}Tick',
                    action_fn=lambda node, service_tree=service_tree, service_name=service_name: self._tick_service_tree(
                        node,
                        service_tree,
                        service_name,
                    ),
                ),
                name=service_name,
            )
            for service_name, service_tree in self._service_trees
        ]

        return BehaviorTree(
            root=BehaviorTree.ParallelNode(
                children=[heroai_branch, planner_branch, *service_branches],
                name='Root',
            )
        )

    def ProcessRestartRequest(self) -> bool:
        restart_step_name = str(
            self.GetBlackboardValue(
                "restart_step_name_request",
                "",
            )
            or ""
        )

        if not restart_step_name:
            return False

        # A wipe restart rebuilds the planner and Start() clears the blackboard.
        # Capture the recovery metadata before that reset, then restore the useful
        # read-only context afterwards for restart-safe script mechanics.
        restart_reason = str(
            self.GetBlackboardValue(
                "restart_step_reason_request",
                "",
            )
            or ""
        )
        restart_origin_step = str(
            self.GetBlackboardValue(
                "restart_step_origin_step_name_request",
                "",
            )
            or ""
        )

        self.ClearBlackboardValue(
            "restart_step_name_request"
        )
        self.ClearBlackboardValue(
            "restart_step_reason_request"
        )
        self.ClearBlackboardValue(
            "restart_step_origin_step_name_request"
        )

        # Ne pas effacer l'étape active avant que le nouveau
        # Planner ait été construit.
        restarted = self.RestartFromNamedPlannerStep(
            restart_step_name,
            auto_start=True,
        )

        if restarted:
            self.SetBlackboardValue(
                "current_step_name",
                restart_step_name,
            )

            self.SetBlackboardValue(
                "last_active_planner_step_name",
                restart_step_name,
            )

            if restart_reason:
                self.SetBlackboardValue(
                    "planner_restart_reason",
                    restart_reason,
                )
                self.SetBlackboardValue(
                    "planner_restart_origin_step_name",
                    restart_origin_step,
                )
                self.SetBlackboardValue(
                    "planner_restart_target_step_name",
                    restart_step_name,
                )

        return restarted

    def tick(self):
        result = self.tree.tick()
        self.ProcessRestartRequest()
        return result

    def _rebuild_root_tree(self):
        blackboard = dict(self.tree.blackboard) if hasattr(self, 'tree') and self.tree is not None else {}
        self.tree = self._build_parallel_tree()
        self.tree.blackboard.update(blackboard)

    def _set_planner_tree(self, planner_tree: BehaviorTree | None):
        self.planner_tree = planner_tree or self._build_default_planner_tree()

    def SetPlannerTree(self, planner_tree: BehaviorTree | None):
        self._planner_steps = []
        self._planner_recovery_anchors.clear()
        self._planner_recovery_pass_id = 0
        self._planner_sequence_name = 'PlannerSequence'
        self._set_planner_tree(planner_tree)

    def SetCurrentTree(
        self,
        planner_tree: BehaviorTree | None,
        auto_start: bool = False,
        reset: bool = True,
    ):
        self.SetPlannerTree(planner_tree)
        if auto_start:
            self.Start()
        elif reset:
            self.Reset()

    def _build_sequence_from_children(
        self,
        children: Sequence[object],
        name: str = 'MainRoutine',
    ) -> BehaviorTree:
        return BehaviorTree(
            BehaviorTree.SequenceNode(
                name=name,
                children=[
                    BehaviorTree.SubtreeNode(
                        name=f'{name} Step {index + 1}',
                        subtree_fn=lambda node, child=child: self._coerce_runtime_tree(child),
                    )
                    for index, child in enumerate(children)
                ],
            )
        )

    def _begin_named_planner_recovery_pass(self, node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        """Start a fresh planner pass and discard anchors from the previous run."""
        self._planner_recovery_pass_id += 1
        self._planner_recovery_anchors.clear()
        self._active_planner_shrine_recovery_checkpoint = None

        node.blackboard["planner_recovery_pass_id"] = self._planner_recovery_pass_id
        # Wipe context is intentionally valid only for the resumed remainder of
        # the current pass. A genuinely new run starts clean.
        node.blackboard.pop("planner_restart_reason", None)
        node.blackboard.pop("planner_restart_origin_step_name", None)
        node.blackboard.pop("planner_restart_target_step_name", None)
        return BehaviorTree.NodeState.SUCCESS

    def _record_named_planner_recovery_anchor(self, step_name: str) -> None:
        """Remember where a named planner step successfully completed.

        Recovery only records living-player positions in an explorable map. The
        stored anchors survive the planner Reset()/Start() performed during a
        restart, but are cleared when a fresh planner pass begins.
        """
        try:
            from ..Agent import Agent
            from ..Map import Map
            from ..Player import Player

            if not Map.IsMapReady() or not Map.IsExplorable():
                return

            player_id = int(Player.GetAgentID() or 0)
            if player_id <= 0 or not Agent.IsValid(player_id) or Agent.IsDead(player_id):
                return

            map_id = int(Map.GetMapID() or 0)
            x, y = Agent.GetXY(player_id)
            self._planner_recovery_anchors[str(step_name)] = (
                map_id,
                float(x),
                float(y),
            )
        except Exception:
            # Recovery metadata must never make a successful planner step fail.
            return

    def ConfigureShrineRecoveryCheckpoints(
        self,
        checkpoints: dict[str, str] | None = None,
    ) -> None:
        """Configure phase-aware shrine recovery checkpoints.

        ``checkpoints`` maps a completed named planner step to the named step that
        should become the recovery target from that point onward on the same map.
        The active checkpoint is cleared on every genuinely fresh planner pass.

        This is intentionally optional. Bots that do not configure checkpoints
        keep the normal nearest-anchor behavior unchanged.
        """
        normalized: dict[str, str] = {}
        for trigger_step, target_step in (checkpoints or {}).items():
            trigger = str(trigger_step or "").strip()
            target = str(target_step or "").strip()
            if trigger and target:
                normalized[trigger] = target
        self._planner_shrine_recovery_checkpoints = normalized
        self._active_planner_shrine_recovery_checkpoint = None

    def _activate_shrine_recovery_checkpoint_for_completed_step(
        self,
        step_name: str,
    ) -> None:
        target_step = str(
            self._planner_shrine_recovery_checkpoints.get(str(step_name), "")
            or ""
        ).strip()
        if not target_step:
            return

        try:
            from ..Map import Map

            if not Map.IsMapReady() or not Map.IsExplorable():
                return
            map_id = int(Map.GetMapID() or 0)
        except Exception:
            return

        self._active_planner_shrine_recovery_checkpoint = (
            map_id,
            str(step_name),
            target_step,
        )

    def _resolve_active_shrine_recovery_checkpoint(
        self,
        map_id: int,
        failed_step_name: str,
    ) -> str | None:
        checkpoint = self._active_planner_shrine_recovery_checkpoint
        if checkpoint is None:
            return None

        checkpoint_map_id, _trigger_step, target_step = checkpoint
        if int(checkpoint_map_id) != int(map_id):
            return None

        step_names = self.GetNamedPlannerStepNames()
        if not step_names:
            return None
        if failed_step_name not in step_names or target_step not in step_names:
            return None

        # Never allow a checkpoint to jump forward past the step where the wipe
        # occurred. If the configured target is no longer valid, geometry/fallback
        # recovery below remains authoritative.
        if step_names.index(target_step) > step_names.index(failed_step_name):
            return None

        return target_step

    def ResolveNearestShrineRecoveryStep(
        self,
        map_id: int,
        position: tuple[float, float],
        failed_step_name: str,
    ) -> tuple[str, float] | str | None:
        """Resolve a safe restart step from completed anchors near the shrine.

        A phase-aware checkpoint, when active for the current map, takes priority
        over geometry. This prevents an old waypoint near a shrine from winning
        merely because the route later revisits that same shrine.

        Only completed anchors from the current planner pass, on the current map,
        and strictly before the failed step are eligible. Recovery resumes from
        the step immediately after the selected completed anchor, so an already
        completed one-shot interaction is not replayed merely because that anchor
        itself is closest to the shrine.
        """
        step_names = self.GetNamedPlannerStepNames()
        if not step_names or failed_step_name not in step_names:
            return None

        checkpoint_step = self._resolve_active_shrine_recovery_checkpoint(
            map_id,
            failed_step_name,
        )
        if checkpoint_step:
            return checkpoint_step

        failed_index = step_names.index(failed_step_name)
        if failed_index <= 0:
            return None

        try:
            px, py = float(position[0]), float(position[1])
        except Exception:
            return None

        best: tuple[str, float] | None = None
        for completed_name, anchor in tuple(self._planner_recovery_anchors.items()):
            if completed_name not in step_names:
                continue

            completed_index = step_names.index(completed_name)
            if completed_index < 0 or completed_index >= failed_index:
                continue

            try:
                anchor_map_id, ax, ay = anchor
                if int(anchor_map_id) != int(map_id):
                    continue
                distance = ((float(ax) - px) ** 2 + (float(ay) - py) ** 2) ** 0.5
            except Exception:
                continue

            restart_index = completed_index + 1
            if restart_index > failed_index or restart_index >= len(step_names):
                continue

            restart_name = step_names[restart_index]
            if best is None or distance < best[1]:
                best = (restart_name, distance)

        return best

    def _build_named_planner_tree(
        self,
        steps: Sequence[tuple[str, Callable[[], object] | object]],
        start_from: str | None = None,
        name: str = 'PlannerSequence',
        repeat: bool = False,
    ) -> BehaviorTree:
        if not steps:
            return BehaviorTree(BehaviorTree.SequenceNode(name=name, children=[]))

        step_names = [step_name for step_name, _ in steps]
        start_index = 0
        if start_from is not None:
            if start_from not in step_names:
                raise ValueError(f"Unknown planner step '{start_from}'. Valid values: {', '.join(step_names)}")
            start_index = step_names.index(start_from)

        def _as_tree(subtree_or_builder: Callable[[], object] | object) -> BehaviorTree:
            subtree = subtree_or_builder() if callable(subtree_or_builder) else subtree_or_builder
            if isinstance(subtree, BehaviorTree):
                return subtree
            if isinstance(subtree, BehaviorTree.Node):
                return BehaviorTree(subtree)
            if hasattr(subtree, 'root') and hasattr(subtree, 'tick') and hasattr(subtree, 'reset'):
                return cast(BehaviorTree, subtree)
            raise TypeError(f'Planner step returned invalid type {type(subtree).__name__}.')

        def _mark_current_step(
            step_name: str,
        ) -> BehaviorTree.Node:
            def _mark(
                node: BehaviorTree.Node,
                step_name: str = step_name,
            ) -> BehaviorTree.NodeState:
                node.blackboard[
                    "current_step_name"
                ] = step_name

                node.blackboard[
                    "last_active_planner_step_name"
                ] = step_name

                return BehaviorTree.NodeState.SUCCESS

            return BehaviorTree.ActionNode(
                name=(
                    f"MarkCurrentStep({step_name})"
                ),
                action_fn=_mark,
                aftercast_ms=0,
            )

        def _mark_completed_step(
            step_name: str,
        ) -> BehaviorTree.Node:
            def _mark(
                node: BehaviorTree.Node,
                step_name: str = step_name,
            ) -> BehaviorTree.NodeState:
                node.blackboard["last_completed_planner_step_name"] = step_name
                self._record_named_planner_recovery_anchor(step_name)
                self._activate_shrine_recovery_checkpoint_for_completed_step(step_name)
                return BehaviorTree.NodeState.SUCCESS

            return BehaviorTree.ActionNode(
                name=f"MarkCompletedStep({step_name})",
                action_fn=_mark,
                aftercast_ms=0,
            )

        children: list[BehaviorTree.Node] = [
            BehaviorTree.SequenceNode(
                name=f'Step: {step_name}',
                children=[
                    _mark_current_step(step_name),
                    BehaviorTree.SubtreeNode(
                        name=step_name,
                        subtree_fn=lambda node, subtree_or_builder=subtree_or_builder: _as_tree(subtree_or_builder),
                    ),
                    _mark_completed_step(step_name),
                ],
            )
            for step_name, subtree_or_builder in steps[start_index:]
        ]

        # Only a genuinely fresh pass clears recovery anchors. Restarting from a
        # named step after a wipe deliberately preserves already-completed anchors.
        if start_from is None:
            children.insert(
                0,
                BehaviorTree.ActionNode(
                    name='BeginPlannerRecoveryPass',
                    action_fn=self._begin_named_planner_recovery_pass,
                    aftercast_ms=0,
                ),
            )
        if repeat:
            full_pass = self._build_named_planner_tree(steps, start_from=None, name=f'{name} Full Pass', repeat=False)

            def _tick_repeated_full_pass(
                node: BehaviorTree.Node,
            ) -> BehaviorTree.NodeState:
                """Repeat successful passes while propagating failures to the planner."""
                full_pass.blackboard = node.blackboard
                result = BehaviorTree.Node._normalize_state(
                    full_pass.tick()
                )

                if result is None:
                    raise TypeError(
                        "Repeated planner pass returned a non-NodeState result."
                    )

                if result == BehaviorTree.NodeState.FAILURE:
                    # Do not swallow the failure. _tick_planner() must receive it
                    # so it can restart the current named planner step.
                    return BehaviorTree.NodeState.FAILURE

                if result == BehaviorTree.NodeState.SUCCESS:
                    # A complete pass may start again from the first named step.
                    full_pass.reset()

                return BehaviorTree.NodeState.RUNNING

            children.append(
                BehaviorTree.ActionNode(
                    name='Loop: restart routine',
                    action_fn=_tick_repeated_full_pass,
                    aftercast_ms=0,
                )
            )
        return BehaviorTree(BehaviorTree.SequenceNode(name=name, children=children))

    def _coerce_runtime_tree(self, subtree_or_builder: Callable[[], object] | object) -> BehaviorTree:
        subtree = subtree_or_builder() if callable(subtree_or_builder) else subtree_or_builder
        if isinstance(subtree, BehaviorTree):
            return subtree
        if isinstance(subtree, BehaviorTree.Node):
            return BehaviorTree(subtree)
        if hasattr(subtree, 'root') and hasattr(subtree, 'tick') and hasattr(subtree, 'reset'):
            return cast(BehaviorTree, subtree)
        raise TypeError(f'Service step returned invalid type {type(subtree).__name__}.')

    def SetMainRoutine(
        self,
        routine: BehaviorTree | BehaviorTree.Node | Callable[[], object] | Sequence[object] | None,
        name: str = 'MainRoutine',
        auto_start: bool = False,
        reset: bool = True,
        repeat: bool = False,
    ):
        if routine is None:
            self.SetPlannerTree(None)
        elif callable(routine):
            self.SetPlannerTree(self._coerce_runtime_tree(routine))
        elif isinstance(routine, RuntimeSequence) and not isinstance(routine, (str, bytes)):
            routine_items = list(routine)
            if routine_items and all(
                isinstance(item, tuple)
                and len(item) == 2
                and isinstance(item[0], str)
                for item in routine_items
            ):
                self.SetNamedPlannerSteps(
                    cast(Sequence[tuple[str, Callable[[], object] | object]], routine_items),
                    name=name,
                    repeat=repeat,
                )
            else:
                self._planner_steps = []
                self._planner_sequence_name = name
                self.planner_repeat = False
                self.SetPlannerTree(self._build_sequence_from_children(routine_items, name=name))
        else:
            self.SetPlannerTree(self._coerce_runtime_tree(routine))

        if auto_start:
            self.Start()
        elif reset:
            self.Reset()

    def SetNamedPlannerSteps(
        self,
        steps: Sequence[tuple[str, Callable[[], object] | object]],
        start_from: str | None = None,
        name: str = 'PlannerSequence',
        repeat: bool = False,
    ):
        self._planner_steps = list(steps)
        self._planner_recovery_anchors.clear()
        self._planner_recovery_pass_id = 0
        self._active_planner_shrine_recovery_checkpoint = None
        self._planner_sequence_name = name
        self.planner_repeat = repeat
        self._set_planner_tree(self._build_named_planner_tree(self._planner_steps, start_from=start_from, name=name, repeat=repeat))
        self.EnsurePartyWipeRecoveryService(
            default_step_name=lambda: (self.GetNamedPlannerStepNames() or [None])[0],
            shrine_step_resolver=(
                self.ResolveNearestShrineRecoveryStep
                if self._nearest_shrine_recovery_enabled
                else None
            ),
        )

    def SetCurrentNamedPlannerSteps(
        self,
        steps: Sequence[tuple[str, Callable[[], object] | object]],
        start_from: str | None = None,
        name: str = 'PlannerSequence',
        auto_start: bool = False,
        reset: bool = True,
        repeat: bool = False,
    ):
        self.SetNamedPlannerSteps(
            steps,
            start_from=start_from,
            name=name,
            repeat=repeat,
        )
        if auto_start:
            self.Start()
        elif reset:
            self.Reset()

    def GetNamedPlannerStepNames(self) -> list[str]:
        return [step_name for step_name, _ in self._planner_steps]

    def RestartFromNamedPlannerStep(
        self,
        step_name: str,
        auto_start: bool = True,
        name: str | None = None,
    ) -> bool:
        if not self._planner_steps:
            return False

        sequence_name = name or self._planner_sequence_name

        self._set_planner_tree(
            self._build_named_planner_tree(
                self._planner_steps,
                start_from=step_name,
                name=sequence_name,
                repeat=self.planner_repeat,
            )
        )

        if auto_start:
            self.Start()
        else:
            self.Reset()

        return True

    def BuildAllSequences(
        self,
        start_from: str | None = None,
        name: str | None = None,
    ) -> BehaviorTree:
        if not self._planner_steps:
            return self._build_default_planner_tree()
        sequence_name = name or self._planner_sequence_name
        return self._build_named_planner_tree(self._planner_steps, start_from=start_from, name=sequence_name)

    def RestartFromSequence(
        self,
        sequence_name: str,
        auto_start: bool = True,
        name: str | None = None,
    ) -> bool:
        return self.RestartFromNamedPlannerStep(
            sequence_name,
            auto_start=auto_start,
            name=name,
        )