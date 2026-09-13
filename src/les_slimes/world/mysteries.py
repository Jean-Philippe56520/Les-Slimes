from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


ALLOWED_MYSTERY_EFFECTS = {
    "energy_delta",
    "health_delta",
    "memory_amplify",
    "signal_pulse",
}


@dataclass(slots=True)
class MysteryObject:
    id: str
    public_label: str
    x: float
    y: float
    radius: float
    effect: str
    parameters: dict[str, Any]
    source: str = "manual"
    active: bool = True
    trigger_count: int = 0
    discoveries: dict[str, int] = field(default_factory=dict)
    last_trigger_by: dict[str, int] = field(default_factory=dict)

    def public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "public_label": self.public_label,
            "x": self.x,
            "y": self.y,
            "radius": self.radius,
            "active": self.active,
            "trigger_count": self.trigger_count,
            "discovered_by_count": sum(1 for value in self.discoveries.values() if value >= 3),
        }

    def to_dict(self, *, include_hidden: bool = True) -> dict[str, Any]:
        data = self.public_dict()
        data.update(
            {
                "source": self.source,
                "discoveries": dict(self.discoveries),
                "last_trigger_by": dict(self.last_trigger_by),
            }
        )
        if include_hidden:
            data["effect"] = self.effect
            data["parameters"] = dict(self.parameters)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MysteryObject":
        validate_mystery_payload(data, require_id=True)
        return cls(
            id=str(data["id"]),
            public_label=str(data["public_label"]),
            x=float(data["x"]),
            y=float(data["y"]),
            radius=float(data["radius"]),
            effect=str(data["effect"]),
            parameters=dict(data.get("parameters", {})),
            source=str(data.get("source", "manual")),
            active=bool(data.get("active", True)),
            trigger_count=int(data.get("trigger_count", 0)),
            discoveries={str(k): int(v) for k, v in data.get("discoveries", {}).items()},
            last_trigger_by={str(k): int(v) for k, v in data.get("last_trigger_by", {}).items()},
        )


def validate_mystery_payload(data: dict[str, Any], *, require_id: bool = False) -> None:
    if not isinstance(data, dict):
        raise ValueError("Mystery must be an object")
    if require_id and not data.get("id"):
        raise ValueError("Mystery id is required")
    label = data.get("public_label")
    if not isinstance(label, str) or not label.strip() or len(label) > 120:
        raise ValueError("public_label must be a non-empty string up to 120 chars")
    for key in ("x", "y", "radius"):
        if not isinstance(data.get(key), (int, float)):
            raise ValueError(f"Mystery {key} must be numeric")
    if float(data["radius"]) <= 0:
        raise ValueError("Mystery radius must be positive")
    effect = data.get("effect")
    if effect not in ALLOWED_MYSTERY_EFFECTS:
        raise ValueError(f"Unsupported mystery effect {effect!r}")
    params = data.get("parameters", {})
    if not isinstance(params, dict):
        raise ValueError("Mystery parameters must be an object")
    if effect in {"energy_delta", "health_delta"}:
        amount = params.get("amount")
        if not isinstance(amount, (int, float)) or not -20 <= amount <= 20:
            raise ValueError(f"{effect} amount must be in [-20,20]")
    elif effect == "memory_amplify":
        factor = params.get("factor")
        if not isinstance(factor, (int, float)) or not 1.0 <= factor <= 1.5:
            raise ValueError("memory_amplify factor must be in [1.0,1.5]")
    elif effect == "signal_pulse":
        if params.get("signal") not in {"S1", "S2", "S3", "S4"}:
            raise ValueError("signal_pulse requires signal S1..S4")
        if "radius" in params and (
            not isinstance(params["radius"], (int, float)) or params["radius"] <= 0
        ):
            raise ValueError("signal_pulse radius must be positive")
