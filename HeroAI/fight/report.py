"""Follower-side: tell the leader which line this character's build declares."""

from __future__ import annotations

from dataclasses import dataclass

from Py4GWCoreLib import GLOBAL_CACHE
from Py4GWCoreLib import SharedCommandType
from Py4GWCoreLib import ThrottledTimer
from Py4GWCoreLib.Player import Player

from .lines import CombatLine
from .lines import get_build_declared_line

REPORT_RETRY_MS = 5000


@dataclass(slots=True)
class ReportState:
    last_reported_line: CombatLine | None = None
    last_reported_build: str = ""


class CombatLineReporter:
    def __init__(self) -> None:
        self.state = ReportState()
        self.retry_timer = ThrottledTimer(REPORT_RETRY_MS)

    def tick(self, build_contract: object | None, build_name: str) -> None:
        """Send only on change. The leader caches the last value, so a steady
        stream would just burn inbox slots other commands need."""
        if build_contract is None:
            return

        declared = get_build_declared_line(build_contract)
        unchanged = self.state.last_reported_line == declared and self.state.last_reported_build == build_name
        if unchanged and not self.retry_timer.IsExpired():
            return

        sender_email = str(Player.GetAccountEmail() or "").strip()
        leader_account = GLOBAL_CACHE.ShMem.GetAccountDataFromPartyNumber(0)
        leader_email = str(getattr(leader_account, "AccountEmail", "") or "").strip() if leader_account else ""
        if not sender_email or not leader_email or sender_email == leader_email:
            return

        try:
            GLOBAL_CACHE.ShMem.SendMessage(
                sender_email,
                leader_email,
                SharedCommandType.ReportCombatLine,
                (float(int(declared)), 0.0, 0.0, 0.0),
            )
        except Exception:
            return

        self.state.last_reported_line = declared
        self.state.last_reported_build = build_name
        self.retry_timer.Reset()

    def reset(self) -> None:
        self.state = ReportState()
