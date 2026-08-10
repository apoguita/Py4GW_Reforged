from __future__ import annotations

from collections.abc import Iterator
from typing import Any


class BuildContractRunner:
    """Advance one selected BuildMgr contract across successive tree ticks."""

    def __init__(self) -> None:
        self._contract: Any | None = None
        self._is_in_combat: bool | None = None
        self._coroutine: Iterator[Any] | None = None

    @property
    def contract(self) -> Any | None:
        return self._contract

    @property
    def is_running(self) -> bool:
        return self._coroutine is not None

    def tick(self, contract: Any | None, *, is_in_combat: bool) -> bool:
        if contract is None:
            self.reset()
            return False

        resolved_phase = bool(is_in_combat)
        if contract is not self._contract or resolved_phase != self._is_in_combat:
            self._replace_execution(contract, resolved_phase)

        if self._coroutine is None:
            process = contract.ProcessCombat if resolved_phase else contract.ProcessOOC
            self._coroutine = iter(process())

        try:
            next(self._coroutine)
        except StopIteration:
            self._coroutine = None

        did_tick_succeed = getattr(contract, 'DidTickSucceed', None)
        return bool(callable(did_tick_succeed) and did_tick_succeed())

    def reset(self) -> None:
        self._close_coroutine()
        self._contract = None
        self._is_in_combat = None

    def _replace_execution(self, contract: Any, is_in_combat: bool) -> None:
        self._close_coroutine()
        self._contract = contract
        self._is_in_combat = is_in_combat

    def _close_coroutine(self) -> None:
        coroutine = self._coroutine
        self._coroutine = None
        if coroutine is None:
            return
        close = getattr(coroutine, 'close', None)
        if callable(close):
            try:
                close()
            except Exception:
                pass
