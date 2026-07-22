# PyPacketSniffer stub — Reforged Native surface
# Exact counterpart of src/GW/packet_sniffer/packet_sniffer_bindings.cpp.
#
# Unified packet sniffer: captures raw StoC and CToS packets through a single
# PacketSniffer facade. Capture is lazy — nothing is hooked until one of the
# initialize* methods is called.

from enum import IntEnum
from typing import List


class PacketDirection(IntEnum):
    StoC: int  # 0
    CToS: int  # 1


# py::enum_ ... .export_values() also exports the members at module level.
StoC: PacketDirection
CToS: PacketDirection


class PacketLogEntry:
    """One captured packet. All fields are read-only."""

    tick: int
    direction: PacketDirection
    header: int
    size: int
    data: List[int]

    def __init__(self) -> None: ...
    def __repr__(self) -> str: ...


class PacketSniffer:
    """Stateless facade over GW::packet_sniffer. Not constructible — use instance()."""

    @staticmethod
    def instance() -> 'PacketSniffer': ...

    def initialize(self) -> bool: ...
    def initialize_stoc(self) -> bool: ...
    def initialize_ctos(self) -> bool: ...
    def terminate(self) -> None: ...
    def terminate_stoc(self) -> None: ...
    def terminate_ctos(self) -> None: ...
    def get_logs(self) -> List[PacketLogEntry]: ...
    def get_stoc_logs(self) -> List[PacketLogEntry]: ...
    def get_ctos_logs(self) -> List[PacketLogEntry]: ...
    def clear_logs(self) -> None: ...
    def clear_stoc_logs(self) -> None: ...
    def clear_ctos_logs(self) -> None: ...
