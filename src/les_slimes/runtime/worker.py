from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Callable

from ..database.sqlite_repo import SQLiteRepository
from ..governance.models import AuthorizationDecision, DivineIntervention
from ..governance.policy import GovernancePolicy
from ..governance.storage import GovernanceStorage
from .canonical import AdvanceResult, CanonicalRuntime
from .commands import apply_command
from .storage import (
    RuntimeCommand,
    RuntimeStorage,
    WriterLease,
    WriterLeaseLost,
)


@dataclass(frozen=True, slots=True)
class WorkerRunResult:
    commands_applied: int
    commands_rejected: int
    final_advance: AdvanceResult


class WriterLeaseUnavailable(RuntimeError):
    pass


def _system_now() -> datetime:
    return datetime.now(UTC)


class CanonicalWorldWorker:
    """Single-writer mutation path for the canonical world runtime."""

    def __init__(
        self,
        repository: SQLiteRepository,
        *,
        holder_id: str,
        batch_size: int = 1000,
        lease_ttl_seconds: float = 30.0,
        clock: Callable[[], datetime] | None = None,
        command_page_size: int = 1000,
    ) -> None:
        if not holder_id:
            raise ValueError("holder_id is required")
        if lease_ttl_seconds <= 0:
            raise ValueError("lease_ttl_seconds must be > 0")
        if command_page_size < 1:
            raise ValueError("command_page_size must be >= 1")
        self.repository = repository
        self.holder_id = holder_id
        self.lease_ttl_seconds = lease_ttl_seconds
        self.clock = clock or _system_now
        self.command_page_size = command_page_size
        self.runtime = CanonicalRuntime(repository, batch_size=batch_size)
        self.storage = RuntimeStorage(repository)
        self.governance = GovernanceStorage(repository)
        self.policy = GovernancePolicy(self.storage, self.governance)

    @staticmethod
    def _utc(value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Worker timestamps must be timezone-aware")
        return value.astimezone(UTC)

    def _now(self) -> datetime:
        return self._utc(self.clock())

    def acquire_lease(self) -> WriterLease:
        lease = self.storage.acquire_lease(
            holder_id=self.holder_id,
            now_utc=self._now(),
            ttl_seconds=self.lease_ttl_seconds,
        )
        if lease is None:
            raise WriterLeaseUnavailable("Canonical writer lease is held by another worker")
        return lease

    def heartbeat_lease(self, lease: WriterLease) -> WriterLease:
        return self.storage.heartbeat_lease(
            lease,
            now_utc=self._now(),
            ttl_seconds=self.lease_ttl_seconds,
        )

    def release_lease(self, lease: WriterLease) -> None:
        self.storage.release_lease(lease)

    def _guard(self, lease_box: list[WriterLease]) -> Callable[[sqlite3.Connection], None]:
        def guard(conn: sqlite3.Connection) -> None:
            self.storage.assert_lease_in_transaction(
                conn,
                lease_box[0],
                now_utc=self._now(),
            )

        return guard

    def _heartbeat_callback(self, lease_box: list[WriterLease]) -> Callable[[], None]:
        def heartbeat() -> None:
            lease_box[0] = self.heartbeat_lease(lease_box[0])

        return heartbeat

    def _get_or_create_intervention(
        self,
        command: RuntimeCommand,
        decision: AuthorizationDecision,
    ) -> DivineIntervention:
        existing = self.governance.get_intervention_for_command(command.id)
        if existing is not None:
            return existing
        return self.governance.create_intervention(
            actor_id=command.actor_id,
            action_kind=command.command_type,
            power_level=decision.required_power_level,
            permission=decision.permission,
            command_id=command.id,
            source_proposal_id=command.source_proposal_id,
            status="authorized" if decision.allowed else "proposed",
            budget_kind=decision.budget_kind,
            budget_cost=decision.budget_cost,
            reason=decision.reason,
            now_utc=self._now(),
        )

    def _reject_command(
        self,
        command: RuntimeCommand,
        intervention: DivineIntervention,
        reason: str,
    ) -> None:
        if intervention.status != "rejected":
            self.governance.reject_intervention(
                intervention.id,
                reason=reason,
                now_utc=self._now(),
            )
        self.storage.mark_rejected(command.id, reason)

    def _governance_commit_mutator(
        self,
        command: RuntimeCommand,
        intervention: DivineIntervention,
    ) -> Callable[[sqlite3.Connection], None]:
        def mutate(conn: sqlite3.Connection) -> None:
            now = self._now()
            self.policy.assert_authorized_in_transaction(
                conn,
                command,
                now_utc=now,
            )
            self.governance.execute_intervention_in_transaction(
                conn,
                intervention=intervention,
                now_utc=now,
                father_unlimited=command.actor_id == "father",
            )

        return mutate

    def run_until_with_lease(
        self,
        target_time: datetime,
        lease: WriterLease,
    ) -> tuple[WorkerRunResult, WriterLease]:
        target = self._utc(target_time)
        lease_box = [self.heartbeat_lease(lease)]
        applied = 0
        rejected = 0

        while True:
            commands = self.storage.pending_commands_due(
                target,
                limit=self.command_page_size,
            )
            if not commands:
                break

            for command in commands:
                lease_box[0] = self.heartbeat_lease(lease_box[0])

                if self.storage.was_persisted_as_applied(command.id):
                    self.storage.mark_applied(
                        command.id,
                        applied_at_utc=self._now(),
                        result={"reconciled": True},
                    )
                    continue

                self.runtime.advance_to(
                    command.created_at_utc,
                    before_batch=self._heartbeat_callback(lease_box),
                    transaction_guard=self._guard(lease_box),
                )
                world = self.repository.load_world()
                decision = self.policy.authorize(command, now_utc=self._now())
                intervention = self._get_or_create_intervention(command, decision)
                if not decision.allowed:
                    self._reject_command(command, intervention, decision.reason)
                    rejected += 1
                    continue

                try:
                    result = apply_command(
                        world,
                        command_type=command.command_type,
                        payload=command.payload,
                        actor_id=command.actor_id,
                        source_proposal_id=command.source_proposal_id,
                    )
                except (KeyError, TypeError, ValueError, PermissionError) as exc:
                    self._reject_command(command, intervention, str(exc))
                    rejected += 1
                    continue

                world._emit(
                    "command_applied",
                    payload={
                        "command_id": command.id,
                        "command_sequence": command.sequence,
                        "intervention_id": intervention.id,
                        "actor_id": command.actor_id,
                        "command_type": command.command_type,
                        "source_proposal_id": command.source_proposal_id,
                        "result": result,
                    },
                )
                lease_box[0] = self.heartbeat_lease(lease_box[0])
                try:
                    self.repository.save_world(
                        world,
                        transaction_guard=self._guard(lease_box),
                        transaction_mutator=self._governance_commit_mutator(
                            command, intervention
                        ),
                    )
                except PermissionError as exc:
                    self._reject_command(command, intervention, str(exc))
                    rejected += 1
                    continue

                self.storage.mark_applied(
                    command.id,
                    applied_at_utc=self._now(),
                    result={**result, "intervention_id": intervention.id},
                )
                applied += 1

        final_advance = self.runtime.advance_to(
            target,
            before_batch=self._heartbeat_callback(lease_box),
            transaction_guard=self._guard(lease_box),
        )
        lease_box[0] = self.heartbeat_lease(lease_box[0])
        return (
            WorkerRunResult(
                commands_applied=applied,
                commands_rejected=rejected,
                final_advance=final_advance,
            ),
            lease_box[0],
        )

    def run_until(self, target_time: datetime) -> WorkerRunResult:
        lease = self.acquire_lease()
        latest = lease
        try:
            result, latest = self.run_until_with_lease(target_time, lease)
            return result
        finally:
            self.release_lease(latest)


__all__ = [
    "CanonicalWorldWorker",
    "WorkerRunResult",
    "WriterLeaseLost",
    "WriterLeaseUnavailable",
]
