from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ..cognition.rules import validate_rule_payload
from ..world.engine import World
from ..world.mysteries import validate_mystery_payload
from .actors import ActorPermission


@dataclass(frozen=True, slots=True)
class CommandDefinition:
    permission: ActorPermission
    validate: Callable[[dict[str, Any]], None]
    apply: Callable[[World, dict[str, Any], str, int | None], dict[str, Any]]


def _require_number(payload: dict[str, Any], key: str) -> float:
    value = payload.get(key)
    if not isinstance(value, (int, float)):
        raise ValueError(f"{key} must be numeric")
    return float(value)


def _validate_deposit_food(payload: dict[str, Any]) -> None:
    _require_number(payload, "x")
    _require_number(payload, "y")
    count = payload.get("count", 1)
    if not isinstance(count, int) or not 1 <= count <= 100:
        raise ValueError("count must be an integer in [1, 100]")


def _apply_deposit_food(
    world: World,
    payload: dict[str, Any],
    actor_id: str,
    source_proposal_id: int | None,
) -> dict[str, Any]:
    food_ids = world.player_deposit_food(
        float(payload["x"]),
        float(payload["y"]),
        int(payload.get("count", 1)),
    )
    return {"food_ids": food_ids, "count": len(food_ids)}


def _validate_emit_signal(payload: dict[str, Any]) -> None:
    signal = payload.get("signal")
    if signal not in World.SIGNALS:
        raise ValueError(f"signal must be one of {World.SIGNALS}")
    _require_number(payload, "x")
    _require_number(payload, "y")
    if "radius" in payload and payload["radius"] is not None:
        _require_number(payload, "radius")


def _apply_emit_signal(
    world: World,
    payload: dict[str, Any],
    actor_id: str,
    source_proposal_id: int | None,
) -> dict[str, Any]:
    radius = payload.get("radius")
    receivers = world.player_emit_signal(
        str(payload["signal"]),
        float(payload["x"]),
        float(payload["y"]),
        radius=float(radius) if radius is not None else None,
    )
    return {"signal": str(payload["signal"]), "receivers": receivers}


def _validate_add_behavior_rule(payload: dict[str, Any]) -> None:
    rule = payload.get("rule")
    if not isinstance(rule, dict):
        raise ValueError("add_behavior_rule requires payload.rule")
    validate_rule_payload(rule, require_id=False)


def _apply_add_behavior_rule(
    world: World,
    payload: dict[str, Any],
    actor_id: str,
    source_proposal_id: int | None,
) -> dict[str, Any]:
    source = "observer" if source_proposal_id is not None else actor_id
    rule = world.add_behavior_rule(dict(payload["rule"]), source=source)
    return {"rule_id": rule.id}


def _validate_remove_behavior_rule(payload: dict[str, Any]) -> None:
    rule_id = payload.get("rule_id")
    if not isinstance(rule_id, str) or not rule_id:
        raise ValueError("remove_behavior_rule requires payload.rule_id")


def _apply_remove_behavior_rule(
    world: World,
    payload: dict[str, Any],
    actor_id: str,
    source_proposal_id: int | None,
) -> dict[str, Any]:
    rule_id = str(payload["rule_id"])
    world.remove_behavior_rule(rule_id)
    return {"rule_id": rule_id}


def _validate_add_mystery(payload: dict[str, Any]) -> None:
    mystery = payload.get("mystery")
    if not isinstance(mystery, dict):
        raise ValueError("add_mystery requires payload.mystery")
    validate_mystery_payload(mystery, require_id=False)


def _apply_add_mystery(
    world: World,
    payload: dict[str, Any],
    actor_id: str,
    source_proposal_id: int | None,
) -> dict[str, Any]:
    source = "observer" if source_proposal_id is not None else actor_id
    mystery = world.add_mystery(dict(payload["mystery"]), source=source)
    return {"mystery_id": mystery.id}


def _validate_remove_mystery(payload: dict[str, Any]) -> None:
    mystery_id = payload.get("mystery_id")
    if not isinstance(mystery_id, str) or not mystery_id:
        raise ValueError("remove_mystery requires payload.mystery_id")


def _apply_remove_mystery(
    world: World,
    payload: dict[str, Any],
    actor_id: str,
    source_proposal_id: int | None,
) -> dict[str, Any]:
    mystery_id = str(payload["mystery_id"])
    world.remove_mystery(mystery_id)
    return {"mystery_id": mystery_id}


COMMANDS: dict[str, CommandDefinition] = {
    "deposit_food": CommandDefinition(
        ActorPermission.DEPOSIT_FOOD,
        _validate_deposit_food,
        _apply_deposit_food,
    ),
    "emit_signal": CommandDefinition(
        ActorPermission.EMIT_SIGNAL,
        _validate_emit_signal,
        _apply_emit_signal,
    ),
    "add_behavior_rule": CommandDefinition(
        ActorPermission.ADD_BEHAVIOR_RULE,
        _validate_add_behavior_rule,
        _apply_add_behavior_rule,
    ),
    "remove_behavior_rule": CommandDefinition(
        ActorPermission.REMOVE_BEHAVIOR_RULE,
        _validate_remove_behavior_rule,
        _apply_remove_behavior_rule,
    ),
    "add_mystery": CommandDefinition(
        ActorPermission.ADD_MYSTERY,
        _validate_add_mystery,
        _apply_add_mystery,
    ),
    "remove_mystery": CommandDefinition(
        ActorPermission.REMOVE_MYSTERY,
        _validate_remove_mystery,
        _apply_remove_mystery,
    ),
}


def get_command_definition(command_type: str) -> CommandDefinition:
    try:
        return COMMANDS[command_type]
    except KeyError as exc:
        raise ValueError(f"Unsupported canonical command type: {command_type}") from exc


def permission_for_command(command_type: str) -> ActorPermission:
    return get_command_definition(command_type).permission


def validate_command_payload(command_type: str, payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise ValueError("command payload must be an object")
    get_command_definition(command_type).validate(payload)


def apply_command(
    world: World,
    *,
    command_type: str,
    payload: dict[str, Any],
    actor_id: str,
    source_proposal_id: int | None = None,
) -> dict[str, Any]:
    definition = get_command_definition(command_type)
    definition.validate(payload)
    return definition.apply(world, payload, actor_id, source_proposal_id)
