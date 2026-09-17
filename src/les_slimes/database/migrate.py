from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from ..governance.invariants import ensure_governance_invariants
from ..governance.storage import GovernanceStorage
from ..runtime.storage import RuntimeStorage
from .postgres_repo import PostgreSQLRepository
from .scope import ensure_canonical_scope
from .sqlite_repo import SQLiteRepository


_COPY_ORDER = (
    "metadata",
    "slimes",
    "foods",
    "mysteries",
    "behavior_rules",
    "memories",
    "relations",
    "signal_associations",
    "heard_signals",
    "events",
    "observer_proposals",
    "checkpoints",
    "runtime_actors",
    "runtime_commands",
    # runtime_writer_lease is deliberately never migrated.
    "divine_actor_state",
    "divine_budget_ledger",
    "divine_sanctions",
    "divine_interventions",
    "divine_journal_entries",
    "divine_proposals",
    "divine_audit_log",
)
_CLEAR_ORDER = tuple(reversed(_COPY_ORDER)) + ("runtime_writer_lease",)


@dataclass(frozen=True, slots=True)
class MigrationResult:
    source_digest: str
    target_digest: str
    copied_rows: dict[str, int]
    pending_commands: int
    audit_valid: bool


def _sqlite_columns(conn: Any, table_name: str) -> list[str]:
    return [str(row["name"]) for row in conn.execute(f"PRAGMA table_info({table_name})")]


def migrate_sqlite_to_postgres(
    source: SQLiteRepository,
    target: PostgreSQLRepository,
) -> MigrationResult:
    """Copy a stopped canonical SQLite database into a fresh PostgreSQL database.

    The source writer must be stopped. A currently valid writer lease causes an
    immediate refusal. The SQLite source is then held under BEGIN IMMEDIATE for the
    duration of the snapshot copy, preventing a new canonical writer from mutating it.
    The target writer lease is intentionally not copied.
    """

    if not source.exists():
        raise FileNotFoundError(f"No canonical SQLite world found at {source.path}")
    if target.exists():
        raise RuntimeError("Target PostgreSQL database already contains a canonical world")

    source_runtime = RuntimeStorage(source)
    lease = source_runtime.current_lease()
    now = datetime.now(UTC)
    if lease is not None and lease.expires_at_utc > now:
        raise RuntimeError(
            f"Source canonical writer lease is still active for {lease.holder_id}; stop the worker first"
        )

    # Bootstrap all target schemas from the source world, then replace every
    # canonical table transactionally from one coherent SQLite snapshot.
    source_world = source.load_world()
    source_digest = source_world.state_digest()
    target.save_world(source_world)
    RuntimeStorage(target)
    GovernanceStorage(target)
    ensure_governance_invariants(target)

    copied: dict[str, int] = {}
    with source._connect() as source_conn:
        source.begin_write(source_conn)
        # Re-check the state after taking the SQLite write lock.
        locked_world = source.load_world()
        locked_digest = locked_world.state_digest()
        if locked_digest != source_digest:
            source_digest = locked_digest

        with target._connect() as target_conn:
            target.begin_write(target_conn)
            for table_name in _CLEAR_ORDER:
                if target.table_exists(target_conn, table_name):
                    target_conn.execute(f"DELETE FROM {table_name}")

            for table_name in _COPY_ORDER:
                if not source.table_exists(source_conn, table_name):
                    copied[table_name] = 0
                    continue
                columns = _sqlite_columns(source_conn, table_name)
                if not columns:
                    copied[table_name] = 0
                    continue
                rows = source_conn.execute(f"SELECT * FROM {table_name}").fetchall()
                copied[table_name] = len(rows)
                if not rows:
                    continue
                column_sql = ", ".join(columns)
                placeholders = ", ".join("?" for _ in columns)
                target_conn.executemany(
                    f"INSERT INTO {table_name}({column_sql}) VALUES ({placeholders})",
                    [tuple(row[column] for column in columns) for row in rows],
                )
            target_conn.commit()
        source_conn.rollback()

    target.sync_sequences()
    ensure_canonical_scope(target)
    ensure_governance_invariants(target)

    target_world = target.load_world()
    target_digest = target_world.state_digest()
    if target_digest != source_digest:
        raise RuntimeError(
            "SQLite -> PostgreSQL migration digest mismatch: "
            f"source={source_digest} target={target_digest}"
        )

    target_runtime = RuntimeStorage(target)
    if target_runtime.current_lease() is not None:
        raise RuntimeError("Target writer lease must be empty after migration")
    source_pending = source_runtime.pending_command_count()
    target_pending = target_runtime.pending_command_count()
    if source_pending != target_pending:
        raise RuntimeError(
            f"Pending command mismatch after migration: {source_pending} != {target_pending}"
        )

    source_governance = GovernanceStorage(source)
    target_governance = GovernanceStorage(target)
    source_audit_valid = source_governance.validate_audit_chain()
    target_audit_valid = target_governance.validate_audit_chain()
    if source_audit_valid != target_audit_valid or not target_audit_valid:
        raise RuntimeError("Governance audit chain validation failed after migration")

    return MigrationResult(
        source_digest=source_digest,
        target_digest=target_digest,
        copied_rows=copied,
        pending_commands=target_pending,
        audit_valid=target_audit_valid,
    )
