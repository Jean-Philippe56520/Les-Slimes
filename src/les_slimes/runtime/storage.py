from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Iterable

from ..database.scope import ensure_canonical_scope
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
    lease_token TEXT,
    generation INTEGER NOT NULL DEFAULT 0,
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


@dataclass(frozen=True, slots=True)
class WriterLease:
    lease_name: str
    holder_id: str
    lease_token: str
    generation: int
    acquired_at_utc: datetime
    heartbeat_at_utc: datetime
    expires_at_utc: datetime


class WriterLeaseLost(RuntimeError):
    pass


class RuntimeStorage:
    def __init__(self, repository: SQLiteRepository) -> None:
        ensure_canonical_scope(repository)
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

            lease_columns = {
                row["name"] for row in conn.execute("PRAGMA table_info(runtime_writer_lease)")
            }
            if "lease_token" not in lease_columns:
                conn.execute("ALTER TABLE runtime_writer_lease ADD COLUMN lease_token TEXT")
            if "generation" not in lease_columns:
                conn.execute(
                    "ALTER TABLE runtime_writer_lease ADD COLUMN generation INTEGER NOT NULL DEFAULT 0"
                )
            conn.execute(
                "UPDATE runtime_writer_lease SET lease_token = ? WHERE lease_token IS NULL",
                (f"legacy:{uuid.uuid4().hex}",),
            )

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

    def pending_commands_due(
        self,
        target_utc: datetime,
        *,
        limit: int = 1000,
    ) -> list[RuntimeCommand]:
        if limit < 1:
            return []
        target = self._utc(target_utc)
        with self.repository._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM runtime_commands
                WHERE status = 'pending' AND created_at_utc <= ?
                ORDER BY sequence ASC
                LIMIT ?
                """,
                (target.isoformat(), limit),
            ).fetchall()
        return [self._row_to_command(row) for row in rows]

    def pending_command_count(self) -> int:
        with self.repository._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS count FROM runtime_commands WHERE status = 'pending'"
            ).fetchone()
        return int(row["count"])

    def oldest_pending_command_utc(self) -> datetime | None:
        with self.repository._connect() as conn:
            row = conn.execute(
                """
                SELECT created_at_utc FROM runtime_commands
                WHERE status = 'pending'
                ORDER BY sequence ASC LIMIT 1
                """
            ).fetchone()
        return self._parse_dt(row["created_at_utc"]) if row else None

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
    ) -> WriterLease | None:
        if not holder_id or ttl_seconds <= 0:
            raise ValueError("holder_id and positive ttl_seconds are required")
        now = self._utc(now_utc)
        expires = now + timedelta(seconds=ttl_seconds)
        token = uuid.uuid4().hex
        with self.repository._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT * FROM runtime_writer_lease WHERE lease_name = ?",
                (lease_name,),
            ).fetchone()
            if row is not None and self._parse_dt(row["expires_at_utc"]) > now:
                conn.rollback()
                return None
            generation = (int(row["generation"]) if row is not None else 0) + 1
            conn.execute(
                """
                INSERT INTO runtime_writer_lease(
                    lease_name, holder_id, lease_token, generation,
                    acquired_at_utc, heartbeat_at_utc, expires_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(lease_name) DO UPDATE SET
                    holder_id = excluded.holder_id,
                    lease_token = excluded.lease_token,
                    generation = excluded.generation,
                    acquired_at_utc = excluded.acquired_at_utc,
                    heartbeat_at_utc = excluded.heartbeat_at_utc,
                    expires_at_utc = excluded.expires_at_utc
                """,
                (
                    lease_name,
                    holder_id,
                    token,
                    generation,
                    now.isoformat(),
                    now.isoformat(),
                    expires.isoformat(),
                ),
            )
            conn.commit()
        return WriterLease(
            lease_name=lease_name,
            holder_id=holder_id,
            lease_token=token,
            generation=generation,
            acquired_at_utc=now,
            heartbeat_at_utc=now,
            expires_at_utc=expires,
        )

    def current_lease(
        self,
        lease_name: str = "canonical_world_writer",
    ) -> WriterLease | None:
        with self.repository._connect() as conn:
            row = conn.execute(
                "SELECT * FROM runtime_writer_lease WHERE lease_name = ?", (lease_name,)
            ).fetchone()
        return self._row_to_lease(row) if row is not None else None

    def heartbeat_lease(
        self,
        lease: WriterLease,
        *,
        now_utc: datetime,
        ttl_seconds: float = 30.0,
    ) -> WriterLease:
        now = self._utc(now_utc)
        expires = now + timedelta(seconds=ttl_seconds)
        with self.repository._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE runtime_writer_lease
                SET heartbeat_at_utc = ?, expires_at_utc = ?
                WHERE lease_name = ? AND holder_id = ?
                  AND lease_token = ? AND generation = ?
                  AND expires_at_utc > ?
                """,
                (
                    now.isoformat(),
                    expires.isoformat(),
                    lease.lease_name,
                    lease.holder_id,
                    lease.lease_token,
                    lease.generation,
                    now.isoformat(),
                ),
            )
            conn.commit()
        if cursor.rowcount != 1:
            raise WriterLeaseLost("Canonical writer lease was lost")
        return WriterLease(
            lease_name=lease.lease_name,
            holder_id=lease.holder_id,
            lease_token=lease.lease_token,
            generation=lease.generation,
            acquired_at_utc=lease.acquired_at_utc,
            heartbeat_at_utc=now,
            expires_at_utc=expires,
        )

    def release_lease(self, lease: WriterLease) -> None:
        with self.repository._connect() as conn:
            conn.execute(
                """
                DELETE FROM runtime_writer_lease
                WHERE lease_name = ? AND holder_id = ?
                  AND lease_token = ? AND generation = ?
                """,
                (
                    lease.lease_name,
                    lease.holder_id,
                    lease.lease_token,
                    lease.generation,
                ),
            )
            conn.commit()

    def assert_lease_in_transaction(
        self,
        conn: sqlite3.Connection,
        lease: WriterLease,
        *,
        now_utc: datetime,
    ) -> None:
        now = self._utc(now_utc)
        row = conn.execute(
            """
            SELECT holder_id, lease_token, generation, expires_at_utc
            FROM runtime_writer_lease WHERE lease_name = ?
            """,
            (lease.lease_name,),
        ).fetchone()
        valid = (
            row is not None
            and row["holder_id"] == lease.holder_id
            and row["lease_token"] == lease.lease_token
            and int(row["generation"]) == lease.generation
            and self._parse_dt(row["expires_at_utc"]) > now
        )
        if not valid:
            raise WriterLeaseLost("Canonical writer lease is no longer valid")

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

    def _row_to_lease(self, row: sqlite3.Row) -> WriterLease:
        return WriterLease(
            lease_name=str(row["lease_name"]),
            holder_id=str(row["holder_id"]),
            lease_token=str(row["lease_token"]),
            generation=int(row["generation"]),
            acquired_at_utc=self._parse_dt(row["acquired_at_utc"]),
            heartbeat_at_utc=self._parse_dt(row["heartbeat_at_utc"]),
            expires_at_utc=self._parse_dt(row["expires_at_utc"]),
        )
