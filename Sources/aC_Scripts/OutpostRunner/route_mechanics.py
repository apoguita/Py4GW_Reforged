from __future__ import annotations

import math
from typing import Any
from typing import cast

PORTAL_EXTENSION_DISTANCE = 450.0
JUNUNDU_STRIKE_SKILL_ID = 1439


def _xy(data: dict[str, Any], key: str) -> tuple[float, float]:
    value = data[key]
    return float(value[0]), float(value[1])


def segment_steps(segment: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    """Return ordered movement steps, preserving legacy path-only routes."""

    declared = segment.get("steps")
    if isinstance(declared, (list, tuple)):
        declared_steps = cast(list[object] | tuple[object, ...], declared)
        steps: list[dict[str, Any]] = []
        for step in declared_steps:
            if not isinstance(step, dict):
                raise TypeError("OutpostRunner route steps must be dictionaries")
            steps.append(cast(dict[str, Any], step).copy())
        return tuple(steps)
    path = list(segment.get("path", []))
    return ({"type": "path", "path": path},) if path else ()


def extended_portal_path(
    points: list[tuple[float, float]],
    extension_distance: float = PORTAL_EXTENSION_DISTANCE,
    approach_origin: tuple[float, float] | None = None,
) -> list[tuple[float, float]]:
    """Add a forward point beyond a captured portal edge when heading is known."""

    route = [(float(x), float(y)) for x, y in points]
    if not route:
        return route
    if len(route) >= 2:
        previous, endpoint = route[-2], route[-1]
    elif approach_origin is not None:
        previous = (float(approach_origin[0]), float(approach_origin[1]))
        endpoint = route[-1]
    else:
        return route
    dx = endpoint[0] - previous[0]
    dy = endpoint[1] - previous[1]
    length = math.hypot(dx, dy)
    if length <= 1.0:
        return route
    scale = float(extension_distance) / length
    return [
        *route,
        (endpoint[0] + dx * scale, endpoint[1] + dy * scale),
    ]


def register_outpost_departure(
    bot: Any,
    points: list[tuple[float, float]],
    target_map_id: int,
    step_name: str,
) -> None:
    """Register an outpost exit through the public movement owner."""

    bot.Move.FollowPathAndExitMap(
        extended_portal_path(points),
        target_map_id=target_map_id,
        step_name=step_name,
    )


def _hero_slot_skill(hero_position: int, slot: int) -> int | None:
    from Py4GWCoreLib import GLOBAL_CACHE

    try:
        bar = list(GLOBAL_CACHE.SkillBar.GetHeroSkillbar(hero_position) or [])
        if len(bar) < slot:
            return None
        skill = bar[slot - 1]
        return int(getattr(getattr(skill, "id", None), "id", 0) or 0)
    except Exception:
        return None


def _expected_hero_count() -> int:
    from Py4GWCoreLib import Party

    heroes = list(Party.GetHeroes() or [])
    try:
        declared_count = int(Party.GetHeroCount() or 0)
    except Exception:
        declared_count = 0
    return max(declared_count, len(heroes))


def _party_slot_one() -> tuple[int | None, tuple[int | None, ...]]:
    from Py4GWCoreLib import GLOBAL_CACHE
    from Py4GWCoreLib import Party

    try:
        player_skill = int(GLOBAL_CACHE.SkillBar.GetSkillIDBySlot(1) or 0)
    except Exception:
        player_skill = None
    heroes = list(Party.GetHeroes() or [])
    expected_count = _expected_hero_count()
    if len(heroes) != expected_count:
        return player_skill, tuple(None for _ in range(expected_count))
    return player_skill, tuple(_hero_slot_skill(position, 1) for position, _hero in enumerate(heroes, start=1))


def full_hero_party_in_junundu() -> bool:
    player_skill, hero_skills = _party_slot_one()
    return bool(
        player_skill == JUNUNDU_STRIKE_SKILL_ID and all(skill == JUNUNDU_STRIKE_SKILL_ID for skill in hero_skills)
    )


def full_hero_party_in_human_form() -> bool:
    player_skill, hero_skills = _party_slot_one()
    observed = (player_skill,) + hero_skills
    return bool(
        all(skill is not None for skill in observed) and all(skill != JUNUNDU_STRIKE_SKILL_ID for skill in observed)
    )


def _required_heroes_close(center_xy: tuple[float, float], radius: float) -> bool:
    from Py4GWCoreLib import Agent
    from Py4GWCoreLib import Party

    heroes = list(Party.GetHeroes() or [])
    if len(heroes) != _expected_hero_count():
        return False
    for hero in heroes:
        agent_id = int(getattr(hero, "agent_id", 0) or 0)
        if (
            agent_id <= 0
            or not Agent.IsValid(agent_id)
            or Agent.IsDead(agent_id)
            or math.dist(center_xy, Agent.GetXY(agent_id)) > radius
        ):
            return False
    return True


def _blessing_active(effect_ids: tuple[int, ...]) -> bool:
    from Py4GWCoreLib import Effects
    from Py4GWCoreLib import Player

    player_id = int(Player.GetAgentID() or 0)
    return player_id > 0 and any(Effects.HasEffect(player_id, effect_id) for effect_id in effect_ids)


def _register_automatic_dialog(bot: Any, button_number: int, step_name: str) -> None:
    """Register the existing public visible-dialog operation as a Botting step."""

    def _send_visible_choice():
        from Py4GWCoreLib import Routines

        yield from Routines.Yield.Player.SendAutomaticDialog(
            button_number,
            log=True,
        )

    bot.States.AddCustomState(_send_visible_choice, step_name)


def _register_blessing(bot: Any, data: dict[str, Any], label: str) -> None:
    approach_xy = _xy(data, "player_approach_xy")
    target_xy = _xy(data, "target_xy")
    effect_ids = tuple(int(value) for value in data["effect_ids"])
    bot.Move.FollowAutoPath([approach_xy], step_name=f"{label}: approach")
    bot.Interact.WithNpcAtXY(*target_xy, step_name=f"{label}: interact")
    _register_automatic_dialog(
        bot,
        max(0, int(data.get("visible_button", 1)) - 1),
        f"{label}: choose blessing",
    )
    bot.Wait.UntilCondition(
        lambda effects=effect_ids: _blessing_active(effects),
        duration=200,
    )


def _register_enter_junundu(bot: Any, data: dict[str, Any], label: str) -> None:
    target_xy = _xy(data, "target_xy")
    approach_xy = _xy(data, "player_approach_xy")
    regroup_xy = _xy(data, "party_regroup_xy") if "party_regroup_xy" in data else target_xy
    regroup_radius = float(data.get("party_regroup_radius", 300.0))
    bot.Move.FollowAutoPath([approach_xy], step_name=f"{label}: approach")
    bot.Party.FlagAllHeroes(*regroup_xy)
    bot.Wait.UntilCondition(
        lambda center=regroup_xy, radius=regroup_radius: _required_heroes_close(
            center,
            radius,
        ),
        duration=200,
    )
    bot.Interact.WithGadgetAtXY(*target_xy, step_name=f"{label}: interact")
    bot.Wait.UntilCondition(full_hero_party_in_junundu, duration=200)
    bot.Party.UnflagAllHeroes()


def _register_npc_dialog_sequence(
    bot: Any,
    data: dict[str, Any],
    label: str,
) -> None:
    approach_xy = _xy(data, "player_approach_xy")
    target_xy = _xy(data, "target_xy")
    target_map_id = int(data["target_map_id"])
    bot.Move.FollowAutoPath([approach_xy], step_name=f"{label}: approach")
    bot.Interact.WithNpcAtXY(*target_xy, step_name=f"{label}: interact")
    for choice_index, _choice_label in enumerate(
        tuple(data["visible_button_labels"]),
        start=1,
    ):
        _register_automatic_dialog(
            bot,
            0,
            f"{label}: visible choice {choice_index}",
        )
    bot.Wait.ForMapLoad(target_map_id=target_map_id, timeout_ms=90_000)


def register_botting_segment(
    bot: Any,
    route_name: str,
    segment_index: int,
    segment: dict[str, Any],
    target_map_id: int = 0,
    resume_key_prefix: str = "",
) -> bool:
    """Register one shared movement segment and report whether it owns map travel."""

    steps = segment_steps(segment)
    owns_map_travel = False
    for step_index, step in enumerate(steps, start=1):
        step_type = str(step.get("type", "")).strip().lower()
        label = str(step.get("name") or f"{route_name} segment {segment_index + 1} step {step_index}")
        resume_key = f"{resume_key_prefix}:segment:{segment_index}:step:{step_index}" if resume_key_prefix else None
        if step_type == "path":
            points = list(step.get("path", []))
            if not points:
                continue
            if target_map_id and step_index == len(steps):
                portal_path = (
                    [*points, _xy(segment, "portal_exit_xy")]
                    if "portal_exit_xy" in segment
                    else extended_portal_path(points)
                )
                exit_kwargs: dict[str, Any] = {
                    "target_map_id": target_map_id,
                    "step_name": label,
                }
                if resume_key is not None:
                    exit_kwargs["resume_key"] = resume_key
                bot.Move.FollowPathAndExitMap(portal_path, **exit_kwargs)
                owns_map_travel = True
            else:
                path_kwargs: dict[str, Any] = {"step_name": label}
                if resume_key is not None:
                    path_kwargs["resume_key"] = resume_key
                bot.Move.FollowAutoPath(points, **path_kwargs)
            continue
        if step_type == "direct_path":
            points = list(step.get("path", []))
            if points:
                bot.Move.FollowPath(points, step_name=label)
            continue
        if step_type == "blessing":
            _register_blessing(bot, step, label)
            continue
        if step_type == "enter_junundu":
            _register_enter_junundu(bot, step, label)
            continue
        if step_type == "verify_human_form":
            bot.Wait.UntilCondition(full_hero_party_in_human_form, duration=200)
            continue
        if step_type == "npc_dialog_sequence":
            _register_npc_dialog_sequence(bot, step, label)
            owns_map_travel = True
            continue
        raise ValueError(
            f"Unsupported OutpostRunner route step type: {step_type!r}; "
            "route mechanics only compose registered public Py4GWCoreLib owners"
        )
    return owns_map_travel
