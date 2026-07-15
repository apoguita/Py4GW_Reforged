"""
Cast strategies for DEMO 2.0 — turn raw binding returns into readable, typed values.

This is the fix for the tool's core defect (structs rendering as raw memory addresses). Every
value a section displays is passed through one of these helpers so the CAST happens in the
section's row-builder, BEFORE the value reaches a renderer. No generic ``repr()``/``str()``
fallback exists here on purpose — a struct must be dereferenced field-by-field by the caller.

The four mechanisms (see docs/demo_replacement/reengineer/R3_wrapper_casting.md):
  M1  ctypes reinterpret cast  -> handled by the wrappers / Context path (GWContext facade)
  M2  enum int -> name         -> enum_pair / enum_name
  M3  encoded wide-string      -> decoded by the wrappers (*_str); we just display both
  M4  native Py* handle        -> call known accessors explicitly (never repr the handle)
"""

from typing import Any
from typing import Callable
from typing import Optional
from typing import Sequence


# ---------------------------------------------------------------------------
# Scalar formatters
# ---------------------------------------------------------------------------
def ptr(value: Any) -> str:
    """Render a pointer-ish int as ``0x00000000`` hex (R1 ``_fmt_ptr``)."""
    try:
        return "0x0" if not value else f"0x{int(value):08X}"
    except (TypeError, ValueError):
        return str(value)


def hex_of(value: Any, width: int = 0) -> str:
    try:
        return f"0x{int(value):0{width}X}" if width else f"0x{int(value):X}"
    except (TypeError, ValueError):
        return str(value)


def flags(value: Any) -> str:
    """Compact single-cell bitfield: ``123 | 0x7B | 0b1111011``."""
    try:
        i = int(value)
        return f"{i} | {hex(i)} | {bin(i)}"
    except (TypeError, ValueError):
        return str(value)


def dec_hex_bin(value: Any) -> "tuple[str, str, str]":
    """Three separate cells for a multi-column bitfield row (agent_demo idiom)."""
    try:
        i = int(value)
        return (str(i), hex(i), bin(i))
    except (TypeError, ValueError):
        s = str(value)
        return (s, "", "")


def f2(value: Any) -> str:
    """Two-decimal float, tolerant of None."""
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return str(value)


def f3(value: Any) -> str:
    try:
        return f"{float(value):.3f}"
    except (TypeError, ValueError):
        return str(value)


def vec(*components: Any, nd: int = 2) -> str:
    """Format a coordinate/vector tuple like ``(1.23, 4.56, 7.89)``."""
    parts = []
    for c in components:
        try:
            parts.append(f"{float(c):.{nd}f}")
        except (TypeError, ValueError):
            parts.append(str(c))
    return "(" + ", ".join(parts) + ")"


def yesno(value: Any) -> str:
    return "Yes" if value else "No"


# ---------------------------------------------------------------------------
# Enum / id-name resolution (M2)
# ---------------------------------------------------------------------------
def id_name(id_value: Any, name: Any) -> str:
    """The canonical ``[id] - name`` display for an (id, name) pair (map_demo idiom)."""
    return f"[{id_value}] - {name}"


def id_name_tuple(pair: Any) -> str:
    """Unpack a wrapper's ``(id, name)`` return into ``[id] - name``."""
    try:
        return id_name(pair[0], pair[1])
    except (TypeError, IndexError, KeyError):
        return str(pair)


def enum_name(enum_type: Callable, value: Any, names: Optional[dict] = None) -> str:
    """Resolve an int to ``[value] - Name`` via an IntEnum (+ optional _Names dict).

    Guards ValueError for unknown ints -> ``[value] - Unknown``.
    """
    try:
        member = enum_type(value)
    except (ValueError, TypeError):
        return f"[{value}] - Unknown"
    if names is not None:
        try:
            return id_name(int(value), names.get(member, "Unknown"))
        except (TypeError, ValueError):
            pass
    name = getattr(member, "name", None)
    return id_name(value, name if name is not None else "Unknown")


# ---------------------------------------------------------------------------
# Handle accessors (M4) — never repr a Py* handle; call its known accessors
# ---------------------------------------------------------------------------
def handle_rows(handle: Any, accessors: "Sequence[tuple[str, str]]") -> "list[tuple[str, str]]":
    """Build (label, value) rows by calling named zero-arg accessors on a handle.

    ``accessors`` is an EXPLICIT list of (label, attr_name) — no reflection/dir(). Each attr may
    be a method (called) or a plain attribute (read). Failures render as ``<err: ...>`` so one
    bad accessor never blanks the whole panel.
    """
    rows: "list[tuple[str, str]]" = []
    for label, attr in accessors:
        rows.append((label, _read_accessor(handle, attr)))
    return rows


def _read_accessor(obj: Any, attr: str) -> str:
    try:
        member = getattr(obj, attr)
    except Exception as e:  # noqa: BLE001 - display, don't crash
        return f"<err: {type(e).__name__}: {e}>"
    if callable(member):
        try:
            member = member()
        except Exception as e:  # noqa: BLE001
            return f"<err: {type(e).__name__}: {e}>"
    return str(member)


# ---------------------------------------------------------------------------
# Safe call — robustness for row-builders (NOT reflection; explicit target)
# ---------------------------------------------------------------------------
def safe(fn: Callable, *args, default: Any = None) -> Any:
    """Call an explicit getter, returning ``default`` on any exception.

    This keeps a single failing getter from blanking an entire build_* block. It is NOT
    auto-discovery — the caller always names the exact function.
    """
    try:
        return fn(*args)
    except Exception:  # noqa: BLE001 - a debug tool must survive a broken getter
        return default


def safe_str(fn: Callable, *args, default: str = "<err>") -> str:
    try:
        result = fn(*args)
    except Exception as e:  # noqa: BLE001
        return f"<err: {type(e).__name__}: {e}>"
    return str(result)
