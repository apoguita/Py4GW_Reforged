"""Script loading with dependency reload.

Re-importing a script is not enough to pick up edits to the code it imports: those
modules stay cached in ``sys.modules``. This module drops the script's supporting
modules before re-importing so a reload sees the edits.

What may be dropped is deliberately narrow. ``Py4GWCoreLib`` is imported by 620 call
sites across scripts and by every widget; dropping it mid-session would leave live
widgets holding a half-replaced library. Only project code under ``RELOAD_ROOTS`` is
eligible, and even then anything a widget also imports is protected -- see
``shared_with_widgets``.
"""

import ast
import importlib.util
import os
import sys

RELOAD_ROOTS = ("Sources", "HeroAI", "Bots", "bot_factory")

# Never dropped: shared with the widget host, or native modules that cannot be re-executed.
PROTECTED_ROOTS = ("Py4GWCoreLib", "Py4GW_widget_manager", "Widgets", "Py4GW", "PySystem")

MODULE_PREFIX = "py4gw_script_"


def module_name_for(script_id: str) -> str:
    safe = "".join(ch if ch.isalnum() else "_" for ch in script_id)
    return MODULE_PREFIX + safe


def imports_in(path: str) -> set:
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            tree = ast.parse(handle.read())
    except (OSError, SyntaxError):
        return set()
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.add(node.module)
    return found


def shared_with_widgets(widgets_path: str = "Widgets", reload_roots=RELOAD_ROOTS) -> set:
    """Modules under ``reload_roots`` that a widget also imports.

    Dropping one of these would hand the script a fresh module while an enabled widget
    keeps the old object. That is a real divergence, not a theoretical one:
    ``HeroAI.cache_data`` holds module-level cache state and is imported by both
    CombatPrep and EZ Cast.
    """
    roots = tuple(reload_roots)
    out = set()
    for current, dirs, files in os.walk(widgets_path):
        if ".widget" not in files:
            continue
        for name in files:
            if not name.endswith(".py"):
                continue
            for module in imports_in(os.path.join(current, name)):
                if module.split(".")[0] in roots:
                    out.add(module)
    return out


def expand(names: set) -> set:
    """Include submodules, so protecting HeroAI.cache_data also protects its children."""
    out = set(names)
    for name in list(names):
        out.update(k for k in sys.modules if k.startswith(name + "."))
    return out


class ScriptLoader:
    """Imports scripts by path, dropping their reloadable dependencies first."""

    def __init__(self, widgets_path: str = "Widgets", reload_roots=RELOAD_ROOTS):
        self.widgets_path = widgets_path
        self.reload_roots = tuple(reload_roots)
        self.protected = None
        self.loaded: dict = {}

    def protected_modules(self) -> set:
        if self.protected is None:
            self.protected = shared_with_widgets(self.widgets_path, self.reload_roots)
        return expand(self.protected)

    def refresh_protected(self) -> set:
        self.protected = None
        return self.protected_modules()

    def purgeable(self) -> list:
        protected = self.protected_modules()
        out = []
        for name in list(sys.modules):
            root = name.split(".")[0]
            if root in PROTECTED_ROOTS or root not in self.reload_roots:
                continue
            if name in protected:
                continue
            out.append(name)
        return sorted(out)

    def purge(self) -> list:
        dropped = self.purgeable()
        for name in dropped:
            sys.modules.pop(name, None)
        return dropped

    def load(self, script_id: str, path: str, reload_dependencies: bool = True):
        """Import (or re-import) a script. Returns (module, dropped_module_names)."""
        name = module_name_for(script_id)
        sys.modules.pop(name, None)
        dropped = self.purge() if reload_dependencies else []

        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            raise ImportError("cannot load %s from %s" % (script_id, path))
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            sys.modules.pop(name, None)
            raise
        self.loaded[script_id] = module
        return module, dropped

    def unload(self, script_id: str) -> bool:
        module = self.loaded.pop(script_id, None)
        return sys.modules.pop(module_name_for(script_id), None) is not None or module is not None

    def entry_points(self, module) -> dict:
        return {
            key: getattr(module, key)
            for key in ("main", "draw", "update", "configure")
            if callable(getattr(module, key, None))
        }
