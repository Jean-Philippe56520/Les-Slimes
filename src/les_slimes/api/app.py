from __future__ import annotations

import os
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field

from ..database.base import RelationalRepository
from ..database.sqlite_repo import SQLiteRepository
from ..divine.session_identity import DivineSessionBindingService
from ..governance.models import BudgetKind, JournalEntryType, PowerLevel, SanctionType
from ..governance.query import GovernanceQueryService
from ..governance.service import DivineGovernanceService, GovernanceAdminService
from ..runtime.actors import ActorPermission, RuntimeActor
from ..runtime.canonical import CanonicalRuntime
from ..runtime.storage import RuntimeCommand, RuntimeStorage
from .auth import ActorAuthenticator, AuthConfigurationError

DATABASE_PATH_ENV = "LES_SLIMES_DB_PATH"
CORS_ORIGINS_ENV = "LES_SLIMES_CORS_ORIGINS"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CommandRequest(StrictModel):
    command_type: str = Field(min_length=1)
    payload: dict[str, Any]
    idempotency_key: str = Field(min_length=1, max_length=200)
    source_proposal_id: int | None = Field(default=None, ge=1)


class JournalRequest(StrictModel):
    entry_type: JournalEntryType
    content: str = Field(min_length=1)
    world_tick: int | None = Field(default=None, ge=0)
    intervention_id: str | None = None
    git_commit: str | None = None
    context: dict[str, Any] | None = None


class ProposalRequest(StrictModel):
    proposal_type: str = Field(min_length=1)
    title: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)


class RegisterActorRequest(StrictModel):
    actor_id: str = Field(min_length=1, max_length=80)
    kind: str = Field(min_length=1, max_length=80)
    display_name: str = Field(min_length=1, max_length=160)
    permissions: list[ActorPermission] = Field(default_factory=list)
    active: bool = True
    reason: str = Field(min_length=1)


class PermissionsRequest(StrictModel):
    permissions: list[ActorPermission]
    reason: str = Field(min_length=1)


class PowerRequest(StrictModel):
    power_level: PowerLevel
    reason: str = Field(min_length=1)


class BudgetRequest(StrictModel):
    budget_kind: BudgetKind
    delta: int
    reason: str = Field(min_length=1)


class ActiveRequest(StrictModel):
    active: bool
    reason: str = Field(min_length=1)


class SanctionRequest(StrictModel):
    sanction_type: SanctionType
    reason: str = Field(min_length=1)
    parameters: dict[str, Any] | None = None
    expires_at_utc: datetime | None = None


class LiftSanctionRequest(StrictModel):
    reason: str = Field(min_length=1)


class BindDivineSessionRequest(StrictModel):
    session_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    actor_id: str = Field(min_length=1, max_length=80)


class RevokeDivineSessionRequest(StrictModel):
    session_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)




def _serialize_command(command: RuntimeCommand) -> dict[str, Any]:
    return {
        "sequence": command.sequence,
        "id": command.id,
        "idempotency_key": command.idempotency_key,
        "actor_id": command.actor_id,
        "command_type": command.command_type,
        "payload": command.payload,
        "source_proposal_id": command.source_proposal_id,
        "status": command.status,
        "created_at_utc": command.created_at_utc.isoformat(),
    }


def _serialize_actor(actor: RuntimeActor) -> dict[str, Any]:
    return {
        "id": actor.id,
        "kind": actor.kind,
        "display_name": actor.display_name,
        "permissions": sorted(actor.permissions),
        "active": actor.active,
    }


def _default_repository() -> RelationalRepository:
    path = Path(os.getenv(DATABASE_PATH_ENV, "data/world.sqlite"))
    return SQLiteRepository(path)


def _cors_origins() -> list[str]:
    raw = os.getenv(CORS_ORIGINS_ENV, "")
    return [origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip()]


