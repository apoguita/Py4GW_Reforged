"""Read-only facade over curated interaction identities and occurrences.

The catalog owns stable occurrence facts. Consumers continue to own route
geometry, interaction behavior, postconditions, and lifecycle decisions.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Iterable
from typing import Iterator

from .data import PARTITIONS
from .data.schema import OccurrenceRow
from .data.schema import RegistryReference

_VALID_STATUSES = frozenset(
    {
        "candidate",
        "reviewed",
        "reviewed_identity_reuse_with_route_marker_geometry",
        "reviewed_identity_with_occurrence_geometry",
        "offline_verified",
        "live_verified",
    }
)


def _normalized(value: object) -> str:
    return str(value or "").strip().casefold().replace(" ", "_").replace("-", "_")


def encoded_units_to_runtime(units: Iterable[int]) -> str:
    """Match ``Agent.GetEncNameStrByID(..., literal=True)`` from UTF-16 units."""
    raw = bytearray()
    for value in units:
        unit = int(value)
        if unit == 0:
            break
        raw.extend(unit.to_bytes(2, "little"))

    text = bytes(raw).decode("utf-16-le", "ignore")
    output: list[str] = []
    for character in text:
        codepoint = ord(character)
        if 32 <= codepoint <= 126:
            output.append(character)
        elif character == "\n":
            output.append("\\n")
        elif character == "\t":
            output.append("\\t")
        else:
            output.append(f"\\x{codepoint:04X}")
    return "".join(output)


def encoded_units_to_legacy_bytes(units: Iterable[int]) -> tuple[int, ...]:
    """Project canonical code units into target_registry little-endian bytes."""
    output: list[int] = []
    for raw in units:
        unit = int(raw)
        if unit == 0:
            break
        output.extend((unit & 0xFF, (unit >> 8) & 0xFF))
    output.extend((0, 0))
    return tuple(output)


def _legacy_bytes_to_units(values: Iterable[int]) -> tuple[int, ...]:
    raw = tuple(int(value) for value in values)
    if len(raw) % 2:
        raise ValueError("target registry encoded identity must contain byte pairs")
    units = []
    for index in range(0, len(raw), 2):
        unit = raw[index] | (raw[index + 1] << 8)
        if unit == 0:
            break
        units.append(unit)
    return tuple(units)


def _resolve_registry_reference(reference: RegistryReference) -> tuple[int, ...]:
    from ..target_registry import get_named_agent_target

    kind, key, encoded_index = reference
    target = get_named_agent_target(kind, key)
    if target is None:
        raise ValueError(f"missing target_registry reference: {kind}:{key}")
    try:
        encoded_name = target.encoded_names[encoded_index]
    except IndexError as exc:
        raise ValueError(f"invalid target_registry encoded index: {kind}:{key}:{encoded_index}") from exc
    return _legacy_bytes_to_units(encoded_name)


@dataclass(frozen=True)
class CatalogIdentity:
    key: str
    kind: str
    aliases: tuple[str, ...]
    encoded_name_units: tuple[int, ...]
    observed_model_ids: tuple[int, ...]
    validation_status: str
    target_registry_reference: RegistryReference | None
    provenance: tuple[dict[str, object], ...]

    @property
    def display_name(self) -> str:
        return self.aliases[0]

    @property
    def encoded_name_runtime(self) -> str:
        return encoded_units_to_runtime(self.encoded_name_units)

    @property
    def legacy_encoded_name(self) -> tuple[int, ...]:
        return encoded_units_to_legacy_bytes(self.encoded_name_units)


@dataclass(frozen=True)
class CatalogOccurrence:
    key: str
    identity_key: str
    map_id: int
    map_name: str
    target_xy: tuple[float, float]
    default_player_approach_xy: tuple[float, float] | None
    capture_ids: tuple[str, ...]
    validation_status: str
    provenance: tuple[dict[str, object], ...]
    identity: CatalogIdentity
    partition: str
    partition_sha256: str

    @property
    def binding(self) -> "CatalogOccurrenceBinding":
        return CatalogOccurrenceBinding(
            occurrence_key=self.key,
            partition=self.partition,
            partition_sha256=self.partition_sha256,
        )


@dataclass(frozen=True)
class CatalogOccurrenceBinding:
    """Hash-exact reference shape used by ledgers and delivery receipts."""

    occurrence_key: str
    partition: str
    partition_sha256: str


class InteractionCatalog:
    """Validate and query the static interaction catalog."""

    def __init__(self) -> None:
        self.identities: dict[str, CatalogIdentity] = {}
        self.occurrences: dict[str, CatalogOccurrence] = {}
        self.partition_hashes: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        pending_occurrences: list[tuple[str, str, OccurrenceRow]] = []
        for partition_module in PARTITIONS:
            partition = str(partition_module.PARTITION)
            partition_sha256 = (
                sha256(repr((partition_module.IDENTITIES, partition_module.OCCURRENCES)).encode("utf-8"))
                .hexdigest()
                .upper()
            )
            self.partition_hashes[partition] = partition_sha256
            for row in partition_module.IDENTITIES:
                (
                    key,
                    kind,
                    aliases,
                    encoded_units,
                    registry_reference,
                    observed_model_ids,
                    validation_status,
                    provenance,
                ) = row
                if key in self.identities:
                    raise ValueError(f"duplicate identity key: {key}")
                if validation_status not in _VALID_STATUSES:
                    raise ValueError(f"{key}: invalid validation_status {validation_status!r}")
                if not aliases:
                    raise ValueError(f"{key}: at least one alias is required")
                if (encoded_units is None) == (registry_reference is None):
                    raise ValueError(f"{key}: define exactly one encoded identity source")
                resolved_units = (
                    _resolve_registry_reference(registry_reference) if registry_reference is not None else encoded_units
                )
                if not resolved_units or any(value < 0 or value > 0xFFFF for value in resolved_units):
                    raise ValueError(f"{key}: encoded identity must use UTF-16 units")
                self.identities[key] = CatalogIdentity(
                    key=key,
                    kind=kind,
                    aliases=aliases,
                    encoded_name_units=resolved_units,
                    observed_model_ids=observed_model_ids,
                    validation_status=validation_status,
                    target_registry_reference=registry_reference,
                    provenance=tuple(dict(item) for item in provenance),
                )
            pending_occurrences.extend((partition, partition_sha256, row) for row in partition_module.OCCURRENCES)

        encoded_owners: dict[tuple[int, ...], str] = {}
        for key, identity in self.identities.items():
            prior = encoded_owners.setdefault(identity.encoded_name_units, key)
            if prior != key:
                raise ValueError(f"encoded identity collision: {prior} and {key}")

        for partition, partition_sha256, row in pending_occurrences:
            (
                key,
                identity_key,
                map_id,
                map_name,
                target_xy,
                default_player_approach_xy,
                capture_ids,
                validation_status,
                provenance,
            ) = row
            key = str(key)
            identity_key = str(identity_key)
            if key in self.occurrences:
                raise ValueError(f"duplicate occurrence key: {key}")
            identity = self.identities.get(identity_key)
            if identity is None:
                raise ValueError(f"{key}: dangling identity_key {identity_key!r}")
            if validation_status not in _VALID_STATUSES:
                raise ValueError(f"{key}: invalid validation_status {validation_status!r}")
            self.occurrences[key] = CatalogOccurrence(
                key=key,
                identity_key=identity_key,
                map_id=int(map_id),
                map_name=str(map_name),
                target_xy=target_xy,
                default_player_approach_xy=default_player_approach_xy,
                capture_ids=capture_ids,
                validation_status=str(validation_status),
                provenance=tuple(dict(item) for item in provenance),
                identity=identity,
                partition=partition,
                partition_sha256=partition_sha256,
            )

    def get_identity(self, key_or_alias: object, *, kind: str | None = None) -> CatalogIdentity | None:
        key_text = str(key_or_alias or "").strip()
        direct = self.identities.get(key_text)
        if direct is not None and (kind is None or direct.kind == kind):
            return direct
        wanted = _normalized(key_text)
        matches = [
            identity
            for identity in self.identities.values()
            if (kind is None or identity.kind == kind)
            and (wanted == _normalized(identity.key) or any(wanted == _normalized(alias) for alias in identity.aliases))
        ]
        if len(matches) > 1:
            raise ValueError(f"ambiguous catalog identity alias: {key_or_alias!r}")
        return matches[0] if matches else None

    def get_occurrence(self, key: str) -> CatalogOccurrence:
        try:
            return self.occurrences[str(key)]
        except KeyError as exc:
            raise KeyError(f"unknown interaction occurrence: {key}") from exc

    def iter_occurrences(self, *, map_id: int | None = None, kind: str | None = None) -> Iterator[CatalogOccurrence]:
        return (
            occurrence
            for occurrence in self.occurrences.values()
            if (map_id is None or occurrence.map_id == map_id) and (kind is None or occurrence.identity.kind == kind)
        )


_DEFAULT_CATALOG: InteractionCatalog | None = None


def _catalog() -> InteractionCatalog:
    global _DEFAULT_CATALOG
    if _DEFAULT_CATALOG is None:
        _DEFAULT_CATALOG = InteractionCatalog()
    return _DEFAULT_CATALOG


def get_interaction_identity(key_or_alias: object, *, kind: str | None = None) -> CatalogIdentity | None:
    return _catalog().get_identity(key_or_alias, kind=kind)


def get_interaction_occurrence(key: str) -> CatalogOccurrence:
    return _catalog().get_occurrence(key)


def get_interaction_occurrence_binding(key: str) -> CatalogOccurrenceBinding:
    return get_interaction_occurrence(key).binding


def iter_interaction_occurrences(*, map_id: int | None = None, kind: str | None = None) -> Iterator[CatalogOccurrence]:
    return _catalog().iter_occurrences(map_id=map_id, kind=kind)
