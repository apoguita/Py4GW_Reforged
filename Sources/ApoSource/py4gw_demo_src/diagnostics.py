"""
File diagnostics for DEMO 2.0 — per-section "Dump to file" (manual, opt-in).

Each section renders a single dump button (``dump_button``) wired to the SAME Block list it draws
on screen, so the written log is exactly the cast, readable view — never a raw struct repr.

Output goes to a ROOT-LEVEL ``demo_diagnostics/`` folder (NOT inside the source package), resolved
relative to the repo root regardless of the process cwd. All file I/O is guarded; a failed write
logs an error and never crashes the widget. There is no auto-logging and no global dump-all — a
dump happens only when the user clicks a section's button (respects the no-auto-invoke rule).
"""

import os

import PyImGui

# repo_root/Sources/ApoSource/py4gw_demo_src/diagnostics.py -> repo_root
_PKG_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_PKG_DIR)))
OUTPUT_DIR = os.path.join(_REPO_ROOT, "demo_diagnostics")

_counter = 0
_last_path: "dict[str, str]" = {}


def _stamp() -> str:
    """Monotonic-ish stamp for filenames. Uses the game tick if available, else a counter."""
    global _counter
    _counter += 1
    try:
        import PySystem  # embedded module — only present in-client

        return f"{PySystem.get_tick_count64()}_{_counter:03d}"
    except Exception:  # noqa: BLE001 - offline / no binding
        return f"{_counter:05d}"


def _console(msg: str, is_error: bool = False) -> None:
    try:
        import PySystem

        mt = PySystem.Console.MessageType
        PySystem.Console.Log("DEMO2.diagnostics", msg, mt.Error if is_error else mt.Info)
    except Exception:  # noqa: BLE001
        pass


def serialize(section_name: str, blocks) -> str:
    """Render a Block list to readable plain text (mirrors the on-screen view)."""
    lines = []
    lines.append("=" * 72)
    lines.append(f"DEMO 2.0 diagnostics — section: {section_name}")
    lines.append(f"stamp: {_stamp()}")
    lines.append(_map_line())
    lines.append("=" * 72)
    lines.append("")

    for block in blocks:
        try:
            kind, title, payload = block
        except (TypeError, ValueError):
            lines.append(f"<malformed block: {block!r}>")
            continue
        lines.append(f"--- {title} ---" if title else "---")
        if kind == "kv":
            width = max((len(str(f)) for f, _ in payload), default=0)
            for field, value in payload:
                lines.append(f"  {str(field).ljust(width)} : {value}")
        elif kind == "multi":
            headers, rows = payload
            lines.append("  " + " | ".join(str(h) for h in headers))
            for row in rows:
                lines.append("  " + " | ".join(str(c) for c in row))
        elif kind == "bools":
            for label, value in payload:
                lines.append(f"  {label} : {'Yes' if value else 'No'}")
        elif kind == "text":
            for ln in str(payload).splitlines():
                lines.append(f"  {ln}")
        lines.append("")
    return "\n".join(lines)


def _map_line() -> str:
    try:
        from Py4GWCoreLib import Map

        return f"map: [{Map.GetMapID()}] {Map.GetMapName()}  instance: {Map.GetInstanceTypeName()}"
    except Exception:  # noqa: BLE001
        return "map: <unavailable>"


def _safe_name(section_name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in section_name)


def dump(section_name: str, blocks) -> str:
    """Write the section's blocks to ``demo_diagnostics/<section>_<stamp>.txt``. Returns the path."""
    try:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        path = os.path.join(OUTPUT_DIR, f"{_safe_name(section_name)}_{_stamp()}.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(serialize(section_name, blocks))
        _last_path[section_name] = path
        _console(f"wrote {path}")
        return path
    except Exception as e:  # noqa: BLE001 - never crash the widget on an I/O error
        _console(f"dump failed for '{section_name}': {type(e).__name__}: {e}", is_error=True)
        _last_path[section_name] = f"<error: {e}>"
        return ""


def dump_button(section_name: str, blocks) -> None:
    """Render the per-section 'Dump to file' button, wired to the already-built blocks."""
    if PyImGui.button(f"Dump to file##{section_name}"):
        dump(section_name, blocks)
    last = _last_path.get(section_name)
    if last:
        PyImGui.same_line(0, 8)
        color = (0.60, 0.60, 0.65, 1.0) if last.startswith("<error") is False else (0.90, 0.30, 0.30, 1.0)
        PyImGui.text_colored(last, color)
