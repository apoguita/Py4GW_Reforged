"""Path helpers for BT-native modular recipe tooling."""

from __future__ import annotations

from pathlib import Path


_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def project_root() -> str:
    try:
        import PySystem

        root = str(PySystem.Console.get_projects_path() or "").strip()
        if root:
            return str(Path(root).resolve())
    except (ImportError, AttributeError, OSError, TypeError, ValueError):
        # Offline tools do not have the embedded PySystem module. Resolve from
        # this package instead of the process working directory, which is not
        # stable in an injected client.
        pass
    return str(_REPOSITORY_ROOT)


def modular_data_root() -> str:
    return str(Path(project_root()) / "json" / "modular")


def modular_settings_root() -> str:
    return str(Path(project_root()) / "Settings" / "ModularBot")


def modular_logs_root() -> str:
    return str(Path(project_root()) / "Logs" / "modular_bot")
