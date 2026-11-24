"""Curated interaction identity and occurrence lookup facade."""

from .facade import CatalogIdentity
from .facade import CatalogOccurrence
from .facade import CatalogOccurrenceBinding
from .facade import InteractionCatalog
from .facade import get_interaction_identity
from .facade import get_interaction_occurrence
from .facade import get_interaction_occurrence_binding
from .facade import iter_interaction_occurrences

__all__ = (
    "CatalogIdentity",
    "CatalogOccurrence",
    "CatalogOccurrenceBinding",
    "InteractionCatalog",
    "get_interaction_identity",
    "get_interaction_occurrence",
    "get_interaction_occurrence_binding",
    "iter_interaction_occurrences",
)
