"""Script discovery — reads ``__script__`` metadata without importing the module.

No ImGui and no Py4GW imports: this module must stay importable and unit-testable from a
plain interpreter, same contract as ``launch_bar.model``.

Scripts live flat in ``Scripts/`` and declare a literal ``__script__`` dict near the top of
the file. Discovery reads only the first ``HEADER_WINDOW`` bytes of each file, so a rescan
costs ~18ms for 150 scripts instead of ~3s for a full ``ast.parse`` of every module.
"""

import ast
import os
from dataclasses import dataclass

HEADER_WINDOW = 8192

RESOURCES = ("character", "inventory", "skills", "dialog", "ui", "sharedmem")

# A script driving the character also drives NPC interaction, so it must exclude
# dialog senders even though it never declares `dialog` itself.
SUBSUMES = {"character": ("dialog",)}


@dataclass
class ScriptMeta:
    id: str
    name: str
    path: str
    function: str = ""
    tags: tuple = ()
    claims: tuple = ()
    mtime: float = 0.0
    error: str = ""

    def resources(self) -> set:
        out = set(self.claims)
        for claim in self.claims:
            out.update(SUBSUMES.get(claim, ()))
        return out

    def conflicts_with(self, other: "ScriptMeta") -> bool:
        return bool(self.resources() & other.resources())


def find_block(text: str) -> str:
    """Return the ``{...}`` source of the ``__script__`` assignment, or "" if incomplete.

    Brace-matched rather than searched for the next "}" so nested dicts and braces inside
    string values do not truncate the block.
    """
    at = text.find("__script__")
    if at < 0:
        return ""
    start = text.find("{", at)
    if start < 0:
        return ""
    depth = 0
    quote = ""
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if quote:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                quote = ""
            continue
        if ch in "\"'":
            quote = ch
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return ""


def parse_metadata(path: str) -> dict:
    """Read a script's ``__script__`` dict. Falls back to a full parse if the header
    window truncated the block."""
    with open(path, encoding="utf-8", errors="replace") as handle:
        head = handle.read(HEADER_WINDOW)
    block = find_block(head)
    if not block:
        with open(path, encoding="utf-8", errors="replace") as handle:
            block = find_block(handle.read())
    if not block:
        raise ValueError("no __script__ block")
    value = ast.literal_eval(block)
    if not isinstance(value, dict):
        raise ValueError("__script__ is not a dict")
    return value


def build_meta(path: str, mtime: float) -> ScriptMeta:
    script_id = os.path.splitext(os.path.basename(path))[0]
    try:
        raw = parse_metadata(path)
    except Exception as exc:
        return ScriptMeta(id=script_id, name=script_id, path=path, mtime=mtime, error=str(exc))
    claims = tuple(str(c) for c in raw.get("claims", ()) if c)
    unknown = [c for c in claims if c not in RESOURCES]
    return ScriptMeta(
        id=script_id,
        name=str(raw.get("name") or script_id),
        path=path,
        function=str(raw.get("function") or ""),
        tags=tuple(str(t) for t in raw.get("tags", ()) if t),
        claims=claims,
        mtime=mtime,
        error="unknown claims: %s" % ", ".join(unknown) if unknown else "",
    )


class ScriptRegistry:
    """Flat registry of ``Scripts/*.py``, refreshed on demand.

    Nothing here runs on a timer. ``refresh()`` reconciles against disk and re-reads only
    files whose mtime moved; ``changed_on_disk()`` answers the same question without
    mutating anything, so a UI can badge "reload available" without reloading.
    """

    def __init__(self, path: str = "Scripts"):
        self.path = path
        self.scripts: dict = {}
        self.pinned: set = set()
        self.stale: set = set()
        self.revision = 0

    def scan_mtimes(self) -> dict:
        try:
            names = [f for f in os.listdir(self.path) if f.endswith(".py")]
        except OSError:
            return {}
        out = {}
        for name in names:
            full = os.path.join(self.path, name)
            try:
                out[os.path.splitext(name)[0]] = (full, os.stat(full).st_mtime)
            except OSError:
                continue
        return out

    def changed_on_disk(self) -> bool:
        """Whether a refresh would change anything. Stats every file; no side effects."""
        seen = self.scan_mtimes()
        if set(seen) != set(self.scripts):
            return True
        return any(self.scripts[k].mtime != m for k, (_, m) in seen.items())

    def refresh(self) -> bool:
        """Reconcile the registry against disk, re-reading only what changed."""
        seen = self.scan_mtimes()
        changed = False
        for script_id in list(self.scripts):
            if script_id not in seen:
                del self.scripts[script_id]
                self.stale.discard(script_id)
                changed = True

        for script_id, (full, mtime) in seen.items():
            known = self.scripts.get(script_id)
            if known is not None and known.mtime == mtime:
                continue
            if script_id in self.pinned:
                # Running script: its imported module is authoritative until it stops.
                if known is not None:
                    self.stale.add(script_id)
                    continue
            self.scripts[script_id] = build_meta(full, mtime)
            self.stale.discard(script_id)
            changed = True

        if changed:
            self.revision += 1
        return changed

    def reload(self) -> bool:
        self.scripts.clear()
        self.stale.clear()
        return self.refresh()

    def pin(self, script_id: str) -> None:
        self.pinned.add(script_id)

    def unpin(self, script_id: str) -> None:
        self.pinned.discard(script_id)
        if script_id in self.stale:
            self.stale.discard(script_id)
            entry = self.scripts.get(script_id)
            if entry is not None:
                try:
                    self.scripts[script_id] = build_meta(entry.path, os.stat(entry.path).st_mtime)
                    self.revision += 1
                except OSError:
                    pass

    def all(self) -> list:
        return sorted(self.scripts.values(), key=lambda s: s.name.lower())

    def get(self, script_id: str):
        return self.scripts.get(script_id)

    def functions(self) -> list:
        return sorted({s.function for s in self.scripts.values() if s.function})

    def tags(self) -> list:
        return sorted({t for s in self.scripts.values() for t in s.tags})

    def query(self, function: str = "", tag: str = "", claim: str = "", text: str = "") -> list:
        needle = text.strip().lower()
        out = []
        for script in self.scripts.values():
            if function and script.function != function:
                continue
            if tag and tag not in script.tags:
                continue
            if claim and claim not in script.claims:
                continue
            if needle and needle not in script.name.lower() and needle not in script.id.lower():
                continue
            out.append(script)
        return sorted(out, key=lambda s: s.name.lower())

    def blocked_by(self, script_id: str, running_ids) -> list:
        """Which of ``running_ids`` would conflict with starting ``script_id``."""
        candidate = self.scripts.get(script_id)
        if candidate is None:
            return []
        out = []
        for other_id in running_ids:
            other = self.scripts.get(other_id)
            if other is not None and other_id != script_id and candidate.conflicts_with(other):
                out.append(other_id)
        return sorted(out)

    def errors(self) -> list:
        return [s for s in self.scripts.values() if s.error]
