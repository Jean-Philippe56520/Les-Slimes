from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Iterable

from ..database.sqlite_repo import SQLiteRepository
from .actors import DEFAULT_ACTORS, RuntimeActor, normalize_permissions
from .commands import validate_command_payload


RUNTIME_SCHEMA = """
CREATE TABLE IF NOT EXISTS runtime_commands (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    idempotency_key TEXT NOT NULL UNIQUE,
    actor_id TEXT NOT NULL,
    command_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    source_proposal_id INTEGER,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at_utc TEXT NOT NULL,
    applied_at_utc TEXT,
    result_json TEXT,
    error_text TEXT
);

CREATE INDEX IF NOT EXISTS idx_runtime_commands_status_sequence
ON runtime_commands(status, sequence);

CREATE TABLE IF NOT EXISTS runtime_writer_lease (
    lease_name TEXT PRIMARY KEY,
    holder_id TEXT NOT NULL,
    acquired_at_utc TEXT NOT NULL,
    heartbeat_at_utc TEXT NOT NULL,
    expires_at_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runtime_actors (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    display_name TEXT NOT NULL,
    permissions_json TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1
);
"""


@dataclass(frozen=True, slots=True)
class RuntimeCommand:
    sequence: int
    id: str
    idempotency_key: str
    actor_id: str
    command_type: str
    payload: dict[str, Any]
    source_proposal_id: int | None
    status: str
    created_at_utc: datetime


