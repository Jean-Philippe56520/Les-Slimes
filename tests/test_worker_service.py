from datetime import UTC, datetime, timedelta

from les_slimes.config import WorldConfig
from les_slimes.database.sqlite_repo import SQLiteRepository
from les_slimes.runtime import (
    CanonicalRuntime,
    CanonicalWorkerService,
    CanonicalWorldWorker,
    RuntimeStorage,
    WorkerServiceConfig,
)
from les_slimes.world.engine import World


class FakeServiceClock:
    def __init__(self, value: datetime) -> None:
        self.value = value
        self.sleeps: list[float] = []

    def now(self) -> datetime:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.value += timedelta(seconds=seconds)

    def advance(self, seconds: float) -> None:
        self.value += timedelta(seconds=seconds)


class TickingClock:
    def __init__(self, value: datetime, step_seconds: float = 1.0) -> None:
        self.value = value
        self.step = timedelta(seconds=step_seconds)

    def now(self) -> datetime:
        current = self.value
        self.value += self.step
        return current


def build_repo(tmp_path, name: str) -> SQLiteRepository:
    repo = SQLiteRepository(tmp_path / name)
    repo.save_world(
        World(
            WorldConfig(
                seed=9191,
                width=30.0,
                height=20.0,
                initial_slimes=8,
                initial_food=12,
                max_food=30,
                food_spawn_probability=0.0,
                tick_duration_seconds=1.0,
            )
        )
    )
    return repo


def test_service_keeps_same_lease_across_heartbeat_and_reports_health(tmp_path):
    start = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)
    repo = build_repo(tmp_path, "service.sqlite")
    CanonicalRuntime(repo).ensure_initialized(start)
    clock = FakeServiceClock(start)
    service = CanonicalWorkerService(
        repo,
        holder_id="service-a",
        clock=clock,
        config=WorkerServiceConfig(
            poll_interval_seconds=25,
            heartbeat_interval_seconds=10,
            lease_ttl_seconds=30,
            batch_size=3,
        ),
    )

    first = service.start()
    clock.advance(20)
    refreshed = service.heartbeat()

    assert refreshed.lease_token == first.lease_token
    assert refreshed.generation == first.generation
    assert refreshed.expires_at_utc == start + timedelta(seconds=50)

    health = service.health()
    assert health.holder_id == "service-a"
    assert health.lease_valid
    assert health.lease_generation == first.generation
    assert health.ticks_due == 20
    assert health.lag_seconds == 20

    service.close()
    assert service.worker.storage.current_lease() is None


def test_service_health_reports_backlog_without_advancing_world(tmp_path):
    start = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)
    repo = build_repo(tmp_path, "health.sqlite")
    CanonicalRuntime(repo).ensure_initialized(start)
    storage = RuntimeStorage(repo)
    storage.enqueue_command(
        actor_id="father",
        command_type="deposit_food",
        payload={"x": 2.0, "y": 3.0, "count": 1},
        idempotency_key="pending-health",
        created_at_utc=start + timedelta(seconds=2),
    )
    clock = FakeServiceClock(start + timedelta(seconds=5))
    service = CanonicalWorkerService(repo, holder_id="health-reader", clock=clock)

    health = service.health()

    assert health.world_tick == 0
    assert health.ticks_due == 5
    assert health.pending_commands == 1
    assert health.oldest_pending_command_utc == start + timedelta(seconds=2)


def test_service_idle_period_is_split_by_heartbeats_and_releases_cleanly(tmp_path):
    start = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)
    repo = build_repo(tmp_path, "idle.sqlite")
    CanonicalRuntime(repo).ensure_initialized(start)
    clock = FakeServiceClock(start)
    service = CanonicalWorkerService(
        repo,
        holder_id="idle-worker",
        clock=clock,
        config=WorkerServiceConfig(
            poll_interval_seconds=25,
            heartbeat_interval_seconds=10,
            lease_ttl_seconds=30,
            batch_size=5,
        ),
    )

    service.serve(stop_requested=lambda: len(clock.sleeps) >= 3)

    assert clock.sleeps == [10, 10, 5]
    assert service.worker.storage.current_lease() is None


