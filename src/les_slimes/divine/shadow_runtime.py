from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .actor_gateway import DivineActorGateway


@dataclass(frozen=True, slots=True)
class ShadowCycleResult:
    actor_id: str
    source_main_sha: str
    world_tick: int
    world_state_digest: str
    journal_id: int
    governance_snapshot: dict[str, Any]
    mode: str = "shadow"


class DivineShadowCycleService:
    """Observation-only divine cycle used before autonomous execution is enabled.

    The service deliberately exposes no canonical command submission, no governance
    administration, no Git write and no promulgation. It may read the World/Registre,
    read governance and append an attributable observation journal entry.
    """

    def __init__(self, gateway: DivineActorGateway) -> None:
        self.gateway = gateway

    def run(
        self,
        meta: Mapping[str, Any],
        *,
        observation: str,
        context: dict[str, Any] | None = None,
    ) -> ShadowCycleResult:
        observation = observation.strip()
        if not observation:
            raise ValueError("shadow observation is required")

        identity = self.gateway.identity_status(meta)
        actor_id = str(identity["identity"])
        if actor_id not in {"order", "chaos"}:
            raise PermissionError("SHADOW_CYCLE_REQUIRES_ORDER_OR_CHAOS")

        source_main_sha = self.gateway.laws_main_sha(meta)
        world = self.gateway.world_observe(meta)
        governance = self.gateway.governance_status(meta)

        tick = int(world["tick"])
        digest = str(world["state_digest"])
        journal_context = {
            "shadow_cycle": True,
            "source_main_sha": source_main_sha,
            "world_state_digest": digest,
            **(context or {}),
        }
        journal = self.gateway.journal_append(
            meta,
            entry_type="observation",
            content=observation,
            world_tick=tick,
            context=journal_context,
        )
        return ShadowCycleResult(
            actor_id=actor_id,
            source_main_sha=source_main_sha,
            world_tick=tick,
            world_state_digest=digest,
            journal_id=int(journal["id"]),
            governance_snapshot=governance,
        )


@dataclass(frozen=True, slots=True)
class DivineAutonomyReadiness:
    session_identity: bool
    actor_gateway: bool
    git_read_only: bool
    drive_proposals: bool
    shadow_runtime: bool
    production_mcp_adapter: bool
    production_providers: bool
    canonical_h24_verified: bool
    autonomous_scheduling_enabled: bool

    @property
    def shadow_ready(self) -> bool:
        return (
            self.session_identity
            and self.actor_gateway
            and self.git_read_only
            and self.drive_proposals
            and self.shadow_runtime
        )

    @property
    def autonomous_ready(self) -> bool:
        return (
            self.shadow_ready
            and self.production_mcp_adapter
            and self.production_providers
            and self.canonical_h24_verified
            and self.autonomous_scheduling_enabled
        )


CURRENT_READINESS = DivineAutonomyReadiness(
    session_identity=True,
    actor_gateway=True,
    git_read_only=True,
    drive_proposals=True,
    shadow_runtime=True,
    production_mcp_adapter=False,
    production_providers=False,
    canonical_h24_verified=False,
    autonomous_scheduling_enabled=False,
)
