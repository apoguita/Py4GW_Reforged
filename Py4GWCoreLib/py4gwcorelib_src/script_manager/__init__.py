"""Script manager — flat, metadata-driven discovery for ``Scripts/``."""

from .discovery import RESOURCES
from .discovery import SUBSUMES
from .discovery import ScriptMeta
from .discovery import ScriptRegistry
from .discovery import build_meta
from .discovery import find_block
from .discovery import parse_metadata
from .loader import PROTECTED_ROOTS
from .loader import RELOAD_ROOTS
from .loader import ScriptLoader
from .loader import shared_with_widgets

__all__ = [
    "PROTECTED_ROOTS",
    "RELOAD_ROOTS",
    "RESOURCES",
    "SUBSUMES",
    "ScriptLoader",
    "ScriptMeta",
    "ScriptRegistry",
    "build_meta",
    "find_block",
    "parse_metadata",
    "shared_with_widgets",
]
