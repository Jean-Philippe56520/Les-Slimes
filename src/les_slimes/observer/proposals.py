from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..cognition.rules import validate_rule_payload
from ..world.engine import World
from ..world.mysteries import validate_mystery_payload


PROPOSAL_TYPES = {
    "observation",
    "hypothesis",
    "experiment_proposal",
    "behavior_candidate",
    "world_event_proposal",
    "mystery_proposal",
}


@dataclass(frozen=True, slots=True)
class ObserverProposal:
    type: str
    summary: str
    confidence: float
    evidence: tuple[str, ...]
    parameters: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "summary": self.summary,
            "confidence": self.confidence,
            "evidence": list(self.evidence),
            "parameters": dict(self.parameters),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ObserverProposal":
        validate_proposal(data)
        return cls(
            type=str(data["type"]),
            summary=str(data["summary"]),
            confidence=float(data["confidence"]),
            evidence=tuple(str(item) for item in data.get("evidence", [])),
            parameters=dict(data.get("parameters", {})),
        )


def validate_proposal(data: dict[str, Any]) -> None:
    if not isinstance(data, dict):
        raise ValueError("Proposal must be an object")
    proposal_type = data.get("type")
    if proposal_type not in PROPOSAL_TYPES:
        raise ValueError(f"Unsupported proposal type {proposal_type!r}")
    summary = data.get("summary")
    if not isinstance(summary, str) or not summary.strip() or len(summary) > 1000:
        raise ValueError("summary must be a non-empty string up to 1000 chars")
    confidence = data.get("confidence")
    if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        raise ValueError("confidence must be in [0,1]")
    evidence = data.get("evidence", [])
    if not isinstance(evidence, list) or len(evidence) > 50:
        raise ValueError("evidence must be a list of at most 50 strings")
    if not all(isinstance(item, str) and item for item in evidence):
        raise ValueError("evidence entries must be non-empty strings")
    parameters = data.get("parameters", {})
    if not isinstance(parameters, dict):
        raise ValueError("parameters must be an object")

    if proposal_type == "behavior_candidate":
        rule = parameters.get("rule")
        if not isinstance(rule, dict):
            raise ValueError("behavior_candidate requires parameters.rule")
        validate_rule_payload(rule, require_id=False)

    if proposal_type == "mystery_proposal":
        mystery = parameters.get("mystery")
        if not isinstance(mystery, dict):
            raise ValueError("mystery_proposal requires parameters.mystery")
        validate_mystery_payload(mystery, require_id=False)

    if proposal_type == "world_event_proposal":
        action = parameters.get("action")
        if action not in {"deposit_food", "emit_signal"}:
            raise ValueError("world_event_proposal action must be deposit_food or emit_signal")
        if action == "deposit_food":
            _require_number(parameters, "x")
            _require_number(parameters, "y")
            count = parameters.get("count", 1)
            if not isinstance(count, int) or not 1 <= count <= 100:
                raise ValueError("deposit_food count must be in [1,100]")
        if action == "emit_signal":
            if parameters.get("signal") not in World.SIGNALS:
                raise ValueError("emit_signal requires signal S1..S4")
            _require_number(parameters, "x")
            _require_number(parameters, "y")
            if "radius" in parameters:
                _require_number(parameters, "radius")


def _require_number(data: dict[str, Any], key: str) -> None:
    if not isinstance(data.get(key), (int, float)):
        raise ValueError(f"{key} must be numeric")


def apply_proposal(world: World, proposal: ObserverProposal) -> dict[str, Any]:
    if proposal.type == "behavior_candidate":
        rule = world.add_behavior_rule(
            dict(proposal.parameters["rule"]), source="observer"
        )
        return {"applied": True, "kind": "behavior_rule", "rule_id": rule.id}

    if proposal.type == "mystery_proposal":
        mystery = world.add_mystery(
            dict(proposal.parameters["mystery"]), source="observer"
        )
        return {"applied": True, "kind": "mystery", "mystery_id": mystery.id}

    if proposal.type == "world_event_proposal":
        params = proposal.parameters
        action = params["action"]
        if action == "deposit_food":
            ids = world.player_deposit_food(
                float(params["x"]),
                float(params["y"]),
                int(params.get("count", 1)),
            )
            return {"applied": True, "kind": action, "food_ids": ids}
        if action == "emit_signal":
            receivers = world.player_emit_signal(
                str(params["signal"]),
                float(params["x"]),
                float(params["y"]),
                float(params["radius"]) if "radius" in params else None,
            )
            return {"applied": True, "kind": action, "receivers": receivers}

    return {
        "applied": False,
        "kind": proposal.type,
        "reason": "Analytical proposals do not mutate the world",
    }
