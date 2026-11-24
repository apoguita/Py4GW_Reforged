"""Typed static row shapes shared by interaction catalog partitions."""

from __future__ import annotations

from typing import TypeAlias

RegistryReference: TypeAlias = tuple[str, str, int]
ProvenanceRow: TypeAlias = tuple[tuple[str, object], ...]
IdentityRow: TypeAlias = tuple[
    str,
    str,
    tuple[str, ...],
    tuple[int, ...] | None,
    RegistryReference | None,
    tuple[int, ...],
    str,
    tuple[ProvenanceRow, ...],
]
OccurrenceRow: TypeAlias = tuple[
    str,
    str,
    int,
    str,
    tuple[float, float],
    tuple[float, float] | None,
    tuple[str, ...],
    str,
    tuple[ProvenanceRow, ...],
]
