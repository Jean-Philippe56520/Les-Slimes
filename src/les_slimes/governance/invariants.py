from __future__ import annotations

from datetime import UTC, datetime

from ..database.sqlite_repo import SQLiteRepository
from .models import PowerLevel


TERMINAL_INTERVENTION_STATUSES = frozenset({"executed", "rejected", "cancelled"})
VALID_INTERVENTION_STATUSES = frozenset(
    {"proposed", "authorized", "executed", "rejected", "cancelled", "transgression"}
)


def ensure_governance_invariants(repository: SQLiteRepository) -> None:
    """Install non-destructive DB guards and backfill actor governance state.

    The function is idempotent and safe to call from every trusted governance/runtime
    entry point. It deliberately uses indexes/triggers rather than rebuilding tables so
    existing SQLite worlds remain readable.
    """
    now = datetime.now(UTC).isoformat()
    with repository._connect() as conn:
        runtime_exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='runtime_actors'"
        ).fetchone()
        governance_exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='divine_actor_state'"
        ).fetchone()
        if runtime_exists is not None and governance_exists is not None:
            conn.execute(
                """
                INSERT INTO divine_actor_state(actor_id, max_power_level, updated_at_utc)
                SELECT id, ?, ? FROM runtime_actors
                WHERE id NOT IN (SELECT actor_id FROM divine_actor_state)
                """,
                (int(PowerLevel.OBSERVATION), now),
            )

        ledger_exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='divine_budget_ledger'"
        ).fetchone()
        if ledger_exists is not None:
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_divine_budget_single_intervention_debit
                ON divine_budget_ledger(intervention_id)
                WHERE intervention_id IS NOT NULL AND delta < 0
                """
            )

        interventions_exist = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='divine_interventions'"
        ).fetchone()
        if interventions_exist is not None:
            conn.executescript(
                """
                CREATE TRIGGER IF NOT EXISTS trg_divine_intervention_valid_status_insert
                BEFORE INSERT ON divine_interventions
                WHEN NEW.status NOT IN (
                    'proposed', 'authorized', 'executed',
                    'rejected', 'cancelled', 'transgression'
                )
                BEGIN
                    SELECT RAISE(ABORT, 'invalid divine intervention status');
                END;

                CREATE TRIGGER IF NOT EXISTS trg_divine_intervention_valid_status_update
                BEFORE UPDATE OF status ON divine_interventions
                WHEN NEW.status NOT IN (
                    'proposed', 'authorized', 'executed',
                    'rejected', 'cancelled', 'transgression'
                )
                BEGIN
                    SELECT RAISE(ABORT, 'invalid divine intervention status');
                END;

                CREATE TRIGGER IF NOT EXISTS trg_divine_intervention_terminal_status
                BEFORE UPDATE OF status ON divine_interventions
                WHEN OLD.status IN ('executed', 'rejected', 'cancelled')
                     AND NEW.status <> OLD.status
                BEGIN
                    SELECT RAISE(ABORT, 'terminal divine intervention status cannot change');
                END;
                """
            )
        conn.commit()