def test_catch_up_heartbeats_between_batches(tmp_path):
    start = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)
    repo = build_repo(tmp_path, "heartbeat-batches.sqlite")
    CanonicalRuntime(repo).ensure_initialized(start)
    clock = TickingClock(start, step_seconds=1)
    worker = CanonicalWorldWorker(
        repo,
        holder_id="batch-worker",
        batch_size=1,
        lease_ttl_seconds=4,
        clock=clock.now,
    )

    result = worker.run_until(start + timedelta(seconds=5))

    assert result.final_advance.current_tick == 5
    assert repo.load_world().tick == 5


def test_crash_takeover_matches_continuous_digest_with_command(tmp_path):
    start = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)
    continuous = build_repo(tmp_path, "continuous.sqlite")
    restarted = build_repo(tmp_path, "restarted.sqlite")
    CanonicalRuntime(continuous).ensure_initialized(start)
    CanonicalRuntime(restarted).ensure_initialized(start)

    for repo in (continuous, restarted):
        RuntimeStorage(repo).enqueue_command(
            actor_id="father",
            command_type="deposit_food",
            payload={"x": 4.0, "y": 5.0, "count": 2},
            idempotency_key="same-logical-command",
            created_at_utc=start + timedelta(seconds=5),
        )

    continuous_clock = FakeServiceClock(start)
    CanonicalWorldWorker(
        continuous,
        holder_id="continuous-worker",
        batch_size=3,
        lease_ttl_seconds=30,
        clock=continuous_clock.now,
    ).run_until(start + timedelta(seconds=20))

    crashed_clock = FakeServiceClock(start)
    worker_a = CanonicalWorldWorker(
        restarted,
        holder_id="worker-a",
        batch_size=3,
        lease_ttl_seconds=10,
        clock=crashed_clock.now,
    )
    lease_a = worker_a.acquire_lease()
    result_a, lease_a = worker_a.run_until_with_lease(
        start + timedelta(seconds=8),
        lease_a,
    )
    assert result_a.final_advance.current_tick == 8

    takeover_clock = FakeServiceClock(start + timedelta(seconds=11))
    worker_b = CanonicalWorldWorker(
        restarted,
        holder_id="worker-b",
        batch_size=4,
        lease_ttl_seconds=10,
        clock=takeover_clock.now,
    )
    result_b = worker_b.run_until(start + timedelta(seconds=20))

    assert result_b.final_advance.current_tick == 20
    assert restarted.load_world().state_digest() == continuous.load_world().state_digest()



class RecordingPublisher:
    def __init__(self):
        self.calls = []

    def maybe_publish(self, *, observed_at_utc):
        self.calls.append(observed_at_utc)
        return ("latest",)


def test_worker_cycle_publishes_observation_after_world_advance(tmp_path):
    start = datetime(2026, 9, 18, 8, 0, tzinfo=UTC)
    repo = build_repo(tmp_path, "observed.sqlite")
    CanonicalRuntime(repo).ensure_initialized(start)
    clock = FakeServiceClock(start + timedelta(seconds=5))
    publisher = RecordingPublisher()
    service = CanonicalWorkerService(
        repo,
        holder_id="observed-worker",
        clock=clock,
        observation_publisher=publisher,
    )

    result = service.cycle()

    assert result.final_advance.current_tick == 5
    assert publisher.calls == [start + timedelta(seconds=5)]
    service.close()



class FailingPublisher:
    def maybe_publish(self, *, observed_at_utc):
        raise RuntimeError("archive unavailable")


def test_observation_export_failure_never_stops_canonical_world(tmp_path):
    start = datetime(2026, 9, 18, 9, 0, tzinfo=UTC)
    repo = build_repo(tmp_path, "export-failure.sqlite")
    CanonicalRuntime(repo).ensure_initialized(start)
    clock = FakeServiceClock(start + timedelta(seconds=3))
    service = CanonicalWorkerService(
        repo,
        holder_id="resilient-worker",
        clock=clock,
        observation_publisher=FailingPublisher(),
    )

    result = service.cycle()

    assert result.final_advance.current_tick == 3
    assert repo.load_world().tick == 3
    assert service.last_observation_error == "RuntimeError: archive unavailable"
    service.close()
