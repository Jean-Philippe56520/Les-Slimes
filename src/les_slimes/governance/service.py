from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any, Iterable

from ..database.sqlite_repo import SQLiteRepository
from ..runtime.actors import ActorPermission, normalize_permissions
from ..runtime.storage import RuntimeStorage
from .models import BudgetKind, JournalEntryType, PowerLevel, SanctionType
from .storage import GovernanceStorage


class GovernanceAdminService:
    """Trusted Father-only administration path for divine governance."""

    def __init__(self, repository: SQLiteRepository) -> None:
        self.repository = repository
        self.runtime = RuntimeStorage(repository)
        self.storage = GovernanceStorage(repository)

    @staticmethod
    def _utc(value: datetime | None = None) -> datetime:
        value = value or datetime.now(UTC)
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Governance timestamps must be timezone-aware")
        return value.astimezone(UTC)

    @staticmethod
    def _require_father(performed_by: str) -> None:
        if performed_by != "father":
            raise PermissionError("Only the Father may administer divine governance")

    def set_permissions(
        self,
        actor_id: str,
        permissions: Iterable[str | ActorPermission],
        *,
        reason: str,
        performed_by: str = "father",
        now_utc: datetime | None = None,
    ):
        self._require_father(performed_by)
        actor = self.runtime.get_actor(actor_id)
        normalized = normalize_permissions(permissions)
        now = self._utc(now_utc)
        with self.repository._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "UPDATE runtime_actors SET permissions_json = ? WHERE id = ?",
                (json.dumps(sorted(normalized)), actor_id),
            )
            self.storage.append_audit_in_transaction(
                conn,
                event_type="permissions_set",
                actor_id=performed_by,
                subject_actor_id=actor_id,
                payload={"permissions": sorted(normalized), "reason": reason},
                created_at_utc=now,
            )
            conn.commit()
        return self.runtime.get_actor(actor.id)

    def set_active(
        self,
        actor_id: str,
        active: bool,
        *,
        reason: str,
        performed_by: str = "father",
        now_utc: datetime | None = None,
    ):
        self._require_father(performed_by)
        self.runtime.get_actor(actor_id)
        now = self._utc(now_utc)
        with self.repository._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "UPDATE runtime_actors SET active = ? WHERE id = ?",
                (int(active), actor_id),
            )
            self.storage.append_audit_in_transaction(
                conn,
                event_type="actor_activation_changed",
                actor_id=performed_by,
                subject_actor_id=actor_id,
                payload={"active": active, "reason": reason},
                created_at_utc=now,
            )
            conn.commit()
        return self.runtime.get_actor(actor_id)

    def set_power_level(
        self,
        actor_id: str,
        power_level: PowerLevel,
        *,
        reason: str,
        performed_by: str = "father",
        now_utc: datetime | None = None,
    ):
        self._require_father(performed_by)
        self.runtime.get_actor(actor_id)
        return self.storage.set_power_level(
            actor_id,
            power_level,
            performed_by=performed_by,
            reason=reason,
            now_utc=self._utc(now_utc),
        )

    def adjust_budget(
        self,
        actor_id: str,
        kind: BudgetKind,
        delta: int,
        *,
        reason: str,
        performed_by: str = "father",
        now_utc: datetime | None = None,
    ) -> int:
        self._require_father(performed_by)
        self.runtime.get_actor(actor_id)
        return self.storage.adjust_budget(
            actor_id,
            kind,
            delta,
            performed_by=performed_by,
            reason=reason,
            now_utc=self._utc(now_utc),
        )

    def impose_sanction(
        self,
        actor_id: str,
        sanction_type: SanctionType,
        *,
        reason: str,
        parameters: dict[str, Any] | None = None,
        expires_at_utc: datetime | None = None,
        performed_by: str = "father",
        now_utc: datetime | None = None,
    ):
        self._require_father(performed_by)
        self.runtime.get_actor(actor_id)
        now = self._utc(now_utc)
        return self.storage.impose_sanction(
            actor_id,
            sanction_type,
            parameters=parameters,
            reason=reason,
            imposed_by=performed_by,
            starts_at_utc=now,
            expires_at_utc=expires_at_utc,
        )

    def lift_sanction(
        self,
        sanction_id: int,
        *,
        reason: str,
        performed_by: str = "father",
        now_utc: datetime | None = None,
    ):
        self._require_father(performed_by)
        return self.storage.lift_sanction(
            sanction_id,
            lifted_by=performed_by,
            reason=reason,
            now_utc=self._utc(now_utc),
        )

    def status(self, actor_id: str, *, now_utc: datetime | None = None) -> dict[str, Any]:
        actor = self.runtime.get_actor(actor_id)
        state = self.storage.get_actor_state(actor_id)
        now = self._utc(now_utc)
        sanctions = self.storage.active_sanctions(actor_id, now_utc=now)
        return {
            "actor_id": actor.id,
            "display_name": actor.display_name,
            "kind": actor.kind,
            "active": actor.active,
            "permissions": sorted(actor.permissions),
            "max_power_level": int(state.max_power_level),
            "max_power_name": state.max_power_level.name.lower(),
            "budgets": {
                kind.value: self.storage.budget_balance(actor_id, kind)
                for kind in BudgetKind
            },
            "active_sanctions": [
                {
                    **asdict(sanction),
                    "sanction_type": sanction.sanction_type.value,
                    "starts_at_utc": sanction.starts_at_utc.isoformat(),
                    "expires_at_utc": sanction.expires_at_utc.isoformat() if sanction.expires_at_utc else None,
                    "lifted_at_utc": sanction.lifted_at_utc.isoformat() if sanction.lifted_at_utc else None,
                }
                for sanction in sanctions
            ],
            "audit_chain_valid": self.storage.validate_audit_chain(),
        }


class DivineGovernanceService:
    """Non-administrative journal/proposal operations available to known actors."""

    def __init__(self, repository: SQLiteRepository) -> None:
        self.runtime = RuntimeStorage(repository)
        self.storage = GovernanceStorage(repository)

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    def journal(
        self,
        actor_id: str,
        entry_type: JournalEntryType,
        content: str,
        *,
        world_tick: int | None = None,
        intervention_id: str | None = None,
        git_commit: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> int:
        self.runtime.get_actor(actor_id)
        return self.storage.add_journal_entry(
            actor_id=actor_id,
            entry_type=entry_type,
            content=content,
            now_utc=self._now(),
            world_tick=world_tick,
            intervention_id=intervention_id,
            git_commit=git_commit,
            context=context,
        )

    def propose(
        self,
        actor_id: str,
        proposal_type: str,
        title: str,
        payload: dict[str, Any],
    ) -> int:
        actor = self.runtime.get_actor(actor_id)
        if not actor.active:
            raise PermissionError("Inactive actors cannot create proposals")
        return self.storage.create_proposal(
            actor_id=actor_id,
            proposal_type=proposal_type,
            title=title,
            payload=payload,
            now_utc=self._now(),
        )
