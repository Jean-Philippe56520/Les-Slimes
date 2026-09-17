from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

from .sqlite_repo import SCHEMA, SQLiteRepository

try:
    import psycopg
    from psycopg.rows import dict_row
except ModuleNotFoundError:  # pragma: no cover - exercised only without postgres extra
    psycopg = None
    dict_row = None


_GLOBAL_WRITE_LOCK = 5495873891907557709
_LASTROWID_TABLES = frozenset(
    {
        "observer_proposals",
        "divine_sanctions",
        "divine_journal_entries",
        "divine_proposals",
    }
)


def _postgres_schema(script: str) -> str:
    """Translate the deliberately small SQLite-compatible DDL subset we use."""
    script = re.sub(r"(?mi)^\s*PRAGMA\s+[^;]+;\s*", "", script)
    script = script.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "BIGSERIAL PRIMARY KEY")
    script = re.sub(r"\bINTEGER\b", "BIGINT", script)
    script = re.sub(r"\bREAL\b", "DOUBLE PRECISION", script)
    script = re.sub(r"\bBLOB\b", "BYTEA", script)
    return script


def _postgres_sql(sql: str) -> str:
    value = sql.strip()
    if value.upper() == "BEGIN IMMEDIATE":
        return "__LES_SLIMES_BEGIN_WRITE__"
    insert_ignore = re.match(r"(?is)^\s*INSERT\s+OR\s+IGNORE\s+INTO\s+", sql)
    if insert_ignore:
        sql = re.sub(r"(?is)^\s*INSERT\s+OR\s+IGNORE\s+INTO\s+", "INSERT INTO ", sql, count=1)
        sql = sql.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"
    return sql.replace("?", "%s")


class _PostgresCursor:
    def __init__(self, cursor: Any, *, lastrowid: int | None = None) -> None:
        self._cursor = cursor
        self.lastrowid = lastrowid

    @property
    def rowcount(self) -> int:
        return int(self._cursor.rowcount)

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def __iter__(self):
        return iter(self._cursor)


class _PostgresConnection:
    """Small compatibility facade for the DB-API subset used by Les Slimes."""

    def __init__(self, raw: Any) -> None:
        self.raw = raw

    def __enter__(self) -> "_PostgresConnection":
        self.raw.__enter__()
        return self

    def __exit__(self, exc_type, exc, tb):
        return self.raw.__exit__(exc_type, exc, tb)

    def execute(self, sql: str, params: Iterable[Any] | None = None) -> _PostgresCursor:
        translated = _postgres_sql(sql)
        if translated == "__LES_SLIMES_BEGIN_WRITE__":
            cursor = self.raw.execute(
                "SELECT pg_advisory_xact_lock(%s)",
                (_GLOBAL_WRITE_LOCK,),
            )
            return _PostgresCursor(cursor)

        params_tuple = tuple(params) if params is not None else None
        table_match = re.match(r"(?is)^\s*INSERT\s+INTO\s+([a-zA-Z_][a-zA-Z0-9_]*)", translated)
        table_name = table_match.group(1).lower() if table_match else None
        wants_lastrowid = (
            table_name in _LASTROWID_TABLES
            and " RETURNING " not in translated.upper()
            and " ON CONFLICT " not in translated.upper()
        )
        if wants_lastrowid:
            translated = translated.rstrip().rstrip(";") + " RETURNING id"

        cursor = self.raw.execute(
            translated,
            params_tuple,
            prepare=False if params_tuple is None and ";" in translated else None,
        )
        lastrowid = None
        if wants_lastrowid:
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError(f"INSERT into {table_name} did not return an id")
            lastrowid = int(row["id"])
        return _PostgresCursor(cursor, lastrowid=lastrowid)

    def executemany(self, sql: str, params_seq: Iterable[Iterable[Any]]) -> _PostgresCursor:
        cursor = self.raw.cursor()
        cursor.executemany(_postgres_sql(sql), [tuple(params) for params in params_seq])
        return _PostgresCursor(cursor)

    def executescript(self, script: str) -> None:
        translated = _postgres_schema(script)
        if translated.strip():
            self.raw.execute(translated, prepare=False)

    def commit(self) -> None:
        self.raw.commit()

    def rollback(self) -> None:
        self.raw.rollback()


