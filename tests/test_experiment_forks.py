from datetime import UTC, datetime

import pytest

from les_slimes.config import WorldConfig
from les_slimes.database.scope import (
    PersistenceScope,
    PersistenceScopeError,
    get_persistence_scope,
)
from les_slimes.database.sqlite_repo import SQLiteRepository
from les_slimes.experiments import (
    create_experiment_fork,
    read_experiment_manifest,
    run_experiment_fork,
)
from les_slimes.runtime import CanonicalRuntime, CanonicalWorldWorker, RuntimeStorage
from les_slimes.world.engine import World


def build_canonical_repo(tmp_path):
    repo = SQLiteRepository(tmp_path / "world.sqlite")
    world = World(
        WorldConfig(
            seed=991,
            width=30.0,
            height=20.0,
            initial_slimes=8,
            initial_food=12,
            max_food=40,
            food_spawn_probability=0.0,
            tick_duration_seconds=1.0,
        )
    )
    world.step(25)
    repo.save_world(world)
    RuntimeStorage(repo)
    CanonicalRuntime(repo).ensure_initialized(datetime(2026, 9, 17, 12, 0, tzinfo=UTC))
    return repo


def test_exact_fork_preserves_source_digest_and_is_noncanonical(tmp_path):
    source = build_canonical_repo(tmp_path)
    before = source.load_world().state_digest()

    fork, manifest = create_experiment_fork(
        source,
        tmp_path / "exp.sqlite",
        experiment_id="EXP-001",
        condition="control",
        source_git_commit="6578e4f",
    )

    assert manifest.source_digest == before
    assert manifest.initial_digest == before
    assert fork.load_world().state_digest() == before
    assert source.load_world().state_digest() == before
    assert get_persistence_scope(fork) == PersistenceScope.NON_CANONICAL_EXPERIMENT


def test_fork_does_not_copy_runtime_tables(tmp_path):
    source = build_canonical_repo(tmp_path)
    storage = RuntimeStorage(source)
    storage.enqueue_command(
        actor_id="father",
        command_type="deposit_food",
        payload={"x": 1.0, "y": 2.0, "count": 1},
        idempotency_key="pending-source-command",
        created_at_utc=datetime(2026, 9, 17, 12, 0, tzinfo=UTC),
    )
    storage.acquire_lease(
        holder_id="worker-a",
        now_utc=datetime(2026, 9, 17, 12, 0, tzinfo=UTC),
        ttl_seconds=30,
    )

    fork, _ = create_experiment_fork(
        source,
        tmp_path / "isolated.sqlite",
        experiment_id="EXP-002",
        condition="control",
        source_git_commit="6578e4f",
    )

    with fork._connect() as conn:
        tables = {
            row["name"]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    assert "runtime_commands" not in tables
    assert "runtime_writer_lease" not in tables
    assert "runtime_actors" not in tables


def test_canonical_runtime_rejects_experiment_database(tmp_path):
    source = build_canonical_repo(tmp_path)
    fork, _ = create_experiment_fork(
        source,
        tmp_path / "exp.sqlite",
        experiment_id="EXP-003",
        condition="control",
        source_git_commit="6578e4f",
    )

    with pytest.raises(PersistenceScopeError):
        CanonicalRuntime(fork)
    with pytest.raises(PersistenceScopeError):
        CanonicalWorldWorker(fork, holder_id="forbidden")
    with pytest.raises(PersistenceScopeError):
        RuntimeStorage(fork)


def test_experiment_runner_rejects_canonical_database(tmp_path):
    source = build_canonical_repo(tmp_path)
    with pytest.raises(PersistenceScopeError):
        run_experiment_fork(source, ticks=10)


def test_running_fork_cannot_change_canonical_world(tmp_path):
    source = build_canonical_repo(tmp_path)
    before = source.load_world().state_digest()
    fork, _ = create_experiment_fork(
        source,
        tmp_path / "exp.sqlite",
        experiment_id="EXP-004",
        condition="treatment",
        source_git_commit="6578e4f",
    )

    world = fork.load_world()
    world.add_mystery(
        {
            "public_label": "Experimental anomaly",
            "x": 5.0,
            "y": 5.0,
            "radius": 2.0,
            "effect": "energy_delta",
            "parameters": {"amount": 3.0},
        },
        source="experiment",
    )
    fork.save_world(world)
    run_experiment_fork(fork, ticks=200)

    assert source.load_world().state_digest() == before


def test_two_exact_forks_are_reproducible(tmp_path):
    source = build_canonical_repo(tmp_path)
    fork_a, _ = create_experiment_fork(
        source,
        tmp_path / "a.sqlite",
        experiment_id="EXP-005",
        condition="control-a",
        source_git_commit="6578e4f",
        run_id="RUN-A",
    )
    fork_b, _ = create_experiment_fork(
        source,
        tmp_path / "b.sqlite",
        experiment_id="EXP-005",
        condition="control-b",
        source_git_commit="6578e4f",
        run_id="RUN-B",
    )

    result_a = run_experiment_fork(fork_a, ticks=500)
    result_b = run_experiment_fork(fork_b, ticks=500)
    assert result_a.final_digest == result_b.final_digest


def test_reseed_is_explicitly_recorded_and_persists(tmp_path):
    source = build_canonical_repo(tmp_path)
    fork, manifest = create_experiment_fork(
        source,
        tmp_path / "seeded.sqlite",
        experiment_id="EXP-006",
        condition="reseeded",
        source_git_commit="6578e4f",
        experiment_seed=12345,
    )

    assert manifest.rng_reseeded is True
    assert manifest.experiment_seed == 12345
    assert manifest.initial_digest != manifest.source_digest

    result = run_experiment_fork(fork, ticks=50)
    restored = SQLiteRepository(fork.path)
    persisted = read_experiment_manifest(restored)
    assert persisted == result
    assert restored.load_world().state_digest() == result.final_digest
