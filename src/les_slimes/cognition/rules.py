from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..entities import Slime


ALLOWED_CONDITIONS = {
    "energy_below",
    "energy_above",
    "age_above",
    "age_below",
    "generation_at_least",
    "memory_count_at_least",
    "relation_count_at_least",
    "signal_association_at_least",
}

ALLOWED_ACTIONS = {
    "rest",
    "explore",
    "seek_memory",
    "follow_signal",
    "follow_social",
    "move_to_point",
}


@dataclass(frozen=True, slots=True)
class BehaviorRule:
    id: str
    name: str
    priority: int
    conditions: tuple[dict[str, Any], ...]
    action: str
    parameters: dict[str, Any] = field(default_factory=dict)
    source: str = "manual"
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "priority": self.priority,
            "conditions": [dict(item) for item in self.conditions],
            "action": self.action,
            "parameters": dict(self.parameters),
            "source": self.source,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BehaviorRule":
        validate_rule_payload(data, require_id=True)
        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            priority=int(data.get("priority", 0)),
            conditions=tuple(dict(item) for item in data.get("conditions", [])),
            action=str(data["action"]),
            parameters=dict(data.get("parameters", {})),
            source=str(data.get("source", "manual")),
            enabled=bool(data.get("enabled", True)),
        )


def validate_rule_payload(data: dict[str, Any], *, require_id: bool = False) -> None:
    if not isinstance(data, dict):
        raise ValueError("Rule must be an object")
    if require_id and not data.get("id"):
        raise ValueError("Rule id is required")
    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Rule name is required")
    action = data.get("action")
    if action not in ALLOWED_ACTIONS:
        raise ValueError(f"Unsupported action {action!r}")
    priority = data.get("priority", 0)
    if not isinstance(priority, int) or not -1000 <= priority <= 1000:
        raise ValueError("priority must be an integer in [-1000, 1000]")
    conditions = data.get("conditions", [])
    if not isinstance(conditions, list) or len(conditions) > 20:
        raise ValueError("conditions must be a list with at most 20 entries")
    for condition in conditions:
        _validate_condition(condition)
    parameters = data.get("parameters", {})
    if not isinstance(parameters, dict):
        raise ValueError("parameters must be an object")
    if action == "move_to_point":
        for key in ("x", "y"):
            value = parameters.get(key)
            if not isinstance(value, (int, float)):
                raise ValueError("move_to_point requires numeric x and y")


def _validate_condition(condition: dict[str, Any]) -> None:
    if not isinstance(condition, dict):
        raise ValueError("Each condition must be an object")
    kind = condition.get("type")
    if kind not in ALLOWED_CONDITIONS:
        raise ValueError(f"Unsupported condition {kind!r}")
    if kind == "signal_association_at_least":
        signal = condition.get("signal")
        value = condition.get("value")
        if signal not in {"S1", "S2", "S3", "S4"}:
            raise ValueError("signal_association_at_least requires S1..S4")
        if not isinstance(value, (int, float)) or not 0 <= value <= 1:
            raise ValueError("Signal association threshold must be in [0,1]")
        return
    value = condition.get("value")
    if not isinstance(value, (int, float)):
        raise ValueError(f"Condition {kind!r} requires numeric value")


def rule_matches(rule: BehaviorRule, slime: Slime) -> bool:
    if not rule.enabled:
        return False
    for condition in rule.conditions:
        kind = condition["type"]
        value = condition.get("value", 0)
        if kind == "energy_below" and not slime.energy < value:
            return False
        if kind == "energy_above" and not slime.energy > value:
            return False
        if kind == "age_above" and not slime.age_ticks > value:
            return False
        if kind == "age_below" and not slime.age_ticks < value:
            return False
        if kind == "generation_at_least" and not slime.generation >= value:
            return False
        if kind == "memory_count_at_least" and not len(slime.memories) >= value:
            return False
        if kind == "relation_count_at_least" and not len(slime.relations) >= value:
            return False
        if kind == "signal_association_at_least":
            signal = condition["signal"]
            if slime.signal_food_associations.get(signal, 0.0) < value:
                return False
    return True
