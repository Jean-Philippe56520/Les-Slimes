from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import pytest

psycopg = pytest.importorskip("psycopg")

from les_slimes.config import WorldConfig
from les_slimes.database.migrate import migrate_sqlite_to_postgres
from les_slimes.database.postgres_repo import PostgreSQLRepository
from les_slimes.database.sqlite_repo import SQLiteRepository
from les_slimes.governance.models import BudgetKind, JournalEntryType, PowerLevel
from les_slimes.governance.service import DivineGovernanceService, GovernanceAdminService
from les_slimes.governance.storage import GovernanceStorage
from les_slimes.runtime import ActorPermission, CanonicalRuntime, CanonicalWorldWorker, RuntimeStorage
from les_slimes.world.engine import World


TEST_DSN = os.getenv("LES_SLIMES_TEST_POSTGRES_URL", "").strip()
pytestmark = pytest.mark.skipif(not TEST_DSN, reason="PostgreSQL integration DSN is not configured")


def _reset_database() -> None:
    with psycopg.connect(TEST_DSN, autocommit=True) as conn:
        conn.execute("DROP SCHEMA IF EXISTS public CASCADE")
        conn.execute("CREATE SCHEMA public")


def _world(seed: int = 7721) -> World:
    world = World(
        WorldConfig(
            seed=seed,
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
    return world


def _repo() -> PostgreSQLRepository:
    _reset_database()
    repo = PostgreSQLRepository(TEST_DSN)
    repo.save_world(_world())
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


def test_sqlite_to_postgres_migration_preserves_world_runtime_and_governance(tmp_path):
    _reset_database()
    source = SQLiteRepository(tmp_path / "source.sqlite")
    source.save_world(_world(seed=8822))
    start = datetime(2026, 9, 17, 13, 0, tzinfo=UTC)
    CanonicalRuntime(source).ensure_initialized(start)
    runtime = RuntimeStorage(source)
    admin = GovernanceAdminService(source)
    admin.set_permissions("order", [ActorPermission.DEPOSIT_FOOD], reason="migration test")
    admin.set_power_level("order", PowerLevel.MIRACLE, reason="migration test")
    admin.adjust_budget("order", BudgetKind.MIRACLE, 2, reason="migration test")
    governance = DivineGovernanceService(source)
    journal_id = governance.journal(
        "herald",
        JournalEntryType.OBSERVATION,
        "Migration test journal entry",
        world_tick=source.load_world().tick,
    )
    runtime.enqueue_command(
        actor_id="order",
        command_type="deposit_food",
        payload={"x": 3.0, "y": 4.0, "count": 1},
        idempotency_key="pending-during-migration",
        created_at_utc=start + timedelta(seconds=5),
    )
    expected_digest = source.load_world().state_digest()

    target = PostgreSQLRepository(TEST_DSN)
    result = migrate_sqlite_to_postgres(source, target)

    assert result.source_digest == expected_digest
    assert result.target_digest == expected_digest
    assert result.pending_commands == 1
    assert result.audit_valid
    assert target.load_world().state_digest() == expected_digest
    target_runtime = RuntimeStorage(target)
    assert target_runtime.pending_command_count() == 1
    assert target_runtime.current_lease() is None
    assert target_runtime.get_actor("herald").kind == "herald"
    target_admin = GovernanceAdminService(target)
    assert target_admin.storage.budget_balance("order", BudgetKind.MIRACLE) == 2
    assert target_admin.storage.validate_audit_chain()

    new_journal_id = DivineGovernanceService(target).journal(
        "herald",
        JournalEntryType.OBSERVATION,
        "Post-migration sequence test",
    )
    assert new_journal_id > journal_id
