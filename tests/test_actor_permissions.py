from datetime import UTC, datetime

import pytest

from les_slimes.config import WorldConfig
from les_slimes.database.sqlite_repo import SQLiteRepository
from les_slimes.governance.models import BudgetKind, PowerLevel
from les_slimes.governance.service import GovernanceAdminService
from les_slimes.runtime import ActorPermission, CanonicalRuntime, CanonicalWorldWorker, RuntimeStorage
from les_slimes.world.engine import World


def build_repo(tmp_path):
    repo = SQLiteRepository(tmp_path / "world.sqlite")
    repo.save_world(
        World(
            WorldConfig(
                seed=222,
                width=30.0,
                height=20.0,
                initial_slimes=5,
                initial_food=5,
                max_food=30,
                food_spawn_probability=0.0,
                tick_duration_seconds=1.0,
            )
        )
    )
    return repo


def test_default_actor_permissions_are_conservative(tmp_path):
    storage = RuntimeStorage(build_repo(tmp_path))

    father = storage.get_actor("father")
    order = storage.get_actor("order")
    chaos = storage.get_actor("chaos")
    observer = storage.get_actor("observer")

    assert father.can(ActorPermission.DEPOSIT_FOOD)
    assert father.can(ActorPermission.EMIT_SIGNAL)
    assert not order.can(ActorPermission.DEPOSIT_FOOD)
    assert not chaos.can(ActorPermission.DEPOSIT_FOOD)
    assert not observer.can(ActorPermission.DEPOSIT_FOOD)


def test_unauthorized_actor_command_is_rejected_without_mutation(tmp_path):
    repo = build_repo(tmp_path)
    start = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)
    CanonicalRuntime(repo).ensure_initialized(start)
    storage = RuntimeStorage(repo)
    initial_next_food_id = repo.load_world().next_food_id

    storage.enqueue_command(
        actor_id="chaos",
        command_type="deposit_food",
        payload={"x": 4.0, "y": 5.0, "count": 2},
        idempotency_key="chaos-no-budget",
        created_at_utc=start,
    )

    result = CanonicalWorldWorker(repo, holder_id="worker-auth", clock=lambda: start).run_until(start)

    assert result.commands_applied == 0
    assert result.commands_rejected == 1
    assert repo.load_world().next_food_id == initial_next_food_id
    assert storage.pending_commands() == []


def test_permission_alone_does_not_enable_actor_command(tmp_path):
    repo = build_repo(tmp_path)
    start = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)
    CanonicalRuntime(repo).ensure_initialized(start)
    admin = GovernanceAdminService(repo)
    admin.set_permissions(
        "order",
        [ActorPermission.DEPOSIT_FOOD],
        reason="permission-only test",
        now_utc=start,
    )
    storage = RuntimeStorage(repo)
    initial_next_food_id = repo.load_world().next_food_id

    storage.enqueue_command(
        actor_id="order",
        command_type="deposit_food",
        payload={"x": 4.0, "y": 5.0, "count": 2},
        idempotency_key="order-permission-only",
        created_at_utc=start,
    )

    result = CanonicalWorldWorker(repo, holder_id="worker-auth", clock=lambda: start).run_until(start)

    assert result.commands_applied == 0
    assert result.commands_rejected == 1
    assert repo.load_world().next_food_id == initial_next_food_id


def test_permission_power_and_budget_enable_actor_command(tmp_path):
    repo = build_repo(tmp_path)
    start = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)
    CanonicalRuntime(repo).ensure_initialized(start)
    admin = GovernanceAdminService(repo)
    admin.set_permissions("order", [ActorPermission.DEPOSIT_FOOD], reason="test", now_utc=start)
    admin.set_power_level("order", PowerLevel.MIRACLE, reason="test", now_utc=start)
    admin.adjust_budget("order", BudgetKind.MIRACLE, 1, reason="test", now_utc=start)
    storage = RuntimeStorage(repo)
    initial_next_food_id = repo.load_world().next_food_id

    storage.enqueue_command(
        actor_id="order",
        command_type="deposit_food",
        payload={"x": 4.0, "y": 5.0, "count": 2},
        idempotency_key="order-miracle",
        created_at_utc=start,
    )

    result = CanonicalWorldWorker(repo, holder_id="worker-auth", clock=lambda: start).run_until(start)

    assert result.commands_applied == 1
    assert result.commands_rejected == 0
    assert repo.load_world().next_food_id == initial_next_food_id + 2
    assert admin.storage.budget_balance("order", BudgetKind.MIRACLE) == 0


def test_inactive_actor_is_rejected_even_with_full_governance(tmp_path):
    repo = build_repo(tmp_path)
    start = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)
    CanonicalRuntime(repo).ensure_initialized(start)
    admin = GovernanceAdminService(repo)
    admin.set_permissions("order", [ActorPermission.DEPOSIT_FOOD], reason="test", now_utc=start)
    admin.set_power_level("order", PowerLevel.MIRACLE, reason="test", now_utc=start)
    admin.adjust_budget("order", BudgetKind.MIRACLE, 1, reason="test", now_utc=start)
    admin.set_active("order", False, reason="test", now_utc=start)
    storage = RuntimeStorage(repo)

    storage.enqueue_command(
        actor_id="order",
        command_type="deposit_food",
        payload={"x": 4.0, "y": 5.0, "count": 1},
        idempotency_key="suspended-order",
        created_at_utc=start,
    )

    result = CanonicalWorldWorker(repo, holder_id="worker-auth", clock=lambda: start).run_until(start)
    assert result.commands_applied == 0
    assert result.commands_rejected == 1
    assert admin.storage.budget_balance("order", BudgetKind.MIRACLE) == 1


def test_unknown_actor_cannot_enqueue_command(tmp_path):
    storage = RuntimeStorage(build_repo(tmp_path))
    with pytest.raises(KeyError):
        storage.enqueue_command(
            actor_id="unknown-god",
            command_type="deposit_food",
            payload={"x": 1.0, "y": 1.0},
            idempotency_key="unknown",
            created_at_utc=datetime(2026, 9, 17, 12, 0, tzinfo=UTC),
        )


def test_legacy_mode_metadata_is_ignored_and_removed_on_save(tmp_path):
    repo = build_repo(tmp_path)
    with repo._connect() as conn:
        repo._set_meta(conn, "mode", b"experiment")
        conn.commit()

    restored = repo.load_world()
    assert not hasattr(restored, "mode")
    before = restored.state_digest()

    repo.save_world(restored)
    reloaded = repo.load_world()
    assert reloaded.state_digest() == before
    with repo._connect() as conn:
        assert conn.execute("SELECT 1 FROM metadata WHERE key='mode'").fetchone() is None
