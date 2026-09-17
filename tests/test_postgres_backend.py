from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import pytest

psycopg = pytest.importorskip("psycopg")

from les_slimes.config import WorldConfig
from les_slimes.database.postgres_repo import PostgreSQLRepository
from les_slimes.governance.models import BudgetKind, PowerLevel
from les_slimes.governance.service import GovernanceAdminService
from les_slimes.governance.storage import GovernanceStorage
from les_slimes.runtime import ActorPermission, CanonicalRuntime, CanonicalWorldWorker, RuntimeStorage
from les_slimes.world.engine import World


TEST_DSN = os.getenv("LES_SLIMES_TEST_POSTGRES_URL", "").strip()
pytestmark = pytest.mark.skipif(not TEST_DSN, reason="PostgreSQL integration DSN is not configured")


def _reset_database() -> None:
    with psycopg.connect(TEST_DSN, autocommit=True) as conn:
        conn.execute("DROP SCHEMA IF EXISTS public CASCADE")
        conn.execute("CREATE SCHEMA public")


def _repo() -> PostgreSQLRepository:
    _reset_database()
    repo = PostgreSQLRepository(TEST_DSN)
    world = World(
        WorldConfig(
            seed=7721,
            width=35.0,
            height=24.0,
            initial_slimes=8,
            initial_food=12,
            max_food=50,
            food_spawn_probability=0.0,
            tick_duration_seconds=1.0,
        )
    )
    world.step(12)
    repo.save_world(world)
    return repo


def test_postgres_save_reload_preserves_exact_world_digest():
    repo = _repo()
    before = repo.load_world()
    digest = before.state_digest()

    repo.save_world(before)
    restored = repo.load_world()

    assert repo.backend_name == "postgresql"
    assert restored.tick == before.tick
    assert restored.state_digest() == digest
    assert restored.rng_state_bytes() == before.rng_state_bytes()


def test_postgres_runtime_lease_is_fenced_and_takeover_increments_generation():
    repo = _repo()
    storage_a = RuntimeStorage(repo)
    storage_b = RuntimeStorage(repo)
    now = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)

    first = storage_a.acquire_lease(holder_id="pg-a", now_utc=now, ttl_seconds=10)
    assert first is not None
    assert storage_b.acquire_lease(holder_id="pg-b", now_utc=now, ttl_seconds=10) is None

    second = storage_b.acquire_lease(
        holder_id="pg-b",
        now_utc=now + timedelta(seconds=11),
        ttl_seconds=10,
    )
    assert second is not None
    assert second.generation == first.generation + 1

    with repo._connect() as conn:
        repo.begin_write(conn)
        with pytest.raises(Exception):
            storage_a.assert_lease_in_transaction(
                conn,
                first,
                now_utc=now + timedelta(seconds=11),
            )
        conn.rollback()


def test_postgres_worker_keeps_world_governance_budget_and_audit_consistent():
    repo = _repo()
    start = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)
    CanonicalRuntime(repo).ensure_initialized(start)
    admin = GovernanceAdminService(repo)
    admin.set_permissions("order", [ActorPermission.DEPOSIT_FOOD], reason="pg integration")
    admin.set_power_level("order", PowerLevel.MIRACLE, reason="pg integration")
    admin.adjust_budget("order", BudgetKind.MIRACLE, 1, reason="pg integration")
    storage = RuntimeStorage(repo)
    before_next_food_id = repo.load_world().next_food_id

    command = storage.enqueue_command(
        actor_id="order",
        command_type="deposit_food",
        payload={"x": 4.0, "y": 5.0, "count": 2},
        idempotency_key="pg-order-miracle",
        created_at_utc=start,
    )
    result = CanonicalWorldWorker(
        repo,
        holder_id="pg-worker",
        clock=lambda: start,
    ).run_until(start)

    assert result.commands_applied == 1
    assert result.commands_rejected == 0
    assert repo.load_world().next_food_id == before_next_food_id + 2
    assert admin.storage.budget_balance("order", BudgetKind.MIRACLE) == 0
    assert admin.storage.validate_audit_chain()
    recent = storage.recent_commands(limit=1)[0]
    assert recent["id"] == command.id
    assert recent["status"] == "applied"


def test_postgres_terminal_intervention_guard_is_enforced_by_database():
    repo = _repo()
    start = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)
    CanonicalRuntime(repo).ensure_initialized(start)
    RuntimeStorage(repo)
    governance = GovernanceStorage(repo)
    from les_slimes.governance.invariants import ensure_governance_invariants

    ensure_governance_invariants(repo)
    intervention = governance.create_intervention(
        actor_id="chaos",
        action_kind="deposit_food",
        power_level=PowerLevel.MIRACLE,
        permission=ActorPermission.DEPOSIT_FOOD.value,
        command_id=None,
        source_proposal_id=None,
        status="proposed",
        budget_kind=BudgetKind.MIRACLE,
        budget_cost=1,
        reason="terminal guard integration test",
        now_utc=start,
    )
    governance.reject_intervention(
        intervention.id,
        reason="integration rejection",
        now_utc=start,
    )

    with pytest.raises(Exception):
        with repo._connect() as conn:
            repo.begin_write(conn)
            conn.execute(
                "UPDATE divine_interventions SET status = 'executed' WHERE id = ?",
                (intervention.id,),
            )
            conn.commit()

    assert governance.get_intervention(intervention.id).status == "rejected"
