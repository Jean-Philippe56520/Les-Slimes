from datetime import UTC, datetime, timedelta

from les_slimes.config import WorldConfig
from les_slimes.database.sqlite_repo import SQLiteRepository
from les_slimes.runtime import CanonicalRuntime, CanonicalWorldWorker, RuntimeStorage
from les_slimes.world.engine import World


def build_repo(tmp_path):
    repo = SQLiteRepository(tmp_path / "world.sqlite")
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


def test_writer_lease_blocks_concurrent_holder(tmp_path):
    repo = build_repo(tmp_path)
    storage = RuntimeStorage(repo)
    now = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)

    assert storage.acquire_lease(holder_id="worker-a", now_utc=now, ttl_seconds=30)
    assert not storage.acquire_lease(
        holder_id="worker-b", now_utc=now + timedelta(seconds=5), ttl_seconds=30
    )
    assert storage.acquire_lease(
        holder_id="worker-b", now_utc=now + timedelta(seconds=31), ttl_seconds=30
    )


def test_worker_applies_command_in_time_order_and_advances_world(tmp_path):
    repo = build_repo(tmp_path)
    start = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)
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

    result = CanonicalWorldWorker(repo, holder_id="worker-a", batch_size=4).run_until(
        start + timedelta(seconds=10)
    )
    world = repo.load_world()

    assert result.commands_applied == 1
    assert result.commands_rejected == 0
    assert world.tick == 10
    assert world.next_food_id >= initial_next_food_id + 3
    assert storage.pending_commands() == []


def test_persisted_command_event_prevents_replay_after_status_crash(tmp_path):
    repo = build_repo(tmp_path)
    start = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)
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

    result = CanonicalWorldWorker(repo, holder_id="worker-recovery").run_until(start)

    assert result.commands_applied == 0
    assert len(repo.load_world().foods) == food_count
    assert storage.pending_commands() == []
