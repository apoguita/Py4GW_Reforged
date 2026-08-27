"""Small indexed offline knowledge layer for HeroAI.

The data is advisory and fails open. JSON is loaded once, indexed in memory, and
never scanned linearly during combat.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from Py4GWCoreLib.Skill import Skill

_BASE = Path(__file__).resolve().parent
_LOADED = False
_AREA: dict[int, dict[str, Any]] = {}
_SKILL_BY_ID: dict[int, dict[str, Any]] = {}
_ENEMY_MODELS: dict[int, dict[str, Any]] = {}
_NAME_TOKENS: dict[str, dict[str, Any]] = {}


def _load_json(name: str) -> dict[str, Any]:
    try:
        return json.loads((_BASE / name).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _ensure_loaded() -> None:
    global _LOADED
    if _LOADED:
        return
    _LOADED = True

    area = _load_json("area_profiles.json").get("profiles", {})
    for key, value in area.items():
        try:
            _AREA[int(key)] = dict(value)
        except Exception:
            continue

    skills = _load_json("skill_profiles.json").get("profiles", {})
    for skill_name, value in skills.items():
        try:
            skill_id = int(Skill.GetID(str(skill_name)) or 0)
        except Exception:
            skill_id = 0
        if skill_id > 0:
            profile = dict(value)
            profile["name"] = str(skill_name)
            _SKILL_BY_ID[skill_id] = profile

    enemies = _load_json("enemy_profiles.json")
    for key, value in enemies.get("models", {}).items():
        try:
            _ENEMY_MODELS[int(key)] = dict(value)
        except Exception:
            continue
    for token, value in enemies.get("named_tokens", {}).items():
        _NAME_TOKENS[str(token).casefold()] = dict(value)


def area_profile(map_id: int) -> dict[str, Any]:
    _ensure_loaded()
    return dict(_AREA.get(int(map_id or 0), {}))


def skill_profile(skill_id: int) -> dict[str, Any]:
    _ensure_loaded()
    return dict(_SKILL_BY_ID.get(int(skill_id or 0), {}))


def enemy_profile(model_id: int, name: str = "") -> dict[str, Any]:
    _ensure_loaded()
    merged = dict(_ENEMY_MODELS.get(int(model_id or 0), {}))
    lname = str(name or "").casefold()
    for token, profile in _NAME_TOKENS.items():
        if token and token in lname:
            for key, value in profile.items():
                if key == "roles":
                    roles = set(merged.get("roles", ()))
                    roles.update(value or ())
                    merged["roles"] = sorted(roles)
                elif key == "priority_bonus":
                    merged[key] = max(int(merged.get(key, 0) or 0), int(value or 0))
                else:
                    merged.setdefault(key, value)
    return merged