def create_app(
    repository: RelationalRepository | None = None,
    *,
    authenticator: ActorAuthenticator | None = None,
) -> FastAPI:
    """Create the canonical API without acquiring the world-writer lease.

    The API can read the canonical world and enqueue attributed commands, but it never
    calls mutating World methods. The CanonicalWorldWorker remains the unique writer.
    """

    repository = repository or _default_repository()
    runtime_storage = RuntimeStorage(repository)
    runtime = CanonicalRuntime(repository)
    governance_admin = GovernanceAdminService(repository)
    governance = DivineGovernanceService(repository)
    governance_query = GovernanceQueryService(repository)
    divine_sessions = DivineSessionBindingService(repository)
    authenticator = authenticator or ActorAuthenticator.from_env(runtime_storage)
    bearer = HTTPBearer(auto_error=False)

    app = FastAPI(
        title="Les Slimes Canonical API",
        version="0.12.0-alpha",
        description="Read/enqueue boundary for the single canonical Les Slimes world.",
    )
    origins = _cors_origins()
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=False,
            allow_methods=["GET", "POST", "PUT", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type", "Accept"],
            max_age=600,
        )

    async def authenticated_actor(
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    ) -> RuntimeActor:
        if credentials is None or credentials.scheme.lower() != "bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Bearer authentication required",
            )
        try:
            return authenticator.authenticate(credentials.credentials)
        except AuthConfigurationError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="API authentication is not configured",
            ) from exc
        except PermissionError as exc:
            code = (
                status.HTTP_403_FORBIDDEN
                if "inactive" in str(exc).lower()
                else status.HTTP_401_UNAUTHORIZED
            )
            raise HTTPException(status_code=code, detail=str(exc)) from exc

    async def creator_actor(
        actor: RuntimeActor = Depends(authenticated_actor),
    ) -> RuntimeActor:
        if actor.id != "father":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Creator authority required",
            )
        return actor

    @app.exception_handler(KeyError)
    async def key_error_handler(_request, exc: KeyError):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": f"Unknown resource: {exc.args[0]}"},
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(_request, exc: ValueError):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(exc)},
        )

    @app.get("/health", tags=["runtime"])
    def health() -> dict[str, Any]:
        try:
            metadata = runtime.inspect_metadata()
            world = repository.load_world()
        except (KeyError, RuntimeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Canonical runtime unavailable: {exc}",
            ) from exc
        now = datetime.now(UTC)
        lag_seconds = max(0.0, (now - metadata.last_simulated_at_utc).total_seconds())
        ticks_due = max(0, int(lag_seconds // metadata.tick_duration_seconds))
        lease = runtime_storage.current_lease()
        lease_valid = bool(lease is not None and lease.expires_at_utc > now)
        oldest_pending = runtime_storage.oldest_pending_command_utc()
        return {
            "status": "ok",
            "world_tick": world.tick,
            "last_simulated_at_utc": metadata.last_simulated_at_utc.isoformat(),
            "wall_clock_utc": now.isoformat(),
            "lag_seconds": lag_seconds,
            "ticks_due": ticks_due,
            "pending_commands": runtime_storage.pending_command_count(),
            "oldest_pending_command_utc": oldest_pending.isoformat() if oldest_pending else None,
            "writer_lease": {
                "valid": lease_valid,
                "holder_id": lease.holder_id if lease is not None else None,
                "generation": lease.generation if lease is not None else None,
                "expires_at_utc": lease.expires_at_utc.isoformat() if lease is not None else None,
            },
        }

    @app.get("/world", tags=["world"])
    def world_summary() -> dict[str, Any]:
        world = repository.load_world()
        metrics = asdict(world.metrics())
        return {
            **metrics,
            "state_digest": world.state_digest(),
            "width": world.config.width,
            "height": world.config.height,
        }

    @app.get("/world/slimes", tags=["world"])
    def world_slimes() -> dict[str, Any]:
        world = repository.load_world()
        slimes = [
            {
                "id": slime.id,
                "parent_id": slime.parent_id,
                "generation": slime.generation,
                "x": slime.x,
                "y": slime.y,
                "heading": slime.heading,
                "energy": slime.energy,
                "health": slime.health,
                "age_ticks": slime.age_ticks,
                "current_action": slime.current_action,
                "alive": slime.alive,
            }
            for slime in sorted(world.slimes.values(), key=lambda item: item.id)
        ]
        return {"tick": world.tick, "slimes": slimes}

    @app.get("/world/foods", tags=["world"])
    def world_foods() -> dict[str, Any]:
        world = repository.load_world()
        foods = [
            {
                "id": food.id,
                "x": food.x,
                "y": food.y,
                "nutrition": food.nutrition,
            }
            for food in sorted(world.foods.values(), key=lambda item: item.id)
        ]
        return {"tick": world.tick, "foods": foods}

    @app.get("/me", tags=["identity"])
    def me(actor: RuntimeActor = Depends(authenticated_actor)) -> dict[str, Any]:
        return _serialize_actor(actor)

    @app.post("/commands", status_code=status.HTTP_201_CREATED, tags=["commands"])
    def enqueue_command(
        request: CommandRequest,
        actor: RuntimeActor = Depends(authenticated_actor),
    ) -> dict[str, Any]:
        command = runtime_storage.enqueue_command(
            actor_id=actor.id,
            command_type=request.command_type,
            payload=request.payload,
            idempotency_key=request.idempotency_key,
            created_at_utc=datetime.now(UTC),
            source_proposal_id=request.source_proposal_id,
        )
        return _serialize_command(command)

    @app.get("/governance", tags=["governance"])
    def governance_status(
        _actor: RuntimeActor = Depends(authenticated_actor),
    ) -> dict[str, Any]:
        return {
            "actors": [governance_admin.status(actor.id) for actor in runtime_storage.list_actors()]
        }

    @app.get("/journals", tags=["governance"])
    def journals(
        actor_id: str | None = None,
        limit: int = Query(default=100, ge=1, le=500),
        _actor: RuntimeActor = Depends(authenticated_actor),
    ) -> dict[str, Any]:
        return {
            "entries": governance_query.recent_journal_entries(actor_id=actor_id, limit=limit)
        }

    @app.post("/journals", status_code=status.HTTP_201_CREATED, tags=["governance"])
    def add_journal(
        request: JournalRequest,
        actor: RuntimeActor = Depends(authenticated_actor),
    ) -> dict[str, Any]:
        entry_id = governance.journal(
            actor.id,
            request.entry_type,
            request.content,
            world_tick=request.world_tick,
            intervention_id=request.intervention_id,
            git_commit=request.git_commit,
            context=request.context,
        )
        return {"id": entry_id, "actor_id": actor.id}

    @app.get("/proposals", tags=["governance"])
    def proposals(
        actor_id: str | None = None,
        limit: int = Query(default=100, ge=1, le=500),
        _actor: RuntimeActor = Depends(authenticated_actor),
    ) -> dict[str, Any]:
        return {
            "proposals": governance_query.recent_proposals(actor_id=actor_id, limit=limit)
        }

    @app.post("/proposals", status_code=status.HTTP_201_CREATED, tags=["governance"])
    def add_proposal(
        request: ProposalRequest,
        actor: RuntimeActor = Depends(authenticated_actor),
    ) -> dict[str, Any]:
        proposal_id = governance.propose(
            actor.id,
            request.proposal_type,
            request.title,
            request.payload,
        )
        return {"id": proposal_id, "actor_id": actor.id}

    @app.post("/admin/actors", status_code=status.HTTP_201_CREATED, tags=["admin"])
    def register_actor(
        request: RegisterActorRequest,
        creator: RuntimeActor = Depends(creator_actor),
    ) -> dict[str, Any]:
        actor = governance_admin.register_actor(
            actor_id=request.actor_id,
            kind=request.kind,
            display_name=request.display_name,
            permissions=request.permissions,
            active=request.active,
            reason=request.reason,
            performed_by=creator.id,
        )
        return _serialize_actor(actor)

    @app.put("/admin/actors/{actor_id}/permissions", tags=["admin"])
    def set_permissions(
        actor_id: str,
        request: PermissionsRequest,
        creator: RuntimeActor = Depends(creator_actor),
    ) -> dict[str, Any]:
        actor = governance_admin.set_permissions(
            actor_id,
            request.permissions,
            reason=request.reason,
            performed_by=creator.id,
        )
        return _serialize_actor(actor)

    @app.put("/admin/actors/{actor_id}/power", tags=["admin"])
    def set_power(
        actor_id: str,
        request: PowerRequest,
        creator: RuntimeActor = Depends(creator_actor),
    ) -> dict[str, Any]:
        state = governance_admin.set_power_level(
            actor_id,
            request.power_level,
            reason=request.reason,
            performed_by=creator.id,
        )
        return {
            "actor_id": state.actor_id,
            "max_power_level": int(state.max_power_level),
            "max_power_name": state.max_power_level.name.lower(),
        }

    @app.post("/admin/actors/{actor_id}/budget", tags=["admin"])
    def adjust_budget(
        actor_id: str,
        request: BudgetRequest,
        creator: RuntimeActor = Depends(creator_actor),
    ) -> dict[str, Any]:
        balance = governance_admin.adjust_budget(
            actor_id,
            request.budget_kind,
            request.delta,
            reason=request.reason,
            performed_by=creator.id,
        )
        return {
            "actor_id": actor_id,
            "budget_kind": request.budget_kind.value,
            "balance": balance,
        }

    @app.put("/admin/actors/{actor_id}/active", tags=["admin"])
    def set_active(
        actor_id: str,
        request: ActiveRequest,
        creator: RuntimeActor = Depends(creator_actor),
    ) -> dict[str, Any]:
        actor = governance_admin.set_active(
            actor_id,
            request.active,
            reason=request.reason,
            performed_by=creator.id,
        )
        return _serialize_actor(actor)

    @app.post("/admin/actors/{actor_id}/sanctions", status_code=status.HTTP_201_CREATED, tags=["admin"])
    def impose_sanction(
        actor_id: str,
        request: SanctionRequest,
        creator: RuntimeActor = Depends(creator_actor),
    ) -> dict[str, Any]:
        sanction = governance_admin.impose_sanction(
            actor_id,
            request.sanction_type,
            reason=request.reason,
            parameters=request.parameters,
            expires_at_utc=request.expires_at_utc,
            performed_by=creator.id,
        )
        return {
            "id": sanction.id,
            "actor_id": sanction.actor_id,
            "sanction_type": sanction.sanction_type.value,
            "reason": sanction.reason,
            "starts_at_utc": sanction.starts_at_utc.isoformat(),
            "expires_at_utc": sanction.expires_at_utc.isoformat() if sanction.expires_at_utc else None,
        }

    @app.post("/admin/divine-sessions/bind", tags=["admin"])
    def bind_divine_session(
        request: BindDivineSessionRequest,
        creator: RuntimeActor = Depends(creator_actor),
    ) -> dict[str, Any]:
        binding = divine_sessions.bind(
            session_id=request.session_id,
            subject_id=request.subject_id,
            actor_id=request.actor_id,
            performed_by=creator.id,
        )
        return {
            "session_hash": binding.session_hash,
            "actor_id": binding.actor_id,
            "status": binding.status,
            "created_at_utc": binding.created_at_utc.isoformat(),
        }

    @app.post("/admin/divine-sessions/revoke", tags=["admin"])
    def revoke_divine_session(
        request: RevokeDivineSessionRequest,
        creator: RuntimeActor = Depends(creator_actor),
    ) -> dict[str, Any]:
        binding = divine_sessions.revoke(
            session_id=request.session_id,
            reason=request.reason,
            performed_by=creator.id,
        )
        return {
            "session_hash": binding.session_hash,
            "actor_id": binding.actor_id,
            "status": binding.status,
            "revoked_at_utc": (
                binding.revoked_at_utc.isoformat()
                if binding.revoked_at_utc is not None
                else None
            ),
        }

    @app.post("/admin/sanctions/{sanction_id}/lift", tags=["admin"])
    def lift_sanction(
        sanction_id: int,
        request: LiftSanctionRequest,
        creator: RuntimeActor = Depends(creator_actor),
    ) -> dict[str, Any]:
        sanction = governance_admin.lift_sanction(
            sanction_id,
            reason=request.reason,
            performed_by=creator.id,
        )
        return {
            "id": sanction.id,
            "actor_id": sanction.actor_id,
            "sanction_type": sanction.sanction_type.value,
            "lifted_at_utc": sanction.lifted_at_utc.isoformat() if sanction.lifted_at_utc else None,
            "lifted_by": sanction.lifted_by,
        }

    return app
