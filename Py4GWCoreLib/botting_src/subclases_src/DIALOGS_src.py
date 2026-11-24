#region STATES
from typing import TYPE_CHECKING, Dict, Callable, Any

if TYPE_CHECKING:
    from Py4GWCoreLib.botting_src.helpers import BottingClass

from ..helpers_src.decorators import _yield_step
from ...Py4GWcorelib import ActionQueueManager

#region DIALOGS
class _DIALOGS:
    def __init__(self, parent: "BottingClass"):
        self.parent = parent
        self._config = parent.config
        self._helpers = parent.helpers
        self._Events = parent.helpers.Events
        self.hero_ai_status = False
        self.hero_ai_pause_status = False


    #region Coroutines (_coro_)
    def _coro_pause_hero_ai(self):
        self.hero_ai_status = self._config.upkeep.hero_ai.is_active()
        self.hero_ai_pause_status = bool(getattr(self._config.upkeep, "hero_ai_paused", None) and self._config.upkeep.hero_ai_paused.is_active())
        if hasattr(self._config.upkeep, "hero_ai_paused"):
            self._config.upkeep.hero_ai_paused.set_now("active", True)
        else:
            self._config.upkeep.hero_ai.set_now("active", False)
        ActionQueueManager().ResetAllQueues()
        yield

    def _coro_restore_hero_ai(self):
        from ...Routines import Routines
        # Give dialog/UI actions time to settle before AI resumes.
        yield from Routines.Yield.wait(350)
        if hasattr(self._config.upkeep, "hero_ai_paused"):
            self._config.upkeep.hero_ai_paused.set_now("active", self.hero_ai_pause_status)
        else:
            self._config.upkeep.hero_ai.set_now("active", self.hero_ai_status)
        yield
        
    def _coro_at_xy(self, x: float, y: float, dialog:int):
        yield from self._coro_pause_hero_ai()
        yield from self.parent.Interact._coro_with_npc_at_xy(x, y, dialog_id=dialog)
        yield from self._coro_restore_hero_ai()
        
    def _coro_with_model(self, model_id: int, dialog:int):
        yield from self._coro_pause_hero_ai()
        yield from self.parent.Interact._coro_with_model(model_id=model_id, dialog_id=dialog)
        yield from self._coro_restore_hero_ai()

    def _coro_move_and_auto_dialog_by_model_id(
        self,
        model_id_or_encoded_name: int | str,
        button_numbers: list[int],
        target_map_id: int,
        timeout_ms: int = 90000,
    ):
        from Sources.ApoSource.ApoBottingLib import wrappers as BT
        from ...routines_src.yield_src.helpers import _run_bt_tree

        tree = BT.Sequence(
            name="Move through fixed multi-page dialogue",
            children=[
                BT.MoveAndAutoDialogByModelID(
                    modelID_or_encStr=model_id_or_encoded_name,
                    button_number=list(button_numbers),  # pyright: ignore[reportArgumentType]
                ),
                BT.WaitForMapLoad(
                    map_id=target_map_id,
                    timeout_ms=timeout_ms,
                ),
            ],
        )
        succeeded = yield from _run_bt_tree(tree, return_bool=True)
        if not succeeded:
            self._Events.on_unmanaged_fail()
            return False
        return True
    
    #region Yield Steps (ys_)
    @_yield_step("PauseHeroAI","PAUSE_HERO_AI")
    def ys_pause_hero_ai(self):
        yield from self._coro_pause_hero_ai()
        
    @_yield_step("RestoreHeroAI","RESTORE_HERO_AI")
    def ys_restore_hero_ai(self):
        yield from self._coro_restore_hero_ai()

    @_yield_step("AtXY","DIALOG_AT_XY")
    def ys_at_xy(self, x: float, y: float, dialog:int, step_name: str=""):
        yield from self._coro_at_xy(x, y, dialog)

    @_yield_step("WithModel","DIALOG_WITH_MODEL")
    def ys_with_model(self, model_id: int, dialog:int, step_name: str=""):
        yield from self._coro_with_model(model_id, dialog)

    @_yield_step("MoveAndAutoDialogByModelID", "MOVE_AND_AUTO_DIALOG_BY_MODEL_ID")
    def ys_move_and_auto_dialog_by_model_id(
        self,
        model_id_or_encoded_name: int | str,
        button_numbers: list[int],
        target_map_id: int,
        timeout_ms: int = 90000,
        step_name: str = "",
    ):
        yield from self._coro_move_and_auto_dialog_by_model_id(
            model_id_or_encoded_name=model_id_or_encoded_name,
            button_numbers=button_numbers,
            target_map_id=target_map_id,
            timeout_ms=timeout_ms,
        )

    #region Helpers
    def AtXY(self, x: float, y: float, dialog:int, step_name: str="") -> None:
        if step_name == "":
            step_name = f"DialogAt_{self._config.get_counter('DIALOG_AT')}"
        self.ys_at_xy(x, y, dialog)

        
    def WithModel(self, model_id: int, dialog:int, step_name: str="") -> None:
        if step_name == "":
            step_name = f"DialogWithModel_{self._config.get_counter('DIALOG_AT')}"
        self.ys_with_model(model_id, dialog)

    def MoveAndAutoDialogByModelID(
        self,
        model_id_or_encoded_name: int | str,
        button_numbers: list[int],
        target_map_id: int,
        timeout_ms: int = 90000,
        step_name: str = "",
    ) -> None:
        self.ys_move_and_auto_dialog_by_model_id(
            model_id_or_encoded_name=model_id_or_encoded_name,
            button_numbers=button_numbers,
            target_map_id=target_map_id,
            timeout_ms=timeout_ms,
            step_name=step_name,
        )
