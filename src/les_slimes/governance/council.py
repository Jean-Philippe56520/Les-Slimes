from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from ..database.scope import ensure_canonical_scope
from ..database.sqlite_repo import SQLiteRepository
from ..runtime.storage import RuntimeStorage


COUNCIL_SCHEMA = """
CREATE TABLE IF NOT EXISTS divine_councils (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    council_key TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    created_at_utc TEXT NOT NULL,
    closed_at_utc TEXT
);

CREATE TABLE IF NOT EXISTS divine_council_positions (
    council_id INTEGER NOT NULL,
    actor_id TEXT NOT NULL,
    proposal_id INTEGER,
    position TEXT NOT NULL,
    argument TEXT NOT NULL,
    created_at_utc TEXT NOT NULL,
    PRIMARY KEY (council_id, actor_id, proposal_id),
    FOREIGN KEY (council_id) REFERENCES divine_councils(id) ON DELETE CASCADE
);
"""


class DivineCouncilStorage:
    def __init__(self, repository: SQLiteRepository) -> None:
        ensure_canonical_scope(repository)
        self.repository = repository
        self.runtime = RuntimeStorage(repository)
        self.initialize_schema()

    @staticmethod
    def _utc(value: datetime | None = None) -> datetime:
        value = value or datetime.now(UTC)
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Council timestamps must be timezone-aware")
        return value.astimezone(UTC)

    def initialize_schema(self) -> None:
        with self.repository._connect() as conn:
            conn.executescript(COUNCIL_SCHEMA)
            conn.commit()

    def create_council(
        self,
        council_key: str,
        title: str,
        *,
        now_utc: datetime | None = None,
    ) -> int:
        if not council_key.strip() or not title.strip():
            raise ValueError("council_key and title are required")
        now = self._utc(now_utc)
        with self.repository._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO divine_councils(council_key, title, created_at_utc)
                VALUES (?, ?, ?)
                """,
                (council_key, title, now.isoformat()),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def set_position(
        self,
        council_id: int,
        actor_id: str,
        *,
        position: str,
        argument: str,
        proposal_id: int | None = None,
        now_utc: datetime | None = None,
    ) -> None:
        actor = self.runtime.get_actor(actor_id)
        if not actor.active:
            raise PermissionError("Inactive actors cannot take a council position")
        if position not in {"support", "oppose", "amend", "abstain", "refer_to_father"}:
            raise ValueError("Unsupported council position")
        if not argument.strip():
            raise ValueError("Council argument is required")
        now = self._utc(now_utc)
        normalized_proposal = proposal_id if proposal_id is not None else 0
        with self.repository._connect() as conn:
            conn.execute(
                """
                INSERT INTO divine_council_positions(
                    council_id, actor_id, proposal_id, position, argument, created_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(council_id, actor_id, proposal_id) DO UPDATE SET
                    position = excluded.position,
                    argument = excluded.argument,
                    created_at_utc = excluded.created_at_utc
                """,
                (council_id, actor_id, normalized_proposal, position, argument, now.isoformat()),
            )
            conn.commit()

    def list_positions(self, council_id: int) -> list[dict[str, Any]]:
        with self.repository._connect() as conn:
            rows = conn.execute(
                """
                SELECT actor_id, proposal_id, position, argument, created_at_utc
                FROM divine_council_positions WHERE council_id = ?
                ORDER BY actor_id, proposal_id
                """,
                (council_id,),
            ).fetchall()
        return [dict(row) for row in rows]
