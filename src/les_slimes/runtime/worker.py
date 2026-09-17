from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from ..database.sqlite_repo import SQLiteRepository
from .actors import permission_for_command
from .canonical import AdvanceResult, CanonicalRuntime
from .storage import RuntimeCommand, RuntimeStorage


@dataclass(frozen=True, slots=True)
class WorkerRunResult:
    commands_applied: int
    commands_rejected: int
    final_advance: AdvanceResult


class WriterLeaseUnavailable(RuntimeError):
    pass


class CanonicalWorldWorker:
    """Single-writer mutation path for the canonical world runtime."""

    def __init__(
        self,
        repository: SQLiteRepository,
        *,
        holder_id: str,
        batch_size: int = 1000,
        lease_ttl_seconds: float = 30.0,
    ) -> None:
        if not holder_id:
            raise ValueError("holder_id is required")
        self.repository = repository
        self.holder_id = holder_id
        self.lease_ttl_seconds = lease_ttl_seconds
        self.runtime = CanonicalRuntime(repository, batch_size=batch_size)
        self.storage = RuntimeStorage(repository)

    @staticmethod
    def _utc(value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Worker timestamps must be timezone-aware")
        return value.astimezone(UTC)

    def run_until(self, target_time: datetime) -> WorkerRunResult:
        target = self._utc(target_time)
        if not self.storage.acquire_lease(
            holder_id=self.holder_id,
            now_utc=target,
            ttl_seconds=self.lease_ttl_seconds,
        ):
            raise WriterLeaseUnavailable("Canonical writer lease is held by another worker")

        applied = 0
        rejected = 0
        try:
            for command in self.storage.pending_commands():
                if command.created_at_utc > target:
                    break

                if self.storage.was_persisted_as_applied(command.id):
                    self.storage.mark_applied(
                        command.id,
                        applied_at_utc=target,
                        result={"reconciled": True},
                    )
                    continue

                self.runtime.advance_to(command.created_at_utc)
                world = self.repository.load_world()
                try:
                    self._authorize(command)
                    result = self._apply_to_world(world, command)
                except (KeyError, TypeError, ValueError, PermissionError) as exc:
                    self.storage.mark_rejected(command.id, str(exc))
                    rejected += 1
                    continue

                world._emit(
                    "command_applied",
                    payload={
                        "command_id": command.id,
                        "command_sequence": command.sequence,
                        "actor_id": command.actor_id,
                        "command_type": command.command_type,
                        "result": result,
                    },
                )
                self.repository.save_world(world)
                self.storage.mark_applied(
                    command.id,
                    applied_at_utc=target,
                    result=result,
                )
                applied += 1
                self.storage.heartbeat_lease(
                    holder_id=self.holder_id,
                    now_utc=target,
                    ttl_seconds=self.lease_ttl_seconds,
                )

            final_advance = self.runtime.advance_to(target)
            return WorkerRunResult(
                commands_applied=applied,
                commands_rejected=rejected,
                final_advance=final_advance,
            )
        finally:
            self.storage.release_lease(holder_id=self.holder_id)

    def _authorize(self, command: RuntimeCommand) -> None:
        actor = self.storage.get_actor(command.actor_id)
        if not actor.active:
            raise PermissionError(f"Actor {actor.id!r} is inactive")
        permission = permission_for_command(command.command_type)
        if not actor.can(permission):
            raise PermissionError(
                f"Actor {actor.id!r} lacks permission {permission.value!r}"
            )

    @staticmethod
    def _apply_to_world(world, command: RuntimeCommand) -> dict[str, Any]:
        payload = command.payload
        if command.command_type == "deposit_food":
            x = float(payload["x"])
            y = float(payload["y"])
            count = int(payload.get("count", 1))
            food_ids = world.player_deposit_food(x, y, count)
            return {"food_ids": food_ids, "count": len(food_ids)}

        if command.command_type == "emit_signal":
            signal = str(payload["signal"])
            x = float(payload["x"])
            y = float(payload["y"])
            radius = payload.get("radius")
            if radius is not None:
                radius = float(radius)
            receivers = world.player_emit_signal(signal, x, y, radius=radius)
            return {"signal": signal, "receivers": receivers}

        raise ValueError(f"Unsupported canonical command type: {command.command_type}")