class PostgreSQLRepository(SQLiteRepository):
    """PostgreSQL implementation preserving the canonical repository semantics.

    World serialization is deliberately shared with SQLite so state digests and
    save/load behavior stay identical. SQL compatibility is isolated in the connection
    facade above; PostgreSQL-specific concurrency guards live in repository primitives.
    """

    backend_name = "postgresql"

    def __init__(self, dsn: str) -> None:
        if psycopg is None:
            raise RuntimeError(
                "PostgreSQL support requires the 'postgres' extra: pip install -e '.[postgres]'"
            )
        if not dsn.startswith(("postgresql://", "postgres://")):
            raise ValueError("PostgreSQL DSN must start with postgresql:// or postgres://")
        self.dsn = dsn
        # Kept only for inherited diagnostic text. PostgreSQL never uses this as storage.
        self.path = Path("postgresql-canonical")

    def _connect(self) -> _PostgresConnection:
        raw = psycopg.connect(
            self.dsn,
            row_factory=dict_row,
            prepare_threshold=None,
        )
        return _PostgresConnection(raw)

    def storage_exists(self) -> bool:
        with self._connect() as conn:
            return self.table_exists(conn, "metadata")

    @staticmethod
    def table_exists(conn: _PostgresConnection, table_name: str) -> bool:
        row = conn.execute(
            """
            SELECT 1 AS present
            FROM information_schema.tables
            WHERE table_schema = current_schema() AND table_name = ?
            """,
            (table_name,),
        ).fetchone()
        return row is not None

    @staticmethod
    def column_names(conn: _PostgresConnection, table_name: str) -> set[str]:
        rows = conn.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = current_schema() AND table_name = ?
            """,
            (table_name,),
        ).fetchall()
        return {str(row["column_name"]) for row in rows}

    @staticmethod
    def execute_script(conn: _PostgresConnection, script: str) -> None:
        conn.executescript(script)

    @staticmethod
    def begin_write(conn: _PostgresConnection) -> None:
        # Psycopg begins the transaction automatically on this first statement.
        # The transaction-scoped advisory lock reproduces SQLite BEGIN IMMEDIATE's
        # serialization for canonical mutations and audit-chain appends.
        conn.raw.execute(
            "SELECT pg_advisory_xact_lock(%s)",
            (_GLOBAL_WRITE_LOCK,),
        )

    @staticmethod
    def lock_writer_lease(conn: _PostgresConnection, lease_name: str) -> None:
        # begin_write() already owns the global canonical write lock. This extra
        # transaction lock makes the lease intent explicit and stable across hosts.
        conn.raw.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
            (lease_name,),
        )

    def install_governance_guards(self, conn: _PostgresConnection) -> None:
        if self.table_exists(conn, "divine_budget_ledger"):
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_divine_budget_single_intervention_debit
                ON divine_budget_ledger(intervention_id)
                WHERE intervention_id IS NOT NULL AND delta < 0
                """
            )
        if self.table_exists(conn, "divine_interventions"):
            conn.execute(
                """
                CREATE OR REPLACE FUNCTION les_slimes_guard_intervention_status()
                RETURNS trigger AS $$
                BEGIN
                    IF NEW.status NOT IN (
                        'proposed', 'authorized', 'executed',
                        'rejected', 'cancelled', 'transgression'
                    ) THEN
                        RAISE EXCEPTION 'invalid divine intervention status';
                    END IF;
                    IF TG_OP = 'UPDATE'
                       AND OLD.status IN ('executed', 'rejected', 'cancelled')
                       AND NEW.status <> OLD.status THEN
                        RAISE EXCEPTION 'terminal divine intervention status cannot change';
                    END IF;
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql;

                DROP TRIGGER IF EXISTS trg_divine_intervention_status_guard
                ON divine_interventions;

                CREATE TRIGGER trg_divine_intervention_status_guard
                BEFORE INSERT OR UPDATE OF status ON divine_interventions
                FOR EACH ROW EXECUTE FUNCTION les_slimes_guard_intervention_status();
                """
            )

    def initialize_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)
            columns = self.column_names(conn, "slimes")
            if "last_signal_emit_tick" not in columns:
                conn.execute(
                    "ALTER TABLE slimes ADD COLUMN last_signal_emit_tick "
                    "BIGINT NOT NULL DEFAULT -1000000"
                )
            conn.commit()

    def exists(self) -> bool:
        if not self.storage_exists():
            return False
        with self._connect() as conn:
            row = conn.execute("SELECT 1 FROM metadata WHERE key='tick'").fetchone()
        return row is not None

    @staticmethod
    def _set_meta(conn: _PostgresConnection, key: str, value: bytes) -> None:
        conn.execute(
            """
            INSERT INTO metadata(key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, bytes(value)),
        )