class RuntimeStorage:
    def __init__(self, repository: SQLiteRepository) -> None:
        self.repository = repository
        self.initialize_schema()

    @staticmethod
    def _utc(value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Runtime timestamps must be timezone-aware")
        return value.astimezone(UTC)

    @classmethod
    def _parse_dt(cls, value: str) -> datetime:
        return cls._utc(datetime.fromisoformat(value))

    def initialize_schema(self) -> None:
        self.repository.initialize_schema()
        with self.repository._connect() as conn:
            conn.executescript(RUNTIME_SCHEMA)
            command_columns = {
                row["name"] for row in conn.execute("PRAGMA table_info(runtime_commands)")
            }
            if "source_proposal_id" not in command_columns:
                conn.execute("ALTER TABLE runtime_commands ADD COLUMN source_proposal_id INTEGER")
            for actor in DEFAULT_ACTORS:
                conn.execute(
                    """
                    INSERT INTO runtime_actors(id, kind, display_name, permissions_json, active)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO NOTHING
                    """,
                    (
                        actor.id,
                        actor.kind,
                        actor.display_name,
                        json.dumps(sorted(actor.permissions)),
                        int(actor.active),
                    ),
                )
            conn.commit()

    def get_actor(self, actor_id: str) -> RuntimeActor:
        with self.repository._connect() as conn:
            row = conn.execute(
                "SELECT * FROM runtime_actors WHERE id = ?", (actor_id,)
            ).fetchone()
        if row is None:
            raise KeyError(actor_id)
        return self._row_to_actor(row)

    def list_actors(self) -> list[RuntimeActor]:
        with self.repository._connect() as conn:
            rows = conn.execute("SELECT * FROM runtime_actors ORDER BY id").fetchall()
        return [self._row_to_actor(row) for row in rows]

    def upsert_actor(
        self,
        *,
        actor_id: str,
        kind: str,
        display_name: str,
        permissions: Iterable[str],
        active: bool = True,
    ) -> RuntimeActor:
        if not actor_id or not kind or not display_name:
            raise ValueError("actor_id, kind and display_name are required")
        normalized = normalize_permissions(permissions)
        with self.repository._connect() as conn:
            conn.execute(
                """
                INSERT INTO runtime_actors(id, kind, display_name, permissions_json, active)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    kind = excluded.kind,
                    display_name = excluded.display_name,
                    permissions_json = excluded.permissions_json,
                    active = excluded.active
                """,
                (
                    actor_id,
                    kind,
                    display_name,
                    json.dumps(sorted(normalized)),
                    int(active),
                ),
            )
            conn.commit()
        return self.get_actor(actor_id)

    def set_actor_permissions(
        self,
        actor_id: str,
        permissions: Iterable[str],
    ) -> RuntimeActor:
        actor = self.get_actor(actor_id)
        return self.upsert_actor(
            actor_id=actor.id,
            kind=actor.kind,
            display_name=actor.display_name,
            permissions=permissions,
            active=actor.active,
        )

    def set_actor_active(self, actor_id: str, active: bool) -> RuntimeActor:
        actor = self.get_actor(actor_id)
        return self.upsert_actor(
            actor_id=actor.id,
            kind=actor.kind,
            display_name=actor.display_name,
            permissions=actor.permissions,
            active=active,
        )

    def enqueue_command(
        self,
        *,
        actor_id: str,
        command_type: str,
        payload: dict[str, Any],
        idempotency_key: str,
        created_at_utc: datetime,
        source_proposal_id: int | None = None,
    ) -> RuntimeCommand:
        if not actor_id or not command_type or not idempotency_key:
            raise ValueError("actor_id, command_type and idempotency_key are required")
        self.get_actor(actor_id)
        validate_command_payload(command_type, payload)
        if source_proposal_id is not None and source_proposal_id < 1:
            raise ValueError("source_proposal_id must be positive")
        created_at = self._utc(created_at_utc)
        payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        command_id = f"CMD-{uuid.uuid4().hex}"
        with self.repository._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                "SELECT * FROM runtime_commands WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            if existing is None:
                conn.execute(
                    """
                    INSERT INTO runtime_commands(
                        id, idempotency_key, actor_id, command_type, payload_json,
                        source_proposal_id, status, created_at_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
                    """,
                    (
                        command_id,
                        idempotency_key,
                        actor_id,
                        command_type,
                        payload_json,
                        source_proposal_id,
                        created_at.isoformat(),
                    ),
                )
                existing = conn.execute(
                    "SELECT * FROM runtime_commands WHERE id = ?", (command_id,)
                ).fetchone()
            conn.commit()
        return self._row_to_command(existing)

    def pending_commands(self, *, limit: int = 1000) -> list[RuntimeCommand]:
        if limit < 1:
            return []
        with self.repository._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM runtime_commands
                WHERE status = 'pending'
                ORDER BY sequence ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._row_to_command(row) for row in rows]

    def recent_commands(self, *, limit: int = 100) -> list[sqlite3.Row]:
        with self.repository._connect() as conn:
            return conn.execute(
                "SELECT * FROM runtime_commands ORDER BY sequence DESC LIMIT ?",
                (limit,),
            ).fetchall()

    def mark_applied(
        self,
        command_id: str,
        *,
        applied_at_utc: datetime,
        result: dict[str, Any],
    ) -> None:
        applied_at = self._utc(applied_at_utc)
        with self.repository._connect() as conn:
            conn.execute(
                """
                UPDATE runtime_commands
                SET status = 'applied', applied_at_utc = ?, result_json = ?, error_text = NULL
                WHERE id = ?
                """,
                (
                    applied_at.isoformat(),
                    json.dumps(result, sort_keys=True, separators=(",", ":")),
                    command_id,
                ),
            )
            conn.commit()

    def mark_rejected(self, command_id: str, error_text: str) -> None:
        with self.repository._connect() as conn:
            conn.execute(
                "UPDATE runtime_commands SET status = 'rejected', error_text = ? WHERE id = ?",
                (error_text, command_id),
            )
            conn.commit()

    def was_persisted_as_applied(self, command_id: str) -> bool:
        with self.repository._connect() as conn:
            rows = conn.execute(
                "SELECT payload_json FROM events WHERE type = 'command_applied' ORDER BY sequence DESC"
            )
            for row in rows:
                payload = json.loads(row["payload_json"])
                if payload.get("command_id") == command_id:
                    return True
        return False

    def acquire_lease(
        self,
        *,
        holder_id: str,
        now_utc: datetime,
        ttl_seconds: float = 30.0,
        lease_name: str = "canonical_world_writer",
    ) -> bool:
        if not holder_id or ttl_seconds <= 0:
            raise ValueError("holder_id and positive ttl_seconds are required")
        now = self._utc(now_utc)
        expires = now + timedelta(seconds=ttl_seconds)
        with self.repository._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT * FROM runtime_writer_lease WHERE lease_name = ?",
                (lease_name,),
            ).fetchone()
            can_take = (
                row is None
                or row["holder_id"] == holder_id
                or self._parse_dt(row["expires_at_utc"]) <= now
            )
            if can_take:
                conn.execute(
                    """
                    INSERT INTO runtime_writer_lease(
                        lease_name, holder_id, acquired_at_utc, heartbeat_at_utc, expires_at_utc
                    ) VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(lease_name) DO UPDATE SET
                        holder_id = excluded.holder_id,
                        acquired_at_utc = excluded.acquired_at_utc,
                        heartbeat_at_utc = excluded.heartbeat_at_utc,
                        expires_at_utc = excluded.expires_at_utc
                    """,
                    (
                        lease_name,
                        holder_id,
                        now.isoformat(),
                        now.isoformat(),
                        expires.isoformat(),
                    ),
                )
            conn.commit()
        return can_take

    def heartbeat_lease(
        self,
        *,
        holder_id: str,
        now_utc: datetime,
        ttl_seconds: float = 30.0,
        lease_name: str = "canonical_world_writer",
    ) -> bool:
        now = self._utc(now_utc)
        expires = now + timedelta(seconds=ttl_seconds)
        with self.repository._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE runtime_writer_lease
                SET heartbeat_at_utc = ?, expires_at_utc = ?
                WHERE lease_name = ? AND holder_id = ?
                """,
                (now.isoformat(), expires.isoformat(), lease_name, holder_id),
            )
            conn.commit()
        return cursor.rowcount == 1

    def release_lease(
        self,
        *,
        holder_id: str,
        lease_name: str = "canonical_world_writer",
    ) -> None:
        with self.repository._connect() as conn:
            conn.execute(
                "DELETE FROM runtime_writer_lease WHERE lease_name = ? AND holder_id = ?",
                (lease_name, holder_id),
            )
            conn.commit()

    def _row_to_actor(self, row: sqlite3.Row) -> RuntimeActor:
        return RuntimeActor(
            id=str(row["id"]),
            kind=str(row["kind"]),
            display_name=str(row["display_name"]),
            permissions=frozenset(json.loads(row["permissions_json"])),
            active=bool(row["active"]),
        )

    def _row_to_command(self, row: sqlite3.Row) -> RuntimeCommand:
        return RuntimeCommand(
            sequence=int(row["sequence"]),
            id=str(row["id"]),
            idempotency_key=str(row["idempotency_key"]),
            actor_id=str(row["actor_id"]),
            command_type=str(row["command_type"]),
            payload=json.loads(row["payload_json"]),
            source_proposal_id=(
                int(row["source_proposal_id"]) if row["source_proposal_id"] is not None else None
            ),
            status=str(row["status"]),
            created_at_utc=self._parse_dt(row["created_at_utc"]),
        )
