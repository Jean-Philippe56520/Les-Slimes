from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable


class ActorPermission(StrEnum):
    DEPOSIT_FOOD = "world.deposit_food"
    EMIT_SIGNAL = "world.emit_signal"
    ADD_BEHAVIOR_RULE = "world.add_behavior_rule"
    REMOVE_BEHAVIOR_RULE = "world.remove_behavior_rule"
    ADD_MYSTERY = "world.add_mystery"
    REMOVE_MYSTERY = "world.remove_mystery"
    APPLY_OBSERVER_PROPOSAL = "observer.apply_proposal"


COMMAND_PERMISSIONS: dict[str, ActorPermission] = {
    "deposit_food": ActorPermission.DEPOSIT_FOOD,
    "emit_signal": ActorPermission.EMIT_SIGNAL,
}


@dataclass(frozen=True, slots=True)
class RuntimeActor:
    id: str
    kind: str
    display_name: str
    permissions: frozenset[str]
    active: bool = True

    def can(self, permission: str | ActorPermission) -> bool:
        value = permission.value if isinstance(permission, ActorPermission) else str(permission)
        return self.active and value in self.permissions


FATHER_PERMISSIONS = frozenset(permission.value for permission in ActorPermission)

DEFAULT_ACTORS: tuple[RuntimeActor, ...] = (
    RuntimeActor(
        id="father",
        kind="father",
        display_name="Le Pere",
        permissions=FATHER_PERMISSIONS,
    ),
    RuntimeActor(
        id="order",
        kind="god",
        display_name="Ordre",
        permissions=frozenset(),
    ),
    RuntimeActor(
        id="chaos",
        kind="god",
        display_name="Chaos",
        permissions=frozenset(),
    ),
    RuntimeActor(
        id="observer",
        kind="observer",
        display_name="Observateur",
        permissions=frozenset(),
    ),
    RuntimeActor(
        id="system",
        kind="system",
        display_name="Systeme",
        permissions=frozenset(),
    ),
)


def normalize_permissions(permissions: Iterable[str | ActorPermission]) -> frozenset[str]:
    allowed = {permission.value for permission in ActorPermission}
    normalized: set[str] = set()
    for permission in permissions:
        value = permission.value if isinstance(permission, ActorPermission) else str(permission)
        if value not in allowed:
            raise ValueError(f"Unknown actor permission: {value}")
        normalized.add(value)
    return frozenset(normalized)


def permission_for_command(command_type: str) -> ActorPermission:
    try:
        return COMMAND_PERMISSIONS[command_type]
    except KeyError as exc:
        raise ValueError(f"Unsupported canonical command type: {command_type}") from exc
