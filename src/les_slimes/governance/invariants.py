from __future__ import annotations

from datetime import UTC, datetime

from ..database.base import RelationalRepository
from .models import PowerLevel


TERMINAL_INTERVENTION_STATUSES = frozenset({"executed", "rejected", "cancelled"})
VALID_INTERVENTION_STATUSES = frozenset(
    {"proposed", "authorized", "executed", "rejected", "cancelled", "transgression"}
)


def ensure_governance_invariants(repository: RelationalRepository) -> None:
    """Install non-destructive DB guards and backfill actor governance state.

    The operation is idempotent. Backend-specific indexes/triggers are installed by
    the repository so governance semantics remain identical across SQL engines.
    """
    now = datetime.now(UTC).isoformat()
    with repository._connect() as conn:
        runtime_exists = repository.table_exists(conn, "runtime_actors")
        governance_exists = repository.table_exists(conn, "divine_actor_state")
        if runtime_exists and governance_exists:
            conn.execute(
                """
                INSERT INTO divine_actor_state(actor_id, max_power_level, updated_at_utc)
                SELECT id, ?, ? FROM runtime_actors
                WHERE id NOT IN (SELECT actor_id FROM divine_actor_state)
                """,
                (int(PowerLevel.OBSERVATION), now),
            )

        repository.install_governance_guards(conn)
        conn.commit()
