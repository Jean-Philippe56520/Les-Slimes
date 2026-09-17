from __future__ import annotations

import json
from typing import Any

from ..database.scope import ensure_canonical_scope
from ..database.sqlite_repo import SQLiteRepository
from .storage import GovernanceStorage


class GovernanceQueryService:
    """Read-only projections for API and user interfaces."""

    def __init__(self, repository: SQLiteRepository) -> None:
        ensure_canonical_scope(repository)
        self.repository = repository
        GovernanceStorage(repository).initialize_schema()

    @staticmethod
    def _limit(value: int) -> int:
        if value < 1 or value > 500:
            raise ValueError("limit must be between 1 and 500")
        return value

    def recent_journal_entries(
        self,
        *,
        actor_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        limit = self._limit(limit)
        sql = "SELECT * FROM divine_journal_entries"
        params: list[Any] = []
        if actor_id is not None:
            sql += " WHERE actor_id = ?"
            params.append(actor_id)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        with self.repository._connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
        return [
            {
                "id": int(row["id"]),
                "actor_id": str(row["actor_id"]),
                "entry_type": str(row["entry_type"]),
                "world_tick": int(row["world_tick"]) if row["world_tick"] is not None else None,
                "intervention_id": str(row["intervention_id"]) if row["intervention_id"] else None,
                "git_commit": str(row["git_commit"]) if row["git_commit"] else None,
                "content": str(row["content"]),
                "context": json.loads(row["context_json"]),
                "created_at_utc": str(row["created_at_utc"]),
            }
            for row in rows
        ]

    def recent_proposals(
        self,
        *,
        actor_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        limit = self._limit(limit)
        sql = "SELECT * FROM divine_proposals"
        params: list[Any] = []
        if actor_id is not None:
            sql += " WHERE actor_id = ?"
            params.append(actor_id)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        with self.repository._connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
        return [
            {
                "id": int(row["id"]),
                "actor_id": str(row["actor_id"]),
                "proposal_type": str(row["proposal_type"]),
                "title": str(row["title"]),
                "payload": json.loads(row["payload_json"]),
                "status": str(row["status"]),
                "created_at_utc": str(row["created_at_utc"]),
                "decided_at_utc": str(row["decided_at_utc"]) if row["decided_at_utc"] else None,
                "decided_by": str(row["decided_by"]) if row["decided_by"] else None,
                "decision_reason": str(row["decision_reason"]) if row["decision_reason"] else None,
            }
            for row in rows
        ]
