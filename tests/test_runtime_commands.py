from datetime import UTC, datetime, timedelta

import pytest

from les_slimes.config import WorldConfig
from les_slimes.database.sqlite_repo import SQLiteRepository
from les_slimes.runtime import (
    CanonicalRuntime,
    CanonicalWorldWorker,
    RuntimeStorage,
    WriterLeaseLost,
)
from les_slimes.world.engine import World


class FakeClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def now(self) -> datetime:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += timedelta(seconds=seconds)


def build_repo(tmp_path, name="world.sqlite"):
    repo = SQLiteRepository(tmp_path / name)
    repo.save_world(
        World(
            WorldConfig(
                seed=1234,
                width=40.0,
                height=30.0,
                initial_slimes=12,
                initial_food=20,
                max_food=60,
                food_spawn_probability=0.0,
                tick_duration_seconds=1.0,
            )
        )
    )
    return repo


def test_idempotency_key_returns_same_command(tmp_path):
    repo = build_repo(tmp_path)
    storage = RuntimeStorage(repo)
    now = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)

    first = storage.enqueue_command(
        actor_id="father",
        command_type="deposit_food",
        payload={"x": 10, "y": 10, "count": 2},
        idempotency_key="same-request",
        created_at_utc=now,
    )
    second = storage.enqueue_command(
        actor_id="father",
        command_type="deposit_food",
        payload={"x": 99, "y": 99, "count": 99},
        idempotency_key="same-request",
        created_at_utc=now,
    )

    assert first.id == second.id
    assert first.sequence == second.sequence
    assert len(storage.pending_commands()) == 1


def test_writer_lease_blocks_concurrent_holder_and_fences_old_owner(tmp_path):
    repo = build_repo(tmp_path)
    storage = RuntimeStorage(repo)
    now = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)

    lease_a = storage.acquire_lease(
        holder_id="worker-a", now_utc=now, ttl_seconds=30
    )
    assert lease_a is not None
    assert (
        storage.acquire_lease(
            holder_id="worker-b", now_utc=now + timedelta(seconds=5), ttl_seconds=30
        )
        is None
    )

    lease_b = storage.acquire_lease(
        holder_id="worker-b", now_utc=now + timedelta(seconds=31), ttl_seconds=30
    )
    assert lease_b is not None
    assert lease_b.generation == lease_a.generation + 1
    assert lease_b.lease_token != lease_a.lease_token

    with pytest.raises(WriterLeaseLost):
        storage.heartbeat_lease(
            lease_a,
            now_utc=now + timedelta(seconds=31),
            ttl_seconds=30,
        )


def test_same_holder_cannot_impersonate_active_lease(tmp_path):
    repo = build_repo(tmp_path)
    storage = RuntimeStorage(repo)
    now = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)
    first = storage.acquire_lease(
        holder_id="same-name", now_utc=now, ttl_seconds=30
    )
    assert first is not None
    assert (
        storage.acquire_lease(
            holder_id="same-name",
            now_utc=now + timedelta(seconds=1),
            ttl_seconds=30,
        )
        is None
    )


def test_stale_writer_cannot_commit_after_takeover(tmp_path):
    repo = build_repo(tmp_path)
    storage = RuntimeStorage(repo)
    start = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)
    original_digest = repo.load_world().state_digest()

    lease_a = storage.acquire_lease(
        holder_id="worker-a", now_utc=start, ttl_seconds=10
    )
    assert lease_a is not None
    stale_world = repo.load_world()
    stale_world.step(5)

    lease_b = storage.acquire_lease(
        holder_id="worker-b",
        now_utc=start + timedelta(seconds=11),
        ttl_seconds=10,
    )
    assert lease_b is not None

    with pytest.raises(WriterLeaseLost):
        repo.save_world(
            stale_world,
            transaction_guard=lambda conn: storage.assert_lease_in_transaction(
                conn,
                lease_a,
                now_utc=start + timedelta(seconds=11),
            ),
        )

    assert repo.load_world().state_digest() == original_digest


def test_worker_applies_command_in_time_order_and_advances_world(tmp_path):
    repo = build_repo(tmp_path)
    start = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)
    clock = FakeClock(start)
    CanonicalRuntime(repo).ensure_initialized(start)
    storage = RuntimeStorage(repo)
    initial_next_food_id = repo.load_world().next_food_id

    storage.enqueue_command(
        actor_id="father",
        command_type="deposit_food",
        payload={"x": 10.0, "y": 12.0, "count": 3},
        idempotency_key="food-1",
        created_at_utc=start + timedelta(seconds=5),
    )

    result = CanonicalWorldWorker(
        repo,
        holder_id="worker-a",
        batch_size=4,
        clock=clock.now,
    ).run_until(start + timedelta(seconds=10))
    world = repo.load_world()

    assert result.commands_applied == 1
    assert result.commands_rejected == 0
    assert world.tick == 10
    assert world.next_food_id >= initial_next_food_id + 3
    assert storage.pending_commands() == []


def test_worker_drains_more_than_one_command_page_before_target(tmp_path):
    repo = build_repo(tmp_path)
    start = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)
    clock = FakeClock(start)
    CanonicalRuntime(repo).ensure_initialized(start)
    storage = RuntimeStorage(repo)

    for index in range(25):
        storage.enqueue_command(
            actor_id="order",
            command_type="deposit_food",
            payload={"x": 1.0, "y": 1.0, "count": 1},
            idempotency_key=f"unauthorized-{index}",
            created_at_utc=start + timedelta(seconds=1),
        )

    result = CanonicalWorldWorker(
        repo,
        holder_id="worker-pages",
        command_page_size=7,
        clock=clock.now,
    ).run_until(start + timedelta(seconds=2))

    assert result.commands_rejected == 25
    assert storage.pending_commands() == []
    assert repo.load_world().tick == 2


def test_persisted_command_event_prevents_replay_after_status_crash(tmp_path):
    repo = build_repo(tmp_path)
    start = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)
    clock = FakeClock(start)
    CanonicalRuntime(repo).ensure_initialized(start)
    storage = RuntimeStorage(repo)
    command = storage.enqueue_command(
        actor_id="father",
        command_type="deposit_food",
        payload={"x": 5.0, "y": 5.0, "count": 1},
        idempotency_key="food-crash",
        created_at_utc=start,
    )

    world = repo.load_world()
    world.player_deposit_food(5.0, 5.0, 1)
    world._emit(
        "command_applied",
        payload={
            "command_id": command.id,
            "command_sequence": command.sequence,
            "actor_id": command.actor_id,
            "command_type": command.command_type,
            "result": {"count": 1},
        },
    )
    repo.save_world(world)
    food_count = len(repo.load_world().foods)

    result = CanonicalWorldWorker(
        repo,
        holder_id="worker-recovery",
        clock=clock.now,
    ).run_until(start)

    assert result.commands_applied == 0
    assert len(repo.load_world().foods) == food_count
    assert storage.pending_commands() == []
